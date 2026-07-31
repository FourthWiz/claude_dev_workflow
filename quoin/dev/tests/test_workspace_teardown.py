"""Tests for workspace.py — feature-workspace `teardown` subcommand (IVG-158, S-03).

Loads the core module via importlib (real file path) and also exercises the
CLI via subprocess for end-to-end + wrapper-parity coverage. No network; all
git fixtures are ephemeral under tmp_path. Determinism: each fixture repo's
actual default branch is read post-init rather than hardcoded main/master.

Coverage maps 1:1 to the S-03 plan acceptance criteria and FR5/AC-5:
  T-01 classify safety, T-02 discovery + orig-repo + record guard,
  T-03/T-04 orchestrator + CLI exit codes, T-05 wrapper parity.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).parent.parent.parent / "core" / "scripts"
CORE_PATH = CORE_DIR / "workspace.py"
WRAPPER_PATH = Path(__file__).parent.parent.parent / "scripts" / "workspace.py"

SUBPROCESS_TIMEOUT = 60  # generous headroom — Drive-mount/cloud-fs flake lesson


def _load_core():
    """Load workspace.py via importlib from its real file path (sibling imports resolve)."""
    spec = importlib.util.spec_from_file_location("_test_core_workspace_teardown", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ws = _load_core()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _git(*args) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
    )
    assert proc.returncode == 0, proc.stderr
    return proc


def make_git_repo(path: Path) -> Path:
    """git init + user config + initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", str(path))
    _git("-C", str(path), "config", "user.email", "test@test.com")
    _git("-C", str(path), "config", "user.name", "Test")
    (path / ".gitkeep").write_text("placeholder")
    _git("-C", str(path), "add", ".gitkeep")
    _git("-C", str(path), "commit", "-m", "init")
    return path


def make_multi_repo_project(tmp_path: Path, names: list[str]) -> Path:
    """git-init each named child under a non-git project root."""
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        make_git_repo(project_root / name)
    return project_root


def worktree_list(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    return out.stdout


def make_workspace(project_root: Path, feature: str, repos: list[str]) -> Path:
    """Build a real workspace (worktrees + record + marker) via S-01 machinery."""
    result = ws.create_workspace(feature, project_root, named_repos=repos, session_uuid="uuid-test")
    assert result.record_written is True, result.message
    slug = ws.slugify(feature)
    return project_root / ".workspaces" / slug


def make_pushed_safe(worktree: Path, feature: str, tmp_path: Path) -> None:
    """Give a worktree an upstream with commits_ahead==0 (the only provably-safe class)."""
    origin = tmp_path / "origins" / f"{worktree.parent.name}-{worktree.name}.git"
    origin.parent.mkdir(parents=True, exist_ok=True)
    _git("init", "--bare", str(origin))
    _git("-C", str(worktree), "remote", "add", "origin", str(origin))
    proc = subprocess.run(
        ["git", "-C", str(worktree), "push", "-u", "origin", feature],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
    )
    assert proc.returncode == 0, proc.stderr


def commit_in(worktree: Path, msg: str) -> None:
    fname = f"extra-{msg}.txt"
    (worktree / fname).write_text(msg)
    _git("-C", str(worktree), "add", fname)
    _git("-C", str(worktree), "commit", "-m", msg)


def run_cli(script_path: Path, *args, cwd=None):
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, cwd=cwd)


def mk_rc(dirty=False, upstream=None, commits_ahead=0, error=None):
    """Construct a branch_hygiene.RepoResult for classifier unit tests."""
    return ws.branch_hygiene.RepoResult(
        repo="/x", current_branch="feat", on_protected=False,
        commits_ahead=commits_ahead, has_task_commits=False, head_sha="abc",
        upstream=upstream, dirty=dirty, error=error,
    )


def record_path(project_root: Path, slug: str) -> Path:
    return project_root / ".workflow_artifacts" / "memory" / "workspaces" / f"{slug}.json"


