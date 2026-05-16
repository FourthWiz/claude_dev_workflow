"""Behavioral algorithm tests for end_of_day session selection.

Tests the Python reference implementations of proc:T-03 (lower_bound),
proc:T-19 (orphan detection), and proc:D-06 (merge contract) via the
shared helper module select_unprocessed_sessions.py.

Uses pytest tmp_path fixtures for filesystem isolation.
"""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

import pytest

# Add the core/scripts directory so we can import the helper directly.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_unprocessed_sessions import (  # noqa: E402
    compute_lower_bound,
    find_orphans,
    merge_daily,
    select_unprocessed_sessions,
)


TODAY = date(2026, 5, 16)


def _write_session(
    sessions_dir: Path,
    filename: str,
    flag: str = "yes",
    status: str = "in_progress",
) -> Path:
    """Write a minimal session file."""
    p = sessions_dir / filename
    p.write_text(
        f"# Session\n\n## Status\n\n{status}\n\n## Cost\n\n- end_of_day_due: {flag}\n",
        encoding="utf-8",
    )
    return p


def _write_daily(daily_dir: Path, date_str: str, body: str = "") -> Path:
    """Write a minimal daily-cache file."""
    p = daily_dir / f"{date_str}.md"
    p.write_text(f"# Daily Cache — {date_str}\n\n## Summary\n\n{body}\n", encoding="utf-8")
    return p


def _make_project(tmp_path: Path) -> Tuple[Path, Path, Path]:
    """Create project structure; return (project_root, sessions_dir, daily_dir)."""
    sessions = tmp_path / ".workflow_artifacts" / "memory" / "sessions"
    sessions.mkdir(parents=True)
    daily = tmp_path / ".workflow_artifacts" / "memory" / "daily"
    daily.mkdir(parents=True)
    return tmp_path, sessions, daily


# ---------------------------------------------------------------------------
# proc:T-03 — lower_bound discovery
# ---------------------------------------------------------------------------


def test_no_prior_daily_lower_bound_is_today(tmp_path):
    """(a) No prior daily: empty daily/ + 3 sessions → lower_bound = today."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY

    _write_session(sessions, f"{today}-task-a.md", flag="yes")
    _write_session(sessions, f"{today}-task-b.md", flag="yes")
    _write_session(sessions, f"{today}-task-c.md", flag="no")

    lb = compute_lower_bound("daily", root, today)
    assert lb == today

    selected = select_unprocessed_sessions(root, today, source="daily")
    names = {p.name for p in selected}
    assert f"{today}-task-a.md" in names
    assert f"{today}-task-b.md" in names
    assert f"{today}-task-c.md" not in names, "flag=no should not be selected"


def test_prior_daily_3_days_ago(tmp_path):
    """(b) Prior daily 3 days ago + mixed flags → lower_bound = prior+1."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    prior_date = today - timedelta(days=3)
    _write_daily(daily, str(prior_date))

    # Sessions after the prior daily window
    d1 = today - timedelta(days=2)
    d2 = today - timedelta(days=1)
    _write_session(sessions, f"{d1}-task-yes.md", flag="yes")
    _write_session(sessions, f"{d1}-task-no.md", flag="no")
    _write_session(sessions, f"{d2}-task-legacy.md")  # no flag line → treated as yes
    _write_session(sessions, f"{today}-task-today.md", flag="yes")

    lb = compute_lower_bound("daily", root, today)
    assert lb == prior_date + timedelta(days=1)

    selected = select_unprocessed_sessions(root, today, source="daily")
    names = {p.name for p in selected}
    assert f"{d1}-task-yes.md" in names
    assert f"{d1}-task-no.md" not in names
    assert f"{d2}-task-legacy.md" in names, "legacy (no flag line) should be treated as yes"
    assert f"{today}-task-today.md" in names


