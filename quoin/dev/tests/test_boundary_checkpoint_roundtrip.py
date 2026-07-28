"""T-10 (IVG-141): boundary_checkpoint.py writer roundtrip + picker selection.

Import-free of the quoin PACKAGE — subprocess-invokes the WRAPPER for writes, and
loads checkpoint_picker via the importlib spec_from_file_location loader (lesson
2026-06-17: test files reading core/scripts must use the importlib loader, NOT a
package import). NEVER `import quoin`.

Covers: full heading-set roundtrip, distinct `boundary-progress-` prefix (NOT
thorough-plan), empty/unknown-SID sentinel guard, own-line heading format
(MIN-2), the `--skill thorough_plan` rejection, always-exit-0 (fail-OPEN), and
the picker-SELECTION roundtrip (MIN-3: a non-empty seeded session makes
derived_task non-empty so the Tier-1 task-match gate is exercised non-trivially).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WRAPPER = REPO_ROOT / "quoin" / "scripts" / "boundary_checkpoint.py"
PICKER_CORE = REPO_ROOT / "quoin" / "core" / "scripts" / "checkpoint_picker.py"


def _load_picker():
    spec = importlib.util.spec_from_file_location("_test_checkpoint_picker", PICKER_CORE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_PICKER = _load_picker()


def _write(root: Path, **overrides):
    args = {
        "--project-root": str(root),
        "--task": "demo-task",
        "--skill": "run",
        "--sid": "SID123",
        "--branch": "main",
        "--resume-command": "/run --resume demo-task",
        "--phase-label": "before implement spawn",
    }
    args.update(overrides)
    argv = [sys.executable, str(WRAPPER)]
    for k, v in args.items():
        argv += [k, v]
    return subprocess.run(argv, capture_output=True, text=True)


def _mem_dir(root: Path) -> Path:
    return root / ".workflow_artifacts" / "memory"


def test_roundtrip_all_headings(tmp_path):
    r = _write(tmp_path, **{"--plan-path": "/x/current-plan.md"})
    assert r.returncode == 0
    ckpt = _mem_dir(tmp_path) / "checkpoints" / "boundary-progress-run-SID123.md"
    assert ckpt.exists()
    text = ckpt.read_text()
    for heading in ("## Active task", "## Session ID", "## Current stage",
                    "## Status", "## Resume command", "## Last user intent",
                    "## In-flight artifacts", "## Saved"):
        assert heading in text, f"missing {heading}"
    assert "demo-task" in text
    assert "phase-boundary checkpoint" in text
    assert "/run --resume demo-task" in text
    assert "/x/current-plan.md" in text


def test_own_line_heading_format(tmp_path):
    """MIN-2: each heading alone on its line; picker extracts non-empty values."""
    _write(tmp_path)
    ckpt = _mem_dir(tmp_path) / "checkpoints" / "boundary-progress-run-SID123.md"
    text = ckpt.read_text()
    # Own-line: no inline-colon heading form.
    assert "## Active task:" not in text
    assert "## Session ID:" not in text
    # picker's extractor returns non-empty for the load-bearing headings.
    assert _PICKER._extract_heading_value(text, "Active task") == "demo-task"
    assert _PICKER._extract_heading_value(text, "Session ID") == "SID123"
    assert _PICKER._extract_heading_value(text, "Status") == "phase-boundary checkpoint"


def test_distinct_prefix_not_thorough_plan(tmp_path):
    _write(tmp_path)
    ckpt = _mem_dir(tmp_path) / "checkpoints" / "boundary-progress-run-SID123.md"
    assert ckpt.name.startswith("boundary-progress-")
    assert not ckpt.name.startswith("thorough-plan-progress-")
    # picker classifies it as the generic checkpoint kind.
    assert _PICKER._classify_kind(ckpt) == "checkpoint"
    # /thorough_plan's §1b glob never matches it.
    matches = list((_mem_dir(tmp_path) / "checkpoints").glob("thorough-plan-progress-*.md"))
    assert matches == []


def test_empty_sid_no_sentinel(tmp_path):
    r = _write(tmp_path, **{"--sid": "", "--skill": "review"})
    assert r.returncode == 0
    ckpt = _mem_dir(tmp_path) / "checkpoints" / "boundary-progress-review-unknown.md"
    assert ckpt.exists()  # checkpoint still written
    sentinels = list(_mem_dir(tmp_path).glob("pending-restore-*.txt"))
    assert sentinels == [], "empty SID must not write a sentinel"


def test_unknown_sid_no_sentinel(tmp_path):
    r = _write(tmp_path, **{"--sid": "unknown", "--skill": "implement"})
    assert r.returncode == 0
    ckpt = _mem_dir(tmp_path) / "checkpoints" / "boundary-progress-implement-unknown.md"
    assert ckpt.exists()
    sentinels = list(_mem_dir(tmp_path).glob("pending-restore-*.txt"))
    assert sentinels == []


def test_sentinel_written_for_real_sid(tmp_path):
    _write(tmp_path, **{"--sid": "REALSID"})
    sentinel = _mem_dir(tmp_path) / "pending-restore-REALSID.txt"
    assert sentinel.exists()
    first_line = sentinel.read_text().splitlines()[0]
    assert first_line.endswith("boundary-progress-run-REALSID.md")


def test_skill_enum_rejects_thorough_plan(tmp_path):
    r = _write(tmp_path, **{"--skill": "thorough_plan"})
    # argparse rejects the choice; fail-OPEN → exit 0, no checkpoint written.
    assert r.returncode == 0
    matches = list((_mem_dir(tmp_path) / "checkpoints").glob("*.md")) \
        if (_mem_dir(tmp_path) / "checkpoints").exists() else []
    assert all("thorough_plan" not in m.name for m in matches)


def test_always_exit_zero(tmp_path):
    # Missing required arg → still exit 0 (fail-OPEN).
    r = subprocess.run([sys.executable, str(WRAPPER), "--task", "x"],
                       capture_output=True, text=True)
    assert r.returncode == 0


def test_picker_selection_roundtrip(tmp_path):
    """MIN-3: SEED a non-empty sessions/<date>-<task>.md whose task ==
    _filename_task(freshest_session.name), then assert select_restore STILL
    picks the boundary checkpoint via the Tier-1 sentinel fast path — proving
    ## Active task byte-equals the derived task under a realistic non-empty
    derived_task (not the trivial empty-session case)."""
    mem = _mem_dir(tmp_path)
    sessions = mem / "sessions"
    sessions.mkdir(parents=True)
    session_file = sessions / "2026-07-28-demo-task.md"
    session_file.write_text("## Status\nin_progress\n\n## Session ID\nSID123\n")

    # Sanity: the writer's --task must equal the derived task.
    derived = _PICKER._filename_task(session_file.name)
    assert derived == "demo-task"

    r = _write(tmp_path, **{"--sid": "SID123", "--task": "demo-task"})
    assert r.returncode == 0
    ckpt = mem / "checkpoints" / "boundary-progress-run-SID123.md"
    assert ckpt.exists()

    now = time.time()
    verdict = _PICKER.select_restore(str(mem), "SID123", now)
    assert verdict["selected_path"] == str(ckpt), verdict
    assert verdict["tier"] == 1
    assert verdict["kind"] == "checkpoint"


def test_picker_selection_task_mismatch_not_selected(tmp_path):
    """Adversarial: if ## Active task does NOT match the derived task, Tier-1
    short-circuits to B3 and the boundary checkpoint is NOT selected — proves
    the roundtrip above is load-bearing on the task value byte-equality."""
    mem = _mem_dir(tmp_path)
    sessions = mem / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-07-28-demo-task.md").write_text(
        "## Status\nin_progress\n\n## Session ID\nSID123\n"
    )
    r = _write(tmp_path, **{"--sid": "SID123", "--task": "OTHER-task"})
    assert r.returncode == 0
    verdict = _PICKER.select_restore(str(mem), "SID123", time.time())
    ckpt = str(mem / "checkpoints" / "boundary-progress-run-SID123.md")
    assert verdict["selected_path"] != ckpt
