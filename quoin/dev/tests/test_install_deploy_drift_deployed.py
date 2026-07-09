"""IVG-136 T-08: deploy_drift_check.py manifest + deployment test.

Tier 1 (CI, unskipped): installer manifest membership (adapter-only — DEPLOYED_SCRIPTS,
NOT CORE_SCRIPTS). Tier 2 (dev-machine only, skipif claude/npx absent): run install.sh
and assert the deployed script exists and `--help` exits 0.
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
SCRIPT_SRC = REPO_ROOT / "quoin" / "scripts" / "deploy_drift_check.py"


def _installer():
    spec = importlib.util.spec_from_file_location("_ddc_deployed_installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tier 1: manifest membership (runs on CI)
# ---------------------------------------------------------------------------

def test_in_deployed_scripts():
    mod = _installer()
    assert "deploy_drift_check.py" in mod.DEPLOYED_SCRIPTS


def test_not_in_core_scripts():
    mod = _installer()
    assert "deploy_drift_check.py" not in mod.CORE_SCRIPTS, (
        "deploy_drift_check.py is adapter-only (D-05) — must NOT be in CORE_SCRIPTS")


def test_source_file_exists():
    assert SCRIPT_SRC.is_file(), f"source not found at {SCRIPT_SRC}"


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
def test_install_deploys_script(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}")
    deployed = tmp_path / ".claude" / "scripts" / "deploy_drift_check.py"
    assert deployed.exists(), f"install.sh did not deploy — expected {deployed}"


@_dev_machine_only
def test_deployed_script_help_exits_zero(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0
    deployed = tmp_path / ".claude" / "scripts" / "deploy_drift_check.py"
    run = subprocess.run(
        ["python3", str(deployed), "--help"], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, f"--help failed: {run.stderr[:500]}"
