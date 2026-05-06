#!/bin/sh
# test_sessionend_close_snapshot.sh — Tests for sessionend.sh STEP 8 Close snapshot
# Run from project root: bash quoin/dev/tests/test_sessionend_close_snapshot.sh
# All tests exit 0 on PASS, emit "FAIL: <reason>" and set FAIL counter.
# Mirrors test_session_lifecycle_hooks.sh style: POSIX sh, mktemp, trap-based cleanup.

PASS=0; FAIL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/../../hooks"

pass() { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }
skip() { echo "SKIP: $1"; PASS=$((PASS+1)); }

TODAY=$(date +%Y%m%d)
TEST_UUID="deadbeef-0000-1234-5678-abcdef000001"

# ── Test A: happy path — snapshot block appended ─────────────────────────────
echo ""
echo "Test A: happy path — Close snapshot block appended to session file"
TA_WORLD=$(mktemp -d)
TA_HOME=$(mktemp -d)
trap 'rm -rf "$TA_WORLD" "$TA_HOME"' EXIT

TA_SESSIONS="$TA_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TA_SESSIONS"

# Compute proj_hash from TA_WORLD (same formula as hook: sed 's|/|-|g')
TA_PROJ_HASH=$(printf '%s' "$TA_WORLD" | sed 's|/|-|g')
TA_JSONL_DIR="$TA_HOME/.claude/projects/$TA_PROJ_HASH"
mkdir -p "$TA_JSONL_DIR"

# Create session file with end_of_day_due: yes but no Session UUID
TA_SESSION_FILE="$TA_SESSIONS/${TODAY}-ta-task.md"
printf '## Cost\nend_of_day_due: yes\nfallback_fires: 0\n' > "$TA_SESSION_FILE"

# Backdate session file to 30 min ago using touch -t
THIRTY_MIN_AGO=$(date -v-30M +%Y%m%d%H%M 2>/dev/null) || THIRTY_MIN_AGO=""
if [ -n "$THIRTY_MIN_AGO" ] && touch -t "${THIRTY_MIN_AGO}" "$TA_SESSION_FILE" 2>/dev/null; then
  # Create JSONL with mtime = now (newer than session file)
  TA_JSONL="$TA_JSONL_DIR/${TEST_UUID}.jsonl"
  printf '{}' > "$TA_JSONL"
  # JSONL is current (mtime = now), session is 30 min old

  TA_STDIN=$(printf '{"cwd":"%s"}' "$TA_WORLD")
  printf '%s' "$TA_STDIN" | env HOME="$TA_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null

  # Assertions
  # Use grep -c without || fallback: grep -c returns count (0 or N) even on no-match; exit 1 on no-match is not an error here
  SNAP_COUNT=$(grep -c '^## Close snapshot$' "$TA_SESSION_FILE" 2>/dev/null); SNAP_COUNT=${SNAP_COUNT:-0}
  UUID_FOUND=$(grep -q "JSONL UUID: ${TEST_UUID}" "$TA_SESSION_FILE" 2>/dev/null && printf '1' || printf '0')
  HASH_FOUND=$(grep -q "Project: ${TA_PROJ_HASH}" "$TA_SESSION_FILE" 2>/dev/null && printf '1' || printf '0')
  CLOSED_FOUND=$(grep -q 'Closed at:' "$TA_SESSION_FILE" 2>/dev/null && printf '1' || printf '0')

  if [ "$SNAP_COUNT" -eq 1 ] && [ "$UUID_FOUND" -eq 1 ] && [ "$HASH_FOUND" -eq 1 ] && [ "$CLOSED_FOUND" -eq 1 ]; then
    pass "Test A — happy path: Close snapshot block appended with correct fields"
  else
    fail "Test A — happy path: snapshot_count=$SNAP_COUNT uuid=$UUID_FOUND hash=$HASH_FOUND closed=$CLOSED_FOUND (all must be 1)"
  fi
else
  skip "Test A — touch -t not available on this platform; happy-path test cannot run"
fi
trap - EXIT
rm -rf "$TA_WORLD" "$TA_HOME"

# ── Test B: idempotent — UUID already in session file, no snapshot appended ──
echo ""
echo "Test B: idempotent — UUID already recorded, no Close snapshot appended"
TB_WORLD=$(mktemp -d)
TB_HOME=$(mktemp -d)
trap 'rm -rf "$TB_WORLD" "$TB_HOME"' EXIT

TB_SESSIONS="$TB_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TB_SESSIONS"
TB_PROJ_HASH=$(printf '%s' "$TB_WORLD" | sed 's|/|-|g')
TB_JSONL_DIR="$TB_HOME/.claude/projects/$TB_PROJ_HASH"
mkdir -p "$TB_JSONL_DIR"

TB_SESSION_FILE="$TB_SESSIONS/${TODAY}-tb-task.md"
# Pre-populate with a matching Session UUID line
printf '## Cost\nend_of_day_due: yes\n- Session UUID: %s\n' "$TEST_UUID" > "$TB_SESSION_FILE"

