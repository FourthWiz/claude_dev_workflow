"""IVG-138 T-08: ci_mirror.py manifest + deployment test.

Tier 1 (CI, unskipped): installer manifest membership. UNLIKE
deploy_drift_check.py (adapter-only — DEPLOYED_SCRIPTS only, asserted NOT in
CORE_SCRIPTS by its own test), ci_mirror.py has a portable-core twin (T-01)
and MUST be registered in BOTH DEPLOYED_SCRIPTS and CORE_SCRIPTS (T-03) — a
missing CORE_SCRIPTS entry breaks the deployed wrapper's `parents[1]/core/
scripts/` loader at runtime (lesson 2026-05-31 "add to BOTH lists"). This is
the required INVERSION of test_install_deploy_drift_deployed.py's
`test_not_in_core_scripts`: do NOT clone it verbatim, assert membership in
BOTH tuples instead of exclusion from one.

Tier 2 (dev-machine only, skipif claude/npx absent): run install.sh and
assert both the wrapper and the core impl were deployed.
"""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"
CORE_SCRIPT_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "ci_mirror.py"
WRAPPER_SCRIPT_SRC = REPO_ROOT / "quoin" / "scripts" / "ci_mirror.py"


def _installer():
    spec = importlib.util.spec_from_file_location("_ci_mirror_deployed_installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tier 1: manifest membership (runs on CI)
# ---------------------------------------------------------------------------

def test_in_deployed_scripts():
    mod = _installer()
    assert "ci_mirror.py" in mod.DEPLOYED_SCRIPTS


def test_in_core_scripts():
    # INVERSION WARNING (T-08): the deploy_drift_check.py template asserts its
    # script is NOT in CORE_SCRIPTS (adapter-only, no core twin). ci_mirror.py
    # is the opposite case — it MUST be in CORE_SCRIPTS. This is a positive
    # membership assertion, not an exclusion — do not collapse this back to a
    # `not in` check.
    mod = _installer()
    assert "ci_mirror.py" in mod.CORE_SCRIPTS, (
        "ci_mirror.py MUST be registered in CORE_SCRIPTS (it has a portable-core "
        "twin, unlike deploy_drift_check.py) — see lesson 2026-05-31")


def test_source_file_exists():
    assert CORE_SCRIPT_SRC.is_file(), f"core source not found at {CORE_SCRIPT_SRC}"
    assert WRAPPER_SCRIPT_SRC.is_file(), f"wrapper source not found at {WRAPPER_SCRIPT_SRC}"


# ---------------------------------------------------------------------------
# Tier 2: deployment test (dev-machine only)
# ---------------------------------------------------------------------------

_SKIP_REASON = (
    "install.sh requires `claude` (hard) and `npx` (soft); dev-machine only.")
_dev_machine_only = pytest.mark.skipif(
    shutil.which("claude") is None or shutil.which("npx") is None,
    reason=_SKIP_REASON,
)


def _run_install(tmp_home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=180,
    )


@_dev_machine_only
def test_install_deploys_both_copies(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}")
    deployed_wrapper = tmp_path / ".claude" / "scripts" / "ci_mirror.py"
    deployed_core = tmp_path / ".claude" / "core" / "scripts" / "ci_mirror.py"
    assert deployed_wrapper.exists(), f"install.sh did not deploy wrapper — expected {deployed_wrapper}"
    assert deployed_core.exists(), f"install.sh did not deploy core impl — expected {deployed_core}"


@_dev_machine_only
def test_deployed_wrapper_help_exits_zero(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0
    deployed_wrapper = tmp_path / ".claude" / "scripts" / "ci_mirror.py"
    run = subprocess.run(
        ["python3", str(deployed_wrapper), "--help"], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, f"--help failed: {run.stderr[:500]}"
