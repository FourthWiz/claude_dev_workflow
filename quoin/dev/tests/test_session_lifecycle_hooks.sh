#!/bin/sh
# test_session_lifecycle_hooks.sh — S-4 lifecycle hook tests
# Tests are static (grep/fixture-based) plus limited subprocess calls.
# Run from project root: bash quoin/dev/tests/test_session_lifecycle_hooks.sh
# All tests exit 0 on PASS, emit "FAIL: <reason>" and set FAIL counter.

PASS=0; FAIL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/../../hooks"

pass() { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

# ── Shared: temp dir cleanup ──────────────────────────────────────────────────
# Each test creates its own mktemp dir; traps are test-local.

# ── Test 1: stale session file → no EOD banner ────────────────────────────────
echo ""
echo "Test 1: stale session file → no EOD banner"
T1_DIR=$(mktemp -d)
trap 'rm -rf "$T1_DIR"' EXIT
mkdir -p "$T1_DIR/.workflow_artifacts/memory/sessions"
STALE_FILE="$T1_DIR/.workflow_artifacts/memory/sessions/2026-04-01-some-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$STALE_FILE"
if touch -t 202504010000 "$STALE_FILE" 2>/dev/null; then
  STDIN_JSON=$(printf '{"cwd": "%s", "session_id": "test-session-123", "source": "startup"}' "$T1_DIR")
  OUTPUT=$(printf '%s' "$STDIN_JSON" | sh "$HOOKS_DIR/sessionstart.sh" 2>/dev/null)
  if printf '%s' "$OUTPUT" | grep -q 'quoin-S-4'; then
    fail "Test 1 — stale file triggered banner (should not)"
  else
    pass "Test 1 — stale file: no banner emitted"
  fi
else
  echo "SKIP: Test 1 — touch -t not available on this platform; stale-file test cannot run"
  PASS=$((PASS+1))
fi
trap - EXIT
rm -rf "$T1_DIR"

# ── Test 2: recent session with end_of_day_due: yes → banner emitted ──────────
echo ""
echo "Test 2: recent session with end_of_day_due: yes → banner emitted"
T2_DIR=$(mktemp -d)
mkdir -p "$T2_DIR/.workflow_artifacts/memory/sessions"
# Fresh session file (mtime = now)
SESSION_FILE2="$T2_DIR/.workflow_artifacts/memory/sessions/2026-05-04-my-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$SESSION_FILE2"

# Clean up any existing sentinel from prior runs to ensure banner can fire
TODAY=$(date -u +%Y%m%d)
SENTINEL_PATH="${TMPDIR:-/tmp}/quoin-s4-eod-banner-${TODAY}.tmp"
rm -f "$SENTINEL_PATH" 2>/dev/null || true

STDIN_JSON=$(printf '{"cwd": "%s", "session_id": "test-session-123", "source": "startup"}' "$T2_DIR")
OUTPUT2=$(printf '%s' "$STDIN_JSON" | sh "$HOOKS_DIR/sessionstart.sh" 2>/dev/null)
if printf '%s' "$OUTPUT2" | grep -q 'quoin-S-4'; then
  if printf '%s' "$OUTPUT2" | grep -q 'my-task'; then
    pass "Test 2 — recent session: banner emitted with task name"
  else
    fail "Test 2 — banner emitted but task name 'my-task' not found in output"
  fi
else
  fail "Test 2 — recent session with end_of_day_due: yes did not trigger banner"
fi
# Clean up sentinel and temp dir
rm -f "$SENTINEL_PATH" 2>/dev/null || true
rm -rf "$T2_DIR"

# ── Test 3: recent session with end_of_day_due: no → no banner ───────────────
echo ""
echo "Test 3: recent session with end_of_day_due: no → no banner"
T3_DIR=$(mktemp -d)
mkdir -p "$T3_DIR/.workflow_artifacts/memory/sessions"
SESSION_FILE3="$T3_DIR/.workflow_artifacts/memory/sessions/2026-05-04-other-task.md"
printf '## Cost\nend_of_day_due: no\n' > "$SESSION_FILE3"

# Ensure sentinel is absent
rm -f "$SENTINEL_PATH" 2>/dev/null || true

STDIN_JSON3=$(printf '{"cwd": "%s", "session_id": "test-session-456", "source": "startup"}' "$T3_DIR")
OUTPUT3=$(printf '%s' "$STDIN_JSON3" | sh "$HOOKS_DIR/sessionstart.sh" 2>/dev/null)
if printf '%s' "$OUTPUT3" | grep -q 'quoin-S-4'; then
  fail "Test 3 — end_of_day_due: no still triggered banner"
else
  pass "Test 3 — end_of_day_due: no: no banner emitted"
fi
rm -rf "$T3_DIR"

# ── Test 4: dedup window — second run within 5 min → banner fires only once ──
echo ""
echo "Test 4: dedup window — second sessionstart within 5 min → banner fires only once"
T4_DIR=$(mktemp -d)
mkdir -p "$T4_DIR/.workflow_artifacts/memory/sessions"
SESSION_FILE4="$T4_DIR/.workflow_artifacts/memory/sessions/2026-05-04-dedup-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$SESSION_FILE4"

# Clean up sentinel before test
rm -f "$SENTINEL_PATH" 2>/dev/null || true

STDIN_JSON4=$(printf '{"cwd": "%s", "session_id": "test-session-789", "source": "startup"}' "$T4_DIR")

# First run — should emit banner
OUTPUT4A=$(printf '%s' "$STDIN_JSON4" | sh "$HOOKS_DIR/sessionstart.sh" 2>/dev/null)
# Second run immediately — sentinel should suppress
OUTPUT4B=$(printf '%s' "$STDIN_JSON4" | sh "$HOOKS_DIR/sessionstart.sh" 2>/dev/null)

FIRST_HAS_BANNER=0
SECOND_HAS_BANNER=0
printf '%s' "$OUTPUT4A" | grep -q 'quoin-S-4' && FIRST_HAS_BANNER=1
printf '%s' "$OUTPUT4B" | grep -q 'quoin-S-4' && SECOND_HAS_BANNER=1

if [ "$FIRST_HAS_BANNER" -eq 1 ] && [ "$SECOND_HAS_BANNER" -eq 0 ]; then
  pass "Test 4 — dedup: banner fired once, suppressed on second run"
elif [ "$FIRST_HAS_BANNER" -eq 0 ]; then
  fail "Test 4 — first run did not fire banner (dedup pre-condition failed)"
else
  fail "Test 4 — second run fired banner (dedup did not suppress)"
fi

# Clean up sentinel and temp dir
rm -f "$SENTINEL_PATH" 2>/dev/null || true
rm -rf "$T4_DIR"

# ── Test 5: sessionend.sh with recent end_of_day_due: yes → nudge emitted ────
echo ""
echo "Test 5: sessionend.sh with recent end_of_day_due: yes → nudge emitted"
T5_DIR=$(mktemp -d)
mkdir -p "$T5_DIR/.workflow_artifacts/memory/sessions"
SESSION_FILE5="$T5_DIR/.workflow_artifacts/memory/sessions/2026-05-04-end-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$SESSION_FILE5"

STDIN_JSON5=$(printf '{"cwd": "%s", "session_id": "test-end-123"}' "$T5_DIR")
OUTPUT5=$(printf '%s' "$STDIN_JSON5" | sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null)
if printf '%s' "$OUTPUT5" | grep -q 'quoin-S-4'; then
  if printf '%s' "$OUTPUT5" | grep -q 'end-task'; then
    # Post-T-00 assertion: verify hookEventName or systemMessage format
    # T-00 determined CASE A-modified: SessionEnd uses systemMessage channel
    if printf '%s' "$OUTPUT5" | grep -q 'systemMessage'; then
      pass "Test 5 — sessionend.sh: nudge emitted with task name and systemMessage channel"
    else
      fail "Test 5 — nudge emitted but systemMessage channel not found in output"
    fi
  else
    fail "Test 5 — nudge emitted but task name 'end-task' not found in output"
  fi
else
  fail "Test 5 — sessionend.sh did not emit nudge for end_of_day_due: yes"
fi
rm -rf "$T5_DIR"

# ── Test 6: sessionend.sh with recent end_of_day_due: no → no nudge ──────────
echo ""
echo "Test 6: sessionend.sh with recent end_of_day_due: no → no nudge"
T6_DIR=$(mktemp -d)
mkdir -p "$T6_DIR/.workflow_artifacts/memory/sessions"
SESSION_FILE6="$T6_DIR/.workflow_artifacts/memory/sessions/2026-05-04-done-task.md"
printf '## Cost\nend_of_day_due: no\n' > "$SESSION_FILE6"

STDIN_JSON6=$(printf '{"cwd": "%s", "session_id": "test-end-456"}' "$T6_DIR")
OUTPUT6=$(printf '%s' "$STDIN_JSON6" | sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null)
if printf '%s' "$OUTPUT6" | grep -q 'quoin-S-4'; then
  fail "Test 6 — sessionend.sh emitted nudge for end_of_day_due: no"
else
  pass "Test 6 — sessionend.sh: no nudge for end_of_day_due: no"
fi
rm -rf "$T6_DIR"

# ── Test 7: both hooks exit 0 when sessions/ is absent ───────────────────────
echo ""
echo "Test 7: both hooks exit 0 when sessions/ directory is absent"
T7_DIR=$(mktemp -d)
# No sessions/ directory created

STDIN_JSON7=$(printf '{"cwd": "%s", "session_id": "test-nosessions"}' "$T7_DIR")

# sessionstart.sh exit code
printf '%s' "$STDIN_JSON7" | sh "$HOOKS_DIR/sessionstart.sh" > /dev/null 2>&1
EXIT_SS=$?

# sessionend.sh exit code
printf '%s' "$STDIN_JSON7" | sh "$HOOKS_DIR/sessionend.sh" > /dev/null 2>&1
EXIT_SE=$?

if [ "$EXIT_SS" -eq 0 ] && [ "$EXIT_SE" -eq 0 ]; then
  pass "Test 7 — both hooks exit 0 with no sessions/ directory"
elif [ "$EXIT_SS" -ne 0 ]; then
  fail "Test 7 — sessionstart.sh exited $EXIT_SS (expected 0)"
else
  fail "Test 7 — sessionend.sh exited $EXIT_SE (expected 0)"
fi
rm -rf "$T7_DIR"

# ── Final summary ──────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
