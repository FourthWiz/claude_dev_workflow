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

# Ceilings = current measured SOURCE size (Stage 1 / T-01 baseline
# date 2026-08-02) for files this wave did NOT slim; RATCHETED (T-12, Stage 6,
# 2026-08-02) to post-slim size * 1.10 (rounded up) for files that WERE slimmed
# this wave (checkpoint, claude_md — see T-06/T-07/T-08).
#
# The 20 §0-carrying skill ceilings were RE-BASELINED on 2026-08-02 (IVG-165
# Commits N1 + N2): N1's generator-conversion boundary marker
# (`<!-- §0-end -->`) adds exactly +17 bytes to every §0 region BY
# CONSTRUCTION (proc:marker-place in the IVG-165 plan), not regrowth. N2
# additionally normalizes 3 pre-existing off-axis prose residuals surfaced by
# the D-08 residual protocol (cleanup/sleep: +256 bytes each, missing
# "escape hatch" sentence added to match the other 17 carriers' wording;
# implement: -1 byte, stray blank line removed) so the upcoming generator
# (Commit A) can render all 20 with an EMPTY diff. This is an AUTHORIZED
# one-time exception to the "do not hand-raise a ceiling" rule below, scoped
# exactly to the marker delta + these 3 named residual normalizations — do
# not treat this re-baseline as license to hand-raise a ceiling for any OTHER
# reason. IVG-165 Commit R re-ratchets all 20 to post-slim size * 1.10 once
# Step B slims the now generator-owned template. Until Commit R lands, a
# failure here (outside the N1/N2 re-baseline above) means
# a file grew for a reason other than the marker and needs to shrink back down.
CEILINGS = {
    "skill:capture_insight": 12254,
    "skill:checkpoint": 77799,  # T-12 ratchet: post-slim 70726 * 1.10 (unaffected by N1/N2 re-baseline; already >= new size)
    "skill:cleanup": 17702,  # N2: +256 bytes, escape-hatch sentence normalized in (D-08 class-b residue)
    "skill:continue_work": 14691,
    "skill:cost_snapshot": 20261,
    "skill:end_of_day": 45583,
    "skill:end_of_task": 50776,
    "skill:expand": 19375,
    "skill:gate": 56830,
    "skill:implement": 49816,  # N2: -1 byte, stray blank line before "Otherwise" removed (D-08 class-b residue)
    "skill:next_steps": 11990,
    "skill:pr": 18743,
    "skill:revise-fast": 26913,
    "skill:rollback": 22118,
    "skill:sleep": 25294,  # N2: +256 bytes, escape-hatch sentence normalized in (D-08 class-b residue)
    "skill:start_of_day": 26580,
    "skill:status": 9022,
    "skill:triage": 31368,
    "skill:weekly_review": 17169,
    "skill:workspace": 17566,
    "claude_md": 40726,  # T-12 ratchet: post-slim 37023 * 1.10
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
