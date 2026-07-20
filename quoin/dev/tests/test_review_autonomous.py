"""SKILL.md-lint tests for `[autonomous]` propagation in /review (IVG-153, T-11).

Text-level guards over `review/SKILL.md` — assert (a) `[autonomous]` is parsed at
bootstrap and the §0'/§0" dispatch blocks are left untouched (owned by T-23) so their
autonomous path proceeds fail-OPEN without AskUserQuestion; (b) review does NOT itself
auto-resolve a BLOCKED verdict (that stays a run-level hard stop); (c) the fan-out spawn
blocks (security_review + performance/architecture-integration dimension subagents)
carry the `[autonomous]` re-prefix under autonomous mode.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "review" / "SKILL.md"


@pytest.fixture(scope="module")
def review_skill_text() -> str:
    assert REVIEW_SKILL.exists(), f"review/SKILL.md not found at {REVIEW_SKILL}"
    return REVIEW_SKILL.read_text(encoding="utf-8")


def _fanout_section(text: str) -> str:
    idx = text.index("## Profile detection and fan-out")
    end = text.index("## Review process")
    return text[idx:end]


def test_autonomous_sentinel_parsed_at_bootstrap(review_skill_text: str) -> None:
    text = review_skill_text
    assert "_AUTONOMOUS" in text
    assert "[autonomous]" in text


def test_doubleprime_dispatch_block_not_hand_edited(review_skill_text: str) -> None:
    text = review_skill_text
    assert "<!-- §0doubleprime-begin -->" in text
    assert "<!-- §0doubleprime-end -->" in text


def test_doubleprime_block_proceeds_fail_open_without_askuserquestion_documented(
    review_skill_text: str,
) -> None:
    """The generated §0'/§0'' block (owned by T-23) documents a fail-OPEN path; this
    body task does not hand-edit it but the surrounding contract must still describe
    fail-OPEN behavior on dispatch failure."""
    text = review_skill_text
    idx = text.index("<!-- §0doubleprime-begin -->")
    end = text.index("<!-- §0doubleprime-end -->")
    section = text[idx:end]
    assert "Fail-OPEN path" in section


def test_review_never_auto_resolves_blocked(review_skill_text: str) -> None:
    section = _fanout_section(review_skill_text)
    assert "never auto-resolves a BLOCKED" in section
    assert "run/SKILL.md" in section


def test_fanout_spawns_carry_autonomous_reprefix(review_skill_text: str) -> None:
    section = _fanout_section(review_skill_text)
    assert "`[autonomous]` propagation" in section
    assert "/security_review" in section
    assert "performance" in section.lower()
    assert "architecture/integration" in section.lower() or "architecture-integration" in section.lower()
    assert "re-prefix" in section.lower()


def test_large_only_security_review_spawn_prefixed(review_skill_text: str) -> None:
    section = _fanout_section(review_skill_text)
    idx = section.index("Large ONLY")
    large_only_bullet = section[idx : idx + 600]
    assert "[autonomous]" in large_only_bullet
    assert "`_AUTONOMOUS`" in large_only_bullet


def test_verdict_emission_unchanged(review_skill_text: str) -> None:
    text = review_skill_text
    assert "`APPROVED`, `CHANGES_REQUESTED`, or `BLOCKED`" in text
