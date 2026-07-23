"""IVG-71 T-08: adapter-pilot token greps over gate/SKILL.md.

Cheap literal-token asserts that verify the gate wiring for the
affected-area test suite precondition is present and correctly formed.

Each assert is annotated with the plan spec that drives it (MAJ-1/CRIT-1/
MIN-3/etc.) so a future failure points directly at the requirement.

Region-level assertions (MAJ-3): each named region is located by its
header string, and `Affected-area test suite` is asserted WITHIN that
region. A dropped region must FAIL the test — a bare occurrence-count
would pass while one region silently lost the row.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"

TOKEN = "Affected-area test suite"

# IVG-151 exit-5 machine tokens (hyphenated exit_reason must appear verbatim).
FLAG = "--require-task-context"
EXIT_REASON = "no-quoin-task-context"

# The three post-implement/post-review sub-regions are delimited by bold text,
# not real markdown headings, so `^#{2,3} ` alone does not isolate them from
# each other (they all fall before the next real heading). _region() must also
# stop at the next sibling boundary in this list (round-2 MINOR-4 fix, cloned
# from test_gate_ci_mirror_tokens.py per IVG-151 T-08).
_REGION_BOUNDARIES = (
    "*Standard gate (Small and Medium tasks):*",
    "*Full gate (Large tasks) — includes everything in Standard, plus:*",
    "**After /review → before /end_of_task (Full gate — always, all task sizes):**",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load() -> str:
    return GATE_SKILL.read_text(encoding="utf-8")


def _region(text: str, header: str) -> str:
    """Return the text from header until the next H2/H3 heading OR sibling boundary.

    Stops at the next `## `/`### ` markdown heading AND at the next sibling
    bold-text sub-region boundary in _REGION_BOUNDARIES — so the Standard /
    Full / post-review sub-regions do not leak into each other (they all sit
    before the next real heading).
    """
    start = text.find(header)
    assert start != -1, f"Region header not found in gate SKILL.md: {header!r}"
    after = text[start + len(header):]
    m = re.search(r"^#{2,3} ", after, re.MULTILINE)
    end = m.start() if m else len(after)
    for boundary in _REGION_BOUNDARIES:
        if boundary == header:
            continue
        idx = after.find(boundary)
        if idx != -1 and idx < end:
            end = idx
    return after[:end]


def _check_block(region_text: str, marker: str) -> str:
    """Return one '- [ ] ' + marker checklist bullet's text, up to (not
    including) the next top-level '- [ ] ' bullet or end of region. Isolates
    ONE literal invocation block from its sibling block in the same region
    (IVG-151 T-08: the affected_tests and ci_mirror blocks are adjacent, and
    after wiring both carry identical exit-5 tokens — a region-level assertion
    could not attribute a dropped row to either block)."""
    m = re.search(r"^- \[ \] " + re.escape(marker), region_text, re.MULTILINE)
    assert m is not None, f"Checklist bullet not found: {marker!r}"
    after = region_text[m.start():]
    nxt = re.search(r"\n- \[ \] ", after)
    return after[: nxt.start()] if nxt else after


def _audit_check_block(region_text: str, check_name: str) -> str:
    """Slice one check's audit glyph-mapping sentence out of the continuous
    Step-5 audit prose paragraph (keyed on the 'Glyph mapping for the `<name>`
    row:' sentence marker that exists verbatim for every check)."""
    marker = f"Glyph mapping for the `{check_name}` row:"
    idx = region_text.find(marker)
    assert idx != -1, f"Audit glyph-mapping sentence not found for {check_name!r}"
    after = region_text[idx:]
    nxt = after.find("Glyph mapping for the `", len(marker))
    return after[:nxt] if nxt != -1 else after


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_affected_tests_script_referenced():
    """affected_tests.py must appear somewhere in gate SKILL.md."""
    text = _load()
    assert "affected_tests.py" in text, (
        "gate/SKILL.md must reference 'affected_tests.py'"
    )


def test_quoin_home_token_form():
    """`__QUOIN_HOME__/scripts/affected_tests.py` must appear (not ~/.claude/ form)."""
    text = _load()
    assert "__QUOIN_HOME__/scripts/affected_tests.py" in text, (
        "gate/SKILL.md must use __QUOIN_HOME__/scripts/affected_tests.py "
        "(not ~/.claude/scripts/affected_tests.py)"
    )


def test_no_tilde_claude_literal():
    """No ~/.claude/ literal in gate SKILL.md (lessons-learned 2026-05-15)."""
    import re
    text = _load()
    matches = re.findall(r"~/\.claude/", text)
    assert not matches, (
        f"gate/SKILL.md must not contain ~/.claude/ — found {len(matches)} occurrence(s). "
        "Use __QUOIN_HOME__ instead."
    )


def test_invocation_uses_project_root():
    """The invocation must use --project-root (CRIT-1 fix)."""
    text = _load()
    assert "--project-root" in text, (
        "gate/SKILL.md must use --project-root in the affected_tests.py invocation "
        "(CRIT-1 fix: helper resolves git repo from --project-root itself)"
    )


def test_no_caller_side_git():
    """gate SKILL.md must NOT contain `git -C` or `main...HEAD` in affected_tests pseudocode (regression guard for round-1 bug)."""
    text = _load()
    # We only check the lines near the affected_tests invocation, not branch_hygiene
    # which legitimately uses git -C. Strategy: check that the affected_tests pseudocode
    # block itself doesn't contain these.
    # Find the Standard gate affected-area block
    block_start = text.find("Affected-area test suite (BLOCKING hard precondition")
    assert block_start != -1, "Could not locate the Standard gate Affected-area test suite block"
    block = text[block_start: block_start + 2000]  # generous window
    assert "main...HEAD" not in block, (
        "gate SKILL.md affected-area block must NOT use main...HEAD "
        "(regression guard for round-1 CRIT-2 bug)"
    )
    assert "/tmp/quoin-changed.txt" not in block, (
        "gate SKILL.md must NOT use a fixed /tmp/quoin-changed.txt temp path (MIN-3)"
    )


def test_ran_pytest_field_in_result_mapping():
    """The gate result mapping must reference `ran_pytest` (MAJ-1: exit 0 distinguishes green vs N/A)."""
    text = _load()
    assert "ran_pytest" in text, (
        "gate/SKILL.md must reference `ran_pytest` in the result mapping so the gate "
        "row can report 'N/A — no affected tests' vs 'green' for the two exit-0 sub-cases (MAJ-1)"
    )


# ---------------------------------------------------------------------------
# Per-region assertions (MAJ-3)
# ---------------------------------------------------------------------------

def test_token_in_standard_gate_checklist():
    """Affected-area test suite token appears in the Standard gate checklist region."""
    text = _load()
    region = _region(text, "*Standard gate (Small and Medium tasks):*")
    assert TOKEN in region, (
        f"'{TOKEN}' not found in the Standard gate checklist region. "
        "The Standard gate checklist must contain this exact token."
    )


def test_token_in_full_gate_checklist():
    """Affected-area test suite token appears in the Full gate checklist region."""
    text = _load()
    region = _region(text, "*Full gate (Large tasks)")
    assert TOKEN in region, (
        f"'{TOKEN}' not found in the Full gate checklist region. "
        "The Full gate checklist must contain this exact token."
    )


def test_token_in_post_review_checklist():
    """Affected-area test suite token appears in the post-review gate block."""
    text = _load()
    region = _region(text, "**After /review → before /end_of_task")
    assert TOKEN in region, (
        f"'{TOKEN}' not found in the post-review gate block. "
        "The post-review gate must contain this exact token."
    )


def test_token_in_step5_audit_enumeration():
    """Affected-area test suite token appears in the Step 5 audit-body enumeration."""
    text = _load()
    region = _region(text, "### Step 5: Write audit log")
    assert TOKEN in region, (
        f"'{TOKEN}' not found in the Step 5 audit-body enumeration. "
        "The audit enumeration must contain this exact token (MAJ-3)."
    )


def test_audit_enumeration_broadened_to_post_review():
    """Step 5 audit enumeration must cover BOTH post-implement AND post-review gates."""
    text = _load()
    region = _region(text, "### Step 5: Write audit log")
    # The plan requires the qualifier to be broadened beyond "post-implement"
    assert "post-review" in region, (
        "Step 5 audit enumeration must explicitly state that Affected-area test suite "
        "is required for BOTH post-implement AND post-review gates (MAJ-3)."
    )


def test_audit_row_glyph_mapping_stated():
    """Step 5 audit enumeration must state the glyph mapping (✓/✗/⚠️) for the affected-area row."""
    text = _load()
    region = _region(text, "### Step 5: Write audit log")
    # At least one of the glyphs should appear in the context of the affected-area row
    has_glyphs = "✓" in region or "✗" in region or "⚠️" in region
    assert has_glyphs, (
        "Step 5 audit enumeration must state the glyph mapping (✓/✗/⚠️) "
        "for the Affected-area test suite row (MAJ-3)."
    )


# ---------------------------------------------------------------------------
# IVG-151 T-08: per-check-block exit-5 token assertions (region THEN check-block)
# ---------------------------------------------------------------------------

def test_exit5_in_standard_gate_affected_block():
    """Standard gate affected_tests block carries flag + hyphenated token + exit 5."""
    block = _check_block(
        _region(_load(), "*Standard gate (Small and Medium tasks):*"), TOKEN
    )
    assert FLAG in block, f"{FLAG} missing from Standard affected block"
    assert EXIT_REASON in block, f"{EXIT_REASON} missing from Standard affected block"
    assert "exit 5" in block, "exit 5 missing from Standard affected block"


def test_exit5_in_post_review_affected_block():
    """Post-review affected_tests block carries flag + hyphenated token + exit 5."""
    block = _check_block(
        _region(_load(), "**After /review → before /end_of_task"), TOKEN
    )
    assert FLAG in block, f"{FLAG} missing from post-review affected block"
    assert EXIT_REASON in block, f"{EXIT_REASON} missing from post-review affected block"
    assert "exit 5" in block, "exit 5 missing from post-review affected block"


def test_exit5_in_full_gate_affected_crosslink():
    """Full gate affected_tests is a CROSS-LINK (not a literal re-invocation) — it
    only asserts exit 5 + an inheritance word, NOT the flag or hyphenated token."""
    block = _check_block(_region(_load(), "*Full gate (Large tasks)"), TOKEN)
    assert "exit 5" in block, "exit 5 missing from Full gate affected cross-link"
    assert ("inherited" in block or "above" in block), (
        "Full gate affected cross-link must carry an inheritance word (inherited/above)"
    )


def test_exit5_in_step5_audit_affected_clause():
    """Step-5 audit affected clause carries exit 5 + the hyphenated token."""
    block = _audit_check_block(
        _region(_load(), "### Step 5: Write audit log"), TOKEN
    )
    assert "exit 5" in block, "exit 5 missing from Step-5 affected audit clause"
    assert EXIT_REASON in block, f"{EXIT_REASON} missing from Step-5 affected audit clause"


# ---------------------------------------------------------------------------
# IVG-151 T-08: isolation regression tests (block-level + subsection-level)
# ---------------------------------------------------------------------------

def test_check_block_isolation_affected_vs_ci_mirror():
    """Synthetic reproduction of the round-2 masking scenario: BOTH blocks present
    in one region but the ci_mirror exit-5 row dropped. The affected block must
    still carry its tokens (unaffected) AND the ci_mirror block must NOT (drop
    detected) — proving the affected assertion is not falsely rescued by the
    sibling ci_mirror block's identical tokens."""
    region = (
        "- [ ] Affected-area test suite (BLOCKING): run affected_tests.py --require-task-context\n"
        "  - exit 5 (exit_reason: no-quoin-task-context) → CLEAN SKIP\n"
        "  - script missing → WARN\n"
        "- [ ] CI mirror (BLOCKING): run ci_mirror.py --require-task-context\n"
        "  - script missing → WARN\n"  # ci_mirror exit-5 row dropped here
    )
    affected_block = _check_block(region, "Affected-area test suite")
    ci_block = _check_block(region, "CI mirror")
    assert "exit 5" in affected_block and EXIT_REASON in affected_block, (
        "affected block must retain its own exit-5 tokens"
    )
    assert "exit 5" not in ci_block, (
        "block isolation must expose a row dropped from ONLY the ci_mirror sibling block"
    )


def test_subregions_do_not_leak_into_each_other():
    """Cross-subsection isolation (round-2 MINOR-4, cloned from ci_mirror tokens):
    each sub-region's exclusive content stays put."""
    text = _load()
    standard = _region(text, "*Standard gate (Small and Medium tasks):*")
    full = _region(text, "*Full gate (Large tasks)")
    post_review = _region(text, "**After /review → before /end_of_task")

    assert "All planned tasks are implemented" not in standard
    assert "All planned tasks are implemented" in full
    assert "pre-merge gate" not in standard
    assert "pre-merge gate" not in full
    assert "pre-merge gate" in post_review


def test_region_isolation_catches_single_region_row_drop():
    """Synthetic: with a naive _region an affected row dropped from ONLY the
    Full-gate sub-region would still pass via the sibling post-review region's
    occurrence. The boundary-aware _region isolates it so the drop is visible."""
    synthetic = (
        "**After /implement -> before /review:**\n\n"
        "*Standard gate (Small and Medium tasks):*\n"
        "- [ ] Affected-area test suite check\n\n"
        "*Full gate (Large tasks) — includes everything in Standard, plus:*\n"
        "- [ ] some other unrelated check\n\n"  # affected row dropped here only
        "**After /review → before /end_of_task (Full gate — always, all task sizes):**\n"
        "- [ ] Affected-area test suite check\n\n"
        "### Step 3a: next real heading\n"
    )
    full = _region(synthetic, "*Full gate (Large tasks) — includes everything in Standard, plus:*")
    assert TOKEN not in full, (
        "region isolation must expose a row dropped from only the Full-gate sub-region"
    )
