#!/usr/bin/env python3
"""
test_sentinel_family_parity.py — drift guard across all 9 sentinel family-list copies.

Verifies that the three sources of the sentinel family list are byte-identical:
  1. hooks/_lib.sh:sentinel_globs() — machine-readable single source of truth
  2. skills/cleanup/SKILL.md ## Hardcoded sentinel allow-list section
  3. skills/sleep/SKILL.md ## Sentinel families covered section

Also asserts:
  - All three lists have EXACTLY 9 entries (catches partial 8→9 edits)
  - idle-advisory-pending-*.txt is present in all three
  - No stray "8 families"/"8 sentinel"/"8 hardcoded" count strings survive in either SKILL.md
  - sessionstart.sh STEP 2 region references sentinel_globs and contains no inlined
    family list (ensures DRY: machine source not duplicated in the hook)

Runnable with:
  python3 quoin/dev/tests/test_sentinel_family_parity.py
  python3 -m pytest quoin/dev/tests/test_sentinel_family_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # quoin/ git repo root
_REPO_ROOT = _PROJECT_ROOT / "quoin"
_LIB_SH = _REPO_ROOT / "hooks" / "_lib.sh"
_SESSIONSTART_SH = _REPO_ROOT / "hooks" / "sessionstart.sh"
_CLEANUP_SKILL_MD = _REPO_ROOT / "skills" / "cleanup" / "SKILL.md"
_SLEEP_SKILL_MD = _REPO_ROOT / "skills" / "sleep" / "SKILL.md"

EXPECTED_FAMILIES = [
    "pending-restore-*.txt",
    "pending-prompt-*.txt",
    "compact-happened-*.txt",
    "mid-agent-handoff-*.txt",
    "pending-resume-ref-*.txt",
    "checkpoint-defer-*.txt",
    "postcompact-reset-*.txt",
    "checkpoint-pending-compact-*.txt",
    "idle-advisory-pending-*.txt",
]
EXPECTED_COUNT = 9
STRAY_8_PATTERN = re.compile(r"8 families|8 sentinel|8 hardcoded", re.IGNORECASE)


def _extract_sentinel_globs_from_lib_sh() -> list[str]:
    """
    Extract the 9 canonical family globs from hooks/_lib.sh:sentinel_globs().
    Parse the function body, collect *-*.txt tokens in order.
    """
    content = _LIB_SH.read_text(encoding="utf-8")
    # Find the sentinel_globs() function body
    match = re.search(
        r"sentinel_globs\(\)\s*\{(.*?)\n\}", content, re.DOTALL
    )
    if not match:
        raise ValueError(f"sentinel_globs() function not found in {_LIB_SH}")
    body = match.group(1)
    # Extract glob patterns: lines containing quoted *-*.txt tokens
    globs = []
    for line in body.splitlines():
        # Match quoted globs like 'pending-restore-*.txt' or "pending-restore-*.txt"
        found = re.findall(r"""['"]([a-z-]+\*\.[a-z]+)['"]""", line)
        for g in found:
            if g not in globs:
                globs.append(g)
    return globs


def _extract_cleanup_sentinel_list() -> list[str]:
    """
    Extract the sentinel families from cleanup/SKILL.md
    ## Hardcoded sentinel allow-list section.
    Looks for numbered list items like: 1. `pending-restore-*.txt`
    """
    content = _CLEANUP_SKILL_MD.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_section = False
    families = []
    for line in lines:
        if re.match(r"^## Hardcoded sentinel allow-list", line):
            in_section = True
            continue
        if in_section:
            if re.match(r"^## ", line):
                break
            # Match numbered list entries: 1. `family-glob-*.txt`
            m = re.match(r"^\d+\.\s+`([^`]+)`", line)
            if m:
                families.append(m.group(1))
    return families


