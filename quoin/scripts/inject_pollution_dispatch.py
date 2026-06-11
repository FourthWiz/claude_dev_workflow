#!/usr/bin/env python3
"""
inject_pollution_dispatch.py — Generator for the §0' Pollution dispatch block.

Inserts/refreshes the §0' Pollution dispatch block (and §0c Pidfile lifecycle for
architect + review) into the 7 Opus-tier Claude adapter SKILL.md files at:
  quoin/adapters/claude/skills/<skill>/SKILL.md

This script is the SOURCE-OF-TRUTH owner for §0' content. The block was dropped
during the Phase-10 adapter migration (commit e732677) and is restored here in a
generator-owned form that prevents re-drift.

Note: This is a STANDALONE script (stdlib-only on the write path). It does NOT
import from quoin/core/scripts/. Registering it in DEPLOYED_SCRIPTS only is
correct. If this script ever imports a core impl, it becomes a wrapper and MUST
also be added to CORE_SCRIPTS and register in sys.modules before exec (lessons
2026-05-31 / 2026-06-08).

Exit codes:
  0  success
  1  write error (file not found or could not write)
  6  --dry-run and --check are mutually exclusive
  7  --check: drift detected (one or more adapter files missing §0' or token mismatch)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

# ─── Constants (byte-identical to test file literals) ────────────────────────

POLLUTION_HEADING = "## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)"
ZC_HEADING = "## §0c Pidfile lifecycle"

# 7 Opus-tier target skills — must carry §0'.
POLLUTION_TARGET_SKILLS = [
    "architect",
    "plan",
    "critic",
    "revise",
    "review",
    "init_workflow",
    "discover",
]

# Skills that also need §0c Pidfile lifecycle (inserted BEFORE §0').
ZC_SKILLS = ["architect", "review"]

# ─── §0c block bodies (verbatim from f81b6ff, §0c path fixed to __QUOIN_HOME__) ─

# NOTE: The sourced helper path `. __QUOIN_HOME__/scripts/pidfile_helpers.sh` uses
# the deploy-root placeholder. installer.py substitutes __QUOIN_HOME__ → deploy root
# and explicitly leaves literal ~/.claude/ UNTOUCHED (lesson 2026-05-15). This is
# the single deliberate divergence from the f81b6ff text (which had `~/.claude/`).

ZC_BLOCK_ARCHITECT = """\
## §0c Pidfile lifecycle

This skill is Opus-tier (no §0 dispatch block). §0c is the only §0-class block in this file — it is both first and last. **Phase-4-only variant:** the actual pidfile acquire/release calls are in Phase 4 (the critic loop), not at skill entry. This block is a pointer comment.

The acquire/release pattern is scoped to Phase 4 only (the internal critic loop). When Phase 4 begins, add:
```
. __QUOIN_HOME__/scripts/pidfile_helpers.sh && pidfile_acquire architect-phase-4
```
When Phase 4 ends (or on any abort from Phase 4): `pidfile_release architect-phase-4`.

If the helper is missing or fails: emit one-line warning `[quoin-S-2: pidfile helpers unavailable; proceeding without lifecycle protection]` and continue (fail-OPEN). The full skill entry/exit does NOT acquire — only Phase 4 inner loop.

Purpose: lets `precompact.sh` hook know an `/architect` Phase 4 session is active.

"""

ZC_BLOCK_REVIEW = """\
## §0c Pidfile lifecycle

This skill is Opus-tier (no §0 dispatch block). §0c is the only §0-class block in this file — it is both first and last.

At entry — immediately after reading this block:

```
. __QUOIN_HOME__/scripts/pidfile_helpers.sh && pidfile_acquire review
```

If the script is missing or fails: emit one-line warning `[quoin-S-2: pidfile helpers unavailable; proceeding without lifecycle protection]` and continue without abort (fail-OPEN).

At exit — call from every completion path AND every error/abort path:
```
pidfile_release review
```

Use a trap when the skill body involves bash-driven subagents:
```
trap 'pidfile_release review' EXIT
```

Purpose: lets `precompact.sh` hook know a `/review` session is active (for escalation from "block with warning" to "block with confidence").

"""

ZC_BLOCKS = {
    "architect": ZC_BLOCK_ARCHITECT,
    "review": ZC_BLOCK_REVIEW,
}

# ─── §0' shared block template ────────────────────────────────────────────────
# Variables: {skill_dispatch_contract}
# All 6 REQUIRED_TOKENS and 3 score-extraction strings are inside this block.

_POLLUTION_BLOCK_TEMPLATE = """\
## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)

