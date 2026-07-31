#!/usr/bin/env python3
"""Portable core implementation of feature-workspace create + teardown (IVG-158).

Gives each in-flight feature its own isolated per-repo git worktree so
concurrent Claude Code sessions never share a mutable branch on the same
repo. This module owns the ``create`` subcommand (S-01) and the ``teardown``
subcommand (S-03) — no takeover, no full liveness. See architecture.md
D-01..D-09.

Public API:
  discover_workspace_repos(project_root, named=None) -> list[Path]
  default_branch(repo) -> str
  add_worktree(repo, feature, dest, base=None) -> WorktreeResult
  read_ownership_record(project_root, slug) -> dict | None
  write_ownership_record(project_root, slug, record) -> bool
  build_record(feature, slug, session_uuid, repos, branches, workspace_path) -> dict
  write_marker(workspace_root, artifact_root, feature, repos) -> bool
  create_workspace(feature, project_root, named_repos=None, base=None,
                    session_uuid=None) -> CreateResult
  discover_workspace_worktrees(ws_root) -> list[Path]
  teardown_workspace(feature, project_root, force=False) -> TeardownResult
  main(argv: list[str] | None = None) -> int

Exit codes (CLI ``create`` subcommand):
  0 — at least one worktree created-or-skipped and record written
  2 — argparse error
  3 — refused (live non-self owner, authoritative or ambiguous) OR
      zero worktrees succeeded (fail-OPEN, non-destructive)

Exit codes (CLI ``teardown`` subcommand):
  0 — torn down, OR graceful nothing-to-tear-down
  2 — argparse error
  3 — refused-unsafe (uncommitted/unpushed guard tripped, ``--force`` not passed)
  4 — partial teardown failure (>=1 ``git worktree remove`` failed; resumable)

Env:
  QUOIN_SUBPROCESS_TIMEOUT — seconds, default 30; bounds every git subprocess.
  QUOIN_WORKSPACE_STALE_HOURS — hours, default 6; owner-liveness threshold
      for the minimal ``_owner_is_live`` stub (full JSONL-mtime liveness is
      a later stage — see architecture.md D-04 / S-04).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Sibling-import bootstrap (robust under direct-run AND wrapper importlib load)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import branch_hygiene  # noqa: E402  (core/scripts sibling — allowed)
import get_session_uuid  # noqa: E402  (core/scripts sibling — allowed)


# ---------------------------------------------------------------------------
# Copy-not-import local helpers (own copy — do NOT cross-import branch_hygiene's)
# ---------------------------------------------------------------------------

def _subprocess_timeout() -> int:
    """Read QUOIN_SUBPROCESS_TIMEOUT (seconds); default 30; bad values fall back to 30.

    Self-contained local copy — do NOT cross-import; each touched core script
    owns its own copy per the repo's copy-not-import convention.
    """
    try:
        return int(os.environ.get("QUOIN_SUBPROCESS_TIMEOUT", "30"))
    except (TypeError, ValueError):
        return 30


def _run(args: list[str]) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_subprocess_timeout(),
        )
        return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except FileNotFoundError:
        return "", "git not found", 1
    except Exception as exc:  # noqa: BLE001
        return "", str(exc), 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_to_epoch(s: str | None) -> float | None:
    """Parse an _utc_now_iso() string back to epoch seconds (aware UTC).

    Bad/empty input -> None. Single-basis helper so _owner_is_live never
    mixes datetime objects with epoch floats (T-01 acceptance).
    """
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def slugify(feature: str) -> str:
    """Lowercase, non-[a-z0-9-] -> '-', collapse repeats, strip leading/trailing '-'.

    Raises ValueError if the result is empty.
    """
    lowered = feature.lower()
    replaced = re.sub(r"[^a-z0-9-]", "-", lowered)
    collapsed = re.sub(r"-+", "-", replaced).strip("-")
    if not collapsed:
        raise ValueError(f"slugify({feature!r}) produced an empty slug")
    return collapsed


def _atomic_write_json(path: Path, obj: Any) -> bool:
    """Write obj as JSON to path atomically (mkdir parents, .tmp sidecar, os.replace).

    Fail-OPEN: on OSError, log to stderr and return False; never raise.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(obj, indent=2) + "\n")
        os.replace(tmp_path, path)
        return True
    except OSError as exc:
        print(f"[workspace] atomic write failed for {path}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# T-02: Repo discovery + selection (D-07)
# ---------------------------------------------------------------------------

def discover_workspace_repos(project_root: Path, named: list[str] | None = None) -> list[Path]:
    """Discover candidate repos via branch_hygiene.discover_repos, filtering .workspaces.

    Does NOT re-implement discovery and does NOT mutate branch_hygiene's shared
    _EXCLUDE_NAMES frozenset (D-07). If `named` is given, keep only repos whose
    .name is in `named`; unknown names raise ValueError naming them (never
    silently dropped). Zero `named` -> all discovered.
    """
    candidates = branch_hygiene.discover_repos(project_root)
    workspaces_root = str((project_root / ".workspaces").resolve())
    filtered = [
        p for p in candidates
        if not (str(p) == workspaces_root or str(p).startswith(workspaces_root + os.sep))
    ]

    if not named:
        return filtered

    by_name = {p.name: p for p in filtered}
    unknown = [n for n in named if n not in by_name]
    if unknown:
        raise ValueError(f"unknown repo name(s) requested: {', '.join(unknown)}")
    return [by_name[n] for n in named]


# ---------------------------------------------------------------------------
# T-03: Default-branch resolution + worktree add (D-08, D-09, arch R-05)
# ---------------------------------------------------------------------------

def default_branch(repo: Path) -> str:
    """Resolve the repo's default branch: origin/HEAD -> current branch -> 'main'."""
    stdout, _, rc = _run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
    )
    if rc == 0 and stdout:
        return stdout.split("/", 1)[-1] if stdout.startswith("origin/") else stdout

    stdout, _, rc = _run(["git", "-C", str(repo), "branch", "--show-current"])
    if rc == 0 and stdout:
        return stdout

    return "main"


