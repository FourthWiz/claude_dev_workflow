#!/bin/sh
# test_stage6_checkpoint_probe_wiring_canary.sh — executable integration canary
# for IVG-258 S-6 (checkpoint-spend conditioning), T-13.
#
# Unlike the text-structural guards (T-02/T-04/T-06/T-08), this test writes a
# run-state record with the REAL writer (run_state.py --write, never
# hand-crafted JSON) and then drives the REAL consumer scripts against it:
# userpromptsubmit.sh unmodified, and the actual fenced ```sh blocks
# EXTRACTED VERBATIM out of checkpoint/SKILL.md's Step 1.4 and run/SKILL.md's
# self-checkpoint bullet — not hand-copied paraphrases of them (D-31).
#
# Case A  — CRIT-1 session-id-mismatch class, branch (2) of the advisory.
# Case A2 — MAJ-3 session-id-mismatch class, branch (3) of the advisory.
# Case B  — MAJ-1 inert-guard class, /checkpoint Step 1.4's sourcing, with a
#           negative control that deletes only the extracted block's source
#           line.
# Case B2 — MAJ-1 round-4 unresolvable-root class, /run's self-checkpoint
#           bullet, positive path only (T-06 clause (h) already text-checks
#           the bare-{root} regression).
#
# Requires: jq on PATH, python3 (stdlib-only run_state.py), sh (POSIX).
#
# Usage: sh quoin/dev/tests/test_stage6_checkpoint_probe_wiring_canary.sh
# Exit 0 if all tests pass; non-zero with failure list otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures/hooks"
HOOK="$SCRIPT_DIR/../../hooks/userpromptsubmit.sh"
CHECKPOINT_SKILL="$SCRIPT_DIR/../../adapters/claude/skills/checkpoint/SKILL.md"
RUN_SKILL="$SCRIPT_DIR/../../adapters/claude/skills/run/SKILL.md"
# This worktree's absolute path — quoted throughout because the repo path
# contains "My Drive" (a literal space).
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

make_stdin() {
  prompt="$1"
  transcript="$2"
  session_id="$3"
  cwd="$4"
  printf '{"prompt":"%s","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
    "$prompt" "$transcript" "$session_id" "$cwd"
}

