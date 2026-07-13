"""IVG-138 T-07: token-parity greps over gate/SKILL.md for the CI mirror wiring.

Per-region two-slicer (lesson 2026-06-04, cloned from
test_gate_deploy_drift_tokens.py): each named region is located by its header
string and the `CI mirror` / `ci_mirror.py` tokens are asserted WITHIN that
region, so a dropped region FAILs (a bare occurrence-count would pass while
one region silently lost the row).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"

CHECK_NAME = "CI mirror"
SCRIPT = "ci_mirror.py"

# The three post-implement/post-review sub-regions are delimited by bold text, not
# real markdown headings, so `^#{2,3} ` alone does not isolate them from each other
# (they all fall before the next real heading, "### Step 3a: ..."). _region() must
# also stop at the next sibling boundary in this list (mirrors the round-2 MINOR-4
# fix in test_gate_deploy_drift_tokens.py).
_REGION_BOUNDARIES = (
    "*Standard gate (Small and Medium tasks):*",
    "*Full gate (Large tasks) — includes everything in Standard, plus:*",
    "**After /review → before /end_of_task (Full gate — always, all task sizes):**",
)


def _load() -> str:
    return GATE_SKILL.read_text(encoding="utf-8")


def _region(text: str, header: str) -> str:
    start = text.find(header)
    assert start != -1, f"Region header not found in gate SKILL.md: {header!r}"
    after = text[start + len(header):]
    m = re.search(r"^#{2,3} ", after, re.MULTILINE)
    end = m.start() if m else len(after)
    for boundary in _REGION_BOUNDARIES:
        if boundary == header:
            continue
        idx = after.find(boundary)
        if idx != -1 and idx < end:
            end = idx
    return after[:end]


def test_script_referenced():
    assert SCRIPT in _load(), "gate/SKILL.md must reference ci_mirror.py"


def test_quoin_home_token_form():
    assert f"__QUOIN_HOME__/scripts/{SCRIPT}" in _load(), (
        "gate/SKILL.md must invoke ci_mirror.py via __QUOIN_HOME__/scripts/")


def test_token_in_standard_gate():
    region = _region(_load(), "*Standard gate (Small and Medium tasks):*")
    assert CHECK_NAME in region and SCRIPT in region


def test_token_in_full_gate():
    region = _region(_load(), "*Full gate (Large tasks)")
    assert CHECK_NAME in region and SCRIPT in region


def test_token_in_post_review():
    region = _region(_load(), "**After /review → before /end_of_task")
    assert CHECK_NAME in region and SCRIPT in region


def test_token_in_step5_audit():
    # The audit enumeration carries the check NAME (the script filename lives in
    # the checklist invocation rows, mirroring the Affected-area test suite /
    # Deploy drift convention).
    region = _region(_load(), "### Step 5: Write audit log")
    assert CHECK_NAME in region


def test_blocking_surface_and_exit3_wording_in_post_implement():
    for header in (
        "*Standard gate (Small and Medium tasks):*",
        "*Full gate (Large tasks)",
    ):
        region = _region(_load(), header)
        assert "BLOCKING-SURFACE" in region, (
            f"post-implement {header!r} region must carry BLOCKING-SURFACE wording for CI mirror exit 3")
        assert "exit 3" in region, (
            f"post-implement {header!r} region must mention exit 3 for CI mirror")


def test_script_missing_warn_wording_in_post_implement():
    for header in (
        "*Standard gate (Small and Medium tasks):*",
        "*Full gate (Large tasks)",
    ):
        region = _region(_load(), header)
        assert "WARN" in region, (
            f"post-implement {header!r} region must carry the script-missing WARN carve-out")


def test_fail_wording_in_post_review():
    region = _region(_load(), "**After /review → before /end_of_task")
    assert "BLOCKING FAIL" in region, "post-review CI mirror row must be a blocking FAIL"


def test_subregions_do_not_leak_into_each_other():
    # Regression guard (mirrors round-2 MINOR-4 in test_gate_deploy_drift_tokens.py):
    # before the region-boundary fix, _region("*Standard gate...") could engulf the
    # Full-gate and post-review bold sub-regions too (all three sit before the next
    # real markdown heading). Assert each region's exclusive content stays put.
    text = _load()
    standard = _region(text, "*Standard gate (Small and Medium tasks):*")
    full = _region(text, "*Full gate (Large tasks)")
    post_review = _region(text, "**After /review → before /end_of_task")

    # "All planned tasks are implemented" only appears in the Full gate checklist.
    assert "All planned tasks are implemented" not in standard
    assert "All planned tasks are implemented" in full

    # "pre-merge gate" only appears in the post-review Deploy drift row's framing text.
    assert "pre-merge gate" not in standard
    assert "pre-merge gate" not in full
    assert "pre-merge gate" in post_review


def test_region_isolation_catches_single_region_row_drop():
    # Synthetic reproduction: with a naive (unfixed) _region, a CI-mirror row
    # dropped from ONLY the Full-gate sub-region would still make
    # test_token_in_full_gate pass, because the region slice would leak content
    # from the sibling post-review sub-region below it. The fixed _region must
    # isolate the Full-gate region so the drop is actually visible.
    synthetic = (
        "**After /implement -> before /review:**\n\n"
        "*Standard gate (Small and Medium tasks):*\n"
        "- [ ] CI mirror check\n\n"
        "*Full gate (Large tasks) — includes everything in Standard, plus:*\n"
        "- [ ] some other unrelated check\n\n"  # CI mirror row dropped here only
        "**After /review → before /end_of_task (Full gate — always, all task sizes):**\n"
        "- [ ] CI mirror check\n\n"
        "### Step 3a: next real heading\n"
    )
    full = _region(synthetic, "*Full gate (Large tasks) — includes everything in Standard, plus:*")
    assert CHECK_NAME not in full, (
        "region isolation must expose a row dropped from only the Full-gate sub-region")
