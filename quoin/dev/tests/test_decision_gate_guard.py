"""S-1 helper + safety unit tests for the fail-closed decision-gate guard (IVG-150, T-07).

Covers AC-1/AC-2/AC-3: the helper writes `needs-decision-{task}.md` under
`.workflow_artifacts/memory/`, emits a parseable NEEDS-DECISION block, exits 3, uses a
filename DISTINCT from `autonomous-halt-{task}.md`, survives the /end_of_task archive move,
and is IGNORED by the live supervisor's read_halt().
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

# ─── Path resolution (sibling-test convention: TESTS_DIR.parent.parent = quoin/quoin) ──
TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
CORE_PATH = PKG_DIR / "core" / "scripts" / "decision_gate_guard.py"
WRAPPER_PATH = PKG_DIR / "scripts" / "decision_gate_guard.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load(CORE_PATH, "_test_dgg_core")
wrapper = _load(WRAPPER_PATH, "_test_dgg_wrapper")


def _run(mod, tmp_path, task="demo-task", skill="end_of_task", site="commit-decision"):
    """Run the helper's main() and return (exit_code, memory_dir)."""
    argv = [
        "fail-closed",
        "--task", task,
        "--skill", skill,
        "--site", site,
        "--reason", "commit decision could not be surfaced",
        "--resume-hint", "re-run /end_of_task interactively",
        "--project-root", str(tmp_path),
    ]
    code = mod.main(argv)
    memory_dir = tmp_path / ".workflow_artifacts" / "memory"
    return code, memory_dir


def test_fail_closed_writes_sentinel_under_memory(tmp_path):
    code, memory_dir = _run(core, tmp_path)
    assert code == 3
    sentinel = memory_dir / "needs-decision-demo-task.md"
    assert sentinel.is_file()
    # It lives under .workflow_artifacts/memory/ (not inside a task folder).
    assert sentinel.parent.name == "memory"
    assert sentinel.parent.parent.name == ".workflow_artifacts"


def test_fail_closed_emits_parseable_needs_decision_block(tmp_path, capsys):
    code, _ = _run(core, tmp_path)
    assert code == 3
    out = capsys.readouterr().out
    assert "gate-result: NEEDS-DECISION" in out
    for token in ("skill: end_of_task", "site: commit-decision", "task: demo-task",
                  "sentinel:", "resume_hint:"):
        assert token in out
    # Re-parseable: the sentinel line points at the needs-decision file.
    assert "needs-decision-demo-task.md" in out


def test_sentinel_atomic_and_schema(tmp_path):
    _run(core, tmp_path)
    memory_dir = tmp_path / ".workflow_artifacts" / "memory"
    sentinel = memory_dir / "needs-decision-demo-task.md"
    lines = sentinel.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 7
    field_names = [ln.split(":", 1)[0] for ln in lines]
    assert field_names == list(core.SENTINEL_FIELDS)
    assert "trigger: non-interactive-decision-gate" in lines
    # No leftover atomic-write temp file.
    assert not list(memory_dir.glob("*.tmp"))


def test_sentinel_survives_simulated_archive_move(tmp_path):
    # AC-2: sentinel under memory/ survives /end_of_task moving the task folder to finalized/.
    _run(core, tmp_path)
    memory_dir = tmp_path / ".workflow_artifacts" / "memory"
    sentinel = memory_dir / "needs-decision-demo-task.md"
    assert sentinel.is_file()
    # Simulate a task folder + archive move (the sentinel is OUTSIDE the task folder).
    task_folder = tmp_path / ".workflow_artifacts" / "demo-task"
    task_folder.mkdir(parents=True)
    (task_folder / "current-plan.md").write_text("plan", encoding="utf-8")
    finalized = tmp_path / ".workflow_artifacts" / "finalized"
    finalized.mkdir(parents=True)
    shutil.move(str(task_folder), str(finalized / "demo-task"))
    assert sentinel.is_file()  # survived


def test_needs_decision_distinct_from_autonomous_halt(tmp_path):
    # AC-3: distinct filename from the halt family; shares memory/ location + schema shape.
    _run(core, tmp_path)
    memory_dir = tmp_path / ".workflow_artifacts" / "memory"
    assert (memory_dir / "needs-decision-demo-task.md").is_file()
    assert not (memory_dir / "autonomous-halt-demo-task.md").exists()
    assert core.SENTINEL_TEMPLATE == "needs-decision-{task}.md"
    assert core.SENTINEL_TEMPLATE != core.HALT_TEMPLATE


def test_supervisor_ignores_needs_decision(tmp_path):
    # AC-3 / R-03: the live supervisor never HALTs on a needs-decision sentinel.
    supervisor = pytest.importorskip("quoin.supervisor")
    _run(core, tmp_path)
    # A needs-decision sentinel exists, but no autonomous-halt sentinel does.
    assert supervisor.read_halt("demo-task", tmp_path) is None


def test_wrapper_importlib_load_exposes_main():
    assert hasattr(wrapper, "main") and callable(wrapper.main)
    for fn in ("cmd_fail_closed", "render_sentinel", "sentinel_path", "SENTINEL_FIELDS"):
        assert hasattr(wrapper, fn)


def test_wrapper_behaves_identically_to_core(tmp_path):
    code, memory_dir = _run(wrapper, tmp_path, task="demo2")
    assert code == 3
    assert (memory_dir / "needs-decision-demo2.md").is_file()
