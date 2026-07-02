"""Prose-contract tests for IVG-105: same-session restore detection.

These tests verify that checkpoint/SKILL.md documents the same-session detection
step (Step 1.5) that fires after the picker resolves a checkpoint and before
Step 2 surfaces the state.

Scenario:
  - User runs /checkpoint (saves in session S)
  - User stays in session S (or returns post-compact) and runs /checkpoint --restore
  - Step 1.5 detects ckpt_sid == current_session_id → shows AskUserQuestion warning

These are prose-contract tests (text inspection) — the runtime logic runs inside
the Claude model; we verify the specification is written correctly.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = (
    REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"
)


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


class TestCheckpointSameSessionRestore:
    """IVG-105: same-session detection in /checkpoint --restore."""

    def test_same_session_heading_present(self):
        """checkpoint/SKILL.md must contain the same-session detection heading."""
        text = _text()
        assert "Same-session" in text or "same-session" in text, (
            "checkpoint/SKILL.md must contain a 'Same-session' detection step."
        )

    def test_same_session_header_text(self):
        """AskUserQuestion header must be 'Same-session restore detected'."""
        text = _text()
        assert "Same-session restore detected" in text, (
            "checkpoint/SKILL.md must document AskUserQuestion header "
            "'Same-session restore detected'."
        )

    def test_session_id_awk_extraction(self):
        """SKILL.md must document awk extraction using the ckpt_sid variable (restore-mode specific)."""
        text = _text()
        assert "ckpt_sid" in text, (
            "checkpoint/SKILL.md must define 'ckpt_sid' variable for same-session "
            "detection (only introduced by T-01 restore-mode step, not present before)."
        )

    def test_same_session_comparison_variable(self):
        """SKILL.md must define _SAME_SESSION comparison variable."""
        text = _text()
        assert "_SAME_SESSION" in text, (
            "checkpoint/SKILL.md must define _SAME_SESSION variable for same-session check."
        )

    def test_fail_open_on_unknown_sid(self):
        """Same-session check must fail-OPEN when SID is unknown or empty."""
        text = _text()
        # Fail-open conditions: either mentions 'unknown' in context of same-session
        # or 'Fail-OPEN' near the detection step
        assert "unknown" in text and "_SAME_SESSION" in text, (
            "checkpoint/SKILL.md must document fail-OPEN: skip same-session check when "
            "SID is 'unknown' or empty."
        )

    def test_option_b_stops_does_not_restore(self):
        """Option B must print fresh-session guide and STOP (not proceed to Step 2)."""
        text = _text()
        assert "do NOT proceed to Step 2" in text, (
            "checkpoint/SKILL.md option B must explicitly state 'do NOT proceed to Step 2' "
            "— this phrase is only present after T-01 is applied."
        )

    def test_step_ordering_before_step2(self):
        """'Same-session detection' heading must appear textually before Step 2 in the file."""
        text = _text()
        idx_15 = text.find("Same-session detection")
        idx_s2 = text.find("### Step 2: Surface checkpoint")
        assert idx_15 != -1, (
            "checkpoint/SKILL.md must contain 'Same-session detection' heading (restore-mode Step 1.5)."
        )
        assert idx_s2 != -1, "checkpoint/SKILL.md must contain '### Step 2: Surface checkpoint'."
        assert idx_15 < idx_s2, (
            "Step 1.5 'Same-session detection' must appear BEFORE "
            "'### Step 2: Surface checkpoint state' in checkpoint/SKILL.md."
        )

    def test_tier1_fast_path_routes_through_step15(self):
        """Tier-1 fast path must route through Step 1.5, not bypass it directly to Step 2."""
        text = _text()
        # After T-01's reroute, the Tier-1 fast path language must reference Step 1.5
        # using the disambiguated phrase "proceed to Step 1.5 (same-session detection)".
        # NOTE: bare "proceed to Step 1.5" exists pre-T-01 (save-mode line ~280); the
        # parenthetical disambiguator is the only reliable guard.
        assert "proceed to Step 1.5 (same-session detection)" in text, (
            "checkpoint/SKILL.md Tier-1 fast path must route through Step 1.5 "
            "(same-session detection) rather than returning immediately to Step 2. "
            "The string 'proceed to Step 1.5 (same-session detection)' is only present "
            "after T-01's reroute is applied."
        )
