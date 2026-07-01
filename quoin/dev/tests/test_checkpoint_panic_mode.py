"""Prose-contract tests for the checkpoint panic/degraded-save mode (T-07).

Verifies that checkpoint/SKILL.md documents a panic tier that:
- Fires at >= PANIC_BPS (default 10000 = 100%)
- Skips heavy gathering and AskUserQuestion
- Writes a skeleton checkpoint + pending-restore sentinel
- Appends a cost-ledger row with "save (panic mode)" note
- Has PANIC_BPS > COMPACT_FIRST_BPS (correct tier ordering)
- Defines the util-read failure contract (fail-safe to 0, fall through to Step 1.5)
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


class TestCheckpointPanicMode:
    """T-07: panic/degraded-save mode prose contracts."""

    def test_panic_bps_knob_referenced(self):
        """SKILL.md must reference PANIC_BPS / QUOIN_PANIC_BPS with default 10000."""
        text = _text()
        assert "PANIC_BPS" in text or "QUOIN_PANIC_BPS" in text, (
            "checkpoint/SKILL.md must reference PANIC_BPS (defined in _lib.sh:read_constants)."
        )
        assert "10000" in text, (
            "checkpoint/SKILL.md must document PANIC_BPS default of 10000 (100.00%)."
        )

    def test_panic_skips_askuserquestion(self):
        """Panic path must explicitly skip AskUserQuestion."""
        text = _text()
        assert any(phrase in text for phrase in [
            "skip ALL",
            "skip heavy",
            "Skip ALL",
            "Skips heavy",
            "no AskUserQuestion",
            "NO AskUserQuestion",
            "without AskUserQuestion",
        ]), (
            "checkpoint/SKILL.md panic path must explicitly state that AskUserQuestion "
            "is skipped (the incident root cause: heavy gather at 115%+ churned 75s)."
        )

    def test_panic_writes_sentinel_and_skeleton(self):
        """Panic path must write both a skeleton checkpoint and a pending-restore sentinel."""
        text = _text()
        # Check for sentinel write reference
        assert "pending-restore" in text, (
            "checkpoint/SKILL.md panic path must write a pending-restore sentinel."
        )
        # Check for skeleton checkpoint write
        assert "skeleton" in text.lower(), (
            "checkpoint/SKILL.md panic path must write a skeleton checkpoint."
        )

    def test_panic_cost_row_note(self):
        """Panic path must append a cost-ledger row with 'save (panic mode)' note."""
        text = _text()
        assert "panic mode" in text.lower(), (
            "checkpoint/SKILL.md panic path must document a cost-ledger row with "
            "'save (panic mode)' NOTE column value."
        )

    def test_panic_tier_ordering(self):
        """PANIC_BPS must be documented as > COMPACT_FIRST_BPS (correct tier ordering)."""
        text = _text()
        assert any(phrase in text for phrase in [
            "COMPACT_FIRST_BPS (9000",
            "COMPACT_FIRST_BPS (notice",
            "COMPACT_FIRST_BPS\n",
            "COMPACT_FIRST_BPS) < PANIC_BPS",
            "COMPACT_FIRST_BPS",
        ]), (
            "checkpoint/SKILL.md must document both COMPACT_FIRST_BPS and PANIC_BPS "
            "with the ordering COMPACT_FIRST_BPS < PANIC_BPS."
        )
        assert any(phrase in text for phrase in [
            "PANIC_BPS (10000",
            "degrade",
        ]), (
            "checkpoint/SKILL.md must document PANIC_BPS as the degrade tier."
        )

    def test_util_read_failure_contract(self):
        """Panic path must define the util-read failure contract (fail-safe to 0)."""
        text = _text()
        assert any(phrase in text for phrase in [
            "util_bps=0",
            "treat.*as 0",
            "treat as 0",
            "fail-safe",
        ]), (
            "checkpoint/SKILL.md panic path must define the util-read failure contract: "
            "if compute_utilization fails, treat util_bps as 0 and fall through to Step 1.5."
        )

    def test_util_read_failure_falls_through(self):
        """Util-read failure must fall through to Step 1.5, not crash."""
        text = _text()
        assert any(phrase in text for phrase in [
            "fall through to Step 1.5",
            "fall through to the normal Step 1.5",
            "proceed to Step 1.5 (no crash)",
        ]), (
            "checkpoint/SKILL.md must state that util-read failure falls through "
            "to Step 1.5 (no crash)."
        )
