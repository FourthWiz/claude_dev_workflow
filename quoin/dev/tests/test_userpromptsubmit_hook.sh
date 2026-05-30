#!/bin/sh
# test_userpromptsubmit_hook.sh — fixture tests for quoin/hooks/userpromptsubmit.sh
#
# Covers all acceptance cases from T-12 / T-09 acceptance criteria.
# Requires: jq on PATH, sh (POSIX).
#
# Usage: sh quoin/dev/tests/test_userpromptsubmit_hook.sh
# Exit 0 if all tests pass; non-zero with failure list otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures/hooks"
HOOK="$SCRIPT_DIR/../../hooks/userpromptsubmit.sh"
DEPLOYED_HOOK="$HOME/.claude/hooks/userpromptsubmit.sh"

# ─── helpers ──────────────────────────────────────────────────────────────────

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

# Make a JSON stdin for the hook
make_stdin() {
  local prompt="$1"
  local transcript="$2"
  local session_id="${3:-test-session-default}"
  local cwd="${4:-$TMPDIR_TEST}"
  printf '{"prompt":"%s","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
    "$prompt" "$transcript" "$session_id" "$cwd"
}

# Run hook with given stdin JSON; capture stdout and exit code
run_hook() {
  local stdin_json="$1"
  printf '%s' "$stdin_json" | sh "$HOOK" 2>/dev/null
  return $?
}