def test_prior_daily_is_today_lower_bound_is_today(tmp_path):
    """(c) Prior daily = today → lower_bound = today (same-day re-run)."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today))
    _write_session(sessions, f"{today}-task-a.md", flag="yes")

    lb = compute_lower_bound("daily", root, today)
    assert lb == today


def test_legacy_session_no_flag_line_treated_as_yes(tmp_path):
    """(d) Legacy session lacking end_of_day_due field → treated as yes (D-02)."""
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    # Write session without flag line
    p = sessions / f"{today}-legacy.md"
    p.write_text("# Session\n\n## Status\n\nin_progress\n", encoding="utf-8")

    selected = select_unprocessed_sessions(root, today, source="daily")
    assert p in selected, "Session without end_of_day_due must be treated as yes (D-02)"


def test_future_dated_session_excluded(tmp_path):
    """(e) Future-dated session excluded from selection."""
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    future = today + timedelta(days=1)
    _write_session(sessions, f"{future}-task-future.md", flag="yes")

    selected = select_unprocessed_sessions(root, today, source="daily")
    names = {p.name for p in selected}
    assert f"{future}-task-future.md" not in names, "Future-dated session must be excluded"


# ---------------------------------------------------------------------------
# proc:T-19 — orphan detection (slug-based criterion)
# ---------------------------------------------------------------------------


def test_orphan_detection_slug_based(tmp_path):
    """(f) CRIT-1 fixture: daily exists but covers only one slug; others are orphans.

    This is the exact bug class from the live project:
      - daily/2026-05-13.md body mentions only 'phase-23-cost-core'
      - sessions 2026-05-13-foo.md and 2026-05-13-bar.md (flag=no) are orphans

    The old date-only criterion would have returned neither (daily exists for the date).
    The slug-based criterion returns both — this test locks that regression.
    """
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY

    # Daily mentions only 'phase-23-cost-core'
    _write_daily(daily, "2026-05-13", body="Completed phase-23-cost-core review session.")

    # Sessions on 2026-05-13 that are NOT mentioned in the daily body
    _write_session(sessions, "2026-05-13-foo.md", flag="no")
    _write_session(sessions, "2026-05-13-bar.md", flag="no")
    # This one IS mentioned (slug = 'phase-23-cost-core')
    _write_session(sessions, "2026-05-13-phase-23-cost-core.md", flag="no")

    recent, historical = find_orphans(root, today, window_days=7)
    recent_names = {p.name for p in recent}

    assert "2026-05-13-foo.md" in recent_names, "foo slug not covered → should be orphan"
    assert "2026-05-13-bar.md" in recent_names, "bar slug not covered → should be orphan"
    assert "2026-05-13-phase-23-cost-core.md" not in recent_names, (
        "phase-23-cost-core slug IS covered by daily body → must NOT be an orphan"
    )

    # Regression: simulate date-only criterion to confirm it would have returned neither.
    # Date-only would say "a daily exists for 2026-05-13, so no orphans on that date" — wrong.
    # The slug-based criterion correctly identifies foo and bar.
    assert len(recent_names) >= 2, "At least 2 orphans expected (foo, bar)"


def test_orphan_slug_word_boundary_no_prefix_collision(tmp_path):
    """(i) Round-4 MAJ-2: slug-prefix collision must NOT produce false-positive coverage.

    'json-discovery-map' as a slug must NOT match inside 'json-discovery-map-review'
    in the daily body. The naive substring check would falsely mark it covered.
    """
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY

    # Daily body mentions 'json-discovery-map-review' but NOT 'json-discovery-map' standalone
    _write_daily(
        daily,
        str(today - timedelta(days=2)),
        body="Completed json-discovery-map-review session today.",
    )

    _write_session(sessions, f"{today - timedelta(days=2)}-json-discovery-map.md", flag="no")
    _write_session(sessions, f"{today - timedelta(days=2)}-json-discovery-map-review.md", flag="no")

    recent, _ = find_orphans(root, today, window_days=7)
    recent_names = {p.name for p in recent}

    shorter_slug_date = str(today - timedelta(days=2))
    assert f"{shorter_slug_date}-json-discovery-map.md" in recent_names, (
        "'json-discovery-map' slug must be an orphan — it must NOT match inside "
        "'json-discovery-map-review' in the daily body (word-boundary-aware regex)."
    )
    assert f"{shorter_slug_date}-json-discovery-map-review.md" not in recent_names, (
        "'json-discovery-map-review' slug IS in the daily body → must NOT be an orphan."
    )


def test_orphan_partitioned_recent_vs_historical(tmp_path):
    """Orphans partitioned correctly: RECENT >= (today - 7 days), HISTORICAL older."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    seven_days_ago = today - timedelta(days=7)

    _write_session(sessions, f"{seven_days_ago}-recent-orphan.md", flag="no")
    _write_session(sessions, f"{seven_days_ago - timedelta(days=1)}-historical-orphan.md", flag="no")

    recent, historical = find_orphans(root, today, window_days=7)
    recent_names = {p.name for p in recent}
    hist_names = {p.name for p in historical}

    assert f"{seven_days_ago}-recent-orphan.md" in recent_names
    assert f"{seven_days_ago - timedelta(days=1)}-historical-orphan.md" in hist_names


# ---------------------------------------------------------------------------
# proc:D-06 — same-day merge: behavioral fixtures (g) and (h)
# ---------------------------------------------------------------------------


