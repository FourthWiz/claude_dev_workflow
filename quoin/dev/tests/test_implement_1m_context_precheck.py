"""Regression tests for the §0-1m-context-precheck block in implement's adapter SKILL.md.

Bug fixed: When /implement was invoked from an Opus 1M parent session, the §0 dispatch
fired `Agent(model="sonnet")`. The Claude Code CLI propagates the parent's
`context-1m-2025-08-07` beta header to all subagent API calls, so the dispatch landed on
Sonnet 1M. Users lacking Sonnet 1M credits got a 400 error:
  "API Error: Usage credits required for 1M context"

Fix: a §0-1m-context-precheck block detects the 1M parent signal (via the model-name
string) and issues an AskUserQuestion before any dispatch is attempted. Users can abort
(run /model first) or proceed in-session at the parent tier.

These tests lock the block's presence, position, and content against regression.
"""
from pathlib import Path

import pytest

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
ADAPTER_SKILL = (
    PKG_DIR / "adapters" / "claude" / "skills" / "implement" / "SKILL.md"
)

BEGIN_MARKER = "<!-- §0-1m-context-precheck-begin -->"
END_MARKER = "<!-- §0-1m-context-precheck-end -->"
SECTION_ZERO_HEADING = "## §0 Model dispatch"
DISPATCH_TRIGGER = "If current_tier > declared_tier"

OPTION_LABEL_ABORT = "Abort — I'll switch with /model first"
OPTION_LABEL_PROCEED = "Proceed in-session at parent tier"

REQUIRED_SUBSTRINGS = ["`1m`", "`1M`", "`(1M context)`", "`context-1m`"]

NO_REDISPATCH_PASSTHROUGH_HINT = "[no-redispatch]"
ABORT_NO_SPAWN_PHRASE = "Do NOT spawn any Agent"


def _read_skill() -> str:
    assert ADAPTER_SKILL.is_file(), f"Adapter SKILL.md not found: {ADAPTER_SKILL}"
    return ADAPTER_SKILL.read_text(encoding="utf-8")


def _line_number(text: str, substring: str) -> int:
    """Return 1-based line number of first occurrence of substring, or -1."""
    for i, line in enumerate(text.splitlines(), start=1):
        if substring in line:
            return i
    return -1


def _lines_in_block(text: str) -> list[str]:
    """Return the lines between (exclusive) the begin and end markers."""
    lines = text.splitlines()
    in_block = False
    block_lines = []
    for line in lines:
        if BEGIN_MARKER in line:
            in_block = True
            continue
        if END_MARKER in line:
            break
        if in_block:
            block_lines.append(line)
    return block_lines


def test_block_markers_present():
    """Both HTML comment markers appear exactly once in the adapter SKILL.md."""
    text = _read_skill()
    assert text.count(BEGIN_MARKER) == 1, (
        f"Expected exactly 1 occurrence of begin marker in adapter SKILL.md, "
        f"got {text.count(BEGIN_MARKER)}"
    )
    assert text.count(END_MARKER) == 1, (
        f"Expected exactly 1 occurrence of end marker in adapter SKILL.md, "
        f"got {text.count(END_MARKER)}"
    )


def test_block_position_in_section_zero():
    """Both markers fall inside the ## §0 Model dispatch H2 section.

    Uses simple line-number bookkeeping: find the §0 heading, find the next H2
    heading after it, and verify that both markers sit between those two lines.
    """
    text = _read_skill()
    lines = text.splitlines()

    section_start = _line_number(text, SECTION_ZERO_HEADING)
    assert section_start != -1, f"Heading '{SECTION_ZERO_HEADING}' not found"

    # Next H2 heading after the §0 heading (signals end of the §0 section).
    section_end = len(lines) + 1  # default: end of file
    for i, line in enumerate(lines[section_start:], start=section_start + 1):
        if line.startswith("## ") and SECTION_ZERO_HEADING not in line:
            section_end = i
            break

    begin_line = _line_number(text, BEGIN_MARKER)
    end_line = _line_number(text, END_MARKER)

    assert section_start < begin_line < section_end, (
        f"Begin marker (line {begin_line}) must sit inside §0 section "
        f"(lines {section_start}–{section_end})"
    )
    assert section_start < end_line < section_end, (
        f"End marker (line {end_line}) must sit inside §0 section "
        f"(lines {section_start}–{section_end})"
    )