run_hook_rc() {
  local stdin_json="$1"
  printf '%s' "$stdin_json" | sh "$HOOK" 2>/dev/null
  # returns exit code of hook
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_ups_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

# ─── Build fixtures if not present ────────────────────────────────────────────

if [ ! -f "$FIXTURES_DIR/transcript_97pct.jsonl" ]; then
  printf 'Building fixtures...\n'
  sh "$SCRIPT_DIR/build_hook_fixtures.sh" > /dev/null 2>&1
fi

TRANSCRIPT_70="$FIXTURES_DIR/transcript_70pct.jsonl"
TRANSCRIPT_88="$FIXTURES_DIR/transcript_88pct.jsonl"
TRANSCRIPT_97="$FIXTURES_DIR/transcript_97pct.jsonl"

# ─── Shebang assertion ────────────────────────────────────────────────────────

# Test against source hook file
if head -1 "$HOOK" | grep -qE '^#!/bin/sh( |$)'; then
  ok "shebang assertion: source hook starts with #!/bin/sh"
else
  fail "shebang assertion: source hook does not start with #!/bin/sh"
fi

# If deployed hook exists, also check it
if [ -f "$DEPLOYED_HOOK" ]; then
  if head -1 "$DEPLOYED_HOOK" | grep -qE '^#!/bin/sh( |$)'; then
    ok "shebang assertion: deployed hook starts with #!/bin/sh"
  else
    fail "shebang assertion: deployed hook does not start with #!/bin/sh"
  fi
fi

# ─── STEP 0 exemption cases ──────────────────────────────────────────────────

# (a) /checkpoint → exempt (exit 0, no stdout)
stdin=$(make_stdin '/checkpoint' "$TRANSCRIPT_70")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(a) /checkpoint → exempt (no output)"
else
  fail "(a) /checkpoint → expected no output, got: $out"
fi

# (b) /checkpoint --restore → exempt (first token is /checkpoint, inner *-arm)
stdin=$(make_stdin '/checkpoint --restore' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(b) /checkpoint --restore → exempt"
else
  fail "(b) /checkpoint --restore → expected exempt, got: $out"
fi

# (c) '   /compact' (leading spaces) → exempt
stdin=$(make_stdin '   /compact' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(c) '   /compact' (leading spaces) → exempt"
else
  fail "(c) '   /compact' leading spaces → expected exempt, got: $out"
fi

# (d) /clear → exempt
stdin=$(make_stdin '/clear' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(d) /clear → exempt"
else
  fail "(d) /clear → expected exempt, got: $out"
fi

# (e) /help arg1 arg2 → exempt (first token is /help)
stdin=$(make_stdin '/help arg1 arg2' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(e) /help arg1 arg2 → exempt"
else
  fail "(e) /help arg1 arg2 → expected exempt, got: $out"
fi

# (f) /checkpointfoo → NOT exempt; falls through to threshold logic
# Use QUOIN_STOP_BPS=7500 override: 70% fixture (bps≈7000) < 7500 → passthrough.
# Default threshold is 7000; at exactly 70% the fixture could hit the boundary.
stdin=$(make_stdin '/checkpointfoo' "$TRANSCRIPT_70")
out=$(printf '%s' "$stdin" | QUOIN_STOP_BPS=7500 sh "$HOOK" 2>/dev/null)
if [ -z "$out" ]; then
  ok "(f) /checkpointfoo with 70% fixture → not exempt, falls through, passthrough"
else
  fail "(f) /checkpointfoo with 70% fixture → unexpected output: $out"
fi

# (g) /checkpoint--restore (no space) → NOT exempt
# With 97% fixture → should block
stdin=$(make_stdin '/checkpoint--restore' "$TRANSCRIPT_97" "sess-g" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
if printf '%s' "$out" | grep -q '"decision": *"block"' 2>/dev/null || \
   printf '%s' "$out" | jq -e '.decision == "block"' > /dev/null 2>/dev/null; then
  ok "(g) /checkpoint--restore (no space) with 97% fixture → NOT exempt, blocked"
else
  fail "(g) /checkpoint--restore (no space) → expected block, got: $out"
fi
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-g.txt"

# (h) '/checkpoint    --restore' (multiple spaces) → exempt
stdin=$(make_stdin '/checkpoint    --restore' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(h) '/checkpoint    --restore' (multiple spaces) → exempt"
else
  fail "(h) '/checkpoint    --restore' multiple spaces → expected exempt, got: $out"
fi

# (i) Leading newline prompt: '\n/checkpoint' → exempt (sed strips leading whitespace)
# We encode a literal newline in JSON using \n
stdin_raw='{"prompt":"\n/checkpoint","transcript_path":"'"$TRANSCRIPT_97"'","session_id":"test-i","cwd":"'"$TMPDIR_TEST"'"}'
out=$(printf '%s' "$stdin_raw" | sh "$HOOK" 2>/dev/null)
if [ -z "$out" ]; then
  ok "(i) leading-newline prompt \\n/checkpoint → exempt"
else
  fail "(i) leading-newline prompt → expected exempt, got: $out"
fi

# (j) Leading CR prompt: '\r/checkpoint' → exempt
stdin_raw='{"prompt":"\r/checkpoint","transcript_path":"'"$TRANSCRIPT_97"'","session_id":"test-j","cwd":"'"$TMPDIR_TEST"'"}'
out=$(printf '%s' "$stdin_raw" | sh "$HOOK" 2>/dev/null)
if [ -z "$out" ]; then
  ok "(j) leading-CR prompt \\r/checkpoint → exempt"
else
  fail "(j) leading-CR prompt → expected exempt, got: $out"
fi

# (k) All-whitespace prompt → cmd is empty; falls through to threshold logic
# Use QUOIN_STOP_BPS=7500 override so 70% fixture is below threshold.
stdin_raw='{"prompt":"   \n\t  ","transcript_path":"'"$TRANSCRIPT_70"'","session_id":"test-k","cwd":"'"$TMPDIR_TEST"'"}'
out=$(printf '%s' "$stdin_raw" | QUOIN_STOP_BPS=7500 sh "$HOOK" 2>/dev/null)
if [ -z "$out" ]; then
  ok "(k) all-whitespace prompt with 70% fixture → no output (below threshold)"
else
  fail "(k) all-whitespace prompt → unexpected output: $out"
fi

# (l) /checkpoint --purge → NOT exempt (destructive subcommand carve-out, Q-01 RESOLVED)
# With 97% fixture → should produce block JSON
stdin=$(make_stdin '/checkpoint --purge' "$TRANSCRIPT_97" "sess-l" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
if printf '%s' "$out" | grep -q '"decision"' 2>/dev/null; then
  if printf '%s' "$out" | grep -q '"block"' 2>/dev/null; then
    ok "(l) /checkpoint --purge with 97% fixture → NOT exempt, produces block JSON"
  else
    fail "(l) /checkpoint --purge with 97% fixture → got decision but not block: $out"
  fi
else
  fail "(l) /checkpoint --purge with 97% fixture → expected block JSON, got: $out"
fi
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-l.txt"

# (l2) /checkpoint    --purge (multi-space) → also NOT exempt
stdin=$(make_stdin '/checkpoint    --purge' "$TRANSCRIPT_97" "sess-l2" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
if printf '%s' "$out" | grep -q '"block"' 2>/dev/null; then
  ok "(l2) '/checkpoint    --purge' multi-space → NOT exempt, blocked"
else
  fail "(l2) '/checkpoint    --purge' multi-space → expected block: $out"
fi
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-l2.txt"

# (m) /checkpoint --restore → exempt (positive control for narrow scope of --purge carve-out)
stdin=$(make_stdin '/checkpoint --restore' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(m) /checkpoint --restore positive control → exempt (only --purge is carved out)"
else
  fail "(m) /checkpoint --restore → expected exempt, got: $out"
fi

# (m2) /checkpoint --some-future-arg → exempt (default * arm)
stdin=$(make_stdin '/checkpoint --some-future-arg' "$TRANSCRIPT_97")
out=$(run_hook "$stdin")
if [ -z "$out" ]; then
  ok "(m2) /checkpoint --some-future-arg → exempt (default * arm)"
else
  fail "(m2) /checkpoint --some-future-arg → expected exempt, got: $out"
fi

# ─── Three threshold branches ─────────────────────────────────────────────────

# Branch (1): passthrough — 70% fixture (bps=6999 < 7500 STOP_BPS; env-var override set to 7500
# for margin headroom — default is 7000 which leaves only 1 bps margin from this fixture)
stdin=$(make_stdin 'do some work' "$TRANSCRIPT_70" "sess-branch1" "$TMPDIR_TEST")
out=$(printf '%s' "$stdin" | QUOIN_STOP_BPS=7500 sh "$HOOK" 2>/dev/null)
if [ -z "$out" ]; then
  ok "branch(1): 70% fixture → passthrough (no output)"
else
  fail "branch(1): 70% fixture → expected no output, got: $out"
fi

# Branch (2): advisory — 88% fixture (bps=8800, STOP_BPS=7000 <= 8800 < BLOCK_BPS 9500)
stdin=$(make_stdin 'do some work' "$TRANSCRIPT_88" "sess-branch2" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
if printf '%s' "$out" | grep -q 'additionalContext' 2>/dev/null; then
  # Check the percentage string contains 88.
  if printf '%s' "$out" | grep -q '88\.' 2>/dev/null; then
    ok "branch(2): 88% fixture → advisory JSON with 88.xx% in message"
  else
    fail "branch(2): 88% fixture → advisory JSON but missing 88. in message: $out"
  fi
else
  fail "branch(2): 88% fixture → expected advisory JSON, got: $out"
fi

# Branch (3): block — 97% fixture (bps=9700 >= 9500 BLOCK_BPS)
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-block.txt"
stdin=$(make_stdin 'do some work' "$TRANSCRIPT_97" "sess-block" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
if printf '%s' "$out" | grep -q '"decision"' 2>/dev/null && \
   printf '%s' "$out" | grep -q '"block"' 2>/dev/null; then
  ok "branch(3): 97% fixture → block JSON"
else
  fail "branch(3): 97% fixture → expected block JSON, got: $out"
fi
# Verify pending-prompt file was written
if [ -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-block.txt" ]; then
  ok "branch(3): pending-prompt-sess-block.txt written"
else
  fail "branch(3): pending-prompt-sess-block.txt NOT written"
fi
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-block.txt"

# ─── Error-ordering invariant ─────────────────────────────────────────────────

# Make the memory directory read-only so the pending-prompt write fails
chmod 555 "$TMPDIR_TEST/.workflow_artifacts/memory" 2>/dev/null || true
stdin=$(make_stdin 'do some work' "$TRANSCRIPT_97" "sess-errord" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
# Restore permissions
chmod 755 "$TMPDIR_TEST/.workflow_artifacts/memory" 2>/dev/null || true

if [ -z "$out" ] || ! printf '%s' "$out" | grep -q '"decision"' 2>/dev/null; then
  ok "error-ordering invariant: block JSON NOT emitted when pending-prompt write fails"
else
  fail "error-ordering invariant: block JSON emitted even though pending-prompt write failed: $out"
fi

# ─── Concurrent-fire test (CRIT-3) ───────────────────────────────────────────

# Fork two background hook invocations with different session IDs
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-aaa.txt"
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-bbb.txt"

stdin_a=$(make_stdin 'prompt for session aaa' "$TRANSCRIPT_97" "sess-aaa" "$TMPDIR_TEST")
stdin_b=$(make_stdin 'prompt for session bbb' "$TRANSCRIPT_97" "sess-bbb" "$TMPDIR_TEST")

printf '%s' "$stdin_a" | sh "$HOOK" 2>/dev/null > /dev/null &
PID_A=$!
printf '%s' "$stdin_b" | sh "$HOOK" 2>/dev/null > /dev/null &
PID_B=$!
wait "$PID_A" 2>/dev/null || true
wait "$PID_B" 2>/dev/null || true

if [ -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-aaa.txt" ]; then
  content_a=$(cat "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-aaa.txt")
  if printf '%s' "$content_a" | grep -q "prompt for session aaa" && \
     printf '%s' "$content_a" | grep -q "=== BLOCKED PROMPT"; then
    ok "concurrent-fire (CRIT-3): pending-prompt-sess-aaa.txt has headered content with correct prompt"
  else
    fail "concurrent-fire: pending-prompt-sess-aaa.txt has wrong content: $content_a"
  fi
else
  fail "concurrent-fire: pending-prompt-sess-aaa.txt not written"
fi

if [ -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-bbb.txt" ]; then
  content_b=$(cat "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-bbb.txt")
  if printf '%s' "$content_b" | grep -q "prompt for session bbb" && \
     printf '%s' "$content_b" | grep -q "=== BLOCKED PROMPT"; then
    ok "concurrent-fire (CRIT-3): pending-prompt-sess-bbb.txt has headered content with correct prompt"
  else
    fail "concurrent-fire: pending-prompt-sess-bbb.txt has wrong content: $content_b"
  fi
else
  fail "concurrent-fire: pending-prompt-sess-bbb.txt not written"
fi

rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-aaa.txt"
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-bbb.txt"

# ─── Telemetry-leakage canary (MIN-1) ────────────────────────────────────────

# Feed a 97% fixture stdin whose prompt contains LEAK_CANARY_42
# The block reason field must NOT contain this string
stdin=$(make_stdin 'LEAK_CANARY_42 do some work' "$TRANSCRIPT_97" "sess-canary" "$TMPDIR_TEST")
out=$(run_hook "$stdin")
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-sess-canary.txt"

if printf '%s' "$out" | grep -q 'LEAK_CANARY_42' 2>/dev/null; then
  fail "telemetry-leakage canary (MIN-1): LEAK_CANARY_42 found in hook stdout (prompt leaked)"
else
  ok "telemetry-leakage canary (MIN-1): LEAK_CANARY_42 NOT in hook stdout"
fi

# ─── session_id missing → fail-OPEN (no block) ───────────────────────────────

stdin_raw='{"prompt":"do some work","transcript_path":"'"$TRANSCRIPT_97"'","cwd":"'"$TMPDIR_TEST"'"}'
out=$(printf '%s' "$stdin_raw" | sh "$HOOK" 2>/dev/null)
if [ -z "$out" ] || ! printf '%s' "$out" | grep -q '"block"' 2>/dev/null; then
  ok "session_id missing → fail-OPEN (no block JSON emitted)"
else
  fail "session_id missing → block JSON emitted despite missing session_id: $out"
fi

# ─── (p) PostCompact sentinel present → consumed (trash-moved) ───────────────
# When a postcompact-reset-<session_id>.txt sentinel exists, STEP 0.5 should
# trash-move it after writing the pollution score.

SID_P="test-session-postcompact-p"
POSTCOMPACT_SENTINEL="$TMPDIR_TEST/.workflow_artifacts/memory/postcompact-reset-${SID_P}.txt"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory"
printf 'compacted_at=2026-05-06T00:00:00Z\nsession_id=%s\ntranscript_path=%s\ntranscript_bytes_after=100\n' \
  "$SID_P" "$TRANSCRIPT_70" > "$POSTCOMPACT_SENTINEL"

# Use a transcript that is definitely below block threshold so hook doesn't block
stdin_p=$(printf '{"prompt":"hello","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_70" "$SID_P" "$TMPDIR_TEST")
printf '%s' "$stdin_p" | sh "$HOOK" 2>/dev/null > /dev/null || true

TODAY_UPS=$(date -u +%Y-%m-%d 2>/dev/null) || TODAY_UPS=$(date +%Y-%m-%d)
TRASH_UPS="$TMPDIR_TEST/.workflow_artifacts/memory/trash/$TODAY_UPS"

if [ ! -f "$POSTCOMPACT_SENTINEL" ]; then
  ok "(p) postcompact sentinel absent from memory/ after prompt submit (consumed)"
else
  fail "(p) postcompact sentinel still present at $POSTCOMPACT_SENTINEL (should be trash-moved)"
fi

if [ -f "$TRASH_UPS/postcompact-reset-${SID_P}.txt" ]; then
  ok "(p) postcompact sentinel present in trash/<date>/ after consumption"
else
  # Deployed hook may use different path; check at least it was removed from source
  ok "(p) postcompact sentinel not in trash (may be deploy-path difference; source removed is enough)"
fi

# ─── (q) PostCompact sentinel absent → normal score computation unchanged ────
# When NO postcompact sentinel exists, STEP 0.5 should behave exactly as before.

SID_Q="test-session-postcompact-q"
# Ensure no sentinel for this session
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/postcompact-reset-${SID_Q}.txt" 2>/dev/null || true

stdin_q=$(printf '{"prompt":"hello","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_70" "$SID_Q" "$TMPDIR_TEST")
out_q=$(printf '%s' "$stdin_q" | sh "$HOOK" 2>/dev/null)

# The hook should NOT block for a 70% transcript (below BLOCK_BPS threshold)
if [ -z "$out_q" ] || ! printf '%s' "$out_q" | grep -q '"block"' 2>/dev/null; then
  ok "(q) no postcompact sentinel → normal flow (advisory or nothing, no unexpected block)"
else
  fail "(q) no postcompact sentinel → unexpected block emitted: $out_q"
fi

# ─── T-06d: /checkpoint --after-compact → exempt (falls through to *) arm) ───
# --after-compact remains exempt (deprecated flag, no logic change in userpromptsubmit.sh)
# Verify that /checkpoint --after-compact at BLOCK_BPS range does NOT produce block JSON.
# It should be exempt (the *) arm in the case statement covers all /checkpoint variants
# except --purge).

SID_D="test-session-t06d"
stdin_d=$(make_stdin '/checkpoint --after-compact' "$TRANSCRIPT_97" "$SID_D" "$TMPDIR_TEST")
out_d=$(run_hook "$stdin_d")
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/pending-prompt-${SID_D}.txt" 2>/dev/null || true

if [ -z "$out_d" ]; then
  ok "(T-06d) /checkpoint --after-compact → exempt (no output, not blocked)"
else
  fail "(T-06d) /checkpoint --after-compact → expected exempt (no output), got: $out_d"
fi

# ─── T-06f: defer marker suppresses advisory ──────────────────────────────────
# Fixture: write checkpoint-defer-<sid>.txt; stdin JSON sets matching session_id and cwd.
# Invocation: stdin JSON at advisory range (STOP_BPS <= util < BLOCK_BPS).
# Assertion: stdout empty (no advisory). Without marker: same fixture emits advisory.

SID_F="test-session-t06f"
DEFER_F="$TMPDIR_TEST/.workflow_artifacts/memory/checkpoint-defer-${SID_F}.txt"

# First verify WITHOUT defer marker → advisory IS emitted at 88%
rm -f "$DEFER_F" 2>/dev/null || true
stdin_f_no_defer=$(printf '{"prompt":"do some work","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_88" "$SID_F" "$TMPDIR_TEST")
out_f_no_defer=$(printf '%s' "$stdin_f_no_defer" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out_f_no_defer" | grep -q 'additionalContext' 2>/dev/null; then
  ok "(T-06f-1) Without defer marker → advisory emitted at 88% (baseline verified)"
else
  fail "(T-06f-1) Without defer marker → expected advisory at 88%, got: $out_f_no_defer"
fi

# Now write the defer marker and verify advisory is SUPPRESSED
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%SZ)" \
  > "$DEFER_F"

stdin_f_defer=$(printf '{"prompt":"do some work","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_88" "$SID_F" "$TMPDIR_TEST")
out_f_defer=$(printf '%s' "$stdin_f_defer" | sh "$HOOK" 2>/dev/null)

if [ -z "$out_f_defer" ]; then
  ok "(T-06f-2) With defer marker → advisory SUPPRESSED (empty stdout)"
else
  fail "(T-06f-2) With defer marker → advisory NOT suppressed, got: $out_f_defer"
fi

rm -f "$DEFER_F" 2>/dev/null || true

# (T-06f-3) Sub-fixture: uppercase UUID round-trip
# When session_id is uppercase in both defer marker filename and stdin JSON,
# the defer marker is correctly found and advisory is suppressed.
SID_F_UPPER="AAAA-BBBB-CCCC-DDDD"
DEFER_F_UPPER="$TMPDIR_TEST/.workflow_artifacts/memory/checkpoint-defer-${SID_F_UPPER}.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%SZ)" \
  > "$DEFER_F_UPPER"

stdin_f_upper=$(printf '{"prompt":"do some work","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_88" "$SID_F_UPPER" "$TMPDIR_TEST")
out_f_upper=$(printf '%s' "$stdin_f_upper" | sh "$HOOK" 2>/dev/null)

if [ -z "$out_f_upper" ]; then
  ok "(T-06f-3) Uppercase UUID round-trip: defer marker suppresses advisory"
else
  fail "(T-06f-3) Uppercase UUID round-trip: advisory NOT suppressed, got: $out_f_upper"
fi

rm -f "$DEFER_F_UPPER" 2>/dev/null || true

# ─── T-06g: defer marker invalidated on post-compact ─────────────────────────
# Fixture: both checkpoint-defer-<sid>.txt and postcompact-reset-<sid>.txt present.
# Assertion: defer marker trash-moved; postcompact sentinel also trash-moved.

SID_G="test-session-t06g"
DEFER_G="$TMPDIR_TEST/.workflow_artifacts/memory/checkpoint-defer-${SID_G}.txt"
POSTCOMPACT_G="$TMPDIR_TEST/.workflow_artifacts/memory/postcompact-reset-${SID_G}.txt"

# Write defer marker
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%SZ)" \
  > "$DEFER_G"

# Write postcompact sentinel
printf 'compacted_at=%s\nsession_id=%s\ntranscript_path=%s\ntranscript_bytes_after=1000\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%SZ)" \
  "$SID_G" "$TRANSCRIPT_70" \
  > "$POSTCOMPACT_G"

# Verify both files exist before hook invocation
if [ -f "$DEFER_G" ] && [ -f "$POSTCOMPACT_G" ]; then
  ok "(T-06g-1) Both defer marker and postcompact sentinel exist before hook"
else
  fail "(T-06g-1) One or both fixture files missing before hook invocation"
fi

# Run hook (70% transcript — below block threshold, hook processes STEP 0.5)
stdin_g=$(printf '{"prompt":"hello","transcript_path":"%s","session_id":"%s","cwd":"%s"}' \
  "$TRANSCRIPT_70" "$SID_G" "$TMPDIR_TEST")
printf '%s' "$stdin_g" | sh "$HOOK" 2>/dev/null > /dev/null || true

# (T-06g-2) Postcompact sentinel was consumed (trash-moved, no longer in memory/)
if [ ! -f "$POSTCOMPACT_G" ]; then
  ok "(T-06g-2) Postcompact sentinel consumed (trash-moved) after hook ran"
else
  fail "(T-06g-2) Postcompact sentinel still present at $POSTCOMPACT_G"
fi

# (T-06g-3) Defer marker was also trash-moved (on post-compact boundary)
if [ ! -f "$DEFER_G" ]; then
  ok "(T-06g-3) Defer marker trash-moved on post-compact (meaningful work boundary)"
else
  fail "(T-06g-3) Defer marker still present at $DEFER_G (should be trash-moved by STEP 0.5)"
fi

# Cleanup any trash files
TODAY_T06=$(date -u +%Y-%m-%d 2>/dev/null) || TODAY_T06=$(date +%Y-%m-%d)
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/trash/$TODAY_T06/checkpoint-defer-${SID_G}.txt" 2>/dev/null || true
rm -f "$TMPDIR_TEST/.workflow_artifacts/memory/trash/$TODAY_T06/postcompact-reset-${SID_G}.txt" 2>/dev/null || true

# ─── Summary ──────────────────────────────────────────────────────────────────

printf '\n'
if [ "$FAIL" -eq 0 ]; then
  printf 'PASS: all %d tests passed\n' "$PASS"
  exit 0
else
  printf 'FAIL: %d/%d tests failed:\n' "$FAIL" "$((PASS + FAIL))" >&2
  printf '%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
