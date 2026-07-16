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


_FILE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")

# Round 2 MAJ-1 / Round 3 MAJ-1 / Round 3 MIN-3: the ONLY suffix _base_slug()
# strips. Deliberately narrow — see the Round 4 MAJ-1 scope note on T-01 in
# current-plan.md before extending this to the broader phase/stage-suffix
# vocabulary (-review, -implement, -pr, -critic-rN, -plan, -revise, -stageN,
# -sN, bare trailing numbers, letter-indexed sub-stages, ...). That
# generalization was deliberately scoped OUT of this round (verified
# false-positive collision risk + inconsistent real-corpus suffix grammar);
# do not "helpfully" widen this without re-opening the plan.
_ORCHESTRATOR_SUFFIX = "-orchestrator"


def _collect_sibling_slugs(files: list[Path]) -> set[str]:
    """Collect every raw slug seen across an already-listed set of session files.

    Single extra in-memory pass over filenames already gathered by the caller's
    one directory listing — never a second directory scan.
    """
    sibling_slugs: set[str] = set()
    for f in files:
        m = _FILE_PATTERN.match(f.name)
        if m:
            sibling_slugs.add(m.group(2))
    return sibling_slugs


def _base_slug(slug: str, sibling_slugs: set[str]) -> str:
    """Derive the base slug, stripping a trailing '-orchestrator' suffix when safe.

    Guarded per Round 3 MIN-3: strips ONLY when (i) the stripped result is
    non-empty AND (ii) the stripped result is itself present in
    `sibling_slugs` (a set of every raw slug seen across sessions/, collected
    in a first pass before this helper is called). This guard prevents
    over-stripping a genuinely `<x>-orchestrator`-named task that has no
    separate `<x>.md` sibling session — such a slug is left unstripped and
    evaluated on its own raw form. An auto-generated `<task>-orchestrator.md`
    file, by contrast, always coexists with at least one `<task>.md` session
    under the base slug, so it passes the guard and gets stripped.
    """
    if slug.endswith(_ORCHESTRATOR_SUFFIX):
        candidate = slug[: -len(_ORCHESTRATOR_SUFFIX)]
        if candidate and candidate in sibling_slugs:
            return candidate
    return slug


def find_orphans(
    project_root: Path,
    today: date,
    window_days: int = 7,
) -> tuple[list[Path], list[Path]]:
    """Detect orphaned session files (flag=no AND base slug uncovered by any daily body).

    Implements proc:T-19 with word-boundary-aware slug matching (Round-4 MAJ-2).
    Hyphens are considered part of the slug token, so "json-discovery-map" does NOT
    match inside "json-discovery-map-review".

    Round 3 MAJ-1: the slug checked is the GUARDED BASE SLUG (`_base_slug()`),
    not the raw filename slug — shared with `find_covered_due_sessions()` so
    both functions agree on orchestrator-suffixed coverage within the same
    `--recover-orphans` run (closes the Step 0a <-> Step 0 same-run
    self-contradiction the critic identified). Phase/stage-suffixed slugs are
    NOT covered by this fix — see the Round 4 MAJ-1 scope note on `_base_slug`.

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

    # 2. Scan all session files (single directory listing, reused below)
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return [], []

    all_files = list(session_dir.iterdir())
    sibling_slugs = _collect_sibling_slugs(all_files)

    flag_pattern = re.compile(r"^-?\s*end_of_day_due:\s*(yes|no)\s*$", re.MULTILINE)
    seven_days_ago = today - timedelta(days=window_days)

    recent_orphans: list[Path] = []
    historical_orphans: list[Path] = []

    for f in all_files:
        m = _FILE_PATTERN.match(f.name)
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

        base_slug = _base_slug(slug, sibling_slugs)

        # Word-boundary-aware slug check: hyphens count as part of the slug token.
        # (?<![\w-]) and (?![\w-]) prevent matching slug as a substring of a longer token.
        slug_re = re.compile(
            r"(?<![\w-])" + re.escape(base_slug) + r"(?![\w-])"
        )
        if slug_re.search(daily_body_union):
            continue  # covered: base slug appears as a standalone token in some daily body

        # flag=no AND base slug uncovered → orphan
        if file_date >= seven_days_ago:
            recent_orphans.append(f)
        else:
            historical_orphans.append(f)

    recent_orphans.sort(key=lambda p: p.name)
    historical_orphans.sort(key=lambda p: p.name)
    return recent_orphans, historical_orphans


def find_covered_due_sessions(
    project_root: Path,
    today: date,
) -> tuple[list[Path], list[Path]]:
    """Partition flag=yes ('due') sessions into covered vs uncovered by daily bodies.

    Mirror image of `find_orphans()`: `find_orphans()` targets flag=no sessions
    that a daily body does NOT cover (missed backlog); this targets flag=yes
    sessions that a daily body ALREADY covers (already captured, should have
    been flipped to `end_of_day_due: no` but never was — the 2026-07-04 pain
    point). Shares the same guarded `_base_slug()` derivation (Round 2 MAJ-1 +
    Round 3 MIN-3) so orchestrator-suffixed sessions classify consistently
    with `find_orphans()`.

    Phase/stage-suffixed flag=yes sessions are NOT reconciled by this function
    (Round 4 MAJ-1 scope note) — they classify uncovered/backlog exactly as
    they did before this fix; this is a documented, deliberate scope
    boundary, not a bug.

    Returns:
        (covered, uncovered) — `covered` sessions are safe to auto-flip to
        `end_of_day_due: no` (their work is already captured in a daily
        body); `uncovered` is genuine backlog, unchanged from today's
        behavior.
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

    # 2. Scan all session files (single directory listing, reused below)
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return [], []

    all_files = list(session_dir.iterdir())
    sibling_slugs = _collect_sibling_slugs(all_files)

    flag_pattern = re.compile(r"^-?\s*end_of_day_due:\s*(yes|no)\s*$", re.MULTILINE)

    covered: list[Path] = []
    uncovered: list[Path] = []

    for f in all_files:
        m = _FILE_PATTERN.match(f.name)
        if not m:
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if file_date > today:
            continue  # future-dated: skip (mirrors select_unprocessed_sessions)

        slug = m.group(2)

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        flag_match = flag_pattern.search(content)
        flag = flag_match.group(1) if flag_match else "yes"  # legacy: missing = yes (D-02)

        if flag != "yes":
            continue  # not a candidate for coverage reconciliation (already no)

        base_slug = _base_slug(slug, sibling_slugs)

        slug_re = re.compile(
            r"(?<![\w-])" + re.escape(base_slug) + r"(?![\w-])"
        )
        if slug_re.search(daily_body_union):
            covered.append(f)
        else:
            uncovered.append(f)

    covered.sort(key=lambda p: p.name)
    uncovered.sort(key=lambda p: p.name)
    return covered, uncovered