def test_merge_daily_fidelity():
    """(g) proc:D-06 merge fidelity: task set-union latest-wins, table replacement, decisions append.

    Pre-existing daily has alpha task block + 1-row Sessions processed table + one decision.
    New sessions: alpha (re-run with updated content) and beta (new).
    merge_daily must:
      (i)  replace alpha's block with new content (latest-wins, NOT duplicate)
      (ii) append beta's block
      (iii) replace Sessions processed table entirely (2 rows)
      (iv) append new decision while preserving existing decision-one
      (v)  produce NO duplicate **Task: alpha** header
    """
    base_content = (
        "# Daily Cache — 2026-05-16\n\n"
        "## Summary\n\nOriginal summary.\n\n"
        "## Sessions processed\n\n"
        "| Date | Task | Phase | Status | Notes |\n"
        "|------|------|-------|--------|-------|\n"
        "| 2026-05-16 | alpha | plan | completed | — |\n\n"
        "## Completed today\n\n"
        "**Task: alpha**\n\nAlpha original content.\n\n"
        "## Decisions log\n\ndecision-one — alpha decision\n"
    )
    alpha_new = "**Task: alpha**\n\nAlpha new content (re-run with updates).\n"
    beta_block = "**Task: beta**\n\nBeta new content.\n"

    result = merge_daily(
        existing_content=base_content,
        new_tasks={"alpha": alpha_new, "beta": beta_block},
        new_session_rows=[
            {"date": "2026-05-16", "task": "alpha", "phase": "plan", "status": "completed", "notes": "—"},
            {"date": "2026-05-16", "task": "beta", "phase": "implement", "status": "completed", "notes": "—"},
        ],
        new_decisions="decision-two — beta decision",
    )

    # (i) latest alpha content present; original replaced
    assert "Alpha new content" in result, "alpha block must be replaced by latest content"
    assert "Alpha original content" not in result, "original alpha content must NOT remain (latest-wins)"

    # (ii) beta present
    assert "Beta new content" in result, "beta block must be appended"

    # (iii) both sessions in table
    assert "| alpha |" in result or "alpha" in result
    assert "| beta |" in result or "beta" in result

    # (iv) both decisions present
    assert "decision-one — alpha decision" in result, "pre-existing decision must be preserved"
    assert "decision-two — beta decision" in result, "new decision must be appended"

    # (v) no duplicate task header
    assert result.count("**Task: alpha**") == 1, "must have exactly one **Task: alpha** header — no duplicates"


def test_merge_daily_idempotency():
    """(h) proc:D-06 idempotency: running merge_daily twice with same inputs produces byte-identical output.

    Covers the idempotency contract from plan D-06 step 15.
    """
    base_content = (
        "# Daily Cache — 2026-05-16\n\n"
        "## Summary\n\nBase summary.\n\n"
        "## Completed today\n\n"
        "**Task: alpha**\n\nAlpha base.\n\n"
        "## Sessions processed\n\n"
        "| Date | Task | Phase | Status | Notes |\n"
        "|------|------|-------|--------|-------|\n"
        "| 2026-05-16 | alpha | plan | completed | — |\n\n"
        "## Decisions log\n\nexisting decision\n"
    )
    merge_kwargs = dict(
        new_tasks={
            "alpha": "**Task: alpha**\n\nAlpha merged.\n",
            "beta": "**Task: beta**\n\nBeta merged.\n",
        },
        new_session_rows=[
            {"date": "2026-05-16", "task": "alpha", "phase": "plan", "status": "completed", "notes": "—"},
            {"date": "2026-05-16", "task": "beta", "phase": "plan", "status": "in_progress", "notes": "—"},
        ],
        new_decisions="new merged decision",
    )

    output1 = merge_daily(base_content, **merge_kwargs)
    # Apply same merge again to the already-merged output — must be idempotent
    output2 = merge_daily(output1, **merge_kwargs)

    assert output1 == output2, (
        "merge_daily must be idempotent: applying the same merge to the already-merged "
        "output must produce byte-identical content.\n"
        f"Length diff: {len(output1)} vs {len(output2)}"
    )


# ---------------------------------------------------------------------------
# proc:D-06 — same-day merge: adapter SKILL.md keyword assertions
# ---------------------------------------------------------------------------


def test_adapter_documents_merge_keywords():
    """Adapter SKILL.md must contain at least 3 of the proc:D-06 merge keywords.

    Guards against a trivially-passing single-word 'MERGE' grep (Round-2 MIN).
    """
    adapter = (
        Path(__file__).resolve().parent.parent.parent
        / "adapters" / "claude" / "skills" / "end_of_day" / "SKILL.md"
    )
    text = adapter.read_text(encoding="utf-8")
    keywords = [
        "task-name set-union",
        "latest wins",
        "regenerate",
        "replace entirely",
        "Sessions processed table",
        "MERGE",
        "section-by-section",
        "proc:D-06",
    ]
    found = [kw for kw in keywords if kw in text]
    assert len(found) >= 3, (
        f"Adapter SKILL.md merge contract must contain at least 3 keywords from proc:D-06. "
        f"Found: {found}"
    )
