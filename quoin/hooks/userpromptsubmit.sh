#!/bin/sh
# userpromptsubmit.sh — UserPromptSubmit hook for quoin workflow isolation
# Deployed to ~/.claude/hooks/ by bash install.sh
#
# Contract: reads transcript_path, prompt, session_id, cwd from stdin JSON.
# Checks context utilization; emits advisory at STOP_BPS or block at BLOCK_BPS.
# Fail-OPEN: any error → exit 0, no output.
#
# Shebang assertion: head -1 ... | grep -qE '^#!/bin/sh( |$)'
# No-args form RECOMMENDED for fail-OPEN hooks (set -e would break fail-OPEN).

# Source shared helper library
. "$(dirname "$0")/_lib.sh" && read_constants

# STEP -1: Capture stdin before any parsing (stdin can only be read once)
STDIN=$(cat)

# STEP 0.5: Pollution-score writer (Plan B — runs on every prompt submit, fail-OPEN)
# T-00 spike confirmed: SessionStart does not provide transcript_path, so the writer
# lives here. Score written before the exemption check so it fires on all prompts.
(
    _ups_tp=$(printf '%s' "$STDIN" | jq -r '.transcript_path // empty' 2>/dev/null) || true
    _ups_sid=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || true
    if [ -n "$_ups_tp" ] && [ -r "$_ups_tp" ]; then
        _ups_score=$(compute_pollution_score "$_ups_tp") || true
        if [ -n "$_ups_score" ]; then
            _ups_cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || true
            [ -z "$_ups_cwd" ] && _ups_cwd="$PWD"
            _ups_mem="${_ups_cwd}/.workflow_artifacts/memory"
            _ups_session=$(find "${_ups_mem}/sessions/" -name "$(date +%Y-%m-%d)-*.md" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)
            if [ -n "$_ups_session" ] && [ -f "$_ups_session" ]; then
                sed -i.bak '/^pollution_score:/d' "$_ups_session" 2>/dev/null && \
                  rm -f "${_ups_session}.bak" 2>/dev/null || true
                printf 'pollution_score: %s\n' "$_ups_score" >> "$_ups_session" 2>/dev/null || true
            else
                mkdir -p "$_ups_mem" 2>/dev/null || true
                printf '%s\n' "$_ups_score" > "${_ups_mem}/pollution-score-latest.txt" 2>/dev/null || true
            fi
            # PostCompact sentinel: if auto-compaction occurred, consume the sentinel.
            # The compacted transcript is naturally small so _ups_score above is already
            # the post-compact value — no recomputation needed. Guard: skip if no session_id.
            if [ -n "$_ups_sid" ]; then
                _ups_postcompact="${_ups_mem}/postcompact-reset-${_ups_sid}.txt"
                if [ -f "$_ups_postcompact" ]; then
                    trash_move "$_ups_postcompact" "$_ups_mem" 2>/dev/null || true
                    # Also expire defer marker on post-compact (meaningful work boundary)
                    _ups_defer="${_ups_mem}/checkpoint-defer-${_ups_sid}.txt"
                    [ -f "$_ups_defer" ] && trash_move "$_ups_defer" "$_ups_mem" 2>/dev/null || true
                fi
            fi
        fi
    fi
) 2>/dev/null || true

# STEP 0: Recovery-command exemption
# Extract prompt field (POSIX-portable; avoid echo's non-portable behavior)
prompt=$(printf '%s' "$STDIN" | jq -r '.prompt // empty' 2>/dev/null) || exit 0

# Strip ALL leading whitespace (including newlines, carriage returns, tabs)
# then extract first whitespace-delimited token (the command token).
# NOTE: sed '^' matches line-by-line; a leading newline creates an empty first
# line that `^[[:space:]]+` cannot strip. tr converts newlines/CRs to spaces
# first so the whole prompt is a single-line string before sed+awk processing.
cmd=$(printf '%s' "$prompt" | tr '\n\r' '  ' | sed -E 's/^[[:space:]]+//' | awk '{print $1}')

# Extract second token for /checkpoint --purge discrimination
arg2=$(printf '%s' "$prompt" | tr '\n\r' '  ' | sed -E 's/^[[:space:]]+//' | awk '{print $2}')

