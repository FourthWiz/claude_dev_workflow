"""Regression test: /init_workflow must not generate invalid Bash(:*.) permission rules.

Claude Code rejects rules like "Bash(rm:*.tmp)" at startup with:
  "Invalid permission rule: :* pattern must be at the end."

The :* wildcard must appear at the END of a Bash() rule (e.g. "Bash(rm:*)"),
not in the middle (e.g. "Bash(rm:*.tmp)"). Since the deny list already
contains "Bash(rm:*)" which overrides any allow rule, these entries were
both invalid AND semantically dead. This test prevents reintroduction.

Fixes IVG-101.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INIT_WORKFLOW_SKILL = (
    REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "init_workflow" / "SKILL.md"
)
ALL_SKILLS_GLOB = (
    REPO_ROOT / "quoin" / "adapters" / "claude" / "skills"
)

# Regex that matches invalid Bash() permission rules where :* appears before
# additional characters (i.e., :* is NOT at the end of the rule).
# Valid: "Bash(rm:*)" — :* is the last thing before )
# Invalid: "Bash(rm:*.tmp)" — :* is followed by .tmp before )
_INVALID_BASH_RULE_RE = re.compile(r'Bash\([^)]*:\*[^)]+\)')


class TestInitWorkflowPermRules:
    """Ensure /init_workflow SKILL.md never introduces invalid Bash(:*.) rules."""

    def test_init_workflow_skill_no_invalid_bash_rules(self):
        """init_workflow/SKILL.md must not contain any Bash(cmd:*.ext) patterns."""
        assert INIT_WORKFLOW_SKILL.exists(), (
            f"Expected SKILL.md at {INIT_WORKFLOW_SKILL} — repo structure may have changed"
        )
        content = INIT_WORKFLOW_SKILL.read_text()
        matches = _INVALID_BASH_RULE_RE.findall(content)
        assert not matches, (
            f"Found invalid Bash permission rules in init_workflow/SKILL.md "
            f"(the :* wildcard must be at the END of a Bash() rule, not followed by more chars): "
            f"{matches}"
        )

    def test_all_skills_no_invalid_bash_rules(self):
        """Broader guard: no SKILL.md in the skills tree should emit invalid Bash(:*.) rules."""
        assert ALL_SKILLS_GLOB.is_dir(), (
            f"Expected skills directory at {ALL_SKILLS_GLOB}"
        )
        skill_files = list(ALL_SKILLS_GLOB.glob("*/SKILL.md"))
        assert skill_files, f"No SKILL.md files found under {ALL_SKILLS_GLOB}"

        violations = {}
        for skill_file in skill_files:
            content = skill_file.read_text()
            matches = _INVALID_BASH_RULE_RE.findall(content)
            if matches:
                violations[str(skill_file.relative_to(REPO_ROOT))] = matches

        assert not violations, (
            f"Found invalid Bash permission rules (the :* wildcard must be at the END "
            f"of a Bash() rule) in the following SKILL.md files: {violations}"
        )
