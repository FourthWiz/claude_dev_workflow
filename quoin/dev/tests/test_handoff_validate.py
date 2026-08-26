"""
Black-box pytest tests for handoff_validate.py (T-10, AC-04).

Tests call the CORE validator via subprocess against synthetic payload
fixtures in quoin/dev/tests/fixtures/handoff_validate/ — mirrors the
test_validate_artifact.py pattern (subprocess, no import of validator
internals). Every fixture is a whole payload per D-22: sentinel zone (where
applicable), marker-delimited envelope, and trailing prose — never a bare
envelope block.

Three set-equalities close the coverage gap named in R-27/R-31/R-32:
  1. rule-ID coverage: the spec's checkable-rule table, the validator's
     emitted rule IDs, and this file's asserted IDs must agree exactly
     over the 20 checkable rules (H-21 is RECOMMENDED and excluded).
  2. status coverage: the four-member status enum must be exercised by
     both a conforming return fixture and an H-05 violating fixture.
  3. a synthetic-table unit test proves the RECOMMENDED-row filter used
     for (1) actually drops the row it's supposed to, rather than being
     unreachable code.

Run: pytest quoin/dev/tests/test_handoff_validate.py -v
"""

import os
import re
import subprocess
import sys

# ── Path setup ────────────────────────────────────────────────────────────

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TEST_DIR, "fixtures", "handoff_validate")
DEV_DIR = os.path.dirname(TEST_DIR)               # quoin/dev/
QUOIN_DIR = os.path.dirname(DEV_DIR)               # quoin/
PROJECT_ROOT = os.path.dirname(QUOIN_DIR)          # project root

VALIDATOR = os.path.join(QUOIN_DIR, "core", "scripts", "handoff_validate.py")
SPEC = os.path.join(QUOIN_DIR, "core", "workflow", "handoff-format.md")


def fixture(name):
    return os.path.join(FIXTURES_DIR, name)


def run_validator(name, *extra_args):
    """Helper: run the CORE validator against a named fixture, return (rc, stderr_lines)."""
    cmd = [sys.executable, VALIDATOR, *extra_args, fixture(name)]
    result = subprocess.run(cmd, capture_output=True, cwd=PROJECT_ROOT)
    stderr = result.stderr.decode("utf-8", errors="replace")
    lines = [ln for ln in stderr.splitlines() if ln.strip()]
    return result.returncode, lines


# ── Conforming fixtures (six): dispatch, one return per status, tabular ────


def test_conforming_dispatch_exits_clean():
    rc, lines = run_validator("conforming-dispatch.md")
    assert rc == 0
    assert lines == []


def test_conforming_return_complete_exits_clean():
    rc, lines = run_validator("conforming-return-complete.md")
    assert rc == 0
    assert lines == []


def test_conforming_return_partial_exits_clean():
    rc, lines = run_validator("conforming-return-partial.md")
    assert rc == 0
    assert lines == []


def test_conforming_return_needs_decision_exits_clean():
    rc, lines = run_validator("conforming-return-needs-decision.md")
    assert rc == 0
    assert lines == []


def test_conforming_return_blocked_exits_clean():
    rc, lines = run_validator("conforming-return-blocked.md")
    assert rc == 0
    assert lines == []


def test_conforming_return_tabular_exits_clean():
    rc, lines = run_validator("conforming-return-tabular.md")
    assert rc == 0
    assert lines == []


# ── Isolation helper ─────────────────────────────────────────────────────
#
# Each violating fixture below is constructed (per current-plan.md T-10 /
# D-29's cascade matrix) to trip exactly one rule. Every assertion checks
# BOTH that the rule's own prefix is present AND that the observed stderr
# line count matches D-29's prediction for that fixture (usually one line),
# so a cascade regression reds the test instead of being silently absorbed.


