"""T-06 (presence): Static test that phase-boundary checkpoint instructions are present
in thorough_plan/SKILL.md (IVG-98).

Checks:
  - '## Phase-boundary checkpoints' heading is present
  - 'thorough-plan:round-' token is present (stage token format)
  - 'thorough_plan_checkpoint.py' is referenced (helper invocation)
  - Checkpoint triggers exist for plan, critic, and revise boundaries
  - fail-OPEN pattern is present ('|| true' or 'fail-OPEN')
  - '2>/dev/null || echo unknown' is present (fail-OPEN UUID/branch acquisitions)
  - Resume-detection reference ('thorough-plan-progress-') is present (T-04 scan)
  - '## Last user intent' is referenced (checkpoint format completeness)
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
THOROUGH_PLAN_SKILL = (
    REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "thorough_plan" / "SKILL.md"
)


def _read() -> str:
    assert THOROUGH_PLAN_SKILL.exists(), (
        f"thorough_plan/SKILL.md not found at {THOROUGH_PLAN_SKILL}"
    )
    return THOROUGH_PLAN_SKILL.read_text(encoding="utf-8")


class TestThoroughPlanPhaseCheckpointPresent:
    """Phase-boundary checkpoint presence assertions (IVG-98 T-06)."""

    def test_phase_boundary_heading_present(self):
        """SKILL.md must contain '## Phase-boundary checkpoints' heading."""
        text = _read()
        assert "## Phase-boundary checkpoints" in text, (
            "thorough_plan/SKILL.md is missing '## Phase-boundary checkpoints' heading"
        )

    def test_stage_token_format_present(self):
        """SKILL.md must reference the stage token format 'thorough-plan:round-'."""
        text = _read()
        assert "thorough-plan:round-" in text, (
            "thorough_plan/SKILL.md is missing the stage token 'thorough-plan:round-'"
        )

    def test_helper_script_referenced(self):
        """SKILL.md must reference 'thorough_plan_checkpoint.py'."""
        text = _read()
        assert "thorough_plan_checkpoint.py" in text, (
            "thorough_plan/SKILL.md is missing 'thorough_plan_checkpoint.py' invocation"
        )

    def test_plan_boundary_trigger_present(self):
        """SKILL.md must have a checkpoint trigger for the plan boundary."""
        text = _read()
        assert "--phase plan" in text, (
            "thorough_plan/SKILL.md is missing '--phase plan' boundary trigger"
        )

    def test_critic_boundary_trigger_present(self):
        """SKILL.md must have a checkpoint trigger for the critic boundary."""
        text = _read()
        assert "--phase critic" in text, (
            "thorough_plan/SKILL.md is missing '--phase critic' boundary trigger"
        )

    def test_revise_boundary_trigger_present(self):
        """SKILL.md must have a checkpoint trigger for the revise boundary."""
        text = _read()
        assert "--phase revise" in text, (
            "thorough_plan/SKILL.md is missing '--phase revise' boundary trigger"
        )

    def test_fail_open_present(self):
        """SKILL.md must reference fail-OPEN pattern ('|| true' or 'fail-OPEN')."""
        text = _read()
        assert "|| true" in text or "fail-OPEN" in text, (
            "thorough_plan/SKILL.md is missing fail-OPEN pattern ('|| true' or 'fail-OPEN') "
            "at the checkpoint call site"
        )

    def test_fail_open_uuid_branch_acquisition(self):
        """SKILL.md must reference fail-OPEN UUID/branch acquisition patterns."""
        text = _read()
        assert "2>/dev/null || echo unknown" in text, (
            "thorough_plan/SKILL.md is missing fail-OPEN UUID/branch acquisition pattern "
            "'2>/dev/null || echo unknown'"
        )

    def test_resume_detection_reference(self):
        """SKILL.md must reference the T-04 startup resume-detection mechanism."""
        text = _read()
        assert "thorough-plan-progress-" in text, (
            "thorough_plan/SKILL.md is missing resume-detection reference "
            "'thorough-plan-progress-' (T-04 direct scan)"
        )

    def test_last_user_intent_referenced(self):
        """SKILL.md must reference '## Last user intent' (checkpoint format completeness)."""
        text = _read()
        assert "## Last user intent" in text or "Last user intent" in text, (
            "thorough_plan/SKILL.md is missing '## Last user intent' reference "
            "(checkpoint format completeness signal)"
        )

    def test_session_state_orchestrator_file_referenced(self):
        """SKILL.md must reference the orchestrator-dedicated session-state file (-orchestrator)."""
        text = _read()
        assert "-orchestrator.md" in text or "orchestrator" in text, (
            "thorough_plan/SKILL.md is missing reference to orchestrator-dedicated session-state "
            "file (M-02/D-07 fix)"
        )

    def test_same_session_check_present(self):
        """SKILL.md must document the same-session check in §1b."""
        text = _read()
        assert "_TP_SAME_SESSION" in text or "Same-session" in text, (
            "thorough_plan/SKILL.md must document same-session detection (_TP_SAME_SESSION) "
            "in the §1b startup resume-detection block (IVG-105)."
        )

    def test_resume_in_new_session_option_present(self):
        """SKILL.md must document option (c) 'Resume in a new session'."""
        text = _read()
        assert any(phrase in text for phrase in [
            "Resume in a new session",
            "resume in a new session",
            "option (c)",
            "Option (c)",
        ]), (
            "thorough_plan/SKILL.md must document option (c) 'Resume in a new session' "
            "for the same-session scenario in §1b (IVG-105)."
        )