def _worktree_list_porcelain(repo: Path) -> str:
    stdout, _, rc = _run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    return stdout if rc == 0 else ""


def _worktree_registered(repo: Path, dest: Path) -> bool:
    """True if dest (resolved) is a listed worktree path for repo (idempotent skip-add)."""
    dest_resolved = str(dest.resolve()) if dest.exists() else str(dest)
    porcelain = _worktree_list_porcelain(repo)
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            wt_path = line[len("worktree "):].strip()
            try:
                wt_resolved = str(Path(wt_path).resolve())
            except OSError:
                wt_resolved = wt_path
            if wt_resolved == dest_resolved or wt_path == str(dest):
                return True
    return False


def _branch_checked_out_elsewhere(repo: Path, branch: str) -> str | None:
    """Return the worktree path where `branch` is already checked out, else None."""
    porcelain = _worktree_list_porcelain(repo)
    current_path: str | None = None
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch ") and current_path is not None:
            # Format: "branch refs/heads/<name>"
            ref = line[len("branch "):].strip()
            branch_name = ref.rsplit("/", 1)[-1] if ref.startswith("refs/heads/") else ref
            if branch_name == branch:
                return current_path
    return None


@dataclasses.dataclass
class WorktreeResult:
    repo: str
    dest: str
    branch: str
    created: bool
    skipped: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def add_worktree(repo: Path, feature: str, dest: Path, base: str | None = None) -> WorktreeResult:
    """Create (or reuse) a linked worktree at dest on the feature branch."""
    repo_str = str(repo)
    dest_str = str(dest)

    if _worktree_registered(repo, dest):
        return WorktreeResult(repo=repo_str, dest=dest_str, branch=feature, created=False, skipped=True, error=None)

    # dest is confirmed NOT already registered (checked above), so any non-None
    # result here is necessarily a DIFFERENT path (arch R-05).
    elsewhere = _branch_checked_out_elsewhere(repo, feature)
    if elsewhere is not None:
        return WorktreeResult(
            repo=repo_str, dest=dest_str, branch=feature, created=False, skipped=False,
            error=f"branch '{feature}' already checked out at {elsewhere}",
        )

    dest.parent.mkdir(parents=True, exist_ok=True)

    base_ref = base or default_branch(repo)
    args = ["git", "-C", repo_str, "worktree", "add", "-b", feature, dest_str, base_ref]
    _, stderr, rc = _run(args)
    if rc != 0:
        # branch may already exist locally — fall back to bare form
        args_fallback = ["git", "-C", repo_str, "worktree", "add", dest_str, feature]
        _, stderr2, rc2 = _run(args_fallback)
        if rc2 != 0:
            return WorktreeResult(
                repo=repo_str, dest=dest_str, branch=feature, created=False, skipped=False,
                error=stderr2 or stderr or f"git worktree add failed (rc={rc2})",
            )

    return WorktreeResult(repo=repo_str, dest=dest_str, branch=feature, created=True, skipped=False, error=None)


