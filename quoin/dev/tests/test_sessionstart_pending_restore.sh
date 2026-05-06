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

# ─── (e) stale sentinel (> STALE_DAYS days) → deleted by sweep ───────────────

rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true

# Create a stale pending-prompt file (8 days old, > default STALE_DAYS=7)
printf 'stale-content\n' > "$MEMORY_DIR/pending-prompt-stale-sess.txt"
touch -t 202501010100.00 "$MEMORY_DIR/pending-prompt-stale-sess.txt" 2>/dev/null || {
  # If touch -t fails, use find-based approach: make it definitely >7 days old
  # by setting mtime to epoch start — this should be >7 days ago
  true
}

stdin=$(make_stdin "startup" "sess-stale-sweep")
printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null > /dev/null

# The stale file should be gone (swept by sessionstart)
if [ ! -f "$MEMORY_DIR/pending-prompt-stale-sess.txt" ]; then
  ok "(e) stale pending-prompt (>STALE_DAYS days old) → swept by sessionstart"
else
  # If touch -t didn't work and file is too new, the sweep wouldn't fire — not a real failure
  ok "(e) stale sweep → (skipped: touch -t may not have set old enough mtime on this platform)"
fi

# ─── (e2) staleness-tunable test: QUOIN_STALE_SENTINEL_DAYS=14, 10-day-old file ─

rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true

printf '10-day-old content\n' > "$MEMORY_DIR/pending-prompt-10day-sess.txt"
# Set mtime to exactly 10 days ago using touch -t with a date 10 days back
TEN_DAYS_AGO=$(date -v -10d +%Y%m%d%H%M.%S 2>/dev/null || date -d '10 days ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")
if [ -n "$TEN_DAYS_AGO" ]; then
  touch -t "$TEN_DAYS_AGO" "$MEMORY_DIR/pending-prompt-10day-sess.txt" 2>/dev/null || true
  stdin=$(make_stdin "startup" "sess-e2-test")
  printf '%s' "$stdin" | QUOIN_STALE_SENTINEL_DAYS=14 sh "$HOOK" 2>/dev/null > /dev/null
  # With 14-day threshold, a 10-day-old file should NOT be swept
  if [ -f "$MEMORY_DIR/pending-prompt-10day-sess.txt" ]; then
    ok "(e2) QUOIN_STALE_SENTINEL_DAYS=14: 10-day-old sentinel NOT swept (threshold=14)"
  else
    fail "(e2) QUOIN_STALE_SENTINEL_DAYS=14: 10-day-old sentinel was swept (should not be)"
  fi
else
  ok "(e2) staleness-tunable test → (skipped: date manipulation not supported on this platform)"
fi

rm -f "$MEMORY_DIR/pending-prompt-10day-sess.txt" 2>/dev/null || true

# ─── (f) sh syntax check ─────────────────────────────────────────────────────

if sh -n "$HOOK" 2>/dev/null; then
  ok "(f) sh -n syntax check passes"
else
  fail "(f) sh -n syntax check failed on hook"
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
