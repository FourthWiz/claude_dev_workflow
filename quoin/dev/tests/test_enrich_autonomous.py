"""SKILL.md-lint tests for `[autonomous]` branches in /enrich (IVG-153, T-08).

Text-level guards over `enrich/SKILL.md` — assert a best-effort autonomous branch at the
gap-questions site (flagged assumptions, no blocking wait) plus the required `confidence`
emission under autonomous. The GENERATED `<!-- §0doubleprime-begin/end -->` block (owned by
T-23) is intentionally left untouched by this task.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ENRICH_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "enrich" / "SKILL.md"


@pytest.fixture(scope="module")
def enrich_skill_text() -> str:
    assert ENRICH_SKILL.exists(), f"enrich/SKILL.md not found at {ENRICH_SKILL}"
    return ENRICH_SKILL.read_text(encoding="utf-8")


def test_autonomous_sentinel_parsed_at_bootstrap(enrich_skill_text: str) -> None:
    text = enrich_skill_text
    assert "_AUTONOMOUS" in text
    assert "[autonomous]" in text


def test_gap_questions_site_autonomous_best_effort_branch(enrich_skill_text: str) -> None:
    text = enrich_skill_text
    idx = text.index("## Process")
    end = text.index("## Output")
    section = text[idx:end]

    assert "**Under `[autonomous]`:**" in section
    assert "skip `AskUserQuestion`" in section
    assert "flag" in section.lower()
    assert "assumption" in section.lower()


def test_autonomous_branch_never_blocks(enrich_skill_text: str) -> None:
    text = enrich_skill_text
    idx = text.index("## Process")
    end = text.index("## Output")
    section = text[idx:end]
    assert "never block waiting for a round-trip" in section


def test_confidence_emission_required_under_autonomous(enrich_skill_text: str) -> None:
    text = enrich_skill_text
    idx = text.index("## Output")
    section = text[idx:]
    assert "**Under `[autonomous]` (REQUIRED):**" in section
    assert "confidence: <float 0..1>" in section
    assert "minimum" in section.lower()


def test_dispatch_sites_not_hand_edited(enrich_skill_text: str) -> None:
    text = enrich_skill_text
    assert "<!-- §0doubleprime-begin -->" in text
    assert "<!-- §0doubleprime-end -->" in text


def test_normal_path_askuserquestion_still_documented(enrich_skill_text: str) -> None:
    """Non-autonomous behavior stays unchanged: the normal gap-questions path still
    documents AskUserQuestion outside the autonomous branch."""
    text = enrich_skill_text
    assert 'use `AskUserQuestion` with a SMALL, focused set of questions' in text