# ---------------------------------------------------------------------------
# T-04: Ownership record + marker (D-02, D-03) with minimal liveness stub
# ---------------------------------------------------------------------------

def _record_path(project_root: Path, slug: str) -> Path:
    return project_root / ".workflow_artifacts" / "memory" / "workspaces" / f"{slug}.json"


def read_ownership_record(project_root: Path, slug: str) -> dict | None:
    """Read the ownership record for slug. Missing/corrupt -> None (fail-OPEN)."""
    path = _record_path(project_root, slug)
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def build_record(
    feature: str,
    slug: str,
    session_uuid: str,
    repos: list[str],
    branches: dict[str, str],
    workspace_path: Path,
) -> dict:
    """Build the D-03 ownership record dict."""
    now = _utc_now_iso()
    pid_start_time: str | None = None
    try:
        # Diagnostic-only best-effort (D-04 no-PID-veto) — never gates anything.
        out, _, rc = _run(["ps", "-o", "lstart=", "-p", str(os.getpid())])
        if rc == 0 and out:
            pid_start_time = out
    except Exception:  # noqa: BLE001
        pid_start_time = None

    return {
        "feature": feature,
        "owner_session_uuid": session_uuid,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "pid_start_time": pid_start_time,
        "created": now,
        "last_seen": now,
        "repos": list(repos),
        "branches": dict(branches),
        "workspace_path": str(workspace_path),
    }


def write_ownership_record(project_root: Path, slug: str, record: dict) -> bool:
    """Write the ownership record via _atomic_write_json (whole-file, no read-modify-write)."""
    return _atomic_write_json(_record_path(project_root, slug), record)


def write_marker(workspace_root: Path, artifact_root: Path, feature: str, repos: list[str]) -> bool:
    """Write the .quoin-workspace.json marker. Returns the atomic-write bool (MIN-3)."""
    marker = {
        "artifact_root": str(artifact_root.resolve()),
        "feature": feature,
        "repos": list(repos),
        "created": _utc_now_iso(),
    }
    marker_path = workspace_root / ".quoin-workspace.json"
    return _atomic_write_json(marker_path, marker)


