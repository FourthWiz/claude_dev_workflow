"""IVG-75 T-04: tests for find_drive_conflicts sweep script.

Two-tier structure:

1. Tier 1 (CI-safe, no `claude`):
   Import installer.py via importlib and assert "find_drive_conflicts.py"
   is present in BOTH DEPLOYED_SCRIPTS and CORE_SCRIPTS. Also asserts both
   source files exist in the repo. Mirrors test_install_branch_hygiene_deployed.py.

2. Behavior tests (tmp_path, no external deps):
   Build fixture trees, call the core scan/quarantine/delete API directly.
   Covers dry-run listing, --quarantine move semantics (including directories),
   --delete, .git pruning, parity negatives, and parity positives.
   Slow-FS tests (genuine FS ops) are marked @pytest.mark.slow_fs.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/ repo root
INSTALLER_PY = REPO_ROOT / "src" / "quoin" / "installer.py"
WRAPPER_SRC = REPO_ROOT / "quoin" / "scripts" / "find_drive_conflicts.py"
CORE_IMPL_SRC = REPO_ROOT / "quoin" / "core" / "scripts" / "find_drive_conflicts.py"

# ---------------------------------------------------------------------------
# Tier 1: installer membership (CI-safe, no claude binary)
# ---------------------------------------------------------------------------


def _load_installer():
    spec = importlib.util.spec_from_file_location("installer", INSTALLER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_installer_deployed_scripts_contains_find_drive_conflicts():
    """DEPLOYED_SCRIPTS must contain find_drive_conflicts.py (wrapper deployment guard)."""
    mod = _load_installer()
    assert "find_drive_conflicts.py" in mod.DEPLOYED_SCRIPTS, (
        "installer.py DEPLOYED_SCRIPTS must contain 'find_drive_conflicts.py'. "
        "Missing entry means install.sh won't deploy the wrapper to "
        "~/.claude/scripts/find_drive_conflicts.py."
    )


def test_installer_core_scripts_contains_find_drive_conflicts():
    """CORE_SCRIPTS must contain find_drive_conflicts.py (wrapper loader guard)."""
    mod = _load_installer()
    assert "find_drive_conflicts.py" in mod.CORE_SCRIPTS, (
        "installer.py CORE_SCRIPTS must contain 'find_drive_conflicts.py'. "
        "Missing entry means the wrapper's parents[1] loader fails at runtime."
    )


def test_source_files_exist():
    """Both source files must exist in the repo."""
    assert WRAPPER_SRC.is_file(), f"Wrapper source missing: {WRAPPER_SRC}"
    assert CORE_IMPL_SRC.is_file(), f"Core impl source missing: {CORE_IMPL_SRC}"


def test_wrapper_help_exits_zero():
    """Wrapper --help must exit 0 (exercises the importlib loader chain)."""
    result = subprocess.run(
        [sys.executable, str(WRAPPER_SRC), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--help failed:\n{result.stderr}"
    assert "find_drive_conflicts" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_core():
    """Load the core module directly for behaviour tests."""
    spec = importlib.util.spec_from_file_location("_fdc_core", CORE_IMPL_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Regex unit tests (fast, no I/O)
# ---------------------------------------------------------------------------

FDC = _load_core()


@pytest.mark.parametrize("name", [
    "a 2.md",
    "report 3.pdf",
    "notes 2.tar.gz",
    "foo 10.md",
    "a 100.md",
    "next_steps 2",
    "x 2.py",
    "bar 2",         # extensionless directory name
])
def test_is_drive_conflict_matches_positives(name):
    """Conservative regex must match known Drive conflict copy shapes."""
    assert FDC.is_drive_conflict(name), f"Expected match for: {name!r}"


@pytest.mark.parametrize("name", [
    "version 2.0 release notes.md",   # space in tail after .0
    "chapter 3.1 intro.md",           # space in tail
    "build 2.0.1 notes.txt",          # space in tail
    "a 1000.md",                      # 4-digit — exceeds cap
    "v2.py",                          # no leading space+digit
    "step 2 notes.md",                # space before end
    "config 2nd.py",                  # non-digit after digit
    "test_quoin2.py",                 # no space+digit prefix
])
def test_is_drive_conflict_rejects_negatives(name):
    """Conservative regex must NOT match legitimate file names."""
    assert not FDC.is_drive_conflict(name), f"Unexpected match for: {name!r}"


# ---------------------------------------------------------------------------
# Behavior tests (tmp_path, slow_fs)
# ---------------------------------------------------------------------------

def _build_fixture(root: Path) -> None:
    """Populate root with a mix of conflict copies and legitimate files."""
    # Conflict-copy files
    (root / "foo 2.py").write_text("conflict copy")
    (root / "notes 2.tar.gz").write_text("conflict tarball")
    (root / "a 100.md").write_text("conflict 3-digit")
    # Conflict-copy directory (with a real nested file)
    conflict_dir = root / "bar 2"
    conflict_dir.mkdir()
    (conflict_dir / "real_file.txt").write_text("real content")
    # Legitimate files (must NOT be matched)
    (root / "baz.py").write_text("real script")
    (root / "version 2.0 release notes.md").write_text("real notes")
    (root / "a 1000.md").write_text("real 4-digit")
    (root / "step 2 notes.md").write_text("real step notes")
    # Simulated .git directory with conflict-shaped internals (must be pruned)
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "index 2").write_text("git internal")


@pytest.mark.slow_fs
def test_dry_run_lists_matches(tmp_path):
    """Dry-run scan must list conflict copies and leave all files on disk."""
    _build_fixture(tmp_path)
    matches = FDC.scan(tmp_path)
    match_names = {p.name for p in matches}
    # Conflict copies found
    assert "foo 2.py" in match_names
    assert "notes 2.tar.gz" in match_names
    assert "a 100.md" in match_names
    assert "bar 2" in match_names
    # Legitimate files not matched
    assert "baz.py" not in match_names
    assert "version 2.0 release notes.md" not in match_names
    assert "a 1000.md" not in match_names
    assert "step 2 notes.md" not in match_names
    # All original files still on disk (no changes)
    assert (tmp_path / "foo 2.py").exists()
    assert (tmp_path / "bar 2").is_dir()
    assert (tmp_path / "baz.py").exists()


@pytest.mark.slow_fs
def test_git_directory_pruned(tmp_path):
    """Items inside .git must never be reported (hard-exclude .git)."""
    _build_fixture(tmp_path)
    matches = FDC.scan(tmp_path)
    match_paths = {str(p) for p in matches}
    # .git/index 2 must not appear in matches
    git_conflict = str(tmp_path / ".git" / "index 2")
    assert git_conflict not in match_paths


@pytest.mark.slow_fs
def test_quarantine_moves_files_and_dirs(tmp_path):
    """--quarantine must move conflict copies to the quarantine dir, leaving legit files."""
    _build_fixture(tmp_path)
    matches = FDC.scan(tmp_path)
    FDC.quarantine(matches, tmp_path)

    # Originals are gone
    assert not (tmp_path / "foo 2.py").exists()
    assert not (tmp_path / "bar 2").exists()

    # Legitimate files untouched
    assert (tmp_path / "baz.py").exists()
    assert (tmp_path / "version 2.0 release notes.md").exists()

    # Quarantine directory exists with the conflict copies
    q_dirs = list((tmp_path / ".drive-conflicts-quarantine").iterdir())
    assert len(q_dirs) == 1, "Expected one date subfolder in quarantine"
    q_date = q_dirs[0]
    assert (q_date / "foo 2.py").exists()
    # bar 2/ was quarantined as a unit — real_file.txt must be inside it
    assert (q_date / "bar 2" / "real_file.txt").exists()


@pytest.mark.slow_fs
def test_quarantine_preserves_relative_subpath(tmp_path):
    """Quarantine must preserve the relative subpath to avoid collisions at different depths."""
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "notes 2.md").write_text("conflict in subdir")
    (tmp_path / "notes 2.md").write_text("conflict at root")

    matches = FDC.scan(tmp_path)
    FDC.quarantine(matches, tmp_path)

    import datetime
    today = datetime.date.today().isoformat()
    q_base = tmp_path / ".drive-conflicts-quarantine" / today

    # Both paths preserved — no collision
    assert (q_base / "notes 2.md").exists()
    assert (q_base / "subdir" / "notes 2.md").exists()


@pytest.mark.slow_fs
def test_delete_removes_matches(tmp_path):
    """--delete must permanently remove conflict copies; legit files untouched."""
    _build_fixture(tmp_path)
    matches = FDC.scan(tmp_path)
    FDC.delete(matches)

    assert not (tmp_path / "foo 2.py").exists()
    assert not (tmp_path / "bar 2").exists()
    assert not (tmp_path / "notes 2.tar.gz").exists()

    # Legitimate files still present
    assert (tmp_path / "baz.py").exists()
    assert (tmp_path / "version 2.0 release notes.md").exists()
    assert (tmp_path / "a 1000.md").exists()


@pytest.mark.slow_fs
def test_parity_positives(tmp_path):
    """Additional parity positives from D-01 must be matched."""
    (tmp_path / "notes 2.tar.gz").write_text("multi-ext conflict")
    (tmp_path / "a 100.md").write_text("3-digit conflict")
    matches = FDC.scan(tmp_path)
    match_names = {p.name for p in matches}
    assert "notes 2.tar.gz" in match_names
    assert "a 100.md" in match_names


@pytest.mark.slow_fs
def test_parity_negatives(tmp_path):
    """Additional parity negatives from D-01 must NOT be matched."""
    (tmp_path / "version 2.0 release notes.md").write_text("legitimate")
    (tmp_path / "a 1000.md").write_text("legitimate 4-digit")
    (tmp_path / "v2.py").write_text("legitimate")
    (tmp_path / "config 2nd.py").write_text("legitimate")
    (tmp_path / "step 2 notes.md").write_text("legitimate")
    matches = FDC.scan(tmp_path)
    assert not matches, f"Expected no matches, got: {[p.name for p in matches]}"


@pytest.mark.slow_fs
def test_json_output(tmp_path):
    """--json flag must output a JSON array of matched paths."""
    (tmp_path / "foo 2.py").write_text("conflict")
    (tmp_path / "baz.py").write_text("legit")

    result = subprocess.run(
        [sys.executable, str(WRAPPER_SRC), "--json", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    import json
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert any("foo 2.py" in p for p in data)
    assert all("baz.py" not in p for p in data)
