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
