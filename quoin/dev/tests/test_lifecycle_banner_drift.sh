#!/bin/sh
# test_lifecycle_banner_drift.sh — Drift test for lifecycle banner wording
#
# Purpose: asserts no banner surface still says '/end_of_day before' —
#   replaced with /checkpoint nudges per checkpoint-scope-expansion stages 1–3.
#
# Invocation (from project root):
#   bash quoin/dev/tests/test_lifecycle_banner_drift.sh
#
# Note: the search-target list is fixed at four paths and must stay aligned
#   with the architecture's Stage 3 R-01 mitigation. Do NOT add or remove
#   targets without updating the architecture.md acceptance spec.

PASS=0; FAIL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/../../.."

pass() { echo "PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }

TMPFILE=$(mktemp 2>/dev/null) || TMPFILE="${TMPDIR:-/tmp}/quoin-drift-tmp-$$"
trap 'rm -f "$TMPFILE"' EXIT

# ── Test 1: no banner surface says '/end_of_day before' ──────────────────────
echo ""
echo "Test 1: no banner surface contains '/end_of_day before'"

grep -rn '/end_of_day before' \
  "$REPO_ROOT/quoin/hooks/" \
  "$REPO_ROOT/quoin/skills/start_of_day/SKILL.md" \
  "$REPO_ROOT/quoin/skills/checkpoint/SKILL.md" \
  "$REPO_ROOT/quoin/CLAUDE.md" \
  > "$TMPFILE" 2>/dev/null
GREP_EXIT=$?
LINE_COUNT=$(wc -l < "$TMPFILE" | tr -d ' ')

if [ "$GREP_EXIT" -eq 1 ] && [ "$LINE_COUNT" -eq 0 ]; then
  pass "Test 1 — no banner surface contains '/end_of_day before'"
else
  fail "Test 1 — '/end_of_day before' still present in one or more banner surfaces (exit=$GREP_EXIT, lines=$LINE_COUNT):"
  cat "$TMPFILE"
fi

# ── Final summary ──────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
