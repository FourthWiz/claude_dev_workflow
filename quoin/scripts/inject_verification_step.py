#!/usr/bin/env python3
"""
inject_verification_step.py — Generator for §V Ground-truth verification.

Inserts/refreshes the §V late verify block (all full-§V skills) and the §V early
claims-manifest block (end_of_day only, CRIT-1) into the Claude adapter SKILL.md
files at:
  quoin/adapters/claude/skills/<skill>/SKILL.md

This script is the SOURCE-OF-TRUTH owner for both §V blocks. Structural clone of
inject_pollution_dispatch.py (§0'/§0″ generator) — same constants/template/render/
inject/check/main shape, adapted for §V's two-block-per-skill design and H3-heading
anchors (§V anchors on a heading TEXT match, not "first H2", since the late block
must land immediately before each skill's own final "Report to user"-class step,
and the early block before end_of_day's Step 3b — never a hardcoded line number).

Note: This is a STANDALONE script (stdlib-only on the write path). It does NOT
import from quoin/core/scripts/. Registering it in DEPLOYED_SCRIPTS only is
correct (mirrors inject_pollution_dispatch.py — lessons 2026-05-31 / 2026-06-08).

RECONCILE_LIGHT_SKILLS (status, triage, cost_snapshot) carries the shorter
reconcile-only block (T-08) — read-only reporters get a single reconcile call
with no side-effect check, injected/refreshed/checked exactly like the late
§V-verify block but under its own heading/markers (§V-reconcile).

Exit codes:
  0  success
  1  write error (file not found or could not write)
  6  --dry-run and --check are mutually exclusive
  7  --check: drift detected (missing/duplicated heading, marker, or required token)
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

# ─── Constants (byte-identical to test file literals) ────────────────────────

VERIFY_HEADING = "## §V Ground-truth verification (execute after the skill's work, before the final report)"
CLAIMS_HEADING = "## §V Claims manifest (emit as an always-run early step)"
LIGHT_HEADING = "## §V Reconcile (read-only — no side-effect check)"

VERIFY_BEGIN = "<!-- §V-verify-begin -->"
VERIFY_END = "<!-- §V-verify-end -->"
CLAIMS_BEGIN = "<!-- §V-claims-begin -->"
CLAIMS_END = "<!-- §V-claims-end -->"
LIGHT_BEGIN = "<!-- §V-reconcile-begin -->"
LIGHT_END = "<!-- §V-reconcile-end -->"

# 3 skills that carry the full late §V verify block.
VERIFY_TARGET_SKILLS = ["end_of_day", "start_of_day", "weekly_review"]

# Only end_of_day also carries the early always-run claims-manifest block (CRIT-1) —
# it is the sole skill with a deterministic SessionEnd-hook backstop (T-12) that needs
# a claim source independent of whether the model's own §V step runs.
CLAIMS_EMIT_SKILLS = ["end_of_day"]

# T-08: read-only reporters that carry the light reconcile-only block (no
# side-effect check — they never write task/session state).
RECONCILE_LIGHT_SKILLS = ["status", "triage", "cost_snapshot"]

# Per-skill anchor for the light block: immediately before each skill's own
# final report/present-style step (D-07 robust anchor — heading TEXT match,
# never a hardcoded line number).
LIGHT_CONTRACTS = {
    "status": {"light_anchor_regex": r"^## Important behaviors\s*$"},
    "triage": {"light_anchor_regex": r"^### Step 5: Present proposal\s*$"},
    "cost_snapshot": {"light_anchor_regex": r"^### Step 3: Print summary\s*$"},
}

# ─── Per-skill late §V verify-block bodies + anchor patterns ─────────────────
# late_anchor_regex matches the skill's OWN final "Report to user"-class heading
# text (D-07 robust anchor) — never a hardcoded line number, so a future step
# renumber inside the skill does not break injection.

VERIFY_CONTRACTS = {
    "end_of_day": {
        "late_anchor_regex": r"^### Step 5: Report to user\s*$",
        "verify_body": """\
Run ground-truth reconciliation before composing the Step 5 report — never on a hardcoded
line number, always immediately before this skill's own final report step.

1. Run `python3 __QUOIN_HOME__/scripts/verify_claims.py --check-side-effects --skill end_of_day
   --project-root <project-root>` (side-effect predicates: daily cache written and non-empty;
   every in-scope session flipped `end_of_day_due: no`; resume-cookie present and unexpired;
   lessons-learned prune handled if oversized).
