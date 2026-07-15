"""Static wiring guard for sessionstart.sh's restore ground-truth backstop (IVG-139, S-4 T-04).

Mirrors test_sessionstart_hook_has_staleness_step.py so the T-01 wiring cannot silently
regress: pins the marker comment, the verify_claims.py call, the CLI flags, the grep token
the hook keys on, the advisory framing, and the shared-namespace guard token (critic
round-1 M-1) — plus a no-literal-home-path guard scoped to just this block.
"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_HOOK = _REPO_ROOT / "quoin" / "hooks" / "sessionstart.sh"


def _hook_text() -> str:
    return _HOOK.read_text(encoding="utf-8")


def test_hook_contains_restore_groundtruth_backstop_marker() -> None:
    assert "restore ground-truth backstop (IVG-139)" in _hook_text(), (
        "sessionstart.sh must contain the 'restore ground-truth backstop (IVG-139)' marker"
    )


def test_hook_references_verify_claims_script() -> None:
    text = _hook_text()
    assert "../scripts/verify_claims.py" in text, (
        "sessionstart.sh must reference ../scripts/verify_claims.py"
    )


def test_hook_uses_check_side_effects_checkpoint_cli_contract() -> None:
    text = _hook_text()
    assert "--check-side-effects" in text, (
        "sessionstart.sh must invoke verify_claims.py with --check-side-effects"
    )
    assert "--skill checkpoint" in text, (
        "sessionstart.sh must invoke verify_claims.py with --skill checkpoint"
    )


def test_hook_greps_task_backstop_token() -> None:
    text = _hook_text()
    assert "task_backstop:" in text, (
        "sessionstart.sh must grep for the 'task_backstop:' token (a predicate-tag rename "
        "must break this test)"
    )


def test_hook_documents_advisory_intent() -> None:
    text = _hook_text()
    assert "advisory" in text, (
        "sessionstart.sh restore ground-truth backstop block must document advisory-only intent"
    )


def test_hook_has_shared_namespace_guard_token() -> None:
    """Pins the critic round-1 M-1 shared-namespace fix so it cannot silently regress."""
    text = _hook_text()
    assert "thorough-plan-progress-*" in text, (
        "sessionstart.sh must skip the predicate for thorough-plan-progress-* checkpoints "
        "(critic round-1 M-1 shared-namespace guard)"
    )


def test_hook_restore_groundtruth_section_has_no_literal_home_claude() -> None:
    """The restore ground-truth backstop block must not contain literal ~/.claude/ paths."""
    text = _hook_text()
    start = text.find("=== restore ground-truth backstop (IVG-139) ===")
    end = text.find("=== end restore ground-truth backstop (IVG-139) ===")
    assert start != -1, "restore ground-truth backstop start marker not found in sessionstart.sh"
    assert end != -1, "restore ground-truth backstop end marker not found in sessionstart.sh"
    section = text[start:end]
    assert "~/.claude/" not in section, (
        "restore ground-truth backstop section of sessionstart.sh must not contain literal "
        "~/.claude/ paths"
    )