def marker_path(ws_root: Path) -> Path:
    return ws_root / ".quoin-workspace.json"


# ---------------------------------------------------------------------------
# T-01: safety classification + proven-merged seam
# ---------------------------------------------------------------------------

def test_classify_dirty_unsafe():
    safe, reasons = ws._classify_worktree_safety(mk_rc(dirty=True, upstream="origin/feat"), False)
    assert safe is False
    assert any("uncommitted" in r for r in reasons)


def test_classify_clean_pushed_safe():
    safe, reasons = ws._classify_worktree_safety(mk_rc(upstream="origin/feat", commits_ahead=0), False)
    assert safe is True
    assert reasons == []


def test_classify_no_upstream_unsafe():
    # R-06 crux: never-pushed branch (default post-create state) must be unsafe.
    safe, reasons = ws._classify_worktree_safety(mk_rc(upstream=None), False)
    assert safe is False
    assert any("no upstream" in r for r in reasons)


def test_classify_ahead_unsafe():
    safe, reasons = ws._classify_worktree_safety(mk_rc(upstream="origin/feat", commits_ahead=2), False)
    assert safe is False
    assert any("unpushed" in r for r in reasons)


def test_classify_git_error_unsafe():
    safe, reasons = ws._classify_worktree_safety(mk_rc(error="boom", upstream="origin/feat"), False)
    assert safe is False
    assert any("git error" in r for r in reasons)


def test_classify_no_upstream_proven_merged_override_safe():
    # Guards the S-05 seam wiring: when proven_merged=True, no-upstream is NOT flagged.
    safe, reasons = ws._classify_worktree_safety(mk_rc(upstream=None), True)
    assert safe is True
    assert reasons == []


def test_proven_merged_stub_false():
    assert ws._proven_merged(Path("/nowhere"), "/nowhere") is False
    assert ws._proven_merged("anything", None) is False


# ---------------------------------------------------------------------------
# T-02: discovery + orig-repo derivation + record guard
# ---------------------------------------------------------------------------

