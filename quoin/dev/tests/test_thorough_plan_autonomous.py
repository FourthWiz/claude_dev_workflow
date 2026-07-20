"""SKILL.md-lint tests for `[autonomous]` branches in /thorough_plan (IVG-153, T-05).

Text-level guards over `thorough_plan/SKILL.md` — assert the required autonomous
branches/keywords are present at each of the 5 genuine interactive sites, mirroring
the repo's existing SKILL.md-lint test style (grep the source, not a runtime harness).
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TP_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "thorough_plan" / "SKILL.md"


@pytest.fixture(scope="module")
def tp_skill_text() -> str:
    assert TP_SKILL.exists(), f"thorough_plan/SKILL.md not found at {TP_SKILL}"
    return TP_SKILL.read_text(encoding="utf-8")


def test_autonomous_sentinel_parsed_at_bootstrap(tp_skill_text: str) -> None:
    text = tp_skill_text
    assert "_AUTONOMOUS" in text
    assert "[autonomous]" in text


def test_site_1_resume_prompt_autonomous_branch(tp_skill_text: str) -> None:
    """Site 1: §1b resume-detection — both the 2-option and same-session 3-option variants."""
    text = tp_skill_text
    normalized = " ".join(text.split())
    assert "**Under `[autonomous]`:** skip the `AskUserQuestion` entirely in both variants" in normalized
    # Dedicated assertion: selects "Resume" and explicitly NOT "new session"/STOP.
    assert "auto-select option **(a) Resume**" in normalized
    assert "NEVER auto-select **(c) Resume in a new session**" in normalized
    assert "STOP instructions and halts" in normalized


def test_site_2_enrich_pre_step_autonomous_branch(tp_skill_text: str) -> None:
    """Site 2: §3b-1 enrich pre-step — skip/best-effort."""
    text = tp_skill_text
    idx = text.index("### 3b-1. Enrich pre-step")
    section = text[idx: idx + 2500]
    assert "**Under `[autonomous]`:**" in section
    assert "best-effort" in section.lower()
    assert "skip the `AskUserQuestion`" in section


def test_site_3_spec_preflight_autonomous_branch(tp_skill_text: str) -> None:
    """Site 3: §3c spec pre-flight — skip-if-spec-exists else non-interactive."""
    text = tp_skill_text
    idx = text.index("### 3c. Spec pre-flight")
    section = text[idx: idx + 2000]
    assert "**Under `[autonomous]`:**" in section
    assert "spec.md` already exists" in section
    assert "run `/specify` non-interactively" in section


def test_site_4_autoclassify_confirm_autonomous_branch(tp_skill_text: str) -> None:
    """Site 4: 1c auto-classify confirm (PROSE, not an AskUserQuestion token)."""
    text = tp_skill_text
    idx = text.index("1c. **Auto-classification**")
    section = text[idx: idx + 1200]
    assert "**Under `[autonomous]`:**" in section
    assert "accept the auto-classified profile" in section


def test_site_5_same_class_escalation_autonomous_branch(tp_skill_text: str) -> None:
    """Site 5: same-class escalation (rule 3 + the same-class-detection paragraph)."""
    text = tp_skill_text

    idx_rule3 = text.index("3. **Stuck in a loop**")
    section_rule3 = text[idx_rule3: idx_rule3 + 1200]
    assert "**Under `[autonomous]`:**" in section_rule3
    assert "auto-select **(a) continue revising**" in section_rule3
    assert "max_rounds" in section_rule3

    idx_detect = text.index("**Same-class detection:**")
    section_detect = text[idx_detect: idx_detect + 800]
    assert "**Under `[autonomous]`:**" in section_detect


def test_deeper_spawns_reprefixed_autonomous(tp_skill_text: str) -> None:
    """The /plan, /critic, /revise, /revise-fast spawn instructions carry the
    [autonomous] re-prefix rule under autonomous."""
    text = tp_skill_text
    assert "Autonomous re-prefix (`[autonomous]` transitive propagation)" in text
    idx = text.index("Autonomous re-prefix")
    section = text[idx: idx + 900]
    assert "/plan" in section
    assert "/critic" in section
    assert "/revise" in section
    assert "/revise-fast" in section
    assert "prefix `[autonomous]` onto EVERY spawn prompt below" in section
