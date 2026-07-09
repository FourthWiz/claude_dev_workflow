"""IVG-136 T-07: token-parity greps over gate/SKILL.md for the Deploy drift wiring.

Per-region two-slicer (lesson 2026-06-04): each named region is located by its header
string and the `Deploy drift` / `deploy_drift_check.py` tokens are asserted WITHIN that
region, so a dropped region FAILs (a bare occurrence-count would pass while one region
silently lost the row). Also asserts (round-1 MAJ-1/MAJ-2 gaps): a distinct exit-2
mention and the "not covered" coverage qualifier actually landed in the SKILL.md text.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"

CHECK_NAME = "Deploy drift"
SCRIPT = "deploy_drift_check.py"


def _load() -> str:
    return GATE_SKILL.read_text(encoding="utf-8")


def _region(text: str, header: str) -> str:
    start = text.find(header)
    assert start != -1, f"Region header not found in gate SKILL.md: {header!r}"
    after = text[start + len(header):]
    m = re.search(r"^#{2,3} ", after, re.MULTILINE)
    return after[: m.start()] if m else after


def test_script_referenced():
    assert SCRIPT in _load(), "gate/SKILL.md must reference deploy_drift_check.py"


def test_quoin_home_token_form():
    assert f"__QUOIN_HOME__/scripts/{SCRIPT}" in _load(), (
        "gate/SKILL.md must invoke deploy_drift_check.py via __QUOIN_HOME__/scripts/")


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
    # The audit enumeration carries the check NAME (the script filename lives in the
    # checklist invocation rows, mirroring the Affected-area test suite convention).
    region = _region(_load(), "### Step 5: Write audit log")
    assert CHECK_NAME in region


def test_warn_wording_in_post_implement():
    region = _region(_load(), "*Standard gate (Small and Medium tasks):*")
    assert "WARN" in region, "post-implement Deploy drift row must be WARN (non-blocking)"


def test_fail_wording_in_post_review():
    region = _region(_load(), "**After /review → before /end_of_task")
    assert "BLOCKING FAIL" in region, "post-review Deploy drift row must be a blocking FAIL"


def test_exit2_row_distinct_from_exit1_and_exit3():
    # An explicit exit-2 mention must exist distinct from the exit-1/exit-3 rows.
    region = _region(_load(), "*Standard gate (Small and Medium tasks):*")
    assert "exit 2" in region and "exit 1" in region and "exit 3" in region, (
        "Deploy drift row must enumerate exit 1, exit 2, and exit 3 distinctly")


def test_coverage_qualifier_present():
    # The "not covered" qualifier from T-03/T-05 must be present in at least one region.
    assert "not covered" in _load(), (
        "gate/SKILL.md must carry the checked/not-covered coverage qualifier verbatim")
