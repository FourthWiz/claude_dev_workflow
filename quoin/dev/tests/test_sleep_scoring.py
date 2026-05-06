#!/usr/bin/env python3
"""
test_sleep_scoring.py — unit tests for sleep_score.py importance scoring.

Runnable with:
  .venv/bin/python quoin/dev/tests/test_sleep_scoring.py

All tests use fixtures under quoin/dev/tests/fixtures/sleep/.
No pytest required — stdlib unittest / plain assert-based tests.
"""

import sys
import os
from pathlib import Path

# Make sleep_score importable from quoin/scripts/
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from sleep_score import (
    load_config,
    collect_entries,
    score_entries,
    dedup_against_lessons,
    RawEntry,
    ScoredEntry,
    DEFAULT_CONFIG,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "sleep"
_SIGNALS_YAML = Path(__file__).parent.parent.parent / "memory" / "sleep-signals.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_test(name: str, fn) -> bool:
    """Run one test function; return True on pass, False on fail/skip."""
    try:
        result = fn()
        if result == "SKIP":
            print(f"  SKIP  {name}")
            return True
        print(f"  PASS  {name}")
        return True
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        return False
    except Exception as e:
        print(f"  ERROR {name}: {type(e).__name__}: {e}")
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_promote_hit():
    """promote_hit/ fixture: at least one entry scores as promote."""
    fixture_dir = str(_FIXTURES / "promote_hit")
    entries = collect_entries(fixture_dir, scan_days=365)
    _assert(len(entries) > 0, f"Expected entries from promote_hit/, got 0 (fixture_dir={fixture_dir})")

    config = DEFAULT_CONFIG
    scored = score_entries(entries, config)
    _assert(len(scored) > 0, "score_entries() returned empty list")

    promote_entries = [e for e in scored if e.bucket == "promote"]
    _assert(
        len(promote_entries) >= 1,
        f"Expected at least 1 promote entry, got 0. Buckets: {[(e.bucket, e.promote_score, e.forget_score) for e in scored]}",
    )


def test_forget_hit():
    """forget_hit/ fixture: at least one entry scores as forget."""
    fixture_dir = str(_FIXTURES / "forget_hit")
    entries = collect_entries(fixture_dir, scan_days=365)
    _assert(len(entries) > 0, f"Expected entries from forget_hit/, got 0 (fixture_dir={fixture_dir})")

    config = DEFAULT_CONFIG
    scored = score_entries(entries, config)
    _assert(len(scored) > 0, "score_entries() returned empty list")

    forget_entries = [e for e in scored if e.bucket == "forget"]
    _assert(
        len(forget_entries) >= 1,
        f"Expected at least 1 forget entry, got 0. Buckets: {[(e.bucket, e.promote_score, e.forget_score) for e in scored]}",
    )


def test_middle_band():
    """middle_band/ fixture: at least one entry scores as middle."""
    fixture_dir = str(_FIXTURES / "middle_band")
    entries = collect_entries(fixture_dir, scan_days=365)
    _assert(len(entries) > 0, f"Expected entries from middle_band/, got 0 (fixture_dir={fixture_dir})")

    config = DEFAULT_CONFIG
    scored = score_entries(entries, config)
    _assert(len(scored) > 0, "score_entries() returned empty list")

    middle_entries = [e for e in scored if e.bucket == "middle"]
    _assert(
        len(middle_entries) >= 1,
        f"Expected at least 1 middle entry, got 0. Buckets: {[(e.bucket, e.promote_score, e.forget_score) for e in scored]}",
    )


def test_dedup_suppress():
    """dedup_suppress/ fixture: overlapping candidate is removed from promote list after dedup."""
    fixture_dir = str(_FIXTURES / "dedup_suppress")
    lessons_fixture = _FIXTURES / "dedup_suppress" / "lessons-learned-fixture.md"

    _assert(lessons_fixture.exists(), f"lessons-learned-fixture.md not found at {lessons_fixture}")

    entries = collect_entries(fixture_dir, scan_days=365)
    _assert(len(entries) > 0, f"Expected entries from dedup_suppress/, got 0 (fixture_dir={fixture_dir})")

    config = DEFAULT_CONFIG
    scored = score_entries(entries, config)

    # Before dedup: should have at least one promote entry (the pyyaml entry with user_marked_yes)
    promote_before = [e for e in scored if e.bucket == "promote"]
    _assert(
        len(promote_before) >= 1,
        f"Expected at least 1 promote entry before dedup, got 0. Buckets: {[(e.bucket, e.promote_score) for e in scored]}",
    )

    # Dedup against the fixture lessons
    lessons_text = lessons_fixture.read_text(encoding="utf-8")
    after = dedup_against_lessons(scored, lessons_text)

    # After dedup: the pyyaml promote entry should be filtered out
    promote_after = [e for e in after if e.bucket == "promote"]
    _assert(
        len(promote_after) == 0,
        f"Expected 0 promote entries after dedup, got {len(promote_after)}: {[e.text[:60] for e in promote_after]}",
    )


def test_weight_override():
    """Overriding promote_min_score to 99 means no entries can reach promote bucket."""
    fixture_dir = str(_FIXTURES / "promote_hit")
    entries = collect_entries(fixture_dir, scan_days=365)
    _assert(len(entries) > 0, "Expected entries from promote_hit/")

    # Override promote_min_score to impossibly high value
    import copy
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["thresholds"]["promote_min_score"] = 99

    scored = score_entries(entries, config)
    promote_entries = [e for e in scored if e.bucket == "promote"]
    _assert(
        len(promote_entries) == 0,
        f"Expected 0 promote entries with min_score=99, got {len(promote_entries)}",
    )


def test_default_weights_present():
    """load_config(signals_yaml_path=...) returns a dict with expected keys; _source sentinel present when pyyaml installed."""
    try:
        import yaml
        pyyaml_available = True
    except ImportError:
        pyyaml_available = False

    if not pyyaml_available:
        # Skip — cannot verify live YAML parse without pyyaml
        return "SKIP"

    if not _SIGNALS_YAML.exists():
        raise AssertionError(f"quoin/memory/sleep-signals.yaml not found at {_SIGNALS_YAML}")

    config = load_config(signals_yaml_path=str(_SIGNALS_YAML))

    # Top-level keys
    _assert("promote" in config, "config missing 'promote' key")
    _assert("forget" in config, "config missing 'forget' key")
    _assert("thresholds" in config, "config missing 'thresholds' key")

    # Expected promote signal keys
    promote = config["promote"]
    _assert("frequency_3plus" in promote, "promote missing 'frequency_3plus'")
    _assert("user_marked_yes" in promote, "promote missing 'user_marked_yes'")

    # Expected forget signal keys
    forget = config["forget"]
    _assert("one_shot" in forget, "forget missing 'one_shot'")
    _assert("user_marked_no" in forget, "forget missing 'user_marked_no'")

    # Expected threshold keys
    thresholds = config["thresholds"]
    _assert("promote_min_score" in thresholds, "thresholds missing 'promote_min_score'")
    _assert("forget_min_score" in thresholds, "thresholds missing 'forget_min_score'")

    # The _source sentinel distinguishes live YAML parse from hardcoded fallback
    _assert(
        config["thresholds"].get("_source") == "claude_md",
        f"Expected thresholds._source == 'claude_md', got {config['thresholds'].get('_source')!r}. "
        "Either pyyaml failed to parse CLAUDE.md or the _source sentinel is missing from the YAML block.",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests():
    tests = [
        ("test_promote_hit", test_promote_hit),
        ("test_forget_hit", test_forget_hit),
        ("test_middle_band", test_middle_band),
        ("test_dedup_suppress", test_dedup_suppress),
        ("test_weight_override", test_weight_override),
        ("test_default_weights_present", test_default_weights_present),
    ]

    print(f"Running {len(tests)} test(s) from {__file__}")
    passed = 0
    failed = 0
    skipped = 0

    for name, fn in tests:
        ok = _run_test(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    # Adjust counts for skips (SKIP returns True in _run_test)
    print(f"\nResults: {passed} passed (includes skips), {failed} failed")

    if failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run_tests()
