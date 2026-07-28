"""T-09 (IVG-141): install.sh deploys boundary_checkpoint.py + roster membership.

Mirrors test_install_session_age_guard_deployed.py. The roster-membership check
is import-free (text-parse of src/quoin/installer.py — NEVER `import quoin`) and
runs everywhere; the live install/deploy check is dev-machine-only.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"
CORE_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "boundary_checkpoint.py"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "boundary_checkpoint.py"

SCRIPT = "boundary_checkpoint.py"


def _roster(name: str) -> list[str]:
    """Line-based extraction (comments contain stray `)`, so a non-greedy paren
    match would truncate the roster early)."""
    entries: list[str] = []
    collecting = False
    for ln in INSTALLER_PY.read_text(encoding="utf-8").splitlines():
        if not collecting:
            if re.match(rf"\s*{name}\s*=\s*\(", ln):
                collecting = True
            continue
        if ln.startswith(")"):
            break
        entries += re.findall(r'"([^"]+\.py)"', ln)
    assert entries, f"{name} tuple not found / empty in installer.py"
    return entries


def test_in_deployed_and_core_scripts():
    assert SCRIPT in _roster("DEPLOYED_SCRIPTS")
    assert SCRIPT in _roster("CORE_SCRIPTS")


def test_source_files_exist():
    assert CORE_SRC.exists(), f"core impl missing: {CORE_SRC}"
    assert WRAPPER_SRC.exists(), f"wrapper missing: {WRAPPER_SRC}"


pytestmark = pytest.mark.skipif(
    shutil.which("claude") is None or shutil.which("npx") is None,
    reason="install.sh requires `claude` (hard) and `npx` (soft); dev-machine only.",
)


def _run_install(tmp_home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env, capture_output=True, text=True,
        cwd=str(REPO_ROOT), timeout=180,
    )


def test_install_deploys_boundary_checkpoint(tmp_path):
    result = _run_install(tmp_path)
    assert result.returncode == 0, result.stderr[:1500]
    deployed = tmp_path / ".claude" / "scripts" / SCRIPT
    assert deployed.exists(), f"install.sh did not deploy {SCRIPT}"
    assert deployed.read_bytes() == WRAPPER_SRC.read_bytes()
    assert os.access(str(deployed), os.X_OK)