# Exact-token match — exempt-list per quoin/CLAUDE.md ### Hooks deployed by quoin
case "$cmd" in
  /compact|/clear|/help)
    exit 0
    ;;
  /checkpoint)
    case "$arg2" in
      --purge)
        # NOT exempt — destructive subcommand falls through to threshold logic
        # (Q-01 RESOLVED option (b): /checkpoint --purge blocked at >=95% utilization)
        ;;
      *)
        # All other /checkpoint subcommands exempt (no-arg, --restore, future args)
        exit 0
        ;;
    esac
    ;;
esac

# STEP 1: Read transcript path
transcript_path=$(printf '%s' "$STDIN" | jq -r '.transcript_path // empty' 2>/dev/null) || exit 0
[ -z "$transcript_path" ] && exit 0

# STEP 2: Compute utilization (returns basis-point integer 0..10000)
util=$(compute_utilization "$transcript_path") || exit 0
[ -z "$util" ] && exit 0

# STEP 3: Branch on utilization
if [ "$util" -lt "$STOP_BPS" ]; then
  # Branch (1): below advisory threshold — transparent passthrough
  exit 0
elif [ "$util" -ge "$STOP_BPS" ] && [ "$util" -lt "$BLOCK_BPS" ]; then
  # Branch (2): advisory range (STOP_BPS..BLOCK_BPS-1) — non-blocking advisory
  # Defer-marker guard: re-parse cwd+session_id from stdin (cheap; $STDIN already in memory)
  # These variables are NOT yet acquired — they are only parsed inside the BLOCK branch (lines below).
  _adv_cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null)
  [ -z "$_adv_cwd" ] && _adv_cwd="$PWD"
  _adv_sid=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null)
  if [ -n "$_adv_sid" ]; then
    _adv_defer="${_adv_cwd}/.workflow_artifacts/memory/checkpoint-defer-${_adv_sid}.txt"
    [ -f "$_adv_defer" ] && exit 0
  fi
  # Defer marker not set — emit advisory
  pct_int=$((util / 100))
  pct_dec=$(printf '%02d' $((util % 100)))
  printf '{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "context at %d.%s%% — consider running /checkpoint and starting a fresh session"}}\n' \
    "$pct_int" "$pct_dec"
  exit 0
else
  # Branch (3): block range (>= BLOCK_BPS)
  # Error-ordering invariant: block JSON emitted ONLY AFTER pending-prompt file is written.
  # If any step fails, exit 0 (fail-OPEN — do NOT lose the user's prompt).

  # STEP A: Re-parse session_id (may already have prompt from STEP 0)
  session_id=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || exit 0

  # STEP B-validate: session_id must be non-empty (discriminant collapses without it)
  [ -z "$session_id" ] && exit 0

  # STEP B: Compute pending-prompt path
  cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
  [ -z "$cwd" ] && cwd="$PWD"
  pending_prompt_file="${cwd}/.workflow_artifacts/memory/pending-prompt-${session_id}.txt"

  # Ensure directory exists
  mkdir -p "${cwd}/.workflow_artifacts/memory" 2>/dev/null || exit 0

  # STEP C: Append blocked prompt to pending-prompt file
  # Uses append (>>) not overwrite (>) so multiple parallel agent completions accumulate.
  # Each entry is prefixed with a === BLOCKED PROMPT [<timestamp>] === header.
  # Migration: if the file exists in legacy raw-text format (no header), convert it
  # to headered format on first append so no prior content is dropped.
  _timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || _timestamp="unknown"
  if [ -f "$pending_prompt_file" ] && ! head -1 "$pending_prompt_file" 2>/dev/null | grep -q '^=== BLOCKED PROMPT'; then
    _legacy=$(cat "$pending_prompt_file" 2>/dev/null)
    {
      printf '=== BLOCKED PROMPT [legacy-pre-migration] ===\n'
      printf '%s\n' "$_legacy"
      printf '=== BLOCKED PROMPT [%s] ===\n' "$_timestamp"
      printf '%s\n' "$prompt"
    } > "$pending_prompt_file" 2>/dev/null || exit 0
  else
    {
      printf '=== BLOCKED PROMPT [%s] ===\n' "$_timestamp"
      printf '%s\n' "$prompt"
    } >> "$pending_prompt_file" 2>/dev/null || exit 0
  fi

  # STEP D: Emit block JSON (only reaches here if STEP C succeeded)
  pct_int=$((util / 100))
  pct_dec=$(printf '%02d' $((util % 100)))
  printf '{"decision": "block", "reason": "context at %d.%s%% — your prompt was saved to pending-prompt-%s.txt; run /checkpoint --restore in a fresh session"}\n' \
    "$pct_int" "$pct_dec" "$session_id"
  exit 0
fi
