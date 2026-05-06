#!/bin/sh
# test_trash_move.sh — unit tests for trash_move() in quoin/hooks/_lib.sh
#
# Covers T-10 acceptance criteria.
# Requires: sh (POSIX). No jq needed.
#
# Usage: sh quoin/dev/tests/test_trash_move.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../../hooks/_lib.sh"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_trash_move_$$"
BASE="$TMPDIR_TEST/base"
mkdir -p "$BASE"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

# Source the library
. "$LIB"

TODAY=$(date -u +%Y-%m-%d 2>/dev/null) || TODAY=$(date +%Y-%m-%d)
TRASH_TODAY="$BASE/trash/$TODAY"

# ─── (a) Basic move ───────────────────────────────────────────────────────────

printf 'hello\n' > "$BASE/test-a.txt"
trash_move "$BASE/test-a.txt" "$BASE"

if [ -f "$TRASH_TODAY/test-a.txt" ]; then
  ok "(a) basic move: file appears in trash/<date>/"
else
  fail "(a) basic move: file NOT found in trash/<date>/"
fi

if [ ! -f "$BASE/test-a.txt" ]; then
  ok "(a) basic move: file removed from source"
else
  fail "(a) basic move: file still at source after trash_move"
fi

# ─── (b) Collision suffix ─────────────────────────────────────────────────────

printf 'first\n' > "$BASE/test-b.txt"
trash_move "$BASE/test-b.txt" "$BASE"
# First copy landed as test-b.txt; now write another with same name
printf 'second\n' > "$BASE/test-b.txt"
trash_move "$BASE/test-b.txt" "$BASE"

if [ -f "$TRASH_TODAY/test-b.txt" ]; then
  ok "(b) collision: first file present as test-b.txt"
else
  fail "(b) collision: first file not found as test-b.txt"
fi

if [ -f "$TRASH_TODAY/test-b.txt-1" ]; then
  ok "(b) collision: second file present with -1 suffix"
else
  fail "(b) collision: second file NOT found as test-b.txt-1"
fi

# ─── (c) Source missing → warning + return 1 ─────────────────────────────────

stderr_c=$(trash_move "$BASE/nonexistent-xyz.txt" "$BASE" 2>&1) || true
exit_c=0
trash_move "$BASE/nonexistent-xyz.txt" "$BASE" 2>/dev/null || exit_c=$?

if [ "$exit_c" -ne 0 ]; then
  ok "(c) missing source: trash_move returns non-zero"
else
  fail "(c) missing source: trash_move returned 0 (expected non-zero)"
fi

if printf '%s' "$stderr_c" | grep -q 'quoin-trash'; then
  ok "(c) missing source: stderr warning emitted"
else
  fail "(c) missing source: no stderr warning found (got: $stderr_c)"
fi

# ─── (d) Trash dir already exists → idempotent ────────────────────────────────

mkdir -p "$TRASH_TODAY"  # pre-create
printf 'idempotent\n' > "$BASE/test-d.txt"
trash_move "$BASE/test-d.txt" "$BASE"

if [ -f "$TRASH_TODAY/test-d.txt" ]; then
  ok "(d) pre-existing trash dir: file moved successfully"
else
  fail "(d) pre-existing trash dir: file NOT found in trash"
fi

# ─── (e) Collision counter keeps incrementing ────────────────────────────────

printf 'v1\n' > "$BASE/test-e.txt"; trash_move "$BASE/test-e.txt" "$BASE"
printf 'v2\n' > "$BASE/test-e.txt"; trash_move "$BASE/test-e.txt" "$BASE"
printf 'v3\n' > "$BASE/test-e.txt"; trash_move "$BASE/test-e.txt" "$BASE"

# Should have test-e.txt, test-e.txt-1, test-e.txt-2
if [ -f "$TRASH_TODAY/test-e.txt" ] && \
   [ -f "$TRASH_TODAY/test-e.txt-1" ] && \
   [ -f "$TRASH_TODAY/test-e.txt-2" ]; then
  ok "(e) collision increments: test-e.txt, test-e.txt-1, test-e.txt-2 all present"
else
  fail "(e) collision increments: not all three copies found in trash"
fi

# ─── summary ─────────────────────────────────────────────────────────────────

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'Failures:%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
