"""SKILL.md-lint tests for the `[autonomous]` branch in /gate (IVG-153, T-10).

Text-level guards over `gate/SKILL.md` — assert (a) an autonomous PASS -> auto-approve ->
Step 5 audit-log path with no `AskUserQuestion`; (b) FAIL is explicitly NOT auto-approved
under autonomous (the FAIL verdict is returned to the orchestrator, which owns retry/
hard-stop); (c) audit-log persistence text is present in the autonomous path (mandatory
in both modes).
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"


@pytest.fixture(scope="module")
def gate_skill_text() -> str:
    assert GATE_SKILL.exists(), f"gate/SKILL.md not found at {GATE_SKILL}"
    return GATE_SKILL.read_text(encoding="utf-8")


def _autonomous_section(text: str) -> str:
    idx = text.index("### Step 3.6: Autonomous auto-approve check")
    end = text.index("### Step 4: STOP and wait")
    return text[idx:end]


def test_autonomous_section_present(gate_skill_text: str) -> None:
    assert "### Step 3.6: Autonomous auto-approve check" in gate_skill_text


def test_autonomous_pass_auto_approves_and_proceeds_to_step5(gate_skill_text: str) -> None:
    section = _autonomous_section(gate_skill_text)
    assert "On checks PASS" in section
    assert "Do NOT call `AskUserQuestion`" in section
    assert "proceed DIRECTLY to Step 5" in section
    assert "auto_approved: true" in section


def test_autonomous_fail_not_auto_approved(gate_skill_text: str) -> None:
    section = _autonomous_section(gate_skill_text)
    assert "On checks FAIL" in section
    assert "do NOT auto-approve" in section
    assert "Return the FAIL verdict to the orchestrator" in section
    assert "orchestrator" in section and "retry/hard-stop" in section.replace("hard-stop decision", "hard-stop decision")


def test_audit_log_persistence_mandatory_in_autonomous_path(gate_skill_text: str) -> None:
    section = _autonomous_section(gate_skill_text)
    assert "audit-log persistence" in section.lower() or "audit log" in section
    # Both branches (PASS and FAIL) reference Step 5 write behavior.
    assert "Step 5" in section


def test_autonomous_independent_of_benchmark_bypass(gate_skill_text: str) -> None:
    section = _autonomous_section(gate_skill_text)
    assert "independent" in section.lower()
    assert "Step 3.5" in section


def test_gate_inline_or_subagent_detection_documented(gate_skill_text: str) -> None:
    section = _autonomous_section(gate_skill_text)
    assert "[autonomous]" in section
    assert "AUTONOMOUS" in section
    assert "inline" in section.lower()


def test_dispatch_sites_not_hand_edited(gate_skill_text: str) -> None:
    text = gate_skill_text
    assert "<!-- §0-worktree-fallback-begin -->" in text
    assert "<!-- §0-worktree-fallback-end -->" in text