def _owner_is_live(record: dict) -> bool:
    """MINIMAL STUB liveness check (T-04).

    This record-mtime check is the deliberate seam the takeover stage (S-04)
    replaces with the get_session_uuid JSONL-mtime primary signal. Create-time
    refusal built on it is best-effort under concurrency (see the
    session-identity note in T-05 / Decisions / R-08 in the plan).

    Both operands are normalized to epoch-seconds floats — never mixed with
    datetime objects (MIN-2).
    """
    try:
        threshold_hours = float(os.environ.get("QUOIN_WORKSPACE_STALE_HOURS", "6"))
    except (TypeError, ValueError):
        threshold_hours = 6.0

    last_seen_epoch = _iso_to_epoch(record.get("last_seen"))

    # The record file's own mtime is the fallback signal when last_seen is
    # unparseable. Callers that want mtime-fallback pass it via
    # record["_record_mtime"] (internal, set by the caller before invoking
    # this function); otherwise last_seen alone is used.
    mtime_epoch: float | None = record.get("_record_mtime")

    candidates = [x for x in (last_seen_epoch, mtime_epoch) if x is not None]
    if not candidates:
        # No usable timestamp at all -- fail-OPEN as stale (safe: treat as
        # reclaimable rather than permanently un-reclaimable).
        return False

    newest = max(candidates)
    now_epoch = datetime.now(timezone.utc).timestamp()
    return (now_epoch - newest) < (threshold_hours * 3600)


def _read_ownership_record_with_mtime(project_root: Path, slug: str) -> dict | None:
    """Like read_ownership_record but injects _record_mtime for _owner_is_live's fallback."""
    path = _record_path(project_root, slug)
    try:
        record = json.loads(path.read_text())
        record["_record_mtime"] = path.stat().st_mtime
        return record
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# T-05: create_workspace orchestrator (D-03 ordering, FR1 idempotency, D-07
# gitignore, collision refusal)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CreateResult:
    slug: str = ""
    workspace_path: str = ""
    per_repo: list[WorktreeResult] = dataclasses.field(default_factory=list)
    record_written: bool = False
    marker_written: bool = False
    refused: bool = False
    ambiguous: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "workspace_path": self.workspace_path,
            "per_repo": [r.to_dict() for r in self.per_repo],
            "record_written": self.record_written,
            "marker_written": self.marker_written,
            "refused": self.refused,
            "ambiguous": self.ambiguous,
            "message": self.message,
        }


def _ensure_gitignore_wholeline(repo_root: Path, line: str) -> None:
    """Append `line` to repo_root/.gitignore if no stripped-whole-line match exists (MIN-5)."""
    gitignore_path = repo_root / ".gitignore"
    existing_lines: list[str] = []
    if gitignore_path.exists():
        try:
            existing_lines = gitignore_path.read_text().splitlines()
        except OSError:
            existing_lines = []

    if any(existing_line.strip() == line for existing_line in existing_lines):
        return

    try:
        with gitignore_path.open("a") as fh:
            if existing_lines and existing_lines[-1] != "":
                fh.write("\n")
            fh.write(line + "\n")
    except OSError as exc:
        print(f"[workspace] failed to update .gitignore at {gitignore_path}: {exc}", file=sys.stderr)


