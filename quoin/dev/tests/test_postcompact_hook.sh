#!/bin/sh
# test_postcompact_hook.sh — fixture tests for quoin/hooks/postcompact.sh
#
# Covers T-09 acceptance criteria.
# Requires: jq on PATH, sh (POSIX).
#
# Usage: sh quoin/dev/tests/test_postcompact_hook.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../../hooks/postcompact.sh"
DEPLOYED_HOOK="$HOME/.claude/hooks/postcompact.sh"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_postcompact_$$"
MEMORY_DIR="$TMPDIR_TEST/.workflow_artifacts/memory"
mkdir -p "$MEMORY_DIR"

# Create a small dummy transcript file
TRANSCRIPT="$TMPDIR_TEST/dummy.jsonl"
printf '{"type":"message"}\n' > "$TRANSCRIPT"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

make_stdin() {
  session_id="${1:-test-session-pc}"
  cwd="${2:-$TMPDIR_TEST}"
  transcript="${3:-$TRANSCRIPT}"
  printf '{"session_id":"%s","cwd":"%s","transcript_path":"%s","hook_event_name":"PostCompact"}' \
    "$session_id" "$cwd" "$transcript"
}

# ─── (e) Shebang assertion ────────────────────────────────────────────────────

if head -1 "$HOOK" | grep -qE '^#!/bin/sh( |$)'; then
  ok "(e) shebang: source hook starts with #!/bin/sh"
else
  fail "(e) shebang: source hook does not start with #!/bin/sh"
fi

# ─── (a) Valid input → sentinel written ──────────────────────────────────────

SID="test-session-pc-a"
stdin=$(make_stdin "$SID" "$TMPDIR_TEST" "$TRANSCRIPT")
stdout=$(printf '%s' "$stdin" | sh "$HOOK" 2>/dev/null)

SENTINEL="$MEMORY_DIR/postcompact-reset-${SID}.txt"

if [ -f "$SENTINEL" ]; then
  ok "(a) valid input: sentinel written at correct path"
else
  fail "(a) valid input: sentinel NOT found at $SENTINEL"
fi

# ─── (b) Sentinel content fields ─────────────────────────────────────────────

if [ -f "$SENTINEL" ]; then
  if grep -q '^compacted_at=' "$SENTINEL"; then
    ok "(b) sentinel has compacted_at= field"
  else
    fail "(b) sentinel missing compacted_at= field"
  fi

  if grep -q '^session_id=' "$SENTINEL"; then
    ok "(b) sentinel has session_id= field"
  else
    fail "(b) sentinel missing session_id= field"
  fi

  if grep -q '^transcript_bytes_after=' "$SENTINEL"; then
    ok "(b) sentinel has transcript_bytes_after= field"
  else
    fail "(b) sentinel missing transcript_bytes_after= field"
  fi
fi

# (b2) compact-happened sentinel present
COMPACT_HAPPENED="${MEMORY_DIR}/compact-happened-${SID}.txt"
if [ -f "${COMPACT_HAPPENED}" ]; then
  ok "(b2) compact-happened sentinel written at correct path"
else
  fail "(b2) compact-happened sentinel NOT written (expected: ${COMPACT_HAPPENED})"
fi

# (b3) compact-happened sentinel has required fields
if [ -f "${COMPACT_HAPPENED}" ]; then
  if grep -q '^compacted_at=' "${COMPACT_HAPPENED}"; then
    ok "(b3) compact-happened sentinel has compacted_at field"
  else
    fail "(b3) compact-happened sentinel missing compacted_at field"
  fi

  if grep -q '^session_id=' "${COMPACT_HAPPENED}"; then
    ok "(b3) compact-happened sentinel has session_id field"
  else
    fail "(b3) compact-happened sentinel missing session_id field"
  fi
fi

# ─── (c) Hook exits 0 and produces no stdout ─────────────────────────────────

SID_C="test-session-pc-c"
stdin_c=$(make_stdin "$SID_C" "$TMPDIR_TEST" "$TRANSCRIPT")
stdout_c=$(printf '%s' "$stdin_c" | sh "$HOOK" 2>/dev/null)
exit_code=0
printf '%s' "$stdin_c" | sh "$HOOK" > /dev/null 2>/dev/null || exit_code=$?

if [ "$exit_code" -eq 0 ]; then
  ok "(c) hook exits 0"
else
  fail "(c) hook exited $exit_code (expected 0)"
fi

if [ -z "$stdout_c" ]; then
  ok "(c) hook produces no stdout"
else
  fail "(c) hook produced stdout: $stdout_c"
fi

# ─── (d) Missing session_id → fail-OPEN, no sentinel, exit 0 ─────────────────

stdin_d='{"cwd":"'"$TMPDIR_TEST"'","transcript_path":"'"$TRANSCRIPT"'","hook_event_name":"PostCompact"}'
exit_d=0
printf '%s' "$stdin_d" | sh "$HOOK" > /dev/null 2>/dev/null || exit_d=$?

if [ "$exit_d" -eq 0 ]; then
  ok "(d) missing session_id: hook exits 0 (fail-OPEN)"
else
  fail "(d) missing session_id: hook exited $exit_d (expected 0)"
fi

# No sentinel should be written when session_id is missing (empty glob = no files)
sentinel_count=$(find "$MEMORY_DIR" -name 'postcompact-reset-*.txt' -maxdepth 1 2>/dev/null | wc -l | awk '{print $1}')
# We already have sentinels from tests (a) and (c) — just check none has empty name
if find "$MEMORY_DIR" -name 'postcompact-reset-.txt' -maxdepth 1 2>/dev/null | grep -q .; then
  fail "(d) missing session_id: stray sentinel 'postcompact-reset-.txt' created"
else
  ok "(d) missing session_id: no sentinel with empty session_id created"
fi

# ─── deployed hook check (if present) ────────────────────────────────────────

if [ -f "$DEPLOYED_HOOK" ]; then
  if head -1 "$DEPLOYED_HOOK" | grep -qE '^#!/bin/sh( |$)'; then
    ok "shebang: deployed hook starts with #!/bin/sh"
  else
    fail "shebang: deployed hook does not start with #!/bin/sh"
  fi
fi

# ─── summary ─────────────────────────────────────────────────────────────────

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'Failures:%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
