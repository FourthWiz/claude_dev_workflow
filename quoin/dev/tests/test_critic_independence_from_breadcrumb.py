"""
test_critic_independence_from_breadcrumb.py — structural text check for R-08 mitigation.

Asserts that /critic's SKILL.md contains the hard rule requiring independent source-file
reads for every CRITICAL or MAJOR finding, and that the rule is worded to exclude
the breadcrumb file itself from satisfying the independence requirement.

No live LLM calls — all assertions are SKILL.md structural text checks. This test
confirms the rule is written in SKILL.md; it cannot confirm the rule is followed at
runtime. The residual coverage gap (R-08 runtime enforcement) is accepted per D-05.
"""

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # Claude_workflow/
CRITIC_SKILL = _PROJECT_ROOT / "quoin" / "skills" / "critic" / "SKILL.md"


def _extract_independence_section(text: str) -> str:
    match = re.search(
        r"^## Critical rule: Breadcrumb independence.+?(?=^## )",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    return match.group(0) if match else ""


def test_hard_independence_rule_verbatim():
    """The exact hard-rule phrase must appear in the Breadcrumb independence section."""
    text = CRITIC_SKILL.read_text(encoding="utf-8")
    section = _extract_independence_section(text)
    assert section, (
        "## Critical rule: Breadcrumb independence section not found in critic/SKILL.md"
    )
    required_phrase = (
        "you MUST have independently read at least one source file "
        "that is NOT `.planner-trace.md` itself"
    )
    assert required_phrase in section, (
        f"Verbatim phrase not found in Breadcrumb independence section:\n"
        f"  Expected: {required_phrase!r}\n"
        f"  Section snippet: {section[:400]!r}"
    )


def test_rule_applies_to_critical_and_major():
    """The independence rule must explicitly apply to both CRITICAL and MAJOR findings."""
    text = CRITIC_SKILL.read_text(encoding="utf-8")
    section = _extract_independence_section(text)
    assert section, (
        "## Critical rule: Breadcrumb independence section not found in critic/SKILL.md"
    )
    assert "CRITICAL" in section, (
        "'CRITICAL' not found in ## Critical rule: Breadcrumb independence section"
    )
    assert "MAJOR" in section, (
        "'MAJOR' not found in ## Critical rule: Breadcrumb independence section"
    )


def test_rule_cites_r08_rationale():
    """The independence rule must cite R-08 or mention 'shallow review' as rationale."""
    text = CRITIC_SKILL.read_text(encoding="utf-8")
    section = _extract_independence_section(text)
    assert section, (
        "## Critical rule: Breadcrumb independence section not found in critic/SKILL.md"
    )
    has_r08 = "R-08" in section
    has_shallow = "shallow review" in section.lower()
    assert has_r08 or has_shallow, (
        "Neither 'R-08' nor 'shallow review' found in ## Critical rule: Breadcrumb independence — "
        "the rationale for the rule must be cited"
    )


def test_rule_states_consequence():
    """The independence rule must state the consequence: demote or drop inadmissible findings."""
    text = CRITIC_SKILL.read_text(encoding="utf-8")
    section = _extract_independence_section(text)
    assert section, (
        "## Critical rule: Breadcrumb independence section not found in critic/SKILL.md"
    )
    has_demote = "demote" in section.lower()
    has_drop = "drop it" in section.lower() or "drop them" in section.lower() or (
        "drop" in section.lower()
    )
    assert has_demote or has_drop, (
        "Neither 'demote' nor 'drop' found in ## Critical rule: Breadcrumb independence — "
        "the consequence for breadcrumb-only findings must be stated"
    )


def test_rule_section_position():
    """Breadcrumb independence section must appear AFTER Fresh context and BEFORE Process."""
    text = CRITIC_SKILL.read_text(encoding="utf-8")
    idx_fresh = text.find("## Critical rule: Fresh context")
    idx_independence = text.find("## Critical rule: Breadcrumb independence")
    idx_process = text.find("## Process")

    assert idx_fresh != -1, (
        "'## Critical rule: Fresh context' not found in critic/SKILL.md"
    )
    assert idx_independence != -1, (
        "'## Critical rule: Breadcrumb independence' not found in critic/SKILL.md"
    )
    assert idx_process != -1, (
        "'## Process' not found in critic/SKILL.md"
    )

    assert idx_fresh < idx_independence, (
        "## Critical rule: Breadcrumb independence must appear AFTER ## Critical rule: Fresh context"
    )
    assert idx_independence < idx_process, (
        "## Critical rule: Breadcrumb independence must appear BEFORE ## Process"
    )


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
