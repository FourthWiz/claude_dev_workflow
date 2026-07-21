"""Unit tests for IVG-153 Stage 2 T-06: quoin.supervisor's relaunch loop.

All tests use a mocked `launch_fn` and a fake `clock` — no real
subprocess is ever spawned. Tests drive the loop purely through sentinel
files written directly to a tmp_path project root.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quoin import supervisor as sup


class _FakeClock:
    def __init__(self) -> None:
        self.sleeps: list = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def test_path_helpers_resolve_under_memory_root(tmp_path: Path) -> None:
    task = "demo-task"
    assert sup.marker_path(task, tmp_path) == (
        tmp_path / ".workflow_artifacts" / "memory" / "autonomous-run-demo-task.marker"
    )
    assert sup.progress_dir(task, tmp_path) == (
        tmp_path / ".workflow_artifacts" / "memory" / "autonomous-progress-demo-task"
    )
    assert sup.done_path(task, tmp_path) == (
        tmp_path / ".workflow_artifacts" / "memory" / "autonomous-done-demo-task.md"
    )
    assert sup.halt_path(task, tmp_path) == (
        tmp_path / ".workflow_artifacts" / "memory" / "autonomous-halt-demo-task.md"
    )


# ---------------------------------------------------------------------------
# read_done / read_halt / count_completion_sentinels
# ---------------------------------------------------------------------------


def test_read_done_false_when_absent(tmp_path: Path) -> None:
    assert sup.read_done("t", tmp_path) is False


def test_read_done_true_when_present(tmp_path: Path) -> None:
    _write(sup.done_path("t", tmp_path), "done\n")
    assert sup.read_done("t", tmp_path) is True


def test_read_halt_none_when_absent(tmp_path: Path) -> None:
    assert sup.read_halt("t", tmp_path) is None


def test_read_halt_extracts_reason_field(tmp_path: Path) -> None:
    _write(
        sup.halt_path("t", tmp_path),
        "task: t\nphase: review\nreason: blocked by security findings\n"
        "timestamp: 2026-07-21T00:00:00Z\nresume_hint: fix findings\n",
    )
    assert sup.read_halt("t", tmp_path) == "blocked by security findings"


def test_read_halt_falls_back_to_raw_text_without_reason_line(tmp_path: Path) -> None:
    _write(sup.halt_path("t", tmp_path), "some unstructured halt note\n")
    assert sup.read_halt("t", tmp_path) == "some unstructured halt note"


def test_count_completion_sentinels_zero_when_dir_absent(tmp_path: Path) -> None:
    assert sup.count_completion_sentinels("t", tmp_path) == 0


def test_count_completion_sentinels_counts_union_of_phase_and_subphase(
    tmp_path: Path,
) -> None:
    d = sup.progress_dir("t", tmp_path)
    _write(d / "discover.done")
    _write(d / "implement.partial-batch-1.done")
    _write(d / "implement.partial-batch-2.done")
    _write(d / "not-a-sentinel.txt")
    assert sup.count_completion_sentinels("t", tmp_path) == 3


# ---------------------------------------------------------------------------
# default_backoff
# ---------------------------------------------------------------------------


def test_default_backoff_is_nondecreasing_and_capped() -> None:
    values = [sup.default_backoff(n) for n in range(1, 12)]
    assert values == sorted(values)
    assert values[-1] <= 300.0
    assert values[0] == 5.0


# ---------------------------------------------------------------------------
# supervise() — terminal conditions
# ---------------------------------------------------------------------------


def test_supervise_done_sentinel_present_returns_success_zero_launches(
    tmp_path: Path,
) -> None:
    _write(sup.done_path("t", tmp_path), "done\n")
    calls: list = []
    result = sup.supervise(
        "t", tmp_path, launch_fn=lambda task: calls.append(task), clock=_FakeClock()
    )
    assert result.status == "SUCCESS"
    assert result.relaunches == 0
    assert calls == []


def test_supervise_halt_sentinel_present_returns_halted_without_launch(
    tmp_path: Path,
) -> None:
    _write(sup.halt_path("t", tmp_path), "reason: git conflict\n")
    calls: list = []
    result = sup.supervise(
        "t", tmp_path, launch_fn=lambda task: calls.append(task), clock=_FakeClock()
    )
    assert result.status == "HALTED"
    assert result.reason == "git conflict"
    assert result.relaunches == 0
    assert calls == []


def test_supervise_done_checked_before_halt(tmp_path: Path) -> None:
    _write(sup.done_path("t", tmp_path), "done\n")
    _write(sup.halt_path("t", tmp_path), "reason: should not matter\n")
    result = sup.supervise(
        "t", tmp_path, launch_fn=lambda task: None, clock=_FakeClock()
    )
    assert result.status == "SUCCESS"


def test_supervise_relaunch_cap_aborts(tmp_path: Path) -> None:
    """Each launch makes SOME progress (never two consecutive zero-progress
    launches), isolating the relaunch-cap terminal condition from the
    no-forward-progress guard."""
    d = sup.progress_dir("t", tmp_path)
    launches: list = []

    def launch_fn(task: str) -> None:
        launches.append(task)
        _write(d / f"implement.batch-{len(launches)}.done")

    clock = _FakeClock()
    result = sup.supervise(
        "t",
        tmp_path,
        launch_fn=launch_fn,
        max_relaunch=3,
        clock=clock,
    )
    assert result.status == "ABORTED"
    assert result.reason == "relaunch cap"
    assert result.relaunches == 3
    assert len(launches) == 3


def test_supervise_two_consecutive_zero_progress_launches_aborts(
    tmp_path: Path,
) -> None:
    launches: list = []

    def launch_fn(task: str) -> None:
        # never writes a new sentinel
        launches.append(task)

    clock = _FakeClock()
    result = sup.supervise(
        "t",
        tmp_path,
        launch_fn=launch_fn,
        max_relaunch=10,
        clock=clock,
    )
    assert result.status == "ABORTED"
    assert result.reason == "no forward progress"
    # Two zero-progress launches trigger the abort.
    assert len(launches) == 2
    assert result.relaunches == 1  # incremented after the 1st, aborted before 2nd's increment


def test_supervise_new_phase_done_resets_streak(tmp_path: Path) -> None:
    d = sup.progress_dir("t", tmp_path)
    state = {"n": 0}

    def launch_fn(task: str) -> None:
        state["n"] += 1
        if state["n"] == 1:
            pass  # zero progress launch #1 -> streak=1
        elif state["n"] == 2:
            _write(d / "discover.done")  # new sentinel -> resets streak to 0
        elif state["n"] == 3:
            # zero-progress in the progress dir, but writes the done
            # sentinel (a different file) — streak becomes 1, not 2, so
            # the loop returns to the top and sees the done sentinel
            # before the guard would ever fire again.
            _write(sup.done_path("t", tmp_path), "done\n")

    clock = _FakeClock()
    result = sup.supervise(
        "t",
        tmp_path,
        launch_fn=launch_fn,
        max_relaunch=10,
        clock=clock,
    )
    assert result.status == "SUCCESS"
    assert state["n"] == 3
    assert result.relaunches == 3


def test_supervise_subphase_only_progress_resets_streak_maj2(tmp_path: Path) -> None:
    """A launch producing ONLY a new sub-phase `.done` (no phase-level
    `.done`) must ALSO reset the zero-progress streak (MAJ-2)."""
    d = sup.progress_dir("t", tmp_path)
    state = {"n": 0}

    def launch_fn(task: str) -> None:
        state["n"] += 1
        if state["n"] == 1:
            pass  # zero progress -> streak=1
        elif state["n"] == 2:
            _write(d / "implement.batch-1.done")  # sub-phase only, resets streak to 0
        elif state["n"] == 3:
            # Writes a SECOND new sub-phase sentinel (keeps resetting the
            # streak) together with the done sentinel, so the loop
            # returns to the top and sees SUCCESS rather than the guard
            # firing on this same launch.
            _write(d / "implement.batch-2.done")
            _write(sup.done_path("t", tmp_path), "done\n")

    clock = _FakeClock()
    result = sup.supervise(
        "t",
        tmp_path,
        launch_fn=launch_fn,
        max_relaunch=10,
        clock=clock,
    )
    # Must NOT have aborted for "no forward progress" — sub-phase progress
    # at launches #2 and #3 kept resetting the streak, so it never hit
    # the >=2 threshold before the done sentinel was observed.
    assert result.status == "SUCCESS"
    assert state["n"] == 3


def test_supervise_max_relaunch_still_caps_under_continual_subphase_progress(
    tmp_path: Path,
) -> None:
    """Even with unbroken sub-phase progress every launch, MAX_RELAUNCH
    independently guarantees termination (e2 in the plan's acceptance)."""
    d = sup.progress_dir("t", tmp_path)
    state = {"n": 0}

    def launch_fn(task: str) -> None:
        state["n"] += 1
        _write(d / f"implement.batch-{state['n']}.done")

    clock = _FakeClock()
    result = sup.supervise(
        "t",
        tmp_path,
        launch_fn=launch_fn,
        max_relaunch=5,
        clock=clock,
    )
    assert result.status == "ABORTED"
    assert result.reason == "relaunch cap"
    assert result.relaunches == 5
    assert state["n"] == 5


def test_supervise_calls_backoff_and_clock_with_increasing_values(
    tmp_path: Path,
) -> None:
    seen_relaunch_numbers: list = []

    def backoff_fn(n: int) -> float:
        seen_relaunch_numbers.append(n)
        return float(n)

    clock = _FakeClock()
    sup.supervise(
        "t",
        tmp_path,
        launch_fn=lambda task: None,
        max_relaunch=4,
        backoff_fn=backoff_fn,
        clock=clock,
    )
    assert seen_relaunch_numbers == sorted(seen_relaunch_numbers)
    assert clock.sleeps == seen_relaunch_numbers


def test_supervise_no_real_subprocess_module_import_is_clean() -> None:
    """supervisor.py must stay import-lean (no subprocess import at top,
    stdlib only) per the R-11/D-01 lazy-import convention."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sup))
    top_level_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module.split(".")[0])

    assert "subprocess" not in top_level_imports