def create_workspace(
    feature: str,
    project_root: Path,
    named_repos: list[str] | None = None,
    base: str | None = None,
    session_uuid: str | None = None,
) -> CreateResult:
    """Create (or idempotently refresh) a feature workspace across selected repos.

    Sequence is load-bearing (D-03): collision check -> discover -> gitignore
    -> worktrees FIRST -> finalize record only after >=1 worktree succeeds.
    """
    slug = slugify(feature)
    project_root = project_root.resolve()
    ws_root = project_root / ".workspaces" / slug

    # Step a: identity resolution — caller-authoritative, derive only if None (MAJ-2).
    identity_authoritative = session_uuid is not None
    resolved_uuid = session_uuid if identity_authoritative else get_session_uuid.get_session_uuid(
        project_path=str(project_root), phase="ad-hoc"
    )

    # Step b: collision / self-vs-other check — UUID EQUALITY ONLY (round-2 MAJ fix).
    record = _read_ownership_record_with_mtime(project_root, slug)
    if record is not None:
        is_self = record.get("owner_session_uuid") == resolved_uuid
        if _owner_is_live(record) and not is_self:
            if identity_authoritative:
                return CreateResult(
                    slug=slug,
                    workspace_path=str(ws_root),
                    refused=True,
                    ambiguous=False,
                    message=f"owned by a live session; run: workspace takeover {feature}",
                )
            else:
                return CreateResult(
                    slug=slug,
                    workspace_path=str(ws_root),
                    refused=True,
                    ambiguous=True,
                    message=(
                        "a live workspace record exists under a different derived "
                        "session id; re-run with --session-uuid to confirm ownership "
                        "(identity derivation is ambiguous under parallel sessions; "
                        "full disambiguation deferred to S-04 liveness)"
                    ),
                )
        # else: no-live-conflict (stale record OR self) -> proceed / adopt-refresh

    # Step c: repo discovery (raises ValueError on unknown named repo).
    repos = discover_workspace_repos(project_root, named_repos)

    # Step d: cwd-as-repo .gitignore edge (D-07 / AC-8) — BEFORE adding worktrees.
    if (project_root / ".git").exists():
        _ensure_gitignore_wholeline(project_root, ".workspaces/")

    # Step e: WORKTREES FIRST.
    results: list[WorktreeResult] = []
    branches: dict[str, str] = {}
    for repo in repos:
        dest = ws_root / repo.name
        result = add_worktree(repo, feature, dest, base)
        results.append(result)
        if result.created or result.skipped:
            branches[repo.name] = feature

    # Step f: finalize record ONLY IF at least one worktree succeeded.
    if any(r.created or r.skipped for r in results):
        rec_obj = build_record(
            feature=feature,
            slug=slug,
            session_uuid=resolved_uuid,
            repos=list(branches),
            branches=branches,
            workspace_path=ws_root,
        )
        record_written = write_ownership_record(project_root, slug, rec_obj)
        marker_written = write_marker(ws_root, artifact_root=project_root, feature=feature, repos=list(branches))
        return CreateResult(
            slug=slug,
            workspace_path=str(ws_root),
            per_repo=results,
            record_written=record_written,
            marker_written=marker_written,
        )

    return CreateResult(
        slug=slug,
        workspace_path=str(ws_root),
        per_repo=results,
        record_written=False,
        marker_written=False,
        message="no worktree created; resumable",
    )


# ---------------------------------------------------------------------------
# S-03 teardown (IVG-158): guarded removal of a feature workspace.
# ---------------------------------------------------------------------------

def _proven_merged(worktree: Path | str, orig_repo: str | None) -> bool:
    """S-05 seam — is this worktree's branch provably pushed/merged?

    In S-03 this is a STUB that ALWAYS returns False: a no-upstream (never
    pushed) branch is therefore never treated as safe, so teardown refuses it
    unless --force. S-05 replaces this single function with the real
    gh-MERGED / `git branch --merged` detection (D-06). This is the ONLY call
    site of the proven-merged override, consumed only by
    _classify_worktree_safety.
    """
    return False


def _classify_worktree_safety(
    rc: "branch_hygiene.RepoResult", proven_merged: bool
) -> tuple[bool, list[str]]:
    """Classify a worktree as safe-to-discard (True) or unsafe (False + reasons).

    Conservative S-03 rule — never silently discards work (arch R-06):
      - rc.error truthy                         -> UNSAFE (cannot prove safe)
      - rc.dirty                                -> UNSAFE (uncommitted changes)
      - rc.upstream is None AND not proven_merged -> UNSAFE (never pushed)
      - rc.upstream is not None AND ahead > 0   -> UNSAFE (unpushed commits)
      - else                                    -> SAFE (clean + upstream + not-ahead)

    Reasons accumulate (dirty + no-upstream can co-occur). safe = not reasons.

    Known limitation (critic MIN-3): rc.dirty is best-effort — a `git status`
    failure inside check_repo yields dirty=False WITHOUT setting rc.error, so a
    status-check failure is invisible here and the worktree may score SAFE. The
    git-level backstop is the non-force `git worktree remove`, which itself
    refuses a modified/untracked tree (surfaces as partial_failure/exit 4, not a
    silent discard). Not fixed in S-03 — check_repo is merged/rostered.
    """
    reasons: list[str] = []
    if rc.error:
        reasons.append(f"git error: {rc.error}")
    if rc.dirty:
        reasons.append("uncommitted changes")
    if rc.upstream is None and not proven_merged:
        reasons.append(
            "no upstream (cannot prove pushed/merged; "
            "proven-merged override deferred to S-05)"
        )
    elif rc.upstream is not None and rc.commits_ahead > 0:
        reasons.append(f"{rc.commits_ahead} unpushed commit(s)")
    return (not reasons, reasons)


