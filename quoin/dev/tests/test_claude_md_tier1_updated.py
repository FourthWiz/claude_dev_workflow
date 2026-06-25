"""
Regression guard for T-01: CLAUDE.md Tier 1 section updated to v3 Class B wording.

Asserts:
  1. v2 "Contract-approval files:" heading is gone (replaced by v3 heading)
  2. v3 "Contract-approval files (v3 format):" heading is present
  3. Class B description for architecture.md is present
  4. Class B description for review-<round>.md is present
  5. cost-ledger line is preserved unchanged (append-only, no v3 changes)

Note (claude-md-trim 2026-06-25): the Tier-1 catalog was extracted from CLAUDE.md
into quoin/memory/tier1-files.md. Tests 2-5 now check tier1-files.md; test 1
checks CLAUDE.md (since the old v2 heading should not appear anywhere).
"""
import pathlib

CLAUDE_MD = pathlib.Path(__file__).parent.parent.parent / "CLAUDE.md"
TIER1_FILES_MD = pathlib.Path(__file__).parent.parent.parent / "memory" / "tier1-files.md"


def _text() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


def _tier1_text() -> str:
    return TIER1_FILES_MD.read_text(encoding="utf-8")


def test_v2_contract_approval_heading_absent():
    text = _text()
    assert "**Contract-approval files:**\n" not in text, (
        "CLAUDE.md still contains the old v2 'Contract-approval files:' heading. "
        "T-01 should have replaced it with the v3 heading."
    )


def test_v3_contract_approval_heading_present():
    # Catalog moved to tier1-files.md (claude-md-trim 2026-06-25)
    text = _tier1_text()
    assert "**Contract-approval files (v3 format):**" in text, (
        "tier1-files.md is missing the v3 'Contract-approval files (v3 format):' heading. "
        "T-01 should have introduced it."
    )


def test_architecture_class_b_description_present():
    # Catalog moved to tier1-files.md (claude-md-trim 2026-06-25)
    text = _tier1_text()
    assert "## For human" in text and "architecture.md" in text, (
        "tier1-files.md does not contain both '## For human' and 'architecture.md'. "
        "T-01 should have added the Class B description for architecture.md."
    )
    assert "body is format-aware structured per" in text, (
        "tier1-files.md is missing the Class B body description for architecture.md."
    )


def test_review_round_class_b_description_present():
    # Catalog moved to tier1-files.md (claude-md-trim 2026-06-25)
    text = _tier1_text()
    assert "review-<round>.md" in text, (
        "tier1-files.md is missing the 'review-<round>.md' Class B entry. "
        "T-01 should have added it."
    )
    assert "same v3 format as architecture.md" in text, (
        "tier1-files.md is missing the 'same v3 format as architecture.md' clause for review-<round>.md."
    )


def test_cost_ledger_line_preserved():
    # Catalog moved to tier1-files.md (claude-md-trim 2026-06-25)
    text = _tier1_text()
    assert "`<task>/cost-ledger.md` (structured, not prose" in text, (
        "tier1-files.md no longer contains the cost-ledger Tier 1 entry. "
        "T-01 must not have removed or altered the cost-ledger line."
    )
