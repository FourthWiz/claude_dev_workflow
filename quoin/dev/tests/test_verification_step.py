"""
Drift-detection tests for the §V Ground-truth verification blocks (IVG-115 T-04/T-09 partial).

Mirrors test_mintier_guard.py's shape: heading-present-once, markers-once, required
tokens inside the block, ordering (claims strictly before verify in end_of_day),
generator idempotence, and run_check()==0 on the committed tree.

Scope note: this covers T-04's acceptance criteria (the generator itself) plus the
structural half of T-05/T-06 (both blocks land correctly in the 3 adapter files).
It does NOT cover the SessionEnd-hook backstop (T-12) or the empty/absent-manifest
runtime behavior (T-01/T-02 own those, in test_verify_claims.py) — the fuller
regression pass across all of that is T-09, not duplicated here.
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
ADAPTER_SKILLS_DIR = PKG_DIR / "adapters" / "claude" / "skills"
SCRIPTS_DIR = PKG_DIR / "scripts"

_ivs_spec = importlib.util.spec_from_file_location(
    "inject_verification_step",
    SCRIPTS_DIR / "inject_verification_step.py",
)
assert _ivs_spec is not None
_ivs = importlib.util.module_from_spec(_ivs_spec)
assert _ivs_spec.loader is not None
_ivs_spec.loader.exec_module(_ivs)

VERIFY_SKILLS = _ivs.VERIFY_TARGET_SKILLS
CLAIMS_SKILLS = _ivs.CLAIMS_EMIT_SKILLS
LIGHT_SKILLS = _ivs.RECONCILE_LIGHT_SKILLS


def _read(skill: str) -> str:
    return (ADAPTER_SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", VERIFY_SKILLS)
def test_verify_heading_present_exactly_once(skill):
    text = _read(skill)
    assert text.count(_ivs.VERIFY_HEADING) == 1


@pytest.mark.parametrize("skill", VERIFY_SKILLS)
@pytest.mark.parametrize("marker", [_ivs.VERIFY_BEGIN, _ivs.VERIFY_END])
def test_verify_markers_present_exactly_once(skill, marker):
    text = _read(skill)
    assert text.count(marker) == 1


@pytest.mark.parametrize("skill", VERIFY_SKILLS)
@pytest.mark.parametrize("token", ["verify_claims", "--reconcile-tasks", "exits 8"])
def test_verify_required_token_in_block(skill, token):
    text = _read(skill)
    idx = text.index(_ivs.VERIFY_HEADING)
    end = text.index(_ivs.VERIFY_END, idx)
    block = text[idx:end]
    assert token in block, f"{skill}: missing {token!r} in §V-verify block"


@pytest.mark.parametrize("skill", CLAIMS_SKILLS)
def test_claims_heading_present_exactly_once(skill):
    text = _read(skill)
    assert text.count(_ivs.CLAIMS_HEADING) == 1


@pytest.mark.parametrize("skill", CLAIMS_SKILLS)
@pytest.mark.parametrize("marker", [_ivs.CLAIMS_BEGIN, _ivs.CLAIMS_END])
def test_claims_markers_present_exactly_once(skill, marker):
    text = _read(skill)
    assert text.count(marker) == 1


@pytest.mark.parametrize("skill", CLAIMS_SKILLS)
def test_claims_before_verify_ordering(skill):
    """CRIT-1/D-07: the early claims block must sit strictly before the late verify block."""
    text = _read(skill)
    claims_idx = text.index(_ivs.CLAIMS_HEADING)
    verify_idx = text.index(_ivs.VERIFY_HEADING)
    assert claims_idx < verify_idx


def test_claims_anchored_before_step_3b():
    """MIN-1: the early claims block must land immediately before end_of_day's Step 3b,
    i.e. AFTER the daily-cache write, never at the bare Step 3 heading."""
    text = _read("end_of_day")
    claims_idx = text.index(_ivs.CLAIMS_HEADING)
    step3b_idx = text.index("### Step 3b: Review and promote daily insights")
    step3_idx = text.index("### Step 3: Produce the daily cache")
    assert step3_idx < claims_idx < step3b_idx


def test_verify_anchored_before_step5():
    for skill, needle in (
        ("end_of_day", "### Step 5: Report to user"),
        ("start_of_day", "### Step 5: Present the briefing"),
        ("weekly_review", "### Step 5: Present to the user"),
    ):
        text = _read(skill)
        verify_idx = text.index(_ivs.VERIFY_HEADING)
        step5_idx = text.index(needle)
        assert verify_idx < step5_idx, f"{skill}: §V-verify block does not precede {needle!r}"


@pytest.mark.parametrize("skill", VERIFY_SKILLS)
def test_verify_injection_idempotent(skill):
    """Running inject_verify_into_file twice on an in-memory copy -> identical output."""
    skill_md = ADAPTER_SKILLS_DIR / skill / "SKILL.md"
    original_text = skill_md.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_skill = Path(tmpdir) / "SKILL.md"
        tmp_skill.write_text(original_text, encoding="utf-8")

        after_first = _ivs.inject_verify_into_file(skill, tmp_skill)
        tmp_skill.write_text(after_first, encoding="utf-8")
        after_second = _ivs.inject_verify_into_file(skill, tmp_skill)

    assert after_first == after_second, (
        f"{skill}: inject_verify_into_file is NOT idempotent — "
        "second injection produced different output than first."
    )


@pytest.mark.parametrize("skill", CLAIMS_SKILLS)
def test_claims_injection_idempotent(skill):
    skill_md = ADAPTER_SKILLS_DIR / skill / "SKILL.md"
    original_text = skill_md.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_skill = Path(tmpdir) / "SKILL.md"
        tmp_skill.write_text(original_text, encoding="utf-8")

        after_first = _ivs.inject_claims_into_file(skill, tmp_skill)
        tmp_skill.write_text(after_first, encoding="utf-8")
        after_second = _ivs.inject_claims_into_file(skill, tmp_skill)

    assert after_first == after_second, (
        f"{skill}: inject_claims_into_file is NOT idempotent — "
        "second injection produced different output than first."
    )


@pytest.mark.parametrize("skill", LIGHT_SKILLS)
def test_light_heading_present_exactly_once(skill):
    text = _read(skill)
    assert text.count(_ivs.LIGHT_HEADING) == 1


@pytest.mark.parametrize("skill", LIGHT_SKILLS)
@pytest.mark.parametrize("marker", [_ivs.LIGHT_BEGIN, _ivs.LIGHT_END])
def test_light_markers_present_exactly_once(skill, marker):
    text = _read(skill)
    assert text.count(marker) == 1


@pytest.mark.parametrize("skill", LIGHT_SKILLS)
@pytest.mark.parametrize("token", ["verify_claims", "--reconcile-tasks", "surface the contradiction"])
def test_light_required_token_in_block(skill, token):
    text = _read(skill)
    idx = text.index(_ivs.LIGHT_HEADING)
    end = text.index(_ivs.LIGHT_END, idx)
    block = text[idx:end]
    assert token in block, f"{skill}: missing {token!r} in §V-reconcile block"


@pytest.mark.parametrize("skill", LIGHT_SKILLS)
def test_light_injection_idempotent(skill):
    """Running inject_light_into_file twice on an in-memory copy -> identical output."""
    skill_md = ADAPTER_SKILLS_DIR / skill / "SKILL.md"
    original_text = skill_md.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_skill = Path(tmpdir) / "SKILL.md"
        tmp_skill.write_text(original_text, encoding="utf-8")

        after_first = _ivs.inject_light_into_file(skill, tmp_skill)
        tmp_skill.write_text(after_first, encoding="utf-8")
        after_second = _ivs.inject_light_into_file(skill, tmp_skill)

    assert after_first == after_second, (
        f"{skill}: inject_light_into_file is NOT idempotent — "
        "second injection produced different output than first."
    )


def test_absent_verification_ran_is_mismatch():
    """T-06/MAJ-1 consumer-side defense: start_of_day's §V-verify block must instruct
    treating a missing/`no` `verification_ran` field on an in-scope end_of_day session
    as a mismatch signal (not a silent pass) — catches a §V that was silently skipped
    upstream. This is a prose contract (no verify_claims.py function owns it), so it's
    drift-tested here rather than in test_verify_claims.py."""
    text = _read("start_of_day")
    idx = text.index(_ivs.VERIFY_HEADING)
    end = text.index(_ivs.VERIFY_END, idx)
    block = text[idx:end]
    assert "verification_ran" in block
    assert "mismatch" in block.lower()


def test_run_check_passes_on_committed_tree():
    result = _ivs.run_check()
    assert result == 0, (
        "inject_verification_step run_check() returned non-zero on the committed tree. "
        "Run `python3 quoin/scripts/inject_verification_step.py` to regenerate."
    )


def test_dry_run_does_not_write(capsys):
    """--dry-run must print previews without touching any adapter file on disk."""
    before = {skill: _read(skill) for skill in set(VERIFY_SKILLS) | set(CLAIMS_SKILLS) | set(LIGHT_SKILLS)}
    result = _ivs.run_inject(dry_run=True)
    assert result == 0
    captured = capsys.readouterr()
    assert "preview" in captured.out
    for skill, text in before.items():
        assert _read(skill) == text, f"{skill}: --dry-run modified the file on disk"
