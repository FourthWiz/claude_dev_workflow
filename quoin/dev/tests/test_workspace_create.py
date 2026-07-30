"""Tests for workspace.py — feature-workspace `create` subcommand (IVG-158, S-01).

Loads the core module via importlib (real file path) and also exercises the
CLI via subprocess for end-to-end + wrapper-parity coverage. No network; all
git fixtures are ephemeral under tmp_path. Determinism: each fixture repo's
actual default branch is read post-init rather than hardcoded main/master.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).parent.parent.parent / "core" / "scripts"
CORE_PATH = CORE_DIR / "workspace.py"
WRAPPER_PATH = Path(__file__).parent.parent.parent / "scripts" / "workspace.py"

SUBPROCESS_TIMEOUT = 60  # generous headroom — Drive-mount/cloud-fs flake lesson


def _load_core():
    """Load workspace.py via importlib from its real file path (sibling imports resolve)."""
    spec = importlib.util.spec_from_file_location("_test_core_workspace", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ws = _load_core()


def make_git_repo(path: Path) -> Path:
    """git init + user.email/name config + initial commit (borrowed pattern)."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT,
    )
    (path / ".gitkeep").write_text("placeholder")
    subprocess.run(["git", "add", ".gitkeep"], capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT,
    )
    return path