def _assert_isolated(name, expected_rc, expected_prefix, extra_args=(), expected_lines=1):
    """Assert a fixture trips exactly ONE rule: the stderr line count matches
    D-29's cascade-matrix prediction for this fixture (expected_lines, one by
    construction for every fixture below), and that single line carries the
    target rule's own prefix — so a cascade regression (another rule's
    prefix appearing instead of, or alongside, the target's) reds the test
    rather than being silently absorbed."""
    rc, lines = run_validator(name, *extra_args)
    assert rc == expected_rc, f"{name}: rc={rc}, expected={expected_rc}, stderr={lines}"
    assert len(lines) == expected_lines, f"{name}: {len(lines)} lines, expected {expected_lines}: {lines}"
    assert any(expected_prefix in ln for ln in lines), f"{name}: missing {expected_prefix!r} in {lines}"


# ── H-01 (FATAL, two branches: no marker at all, unmatched close) ──────────


def test_h01_no_marker_at_all():
    _assert_isolated("h01-no-marker.md", 1, "FAIL H-01")


def test_h01_unmatched_close():
    _assert_isolated("h01-unmatched-close.md", 1, "FAIL H-01")


# ── H-02 (ADVISORY, gating: stops evaluation, no FAIL anywhere) ────────────


def test_h02_unknown_major_stops_evaluation():
    rc, lines = run_validator("h02-unknown-major.md")
    assert rc == 0
    assert len(lines) == 1
    assert "WARN H-02" in lines[0]
    assert not any("FAIL" in ln for ln in lines)


# ── H-03 (ADVISORY, non-gating: processing continues) ──────────────────────


def test_h03_unknown_minor_continues_processing():
    _assert_isolated("h03-unknown-minor.md", 0, "WARN H-03")


# ── H-04 (FATAL, gating: direction-keyed rules skip) ────────────────────────


def test_h04_bad_direction_keyword():
    _assert_isolated("h04-bad-direction.md", 1, "FAIL H-04")


# ── H-05 (FATAL, one violating fixture per status — MAJ-2) ─────────────────


def test_h05_complete_missing_summary():
    _assert_isolated("h05-complete-missing-summary.md", 1, "FAIL H-05")


def test_h05_partial_missing_remaining():
    _assert_isolated("h05-partial-missing-remaining.md", 1, "FAIL H-05")


def test_h05_needs_decision_missing_reason():
    _assert_isolated("h05-needs-decision-missing-reason.md", 1, "FAIL H-05")


def test_h05_blocked_missing_resume_hint():
    _assert_isolated("h05-blocked-missing-resume-hint.md", 1, "FAIL H-05")


# ── H-06 (FATAL, gating: H-05 degrades, H-14/H-16 still run) ───────────────


def test_h06_bad_status_enum():
    _assert_isolated("h06-bad-status.md", 1, "FAIL H-06")


# ── H-07 (FATAL, checked only when verdict present) ─────────────────────────


def test_h07_bad_verdict_vocabulary():
    _assert_isolated("h07-bad-verdict.md", 1, "FAIL H-07")


# ── H-08 / H-09 (FATAL, byte bounds — value vs. envelope, MIN-7) ───────────


def test_h08_per_value_byte_bound():
    _assert_isolated("h08-value-too-long.md", 1, "FAIL H-08")


def test_h09_envelope_byte_bound():
    _assert_isolated("h09-envelope-too-long.md", 1, "FAIL H-09")


# ── H-10 / H-11 (FATAL, control character / sentinel-in-value) ─────────────


def test_h10_control_character_in_value():
    _assert_isolated("h10-control-char.md", 1, "FAIL H-10")


def test_h11_sentinel_token_in_value():
    _assert_isolated("h11-sentinel-in-value.md", 1, "FAIL H-11")


# ── H-12 (ADVISORY, first occurrence wins) ──────────────────────────────────


def test_h12_duplicate_key_warns():
    _assert_isolated("h12-duplicate-key.md", 0, "WARN H-12")


# ── H-13 (FATAL, two violating clauses per D-22) ────────────────────────────


def test_h13_prose_before_open_marker():
    _assert_isolated("h13-prose-before-marker.md", 1, "FAIL H-13")


