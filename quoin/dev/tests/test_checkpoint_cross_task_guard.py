"""Prose-contract tests for the checkpoint restore picker hardening.

Covers:
- T-04: cross-task identity guard (combined auto-pick gate)
- T-05: staleness guard (QUOIN_RESTORE_STALE_DAYS knob, OR semantics)
- T-06: pending-prompt cross-reference (Step 1.0 anchor preamble, all-iteration,
        no-pending-restore fallthrough, .workflow_artifacts/memory path discipline)
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


class TestCrossTaskGuard:
    """T-04: cross-task identity guard at auto-pick."""

    def test_cross_task_guard_present(self):
        """SKILL.md must describe comparing candidate task vs freshest session-state task."""
        text = _text()
        assert "cross-task" in text.lower() or "cross_task" in text, (
            "checkpoint/SKILL.md picker must contain a cross-task identity guard "
            "comparing the candidate '## Active task' against the freshest session-state task."
        )

    def test_cross_task_guard_suppresses_silent_autopick(self):
        """When candidate task != freshest session task, prose must mandate suppressing auto-pick."""
        text = _text()
        # Must mention that mismatch → suppress or loud warning or B3 routing
        assert any(phrase in text for phrase in [
            "auto-pick suppressed",
            "suppress auto-pick",
            "suppress silent auto-pick",
            "LOUD WARNING",
            "loud warning",
        ]), (
            "checkpoint/SKILL.md must state that a cross-task mismatch suppresses "
            "silent auto-pick and emits a loud warning (routing to B3 synthesis)."
        )

    def test_cross_task_routes_to_b3(self):
        """Cross-task suppression must route to B3 session-state synthesis."""
        text = _text()
        assert "B3" in text and "synthesis" in text.lower(), (
            "checkpoint/SKILL.md must route suppressed auto-pick to B3 synthesis."
        )


class TestStalenessGuard:
    """T-05: staleness guard (age-based)."""

    def test_restore_stale_days_knob_present(self):
        """SKILL.md must contain the QUOIN_RESTORE_STALE_DAYS inline knob with default 1."""
        text = _text()
        assert "QUOIN_RESTORE_STALE_DAYS" in text, (
            "checkpoint/SKILL.md picker must reference QUOIN_RESTORE_STALE_DAYS."
        )
        assert ":-1" in text, (
            "QUOIN_RESTORE_STALE_DAYS must have default value 1 (inline ':-1')."
        )

    def test_staleness_suppresses_autopick(self):
        """When candidate is older than threshold AND fresher session-state exists, suppress auto-pick."""
        text = _text()
        # Must mention that stale + fresher session-state → suppress
        assert "stale" in text.lower(), (
            "checkpoint/SKILL.md must describe the staleness guard that suppresses "
            "silent auto-pick when the candidate is too old."
        )

    def test_combined_gate_or_semantics(self):
        """The combined gate (D-03) must use OR semantics: stale OR cross-task → suppress."""
        text = _text()
        # Look for the OR gate pattern
        assert any(phrase in text for phrase in [
            "stale=1 ] || [ \"$cross_task",
            "stale OR cross_task",
            "stale\" -eq 1 ] || [ \"$cross",
            "if [ \"$stale\" -eq 1 ] || [ \"$cross_task",
        ]), (
            "checkpoint/SKILL.md must implement the combined gate with OR semantics: "
            "suppress auto-pick if EITHER stale OR cross-task. "
            "Expected to find 'stale OR cross_task' or equivalent shell OR expression."
        )


class TestPendingPromptCrossRef:
    """T-06: pending-prompt cross-reference (Step 1.0 anchor preamble)."""

    def test_step_1_0_preamble_present(self):
        """SKILL.md must describe a Step 1.0 or equivalent anchor-selection preamble."""
        text = _text()
        assert "Step 1.0" in text or "Anchor selection" in text or "anchor selection" in text, (
            "checkpoint/SKILL.md restore mode must describe a Step 1.0 anchor-selection "
            "preamble establishing the 4-tier priority order."
        )

    def test_four_tier_priority_documented(self):
        """SKILL.md must document at least 4 priority tiers for restore anchor selection."""
        text = _text()
        assert "Tier 1" in text and "Tier 2" in text and "Tier 3" in text and "Tier 4" in text, (
            "checkpoint/SKILL.md must document a 4-tier anchor-selection priority order."
        )

    def test_pending_prompt_enumeration_iterates_all(self):
        """Tier-2 must iterate ALL in-window pending-prompt sentinels, not stop at first."""
        text = _text()
        assert "pending-prompt-" in text, (
            "checkpoint/SKILL.md must enumerate pending-prompt-<SID> sentinels in tier-2."
        )
        # Must iterate (loop / for / all)
        assert any(phrase in text for phrase in [
            "iterate ALL",
            "enumerate ALL",
            "ALL in-window pending-prompt",
            "all in-window",
        ]), (
            "checkpoint/SKILL.md tier-2 must iterate ALL in-window pending-prompt-*.txt "
            "sentinels (mtime-descending), not stop at the first one found."
        )

    def test_no_pending_restore_fallthrough(self):
        """When tier-2 finds no valid anchor, it must fall through gracefully."""
        text = _text()
        assert any(phrase in text for phrase in [
            "no silent failure",
            "fallthrough",
            "fall through",
            "fall-through",
            "Explicit fallthrough",
        ]), (
            "checkpoint/SKILL.md tier-2 must document graceful fallthrough when "
            "no pending-prompt resolves to a valid anchor."
        )

    def test_enumeration_path_uses_workflow_artifacts(self):
        """Tier-2 enumeration path must use .workflow_artifacts/memory, not bare 'memory'."""
        text = _text()
        assert ".workflow_artifacts/memory" in text, (
            "checkpoint/SKILL.md tier-2 enumeration path must be '.workflow_artifacts/memory' "
            "(cwd-from-stdin discipline, lesson 2026-05-16) — not bare 'memory'."
        )