2. Run `python3 __QUOIN_HOME__/scripts/verify_claims.py --reconcile-tasks --claims-file
   <the manifest this skill's own §V Claims manifest step wrote> [--gh-json-file <path> if
   available]` — the in-session model path (live gh, NOT `--finalized-only`; that flag is
   reserved for the SessionEnd hook backstop).
3. If either command exits 8: do NOT finalize a clean report. Surface every MISSING/MISMATCH
   line to the user, self-correct the deterministic gaps you can before composing the report
   (re-flip any session still `end_of_day_due: yes` — idempotent with Step 3d; re-run any
   skipped lessons-learned prune prompt), increment `verification_mismatches` in the
   session-state `## Cost` block, and (re-)write `memory/verification/end_of_day-<today>.md`.
   Leave `verification_ran: no`.
4. If both commands exit 0: set `verification_ran: yes` in the session-state `## Cost` block
   and proceed to the Step 5 report.

Consumers (`/start_of_day`, `/weekly_review`) treat an absent or `no` `verification_ran` on an
in-scope end_of_day session as a mismatch signal — always write this field, never omit it.\
""",
    },
    "start_of_day": {
        "late_anchor_regex": r"^### Step 5: Present the briefing\s*$",
        "verify_body": """\
Before Step 5 (Present the briefing), reconcile trusted state — never on a hardcoded line
number, always immediately before this skill's own final report step.

Run `python3 __QUOIN_HOME__/scripts/verify_claims.py --reconcile-tasks --project-root
<project-root>` (live gh; this subsumes the existing Step 4 `gh pr list` call — derive any
PR/task-status line you present in the briefing from THIS reconcile table, never from a
daily-cache narrative alone).

For every in-scope end_of_day session read in Step 1/Step 4: treat a MISSING or `no`
`verification_ran` field as a mismatch signal to surface, not a silent pass — an
end_of_day session whose own §V step was silently skipped upstream is itself informative.

If the reconcile exits 8: surface the MISMATCH/coverage lines in the briefing rather than
silently dropping them.\
""",
    },
    "weekly_review": {
        "late_anchor_regex": r"^### Step 5: Present to the user\s*$",
        "verify_body": """\
Before Step 5 (Present to the user), reconcile the week's rollup — never on a hardcoded
line number, always immediately before this skill's own final report step.

Run `python3 __QUOIN_HOME__/scripts/verify_claims.py --reconcile-tasks --project-root
<project-root>` (live gh). Before asserting any task "completed" or "merged" in the
`## Completed Work` section, confirm the reconcile table agrees (`finalized: true` or
`pr: MERGED`) — never assert completion from the daily-cache narrative alone.

If the reconcile exits 8: surface each MISMATCH under `## Decisions Made` (or a dedicated
note) rather than silently completing the rollup.\
""",
    },
}

# ─── end_of_day-only early claims-manifest block ─────────────────────────────
# Anchored immediately BEFORE '### Step 3b' — i.e. AFTER the daily-cache write inside
# Step 3, NOT at the '### Step 3' heading itself (MIN-1: anchoring at the heading would
# place the manifest-write instruction above the cache it derives from).

CLAIMS_CONTRACTS = {
    "end_of_day": {
        "early_claims_anchor_regex": r"^### Step 3b: Review and promote daily insights\s*$",
        "claims_body": """\
This step ALWAYS runs (it is not the verification step — it is the claim source the
SessionEnd-hook backstop reads even when the model later skips §V, CRIT-1) and runs
immediately after the daily cache above is written, never before.

