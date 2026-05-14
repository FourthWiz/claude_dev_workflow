#!/bin/sh
# sessionstart.sh — SessionStart hook for quoin workflow isolation
# Deployed to ~/.claude/hooks/ by bash install.sh
# Registered for BOTH matchers: startup and resume.
#
# S-2 responsibility: pending-restore banner emission.
#   - Sweeps stale pending-prompt-*.txt and pending-restore-*.txt files
#   - Surfaces pending-restore banner if a sentinel is found for this session
#     (or mtime-most-recent if no current-session match)
#
# Fail-OPEN: any error → exit 0, no output.
# Shebang assertion: head -1 ... | grep -qE '^#!/bin/sh( |$)'
# No-args form RECOMMENDED for fail-OPEN hooks.

# Source shared helper library
. "$(dirname "$0")/_lib.sh" && read_constants

# STEP -1: Capture stdin before any parsing (stdin can only be read once)
STDIN=$(cat)

# STEP 1: Parse source and session_id
src=$(printf '%s' "$STDIN" | jq -r '.source // empty' 2>/dev/null) || exit 0
session_id=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
[ -z "$cwd" ] && cwd="$PWD"

MEMORY_DIR="${cwd}/.workflow_artifacts/memory"

# === S-4 missing-EOD banner ===
# Check for session files with end_of_day_due: yes within last 36 hours.
# Sentinel dedup: skip if banner fired within the last 5 minutes.

SESSIONS_DIR="${MEMORY_DIR}/sessions"
EOD_SENTINEL="${TMPDIR:-/tmp}/quoin-s4-eod-banner-$(date -u +%Y%m%d).tmp"
EOD_BANNER_FIRED=0

# Dedup check: if sentinel exists and is < 300 seconds old, skip banner
if [ -f "$EOD_SENTINEL" ]; then
  SENTINEL_MTIME=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$EOD_SENTINEL" 2>/dev/null \
    || stat -f %m "$EOD_SENTINEL" 2>/dev/null \
    || echo 0)
  SENTINEL_AGE=$(( $(date +%s) - SENTINEL_MTIME ))
  if [ "$SENTINEL_AGE" -lt 300 ]; then
    EOD_BANNER_FIRED=1
  fi
fi

if [ "$EOD_BANNER_FIRED" -eq 0 ] && [ -d "$SESSIONS_DIR" ]; then
  # Collect task names from session files modified within last 36 hours
  # with end_of_day_due: yes
  # 36 hours = 1.5 days; -mtime -2 catches files modified within last 48h on most systems
  # Use a temp file to collect results (POSIX-safe: avoids < <(...) bash-ism)
  _EOD_TMPFILE=$(mktemp 2>/dev/null) || _EOD_TMPFILE="${TMPDIR:-/tmp}/quoin-s4-eod-tmp-$$"
  find "$SESSIONS_DIR" -maxdepth 1 -name '*.md' -mtime -2 2>/dev/null > "$_EOD_TMPFILE"

  UNFINISHED_TASKS=""
  while IFS= read -r session_file; do
    [ -f "$session_file" ] || continue
    if grep -q 'end_of_day_due: yes' "$session_file" 2>/dev/null; then
      # Extract task name from filename: <date>-<task-name>.md → task-name
      task_name=$(basename "$session_file" .md | sed 's/^[0-9]*-[0-9]*-[0-9]*-//')
      UNFINISHED_TASKS="${UNFINISHED_TASKS}${task_name} "
    fi
  done < "$_EOD_TMPFILE"
  rm -f "$_EOD_TMPFILE" 2>/dev/null || true

  UNFINISHED_TASKS="${UNFINISHED_TASKS% }"
  # banner shape mirrors quoin/skills/start_of_day/SKILL.md Step 1 — keep in sync
  if [ -n "$UNFINISHED_TASKS" ]; then
    printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "[quoin-S-4] Unfinished /end_of_day detected for task(s): %s — run /checkpoint to save your place (or /end_of_day to wrap up the workday)."}}\n' \
      "$UNFINISHED_TASKS"
    # Write dedup sentinel
    touch "$EOD_SENTINEL" 2>/dev/null || true
  fi
fi
# === end S-4 missing-EOD banner ===

# STEP 2: Sweep stale sentinel files
# Trash-move pending-prompt-*.txt and pending-restore-*.txt older than STALE_DAYS days.
# STALE_DAYS sourced from read_constants() (default 7, override via QUOIN_STALE_SENTINEL_DAYS)
# Using find -exec sh -c to avoid word-splitting on paths containing spaces.
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
find "$MEMORY_DIR" -maxdepth 1 \( -name 'pending-prompt-*.txt' -o -name 'pending-restore-*.txt' \) -mtime +"$STALE_DAYS" \
  -exec sh -c ". \"$HOOKS_DIR/_lib.sh\" && trash_move \"\$1\" \"\$2\"" _ {} "$MEMORY_DIR" \; 2>/dev/null || true

# STEP 3: Look for current-session pending-restore sentinel
pending_restore=""
session_id_match="current-session"

if [ -n "$session_id" ] && [ -f "${MEMORY_DIR}/pending-restore-${session_id}.txt" ]; then
  pending_restore="${MEMORY_DIR}/pending-restore-${session_id}.txt"
  session_id_match="current-session"
fi

# STEP 4: Fallback to mtime-most-recent if no current-session match
# (UUID-shaped session_ids have no time-ordering; lex order is meaningless)
if [ -z "$pending_restore" ]; then
  most_recent=$(ls -t "${MEMORY_DIR}"/pending-restore-*.txt 2>/dev/null | head -1)
  if [ -n "$most_recent" ] && [ -f "$most_recent" ]; then
    pending_restore="$most_recent"
    session_id_match="mismatch-warning: surfaced from different session (mtime-most-recent fallback)"
  fi
fi

# STEP 5: If no sentinel found → exit 0 transparently
if [ -z "$pending_restore" ]; then
  exit 0
fi

# STEP 6: Read sentinel content (the checkpoint file path)
sentinel_content=$(cat "$pending_restore" 2>/dev/null) || exit 0
[ -z "$sentinel_content" ] && exit 0

# Emit banner JSON
printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "Pending restore detected. A /checkpoint --restore is recommended (checkpoint: %s — session-id match: %s)"}}\n' \
  "$sentinel_content" "$session_id_match"

# === S-1 pollution-score writer (stub — populated by S-1) ===
# (intentionally empty; S-1 implementation extends this block)