def discover_workspace_worktrees(ws_root: Path) -> list[Path]:
    """Deterministically enumerate a workspace's worktree subdirs.

    Immediate subdirectories of ws_root that contain a `.git` entry (a linked
    worktree has a `.git` FILE). The `.quoin-workspace.json` marker (a file, not
    a dir) and any stray non-worktree dir are skipped. Returns [] when ws_root
    is absent. Discovery never depends on the ownership record (D-06) — a
    missing/corrupt record can never block teardown.
    """
    if not ws_root.exists():
        return []
    result: list[Path] = []
    try:
        for sub in sorted(ws_root.iterdir()):
            if sub.is_dir() and (sub / ".git").exists():
                result.append(sub)
    except OSError:
        return []
    return result


def _worktree_orig_repo(worktree: Path | str) -> str | None:
    """Derive a worktree's ORIGINAL repo path from `git worktree list --porcelain`.

    The FIRST `worktree ` line is always the main working tree = the original
    repo. Returns its path, or None on git error (worktree then skipped from
    removal — resumable). The S-01 record stores repo NAMES, not original-repo
    absolute paths, so this derivation is what teardown targets with
    `git -C <orig-repo> worktree remove`.
    """
    stdout, _, rc = _run(["git", "-C", str(worktree), "worktree", "list", "--porcelain"])
    if rc != 0:
        return None
    for line in stdout.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):].strip()
    return None


def _read_record_safe(project_root: Path, slug: str) -> dict | None:
    """Read the ownership record, guarding against a valid-JSON non-object (S-02).

    read_ownership_record can return any JSON value (a list, number, or bare
    string) for a corrupt record. Guard isinstance(dict) so a non-object record
    yields None (fall back to deterministic ws_root discovery) instead of an
    AttributeError on `.get()`. The record is advisory only in teardown.
    """
    rec = read_ownership_record(project_root, slug)
    if isinstance(rec, dict):
        return rec
    return None


def _unlink_record_if_present(project_root: Path, slug: str) -> bool:
    """Unlink the ownership record file if it exists. Fail-OPEN (never raises)."""
    path = _record_path(project_root, slug)
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError as exc:
        print(f"[workspace] failed to unlink record {path}: {exc}", file=sys.stderr)
    return False


@dataclasses.dataclass
class WorktreeStatus:
    worktree: str
    orig_repo: str | None
    safe: bool
    reasons: list[str]
    removed: bool
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class TeardownResult:
    slug: str
    workspace_path: str
    per_repo: list[WorktreeStatus] = dataclasses.field(default_factory=list)
    refused: bool = False
    forced: bool = False
    record_removed: bool = False
    folder_removed: bool = False
    partial_failure: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "workspace_path": self.workspace_path,
            "per_repo": [s.to_dict() for s in self.per_repo],
            "refused": self.refused,
            "forced": self.forced,
            "record_removed": self.record_removed,
            "folder_removed": self.folder_removed,
            "partial_failure": self.partial_failure,
            "message": self.message,
        }


def _render_unsafe(statuses: list[WorktreeStatus]) -> str:
    return "; ".join(
        f"{Path(s.worktree).name}: {', '.join(s.reasons)}"
        for s in statuses if not s.safe
    )


