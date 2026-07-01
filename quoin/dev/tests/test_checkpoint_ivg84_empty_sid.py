"""IVG-84 T-10: Regression tests for empty/unknown-SID guard and Tier-1 fast-path skip.

Contributing bug: when the session UUID could not be resolved, the old code would
write `pending-restore-.txt` (empty suffix), creating an orphan sentinel that could
never be matched by a real UUID and would confuse the restore picker.

These tests pin the PROSE in checkpoint/SKILL.md to ensure:
  (a) All four sentinel write sites (Step 3, Step 4b, Step 4c, defer mode) document
      refusing to write when SID is empty or the literal 'unknown'.
  (b) The Tier-1 fast path documents skipping BEFORE constructing
      `pending-restore-${current_session_id}` when SID is empty/unknown.
  (c) The literal orphan filename `pending-restore-.txt` is named in the guard rationale.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — pin to SOURCE (not deployed ~/.claude copy)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"
CLEANUP_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "cleanup" / "SKILL.md"


def _checkpoint_text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test (a): Step 3 — pending-restore write site has empty/unknown guard
# ---------------------------------------------------------------------------

def test_step3_empty_sid_guard():
    """Step 3 (pending-restore write) must document refusing when SID is empty/unknown."""
    text = _checkpoint_text()

    # Find the Step 3 section
    step3_idx = text.find("### Step 3: Write pending-restore sentinel")
    assert step3_idx != -1, "Step 3 heading not found in checkpoint/SKILL.md"

    # Step 3 ends at the next ### heading
    next_section = text.find("### Step 4:", step3_idx)
    if next_section == -1:
        next_section = len(text)
    step3_text = text[step3_idx:next_section]

    # Guard must be present in Step 3
    assert "empty" in step3_text.lower() or "unknown" in step3_text, (
        "Step 3 does not document refusing to write when SID is empty/unknown.\n"
        f"Step 3 content (first 500 chars):\n{step3_text[:500]}"
    )
    assert "pending-restore-.txt" in step3_text, (
        "Step 3 must name the orphan filename `pending-restore-.txt` in its guard rationale.\n"
        f"Step 3 content (first 500 chars):\n{step3_text[:500]}"
    )


# ---------------------------------------------------------------------------
# Test (a): Step 4b — pending-resume-ref write site has empty/unknown guard
# ---------------------------------------------------------------------------

def test_step4b_empty_sid_guard():
    """Step 4b (load-as-reference sentinel) must document refusing when SID is empty/unknown."""
    text = _checkpoint_text()

    step4b_idx = text.find("### Step 4b: Load-as-reference mode sentinel")
    assert step4b_idx != -1, "Step 4b heading not found in checkpoint/SKILL.md"

    next_section = text.find("### Step 4c:", step4b_idx)
    if next_section == -1:
        next_section = len(text)
    step4b_text = text[step4b_idx:next_section]

    assert ("empty" in step4b_text.lower() or "unknown" in step4b_text), (
        "Step 4b does not document refusing to write when SID is empty/unknown.\n"
        f"Step 4b content (first 500 chars):\n{step4b_text[:500]}"
    )


# ---------------------------------------------------------------------------
# Test (a): Step 4c — mid-agent-handoff write site has empty/unknown guard
# ---------------------------------------------------------------------------

def test_step4c_empty_sid_guard():
    """Step 4c (mid-agent handoff sentinel) must document refusing when SID is empty/unknown."""
    text = _checkpoint_text()

    step4c_idx = text.find("### Step 4c: Mid-agent mode sentinel")
    assert step4c_idx != -1, "Step 4c heading not found in checkpoint/SKILL.md"

    next_section = text.find("### Step 5:", step4c_idx)
    if next_section == -1:
        next_section = len(text)
    step4c_text = text[step4c_idx:next_section]

    assert ("empty" in step4c_text.lower() or "unknown" in step4c_text), (
        "Step 4c does not document refusing to write when SID is empty/unknown.\n"
        f"Step 4c content (first 500 chars):\n{step4c_text[:500]}"
    )


# ---------------------------------------------------------------------------
# Test (a): Defer mode — checkpoint-defer write site has empty/unknown guard
# ---------------------------------------------------------------------------

def test_defer_mode_empty_sid_guard():
    """Defer mode (checkpoint-defer sentinel) must document refusing when SID is empty/unknown."""
    text = _checkpoint_text()

    defer_idx = text.find("## Defer mode (`--defer` argument present)")
    assert defer_idx != -1, "Defer mode section not found in checkpoint/SKILL.md"

    # End of defer mode: next ## section
    next_section = text.find("\n## ", defer_idx + 1)
    if next_section == -1:
        next_section = len(text)
    defer_text = text[defer_idx:next_section]

    assert ("empty" in defer_text.lower() or "unknown" in defer_text), (
        "Defer mode does not document refusing to write when SID is empty/unknown.\n"
        f"Defer mode content (first 600 chars):\n{defer_text[:600]}"
    )


# ---------------------------------------------------------------------------
# Test (b): Tier-1 fast path documents skipping before constructing the sentinel
# ---------------------------------------------------------------------------

def test_tier1_fast_path_empty_sid_skip():
    """Tier-1 fast path must document skipping BEFORE constructing pending-restore-${id}.

    The guard must appear BEFORE the `if exists pending-restore-${current_session_id}`
    check so the orphan filename is never even constructed.
    """
    text = _checkpoint_text()

    # Locate the Tier-1 description and the fast path pseudocode block
    tier1_idx = text.find("**Tier 1 — Fast path (current-session sentinel, fast validation):**")
    assert tier1_idx != -1, "Tier-1 fast path heading not found in checkpoint/SKILL.md"

    # The fast path block ends before Tier 2
    tier2_idx = text.find("**Tier 2 —", tier1_idx)
    if tier2_idx == -1:
        tier2_idx = len(text)
    tier1_text = text[tier1_idx:tier2_idx]

    # The guard must appear before the `pending-restore-${current_session_id}` construction
    guard_phrases = ["empty string OR", "empty or", "empty/unknown", "SKIP the fast path"]
    guard_found = any(phrase.lower() in tier1_text.lower() for phrase in guard_phrases)
    assert guard_found, (
        "Tier-1 fast path does not document skipping when current_session_id is empty/unknown.\n"
        f"Tier-1 text (first 800 chars):\n{tier1_text[:800]}"
    )

    # Confirm the guard appears BEFORE `pending-restore-${current_session_id}`
    guard_pos = min(
        (tier1_text.lower().find(p.lower()) for p in guard_phrases
         if p.lower() in tier1_text.lower()),
        default=None,
    )
    construct_pos = tier1_text.find("pending-restore-${current_session_id}")
    if construct_pos == -1:
        # Also check the code block form
        construct_pos = tier1_text.find("pending-restore-${current_session_id}")

    if guard_pos is not None and construct_pos != -1:
        assert guard_pos < construct_pos, (
            "The empty/unknown-SID guard appears AFTER the pending-restore construction — "
            "it must appear BEFORE to prevent the orphan filename from being constructed.\n"
            f"Guard position in Tier-1 text: {guard_pos}\n"
            f"Construction position in Tier-1 text: {construct_pos}"
        )


# ---------------------------------------------------------------------------
# Test (c): `pending-restore-.txt` named in at least one guard
# ---------------------------------------------------------------------------

def test_orphan_filename_named_in_guards():
    """The literal orphan filename `pending-restore-.txt` must be named in guard rationale.

    This ensures the doc explicitly calls out WHY the guard is needed — the specific
    artifact name that would be created if the guard were absent.
    """
    text = _checkpoint_text()
    assert "pending-restore-.txt" in text, (
        "checkpoint/SKILL.md does not mention the orphan filename `pending-restore-.txt`. "
        "The empty-SID guard rationale must name this specific artifact."
    )
