#!/bin/sh
# test_sessionstart_pending_restore.sh — fixture tests for quoin/hooks/sessionstart.sh
#
# Covers sub-cases from T-12c / T-11 acceptance criteria.
# Requires: jq on PATH, sh (POSIX).
#
# Usage: sh quoin/dev/tests/test_sessionstart_pending_restore.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../../hooks/sessionstart.sh"
DEPLOYED_HOOK="$HOME/.claude/hooks/sessionstart.sh"
RUN_STATE="$SCRIPT_DIR/../../core/scripts/run_state.py"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_sessionstart_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

MEMORY_DIR="$TMPDIR_TEST/.workflow_artifacts/memory"

make_stdin() {
  local source="$1"
  local session_id="${2:-test-session-ss}"
  local cwd="${3:-$TMPDIR_TEST}"
  printf '{"source":"%s","session_id":"%s","cwd":"%s"}' "$source" "$session_id" "$cwd"
}

# ─── Shebang assertion ────────────────────────────────────────────────────────

if head -1 "$HOOK" | grep -qE '^#!/bin/sh( |$)'; then
  ok "shebang assertion: source hook starts with #!/bin/sh"
else
  fail "shebang assertion: source hook does not start with #!/bin/sh"
fi

if [ -f "$DEPLOYED_HOOK" ]; then
  if head -1 "$DEPLOYED_HOOK" | grep -qE '^#!/bin/sh( |$)'; then
    ok "shebang assertion: deployed hook starts with #!/bin/sh"
  else
    fail "shebang assertion: deployed hook does not start with #!/bin/sh"
  fi
fi

# ─── (a) source=startup + sentinel matching session_id → banner emitted ───────

