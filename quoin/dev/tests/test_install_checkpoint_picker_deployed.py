"""IVG-139 T-07: install.sh deploys checkpoint_picker.py to both targets.

Two-tier test (modelled verbatim on test_install_verify_claims_deployed.py):

1. Non-skipped unit-level assertion (runs on CI without `claude`):
   Import installer.py and assert "checkpoint_picker.py" is in BOTH
   DEPLOYED_SCRIPTS and CORE_SCRIPTS. This is the regression guard for the
   silent-skip failure mode (a wrapped script missing from either list fails
   at runtime — lessons-learned 2026-05-31).

2. Deployment test (dev-machine only — skipif claude/npx absent):
   Run install.sh and assert BOTH deployment targets are present:
     - wrapper at ~/.claude/scripts/checkpoint_picker.py
     - core impl at ~/.claude/core/scripts/checkpoint_picker.py
   Also asserts the deployed wrapper runs end-to-end against an empty
   memory dir and exits 0 (exercises the parents[1] loader; the module's
   CLI is fail-OPEN by construction — see checkpoint_picker.py main()).
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/ repo root
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "checkpoint_picker.py"
CORE_IMPL_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "checkpoint_picker.py"

INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"


# ---------------------------------------------------------------------------
# Tier 1: non-skipped unit-level assertion (runs on CI)
# ---------------------------------------------------------------------------


def test_installer_deployed_scripts_contains_checkpoint_picker():
    """DEPLOYED_SCRIPTS in installer.py must contain 'checkpoint_picker.py'.

    Missing entry means install.sh never deploys the adapter wrapper to
    ~/.claude/scripts/checkpoint_picker.py (R-04).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "checkpoint_picker.py" in mod.DEPLOYED_SCRIPTS, (
        "installer.py DEPLOYED_SCRIPTS must contain 'checkpoint_picker.py'. "
        "Missing entry means install.sh won't deploy the adapter wrapper to "
        "~/.claude/scripts/checkpoint_picker.py."
    )


def test_installer_core_scripts_contains_checkpoint_picker():
    """CORE_SCRIPTS in installer.py must contain 'checkpoint_picker.py'.

    Missing entry means the wrapper's parents[1] loader fails at runtime
    with a FileNotFoundError (R-04).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "checkpoint_picker.py" in mod.CORE_SCRIPTS, (
        "installer.py CORE_SCRIPTS must contain 'checkpoint_picker.py'. "
        "Missing entry means install.sh won't deploy the core impl to "
        "~/.claude/core/scripts/checkpoint_picker.py, causing the wrapper's "
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
        timeout=180,  # R-07: 2x baseline — subprocess is unavoidable here
    )


@_dev_machine_only
def test_install_deploys_checkpoint_picker_wrapper_and_core(tmp_path):
    """install.sh must deploy checkpoint_picker.py to both scripts/ and core/scripts/."""
    assert INSTALL_SH.is_file(), f"install.sh not found at {INSTALL_SH}"

    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
    )

    deployed_wrapper = tmp_path / ".claude" / "scripts" / "checkpoint_picker.py"
    assert deployed_wrapper.exists(), (
        f"install.sh did not deploy wrapper — expected at {deployed_wrapper}"
    )
    deployed_core = tmp_path / ".claude" / "core" / "scripts" / "checkpoint_picker.py"
    assert deployed_core.exists(), (
        f"install.sh did not deploy core impl — expected at {deployed_core}"
    )


@_dev_machine_only
def test_deployed_wrapper_runs_end_to_end(tmp_path):
    """Deployed wrapper must run against an empty memory dir and exit 0
    (exercises the parents[1] loader). The module is fail-OPEN (D-01/D-03):
    main() never raises, always exits 0, and prints a Verdict/error JSON.
    """
    result = _run_install(tmp_path)
    assert result.returncode == 0

    deployed_wrapper = tmp_path / ".claude" / "scripts" / "checkpoint_picker.py"
    assert deployed_wrapper.exists(), "install.sh did not deploy wrapper"

    empty_memory_dir = tmp_path / "empty_memory"
    empty_memory_dir.mkdir(parents=True, exist_ok=True)

    run = subprocess.run(
        ["python3", str(deployed_wrapper), "--memory-dir", str(empty_memory_dir), "--sid", "test-sid"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, (
        f"Deployed wrapper failed (rc={run.returncode}): {run.stdout[:500]} {run.stderr[:500]}"
    )
    assert run.stdout.strip(), "Deployed wrapper printed no output"
