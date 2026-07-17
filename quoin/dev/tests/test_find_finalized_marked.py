"""Behavioral tests for find_finalized_marked() and the --include-finalized-marked
CLI wiring (IVG-137 / T-01(c), Round 3 MAJ-2 producer).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_unprocessed_sessions import find_finalized_marked  # noqa: E402


TODAY = date(2026, 7, 16)


def _write_session(
    sessions_dir: Path,
    filename: str,
    flag: str = "no",
    marker_date: str | None = None,
) -> Path:
    p = sessions_dir / filename
    body = f"# Session\n\n## Status\n\ncompleted\n\n## Cost\n\n- end_of_day_due: {flag}\n"
    if marker_date is not None:
        body += f"- finalized_by_end_of_task: {marker_date}\n"
    p.write_text(body, encoding="utf-8")
    return p


def _write_daily(daily_dir: Path, date_str: str, body: str = "") -> Path:
    p = daily_dir / f"{date_str}.md"
    p.write_text(f"# Daily Cache — {date_str}\n\n## Summary\n\n{body}\n", encoding="utf-8")
    return p


def _make_project(tmp_path: Path) -> Tuple[Path, Path, Path]:
    sessions = tmp_path / ".workflow_artifacts" / "memory" / "sessions"
    sessions.mkdir(parents=True)
    daily = tmp_path / ".workflow_artifacts" / "memory" / "daily"
    daily.mkdir(parents=True)
    return tmp_path, sessions, daily


def test_marker_in_window_returned(tmp_path):
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    lower_bound = today - timedelta(days=3)
    p = _write_session(sessions, f"{today}-finalized-task.md", flag="no", marker_date=str(today))

    result = find_finalized_marked(root, lower_bound, today)
    assert p in result


def test_marker_outside_window_excluded(tmp_path):
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    lower_bound = today - timedelta(days=3)
    outside = lower_bound - timedelta(days=1)
    _write_session(sessions, f"{outside}-finalized-task.md", flag="no", marker_date=str(outside))

    result = find_finalized_marked(root, lower_bound, today)
    assert result == []


def test_no_marker_excluded_regardless_of_flag(tmp_path):
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    lower_bound = today - timedelta(days=3)
    _write_session(sessions, f"{today}-unmarked-yes.md", flag="yes", marker_date=None)
    _write_session(sessions, f"{today}-unmarked-no.md", flag="no", marker_date=None)

    result = find_finalized_marked(root, lower_bound, today)
    assert result == []


def test_marker_returned_regardless_of_flag_value(tmp_path):
    """find_finalized_marked() must NOT filter on end_of_day_due at all — a
    marked session is flag=no by construction, but the function should not
    assume it (defensive: even a flag=yes marked file is returned)."""
    root, sessions, _ = _make_project(tmp_path)
    today = TODAY
    lower_bound = today - timedelta(days=3)
    p = _write_session(sessions, f"{today}-still-yes-but-marked.md", flag="yes", marker_date=str(today))

    result = find_finalized_marked(root, lower_bound, today)
    assert p in result


# ---------------------------------------------------------------------------
# CLI: --show-window --include-finalized-marked
# ---------------------------------------------------------------------------


def test_show_window_include_finalized_marked_emits_finalized_lines(tmp_path, capsys):
    import select_unprocessed_sessions as module

    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today - timedelta(days=1)))
    plain_session = sessions / f"{today}-plain-task.md"
    plain_session.write_text(
        "# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: yes\n",
        encoding="utf-8",
    )
    finalized_session = _write_session(
        sessions, f"{today}-finalized-task.md", flag="no", marker_date=str(today)
    )

    rc = module.main([
        "--window", f"{today}..{today}",
        "--lower-bound-source", "daily",
        "--project-root", str(root),
        "--show-window",
        "--include-finalized-marked",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    lines = out.splitlines()

    assert lines[0].startswith("WINDOW: ")
    window_idx = 0
    finalized_lines = [i for i, line in enumerate(lines) if line.startswith("FINALIZED: ")]
    assert finalized_lines, "expected at least one FINALIZED: line"
    plain_lines = [i for i, line in enumerate(lines) if line == str(plain_session)]
    assert plain_lines, "expected the plain script_file_list entry"

    # Ordering: WINDOW: line, then plain file list, then FINALIZED: lines.
    assert window_idx < plain_lines[0] < finalized_lines[0]
    assert any(str(finalized_session) in line for line in lines if line.startswith("FINALIZED: "))
    # The finalized session (flag=no) must NOT appear in the plain file list.
    assert str(finalized_session) not in [lines[i] for i in plain_lines]


def test_include_finalized_marked_without_show_window_is_noop(tmp_path, capsys):
    import select_unprocessed_sessions as module

    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    plain_session = sessions / f"{today}-plain-task.md"
    plain_session.write_text(
        "# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: yes\n",
        encoding="utf-8",
    )
    _write_session(sessions, f"{today}-finalized-task.md", flag="no", marker_date=str(today))

    rc_without = module.main([
        "--window", f"{today}..{today}",
        "--lower-bound-source", "daily",
        "--project-root", str(root),
    ])
    out_without = capsys.readouterr().out

    rc_with_flag_only = module.main([
        "--window", f"{today}..{today}",
        "--lower-bound-source", "daily",
        "--project-root", str(root),
        "--include-finalized-marked",
    ])
    out_with_flag_only = capsys.readouterr().out

    assert rc_without == 0
    assert rc_with_flag_only == 0
    assert out_without == out_with_flag_only, (
        "--include-finalized-marked without --show-window must be a no-op — "
        "output must be identical to the flag-less invocation"
    )
    assert "FINALIZED:" not in out_with_flag_only


def test_single_subprocess_invocation_semantics(tmp_path, capsys):
    """Both WINDOW:, plain file list, and FINALIZED: lines must come from ONE
    module.main() call (not a second script invocation) — assert by calling
    main() exactly once and checking all three pieces are present in that
    single call's stdout."""
    import select_unprocessed_sessions as module

    root, sessions, daily = _make_project(tmp_path)
    today = TODAY
    _write_daily(daily, str(today - timedelta(days=1)))
    plain_session = sessions / f"{today}-plain-task.md"
    plain_session.write_text(
        "# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: yes\n",
        encoding="utf-8",
    )
    _write_session(sessions, f"{today}-finalized-task.md", flag="no", marker_date=str(today))

    rc = module.main([
        "--window", f"{today}..{today}",
        "--lower-bound-source", "daily",
        "--project-root", str(root),
        "--show-window",
        "--include-finalized-marked",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "WINDOW:" in out
    assert str(plain_session) in out
    assert "FINALIZED:" in out
