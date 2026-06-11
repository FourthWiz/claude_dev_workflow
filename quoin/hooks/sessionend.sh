#!/bin/sh
# sessionend.sh — SessionEnd hook for quoin workflow isolation
# Deployed to ~/.claude/hooks/ by bash install.sh
# Registered for: SessionEnd (confirmed by T-00 spike — event name verified against Anthropic docs).
#
# S-4 responsibility: EOD nudge at session end.
#   - Reads most-recently-modified sessions/*.md file (mtime within 8 hours)
#   - If end_of_day_due: yes → emits one systemMessage nudge
#   - Does NOT invoke /end_of_day — nudge only
#
# Output channel: systemMessage (SessionEnd does NOT support additionalContext — T-00 confirmed)
# SessionEnd runs asynchronously; exit code is ignored. Fail-OPEN by design.
#
# Fail-OPEN: any error → exit 0, no output.

. "$(dirname "$0")/_lib.sh" && read_constants

# STEP -1: Capture stdin (even if unused — consistency with other hooks)
STDIN=$(cat)

# STEP 1: Parse cwd from stdin
cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
[ -z "$cwd" ] && cwd="$PWD"
cwd=$(resolve_project_root "$cwd")

SESSIONS_DIR="${cwd}/.workflow_artifacts/memory/sessions"

# STEP 2: If sessions/ does not exist → exit 0 silently
[ -d "$SESSIONS_DIR" ] || exit 0

# STEP 3: Find most recently modified session file within the last 8 hours
# 8 hours = 28800 seconds; use -mtime -1 (24h window) + mtime sort for portability
# Then apply a POSIX-compatible age check using file mtime vs current time
NOW=$(date +%s)
EIGHT_HOURS=28800

RECENT_FILE=""
RECENT_MTIME=0

# Use a temp file to collect find results (POSIX-safe: avoids < <(...) bash-ism)
_SE_TMPFILE=$(mktemp 2>/dev/null) || _SE_TMPFILE="${TMPDIR:-/tmp}/quoin-s4-se-tmp-$$"
find "$SESSIONS_DIR" -maxdepth 1 -name '*.md' -mtime -1 2>/dev/null > "$_SE_TMPFILE"

while IFS= read -r f; do
  [ -f "$f" ] || continue
  # Get file mtime in epoch seconds using a POSIX-portable approach
  # Try: python3 (available on macOS + Linux); fallback: stat (BSD form works on darwin)
  fmtime=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$f" 2>/dev/null) \
    || fmtime=$(stat -f %m "$f" 2>/dev/null) \
    || fmtime=0
  age=$(( NOW - fmtime ))
  if [ "$age" -le "$EIGHT_HOURS" ] && [ "$fmtime" -gt "$RECENT_MTIME" ]; then
    RECENT_MTIME="$fmtime"
    RECENT_FILE="$f"
  fi
done < "$_SE_TMPFILE"
rm -f "$_SE_TMPFILE" 2>/dev/null || true

# STEP 4: If no recent file found → exit 0
[ -z "$RECENT_FILE" ] && exit 0

# STEP 5: Check end_of_day_due field
grep -q 'end_of_day_due: yes' "$RECENT_FILE" 2>/dev/null || exit 0

# STEP 6: Extract task name for the nudge message
task_name=$(basename "$RECENT_FILE" .md | sed 's/^[0-9]*-[0-9]*-[0-9]*-//')

# Banner shape mirrors quoin/hooks/sessionstart.sh:69 and quoin/skills/start_of_day/SKILL.md Step 1 — keep in sync; drift test: quoin/dev/tests/test_lifecycle_banner_drift.sh
# STEP 7: Emit nudge via systemMessage
# SessionEnd output channel is systemMessage (not additionalContext — confirmed by T-00 spike).
printf '{"systemMessage": "[quoin-S-4] Session ending with unfinished task: %s — run /checkpoint to save your place (resume next session) or /end_of_day to wrap up the workday."}\n' \
  "$task_name"

# STEP 8: Capture Close snapshot
# Writes a ## Close snapshot block to the active session-state file so /end_of_day
# Step 3e can reconcile the session UUID into the cost ledger.
# Fail-OPEN: every failure path falls through to exit 0 with no output.
# No new dependencies (python3, stat, find, sed, grep, basename, date, mktemp, cat).
# No stdout output — the existing STEP 7 systemMessage is the only stdout line.
_S2_TMP=""
_S2_BLOCK=""
_S2_CLEANUP() { rm -f "$_S2_TMP" "$_S2_BLOCK" 2>/dev/null || true; }

proj_hash=$(printf '%s' "$cwd" | sed 's|/|-|g') || { _S2_CLEANUP; exit 0; }
jsonl_dir="$HOME/.claude/projects/$proj_hash"
[ -d "$jsonl_dir" ] || exit 0

_S2_TMP=$(mktemp 2>/dev/null) || _S2_TMP="${TMPDIR:-/tmp}/quoin-s2-tmp-$$"
find "$jsonl_dir" -maxdepth 1 -name '*.jsonl' -mmin -60 2>/dev/null > "$_S2_TMP" || { _S2_CLEANUP; exit 0; }

# Select JSONL with greatest mtime using python3; fallback to stat -f %m (BSD)
selected_jsonl=$(python3 - "$_S2_TMP" <<'PYEOF' 2>/dev/null
import sys, os
with open(sys.argv[1]) as f:
    files = [l.strip() for l in f if l.strip()]
if not files:
    sys.exit(1)
best = max(files, key=lambda p: os.path.getmtime(p))
print(best)
PYEOF
) || selected_jsonl=""

if [ -z "$selected_jsonl" ]; then
  _S2_CLEANUP; exit 0
fi

# Get mtime of selected JSONL (seconds since epoch)
jsonl_mtime=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$selected_jsonl" 2>/dev/null) \
  || jsonl_mtime=$(stat -f %m "$selected_jsonl" 2>/dev/null) \
  || jsonl_mtime=0

# Get mtime of session-state file
session_mtime=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$RECENT_FILE" 2>/dev/null) \
  || session_mtime=$(stat -f %m "$RECENT_FILE" 2>/dev/null) \
  || session_mtime=0

# Stale cross-check: skip if JSONL was modified before the session-state file
if [ "$jsonl_mtime" -lt "$session_mtime" ] 2>/dev/null; then
  _S2_CLEANUP; exit 0
fi

jsonl_uuid=$(basename "$selected_jsonl" .jsonl) || { _S2_CLEANUP; exit 0; }

# Idempotency check: skip if UUID already recorded in the session file
grep -q "Session UUID:[[:space:]]*$jsonl_uuid" "$RECENT_FILE" 2>/dev/null && { _S2_CLEANUP; exit 0; }

# Build the snapshot block in a tmpfile then atomically append it
_S2_BLOCK=$(mktemp 2>/dev/null) || _S2_BLOCK="${TMPDIR:-/tmp}/quoin-s2-block-$$"
printf '\n## Close snapshot\n- Closed at: %s\n- JSONL UUID: %s\n- Project: %s\n- Note: session closed; UUID captured by sessionend hook for EOD reconciliation\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$jsonl_uuid" "$proj_hash" > "$_S2_BLOCK" 2>/dev/null || { _S2_CLEANUP; exit 0; }

cat "$_S2_BLOCK" >> "$RECENT_FILE" 2>/dev/null || true
_S2_CLEANUP

exit 0
