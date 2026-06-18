#!/usr/bin/env python3
"""quoin/core/scripts/memory_select.py — selective retrieval for lessons-learned.md.

Returns task-relevant entries from lessons-learned.md using a deterministic
token/substring overlap matcher. Low threshold errs toward over-inclusion (R-04).
Falls back to wholesale read on pathological inputs — selection NEVER fails.

Public API:
  Entry: dataclass(header, applies_to, body, lineno)
  SelectResult: dataclass(selected, fellback_to_wholesale, total, selected_count)
  parse_entries(text: str) -> list[Entry]
  tokenize(s: str) -> set[str]
  score(task_tokens: set[str], entry: Entry) -> int
  select(text: str, task_text: str, threshold: int = SELECT_THRESHOLD) -> SelectResult
  main(argv: list[str] | None = None) -> int

Exit codes:
  0 — success (selected entries printed, or JSON emitted)
  2 — usage/IO error (bad args, file not found)
  NOTE: there is NO exit 1 — selection always succeeds (degrades to wholesale).

IVG-50 S-1: selective retrieval for lessons-learned.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default score threshold: 1 shared token = include. Errs toward over-inclusion (R-04).
SELECT_THRESHOLD: int = 1

# Minimum number of results to return before falling back to wholesale.
# If select() would return fewer than this, return all entries.
MIN_RESULTS: int = 5

# Maximum fraction of all entries to return before falling back to wholesale.
# If select() would return more than this fraction, return all entries.
MAX_FRACTION: float = 0.6

# Minimum token length — tokens shorter than this are dropped.
MIN_TOKEN_LEN: int = 3

# Planning/review skill names that trigger always-include when they appear in Applies-to.
PLANNING_SKILL_NAMES: frozenset[str] = frozenset({
    "/plan", "/critic", "/architect", "/review",
})

# Stopwords dropped from token sets.
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "are", "was",
    "not", "but", "have", "had", "has", "its", "also", "any", "all",
    "use", "used", "using", "can", "via", "per", "see", "run", "runs",
    "add", "new", "one", "two", "get", "set", "our", "when", "which",
    "into", "each", "will", "does", "then", "they", "them", "been",
    "may", "it", "in", "on", "of", "to", "a", "an", "is", "as", "at",
    "by", "if", "or", "so", "do", "be", "we", "no", "up", "out",
})

# Pattern matching ## headers (lesson entries start with "## <date> — <task>").
# The template/comment block is skipped — it starts with HTML <!-- or <date> placeholder.
_HEADER_RE = re.compile(r"^## ", re.MULTILINE)

# Applies-to line pattern
_APPLIES_TO_RE = re.compile(r"\*\*Applies to:\*\*\s*(.*)")

# Default path for lessons-learned.md, resolved relative to CWD.
_DEFAULT_LESSONS_PATH = Path(".workflow_artifacts") / "memory" / "lessons-learned.md"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    """A single lessons-learned entry."""
    header: str       # The ## header line (date + task name)
    applies_to: str   # Text after **Applies to:**
    body: str         # Full entry text (including header)
    lineno: int       # 1-based line number of the ## header in the source


@dataclass
class SelectResult:
    """Result of select()."""
    selected: list[Entry] = field(default_factory=list)
    fellback_to_wholesale: bool = False
    total: int = 0
    selected_count: int = 0

    @property
    def selected_headers(self) -> list[str]:
        return [e.header for e in self.selected]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_entries(text: str) -> list[Entry]:
    """Split *text* into Entry objects, one per ## header.

    Skips the template/comment block at the top of lessons-learned.md:
    - Lines beginning with <!-- ... --> (HTML comments)
    - The literal template example starting with ``## <date>``

    Only entries whose header matches ``## <date>`` (date = 4 digits) or
    ``## YYYY-MM-DD`` format (real entries) are kept.
    """
    entries: list[Entry] = []
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)

    # Find all ## header positions
    positions: list[int] = []  # 0-based line indices of ## headers
    for i, line in enumerate(lines):
        if line.startswith("## "):
            positions.append(i)

    for idx, pos in enumerate(positions):
        # Determine end of this entry
        end_pos = positions[idx + 1] if idx + 1 < len(positions) else total_lines

        header_line = lines[pos].rstrip("\n").rstrip("\r")

        # Skip the template comment block: "## <date> — <task-name>" placeholder
        # (the literal angle-bracket form used in the comment block at the top)
        if "<date>" in header_line:
            continue

        # Reconstruct the entry body
        body = "".join(lines[pos:end_pos])

        # Extract Applies-to text
        applies_to = ""
        match = _APPLIES_TO_RE.search(body)
        if match:
            applies_to = match.group(1).strip()

        entries.append(Entry(
            header=header_line.lstrip("# ").strip(),  # strip "## " prefix
            applies_to=applies_to,
            body=body,
            lineno=pos + 1,  # 1-based
        ))

    return entries


def tokenize(s: str) -> set[str]:
    """Lowercase, split on non-alphanumeric, drop stopwords and short tokens.

    Deterministic: same input → same output. No stemming, no LLM.
    """
    tokens = re.split(r"[^a-z0-9]+", s.lower())
    return {
        t for t in tokens
        if len(t) >= MIN_TOKEN_LEN and t not in _STOPWORDS
    }


def score(task_tokens: set[str], entry: Entry) -> int:
    """Count shared tokens between task_tokens and the entry's applies_to + header.

    Primary signal: Applies-to tag + header (cheap, high-signal).
    Entry body is NOT scored — keeps over-inclusion bounded per R-04 design.
    """
    entry_tokens = tokenize(entry.applies_to + " " + entry.header)
    return len(task_tokens & entry_tokens)


def _always_include(entry: Entry, task_tokens: set[str]) -> bool:
    """Return True if this entry must always be included regardless of score.

    Always-include rules (R-04 — bias toward keeping a lesson):
    1. Entry's Applies-to line names a planning/review skill literally.
    2. Entry's header task-name shares any token with the task text.
    """
    # Rule 1: planning/review skill named in applies_to
    applies_lower = entry.applies_to.lower()
    for skill in PLANNING_SKILL_NAMES:
        if skill in applies_lower:
            return True

    # Rule 2: header task-name tokens overlap with task tokens
    header_tokens = tokenize(entry.header)
    if header_tokens & task_tokens:
        return True

    return False


def select(
    text: str,
    task_text: str,
    threshold: int = SELECT_THRESHOLD,
) -> SelectResult:
    """Select task-relevant entries from *text* (a lessons-learned.md blob).

    Returns entries with score >= threshold, PLUS always-include entries.
    Falls back to wholesale if result count < MIN_RESULTS or > MAX_FRACTION * total.

    The wholesale fallback guarantees pathological inputs degrade safely to
    the existing behavior, never to under-inclusion (R-04).
    """
    entries = parse_entries(text)
    total = len(entries)
    result = SelectResult(total=total)

    if total == 0:
        result.fellback_to_wholesale = True
        result.selected_count = 0
        return result

    # Tokenize the task description
    task_tokens = tokenize(task_text) if task_text.strip() else set()

    # Score each entry and apply always-include rules
    selected: list[Entry] = []
    for entry in entries:
        s = score(task_tokens, entry)
        ai = _always_include(entry, task_tokens) if task_tokens else False
        if s >= threshold or ai:
            selected.append(entry)

    selected_count = len(selected)

    # Wholesale fallback conditions:
    # 1. Task text empty or garbage (no tokens) → always wholesale
    # 2. Fewer than MIN_RESULTS selected
    # 3. More than MAX_FRACTION of all entries selected (no useful filtering)
    if (
        not task_tokens
        or selected_count < MIN_RESULTS
        or selected_count > ceil(MAX_FRACTION * total)
    ):
        result.fellback_to_wholesale = True
        result.selected = list(entries)
        result.selected_count = total
        return result

    result.selected = selected
    result.selected_count = selected_count
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memory_select",
        description=(
            "Select task-relevant entries from lessons-learned.md using "
            "deterministic token overlap. Falls back to wholesale read on "
            "pathological inputs. Never exits 1 — selection always succeeds."
        ),
    )
    parser.add_argument(
        "--task-text",
        required=True,
        metavar="TEXT",
        help="Task description text to match against lessons-learned entries.",
    )
    parser.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help=(
            "Path to lessons-learned.md. "
            f"Default: {_DEFAULT_LESSONS_PATH} (relative to CWD)."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=SELECT_THRESHOLD,
        metavar="N",
        help=f"Minimum score to include an entry (default: {SELECT_THRESHOLD}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help=(
            'Output result as JSON: '
            '{"selected":[{"header":...,"lineno":...,"score":...}...],'
            '"fellback_to_wholesale":bool,"total":N,"selected_count":M}.'
        ),
    )
    parser.add_argument(
        "--ids-only",
        action="store_true",
        dest="ids_only",
        help="Output only entry headers (one per line), not full body text.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code (0=success, 2=usage/IO error).

    Note: there is NO exit code 1. Selection always succeeds (degrades to wholesale).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve file path
    if args.file:
        lessons_path = Path(args.file).resolve()
    else:
        lessons_path = (Path.cwd() / _DEFAULT_LESSONS_PATH).resolve()

    if not lessons_path.exists():
        print(
            f"error: lessons-learned.md not found at {lessons_path}. "
            "Pass --file or run from the project root.",
            file=sys.stderr,
        )
        return 2

    try:
        text = lessons_path.read_text(encoding="utf-8")
    except (OSError, PermissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = select(text, args.task_text, threshold=args.threshold)

    if args.as_json:
        # Include score in each entry's JSON output
        task_tokens = tokenize(args.task_text) if args.task_text.strip() else set()
        selected_json = [
            {
                "header": e.header,
                "lineno": e.lineno,
                "score": score(task_tokens, e),
            }
            for e in result.selected
        ]
        print(json.dumps({
            "selected": selected_json,
            "fellback_to_wholesale": result.fellback_to_wholesale,
            "total": result.total,
            "selected_count": result.selected_count,
        }))
        return 0

    if args.ids_only:
        for entry in result.selected:
            print(entry.header)
        return 0

    # Default: print concatenated entry bodies (what a planning skill would read)
    print("".join(e.body for e in result.selected), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
