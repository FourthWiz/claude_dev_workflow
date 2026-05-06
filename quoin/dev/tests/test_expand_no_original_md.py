"""
Acceptance tests for /expand cleanup per architecture §5.6.

Asserts that expand/SKILL.md has no .original.md references,
sequential step numbering 1-7, and the correct 7-step pipeline header.
"""
import pathlib
import re

EXPAND_SKILL = pathlib.Path(__file__).parent.parent.parent / "skills" / "expand" / "SKILL.md"


def test_expand_skill_has_no_original_md_references():
    """§5.6 acceptance: .original.md must not appear anywhere in expand/SKILL.md."""
    content = EXPAND_SKILL.read_text()
    assert ".original.md" not in content, (
        "expand/SKILL.md still contains '.original.md' references — "
        "apply T-05 edits (a)/(b)/(c)/(d)/(e)/(g)/(h)/(i) to remove all 11 instances."
    )


def test_expand_step_numbering_is_sequential():
    """Step headings must be numbered 1-7 with no gaps."""
    content = EXPAND_SKILL.read_text()
    step_nums = [int(m.group(1)) for m in re.finditer(r"^### Step (\d+):", content, re.MULTILINE)]
    assert step_nums == list(range(1, len(step_nums) + 1)), (
        f"expand/SKILL.md step numbers are not sequential: found {step_nums}"
    )
    assert len(step_nums) == 7, (
        f"expand/SKILL.md has {len(step_nums)} steps, expected 7 after T-05 edits."
    )


def test_expand_pipeline_header_count_matches_steps():
    """Body header must say '7-step pipeline' (not 8-step); architecture ref must be §5.6."""
    content = EXPAND_SKILL.read_text()

    assert "## 7-step pipeline" in content, (
        "expand/SKILL.md is missing '## 7-step pipeline' header — apply T-05 edit (f)."
    )
    assert "## 8-step pipeline" not in content, (
        "expand/SKILL.md still has '## 8-step pipeline' header."
    )

    # No 8-step / eight-step anywhere (case-insensitive)
    assert not re.search(r"(8|eight)[ -]?step", content, re.IGNORECASE), (
        "expand/SKILL.md still has an '8-step'/'eight-step' reference."
    )

    assert "§5.6's 7-step pipeline" in content, (
        "expand/SKILL.md architecture cross-reference should read '§5.6's 7-step pipeline'."
    )
