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
cwd=$(resolve_project_root "$cwd")

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

# === S-5 discovery-staleness banner ===
# Runs after S-4. Calls discovery_staleness.py (deployed wrapper) via hook-relative path.
# Fail-OPEN: any error (python missing, script absent, non-zero-other) → no banner, continue.
# Exit codes: 0=fresh/disabled (no banner), 10=stale, 11=absent, 12=serena-present-but-stale.
# Dedup sentinel: mirrors S-4 pattern exactly, including stat -f %m fallback.

_disc_banner=""
_DISC_SENTINEL="${TMPDIR:-/tmp}/quoin-s5-staleness-banner-$(date -u +%Y%m%d).tmp"

# Dedup check: skip if sentinel fired within the last 300 seconds
if [ -f "$_DISC_SENTINEL" ]; then
  _disc_sentinel_mtime=$(python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$_DISC_SENTINEL" 2>/dev/null \
    || stat -f %m "$_DISC_SENTINEL" 2>/dev/null \
    || echo 0)
  _disc_sentinel_age=$(( $(date +%s) - _disc_sentinel_mtime ))
  if [ "$_disc_sentinel_age" -lt 300 ]; then
    _DISC_SKIP_S5=1
  fi
fi

if [ "${_DISC_SKIP_S5:-0}" = "0" ]; then
  if command -v python3 >/dev/null 2>&1; then
    # env (QUOIN_DISCOVERY_STALE_DAYS, QUOIN_DISCOVERY_REFRESH_DISABLE) propagates to child
    python3 "$(dirname "$0")/../scripts/discovery_staleness.py" "$cwd" --quiet >/dev/null 2>&1
    _disc_rc=$?
  else
    _disc_rc=0   # no python → no signal → no banner (fail-OPEN)
  fi
  case "$_disc_rc" in
    10) _disc_banner="[quoin-S-5] Discovery memory may be stale — run /start_of_day or /discover to refresh. Set QUOIN_DISCOVERY_REFRESH_DISABLE=1 to silence." ;;
    11) _disc_banner="[quoin-S-5] No discovery memory found — run /discover to index the project." ;;
    12) _disc_banner="[quoin-S-5] Serena project memory is stale — run /start_of_day and choose 'Set up / Refresh Serena memory'. Set QUOIN_DISCOVERY_REFRESH_DISABLE=1 to silence." ;;
    *)  _disc_banner="" ;;   # 0 fresh/disabled, 2 error → silent (fail-OPEN)
  esac
  if [ -n "$_disc_banner" ]; then
    printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' "$_disc_banner"
    touch "$_DISC_SENTINEL" 2>/dev/null || true
  fi
fi
# === end S-5 discovery-staleness banner ===

# STEP 2: UUID-aware sweep of all 9 sentinel families.
# Tight window (SESSIONSTART_SWEEP_DAYS, default 1d) when current session is known;
# falls back to conservative STALE_DAYS (7d) age-only when session_id is empty (defensive — see D-02).
# NOTE (D-08): the tight window also applies to pending-restore/pending-resume-ref/mid-agent-handoff,
# so STEP 4's cross-session fallback now sees only <=1d non-current pending-restore anchors. This is
# an INTENTIONAL narrowing of the STEP 4 input set (NOT a no-op); the banner-rendering code below is
# byte-unchanged. Do NOT re-add any "STEP 3+ unchanged" claim.
# Safe for paths with spaces: IFS= read -r preserves the full path (verified on the "My Drive" root).
# Sentinel basenames are FAMILY-<uuid>.txt (no newlines), so the find|while-read pipe is newline-safe
# for this controlled filename set — diverges from the old -exec form but is correct here.
# (_lib.sh sourced once at sessionstart.sh:16, so sentinel_globs/trash_move are in scope; no per-file re-source.)
if [ -n "$session_id" ]; then
  _sweep_days="$SESSIONSTART_SWEEP_DAYS"
else
  _sweep_days="$STALE_DAYS"   # no anchor → conservative age-only (defensive, see D-02)
fi
sentinel_globs | while IFS= read -r _glob; do
  [ -n "$_glob" ] || continue
  find "$MEMORY_DIR" -maxdepth 1 -name "$_glob" -mtime +"$_sweep_days" 2>/dev/null | \
  while IFS= read -r _f; do
    [ -f "$_f" ] || continue
    _base=$(basename "$_f")
    # current-session protection: skip files ending in -SESSION_ID.txt
    if [ -n "$session_id" ] && [ "$_base" != "${_base%-${session_id}.txt}" ]; then
      continue
    fi
    trash_move "$_f" "$MEMORY_DIR" 2>/dev/null || true
  done
done 2>/dev/null || true

# STEP 3: Look for sentinel files (priority order: pending-restore > pending-resume-ref > mid-agent-handoff)
# Emit AT MOST ONE banner per session start.
pending_restore=""
pending_resume_ref=""
mid_agent_handoff=""
session_id_match="current-session"
banner_text=""
banner_type=""

# STEP 3a: Check for pending-restore (highest priority — direct resume)
if [ -n "$session_id" ] && [ -f "${MEMORY_DIR}/pending-restore-${session_id}.txt" ]; then
  pending_restore="${MEMORY_DIR}/pending-restore-${session_id}.txt"
  session_id_match="current-session"
fi

# STEP 3b: Check for pending-resume-ref (informational — load as background reference)
if [ -n "$session_id" ] && [ -f "${MEMORY_DIR}/pending-resume-ref-${session_id}.txt" ]; then
  pending_resume_ref="${MEMORY_DIR}/pending-resume-ref-${session_id}.txt"
fi