TB_JSONL="$TB_JSONL_DIR/${TEST_UUID}.jsonl"
printf '{}' > "$TB_JSONL"

TB_STDIN=$(printf '{"cwd":"%s"}' "$TB_WORLD")
printf '%s' "$TB_STDIN" | env HOME="$TB_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null

SNAP_COUNT_B=$(grep -c '^## Close snapshot$' "$TB_SESSION_FILE" 2>/dev/null); SNAP_COUNT_B=${SNAP_COUNT_B:-0}
if [ "$SNAP_COUNT_B" -eq 0 ]; then
  pass "Test B — idempotent: no Close snapshot appended when UUID already recorded"
else
  fail "Test B — idempotent: snapshot was appended despite UUID already in file (count=$SNAP_COUNT_B)"
fi
trap - EXIT
rm -rf "$TB_WORLD" "$TB_HOME"

# ── Test C: stale JSONL outside -mmin -60 window — no snapshot ───────────────
echo ""
echo "Test C: stale JSONL (>60 min old) — no snapshot appended"
TC_WORLD=$(mktemp -d)
TC_HOME=$(mktemp -d)
trap 'rm -rf "$TC_WORLD" "$TC_HOME"' EXIT

TC_SESSIONS="$TC_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TC_SESSIONS"
TC_PROJ_HASH=$(printf '%s' "$TC_WORLD" | sed 's|/|-|g')
TC_JSONL_DIR="$TC_HOME/.claude/projects/$TC_PROJ_HASH"
mkdir -p "$TC_JSONL_DIR"

TC_SESSION_FILE="$TC_SESSIONS/${TODAY}-tc-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$TC_SESSION_FILE"

TC_UUID="deadbeef-0000-1234-5678-abcdef000003"
TC_JSONL="$TC_JSONL_DIR/${TC_UUID}.jsonl"
printf '{}' > "$TC_JSONL"

# Backdate JSONL to 90 min ago (beyond the -mmin -60 find window)
NINETY_MIN_AGO=$(date -v-90M +%Y%m%d%H%M 2>/dev/null) || NINETY_MIN_AGO=""
if [ -n "$NINETY_MIN_AGO" ] && touch -t "${NINETY_MIN_AGO}" "$TC_JSONL" 2>/dev/null; then
  TC_STDIN=$(printf '{"cwd":"%s"}' "$TC_WORLD")
  printf '%s' "$TC_STDIN" | env HOME="$TC_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null

  SNAP_COUNT_C=$(grep -c '^## Close snapshot$' "$TC_SESSION_FILE" 2>/dev/null); SNAP_COUNT_C=${SNAP_COUNT_C:-0}
  if [ "$SNAP_COUNT_C" -eq 0 ]; then
    pass "Test C — stale JSONL: no snapshot appended (find -mmin filter excluded it)"
  else
    fail "Test C — stale JSONL: snapshot was appended despite JSONL being 90 min old"
  fi
else
  skip "Test C — touch -t not available on this platform; stale-JSONL test cannot run"
fi
trap - EXIT
rm -rf "$TC_WORLD" "$TC_HOME"

# ── Test D: JSONL within window but older than session file — stale cross-check
echo ""
echo "Test D: JSONL within 60-min window but mtime < session-state mtime — no snapshot"
TD_WORLD=$(mktemp -d)
TD_HOME=$(mktemp -d)
trap 'rm -rf "$TD_WORLD" "$TD_HOME"' EXIT

TD_SESSIONS="$TD_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TD_SESSIONS"
TD_PROJ_HASH=$(printf '%s' "$TD_WORLD" | sed 's|/|-|g')
TD_JSONL_DIR="$TD_HOME/.claude/projects/$TD_PROJ_HASH"
mkdir -p "$TD_JSONL_DIR"

TD_SESSION_FILE="$TD_SESSIONS/${TODAY}-td-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$TD_SESSION_FILE"

TD_UUID="deadbeef-0000-1234-5678-abcdef000004"
TD_JSONL="$TD_JSONL_DIR/${TD_UUID}.jsonl"
printf '{}' > "$TD_JSONL"

# Set JSONL to 30 min ago, session file to now
THIRTY_MIN_AGO_D=$(date -v-30M +%Y%m%d%H%M 2>/dev/null) || THIRTY_MIN_AGO_D=""
if [ -n "$THIRTY_MIN_AGO_D" ] && touch -t "${THIRTY_MIN_AGO_D}" "$TD_JSONL" 2>/dev/null; then
  # Touch session file to now (it is already newer by default, but be explicit)
  touch "$TD_SESSION_FILE" 2>/dev/null || true

  TD_STDIN=$(printf '{"cwd":"%s"}' "$TD_WORLD")
  printf '%s' "$TD_STDIN" | env HOME="$TD_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null

  SNAP_COUNT_D=$(grep -c '^## Close snapshot$' "$TD_SESSION_FILE" 2>/dev/null); SNAP_COUNT_D=${SNAP_COUNT_D:-0}
  if [ "$SNAP_COUNT_D" -eq 0 ]; then
    pass "Test D — stale cross-check: no snapshot when JSONL older than session file"
  else
    fail "Test D — stale cross-check: snapshot appended despite JSONL mtime < session mtime"
  fi
