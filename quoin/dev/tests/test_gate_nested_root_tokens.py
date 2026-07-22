"""IVG-119 T-10: token-parity greps over gate/SKILL.md for the Nested memory roots wiring.

Modeled on test_gate_deploy_drift_tokens.py (per-region two-slicer, lesson 2026-06-04):
each named region is located by its header string and the `Nested memory roots` /
`nested_root_check.py` tokens are asserted WITHIN that region, so a dropped region FAILs.
Unlike Deploy drift, this check is WARN-only — it NEVER blocks at any gate phase (incl.
post-review), so there is no BLOCKING-FAIL assertion.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "gate" / "SKILL.md"

CHECK_NAME = "Nested memory roots"
SCRIPT = "nested_root_check.py"

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
    assert SCRIPT in _load(), "gate/SKILL.md must reference nested_root_check.py"


def test_quoin_home_token_form():
    assert f"__QUOIN_HOME__/scripts/{SCRIPT}" in _load(), (
        "gate/SKILL.md must invoke nested_root_check.py via __QUOIN_HOME__/scripts/")


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
    region = _region(_load(), "### Step 5: Write audit log")
    assert CHECK_NAME in region


def test_warn_only_never_blocks():
    # The check is WARN-only at every phase; assert no BLOCKING-FAIL wording ever
    # attaches to a nested-root row (post-review included).
    for header in (
        "*Standard gate (Small and Medium tasks):*",
        "**After /review → before /end_of_task",
    ):
        region = _region(_load(), header)
        assert CHECK_NAME in region
        assert "WARN" in region


def test_subregions_do_not_leak_into_each_other():
    text = _load()
    standard = _region(text, "*Standard gate (Small and Medium tasks):*")
    full = _region(text, "*Full gate (Large tasks)")
    post_review = _region(text, "**After /review → before /end_of_task")

    assert "All planned tasks are implemented" not in standard
    assert "All planned tasks are implemented" in full
    assert "pre-merge gate" not in standard
    assert "pre-merge gate" not in full
    assert "pre-merge gate" in post_review


def test_region_isolation_catches_single_region_row_drop():
    synthetic = (
        "**After /implement -> before /review:**\n\n"
        "*Standard gate (Small and Medium tasks):*\n"
        "- [ ] Nested memory roots check\n\n"
        "*Full gate (Large tasks) — includes everything in Standard, plus:*\n"
        "- [ ] some other unrelated check\n\n"  # Nested memory roots row dropped here only
        "**After /review → before /end_of_task (Full gate — always, all task sizes):**\n"
        "- [ ] Nested memory roots check\n\n"
        "### Step 3a: next real heading\n"
    )
    full = _region(synthetic, "*Full gate (Large tasks) — includes everything in Standard, plus:*")
    assert CHECK_NAME not in full, (
        "region isolation must expose a row dropped from only the Full-gate sub-region")