def find_finalized_marked(
    project_root: Path,
    lower_bound: date,
    today: date,
) -> list[Path]:
    """Find in-window sessions carrying a 'finalized_by_end_of_task' marker.

    Implements the Round 3 MAJ-2 digest-preservation producer consumed by
    `/end_of_day` Step 2 (`in_scope = script_file_list ∪ confirmed_orphans ∪
    finalized_marked`). A session flipped to `end_of_day_due: no` by
    `flip_finalized_task_sessions()` (T-03) is flag=no by construction, so it
    structurally cannot appear in `select_unprocessed_sessions()`'s flag=yes-only
    output — this function scans independently and does NOT filter on
    `end_of_day_due` at all; only the marker's presence and the file's date
    matter.

    Args:
        lower_bound: inclusive window lower bound — the SAME value the caller
            already computed for `--show-window`; not recomputed here.
        today: inclusive window upper bound.

    Returns paths sorted by (date_prefix, filename).
    """
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return []

    marker_pattern = re.compile(
        r"^-?\s*finalized_by_end_of_task:\s*\d{4}-\d{2}-\d{2}\s*$", re.MULTILINE
    )

    result: list[Path] = []
    for f in session_dir.iterdir():
        m = _FILE_PATTERN.match(f.name)
        if not m:
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if file_date < lower_bound or file_date > today:
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        if marker_pattern.search(content):
            result.append(f)

    result.sort(key=lambda p: p.name)
    return result


