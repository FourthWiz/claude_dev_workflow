"""Unit tests for the portable cost-event module (quoin/core/scripts/cost_event.py).

All tests call cost_event.parse_row / format_row / CostEvent directly.
No test imports cost_from_jsonl.py, reads ~/.claude/projects/, or invokes npx.
Fixtures are inline string constants.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Load the canonical module from core/scripts/ (not the wrapper)
# ---------------------------------------------------------------------------

_CORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "quoin"
    / "core"
    / "scripts"
    / "cost_event.py"
)

_MODULE_NAME = "_quoin_core_cost_event_test"
_SPEC = importlib.util.spec_from_file_location(_MODULE_NAME, _CORE_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _MOD
_SPEC.loader.exec_module(_MOD)

CostEvent = _MOD.CostEvent
parse_row = _MOD.parse_row
format_row = _MOD.format_row
RowParseError = _MOD.RowParseError


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

_6COL = "abc123 | 2026-05-12 | plan | opus | task | my note"
_7COL_ZERO = "abc123 | 2026-05-12 | plan | opus | task | my note | 0"
_7COL_THREE = "abc123 | 2026-05-12 | plan | opus | task | my note | 3"
_7COL_BAD_INT = "abc123 | 2026-05-12 | plan | opus | task | my note | notanint"
_8COL = "abc123 | 2026-05-12 | plan | opus | task | my note | 2 | extra"
_EXTRA_SPACES = "abc123  |  2026-05-12  |  plan  |  opus  |  task  |  my note  |  1"
_NON_TASK = "abc123 | 2026-05-12 | plan | opus | event | my note | 0"
_BLANK = ""
_COMMENT = "# Cost Ledger — foo"
_TOO_FEW = "a | b | c | d"
_QUOTED_NOTE = 'abc123 | 2026-05-12 | plan | opus | task | "quoted note with spaces" | 0'
_INNER_QUOTES = 'abc123 | 2026-05-12 | plan | opus | task | "phase-23 \\"runtime-neutral\\" cost" | 0'


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_6col_legacy_returns_fallback_zero():
    """6-col row → fallback_fires=0; all other fields populated."""
    event = parse_row(_6COL)
    assert event is not None
    assert event.fallback_fires == 0
    assert event.uuid == "abc123"
    assert event.date == "2026-05-12"
    assert event.phase == "plan"
    assert event.model_or_effort == "opus"
    assert event.category == "task"
    assert event.note == "my note"


def test_parse_7col_zero_explicit():
    """7-col row with fallback_fires=0 → identical to 6-col result."""
    event = parse_row(_7COL_ZERO)
    assert event is not None
    assert event.fallback_fires == 0
    assert event.uuid == "abc123"
    assert event.note == "my note"


def test_parse_7col_nonzero():
    """7-col row with fallback_fires=3 → field is 3."""
    event = parse_row(_7COL_THREE)
    assert event is not None
    assert event.fallback_fires == 3


def test_parse_7col_malformed_int_warns_and_zeros(capsys):
    """Non-integer 7th col → fallback_fires=0 AND stderr warns with cost_snapshot.WARN prefix."""
    event = parse_row(_7COL_BAD_INT, source="test.md", lineno=42)
    assert event is not None
    assert event.fallback_fires == 0
    captured = capsys.readouterr()
    assert "cost_snapshot.WARN" in captured.err
    assert "malformed fallback_fires column" in captured.err
    assert "test.md:42" in captured.err


def test_parse_8col_extra_warns_and_takes_7th(capsys):
    """8-col row → fallback_fires is 7th column; stderr warns with cost_snapshot.WARN prefix."""
    event = parse_row(_8COL, source="test.md", lineno=7)
    assert event is not None
    assert event.fallback_fires == 2
    captured = capsys.readouterr()
    assert "cost_snapshot.WARN" in captured.err
    assert "extra columns" in captured.err
    assert "test.md:7" in captured.err


def test_parse_extra_spaces_strip_clean():
    """Extra spaces around pipes → all fields stripped clean."""
    event = parse_row(_EXTRA_SPACES)
    assert event is not None
    assert event.uuid == "abc123"
    assert event.date == "2026-05-12"
    assert event.phase == "plan"
    assert event.model_or_effort == "opus"
    assert event.category == "task"
    assert event.note == "my note"
    assert event.fallback_fires == 1


def test_parse_non_task_category_returns_none():
    """Category 'event' (not 'task') → returns None (skip-line semantics)."""
    result = parse_row(_NON_TASK)
    assert result is None


def test_parse_blank_line_returns_none():
    """Blank line → returns None."""
    assert parse_row(_BLANK) is None
    assert parse_row("   ") is None


def test_parse_comment_line_returns_none():
    """Comment line (starts with #) → returns None."""
    assert parse_row(_COMMENT) is None


def test_parse_too_few_columns_returns_none():
    """Row with fewer than 6 columns → returns None."""
    assert parse_row(_TOO_FEW) is None


def test_format_round_trip_7col():
    """format_row(parse_row(line)) == line.strip() for a valid 7-col input."""
    line = _7COL_THREE
    event = parse_row(line)
    assert event is not None
    assert format_row(event) == line.strip()


def test_format_round_trip_6col_upgrades_to_7col():
    """format_row(parse_row(6col_line)) appends ' | 0' (documented one-way upgrade)."""
    event = parse_row(_6COL)
    assert event is not None
    result = format_row(event)
    assert result.endswith("| 0")
    # The first 6 fields round-trip cleanly
    assert result.startswith(_6COL.strip())


def test_parse_quoted_note_preserves_quotes():
    """Quoted note field → literal double-quotes preserved verbatim (D-05)."""
    event = parse_row(_QUOTED_NOTE)
    assert event is not None
    assert event.note == '"quoted note with spaces"'


def test_format_round_trip_quoted_note():
    """format_row(parse_row(quoted_note_line)) == line.strip() byte-for-byte."""
    event = parse_row(_QUOTED_NOTE)
    assert event is not None
    assert format_row(event) == _QUOTED_NOTE.strip()


def test_parse_inner_double_quotes_preserved():
    """Note field with escaped inner double-quotes → preserved byte-for-byte (D-05, MAJ-3 case o)."""
    event = parse_row(_INNER_QUOTES)
    assert event is not None
    # The note field is preserved exactly as it appeared between the pipes
    expected_note = r'"phase-23 \"runtime-neutral\" cost"'
    assert event.note == expected_note
    # Full row round-trips byte-for-byte
    assert format_row(event) == _INNER_QUOTES.strip()