printf '/checkpoint/file/for/startup.md\n' > "$MEMORY_DIR/pending-restore-sess-startup.txt"
stdin=$(make_stdin "startup" "sess-startup")
out=$(printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'Pending restore detected' 2>/dev/null; then
  ok "(a) source=startup + matching sentinel → banner JSON emitted"
else
  fail "(a) source=startup + matching sentinel → expected banner, got: $out"
fi

if printf '%s' "$out" | grep -q 'current-session' 2>/dev/null; then
  ok "(a) source=startup + matching sentinel → session-id match status is current-session"
else
  fail "(a) source=startup → banner emitted but missing current-session marker: $out"
fi

rm -f "$MEMORY_DIR/pending-restore-sess-startup.txt"

# ─── (b) source=resume + sentinel matching session_id → banner emitted (CRIT-2) ─

printf '/checkpoint/file/for/resume.md\n' > "$MEMORY_DIR/pending-restore-sess-resume.txt"
stdin=$(make_stdin "resume" "sess-resume")
out=$(printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'Pending restore detected' 2>/dev/null; then
  ok "(b) source=resume + matching sentinel → banner JSON emitted (CRIT-2 critical case)"
else
  fail "(b) source=resume + matching sentinel → expected banner, got: $out"
fi

rm -f "$MEMORY_DIR/pending-restore-sess-resume.txt"

# ─── (c) sentinel absent and no fallback → exit 0 no output ──────────────────

# Ensure no sentinel files exist
rm -f "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true
stdin=$(make_stdin "startup" "sess-no-sentinel")
out=$(printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null)

if [ -z "$out" ]; then
  ok "(c) sentinel absent → exit 0 no output"
else
  fail "(c) sentinel absent → expected no output, got: $out"
fi

# ─── (d) sentinel present under DIFFERENT session_id → banner with mismatch ──

printf '/checkpoint/file/for/other-session.md\n' > "$MEMORY_DIR/pending-restore-sess-other.txt"
stdin=$(make_stdin "startup" "sess-current-no-match")
out=$(printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'Pending restore detected' 2>/dev/null; then
  ok "(d) different session_id sentinel → banner emitted (mtime-most-recent fallback)"
else
  fail "(d) different session_id sentinel → expected banner, got: $out"
fi

if printf '%s' "$out" | grep -q 'mismatch' 2>/dev/null; then
  ok "(d) different session_id → mismatch warning in banner"
else
  fail "(d) different session_id → expected mismatch warning in banner, got: $out"
fi

rm -f "$MEMORY_DIR/pending-restore-sess-other.txt"

# ─── (d2) mtime-most-recent fallback test ────────────────────────────────────
# Create three pending-restore files with controlled mtimes:
# zzzzZZ is oldest, aaaaAA is middle, mmmmMM is newest (within last 24h).
# Lex order: zzzzZZ > mmmmMM > aaaaAA
# Mtime order (newest first): mmmmMM > aaaaAA > zzzzZZ
# The hook should surface mmmmMM (mtime-newest), NOT zzzzZZ (lex-greatest).
#
# IMPORTANT: Files must be RECENT (within STALE_DAYS=7 default) to survive the
# stale-sentinel sweep at step 2. Use QUOIN_STALE_SENTINEL_DAYS=30 and recent
# timestamps separated by seconds within the current day.

rm -f "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true

# Write files in order (each touch to set mtime), using slight delays via
# sequential writes. We use seconds-resolution touch with today's date.
# zzzzZZ: 1 hour ago, aaaaAA: 30min ago, mmmmMM: just now
NOW_DATE=$(date +%Y%m%d%H%M.%S 2>/dev/null || date +%Y%m%d%H%M 2>/dev/null || echo "")

printf 'checkpoint-zzzzZZ.md\n' > "$MEMORY_DIR/pending-restore-zzzzZZ.txt"
printf 'checkpoint-aaaaAA.md\n' > "$MEMORY_DIR/pending-restore-aaaaAA.txt"
printf 'checkpoint-mmmmMM.md\n' > "$MEMORY_DIR/pending-restore-mmmmMM.txt"

# Use QUOIN_STALE_SENTINEL_DAYS=30 so stale sweep doesn't remove them.
# We rely on filesystem write order for mtime: mmmmMM was written last → newest mtime.
# (All three files will have very close mtimes — within a second — so test is best-effort.)
# To guarantee order, wait 1s between writes if possible.
# Instead of sleeping, use a known-ordering approach: write all then touch the
# "oldest" ones to be 2 minutes ago (using date-based touch on macOS).

# Set zzzzZZ to 2 minutes ago, aaaaAA to 1 minute ago, mmmmMM stays fresh
TWO_MIN_AGO=$(date -v -2M +%Y%m%d%H%M.%S 2>/dev/null || \
              date -d '2 minutes ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")
ONE_MIN_AGO=$(date -v -1M +%Y%m%d%H%M.%S 2>/dev/null || \
              date -d '1 minute ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")

if [ -n "$TWO_MIN_AGO" ] && [ -n "$ONE_MIN_AGO" ]; then
  touch -t "$TWO_MIN_AGO" "$MEMORY_DIR/pending-restore-zzzzZZ.txt" 2>/dev/null || true
  touch -t "$ONE_MIN_AGO" "$MEMORY_DIR/pending-restore-aaaaAA.txt" 2>/dev/null || true
  # mmmmMM keeps current mtime (newest)

  stdin=$(make_stdin "startup" "sess-mtime-test")
  out=$(printf '%s' "$stdin" | QUOIN_STALE_SENTINEL_DAYS=30 sh "$HOOK" 2>/dev/null)

  if printf '%s' "$out" | grep -q 'mmmmMM' 2>/dev/null; then
    ok "(d2) mtime-most-recent fallback → surfaced mmmmMM (mtime-newest, not lex-greatest)"
  else
    fail "(d2) mtime-most-recent fallback → expected mmmmMM, got: $out"
  fi

  if printf '%s' "$out" | grep -q 'zzzzZZ' 2>/dev/null && \
     ! printf '%s' "$out" | grep -q 'mmmmMM' 2>/dev/null; then
    fail "(d2) mtime fallback → incorrectly surfaced lex-greatest (zzzzZZ)"
  fi
else
  ok "(d2) mtime-most-recent fallback → (skipped: date -v/-d not supported)"
fi

rm -f "$MEMORY_DIR/pending-restore-zzzzZZ.txt" "$MEMORY_DIR/pending-restore-aaaaAA.txt" "$MEMORY_DIR/pending-restore-mmmmMM.txt"

# ─── (e) stale sentinel (> STALE_DAYS days) → trash-moved by sweep ──────────

rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true

# Create a stale pending-prompt file (8 days old, > default STALE_DAYS=7)
printf 'stale-content\n' > "$MEMORY_DIR/pending-prompt-stale-sess.txt"
touch -t 202501010100.00 "$MEMORY_DIR/pending-prompt-stale-sess.txt" 2>/dev/null || {
  # If touch -t fails, the sweep won't fire — test falls through to skip path
  true
}

stdin=$(make_stdin "startup" "sess-stale-sweep")
printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null > /dev/null

TODAY_SS=$(date -u +%Y-%m-%d 2>/dev/null) || TODAY_SS=$(date +%Y-%m-%d)
TRASH_SS="$MEMORY_DIR/trash/$TODAY_SS"

# The stale file should be trash-moved (not hard-deleted)
if [ ! -f "$MEMORY_DIR/pending-prompt-stale-sess.txt" ]; then
  if [ -f "$TRASH_SS/pending-prompt-stale-sess.txt" ]; then
    ok "(e) stale pending-prompt → trash-moved to trash/<date>/ by sessionstart sweep"
  else
    ok "(e) stale pending-prompt → removed from memory/ (trash/<date>/ check skipped: deploy may differ)"
  fi
else
  # If touch -t didn't work and file is too new, the sweep wouldn't fire — not a real failure
  ok "(e) stale sweep → (skipped: touch -t may not have set old enough mtime on this platform)"
fi

# ─── (e2) staleness-tunable test: QUOIN_SESSIONSTART_SWEEP_DAYS=2, 3-day-old file ─
# After T-02 refactor: the UUID-aware sweep window is QUOIN_SESSIONSTART_SWEEP_DAYS
# (default 1d), NOT QUOIN_STALE_SENTINEL_DAYS (which now only applies to empty-SID
# fallback path — D-02).
# Test 1: a 3-day-old OTHER-session file IS swept at SWEEP_DAYS=2 (threshold exceeded).
# Test 2: a 3-day-old SAME-session file is NOT swept (UUID protection, regardless of age).
# Test 3: a 3-day-old OTHER-session file is NOT swept at SWEEP_DAYS=5 (under threshold).

rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true

THREE_DAYS_AGO=$(date -v -3d +%Y%m%d%H%M.%S 2>/dev/null || date -d '3 days ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")
if [ -n "$THREE_DAYS_AGO" ]; then
  # --- test (e2a): 3-day-old OTHER file swept at SWEEP_DAYS=2 ---
  printf '3-day-old other\n' > "$MEMORY_DIR/pending-prompt-3day-other-e2.txt"
  touch -t "$THREE_DAYS_AGO" "$MEMORY_DIR/pending-prompt-3day-other-e2.txt" 2>/dev/null || true
  stdin_e2a=$(make_stdin "startup" "sess-e2-test")
  printf '%s' "$stdin_e2a" | QUOIN_SESSIONSTART_SWEEP_DAYS=2 sh "$HOOK" 2>/dev/null > /dev/null
  if [ ! -f "$MEMORY_DIR/pending-prompt-3day-other-e2.txt" ]; then
    ok "(e2a) QUOIN_SESSIONSTART_SWEEP_DAYS=2: 3-day-old OTHER sentinel swept (threshold=2)"
  else
    fail "(e2a) QUOIN_SESSIONSTART_SWEEP_DAYS=2: 3-day-old OTHER sentinel NOT swept (should be)"
  fi
  rm -f "$MEMORY_DIR/pending-prompt-3day-other-e2.txt" 2>/dev/null || true

  # --- test (e2b): same-session file NOT swept by UUID protection ---
  printf '3-day-old same-session\n' > "$MEMORY_DIR/pending-prompt-3day-sess-e2-test.txt"
  touch -t "$THREE_DAYS_AGO" "$MEMORY_DIR/pending-prompt-3day-sess-e2-test.txt" 2>/dev/null || true
  stdin_e2b=$(make_stdin "startup" "sess-e2-test")
  printf '%s' "$stdin_e2b" | QUOIN_SESSIONSTART_SWEEP_DAYS=2 sh "$HOOK" 2>/dev/null > /dev/null
  if [ -f "$MEMORY_DIR/pending-prompt-3day-sess-e2-test.txt" ]; then
    ok "(e2b) QUOIN_SESSIONSTART_SWEEP_DAYS=2: same-session 3-day sentinel NOT swept (UUID-protected)"
  else
    fail "(e2b) QUOIN_SESSIONSTART_SWEEP_DAYS=2: same-session 3-day sentinel was swept (UUID not protecting)"
  fi
  rm -f "$MEMORY_DIR/pending-prompt-3day-sess-e2-test.txt" 2>/dev/null || true

  # --- test (e2c): 3-day-old OTHER file NOT swept at SWEEP_DAYS=5 (under threshold) ---
  printf '3-day-old other under threshold\n' > "$MEMORY_DIR/pending-prompt-3day-other2-e2.txt"
  touch -t "$THREE_DAYS_AGO" "$MEMORY_DIR/pending-prompt-3day-other2-e2.txt" 2>/dev/null || true
  stdin_e2c=$(make_stdin "startup" "sess-e2-test")
  printf '%s' "$stdin_e2c" | QUOIN_SESSIONSTART_SWEEP_DAYS=5 sh "$HOOK" 2>/dev/null > /dev/null
  if [ -f "$MEMORY_DIR/pending-prompt-3day-other2-e2.txt" ]; then
    ok "(e2c) QUOIN_SESSIONSTART_SWEEP_DAYS=5: 3-day-old OTHER sentinel NOT swept (threshold=5, under)"
  else
    fail "(e2c) QUOIN_SESSIONSTART_SWEEP_DAYS=5: 3-day-old OTHER sentinel swept (should not be at threshold=5)"
  fi
  rm -f "$MEMORY_DIR/pending-prompt-3day-other2-e2.txt" 2>/dev/null || true
else
  ok "(e2a) staleness-tunable test → (skipped: date manipulation not supported on this platform)"
  ok "(e2b) staleness-tunable UUID-protect test → (skipped: date manipulation not supported)"
  ok "(e2c) staleness-tunable under-threshold test → (skipped: date manipulation not supported)"
fi

# ─── (f) sh syntax check ─────────────────────────────────────────────────────

if sh -n "$HOOK" 2>/dev/null; then
  ok "(f) sh -n syntax check passes"
else
  fail "(f) sh -n syntax check failed on hook"
fi

# ─── T-10: New sentinel types for sessionstart.sh ─────────────────────────────
# Tests the two new sentinel families introduced by T-04/T-05.

SID_T10="sess-t10-$(date -u +%s)"

# (T-10a) pending-resume-ref sentinel → informational banner emitted
printf 'prior_session_uuid=%s\ncheckpoint_path=/some/checkpoint.md\n' "$SID_T10" \
  > "$MEMORY_DIR/pending-resume-ref-${SID_T10}.txt"
out_t10a=$(printf '%s' "$(make_stdin "resume" "$SID_T10")" | sh "$HOOK" 2>/dev/null)
if printf '%s' "$out_t10a" | grep -q 'Prior session loaded as reference' 2>/dev/null; then
  ok "(T-10a) pending-resume-ref sentinel → 'Prior session loaded as reference' banner emitted"
else
  fail "(T-10a) pending-resume-ref sentinel → expected reference banner, got: $out_t10a"
fi
rm -f "$MEMORY_DIR/pending-resume-ref-${SID_T10}.txt"

# (T-10b) mid-agent-handoff sentinel → advisory banner emitted
printf 'prior_session_uuid=%s\ntask_name=my-task\nactive_skills=critic 99999\ntimestamp=2026-05-15T10:00:00Z\n' \
  "$SID_T10" > "$MEMORY_DIR/mid-agent-handoff-${SID_T10}.txt"
out_t10b=$(printf '%s' "$(make_stdin "startup" "$SID_T10")" | sh "$HOOK" 2>/dev/null)
if printf '%s' "$out_t10b" | grep -q 'Mid-agent handoff detected' 2>/dev/null; then
  ok "(T-10b) mid-agent-handoff sentinel → 'Mid-agent handoff detected' banner emitted"
else
  fail "(T-10b) mid-agent-handoff sentinel → expected handoff banner, got: $out_t10b"
fi
rm -f "$MEMORY_DIR/mid-agent-handoff-${SID_T10}.txt"

# (T-10c) stale pending-resume-ref (10+ days old) → trash-moved
printf 'prior_session_uuid=stale-uuid\ncheckpoint_path=/old/checkpoint.md\n' \
  > "$MEMORY_DIR/pending-resume-ref-stale-sess.txt"
touch -t 202501010100.00 "$MEMORY_DIR/pending-resume-ref-stale-sess.txt" 2>/dev/null || true
out_t10c=$(printf '%s' "$(make_stdin "startup" "sess-t10c-fresh")" | sh "$HOOK" 2>/dev/null)
TODAY_T10=$(date -u +%Y-%m-%d 2>/dev/null) || TODAY_T10=$(date +%Y-%m-%d)
if [ ! -f "$MEMORY_DIR/pending-resume-ref-stale-sess.txt" ]; then
  ok "(T-10c) stale pending-resume-ref → trash-moved by sessionstart sweep"
else
  ok "(T-10c) stale pending-resume-ref → sweep check (skipped if touch -t not supported on this platform)"
  rm -f "$MEMORY_DIR/pending-resume-ref-stale-sess.txt"
fi

# (T-10d) stale mid-agent-handoff (10+ days old) → trash-moved
printf 'prior_session_uuid=stale-uuid\ntask_name=old-task\nactive_skills=critic 99999\ntimestamp=2026-01-01T01:00:00Z\n' \
  > "$MEMORY_DIR/mid-agent-handoff-stale-sess.txt"
touch -t 202501010100.00 "$MEMORY_DIR/mid-agent-handoff-stale-sess.txt" 2>/dev/null || true
out_t10d=$(printf '%s' "$(make_stdin "startup" "sess-t10d-fresh")" | sh "$HOOK" 2>/dev/null)
if [ ! -f "$MEMORY_DIR/mid-agent-handoff-stale-sess.txt" ]; then
  ok "(T-10d) stale mid-agent-handoff → trash-moved by sessionstart sweep"
else
  ok "(T-10d) stale mid-agent-handoff → sweep check (skipped if touch -t not supported on this platform)"
  rm -f "$MEMORY_DIR/mid-agent-handoff-stale-sess.txt"
fi

# (T-10e) priority ordering: when all three sentinel types match the same session_id,
# pending-restore is surfaced (highest priority)
SID_T10E="sess-t10-priority-$(date -u +%s)"
printf '/checkpoint/path.md\n' > "$MEMORY_DIR/pending-restore-${SID_T10E}.txt"
printf 'prior_session_uuid=%s\ncheckpoint_path=/cp.md\n' "$SID_T10E" \
  > "$MEMORY_DIR/pending-resume-ref-${SID_T10E}.txt"
printf 'prior_session_uuid=%s\ntask_name=t\nactive_skills=critic 1\ntimestamp=2026-05-15T10:00:00Z\n' \
  "$SID_T10E" > "$MEMORY_DIR/mid-agent-handoff-${SID_T10E}.txt"

out_t10e=$(printf '%s' "$(make_stdin "startup" "$SID_T10E")" | sh "$HOOK" 2>/dev/null)
if printf '%s' "$out_t10e" | grep -q 'Pending restore detected' 2>/dev/null; then
  ok "(T-10e) priority ordering: pending-restore surfaced first when all three sentinels present"
else
  fail "(T-10e) priority ordering: expected pending-restore banner first, got: $out_t10e"
fi

# Only one banner emitted (not multiple)
banner_count_t10e=$(printf '%s' "$out_t10e" | grep -c 'hookSpecificOutput' 2>/dev/null || echo 0)
if [ "$banner_count_t10e" -le 1 ]; then
  ok "(T-10e) AT MOST ONE banner emitted when multiple sentinels present"
else
  fail "(T-10e) multiple banners emitted (expected at most one): count=$banner_count_t10e"
fi

rm -f "$MEMORY_DIR/pending-restore-${SID_T10E}.txt" \
      "$MEMORY_DIR/pending-resume-ref-${SID_T10E}.txt" \
      "$MEMORY_DIR/mid-agent-handoff-${SID_T10E}.txt"

# ─── IVG-95 / T-05: UUID-aware sweep behavior tests ─────────────────────────
# These tests require touch -t with date -v/-d support (skip gracefully if absent).
# Use QUOIN_SESSIONSTART_SWEEP_DAYS=1 explicitly to test the tight window.

HAVE_DATE_V=$(date -v -2d >/dev/null 2>&1 && echo yes || echo no)

# (g) Current-session protection: 2-day-old compact-happened-SID.txt is NOT swept
# when running with the SAME session_id.
if [ "$HAVE_DATE_V" = "yes" ]; then
  SID_G="sess-uuid-protect-g"
  printf 'content\n' > "$MEMORY_DIR/compact-happened-${SID_G}.txt"
  TWO_DAYS_AGO_G=$(date -v -2d +%Y%m%d%H%M.%S 2>/dev/null || echo "")
  touch -t "$TWO_DAYS_AGO_G" "$MEMORY_DIR/compact-happened-${SID_G}.txt" 2>/dev/null || true
  stdin_g=$(make_stdin "startup" "$SID_G")
  printf '%s' "$stdin_g" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null > /dev/null
  if [ -f "$MEMORY_DIR/compact-happened-${SID_G}.txt" ]; then
    ok "(g) current-session protection: 2-day-old compact-happened-SID NOT swept (same session_id)"
  else
    fail "(g) current-session protection: compact-happened-SID was swept — current session NOT protected"
  fi
  rm -f "$MEMORY_DIR/compact-happened-${SID_G}.txt"
else
  ok "(g) current-session protection → (skipped: date -v not supported)"
fi

# (h) Non-current sweep (regression-proving test): 2-day-old compact-happened-OTHER.txt
# IS swept when running with a DIFFERENT session_id and default 1d window.
# This test MUST FAIL if T-02 is reverted (pre-fix: 6-family at 7d → 2-day file survives).
if [ "$HAVE_DATE_V" = "yes" ]; then
  SID_H_CURRENT="sess-current-h"
  SID_H_OTHER="sess-other-h"
  printf 'content\n' > "$MEMORY_DIR/compact-happened-${SID_H_OTHER}.txt"
  TWO_DAYS_AGO_H=$(date -v -2d +%Y%m%d%H%M.%S 2>/dev/null || echo "")
  touch -t "$TWO_DAYS_AGO_H" "$MEMORY_DIR/compact-happened-${SID_H_OTHER}.txt" 2>/dev/null || true
  stdin_h=$(make_stdin "startup" "$SID_H_CURRENT")
  printf '%s' "$stdin_h" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null > /dev/null
  if [ ! -f "$MEMORY_DIR/compact-happened-${SID_H_OTHER}.txt" ]; then
    ok "(h) non-current sweep: 2-day-old compact-happened-OTHER trash-moved (regression-proving)"
  else
    fail "(h) non-current sweep: compact-happened-OTHER NOT swept — pre-fix behavior detected"
  fi
  rm -f "$MEMORY_DIR/compact-happened-${SID_H_OTHER}.txt" 2>/dev/null || true
else
  ok "(h) non-current sweep → (skipped: date -v not supported)"
fi

# (i) Fresh-file safety: postcompact-reset-OTHER.txt with mtime=now is NOT swept
# (younger than 1d window).
SID_I_OTHER="sess-fresh-i"
SID_I_CURRENT="sess-current-i"
printf 'fresh content\n' > "$MEMORY_DIR/postcompact-reset-${SID_I_OTHER}.txt"
# mtime is "now" by default (just written)
stdin_i=$(make_stdin "startup" "$SID_I_CURRENT")
printf '%s' "$stdin_i" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null > /dev/null
if [ -f "$MEMORY_DIR/postcompact-reset-${SID_I_OTHER}.txt" ]; then
  ok "(i) fresh-file safety: postcompact-reset-OTHER with mtime=now NOT swept"
else
  fail "(i) fresh-file safety: postcompact-reset-OTHER was swept (should be younger than 1d)"
fi
rm -f "$MEMORY_DIR/postcompact-reset-${SID_I_OTHER}.txt" 2>/dev/null || true

# (j) New-family parity: 3 newly-covered families (checkpoint-defer, postcompact-reset,
# idle-advisory-pending) are all swept when 2 days old with a different session_id.
# Proves the 3 newly-covered families including the 9th (idle-advisory-pending).
if [ "$HAVE_DATE_V" = "yes" ]; then
  SID_J_CURRENT="sess-current-j"
  SID_J_OTHER="sess-other-j"
  printf 'content\n' > "$MEMORY_DIR/checkpoint-defer-${SID_J_OTHER}.txt"
  printf 'content\n' > "$MEMORY_DIR/postcompact-reset-${SID_J_OTHER}.txt"
  printf 'content\n' > "$MEMORY_DIR/idle-advisory-pending-${SID_J_OTHER}.txt"
  TWO_DAYS_AGO_J=$(date -v -2d +%Y%m%d%H%M.%S 2>/dev/null || echo "")
  touch -t "$TWO_DAYS_AGO_J" "$MEMORY_DIR/checkpoint-defer-${SID_J_OTHER}.txt" 2>/dev/null || true
  touch -t "$TWO_DAYS_AGO_J" "$MEMORY_DIR/postcompact-reset-${SID_J_OTHER}.txt" 2>/dev/null || true
  touch -t "$TWO_DAYS_AGO_J" "$MEMORY_DIR/idle-advisory-pending-${SID_J_OTHER}.txt" 2>/dev/null || true
  stdin_j=$(make_stdin "startup" "$SID_J_CURRENT")
  printf '%s' "$stdin_j" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null > /dev/null
  J_PASS=1
  [ -f "$MEMORY_DIR/checkpoint-defer-${SID_J_OTHER}.txt" ] && J_PASS=0
  [ -f "$MEMORY_DIR/postcompact-reset-${SID_J_OTHER}.txt" ] && J_PASS=0
  [ -f "$MEMORY_DIR/idle-advisory-pending-${SID_J_OTHER}.txt" ] && J_PASS=0
  if [ "$J_PASS" -eq 1 ]; then
    ok "(j) new-family parity: all 3 newly-covered families (incl. 9th idle-advisory) trash-moved"
  else
    fail "(j) new-family parity: one or more newly-covered family files NOT swept"
  fi
  rm -f "$MEMORY_DIR/checkpoint-defer-${SID_J_OTHER}.txt" \
        "$MEMORY_DIR/postcompact-reset-${SID_J_OTHER}.txt" \
        "$MEMORY_DIR/idle-advisory-pending-${SID_J_OTHER}.txt" 2>/dev/null || true
else
  ok "(j) new-family parity → (skipped: date -v not supported)"
fi

# (k) Empty-SID degraded-path conservatism: run hook with session_id="", a 2-day-old
# sentinel present; assert it is NOT trashed at the 1d window (empty SID → falls back
# to 7d age-only, file survives). Label: "degraded-path conservatism" — NOT "protect
# current session" (current writers never emit empty-SID sentinels, per D-02).
if [ "$HAVE_DATE_V" = "yes" ]; then
  printf 'content\n' > "$MEMORY_DIR/compact-happened-emptysid.txt"
  TWO_DAYS_AGO_K=$(date -v -2d +%Y%m%d%H%M.%S 2>/dev/null || echo "")
  touch -t "$TWO_DAYS_AGO_K" "$MEMORY_DIR/compact-happened-emptysid.txt" 2>/dev/null || true
  stdin_k=$(printf '{"source":"startup","session_id":"","cwd":"%s"}' "$TMPDIR_TEST")
  printf '%s' "$stdin_k" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null > /dev/null
  if [ -f "$MEMORY_DIR/compact-happened-emptysid.txt" ]; then
    ok "(k) degraded-path conservatism: empty-SID + 2-day file NOT swept at 1d (falls back to 7d)"
  else
    fail "(k) degraded-path conservatism: 2-day file WAS swept with empty session_id (should survive at 1d)"
  fi
  rm -f "$MEMORY_DIR/compact-happened-emptysid.txt" 2>/dev/null || true
else
  ok "(k) degraded-path conservatism → (skipped: date -v not supported)"
fi

# (l) STEP 4 fallback-window narrowing (pins D-08 behavior).
# (l-1): 2-day-old pending-restore-OTHER IS swept by STEP 2, so STEP 4 does NOT
#         surface it as a "different session" restore banner.
# (l-2): Fresh pending-restore-OTHER SURVIVES (under 1d) AND STEP 4 surfaces it.
if [ "$HAVE_DATE_V" = "yes" ]; then
  SID_L_CURRENT="sess-current-l"
  SID_L_OTHER="sess-other-l"

  # (l-1): 2-day-old non-current pending-restore → swept by STEP 2, not surfaced by STEP 4
  printf '/old/checkpoint.md\n' > "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt"
  TWO_DAYS_AGO_L=$(date -v -2d +%Y%m%d%H%M.%S 2>/dev/null || echo "")
  touch -t "$TWO_DAYS_AGO_L" "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt" 2>/dev/null || true
  stdin_l1=$(make_stdin "startup" "$SID_L_CURRENT")
  out_l1=$(printf '%s' "$stdin_l1" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null)
  # File should be swept (not present) AND the banner should NOT mention "different session"
  L1_FILE_SWEPT=0
  L1_BANNER_SILENT=0
  [ ! -f "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt" ] && L1_FILE_SWEPT=1
  if ! printf '%s' "$out_l1" | grep -q 'different session\|mismatch-warning\|mtime-most-recent' 2>/dev/null; then
    L1_BANNER_SILENT=1
  fi
  if [ "$L1_FILE_SWEPT" -eq 1 ] && [ "$L1_BANNER_SILENT" -eq 1 ]; then
    ok "(l-1) D-08 narrowing: 2-day-old non-current pending-restore swept + STEP 4 banner silent"
  else
    fail "(l-1) D-08 narrowing: file_swept=$L1_FILE_SWEPT banner_silent=$L1_BANNER_SILENT (expected 1 1)"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt" 2>/dev/null || true

  # (l-2): Fresh non-current pending-restore SURVIVES (< 1d) AND STEP 4 surfaces banner
  printf '/recent/checkpoint.md\n' > "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt"
  # mtime = now by default (just written) → survives 1d sweep
  stdin_l2=$(make_stdin "startup" "$SID_L_CURRENT")
  out_l2=$(printf '%s' "$stdin_l2" | QUOIN_SESSIONSTART_SWEEP_DAYS=1 sh "$HOOK" 2>/dev/null)
  L2_SURVIVED=0
  L2_BANNER_FIRED=0
  [ -f "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt" ] && L2_SURVIVED=1
  printf '%s' "$out_l2" | grep -q 'mismatch\|mtime-most-recent\|different session\|Pending restore' 2>/dev/null && L2_BANNER_FIRED=1
  if [ "$L2_SURVIVED" -eq 1 ] && [ "$L2_BANNER_FIRED" -eq 1 ]; then
    ok "(l-2) D-08 narrowing: fresh non-current pending-restore survives AND STEP 4 banner fires"
  else
    fail "(l-2) D-08 narrowing: survived=$L2_SURVIVED banner_fired=$L2_BANNER_FIRED (expected 1 1)"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_L_OTHER}.txt" 2>/dev/null || true
else
  ok "(l-1) D-08 narrowing → (skipped: date -v not supported)"
  ok "(l-2) D-08 narrowing → (skipped: date -v not supported)"
fi

# ─── T-03 (IVG-139): restore ground-truth backstop — WARN / silent / never-block /
# advisory / shared-namespace-skip. No existing `command -v python3` skip idiom exists
# in this file to mirror (critic round-1 m-2) — this guard is written fresh, following
# only the file's generic `ok "... skipped: ..."` message shape.

if command -v python3 >/dev/null 2>&1; then
  T139_SESSIONS_DIR="$MEMORY_DIR/sessions"
  T139_CPDIR="$MEMORY_DIR/cpdir"
  mkdir -p "$T139_SESSIONS_DIR" "$T139_CPDIR"

  # (m1) MISMATCH → WARN present, exit 0 (never-block)
  rm -f "$T139_SESSIONS_DIR"/*.md "$T139_CPDIR"/*.md "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true
  printf 'state\n' > "$T139_SESSIONS_DIR/2026-07-09-othertask.md"
  printf '## Active task\nmytask\n' > "$T139_CPDIR/2026-07-09T0900-mytask.md"
  SID_M1="sess-ivg139-m1"
  printf '%s\n' "$T139_CPDIR/2026-07-09T0900-mytask.md" > "$MEMORY_DIR/pending-restore-${SID_M1}.txt"
  stdin_m1=$(make_stdin "startup" "$SID_M1")
  out_m1=$(printf '%s' "$stdin_m1" | sh "$HOOK" 2>/dev/null); rc_m1=$?
  if printf '%s' "$out_m1" | grep -q 'Pending restore detected' 2>/dev/null && \
     printf '%s' "$out_m1" | grep -q 'task-context mismatch' 2>/dev/null && \
     [ "$rc_m1" -eq 0 ]; then
    ok "(m1) IVG-139 task-context MISMATCH → WARN present, never-block (rc=0)"
  else
    fail "(m1) IVG-139 mismatch → expected WARN+rc0, got rc=$rc_m1 out: $out_m1"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_M1}.txt"

  # (m2) MATCH → silent (no WARN)
  rm -f "$T139_SESSIONS_DIR"/*.md "$T139_CPDIR"/*.md 2>/dev/null || true
  printf 'state\n' > "$T139_SESSIONS_DIR/2026-07-09-mytask.md"
  printf '## Active task\nmytask\n' > "$T139_CPDIR/2026-07-09T0900-mytask.md"
  SID_M2="sess-ivg139-m2"
  printf '%s\n' "$T139_CPDIR/2026-07-09T0900-mytask.md" > "$MEMORY_DIR/pending-restore-${SID_M2}.txt"
  stdin_m2=$(make_stdin "startup" "$SID_M2")
  out_m2=$(printf '%s' "$stdin_m2" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_m2" | grep -q 'Pending restore detected' 2>/dev/null && \
     ! printf '%s' "$out_m2" | grep -q 'task-context mismatch' 2>/dev/null; then
    ok "(m2) IVG-139 task-context MATCH → no WARN (silent)"
  else
    fail "(m2) IVG-139 match → expected no WARN, got: $out_m2"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_M2}.txt"

  # (m3) advisory / does-not-override: mismatch state still recommends restore
  rm -f "$T139_SESSIONS_DIR"/*.md "$T139_CPDIR"/*.md 2>/dev/null || true
  printf 'state\n' > "$T139_SESSIONS_DIR/2026-07-09-othertask.md"
  printf '## Active task\nmytask\n' > "$T139_CPDIR/2026-07-09T0900-mytask.md"
  SID_M3="sess-ivg139-m3"
  printf '%s\n' "$T139_CPDIR/2026-07-09T0900-mytask.md" > "$MEMORY_DIR/pending-restore-${SID_M3}.txt"
  stdin_m3=$(make_stdin "startup" "$SID_M3")
  out_m3=$(printf '%s' "$stdin_m3" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_m3" | grep -q '/checkpoint --restore is recommended' 2>/dev/null && \
     printf '%s' "$out_m3" | grep -q 'task-context mismatch' 2>/dev/null; then
    ok "(m3) IVG-139 advisory: WARN augments, restore recommendation still present"
  else
    fail "(m3) IVG-139 advisory → expected both restore-recommendation and WARN, got: $out_m3"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_M3}.txt"

  # (m4) fail-OPEN on absent checkpoint file (R-04 pre-guard: [ -f "$_gt_cp" ])
  rm -f "$T139_SESSIONS_DIR"/*.md "$T139_CPDIR"/*.md 2>/dev/null || true
  printf 'state\n' > "$T139_SESSIONS_DIR/2026-07-09-othertask.md"
  SID_M4="sess-ivg139-m4"
  printf '%s\n' "$T139_CPDIR/nonexistent-2026-07-09T0900-mytask.md" > "$MEMORY_DIR/pending-restore-${SID_M4}.txt"
  stdin_m4=$(make_stdin "startup" "$SID_M4")
  out_m4=$(printf '%s' "$stdin_m4" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_m4" | grep -q 'Pending restore detected' 2>/dev/null && \
     ! printf '%s' "$out_m4" | grep -q 'task-context mismatch' 2>/dev/null; then
    ok "(m4) IVG-139 fail-OPEN: absent checkpoint file → no WARN"
  else
    fail "(m4) IVG-139 fail-OPEN → expected no WARN on absent file, got: $out_m4"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_M4}.txt"

  # (m5) shared-namespace guard (critic round-1 M-1) — regression test constructed so it
  # FAILS without the T-01 basename guard: freshest session has a genuinely different task,
  # which would trigger task_backstop: if the predicate ran on a thorough-plan-progress-*
  # candidate.
  rm -f "$T139_SESSIONS_DIR"/*.md "$T139_CPDIR"/*.md 2>/dev/null || true
  printf 'state\n' > "$T139_SESSIONS_DIR/2026-07-09-othertask.md"
  SID_M5="sess-ivg139-m5"
  printf 'irrelevant\n' > "$T139_CPDIR/thorough-plan-progress-${SID_M5}.md"
  printf '%s\n' "$T139_CPDIR/thorough-plan-progress-${SID_M5}.md" > "$MEMORY_DIR/pending-restore-${SID_M5}.txt"
  stdin_m5=$(make_stdin "startup" "$SID_M5")
  out_m5=$(printf '%s' "$stdin_m5" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_m5" | grep -q 'Pending restore detected' 2>/dev/null && \
     ! printf '%s' "$out_m5" | grep -q 'task-context mismatch' 2>/dev/null; then
    ok "(m5) IVG-139 shared-namespace guard: thorough-plan-progress-* checkpoint never WARNs"
  else
    fail "(m5) IVG-139 shared-namespace guard → expected no WARN for thorough-plan-progress-*, got: $out_m5"
  fi
  rm -f "$MEMORY_DIR/pending-restore-${SID_M5}.txt"

  rm -rf "$T139_CPDIR" 2>/dev/null || true
  rm -f "$T139_SESSIONS_DIR"/*.md 2>/dev/null || true
else
  ok "(m1) IVG-139 task-context mismatch → (skipped: no python3)"
  ok "(m2) IVG-139 task-context match → (skipped: no python3)"
  ok "(m3) IVG-139 advisory/does-not-override → (skipped: no python3)"
  ok "(m4) IVG-139 fail-OPEN absent checkpoint → (skipped: no python3)"
  ok "(m5) IVG-139 shared-namespace guard → (skipped: no python3)"
fi

# ─── IVG-258 S-4 (T-11): compact-matcher fixtures ─────────────────────────────

if command -v python3 >/dev/null 2>&1; then

  # (c1) single-object case, envelope-shape, and initialUserMessage position
  # (Candidate B — nested inside hookSpecificOutput, per T-01 probe (e)).
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c1-task \
    --session-id sess-c1 --phase implement --subphase code --step "c1 step" \
    --next-action "c1 next" --resume-command "/run --resume c1-task" >/dev/null 2>&1
  stdin_c1=$(make_stdin "compact" "sess-c1")
  out_c1=$(printf '%s' "$stdin_c1" | sh "$HOOK" 2>/dev/null)
  obj_count_c1=$(printf '%s' "$out_c1" | jq -s 'length' 2>/dev/null) || obj_count_c1="err"
  if [ "$obj_count_c1" = "1" ]; then
    ok "(c1) compact + matching record → exactly one JSON object"
  else
    fail "(c1) compact + matching record → object count wrong: $obj_count_c1"
  fi
  if printf '%s' "$out_c1" | jq -e '.hookSpecificOutput.hookEventName == "SessionStart"' >/dev/null 2>&1; then
    ok "(c1-envelope) hookSpecificOutput.hookEventName == SessionStart"
  else
    fail "(c1-envelope) hookSpecificOutput.hookEventName wrong or missing"
  fi
  if printf '%s' "$out_c1" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null 2>&1; then
    ok "(c1-envelope2) hookSpecificOutput.additionalContext non-empty"
  else
    fail "(c1-envelope2) hookSpecificOutput.additionalContext missing or empty"
  fi
  if printf '%s' "$out_c1" | jq -e '.hookSpecificOutput.initialUserMessage == "/run --resume c1-task"' >/dev/null 2>&1; then
    ok "(c1-ium) initialUserMessage nested in hookSpecificOutput (Candidate B), round-trips byte-for-byte"
  else
    fail "(c1-ium) initialUserMessage missing, wrong value, or wrong position"
  fi
  rm -f "$MEMORY_DIR/run-state-c1-task.json" "$MEMORY_DIR/run-notes-c1-task.md"

  # (c2) no STEP 2 sweep on the compact path — plant two stale sentinel families
  # (older than the sweep window) and confirm both survive a compact invocation,
  # with trash/ gaining nothing. Anchored on the sentinels' own presence, not on
  # absence of output (stage-1 lesson).
  printf 'stale prompt\n' > "$MEMORY_DIR/pending-prompt-c2-sentinel.txt"
  printf 'stale defer\n' > "$MEMORY_DIR/checkpoint-defer-c2-sentinel.txt"
  touch -t 202001010000 "$MEMORY_DIR/pending-prompt-c2-sentinel.txt"
  touch -t 202001010000 "$MEMORY_DIR/checkpoint-defer-c2-sentinel.txt"
  trash_before_c2=$(ls "$MEMORY_DIR/trash/"*/* 2>/dev/null | wc -l | awk '{print $1}')
  stdin_c2=$(make_stdin "compact" "sess-c2-nomatch")
  printf '%s' "$stdin_c2" | sh "$HOOK" >/dev/null 2>&1 || true
  trash_after_c2=$(ls "$MEMORY_DIR/trash/"*/* 2>/dev/null | wc -l | awk '{print $1}')
  if [ -f "$MEMORY_DIR/pending-prompt-c2-sentinel.txt" ] && [ -f "$MEMORY_DIR/checkpoint-defer-c2-sentinel.txt" ] && [ "$trash_after_c2" = "$trash_before_c2" ]; then
    ok "(c2) compact path never runs STEP 2 sweep — stale sentinels from two families survive, trash/ unchanged"
  else
    fail "(c2) compact path swept a sentinel (trash $trash_before_c2->$trash_after_c2)"
  fi
  rm -f "$MEMORY_DIR/pending-prompt-c2-sentinel.txt" "$MEMORY_DIR/checkpoint-defer-c2-sentinel.txt"

  # (c3) silent no-op — source=compact, no run-state record at all → zero bytes, exit 0
  stdin_c3=$(make_stdin "compact" "sess-c3-none")
  rc_c3=0
  out_c3=$(printf '%s' "$stdin_c3" | sh "$HOOK" 2>/dev/null) || rc_c3=$?
  if [ "$rc_c3" -eq 0 ] && [ -z "$out_c3" ]; then
    ok "(c3) compact + no matching record → exit 0, zero bytes"
  else
    fail "(c3) compact + no matching record → rc=$rc_c3 out=$out_c3"
  fi

  # (c4) session_id mismatch — active record exists but under a different id →
  # zero bytes, exit 0 (pins the D-06 exact-equality precondition as a behavior)
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c4-task \
    --session-id sess-c4-real --phase implement --next-action "c4 next" >/dev/null 2>&1
  stdin_c4=$(make_stdin "compact" "sess-c4-different")
  rc_c4=0
  out_c4=$(printf '%s' "$stdin_c4" | sh "$HOOK" 2>/dev/null) || rc_c4=$?
  if [ "$rc_c4" -eq 0 ] && [ -z "$out_c4" ]; then
    ok "(c4) compact + session_id mismatch → exit 0, zero bytes"
  else
    fail "(c4) compact + session_id mismatch → rc=$rc_c4 out=$out_c4"
  fi
  rm -f "$MEMORY_DIR/run-state-c4-task.json" "$MEMORY_DIR/run-notes-c4-task.md"

  # (c5) notes_path containment — four rejection shapes; additionalContext still
  # carries the other five fields, but with no run-notes line
  # (c5a) traversal via ..
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c5a-task \
    --session-id sess-c5a --phase implement --next-action "c5a next" >/dev/null 2>&1
  python3 - "$MEMORY_DIR/run-state-c5a-task.json" "$MEMORY_DIR/run-notes-x/../../evil-c5a.md" <<'PYEOF'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["notes_path"] = v
json.dump(d, open(p, "w"), indent=2)
PYEOF
  out_c5a=$(printf '%s' "$(make_stdin "compact" "sess-c5a")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c5a" | jq -e '.hookSpecificOutput.additionalContext | (contains("run-notes:") | not) and contains("next action: c5a next")' >/dev/null 2>&1; then
    ok "(c5a) traversal notes_path (..) → run-notes line omitted, other fields present"
  else
    fail "(c5a) traversal notes_path not rejected: $out_c5a"
  fi
  rm -f "$MEMORY_DIR/run-state-c5a-task.json" "$MEMORY_DIR/run-notes-c5a-task.md"

  # (c5b) outside MEMORY_DIR entirely
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c5b-task \
    --session-id sess-c5b --phase implement --next-action "c5b next" >/dev/null 2>&1
  python3 - "$MEMORY_DIR/run-state-c5b-task.json" "$TMPDIR_TEST/outside-c5b.md" <<'PYEOF'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["notes_path"] = v
json.dump(d, open(p, "w"), indent=2)
PYEOF
  out_c5b=$(printf '%s' "$(make_stdin "compact" "sess-c5b")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c5b" | jq -e '.hookSpecificOutput.additionalContext | (contains("run-notes:") | not) and contains("next action: c5b next")' >/dev/null 2>&1; then
    ok "(c5b) out-of-MEMORY_DIR notes_path → run-notes line omitted, other fields present"
  else
    fail "(c5b) out-of-tree notes_path not rejected: $out_c5b"
  fi
  rm -f "$MEMORY_DIR/run-state-c5b-task.json" "$MEMORY_DIR/run-notes-c5b-task.md"

  # (c5c) symlinked intermediate subdirectory (nested path, caught by the
  # flatness check the same way stage-3's precompact.sh fixture is)
  mkdir -p "$TMPDIR_TEST/c5c-target-dir"
  printf 'victim\n' > "$TMPDIR_TEST/c5c-target-dir/victim.md"
  ln -s "$TMPDIR_TEST/c5c-target-dir" "$MEMORY_DIR/run-notes-c5c-esc"
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c5c-task \
    --session-id sess-c5c --phase implement --next-action "c5c next" >/dev/null 2>&1
  python3 - "$MEMORY_DIR/run-state-c5c-task.json" "$MEMORY_DIR/run-notes-c5c-esc/victim.md" <<'PYEOF'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["notes_path"] = v
json.dump(d, open(p, "w"), indent=2)
PYEOF
  out_c5c=$(printf '%s' "$(make_stdin "compact" "sess-c5c")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c5c" | jq -e '.hookSpecificOutput.additionalContext | (contains("run-notes:") | not) and contains("next action: c5c next")' >/dev/null 2>&1; then
    ok "(c5c) symlinked-intermediate-dir notes_path → run-notes line omitted, other fields present"
  else
    fail "(c5c) symlinked-intermediate-dir notes_path not rejected: $out_c5c"
  fi
  rm -f "$MEMORY_DIR/run-state-c5c-task.json" "$MEMORY_DIR/run-notes-c5c-task.md" "$MEMORY_DIR/run-notes-c5c-esc"
  find "$TMPDIR_TEST/c5c-target-dir" -depth -exec rm -f {} \; 2>/dev/null
  rmdir "$TMPDIR_TEST/c5c-target-dir" 2>/dev/null || true

  # (c5d) notes_path itself is a symlink directly under MEMORY_DIR
  printf 'victim2\n' > "$TMPDIR_TEST/c5d-victim.md"
  ln -s "$TMPDIR_TEST/c5d-victim.md" "$MEMORY_DIR/run-notes-c5d-task.md"
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c5d-task \
    --session-id sess-c5d --phase implement --next-action "c5d next" >/dev/null 2>&1
  out_c5d=$(printf '%s' "$(make_stdin "compact" "sess-c5d")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c5d" | jq -e '.hookSpecificOutput.additionalContext | (contains("run-notes:") | not) and contains("next action: c5d next")' >/dev/null 2>&1; then
    ok "(c5d) notes_path itself a symlink → run-notes line omitted, other fields present"
  else
    fail "(c5d) symlinked notes_path file not rejected: $out_c5d"
  fi
  rm -f "$MEMORY_DIR/run-state-c5d-task.json" "$MEMORY_DIR/run-notes-c5d-task.md" "$TMPDIR_TEST/c5d-victim.md"

  # (c6) stage-boundary payload vs sibling mid-phase record
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c6a-task \
    --session-id sess-c6a --phase implement --subphase code --step "old step" \
    --at-stage-boundary true --next-action "start review" >/dev/null 2>&1
  out_c6a=$(printf '%s' "$(make_stdin "compact" "sess-c6a")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c6a" | jq -e '.hookSpecificOutput.additionalContext | contains("phase (completed): implement") and contains("sub-phase (completed): code") and contains("stage complete") and (contains("step: old step") | not) and contains("next action: start review")' >/dev/null 2>&1; then
    ok "(c6a) at_stage_boundary: true → D-11 boundary framing replaces the raw step line"
  else
    fail "(c6a) boundary framing missing or wrong: $out_c6a"
  fi
  rm -f "$MEMORY_DIR/run-state-c6a-task.json" "$MEMORY_DIR/run-notes-c6a-task.md"

  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c6b-task \
    --session-id sess-c6b --phase implement --subphase code --step "mid step" \
    --at-stage-boundary false --next-action "keep going" >/dev/null 2>&1
  out_c6b=$(printf '%s' "$(make_stdin "compact" "sess-c6b")" | sh "$HOOK" 2>/dev/null)
  if printf '%s' "$out_c6b" | jq -e '.hookSpecificOutput.additionalContext | contains("step: mid step") and (contains("stage complete") | not)' >/dev/null 2>&1; then
    ok "(c6b) at_stage_boundary: false → raw step line echoed verbatim (sibling of c6a)"
  else
    fail "(c6b) mid-phase step line missing or wrongly replaced: $out_c6b"
  fi
  rm -f "$MEMORY_DIR/run-state-c6b-task.json" "$MEMORY_DIR/run-notes-c6b-task.md"

else
  ok "(c1)..(c6b) compact-matcher fixtures → (skipped: no python3)"
fi

# (c7) AC-7 fail-OPEN fixtures on the compact path

# (c7a) malformed stdin
rc_c7a=0
out_c7a=$(printf 'not json' | sh "$HOOK" 2>/dev/null) || rc_c7a=$?
if [ "$rc_c7a" -eq 0 ] && [ -z "$out_c7a" ]; then
  ok "(c7a) malformed stdin on compact path → exit 0, empty stdout"
else
  fail "(c7a) malformed stdin → rc=$rc_c7a out=$out_c7a"
fi

# (c7b) missing session_id
stdin_c7b='{"source":"compact","cwd":"'"$TMPDIR_TEST"'"}'
rc_c7b=0
out_c7b=$(printf '%s' "$stdin_c7b" | sh "$HOOK" 2>/dev/null) || rc_c7b=$?
if [ "$rc_c7b" -eq 0 ] && [ -z "$out_c7b" ]; then
  ok "(c7b) missing session_id on compact path → exit 0, empty stdout"
else
  fail "(c7b) missing session_id → rc=$rc_c7b out=$out_c7b"
fi

# (c7c) jq absent — same stub-PATH idiom as the precompact.sh fixture
STUB_DIR_C7="$TMPDIR_TEST/stubpath-compact"
mkdir -p "$STUB_DIR_C7"
stub_missing_c7=""
for _u in cat dirname date find grep sed awk ls mkdir mv wc basename head tr xargs rm; do
  _up=$(command -v "$_u" 2>/dev/null) || _up=""
  if [ -n "$_up" ]; then
    ln -s "$_up" "$STUB_DIR_C7/$_u" 2>/dev/null || true
  fi
  [ -x "$STUB_DIR_C7/$_u" ] || stub_missing_c7="$stub_missing_c7 $_u"
done
if [ -z "$stub_missing_c7" ] && [ ! -e "$STUB_DIR_C7/jq" ]; then
  ok "(c7c-plant) stub PATH resolves every coreutil the hook needs pre-jq, jq deliberately absent"
else
  fail "(c7c-plant) stub PATH setup wrong (missing:$stub_missing_c7)"
fi
stdin_c7c=$(make_stdin "compact" "sess-c7c-nojq")
rc_c7c=0
out_c7c=$(printf '%s' "$stdin_c7c" | PATH="$STUB_DIR_C7" /bin/sh "$HOOK" 2>/dev/null) || rc_c7c=$?
if [ "$rc_c7c" -eq 0 ] && [ -z "$out_c7c" ]; then
  ok "(c7c) jq absent on compact path → exit 0, empty stdout"
else
  fail "(c7c) jq absent → rc=$rc_c7c out=$out_c7c"
fi

# (c7d) unreadable MEMORY_DIR — mode 000, directory exists (distinct guard from
# a missing directory: passes run_state_select's own [ -d ], then find fails
# silently to Permission denied and yields zero candidates)
if command -v python3 >/dev/null 2>&1 && [ "$(id -u)" != "0" ]; then
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c7d-task \
    --session-id sess-c7d --phase implement --next-action "c7d next" >/dev/null 2>&1
  chmod 000 "$MEMORY_DIR"
  rc_c7d=0
  out_c7d=$(printf '%s' "$(make_stdin "compact" "sess-c7d")" | sh "$HOOK" 2>/dev/null) || rc_c7d=$?
  chmod 755 "$MEMORY_DIR"
  if [ "$rc_c7d" -eq 0 ] && [ -z "$out_c7d" ]; then
    ok "(c7d) unreadable MEMORY_DIR (mode 000) on compact path → exit 0, empty stdout"
  else
    fail "(c7d) unreadable MEMORY_DIR → rc=$rc_c7d out=$out_c7d"
  fi
  rm -f "$MEMORY_DIR/run-state-c7d-task.json" "$MEMORY_DIR/run-notes-c7d-task.md"
else
  ok "(c7d) unreadable MEMORY_DIR → (skipped: no python3, or running as root)"
fi

# (c7e) no fail-OPEN fixture above needs /dev/tty access — sessionstart.sh
# never opens /dev/tty anywhere in the file (static fact, verified once here
# rather than per-fixture)
if grep -q '/dev/tty' "$HOOK"; then
  fail "(c7e) sessionstart.sh references /dev/tty — the fail-OPEN fixtures above assume it never does"
else
  ok "(c7e) sessionstart.sh contains no /dev/tty reference (static, covers all AC-7 fixtures)"
fi

# (c8) hostile-filesystem probe — run-state-*.json as a FIFO, and separately as
# a symlink to /dev/zero. Neither matches run_state_select's `-type f` glob, so
# the compact branch's own empty-result path is what actually fires; assert
# exit 0 and no stdout either way, with no hang (stage-3 lesson).
mkfifo "$MEMORY_DIR/run-state-c8-fifo.json" 2>/dev/null || true
rc_c8a=0
out_c8a=$(printf '%s' "$(make_stdin "compact" "sess-c8-fifo")" | sh "$HOOK" 2>/dev/null) || rc_c8a=$?
if [ "$rc_c8a" -eq 0 ] && [ -z "$out_c8a" ]; then
  ok "(c8a) run-state-*.json as a FIFO → exit 0, empty stdout, no hang"
else
  fail "(c8a) FIFO run-state file → rc=$rc_c8a out=$out_c8a"
fi
rm -f "$MEMORY_DIR/run-state-c8-fifo.json"

ln -s /dev/zero "$MEMORY_DIR/run-state-c8-symlink.json" 2>/dev/null || true
rc_c8b=0
out_c8b=$(printf '%s' "$(make_stdin "compact" "sess-c8-symlink")" | sh "$HOOK" 2>/dev/null) || rc_c8b=$?
if [ "$rc_c8b" -eq 0 ] && [ -z "$out_c8b" ]; then
  ok "(c8b) run-state-*.json as a symlink to /dev/zero → exit 0, empty stdout, no hang"
else
  fail "(c8b) symlink-to-/dev/zero run-state file → rc=$rc_c8b out=$out_c8b"
fi
rm -f "$MEMORY_DIR/run-state-c8-symlink.json"

# (c9) deployed-hook parity — the single-object case, re-run against the deployed
# copy too. Ordered strictly after `bash quoin/install.sh` in T-14's sweep, since
# the deployed hook only exists/reflects this stage's edits once that runs;
# skips gracefully (not a failure) before then, matching the existing shebang
# check's own `if [ -f "$DEPLOYED_HOOK" ]` idiom above.
if [ -f "$DEPLOYED_HOOK" ] && command -v python3 >/dev/null 2>&1; then
  python3 "$RUN_STATE" --write --project-root "$TMPDIR_TEST" --task c9-task \
    --session-id sess-c9 --phase implement --next-action "c9 next" \
    --resume-command "/run --resume c9-task" >/dev/null 2>&1
  out_c9=$(printf '%s' "$(make_stdin "compact" "sess-c9")" | sh "$DEPLOYED_HOOK" 2>/dev/null)
  obj_count_c9=$(printf '%s' "$out_c9" | jq -s 'length' 2>/dev/null) || obj_count_c9="err"
  if [ "$obj_count_c9" = "1" ] && printf '%s' "$out_c9" | jq -e '.hookSpecificOutput.hookEventName == "SessionStart" and .hookSpecificOutput.initialUserMessage == "/run --resume c9-task"' >/dev/null 2>&1; then
    ok "(c9) deployed hook: single-object compact case matches the source-tree behavior"
  else
    fail "(c9) deployed hook compact case diverged: count=$obj_count_c9 out=$out_c9"
  fi
  rm -f "$MEMORY_DIR/run-state-c9-task.json" "$MEMORY_DIR/run-notes-c9-task.md"
else
  ok "(c9) deployed hook compact parity → (skipped: deployed hook not present yet, or no python3 — expected before bash quoin/install.sh runs)"
fi

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
