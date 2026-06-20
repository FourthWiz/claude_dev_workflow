"""Tests for the Serena code-intelligence integration (serena-integration task)."""
from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent  # quoin/
SOURCE_ROOT = REPO_ROOT / "quoin"

SERENA_MEMORY = SOURCE_ROOT / "memory" / "serena-activation.md"
INSTALLER = REPO_ROOT / "src" / "quoin" / "installer.py"
CLAUDE_MD = SOURCE_ROOT / "CLAUDE.md"
ADAPTER_INIT_WORKFLOW = SOURCE_ROOT / "adapters" / "claude" / "skills" / "init_workflow" / "SKILL.md"


def test_serena_memory_file_exists_and_tier1() -> None:
    """serena-activation.md must exist, be non-empty, start with an English heading,
    and contain the required key terms (Tier-1 guard)."""
    assert SERENA_MEMORY.exists(), f"Missing: {SERENA_MEMORY}"
    text = SERENA_MEMORY.read_text(encoding="utf-8")
    assert text.strip(), "serena-activation.md is empty"
    assert text.lstrip().startswith("# "), "Must start with a Markdown H1 heading (Tier-1)"
    for term in ("ToolSearch", "activate_project", "initial_instructions", "onboarding"):
        assert term in text, f"Missing required term '{term}' in serena-activation.md"
    assert "do nothing" in text, (
        "Graceful-absence rule must include 'do nothing' phrase in serena-activation.md"
    )


def test_serena_memory_registered_in_installer() -> None:
    """serena-activation.md must be in TIER1_MEMORY_FILES or deploy_memory() silently skips it."""
    source = INSTALLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    tier1: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TIER1_MEMORY_FILES":
                    if isinstance(node.value, ast.Tuple):
                        tier1 = [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
    assert "serena-activation.md" in tier1, (
        "'serena-activation.md' not found in TIER1_MEMORY_FILES in installer.py"
    )


def test_serena_memory_uses_quoin_home_token() -> None:
    """SOURCE memory file must use __QUOIN_HOME__ token, never the literal ~/.claude/ path."""
    text = SERENA_MEMORY.read_text(encoding="utf-8")
    assert "~/.claude/" not in text, (
        "serena-activation.md must use __QUOIN_HOME__ token, not literal ~/.claude/"
    )


def test_claude_md_has_conditional_serena_pointer() -> None:
    """CLAUDE.md must have a conditional Serena block with both the present/absent branches
    and a pointer to serena-activation.md."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "serena-activation.md" in text, (
        "CLAUDE.md must reference serena-activation.md"
    )
    # Must have the ToolSearch probe (marks it as conditional, not unconditional)
    assert "ToolSearch" in text or "mcp__serena__" in text, (
        "CLAUDE.md Serena block must include a conditional probe (ToolSearch or mcp__serena__)"
    )
    # Must have the graceful-absence branch — "do nothing" or "don't exist" or "absent"
    has_absence = any(phrase in text for phrase in ("do nothing", "don't exist", "no schema"))
    assert has_absence, (
        "CLAUDE.md Serena block must include a graceful-absence branch"
    )


def test_init_workflow_adapter_has_serena_step() -> None:
    """The ADAPTER init_workflow SKILL.md must contain the three-branch Serena Step 6.5."""
    text = ADAPTER_INIT_WORKFLOW.read_text(encoding="utf-8")
    assert "Serena" in text, "adapter SKILL.md must reference Serena"
    assert "activate_project" in text, "adapter SKILL.md must reference activate_project"
    assert "onboarding" in text, "adapter SKILL.md must reference onboarding"
    assert "Skip for now" in text, "adapter SKILL.md must have 'Skip for now' AskUserQuestion option"
    # All three branches present
    assert "ABSENT" in text or "not installed" in text or "Install Serena" in text, (
        "adapter SKILL.md must have branch (a) — absent/install path"
    )
    assert "not yet onboarded" in text or "Onboarding has not been performed" in text or "PRESENT, not yet" in text, (
        "adapter SKILL.md must have branch (b) — present-but-not-onboarded path"
    )
    assert "already onboarded" in text or "PRESENT, already" in text, (
        "adapter SKILL.md must have branch (c) — already-onboarded path"
    )


def test_init_workflow_serena_uses_quoin_home_token() -> None:
    """The adapter SKILL.md Serena block must not use literal ~/.claude/ paths."""
    text = ADAPTER_INIT_WORKFLOW.read_text(encoding="utf-8")
    # Find the Serena step section (between Step 6.5 and Step 7)
    start = text.find("Step 6.5")
    end = text.find("### Step 7", start)
    if start == -1 or end == -1:
        # Fallback: check the whole file
        serena_section = text
    else:
        serena_section = text[start:end]
    assert "~/.claude/" not in serena_section, (
        "adapter SKILL.md Serena block must use __QUOIN_HOME__, not literal ~/.claude/"
    )
