"""Prose-contract test: /checkpoint --restore fast-path applies cross-task guard.

Background (2026-06-04 incident):
  The Tier-1 fast path returned a checkpoint immediately when
  pending-restore-${current_session_id}.txt existed and its path was valid,
  skipping ALL safety checks. A stale block-hook checkpoint with
  ## Active task = unknown-task was silently restored instead of routing to
  B3 session-state synthesis.

Fix: the fast path now applies the cross-task identity guard before returning
(fast validation, not fast bypass). Staleness is intentionally NOT evaluated
in the fast path — a same-task sentinel that is several days old still returns
fast (correct behavior; the user intends to resume the same task).

This test is a prose-contract test: it asserts on SKILL.md wording because
the picker runs inside the Claude model at runtime. Uses two region slicers
to avoid false-passes from guard tokens that already appear in the Tier-3
combined gate (which legitimately contains 'cross-task', 'B3', 'freshest_task',
'QUOIN_RESTORE_STALE_DAYS'). Each region has exactly one genuine flip assertion
confirmed to FAIL against the pre-edit SKILL.md.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Region slicers
# NOTE: Both anchors appear exactly once in the pre-edit and post-edit file.
# The L634 block is scoped deliberately: 'cross-task', 'B3', 'freshest_task',
# and 'QUOIN_RESTORE_STALE_DAYS' all appear in the Tier-3 combined gate outside
# this region — whole-file assertions would pass pre-edit and provide zero coverage.
# ---------------------------------------------------------------------------

def _fast_path_region(text: str) -> str:
    """Slice the L583 Tier-1 one-liner region (between Tier-1 and Tier-2 anchors, ~225 chars).

    Contains the Tier-1 description sentence only. The cross-task guard description
    and the 'fast validation' marker belong here after the edit.
    """
    t1 = text.find("Tier 1 — Fast path")
    t2 = text.find("Tier 2 —")
    assert t1 != -1, "Tier-1 anchor 'Tier 1 — Fast path' not found in SKILL.md"
    assert t2 != -1 and t2 > t1, "Tier-2 anchor 'Tier 2 —' not found after Tier-1 anchor"
    return text[t1:t2]


def _l634_block(text: str) -> str:
    """Slice the L634 detailed fast-path block (between 'Fast path (sub-second' and 'Full enumeration path').

    Contains the pseudocode and detailed prose for the fast-path logic.
    After the fix this block documents the cross-task guard, B3 routing,
    freshest_task derivation, and absence of staleness checks.
    """
    a = text.find("Fast path (sub-second")
    b = text.find("Full enumeration path", a)
    assert a != -1 and b != -1 and b > a, (
        "L634 fast-path block anchors not found: "
        "'Fast path (sub-second' and 'Full enumeration path' must both be present"
    )
    return text[a:b]


# ---------------------------------------------------------------------------
# L583 region assertions
# ---------------------------------------------------------------------------

class TestFastPathL583Region:
    """Assertions scoped to the Tier-1 one-liner region (~L583)."""

    def test_bypass_phrase_absent_l583(self):
        """FLIP: 'skip all enumeration' must be gone from the L583 region post-edit.

        Pre-edit: the L583 sentence read 'return that checkpoint immediately (skip all
        enumeration)' — count=1 in this region. This assertion FAILS pre-edit and PASSES
        post-edit, confirming the bypass language was removed.
        """
        text = _text()
        region = _fast_path_region(text)
        assert "skip all enumeration" not in region, (
            "checkpoint/SKILL.md Tier-1 fast-path description must not claim it skips all "
            "enumeration without applying the cross-task guard. The pre-edit phrase "
            "'return that checkpoint immediately (skip all enumeration)' must be replaced "
            "with wording that describes the cross-task validation step."
        )

    def test_fast_validation_marker_l583(self):
        """'fast validation' must appear in the L583 region after the edit."""
        text = _text()
        region = _fast_path_region(text)
        assert "fast validation" in region, (
            "checkpoint/SKILL.md Tier-1 fast-path description must use the phrase "
            "'fast validation' (or equivalent) to make clear this is validation, not bypass."
        )


# ---------------------------------------------------------------------------
# L634 block assertions
# ---------------------------------------------------------------------------

class TestFastPathL634Block:
    """Assertions scoped to the L634 detailed fast-path block."""

    def test_bypass_phrase_absent_l634(self):
        """FLIP: 'bypass all enumeration' must be gone from the L634 block post-edit.

        Pre-edit: the L634 header read 'Fast path (sub-second, bypass all enumeration):'
        — count=1 in this block. This assertion FAILS pre-edit and PASSES post-edit.
        """
        text = _text()
        block = _l634_block(text)
        assert "bypass all enumeration" not in block, (
            "checkpoint/SKILL.md L634 fast-path block header must not claim it bypasses all "
            "enumeration. The pre-edit header 'Fast path (sub-second, bypass all enumeration):' "
            "must be replaced with wording that reflects the cross-task validation step."
        )

    def test_fast_validation_marker_l634(self):
        """'fast validation' must appear in the L634 block as a post-edit-only marker."""
        text = _text()
        block = _l634_block(text)
        assert "fast validation" in block, (
            "checkpoint/SKILL.md L634 fast-path block must contain the phrase 'fast validation' "
            "to make clear the fast path validates (cross-task guard) before returning."
        )

    def test_cross_task_guard_described_in_l634(self):
        """The cross-task guard must be described in the L634 block."""
        text = _text()
        block = _l634_block(text)
        assert "cross-task" in block or "cross_task" in block, (
            "checkpoint/SKILL.md L634 fast-path block must describe the cross-task identity "
            "guard. The guard fires when cand_task != freshest_task and routes to B3."
        )

    def test_b3_routing_described_in_l634(self):
        """B3 routing on cross-task suppression must be described in the L634 block."""
        text = _text()
        block = _l634_block(text)
        assert "B3" in block, (
            "checkpoint/SKILL.md L634 fast-path block must state that a suppressed "
            "fast-path candidate routes to B3 session-state synthesis."
        )

    def test_freshest_task_variable_in_l634(self):
        """The freshest_task variable must appear in the L634 block."""
        text = _text()
        block = _l634_block(text)
        assert "freshest_task" in block, (
            "checkpoint/SKILL.md L634 fast-path block must reference the 'freshest_task' "
            "variable used by the cross-task guard."
        )

    def test_staleness_guard_absent_from_l634(self):
        """QUOIN_RESTORE_STALE_DAYS must NOT appear in the L634 block.

        Staleness evaluation belongs only in the Tier-3 combined gate. The fast path
        uses the cross-task guard only to avoid over-suppressing same-task multi-day resumes.
        """
        text = _text()
        block = _l634_block(text)
        assert "QUOIN_RESTORE_STALE_DAYS" not in block, (
            "checkpoint/SKILL.md L634 fast-path block must NOT reference QUOIN_RESTORE_STALE_DAYS. "
            "Staleness evaluation belongs only at Tier-3 (the combined gate). Including it here "
            "would over-suppress the normal save-tonight/resume-tomorrow use case."
        )

    def test_cand_age_days_absent_from_l634(self):
        """cand_age_days must NOT appear in the L634 block (staleness not evaluated here)."""
        text = _text()
        block = _l634_block(text)
        assert "cand_age_days" not in block, (
            "checkpoint/SKILL.md L634 fast-path block must NOT reference cand_age_days. "
            "Staleness is not evaluated in the fast path."
        )


# ---------------------------------------------------------------------------
# Cross-region consistency assertions
# ---------------------------------------------------------------------------

class TestFastPathCrossRegion:
    """Assertions that span both fast-path regions to catch partial edits."""

    def test_bypass_absent_from_both_regions(self):
        """'bypass all enumeration' must be absent from BOTH fast-path regions.

        Guards against editing only one block and leaving the other claiming bypass.
        """
        text = _text()
        r1 = _fast_path_region(text)
        r2 = _l634_block(text)
        assert "bypass all enumeration" not in r1 and "bypass all enumeration" not in r2, (
            "checkpoint/SKILL.md: 'bypass all enumeration' must be absent from BOTH fast-path "
            "regions (L583 one-liner and L634 detailed block). Found in: "
            f"{'L583 region' if 'bypass all enumeration' in r1 else ''}"
            f"{'L634 block' if 'bypass all enumeration' in r2 else ''}."
        )

    def test_fast_validation_in_at_least_one_region(self):
        """'fast validation' must appear in at least one fast-path region.

        Guards against editing zero regions (all assertions pass trivially from Tier-3 text).
        """
        text = _text()
        r1 = _fast_path_region(text)
        r2 = _l634_block(text)
        assert "fast validation" in r1 or "fast validation" in r2, (
            "checkpoint/SKILL.md: 'fast validation' must appear in at least one of the two "
            "fast-path regions (L583 or L634). This is the post-edit-only marker confirming "
            "that at least one fast-path block was rewritten to describe the guard."
        )


# ---------------------------------------------------------------------------
# 6-path contract table assertion
# ---------------------------------------------------------------------------

class TestContractTable:
    """The 6-path consumed_sentinel_path contract table must cover both fast-path outcomes."""

    def test_contract_table_covers_suppressed_fastpath(self):
        """The contract table must document the suppressed fast-path → B3 route outcome."""
        text = _text()
        assert "cross-task guard SUPPRESSED" in text or "SUPPRESSED → B3" in text, (
            "checkpoint/SKILL.md 6-path contract table must document the fast-path suppression "
            "case (cross-task guard fires → B3 route, consumed_sentinel_path = ''). "
            "Row 1a or an equivalent annotation is required."
        )
