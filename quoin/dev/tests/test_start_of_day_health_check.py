#!/usr/bin/env python3
"""
test_start_of_day_health_check.py — contract tests for the Step 1b sentinel-health
check added to adapters/claude/skills/start_of_day/SKILL.md (IVG-95 T-04).

Asserts:
  (a) The SKILL.md contains a "Step 1b" section (or "Step 1b:" heading) describing
      a sentinel or health check.
  (b) The section references QUOIN_SOD_SENTINEL_WARN (the threshold knob).
  (c) The section references /cleanup (directing the user where to go).
  (d) The section is read-only — contains neither 'trash_move' nor 'rm ' (SOD must
      never mutate; advisory only).
  (e) The section (and the whole file) contains no literal '~/.claude/' path
      (must use __QUOIN_HOME__ token instead — lessons-learned 2026-05-15).

Runnable with:
  python3 quoin/dev/tests/test_start_of_day_health_check.py
  python3 -m pytest quoin/dev/tests/test_start_of_day_health_check.py
"""

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # quoin/ git repo root
_SKILL_MD = (
    _PROJECT_ROOT
    / "quoin"
    / "adapters"
    / "claude"
    / "skills"
    / "start_of_day"
    / "SKILL.md"
)


def _extract_step1b_section(content: str) -> str:
    """
    Extract the body of the Step 1b section from the SKILL.md.
    Searches for lines matching '### Step 1b' or '**Step 1b' or 'Step 1b:'.
    Returns the text from the matching line through the next H3/H2 heading or
    a blank-then-H3 boundary.
    """
    lines = content.splitlines()
    in_section = False
    section_lines: list[str] = []
    for i, line in enumerate(lines):
        if re.match(r"^###\s+Step 1b", line) or re.match(r"^\*\*Step 1b[:\s]", line):
            in_section = True
            section_lines.append(line)
            continue
        if in_section:
            # Stop at next H2 or H3 heading (new section)
            if re.match(r"^##", line):
                break
            section_lines.append(line)
    return "\n".join(section_lines)


def test_step1b_section_exists() -> None:
    """(a) A Step 1b section describing sentinel/health check must be present."""
    assert _SKILL_MD.exists(), f"start_of_day SKILL.md not found at {_SKILL_MD}"
    content = _SKILL_MD.read_text(encoding="utf-8")
    section = _extract_step1b_section(content)
    assert section, (
        "Step 1b section not found in start_of_day/SKILL.md. "
        "Expected a '### Step 1b' or '**Step 1b' heading describing sentinel/health check."
    )
    # The section should mention sentinel or health check
    lower = section.lower()
    assert "sentinel" in lower or "health" in lower, (
        f"Step 1b section found but does not mention 'sentinel' or 'health'. "
        f"Section content:\n{section[:500]}"
    )


def test_step1b_references_quoin_sod_sentinel_warn() -> None:
    """(b) Step 1b must reference QUOIN_SOD_SENTINEL_WARN (the threshold knob)."""
    assert _SKILL_MD.exists(), f"start_of_day SKILL.md not found at {_SKILL_MD}"
    content = _SKILL_MD.read_text(encoding="utf-8")
    section = _extract_step1b_section(content)
    assert section, "Step 1b section not found — run test_step1b_section_exists first."
    assert "QUOIN_SOD_SENTINEL_WARN" in section, (
        "Step 1b section does not reference QUOIN_SOD_SENTINEL_WARN. "
        "The health check threshold must be documented with its env knob name."
    )


def test_step1b_references_cleanup() -> None:
    """(c) Step 1b must reference /cleanup (directing users to the fix)."""
    assert _SKILL_MD.exists(), f"start_of_day SKILL.md not found at {_SKILL_MD}"
    content = _SKILL_MD.read_text(encoding="utf-8")
    section = _extract_step1b_section(content)
    assert section, "Step 1b section not found — run test_step1b_section_exists first."
    assert "/cleanup" in section, (
        "Step 1b section does not reference /cleanup. "
        "The advisory banner must direct users to /cleanup to resolve stale sentinels."
    )


def test_step1b_is_read_only() -> None:
    """(d) Step 1b must be read-only — no trash_move() call or rm command in the section.

    The section may *mention* trash_move or rm in documentation prose like
    "no trash_move, no rm" — that is allowed. What must NOT appear is
    actual invocations: trash_move followed by a path argument, or standalone
    rm commands in code blocks.
    """
    assert _SKILL_MD.exists(), f"start_of_day SKILL.md not found at {_SKILL_MD}"
    content = _SKILL_MD.read_text(encoding="utf-8")
    section = _extract_step1b_section(content)
    assert section, "Step 1b section not found — run test_step1b_section_exists first."

    # Check that 'trash_move' does not appear as a command invocation.
    # Invocation pattern: trash_move followed by a space and a path/variable
    # (as opposed to documentation prose "no trash_move, no rm").
    import re as _re
    trash_move_call = _re.search(r"\btrash_move\s+[\"']?\$", section)
    assert trash_move_call is None, (
        "Step 1b section contains a trash_move() call invocation. "
        "SOD health check must be read-only — no mutations. "
        "Direct users to /cleanup for actual cleanup."
    )

    # Check 'rm -f' or 'rm $' — actual rm invocations (not prose mentions of 'rm')
    rm_invocation = _re.search(r"\brm\s+(-[a-z]+\s+)?\$", section)
    assert rm_invocation is None, (
        "Step 1b section contains an rm invocation. "
        "SOD health check must be read-only — no file deletions."
    )

    # Verify the section explicitly says "read-only" to document the intent
    assert "read-only" in section.lower() or "read only" in section.lower(), (
        "Step 1b section does not explicitly state it is read-only. "
        "Add 'read-only' documentation to clarify SOD must not mutate."
    )


def test_no_literal_tilde_claude_paths() -> None:
    """(e) Whole SKILL.md must contain no literal '~/.claude/' path."""
    assert _SKILL_MD.exists(), f"start_of_day SKILL.md not found at {_SKILL_MD}"
    content = _SKILL_MD.read_text(encoding="utf-8")
    matches = re.findall(r"~/\.claude/", content)
    assert len(matches) == 0, (
        f"Found {len(matches)} literal '~/.claude/' path(s) in start_of_day/SKILL.md. "
        "Use __QUOIN_HOME__ token instead (lessons-learned 2026-05-15)."
    )


if __name__ == "__main__":
    import traceback

    print(f"test_start_of_day_health_check.py — project root: {_PROJECT_ROOT}")
    print(f"SKILL.md path: {_SKILL_MD}")

    all_tests = [
        test_step1b_section_exists,
        test_step1b_references_quoin_sod_sentinel_warn,
        test_step1b_references_cleanup,
        test_step1b_is_read_only,
        test_no_literal_tilde_claude_paths,
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
        print("All health check tests passed.")
        sys.exit(0)
    else:
        print(f"FAILED: {failures} test(s) failed.", file=sys.stderr)
        sys.exit(1)
