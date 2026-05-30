#!/bin/sh
# test_recent_sessions_hook.sh — Shell tests for STEP 0.7/0.9 in userpromptsubmit.sh
# and STEP 1b in precompact.sh.
#
# Usage: sh quoin/dev/tests/test_recent_sessions_hook.sh
# Returns 0 on success, non-zero on failure.
#
# Requires: jq, python3, sh
# Note: these tests exercise the deployed hook at ~/.claude/hooks/userpromptsubmit.sh
# and ~/.claude/hooks/precompact.sh. Run after 'bash install.sh' to ensure latest
# versions are deployed.

PASS=0
FAIL=0
HOOK_UPS="$HOME/.claude/hooks/userpromptsubmit.sh"
HOOK_PRE="$HOME/.claude/hooks/precompact.sh"

# ── Helper ────────────────────────────────────────────────────────────────────

pass() { printf 'PASS: %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf 'FAIL: %s\n' "$1"; FAIL=$((FAIL + 1)); }

require_hook() {
    if [ ! -f "$1" ]; then
        printf 'SKIP: hook not found at %s (run bash install.sh first)\n' "$1"
        exit 0
    fi
}

# ── Setup: verify hooks exist ─────────────────────────────────────────────────

require_hook "$HOOK_UPS"
require_hook "$HOOK_PRE"

# ── Test 1: Single prompt → recent-sessions.md created with one line ──────────

TMP1=$(mktemp -d)
trap 'rm -rf "$TMP1"' EXIT

printf '{"session_id":"test-uuid-t1","cwd":"%s","transcript_path":"/dev/null","prompt":"hello"}' \
    "$TMP1" | sh "$HOOK_UPS" 2>/dev/null

RS1="${TMP1}/.workflow_artifacts/memory/recent-sessions.md"
if [ -f "$RS1" ]; then
    line_count=$(wc -l < "$RS1" | tr -d ' ')
    if [ "$line_count" -ge 1 ]; then
        if grep -q "test-uuid-t1" "$RS1" 2>/dev/null; then
            pass "Test 1: recent-sessions.md created with correct session_id"
        else
            fail "Test 1: session_id not in recent-sessions.md"
        fi
    else
        fail "Test 1: recent-sessions.md is empty"
    fi
else
    fail "Test 1: recent-sessions.md not created"
fi

# ── Test 2: Second prompt same session, timestamps close → no advisory file ───

TMP2=$(mktemp -d)
mkdir -p "${TMP2}/.workflow_artifacts/memory"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || NOW=$(date +%Y-%m-%dT%H:%M:%SZ)
printf '%s | test-uuid-t2\n' "$NOW" > "${TMP2}/.workflow_artifacts/memory/recent-sessions.md"

printf '{"session_id":"test-uuid-t2","cwd":"%s","transcript_path":"/dev/null","prompt":"hello again"}' \
    "$TMP2" | sh "$HOOK_UPS" 2>/dev/null

if [ -f "${TMP2}/.workflow_artifacts/memory/idle-advisory-pending-test-uuid-t2.txt" ]; then
    fail "Test 2: idle advisory flag created for non-idle session"
else
    pass "Test 2: no idle advisory for session with recent activity"
fi

# ── Test 3: Prompt with old entry for same session (>1h ago) → advisory emitted
# Note: STEP 0.7 writes the idle flag and STEP 0.9 immediately consumes+deletes it
# in the same hook invocation, so we check stdout for the advisory JSON instead.

TMP3=$(mktemp -d)
mkdir -p "${TMP3}/.workflow_artifacts/memory"
# Write an entry with a timestamp far in the past (guaranteed >1h ago)
OLD_TS="2000-01-01T00:00:00Z"
printf '%s | test-uuid-t3\n' "$OLD_TS" > "${TMP3}/.workflow_artifacts/memory/recent-sessions.md"

OUT3=$(printf '{"session_id":"test-uuid-t3","cwd":"%s","transcript_path":"/dev/null","prompt":"hello"}' \
    "$TMP3" | sh "$HOOK_UPS" 2>/dev/null)
if printf '%s' "$OUT3" | grep -q "quoin-idle"; then
    pass "Test 3: idle advisory emitted for session idle >1h"
else
    fail "Test 3: idle advisory NOT emitted for session idle >1h"
fi

# ── Test 4: Missing session_id → no file written, no advisory (fail-open) ─────

TMP4=$(mktemp -d)
printf '{"cwd":"%s","transcript_path":"/dev/null","prompt":"hello"}' \
    "$TMP4" | sh "$HOOK_UPS" 2>/dev/null

RS4="${TMP4}/.workflow_artifacts/memory/recent-sessions.md"
if [ -f "$RS4" ]; then
    fail "Test 4: recent-sessions.md created when session_id missing"
else
    pass "Test 4: no file created when session_id absent (fail-open)"
fi

# ── Test 5: Precompact hook → one line appended to recent-sessions.md ─────────

TMP5=$(mktemp -d)
printf '{"trigger":"auto","session_id":"pre-uuid-t5","cwd":"%s","transcript_path":"/dev/null"}' \
    "$TMP5" | sh "$HOOK_PRE" 2>/dev/null

RS5="${TMP5}/.workflow_artifacts/memory/recent-sessions.md"
if [ -f "$RS5" ]; then
    if grep -q "pre-uuid-t5" "$RS5" 2>/dev/null; then
        pass "Test 5: precompact hook appended session_id to recent-sessions.md"
    else
        fail "Test 5: session_id not found in recent-sessions.md after precompact"
    fi
else
    fail "Test 5: recent-sessions.md not created by precompact hook"
fi

# ── Test 6: Different session_id already in file → new entry appended correctly

TMP6=$(mktemp -d)
mkdir -p "${TMP6}/.workflow_artifacts/memory"
printf '2026-01-01T00:00:00Z | other-uuid-existing\n' > "${TMP6}/.workflow_artifacts/memory/recent-sessions.md"

printf '{"session_id":"new-uuid-t6","cwd":"%s","transcript_path":"/dev/null","prompt":"hi"}' \
    "$TMP6" | sh "$HOOK_UPS" 2>/dev/null

RS6="${TMP6}/.workflow_artifacts/memory/recent-sessions.md"
if grep -q "other-uuid-existing" "$RS6" 2>/dev/null && grep -q "new-uuid-t6" "$RS6" 2>/dev/null; then
    pass "Test 6: both existing and new session_id present in recent-sessions.md"
else
    fail "Test 6: recent-sessions.md does not contain both entries"
fi

# ── Summary ───────────────────────────────────────────────────────────────────

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