Write a STRUCTURED `## Claims` manifest — a fenced `yaml` block, one entry per in-window
task, `{task_ref: <str>, status: <enum>}` where `status` is one of `{awaiting_pr,
awaiting_end_of_task, in_progress, merged, finalized}` — to
`memory/verification/end_of_day-<today>.md`. Enumerate EVERY in-window task (a task
finalized within the run window, or an in-window active task). This manifest MUST NOT be
written empty WHEN THERE IS IN-WINDOW WORK to claim; a genuine quiet day with no in-window
finalized/active work correctly writes a zero-claim manifest (you are NOT required to
enumerate the full all-time `finalized/` archive).\
""",
    },
}


# ─── Block rendering ──────────────────────────────────────────────────────────

def render_verify_block(skill: str) -> str:
    """Render the late §V verify block for a given skill."""
    body = VERIFY_CONTRACTS[skill]["verify_body"]
    return f"{VERIFY_HEADING}\n\n{VERIFY_BEGIN}\n{body}\n{VERIFY_END}\n\n"


def render_claims_block(skill: str) -> str:
    """Render the early §V claims-manifest block for a given skill (end_of_day only)."""
    body = CLAIMS_CONTRACTS[skill]["claims_body"]
    return f"{CLAIMS_HEADING}\n\n{CLAIMS_BEGIN}\n{body}\n{CLAIMS_END}\n\n"


def render_light_block(skill: str) -> str:
    """Render the light reconcile-only block for a reporter skill (T-08)."""
    body = (
        "Before surfacing any task/PR status, run `python3 __QUOIN_HOME__/scripts/"
        "verify_claims.py --reconcile-tasks --project-root <project-root>` and derive the "
        "displayed status from the reconcile table, not from a cached narrative alone. "
        "If the reconcile exits 8, surface the contradiction rather than silently reporting "
        "the narrative version."
    )
    return f"{LIGHT_HEADING}\n\n{LIGHT_BEGIN}\n{body}\n{LIGHT_END}\n\n"


# ─── File manipulation ────────────────────────────────────────────────────────

def _replace_existing_block(text: str, heading: str, end_marker: str, new_block: str) -> str:
    """Replace an existing block (heading through its own end_marker) in place.

    Deliberately does NOT delimit on "next '## ' heading" (the pattern
    inject_pollution_dispatch.py uses) — end_of_day carries TWO §V-owned H2 blocks
    (claims + verify) in the same file, so "next H2" from the claims heading can
    resolve to the verify heading and swallow everything between them. Anchoring on
    this block's own end marker is exact regardless of what else shares the file.
    """
    pattern = re.compile(
        r"^" + re.escape(heading) + r".*?" + re.escape(end_marker) + r"\n*",
        flags=re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        return text[: match.start()] + new_block + text[match.end() :]
    return text


def _find_anchor_line_index(lines: list[str], anchor_regex: str) -> int:
    """Return the 0-indexed line number of the first line matching anchor_regex.

    Returns -1 if not found (caller should FAIL LOUD — anchors are heading TEXT
    matches, not line numbers, so a missing match means the skill's structure
    changed in a way this generator does not yet know how to target).
    """
    pattern = re.compile(anchor_regex)
    for i, line in enumerate(lines):
        if pattern.match(line.rstrip("\n")):
            return i
    return -1


def inject_verify_into_file(skill: str, skill_md: pathlib.Path) -> str:
    """Return new content for skill_md with the late §V verify block injected/refreshed."""
    text = skill_md.read_text(encoding="utf-8")
    block = render_verify_block(skill)

    if VERIFY_HEADING in text:
        return _replace_existing_block(text, VERIFY_HEADING, VERIFY_END, block)

    lines = text.splitlines(keepends=True)
    anchor_regex = VERIFY_CONTRACTS[skill]["late_anchor_regex"]
    idx = _find_anchor_line_index(lines, anchor_regex)
    if idx == -1:
        raise ValueError(
            f"No line matching anchor {anchor_regex!r} found in {skill_md} — cannot "
            "determine §V verify-block insertion point. FAIL LOUD."
        )
    lines.insert(idx, block)
    return "".join(lines)


def inject_claims_into_file(skill: str, skill_md: pathlib.Path) -> str:
    """Return new content for skill_md with the early §V claims block injected/refreshed."""
    text = skill_md.read_text(encoding="utf-8")
    block = render_claims_block(skill)

    if CLAIMS_HEADING in text:
        return _replace_existing_block(text, CLAIMS_HEADING, CLAIMS_END, block)

    lines = text.splitlines(keepends=True)
    anchor_regex = CLAIMS_CONTRACTS[skill]["early_claims_anchor_regex"]
    idx = _find_anchor_line_index(lines, anchor_regex)
    if idx == -1:
        raise ValueError(
            f"No line matching anchor {anchor_regex!r} found in {skill_md} — cannot "
            "determine §V claims-block insertion point. FAIL LOUD."
        )
    lines.insert(idx, block)
    return "".join(lines)


def inject_light_into_file(skill: str, skill_md: pathlib.Path) -> str:
    """Return new content for skill_md with the light §V-reconcile block injected/refreshed."""
    text = skill_md.read_text(encoding="utf-8")
    block = render_light_block(skill)

    if LIGHT_HEADING in text:
        return _replace_existing_block(text, LIGHT_HEADING, LIGHT_END, block)

    lines = text.splitlines(keepends=True)
    anchor_regex = LIGHT_CONTRACTS[skill]["light_anchor_regex"]
    idx = _find_anchor_line_index(lines, anchor_regex)
    if idx == -1:
        raise ValueError(
            f"No line matching anchor {anchor_regex!r} found in {skill_md} — cannot "
            "determine §V-reconcile insertion point. FAIL LOUD."
        )
    lines.insert(idx, block)
    return "".join(lines)


def _atomic_write(skill_md: pathlib.Path, content: str) -> None:
    tmp_path = skill_md.with_suffix(".md.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, skill_md)


# ─── Main processing ──────────────────────────────────────────────────────────

def _get_adapter_dir() -> pathlib.Path:
    """Return the adapter skills directory (quoin/adapters/claude/skills/)."""
    script_dir = pathlib.Path(__file__).resolve().parent
    quoin_pkg = script_dir.parent  # quoin/quoin/
    return quoin_pkg / "adapters" / "claude" / "skills"


def run_inject(*, dry_run: bool = False) -> int:
    """Inject/refresh the late §V block into VERIFY_TARGET_SKILLS, and the early
    claims block into CLAIMS_EMIT_SKILLS. Claims injection runs first for end_of_day
    so the late-block insertion (which may match a line shifted by the early
    insertion) always re-reads fresh content between the two passes.

    Returns 0 on success, 1 on any error.
    """
    adapter_dir = _get_adapter_dir()
    errors: list[str] = []

    for skill in CLAIMS_EMIT_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"MISSING (§V-claims): {skill_md}")
            continue
        try:
            new_content = inject_claims_into_file(skill, skill_md)
        except (ValueError, OSError) as e:
            errors.append(f"ERROR processing §V-claims for {skill}: {e}")
            continue
        if dry_run:
            print(f"=== {skill} §V-claims preview ===")
            idx = new_content.find(CLAIMS_HEADING)
            end = new_content.find("\n## ", idx + len(CLAIMS_HEADING))
            print(new_content[idx : end + 1 if end != -1 else None][:800])
            continue
        try:
            _atomic_write(skill_md, new_content)
        except OSError as e:
            errors.append(f"WRITE ERROR for §V-claims in {skill}: {e}")
            continue
        print(f"  injected §V-claims into {skill_md}")

    for skill in VERIFY_TARGET_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"MISSING (§V-verify): {skill_md}")
            continue
        try:
            new_content = inject_verify_into_file(skill, skill_md)
        except (ValueError, OSError) as e:
            errors.append(f"ERROR processing §V-verify for {skill}: {e}")
            continue
        if dry_run:
            print(f"=== {skill} §V-verify preview ===")
            idx = new_content.find(VERIFY_HEADING)
            end = new_content.find("\n## ", idx + len(VERIFY_HEADING))
            print(new_content[idx : end + 1 if end != -1 else None][:800])
            continue
        try:
            _atomic_write(skill_md, new_content)
        except OSError as e:
            errors.append(f"WRITE ERROR for §V-verify in {skill}: {e}")
            continue
        print(f"  injected §V-verify into {skill_md}")

    for skill in RECONCILE_LIGHT_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"MISSING (§V-reconcile): {skill_md}")
            continue
        try:
            new_content = inject_light_into_file(skill, skill_md)
        except (ValueError, OSError) as e:
            errors.append(f"ERROR processing §V-reconcile for {skill}: {e}")
            continue
        if dry_run:
            print(f"=== {skill} §V-reconcile preview ===")
            idx = new_content.find(LIGHT_HEADING)
            end = new_content.find("\n## ", idx + len(LIGHT_HEADING))
            print(new_content[idx : end + 1 if end != -1 else None][:800])
            continue
        try:
            _atomic_write(skill_md, new_content)
        except OSError as e:
            errors.append(f"WRITE ERROR for §V-reconcile in {skill}: {e}")
            continue
        print(f"  injected §V-reconcile into {skill_md}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return 0


def run_check() -> int:
    """--check mode: verify VERIFY_TARGET_SKILLS carry a fresh late §V block (heading
    once, markers once, required tokens present) and CLAIMS_EMIT_SKILLS additionally
    carry a fresh early §V-claims block, with claims strictly before verify in the file.

    Returns 0 if all files are fresh, 7 if any drift detected.
    """
    adapter_dir = _get_adapter_dir()

    verify_required_tokens = [
        "verify_claims",
        "--reconcile-tasks",
        "exits 8",
    ]
    claims_required_tokens = [
        "## Claims",
        "memory/verification/end_of_day-<today>.md",
        "MUST NOT be written empty",
    ]
    light_required_tokens = [
        "verify_claims",
        "--reconcile-tasks",
        "surface the contradiction",
    ]

    def _normalize(s: str) -> str:
        # Required tokens are checked against reflowed prose, so collapse all
        # whitespace runs (including the line breaks a token may be word-wrapped
        # across) to single spaces before substring matching.
        return re.sub(r"\s+", " ", s)

    drifted: list[str] = []

    for skill in VERIFY_TARGET_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            drifted.append(f"{skill}: adapter SKILL.md missing at {skill_md}")
            continue
        text = skill_md.read_text(encoding="utf-8")

        if text.count(VERIFY_HEADING) == 0:
            drifted.append(f"{skill}: §V-verify heading missing")
            continue
        if text.count(VERIFY_HEADING) > 1:
            drifted.append(f"{skill}: §V-verify heading appears more than once")

        for marker in (VERIFY_BEGIN, VERIFY_END):
            if text.count(marker) != 1:
                drifted.append(f"{skill}: §V-verify marker {marker!r} missing or duplicated")

        block_match = re.search(
            re.escape(VERIFY_HEADING) + r".*?" + re.escape(VERIFY_END),
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
        if not block_match:
            drifted.append(f"{skill}: §V-verify block could not be extracted")
        else:
            block = _normalize(block_match.group(0))
            for token in verify_required_tokens:
                if _normalize(token) not in block:
                    drifted.append(f"{skill}: missing required token {token!r} in §V-verify block")

    for skill in CLAIMS_EMIT_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            drifted.append(f"{skill}: adapter SKILL.md missing at {skill_md} (§V-claims check)")
            continue
        text = skill_md.read_text(encoding="utf-8")

        if text.count(CLAIMS_HEADING) == 0:
            drifted.append(f"{skill}: §V-claims heading missing")
            continue
        if text.count(CLAIMS_HEADING) > 1:
            drifted.append(f"{skill}: §V-claims heading appears more than once")

        for marker in (CLAIMS_BEGIN, CLAIMS_END):
            if text.count(marker) != 1:
                drifted.append(f"{skill}: §V-claims marker {marker!r} missing or duplicated")

        block_match = re.search(
            re.escape(CLAIMS_HEADING) + r".*?" + re.escape(CLAIMS_END),
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
        if not block_match:
            drifted.append(f"{skill}: §V-claims block could not be extracted")
        else:
            block = _normalize(block_match.group(0))
            for token in claims_required_tokens:
                if _normalize(token) not in block:
                    drifted.append(f"{skill}: missing required token {token!r} in §V-claims block")

        claims_idx = text.find(CLAIMS_HEADING)
        verify_idx = text.find(VERIFY_HEADING)
        if claims_idx != -1 and verify_idx != -1 and claims_idx >= verify_idx:
            drifted.append(f"{skill}: §V-claims appears AFTER §V-verify (ordering violation)")

    for skill in RECONCILE_LIGHT_SKILLS:
        skill_md = adapter_dir / skill / "SKILL.md"
        if not skill_md.exists():
            drifted.append(f"{skill}: adapter SKILL.md missing at {skill_md} (§V-reconcile check)")
            continue
        text = skill_md.read_text(encoding="utf-8")

        if text.count(LIGHT_HEADING) == 0:
            drifted.append(f"{skill}: §V-reconcile heading missing")
            continue
        if text.count(LIGHT_HEADING) > 1:
            drifted.append(f"{skill}: §V-reconcile heading appears more than once")

        for marker in (LIGHT_BEGIN, LIGHT_END):
            if text.count(marker) != 1:
                drifted.append(f"{skill}: §V-reconcile marker {marker!r} missing or duplicated")

        block_match = re.search(
            re.escape(LIGHT_HEADING) + r".*?" + re.escape(LIGHT_END),
            text,
            flags=re.DOTALL | re.MULTILINE,
        )
        if not block_match:
            drifted.append(f"{skill}: §V-reconcile block could not be extracted")
        else:
            block = _normalize(block_match.group(0))
            for token in light_required_tokens:
                if _normalize(token) not in block:
                    drifted.append(f"{skill}: missing required token {token!r} in §V-reconcile block")

    if drifted:
        for msg in drifted:
            print(f"DRIFT: {msg}", file=sys.stderr)
        return 7
    print("inject_verification_step --check: all target adapter files are fresh")
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
        help="Verify all target adapter SKILL.md files carry correct §V blocks; exit 7 if any drift",
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