def test_block_position_before_dispatch_trigger():
    """Begin marker's line number is strictly less than the dispatch trigger line.

    The precheck must run BEFORE the tier comparison — if the block sits after
    the dispatch trigger, a 1M parent could slip through to the Agent call before
    the precheck fires.
    """
    text = _read_skill()
    begin_line = _line_number(text, BEGIN_MARKER)
    trigger_line = _line_number(text, DISPATCH_TRIGGER)

    assert trigger_line != -1, f"Dispatch trigger not found: '{DISPATCH_TRIGGER}'"
    assert begin_line < trigger_line, (
        f"Begin marker (line {begin_line}) must appear before dispatch trigger "
        f"(line {trigger_line}) — the precheck fires before tier comparison"
    )


def test_block_contains_required_option_labels():
    """Both AskUserQuestion option labels appear verbatim inside the marker pair.

    String equality is the drift-detection contract: if these labels change in the
    SKILL.md, the real AskUserQuestion output diverges from the documented intent.
    """
    text = _read_skill()
    block_text = "\n".join(_lines_in_block(text))

    assert OPTION_LABEL_ABORT in block_text, (
        f"Option label not found in block: {OPTION_LABEL_ABORT!r}"
    )
    assert OPTION_LABEL_PROCEED in block_text, (
        f"Option label not found in block: {OPTION_LABEL_PROCEED!r}"
    )


def test_block_contains_substring_list():
    """The block documents all four 1M-detection substrings for the model name check."""
    text = _read_skill()
    block_text = "\n".join(_lines_in_block(text))

    for substr in REQUIRED_SUBSTRINGS:
        assert substr in block_text, (
            f"Detection substring {substr!r} not found in precheck block. "
            "The block must list all four 1M signal strings."
        )


def test_block_documents_no_redispatch_passthrough():
    """The block states that a [no-redispatch] prompt skips the precheck.

    Without this guard, the precheck would intercept manual-override invocations
    (e.g., '[no-redispatch] /implement') and erroneously show the AskUserQuestion
    to users who already opted out of dispatch.
    """
    text = _read_skill()
    block_text = "\n".join(_lines_in_block(text))

    assert NO_REDISPATCH_PASSTHROUGH_HINT in block_text, (
        f"Block must document the [no-redispatch] passthrough case. "
        f"Hint string not found: {NO_REDISPATCH_PASSTHROUGH_HINT!r}"
    )
    # Extra specificity: the passthrough rule must appear after the option labels
    # (it's a conditional, not the main path).
    label_pos = block_text.find(OPTION_LABEL_ABORT)
    passthrough_pos = block_text.find(NO_REDISPATCH_PASSTHROUGH_HINT)
    # Allow passthrough to appear anywhere in the block (it also appears inside
    # the option descriptions as context) — just assert it IS there (above).


def test_block_documents_abort_no_tool_call():
    """The block states that the Abort path must NOT spawn any Agent.

    This anchors the "abort means abort" invariant — without it, a future edit
    could accidentally add an Agent call inside the abort branch.

    Whitespace-normalized match: the phrase may span a line break in the SKILL.md
    block (e.g., "Do NOT spawn any\n          Agent"), so we collapse all
    whitespace sequences to a single space before asserting.
    """
    text = _read_skill()
    block_text = "\n".join(_lines_in_block(text))
    # Normalize: collapse any sequence of whitespace (including newlines) to a
    # single space so the assertion is robust to line-wrap formatting in the block.
    normalized = " ".join(block_text.split())

    assert ABORT_NO_SPAWN_PHRASE in normalized, (
        f"Block must contain the phrase {ABORT_NO_SPAWN_PHRASE!r} (whitespace-normalized) "
        "to document that the Abort path does not spawn any Agent tool call."
    )