def teardown_workspace(
    feature: str, project_root: Path, force: bool = False
) -> TeardownResult:
    """Tear down a feature workspace: guard, remove worktrees, prune, clean up.

    Order is load-bearing (D-06, FR5) — a crash leaves a resumable state:
    discover -> guard (refuse-unless-force) -> remove worktrees FIRST -> prune
    -> rmtree folder+marker (CONFIRM removal) -> unlink record ONLY IF the
    folder is confirmed gone. See architecture.md D-06 and the plan Decisions.
    """
    slug = slugify(feature)
    project_root = project_root.resolve()
    ws_root = project_root / ".workspaces" / slug
    # Record is advisory (discovery is deterministic); read only for the
    # dangling-record cleanup below and never load-bearing for discovery.
    _read_record_safe(project_root, slug)

    worktrees = discover_workspace_worktrees(ws_root)

    # MISSING-WORKSPACE (graceful, exit 0): nothing to remove. If a stray record
    # file lingers, unlink it to clear a dangling record.
    if not ws_root.exists() and not worktrees:
        record_removed = _unlink_record_if_present(project_root, slug)
        return TeardownResult(
            slug=slug,
            workspace_path=str(ws_root),
            record_removed=record_removed,
            message="nothing to tear down",
        )

    # GUARD: classify every worktree (read-only reuse of branch_hygiene).
    statuses: list[WorktreeStatus] = []
    for wt in worktrees:
        orig = _worktree_orig_repo(wt)
        rc = branch_hygiene.check_repo(Path(wt))
        safe, reasons = _classify_worktree_safety(rc, _proven_merged(wt, orig))
        statuses.append(
            WorktreeStatus(
                worktree=str(wt), orig_repo=orig, safe=safe, reasons=reasons,
                removed=False, error=None,
            )
        )

    unsafe = [s for s in statuses if not s.safe]
    if unsafe and not force:
        return TeardownResult(
            slug=slug,
            workspace_path=str(ws_root),
            per_repo=statuses,
            refused=True,
            message=f"refused (unsafe): {_render_unsafe(unsafe)}",
        )

    # FORCE bypass MUST be explicit AND logged (audit trail — critic MIN-1).
    if force and unsafe:
        print(
            f"[workspace] --force teardown: bypassing guard for {slug}; "
            f"unsafe: {_render_unsafe(unsafe)}",
            file=sys.stderr,
        )

    # REMOVE worktrees FIRST (git --force IFF teardown --force: user-force =>
    # git-force). All git ops run -C <orig_repo>, never from the worktree.
    removed_repos: set[str] = set()
    for s in statuses:
        if s.orig_repo is None:
            s.error = "could not derive original repo"
            continue
        wt_path = Path(s.worktree)
        # Idempotency: already-gone worktree -> treat as removed (re-runnable).
        if not wt_path.exists() or not _worktree_registered(
            Path(s.orig_repo), wt_path
        ):
            s.removed = True
            continue
        args = ["git", "-C", s.orig_repo, "worktree", "remove"]
        if force:
            args.append("--force")
        args.append(s.worktree)
        _, err, rc = _run(args)
        if rc == 0:
            s.removed = True
            removed_repos.add(s.orig_repo)
        else:
            s.error = err or "git worktree remove failed"

    # PRUNE stale admin entries for each repo that had a removal.
    for orig in removed_repos:
        _run(["git", "-C", orig, "worktree", "prune"])

    # PARTIAL-FAILURE gate (exit 4): leave folder+record so a re-run finishes.
    if any(s.error and not s.removed for s in statuses):
        failed = [Path(s.worktree).name for s in statuses if s.error and not s.removed]
        return TeardownResult(
            slug=slug,
            workspace_path=str(ws_root),
            per_repo=statuses,
            forced=force,
            partial_failure=True,
            message=f"partial teardown; re-run (failed: {', '.join(failed)})",
        )

    # CLEANUP (all removals succeeded): rmtree folder+marker, CONFIRM removal,
    # unlink record ONLY IF folder confirmed gone (critic MIN-4) — keeps the
    # resumability invariant exact if a locked file leaves ws_root behind.
    shutil.rmtree(ws_root, ignore_errors=True)
    folder_removed = not ws_root.exists()
    record_removed = (
        _unlink_record_if_present(project_root, slug) if folder_removed else False
    )

    return TeardownResult(
        slug=slug,
        workspace_path=str(ws_root),
        per_repo=statuses,
        forced=force,
        folder_removed=folder_removed,
        record_removed=record_removed,
        message="torn down",
    )


