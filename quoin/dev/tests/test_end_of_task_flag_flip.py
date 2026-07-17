"""Behavioral tests for flip_finalized_task_sessions() and the
--flip-finalized-task CLI mode (IVG-137 / T-03, Round 3 MIN-2 single-invocation
flip; script-level coverage only — SKILL.md wiring and the full digest-union
acceptance suite land with the T-03 SKILL.md batch).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_unprocessed_sessions import flip_finalized_task_sessions  # noqa: E402


TODAY = date(2026, 7, 16)


def _write_session(sessions_dir: Path, filename: str, flag: str = "yes") -> Path:
    p = sessions_dir / filename
    p.write_text(
        f"# Session\n\n## Status\n\nin_progress\n\n## Cost\n\n- end_of_day_due: {flag}\n",
        encoding="utf-8",
    )
    return p


def _make_project(tmp_path: Path) -> Tuple[Path, Path]:
    sessions = tmp_path / ".workflow_artifacts" / "memory" / "sessions"
    sessions.mkdir(parents=True)
    return tmp_path, sessions


def test_flips_exact_slug_match(tmp_path):
    root, sessions = _make_project(tmp_path)
    p = _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")

    flipped = flip_finalized_task_sessions(root, "my-task", "2026-07-16")

    assert p in flipped
    content = p.read_text(encoding="utf-8")
    assert "end_of_day_due: no" in content
    assert "finalized_by_end_of_task: 2026-07-16" in content


def test_flips_orchestrator_sibling(tmp_path):
    root, sessions = _make_project(tmp_path)
    base = _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")
    orch = _write_session(sessions, f"{TODAY}-my-task-orchestrator.md", flag="yes")

    flipped = flip_finalized_task_sessions(root, "my-task", "2026-07-16")

    assert set(flipped) == {base, orch}
    for p in (base, orch):
        content = p.read_text(encoding="utf-8")
        assert "end_of_day_due: no" in content
        assert "finalized_by_end_of_task: 2026-07-16" in content


def test_other_task_untouched(tmp_path):
    root, sessions = _make_project(tmp_path)
    _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")
    other = _write_session(sessions, f"{TODAY}-other-task.md", flag="yes")

    flip_finalized_task_sessions(root, "my-task", "2026-07-16")

    content = other.read_text(encoding="utf-8")
    assert "end_of_day_due: yes" in content
    assert "finalized_by_end_of_task" not in content


def test_other_task_ending_in_orchestrator_untouched(tmp_path):
    """A DIFFERENT task whose slug happens to end in '-orchestrator' must not
    be touched by an unrelated task's flip — proves the exact-match design
    needs no MIN-3-style sibling guard here (Round 3 / MIN-3)."""
    root, sessions = _make_project(tmp_path)
    _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")
    unrelated = _write_session(sessions, f"{TODAY}-something-else-orchestrator.md", flag="yes")

    flip_finalized_task_sessions(root, "my-task", "2026-07-16")

    content = unrelated.read_text(encoding="utf-8")
    assert "end_of_day_due: yes" in content
    assert "finalized_by_end_of_task" not in content


def test_idempotent_rerun(tmp_path):
    root, sessions = _make_project(tmp_path)
    p = _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")

    flip_finalized_task_sessions(root, "my-task", "2026-07-16")
    first = p.read_text(encoding="utf-8")
    flip_finalized_task_sessions(root, "my-task", "2026-07-16")
    second = p.read_text(encoding="utf-8")

    assert first == second
    assert second.count("finalized_by_end_of_task") == 1
    assert second.count("end_of_day_due:") == 1


def test_multi_date_sessions_all_flipped_single_invocation(tmp_path):
    root, sessions = _make_project(tmp_path)
    p1 = _write_session(sessions, "2026-07-10-my-task.md", flag="yes")
    p2 = _write_session(sessions, "2026-07-14-my-task.md", flag="yes")

    flipped = flip_finalized_task_sessions(root, "my-task", "2026-07-16")

    assert set(flipped) == {p1, p2}


def test_cli_flip_finalized_task_single_invocation(tmp_path, capsys):
    import select_unprocessed_sessions as module

    root, sessions = _make_project(tmp_path)
    p = _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")

    rc = module.main([
        "--project-root", str(root),
        "--flip-finalized-task", "my-task",
        "--finalization-date", "2026-07-16",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert str(p) in out
    assert "end_of_day_due: no" in p.read_text(encoding="utf-8")


def test_cli_requires_finalization_date(tmp_path, capsys):
    import select_unprocessed_sessions as module

    root, sessions = _make_project(tmp_path)
    _write_session(sessions, f"{TODAY}-my-task.md", flag="yes")

    rc = module.main([
        "--project-root", str(root),
        "--flip-finalized-task", "my-task",
    ])
    assert rc == 1