# STEP 3c: Check for mid-agent-handoff (advisory — skill was running at checkpoint)
if [ -n "$session_id" ] && [ -f "${MEMORY_DIR}/mid-agent-handoff-${session_id}.txt" ]; then
  mid_agent_handoff="${MEMORY_DIR}/mid-agent-handoff-${session_id}.txt"
fi

# STEP 4: Fallback to mtime-most-recent if no current-session match for pending-restore
# (UUID-shaped session_ids have no time-ordering; lex order is meaningless)
if [ -z "$pending_restore" ]; then
  most_recent=$(ls -t "${MEMORY_DIR}"/pending-restore-*.txt 2>/dev/null | head -1)
  if [ -n "$most_recent" ] && [ -f "$most_recent" ]; then
    pending_restore="$most_recent"
    session_id_match="mismatch-warning: surfaced from different session (mtime-most-recent fallback)"
  fi
fi

# STEP 5: Build banner text (AT MOST ONE banner; use highest-priority sentinel)
# Priority: pending-restore > pending-resume-ref > mid-agent-handoff
if [ -n "$pending_restore" ]; then
  sentinel_content=$(cat "$pending_restore" 2>/dev/null)
  if [ -n "$sentinel_content" ]; then
    banner_text="Pending restore detected. A /checkpoint --restore is recommended (checkpoint: ${sentinel_content} — session-id match: ${session_id_match})"
    banner_type="pending-restore"

    # === restore ground-truth backstop (IVG-139) ===
    # NOTE: intentionally NOT labeled "S-4"/"S-5" — this file already has an internal
    # "=== S-4 missing-EOD banner ===" block (:30) and "=== S-5 discovery-staleness banner ==="
    # block (:79) whose numbering is unrelated to architecture stage IDs; reusing either token
    # here would make it mean three different things in one file (critic round-1 m-1).
    # Advisory-only: append a task-context-mismatch WARN to the pending-restore banner by
    # reusing verify_claims.py check_side_effects(skill=checkpoint) UNCHANGED. WARN-not-block.
    # Fail-OPEN: any error/other-rc -> no suffix (SessionStart cannot block regardless).
    # Shared-namespace guard (critic round-1 M-1): the pending-restore sentinel family is
    # SHARED with /thorough_plan (thorough_plan_checkpoint.py:190-191 writes this same
    # sentinel, pointing at a fixed thorough-plan-progress-{sid}.md filename, :131). The
    # reused predicate is kind-blind and filename_task() on that filename shape NEVER equals
    # a real sessions/*.md task, so calling the predicate on it would ALWAYS emit
    # task_backstop: and ALWAYS warn — a false positive on every normal /thorough_plan
    # resume. Skip the predicate call entirely for that filename shape instead.
    _gt_cp=$(printf '%s' "$sentinel_content" | head -1)
    if [ -n "$_gt_cp" ] && [ -f "$_gt_cp" ] && command -v python3 >/dev/null 2>&1; then
      case "$(basename "$_gt_cp")" in
        thorough-plan-progress-*)
          : ;;  # /thorough_plan owns its own resume; not a /checkpoint task-mismatch signal
        *)
          _gt_json=$(python3 "$(dirname "$0")/../scripts/verify_claims.py" \
            --check-side-effects --skill checkpoint \
            --checkpoint-file "$_gt_cp" --project-root "$cwd" --json 2>/dev/null)
          _gt_rc=$?
          # WARN ONLY on a genuine task-context mismatch (task_backstop predicate) — never on
          # inflight_missing / checkpoint_file_missing / usage errors (R-04 false-positive guard).
          if [ "$_gt_rc" -eq 8 ] && printf '%s' "$_gt_json" | grep -q 'task_backstop:'; then
            banner_text="${banner_text} [quoin-IVG-139 WARN: task-context mismatch — this checkpoint's task differs from your freshest session-state; verify before /checkpoint --restore (advisory only; the /checkpoint picker makes the actual decision)]"
          fi
          ;;
      esac
    fi
    # === end restore ground-truth backstop (IVG-139) ===
  fi
elif [ -n "$pending_resume_ref" ]; then
  # Read prior_session_uuid and checkpoint_path from the sentinel
  ref_prior_uuid=$(grep '^prior_session_uuid=' "$pending_resume_ref" 2>/dev/null | cut -d= -f2)
  ref_checkpoint=$(grep '^checkpoint_path=' "$pending_resume_ref" 2>/dev/null | cut -d= -f2-)
  banner_text="Prior session loaded as reference. Checkpoint: ${ref_checkpoint:-unknown}. Run /checkpoint --restore only if you want to resume; otherwise this prior context is read-only background (prior session UUID: ${ref_prior_uuid:-unknown})."
  banner_type="pending-resume-ref"
elif [ -n "$mid_agent_handoff" ]; then
  # Read prior_session_uuid and active_skills from the sentinel
  handoff_uuid=$(grep '^prior_session_uuid=' "$mid_agent_handoff" 2>/dev/null | cut -d= -f2)
  handoff_skills=$(grep '^active_skills=' "$mid_agent_handoff" 2>/dev/null | cut -d= -f2-)
  banner_text="Mid-agent handoff detected: session ${handoff_uuid:-unknown} had active skill(s) [${handoff_skills:-unknown}] when paused. Inspect ${mid_agent_handoff} and decide whether to /checkpoint --restore, /clear and re-run, or abandon."
  banner_type="mid-agent-handoff"
fi

# STEP 6: Emit banner if any sentinel was found
if [ -n "$banner_text" ]; then
  printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' \
    "$banner_text"
fi

# === S-1 pollution-score writer (stub — populated by S-1) ===
# (intentionally empty; S-1 implementation extends this block)