def _extract_sleep_sentinel_list() -> list[str]:
    """
    Extract the sentinel families from sleep/SKILL.md
    ## Sentinel families covered section.
    """
    content = _SLEEP_SKILL_MD.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_section = False
    families = []
    for line in lines:
        if re.match(r"^\*\*Sentinel families covered", line):
            in_section = True
            continue
        if in_section:
            # Stop at a blank line that precedes the next major block or end of list
            if re.match(r"^(All \d+|These|The family)", line):
                break
            if re.match(r"^##", line):
                break
            # Match numbered list entries: 1. `family-glob-*.txt`
            m = re.match(r"^\d+\.\s+`([^`]+)`", line)
            if m:
                families.append(m.group(1))
    return families


def _check_sessionstart_no_inline_list() -> tuple[bool, str]:
    """
    Assert that sessionstart.sh STEP 2 region:
    - references 'sentinel_globs' (uses the shared function)
    - does NOT contain a standalone 'pending-restore-*.txt' literal outside that call
      (would indicate an inlined second family list)
    """
    content = _SESSIONSTART_SH.read_text(encoding="utf-8")

    # Find STEP 2 region (between 'STEP 2' and 'STEP 3')
    step2_match = re.search(
        r"# STEP 2:(.*?)# STEP 3:", content, re.DOTALL
    )
    if not step2_match:
        return False, "Could not locate STEP 2 region in sessionstart.sh"
    step2_body = step2_match.group(1)

    # Must reference sentinel_globs
    if "sentinel_globs" not in step2_body:
        return False, "STEP 2 region does not reference sentinel_globs() — the loop must use the shared helper"

    # Must NOT contain a standalone inline family list (any literal from the families)
    # The loop variable $_glob may expand to the family names, but sentinel_globs() is the source.
    # We check that no family-literal appears OUTSIDE of the sentinel_globs call syntax.
    # Specifically: 'pending-restore-*.txt' as a standalone literal (not inside a comment or quotes
    # as part of a direct hardcoded find pattern) should be absent.
    # A conservative check: the body should not contain '-name' alongside a family literal inline.
    inline_find = re.search(
        r"-name\s+['\"]?(pending-restore|pending-prompt|compact-happened|mid-agent-handoff)[^$]",
        step2_body,
    )
    if inline_find:
        return (
            False,
            f"STEP 2 region contains an inlined family literal in a -name pattern: "
            f"'{inline_find.group(0)[:60]}' — family list must come from sentinel_globs() only",
        )

    return True, "STEP 2 region references sentinel_globs and contains no inlined family list"


def test_lib_sh_parses_nine_families() -> None:
    """sentinel_globs() in _lib.sh must declare exactly 9 families."""
    globs = _extract_sentinel_globs_from_lib_sh()
    assert len(globs) == EXPECTED_COUNT, (
        f"hooks/_lib.sh:sentinel_globs() has {len(globs)} families, expected {EXPECTED_COUNT}. "
        f"Found: {globs}"
    )


def test_cleanup_skill_md_has_nine_families() -> None:
    """cleanup/SKILL.md allow-list section must have exactly 9 families."""
    families = _extract_cleanup_sentinel_list()
    assert len(families) == EXPECTED_COUNT, (
        f"cleanup/SKILL.md allow-list has {len(families)} families, expected {EXPECTED_COUNT}. "
        f"Found: {families}"
    )


def test_sleep_skill_md_has_nine_families() -> None:
    """sleep/SKILL.md sentinel families section must have exactly 9 families."""
    families = _extract_sleep_sentinel_list()
    assert len(families) == EXPECTED_COUNT, (
        f"sleep/SKILL.md sentinel list has {len(families)} families, expected {EXPECTED_COUNT}. "
        f"Found: {families}"
    )


def test_all_three_lists_identical() -> None:
    """All three family lists must be byte-identical (same 9 families, same order)."""
    lib_globs = _extract_sentinel_globs_from_lib_sh()
    cleanup_families = _extract_cleanup_sentinel_list()
    sleep_families = _extract_sleep_sentinel_list()

    assert lib_globs == cleanup_families, (
        f"Family list mismatch between _lib.sh ({lib_globs}) "
        f"and cleanup/SKILL.md ({cleanup_families})"
    )
    assert lib_globs == sleep_families, (
        f"Family list mismatch between _lib.sh ({lib_globs}) "
        f"and sleep/SKILL.md ({sleep_families})"
    )
    assert cleanup_families == sleep_families, (
        f"Family list mismatch between cleanup/SKILL.md ({cleanup_families}) "
        f"and sleep/SKILL.md ({sleep_families})"
    )


