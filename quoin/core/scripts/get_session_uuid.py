#!/usr/bin/env python3
"""Portable core implementation of session UUID capture for cost ledger.

Finds the Claude Code session JSONL file for the current project and returns
its stem (the UUID used by Claude Code as the session identifier).

Public API:
  project_hash(project_path: str) -> str
  get_session_uuid(project_path=None, home=None, phase=None) -> str
  main(argv=None) -> int

Exit codes:
  0 — always (fail-open design)

Fallback UUID form: unknown-<phase_slug>-<YYYYMMDD>T<HHMMSS>Z
  where phase_slug replaces '-' with '_' (e.g., end-of-task -> end_of_task)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Hash logic — INLINE COPY from quoin/scripts/cost_from_jsonl.py (adapter-owned).
# Do NOT import from cost_from_jsonl.py — that file is CLAUDE-ADAPTER-OWNED
# and must not be imported from quoin/core/. The function is a one-line regex
# substitution with negligible drift risk. Parity tested by test_get_session_uuid.py.
# ---------------------------------------------------------------------------

def project_hash(project_path: str) -> str:
    """Convert /abs/path/to/project to the ~/.claude/projects/HASH form
    used by Claude Code session JSONL files.
    Empirical rule (verified 2026-04-27 by listing ~/.claude/projects/ on the
    developer machine): replace ANY character that is NOT [A-Za-z0-9-] with '-'.
    This covers '/' -> '-', '.' -> '-', '@' -> '-', '_' -> '-', ' ' -> '-', etc.
    Example: '/Users/ivgo/.../GoogleDrive-ivan.gorban@gmail.com/My Drive/...'
    becomes '-Users-ivgo-...-GoogleDrive-ivan-gorban-gmail-com-My-Drive-...'.
    Note: CLAUDE.md's legacy description 'project path with / replaced by -' is
    a simplification -- the actual on-disk transform is the broader regex rule.
    Path-with-spaces: the project path may contain spaces (e.g., 'My Drive');
    the transform replaces spaces with '-' as well. Quote all path expansions
    in callers to prevent shell word-splitting."""
    return re.sub(r'[^A-Za-z0-9-]', '-', project_path)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _fallback_uuid(phase: str | None) -> str:
    """Return a deterministic fallback UUID in unknown-<phase_slug>-<ISO>Z form.

    Phase dashes are slugified to underscores so the UUID stem is unambiguous
    (e.g., 'end-of-task' -> 'end_of_task'). This keeps the cost_snapshot
    'unknown-*' skip filter working without any changes to that filter.
    """
    phase_slug = (phase or "unknown").replace("-", "_")
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"unknown-{phase_slug}-{ts}"


def get_session_uuid(
    project_path: str | None = None,
    home: str | None = None,
    phase: str | None = None,
) -> str:
    """Find the most-recently-modified JSONL under ~/.claude/projects/<hash>/.

    Returns the JSONL stem (session UUID). Falls back to a synthetic
    unknown-<phase_slug>-<timestamp> UUID on any error (fail-open).

    Args:
        project_path: Absolute path to the project root. Defaults to cwd.
        home: Home directory override (for testing). Defaults to Path.home().
        phase: Phase name for fallback UUID discrimination (e.g., 'implement').
    """
    try:
        proj_path = project_path or str(Path.cwd())
        home_path = Path(home) if home else Path.home()
        proj_dir = home_path / ".claude" / "projects" / project_hash(proj_path)
        jsonl_files = sorted(
            proj_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if jsonl_files:
            return jsonl_files[0].stem
    except Exception:  # noqa: BLE001
        pass
    return _fallback_uuid(phase)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Accepts --project-path PATH and --phase PHASE.
    Prints the UUID to stdout.
    Always exits 0 (fail-open).
    """
    parser = argparse.ArgumentParser(
        description="Get the Claude Code session UUID for cost ledger recording.",
        add_help=True,
    )
    parser.add_argument(
        "--project-path",
        default=None,
        metavar="PATH",
        help="Absolute path to the project root (defaults to cwd).",
    )
    parser.add_argument(
        "--phase",
        default=None,
        metavar="PHASE",
        help="Phase name for fallback UUID (e.g., implement, end-of-task).",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # Even on arg parse errors, print a fallback and exit 0 (fail-open)
        print(_fallback_uuid(None))
        return 0

    uuid = get_session_uuid(
        project_path=args.project_path,
        phase=args.phase,
    )
    print(uuid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
