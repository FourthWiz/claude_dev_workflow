#!/usr/bin/env bash
# verify_timeout_metric.sh — Post-merge stream-idle timeout verification harness.
#
# Usage: bash verify_timeout_metric.sh [DAYS]
#   DAYS: lookback window in days (default: 7)
#
# Exits 0 (PASS) if ≤1 file with 'Stream idle timeout' in the last DAYS days.
# Exits 1 (FAIL) if >1 file (target metric exceeded).
#
# Day-0 sanity gate: on pre-merge baseline, this MUST report a non-zero count.
# If it reports 0 on day-0, the proc itself is broken — investigate before relying on it.
#
# Run daily for 14 days post-merge per proc:T-12-verify in the plan.

set -euo pipefail

PROJ_HASH="-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com-My-Drive-Storage-Claude-workflow"
PROJ_DIR="$HOME/.claude/projects/$PROJ_HASH"
SINCE_DAYS="${1:-7}"

if [ ! -d "$PROJ_DIR" ]; then
  echo "ERROR: project dir not found: $PROJ_DIR"
  echo "Check PROJ_HASH matches your actual project path hash."
  exit 2
fi

# Count files (not occurrences) with at least one 'Stream idle timeout' in the window.
# find -mtime -N includes files modified in the last N days.
COUNT=$(find "$PROJ_DIR" -maxdepth 1 -name "*.jsonl" -mtime "-${SINCE_DAYS}" -exec grep -l 'Stream idle timeout' {} \; 2>/dev/null | wc -l | tr -d ' ')

echo "Stream-idle timeouts in last ${SINCE_DAYS}d: ${COUNT} file(s)"
echo "Target: ≤ 1 per ${SINCE_DAYS}-day window"

if [ "$COUNT" -eq 0 ]; then
  echo "NOTE: 0 files found. If this is the day-0 baseline check, this is UNEXPECTED"
  echo "      (we know ≥6 incidents exist from Apr 28-29). Investigate the proc itself."
  echo "PASS (but verify the sanity gate above before trusting this result)"
  exit 0
fi

if [ "$COUNT" -gt 1 ]; then
  echo "FAIL: target is ≤ 1 per ${SINCE_DAYS}-day window (found ${COUNT})"
  echo ""
  echo "Incident details (files containing timeouts, most recent first):"
  find "$PROJ_DIR" -maxdepth 1 -name "*.jsonl" -mtime "-${SINCE_DAYS}" -exec grep -l 'Stream idle timeout' {} \; 2>/dev/null \
    | xargs ls -lt 2>/dev/null \
    | head -10
  echo ""
  echo "Next steps: capture session UUID + tool-call count + subagent name,"
  echo "append to next-steps-timeout-debug.md, open a follow-up task."
  exit 1
fi

echo "PASS"