def test_idle_advisory_present_in_all_three() -> None:
    """idle-advisory-pending-*.txt must be present in all three lists."""
    lib_globs = _extract_sentinel_globs_from_lib_sh()
    cleanup_families = _extract_cleanup_sentinel_list()
    sleep_families = _extract_sleep_sentinel_list()

    assert "idle-advisory-pending-*.txt" in lib_globs, (
        "idle-advisory-pending-*.txt missing from hooks/_lib.sh:sentinel_globs()"
    )
    assert "idle-advisory-pending-*.txt" in cleanup_families, (
        "idle-advisory-pending-*.txt missing from cleanup/SKILL.md allow-list"
    )
    assert "idle-advisory-pending-*.txt" in sleep_families, (
        "idle-advisory-pending-*.txt missing from sleep/SKILL.md sentinel list"
    )


def test_no_stray_eight_count_strings_in_cleanup() -> None:
    """No '8 families'/'8 sentinel'/'8 hardcoded' count strings in cleanup/SKILL.md."""
    content = _CLEANUP_SKILL_MD.read_text(encoding="utf-8")
    matches = STRAY_8_PATTERN.findall(content)
    assert len(matches) == 0, (
        f"Stray '8 families/sentinel/hardcoded' count string(s) found in cleanup/SKILL.md: "
        f"{matches}. Update all count strings from 8→9."
    )


def test_no_stray_eight_count_strings_in_sleep() -> None:
    """No '8 families'/'8 sentinel'/'8 hardcoded' count strings in sleep/SKILL.md."""
    content = _SLEEP_SKILL_MD.read_text(encoding="utf-8")
    matches = STRAY_8_PATTERN.findall(content)
    assert len(matches) == 0, (
        f"Stray '8 families/sentinel/hardcoded' count string(s) found in sleep/SKILL.md: "
        f"{matches}. Update all count strings from 8→9."
    )


def test_sessionstart_uses_sentinel_globs_not_inline_list() -> None:
    """sessionstart.sh STEP 2 uses sentinel_globs() — not an inlined family list."""
    ok, msg = _check_sessionstart_no_inline_list()
    assert ok, msg


def test_expected_families_all_present() -> None:
    """All 9 expected family globs are present in all three sources."""
    lib_globs = _extract_sentinel_globs_from_lib_sh()
    cleanup_families = _extract_cleanup_sentinel_list()
    sleep_families = _extract_sleep_sentinel_list()

    for family in EXPECTED_FAMILIES:
        assert family in lib_globs, f"'{family}' missing from hooks/_lib.sh:sentinel_globs()"
        assert family in cleanup_families, f"'{family}' missing from cleanup/SKILL.md allow-list"
        assert family in sleep_families, f"'{family}' missing from sleep/SKILL.md sentinel list"


if __name__ == "__main__":
    import traceback

    print(f"test_sentinel_family_parity.py — project root: {_PROJECT_ROOT}")

    all_tests = [
        test_lib_sh_parses_nine_families,
        test_cleanup_skill_md_has_nine_families,
        test_sleep_skill_md_has_nine_families,
        test_all_three_lists_identical,
        test_idle_advisory_present_in_all_three,
        test_no_stray_eight_count_strings_in_cleanup,
        test_no_stray_eight_count_strings_in_sleep,
        test_sessionstart_uses_sentinel_globs_not_inline_list,
        test_expected_families_all_present,
    ]
    failures = 0
    for t in all_tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}", file=sys.stderr)
            failures += 1
        except Exception:
            print(f"ERROR: {t.__name__}:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            failures += 1

    print()
    if failures == 0:
        print("All parity tests passed.")
        sys.exit(0)
    else:
        print(f"FAILED: {failures} test(s) failed.", file=sys.stderr)
        sys.exit(1)
