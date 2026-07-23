"""needs-decision sentinel field-schema drift test (IVG-150, T-21 / AC-3).

The existing test_autonomous_sentinel_contract.py covers path templates / roster ONLY, NOT
field schemas — so this is a NEW test. It asserts the helper-written sentinel has exactly the 7
documented fields, that decision-gate-guard.md documents the same 7 field names (doc<->code
byte-match), and that the filename template is DISTINCT from the autonomous-halt family.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent
CORE_PATH = PKG_DIR / "core" / "scripts" / "decision_gate_guard.py"
RULE_DOC = PKG_DIR / "memory" / "decision-gate-guard.md"

_spec = importlib.util.spec_from_file_location("_dgg_core_t21", CORE_PATH)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

EXPECTED_FIELDS = ("task", "trigger", "skill", "site", "reason", "timestamp", "resume_hint")


def test_needs_decision_schema_fields(tmp_path):
    core.main([
        "fail-closed", "--task", "t", "--skill", "s", "--site", "x",
        "--reason", "r", "--resume-hint", "h", "--project-root", str(tmp_path),
    ])
    sentinel = tmp_path / ".workflow_artifacts" / "memory" / "needs-decision-t.md"
    lines = sentinel.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 7
    fields = tuple(ln.split(":", 1)[0] for ln in lines)
    assert fields == EXPECTED_FIELDS
    # code<->constant agreement
    assert tuple(core.SENTINEL_FIELDS) == EXPECTED_FIELDS
    # doc documents the SAME 7 field names (doc<->code byte-match)
    doc = RULE_DOC.read_text(encoding="utf-8")
    for field in EXPECTED_FIELDS:
        assert f"{field}:" in doc, f"decision-gate-guard.md does not document field '{field}'"
    assert "trigger: non-interactive-decision-gate" in doc


def test_needs_decision_distinct_from_halt_template():
    assert core.SENTINEL_TEMPLATE == "needs-decision-{task}.md"
    assert core.HALT_TEMPLATE == "autonomous-halt-{task}.md"
    assert core.SENTINEL_TEMPLATE != core.HALT_TEMPLATE
    # both docs agree on the distinct-filename rule
    doc = RULE_DOC.read_text(encoding="utf-8")
    assert "needs-decision-{task}.md" in doc
    assert "autonomous-halt-{task}.md" in doc
    assert "DISTINCT" in doc
