"""Shared session-selection helper for end_of_day and weekly_review.

Implements proc:T-03 (lower_bound discovery) and proc:T-19 (orphan detection)
from the eod-rollup-and-approvals plan. Stdlib-only; Python 3.8+.

CLI usage:
  python3 select_unprocessed_sessions.py \\
    --lower-bound-source MODE \\
    --project-root PATH \\
    [--window LOWER..UPPER] \\
    [--explicit-lower-bound YYYY-MM-DD] \\
    [--show-window]

  MODE: daily | weekly | explicit
  --window is optional: when omitted, `today` defaults to the system date. The LOWER
    part, when provided, is parsed but intentionally discarded — the authoritative
    lower_bound always comes from --lower-bound-source (see main()/compute_lower_bound()).
  --show-window prints one line `WINDOW: <lower_bound>..<today>` before the file list —
    this is the AUTHORITATIVE selection mechanism for /end_of_day (run once per run).
  Output: one session file path per line, sorted by date then filename.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Core functions (importable by tests and other skills)
# ---------------------------------------------------------------------------

def compute_lower_bound(
    source: str,
    project_root: Path,
    today: date,
    explicit_lower: str | None = None,
) -> date:
    """Compute the lower_bound date for session enumeration.

    Args:
        source: "daily", "weekly", or "explicit"
        project_root: root of the workflow project (contains .workflow_artifacts/)
        today: the current date
        explicit_lower: override value when source == "explicit" (YYYY-MM-DD string)

    Returns:
        lower_bound date (inclusive)
    """
    if source == "explicit":
        if explicit_lower is None:
            raise ValueError("--explicit-lower-bound required when source is 'explicit'")
        return date.fromisoformat(explicit_lower)

    if source == "daily":
        anchor_dir = project_root / ".workflow_artifacts" / "memory" / "daily"
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
        candidates: list[date] = []
        if anchor_dir.is_dir():
            for f in anchor_dir.iterdir():
                if pattern.match(f.name):
                    try:
                        candidates.append(date.fromisoformat(f.name[:10]))
                    except ValueError:
                        pass
        if not candidates:
            return today
        most_recent = max(candidates)
        if most_recent >= today:
            return today
        return most_recent + timedelta(days=1)

    if source == "weekly":
        anchor_dir = project_root / ".workflow_artifacts" / "memory" / "weekly"
        pattern = re.compile(r"^\d{4}-W\d{2}\.md$")
        candidates_weekly: list[str] = []
        if anchor_dir.is_dir():
            for f in anchor_dir.iterdir():
                if pattern.match(f.name):
                    candidates_weekly.append(f.name[:-3])  # strip .md
        if not candidates_weekly:
            return today - timedelta(days=7)
        last_week_str = max(candidates_weekly)
        # Parse ISO week (e.g. "2026-W19") to monday of that week
        last_week_monday = _iso_week_to_monday(last_week_str)
        return last_week_monday + timedelta(days=7)

    raise ValueError(f"Unknown source: {source!r}. Must be 'daily', 'weekly', or 'explicit'.")


def _iso_week_to_monday(week_str: str) -> date:
    """Convert "YYYY-Www" to the Monday of that ISO week."""
    year_str, week_str_part = week_str.split("-W")
    year = int(year_str)
    week = int(week_str_part)
    # ISO week 1 is the week containing the first Thursday; Monday is day 1.
    jan4 = date(year, 1, 4)  # Jan 4 is always in week 1
    week1_monday = jan4 - timedelta(days=jan4.isoweekday() - 1)
    return week1_monday + timedelta(weeks=week - 1)


def select_unprocessed_sessions(
    project_root: Path,
    today: date,
    source: str = "daily",
    explicit_lower: str | None = None,
    lower_bound: date | None = None,
) -> list[Path]:
    """Enumerate unprocessed session files in scope.

    A session file is in scope iff:
      (a) basename matches YYYY-MM-DD-<slug>.md
      (b) end_of_day_due is "yes" (missing field treated as "yes" per D-02)
      (c) file_date <= today. Selection is otherwise flag-authoritative only —
          `lower_bound` plays NO role in this filter; it is accepted below purely
          as an optional short-circuit for a caller's already-computed value
          (avoids a redundant `compute_lower_bound()` directory scan). Passing a
          different `lower_bound` value MUST NOT change the returned selection.

    Args:
        lower_bound: precomputed lower_bound (see `main()` / `--show-window`). When
            provided, `compute_lower_bound()` is NOT called — this is a pure
            short-circuit, not a new filter criterion.

    Returns paths sorted by (date_prefix, filename).
    """
    if lower_bound is None:
        lower_bound = compute_lower_bound(source, project_root, today, explicit_lower)
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return []

    file_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
    flag_pattern = re.compile(r"^-?\s*end_of_day_due:\s*(yes|no)\s*$", re.MULTILINE)

    result: list[Path] = []
    for f in session_dir.iterdir():
        m = file_pattern.match(f.name)
        if not m:
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue

        if file_date > today:
            continue  # future-dated: skip

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        flag_match = flag_pattern.search(content)
        flag = flag_match.group(1) if flag_match else "yes"  # legacy: missing = yes (D-02)

        if flag != "yes":
            continue  # already processed; flag authoritative

        result.append(f)

    result.sort(key=lambda p: p.name)
    return result


def find_orphans(
    project_root: Path,
    today: date,
    window_days: int = 7,
) -> tuple[list[Path], list[Path]]:
    """Detect orphaned session files (flag=no AND slug uncovered by any daily body).

    Implements proc:T-19 with word-boundary-aware slug matching (Round-4 MAJ-2).
    Hyphens are considered part of the slug token, so "json-discovery-map" does NOT
    match inside "json-discovery-map-review".

    Returns:
        (recent_orphans, historical_orphans)
        recent = file_date >= (today - window_days days)
        historical = older
    """
    # 1. Build union body text of all daily files (excluding insights-*.md)
    daily_dir = project_root / ".workflow_artifacts" / "memory" / "daily"
    daily_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    daily_body_union = ""
    if daily_dir.is_dir():
        for f in daily_dir.iterdir():
            if daily_pattern.match(f.name):
                try:
                    daily_body_union += f.read_text(encoding="utf-8") + "\n"
                except OSError:
                    pass

    # 2. Scan all session files
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return [], []

    file_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
    flag_pattern = re.compile(r"^-?\s*end_of_day_due:\s*(yes|no)\s*$", re.MULTILINE)
    seven_days_ago = today - timedelta(days=window_days)

    recent_orphans: list[Path] = []
    historical_orphans: list[Path] = []

    for f in session_dir.iterdir():
        m = file_pattern.match(f.name)
        if not m:
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue

        slug = m.group(2)

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        flag_match = flag_pattern.search(content)
        flag = flag_match.group(1) if flag_match else "yes"

        if flag != "no":
            continue  # not a candidate for orphan recovery

        # Word-boundary-aware slug check: hyphens count as part of the slug token.
        # (?<![\w-]) and (?![\w-]) prevent matching slug as a substring of a longer token.
        slug_re = re.compile(
            r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])"
        )
        if slug_re.search(daily_body_union):
            continue  # covered: slug appears as a standalone token in some daily body

        # flag=no AND slug uncovered → orphan
        if file_date >= seven_days_ago:
            recent_orphans.append(f)
        else:
            historical_orphans.append(f)

    recent_orphans.sort(key=lambda p: p.name)
    historical_orphans.sort(key=lambda p: p.name)
    return recent_orphans, historical_orphans


# ---------------------------------------------------------------------------
# proc:D-06 — same-day daily-cache merge
# ---------------------------------------------------------------------------

# Closed section order for daily-cache files (per plan D-02 + SKILL.md template).
_CLOSED_SECTION_ORDER = [
    "For human",
    "Summary",
    "Sessions processed",
    "Completed today",
    "Unfinished — carry forward",
    "Decisions log",
    "Git activity summary",
    "Cost summary",
    "Tomorrow's priorities",
]


def _parse_h2_sections(content: str) -> tuple[str, dict]:
    """Split content into (preamble, {section_name: body_text}) by H2 headings."""
    h2_re = re.compile(r"^(## .+)$", re.MULTILINE)
    matches = list(h2_re.finditer(content))
    if not matches:
        return content, {}
    preamble = content[: matches[0].start()]
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1)[3:]  # strip '## '
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[name] = content[body_start:body_end]
    return preamble, sections


def _render_h2_sections(preamble: str, sections: dict) -> str:
    """Compose content from preamble + sections in closed order (unknown sections appended last)."""
    parts = [preamble]
    seen: set[str] = set()
    for name in _CLOSED_SECTION_ORDER:
        if name in sections:
            parts.append(f"## {name}{sections[name]}")
            seen.add(name)
    for name in sorted(sections):  # stable order for unknown sections
        if name not in seen:
            parts.append(f"## {name}{sections[name]}")
    return "".join(parts)


def _parse_task_blocks(body: str) -> dict:
    """Extract {task_name: block_text} from a ## Completed today body.

    Task boundaries are `**Task: <name>**` lines (the live daily-cache convention).
    """
    task_re = re.compile(r"^\*\*Task: (.+?)\*\*", re.MULTILINE)
    matches = list(task_re.finditer(body))
    if not matches:
        return {}
    blocks: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        blocks[name] = body[start:end]
    return blocks


def merge_daily(
    existing_content: str,
    new_tasks: dict,
    new_session_rows: list,
    new_decisions: str = "",
    new_sections: dict | None = None,
) -> str:
    """Merge new session data into an existing daily-cache file (proc:D-06).

    Implements the section-by-section merge algorithm from plan D-06:
    - ## Completed today  : task-name set-union, latest-wins (callers supply task blocks)
    - ## Sessions processed: replace entire table
    - ## Decisions log    : append-only, line-level dedup for idempotency
    - Regenerated sections: replace if key present in new_sections, else keep existing

    Args:
        existing_content : current text of daily/<today>.md
        new_tasks        : {task_name: block_text} — new or updated Completed today entries
        new_session_rows : list of dicts (date/task/phase/status/notes) for Sessions processed
        new_decisions    : text to append to Decisions log; line-level dedup prevents re-append
        new_sections     : optional overrides for regenerated sections; recognised keys:
                           "Summary", "Cost summary", "Git activity summary",
                           "Tomorrow's priorities", "Unfinished — carry forward"

    Returns:
        merged content string (caller is responsible for atomic write)
    """
    if new_sections is None:
        new_sections = {}

    preamble, sections = _parse_h2_sections(existing_content)

    # Step 3 — ## Completed today: task-name set-union, latest-wins
    existing_tasks = _parse_task_blocks(sections.get("Completed today", ""))
    for task_name, block in new_tasks.items():
        existing_tasks[task_name] = block  # latest-wins: overwrite on same key
    if existing_tasks:
        rendered_tasks = "\n\n" + "\n\n".join(
            block.rstrip("\n") for _, block in sorted(existing_tasks.items())
        ) + "\n"
    else:
        rendered_tasks = sections.get("Completed today", "\n")
    sections["Completed today"] = rendered_tasks

    # Step 4 — ## Sessions processed: replace entire table
    if new_session_rows:
        header = (
            "\n\n| Date | Task | Phase | Status | Notes |\n"
            "|------|------|-------|--------|-------|\n"
        )
        row_lines = "".join(
            "| {date} | {task} | {phase} | {status} | {notes} |\n".format(
                date=r.get("date", ""),
                task=r.get("task", ""),
                phase=r.get("phase", ""),
                status=r.get("status", ""),
                notes=r.get("notes", "—"),
            )
            for r in new_session_rows
        )
        sections["Sessions processed"] = header + row_lines
    elif "Sessions processed" not in sections:
        sections["Sessions processed"] = "\n\n_No sessions processed._\n"

    # Step 5 — ## Decisions log: append-only, line-level dedup for idempotency
    existing_decisions = sections.get("Decisions log", "\n")
    if new_decisions.strip():
        existing_lines: set[str] = set(existing_decisions.splitlines())
        novel = [
            line
            for line in new_decisions.splitlines()
            if line.strip() and line not in existing_lines
        ]
        if novel:
            sections["Decisions log"] = (
                existing_decisions.rstrip("\n") + "\n" + "\n".join(novel) + "\n"
            )
    else:
        sections["Decisions log"] = existing_decisions

    # Steps 6–10 — regenerated sections: replace if caller supplied override
    for name in (
        "Cost summary",
        "Git activity summary",
        "Summary",
        "Tomorrow's priorities",
        "Unfinished — carry forward",
    ):
        if name in new_sections:
            sections[name] = new_sections[name]

    return _render_h2_sections(preamble, sections)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_window(window_str: str) -> tuple[str, str]:
    """Parse "LOWER..UPPER" into (lower, upper) date strings."""
    parts = window_str.split("..")
    if len(parts) != 2:
        raise ValueError(f"--window must be LOWER..UPPER, got: {window_str!r}")
    return parts[0].strip(), parts[1].strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enumerate unprocessed session files for end_of_day / weekly_review."
    )
    parser.add_argument(
        "--window",
        required=False,
        default=None,
        help=(
            "Date range LOWER..UPPER (YYYY-MM-DD..YYYY-MM-DD). Optional — when omitted, "
            "`today` defaults to the system date (date.today()). The LOWER part, when "
            "provided, is parsed but intentionally discarded (see comment at the discard "
            "site below) — the real lower_bound always comes from --lower-bound-source, "
            "never from --window."
        ),
    )
    parser.add_argument(
        "--lower-bound-source",
        required=True,
        choices=["daily", "weekly", "explicit"],
        help="How to discover the lower bound date",
    )
    parser.add_argument(
        "--explicit-lower-bound",
        help="Override lower bound (YYYY-MM-DD); only used when --lower-bound-source=explicit",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to the project root (default: current directory)",
    )
    parser.add_argument(
        "--show-window",
        action="store_true",
        help=(
            "Print exactly one line 'WINDOW: <lower_bound>..<today>' before the file list. "
            "This is the single, non-widened lower_bound value the script already derives "
            "internally, now surfaced instead of silently discarded."
        ),
    )
    args = parser.parse_args(argv)

    if args.window is not None:
        # LOWER is parsed but intentionally unused as a filter — the real lower_bound
        # always comes from --lower-bound-source below. Do not "fix" this by wiring
        # _lower_str in: that would reintroduce the dead-filter trap this plan removes.
        _lower_str, upper_str = _parse_window(args.window)
        try:
            today = date.fromisoformat(upper_str)
        except ValueError:
            print(f"Error: invalid upper date in --window: {upper_str!r}", file=sys.stderr)
            return 1
    else:
        today = date.today()

    project_root = Path(args.project_root).resolve()
    lower_bound = compute_lower_bound(
        args.lower_bound_source, project_root, today, args.explicit_lower_bound
    )
    if args.show_window:
        print(f"WINDOW: {lower_bound}..{today}")

    files = select_unprocessed_sessions(
        project_root=project_root,
        today=today,
        source=args.lower_bound_source,
        explicit_lower=args.explicit_lower_bound,
        lower_bound=lower_bound,
    )
    for f in files:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
