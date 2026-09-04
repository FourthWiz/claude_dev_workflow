"""IVG-258 stage 5 T-05: install.sh deploys compaction_telemetry.py to both targets.

Two-tier test, modelled on test_install_run_state_deployed.py:

1. Non-skipped unit-level assertions (run on CI without `claude`):
   - installer.py DEPLOYED_SCRIPTS and CORE_SCRIPTS both list
     compaction_telemetry.py.
   - Both the wrapper and core impl source files exist on disk.

2. Deployment test (dev-machine only — skipif claude/npx absent):
   Run install.sh and assert both the wrapper and the core twin land, and
   that each self-runs (--help exits 0) against the deployed copy.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "compaction_telemetry.py"
CORE_IMPL_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "compaction_telemetry.py"
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"


def _load_installer():
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_installer_deployed_scripts_contains_compaction_telemetry():
    mod = _load_installer()
    assert "compaction_telemetry.py" in mod.DEPLOYED_SCRIPTS, (
        "installer.py DEPLOYED_SCRIPTS must contain 'compaction_telemetry.py'."
    )


def test_installer_core_scripts_contains_compaction_telemetry():
    mod = _load_installer()
    assert "compaction_telemetry.py" in mod.CORE_SCRIPTS, (
        "installer.py CORE_SCRIPTS must contain 'compaction_telemetry.py' — the "
        "wrapper's parents[1] loader fails at runtime otherwise."
    )


def test_source_files_exist():
    assert WRAPPER_SRC.is_file(), f"Wrapper source not found at {WRAPPER_SRC}."
    assert CORE_IMPL_SRC.is_file(), f"Core impl source not found at {CORE_IMPL_SRC}."


_SKIP_REASON = (
    "install.sh requires `claude` (hard) and `npx` (soft); dev-machine only."
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


@pytest.fixture(scope="module")
def _installed_home(tmp_path_factory):
    """Both deployment tests below share ONE install.sh run (mirrors the
    run_state.py precedent's module-scoped fixture)."""
    tmp_home = tmp_path_factory.mktemp("compaction-telemetry-deployed-home")
    result = _run_install(tmp_home)
    return tmp_home, result


@_dev_machine_only
def test_install_deploys_wrapper_and_core(_installed_home):
    tmp_home, result = _installed_home
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
    )
    wrapper = tmp_home / ".claude" / "scripts" / "compaction_telemetry.py"
    core = tmp_home / ".claude" / "core" / "scripts" / "compaction_telemetry.py"
    assert wrapper.exists(), f"wrapper not deployed — expected at {wrapper}"
    assert core.exists(), f"core impl not deployed — expected at {core}"


@_dev_machine_only
def test_deployed_wrapper_self_test(_installed_home):
    tmp_home, result = _installed_home
    assert result.returncode == 0
    wrapper = tmp_home / ".claude" / "scripts" / "compaction_telemetry.py"
    assert wrapper.exists(), "install.sh did not deploy wrapper"
    run = subprocess.run(
        ["python3", str(wrapper), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, (
        f"Deployed wrapper --help failed (rc={run.returncode}): {run.stderr[:500]}"
    )
    core = tmp_home / ".claude" / "core" / "scripts" / "compaction_telemetry.py"
    run_core = subprocess.run(
        ["python3", str(core), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run_core.returncode == 0, (
        f"Deployed core --help failed (rc={run_core.returncode}): {run_core.stderr[:500]}"
    )
