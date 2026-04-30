"""T-10: backward-compat parser test for cost-ledger 6- and 7-column schema.

Verifies that the parsing logic described in cost_snapshot/SKILL.md T-06:
- tolerates 6-column rows (legacy format)
- reads 7th column (fallback_fires) when present
- emits stderr WARN on malformed 7th column
- handles extra columns gracefully
- uses split("|")+strip (not split(" | "))
- rejects non-"task" category rows (defensive guard)
"""
import sys
import io
import pytest


class SkipLine(Exception):
    """Raised when a line should be skipped (e.g., non-task category)."""
    pass


def parse_ledger_line(line: str, *, ledger: str = "<test>", lineno: int = 0) -> dict:
    """Parse a single cost-ledger line.

    Returns a dict with keys: uuid, date, phase, model, category, note, fallback_fires.
    Raises SkipLine if the line should be ignored (comment, blank, non-task category).
    Emits stderr WARN for malformed or extra-column rows.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        raise SkipLine("blank or comment")

    parts = [p.strip() for p in stripped.split("|")]
    if len(parts) < 6:
        raise SkipLine(f"too few columns ({len(parts)})")

    uuid = parts[0]
    date = parts[1]
    phase = parts[2]
    model = parts[3]
    category = parts[4]
    note = parts[5]

    # Defensive guard: only accept "task" category rows
    if category != "task":
        raise SkipLine(f"non-task category: {category!r}")

    fallback_fires = 0
    if len(parts) == 7:
        raw = parts[6]
        try:
            fallback_fires = int(raw)
        except ValueError:
            print(
                f"cost_snapshot.WARN: malformed fallback_fires column at {ledger}:{lineno}: {raw!r}",
                file=sys.stderr,
            )
            fallback_fires = 0
    elif len(parts) > 7:
        raw = parts[6]
        try:
            fallback_fires = int(raw)
        except ValueError:
            fallback_fires = 0
        print(
            f"cost_snapshot.WARN: extra columns at {ledger}:{lineno} (found {len(parts)}, expected ≤7)",
            file=sys.stderr,
        )

    return {
        "uuid": uuid,
        "date": date,
        "phase": phase,
        "model": model,
        "category": category,
        "note": note,
        "fallback_fires": fallback_fires,
    }


# ── Fixture rows ─────────────────────────────────────────────────────────────

ROW_6_COL = "abc123 | 2026-04-30 | plan | opus | task | 6-col legacy row"
ROW_7_COL_ZERO = "abc124 | 2026-04-30 | implement | sonnet | task | 7-col zero | 0"
ROW_7_COL_THREE = "abc125 | 2026-04-30 | review | opus | task | 7-col three fires | 3"
ROW_7_COL_MALFORMED = "abc126 | 2026-04-30 | critic | opus | task | 7-col bad int | oops"
ROW_8_COL = "abc127 | 2026-04-30 | gate | sonnet | task | 8-col extra | 2 | IGNORED"
ROW_EXTRA_SPACES = "abc128 | 2026-04-30 | plan | opus | task | extra-spaces row | 2"
ROW_NON_TASK = "abc129 | 2026-04-30 | gate | sonnet | event | non-task category"


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_6col_legacy_fallback_is_zero():
    """Row (1): 6-column row → fallback_fires defaults to 0."""
    result = parse_ledger_line(ROW_6_COL)
    assert result["fallback_fires"] == 0
    assert result["category"] == "task"


def test_7col_zero_explicit():
    """Row (2): 7-column row with fallback_fires=0 → parses as 0."""
    result = parse_ledger_line(ROW_7_COL_ZERO)
    assert result["fallback_fires"] == 0
    assert result["category"] == "task"


def test_7col_nonzero():
    """Row (3): 7-column row with fallback_fires=3 → parses as 3."""
    result = parse_ledger_line(ROW_7_COL_THREE)
    assert result["fallback_fires"] == 3
    assert result["category"] == "task"


def test_7col_malformed_emits_warn(capsys):
    """Row (4): malformed integer → fallback_fires=0, stderr WARN emitted."""
    result = parse_ledger_line(ROW_7_COL_MALFORMED, ledger="test.md", lineno=4)
    assert result["fallback_fires"] == 0
    captured = capsys.readouterr()
    assert "cost_snapshot.WARN" in captured.err
    assert "malformed fallback_fires" in captured.err


def test_8col_extra_columns_emits_warn(capsys):
    """Row (5): 8-column row → 7th column used as fallback_fires, extra ignored with WARN."""
    result = parse_ledger_line(ROW_8_COL, ledger="test.md", lineno=5)
    assert result["fallback_fires"] == 2
    captured = capsys.readouterr()
    assert "cost_snapshot.WARN" in captured.err
    assert "extra columns" in captured.err


def test_extra_spaces_split_and_strip():
    """Row (6): extra spaces around pipe delimiters parse cleanly via split('|')+strip."""
    result = parse_ledger_line(ROW_EXTRA_SPACES)
    assert result["fallback_fires"] == 2
    assert result["uuid"] == "abc128"


def test_non_task_category_raises_skipline():
    """Negative: category != 'task' must raise SkipLine."""
    with pytest.raises(SkipLine):
        parse_ledger_line(ROW_NON_TASK)


def test_blank_line_raises_skipline():
    with pytest.raises(SkipLine):
        parse_ledger_line("")


def test_comment_line_raises_skipline():
    with pytest.raises(SkipLine):
        parse_ledger_line("# Cost Ledger — my-task")


def test_too_few_columns_raises_skipline():
    with pytest.raises(SkipLine):
        parse_ledger_line("a | b | c | d")  # only 4 columns
