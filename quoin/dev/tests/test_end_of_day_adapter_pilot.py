"""Phase 16 adapter pilot tests for end_of_day.

Parametrized over the single skill migrated in Phase 16. Follows the
pattern established by test_end_of_task_adapter_pilot.py and
test_run_adapter_pilot.py.

Skill parameters: (skill_name, expected_model, has_section_0)
  - end_of_day: haiku, §0 present (cheap-tier — self-dispatches to Haiku)
"""
import re
from pathlib import Path

import pytest
import yaml

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent
INSTALL_SH = PKG_DIR / "install.sh"

FORBIDDEN_TOKENS = ("~/.claude", "Haiku", "Sonnet", "Opus", "Agent", "gh CLI")
REQUIRED_MENTION = ".workflow_artifacts/<task-name>/"

SKILLS = [
    ("end_of_day", "haiku", True),
]

SKILL_IDS = [s[0] for s in SKILLS]

# Phase 6–15 skills — used for the regression-guard test below.
PRIOR_PHASE_SKILLS = [
    "capture_insight", "triage", "start_of_day",
    "review", "plan", "critic", "revise", "revise-fast",
    "architect", "thorough_plan", "gate", "implement", "rollback",
    "end_of_task", "run",
]


def _slash_regex(name: str) -> re.Pattern:
    """Word-boundary regex for a slash-command token.

    Matches /name only when:
    - NOT preceded by an alphanumeric char or [-_] (avoids matching path
      components like 'skills/end_of_day.md')
    - NOT followed by an alphanumeric char or [-_] (avoids matching
      'end_of_day-2026-05-11.md')
    """
    return re.compile(
        r"(?<![a-zA-Z0-9_\-])"
        + re.escape("/" + name.lstrip("/"))
        + r"(?=[^a-zA-Z0-9_\-]|$)"
    )


def _core_doc(skill_name: str) -> Path:
    return PKG_DIR / "core" / "skills" / f"{skill_name}.md"


def _adapter_skill(skill_name: str) -> Path:
    return PKG_DIR / "adapters" / "claude" / "skills" / skill_name / "SKILL.md"


def _legacy_stub(skill_name: str) -> Path:
    return PKG_DIR / "skills" / skill_name / "SKILL.md"


def _adapter_var(skill_name: str) -> str:
    """Return the expected ADAPTER_*_SRC variable name for a skill."""
    return "ADAPTER_" + skill_name.upper().replace("-", "_") + "_SRC"