This skill runs in the user's current session. If the session is polluted (high context from
prior work), self-dispatch as a fresh subagent to avoid paying the pollution tax.

Detection:
  - Read the most-recent session-state file: `.workflow_artifacts/memory/sessions/<today>-<task>.md`
    OR the fallback `.workflow_artifacts/memory/pollution-score-latest.txt`.
  - Parse the `pollution_score: N` field (integer).
  - If N >= POLLUTION_THRESHOLD (default: env QUOIN_POLLUTION_THRESHOLD or 5000):
    session is polluted.
  - Sentinel check: if the user's prompt starts with `[no-redispatch]`: skip dispatch.
  - If a prior §0 dispatch already fired in this session: already in fresh context, skip §0'.

Dispatch action (when pollution detected AND no sentinel AND no prior §0 dispatch):
{skill_dispatch_contract}
  If task description cannot be determined:
    Emit: `[quoin-S-1: cannot extract per-skill dispatch contract; running in main]`
    Proceed with skill body.

  Otherwise spawn an Agent subagent:
    model: "opus"
    description: "{skill} — pollution-isolated dispatch"
    prompt: "{skill_prompt}"

  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path:
  If Agent tool unavailable or errors:
    Emit: `[quoin-S-1: pollution dispatch unavailable; proceeding in current session]`
    Proceed with skill body.

Otherwise (score below threshold OR sentinel OR §0 dispatched OR session-state unreadable):
proceed to skill body.

"""

# ─── Per-skill dispatch contract fields ──────────────────────────────────────
# Verbatim from f81b6ff per skill, used to fill {skill_dispatch_contract} in the template.
# Also provides {skill_prompt} substitution.

# Each entry: (contract_body_lines, prompt_string)
DISPATCH_CONTRACTS = {
    "architect": (
        """\
  Determine dispatch contract fields:
    - Extract the task description from the user's invocation.
    - Paths to /discover output are static (relative to cwd):
        `.workflow_artifacts/memory/repos-inventory.md`
        `.workflow_artifacts/memory/architecture-overview.md`
        `.workflow_artifacts/memory/dependencies-map.md`
""",
        "[no-redispatch]\\n/architect <task description>\\nArchitecture context paths:\\n"
        "- .workflow_artifacts/memory/repos-inventory.md\\n"
        "- .workflow_artifacts/memory/architecture-overview.md\\n"
        "- .workflow_artifacts/memory/dependencies-map.md",
    ),
    "plan": (
        """\
  Determine dispatch contract fields:
    - Extract the task description from the user's invocation.
    - Locate architecture.md at the task root (if exists): `.workflow_artifacts/<task>/architecture.md`.
    - Detect stage number from the user prompt if multi-stage.
""",
        "[no-redispatch]\\n/plan <task description>\\nPlan context paths:\\n"
        "- .workflow_artifacts/<task>/architecture.md (if exists)\\n"
        "- Stage: <N> (if multi-stage)",
    ),
    "critic": (
        """\
  Determine dispatch contract fields:
    - Locate the target artifact path from the invocation (e.g., `/critic Target: <path>`
      convention used by /thorough_plan, or the most-recent current-plan.md in the task dir).
""",
        "[no-redispatch]\\n/critic\\nTarget: <absolute path to target artifact>",
    ),
    "revise": (
        """\
  Determine dispatch contract fields:
    - Locate current-plan.md in the task directory (resolve via path_resolve.py).
    - Locate the most-recent critic-response-N.md in the same task directory.
""",
        "[no-redispatch]\\n/revise\\nPlan path: <absolute path to current-plan.md>\\n"
        "Critic response: <absolute path to critic-response-N.md>",
    ),
    "review": (
        """\
  Determine dispatch contract fields:
    - Locate `current-plan.md` in the task directory (resolve via path_resolve.py).
    - Get the current git branch (`git rev-parse --abbrev-ref HEAD`).
""",
        "[no-redispatch]\\n/review\\nPlan path: <absolute path to current-plan.md>\\n"
        "Branch: <current git branch>",
    ),
    "init_workflow": (
        """\
  Determine dispatch contract fields:
    - Use the current working directory as the project root absolute path.
""",
        "[no-redispatch]\\n/init_workflow <project root absolute path>",
    ),
    "discover": (
        """\
  Determine dispatch contract fields:
    - Use the current working directory as the project root absolute path.
""",
        "[no-redispatch]\\n/discover <project root absolute path>",
    ),
}


# ─── Block rendering ──────────────────────────────────────────────────────────

def render_pollution_block(skill: str) -> str:
    """Render the §0' block for a given skill."""
    contract_body, prompt_str = DISPATCH_CONTRACTS[skill]
    return _POLLUTION_BLOCK_TEMPLATE.format(
        skill_dispatch_contract=contract_body,
        skill=skill,
        skill_prompt=prompt_str,
    )


