"""Tests for workspace.py — `_proven_merged` real detection + `status`/`list` (IVG-158, S-05).

Loads the core module via importlib (real file path) and also exercises the
CLI via subprocess for end-to-end + wrapper-parity coverage. No network; all
git fixtures are ephemeral under tmp_path. Determinism: each fixture repo's
actual default branch is read post-init rather than hardcoded main/master.

Mirrors test_workspace_teardown.py's importlib-load + git-fixture + `run_cli`
style (own copy of fixtures — do NOT cross-import between test files, same
copy-not-import convention as the source module itself).

Coverage maps 1:1 to the S-05 plan acceptance criteria (T-01/T-02/T-04):
  `_proven_merged` gh-path + gh-free path + `_worktree_branch`, `collect_status`
  merged/non-merged offer flags, CLI `status`/`list` end-to-end + read-only
  invariant + wrapper parity.
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
    spec = importlib.util.spec_from_file_location("_test_core_workspace_status", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ws = _load_core()


# ---------------------------------------------------------------------------
# Fixtures / helpers (own copy — see module docstring)
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


def commit_in(worktree: Path, msg: str) -> None:
    fname = f"extra-{msg}.txt"
    (worktree / fname).write_text(msg)
    _git("-C", str(worktree), "add", fname)
    _git("-C", str(worktree), "commit", "-m", msg)


def merge_into_default(project_root: Path, worktree: Path, feature: str) -> None:
    """Commit in `worktree`, then merge `feature` into the ORIG repo's default branch.

    Makes the feature branch genuinely reachable from default — a real
    gh-free proven-merged state. Reads the repo's actual default branch
    rather than hardcoding main/master.
    """
    commit_in(worktree, "mergeme")
    orig_repo = project_root / worktree.name
    default = ws.default_branch(orig_repo)
    _git("-C", str(orig_repo), "checkout", default)
    _git("-C", str(orig_repo), "merge", feature)


def run_cli(script_path: Path, *args, cwd=None):
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, cwd=cwd)


def record_path(project_root: Path, slug: str) -> Path:
    return project_root / ".workflow_artifacts" / "memory" / "workspaces" / f"{slug}.json"


# ---------------------------------------------------------------------------
# `_proven_merged` direct: gh-path
# ---------------------------------------------------------------------------

def test_proven_merged_gh_true_short_circuits(monkeypatch, tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "gh-true-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    # Never merged into default; gh alone must be enough to prove it.
    commit_in(wt, "unmerged")
    monkeypatch.setattr(ws, "_gh_pr_merged", lambda branch, cwd: True)

    orig = ws._worktree_orig_repo(wt)
    assert ws._proven_merged(wt, orig) is True


def test_proven_merged_gh_false_falls_through_to_git_false(monkeypatch, tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "gh-false-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    commit_in(wt, "unmerged")  # diverge; never merged into default
    monkeypatch.setattr(ws, "_gh_pr_merged", lambda branch, cwd: False)

    orig = ws._worktree_orig_repo(wt)
    assert ws._proven_merged(wt, orig) is False


# ---------------------------------------------------------------------------
# `_proven_merged` direct: gh-free path (QUOIN_WORKSPACE_DISABLE_GH)
# ---------------------------------------------------------------------------

def test_proven_merged_gh_free_merged_true(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_WORKSPACE_DISABLE_GH", "1")
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "ghfree-merged-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    merge_into_default(project_root, wt, "ghfree-merged-feat")

    orig = ws._worktree_orig_repo(wt)
    assert ws._proven_merged(wt, orig) is True


def test_proven_merged_gh_free_not_merged_false(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_WORKSPACE_DISABLE_GH", "1")
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "ghfree-unmerged-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    commit_in(wt, "unmerged")  # diverge; never merged into default

    orig = ws._worktree_orig_repo(wt)
    assert ws._proven_merged(wt, orig) is False


def test_worktree_branch_returns_feature_name(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "branch-name-feat", ["repo-a"])
    wt = ws_root / "repo-a"
    assert ws._worktree_branch(wt) == "branch-name-feat"


def test_worktree_branch_none_on_bad_path():
    assert ws._worktree_branch(Path("/nowhere-at-all")) is None


# ---------------------------------------------------------------------------
# `collect_status`: merged/non-merged offer flags + view shape
# ---------------------------------------------------------------------------

def test_collect_status_two_repo_view(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    make_workspace(project_root, "status-two-feat", ["repo-a", "repo-b"])

    views = ws.collect_status(project_root)
    assert len(views) == 1
    v = views[0]
    assert len(v.worktrees) == 2
    assert v.feature == "status-two-feat"
    assert v.owner_session_uuid == "uuid-test"
    assert v.live is True  # freshly written record -> last_seen just now


def test_collect_status_merged_offer_true(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_WORKSPACE_DISABLE_GH", "1")
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    ws_root = make_workspace(project_root, "status-merged-feat", ["repo-a", "repo-b"])
    for name in ("repo-a", "repo-b"):
        merge_into_default(project_root, ws_root / name, "status-merged-feat")

    views = ws.collect_status(project_root)
    assert len(views) == 1
    v = views[0]
    assert v.offer_teardown is True
    assert len(v.worktrees) == 2
    assert all(w.merged is True and w.safe is True for w in v.worktrees)


def test_collect_status_non_merged_no_upstream_offer_false(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_WORKSPACE_DISABLE_GH", "1")
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "status-unmerged-feat", ["repo-a"])
    commit_in(ws_root / "repo-a", "unmerged")  # diverge; never merged

    views = ws.collect_status(project_root)
    assert len(views) == 1
    v = views[0]
    assert v.offer_teardown is False
    assert v.worktrees[0].merged is False
    assert v.worktrees[0].safe is False
    assert any("no upstream" in r for r in v.worktrees[0].reasons)


def test_collect_status_empty_project_empty_list(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    assert ws.collect_status(project_root) == []


# ---------------------------------------------------------------------------
# `status`/`list` CLI end-to-end + read-only invariant
# ---------------------------------------------------------------------------

def test_cli_status_json_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    make_workspace(project_root, "cli-status-feat", ["repo-a"])

    # gh deliberately left enabled here — synthetic repos have no GitHub
    # remote, so gh naturally fails/is unavailable and must fail OPEN
    # (falls through to the git path) rather than crash (risk R-08).
    proc = run_cli(CORE_PATH, "status", "--project-root", str(project_root))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "workspaces" in payload
    assert isinstance(payload["workspaces"], list)
    assert len(payload["workspaces"]) == 1
    assert payload["workspaces"][0]["feature"] == "cli-status-feat"


def test_cli_list_alias_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    make_workspace(project_root, "cli-list-feat", ["repo-a"])

    proc = run_cli(CORE_PATH, "list", "--project-root", str(project_root))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "workspaces" in payload
    assert len(payload["workspaces"]) == 1


def test_cli_status_badargs_exit2(tmp_path):
    proc = run_cli(CORE_PATH, "status", "--bogus-flag")
    assert proc.returncode == 2


def test_status_is_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOIN_WORKSPACE_DISABLE_GH", "1")
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_root = make_workspace(project_root, "readonly-feat", ["repo-a"])
    slug = ws.slugify("readonly-feat")
    record_file = record_path(project_root, slug)

    before_record = record_file.read_bytes()
    before_worktrees = worktree_list(project_root / "repo-a")
    before_ws_root_listing = sorted(p.name for p in ws_root.iterdir())

    proc = run_cli(CORE_PATH, "status", "--project-root", str(project_root))
    assert proc.returncode == 0, proc.stderr

    after_record = record_file.read_bytes()
    after_worktrees = worktree_list(project_root / "repo-a")
    after_ws_root_listing = sorted(p.name for p in ws_root.iterdir())

    assert before_record == after_record
    assert before_worktrees == after_worktrees
    assert before_ws_root_listing == after_ws_root_listing


# ---------------------------------------------------------------------------
# Wrapper parity (no new file — verify the re-export reaches status/collect_status)
# ---------------------------------------------------------------------------

def test_wrapper_exposes_collect_status():
    spec = importlib.util.spec_from_file_location("_test_wrapper_workspace_status", WRAPPER_PATH)
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = wrapper
    spec.loader.exec_module(wrapper)
    assert hasattr(wrapper, "collect_status")
    assert callable(wrapper.collect_status)
    assert hasattr(wrapper, "enumerate_workspaces")


def test_wrapper_status_cli_parity(tmp_path):
    project_core = make_multi_repo_project(tmp_path / "core_side", ["repo-a"])
    project_wrapper = make_multi_repo_project(tmp_path / "wrapper_side", ["repo-a"])
    make_workspace(project_core, "parity-status", ["repo-a"])
    make_workspace(project_wrapper, "parity-status", ["repo-a"])

    core_proc = run_cli(CORE_PATH, "status", "--project-root", str(project_core))
    wrapper_proc = run_cli(WRAPPER_PATH, "status", "--project-root", str(project_wrapper))

    assert core_proc.returncode == wrapper_proc.returncode == 0
    core_payload = json.loads(core_proc.stdout)
    wrapper_payload = json.loads(wrapper_proc.stdout)
    assert core_payload.keys() == wrapper_payload.keys()
    core_ws = core_payload["workspaces"][0]
    wrapper_ws = wrapper_payload["workspaces"][0]
    assert core_ws.keys() == wrapper_ws.keys()
