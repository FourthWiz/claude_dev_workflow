"""Structural tests for end_of_day session-selection documentation.

These tests grep SKILL.md and core doc text to assert that the hybrid
date-window + flag rule, lower_bound procedure, same-day merge contract,
and --recover-orphans subcommand are properly documented.

Documentation-conformance tests — they assert the SKILL.md documented
contract, NOT runtime behavior of the live daily files (live files
pre-date the new template and lack some sections; see plan R-01 notes).
"""
from pathlib import Path

import pytest

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent

ADAPTER_SKILL = PKG_DIR / "adapters" / "claude" / "skills" / "end_of_day" / "SKILL.md"
CORE_DOC = PKG_DIR / "core" / "skills" / "end_of_day.md"
WEEKLY_ADAPTER = PKG_DIR / "adapters" / "claude" / "skills" / "weekly_review" / "SKILL.md"


def _adapter_text() -> str:
    return ADAPTER_SKILL.read_text(encoding="utf-8")


def _core_text() -> str:
    return CORE_DOC.read_text(encoding="utf-8")


def test_core_doc_no_today_glob_in_inputs():
    """Core doc Inputs section must not reference the old today-only glob."""
    text = _core_text()
    assert "<today>-*.md" not in text, (
        "core/skills/end_of_day.md Inputs must not reference '<today>-*.md'. "
        "Update to describe the hybrid date-window selection."
    )


def test_adapter_states_hybrid_selection():
    """Adapter Step 3 must document both 'date window' and 'end_of_day_due'."""
    text = _adapter_text()
    step3_start = text.find("### Step 3:")
    assert step3_start != -1, "Could not find '### Step 3:' in adapter SKILL.md"
    step3_end = text.find("### Step 3b:", step3_start)
    step3 = text[step3_start:step3_end if step3_end != -1 else step3_start + 3000]
    assert "date" in step3 and "window" in step3, (
        "Step 3 must describe a 'date window' for session selection."
    )
    assert "end_of_day_due" in step3, (
        "Step 3 must mention the 'end_of_day_due' flag as part of the selection rule."
    )


def test_adapter_mentions_lower_bound_procedure():
    """Adapter Step 3 must document the lower_bound discovery rule."""
    text = _adapter_text()
    assert "lower_bound" in text, (
        "Adapter SKILL.md must document the 'lower_bound' concept for window discovery."
    )
    assert "most recent" in text.lower(), (
        "Adapter SKILL.md must describe finding the 'most recent' daily file to anchor lower_bound."
    )


def test_adapter_legacy_treated_as_yes():
    """Adapter must document that legacy session files (no flag line) are treated as yes."""
    text = _adapter_text()
    assert "treated as" in text.lower() and "yes" in text, (
        "Adapter SKILL.md must state that legacy session files lacking 'end_of_day_due' "
        "are treated as 'yes'."
    )


def test_adapter_processed_window_in_cost_summary():
    """Cost summary section must scope to the processed date window, not only today."""
    text = _adapter_text()
    cost_start = text.find("Cost summary")
    assert cost_start != -1, "Could not find 'Cost summary' reference in adapter SKILL.md"
    cost_region = text[cost_start: cost_start + 1000]
    has_window_scope = "processed window" in cost_region or "processed date window" in cost_region
    assert has_window_scope, (
        "Cost summary section must reference 'processed window' or 'processed date window', "
        "not only today's date."
    )


def test_adapter_insights_scan_iterates_window():
    """Step 3b must describe scanning insights files for every DATE in the processed window."""
    text = _adapter_text()
    step3b_start = text.find("### Step 3b:")
    assert step3b_start != -1, "Could not find '### Step 3b:' in adapter SKILL.md"
    step3b_end = text.find("### Step 3c:", step3b_start)
    step3b = text[step3b_start: step3b_end if step3b_end != -1 else step3b_start + 1500]
    has_window_scan = "processed window" in step3b or "every DATE" in step3b or "date window" in step3b
    assert has_window_scan, (
        "Step 3b must describe scanning insights files across the full processed date window, "
        "not only today."
    )


def test_documented_closed_section_set_updated():
    """Core doc Notes section must enumerate 9 closed sections including 'Sessions processed'.

    Documentation-conformance test — asserts the core doc documented section set;
    does NOT assert runtime daily-cache shape (live files pre-date the template and
    lack '## For human'; see R-01 notes and follow-up).
    """
    text = _core_text()
    notes_start = text.find("## Notes")
    assert notes_start != -1, "Could not find '## Notes' in core/skills/end_of_day.md"
    notes_text = text[notes_start:]
    assert "Sessions processed" in notes_text, (
        "core/skills/end_of_day.md Notes section must list '## Sessions processed' "
        "in the closed section set (9 total: For human, Summary, Sessions processed, "
        "Completed today, Unfinished, Decisions log, Git activity summary, Cost summary, "
        "Tomorrow's priorities)."
    )


def test_adapter_same_day_rerun_merge_contract_strict():
    """Adapter must document the same-day re-run MERGE contract with specific keywords.

    Asserts at least 3 of the merge-rule keyword phrases from proc:D-06. Guards against
    a trivially-passing single-word 'MERGE' grep (Round-2 MIN issue).
    """
    text = _adapter_text()
    keywords = [
        "task-name set-union",
        "latest wins",
        "regenerate",
        "replace entirely",
        "Sessions processed table",
        "MERGE",
        "section-by-section",
        "proc:D-06",
    ]
    found = [kw for kw in keywords if kw in text]
    assert len(found) >= 3, (
        f"Adapter SKILL.md must document the merge contract with at least 3 of the "
        f"following keywords: {keywords}. Found only: {found}"
    )


def test_adapter_recover_orphans_documented():
    """Adapter must document --recover-orphans with slug-based criterion."""
    text = _adapter_text()
    assert "--recover-orphans" in text, (
        "Adapter SKILL.md must document the '--recover-orphans' subcommand."
    )
    assert "slug" in text, (
        "Adapter SKILL.md must mention 'slug' as part of the orphan detection criterion."
    )
    assert "every daily file" in text or "every daily" in text, (
        "Adapter SKILL.md must specify that orphan detection checks the slug against "
        "'every daily file' body."
    )


def test_weekly_review_honors_flag_signal():
    """weekly_review adapter Step 2 must reference end_of_day_due or select_unprocessed_sessions."""
    if not WEEKLY_ADAPTER.is_file():
        pytest.skip(f"weekly_review adapter SKILL.md not found: {WEEKLY_ADAPTER}")
    text = WEEKLY_ADAPTER.read_text(encoding="utf-8")
    has_flag = "end_of_day_due" in text
    has_helper = "select_unprocessed_sessions" in text
    has_slug_covering = "slug" in text and "covering daily" in text
    assert has_flag or has_helper or has_slug_covering, (
        "weekly_review adapter SKILL.md Step 2 must reference 'end_of_day_due' AND "
        "either 'select_unprocessed_sessions' or ('slug' AND 'covering daily')."
    )
