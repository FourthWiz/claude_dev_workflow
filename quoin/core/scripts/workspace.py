#!/usr/bin/env python3
"""Portable core implementation of feature-workspace create (IVG-158, S-01).

Gives each in-flight feature its own isolated per-repo git worktree so
concurrent Claude Code sessions never share a mutable branch on the same
repo. This module owns the ``create`` subcommand only (S-01 scope) — no
teardown, no takeover, no full liveness. See architecture.md D-01..D-09.

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
  main(argv: list[str] | None = None) -> int

Exit codes (CLI ``create`` subcommand):
  0 — at least one worktree created-or-skipped and record written
  2 — argparse error
  3 — refused (live non-self owner, authoritative or ambiguous) OR
      zero worktrees succeeded (fail-OPEN, non-destructive)

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

    return 2


if __name__ == "__main__":
    sys.exit(main())
