"""T-08: Unit tests for analyze_cost_ledger.py — inline-first reader precedence
and the never-silent-$0 resolved_total/unresolvable_count split (D-1/D-2/D-3).

No test file existed for this module before stage 4 (verified). Fixtures are
authored as RAW ledger lines (per plan D-4) — never produced by enabling
QUOIN_INLINE_COST_CAPTURE.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load analyze_cost_ledger.py via spec_from_file_location (adapter script)
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts"
_ACL_PATH = _SCRIPTS_PATH / "analyze_cost_ledger.py"

_SPEC = importlib.util.spec_from_file_location("_quoin_adapter_analyze_cost_ledger_test", _ACL_PATH)
_ACL = importlib.util.module_from_spec(_SPEC)
sys.modules["_quoin_adapter_analyze_cost_ledger_test"] = _ACL
_SPEC.loader.exec_module(_ACL)

parse_ledger_file = _ACL.parse_ledger_file
build_report = _ACL.build_report
format_report = _ACL.format_report
project_hash = _ACL.project_hash


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_ledger(tmp_path: Path, lines: list[str]) -> Path:
    task_dir = tmp_path / "project" / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = task_dir / "cost-ledger.md"
    ledger_path.write_text("# Cost Ledger — my-task\n" + "\n".join(lines) + "\n")
    return ledger_path


def _make_jsonl(home: Path, uuid: str, proj_hash: str, cost_input_tokens: int = 1_000_000) -> None:
    """Write a minimal fixture JSONL resolving `uuid` to a nonzero cost via
    the real claude-opus-4-8 price table (~$5.00 per 1M input tokens)."""
    proj_dir = home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = proj_dir / f"{uuid}.jsonl"
    row = {
        "message": {
            "model": "claude-opus-4-8",
            "usage": {"input_tokens": cost_input_tokens, "output_tokens": 0},
        }
    }
    jsonl_path.write_text(json.dumps(row) + "\n")


# Canonical mixed-column ledger rows (raw pipe-delimited text, D-4).
_6COL = "uuid-6col | 2026-07-27 | plan | opus | task | six col note"
_7COL = "uuid-7col | 2026-07-27 | plan | opus | task | seven col note | 0"
_8COL_RESOLVED = "uuid-8res | 2026-07-27 | implement | opus | task | resolved note | 0 | usd=1.5;tok=1000;src=nested_jsonl"
_8COL_RESOLVED_BACKFILL = "uuid-8bak | 2026-07-27 | implement | opus | task | backfill note | 0 | usd=0.75;tok=500;src=backfill_session"
_8COL_RESOLVED_ZERO = "uuid-8zero | 2026-07-27 | implement | opus | task | resolved zero | 0 | usd=0.0;tok=9;src=nested_jsonl"
_8COL_UNRESOLVED = "uuid-8unres | 2026-07-27 | implement | opus | task | unresolved note | 0 | tok=45;src=unresolved"
_9COL_TOLERATED = "uuid-9col | 2026-07-27 | implement | opus | task | nine col note | 0 | usd=2.0;tok=1;src=nested_jsonl | extra-ignored-col"


# ---------------------------------------------------------------------------
# 6/7-col regression — must parse exactly as pre-stage-4 (R-01)
# ---------------------------------------------------------------------------

def test_6col_legacy_row_resolves_via_jsonl(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_6COL])
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    ph = project_hash(str(project_root))
    _make_jsonl(home, "uuid-6col", ph)

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 0
    assert report["resolved_total"] > 0
    assert report["total_cost"] == report["resolved_total"]


def test_7col_legacy_row_missing_jsonl_is_unresolvable_not_silent_zero(tmp_path):
    """R-03/D-3: a legacy row with no JSONL must be counted as unresolvable,
    NEVER silently folded into a $0 contribution to the resolved total."""
    ledger_path = _write_ledger(tmp_path, [_7COL])
    project_root = tmp_path / "project"
    home = tmp_path / "home"  # no .claude/projects/ tree at all — no JSONL exists
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 1
    assert report["resolved_total"] == 0.0
    assert report["no_jsonl_count"] == 1


# ---------------------------------------------------------------------------
# 8-col resolved — inline usd used directly, NO JSONL lookup (R-01/R-04)
# ---------------------------------------------------------------------------

def test_8col_resolved_row_bypasses_jsonl_lookup(tmp_path):
    """A resolved col-8 row must use the inline usd even when the JSONL tree
    is completely empty — proving the JSONL lookup was skipped."""
    ledger_path = _write_ledger(tmp_path, [_8COL_RESOLVED])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"  # deliberately no JSONL tree at all
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 0
    assert abs(report["resolved_total"] - 1.5) < 1e-9


def test_8col_resolved_backfill_session_also_bypasses_jsonl(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_8COL_RESOLVED_BACKFILL])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 0
    assert abs(report["resolved_total"] - 0.75) < 1e-9


def test_8col_resolved_zero_is_real_not_unresolvable(tmp_path):
    """MINOR-5/D-8: a genuine resolved usd=0.0 contributes to resolved_total
    (as 0.0) and must NOT increment unresolvable_count."""
    ledger_path = _write_ledger(tmp_path, [_8COL_RESOLVED_ZERO])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 0
    assert report["resolved_total"] == 0.0


# ---------------------------------------------------------------------------
# 8-col unresolved — never folded into $0 (D-3, the R-03 mitigation)
# ---------------------------------------------------------------------------

def test_8col_unresolved_row_counted_never_folded_to_zero(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_8COL_UNRESOLVED])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["unresolvable_count"] == 1
    assert report["resolved_total"] == 0.0


# ---------------------------------------------------------------------------
# >=9-col — tolerated (col 8 = attribution, rest ignored, no crash)
# ---------------------------------------------------------------------------

def test_9col_row_tolerated_takes_8th_as_attribution(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_9COL_TOLERATED])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    assert len(rows) == 1
    assert rows[0]["attribution"] == "usd=2.0;tok=1;src=nested_jsonl"

    report = build_report(rows, project_root, ph, home)
    assert report["unresolvable_count"] == 0
    assert abs(report["resolved_total"] - 2.0) < 1e-9


# ---------------------------------------------------------------------------
# Mixed ledger — the shared T-08/T-12 fixture; correct partition end-to-end
#
# Stage-6 T-03 traceability: this section already exercises the exact mixed-
# column set the stage-6 plan asks for (legacy 6-col, legacy 7-col-no-JSONL,
# col-8 nested_jsonl, col-8 backfill_session, col-8 unresolved), asserting
# resolved_total sums ONLY resolved rows, unresolvable_count == exactly the
# unresolvable/no-JSONL rows (never folded into a silent $0), and both the
# `(partial)` and non-partial format_report render branches. No gap found;
# no new tests added here per plan T-03.
# ---------------------------------------------------------------------------

def test_mixed_ledger_resolved_total_excludes_unresolvable_slice(tmp_path):
    """Load-bearing (mutation-style, per lessons 2026-06-15): if a future
    regression folded the unresolved row into resolved_total OR stopped
    counting it, this assertion catches it — resolved_total must equal
    EXACTLY the sum of the two resolved rows, and unresolvable_count must
    equal EXACTLY the count of unresolvable/missing-JSONL rows."""
    ledger_path = _write_ledger(
        tmp_path,
        [_6COL, _7COL, _8COL_RESOLVED, _8COL_RESOLVED_BACKFILL, _8COL_UNRESOLVED],
    )
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    ph = project_hash(str(project_root))
    # Only the 6-col legacy row resolves via JSONL; the 7-col legacy row's
    # JSONL is deliberately absent (unresolvable).
    _make_jsonl(home, "uuid-6col", ph)

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    # unresolvable: 7-col (no JSONL) + 8-col-unresolved = 2
    assert report["unresolvable_count"] == 2
    # resolved: 6-col JSONL cost (1M input tok @ claude-opus-4-8 = $5.00,
    # per _make_jsonl's default) + 1.5 (nested_jsonl) + 0.75 (backfill)
    expected_total = 5.00 + 1.5 + 0.75
    assert abs(report["resolved_total"] - expected_total) < 1e-9


def test_format_report_shows_partial_marker_when_unresolvable(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_8COL_RESOLVED, _8COL_UNRESOLVED])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)
    text = format_report(report, project_root, ledger_count=1, top_n=10, report_date="2026-07-27")

    assert "(partial)" in text
    assert "Unresolvable: 1" in text
    assert "not $0" in text


def test_format_report_no_partial_marker_when_fully_resolved(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_8COL_RESOLVED])
    project_root = tmp_path / "project"
    home = tmp_path / "empty-home"
    ph = project_hash(str(project_root))

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)
    text = format_report(report, project_root, ledger_count=1, top_n=10, report_date="2026-07-27")

    assert "(partial)" not in text


# ---------------------------------------------------------------------------
# IVG-157 T-06: shared-UUID cohort attribution (analyze surface)
#
# Non-negotiable (Q-01 = LABELED BUCKET, locked): a UUID shared by two or
# more legacy rows must be resolved ONCE and shown as a labeled
# shared_bucket, never as a whole-session dollar figure duplicated onto each
# participating phase, never a silent $0.
# ---------------------------------------------------------------------------

_SHARED_UUID = "uuid-shared-cohort"
_SHARED_ROW_PLAN = f"{_SHARED_UUID} | 2026-07-27 | thorough-plan | opus | task | plan note"
_SHARED_ROW_CHECKPOINT = f"{_SHARED_UUID} | 2026-07-27 | checkpoint | opus | task | save"


def test_shared_uuid_cohort_counted_once_not_per_phase(tmp_path):
    """Two legacy rows (plan + checkpoint) sharing one UUID with a real
    fixture JSONL: shared_bucket.cost == session cost ONCE, resolved_total
    == session cost (NOT 2x), and neither phase shows the whole-session
    dollar in by_phase."""
    ledger_path = _write_ledger(tmp_path, [_SHARED_ROW_PLAN, _SHARED_ROW_CHECKPOINT])
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    ph = project_hash(str(project_root))
    _make_jsonl(home, _SHARED_UUID, ph)  # ~$5.00 session per _make_jsonl default

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)

    assert report["shared_bucket"]["uuids"] == 1
    assert report["shared_bucket"]["cost"] == pytest.approx(5.00)
    assert abs(report["resolved_total"] - 5.00) < 1e-9  # NOT 2x
    assert "thorough-plan" not in report["by_phase"]
    assert "checkpoint" not in report["by_phase"]
    assert report["shared_bucket"]["phases"]["checkpoint"] == {
        "save": 1, "restore": 0, "count": 1,
    }


def test_format_report_renders_shared_session_bucket_line(tmp_path):
    ledger_path = _write_ledger(tmp_path, [_SHARED_ROW_PLAN, _SHARED_ROW_CHECKPOINT])
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    ph = project_hash(str(project_root))
    _make_jsonl(home, _SHARED_UUID, ph)

    rows = parse_ledger_file(ledger_path, task_name="my-task")
    report = build_report(rows, project_root, ph, home)
    text = format_report(report, project_root, ledger_count=1, top_n=10, report_date="2026-07-27")

    assert "shared-session (multi-phase)" in text
    assert "not separately attributable" in text
