"""SKILL.md-lint tests for the /specify non-interactive autonomous degrade (IVG-153, T-07).

Text-level guards over `specify/SKILL.md` (and its runtime-neutral core mirror) — assert
the autonomous branch does NOT call AskUserQuestion for elicitation, writes a `confidence`
frontmatter field, and auto-rejects the repo-spec update gate. The GENERATED
`<!-- §0doubleprime-begin/end -->` block (owned by T-23) is intentionally left untouched.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPECIFY_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "specify" / "SKILL.md"
SPECIFY_CORE = REPO_ROOT / "quoin" / "core" / "skills" / "specify.md"


@pytest.fixture(scope="module")
def specify_skill_text() -> str:
    assert SPECIFY_SKILL.exists(), f"specify/SKILL.md not found at {SPECIFY_SKILL}"
    return SPECIFY_SKILL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def specify_core_text() -> str:
    assert SPECIFY_CORE.exists(), f"core/skills/specify.md not found at {SPECIFY_CORE}"
    return SPECIFY_CORE.read_text(encoding="utf-8")


def test_autonomous_sentinel_parsed_at_bootstrap(specify_skill_text: str) -> None:
    text = specify_skill_text
    assert "_AUTONOMOUS" in text
    assert "[autonomous]" in text


def test_autonomous_branch_does_not_call_askuserquestion_for_elicitation(specify_skill_text: str) -> None:
    """(a) The [autonomous] degrade branch skips AskUserQuestion-based elicitation."""
    text = specify_skill_text
    idx = text.index("### Non-interactive degrade")
    # Slice up to (not including) "## Writing the spec" so we only inspect the degrade section.
    end = text.index("## Writing the spec")
    section = text[idx:end]

    assert "**Under `[autonomous]`" in section
    assert "skip the `AskUserQuestion`-based elicitation above" in section
    assert "do not wait for a round-trip" in section

    # Negative: the degrade section itself must not instruct calling AskUserQuestion.
    assert "AskUserQuestion(" not in section
    assert "Use the `AskUserQuestion` tool" not in section


def test_autonomous_branch_writes_confidence_frontmatter(specify_skill_text: str) -> None:
    """(b) The branch writes a `confidence` frontmatter field."""
    text = specify_skill_text
    assert "confidence: <float 0..1>" in text
    # Present in both the degrade-section description and the frontmatter write-site.
    assert text.count("confidence") >= 3
    idx = text.index("**Frontmatter (YAML):**")
    frontmatter_section = text[idx: idx + 900]
    assert "confidence" in frontmatter_section


def test_repo_spec_gate_autoreject_under_autonomous(specify_skill_text: str) -> None:
    """(c) The repo-spec update gate auto-rejects under autonomous."""
    text = specify_skill_text
    idx = text.index("## Repo main spec update check")
    section = text[idx:]
    assert "**Under `[autonomous]`:**" in section
    assert 'Option 2: "Reject' in section
    assert "NEVER auto-write" in section or "NEVER auto-writes" in section


def test_confidence_allowed_additive_frontmatter_key(specify_skill_text: str) -> None:
    """validate_artifact-compatible note that `confidence` is an allowed frontmatter key
    (V-01 only parses YAML — no schema break)."""
    normalized = " ".join(specify_skill_text.split())
    assert "ALLOWED additive frontmatter key" in normalized
    assert "V-01" in normalized


def test_dispatch_sites_not_hand_edited(specify_skill_text: str) -> None:
    """§0'/§0″ dispatch sites are covered by the T-23 generator change, not hand-edited here."""
    text = specify_skill_text
    assert "<!-- §0doubleprime-begin -->" in text
    assert "<!-- §0doubleprime-end -->" in text
    assert "generator-owned mechanism" in text


def test_core_mirror_documents_autonomous_degrade(specify_core_text: str) -> None:
    text = specify_core_text
    assert "Autonomous non-interactive degrade" in text
    assert "confidence" in text
    assert "auto-reject" in text.lower()


def test_specify_askuserquestion_not_removed_from_normal_path(specify_skill_text: str) -> None:
    """Non-autonomous behavior stays byte-unchanged: the normal elicitation path still
    documents AskUserQuestion outside the autonomous degrade branch."""
    text = specify_skill_text
    assert "Use the `AskUserQuestion` tool to draw out the shape of the feature" in text
