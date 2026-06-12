"""T-09: Installer deploy tests for spend_monitor.py (IVG-62).

Verifies:
1. "spend_monitor.py" is in BOTH DEPLOYED_SCRIPTS and CORE_SCRIPTS in installer.py
   (lessons-learned 2026: missing EITHER breaks the wrapper's parents[1]/core/scripts/ resolution)
2. deploy_scripts + deploy_core_scripts copy both files to a temp dest without sys.exit(1)
3. Both dest/scripts/spend_monitor.py and dest/core/scripts/spend_monitor.py exist after deploy.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

sys.path.insert(0, str(REPO_ROOT / "src"))
from quoin.installer import CORE_SCRIPTS, DEPLOYED_SCRIPTS, deploy_core_scripts, deploy_scripts  # noqa: E402  # type: ignore[import]


# ---------------------------------------------------------------------------
# T-09a: membership tests (fast, no file I/O)
# ---------------------------------------------------------------------------

def test_spend_monitor_in_deployed_scripts():
    """spend_monitor.py must be in DEPLOYED_SCRIPTS (wrapper)."""
    assert "spend_monitor.py" in DEPLOYED_SCRIPTS, (
        "spend_monitor.py missing from DEPLOYED_SCRIPTS in installer.py. "
        "Adding only one of DEPLOYED_SCRIPTS / CORE_SCRIPTS breaks the parents[1] path resolution "
        "in the wrapper at runtime."
    )


def test_spend_monitor_in_core_scripts():
    """spend_monitor.py must be in CORE_SCRIPTS (core impl)."""
    assert "spend_monitor.py" in CORE_SCRIPTS, (
        "spend_monitor.py missing from CORE_SCRIPTS in installer.py. "
        "Both lists are required — wrapper loads from parents[1]/core/scripts/."
    )


# ---------------------------------------------------------------------------
# T-09b: deploy function tests (file-based)
# ---------------------------------------------------------------------------

@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a minimal source directory with stub spend_monitor.py in BOTH locations."""
    src = tmp_path / "source"

    # Adapter wrapper: quoin/scripts/spend_monitor.py
    scripts_dir = src / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "spend_monitor.py").write_text(
        "# stub spend_monitor.py wrapper\npass\n", encoding="utf-8"
    )

    # Core impl: quoin/core/scripts/spend_monitor.py
    core_scripts_dir = src / "core" / "scripts"
    core_scripts_dir.mkdir(parents=True)
    (core_scripts_dir / "spend_monitor.py").write_text(
        "# stub spend_monitor.py core\npass\n", encoding="utf-8"
    )

    # Add stubs for all other DEPLOYED_SCRIPTS and CORE_SCRIPTS so deploy_* don't fail
    for fname in DEPLOYED_SCRIPTS:
        stub = scripts_dir / fname
        if not stub.exists():
            stub.write_text(f"# stub {fname}\n", encoding="utf-8")
    for fname in CORE_SCRIPTS:
        stub = core_scripts_dir / fname
        if not stub.exists():
            stub.write_text(f"# stub {fname}\n", encoding="utf-8")

    return src


@pytest.fixture
def dest_root(tmp_path: Path) -> Path:
    """Create a temp dest root."""
    d = tmp_path / "dest"
    d.mkdir()
    return d


def test_deploy_scripts_lands_spend_monitor_wrapper(source_dir, dest_root):
    """deploy_scripts copies spend_monitor.py to dest/scripts/ (adapter wrapper)."""
    deploy_scripts(source_dir, dest_root)
    wrapper_path = dest_root / "scripts" / "spend_monitor.py"
    assert wrapper_path.exists(), (
        f"spend_monitor.py wrapper not found at {wrapper_path} after deploy_scripts"
    )


def test_deploy_core_scripts_lands_spend_monitor_impl(source_dir, dest_root):
    """deploy_core_scripts copies spend_monitor.py to dest/core/scripts/ (core impl)."""
    deploy_core_scripts(source_dir, dest_root)
    impl_path = dest_root / "core" / "scripts" / "spend_monitor.py"
    assert impl_path.exists(), (
        f"spend_monitor.py core impl not found at {impl_path} after deploy_core_scripts"
    )


def test_both_paths_land_after_both_deploys(source_dir, dest_root):
    """Both wrapper and core impl land when both deploy functions are called."""
    deploy_scripts(source_dir, dest_root)
    deploy_core_scripts(source_dir, dest_root)

    wrapper = dest_root / "scripts" / "spend_monitor.py"
    impl = dest_root / "core" / "scripts" / "spend_monitor.py"
    assert wrapper.exists(), f"Wrapper missing: {wrapper}"
    assert impl.exists(), f"Core impl missing: {impl}"
