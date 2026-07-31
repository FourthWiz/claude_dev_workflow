"""Unit tests for nested_root_check.py (IVG-119, T-01).

Golden synthetic tree mirroring this workspace's real nested-root corpus, plus an
exit-code / fail-OPEN / exclusion matrix. Imports the portable-core implementation
directly (no subprocess needed for exit codes — main() returns the int).
"""

import os
import sys
from pathlib import Path

import pytest

# Add core scripts dir so `from path_resolve import ...` inside the module resolves,
# and so we import the portable implementation under test.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core" / "scripts"))
import nested_root_check as nrc  # noqa: E402
from nested_root_check import find_descendant_roots, main  # noqa: E402


# Stray dir whose NAME is the argparse usage text (not `.workflow_artifacts`), but
# which contains a `.workflow_artifacts` child — the real-world generator bug (MIN-5).
_STRAY_NAME = (
    "usage: path_resolve.py [-h] --task TASK_NAME [--stage N_OR_NAME]\n"
    "                       [--project-root PATH]"
)


def _mkroot(parent: Path) -> Path:
    d = parent / ".workflow_artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def tree(tmp_path):
    """Build the golden synthetic project tree; return project_root."""
    root = tmp_path
    # Canonical root (legit — must NEVER be a finding).
    _mkroot(root)
    # Genuine accidental nested roots.
    _mkroot(root / "quoin")
    _mkroot(root / "quoin" / "quoin")
    _mkroot(root / "quoin" / "vscode-extension")
    _mkroot(root / ".workflow_artifacts" / "memory")
    _mkroot(root / ".workflow_artifacts" / "serena-memory-dashboard")
    # Two under finalized/*/ (flagged by default).
    _mkroot(root / ".workflow_artifacts" / "finalized" / "task-alpha")
    _mkroot(root / ".workflow_artifacts" / "finalized" / "task-beta")
    # Stray argparse-usage-named dir with a nested child (child IS the finding).
    _mkroot(root / _STRAY_NAME)
    # Fixtures subtree — must be pruned/excluded entirely.
    _mkroot(root / "quoin" / "quoin" / "dev" / "tests" / "fixtures" / "sample")
    return root


def _finding_strs(root, **kw):
    return {str(p) for p in find_descendant_roots(root, **kw)}


def test_canonical_root_not_flagged(tree):
    found = _finding_strs(tree)
    assert str(tree / ".workflow_artifacts") not in found


def test_genuine_nested_roots_found(tree):
    found = _finding_strs(tree)
    for rel in (
        Path("quoin") / ".workflow_artifacts",
        Path("quoin") / "quoin" / ".workflow_artifacts",
        Path("quoin") / "vscode-extension" / ".workflow_artifacts",
        Path(".workflow_artifacts") / "memory" / ".workflow_artifacts",
        Path(".workflow_artifacts") / "serena-memory-dashboard" / ".workflow_artifacts",
    ):
        assert str(tree / rel) in found


def test_stray_argparse_dir_child_found(tree):
    """MIN-5: the stray dir isn't named .workflow_artifacts; its child IS the finding."""
    found = _finding_strs(tree)
    assert str(tree / _STRAY_NAME / ".workflow_artifacts") in found


def test_finalized_flagged_by_default(tree):
    found = _finding_strs(tree)
    assert str(tree / ".workflow_artifacts" / "finalized" / "task-alpha" / ".workflow_artifacts") in found
    assert str(tree / ".workflow_artifacts" / "finalized" / "task-beta" / ".workflow_artifacts") in found


def test_fixtures_subtree_excluded(tree):
    found = _finding_strs(tree)
    assert not any(os.path.join("dev", "tests", "fixtures") in f for f in found)


def test_exclude_finalized_flag(tree):
    with_fin = _finding_strs(tree, include_finalized=True)
    without_fin = _finding_strs(tree, include_finalized=False)
    dropped = with_fin - without_fin
    assert dropped == {
        str(tree / ".workflow_artifacts" / "finalized" / "task-alpha" / ".workflow_artifacts"),
        str(tree / ".workflow_artifacts" / "finalized" / "task-beta" / ".workflow_artifacts"),
    }


def test_env_exclude_finalized_substring(tree, monkeypatch):
    monkeypatch.setenv("QUOIN_NESTED_ROOT_EXCLUDE", "finalized/")
    found = _finding_strs(tree)
    assert not any((os.sep + "finalized" + os.sep) in f for f in found)


def test_marker_blesses_one_root(tree):
    blessed = tree / "quoin" / ".workflow_artifacts"
    (blessed / ".quoin-nested-ok").write_text("ok\n")
    found = _finding_strs(tree)
    assert str(blessed) not in found
    # Sibling nested roots remain flagged.
    assert str(tree / "quoin" / "quoin" / ".workflow_artifacts") in found


def test_exit_1_on_nested(tree):
    assert main(["--project-root", str(tree), "--format", "json"]) == 1


def test_exit_0_on_fixture_only_tree(tmp_path):
    _mkroot(tmp_path)  # canonical only
    _mkroot(tmp_path / "pkg" / "dev" / "tests" / "fixtures" / "case")
    assert main(["--project-root", str(tmp_path), "--format", "json"]) == 0


def test_exit_0_disable_knob(tree, monkeypatch):
    monkeypatch.setenv("QUOIN_DISABLE_NESTED_ROOT_CHECK", "1")
    assert main(["--project-root", str(tree)]) == 0


def test_exit_3_fail_open_on_oserror(tree, monkeypatch):
    def _boom(*_a, **_k):
        raise OSError("simulated walk failure")

    monkeypatch.setattr(nrc.os, "walk", _boom)
    assert main(["--project-root", str(tree)]) == 3


def test_argparse_error_exit_2(tree):
    with pytest.raises(SystemExit) as exc:
        main(["--format", "bogus"])
    assert exc.value.code == 2


def test_workspaces_subtree_pruned(tree):
    """T-06 (IVG-158 R-09): .workspaces subtree is pruned before descent — a deeply
    nested .workflow_artifacts inside a workspace worktree must NOT be found, while
    a genuine nested root OUTSIDE .workspaces still IS — proving the prune is scoped
    to .workspaces, not a blanket suppression."""
    # The trap: a deep nested root inside a workspace worktree.
    _mkroot(tree / ".workspaces" / "feat" / "repoA" / "sub")
    # Simulate the worktree shape: a `.git` FILE (not dir), documenting the R-09
    # rationale (a `.git` file is not pruned like a `.git` dir would be).
    git_file_dir = tree / ".workspaces" / "feat" / "repoA"
    git_file_dir.mkdir(parents=True, exist_ok=True)
    (git_file_dir / ".git").write_text("gitdir: /elsewhere/.git/worktrees/repoA\n")
    # A genuine nested root OUTSIDE .workspaces — must still be flagged.
    _mkroot(tree / "pkg")

    found = _finding_strs(tree)

    assert not any(".workspaces" in f for f in found), (
        f".workspaces subtree should be pruned before descent, but found: "
        f"{[f for f in found if '.workspaces' in f]}"
    )
    assert str(tree / "pkg" / ".workflow_artifacts") in found
    assert str(tree / ".workflow_artifacts") not in found
