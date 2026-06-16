#!/usr/bin/env python3
"""quoin/core/scripts/find_drive_conflicts.py — sweep for Google Drive conflict copies.

Google Drive CloudStorage creates conflict copies by appending " 2", " 3", etc.
(up to a few digits) before the file extension when it cannot reconcile changes.
These copies pollute working trees on shared drives and can cause test flakes.

Public API:
  scan(root: Path, extra_excludes: frozenset[str] = frozenset()) -> list[Path]
  quarantine(matches: list[Path], root: Path) -> None
  delete(matches: list[Path]) -> None
  main(argv: list[str] | None = None) -> int

Conservative anchored regex (D-01):
  r" \\d{1,3}(\\.[^ ]*)?$"
  - \\d{1,3}: caps digit run at 1–3 (Drive conflict indices are tiny integers;
    4-digit numbers almost certainly belong to real filenames).
  - (\\.[^ ]*)?$: extension (if present) must start with a dot and contain NO
    spaces. This kills the "version 2.0 release notes.md" false-positive class
    because the tail after ".0" contains spaces.

Proven MATCHES (true conflict copies):
  a 2.md, report 3.pdf, notes 2.tar.gz, foo 10.md, a 100.md, next_steps 2, x 2.py

Proven NON-MATCHES (legitimate filenames):
  version 2.0 release notes.md (space in tail), chapter 3.1 intro.md (space in tail),
  a 1000.md (4-digit exceeds cap), v2.py (no space+digit), step 2 notes.md (space before end),
  config 2nd.py (non-digit after digit), test_quoin2.py (no space+digit prefix)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Conservative anchored regex — see module docstring for rationale.
CONFLICT_RE = re.compile(r" \d{1,3}(\.[^ ]*)?$")

#: Directory names always skipped during the walk (never recurse into these).
HARD_EXCLUDES: frozenset[str] = frozenset({
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".drive-conflicts-quarantine",
})


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def is_drive_conflict(name: str) -> bool:
    """Return True iff *name* matches the conservative Drive-conflict pattern."""
    return CONFLICT_RE.search(name) is not None


def scan(root: Path, extra_excludes: frozenset[str] = frozenset()) -> list[Path]:
    """Return a sorted list of paths under *root* that look like Drive conflict copies.

    Directories whose *name* matches are returned as a unit (no recursion into them).
    Files whose *name* matches are returned individually.

    Hard-excluded directory names (`.git`, `.venv`, `node_modules`, `__pycache__`,
    `.drive-conflicts-quarantine`) are never recursed into. Caller may supply
    additional *extra_excludes* (e.g. from ``--exclude`` CLI args).
    """
    all_excludes = HARD_EXCLUDES | extra_excludes
    matches: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in-place so os.walk does not descend into them.
        dirnames[:] = [
            d for d in dirnames
            if d not in all_excludes
        ]

        # Check directory names — match → yield entire subtree as one unit,
        # remove from dirnames so we don't descend into it.
        conflict_dirs = [d for d in dirnames if is_drive_conflict(d)]
        for d in conflict_dirs:
            matches.append(Path(dirpath) / d)
            dirnames.remove(d)

        # Check file names.
        for f in filenames:
            if is_drive_conflict(f):
                matches.append(Path(dirpath) / f)

    matches.sort()
    return matches


def quarantine(matches: list[Path], root: Path) -> None:
    """Move *matches* into ``<root>/.drive-conflicts-quarantine/<ISO-date>/``.

    Relative sub-paths are preserved to avoid collisions when two same-named
    conflict items exist at different depths. Uses ``shutil.move`` so directories
    are moved as complete subtrees.
    """
    today = datetime.date.today().isoformat()
    quarantine_base = root / ".drive-conflicts-quarantine" / today

    for src in matches:
        try:
            rel = src.relative_to(root)
        except ValueError:
            rel = Path(src.name)

        dest = quarantine_base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        print(f"quarantined: {src} -> {dest}")


def delete(matches: list[Path]) -> None:
    """Permanently remove *matches* from disk.

    Directories are removed via ``shutil.rmtree``; files via ``os.remove``.
    Only call this after dry-run / quarantine review.
    """
    for path in matches:
        if path.is_dir():
            shutil.rmtree(path)
            print(f"deleted dir: {path}")
        else:
            os.remove(path)
            print(f"deleted file: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="find_drive_conflicts",
        description=(
            "Sweep a directory tree for Google Drive sync-conflict copies "
            "(files/dirs whose name ends with ' N' or ' N.ext' where N is 1–3 digits). "
            "Default mode is DRY-RUN — no files are modified."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PATH",
        help="Root path to sweep (default: current directory).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--quarantine",
        action="store_true",
        help=(
            "Move matches into <PATH>/.drive-conflicts-quarantine/<ISO-date>/ "
            "(recoverable; directories moved as a unit)."
        ),
    )
    mode.add_argument(
        "--delete",
        action="store_true",
        help=(
            "Permanently remove matches (irreversible; use --quarantine first to review)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output matches as a JSON array of paths (for scripting/tests).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "Additional directory name to skip (can be repeated). "
            "The following are always skipped: .git, .venv, node_modules, "
            "__pycache__, .drive-conflicts-quarantine."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code (0 on success, non-zero on IO error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    root = Path(args.path).resolve() if args.path else Path.cwd()
    extra_excludes: frozenset[str] = frozenset(args.exclude)

    try:
        matches = scan(root, extra_excludes)
    except (OSError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps([str(p) for p in matches]))
        return 0

    if not matches:
        if not (args.quarantine or args.delete):
            print("No Drive conflict copies found.")
        return 0

    if args.quarantine:
        try:
            quarantine(matches, root)
        except (OSError, PermissionError) as exc:
            print(f"error during quarantine: {exc}", file=sys.stderr)
            return 1
    elif args.delete:
        try:
            delete(matches)
            print(f"Deleted {len(matches)} item(s).")
        except (OSError, PermissionError) as exc:
            print(f"error during delete: {exc}", file=sys.stderr)
            return 1
    else:
        # Dry-run: list matches to stdout.
        for p in matches:
            print(p)
        print(f"\n{len(matches)} Drive conflict copy(ies) found (dry-run; no changes made).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