else
  skip "Test D — touch -t not available on this platform; stale-cross-check test cannot run"
fi
trap - EXIT
rm -rf "$TD_WORLD" "$TD_HOME"

# ── Test E: no project-hash directory — fail-OPEN exit 0, nudge unchanged ────
echo ""
echo "Test E: no project-hash directory — hook exits 0 without snapshot"
TE_WORLD=$(mktemp -d)
TE_HOME=$(mktemp -d)
trap 'rm -rf "$TE_WORLD" "$TE_HOME"' EXIT

TE_SESSIONS="$TE_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TE_SESSIONS"
# NOTE: we deliberately do NOT create the project-hash directory in TE_HOME

TE_SESSION_FILE="$TE_SESSIONS/${TODAY}-te-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$TE_SESSION_FILE"

TE_STDIN=$(printf '{"cwd":"%s"}' "$TE_WORLD")
TE_OUTPUT=$(printf '%s' "$TE_STDIN" | env HOME="$TE_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null)
TE_EXIT=$?

SNAP_COUNT_E=$(grep -c '^## Close snapshot$' "$TE_SESSION_FILE" 2>/dev/null); SNAP_COUNT_E=${SNAP_COUNT_E:-0}

if [ "$TE_EXIT" -eq 0 ] && [ "$SNAP_COUNT_E" -eq 0 ]; then
  # Verify STEP 7 nudge behavior is still intact (end_of_day_due: yes → systemMessage)
  if printf '%s' "$TE_OUTPUT" | grep -q 'systemMessage'; then
    pass "Test E — no project dir: exit 0, no snapshot, STEP 7 nudge emitted"
  else
    fail "Test E — no project dir: exit 0 and no snapshot, but STEP 7 nudge missing from output"
  fi
else
  fail "Test E — no project dir: exit=$TE_EXIT snapshot_count=$SNAP_COUNT_E (expected exit=0, count=0)"
fi
trap - EXIT
rm -rf "$TE_WORLD" "$TE_HOME"

# ── Test F: unreadable project-hash directory — fail-OPEN exit 0 ─────────────
echo ""
echo "Test F: unreadable project-hash directory — hook exits 0 (fail-OPEN)"
TF_WORLD=$(mktemp -d)
TF_HOME=$(mktemp -d)
trap 'chmod 755 "$TF_HOME/.claude/projects" 2>/dev/null || true; rm -rf "$TF_WORLD" "$TF_HOME"' EXIT

TF_SESSIONS="$TF_WORLD/.workflow_artifacts/memory/sessions"
mkdir -p "$TF_SESSIONS"
TF_PROJ_HASH=$(printf '%s' "$TF_WORLD" | sed 's|/|-|g')
TF_JSONL_DIR="$TF_HOME/.claude/projects/$TF_PROJ_HASH"
mkdir -p "$TF_JSONL_DIR"

TF_SESSION_FILE="$TF_SESSIONS/${TODAY}-tf-task.md"
printf '## Cost\nend_of_day_due: yes\n' > "$TF_SESSION_FILE"

# Attempt chmod 000 on the project-hash dir; skip if platform doesn't support it
if chmod 000 "$TF_JSONL_DIR" 2>/dev/null; then
  TF_STDIN=$(printf '{"cwd":"%s"}' "$TF_WORLD")
  printf '%s' "$TF_STDIN" | env HOME="$TF_HOME" sh "$HOOKS_DIR/sessionend.sh" 2>/dev/null
  TF_EXIT=$?
  # Restore permissions for cleanup
  chmod 755 "$TF_JSONL_DIR" 2>/dev/null || true

  SNAP_COUNT_F=$(grep -c '^## Close snapshot$' "$TF_SESSION_FILE" 2>/dev/null); SNAP_COUNT_F=${SNAP_COUNT_F:-0}
  if [ "$TF_EXIT" -eq 0 ] && [ "$SNAP_COUNT_F" -eq 0 ]; then
    pass "Test F — unreadable dir: hook exits 0, no snapshot (fail-OPEN)"
  else
    fail "Test F — unreadable dir: exit=$TF_EXIT snapshot_count=$SNAP_COUNT_F (expected exit=0, count=0)"
  fi
else
  skip "Test F — chmod 000 not supported on this platform; fail-OPEN test cannot run"
fi
trap - EXIT
chmod 755 "$TF_HOME/.claude/projects/$TF_PROJ_HASH" 2>/dev/null || true
rm -rf "$TF_WORLD" "$TF_HOME"

# ── Final summary ──────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
