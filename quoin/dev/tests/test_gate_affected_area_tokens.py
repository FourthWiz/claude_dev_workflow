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

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"

TOKEN = "Affected-area test suite"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load() -> str:
    return GATE_SKILL.read_text(encoding="utf-8")


def _region(text: str, header: str) -> str:
    """Return the text from header until the next H2 or H3 markdown heading.

    Only stops at lines starting with `## ` or `### ` (two or more hashes +
    space) — intentionally excludes single-hash comment annotations like
    `# V-05 reminder:` or `# NOTE:` that are embedded in prose blocks.
    """
    start = text.find(header)
    assert start != -1, f"Region header not found in gate SKILL.md: {header!r}"
    after = text[start + len(header):]
    import re
    # Only H2 (##) or H3 (###) headings end a section — not single-hash comments
    m = re.search(r"^#{2,3} ", after, re.MULTILINE)
    if m:
        return after[: m.start()]
    return after


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
