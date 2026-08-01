"""IVG-162 T-02: per-file byte-ceiling checks (provisional = current size).

Guards the 20 SECTION0_SKILLS deployed SKILL.md SOURCE files (the §0-carrying
skill set — see quoin/CLAUDE.md "### §0 Model dispatch preamble") plus the
quoin/CLAUDE.md SOURCE file, against a per-file byte ceiling.

Modeled on test_preamble_freshness.py (TestSizeBudget — parametrized per-file,
independent assertions) and test_claude_md_size_ceiling.py (source-guard, not
deployed — D-06: measuring SOURCE keeps this test deterministic and
env-independent; the footprint REPORT (footprint_report.py / T-01) measures
DEPLOYED copies separately for the token-saving narrative).

Ceilings are PROVISIONAL at Stage 1: each equals the file's CURRENT measured
size (captured alongside the T-01 footprint baseline
`.workflow_artifacts/ivg-162-token-optimization-wave1/footprint-baseline.json`)
— nothing fails yet. Stage 6 (T-12) ratchets every slimmed file's ceiling down
to post-slim size * 1.10 (rounded up), so this test starts guarding regrowth
only once the wave's slims have landed.

Each file is an INDEPENDENT parametrized assertion (hard constraint — not one
aggregate budget), so a regression in one file never masks a regression in
another, and a single ratchet edit (T-12) never has to touch every case.
"""

import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
QUOIN_DIR = HERE.parent.parent  # quoin/dev/tests -> quoin/dev -> quoin
SKILLS_DIR = QUOIN_DIR / "adapters" / "claude" / "skills"
CLAUDE_MD = QUOIN_DIR / "CLAUDE.md"

# The 20 §0-carrying skills (single source of truth: quoin/CLAUDE.md "### §0
# Model dispatch preamble" skill list, byte-mirrored against
# test_quoin_stage1_worktree_fallback.py's SOURCE_MUTATING_WORKTREE_SKILLS
# subset for the 5 sidecar carriers within this set).
SECTION0_SKILLS = [
    "gate",
    "end_of_day",
    "start_of_day",
    "triage",
    "capture_insight",
    "cleanup",
    "cost_snapshot",
    "weekly_review",
    "end_of_task",
    "implement",
    "rollback",
    "expand",
    "revise-fast",
    "sleep",
    "next_steps",
    "checkpoint",
    "continue_work",
    "pr",
    "status",
    "workspace",
]

# PROVISIONAL ceilings = current measured SOURCE size (Stage 1 / T-01 baseline
# date 2026-08-02). Ratcheted DOWN post-slim by T-12 in Stage 6 — do not
# hand-raise a ceiling to "fix" a failure; a failure here means a file grew
# and the wave's slim target for that file needs to shrink it back down.
CEILINGS = {
    "skill:capture_insight": 12237,
    "skill:checkpoint": 94408,
    "skill:cleanup": 17429,
    "skill:continue_work": 15477,
    "skill:cost_snapshot": 20244,
    "skill:end_of_day": 46351,
    "skill:end_of_task": 51550,
    "skill:expand": 20119,
    "skill:gate": 57562,
    "skill:implement": 50579,
    "skill:next_steps": 11973,
    "skill:pr": 19463,
    "skill:revise-fast": 27687,
    "skill:rollback": 22874,
    "skill:sleep": 25021,
    "skill:start_of_day": 26563,
    "skill:status": 9005,
    "skill:triage": 31351,
    "skill:weekly_review": 17152,
    "skill:workspace": 18328,
    "claude_md": 39136,
}


def _target_path(key: str) -> pathlib.Path:
    if key == "claude_md":
        return CLAUDE_MD
    assert key.startswith("skill:"), f"unrecognized ceiling key: {key}"
    skill = key.split(":", 1)[1]
    return SKILLS_DIR / skill / "SKILL.md"


def test_section0_skills_set_matches_ceiling_keys():
    """Guard against the 20-skill set and the ceiling dict silently drifting apart."""
    assert len(SECTION0_SKILLS) == 20, (
        f"expected exactly 20 §0-carrying skills, got {len(SECTION0_SKILLS)}"
    )
    skill_keys = {k for k in CEILINGS if k.startswith("skill:")}
    expected_keys = {f"skill:{s}" for s in SECTION0_SKILLS}
    assert skill_keys == expected_keys, (
        f"CEILINGS skill keys {skill_keys} do not match SECTION0_SKILLS {expected_keys}"
    )


@pytest.mark.parametrize("key", sorted(CEILINGS.keys()))
def test_file_within_byte_ceiling(key):
    path = _target_path(key)
    assert path.exists(), f"ceiling target missing on disk: {path}"
    size = len(path.read_bytes())
    ceiling = CEILINGS[key]
    assert size <= ceiling, (
        f"{path} is {size} bytes, exceeds provisional ceiling of {ceiling} bytes "
        f"(key={key}). If this is a deliberate wave slim overshoot, ratchet the "
        f"ceiling per T-12 (Stage 6) with a rationale, never silently."
    )