def test_h13_marker_shares_line_with_sentinel_zone():
    _assert_isolated("h13-marker-shares-line.md", 1, "FAIL H-13")


# ── H-14 (ADVISORY, unknown key ignored, does not trip H-16) ───────────────


def test_h14_unknown_key_warns():
    _assert_isolated("h14-unknown-key.md", 0, "WARN H-14")


# ── H-15 / H-19 (FATAL, disjoint tabular rules — per-row arity vs. count) ──


def test_h15_tabular_row_arity_mismatch():
    _assert_isolated("h15-row-arity-mismatch.md", 1, "FAIL H-15")


def test_h19_tabular_declared_count_mismatch():
    _assert_isolated("h19-declared-count-mismatch.md", 1, "FAIL H-19")


# ── H-16 (FATAL, subsequence over recognised keys' first occurrences) ──────


def test_h16_bad_field_order():
    _assert_isolated("h16-bad-field-order.md", 1, "FAIL H-16")


# ── H-17 (ADVISORY, literal escape sequence; list/tabular shapes exempt) ───


def test_h17_literal_escape_sequence():
    _assert_isolated("h17-literal-escape.md", 0, "WARN H-17")


# ── H-18 (FATAL, --direction assertion disagrees with marker) ──────────────


def test_h18_direction_assertion_disagrees_with_marker():
    _assert_isolated(
        "h18-direction-mismatch.md", 1, "FAIL H-18", extra_args=("--direction", "dispatch")
    )


# ── H-20 (FATAL, envelope line shape — non-tabular continuation line) ──────


def test_h20_continuation_line_outside_tabular_block():
    _assert_isolated("h20-continuation-line.md", 1, "FAIL H-20")


# ── Status coverage dimension (MAJ-2, D-30) ─────────────────────────────────

_STATUS_ENUM = {"COMPLETE", "PARTIAL", "NEEDS-DECISION", "BLOCKED"}

_CONFORMING_RETURN_FIXTURES = (
    "conforming-return-complete.md",
    "conforming-return-partial.md",
    "conforming-return-needs-decision.md",
    "conforming-return-blocked.md",
)

_H05_VIOLATING_FIXTURES = (
    "h05-complete-missing-summary.md",
    "h05-partial-missing-remaining.md",
    "h05-needs-decision-missing-reason.md",
    "h05-blocked-missing-resume-hint.md",
)


def _harvest_status(fixture_name):
    text = open(fixture(fixture_name), encoding="utf-8").read()
    m = re.search(r"^status: (\S+)$", text, re.MULTILINE)
    assert m, f"{fixture_name}: no status: line found"
    return m.group(1)


def test_status_coverage_conforming_fixtures_exercise_all_four_statuses():
    harvested = {_harvest_status(name) for name in _CONFORMING_RETURN_FIXTURES}
    assert harvested == _STATUS_ENUM, (
        f"conforming fixtures cover {harvested}, enum is {_STATUS_ENUM} "
        f"— missing {_STATUS_ENUM - harvested}"
    )


def test_status_coverage_h05_violating_fixtures_exercise_all_four_statuses():
    harvested = {_harvest_status(name) for name in _H05_VIOLATING_FIXTURES}
    assert harvested == _STATUS_ENUM, (
        f"H-05 violating fixtures cover {harvested}, enum is {_STATUS_ENUM} "
        f"— missing {_STATUS_ENUM - harvested}"
    )


# ── Three-way rule-ID set equality (proc:T-10) ──────────────────────────────
#
# spec_ids: extracted from handoff-format.md's checkable-rule table (the
# only table whose first column is bare H-NN and whose second column is a
# severity token — the Rule Interaction Cascade table's first column carries
# extra prose after the ID, so it never matches this pattern).
# impl_ids: extracted from handoff_validate.py's emitted FAIL/WARN message
# prefixes (not from function names — several rules share one function,
# e.g. check_h_02_h_03, and H-01 has no dedicated function at all since it
# is handled inline in validate(); the message prefix is what the validator
# actually emits and is the accurate proxy for "this rule is implemented").
# test_ids: the IDs this file asserts above.

