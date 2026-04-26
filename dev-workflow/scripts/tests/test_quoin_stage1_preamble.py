"""
Quoin Stage 1 — structural consistency tests for the §0 self-dispatch preamble.

The 12 cheap-tier SKILL.md files carry a `## §0 Model dispatch ...` block as
the first body H2 after the H1. This test file enforces the static-structural
invariants of that block: heading uniqueness, ordering, two-layer dispatch
contract (load-bearing `model:` parameter line + defensive `dispatched-tier:`
marker), placeholder substitution, sentinel grammar, load-bearing-rule
preservation, and the revise/revise-fast SYNC contract.

Per Stage 1 plan D-03 and lesson 2026-04-23 LLM-replay non-determinism: this
file contains NO live LLM calls — only deterministic pathlib + string + YAML
parsing. Functional dispatch verification lives in T-00 (pilot HITL) and T-09
(four-phase HITL smoke), not here.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
SKILLS_DIR = TESTS_DIR.parent.parent / "skills"

SO_HEADING = "## §0 Model dispatch (FIRST STEP — execute before anything else)"
MR_HEADING = "## Model requirement"

# 12 cheap-tier skills — must carry §0.
CHEAP_TIER_SKILLS = [
    "gate",
    "end_of_day",
    "start_of_day",
    "capture_insight",
    "cost_snapshot",
    "weekly_review",
    "end_of_task",
    "implement",
    "rollback",
    "expand",
    "revise-fast",
    "triage",
]

# 9 Opus-tier skills — must NOT carry §0.
OPUS_TIER_SKILLS = [
    "architect",
    "plan",
    "critic",
    "revise",
    "thorough_plan",
    "run",
    "init_workflow",
    "discover",
    "review",
]

YAML_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _yaml_field(yaml_block: str, field: str) -> str:
    for line in yaml_block.splitlines():
        line = line.rstrip()
        if line.startswith(f"{field}:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return value
    raise AssertionError(f"YAML field `{field}` not found in: {yaml_block[:200]}")


def extract_preamble_block(skill_path: Path) -> str:
    """Return the §0 block content (heading line through last line before next ## H2).

    Slice is inclusive of the §0 heading line and exclusive of the next H2
    heading. Used by every §0-content assertion to prevent collision with
    YAML frontmatter `model: ...` lines (which sit OUTSIDE the slice).
    """
    text = skill_path.read_text(encoding="utf-8")
    match = re.search(
        r"^## §0 Model dispatch \(FIRST STEP — execute before anything else\).+?(?=^## )",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    if not match:
        return ""
    return match.group(0)


# -----------------------------------------------------------------------------
# (a) Each cheap-tier skill has exactly one §0 heading.
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("skill", CHEAP_TIER_SKILLS)
def test_each_skill_has_preamble_heading(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    count = text.count(SO_HEADING)
    assert count == 1, (
        f"{skill}/SKILL.md contains the §0 heading {count} times (expected exactly 1). "
        f"Heading literal: {SO_HEADING!r}"
    )


# -----------------------------------------------------------------------------
# (b) The §0 heading is the FIRST `## ` heading after the H1 — i.e., the first
# body H2 the model encounters after skill identity. Phrased durably so a future
# maintainer adding a documentation H2 (e.g., `## Note: renamed in 2027`) gets
# a clear failure message rather than a tangential one.
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("skill", CHEAP_TIER_SKILLS)
def test_each_skill_first_body_h2_is_preamble(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    # Skip frontmatter to find the H1.
    after_yaml = YAML_RE.sub("", text, count=1)
    body_h2_lines = [ln for ln in after_yaml.splitlines() if ln.startswith("## ")]
    assert body_h2_lines, f"{skill}/SKILL.md has no body H2 headings"
    assert body_h2_lines[0] == SO_HEADING, (
        f"{skill}/SKILL.md first body H2 is {body_h2_lines[0]!r}, expected the §0 heading. "
        "If a documentation H2 was added before §0, move it after §0 — the cost-guardrail "
        "rule (D-04) requires §0 to be the first H2 the model encounters."
    )


# -----------------------------------------------------------------------------
# (c) Two-layer dispatch contract:
#   (i)   load-bearing: literal `model: "<declared>"` parameter line in slice
#   (ii)  defensive marker: `dispatched-tier:` token in slice
#   (iii) placeholder substitution complete: no `<declared>` or `<skill name>`
#   (iv)  discrimination proof: `dispatched-tier` does NOT appear OUTSIDE slice
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("skill", CHEAP_TIER_SKILLS)
def test_each_skill_preamble_substitutes_declared_model(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    yaml_match = YAML_RE.match(text)
    assert yaml_match, f"{skill}/SKILL.md has no YAML frontmatter"
    declared = _yaml_field(yaml_match.group(1), "model")
    assert declared in ("haiku", "sonnet"), (
        f"{skill}/SKILL.md declares model={declared!r}; expected `haiku` or `sonnet` "
        "(opus-tier skills must not carry §0)."
    )

    slice_text = extract_preamble_block(path)
    assert slice_text, f"{skill}/SKILL.md §0 slice is empty"

    # (i) Load-bearing: actual `model: "<declared>"` parameter line.
    pattern = r'^\s*model: "' + re.escape(declared) + r'"\s*$'
    assert re.search(pattern, slice_text, re.MULTILINE), (
        f"{skill}/SKILL.md §0 slice missing literal `model: \"{declared}\"` parameter line. "
        "This is the load-bearing layer of the round-3 MAJ-1 fix — without it, the dispatch "
        "silently no-ops."
    )

    # (ii) Defensive marker.
    assert "dispatched-tier:" in slice_text, (
        f"{skill}/SKILL.md §0 slice missing `dispatched-tier:` marker token "
        "(D-06 layer 2 — defensive signal that the dispatch action was authored deliberately)."
    )

    # (iii) Placeholder substitution complete.
    assert "<declared>" not in slice_text, (
        f"{skill}/SKILL.md §0 slice still contains literal `<declared>` placeholder. "
        "T-02 substitution failed — re-run the per-skill substitution from the YAML model field."
    )
    assert "<skill name>" not in slice_text, (
        f"{skill}/SKILL.md §0 slice still contains literal `<skill name>` placeholder. "
        "T-02 substitution failed — re-run the per-skill substitution from the YAML name field."
    )

    # (iv) Discrimination proof: `dispatched-tier` token must NOT appear outside the §0 slice.
    pre_slice = text.split("## §0", 1)[0]
    assert "dispatched-tier" not in pre_slice, (
        f"{skill}/SKILL.md contains `dispatched-tier` token OUTSIDE the §0 slice "
        "(in pre-§0 region — frontmatter or intro prose). The slicer is failing to discriminate."
    )


# -----------------------------------------------------------------------------
# (d) None of the 9 Opus-tier skills carry §0 (catches accidental over-application).
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("skill", OPUS_TIER_SKILLS)
def test_no_opus_tier_skill_has_preamble(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert SO_HEADING not in text, (
        f"{skill}/SKILL.md is opus-tier but contains the §0 heading. The Stage 1 architecture "
        "scope explicitly limits §0 to the 12 cheap-tier skills (D-01)."
    )


# -----------------------------------------------------------------------------
# (e) Sentinel grammar: bare `[no-redispatch]`, counter form `[no-redispatch:N]`,
# abort message leading constant, AND the I-01 fail-graceful warning string —
# all must appear in every cheap-tier skill's §0 slice.
# -----------------------------------------------------------------------------
RECURSION_TOKENS = [
    "[no-redispatch]",
    "[no-redispatch:N]",
    "Quoin self-dispatch hard-cap reached at N=",
    "[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]",
]


@pytest.mark.parametrize("skill", CHEAP_TIER_SKILLS)
@pytest.mark.parametrize("token", RECURSION_TOKENS)
def test_recursion_abort_sentinel_present(skill, token):
    path = SKILLS_DIR / skill / "SKILL.md"
    slice_text = extract_preamble_block(path)
    assert token in slice_text, (
        f"{skill}/SKILL.md §0 slice missing required sentinel/grammar token: {token!r}"
    )


# -----------------------------------------------------------------------------
# (f) Pre-§0 intro region preserved — count lines between H1 and §0 heading,
# assert ≥ 0 (smoke check that the per-file Edit anchor did not delete intro).
# Actual content equality is checked by git diff in T-08.
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("skill", CHEAP_TIER_SKILLS)
def test_no_inter_h2_prose_deleted_by_insertion(skill):
    path = SKILLS_DIR / skill / "SKILL.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    h1_idx = next((i for i, ln in enumerate(lines) if ln.startswith("# ") and not ln.startswith("## ")), None)
    so_idx = next((i for i, ln in enumerate(lines) if ln == SO_HEADING), None)
    assert h1_idx is not None, f"{skill}/SKILL.md has no H1"
    assert so_idx is not None, f"{skill}/SKILL.md has no §0 heading"
    inter_count = so_idx - h1_idx - 1
    assert inter_count >= 0, (
        f"{skill}/SKILL.md §0 heading appears before H1 (h1_idx={h1_idx}, so_idx={so_idx}). "
        "T-02 insertion broke the file structure."
    )


# -----------------------------------------------------------------------------
# (g) Load-bearing rules preserved — for skills with semantically critical H2s
# that must remain present and ORDERED AFTER §0, assert both invariants hold.
# Catches accidental deletion or reordering during §0 insertion.
# -----------------------------------------------------------------------------
LOAD_BEARING_HEADINGS = {
    "implement": "## Explicit invocation only",
    "expand": "## Hardcoded Tier 1 path list",
    "end_of_task": "## When to use",
}


@pytest.mark.parametrize("skill,heading", sorted(LOAD_BEARING_HEADINGS.items()))
def test_load_bearing_rules_preserved(skill, heading):
    path = SKILLS_DIR / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert SO_HEADING in text, f"{skill}/SKILL.md missing §0 heading"
    assert heading in text, (
        f"{skill}/SKILL.md missing load-bearing heading {heading!r} — "
        "T-02 insertion likely deleted it."
    )
    so_idx = text.index(SO_HEADING)
    rule_idx = text.index(heading)
    assert so_idx < rule_idx, (
        f"{skill}/SKILL.md: §0 heading appears AFTER load-bearing heading {heading!r}. "
        "Per D-04 cost-guardrail rule, §0 must precede every load-bearing rule so the "
        "model decides to dispatch BEFORE encountering the rule."
    )


# -----------------------------------------------------------------------------
# (h) revise/SKILL.md ↔ revise-fast/SKILL.md SYNC contract — every diff line
# must fall inside the `## Model requirement` section OR the `## §0 ...` block.
# Promotes the SYNC WARNING comment from documentation to enforced contract.
# -----------------------------------------------------------------------------
def test_revise_revise_fast_sync_contract():
    revise_text = (SKILLS_DIR / "revise" / "SKILL.md").read_text(encoding="utf-8")
    revise_fast_text = (SKILLS_DIR / "revise-fast" / "SKILL.md").read_text(encoding="utf-8")

    # Slice from the H1 line (anchored regex — substring match would land inside
    # the SYNC WARNING comment block in revise-fast, which references the H1
    # token in its `sed -n '/^# Revise/,$p'` diff command).
    h1_re = re.compile(r"^# Revise\s*$", re.MULTILINE)
    a_match = h1_re.search(revise_text)
    b_match = h1_re.search(revise_fast_text)
    assert a_match, "revise/SKILL.md missing `# Revise` H1"
    assert b_match, "revise-fast/SKILL.md missing `# Revise` H1"
    revise_body = revise_text[a_match.start():]
    revise_fast_body = revise_fast_text[b_match.start():]

    a_lines = revise_body.splitlines()
    b_lines = revise_fast_body.splitlines()

    def section_at(lines: list[str], idx: int) -> str | None:
        if idx >= len(lines):
            return None
        # Look back for the most recent `## ` heading.
        for i in range(idx, -1, -1):
            if lines[i].startswith("## "):
                return lines[i]
        # No preceding heading. If this is a blank line and the next non-blank
        # line is a `## ` heading, classify as belonging to that heading's
        # section (handles the blank line immediately preceding §0 in
        # revise-fast, which SequenceMatcher includes in the insert opcode).
        if not lines[idx].strip():
            for j in range(idx + 1, len(lines)):
                if lines[j].startswith("## "):
                    return lines[j]
                if lines[j].strip():
                    return None
        return None

    allowed_sections = {SO_HEADING, MR_HEADING}
    sm = difflib.SequenceMatcher(a=a_lines, b=b_lines, autojunk=False)
    unexpected = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for i in range(i1, i2):
            sec = section_at(a_lines, i)
            if sec not in allowed_sections:
                unexpected.append(
                    f"  revise/SKILL.md line {i+1} (section={sec!r}): {a_lines[i]!r}"
                )
        for j in range(j1, j2):
            sec = section_at(b_lines, j)
            if sec not in allowed_sections:
                unexpected.append(
                    f"  revise-fast/SKILL.md line {j+1} (section={sec!r}): {b_lines[j]!r}"
                )

    assert not unexpected, (
        "Unexpected diff lines between revise and revise-fast — only the "
        "`## Model requirement` section AND the `## §0 Model dispatch ...` block "
        "may differ:\n" + "\n".join(unexpected[:20])
    )
