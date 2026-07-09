"""IVG-115 T-03: install.sh deploys verify_claims.py to both targets.

Two-tier test (modelled verbatim on test_install_affected_tests_deployed.py):

1. Non-skipped unit-level assertion (runs on CI without `claude`):
   Import installer.py and assert "verify_claims.py" is in BOTH
   DEPLOYED_SCRIPTS and CORE_SCRIPTS. This is the regression guard for the
   silent-skip failure mode (a wrapped script missing from either list fails
   at runtime — lessons-learned 2026-05-31).

2. Deployment test (dev-machine only — skipif claude/npx absent):
   Run install.sh and assert BOTH deployment targets are present:
     - wrapper at ~/.claude/scripts/verify_claims.py
     - core impl at ~/.claude/core/scripts/verify_claims.py
   Also asserts the deployed wrapper's --self-test exits 0 post-deploy
   (exercises the parents[1] loader end-to-end, per T-03 acceptance).
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/ repo root
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "verify_claims.py"
CORE_IMPL_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "verify_claims.py"

INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"


# ---------------------------------------------------------------------------
# Tier 1: non-skipped unit-level assertion (runs on CI)
# ---------------------------------------------------------------------------


def test_installer_deployed_scripts_contains_verify_claims():
    """DEPLOYED_SCRIPTS in installer.py must contain 'verify_claims.py'.

    Missing entry means install.sh never deploys the adapter wrapper to
    ~/.claude/scripts/verify_claims.py (R-04).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "verify_claims.py" in mod.DEPLOYED_SCRIPTS, (
        "installer.py DEPLOYED_SCRIPTS must contain 'verify_claims.py'. "
        "Missing entry means install.sh won't deploy the adapter wrapper to "
        "~/.claude/scripts/verify_claims.py."
    )


def test_installer_core_scripts_contains_verify_claims():
    """CORE_SCRIPTS in installer.py must contain 'verify_claims.py'.

    Missing entry means the wrapper's parents[1] loader fails at runtime
    with a FileNotFoundError (R-04).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "verify_claims.py" in mod.CORE_SCRIPTS, (
        "installer.py CORE_SCRIPTS must contain 'verify_claims.py'. "
        "Missing entry means install.sh won't deploy the core impl to "
        "~/.claude/core/scripts/verify_claims.py, causing the wrapper's "
        "parents[1] loader to fail at runtime."
    )


def test_source_files_exist():
    """Source files for both targets must exist in the repo."""
    assert WRAPPER_SRC.is_file(), (
        f"Wrapper source not found at {WRAPPER_SRC}. "
        "This file must exist for install.sh to deploy it."
    )
    assert CORE_IMPL_SRC.is_file(), (
        f"Core impl source not found at {CORE_IMPL_SRC}. "
        "This file must exist for install.sh to deploy it."
    )


# ---------------------------------------------------------------------------
# Tier 2: deployment test (dev-machine only)
# ---------------------------------------------------------------------------

_SKIP_REASON = (
    "install.sh requires `claude` (hard) and `npx` (soft); test is dev-machine only. "
    "install.sh aborts on missing claude, so test cannot run on CI."
)
_dev_machine_only = pytest.mark.skipif(
    shutil.which("claude") is None or shutil.which("npx") is None,
    reason=_SKIP_REASON,
)


def _run_install(tmp_home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=180,
    )


@_dev_machine_only
def test_install_deploys_verify_claims_wrapper_and_core(tmp_path):
    """install.sh must deploy verify_claims.py to both scripts/ and core/scripts/."""
    assert INSTALL_SH.is_file(), f"install.sh not found at {INSTALL_SH}"

    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
    )

    deployed_wrapper = tmp_path / ".claude" / "scripts" / "verify_claims.py"
    assert deployed_wrapper.exists(), (
        f"install.sh did not deploy wrapper — expected at {deployed_wrapper}"
    )
    deployed_core = tmp_path / ".claude" / "core" / "scripts" / "verify_claims.py"
    assert deployed_core.exists(), (
        f"install.sh did not deploy core impl — expected at {deployed_core}"
    )


@_dev_machine_only
def test_deployed_wrapper_self_test_passes(tmp_path):
    """Deployed wrapper's --self-test must exit 0 (exercises the parents[1] loader)."""
    result = _run_install(tmp_path)
    assert result.returncode == 0

    deployed_wrapper = tmp_path / ".claude" / "scripts" / "verify_claims.py"
    assert deployed_wrapper.exists(), "install.sh did not deploy wrapper"

    run = subprocess.run(
        ["python3", str(deployed_wrapper), "--self-test"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, (
        f"Deployed wrapper --self-test failed (rc={run.returncode}): {run.stdout[:500]} {run.stderr[:500]}"
    )


# ---------------------------------------------------------------------------
# T-09 extension: inject_verification_step.py must also deploy (DEPLOYED-only,
# standalone generator — no CORE_SCRIPTS counterpart, per T-04).
# ---------------------------------------------------------------------------

GENERATOR_SRC = REPO_ROOT / "quoin" / "scripts" / "inject_verification_step.py"


def test_installer_deployed_scripts_contains_inject_verification_step():
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "inject_verification_step.py" in mod.DEPLOYED_SCRIPTS, (
        "installer.py DEPLOYED_SCRIPTS must contain 'inject_verification_step.py'. "
        "Missing entry means install.sh won't deploy the §V block generator to "
        "~/.claude/scripts/inject_verification_step.py."
    )


def test_generator_source_file_exists():
    assert GENERATOR_SRC.is_file(), (
        f"Generator source not found at {GENERATOR_SRC}. "
        "This file must exist for install.sh to deploy it."
    )


@_dev_machine_only
def test_install_deploys_inject_verification_step(tmp_path):
    """install.sh must deploy inject_verification_step.py to scripts/."""
    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
    )

    deployed = tmp_path / ".claude" / "scripts" / "inject_verification_step.py"
    assert deployed.exists(), (
        f"install.sh did not deploy inject_verification_step.py — expected at {deployed}"
    )
