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
                    # Trash-moves: postcompact-reset-${_ups_sid}.txt and checkpoint-defer-${_ups_sid}.txt.
                    # Preserved (intentionally NOT moved here): compact-happened-${_ups_sid}.txt (read by /checkpoint Step 1.4).
                    trash_move "$_ups_postcompact" "$_ups_mem" 2>/dev/null || true
                    # Also expire defer marker on post-compact (meaningful work boundary)
                    _ups_defer="${_ups_mem}/checkpoint-defer-${_ups_sid}.txt"
                    [ -f "$_ups_defer" ] && trash_move "$_ups_defer" "$_ups_mem" 2>/dev/null || true
                fi
            fi
        fi
    fi
) 2>/dev/null || true

# STEP 0.7: Recent-session tracking + idle flag
(
    _rs_sid=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || true
    _rs_cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || true
    [ -z "$_rs_cwd" ] && _rs_cwd="$PWD"
    [ -z "$_rs_sid" ] && exit 0

    _rs_mem="${_rs_cwd}/.workflow_artifacts/memory"
    mkdir -p "$_rs_mem" 2>/dev/null || exit 0
    _rs_file="${_rs_mem}/recent-sessions.md"
    _rs_now=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || _rs_now=$(date +%Y-%m-%dT%H:%M:%SZ)

    # Idle check: look for previous entry for this session_id
    _rs_idle=0
    if [ -f "$_rs_file" ]; then
        _rs_prev=$(grep " | ${_rs_sid}$" "$_rs_file" 2>/dev/null | tail -1)
        if [ -n "$_rs_prev" ]; then
            _rs_prev_ts=$(printf '%s' "$_rs_prev" | awk '{print $1}')
            _rs_prev_epoch=$(python3 -c "
import sys, datetime
ts = sys.argv[1].replace('Z', '+00:00')
try:
    d = datetime.datetime.fromisoformat(ts)
    print(int(d.timestamp()))
except Exception:
    sys.exit(1)
" "$_rs_prev_ts" 2>/dev/null) || _rs_prev_epoch=0
            _rs_now_epoch=$(python3 -c "import time; print(int(time.time()))" 2>/dev/null) || _rs_now_epoch=0
            if [ -n "$_rs_prev_epoch" ] && [ "$_rs_prev_epoch" -gt 0 ] && [ "$_rs_now_epoch" -gt 0 ]; then
                _rs_gap=$(( _rs_now_epoch - _rs_prev_epoch ))
                [ "$_rs_gap" -gt 3600 ] && _rs_idle=1
            fi
        fi
    fi

    # Append current entry (unconditional)
    printf '%s | %s\n' "$_rs_now" "$_rs_sid" >> "$_rs_file" 2>/dev/null || true

    # Write idle flag file if idle gap detected
    if [ "$_rs_idle" -eq 1 ]; then
        printf '%s\n' "$_rs_now" > "${_rs_mem}/idle-advisory-pending-${_rs_sid}.txt" 2>/dev/null || true
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

# STEP 0.9: Idle-session advisory (parent shell, after STEP 0 exemption check)
_idle_cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null)
[ -z "$_idle_cwd" ] && _idle_cwd="$PWD"
_idle_sid=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$_idle_sid" ]; then
    _idle_flag="${_idle_cwd}/.workflow_artifacts/memory/idle-advisory-pending-${_idle_sid}.txt"
    if [ -f "$_idle_flag" ]; then
        rm -f "$_idle_flag" 2>/dev/null || true
        printf '{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[quoin-idle] This session has been idle for over 1 hour. Consider starting a fresh session to keep token usage low. Run /continue_work to resume context in a new session."}}\n'
        exit 0
    fi
fi

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
  # Task-notification detection (T-03): background subagent completions (wrapped in
  # <task-notification>...</task-notification> tags) are marked [non-replayable:task-notification]
  # in the header so restore CASE B excludes them from 'all' replay while preserving
  # the audit trail. Users can still replay them by explicit single-number selection.
  _timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || _timestamp="unknown"
  _is_task_notification=0
  case "$prompt" in *'<task-notification>'*) _is_task_notification=1 ;; esac
  if [ "$_is_task_notification" -eq 1 ]; then
    _prompt_header="=== BLOCKED PROMPT [${_timestamp}] [non-replayable:task-notification] ==="
  else
    _prompt_header="=== BLOCKED PROMPT [${_timestamp}] ==="
  fi
  if [ -f "$pending_prompt_file" ] && ! head -1 "$pending_prompt_file" 2>/dev/null | grep -q '^=== BLOCKED PROMPT'; then
    _legacy=$(cat "$pending_prompt_file" 2>/dev/null)
    {
      printf '=== BLOCKED PROMPT [legacy-pre-migration] ===\n'
      printf '%s\n' "$_legacy"
      printf '%s\n' "$_prompt_header"
      printf '%s\n' "$prompt"
    } > "$pending_prompt_file" 2>/dev/null || exit 0
  else
    {
      printf '%s\n' "$_prompt_header"
      printf '%s\n' "$prompt"
    } >> "$pending_prompt_file" 2>/dev/null || exit 0
  fi

  # STEP C2: Hook forced minimal save (T-02) — write skeleton checkpoint + pending-restore sentinel.
  # Pure bash; fail-OPEN: failures here do NOT prevent STEP D block JSON emission.
  # Error-ordering invariant preserved: STEP C2 is strictly between STEP C and STEP D.
  # Atomic writes: skeleton and sentinel both written via tmp+mv (mirrors precompact.sh:216-221).
  # PID suffix ($$) in skeleton filename prevents same-minute filename collision under
  # parallel block fires (same session_id, concurrent task-notifications).
  # A3 guard: if pending-restore-${session_id}.txt already exists, skip the skeleton write
  # to preserve the higher-quality anchor from a prior voluntary or precompact save.
  _blocksave_ok=0
  _pr_file="${cwd}/.workflow_artifacts/memory/pending-restore-${session_id}.txt"
  if [ -f "$_pr_file" ]; then
    _blocksave_ok=1  # A3 guard: valid sentinel already exists; preserve it
  else
    _cp_dir="${cwd}/.workflow_artifacts/memory/checkpoints"
    if mkdir -p "$_cp_dir" 2>/dev/null; then
      _now=$(date -u +%Y-%m-%dT%H%M 2>/dev/null) || _now="0000-00-00T0000"
      _date=$(printf '%s' "$_now" | cut -dT -f1)
      _hhmm=$(printf '%s' "$_now" | cut -dT -f2)
      _ts_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || _ts_iso="unknown"
      _ss_dir="${cwd}/.workflow_artifacts/memory/sessions"
      _latest_ss=$(ls -t "$_ss_dir"/*.md 2>/dev/null | head -1)
      _task="unknown-task"
      [ -n "$_latest_ss" ] && _task=$(basename "$_latest_ss" .md | sed 's/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-//')
      _branch="unknown"
      command -v git >/dev/null 2>&1 && _b=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null) && _branch="$_b"
      _plan=$(find "${cwd}/.workflow_artifacts" -name current-plan.md -exec ls -t {} + 2>/dev/null | head -1)
      _arch=$(find "${cwd}/.workflow_artifacts" -name architecture.md -exec ls -t {} + 2>/dev/null | head -1)
      _cp_file="${_cp_dir}/${_date}T${_hhmm}-$$-${_task}-blocksave.md"
      _cp_tmp="${_cp_file}.tmp"
      {
        printf '## Status\nblock-hook forced save (context overflow)\n\n'
        printf '## Current stage\n(unknown - forced save)\n\n'
        printf '## Active task\n%s\n\n' "$_task"
        printf '## Branch\n%s\n\n' "$_branch"
        printf '## Session ID\n%s\n\n' "$session_id"
        printf '## Saved at\n%s\n\n' "$_ts_iso"
        printf '## In-flight artifacts\n- current-plan.md: %s\n- architecture.md: %s\n- session-state: %s\n\n' \
          "${_plan:-(none found)}" "${_arch:-(none found)}" "${_latest_ss:-(none found)}"
        printf '## Restore hint\nRun /checkpoint --restore in a fresh session to resume task %s from branch %s.\n' \
          "$_task" "$_branch"
      } > "$_cp_tmp" 2>/dev/null && mv "$_cp_tmp" "$_cp_file" 2>/dev/null && {
        printf '%s\n' "$_cp_file" > "${_pr_file}.tmp" 2>/dev/null \
          && mv "${_pr_file}.tmp" "$_pr_file" 2>/dev/null \
          && _blocksave_ok=1
      }
      [ "$_blocksave_ok" -eq 1 ] || printf '[quoin-ups] WARNING: block-path skeleton save failed; pending-prompt still saved\n' >&2
    fi
  fi
  # fall through to STEP D regardless of _blocksave_ok — NEVER exit 0 before STEP D

  # STEP D: Emit block JSON (only reaches here if STEP C succeeded)
  # Message reflects actual saved state (_blocksave_ok=1: fresh skeleton+sentinel written;
  # _blocksave_ok=0: pre-existing sentinel or skeleton save failed but prompt is saved).
  pct_int=$((util / 100))
  pct_dec=$(printf '%02d' $((util % 100)))
  if [ "$_blocksave_ok" -eq 1 ]; then
    _restore_note="restore state saved (checkpoint + pending-restore sentinel)"
  else
    _restore_note="restore state is available (if a prior save exists)"
  fi
  printf '{"decision": "block", "reason": "context at %d.%s%% — your prompt was saved to pending-prompt-%s.txt; %s; run /checkpoint --restore in a fresh session"}\n' \
    "$pct_int" "$pct_dec" "$session_id" "$_restore_note"
  exit 0
fi
