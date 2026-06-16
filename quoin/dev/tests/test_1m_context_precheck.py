"""Parametrized regression tests for the §0-1m-context-precheck and
§0prime-1m-context-precheck blocks across all 25 target skills.

Background
----------
When /implement was invoked from an Opus 1M parent session, the §0 cost-guardrail
dispatch fired `Agent(model="sonnet")`. The Claude Code CLI propagates the parent's
`context-1m-2025-08-07` beta header to all subagent API calls, so the dispatch
landed on Sonnet 1M. Users lacking Sonnet 1M credits got a 400 error:
  "API Error: Usage credits required for 1M context"

Fix (IVG-73): a precheck block detects the 1M parent signal (via the model-name
string) and issues an AskUserQuestion before any dispatch is attempted. Users can
abort (run /model first) or proceed in-session at the parent tier.

This file generalises test_implement_1m_context_precheck.py (which tested only
/implement) to cover all 19 §0 cheap-tier skills (18 + implement) and all 7 §0'
pollution-dispatch skills.

After this file is green, test_implement_1m_context_precheck.py is deleted (D-03).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
ADAPTER_SKILLS_DIR = PKG_DIR / "adapters" / "claude" / "skills"
LEGACY_SKILLS_DIR = PKG_DIR / "skills"

# ---------------------------------------------------------------------------
# Path resolver (mirrors skill_md_path() in test_quoin_stage1_preamble.py)
# ---------------------------------------------------------------------------

# Skills migrated to the three-file adapter pattern. Self-contained copy —
# do NOT import across test modules (repo convention).
MIGRATED_TO_ADAPTER: frozenset[str] = frozenset({
    "capture_insight", "triage", "start_of_day", "plan", "critic", "revise",
    "revise-fast", "gate", "implement", "rollback", "end_of_task", "run",
    "end_of_day", "weekly_review", "cost_snapshot", "expand", "pr", "status",
    # §0' targets — all adapter-path
    "architect", "review", "init_workflow", "discover",
})


def skill_md_path(skill_name: str) -> Path:
    """Return the canonical SKILL.md path for a given skill."""
    if skill_name in MIGRATED_TO_ADAPTER:
        return ADAPTER_SKILLS_DIR / skill_name / "SKILL.md"
    return LEGACY_SKILLS_DIR / skill_name / "SKILL.md"


# ---------------------------------------------------------------------------
# Per-skill data tables (T-01 source of truth)
# ---------------------------------------------------------------------------

# §0 targets: (skill_name, declared_tier, proceed_ref)
# proceed_ref ∈ {"§1", "§0c"}; declared_tier ∈ {"haiku", "sonnet"}
# NOTE: implement is folded here (D-03) to maintain coverage without a separate file.
SECTION0_TARGETS = [
    ("gate",           "sonnet", "§1"),
    ("end_of_day",     "haiku",  "§1"),
    ("start_of_day",   "haiku",  "§1"),
    ("capture_insight","haiku",  "§1"),
    ("cost_snapshot",  "haiku",  "§1"),
    ("weekly_review",  "haiku",  "§1"),
    ("end_of_task",    "sonnet", "§1"),
    ("implement",      "sonnet", "§1"),
    ("rollback",       "sonnet", "§1"),
    ("expand",         "sonnet", "§1"),
    ("revise-fast",    "sonnet", "§1"),
    ("triage",         "haiku",  "§1"),
    ("pr",             "sonnet", "§1"),
    ("status",         "haiku",  "§1"),
    ("cleanup",        "haiku",  "§0c"),
    ("sleep",          "haiku",  "§0c"),
    ("next_steps",     "haiku",  "§1"),
    ("checkpoint",     "haiku",  "§0c"),
    ("continue_work",  "sonnet", "§1"),
]

# §0' targets: just the skill name; tier is always opus; proceed = "skill body"
SECTION0PRIME_TARGETS = [
    "architect",
    "plan",
    "critic",
    "revise",
    "review",
    "init_workflow",
    "discover",
]

# Skill-agnostic invariants (must appear in every precheck block, verbatim)
REQUIRED_DETECTION_SUBSTRINGS = ["`1m`", "`1M`", "`(1M context)`", "`context-1m`"]
OPTION_LABEL_ABORT  = "Abort — I'll switch with /model first"
OPTION_LABEL_PROCEED = "Proceed in-session at parent tier"
NO_REDISPATCH_HINT  = "[no-redispatch]"
ABORT_NO_SPAWN_PHRASE = "Do NOT spawn any Agent"

# Marker literals (full literal — MINOR-6: substring checks must use these exactly,
# not loose `§0-` which would also match `§0prime-`)
S0_BEGIN_MARKER  = "<!-- §0-1m-context-precheck-begin -->"
S0_END_MARKER    = "<!-- §0-1m-context-precheck-end -->"
S0P_BEGIN_MARKER = "<!-- §0prime-1m-context-precheck-begin -->"
S0P_END_MARKER   = "<!-- §0prime-1m-context-precheck-end -->"

S0_SECTION_HEADING  = "## §0 Model dispatch"
S0P_SECTION_HEADING = "## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)"
S0_DISPATCH_TRIGGER = "If current_tier > declared_tier"
S0P_DISPATCH_ANCHOR = "Dispatch action (when pollution detected"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _line_number(text: str, substring: str) -> int:
    """Return 1-based line number of first occurrence of substring, or -1."""
    for i, line in enumerate(text.splitlines(), start=1):
        if substring in line:
            return i
    return -1


def _extract_block(text: str, begin_marker: str, end_marker: str) -> str:
    """Return the text between (exclusive) begin and end markers, or empty string."""
    lines = text.splitlines()
    in_block = False
    block_lines: list[str] = []
    for line in lines:
        if begin_marker in line:
            in_block = True
            continue
        if end_marker in line:
            break
        if in_block:
            block_lines.append(line)
    return "\n".join(block_lines)


def _section_bounds(text: str, section_heading: str) -> tuple[int, int]:
    """Return (start_line, end_line) for the named H2 section (1-based, inclusive start).

    end_line is the line of the next ## heading after the section, or len(lines)+1.
    """
    lines = text.splitlines()
    start = _line_number(text, section_heading)
    assert start != -1, f"Section heading not found: {section_heading!r}"
    end = len(lines) + 1
    for i, line in enumerate(lines[start:], start=start + 1):
        if line.startswith("## ") and section_heading not in line:
            end = i
            break
    return start, end


def _normalize_ws(s: str) -> str:
    """Collapse whitespace sequences (including newlines) to a single space."""
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# §0 parametrized tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill,declared_tier,proceed_ref", SECTION0_TARGETS)
class TestSection0Precheck:
    """All assertions from T-04 checks (a)–(f) + CRIT-1 proceed-ref + MINOR-2 dispatch-noun."""

    def _read(self, skill: str) -> str:
        path = skill_md_path(skill)
        assert path.is_file(), f"SKILL.md not found: {path}"
        return path.read_text(encoding="utf-8")

    def test_markers_present_once(self, skill, declared_tier, proceed_ref):
        """Both §0 markers appear exactly once (full literal, not §0prime-)."""
        text = self._read(skill)
        assert text.count(S0_BEGIN_MARKER) == 1, (
            f"[{skill}] Expected exactly 1 §0-begin marker, got {text.count(S0_BEGIN_MARKER)}"
        )
        assert text.count(S0_END_MARKER) == 1, (
            f"[{skill}] Expected exactly 1 §0-end marker, got {text.count(S0_END_MARKER)}"
        )

    def test_markers_inside_section_zero(self, skill, declared_tier, proceed_ref):
        """Both markers sit inside ## §0 Model dispatch (bounded by next ## H2)."""
        text = self._read(skill)
        sec_start, sec_end = _section_bounds(text, S0_SECTION_HEADING)
        begin_line = _line_number(text, S0_BEGIN_MARKER)
        end_line   = _line_number(text, S0_END_MARKER)
        assert sec_start < begin_line < sec_end, (
            f"[{skill}] §0-begin marker (line {begin_line}) not inside §0 section "
            f"(lines {sec_start}–{sec_end})"
        )
        assert sec_start < end_line < sec_end, (
            f"[{skill}] §0-end marker (line {end_line}) not inside §0 section "
            f"(lines {sec_start}–{sec_end})"
        )

    def test_begin_marker_before_dispatch_trigger(self, skill, declared_tier, proceed_ref):
        """§0-begin marker appears before the 'If current_tier > declared_tier' trigger."""
        text = self._read(skill)
        begin_line   = _line_number(text, S0_BEGIN_MARKER)
        trigger_line = _line_number(text, S0_DISPATCH_TRIGGER)
        assert trigger_line != -1, f"[{skill}] Dispatch trigger not found"
        assert begin_line < trigger_line, (
            f"[{skill}] §0-begin (line {begin_line}) must precede dispatch trigger "
            f"(line {trigger_line})"
        )

    def test_detection_substrings_present(self, skill, declared_tier, proceed_ref):
        """All 4 required 1M-detection substrings appear in the block."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        for substr in REQUIRED_DETECTION_SUBSTRINGS:
            assert substr in block, (
                f"[{skill}] Detection substring {substr!r} not found in precheck block"
            )

    def test_option_labels_present(self, skill, declared_tier, proceed_ref):
        """Both AskUserQuestion option labels appear verbatim in the block."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        assert OPTION_LABEL_ABORT in block, (
            f"[{skill}] Option label not found in block: {OPTION_LABEL_ABORT!r}"
        )
        assert OPTION_LABEL_PROCEED in block, (
            f"[{skill}] Option label not found in block: {OPTION_LABEL_PROCEED!r}"
        )

    def test_no_redispatch_passthrough_present(self, skill, declared_tier, proceed_ref):
        """[no-redispatch] passthrough is documented in the block."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        assert NO_REDISPATCH_HINT in block, (
            f"[{skill}] [no-redispatch] passthrough not found in block"
        )

    def test_abort_no_spawn_phrase_present(self, skill, declared_tier, proceed_ref):
        """'Do NOT spawn any Agent' appears in the block (whitespace-normalized)."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        normalized = _normalize_ws(block)
        assert ABORT_NO_SPAWN_PHRASE in normalized, (
            f"[{skill}] '{ABORT_NO_SPAWN_PHRASE}' not found in block (normalized)"
        )

    def test_no_implement_token_in_block(self, skill, declared_tier, proceed_ref):
        """No literal '/implement' remains in the block (correct skill token substituted).

        Exception: the `implement` skill itself legitimately contains '/implement'
        as its own skill token — it is the reference implementation and is not a
        substitution failure.
        """
        if skill == "implement":
            pytest.skip("implement is the reference skill; /implement is its own correct token")
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        assert "/implement" not in block, (
            f"[{skill}] '/implement' found in block — skill token substitution missing"
        )

    def test_skill_token_present_in_block(self, skill, declared_tier, proceed_ref):
        """The skill's own /<skill> token appears in the block."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        skill_token = f"/{skill}"
        assert skill_token in block, (
            f"[{skill}] Skill token {skill_token!r} not found in precheck block"
        )

    def test_proceed_ref_correct(self, skill, declared_tier, proceed_ref):
        """CRIT-1: proceed-ref assertion — §1 vs §0c per T-01 table."""
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        if proceed_ref == "§0c":
            assert "§1" not in block, (
                f"[{skill}] §0c-class skill must have NO '§1' in precheck block"
            )
            assert "§0c" in block, (
                f"[{skill}] §0c-class skill must have '§0c' in precheck block"
            )
        else:
            assert "§1" in block, (
                f"[{skill}] §1-class skill must have '§1' in precheck block (proceed-to-body refs)"
            )

    def test_dispatch_noun_correct(self, skill, declared_tier, proceed_ref):
        """MINOR-2: dispatch-tier noun assertion — haiku skills must not say Sonnet
        in user-facing Question/Option text.

        Note: the block legitimately contains `` `model: "sonnet"|"opus"|"haiku"` ``
        as fixed Agent API documentation — that line is NOT a user-facing tier noun.
        We check only the user-facing dispatch lines (the Question and Option descriptions),
        identified by the 'Dispatching /<skill> to' sentence.
        """
        text = self._read(skill)
        block = _extract_block(text, S0_BEGIN_MARKER, S0_END_MARKER)
        # Extract user-facing dispatch lines: from 'Dispatching' through the option descriptions.
        # A reliable anchor is the Question text line.
        dispatch_question_marker = f"Dispatching /{skill} to"
        dispatch_pos = block.find(dispatch_question_marker)
        assert dispatch_pos != -1, (
            f"[{skill}] 'Dispatching /{skill} to' not found in precheck block"
        )
        # Take the user-facing portion from the Question through the end of the block.
        user_facing_text = block[dispatch_pos:]

        tier_title = declared_tier.title()  # "Haiku", "Sonnet", "Opus"
        if declared_tier == "haiku":
            # The user-facing question/option text must not say Sonnet/sonnet.
            assert "Sonnet" not in user_facing_text and "sonnet" not in user_facing_text, (
                f"[{skill}] Haiku-tier skill must not have 'Sonnet'/'sonnet' in user-facing "
                f"dispatch text (after 'Dispatching /{skill} to')"
            )
            assert "haiku" in user_facing_text.lower(), (
                f"[{skill}] Haiku-tier skill must have 'haiku' (case-insensitive) in user-facing "
                f"dispatch text"
            )
        elif declared_tier == "sonnet":
            assert "Sonnet" in user_facing_text, (
                f"[{skill}] Sonnet-tier skill must have 'Sonnet' in user-facing dispatch text"
            )


# ---------------------------------------------------------------------------
# §0' parametrized tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skill", SECTION0PRIME_TARGETS)
class TestSection0PrimePrecheck:
    """All assertions from T-05 checks (a)–(e) + MAJOR-1a/d2 no-§1 + MINOR-2/d3 opus noun."""

    def _read(self, skill: str) -> str:
        path = skill_md_path(skill)
        assert path.is_file(), f"SKILL.md not found: {path}"
        return path.read_text(encoding="utf-8")

    def test_markers_present_once(self, skill):
        """Both §0prime markers appear exactly once (full literal)."""
        text = self._read(skill)
        assert text.count(S0P_BEGIN_MARKER) == 1, (
            f"[{skill}] Expected exactly 1 §0prime-begin marker, got {text.count(S0P_BEGIN_MARKER)}"
        )
        assert text.count(S0P_END_MARKER) == 1, (
            f"[{skill}] Expected exactly 1 §0prime-end marker, got {text.count(S0P_END_MARKER)}"
        )

    def test_markers_inside_section_zero_prime(self, skill):
        """Both §0prime markers sit inside ## §0' Pollution dispatch (bounded by next ## H2)."""
        text = self._read(skill)
        sec_start, sec_end = _section_bounds(text, S0P_SECTION_HEADING)
        begin_line = _line_number(text, S0P_BEGIN_MARKER)
        end_line   = _line_number(text, S0P_END_MARKER)
        assert sec_start < begin_line < sec_end, (
            f"[{skill}] §0prime-begin marker (line {begin_line}) not inside §0' section "
            f"(lines {sec_start}–{sec_end})"
        )
        assert sec_start < end_line < sec_end, (
            f"[{skill}] §0prime-end marker (line {end_line}) not inside §0' section "
            f"(lines {sec_start}–{sec_end})"
        )

    def test_begin_marker_before_dispatch_anchor(self, skill):
        """§0prime-begin marker appears before 'Dispatch action (when pollution detected'."""
        text = self._read(skill)
        begin_line  = _line_number(text, S0P_BEGIN_MARKER)
        anchor_line = _line_number(text, S0P_DISPATCH_ANCHOR)
        assert anchor_line != -1, f"[{skill}] §0' dispatch anchor not found"
        assert begin_line < anchor_line, (
            f"[{skill}] §0prime-begin (line {begin_line}) must precede dispatch anchor "
            f"(line {anchor_line})"
        )

    def test_detection_substrings_present(self, skill):
        """All 4 required 1M-detection substrings appear in the §0prime block."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        for substr in REQUIRED_DETECTION_SUBSTRINGS:
            assert substr in block, (
                f"[{skill}] Detection substring {substr!r} not found in §0prime precheck block"
            )

    def test_option_labels_present(self, skill):
        """Both option labels appear verbatim in the §0prime block."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        assert OPTION_LABEL_ABORT in block, (
            f"[{skill}] Option label not found in §0prime block: {OPTION_LABEL_ABORT!r}"
        )
        assert OPTION_LABEL_PROCEED in block, (
            f"[{skill}] Option label not found in §0prime block: {OPTION_LABEL_PROCEED!r}"
        )

    def test_no_redispatch_passthrough_present(self, skill):
        """[no-redispatch] passthrough is documented in the §0prime block."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        assert NO_REDISPATCH_HINT in block, (
            f"[{skill}] [no-redispatch] passthrough not found in §0prime block"
        )

    def test_abort_no_spawn_phrase_present(self, skill):
        """'Do NOT spawn any Agent' appears in the §0prime block (whitespace-normalized)."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        normalized = _normalize_ws(block)
        assert ABORT_NO_SPAWN_PHRASE in normalized, (
            f"[{skill}] '{ABORT_NO_SPAWN_PHRASE}' not found in §0prime block (normalized)"
        )

    def test_no_implement_token_in_block(self, skill):
        """No literal '/implement' remains in the §0prime block."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        assert "/implement" not in block, (
            f"[{skill}] '/implement' found in §0prime block — skill token substitution missing"
        )

    def test_skill_token_present_in_block(self, skill):
        """The skill's own /<skill> token appears in the §0prime block."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        skill_token = f"/{skill}"
        assert skill_token in block, (
            f"[{skill}] Skill token {skill_token!r} not found in §0prime precheck block"
        )

    def test_no_section1_ref_in_block(self, skill):
        """MAJOR-1a/d2: no literal '§1' in the §0prime block; 'skill body' present instead."""
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        assert "§1" not in block, (
            f"[{skill}] §0prime block must NOT contain '§1' (use 'skill body' instead)"
        )
        assert "skill body" in block, (
            f"[{skill}] §0prime block must contain 'skill body' (proceed-to-body reference)"
        )

    def test_opus_noun_correct(self, skill):
        """MINOR-2/d3: 'Opus'/'opus' present; no 'Sonnet'/'sonnet' in user-facing §0prime text.

        Note: the block legitimately contains `` `model: "sonnet"|"opus"|"haiku"` ``
        as fixed Agent API documentation — that line is NOT a user-facing tier noun.
        We check only the user-facing dispatch lines (the Question and Option descriptions),
        identified by the 'Dispatching /<skill> to' sentence.
        """
        text = self._read(skill)
        block = _extract_block(text, S0P_BEGIN_MARKER, S0P_END_MARKER)
        # Extract user-facing dispatch lines from the Question through end of block.
        dispatch_question_marker = f"Dispatching /{skill} to"
        dispatch_pos = block.find(dispatch_question_marker)
        assert dispatch_pos != -1, (
            f"[{skill}] 'Dispatching /{skill} to' not found in §0prime precheck block"
        )
        user_facing_text = block[dispatch_pos:]

        assert "Sonnet" not in user_facing_text and "sonnet" not in user_facing_text, (
            f"[{skill}] §0prime block user-facing text must not have 'Sonnet'/'sonnet' — use 'Opus'/'opus'"
        )
        assert "Opus" in user_facing_text or "opus" in user_facing_text, (
            f"[{skill}] §0prime block must have 'Opus'/'opus' in user-facing dispatch text"
        )
