"""Behavioral tests for find_covered_due_sessions() and the guarded _base_slug()
helper (IVG-137 / T-01).

Covers proc:T-01(a): covered-but-due reconciliation (the INVERSE of
find_orphans — flag=YES sessions already captured in a daily body) and the
orchestrator-suffix-safe base-slug derivation shared with find_orphans().
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

# Add the core/scripts directory so we can import the helper directly.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_unprocessed_sessions import (  # noqa: E402
    _base_slug,
    find_covered_due_sessions,
)


TODAY = date(2026, 7, 16)


def _write_session(sessions_dir: Path, filename: str, flag: str = "yes") -> Path:
    """Write a minimal session file."""
    p = sessions_dir / filename
    p.write_text(
        f"# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: {flag}\n",
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
# _base_slug() unit tests
# ---------------------------------------------------------------------------


def test_base_slug_strips_when_sibling_exists():
    siblings = {"foo", "foo-orchestrator"}
    assert _base_slug("foo-orchestrator", siblings) == "foo"


def test_base_slug_no_strip_without_sibling():
    """(Round 3 / MIN-3) A task literally named '<x>-orchestrator' with no bare
    '<x>' sibling must NOT be stripped."""
    siblings = {"foo-orchestrator"}
    assert _base_slug("foo-orchestrator", siblings) == "foo-orchestrator"


def test_base_slug_no_strip_when_stripped_result_empty():
    siblings = {"orchestrator", ""}
    assert _base_slug("-orchestrator", siblings) == "-orchestrator"


def test_base_slug_non_orchestrator_slug_unchanged():
    siblings = {"foo-review", "foo"}
    assert _base_slug("foo-review", siblings) == "foo-review"


# ---------------------------------------------------------------------------
# find_covered_due_sessions() — core partition behavior
# ---------------------------------------------------------------------------


def test_covered_vs_uncovered_partition(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed task-alpha review session.")

    _write_session(sessions, f"{today}-task-alpha.md", flag="yes")  # covered
    _write_session(sessions, f"{today}-task-beta.md", flag="yes")  # uncovered

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {p.name for p in covered}
    uncovered_names = {p.name for p in uncovered}

    assert f"{today}-task-alpha.md" in covered_names
    assert f"{today}-task-beta.md" in uncovered_names
    assert f"{today}-task-beta.md" not in covered_names
    assert f"{today}-task-alpha.md" not in uncovered_names


def test_word_boundary_no_prefix_collision(tmp_path):
    """slug 'foo-bar' must NOT be considered covered by 'foo-bar-baz' in the daily body."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed foo-bar-baz work today.")
    _write_session(sessions, f"{today}-foo-bar.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {p.name for p in covered}
    uncovered_names = {p.name for p in uncovered}

    assert f"{today}-foo-bar.md" in uncovered_names
    assert f"{today}-foo-bar.md" not in covered_names


def test_missing_flag_treated_as_yes(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed legacy-task today.")
    p = sessions / f"{today}-legacy-task.md"
    p.write_text("# Session\n\n## Status\n\nin_progress\n", encoding="utf-8")

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {q.name for q in covered}
    assert p.name in covered_names, "missing end_of_day_due must be treated as yes (D-02)"


def test_body_tmp_files_excluded(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed real-task today.")
    _write_session(sessions, f"{today}-real-task.md", flag="yes")
    # Crashed writer leftover — must be excluded by the .md$ file_pattern.
    (sessions / f"{today}-real-task.md.body.tmp").write_text("garbage", encoding="utf-8")
    (sessions / f"{today}-real-task.md.tmp").write_text("garbage", encoding="utf-8")

    covered, uncovered = find_covered_due_sessions(root, today)
    all_names = {p.name for p in covered} | {p.name for p in uncovered}
    assert f"{today}-real-task.md.body.tmp" not in all_names
    assert f"{today}-real-task.md.tmp" not in all_names


def test_empty_daily_dir_all_uncovered(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_session(sessions, f"{today}-task-a.md", flag="yes")
    _write_session(sessions, f"{today}-task-b.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    assert covered == []
    uncovered_names = {p.name for p in uncovered}
    assert f"{today}-task-a.md" in uncovered_names
    assert f"{today}-task-b.md" in uncovered_names


def test_future_dated_session_skipped(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    future = today + timedelta(days=1)
    _write_daily(daily, str(today), body="Completed future-task today.")
    _write_session(sessions, f"{future}-future-task.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    all_names = {p.name for p in covered} | {p.name for p in uncovered}
    assert f"{future}-future-task.md" not in all_names, "future-dated session must be skipped entirely"


def test_flag_no_sessions_excluded_from_both_lists(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed task-x today.")
    _write_session(sessions, f"{today}-task-x.md", flag="no")

    covered, uncovered = find_covered_due_sessions(root, today)
    all_names = {p.name for p in covered} | {p.name for p in uncovered}
    assert f"{today}-task-x.md" not in all_names, (
        "flag=no is not a candidate for coverage reconciliation — it belongs to find_orphans()"
    )


# ---------------------------------------------------------------------------
# Orchestrator-suffix handling (Round 2, Round 3)
# ---------------------------------------------------------------------------


def test_orchestrator_suffixed_slug_covered_when_base_covered(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed ivg-137-eod-orphan-reconciliation work.")
    _write_session(sessions, f"{today}-ivg-137-eod-orphan-reconciliation.md", flag="yes")
    _write_session(sessions, f"{today}-ivg-137-eod-orphan-reconciliation-orchestrator.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {p.name for p in covered}
    assert f"{today}-ivg-137-eod-orphan-reconciliation.md" in covered_names
    assert f"{today}-ivg-137-eod-orphan-reconciliation-orchestrator.md" in covered_names


def test_orchestrator_suffixed_slug_uncovered_when_base_uncovered(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed something-unrelated today.")
    _write_session(sessions, f"{today}-ivg-137-eod-orphan-reconciliation.md", flag="yes")
    _write_session(sessions, f"{today}-ivg-137-eod-orphan-reconciliation-orchestrator.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    uncovered_names = {p.name for p in uncovered}
    assert f"{today}-ivg-137-eod-orphan-reconciliation.md" in uncovered_names
    assert f"{today}-ivg-137-eod-orphan-reconciliation-orchestrator.md" in uncovered_names


def test_genuine_orchestrator_named_task_not_stripped(tmp_path):
    """(Round 3 / MIN-3) A task literally named '<x>-orchestrator' with NO bare
    '<x>.md' sibling must be evaluated on its own raw slug, not stripped."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    # Daily body mentions the raw slug verbatim (including '-orchestrator').
    _write_daily(daily, str(today), body="Completed foo-orchestrator work today.")
    _write_session(sessions, f"{today}-foo-orchestrator.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {p.name for p in covered}
    assert f"{today}-foo-orchestrator.md" in covered_names, (
        "raw slug 'foo-orchestrator' appears verbatim in the daily body and has no "
        "bare 'foo.md' sibling, so it must be matched on its own raw slug"
    )


def test_genuine_orchestrator_named_task_uncovered_when_daily_lacks_it(tmp_path):
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    # Daily body mentions only the stripped form 'foo' — must NOT count, since
    # there is no 'foo.md' sibling to justify stripping.
    _write_daily(daily, str(today), body="Completed foo work today.")
    _write_session(sessions, f"{today}-foo-orchestrator.md", flag="yes")

    covered, uncovered = find_covered_due_sessions(root, today)
    uncovered_names = {p.name for p in uncovered}
    assert f"{today}-foo-orchestrator.md" in uncovered_names, (
        "no 'foo.md' sibling exists, so 'foo-orchestrator' must not be stripped to "
        "'foo' — the daily body mentioning 'foo' must not create false coverage"
    )


# ---------------------------------------------------------------------------
# Round 4 / MAJ-1 — freeze the phase/stage-suffix scope boundary
# ---------------------------------------------------------------------------


def test_phase_suffixed_slug_stays_uncovered_even_when_root_covered(tmp_path):
    """(Round 4 / MAJ-1 scope boundary) A phase/stage-suffixed slug (e.g.
    'foo-review') whose ROOT task IS covered in a daily body must STILL be
    classified uncovered — _base_slug() only strips '-orchestrator', not the
    broader phase/stage-suffix vocabulary. This is documented, intended
    behavior for this round, not a bug; the test guards against an
    accidental future widening of _base_slug()."""
    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed foo work today.")
    _write_session(sessions, f"{today}-foo.md", flag="yes")  # covered
    _write_session(sessions, f"{today}-foo-review.md", flag="yes")  # NOT covered
    _write_session(sessions, f"{today}-foo-s3-implement.md", flag="yes")  # NOT covered

    covered, uncovered = find_covered_due_sessions(root, today)
    covered_names = {p.name for p in covered}
    uncovered_names = {p.name for p in uncovered}

    assert f"{today}-foo.md" in covered_names
    assert f"{today}-foo-review.md" in uncovered_names
    assert f"{today}-foo-review.md" not in covered_names
    assert f"{today}-foo-s3-implement.md" in uncovered_names
    assert f"{today}-foo-s3-implement.md" not in covered_names


# ---------------------------------------------------------------------------
# CLI: --reconcile-covered
# ---------------------------------------------------------------------------


def test_reconcile_covered_cli_exits_0_and_emits_two_lists(tmp_path, capsys):
    import select_unprocessed_sessions as module

    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today), body="Completed task-covered today.")
    _write_session(sessions, f"{today}-task-covered.md", flag="yes")
    _write_session(sessions, f"{today}-task-uncovered.md", flag="yes")

    rc = module.main([
        "--window", f"{today}..{today}",
        "--project-root", str(root),
        "--reconcile-covered",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert "COVERED:" in lines
    assert "UNCOVERED:" in lines
    covered_idx = lines.index("COVERED:")
    uncovered_idx = lines.index("UNCOVERED:")
    assert covered_idx < uncovered_idx
    assert any(f"{today}-task-covered.md" in line for line in lines[covered_idx:uncovered_idx])
    assert any(f"{today}-task-uncovered.md" in line for line in lines[uncovered_idx:])


def test_reconcile_covered_cli_does_not_require_lower_bound_source(tmp_path, capsys):
    """--reconcile-covered must work without --lower-bound-source."""
    import select_unprocessed_sessions as module

    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_session(sessions, f"{today}-task-a.md", flag="yes")

    rc = module.main([
        "--window", f"{today}..{today}",
        "--project-root", str(root),
        "--reconcile-covered",
    ])
    assert rc == 0
