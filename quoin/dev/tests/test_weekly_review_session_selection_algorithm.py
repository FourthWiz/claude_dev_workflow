"""Behavioral tests for weekly_review session selection using shared helper.

Tests select_unprocessed_sessions with --lower-bound-source weekly, plus
parity assertions comparing daily vs weekly mode outputs for matching windows.

Uses pytest tmp_path fixtures for filesystem isolation.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_unprocessed_sessions import (  # noqa: E402
    compute_lower_bound,
    find_orphans,
    select_unprocessed_sessions,
)

TODAY = date(2026, 5, 16)  # A Saturday (ISO week 2026-W20)


def _make_project(tmp_path: Path) -> Tuple[Path, Path, Path, Path]:
    sessions = tmp_path / ".workflow_artifacts" / "memory" / "sessions"
    sessions.mkdir(parents=True)
    daily = tmp_path / ".workflow_artifacts" / "memory" / "daily"
    daily.mkdir(parents=True)
    weekly_dir = tmp_path / ".workflow_artifacts" / "memory" / "weekly"
    weekly_dir.mkdir(parents=True)
    return tmp_path, sessions, daily, weekly_dir


def _write_session(sessions_dir: Path, filename: str, flag: str = "yes") -> Path:
    p = sessions_dir / filename
    p.write_text(
        f"# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: {flag}\n",
        encoding="utf-8",
    )
    return p


def _write_daily(daily_dir: Path, date_str: str, body: str = "") -> Path:
    p = daily_dir / f"{date_str}.md"
    p.write_text(f"# Daily Cache — {date_str}\n\n{body}\n", encoding="utf-8")
    return p


def _write_weekly(weekly_dir: Path, iso_week: str) -> Path:
    p = weekly_dir / f"{iso_week}.md"
    p.write_text(f"# Weekly Review — {iso_week}\n\n## Summary\n\nSomething done.\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Weekly-mode lower_bound tests
# ---------------------------------------------------------------------------


def test_no_prior_weekly_lower_bound_is_7_days_ago(tmp_path):
    """(i) No prior weekly file → lower_bound = today - 7 days."""
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    lb = compute_lower_bound("weekly", root, TODAY)
    assert lb == TODAY - timedelta(days=7)


def test_prior_weekly_lower_bound_is_next_monday(tmp_path):
    """(ii) Prior weekly at 2026-W19 → lower_bound = 2026-05-11 (Monday after W19)."""
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    _write_weekly(weekly_dir, "2026-W19")  # W19 monday = 2026-05-04

    lb = compute_lower_bound("weekly", root, TODAY)
    # W19 monday = 2026-05-04; lower_bound = 2026-05-04 + 7 = 2026-05-11
    assert lb == date(2026, 5, 11)

    # Sessions on or after 2026-05-11 with flag=yes should be selected
    d1 = date(2026, 5, 11)
    _write_session(sessions, f"{d1}-task-new.md", flag="yes")
    _write_session(sessions, f"{date(2026, 5, 4)}-task-old.md", flag="yes")  # in W19, not in scope

    selected = select_unprocessed_sessions(root, TODAY, source="weekly")
    names = {p.name for p in selected}
    assert f"{d1}-task-new.md" in names
    # Old session from W19 should NOT be selected (date before lower_bound);
    # unless flag=yes triggers the catch-up rule — it does! flag=yes is included.
    # The catch-up rule: flag=yes sessions from before lower_bound are included.
    assert f"{date(2026, 5, 4)}-task-old.md" in names, (
        "flag=yes sessions from before lower_bound are included by the catch-up rule"
    )


def test_two_iso_weeks_gap(tmp_path):
    """(iii) Two ISO weeks gap: last weekly is W18, today in W20 → mid-gap session selected."""
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    _write_weekly(weekly_dir, "2026-W18")  # W18 monday = 2026-04-27

    lb = compute_lower_bound("weekly", root, TODAY)
    # W18 monday = 2026-04-27; lower_bound = 2026-04-27 + 7 = 2026-05-04
    assert lb == date(2026, 5, 4)

    mid_gap = date(2026, 5, 7)
    _write_session(sessions, f"{mid_gap}-task-mid.md", flag="yes")

    selected = select_unprocessed_sessions(root, TODAY, source="weekly")
    names = {p.name for p in selected}
    assert f"{mid_gap}-task-mid.md" in names


def test_same_week_rerun_no_new_sessions(tmp_path):
    """(iv) Prior weekly is current week → no unprocessed in-window sessions (all flag=no)."""
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    _write_weekly(weekly_dir, "2026-W20")  # current week

    # Sessions in W20 already processed (flag=no)
    d = date(2026, 5, 12)
    p = sessions / f"{d}-task-done.md"
    p.write_text(
        "# Session\n\n## Status\n\ncompleted\n\n## Cost\n\n- end_of_day_due: no\n",
        encoding="utf-8",
    )

    selected = select_unprocessed_sessions(root, TODAY, source="weekly")
    names = {p.name for p in selected}
    assert f"{d}-task-done.md" not in names, (
        "flag=no sessions must not be selected in same-week re-run"
    )


def test_orphan_in_window_not_in_selection(tmp_path):
    """(v) Orphan (flag=no, slug uncovered) returned by find_orphans, NOT select_unprocessed."""
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    today = TODAY

    # Daily exists but body does NOT mention the orphan slug
    _write_daily(daily, str(today - timedelta(days=2)), body="Completed something-else.")

    orphan_date = today - timedelta(days=2)
    _write_session(sessions, f"{orphan_date}-orphan-task.md", flag="no")

    # Should NOT be in select_unprocessed_sessions
    selected = select_unprocessed_sessions(root, today, source="weekly")
    names = {p.name for p in selected}
    assert f"{orphan_date}-orphan-task.md" not in names

    # SHOULD be in find_orphans
    recent, _ = find_orphans(root, today, window_days=7)
    recent_names = {p.name for p in recent}
    assert f"{orphan_date}-orphan-task.md" in recent_names


# ---------------------------------------------------------------------------
# Parity test: daily vs weekly produce identical results for matching windows
# ---------------------------------------------------------------------------


def test_daily_weekly_parity_for_matching_window(tmp_path):
    """Parity: daily and weekly modes return identical results for matching windows.

    When daily/ and weekly/ anchors are both absent and today is the upper bound,
    both modes enumerate the same session files (all flag=yes in the window).
    """
    root, sessions, daily, weekly_dir = _make_project(tmp_path)
    today = TODAY

    # Add sessions with flag=yes
    for i in range(3):
        d = today - timedelta(days=i + 1)
        _write_session(sessions, f"{d}-task-{i}.md", flag="yes")

    daily_selected = select_unprocessed_sessions(root, today, source="daily")
    weekly_selected = select_unprocessed_sessions(root, today, source="weekly")

    daily_names = {p.name for p in daily_selected}
    weekly_names = {p.name for p in weekly_selected}

    # Both modes should select the same sessions when anchors are absent
    # (daily lb = today, weekly lb = today - 7; but flag=yes catch-up rule means
    # flag=yes sessions are always included regardless of lower_bound)
    # All 3 sessions have flag=yes so they appear in both
    assert daily_names == weekly_names, (
        f"Parity mismatch: daily selected {daily_names}, weekly selected {weekly_names}"
    )
