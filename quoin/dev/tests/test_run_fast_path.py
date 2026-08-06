"""Tests for IVG-246 `run/SKILL.md` fast-path-triage prose (T-05 onward).

T-05 covers `fast:` tag parsing: the token must be documented as stripped in
the same "Parse input and determine task profile" block as `strict:` /
`small:`/`medium:`/`large:` / `max_rounds:`, ORTHOGONAL to (composable with)
the profile tags, and stripped before the derived task name — the same
non-pollution treatment already given to `--autonomous` and `strict:`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_SOURCE_ROOT = _REPO_ROOT / "quoin"
_RUN_SKILL = _SOURCE_ROOT / "adapters" / "claude" / "skills" / "run" / "SKILL.md"


@pytest.fixture(scope="module")
def run_skill_text() -> str:
    assert _RUN_SKILL.exists(), f"run/SKILL.md not found at {_RUN_SKILL}"
    return _RUN_SKILL.read_text(encoding="utf-8")


def _parse_block(text: str) -> str:
    start = text.index("### Parse input and determine task profile")
    end = text.index("### Determine task name", start)
    return text[start:end]


def test_fast_tag_stripping(run_skill_text: str) -> None:
    block = _parse_block(run_skill_text)

    assert "`fast:`" in block, (
        "the 'fast:' tag must be documented in the same "
        "'Parse input and determine task profile' block as strict:/small:/"
        "medium:/large:/max_rounds:"
    )
    # It's documented alongside the other stripped tokens in this same block.
    assert "`strict:`" in block
    assert "`small:`" in block
    assert "`max_rounds:" in block

    # Explicitly stripped before profile classification / task-name
    # derivation — same non-pollution treatment as --autonomous / strict:.
    assert "Strip the token" in block or "Strip token" in block
    assert "task name" in block.lower(), (
        "the block must document that 'fast:' does not reach the derived "
        "task name (AC-3)"
    )

    # Orthogonal / composable with profile tags — not mutually exclusive.
    assert "ORTHOGONAL" in block or "orthogonal" in block


def test_fast_tag_composable_with_profile_example(run_skill_text: str) -> None:
    """The block must give a concrete composability example (a `fast:` +
    profile-tag combination) showing the profile tag still wins for
    profile purposes while `fast:` independently forces route evaluation."""
    block = _parse_block(run_skill_text)
    assert "fast: large:" in block or "fast:` `large:`" in block or (
        "fast:" in block and "large:" in block and "route" in block.lower()
    )


# ─── T-06: Phase 1.6 section — routing, modes, evidence ladder, eligibility ──

def _phase_1_6_section(text: str) -> str:
    start = text.index("## Phase 1.6 — Fast-path triage (conditional)")
    end = text.index("## Phase 2 — Architect", start)
    return text[start:end]


def test_evidence_ladder_documented(run_skill_text: str) -> None:
    section = _phase_1_6_section(run_skill_text)
    assert "spec.md" in section
    assert "enriched-prompt.md" in section
    assert "raw task description" in section
    # Precedence order (D-04a): spec.md, else enriched-prompt.md, else raw description.
    spec_idx = section.index("spec.md")
    enriched_idx = section.index("enriched-prompt.md")
    raw_idx = section.index("raw task description")
    assert spec_idx < enriched_idx < raw_idx, (
        "evidence ladder must be documented in precedence order: spec.md, "
        "then enriched-prompt.md, then the raw task description"
    )


def test_eligibility_criteria_explicit_and_stricter_than_small(run_skill_text: str) -> None:
    section = _phase_1_6_section(run_skill_text)
    # The five-way eligibility conjunction (D-10), written out verbatim.
    assert "single module" in section
    assert "cross-module" in section or "cross-repo" in section
    assert "pattern already present" in section
    assert "data migration" in section
    assert "public-contract change" in section
    assert "implementation checklist" in section
    assert "stricter" in section.lower(), (
        "the section must state that fast-path eligibility is stricter than "
        "the existing Small-task threshold"
    )


def test_ledger_phase_is_triage_not_roster_name(run_skill_text: str) -> None:
    section = _phase_1_6_section(run_skill_text)
    assert "phase `triage`" in section or "phase 'triage'" in section
    assert "fast_path_triage" in section
    assert "different string" in section or "DIFFERENT string" in section, (
        "the section must state, in its own prose, that the ledger phase "
        "('triage') and the roster/sentinel name ('fast_path_triage') are "
        "deliberately different strings (D-11)"
    )


def test_no_table_in_guarded_slice_line_66_to_resume_heading(run_skill_text: str) -> None:
    """P-03b span rule, targeted: from the FIRST occurrence of the checkpoint
    heading literal (the inline mention near line 66, in "Parse input and
    determine task profile") to the REAL `## Checkpoint interaction
    protocol` heading itself, there must be ZERO pipe-leading (table) lines.
    This is the exact span every Phase 1.6-adjacent task (T-05 through T-13)
    writes into; the real checkpoint table lives only after its own heading,
    so a zero baseline here is non-vacuous and catches any table sneaking
    into the new prose specifically (distinct from T-04's whole-span
    baseline-count guard, which tolerates the real table's 8 rows)."""
    text = run_skill_text
    first_mention = text.index("## Checkpoint interaction protocol")
    real_heading = text.index("## Checkpoint interaction protocol", first_mention + 1)
    sub_slice = text[first_mention:real_heading]

    pipe_lines = [line for line in sub_slice.splitlines() if line.strip().startswith("|")]
    assert pipe_lines == [], (
        f"found {len(pipe_lines)} pipe-leading (table) line(s) between the first "
        f"'## Checkpoint interaction protocol' mention and its real heading — "
        f"P-03b forbids adding a table anywhere in this span: {pipe_lines}"
    )