def test_discover_worktrees_two_repos(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    ws_root = make_workspace(project_root, "disc-feat", ["repo-a", "repo-b"])
    found = ws.discover_workspace_worktrees(ws_root)
    names = sorted(p.name for p in found)
    assert names == ["repo-a", "repo-b"]
    # The .quoin-workspace.json marker file must be excluded.
    assert all(p.name != ".quoin-workspace.json" for p in found)


def test_orig_repo_derivation(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    ws_root = make_workspace(project_root, "orig-feat", ["repo-a", "repo-b"])
    for wt in ws.discover_workspace_worktrees(ws_root):
        orig = ws._worktree_orig_repo(wt)
        assert orig is not None
        assert Path(orig).resolve() == (project_root / wt.name).resolve()


def test_discover_absent_ws_root_empty(tmp_path):
    assert ws.discover_workspace_worktrees(tmp_path / "does-not-exist") == []


def test_read_record_safe_non_dict_returns_none(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    make_workspace(project_root, "guard-feat", ["repo-a"])
    slug = ws.slugify("guard-feat")
    # Overwrite the record with a valid-JSON NON-object (a list).
    record_path(project_root, slug).write_text(json.dumps(["not", "a", "dict"]))
    assert ws._read_record_safe(project_root, slug) is None


# ---------------------------------------------------------------------------
# T-03/T-04: orchestrator + CLI exit codes
# ---------------------------------------------------------------------------

def test_teardown_refuses_dirty(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "dirty-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    make_pushed_safe(wt, "dirty-feat", tmp_path)
    (wt / "uncommitted.txt").write_text("dirty")

    result = ws.teardown_workspace("dirty-feat", project_root, force=False)
    assert result.refused is True
    assert ws_root.exists()
    assert record_path(project_root, ws.slugify("dirty-feat")).exists()


def test_teardown_refuses_commits_ahead(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "ahead-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    make_pushed_safe(wt, "ahead-feat", tmp_path)
    commit_in(wt, "local")

    result = ws.teardown_workspace("ahead-feat", project_root, force=False)
    assert result.refused is True
    assert ws_root.exists()


def test_teardown_refuses_no_upstream(tmp_path):
    # R-06 crux: create then teardown, no push, no force -> must refuse.
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "noup-feat", ["repo-a"])

    result = ws.teardown_workspace("noup-feat", project_root, force=False)
    assert result.refused is True
    assert any("no upstream" in r for s in result.per_repo for r in s.reasons)
    assert ws_root.exists()
    assert record_path(project_root, ws.slugify("noup-feat")).exists()


def test_teardown_force_overrides_dirty(tmp_path, capsys):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "fdirty-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    make_pushed_safe(wt, "fdirty-feat", tmp_path)
    (wt / "uncommitted.txt").write_text("dirty")

    result = ws.teardown_workspace("fdirty-feat", project_root, force=True)
    assert result.forced is True
    assert result.folder_removed is True
    assert not ws_root.exists()
    # critic MIN-1: the --force bypass MUST be logged (catch a silent-force regression).
    assert "force" in capsys.readouterr().err.lower()


def test_teardown_force_overrides_no_upstream(tmp_path, capsys):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "fnoup-feat", ["repo-a"])

    result = ws.teardown_workspace("fnoup-feat", project_root, force=True)
    assert result.folder_removed is True
    assert result.record_removed is True
    assert not ws_root.exists()
    assert "force" in capsys.readouterr().err.lower()


def test_teardown_force_overrides_commits_ahead(tmp_path, capsys):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "fahead-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    make_pushed_safe(wt, "fahead-feat", tmp_path)
    commit_in(wt, "local")

    result = ws.teardown_workspace("fahead-feat", project_root, force=True)
    assert result.folder_removed is True
    assert not ws_root.exists()
    assert "force" in capsys.readouterr().err.lower()


def test_teardown_clean_removes_all(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    ws_root = make_workspace(project_root, "clean-feat", ["repo-a", "repo-b"])
    for name in ("repo-a", "repo-b"):
        make_pushed_safe(ws_root / name, "clean-feat", tmp_path)

    result = ws.teardown_workspace("clean-feat", project_root, force=False)
    assert result.refused is False
    assert result.folder_removed is True
    assert result.record_removed is True
    # No dangling worktree in EITHER original repo.
    for name in ("repo-a", "repo-b"):
        assert str(ws_root / name) not in worktree_list(project_root / name)
    assert not ws_root.exists()
    assert not marker_path(ws_root).exists()
    assert not record_path(project_root, ws.slugify("clean-feat")).exists()


def test_teardown_record_non_dict_guard(tmp_path):
    # Seed a JSON-list record; teardown must still discover via ws_root (no AttributeError).
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "recguard-feat", ["repo-a"])
    make_pushed_safe(ws_root / "repo-a", "recguard-feat", tmp_path)
    record_path(project_root, ws.slugify("recguard-feat")).write_text(json.dumps(["corrupt"]))

    result = ws.teardown_workspace("recguard-feat", project_root, force=False)
    assert result.folder_removed is True
    assert not ws_root.exists()


def test_teardown_missing_workspace_graceful(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    result = ws.teardown_workspace("never-created", project_root, force=False)
    assert result.refused is False
    assert result.partial_failure is False
    assert result.message == "nothing to tear down"


def test_teardown_rerun_idempotent(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "rerun-feat", ["repo-a"])
    make_pushed_safe(ws_root / "repo-a", "rerun-feat", tmp_path)

    first = ws.teardown_workspace("rerun-feat", project_root, force=False)
    assert first.folder_removed is True
    second = ws.teardown_workspace("rerun-feat", project_root, force=False)
    assert second.refused is False
    assert second.message == "nothing to tear down"


def test_teardown_partial_then_resume(tmp_path):
    # Simulate a crash: manually remove one worktree first, then teardown completes.
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    ws_root = make_workspace(project_root, "resume-feat", ["repo-a", "repo-b"])
    for name in ("repo-a", "repo-b"):
        make_pushed_safe(ws_root / name, "resume-feat", tmp_path)

    # Pre-remove repo-a's worktree from its original repo (crash mid-teardown).
    _git("-C", str(project_root / "repo-a"), "worktree", "remove", str(ws_root / "repo-a"))
    assert not (ws_root / "repo-a").exists()

    result = ws.teardown_workspace("resume-feat", project_root, force=False)
    assert result.folder_removed is True
    assert result.record_removed is True
    assert not ws_root.exists()
    assert str(ws_root / "repo-b") not in worktree_list(project_root / "repo-b")


# ---------------------------------------------------------------------------
# T-04: CLI subcommand + exit codes (subprocess)
# ---------------------------------------------------------------------------

def test_cli_teardown_clean_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "cli-clean", ["repo-a"])
    make_pushed_safe(ws_root / "repo-a", "cli-clean", tmp_path)

    proc = run_cli(CORE_PATH, "teardown", "cli-clean", "--project-root", str(project_root))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["folder_removed"] is True
    assert payload["record_removed"] is True


def test_cli_teardown_refused_exit3(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    make_workspace(project_root, "cli-refuse", ["repo-a"])  # no-upstream -> unsafe
    proc = run_cli(CORE_PATH, "teardown", "cli-refuse", "--project-root", str(project_root))
    assert proc.returncode == 3
    payload = json.loads(proc.stdout)
    assert payload["refused"] is True


def test_cli_teardown_force_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    make_workspace(project_root, "cli-force", ["repo-a"])  # no-upstream -> unsafe
    proc = run_cli(CORE_PATH, "teardown", "cli-force", "--project-root", str(project_root), "--force")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["folder_removed"] is True
    assert "force" in proc.stderr.lower()


def test_cli_teardown_badargs_exit2(tmp_path):
    proc = run_cli(CORE_PATH, "teardown")  # missing required positional
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# T-05: wrapper parity (no new file — verify the re-export reaches teardown)
# ---------------------------------------------------------------------------

def test_wrapper_exposes_teardown():
    spec = importlib.util.spec_from_file_location("_test_wrapper_workspace_teardown", WRAPPER_PATH)
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = wrapper
    spec.loader.exec_module(wrapper)
    assert hasattr(wrapper, "teardown_workspace")
    assert callable(wrapper.teardown_workspace)
    assert hasattr(wrapper, "discover_workspace_worktrees")


def test_wrapper_teardown_cli_parity(tmp_path):
    project_core = make_multi_repo_project(tmp_path / "core_side", ["repo-a"])
    project_wrapper = make_multi_repo_project(tmp_path / "wrapper_side", ["repo-a"])
    ws_core = make_workspace(project_core, "parity-td", ["repo-a"])
    ws_wrapper = make_workspace(project_wrapper, "parity-td", ["repo-a"])
    make_pushed_safe(ws_core / "repo-a", "parity-td", tmp_path)
    make_pushed_safe(ws_wrapper / "repo-a", "parity-td", tmp_path)

    core_proc = run_cli(CORE_PATH, "teardown", "parity-td", "--project-root", str(project_core))
    wrapper_proc = run_cli(WRAPPER_PATH, "teardown", "parity-td", "--project-root", str(project_wrapper))

    assert core_proc.returncode == wrapper_proc.returncode == 0
    core_payload = json.loads(core_proc.stdout)
    wrapper_payload = json.loads(wrapper_proc.stdout)
    assert core_payload.keys() == wrapper_payload.keys()
    assert core_payload["folder_removed"] == wrapper_payload["folder_removed"] is True
