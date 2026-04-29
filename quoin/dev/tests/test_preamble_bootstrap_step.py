"""
T-04 acceptance test: Verify each of the 7 spawn-target SKILL.md files has the
additive preamble-read bootstrap step AND that all existing references remain intact.

Per T-04 plan:
(a) new step text appears verbatim with correct <skill> substitution
(b) existing format-kit.md reference in ## Session bootstrap still present
(c) existing glossary.md reference in ## Session bootstrap still present
(d) existing format-kit.md write-site reference still present (6 of 7 skills; gate has none)
(e) new step appears BEFORE every other bootstrap read in source order
"""

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
QUOIN_DIR = HERE.parent.parent  # quoin/dev/tests/ -> quoin/dev/ -> quoin/

# Import SPAWN_TARGETS
sys.path.insert(0, str(QUOIN_DIR / "scripts"))
from build_preambles import SPAWN_TARGETS  # noqa: E402

PREAMBLE_STEP_FRAGMENT = "preamble.md` if it exists; if missing or empty, proceed normally."
FORMAT_KIT_REF = "~/.claude/memory/format-kit.md"
GLOSSARY_REF = "~/.claude/memory/glossary.md"
WRITE_SITE_PATTERN = "Reference files (apply HERE at the body-generation"

# Skills that have write-site references (gate has none per plan)
SKILLS_WITH_WRITE_SITE = {"critic", "revise", "revise-fast", "plan", "review", "architect"}


def _skill_md(skill: str) -> pathlib.Path:
    return QUOIN_DIR / "skills" / skill / "SKILL.md"


def _find_line_numbers(lines: list, pattern: str) -> list:
    """Return 1-based line numbers where pattern appears in lines list."""
    return [i + 1 for i, ln in enumerate(lines) if pattern in ln]


@pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
def test_preamble_step_present(skill):
    """(a) New preamble step text appears verbatim with correct skill name."""
    content = _skill_md(skill).read_text(encoding="utf-8")
    assert PREAMBLE_STEP_FRAGMENT in content, (
        f"SKILL.md for {skill} is missing the preamble bootstrap step text"
    )
    skill_path = f"~/.claude/skills/{skill}/preamble.md"
    assert skill_path in content, (
        f"SKILL.md for {skill} should reference '~/.claude/skills/{skill}/preamble.md'"
    )


@pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
def test_format_kit_reference_intact(skill):
    """(b) Existing format-kit.md reference in ## Session bootstrap still present."""
    content = _skill_md(skill).read_text(encoding="utf-8")
    assert FORMAT_KIT_REF in content, (
        f"SKILL.md for {skill} is missing the format-kit.md reference — additive-only violation"
    )


@pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
def test_glossary_reference_intact(skill):
    """(c) Existing glossary.md reference in ## Session bootstrap still present."""
    content = _skill_md(skill).read_text(encoding="utf-8")
    assert GLOSSARY_REF in content, (
        f"SKILL.md for {skill} is missing the glossary.md reference — additive-only violation"
    )


@pytest.mark.parametrize("skill", list(SKILLS_WITH_WRITE_SITE))
def test_write_site_reference_intact(skill):
    """(d) Write-site format-kit reference still present for the 6 non-gate skills."""
    content = _skill_md(skill).read_text(encoding="utf-8")
    assert WRITE_SITE_PATTERN in content, (
        f"SKILL.md for {skill} is missing the write-site format-kit reference — "
        f"additive-only violation"
    )


@pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
def test_preamble_step_is_first_bootstrap_read(skill):
    """(e) New preamble step appears before all other bootstrap reads in source order."""
    lines = _skill_md(skill).read_text(encoding="utf-8").splitlines()

    preamble_lines = _find_line_numbers(lines, f"~/.claude/skills/{skill}/preamble.md")
    assert preamble_lines, f"No preamble step found in {skill}/SKILL.md"
    preamble_line = preamble_lines[0]

    # Find the other bootstrap read markers
    format_kit_lines = _find_line_numbers(lines, FORMAT_KIT_REF)
    glossary_lines = _find_line_numbers(lines, GLOSSARY_REF)

    for ref_line in format_kit_lines + glossary_lines:
        assert preamble_line < ref_line, (
            f"In {skill}/SKILL.md, preamble step (line {preamble_line}) should appear "
            f"before format-kit/glossary reference (line {ref_line})"
        )
