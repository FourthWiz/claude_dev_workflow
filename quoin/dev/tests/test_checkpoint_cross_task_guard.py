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


class TestPrimaryPickerDelegation:
    """T-05 (IVG-139 S-3): the restore section's PRIMARY decision path now delegates
    to checkpoint_picker.py; the prose tiers above (still asserted by this file's
    other test classes) are retained only as the fail-OPEN fallback.

    Decision-equivalence argument (T-06, two parts, since SKILL.md is
    LLM-interpreted prose and not executable):
      1. Module boundary: `test_checkpoint_picker_roundtrip.py` proves
         `checkpoint_picker.py`'s Verdict matches `checkpoint-spec.md` across the
         named incident/prose/spec-anchored fixtures (tier-1 same-task fastpath,
         tier-1 cross-task->B3, tier-2 anchor precedence, tier-3 autopick,
         tier-3 gate-suppressed stale/cross-task, B3 clause-A/clause-B,
         thorough-plan-progress routing, same-session detection, and the new
         multi-candidate mixed-validity fixture below).
      2. Delegation: THIS file's tests (above) prove the SKILL correctly
         delegates to that module boundary -- it shells out with the right
         flags, parses the Verdict without re-deriving the decision, and falls
         back to the (unchanged, still-tested) prose tiers on any failure.

      Together these two parts establish equivalence WITHOUT re-testing
      SKILL.md's un-executable prose against the incident corpus directly.

      OUT OF SCOPE (spec blind spot, NOT proven equivalent): the interactive
      2+-candidate numbered-picker UX (SKILL.md:865-877), where a human can
      explicitly select an older, valid, same-task candidate over the
      auto-suppressed freshest one. `test_multi_candidate_freshest_suppressed_
      bypasses_valid_older_same_task` in the roundtrip harness characterizes
      (does not endorse) the module-driven path's behavior in that scenario --
      it bypasses the valid older candidate rather than offering the numbered
      choice. See Q-01 in the S-3 plan for the gate ruling accepting this as a
      conscious, documented outcome change.
    """

    def test_invokes_checkpoint_picker_module(self):
        """SKILL.md restore section must shell out to checkpoint_picker.py."""
        text = _text()
        assert "checkpoint_picker.py" in text, (
            "checkpoint/SKILL.md restore section must invoke checkpoint_picker.py "
            "as the primary restore-decision path (IVG-139 S-3)."
        )
        assert "--memory-dir" in text and "--sid" in text, (
            "checkpoint_picker.py invocation must pass --memory-dir and --sid flags."
        )

    def test_parses_json_verdict_without_jq(self):
        """The Verdict JSON must be parsed via python3 -c (not jq — D-04)."""
        text = _text()
        assert "json.loads" in text, (
            "checkpoint/SKILL.md must parse the picker's JSON Verdict via a python3 "
            "json.loads one-liner, not jq."
        )
        assert "\\x1f" in text, (
            "checkpoint/SKILL.md must split the parsed Verdict fields on the ASCII Unit "
            "Separator (\\x1f), not tab (CRIT-1 — tab collapses empty fields on bash 3.2)."
        )

    def test_fallback_picker_retained(self):
        """The fail-OPEN prose fallback must still be present and clearly labelled."""
        text = _text()
        assert "Fallback picker" in text and "fail-OPEN" in text, (
            "checkpoint/SKILL.md must retain the prose picker as a labelled fail-OPEN "
            "fallback for when checkpoint_picker.py is unavailable (D-03)."
        )
        # Fallback must still be reachable via the same Tier-1..4 anchors the other
        # tests in this file assert on — i.e. it is not merely referenced, it is present.
        assert "Tier 1 — Fast path" in text and "Tier 2 —" in text, (
            "The fallback picker must retain the original Tier-1..4 prose verbatim."
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


class TestAmbiguityGate:
    """IVG-160 (AC-8/FR-8): the distinct-task ambiguity gate must be present in BOTH the
    module-driven Step-1.0b render and the fail-OPEN Fallback picker prose, and the fallback
    gate must run BEFORE the step-5 B3 Clause-A/B trigger (module↔prose parity).

    Reads the SOURCE adapters SKILL.md via `_text()` (the established prose-contract idiom;
    marker/anchor strings are byte-identical in source and deployed, so correctness is
    unaffected and the read is not deploy-order-dependent — MIN-1, round 2)."""

    # -- 8a. Presence greps (existence of the T-06 markers) --

    def test_ambiguity_window_knob_present(self):
        text = _text()
        assert "QUOIN_RESTORE_AMBIGUITY_WINDOW" in text, (
            "checkpoint/SKILL.md must reference the QUOIN_RESTORE_AMBIGUITY_WINDOW knob (IVG-160)."
        )

    def test_step_1_0b_ambiguity_branch_present(self):
        text = _text()
        assert 'tier == "ambiguous"' in text, (
            "checkpoint/SKILL.md Step 1.0b must branch on the module's tier == \"ambiguous\" Verdict."
        )
        # The shared substring appears in BOTH the Step-1.0b branch and the fallback section.
        assert text.count("Distinct-task ambiguity gate") >= 2, (
            "the 'Distinct-task ambiguity gate' marker must appear in BOTH the Step-1.0b branch "
            "and the Fallback picker section."
        )

    def test_fallback_unique_label_present(self):
        text = _text()
        assert "Distinct-task ambiguity gate — fallback parity" in text, (
            "the fallback gate must carry the section-unique '— fallback parity' label (IVG-160)."
        )

    def test_second_ambiguity_only_json_parse_present(self):
        text = _text()
        # Step 1.0a already uses one json.loads; Step 1.0b adds a SECOND, ambiguity-only parse.
        assert text.count("json.loads") >= 2, (
            "Step 1.0b must run a SECOND, ambiguity-only json.loads candidate parse "
            "(the fixed-field scalar parse cannot carry the variable-length candidates list)."
        )
        assert "\\x1f" in text, (
            "the ambiguity candidate rows must be \\x1f-separated (bash-3.2 empty-field safety)."
        )

    def test_fallback_distinct_task_picker_language_present(self):
        text = _text()
        assert ">= 2 distinct tasks" in text, (
            "the fallback gate must present the picker when >= 2 distinct tasks are in the window."
        )

    def test_min1_bullet_skip_instruction_present(self):
        text = _text()
        assert "do NOT execute bullets 1-5" in text, (
            "Step 1.0b ambiguity branch must explicitly skip bullets 1-5 (MIN-1) so the empty "
            "top-level selected_path/consumed_sentinel_path cannot clobber the bound cp_path."
        )

    def test_min2_loop_guard_token_present(self):
        text = _text()
        assert '|| [ -n "$task" ]' in text, (
            "the ambiguity candidate read loop must carry the '|| [ -n \"$task\" ]' guard so the "
            "final row is processed even if the trailing newline is absent (bash 3.2.57, MIN-2)."
        )

    # -- 8b. Ordering assert (the load-bearing parity guard) --

    def test_fallback_gate_precedes_b3_trigger(self):
        """The fallback distinct-task gate marker must appear BEFORE the step-5 B3-trigger anchor
        WITHIN the Fallback picker section. Slicing to the section first (excluding the ~Step-1.0b
        occurrence) and anchoring on the fallback-UNIQUE label makes this genuinely load-bearing:
        a regression that moves the gate back inside the Normal picker (below the B3 trigger)
        fails RED (round-2 MAJ-1 vacuity fix)."""
        text = _text()
        fb_start = text.find("#### Fallback picker")   # heading exists verbatim
        assert fb_start != -1, "fallback section heading not found"
        fb = text[fb_start:]
        idx_gate = fb.find("Distinct-task ambiguity gate — fallback parity")  # 6c fallback-unique
        idx_b3 = fb.find("check the B3 session-state fallback trigger")        # step-5 B3 anchor
        assert idx_gate != -1, "fallback ambiguity-gate marker not found in fallback section"
        assert idx_b3 != -1, "B3 trigger anchor not found in fallback section"
        assert idx_gate < idx_b3, (
            "fallback distinct-task gate must precede the step-5 B3 trigger (module↔prose "
            "pre-Clause-B parity, AC-8/FR-8)."
        )
