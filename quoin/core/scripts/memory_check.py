#!/usr/bin/env python3
"""quoin/core/scripts/memory_check.py — referential-integrity checker for quoin auto-memory.

Verifies that every Markdown link in MEMORY.md resolves to a sibling fact-file, and
that every sibling fact-file is referenced by at least one MEMORY.md link.

Public API:
  FORWARD_LINKS_ARE_ERRORS: bool — D-S2-2 single point of change (see below)
  LINK_RE: re.Pattern — compiled regex that captures Markdown link targets
  parse_links(memory_md_text: str) -> list[str]
  find_fact_files(memory_dir: Path) -> set[str]
  check(memory_dir: Path, allow_forward_links: bool = ...) -> dict
  check_index_pointers(memory_dir: Path) -> list   # D-S2-4 stub (inert until S-1)
  main(argv: list[str] | None = None) -> int

Exit codes:
  0 — clean (no integrity errors)
  1 — integrity errors found
  2 — usage/IO error (missing MEMORY.md, unreadable dir, bad args)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# D-S2-2: single flip-point for forward-link policy.
# A "forward link" is a MEMORY.md link whose target file does not yet exist.
# When True (default), forward links are treated as errors (reported under
# "dangling"). Flip this constant or use --allow-forward-links per-run to relax.
FORWARD_LINKS_ARE_ERRORS = True  # D-S2-2: single point of change

#: Captures Markdown inline link targets: [text](target).
#: Filters to .md targets; URL targets (containing "://") are skipped by check().
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Files to exclude from the "fact files" set even if they have .md extension.
_INDEX_FILENAMES: frozenset[str] = frozenset({"MEMORY.md", "MEMORY-INDEX.md"})


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_links(memory_md_text: str) -> list[str]:
    """Return ordered list of Markdown link targets from *memory_md_text*.

    Includes all targets matched by LINK_RE; URL filtering is done in check().
    Duplicate targets are preserved (order matters for reporting).
    """
    return LINK_RE.findall(memory_md_text)


def find_fact_files(memory_dir: Path) -> set[str]:
    """Return the set of sibling *.md file names in *memory_dir*.

    Excludes MEMORY.md itself and any future MEMORY-INDEX.md (D-S2-4 forward-compat).
    Names only, not full paths.
    """
    return {
        p.name
        for p in memory_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and p.name not in _INDEX_FILENAMES
    }


def check(
    memory_dir: Path,
    allow_forward_links: bool = not FORWARD_LINKS_ARE_ERRORS,
) -> dict:
    """Check referential integrity of the auto-memory directory.

    Returns a dict:
      {
        "dangling": [str, ...],  # link targets with no matching sibling file
        "orphans":  [str, ...],  # fact-files not referenced by any link
        "forward":  [],          # reserved for S-1/S-3 (always empty in S-2)
        "ok":       bool,        # True iff no errors (see policy below)
      }

    Policy:
      - Orphans are always errors (ok=False if any orphans).
      - Dangling links are errors unless allow_forward_links=True.
      - "forward" key is present but empty (forward-compat with S-1/S-3).
    """
    memory_md = memory_dir / "MEMORY.md"
    text = memory_md.read_text(encoding="utf-8")

    raw_targets = parse_links(text)
    # Filter: only .md targets, skip URLs
    link_targets: list[str] = [
        t for t in raw_targets
        if t.endswith(".md") and "://" not in t
    ]

    fact_files = find_fact_files(memory_dir)
    linked_set = set(link_targets)

    # Dangling: link target has no matching sibling file
    dangling: list[str] = [t for t in link_targets if t not in fact_files]

    # Orphans: fact-file not referenced by any link
    orphans: list[str] = sorted(fact_files - linked_set)

    ok = (not orphans) and (allow_forward_links or not dangling)

    return {
        "dangling": dangling,
        "orphans": orphans,
        "forward": [],  # S-1/S-3 forward-compat stub
        "ok": ok,
    }


def check_index_pointers(memory_dir: Path) -> list:
    """Stub for S-1 forward-compat (D-S2-4).

    When S-1 ships a MEMORY-INDEX.md, this function will validate that every
    index pointer resolves. Until then, returns [] unconditionally.
    """
    # S-1 hook point: when MEMORY-INDEX.md exists, validate its pointers.
    # For S-2, no S-1 index exists yet — return empty list (inert).
    if not (memory_dir / "MEMORY-INDEX.md").exists():
        return []
    return []  # S-1 not yet implemented


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory_check",
        description=(
            "Check referential integrity of a quoin auto-memory directory. "
            "Verifies every MEMORY.md link resolves to a sibling fact-file "
            "and every sibling fact-file is referenced by MEMORY.md. "
            "Report-only: never deletes or rewrites files."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        metavar="PATH",
        help=(
            "Memory directory to check (must contain MEMORY.md). "
            "Default: $CLAUDE_MEMORY_DIR if set, else current directory "
            "if it contains MEMORY.md."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help=(
            'Output result as JSON: {"dangling":[...],"orphans":[...],'
            '"forward":[],"ok":bool} (for scripting/tests).'
        ),
    )
    parser.add_argument(
        "--allow-forward-links",
        action="store_true",
        default=False,
        help=(
            "Treat MEMORY.md links to missing files as warnings, not errors. "
            "Overrides the FORWARD_LINKS_ARE_ERRORS constant for this run."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code (0=clean, 1=errors, 2=usage/IO error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve memory directory
    if args.path:
        memory_dir = Path(args.path).resolve()
    else:
        import os
        env_dir = os.environ.get("CLAUDE_MEMORY_DIR")
        if env_dir:
            memory_dir = Path(env_dir).resolve()
        elif (Path.cwd() / "MEMORY.md").exists():
            memory_dir = Path.cwd()
        else:
            print(
                "error: no memory directory found. "
                "Pass PATH, set $CLAUDE_MEMORY_DIR, or run from a dir containing MEMORY.md.",
                file=sys.stderr,
            )
            return 2

    memory_md = memory_dir / "MEMORY.md"

    if not memory_dir.is_dir():
        print(f"error: not a directory: {memory_dir}", file=sys.stderr)
        return 2
    if not memory_md.exists():
        print(f"error: MEMORY.md not found in {memory_dir}", file=sys.stderr)
        return 2

    try:
        result = check(memory_dir, allow_forward_links=args.allow_forward_links)
    except (OSError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result))
        return 0 if result["ok"] else 1

    # Human-readable output
    issues = 0

    if result["dangling"]:
        print("Dangling links (MEMORY.md links to missing files):")
        for target in result["dangling"]:
            print(f"  - {target}")
        issues += len(result["dangling"])

    if result["orphans"]:
        print("Orphaned fact-files (not referenced by MEMORY.md):")
        for name in result["orphans"]:
            print(f"  - {name}")
        issues += len(result["orphans"])

    if result["ok"]:
        print("Memory integrity OK.")
        return 0
    else:
        print(f"{issues} integrity issue(s) found.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