# ── Parametrized tests (run over the end_of_day skill) ────────────────────


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_core_skill_doc_exists(skill_name, expected_model, has_section_0):
    path = _core_doc(skill_name)
    assert path.is_file(), f"Missing core skill doc: {path}"


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_core_skill_doc_no_forbidden_tokens(skill_name, expected_model, has_section_0):
    text = _core_doc(skill_name).read_text(encoding="utf-8")

    # Static forbidden tokens — raw substring check.
    hits = [t for t in FORBIDDEN_TOKENS if t in text]

    # Per-skill slash form — negative-lookahead regex (D-03: bare substring FORBIDDEN).
    if _slash_regex(skill_name).search(text):
        hits.append(f"/{skill_name}")

    assert not hits, (
        f"Core doc for {skill_name} contains forbidden tokens: {hits}"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_core_skill_doc_mentions_anchor(skill_name, expected_model, has_section_0):
    text = _core_doc(skill_name).read_text(encoding="utf-8")
    assert REQUIRED_MENTION in text, (
        f"Core doc for {skill_name} must contain literal: {REQUIRED_MENTION}"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_adapter_skill_md_exists(skill_name, expected_model, has_section_0):
    path = _adapter_skill(skill_name)
    assert path.is_file(), f"Missing adapter SKILL.md: {path}"


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_adapter_skill_md_declares_correct_model(skill_name, expected_model, has_section_0):
    text = _adapter_skill(skill_name).read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"Adapter SKILL.md for {skill_name} missing YAML frontmatter"
    fm = yaml.safe_load(parts[1])
    assert fm.get("model") == expected_model, (
        f"Adapter SKILL.md for {skill_name} must declare model: {expected_model} "
        f"(got {fm.get('model')!r})"
    )
    assert fm.get("name") == skill_name, (
        f"Adapter SKILL.md for {skill_name} must declare name: {skill_name} "
        f"(got {fm.get('name')!r})"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_adapter_skill_md_references_core_doc(skill_name, expected_model, has_section_0):
    text = _adapter_skill(skill_name).read_text(encoding="utf-8")
    ref = f"quoin/core/skills/{skill_name}.md"
    assert ref in text, (
        f"Adapter SKILL.md for {skill_name} must reference the portable intent doc: {ref}"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_install_sh_has_adapter_override(skill_name, expected_model, has_section_0):
    text = INSTALL_SH.read_text(encoding="utf-8")
    var_name = _adapter_var(skill_name)
    assert var_name in text, f"install.sh missing {var_name} variable"
    branch = f'elif [ "$skill_name" = "{skill_name}" ]'
    assert branch in text, (
        f"install.sh missing per-skill override branch: {branch}"
    )
    # Pre-flight check must appear before the skills loop.
    preflight_idx = text.find(f"{var_name}=")
    loop_idx = text.find('for skill_dir in "$SCRIPT_DIR/skills"/*/')
    assert preflight_idx != -1 and loop_idx != -1
    assert preflight_idx < loop_idx, (
        f"Pre-flight existence check for {var_name} must appear BEFORE the skills loop"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_legacy_stub_differs_from_adapter(skill_name, expected_model, has_section_0):
    """Adapter must contain full body; legacy is a short stub."""
    legacy_bytes = _legacy_stub(skill_name).read_bytes()
    adapter_bytes = _adapter_skill(skill_name).read_bytes()
    assert legacy_bytes != adapter_bytes, (
        f"Legacy stub and adapter SKILL.md for {skill_name} must differ — "
        "the legacy file should be a short deprecated pointer"
    )
    assert len(legacy_bytes) < len(adapter_bytes), (
        f"Legacy stub for {skill_name} should be shorter than the full adapter SKILL.md"
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_legacy_stub_frontmatter_byte_equals_adapter(skill_name, expected_model, has_section_0):
    """Stub frontmatter MUST byte-equal adapter frontmatter."""
    legacy_text = _legacy_stub(skill_name).read_text(encoding="utf-8")
    adapter_text = _adapter_skill(skill_name).read_text(encoding="utf-8")
    legacy_fm = legacy_text.split("---", 2)[1]
    adapter_fm = adapter_text.split("---", 2)[1]
    assert legacy_fm == adapter_fm, (
        f"Legacy stub frontmatter for {skill_name} must byte-equal adapter frontmatter. "
        "Drift here causes silent runtime divergence."
    )


@pytest.mark.parametrize("skill_name,expected_model,has_section_0", SKILLS, ids=SKILL_IDS)
def test_adapter_skill_md_has_or_lacks_section_0(skill_name, expected_model, has_section_0):
    text = _adapter_skill(skill_name).read_text(encoding="utf-8")
    has_block = "## §0 Model dispatch" in text
    if has_section_0:
        assert has_block, (
            f"Adapter SKILL.md for {skill_name} (cheap-tier) must carry "
            "## §0 Model dispatch block"
        )
    else:
        assert not has_block, (
            f"Adapter SKILL.md for {skill_name} (Opus-tier) must NOT carry "
            "## §0 dispatch block"
        )


# ── Non-parametrized constraint guards ────────────────────────────────────


def test_end_of_day_has_no_preamble_md():
    """end_of_day is NOT a subagent-preamble spawn target.

    Per CLAUDE.md "Subagent preamble" section, the 7 spawn-target skills
    are: critic, revise, revise-fast, plan, review, gate, architect.
    end_of_day is excluded — `build_preambles.py` does not generate one.
    Asserting absence prevents accidental preamble leak.
    """
    legacy_preamble = PKG_DIR / "skills" / "end_of_day" / "preamble.md"
    adapter_preamble = (
        PKG_DIR / "adapters" / "claude" / "skills" / "end_of_day" / "preamble.md"
    )
    assert not legacy_preamble.exists(), (
        f"CONSTRAINT VIOLATION: {legacy_preamble} unexpectedly exists. "
        "end_of_day is NOT a spawn-target; build_preambles.py must not generate one."
    )
    assert not adapter_preamble.exists(), (
        f"CONSTRAINT VIOLATION: {adapter_preamble} unexpectedly exists. "
        "end_of_day is NOT a spawn-target; build_preambles.py must not generate one."
    )


# ── Regression-guard tests (Phase 15 skills must still be covered) ────────


def test_phase_15_skills_still_covered():
    """Regression guard for the end_of_day work — verifies all 15 Phase 6–15 skills are still covered.

    Asserts that each Phase 6–15 migrated skill still has:
    - its core doc at quoin/core/skills/<skill>.md
    - its adapter at quoin/adapters/claude/skills/<skill>/SKILL.md
    - its install.sh override variable and elif branch
    """
    install_text = INSTALL_SH.read_text(encoding="utf-8")
    for skill in PRIOR_PHASE_SKILLS:
        core_doc = _core_doc(skill)
        assert core_doc.is_file(), (
            f"Regression: core doc for prior-phase skill {skill!r} is missing: {core_doc}"
        )
        adapter = _adapter_skill(skill)
        assert adapter.is_file(), (
            f"Regression: adapter SKILL.md for prior-phase skill {skill!r} is missing: {adapter}"
        )
        var_name = _adapter_var(skill)
        assert var_name in install_text, (
            f"Regression: install.sh missing {var_name} for prior-phase skill {skill!r}"
        )


def test_adapter_step_3_does_not_use_today_glob():
    """Regression test: Step 3 must NOT use the <today>-*.md glob for session selection.

    The old glob silently skipped all sessions from prior days even when their
    end_of_day_due flag was yes. The fix replaces it with the hybrid date-window rule.
    """
    text = _adapter_skill("end_of_day").read_text(encoding="utf-8")
    # The literal glob that caused the bug:
    assert "sessions/<today>-*.md" not in text, (
        "end_of_day SKILL.md Step 3 must NOT use the today-only glob "
        "'sessions/<today>-*.md'. Replace with the hybrid date-window + flag rule."
    )


def test_install_fresh_clone_lists_end_of_day_in_migrated_skills():
    """Guard that test_install_fresh_clone.py includes end_of_day in MIGRATED_SKILLS (T-07 edit)."""
    target = PKG_DIR / "dev" / "tests" / "test_install_fresh_clone.py"
    text = target.read_text(encoding="utf-8")
    tuple_start = text.find('MIGRATED_SKILLS = (')
    assert tuple_start != -1, "test_install_fresh_clone.py missing MIGRATED_SKILLS tuple"
    tuple_end = text.find(')', tuple_start)
    tuple_region = text[tuple_start:tuple_end + 1]
    assert '"end_of_day"' in tuple_region, (
        'test_install_fresh_clone.py MIGRATED_SKILLS tuple must include "end_of_day" '
        "(T-07 edit). The entry was reverted — restore it."
    )
