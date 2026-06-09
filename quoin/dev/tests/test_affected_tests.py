"""Unit tests for quoin.core.scripts.affected_tests.

Tests are hermetic — they use git init in tmp_path and do NOT depend on
the real quoin tree or the network.

Coverage:
  - name-match: changed foo.py with test_foo.py -> selector
  - import-graph (whole-word \b{S}\b) with the real quoin dynamic-loader idiom
  - unmatched source: orphan.py with zero references -> unmatched_sources; exit 3
    without --allow-unmatched; exit 0 with --allow-unmatched when pytest passes
  - changed test file selected directly
  - --select-only does not invoke pytest (ran_pytest=False)
  - git-root resolution (CRIT-1): outer non-git dir with child git repo
  - diff-basis fallback (CRIT-2): HEAD==main + dirty .py -> worktree fallback
  - F-01 fix: committed .py source on branch with no upstream, clean worktree
    -> base-branch-diff (NOT no-changes)
  - F-01 end-to-end: committed-clean no-upstream branch + red test -> exit 1
  - F-02 fix: --allow-unmatched + single unmatched source, empty selectors -> exit 0
  - exit-code matrix: 0a, 0c, 1, 4, 2
  - docs-only branch (MAJ-1): .md/.json/SKILL.md only -> exit 0, ran_pytest=False,
    pytest NOT invoked (subprocess.run spy), exit_reason=docs-only-no-selectors
  - QUOIN_DISABLE_AFFECTED_TESTS=1 -> exit 3 + {"disabled": true}
  - determinism: selector list is sorted/stable
  - no --base flag (MIN-1)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helper: load the core module from its canonical source path (hermetic)
# ---------------------------------------------------------------------------

_CORE_PATH = Path(__file__).resolve().parents[2] / "core" / "scripts" / "affected_tests.py"


def _load_core():
    spec = importlib.util.spec_from_file_location("_quoin_core_affected_tests_test", _CORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_at = _load_core()


# ---------------------------------------------------------------------------
# Fixture: tiny fake repo tree (no git)
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_repo(tmp_path):
    """Create a minimal fake repo with sources + test files (no git)."""
    # Source files
    (tmp_path / "foo.py").write_text("def foo(): pass\n")
    (tmp_path / "bar.py").write_text("def bar(): pass\n")
    (tmp_path / "orphan.py").write_text("def orphan(): pass\n")

    # Test files
    (tmp_path / "test_foo.py").write_text("# tests for foo\nimport foo\ndef test_foo(): pass\n")
    # test_misc.py uses the quoin dynamic-loader idiom for bar
    (tmp_path / "test_misc.py").write_text(
        "import importlib.util\n"
        "import sys\n"
        "from pathlib import Path\n"
        "_CORE_PATH = Path(__file__).resolve().parent / 'bar.py'\n"
        "_SPEC = importlib.util.spec_from_file_location('_quoin_core_bar_test', _CORE_PATH)\n"
        "_CORE = importlib.util.module_from_spec(_SPEC)\n"
        "sys.modules[_SPEC.name] = _CORE\n"
        "_SPEC.loader.exec_module(_CORE)\n"
        "def test_bar(): pass\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# map_changed_to_tests
# ---------------------------------------------------------------------------

class TestMapChangedToTests:
    def test_name_match(self, fake_repo):
        """foo.py -> test_foo.py via name-match."""
        selectors, unmatched, ignored = _at.map_changed_to_tests(["foo.py"], fake_repo)
        assert any("test_foo.py" in s for s in selectors), f"expected test_foo.py in {selectors}"
        assert not unmatched
        assert not ignored

    def test_import_graph_whole_word(self, fake_repo):
        """bar.py has no test_bar.py but test_misc.py contains \\bbar\\b."""
        selectors, unmatched, ignored = _at.map_changed_to_tests(["bar.py"], fake_repo)
        assert any("test_misc.py" in s for s in selectors), (
            f"expected test_misc.py via whole-word grep, got {selectors}"
        )
        assert not unmatched, f"expected no unmatched, got {unmatched}"

    def test_unmatched_source(self, fake_repo):
        """orphan.py has no test anywhere -> unmatched_sources."""
        selectors, unmatched, ignored = _at.map_changed_to_tests(["orphan.py"], fake_repo)
        assert "orphan.py" in unmatched
        assert not selectors

    def test_changed_test_file_selected_directly(self, fake_repo):
        """test_foo.py itself -> included as a selector."""
        selectors, unmatched, ignored = _at.map_changed_to_tests(["test_foo.py"], fake_repo)
        assert any("test_foo.py" in s for s in selectors)
        assert not unmatched

    def test_ignored_non_py(self, fake_repo):
        """Non-.py files -> ignored (not unmatched_sources)."""
        selectors, unmatched, ignored = _at.map_changed_to_tests(
            ["gate/SKILL.md", "notes.md", "config.json"], fake_repo
        )
        assert not selectors
        assert not unmatched
        assert ignored  # all three should be in ignored

    def test_determinism(self, fake_repo):
        """Selector list is sorted and stable across calls."""
        s1, _, _ = _at.map_changed_to_tests(["foo.py", "bar.py"], fake_repo)
        s2, _, _ = _at.map_changed_to_tests(["bar.py", "foo.py"], fake_repo)
        assert s1 == s2, "selectors should be order-independent"
        assert s1 == sorted(s1), "selectors should be sorted"


# ---------------------------------------------------------------------------
# resolve_repo
# ---------------------------------------------------------------------------

class TestResolveRepo:
    def test_resolves_child_git_repo(self, tmp_path):
        """Outer non-git dir with a child git repo -> returns child."""
        child = tmp_path / "myrepo"
        child.mkdir()
        (child / ".git").mkdir()
        result = _at.resolve_repo(tmp_path)
        assert result is not None
        assert result.resolve() == child.resolve()

    def test_no_git_repo_returns_none(self, tmp_path):
        """No git repos under project_root -> returns None."""
        result = _at.resolve_repo(tmp_path)
        assert result is None

    def test_project_root_is_git_repo(self, tmp_path):
        """If project_root itself is a git repo -> returns it."""
        (tmp_path / ".git").mkdir()
        result = _at.resolve_repo(tmp_path)
        assert result is not None
        assert result.resolve() == tmp_path.resolve()

    def test_multiple_repos_raises(self, tmp_path):
        """Multiple repos -> RuntimeError (caller should exit 3)."""
        (tmp_path / "repo1").mkdir()
        (tmp_path / "repo1" / ".git").mkdir()
        (tmp_path / "repo2").mkdir()
        (tmp_path / "repo2" / ".git").mkdir()
        with pytest.raises(RuntimeError, match="Multiple git repos"):
            _at.resolve_repo(tmp_path)


# ---------------------------------------------------------------------------
# changed_files (diff-basis fallback — CRIT-2)
# ---------------------------------------------------------------------------

def _git(*args, cwd):
    """Run a git command in the given directory."""
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True)


class TestChangedFiles:
    def test_worktree_fallback_on_main(self, tmp_path):
        """HEAD==main (no feature branch, no upstream) + dirty .py -> worktree-diff."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        # Commit a baseline
        (repo / "base.py").write_text("# baseline\n")
        _git("add", "base.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)
        # Make an uncommitted change
        (repo / "dirty.py").write_text("# dirty\n")
        _git("add", "dirty.py", cwd=repo)

        files, reason = _at.changed_files(repo)
        assert "dirty.py" in files, f"Expected dirty.py in files, got {files}"
        assert reason == "worktree-diff"

    def test_clean_tree_no_changes(self, tmp_path):
        """Genuinely clean tree -> empty list + reason no-changes."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        (repo / "base.py").write_text("# baseline\n")
        _git("add", "base.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)

        files, reason = _at.changed_files(repo)
        assert files == []
        assert reason == "no-changes"

    def test_not_a_git_repo(self, tmp_path):
        """Not a git repo -> git-error reason."""
        not_repo = tmp_path / "not_repo"
        not_repo.mkdir()
        files, reason = _at.changed_files(not_repo)
        assert reason == "git-error"

    def test_committed_clean_no_upstream_returns_base_branch_diff(self, tmp_path):
        """F-01 fix: committed .py change on branch with no upstream, clean worktree
        -> base-branch-diff (NOT no-changes).

        This is the canonical /review + /gate state: git switch -c creates a
        feature branch without --track, so @{u} does not exist.  The gate's
        'No uncommitted changes' check ensures the tree is committed-clean.
        Before F-01, this yielded 'no-changes' -> false APPROVE with zero tests run.
        After F-01, the base-branch merge-base step detects the committed change.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        # Commit a baseline on main
        (repo / "base.py").write_text("# baseline\n")
        _git("add", "base.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)
        # Create a feature branch (no upstream — mirrors `git switch -c`)
        _git("switch", "-c", "feature/my-change", cwd=repo)
        # Commit a .py source change on the feature branch (committed-clean)
        (repo / "src.py").write_text("def src(): return 42\n")
        _git("add", "src.py", cwd=repo)
        _git("commit", "-m", "add src.py", cwd=repo)
        # Tree is clean: no uncommitted changes, no upstream

        files, reason = _at.changed_files(repo)
        assert "src.py" in files, (
            f"F-01 regression: committed src.py not detected; got files={files}, reason={reason}"
        )
        assert reason == "base-branch-diff", (
            f"Expected reason=base-branch-diff, got {reason}"
        )


# ---------------------------------------------------------------------------
# CLI exit-code matrix
# ---------------------------------------------------------------------------

def _cli(args, env=None):
    """Run main(args) and return exit code."""
    import os
    saved = {k: os.environ.get(k) for k in (env or {})}
    try:
        if env:
            for k, v in env.items():
                os.environ[k] = v
        return _at.main(args)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestCLIExitCodes:
    def test_bad_args_exit_2(self):
        """Missing required argument group -> exit 2."""
        rc = _cli([])
        assert rc == 2

    def test_no_base_flag(self):
        """--base is not a recognized flag (MIN-1)."""
        rc = _cli(["--base", "main", "--files", "foo.py"])
        assert rc == 2

    def test_select_only_no_pytest(self, fake_repo):
        """--select-only emits JSON without running pytest (ran_pytest=False)."""
        with mock.patch("subprocess.run") as mock_run:
            rc = _cli(["--select-only", "--files", "foo.py",
                       "--repo-root", str(fake_repo)])
            assert rc == 0
            # subprocess.run should NOT have been called for pytest
            # (only allowable calls would be for git, but we're using --files mode)
            for call in mock_run.call_args_list:
                call_args = call[0][0] if call[0] else call.args[0]
                assert "pytest" not in str(call_args), (
                    f"pytest should not be invoked with --select-only, got {call_args}"
                )

    def test_exit_0c_clean_tree(self, tmp_path):
        """--project-root on clean repo -> exit 0, exit_reason=no-changes."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        (repo / "base.py").write_text("# baseline\n")
        _git("add", "base.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)

        captured = []
        original_print = __builtins__["print"] if isinstance(__builtins__, dict) else print

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cli(["--project-root", str(tmp_path)])
        assert rc == 0
        output = buf.getvalue()
        data = json.loads(output)
        assert data["exit_reason"] == "no-changes"
        assert data["ran_pytest"] is False

    def test_exit_0b_docs_only(self, fake_repo):
        """Docs-only changeset -> exit 0, ran_pytest=False, exit_reason=docs-only."""
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with mock.patch("subprocess.run") as mock_run:
                rc = _cli(["--files", "gate/SKILL.md", "notes.md",
                            "--repo-root", str(fake_repo)])
                # Assert pytest was NOT spawned
                for call in mock_run.call_args_list:
                    call_args = call[0][0] if call[0] else call.args[0]
                    assert "pytest" not in str(call_args), (
                        f"pytest must NOT be invoked for docs-only: {call_args}"
                    )
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert data["exit_reason"] == "docs-only-no-selectors"
        assert data["ran_pytest"] is False
        assert data["selectors"] == []
        assert data["unmatched_sources"] == []

    def test_docs_only_distinct_from_exit_4(self, fake_repo):
        """A changed real .py source with no test -> exit 3/4 (NOT 0b)."""
        rc = _cli(["--files", "orphan.py", "--repo-root", str(fake_repo)])
        assert rc in (3, 4), f"Expected 3 or 4 for unmatched .py source, got {rc}"

    def test_docs_only_distinct_from_exit_0c(self, fake_repo):
        """Docs-only reports exit_reason=docs-only-no-selectors, NOT no-changes."""
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cli(["--files", "README.md",
                       "--repo-root", str(fake_repo)])
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert data["exit_reason"] == "docs-only-no-selectors"
        assert data["exit_reason"] != "no-changes"

    def test_exit_1_red_tests(self, tmp_path):
        """A deliberately failing affected test -> exit 1."""
        # Write a failing test
        (tmp_path / "src.py").write_text("def src(): pass\n")
        (tmp_path / "test_src.py").write_text(
            "def test_src_fails(): assert False, 'deliberate failure'\n"
        )
        rc = _cli(["--files", "src.py", "--repo-root", str(tmp_path)])
        assert rc == 1, f"Expected exit 1 (red tests), got {rc}"

    def test_exit_3_unmatched_without_allow(self, fake_repo):
        """orphan.py with no test + no --allow-unmatched -> exit 3."""
        rc = _cli(["--files", "orphan.py", "--repo-root", str(fake_repo)])
        assert rc == 3

    def test_allow_unmatched_green(self, tmp_path):
        """--allow-unmatched: unmatched source + other tests passing -> exit 0."""
        # Create a test that PASSES (not related to orphan.py)
        (tmp_path / "orphan.py").write_text("def orphan(): pass\n")
        (tmp_path / "other.py").write_text("def other(): pass\n")
        (tmp_path / "test_other.py").write_text("def test_other(): pass\n")
        rc = _cli(["--files", "orphan.py", "other.py",
                   "--repo-root", str(tmp_path),
                   "--allow-unmatched"])
        assert rc == 0, f"Expected exit 0 with --allow-unmatched and passing tests, got {rc}"

    def test_allow_unmatched_single_unmatched_no_selectors_exit_0(self, tmp_path):
        """F-02 fix: --allow-unmatched + single unmatched .py source (no selectors)
        -> exit 0, NOT exit 4.

        The escape-hatch contract says --allow-unmatched "yields exit 0 when
        affected pytest passes."  With empty selectors there is nothing to run,
        so exit 0 with ran_pytest=False and unmatched_warning=true is the
        consistent interpretation (the user opted in to 'I know tests are missing').
        """
        (tmp_path / "orphan.py").write_text("def orphan(): pass\n")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cli(["--files", "orphan.py",
                       "--repo-root", str(tmp_path),
                       "--allow-unmatched"])
        assert rc == 0, (
            f"F-02 regression: expected exit 0 with --allow-unmatched + single "
            f"unmatched source and no selectors, got {rc}"
        )
        data = json.loads(buf.getvalue())
        assert data.get("unmatched_warning") is True, (
            f"Expected unmatched_warning=true in output, got {data}"
        )
        assert data["ran_pytest"] is False

    def test_f01_committed_clean_no_upstream_red_test_exit_1(self, tmp_path):
        """F-01 end-to-end: committed-clean feature branch, no upstream, red test
        -> exit 1 (affected suite RED), NOT exit 0 (false APPROVE).

        Reproduces the exact hermetic scenario from review-1.md: a branch with a
        committed change to src.py whose test_src.py asserts False.  Before F-01
        this yielded exit 0 / no-changes.  After F-01 the red test is selected
        via the base-branch merge-base diff and exit 1 is produced.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        # Baseline commit on main
        (repo / "baseline.py").write_text("# baseline\n")
        _git("add", "baseline.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)
        # Feature branch (no upstream)
        _git("switch", "-c", "feature/red-test", cwd=repo)
        # Commit src.py + a red test (tree committed-clean, no upstream)
        (repo / "src.py").write_text("def src(): return 42\n")
        (repo / "test_src.py").write_text(
            "def test_src_fails(): assert False, 'deliberate failure — F-01 regression guard'\n"
        )
        _git("add", "src.py", "test_src.py", cwd=repo)
        _git("commit", "-m", "add src + red test", cwd=repo)
        # Tree is clean: committed-clean, no upstream — the exact false-APPROVE state

        # Use --project-root (outer non-git) to exercise the full pipeline
        rc = _cli(["--project-root", str(tmp_path)])
        assert rc == 1, (
            f"F-01 regression: expected exit 1 (red affected test), got {rc}. "
            f"If exit 0 is returned, the base-branch merge-base diff step is not firing "
            f"and the committed-clean no-upstream false-APPROVE bug is still present."
        )

    def test_disable_env_exit_3(self):
        """QUOIN_DISABLE_AFFECTED_TESTS=1 -> exit 3 + {"disabled": true}."""
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cli(
                ["--files", "anything.py"],
                env={"QUOIN_DISABLE_AFFECTED_TESTS": "1"},
            )
        assert rc == 3, f"Expected exit 3 on DISABLE, got {rc}"
        data = json.loads(buf.getvalue())
        assert data.get("disabled") is True

    def test_project_root_resolves_to_child(self, tmp_path):
        """--project-root outer (no .git) with child git repo -> resolves OK."""
        repo = tmp_path / "quoin"
        repo.mkdir()
        _git("init", "-b", "main", cwd=repo)
        _git("config", "user.email", "test@test.com", cwd=repo)
        _git("config", "user.name", "Test", cwd=repo)
        (repo / "base.py").write_text("# baseline\n")
        _git("add", "base.py", cwd=repo)
        _git("commit", "-m", "baseline", cwd=repo)
        # Make a staged change so changed_files has something
        (repo / "new.py").write_text("# new\n")
        _git("add", "new.py", cwd=repo)

        # Run with --select-only so we don't need matching test files
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cli(["--select-only", "--project-root", str(tmp_path)])
        # Should not error with "not a git repository"
        assert rc == 0, f"Expected exit 0, got {rc}"

    def test_project_root_no_repo_exits_3(self, tmp_path):
        """--project-root pointing at a dir with no nested git -> exit 3."""
        rc = _cli(["--project-root", str(tmp_path)])
        assert rc == 3

    def test_no_pytest_invocation_when_select_only(self, fake_repo):
        """--select-only: subprocess.run is never called with pytest in args."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0)
            rc = _cli(["--select-only", "--files", "foo.py",
                       "--repo-root", str(fake_repo)])
            for call in mock_run.call_args_list:
                args_used = call[0][0] if call[0] else []
                assert "-m" not in str(args_used) or "pytest" not in str(args_used), (
                    f"pytest must not run on --select-only, call: {call}"
                )