# ---------------------------------------------------------------------------
# T-06: CLI + main (create subcommand)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage per-repo git worktree feature workspaces.",
        add_help=True,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create or refresh a feature workspace.")
    create_parser.add_argument("feature", help="Feature name (slugified for the workspace folder).")
    create_parser.add_argument(
        "repos", nargs="*", default=[],
        help="Optional trailing positional repo names to include (union with --repos).",
    )
    create_parser.add_argument(
        "--repos", dest="repos_flag", default=None,
        help="Comma-separated repo names to include (union with trailing positional repos).",
    )
    create_parser.add_argument(
        "--base", default=None,
        help="Base ref for new branches (default: per-repo default_branch()).",
    )
    create_parser.add_argument(
        "--project-root", default=None,
        help="Project root (default: cwd).",
    )
    create_parser.add_argument(
        "--session-uuid", dest="session_uuid", default=None,
        help="Authoritative owner-identity seam (the /workspace skill passes the real "
             "session UUID). Default: best-effort derive via get_session_uuid.",
    )
    create_parser.add_argument(
        "--json", dest="json_output", action="store_true", default=True,
        help="Emit the CreateResult as JSON (default: on).",
    )

    teardown_parser = subparsers.add_parser(
        "teardown", help="Tear down a feature workspace (uncommitted/unpushed guarded)."
    )
    teardown_parser.add_argument(
        "feature", help="Feature name (slugified for the workspace folder)."
    )
    teardown_parser.add_argument(
        "--project-root", default=None,
        help="Project root (default: cwd).",
    )
    teardown_parser.add_argument(
        "--force", action="store_true", default=False,
        help="Explicit escape hatch: bypass the uncommitted/unpushed guard "
             "(logged to stderr) and discard the worktrees anyway.",
    )
    teardown_parser.add_argument(
        "--json", dest="json_output", action="store_true", default=True,
        help="Emit the TeardownResult as JSON (default: on).",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    if args.command == "create":
        project_root = Path(args.project_root) if args.project_root else Path.cwd()
        named: list[str] = list(args.repos)
        if args.repos_flag:
            named.extend(n.strip() for n in args.repos_flag.split(",") if n.strip())
        named_or_none = named or None

        try:
            result = create_workspace(
                feature=args.feature,
                project_root=project_root,
                named_repos=named_or_none,
                base=args.base,
                session_uuid=args.session_uuid,
            )
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            print(f"[workspace] {exc}", file=sys.stderr)
            return 3

        print(json.dumps(result.to_dict(), indent=2))
        for r in result.per_repo:
            status = "skipped" if r.skipped else ("created" if r.created else "error")
            print(f"{status} {r.repo} -> {r.dest} ({r.error or 'ok'})", file=sys.stderr)

        if result.refused or (not result.record_written and not result.per_repo):
            return 3
        if not result.per_repo or not any(r.created or r.skipped for r in result.per_repo):
            return 3
        return 0

    if args.command == "teardown":
        project_root = Path(args.project_root) if args.project_root else Path.cwd()

        try:
            result = teardown_workspace(
                feature=args.feature,
                project_root=project_root,
                force=args.force,
            )
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            print(f"[workspace] {exc}", file=sys.stderr)
            return 3

        print(json.dumps(result.to_dict(), indent=2))
        for s in result.per_repo:
            name = Path(s.worktree).name
            if result.refused and not s.safe:
                print(f"refused {name}: {', '.join(s.reasons)}", file=sys.stderr)
            elif s.error and not s.removed:
                print(f"failed {name}: {s.error}", file=sys.stderr)
            elif s.removed:
                print(f"removed {name}", file=sys.stderr)

        if result.refused:
            return 3
        if result.partial_failure:
            return 4
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
