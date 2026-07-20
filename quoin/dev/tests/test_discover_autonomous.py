"""SKILL.md-lint tests for `[autonomous]` branches in /discover (IVG-153, T-22).

Text-level guards over `discover/SKILL.md` — assert the `[autonomous]` sentinel is parsed
at bootstrap into `_AUTONOMOUS`, and that the repo main spec offer (the two GENUINE
non-dispatch prompts: DRAFT when `.workflow_artifacts/spec.md` is absent, REFRESH when
present) is entirely auto-skipped under autonomous, with a dedicated assertion that
autonomous mode never writes `.workflow_artifacts/spec.md` (the repo main spec is
human-owned; autonomous must not fabricate it). The GENERATED
`<!-- §0doubleprime-begin/end -->` block (owned by T-23) is intentionally left untouched
by this task.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DISCOVER_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "discover" / "SKILL.md"


@pytest.fixture(scope="module")
def discover_skill_text() -> str:
    assert DISCOVER_SKILL.exists(), f"discover/SKILL.md not found at {DISCOVER_SKILL}"
    return DISCOVER_SKILL.read_text(encoding="utf-8")


def test_autonomous_sentinel_parsed_at_bootstrap(discover_skill_text: str) -> None:
    text = discover_skill_text
    assert "_AUTONOMOUS" in text
    assert "[autonomous]" in text
    assert "Autonomous mode bootstrap" in text


def test_repo_spec_offer_section_has_autonomous_skip_branch(discover_skill_text: str) -> None:
    text = discover_skill_text
    idx = text.index("### Repo main spec (optional offer)")
    end = text.index("Tell the user:")
    section = text[idx:end]

    assert "**Autonomous mode:**" in section
    assert "skip this entire offer" in section
    assert "do NOT call `AskUserQuestion`" in section


def test_autonomous_never_writes_spec_md(discover_skill_text: str) -> None:
    """Dedicated assertion: under autonomous, discover must NEVER auto-write or
    auto-modify .workflow_artifacts/spec.md — the repo main spec is human-owned."""
    text = discover_skill_text
    idx = text.index("### Repo main spec (optional offer)")
    end = text.index("Tell the user:")
    section = text[idx:end]

    assert "**Autonomous mode:**" in section
    autonomous_idx = section.index("**Autonomous mode:**")
    # The autonomous clause itself (up to the next bullet describing the interactive
    # DRAFT branch) must explicitly rule out writing spec.md.
    next_bullet_idx = section.index(
        "- If `.workflow_artifacts/spec.md` is ABSENT", autonomous_idx
    )
    autonomous_clause = section[autonomous_idx:next_bullet_idx]
    assert "NEVER auto-write" in autonomous_clause
    assert "spec.md" in autonomous_clause
    assert "human-owned" in autonomous_clause


def test_autonomous_branch_covers_both_draft_and_refresh_sites(discover_skill_text: str) -> None:
    """The single autonomous branch must gate BOTH the absent-spec DRAFT prompt (L543)
    and the present-spec REFRESH prompt (L546)."""
    text = discover_skill_text
    idx = text.index("### Repo main spec (optional offer)")
    end = text.index("Tell the user:")
    section = text[idx:end]
    autonomous_idx = section.index("**Autonomous mode:**")
    next_bullet_idx = section.index(
        "- If `.workflow_artifacts/spec.md` is ABSENT", autonomous_idx
    )
    autonomous_clause = section[autonomous_idx:next_bullet_idx]
    assert "absent" in autonomous_clause.lower()
    assert "DRAFT" in autonomous_clause
    assert "REFRESH" in autonomous_clause


def test_dispatch_sites_not_hand_edited(discover_skill_text: str) -> None:
    text = discover_skill_text
    assert "<!-- §0doubleprime-begin -->" in text
    assert "<!-- §0doubleprime-end -->" in text


def test_normal_path_askuserquestion_still_documented(discover_skill_text: str) -> None:
    """Non-autonomous behavior stays unchanged: the normal offer still documents
    AskUserQuestion for both the DRAFT and REFRESH prompts."""
    text = discover_skill_text
    assert "`AskUserQuestion` offering to DRAFT a repo main spec" in text
    assert "`AskUserQuestion` offering to REFRESH it" in text
