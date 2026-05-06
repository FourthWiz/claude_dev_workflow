#!/bin/sh
# postcompact.sh — PostCompact hook for quoin workflow
# Deployed to ~/.claude/hooks/ by bash install.sh
# Fires after auto compaction completes. No decision control — side effects only.
# Writes a postcompact-reset-${session_id}.txt sentinel so userpromptsubmit.sh
# STEP 0.5 can detect compaction and trash-move the sentinel on the next prompt submit.
# Fail-OPEN: any error → exit 0. No stdout output.
#
# Shebang assertion: head -1 ... | grep -qE '^#!/bin/sh( |$)'

# STEP -1: Capture stdin before any parsing (stdin can only be read once)
STDIN=$(cat)

# Parse fields from JSON (same pattern as precompact.sh lines 17-38)
session_id=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
transcript_path=$(printf '%s' "$STDIN" | jq -r '.transcript_path // empty' 2>/dev/null) || exit 0

# Guard: session_id required for a usable sentinel filename
[ -z "$session_id" ] && exit 0
[ -z "$cwd" ] && cwd="$PWD"

MEMORY_DIR="${cwd}/.workflow_artifacts/memory"
[ -d "$MEMORY_DIR" ] || exit 0

SENTINEL="${MEMORY_DIR}/postcompact-reset-${session_id}.txt"

compacted_at=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || compacted_at="unknown"

transcript_bytes_after=0
if [ -n "$transcript_path" ] && [ -r "$transcript_path" ]; then
    transcript_bytes_after=$(wc -c < "$transcript_path" 2>/dev/null | awk '{print $1}') || transcript_bytes_after=0
fi
transcript_bytes_after=${transcript_bytes_after:-0}

printf 'compacted_at=%s\nsession_id=%s\ntranscript_path=%s\ntranscript_bytes_after=%s\n' \
    "$compacted_at" "$session_id" "$transcript_path" "$transcript_bytes_after" \
    > "$SENTINEL" 2>/dev/null || true

exit 0
