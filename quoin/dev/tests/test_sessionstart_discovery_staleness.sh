#!/bin/sh
# test_sessionstart_discovery_staleness.sh — S-5 banner tests for IVG-106 T-02
#
# Covers acceptance criteria from T-02: stale/absent/fresh/disable/serena banner cases.
# Mirrors test_sessionstart_pending_restore.sh structure.
#
# Usage: sh quoin/dev/tests/test_sessionstart_discovery_staleness.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../../hooks/sessionstart.sh"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
clear_disc_sentinel() {
  # Remove the S-5 dedup sentinel so each test starts fresh
  rm -f "${TMPDIR:-/tmp}/quoin-s5-staleness-banner-$(date -u +%Y%m%d).tmp" 2>/dev/null || true
}
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_ss_disc_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/cache"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

CACHE_DIR="$TMPDIR_TEST/.workflow_artifacts/cache"
MEMORY_DIR="$TMPDIR_TEST/.workflow_artifacts/memory"

make_stdin() {
  local cwd="${1:-$TMPDIR_TEST}"
  printf '{"source":"startup","session_id":"test-disc-sess","cwd":"%s"}' "$cwd"
}

write_staleness_md() {
  # Write _staleness.md with Updated = N days ago (arg: days_ago)
  local days_ago="$1"
  # Compute timestamp N days ago using python3
  local ts
  ts=$(python3 -c "
from datetime import datetime, timezone, timedelta
now = datetime.now(tz=timezone.utc)
ago = now - timedelta(days=$days_ago)
print(ago.strftime('%Y-%m-%dT%H:%M:%SZ'))
" 2>/dev/null) || { ts="2020-01-01T00:00:00Z"; }
  printf '| Repo | HEAD | Updated |\n|------|------|--------|\n| repo | abc | %s |\n' "$ts" \
    > "$CACHE_DIR/_staleness.md"
}

# ─── (a) stale _staleness.md 10d old → banner with "quoin-S-5" and "stale" ──

clear_disc_sentinel
write_staleness_md 10
out=$(printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'quoin-S-5' 2>/dev/null; then
  ok "(a) stale discovery (10d) → S-5 banner emitted"
else
  fail "(a) stale discovery (10d) → expected S-5 banner, got: $out"
fi

if printf '%s' "$out" | grep -q 'stale\|may be stale' 2>/dev/null; then
  ok "(a) stale banner contains 'stale' text"
else
  fail "(a) stale banner missing 'stale' text: $out"
fi

rm -f "$CACHE_DIR/_staleness.md"

# ─── (b) fresh _staleness.md (1d) → NO S-5 banner ────────────────────────────

clear_disc_sentinel
write_staleness_md 1
out=$(printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'quoin-S-5' 2>/dev/null; then
  fail "(b) fresh discovery (1d) → S-5 banner should NOT appear, got: $out"
else
  ok "(b) fresh discovery (1d) → no S-5 banner (correct)"
fi

rm -f "$CACHE_DIR/_staleness.md"

# ─── (c) QUOIN_DISCOVERY_REFRESH_DISABLE=1 → NO banner ───────────────────────

clear_disc_sentinel
write_staleness_md 10
out=$(printf '%s' "$(make_stdin)" | QUOIN_DISCOVERY_REFRESH_DISABLE=1 sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'quoin-S-5' 2>/dev/null; then
  fail "(c) QUOIN_DISCOVERY_REFRESH_DISABLE=1 → banner should be suppressed, got: $out"
else
  ok "(c) QUOIN_DISCOVERY_REFRESH_DISABLE=1 → no S-5 banner (correct)"
fi

rm -f "$CACHE_DIR/_staleness.md"

# ─── (d) absent artifacts → banner contains "No discovery memory" ─────────────

clear_disc_sentinel
rm -f "$CACHE_DIR/_staleness.md" 2>/dev/null || true
out=$(printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'quoin-S-5' 2>/dev/null && \
   printf '%s' "$out" | grep -q 'No discovery memory' 2>/dev/null; then
  ok "(d) absent artifacts → S-5 banner with 'No discovery memory'"
else
  fail "(d) absent artifacts → expected S-5 'No discovery memory' banner, got: $out"
fi

# ─── (e) hook exit code always 0 ─────────────────────────────────────────────

clear_disc_sentinel
write_staleness_md 10
printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null
_hook_exit=$?
if [ "$_hook_exit" -eq 0 ]; then
  ok "(e) hook exit code is 0 (fail-OPEN)"
else
  fail "(e) hook exit code is not 0: $_hook_exit"
fi

rm -f "$CACHE_DIR/_staleness.md"

# ─── (f) serena-only-stale (marker present at 40d, discovery fresh 1d) ───────

clear_disc_sentinel
write_staleness_md 1
_marker="$MEMORY_DIR/serena-onboarded.md"
printf 'Serena onboarded.\n' > "$_marker"
# Backdate marker to 40 days ago
python3 -c "
import os, time
from datetime import datetime, timezone, timedelta
old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=40)).timestamp()
os.utime('$_marker', (old_ts, old_ts))
" 2>/dev/null || true

out=$(printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'quoin-S-5' 2>/dev/null && \
   printf '%s' "$out" | grep -q 'Serena project memory' 2>/dev/null; then
  ok "(f) serena-only-stale (marker 40d, discovery 1d) → S-5 Serena banner"
else
  fail "(f) serena-only-stale → expected S-5 Serena banner, got: $out"
fi

rm -f "$_marker" "$CACHE_DIR/_staleness.md"

# ─── (g) fresh discovery + absent serena marker → NO S-5 Serena banner ───────
# (Graceful Absence: absent marker does not trigger exit-12)

clear_disc_sentinel
write_staleness_md 1
# No serena-onboarded.md
out=$(printf '%s' "$(make_stdin)" | sh "$HOOK" 2>/dev/null)

if printf '%s' "$out" | grep -q 'Serena project memory' 2>/dev/null; then
  fail "(g) absent serena marker → S-5 Serena banner should NOT appear, got: $out"
else
  ok "(g) absent serena marker + fresh discovery → no S-5 Serena banner (Graceful Absence)"
fi

rm -f "$CACHE_DIR/_staleness.md"

# ─── sh syntax check ─────────────────────────────────────────────────────────

if sh -n "$HOOK" 2>/dev/null; then
  ok "sh -n syntax check passes"
else
  fail "sh -n syntax check failed on hook"
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
