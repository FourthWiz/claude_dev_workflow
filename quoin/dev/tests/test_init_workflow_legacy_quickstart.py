"""T-09: /init_workflow legacy-prompt static contract test.

/init_workflow is interactive — direct runtime testing requires a Claude
Code harness. We test the SKILL.md text contract instead (per architecture
rebrand-path-conflicts integration concern + 'structural contract over
LLM replay' lesson).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_MD = REPO_ROOT / "quoin" / "skills" / "init_workflow" / "SKILL.md"


def _skill_md_text() -> str:
    assert SKILL_MD.exists(), f"init_workflow SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text()


def test_skill_md_contains_legacy_quickstart_prompt():
    """SKILL.md must contain the literal legacy-detection prompt phrases."""
    text = _skill_md_text()
    required = [
        "Legacy QUICKSTART location detected",
        "(project)/dev-workflow/QUICKSTART.md",
        "[m] Move",
        "[d] Delete",
        "[k] Keep",
    ]
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, f"init_workflow SKILL.md is missing legacy-prompt phrases: {missing}"


def test_skill_md_step_7_writes_to_workflow_artifacts():
    """Step 7 must reference .workflow_artifacts/QUICKSTART.md (new location).

    The old (project)/dev-workflow/QUICKSTART.md path may ONLY appear inside
    the legacy-detection sub-block.
    """
    text = _skill_md_text()
    assert ".workflow_artifacts/QUICKSTART.md" in text, (
        "Step 7 must reference the new .workflow_artifacts/QUICKSTART.md location"
    )

    # Isolate Step 7 body — between '### Step 7' and the next '### Step ' heading.
    step_7_match = re.search(
        r"### Step 7:.*?(?=\n### Step \d+:)", text, re.DOTALL
    )
    assert step_7_match, "Step 7 heading not found in SKILL.md"
    step_7_body = step_7_match.group(0)

    # The old path should only appear inside the legacy-detection block of Step 7
    old_path = "(project)/dev-workflow/QUICKSTART.md"
    legacy_section_pattern = r"Legacy QUICKSTART.*?\[k\] Keep.*?\)"
    legacy_section = re.search(legacy_section_pattern, step_7_body, re.DOTALL)
    assert legacy_section, "Legacy-detection prompt block not found in Step 7"


def test_skill_md_safe_default_when_source_clone_present():
    """SKILL.md must instruct safe default to [k] when source-clone collision detected."""
    text = _skill_md_text()
    # Instruction must mention dev-workflow/install.sh OR dev-workflow/SETUP.md
    # AND mention defaulting to [k]
    assert "dev-workflow/install.sh" in text or "dev-workflow/SETUP.md" in text, (
        "SKILL.md must mention checking for install.sh or SETUP.md (source-clone detection)"
    )
    assert "default to `[k]`" in text or "default to [k]" in text, (
        "SKILL.md must instruct defaulting to [k]eep when source clone is detected"
    )


def test_skill_md_workflow_user_guide_qualified():
    """Prose references to Workflow-User-Guide.html in Step 7/8 must be qualified.

    Tree-diagram entries with bare filename are allowed (ASCII art).
    """
    text = _skill_md_text()
    # Find all Workflow-User-Guide.html references
    lines = text.splitlines()
    unqualified = []
    for i, line in enumerate(lines, start=1):
        if "Workflow-User-Guide.html" not in line:
            continue
        # Skip tree-diagram lines (contain box-drawing chars)
        if any(c in line for c in "│├└─"):
            continue
        if "<your-quoin-clone>/" not in line:
            unqualified.append(f"line {i}: {line.strip()}")
    assert not unqualified, (
        "Found unqualified Workflow-User-Guide.html refs in SKILL.md prose:\n"
        + "\n".join(unqualified)
    )
