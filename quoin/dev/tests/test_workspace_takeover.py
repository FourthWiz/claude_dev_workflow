"""Tests for workspace.py S-04 — owner-liveness, takeover, heartbeat, and the
untrusted-record structural guard (IVG-158, S-04).

Loads the core module via importlib (real file path); exercises the Python API
directly and the CLI via subprocess. JSONL-liveness fixtures thread a hermetic
fake ``home`` (direct call) / ``--home`` (subprocess) so no test ever touches the
real ``~/.claude``. Freshness is controlled with ``os.utime`` (deterministic,
no real-clock races). No network; all git fixtures are ephemeral under tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).parent.parent.parent / "core" / "scripts"
CORE_PATH = CORE_DIR / "workspace.py"
WRAPPER_PATH = Path(__file__).parent.parent.parent / "scripts" / "workspace.py"

SUBPROCESS_TIMEOUT = 60  # generous headroom — Drive-mount/cloud-fs flake lesson

STALE_SECONDS = 7 * 3600  # > default 6h QUOIN_WORKSPACE_STALE_HOURS threshold


def _load_core():
    """Load workspace.py via importlib from its real file path (sibling imports resolve)."""
    spec = importlib.util.spec_from_file_location("_test_core_workspace_s04", CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ws = _load_core()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True, timeout=SUBPROCESS_TIMEOUT)
    subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, check=True,
                   cwd=str(path), timeout=SUBPROCESS_TIMEOUT)
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, check=True,
                   cwd=str(path), timeout=SUBPROCESS_TIMEOUT)
    (path / ".gitkeep").write_text("placeholder")
    subprocess.run(["git", "add", ".gitkeep"], capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT)
    subprocess.run(["git", "commit", "-m", "init"], capture_output=True, check=True, cwd=str(path), timeout=SUBPROCESS_TIMEOUT)
    return path


def make_multi_repo_project(tmp_path: Path, names: list[str]) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        make_git_repo(project_root / name)
    return project_root


def git_status_porcelain(repo: Path) -> str:
    out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                         capture_output=True, text=True, check=True, timeout=SUBPROCESS_TIMEOUT)
    return out.stdout


def run_cli(script_path: Path, *args, cwd=None):
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT, cwd=cwd)


def make_owner_jsonl(fake_home: Path, owner: str, projdir_name: str, mtime: float) -> Path:
    """Place <fake_home>/.claude/projects/<projdir_name>/<owner>.jsonl with a known mtime."""
    p = fake_home / ".claude" / "projects" / projdir_name / f"{owner}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"type":"summary"}\n')
    os.utime(p, (mtime, mtime))
    return p


def stale_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=STALE_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_record_file(project_root: Path, slug: str) -> dict:
    return json.loads(ws._record_path(project_root, slug).read_text())


def staleify_record(project_root: Path, slug: str) -> None:
    """Force both the last_seen field and the file mtime to a stale value."""
    path = ws._record_path(project_root, slug)
    rec = json.loads(path.read_text())
    rec["last_seen"] = stale_iso()
    path.write_text(json.dumps(rec, indent=2) + "\n")
    st = time.time() - STALE_SECONDS
    os.utime(path, (st, st))


# ---------------------------------------------------------------------------
# T-01: reader hardening (isinstance(dict) guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", ["[]", "42", '"x"', "true", "null"])
def test_read_record_non_dict_body_returns_none(tmp_path, body):
    pr = tmp_path / "proj"
    ws._record_path(pr, "feat").parent.mkdir(parents=True, exist_ok=True)
    ws._record_path(pr, "feat").write_text(body)
    assert ws.read_ownership_record(pr, "feat") is None


@pytest.mark.parametrize("body", ["[]", "42", '"x"', "true", "null"])
def test_read_record_with_mtime_non_dict_body_returns_none(tmp_path, body):
    pr = tmp_path / "proj"
    ws._record_path(pr, "feat").parent.mkdir(parents=True, exist_ok=True)
    ws._record_path(pr, "feat").write_text(body)
    assert ws._read_ownership_record_with_mtime(pr, "feat") is None


def test_read_record_valid_dict_positive(tmp_path):
    pr = tmp_path / "proj"
    ws._record_path(pr, "feat").parent.mkdir(parents=True, exist_ok=True)
    ws._record_path(pr, "feat").write_text('{"owner_session_uuid": "abc"}')
    assert ws.read_ownership_record(pr, "feat") == {"owner_session_uuid": "abc"}
    with_mtime = ws._read_ownership_record_with_mtime(pr, "feat")
    assert with_mtime["owner_session_uuid"] == "abc"
    assert isinstance(with_mtime["_record_mtime"], float)


def test_read_record_corrupt_json_returns_none(tmp_path):
    pr = tmp_path / "proj"
    ws._record_path(pr, "feat").parent.mkdir(parents=True, exist_ok=True)
    ws._record_path(pr, "feat").write_text("{not json")
    assert ws.read_ownership_record(pr, "feat") is None
    assert ws._read_ownership_record_with_mtime(pr, "feat") is None


# ---------------------------------------------------------------------------
# T-02: _owner_jsonl_mtime — owner-keyed, launch-cwd-independent locator
# ---------------------------------------------------------------------------

def test_owner_jsonl_mtime_found_under_original_repo_hash(tmp_path):
    """The discriminating case: transcript under an ORIGINAL-repo-dir hash that is
    NEITHER the project-root NOR the workspace hash is still located (owner-keyed)."""
    fake_home = tmp_path / "home"
    project_root = tmp_path / "project"
    owner = "owner-A"
    # project_hash of a launch dir that is an original repo dir — the exact case
    # the old 3-candidate project_hash set missed.
    projdir = ws.get_session_uuid.project_hash(str(project_root / "some-repo"))
    mtime = time.time()
    make_owner_jsonl(fake_home, owner, projdir, mtime)
    got = ws._owner_jsonl_mtime({"owner_session_uuid": owner}, home=str(fake_home))
    assert got == pytest.approx(mtime, abs=1)


def test_owner_jsonl_mtime_synthetic_owner_short_circuits(tmp_path):
    fake_home = tmp_path / "home"
    # Even if a matching file exists, an unknown-* owner must never scan for it.
    make_owner_jsonl(fake_home, "unknown-implement-20260101T000000Z", "any-hash", time.time())
    assert ws._owner_jsonl_mtime(
        {"owner_session_uuid": "unknown-implement-20260101T000000Z"}, home=str(fake_home)
    ) is None


def test_owner_jsonl_mtime_missing_transcript_returns_none(tmp_path):
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "projects" / "some-hash").mkdir(parents=True)
    assert ws._owner_jsonl_mtime({"owner_session_uuid": "owner-Z"}, home=str(fake_home)) is None


def test_owner_jsonl_mtime_absent_projects_dir_returns_none(tmp_path):
    fake_home = tmp_path / "home"  # no .claude/projects at all
    assert ws._owner_jsonl_mtime({"owner_session_uuid": "owner-Z"}, home=str(fake_home)) is None


@pytest.mark.parametrize("owner", [None, 42, "", [], {}])
def test_owner_jsonl_mtime_bad_owner_returns_none(tmp_path, owner):
    fake_home = tmp_path / "home"
    assert ws._owner_jsonl_mtime({"owner_session_uuid": owner}, home=str(fake_home)) is None


@pytest.mark.parametrize("rec", [
    {"owner_session_uuid": "x", "repos": 42},
    {"owner_session_uuid": "x", "repos": [123]},
    {"owner_session_uuid": "x", "workspace_path": 99},
])
def test_owner_jsonl_mtime_corrupt_nested_fields_no_raise(tmp_path, rec):
    """C3-specific smoke: corrupt nested fields never raise (hermetic fake home)."""
    fake_home = tmp_path / "home"
    assert ws._owner_jsonl_mtime(rec, home=str(fake_home)) is None


def test_owner_jsonl_mtime_picks_freshest_across_dirs(tmp_path):
    fake_home = tmp_path / "home"
    owner = "owner-dup"
    older = time.time() - 100
    newer = time.time()
    make_owner_jsonl(fake_home, owner, "hash-1", older)
    make_owner_jsonl(fake_home, owner, "hash-2", newer)
    got = ws._owner_jsonl_mtime({"owner_session_uuid": owner}, home=str(fake_home))
    assert got == pytest.approx(newer, abs=1)


# ---------------------------------------------------------------------------
# T-03: _owner_is_live — JSONL primary folded in front of the fallback
# ---------------------------------------------------------------------------

def test_owner_is_live_jsonl_primary_overrides_stale_last_seen(tmp_path):
    fake_home = tmp_path / "home"
    owner = "owner-live"
    make_owner_jsonl(fake_home, owner, "some-hash", time.time())  # FRESH transcript
    rec = {"owner_session_uuid": owner, "last_seen": stale_iso(), "_record_mtime": time.time() - STALE_SECONDS}
    assert ws._owner_is_live(rec, home=str(fake_home)) is True


def test_owner_is_live_stale_all_signals(tmp_path):
    fake_home = tmp_path / "home"
    owner = "owner-dead"
    make_owner_jsonl(fake_home, owner, "some-hash", time.time() - STALE_SECONDS)  # STALE transcript
    rec = {"owner_session_uuid": owner, "last_seen": stale_iso(), "_record_mtime": time.time() - STALE_SECONDS}
    assert ws._owner_is_live(rec, home=str(fake_home)) is False


def test_owner_is_live_no_jsonl_fresh_last_seen(tmp_path):
    fake_home = tmp_path / "home"  # no transcript
    rec = {"owner_session_uuid": "owner-none", "last_seen": ws._utc_now_iso()}
    assert ws._owner_is_live(rec, home=str(fake_home)) is True


def test_owner_is_live_no_signal_returns_false(tmp_path):
    fake_home = tmp_path / "home"
    assert ws._owner_is_live({"owner_session_uuid": "owner-none"}, home=str(fake_home)) is False


def test_owner_is_live_backward_compat_no_owner_key(tmp_path):
    """Existing S-01 behaviour: a record with NO owner key reduces to last_seen/mtime."""
    fake_home = tmp_path / "home"
    assert ws._owner_is_live({"last_seen": ws._utc_now_iso()}, home=str(fake_home)) is True
    assert ws._owner_is_live(
        {"last_seen": None, "_record_mtime": time.time() - STALE_SECONDS}, home=str(fake_home)
    ) is False


def test_owner_is_live_corrupt_record_mtime_no_raise(tmp_path):
    fake_home = tmp_path / "home"
    rec = {"owner_session_uuid": "owner-x", "_record_mtime": "boom"}
    assert ws._owner_is_live(rec, home=str(fake_home)) is False


# ---------------------------------------------------------------------------
# T-04: takeover_workspace — non-destructive record flip (D-05, R-02 proof)
# ---------------------------------------------------------------------------

def test_takeover_stale_reassigns_and_preserves_worktree_bytes(tmp_path):
    """The R-02 safety proof: a stale takeover flips the record but byte-preserves
    all uncommitted work and leaves git status untouched."""
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    create = ws.create_workspace("wt-feat", project_root, session_uuid="owner-X")
    slug = create.slug
    ws_repo = Path(create.workspace_path) / "repo-a"
    dirty = ws_repo / "dirty.txt"
    dirty.write_text("uncommitted-work-bytes")
    before_bytes = dirty.read_bytes()
    before_status = git_status_porcelain(ws_repo)

    before_rec = read_record_file(project_root, slug)
    staleify_record(project_root, slug)

    result = ws.takeover_workspace("wt-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert result.took_over is True
    assert result.prior_owner == "owner-X"
    assert result.new_owner == "owner-Y"

    after_rec = read_record_file(project_root, slug)
    assert after_rec["owner_session_uuid"] == "owner-Y"
    # Preserved fields byte-identical.
    for k in ("feature", "created", "repos", "branches", "workspace_path"):
        assert after_rec[k] == before_rec[k]
    # Internal read-time key never persisted.
    assert "_record_mtime" not in after_rec
    # Working tree untouched.
    assert dirty.read_bytes() == before_bytes
    assert git_status_porcelain(ws_repo) == before_status


def test_takeover_fresh_last_seen_owner_refused(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws.create_workspace("live-feat", project_root, session_uuid="owner-X")
    before = read_record_file(project_root, "live-feat")
    result = ws.takeover_workspace("live-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert result.refused is True
    assert result.live is True
    assert result.took_over is False
    assert read_record_file(project_root, "live-feat") == before  # unchanged


def test_takeover_force_overrides_live(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws.create_workspace("force-feat", project_root, session_uuid="owner-X")
    result = ws.takeover_workspace("force-feat", project_root, session_uuid="owner-Y",
                                   force=True, home=str(fake_home))
    assert result.took_over is True
    assert read_record_file(project_root, "force-feat")["owner_session_uuid"] == "owner-Y"


def test_takeover_self_owner_idempotent(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    ws.create_workspace("self-feat", project_root, session_uuid="owner-X")
    result = ws.takeover_workspace("self-feat", project_root, session_uuid="owner-X", home=str(fake_home))
    assert result.took_over is True
    assert result.refused is False
    assert read_record_file(project_root, "self-feat")["owner_session_uuid"] == "owner-X"


def test_takeover_no_record(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    result = ws.takeover_workspace("never-created", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert result.no_record is True
    assert result.took_over is False


def test_takeover_missing_owner_key_stale_flips_cleanly(tmp_path):
    """ROUND-3 MAJ-1 regression: a dict record MISSING owner_session_uuid with a
    stale mtime flips cleanly (prior_owner == '') and NEVER raises KeyError."""
    fake_home = tmp_path / "home"
    project_root = tmp_path / "proj"
    slug = "orphan-feat"
    path = ws._record_path(project_root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"feature": "orphan-feat", "repos": ["r"]}, indent=2) + "\n")
    st = time.time() - STALE_SECONDS
    os.utime(path, (st, st))
    result = ws.takeover_workspace("orphan-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert result.took_over is True
    assert result.prior_owner == ""
    after = read_record_file(project_root, slug)
    assert after["owner_session_uuid"] == "owner-Y"
    assert isinstance(after, dict)


def test_takeover_record_mtime_fallback_stale_vs_fresh(tmp_path):
    """Synthetic unknown-* owner (no JSONL): last_seen/mtime fallback drives the gate."""
    fake_home = tmp_path / "home"
    project_root = tmp_path / "proj"
    slug = "fb-feat"
    path = ws._record_path(project_root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Fresh last_seen -> live -> refused.
    path.write_text(json.dumps({"owner_session_uuid": "unknown-x-1", "last_seen": ws._utc_now_iso()}) + "\n")
    r1 = ws.takeover_workspace("fb-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert r1.refused is True
    # Stale last_seen + stale mtime -> reassigned.
    staleify_record(project_root, slug)
    r2 = ws.takeover_workspace("fb-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
    assert r2.took_over is True


# ---------------------------------------------------------------------------
# T-05: CLI takeover + exit-code contract + wrapper parity
# ---------------------------------------------------------------------------

def _empty_home(tmp_path) -> str:
    h = tmp_path / "cli-home"
    h.mkdir(parents=True, exist_ok=True)
    return str(h)


def test_cli_takeover_stale_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    run_cli(CORE_PATH, "create", "cli-tk", "--project-root", str(project_root), "--session-uuid", "owner-X")
    staleify_record(project_root, "cli-tk")
    proc = run_cli(CORE_PATH, "takeover", "cli-tk", "--project-root", str(project_root),
                   "--session-uuid", "owner-Y", "--home", _empty_home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert read_record_file(project_root, "cli-tk")["owner_session_uuid"] == "owner-Y"


def test_cli_takeover_live_exit3_then_force_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    run_cli(CORE_PATH, "create", "cli-live", "--project-root", str(project_root), "--session-uuid", "owner-X")
    before = read_record_file(project_root, "cli-live")
    proc = run_cli(CORE_PATH, "takeover", "cli-live", "--project-root", str(project_root),
                   "--session-uuid", "owner-Y", "--home", _empty_home(tmp_path))
    assert proc.returncode == 3
    assert read_record_file(project_root, "cli-live") == before
    proc2 = run_cli(CORE_PATH, "takeover", "cli-live", "--project-root", str(project_root),
                    "--session-uuid", "owner-Y", "--force", "--home", _empty_home(tmp_path))
    assert proc2.returncode == 0, proc2.stderr


def test_cli_takeover_no_record_exit4(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    proc = run_cli(CORE_PATH, "takeover", "ghost-feat", "--project-root", str(project_root),
                   "--session-uuid", "owner-Y", "--home", _empty_home(tmp_path))
    assert proc.returncode == 4


def test_cli_takeover_badargs_exit2(tmp_path):
    proc = run_cli(CORE_PATH, "takeover")  # missing required feature
    assert proc.returncode == 2


def test_wrapper_reexports_takeover_and_heartbeat():
    spec = importlib.util.spec_from_file_location("_test_wrapper_workspace_s04", WRAPPER_PATH)
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = wrapper
    spec.loader.exec_module(wrapper)
    assert hasattr(wrapper, "takeover_workspace")
    assert hasattr(wrapper, "heartbeat_workspace")
    assert callable(wrapper.takeover_workspace)


# ---------------------------------------------------------------------------
# T-06: heartbeat_workspace + marker walk-up (owner-only refresh)
# ---------------------------------------------------------------------------

def test_heartbeat_owner_refreshes_last_seen(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    create = ws.create_workspace("hb-feat", project_root, session_uuid="owner-H")
    ws_root = Path(create.workspace_path)
    staleify_record(project_root, "hb-feat")
    old = read_record_file(project_root, "hb-feat")["last_seen"]
    ok = ws.heartbeat_workspace(cwd=ws_root / "repo-a", session_uuid="owner-H", home=str(fake_home))
    assert ok is True
    new = read_record_file(project_root, "hb-feat")["last_seen"]
    assert new != old
    assert ws._iso_to_epoch(new) > ws._iso_to_epoch(old)


def test_heartbeat_non_owner_no_op(tmp_path):
    fake_home = tmp_path / "home"
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    create = ws.create_workspace("hb-feat2", project_root, session_uuid="owner-H")
    ws_root = Path(create.workspace_path)
    before = read_record_file(project_root, "hb-feat2")
    ok = ws.heartbeat_workspace(cwd=ws_root, session_uuid="someone-else", home=str(fake_home))
    assert ok is False
    assert read_record_file(project_root, "hb-feat2") == before


def test_heartbeat_outside_workspace_no_op(tmp_path):
    fake_home = tmp_path / "home"
    outside = tmp_path / "nowhere"
    outside.mkdir(parents=True)
    assert ws.heartbeat_workspace(cwd=outside, session_uuid="anyone", home=str(fake_home)) is False


@pytest.mark.parametrize("marker_body", ["42", "[]", '"x"', "{not json"])
def test_heartbeat_corrupt_marker_no_raise(tmp_path, marker_body):
    fake_home = tmp_path / "home"
    ws_root = tmp_path / "ws"
    ws_root.mkdir(parents=True)
    (ws_root / ".quoin-workspace.json").write_text(marker_body)
    assert ws.heartbeat_workspace(cwd=ws_root, session_uuid="anyone", home=str(fake_home)) is False


def test_heartbeat_marker_missing_fields_no_op(tmp_path):
    fake_home = tmp_path / "home"
    ws_root = tmp_path / "ws"
    ws_root.mkdir(parents=True)
    (ws_root / ".quoin-workspace.json").write_text(json.dumps({"repos": ["r"]}))  # no artifact_root/feature
    assert ws.heartbeat_workspace(cwd=ws_root, session_uuid="anyone", home=str(fake_home)) is False


def test_cli_heartbeat_exit0(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    create = ws.create_workspace("cli-hb", project_root, session_uuid="owner-H")
    ws_root = Path(create.workspace_path)
    proc = run_cli(CORE_PATH, "heartbeat", "--cwd", str(ws_root), "--session-uuid", "owner-H",
                   "--home", _empty_home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["refreshed"] is True


def test_cli_heartbeat_non_owner_exit0_false(tmp_path):
    project_root = make_multi_repo_project(tmp_path, ["repo-a"])
    create = ws.create_workspace("cli-hb2", project_root, session_uuid="owner-H")
    ws_root = Path(create.workspace_path)
    proc = run_cli(CORE_PATH, "heartbeat", "--cwd", str(ws_root), "--session-uuid", "not-owner",
                   "--home", _empty_home(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["refreshed"] is False


# ---------------------------------------------------------------------------
# T-07: sessionstart.sh heartbeat wiring (presence + fail-OPEN structure)
# ---------------------------------------------------------------------------

def test_sessionstart_heartbeat_block_wired():
    """Guard the opt-in wiring: raw_cwd capture before resolve_project_root, the
    env gate, and the fail-OPEN suppression idioms that keep the hook fail-OPEN."""
    hook = (Path(__file__).parent.parent.parent / "hooks" / "sessionstart.sh").read_text()
    # raw_cwd captured before the project-root rewrite.
    assert 'raw_cwd="$cwd"' in hook
    assert hook.index('raw_cwd="$cwd"') < hook.index('cwd=$(resolve_project_root "$cwd")')
    # Opt-in gate, default OFF.
    assert '"${QUOIN_WORKSPACE_HEARTBEAT:-0}" = "1"' in hook
    # Shells out to workspace.py heartbeat with the raw cwd + session id.
    assert "workspace.py" in hook and "heartbeat" in hook
    assert '--cwd "$raw_cwd"' in hook
    # Fail-OPEN: output suppressed and || true so it can never change stdout/exit.
    block = hook[hook.index("S-04 workspace heartbeat"):]
    assert ">/dev/null 2>&1" in block
    assert "|| true" in block


# ---------------------------------------------------------------------------
# T-09: structural untrusted-record guard — full corpus x every consumer
# ---------------------------------------------------------------------------
#
# INVARIANT: every on-disk-record/marker consumer either (a) has a whole-body
# fail-OPEN exception wrap returning its sentinel, or (b) accesses every field via
# .get(key[, default]) — NEVER a bare subscript on an untrusted dict. This test
# feeds the full corrupt-record corpus through EVERY consumer and asserts none
# raises. Mutation-checked (documented): deleting any one guard flips exactly that
# consumer's row RED.

# (id, json-encodable body)
_CORPUS = [
    ("list", []),
    ("int", 42),
    ("str", "x"),
    ("bool", True),
    ("null", None),
    ("empty_dict", {}),
    ("owner_non_str", {"owner_session_uuid": 42}),
    ("repos_int", {"owner_session_uuid": "x", "repos": 42}),
    ("repos_list_int", {"owner_session_uuid": "x", "repos": [123]}),
    ("workspace_path_int", {"owner_session_uuid": "x", "workspace_path": 99}),
    ("last_seen_dict", {"owner_session_uuid": "x", "last_seen": {}}),
    ("last_seen_int", {"owner_session_uuid": "x", "last_seen": 123}),
    ("record_mtime_str", {"owner_session_uuid": "x", "_record_mtime": "boom"}),
]

_CORPUS_IDS = [c[0] for c in _CORPUS]
_CORPUS_BODIES = [c[1] for c in _CORPUS]

_CONSUMERS = ["c1", "c2", "c3", "c4", "c5", "c6"]


def _write_record_raw(project_root: Path, slug: str, body, stale: bool = False) -> None:
    path = ws._record_path(project_root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body))
    if stale:
        st = time.time() - STALE_SECONDS
        os.utime(path, (st, st))


@pytest.mark.parametrize("consumer", _CONSUMERS)
@pytest.mark.parametrize("body", _CORPUS_BODIES, ids=_CORPUS_IDS)
def test_untrusted_record_guard(tmp_path, consumer, body):
    """Every (consumer, corpus-item) pair returns its fail-OPEN sentinel, never raises."""
    fake_home = tmp_path / "home"
    project_root = tmp_path / "proj"
    slug = "guard-feat"

    if consumer == "c1":
        _write_record_raw(project_root, slug, body)
        out = ws.read_ownership_record(project_root, slug)
        assert out is None or isinstance(out, dict)
    elif consumer == "c2":
        _write_record_raw(project_root, slug, body)
        out = ws._read_ownership_record_with_mtime(project_root, slug)
        assert out is None or isinstance(out, dict)
    elif consumer == "c3":
        out = ws._owner_jsonl_mtime(body, home=str(fake_home))
        assert out is None or isinstance(out, float)
    elif consumer == "c4":
        out = ws._owner_is_live(body, home=str(fake_home))
        assert isinstance(out, bool)
    elif consumer == "c5":
        # STALE mtime so the flip path (not the refuse path) is exercised.
        _write_record_raw(project_root, slug, body, stale=True)
        out = ws.takeover_workspace("guard-feat", project_root, session_uuid="owner-Y", home=str(fake_home))
        assert isinstance(out, ws.TakeoverResult)
        # A dict body that flips must leave a well-formed dict on disk.
        if out.took_over:
            assert isinstance(read_record_file(project_root, slug), dict)
    elif consumer == "c6":
        ws_root = tmp_path / "ws"
        ws_root.mkdir(parents=True, exist_ok=True)
        (ws_root / ".quoin-workspace.json").write_text(
            json.dumps({"artifact_root": str(project_root), "feature": "guard-feat"})
        )
        _write_record_raw(project_root, slug, body)
        out = ws.heartbeat_workspace(cwd=ws_root, session_uuid="owner-H", home=str(fake_home))
        assert isinstance(out, bool)