_SPEC_TABLE_ROW_RE = re.compile(
    r"^\|\s*(H-\d{2})\s*\|\s*(FATAL|ADVISORY|RECOMMENDED)\s*\|", re.MULTILINE
)
_IMPL_MESSAGE_ID_RE = re.compile(r"(?:FAIL|WARN) (H-\d{2}):")

_TEST_IDS = {
    "H-01", "H-02", "H-03", "H-04", "H-05", "H-06", "H-07", "H-08", "H-09",
    "H-10", "H-11", "H-12", "H-13", "H-14", "H-15", "H-16", "H-17", "H-18",
    "H-19", "H-20",
}


def _extract_spec_rule_ids(text, drop_recommended=True):
    """Pure extraction helper over the checkable-rule table's own text shape
    (proc:T-10). Returns the set of rule IDs, optionally dropping RECOMMENDED
    rows. Exposed as a standalone function so the round-3 MIN-5 unit test
    below can feed it a synthetic table independent of the real spec file."""
    ids = set()
    for rule_id, severity in _SPEC_TABLE_ROW_RE.findall(text):
        if drop_recommended and severity == "RECOMMENDED":
            continue
        ids.add(rule_id)
    return ids


def test_rule_id_coverage_spec_impl_test_agree():
    spec_text = open(SPEC, encoding="utf-8").read()
    spec_ids = _extract_spec_rule_ids(spec_text)

    impl_text = open(VALIDATOR, encoding="utf-8").read()
    impl_ids = set(_IMPL_MESSAGE_ID_RE.findall(impl_text))

    assert spec_ids == impl_ids == _TEST_IDS, (
        f"rule-ID coverage mismatch — "
        f"spec-only: {spec_ids - impl_ids - _TEST_IDS or spec_ids - (impl_ids & _TEST_IDS)}, "
        f"impl-only: {impl_ids - spec_ids}, "
        f"test-only: {_TEST_IDS - spec_ids}, "
        f"spec={sorted(spec_ids)} impl={sorted(impl_ids)} test={sorted(_TEST_IDS)}"
    )
    assert len(spec_ids) == 20, f"expected 20 checkable rules, got {len(spec_ids)}"
    assert "H-21" not in spec_ids, "H-21 is RECOMMENDED and must be excluded by the severity filter"


def test_h21_present_in_spec_absent_from_impl_and_test():
    """The RECOMMENDED escape hatch working, not a gap (D-20's own acceptance)."""
    spec_text = open(SPEC, encoding="utf-8").read()
    assert re.search(r"^\|\s*H-21\s*\|\s*RECOMMENDED\s*\|", spec_text, re.MULTILINE)
    impl_text = open(VALIDATOR, encoding="utf-8").read()
    assert "H-21" not in set(_IMPL_MESSAGE_ID_RE.findall(impl_text))
    assert "H-21" not in _TEST_IDS


# ── RECOMMENDED-row filter unit test (round-3 MIN-5) ────────────────────────


def test_extraction_helper_drops_recommended_row_from_synthetic_table():
    synthetic_table = (
        "| Rule | Severity | Description |\n"
        "|---|---|---|\n"
        "| H-90 | FATAL | synthetic fatal rule |\n"
        "| H-91 | ADVISORY | synthetic advisory rule |\n"
        "| H-92 | RECOMMENDED | synthetic recommended rule, unchecked |\n"
    )
    result = _extract_spec_rule_ids(synthetic_table)
    assert result == {"H-90", "H-91"}, f"expected H-90/H-91 only, got {result}"
    assert "H-92" not in result, "RECOMMENDED row must be dropped by the severity filter"

    # And with the filter disabled, the dropped row reappears — proves the
    # filter is what does the dropping, not an unrelated regex mismatch.
    unfiltered = _extract_spec_rule_ids(synthetic_table, drop_recommended=False)
    assert unfiltered == {"H-90", "H-91", "H-92"}
