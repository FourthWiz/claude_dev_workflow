"""IVG-119 T-19: install.sh deploys lessons_guard.py to both targets.

Two-tier test (mirrors test_install_nested_root_check_deployed.py):

1. Non-skipped unit-level assertion: "lessons_guard.py" is in BOTH
   DEPLOYED_SCRIPTS and CORE_SCRIPTS (wrapped portable-core).
2. Deployment test (dev-machine only): wrapper + core twin land, wrapper --help
   exit 0 via the parents[1] loader.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "lessons_guard.py"
CORE_IMPL_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "lessons_guard.py"
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"


def _load_installer():
    import importlib.util

    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_installer_deployed_scripts_contains_lessons_guard():
    mod = _load_installer()
    assert "lessons_guard.py" in mod.DEPLOYED_SCRIPTS


def test_installer_core_scripts_contains_lessons_guard():
    mod = _load_installer()
    assert "lessons_guard.py" in mod.CORE_SCRIPTS, (
        "CORE_SCRIPTS must contain 'lessons_guard.py' or the wrapper's parents[1] loader "
        "fails at runtime."
    )


def test_source_files_exist():
    assert WRAPPER_SRC.is_file(), f"Wrapper source not found at {WRAPPER_SRC}."
    assert CORE_IMPL_SRC.is_file(), f"Core impl source not found at {CORE_IMPL_SRC}."


_SKIP_REASON = "install.sh requires `claude` (hard) and `npx` (soft); dev-machine only."
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
def test_install_deploys_wrapper_and_core(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0, (
        f"install.sh failed: rc={result.returncode}\n"
        f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
    )
    wrapper = tmp_path / ".claude" / "scripts" / "lessons_guard.py"
    core = tmp_path / ".claude" / "core" / "scripts" / "lessons_guard.py"
    assert wrapper.exists(), f"wrapper not deployed — expected at {wrapper}"
    assert core.exists(), f"core impl not deployed — expected at {core}"


@_dev_machine_only
def test_deployed_wrapper_imports_core(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0
    wrapper = tmp_path / ".claude" / "scripts" / "lessons_guard.py"
    assert wrapper.exists(), "install.sh did not deploy wrapper"
    run = subprocess.run(
        ["python3", str(wrapper), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert run.returncode == 0, (
        f"Deployed wrapper --help failed (rc={run.returncode}): {run.stderr[:500]}"
    )