def repo_current_branch(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    return out.stdout.strip()


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


# ---------------------------------------------------------------------------
# T-01: scaffold + local helpers
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert ws.slugify("Feat/X_1") == "feat-x-1"


def test_slugify_collapses_and_strips():
    assert ws.slugify("--Hello   World--") == "hello-world"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        ws.slugify("___")


def test_atomic_write_json_no_tmp_leftover(tmp_path):
    target = tmp_path / "sub" / "record.json"
    ok = ws._atomic_write_json(target, {"a": 1})
    assert ok is True
    assert target.exists()
    assert json.loads(target.read_text()) == {"a": 1}
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_sibling_imports_resolve():
    assert hasattr(ws, "branch_hygiene")
    assert hasattr(ws, "get_session_uuid")
    assert callable(ws.branch_hygiene.discover_repos)
    assert callable(ws.get_session_uuid.get_session_uuid)


def test_iso_to_epoch_roundtrip():
    now_iso = ws._utc_now_iso()
    epoch = ws._iso_to_epoch(now_iso)
    assert isinstance(epoch, float)
    assert ws._iso_to_epoch("") is None
    assert ws._iso_to_epoch(None) is None
    assert ws._iso_to_epoch("not-a-date") is None


# ---------------------------------------------------------------------------
# T-02: repo discovery + selection
# ---------------------------------------------------------------------------

def test_discover_multi(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    repos = ws.discover_workspace_repos(project_root)
    names = sorted(p.name for p in repos)
    assert names == ["repo-a", "repo-b"]


def test_discover_named_subset(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    repos = ws.discover_workspace_repos(project_root, named=["repo-a"])
    assert [p.name for p in repos] == ["repo-a"]


def test_discover_unknown_name_errors(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    with pytest.raises(ValueError, match="repo-zzz"):
        ws.discover_workspace_repos(project_root, named=["repo-zzz"])


def test_discover_excludes_workspaces(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws_dir = project_root / ".workspaces" / "some-feature" / "repo-a"
    ws_dir.mkdir(parents=True)
    (ws_dir / ".git").write_text("gitdir: /nowhere")
    repos = ws.discover_workspace_repos(project_root)
    assert all(".workspaces" not in str(p) for p in repos)


def test_discover_single_repo_degrade(tmp_path):
    project_root = tmp_path / "solo"
    make_git_repo(project_root)
    repos = ws.discover_workspace_repos(project_root)
    assert len(repos) == 1
    assert repos[0].resolve() == project_root.resolve()


# ---------------------------------------------------------------------------
# T-03: default-branch resolution + worktree add
# ---------------------------------------------------------------------------

def test_add_worktree_creates_on_feature_branch(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    orig_branch = repo_current_branch(repo)
    dest = tmp_path / "ws" / "repo"
    result = ws.add_worktree(repo, "my-feature", dest)
    assert result.created is True
    assert result.error is None
    assert repo_current_branch(dest) == "my-feature"
    assert repo_current_branch(repo) == orig_branch


def test_add_worktree_base_ref(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    orig_branch = repo_current_branch(repo)
    dest = tmp_path / "ws" / "repo"
    result = ws.add_worktree(repo, "feat-base", dest, base=orig_branch)
    assert result.created is True
    assert repo_current_branch(dest) == "feat-base"


def test_add_worktree_idempotent_skip(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    dest = tmp_path / "ws" / "repo"
    first = ws.add_worktree(repo, "feat-x", dest)
    assert first.created is True
    second = ws.add_worktree(repo, "feat-x", dest)
    assert second.skipped is True
    assert second.error is None


def test_add_worktree_branch_already_checked_out(tmp_path):
    repo = make_git_repo(tmp_path / "repo")
    dest1 = tmp_path / "ws" / "repo"
    dest2 = tmp_path / "ws2" / "repo"
    first = ws.add_worktree(repo, "shared-feat", dest1)
    assert first.created is True
    second = ws.add_worktree(repo, "shared-feat", dest2)
    assert second.created is False
    assert second.error is not None
    assert "already checked out" in second.error


# ---------------------------------------------------------------------------
# T-04: ownership record + marker
# ---------------------------------------------------------------------------

def test_record_fields_present(tmp_path):
    rec = ws.build_record(
        feature="my-feat", slug="my-feat", session_uuid="uuid-123",
        repos=["repo-a"], branches={"repo-a": "my-feat"},
        workspace_path=tmp_path / ".workspaces" / "my-feat",
    )
    for field in ("feature", "owner_session_uuid", "hostname", "pid", "pid_start_time",
                  "created", "last_seen", "repos", "branches", "workspace_path"):
        assert field in rec


def test_record_caller_uuid_verbatim(tmp_path):
    rec = ws.build_record(
        feature="f", slug="f", session_uuid="caller-uuid-verbatim",
        repos=[], branches={}, workspace_path=tmp_path,
    )
    assert rec["owner_session_uuid"] == "caller-uuid-verbatim"


def test_marker_artifact_root(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    ws_root = tmp_path / "ws"
    ok = ws.write_marker(ws_root, artifact_root=project_root, feature="f", repos=["repo-a"])
    assert ok is True
    marker = json.loads((ws_root / ".quoin-workspace.json").read_text())
    assert marker["artifact_root"] == str(project_root.resolve())
    assert marker["feature"] == "f"


def test_marker_write_failure_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "_atomic_write_json", lambda path, obj: False)
    ok = ws.write_marker(tmp_path / "ws", artifact_root=tmp_path, feature="f", repos=[])
    assert ok is False


def test_owner_live_fresh_vs_stale():
    fresh = {"last_seen": ws._utc_now_iso()}
    assert ws._owner_is_live(fresh) is True

    stale_epoch = time.time() - (7 * 3600)
    stale = {"last_seen": None, "_record_mtime": stale_epoch}
    assert ws._owner_is_live(stale) is False


def test_owner_live_bad_last_seen_uses_mtime():
    fresh_mtime = time.time()
    rec = {"last_seen": "garbage-not-a-date", "_record_mtime": fresh_mtime}
    assert ws._owner_is_live(rec) is True

    stale_mtime = time.time() - (7 * 3600)
    rec2 = {"last_seen": "garbage-not-a-date", "_record_mtime": stale_mtime}
    assert ws._owner_is_live(rec2) is False


# ---------------------------------------------------------------------------
# T-05: create_workspace orchestrator
# ---------------------------------------------------------------------------

def test_create_multi_repo_end_to_end(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    result = ws.create_workspace("my-feature", project_root, session_uuid="uuid-A")
    assert result.refused is False
    assert result.record_written is True
    assert result.marker_written is True
    assert len(result.per_repo) == 2
    for r in result.per_repo:
        assert r.created is True
        orig = project_root / Path(r.repo).name
        assert "worktree " + r.dest in worktree_list(orig)
        assert repo_current_branch(orig) != "my-feature"


def test_create_single_repo_end_to_end(tmp_path):
    project_root = tmp_path / "solo"
    make_git_repo(project_root)
    result = ws.create_workspace("solo-feat", project_root, session_uuid="uuid-solo")
    assert result.refused is False
    assert len(result.per_repo) == 1
    assert result.record_written is True


def test_create_idempotent_rerun(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    first = ws.create_workspace("re-feat", project_root, session_uuid="uuid-same")
    assert first.record_written is True
    second = ws.create_workspace("re-feat", project_root, session_uuid="uuid-same")
    assert second.refused is False
    assert all(r.skipped for r in second.per_repo)


def test_create_rerun_derived_uuid_drift_ambiguous(tmp_path, monkeypatch):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    # Seed a LIVE record owned by a uuid that will differ from the derived one.
    first = ws.create_workspace("drift-feat", project_root, session_uuid="owner-uuid")
    assert first.record_written is True

    monkeypatch.setattr(
        ws.get_session_uuid, "get_session_uuid",
        lambda project_path=None, home=None, phase=None: "derived-different-uuid",
    )
    result = ws.create_workspace("drift-feat", project_root, session_uuid=None)
    assert result.refused is True
    assert result.ambiguous is True
    # Worktrees/record untouched — no new per_repo entries attempted.
    assert result.per_repo == []


def test_create_partial_then_resume(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a", "repo-b"])
    # Pre-block repo-b by checking out the feature branch in its primary tree.
    repo_b = project_root / "repo-b"
    subprocess.run(
        ["git", "-C", str(repo_b), "checkout", "-b", "partial-feat"],
        capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    result = ws.create_workspace("partial-feat", project_root, session_uuid="uuid-p")
    errored = [r for r in result.per_repo if r.error is not None]
    succeeded = [r for r in result.per_repo if r.created or r.skipped]
    assert len(errored) == 1
    assert len(succeeded) == 1
    assert result.record_written is True

    # Resume: switch repo-b back so the branch is free, re-run.
    subprocess.run(
        ["git", "-C", str(repo_b), "checkout", "-"],
        capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        ["git", "-C", str(repo_b), "branch", "-D", "partial-feat"],
        capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    resumed = ws.create_workspace("partial-feat", project_root, session_uuid="uuid-p")
    assert all(r.created or r.skipped for r in resumed.per_repo)


def test_create_zero_success_no_record(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    repo_a = project_root / "repo-a"
    subprocess.run(
        ["git", "-C", str(repo_a), "checkout", "-b", "blocked-feat"],
        capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT,
    )
    result = ws.create_workspace("blocked-feat", project_root, session_uuid="uuid-z")
    assert result.record_written is False
    assert result.marker_written is False
    assert not (project_root / ".workflow_artifacts" / "memory" / "workspaces" / "blocked-feat.json").exists()


def test_create_refuses_live_non_self_owner(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    seeded = ws.create_workspace("takeover-feat", project_root, session_uuid="owner-A")
    assert seeded.record_written is True
    # workspace_path in the seeded record equals str(ws_root) genuinely (non-vacuous).
    rec = ws.read_ownership_record(project_root, "takeover-feat")
    assert rec["workspace_path"] == str(project_root / ".workspaces" / "takeover-feat")

    result = ws.create_workspace("takeover-feat", project_root, session_uuid="owner-B")
    assert result.refused is True
    assert result.ambiguous is False
    assert "takeover" in result.message


def test_create_cwd_as_repo_gitignore(tmp_path):
    project_root = tmp_path / "solo"
    make_git_repo(project_root)
    ws.create_workspace("gi-feat", project_root, session_uuid="uuid-gi")
    gitignore = (project_root / ".gitignore").read_text()
    assert gitignore.count(".workspaces/") == 1
    # No substring false-match: a pre-existing ".workspaces/foo" line must not satisfy the check.
    (project_root / ".gitignore").write_text(gitignore + ".workspaces/foo\n")
    ws.create_workspace("gi-feat", project_root, session_uuid="uuid-gi")
    final = (project_root / ".gitignore").read_text()
    assert final.count(".workspaces/\n") == 1


def test_create_marker_write_failure_flagged(tmp_path, monkeypatch):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])

    orig_atomic = ws._atomic_write_json
    calls = {"n": 0}

    def flaky(path, obj):
        calls["n"] += 1
        if "quoin-workspace.json" in str(path):
            return False
        return orig_atomic(path, obj)

    monkeypatch.setattr(ws, "_atomic_write_json", flaky)
    result = ws.create_workspace("mk-feat", project_root, session_uuid="uuid-mk")
    assert result.record_written is True
    assert result.marker_written is False


# ---------------------------------------------------------------------------
# T-06: CLI
# ---------------------------------------------------------------------------

def run_cli(script_path: Path, *args, cwd=None):
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, cwd=cwd)


def test_cli_create_end_to_end(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    proc = run_cli(CORE_PATH, "create", "cli-feat", "--project-root", str(project_root))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["marker_written"] is True


def test_cli_session_uuid_stored(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    proc = run_cli(
        CORE_PATH, "create", "cli-uuid-feat", "--project-root", str(project_root),
        "--session-uuid", "explicit-cli-uuid",
    )
    assert proc.returncode == 0, proc.stderr
    rec = json.loads(
        (project_root / ".workflow_artifacts" / "memory" / "workspaces" / "cli-uuid-feat.json").read_text()
    )
    assert rec["owner_session_uuid"] == "explicit-cli-uuid"


def test_cli_refuse_exit3(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    proc1 = run_cli(
        CORE_PATH, "create", "cli-refuse-feat", "--project-root", str(project_root),
        "--session-uuid", "owner-X",
    )
    assert proc1.returncode == 0, proc1.stderr
    proc2 = run_cli(
        CORE_PATH, "create", "cli-refuse-feat", "--project-root", str(project_root),
        "--session-uuid", "owner-Y",
    )
    assert proc2.returncode == 3


def test_cli_badargs_exit2(tmp_path):
    proc = run_cli(CORE_PATH, "not-a-real-subcommand")
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# T-07: wrapper parity
# ---------------------------------------------------------------------------

def test_wrapper_reexports_public_api():
    spec = importlib.util.spec_from_file_location("_test_wrapper_workspace", WRAPPER_PATH)
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = wrapper
    spec.loader.exec_module(wrapper)
    assert hasattr(wrapper, "create_workspace")
    assert hasattr(wrapper, "main")
    assert callable(wrapper.create_workspace)


def test_wrapper_cli_parity(tmp_path):
    project_core = make_multi_repo_project(tmp_path / "core_side", ["repo-a"])
    project_wrapper = make_multi_repo_project(tmp_path / "wrapper_side", ["repo-a"])

    core_proc = run_cli(CORE_PATH, "create", "parity-feat", "--project-root", str(project_core))
    wrapper_proc = run_cli(WRAPPER_PATH, "create", "parity-feat", "--project-root", str(project_wrapper))

    assert core_proc.returncode == wrapper_proc.returncode == 0
    core_payload = json.loads(core_proc.stdout)
    wrapper_payload = json.loads(wrapper_proc.stdout)
    assert core_payload.keys() == wrapper_payload.keys()
    assert core_payload["record_written"] == wrapper_payload["record_written"] is True
