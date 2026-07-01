"""
test_checkpoint_cleanup_autofire.py — structural tests for /checkpoint auto-cleanup integration.

Verifies that checkpoint/SKILL.md correctly documents the Step 1.47 auto-cleanup
integration per IVG-68 plan T-09.

Per Stage 1 plan D-03: purely deterministic pathlib + string parsing. No live LLM calls.
"""
from __future__ import annotations

from pathlib import Path

TESTS_DIR = Path(__file__).parent
CHECKPOINT_SKILL = TESTS_DIR.parent.parent / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


# ── 1. Step 1.47 heading exists ───────────────────────────────────────────────

def test_step_147_present():
    text = _text()
    assert "### Step 1.47" in text or "Step 1.47" in text, (
        "checkpoint/SKILL.md does not contain 'Step 1.47'. "
        "The auto-cleanup step must be inserted as Step 1.47 inside Step 1.5."
    )


# ── 2. --no-cleanup flag documented ──────────────────────────────────────────

def test_no_cleanup_flag():
    text = _text()
    assert "--no-cleanup" in text, (
        "checkpoint/SKILL.md does not contain '--no-cleanup'. "
        "The opt-out flag must be documented in the arg-parse section."
    )


# ── 3. Skip conditions documented ────────────────────────────────────────────

def test_skip_conditions():
    text = _text()
    # mid-agent skip
    assert "mid-agent" in text, (
        "checkpoint/SKILL.md does not document 'mid-agent' as a cleanup skip condition."
    )
    # COMPACT_FIRST_BPS or high-util skip
    assert "COMPACT_FIRST_BPS" in text or "high-util" in text, (
        "checkpoint/SKILL.md does not document COMPACT_FIRST_BPS/high-util as a cleanup skip condition."
    )
    # panic skip
    assert "PANIC_BPS" in text or "panic" in text.lower(), (
        "checkpoint/SKILL.md does not document panic as a cleanup skip condition."
    )


# ── 4. Cleanup runs before Step 2 write ──────────────────────────────────────

def test_cleanup_before_step2():
    text = _text()
    # Must document ordering: cleanup before step 2 write
    assert any(phrase in text for phrase in [
        "BEFORE Step 2",
        "before Step 2",
        "runs BEFORE Step 2",
        "runs before Step 2",
        "Step 1.47 runs BEFORE",
        "CRITICAL invariant",
    ]), (
        "checkpoint/SKILL.md must state that Step 1.47 cleanup runs BEFORE Step 2 writes "
        "the new checkpoint file."
    )


# ── 5. Recovery instruction does not claim /sleep --restore ──────────────────

def test_recovery_not_sleep_restore():
    text = _text()
    # The Step 1.47 section should not claim recovery via /sleep --restore for trash/ files
    # It's OK if /sleep --restore appears elsewhere in the file (restore mode etc.)
    # We check that the auto-cleanup section explicitly disclaims /sleep --restore
    assert "NOT `/sleep --restore`" in text or "not /sleep --restore" in text.lower() or \
           "NOT /sleep --restore" in text or \
           "only searches `forgotten/`" in text or \
           "only reads `forgotten/`" in text or \
           "only reads forgotten/" in text, (
        "checkpoint/SKILL.md Step 1.47 should explicitly disclaim '/sleep --restore' for "
        "trash/ file recovery (it only reads forgotten/ text entries, not trash/ files)."
    )