def flip_finalized_task_sessions(
    project_root: Path,
    slug: str,
    finalization_date: str,
) -> list[Path]:
    """Flip a finalized task's sessions to end_of_day_due: no, with a provenance marker.

    Implements the Round 3 MIN-2 single-invocation flip for `/end_of_task`
    Sub-phase B (replaces what would otherwise be a per-file Read+Edit loop
    that risks blowing the ~15-tool-use cap). Scans ALL session files under
    `sessions/` (all dates — a finalized task's sessions can span any date
    range), matching files whose raw slug is EXACTLY `slug` OR EXACTLY
    `<slug>-orchestrator` (direct string equality both ways). This is the
    reverse of `_base_slug()`'s derivation direction: the caller supplies the
    task's own known, exact finalized slug (not an observed slug being
    reverse-engineered), so no sibling-existence guard is needed here — see
    plan Round 3 MIN-3 for why the two guard directions differ.

    For each match: atomically flips `end_of_day_due` to `no`, and
    writes/overwrites a `finalized_by_end_of_task: <finalization_date>`
    marker line immediately alongside the flag line (same write). Idempotent
    — re-running on an already-flipped, already-marked file replaces the
    marker with the new date and leaves the flag at `no` (no-op on the flag).

    Returns the list of flipped file paths, sorted by name.
    """
    session_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not session_dir.is_dir():
        return []

    flag_pattern = re.compile(r"^(-?\s*)end_of_day_due:\s*(?:yes|no)\s*$", re.MULTILINE)
    marker_pattern = re.compile(
        r"^-?\s*finalized_by_end_of_task:\s*\d{4}-\d{2}-\d{2}\s*\n?", re.MULTILINE
    )
    orchestrator_slug = f"{slug}-orchestrator"

    flipped: list[Path] = []
    for f in sorted(session_dir.iterdir(), key=lambda p: p.name):
        m = _FILE_PATTERN.match(f.name)
        if not m:
            continue
        file_slug = m.group(2)
        if file_slug != slug and file_slug != orchestrator_slug:
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        marker_line = f"finalized_by_end_of_task: {finalization_date}"

        # Idempotency: strip any existing marker line first so a re-run
        # replaces (not duplicates) it.
        content_no_marker = marker_pattern.sub("", content)

        def _flip_and_mark(mo: "re.Match[str]", _marker_line: str = marker_line) -> str:
            prefix = mo.group(1)
            return f"{prefix}end_of_day_due: no\n{prefix}{_marker_line}"

        new_content, n = flag_pattern.subn(_flip_and_mark, content_no_marker, count=1)
        if n == 0:
            # Legacy: no flag line present (missing = yes per D-02). Append an
            # explicit flag + marker pair at end of file.
            if not new_content.endswith("\n"):
                new_content += "\n"
            new_content += f"- end_of_day_due: no\n- {marker_line}\n"

        tmp_path = f.with_name(f.name + ".tmp")
        tmp_path.write_text(new_content, encoding="utf-8")
        tmp_path.replace(f)
        flipped.append(f)

    flipped.sort(key=lambda p: p.name)
    return flipped


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
        required=False,
        default=None,
        choices=["daily", "weekly", "explicit"],
        help=(
            "How to discover the lower bound date. Required for the default "
            "(window/selection) mode; not used by --reconcile-covered or "
            "--flip-finalized-task, which operate independently of lower_bound."
        ),
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
    parser.add_argument(
        "--reconcile-covered",
        action="store_true",
        help=(
            "Dry-run mode: print two labelled lists, 'COVERED:' (flag=yes sessions "
            "already covered by a daily body — safe to auto-flip to end_of_day_due: "
            "no) and 'UNCOVERED:' (genuine backlog). Makes no writes. Does not "
            "require --lower-bound-source."
        ),
    )
    parser.add_argument(
        "--include-finalized-marked",
        action="store_true",
        help=(
            "With --show-window, additionally print 'FINALIZED: <path>' lines "
            "(after the WINDOW: line and the plain file list) for in-window "
            "flag=no sessions carrying a finalized_by_end_of_task marker. No-op "
            "when --show-window is not also passed."
        ),
    )
    parser.add_argument(
        "--flip-finalized-task",
        metavar="SLUG",
        default=None,
        help=(
            "Flip every session whose raw slug is exactly SLUG or "
            "'SLUG-orchestrator' to end_of_day_due: no, writing a "
            "finalized_by_end_of_task marker on each (requires "
            "--finalization-date). Prints one flipped file path per line. "
            "Does not require --lower-bound-source."
        ),
    )
    parser.add_argument(
        "--finalization-date",
        default=None,
        help="YYYY-MM-DD date recorded in the finalized_by_end_of_task marker; required with --flip-finalized-task.",
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

    if args.reconcile_covered:
        covered, uncovered = find_covered_due_sessions(project_root, today)
        print("COVERED:")
        for f in covered:
            print(f)
        print("UNCOVERED:")
        for f in uncovered:
            print(f)
        return 0

    if args.flip_finalized_task is not None:
        if args.finalization_date is None:
            print(
                "Error: --finalization-date is required with --flip-finalized-task",
                file=sys.stderr,
            )
            return 1
        flipped = flip_finalized_task_sessions(
            project_root, args.flip_finalized_task, args.finalization_date
        )
        for f in flipped:
            print(f)
        return 0

    if args.lower_bound_source is None:
        print(
            "Error: --lower-bound-source is required unless --reconcile-covered "
            "or --flip-finalized-task is used",
            file=sys.stderr,
        )
        return 1

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

    if args.show_window and args.include_finalized_marked:
        finalized = find_finalized_marked(project_root, lower_bound, today)
        for f in finalized:
            print(f"FINALIZED: {f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
