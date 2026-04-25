"""Static-assertion contract tests for .tmp cleanup hardening (T-07 / T-08).

These tests assert the text contracts established in Stage 5 T-07 across
all 5 Class B writer SKILL.md files. They fire if a future edit reverts
the semicolon separator, removes the dual-target rm, or drops the pre-write
sweep or English-fallback cleanup.
"""

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / "dev-workflow" / "skills"

CLASS_B_WRITERS = ["plan", "architect", "review", "revise", "revise-fast"]

SKILL_PATHS = {
    name: SKILLS_DIR / name / "SKILL.md" for name in CLASS_B_WRITERS
}


def _text(skill_name: str) -> str:
    return SKILL_PATHS[skill_name].read_text()


def test_step6_uses_semicolon_separator():
    """Step 6 atomic rename must use ';' separator, not '&&', so cleanup runs even if mv fails."""
    for name in CLASS_B_WRITERS:
        text = _text(name)
        # Must NOT have: mv ...tmp ... && rm
        bad_pattern = re.findall(r"mv\s+\S+\.tmp\s+\S+\s*&&\s*\(?rm", text)
        assert not bad_pattern, (
            f"{name}/SKILL.md: Step 6 still uses '&& rm' pattern (should be '; (rm ...)'): "
            f"{bad_pattern}"
        )
        # Must have the semicolon pattern
        good_pattern = re.findall(r"mv\s+\S+\.tmp\s+\S+\s*;\s*\(?rm", text)
        assert good_pattern, (
            f"{name}/SKILL.md: Step 6 missing '; (rm ...)' separator pattern"
        )


def test_step6_rm_targets_both_tmp_files():
    """Step 6 rm must target BOTH .body.tmp AND .tmp as distinct positional args."""
    for name in CLASS_B_WRITERS:
        text = _text(name)
        # Require two distinct .tmp arguments in a single rm -f call.
        # Substring containment ("body.tmp" in line and ".tmp" in line) is always
        # True when body.tmp is present, so we use a regex requiring two separate
        # whitespace-separated targets.
        dual_target = re.search(
            r"rm\s+-f\s+\S+\.body\.tmp\s+\S+\.tmp\b", text
        )
        assert dual_target, (
            f"{name}/SKILL.md: no rm -f line with two distinct targets "
            f"(<path>.body.tmp <path>.tmp) — dual-target cleanup missing"
        )


def test_step1_pre_write_sweep_present():
    """Each SKILL.md must have a pre-write sweep line near the Step 1 body-write instruction."""
    for name in CLASS_B_WRITERS:
        text = _text(name)
        # The sweep must reference rm -f and body.tmp together
        sweep_lines = [
            line for line in text.splitlines()
            if "pre-write sweep" in line.lower() or (
                "rm -f" in line and "body.tmp" in line and ".tmp" in line
                and "Step 6" not in line and "Step 5" not in line
                and "fallback" not in line.lower()
            )
        ]
        assert sweep_lines, (
            f"{name}/SKILL.md: no pre-write sweep found near Step 1 "
            f"(expected 'rm -f ...body.tmp ...' before the .body.tmp write instruction)"
        )
        # Verify the sweep appears before Step 2 (i.e., in the Step 1 area)
        lines = text.splitlines()
        step2_idx = next(
            (i for i, l in enumerate(lines)
             if re.match(r"\*\*Step 2[: ]", l) or re.match(r"Step 2:", l)), None
        )
        if step2_idx is not None:
            pre_step2_text = "\n".join(lines[:step2_idx])
            has_sweep_before_step2 = any(
                "pre-write sweep" in l.lower() or (
                    "rm -f" in l and "body.tmp" in l and ".tmp" in l
                )
                for l in lines[:step2_idx]
            )
            assert has_sweep_before_step2, (
                f"{name}/SKILL.md: pre-write sweep not found before Step 2 "
                f"(sweep must be in the Step 1 section)"
            )


def test_english_fallback_cleans_body_tmp():
    """Each English-fallback path must mention .body.tmp cleanup."""
    for name in CLASS_B_WRITERS:
        text = _text(name)
        # Find the English-fallback section
        fallback_match = re.search(
            r"English-fallback.*?(?=\*\*Step 6|\Z)", text, re.DOTALL
        )
        if fallback_match:
            fallback_text = fallback_match.group(0)
            assert "body.tmp" in fallback_text, (
                f"{name}/SKILL.md: English-fallback section does not mention .body.tmp cleanup"
            )


def test_negative_case_caught():
    """Assertion machinery must FAIL on synthetic SKILL.md texts with each broken pattern.

    Guards against the tests regressing to no-ops (lesson 2026-04-24).
    Three synthetic cases: (1) old && separator, (2) single-target rm, (3) missing pre-write sweep.
    """
    # Case 1: old '&&' separator instead of ';'
    synthetic_and = (
        "**Step 6: Atomic rename.**\n"
        "`mv <plan-path>.tmp <plan-path> && rm -f <plan-path>.body.tmp`\n"
    )
    bad_pattern = re.findall(r"mv\s+\S+\.tmp\s+\S+\s*&&\s*\(?rm", synthetic_and)
    assert bad_pattern, (
        "Test machinery flaw: bad '&& rm' pattern not found in synthetic text"
    )
    good_pattern = re.findall(r"mv\s+\S+\.tmp\s+\S+\s*;\s*\(?rm", synthetic_and)
    assert not good_pattern, (
        "Test machinery flaw: good '; (rm' pattern found in synthetic text that should be broken"
    )
    caught_bad = bool(bad_pattern)
    would_fail = caught_bad and not good_pattern
    assert would_fail, (
        "test_step6_uses_semicolon_separator would NOT catch the broken && pattern"
    )

    # Case 2: single-target rm — body.tmp only, no separate .tmp target.
    # Old substring check ("body.tmp" in line and ".tmp" in line) passes this because
    # ".tmp" is a substring of "body.tmp". New regex must reject it.
    synthetic_single_target = (
        "**Step 6: Atomic rename.**\n"
        "`mv <plan-path>.tmp <plan-path> ; (rm -f <plan-path>.body.tmp 2>/dev/null || true)`\n"
    )
    dual_target_match = re.search(
        r"rm\s+-f\s+\S+\.body\.tmp\s+\S+\.tmp\b", synthetic_single_target
    )
    assert dual_target_match is None, (
        "Test machinery flaw: dual-target regex matched single-target synthetic text — "
        "test_step6_rm_targets_both_tmp_files would NOT catch a single-target regression"
    )

    # Case 3: SKILL.md missing 'pre-write sweep' — test_step1_pre_write_sweep_present must reject it.
    synthetic_no_sweep = (
        "**Step 1: Write body.**\n"
        "Write the plan body to `<plan-path>.body.tmp`.\n"
        "**Step 2: Do next thing.**\n"
    )
    sweep_lines = [
        line for line in synthetic_no_sweep.splitlines()
        if "pre-write sweep" in line.lower() or (
            "rm -f" in line and "body.tmp" in line and ".tmp" in line
            and "Step 6" not in line and "Step 5" not in line
            and "fallback" not in line.lower()
        )
    ]
    assert not sweep_lines, (
        "Test machinery flaw: pre-write sweep found in synthetic text that should lack it — "
        "test_step1_pre_write_sweep_present would NOT catch a missing sweep"
    )