run_hook() {
  stdin_json="$1"
  printf '%s' "$stdin_json" | sh "$HOOK" 2>/dev/null
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_s6_canary_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

if [ ! -f "$FIXTURES_DIR/transcript_97pct.jsonl" ]; then
  printf 'Building fixtures...\n'
  sh "$SCRIPT_DIR/build_hook_fixtures.sh" > /dev/null 2>&1
fi

TRANSCRIPT_88="$FIXTURES_DIR/transcript_88pct.jsonl"
TRANSCRIPT_97="$FIXTURES_DIR/transcript_97pct.jsonl"

# ─── Write the fixture run-state record via the REAL writer ─────────────────
# Deliberately mismatched session_id ("sid-other-party"), reproducing exactly
# the record shape thorough_plan/SKILL.md:568 leaves behind mid-round (a
# third-party session_id, active: true, at_stage_boundary: false).

python3 "$REPO_ROOT/quoin/core/scripts/run_state.py" --write \
  --project-root "$TMPDIR_TEST" \
  --task canary-probe \
  --session-id "sid-other-party" \
  --phase implement \
  --phase-index 2 \
  --at-stage-boundary false \
  --step "canary: probe wiring check" \
  --next-action "verify run_state_probe wiring" \
  --artifact "N/A" > /dev/null

RUN_STATE_FILE="$TMPDIR_TEST/.workflow_artifacts/memory/run-state-canary-probe.json"
if [ -f "$RUN_STATE_FILE" ]; then
  ok "fixture: run_state.py --write produced $RUN_STATE_FILE"
else
  fail "fixture: run_state.py --write did not produce the expected run-state file"
fi

# ═══ Case A — CRIT-1 session-id-mismatch class, branch (2) (advisory) ═══════

stdin_a=$(make_stdin 'reviewing the diff now' "$TRANSCRIPT_88" "sid-hook-invoker" "$TMPDIR_TEST")
out_a=$(run_hook "$stdin_a")
if printf '%s' "$out_a" | grep -q 'consider running /checkpoint' 2>/dev/null; then
  ok "Case A: 88% + real active record, session_id mismatch → checkpoint nudge fires"
else
  fail "Case A: expected 'consider running /checkpoint' in hook output, got: $out_a"
fi

# ═══ Case A2 — MAJ-3 session-id-mismatch class, branch (3) ══════════════════

stdin_a2=$(make_stdin 'reviewing the diff now' "$TRANSCRIPT_97" "sid-hook-invoker" "$TMPDIR_TEST")
out_a2=$(run_hook "$stdin_a2")
if printf '%s' "$out_a2" | grep -q 'and consider /checkpoint plus a fresh session' 2>/dev/null; then
  ok "Case A2: 97% + real active record, session_id mismatch → checkpoint nudge fires"
else
  fail "Case A2: expected 'and consider /checkpoint plus a fresh session' in hook output, got: $out_a2"
fi

# ─── Extraction helper: slice a heading range, then pull the single fenced
# ```sh block within it whose content contains a given pattern. ────────────

extract_probe_block() {
  # $1 = source file, $2 = start heading (literal), $3 = end heading (literal)
  src="$1"; start_h="$2"; end_h="$3"
  awk -v start="$start_h" -v end="$end_h" '
    index($0, start) == 1 { insec = 1 }
    insec { print }
    insec && index($0, end) == 1 && NR > 1 { exit }
  ' "$src" > "$TMPDIR_TEST/_slice.tmp"
  awk '
    /^[ \t]*```sh$/ { capturing = 1; block = ""; next }
    /^[ \t]*```$/ {
      if (capturing && index(block, "command -v run_state_probe") > 0) { printf "%s", block }
      capturing = 0; block = ""; next
    }
    capturing { block = block $0 "\n" }
  ' "$TMPDIR_TEST/_slice.tmp"
}

# ═══ Case B — MAJ-1 inert-guard class (/checkpoint Step 1.4 sourcing) ═══════

extract_probe_block "$CHECKPOINT_SKILL" "### Step 1.4:" "### Step 1.45:" \
  | sed 's#__QUOIN_HOME__#"$REPO_ROOT/quoin"#' \
  > "$TMPDIR_TEST/step14_block.sh"

if [ -s "$TMPDIR_TEST/step14_block.sh" ]; then
  ok "Case B step 0: extracted a non-empty fenced block from checkpoint/SKILL.md Step 1.4"
else
  fail "Case B step 0: extraction from checkpoint/SKILL.md Step 1.4 produced nothing"
fi

# Positive path: real record is still fresh/active at $TMPDIR_TEST.
out_b1=$(REPO_ROOT="$REPO_ROOT" _PROJECT_ROOT="$TMPDIR_TEST" sh "$TMPDIR_TEST/step14_block.sh")
if [ "$out_b1" = "PROBE_ACTIVE" ]; then
  ok "Case B.1: extracted checkpoint/SKILL.md block prints PROBE_ACTIVE against a real active record"
else
  fail "Case B.1: expected stdout exactly PROBE_ACTIVE, got: $out_b1"
fi

# Negative control: delete ONLY the extracted copy's source line.
sed '/_lib\.sh/d' "$TMPDIR_TEST/step14_block.sh" > "$TMPDIR_TEST/step14_block_neg.sh"
out_b2=$(REPO_ROOT="$REPO_ROOT" _PROJECT_ROOT="$TMPDIR_TEST" sh "$TMPDIR_TEST/step14_block_neg.sh")
if [ "$out_b2" = "GUARD_UNAVAILABLE" ]; then
  ok "Case B.2 (negative control): the same block, source line removed, prints GUARD_UNAVAILABLE"
else
  fail "Case B.2 (negative control): expected stdout exactly GUARD_UNAVAILABLE, got: $out_b2"
fi

# ═══ Case B2 — MAJ-1 round-4 unresolvable-root class (/run self-checkpoint) ═

extract_probe_block "$RUN_SKILL" "## Hook cooperation (autonomous)" "## Gate boundaries reference" \
  | sed 's#__QUOIN_HOME__#"$REPO_ROOT/quoin"#' \
  > "$TMPDIR_TEST/run_hook_coop_block.sh"

if [ -s "$TMPDIR_TEST/run_hook_coop_block.sh" ]; then
  ok "Case B2 step 0: extracted a non-empty fenced block from run/SKILL.md's self-checkpoint bullet"
else
  fail "Case B2 step 0: extraction from run/SKILL.md's Hook cooperation section produced nothing"
fi

# Positive path only: unlike Case B, this block resolves its own root via
# resolve_project_root "$(pwd)" rather than an env var — controlled here by
# changing the current directory, not by exporting _PROJECT_ROOT.
out_b2pos=$(cd "$TMPDIR_TEST" && REPO_ROOT="$REPO_ROOT" sh "$TMPDIR_TEST/run_hook_coop_block.sh")
if [ "$out_b2pos" = "PROBE_ACTIVE" ]; then
  ok "Case B2: extracted run/SKILL.md block prints PROBE_ACTIVE against a real active record"
else
  fail "Case B2: expected stdout exactly PROBE_ACTIVE, got: $out_b2pos"
fi

# ─── Silence check: none of the extracted blocks should ever emit anything
# other than the single token line on stdout (already enforced by the exact
# equality checks above); no stderr leakage either. ──────────────────────────

# ─── Summary ─────────────────────────────────────────────────────────────────

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'Failures:%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
exit 0
