"""IVG-258 T-07: run_state.py writer/reader unit tests, including the
writer-to-POSIX-shell-reader round trip.

Shape mirrors test_boundary_checkpoint_roundtrip.py: subprocess the script
against tmp_path, assert on files and stdout. No LLM calls.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "quoin" / "core" / "scripts" / "run_state.py"
READER = REPO_ROOT / "quoin" / "dev" / "spikes" / "run_state_read.sh"

PY = sys.executable


def _run(args, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [PY, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        timeout=30,
        env=full_env,
    )


def _read_reader(memory_dir: Path, task: str, *keys, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        ["sh", str(READER), str(memory_dir), task, *keys],
        capture_output=True,
        text=True,
        timeout=30,
        env=full_env,
    )
    out = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    out["_stderr"] = result.stderr
    out["_returncode"] = result.returncode
    return out


def _record_path(root: Path, task: str) -> Path:
    return root / ".workflow_artifacts" / "memory" / f"run-state-{task}.json"


def _memory_dir(root: Path) -> Path:
    return root / ".workflow_artifacts" / "memory"


def _load(root: Path, task: str) -> dict:
    return json.loads(_record_path(root, task).read_text(encoding="utf-8"))


def _write(root, task, **kwargs):
    args = ["--write", "--project-root", str(root), "--task", task]
    for key, value in kwargs.items():
        flag = "--" + key.replace("_", "-")
        if key == "require_existing":
            if value:
                args += [flag]
            continue
        if isinstance(value, list):
            for v in value:
                args += [flag, v]
        elif isinstance(value, bool):
            args += [flag, "true" if value else "false"]
        else:
            args += [flag, str(value)]
    return _run(args)


def test_write_creates_record_one_key_per_line(tmp_path):
    _write(tmp_path, "t1", step="hello")
    text = _record_path(tmp_path, "t1").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip() not in ("{", "}")]
    key_lines = [ln for ln in lines if ln.strip().startswith('"')]
    assert len(key_lines) == 16
    assert len(lines) == len(key_lines)


def test_write_emits_exact_key_colon_space_spacing(tmp_path):
    _write(tmp_path, "t2", step="x")
    text = _record_path(tmp_path, "t2").read_text(encoding="utf-8")
    assert text.count('"active": true') == 1


def test_write_is_atomic_no_tmp_left(tmp_path):
    _write(tmp_path, "t3", step="x")
    leftovers = list(_memory_dir(tmp_path).glob("*.tmp"))
    assert leftovers == []


def test_write_atomicity_under_interrupt(tmp_path):
    memory_dir = _memory_dir(tmp_path)
    memory_dir.mkdir(parents=True, exist_ok=True)
    stray = memory_dir / "run-state-t4.json.deadbeef.tmp"
    stray.write_text("garbage-from-a-crashed-writer", encoding="utf-8")
    _write(tmp_path, "t4", step="final")
    record = _load(tmp_path, "t4")
    assert record["step"] == "final"
    assert len(record) == 16


def test_concurrent_writers_never_produce_a_partial_record(tmp_path):
    task = "t5"
    threads = []
    for i in range(8):
        t = threading.Thread(target=_write, args=(tmp_path, task), kwargs={"step": f"writer-{i}"})
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    path = _record_path(tmp_path, task)
    deadline = time.time() + 5
    seen = 0
    while time.time() < deadline and seen < 200:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        assert len(data) == 16
        assert set(data.keys()) == {
            "schema", "task", "session_id", "active", "phase", "phase_index",
            "subphase", "step", "at_stage_boundary", "route", "profile",
            "artifacts", "next_action", "resume_command", "notes_path", "updated_at",
        }
        seen += 1


def test_temp_file_name_is_writer_unique(tmp_path):
    memory_dir = _memory_dir(tmp_path)
    memory_dir.mkdir(parents=True, exist_ok=True)
    shared_tmp = memory_dir / "run-state-t6.json.tmp"
    shared_tmp.write_text("should never be touched by the writer", encoding="utf-8")
    before = {p.name for p in memory_dir.glob("*.tmp")}
    _write(tmp_path, "t6", step="x")
    after = {p.name for p in memory_dir.glob("*.tmp")}
    new_files = after - before
    import re
    for name in new_files:
        assert name != "run-state-t6.json.tmp", (
            "writer must never use the shared fixed .tmp sibling name"
        )
        assert re.match(r"run-state-.*\.json\..*\.tmp$", name)
    assert shared_tmp.exists()  # untouched garbage, left alone
    assert shared_tmp.read_text(encoding="utf-8") == "should never be touched by the writer"


def test_clear_sets_active_false(tmp_path):
    _write(tmp_path, "t7", step="x")
    _run(["--clear", "--project-root", str(tmp_path), "--task", "t7"])
    assert _load(tmp_path, "t7")["active"] is False


def test_clear_on_missing_record_is_noop_exit_zero(tmp_path):
    result = _run(["--clear", "--project-root", str(tmp_path), "--task", "ghost"])
    assert result.returncode == 0
    assert not _record_path(tmp_path, "ghost").exists()


def test_require_existing_write_on_missing_record_creates_nothing(tmp_path):
    result = _run([
        "--write", "--require-existing", "--project-root", str(tmp_path),
        "--task", "t8", "--step", "x",
    ])
    assert result.returncode == 0
    assert not _record_path(tmp_path, "t8").exists()


def test_require_existing_write_updates_an_existing_record(tmp_path):
    _write(tmp_path, "t9", step="first")
    _write(tmp_path, "t9", require_existing=True, step="second")
    assert _load(tmp_path, "t9")["step"] == "second"


def test_require_existing_write_does_not_reactivate_a_cleared_record(tmp_path):
    _write(tmp_path, "t10", step="first")
    _run(["--clear", "--project-root", str(tmp_path), "--task", "t10"])
    before = _load(tmp_path, "t10")
    before_mtime = _record_path(tmp_path, "t10").stat().st_mtime_ns
    _write(tmp_path, "t10", require_existing=True, step="second")
    after = _load(tmp_path, "t10")
    after_mtime = _record_path(tmp_path, "t10").stat().st_mtime_ns
    assert after["active"] is False
    assert after["step"] == before["step"] == "first"
    assert after["updated_at"] == before["updated_at"]
    assert after_mtime == before_mtime


def test_read_emits_key_equals_value_per_field_in_requested_order(tmp_path):
    _write(tmp_path, "t11", phase="implement", step="doing")
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t11",
        "--fields", "step,phase,schema",
    ])
    lines = result.stdout.strip().splitlines()
    assert lines == ["step=doing", "phase=implement", "schema=1"]


def test_read_unknown_field_on_existing_record_emits_empty_value(tmp_path):
    _write(tmp_path, "t12", step="x")
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t12",
        "--fields", "not_a_real_field",
    ])
    assert result.stdout.strip() == "not_a_real_field="


def test_read_on_missing_record_emits_nothing_exit_zero(tmp_path):
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "ghost2",
        "--fields", "task",
    ])
    assert result.returncode == 0
    assert result.stdout == ""


def test_read_sanitizes_a_record_it_did_not_itself_write(tmp_path):
    """`--write` always sanitizes before a record reaches disk, so this
    condition never arises through the shipped writer. It covers a record
    `_do_write` did not produce -- hand-edited, or written by some future
    caller that bypasses it -- carrying a raw embedded newline. `--read`'s
    own render loop must not let that newline forge an extra output line."""
    _write(tmp_path, "t12b", step="x")
    path = _record_path(tmp_path, "t12b")
    forged = '"line one\\nactive=true\\nnext_action=start end_of_task"'
    path.write_text(
        path.read_text(encoding="utf-8").replace('"x"', forged),
        encoding="utf-8",
    )
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t12b",
        "--fields", "step",
    ])
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("step=line one active=true next_action=start end_of_task")


def test_schema_forward_record_reads_as_absent(tmp_path):
    _write(tmp_path, "t13", step="x")
    path = _record_path(tmp_path, "t13")
    path.write_text(path.read_text(encoding="utf-8").replace('"schema": 1', '"schema": 2'), encoding="utf-8")
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t13", "--fields", "task",
    ])
    assert result.returncode == 0
    assert result.stdout == ""


def test_schema_lower_reads_recognised_fields(tmp_path):
    _write(tmp_path, "t14", step="x")
    path = _record_path(tmp_path, "t14")
    path.write_text(path.read_text(encoding="utf-8").replace('"schema": 1', '"schema": 0'), encoding="utf-8")
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t14", "--fields", "task,step",
    ])
    assert result.stdout.strip().splitlines() == ["task=t14", "step=x"]


def test_read_max_age_days_hides_a_stale_record(tmp_path):
    _write(tmp_path, "t15", step="x")
    path = _record_path(tmp_path, "t15")
    old = time.time() - (3 * 86400)
    os.utime(path, (old, old))
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t15",
        "--max-age-days", "1", "--fields", "task",
    ])
    assert result.stdout == ""


def test_read_max_age_days_zero_disables_the_check(tmp_path):
    _write(tmp_path, "t16", step="x")
    path = _record_path(tmp_path, "t16")
    old = time.time() - (30 * 86400)
    os.utime(path, (old, old))
    result = _run([
        "--read", "--project-root", str(tmp_path), "--task", "t16",
        "--max-age-days", "0", "--fields", "task",
    ])
    assert result.stdout.strip() == "task=t16"


def test_step_and_next_action_are_sanitized(tmp_path):
    adversarial = "a \"b\" c\\d\r\n\tVT\x0bFF\x0cESC\x1bDEL\x7fé✓"
    _write(tmp_path, "t17", step=adversarial, next_action=adversarial)
    record = _load(tmp_path, "t17")
    for field in ("step", "next_action"):
        val = record[field]
        assert '"' not in val
        assert "\\" not in val
        assert "\r" not in val and "\n" not in val and "\t" not in val
        assert "\x1b" not in val and "\x7f" not in val
        assert "é" in val and "✓" in val


def test_record_contains_no_backslash_byte(tmp_path):
    adversarial = "back\\slash and é✓ non-ascii"
    _write(tmp_path, "t18", step=adversarial, next_action=adversarial, resume_command=adversarial)
    raw = _record_path(tmp_path, "t18").read_bytes()
    assert b"\\" not in raw


def test_writer_output_is_readable_by_the_posix_shell_reader(tmp_path):
    task = "t19"
    step_val = 'emb"ed\\ded:col,on\nnewline\x1bESC\x7fDELéhéllo — ünïcode ✓ trailing comma,'
    next_action_val = ","
    resume_val = "/run --resume t19 has=equals"
    artifact_val = "a" * 300

    _write(
        tmp_path, task,
        step=step_val,
        next_action=next_action_val,
        resume_command=resume_val,
        artifact=[artifact_val],
    )
    record = _load(tmp_path, task)
    memory_dir = _memory_dir(tmp_path)
    got = _read_reader(memory_dir, task, "step", "next_action", "resume_command")
    assert got["step"] == record["step"]
    assert got["next_action"] == record["next_action"]
    assert got["resume_command"] == record["resume_command"]


CLASSES = [
    '"', "'", "\\", ",", ":", "=", "\n", "\t", "\r", "\x1b", "\x7f",
    "é", "{", "}", "foo=bar", "",
]
POSITIONS = ["leading", "embedded", "trailing"]


def _build_cell(cls_value: str, position: str) -> str:
    if position == "leading":
        return cls_value + "TAIL"
    if position == "trailing":
        return "HEAD" + cls_value
    return "HEAD" + cls_value + "TAIL"


def _matrix_cells():
    assert len(CLASSES) == 16 and len(POSITIONS) == 3
    cells = []
    for cls in CLASSES:
        for pos in POSITIONS:
            cells.append((f"{cls!r}@{pos}", _build_cell(cls, pos)))
    cells.append(("whole-value-comma", ","))
    cells.append(("whole-value-quote", '"'))
    return cells


@pytest.mark.parametrize("label,value", _matrix_cells())
def test_extractor_is_total_over_character_class_matrix(tmp_path, label, value):
    task = "matrix"
    _write(tmp_path, task, step=value)
    record = _load(tmp_path, task)
    got = _read_reader(_memory_dir(tmp_path), task, "step")
    assert got.get("step") == record["step"], f"cell {label!r} failed to round-trip"


def test_fail_open_unwritable_project_root_exits_zero_no_stdout(tmp_path):
    unwritable = tmp_path / "ro"
    unwritable.mkdir()
    unwritable.chmod(0o500)
    try:
        result = _run(["--write", "--project-root", str(unwritable / "nested"), "--task", "x", "--step", "y"])
        assert result.returncode == 0
        assert result.stdout == ""
    finally:
        unwritable.chmod(0o700)


def test_fail_open_bad_argument_exits_zero(tmp_path):
    result = _run(["--not-a-real-flag"])
    assert result.returncode == 0


def test_resume_command_never_carries_autonomous_flag(tmp_path):
    _write(tmp_path, "t20", resume_command="/run --resume --autonomous t20")
    record = _load(tmp_path, "t20")
    assert "--autonomous" not in record["resume_command"]


def test_resume_command_c0_byte_does_not_reconstitute_autonomous_flag(tmp_path):
    """A C0 control byte immediately adjacent to `--autonomous` defeats the
    strip regex's `\\S`-based word-boundary lookaround (a C0 byte is not
    whitespace), so the raw token survives `_strip_autonomous` unstripped.
    Sanitizing must run BEFORE the strip, not after, or the later sanitize
    pass (which turns the C0 byte into a space) re-forms a clean,
    whitespace-bounded `--autonomous` token in the stored record."""
    hostile = "/run --resume t20b --autonomous\x01"
    _write(tmp_path, "t20b", resume_command=hostile)
    record = _load(tmp_path, "t20b")
    assert "--autonomous" not in record["resume_command"]


def test_notes_appended_only_when_not_at_stage_boundary(tmp_path):
    _write(tmp_path, "t21", at_stage_boundary=True, step="x")
    notes = _memory_dir(tmp_path) / "run-notes-t21.md"
    assert not notes.exists()
    _write(tmp_path, "t21", at_stage_boundary=False, step="y")
    assert notes.exists()
    assert notes.read_text(encoding="utf-8").count("## ") == 1


def test_notes_rotation_leaves_exactly_two_files(tmp_path):
    task = "t22"
    env = {"QUOIN_RUN_NOTES_MAX_BYTES": "200"}
    for i in range(3):
        args = [
            "--write", "--project-root", str(tmp_path), "--task", task,
            "--at-stage-boundary", "false", "--step", "x" * 70,
        ]
        full_env = dict(os.environ)
        full_env.update(env)
        subprocess.run([PY, str(SCRIPT)] + args, capture_output=True, text=True, timeout=30, env=full_env)
    memory_dir = _memory_dir(tmp_path)
    notes_files = sorted(p.name for p in memory_dir.glob(f"run-notes-{task}.md*"))
    assert notes_files == [f"run-notes-{task}.md", f"run-notes-{task}.md.1"]


def test_notes_append_refuses_to_follow_a_symlink(tmp_path):
    """`notes_path` (`run-notes-{task}.md`) can be replaced by a symlink
    pointing anywhere on disk; a plain `open(path, "a")` follows it and
    writes the notes block through the link. The write must refuse instead
    -- the JSON record write is already symlink-safe via `os.replace`,
    which always replaces the link itself rather than writing through it."""
    memory_dir = _memory_dir(tmp_path)
    memory_dir.mkdir(parents=True, exist_ok=True)
    outside_target = tmp_path / "outside-target.md"
    outside_target.write_text("", encoding="utf-8")
    (memory_dir / "run-notes-t25sym.md").symlink_to(outside_target)

    result = _write(tmp_path, "t25sym", at_stage_boundary=False, step="x")
    assert result.returncode == 0
    # The record write must still succeed even though the notes append was
    # refused -- notes are best-effort and must never abort the record.
    assert _record_path(tmp_path, "t25sym").exists()
    assert outside_target.read_text(encoding="utf-8") == ""
    assert (memory_dir / "run-notes-t25sym.md").is_symlink()


def test_notes_file_rejects_a_forged_entry(tmp_path):
    """A newline embedded in a written value must not let the value forge an
    extra `## ` heading line or `- next_action:` line of its own in the notes
    file -- the record's own JSON serialization already collapses it to one
    line via `_render`, and the notes block must be built from the same
    sanitized value, not the raw one (issue 4). A plain substring count of
    "## " would not discriminate a real forged heading from the same text
    merely embedded mid-line, so this asserts on actual heading LINES.
    """
    hostile = "legit-step\n## FORGED HEADING\n- next_action: FORGED-INSTRUCTION"
    _write(tmp_path, "t23", at_stage_boundary=False, step=hostile, next_action=hostile)
    record = _load(tmp_path, "t23")
    assert "\n" not in record["step"]
    assert "\n" not in record["next_action"]
    notes = _memory_dir(tmp_path) / "run-notes-t23.md"
    text = notes.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading_lines = [ln for ln in lines if ln.startswith("## ")]
    assert len(heading_lines) == 1, f"forged heading line leaked into notes file:\n{text}"
    next_action_lines = [ln for ln in lines if ln.startswith("- next_action:")]
    assert len(next_action_lines) == 1, f"forged next_action line leaked into notes file:\n{text}"


def test_sanitized_field_is_truncated_with_a_marker(tmp_path):
    oversized = "x" * 500_000
    _write(tmp_path, "t24", next_action=oversized)
    record = _load(tmp_path, "t24")
    assert len(record["next_action"].encode("utf-8")) < 4200
    assert record["next_action"].endswith("[truncated]")


def test_sanitize_idempotent_at_the_4093_byte_utf8_boundary():
    """A 4-byte UTF-8 character starting at byte offset 4093 leaves exactly
    three of its bytes inside the pre-fix truncation window, decoding as a
    dangling continuation the marker then follows -- the one split position
    (of all `_MAX_FIELD_BYTES`-adjacent positions) where the pre-fix
    `_sanitize` was not a fixed point. Reserving the marker's own bytes out
    of the truncation budget makes every position idempotent."""
    sys.path.insert(0, str(REPO_ROOT / "quoin" / "core" / "scripts"))
    import run_state  # noqa: E402

    value = "a" * 4093 + "\U0001F600" + "b" * 300
    once = run_state._sanitize(value)
    twice = run_state._sanitize(once)
    assert once == twice
    assert len(once.encode("utf-8")) <= 4096
    assert len(twice.encode("utf-8")) <= 4096


def test_malformed_stale_days_env_does_not_crash_read_write_or_clear(tmp_path):
    env = {"QUOIN_RUN_STATE_STALE_DAYS": "abc"}
    full_env = dict(os.environ)
    full_env.update(env)
    for args in (
        ["--write", "--project-root", str(tmp_path), "--task", "t25", "--step", "x"],
        ["--read", "--project-root", str(tmp_path), "--task", "t25", "--fields", "phase"],
        ["--clear", "--project-root", str(tmp_path), "--task", "t25"],
    ):
        result = subprocess.run(
            [PY, str(SCRIPT)] + args, capture_output=True, text=True, timeout=30, env=full_env
        )
        assert result.returncode == 0, f"{args} exited {result.returncode}: {result.stderr}"
        assert "Traceback" not in result.stderr


def test_reader_is_task_scoped_not_freshest_of_any_task(tmp_path):
    """The reader must address run-state-{task}.json directly, never the
    freshest active record across ALL tasks in the memory dir -- a
    task-blind reader answering for "alpha" with "beta"'s data misdirects
    whatever consumes resume_command/next_action (issue 6)."""
    _write(tmp_path, "alpha", next_action="start alpha-action", resume_command="/run --resume alpha")
    _write(tmp_path, "beta", next_action="start beta-action", resume_command="/run --resume beta")
    memory_dir = _memory_dir(tmp_path)
    got_alpha = _read_reader(memory_dir, "alpha", "resume_command", "next_action")
    got_beta = _read_reader(memory_dir, "beta", "resume_command", "next_action")
    assert got_alpha["resume_command"] == "/run --resume alpha"
    assert got_alpha["next_action"] == "start alpha-action"
    assert got_beta["resume_command"] == "/run --resume beta"
    assert got_beta["next_action"] == "start beta-action"


def test_reader_ignores_a_task_argument_containing_shell_metacharacters(tmp_path):
    _write(tmp_path, "alpha", next_action="start alpha-action")
    memory_dir = _memory_dir(tmp_path)
    got = _read_reader(memory_dir, "alpha; touch pwned", "next_action")
    assert got.get("next_action") is None
    assert not (tmp_path / "pwned").exists()


def test_reader_stale_days_injection_does_not_execute(tmp_path):
    """A malicious QUOIN_RUN_STATE_STALE_DAYS must never reach the `find
    -mtime -$((...))` arithmetic-eval sink unvalidated (issue 5)."""
    _write(tmp_path, "alpha", step="x")
    memory_dir = _memory_dir(tmp_path)
    marker = tmp_path / "pwned"
    hostile = f'q[$(touch "{marker}")]'
    got = _read_reader(memory_dir, "alpha", "step", env={"QUOIN_RUN_STATE_STALE_DAYS": hostile})
    assert not marker.exists()
    assert got.get("_stderr", "") == "" or "PWNED" not in got["_stderr"]


def test_reader_default_stale_days_still_selects_a_record_backdated_30_hours(tmp_path):
    """With QUOIN_RUN_STATE_STALE_DAYS unset, the reader's default freshness
    window must remain the documented `-mtime -2` (< 48h) pre-filter -- a
    30h-old record is well inside that window and must still be selected.
    Regression guard for a real bug caught only by the sh-level spike
    harness's window probes: the numeric-validation rewrite's un-defaulted
    `$QUOIN_RUN_STATE_STALE_DAYS` reference in the fallback branch silently
    collapsed the window to `-mtime -1` (< 24h) whenever the env var was
    unset, which every other test here was too fast (sub-second) to notice.
    """
    _write(tmp_path, "old30h", step="x")
    path = _record_path(tmp_path, "old30h")
    thirty_hours_ago = time.time() - (30 * 3600)
    os.utime(path, (thirty_hours_ago, thirty_hours_ago))
    got = _read_reader(_memory_dir(tmp_path), "old30h", "step")
    assert got.get("step") == "x"


@pytest.mark.parametrize("stale_days", ["08", "010", "0"])
def test_reader_stale_days_leading_zero_does_not_misparse_as_octal(tmp_path, stale_days):
    """A `QUOIN_RUN_STATE_STALE_DAYS` value with a leading zero passes the
    character-class validation (all digits) but is not valid octal --
    `$((08 + 1))` errors under bash/dash and `$((010 + 1))` silently reads
    as 9 (base-8 10 = 8, +1). The reader must strip leading zeros before
    the value reaches arithmetic expansion so it is read as decimal."""
    _write(tmp_path, "octal", step="x")
    got = _read_reader(
        _memory_dir(tmp_path), "octal", "step",
        env={"QUOIN_RUN_STATE_STALE_DAYS": stale_days},
    )
    assert got.get("step") == "x"
    assert "Illegal number" not in got.get("_stderr", "")
    assert "too great for base" not in got.get("_stderr", "")