def render_zc_block(skill: str) -> str:
    """Render the §0c block for architect or review."""
    return ZC_BLOCKS[skill]


# ─── File manipulation ────────────────────────────────────────────────────────

def _find_first_h2(lines: list[str]) -> int:
    """Return the 0-indexed line number of the first '## ' heading.

    Skips H1 (^# ) and optional portable-intent line and intro paragraph.
    Returns -1 if no H2 found (caller should FAIL LOUD).
    """
    past_h1 = False
    for i, line in enumerate(lines):
        if not past_h1:
            if line.startswith("# "):
                past_h1 = True
            continue
        if line.startswith("## "):
            return i
    return -1


def _replace_existing_block(text: str, heading: str, new_block: str) -> str:
    """Replace an existing block (heading through line before next '## ') in place."""
    # Find the block: from heading to (but not including) the next '## '
    pattern = re.compile(
        r"^" + re.escape(heading) + r".+?(?=^## )",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        return text[: match.start()] + new_block + text[match.end() :]
    return text


def inject_blocks_into_file(skill: str, skill_md: pathlib.Path) -> str:
    """Return the new content for skill_md with §0' (and §0c if needed) injected.

    Strategy (per plan D-A5 / proc:T-02-anchor):
    - If §0' already present: replace in place (idempotent refresh).
    - If §0' absent: find the first H2, insert before it.
    - For architect/review: handle §0c similarly.
    - FAIL LOUD if no H2 found at all.
    """
    text = skill_md.read_text(encoding="utf-8")
    pollution_block = render_pollution_block(skill)
    needs_zc = skill in ZC_SKILLS

    # ── Refresh path (idempotent): block(s) already present ──
    if POLLUTION_HEADING in text:
        text = _replace_existing_block(text, POLLUTION_HEADING, pollution_block)
        if needs_zc and ZC_HEADING in text:
            text = _replace_existing_block(text, ZC_HEADING, render_zc_block(skill))
        elif needs_zc and ZC_HEADING not in text:
            # §0c absent but §0' present (shouldn't happen on fresh files, but handle):
            # Insert §0c immediately before §0'
            text = text.replace(POLLUTION_HEADING, render_zc_block(skill) + POLLUTION_HEADING, 1)
        return text

    # ── Insert path: block(s) absent, find anchor ──
    lines = text.splitlines(keepends=True)
    anchor_idx = _find_first_h2(lines)
    if anchor_idx == -1:
        raise ValueError(
            f"No '## ' heading found in {skill_md} — cannot determine insertion anchor. "
            "FAIL LOUD: the generator requires at least one H2 heading as an insertion point."
        )

    # Build insertion: for ZC skills insert §0c THEN §0'; for others just §0'.
    if needs_zc:
        insert_text = render_zc_block(skill) + pollution_block
    else:
        insert_text = pollution_block

    # Insert immediately before the anchor line
    lines.insert(anchor_idx, insert_text)
    return "".join(lines)


# ─── Main processing ──────────────────────────────────────────────────────────

def _get_adapter_dir() -> pathlib.Path:
    """Return the adapter skills directory (quoin/adapters/claude/skills/)."""
    script_dir = pathlib.Path(__file__).resolve().parent
    # scripts/ is inside quoin/quoin/; adapter dir is at quoin/quoin/adapters/claude/skills/
    quoin_pkg = script_dir.parent   # quoin/quoin/
    return quoin_pkg / "adapters" / "claude" / "skills"


def run_inject(*, dry_run: bool = False) -> int:
    """Inject/refresh §0' (and §0c) into all 7 target adapter SKILL.md files.

    Returns 0 on success, 1 on any error.
    """
    adapter_dir = _get_adapter_dir()
    errors = []

    for skill in POLLUTION_TARGET_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"MISSING: {skill_md}")
            continue

        try:
            new_content = inject_blocks_into_file(skill, skill_md)
        except (ValueError, OSError) as e:
            errors.append(f"ERROR processing {skill}: {e}")
            continue

        if dry_run:
            print(f"=== {skill} ===")
            # Show only the injected block(s) for brevity
            idx = new_content.find("## §0")
            preview = new_content[idx : new_content.find("\n## ", idx + 4) + 1] if idx != -1 else "(no §0 block found)"
            print(preview[:500])
            continue

        # Atomic write: .tmp + os.replace()
        tmp_path = skill_md.with_suffix(".md.tmp")
        try:
            tmp_path.write_text(new_content, encoding="utf-8")
            os.replace(tmp_path, skill_md)
        except OSError as e:
            errors.append(f"WRITE ERROR for {skill}: {e}")
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            continue
        print(f"  injected §0' into {skill_md.relative_to(adapter_dir.parent.parent.parent.parent)}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return 0


def run_check() -> int:
    """--check mode: verify all 7 adapter SKILL.md files carry correct §0' (and §0c) blocks.

    Returns 0 if all files are fresh, 7 if any drift detected.
    Also verifies the 6 REQUIRED_TOKENS from test_quoin_pollution_preamble.py
    and the 3 file-wide strings from test_pollution_score_extraction.py are
    present inside the rendered §0' block (MIN-A anti-drift cross-guard).

    Note: The literal `5000` threshold value is also checked (MIN-A, per plan).
    """
    adapter_dir = _get_adapter_dir()

    # Required tokens inside §0' block (test_quoin_pollution_preamble.py REQUIRED_TOKENS)
    required_tokens = [
        "[no-redispatch]",
        "[quoin-S-1: cannot extract per-skill dispatch contract; running in main]",
        "[quoin-S-1: pollution dispatch unavailable; proceeding in current session]",
        "pollution_score",
        "POLLUTION_THRESHOLD",
        'model: "opus"',
    ]
    # Required file-wide strings (test_pollution_score_extraction.py)
    score_extraction_strings = [
        "pollution_score",
        "pollution-score-latest.txt",
        "sessions/",
    ]
    # MIN-A: literal default threshold value must be in block
    threshold_token = "5000"

    drifted = []

    for skill in POLLUTION_TARGET_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            drifted.append(f"{skill}: adapter SKILL.md missing at {skill_md}")
            continue

        text = skill_md.read_text(encoding="utf-8")

        # Check §0' heading present
        if POLLUTION_HEADING not in text:
            drifted.append(f"{skill}: §0' heading missing")
            continue

        # Extract §0' block (same regex as test file)
        block_match = re.search(
            r"^## §0' Pollution dispatch \(execute after §0 / §0c if present — before skill body\).+?(?=^## )",
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
        if not block_match:
            drifted.append(f"{skill}: §0' block could not be extracted (no trailing ## heading?)")
            continue
        block = block_match.group(0)

        # Check required tokens inside block
        for token in required_tokens:
            if token not in block:
                drifted.append(f"{skill}: missing required token {token!r} in §0' block")

        # Check score-extraction strings inside block
        for s in score_extraction_strings:
            if s not in block:
                drifted.append(f"{skill}: missing score-extraction string {s!r} in §0' block")

        # MIN-A: literal threshold value
        if threshold_token not in block:
            drifted.append(f"{skill}: missing threshold value {threshold_token!r} in §0' block")

        # Check §0c for ZC skills
        if skill in ZC_SKILLS:
            if ZC_HEADING not in text:
                drifted.append(f"{skill}: §0c heading missing")
            else:
                zc_idx = text.index(ZC_HEADING)
                p_idx = text.index(POLLUTION_HEADING)
                if zc_idx >= p_idx:
                    drifted.append(f"{skill}: §0c appears AFTER §0' (ordering violation)")
                # Check §0c placeholder discipline: __QUOIN_HOME__ present, no literal ~/.claude/ in source line
                zc_end = text.find("\n## ", zc_idx + len(ZC_HEADING))
                zc_block = text[zc_idx : zc_end] if zc_end != -1 else text[zc_idx:]
                if "__QUOIN_HOME__/scripts/pidfile_helpers.sh" not in zc_block:
                    drifted.append(f"{skill}: §0c missing __QUOIN_HOME__ placeholder in pidfile source line")
                # Scan for literal ~/.claude/ in any source line
                for line in zc_block.splitlines():
                    if "~/.claude/scripts/pidfile_helpers" in line:
                        drifted.append(f"{skill}: §0c has literal ~/.claude/ in pidfile source line (must use __QUOIN_HOME__)")
                        break

    if drifted:
        for msg in drifted:
            print(f"DRIFT: {msg}", file=sys.stderr)
        return 7
    print("inject_pollution_dispatch --check: all 7 adapter files are fresh")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered blocks to stdout instead of writing to disk",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify all 7 adapter SKILL.md files carry correct §0' blocks; exit 7 if any drift",
    )
    args = parser.parse_args()

    if args.dry_run and args.check:
        print("--dry-run and --check are mutually exclusive", file=sys.stderr)
        return 6

    if args.check:
        return run_check()

    return run_inject(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
