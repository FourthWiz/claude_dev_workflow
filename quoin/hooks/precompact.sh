#!/bin/sh
# precompact.sh — PreCompact hook for quoin workflow isolation
# Deployed to ~/.claude/hooks/ by bash install.sh
#
# Contract: fires on PreCompact event (auto compaction only — manual /compact
# is passed through). Saves checkpoint state. If skill pidfiles are active:
# allows compaction (workflow continues uninterrupted). If no pidfiles (direct
# conversation): writes pending-restore sentinel and blocks compaction.
# Fail-OPEN: any error → exit 0, no output (compaction proceeds unblocked).
#
# Shebang assertion: head -1 ... | grep -qE '^#!/bin/sh( |$)'
# No-args form RECOMMENDED for fail-OPEN hooks (set -e would break fail-OPEN).

# Source shared helper library
. "$(dirname "$0")/_lib.sh" && read_constants

# STEP -1: Capture stdin before any parsing (stdin can only be read once)
STDIN=$(cat)

# STEP 1: Parse trigger field
# If jq is absent, safe_jq_or_passthrough returns non-zero → fail-OPEN
trigger=$(printf '%s' "$STDIN" | jq -r '.trigger // empty' 2>/dev/null) || exit 0

# Manual /compact: pass through immediately — do not block user-initiated compaction
if [ "$trigger" = "manual" ]; then
  exit 0
fi

# Override: user opted in to allow compact even during auto trigger
if [ "${CLAUDE_ALLOW_COMPACT:-0}" = "1" ]; then
  exit 0
fi

# Parse remaining fields
session_id=$(printf '%s' "$STDIN" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
cwd=$(printf '%s' "$STDIN" | jq -r '.cwd // empty' 2>/dev/null) || exit 0
[ -z "$cwd" ] && cwd="$PWD"
transcript_path=$(printf '%s' "$STDIN" | jq -r '.transcript_path // empty' 2>/dev/null) || exit 0

# Override: .allow-compact marker file in cwd
if [ -f "${cwd}/.allow-compact" ]; then
  exit 0
fi

# Require session_id for pending-restore discriminant (CRIT-3 fix)
# Without session_id the sentinel cannot be matched in sessionstart / /checkpoint --restore
if [ -z "$session_id" ]; then
  printf '[quoin-precompact] WARNING: session_id absent from stdin; cannot write session-scoped sentinel; proceeding fail-OPEN\n' >&2
  exit 0
fi

# Pre-compute sentinel path so we can check it before writing a new checkpoint (A3 fix)
MEMORY_DIR="${cwd}/.workflow_artifacts/memory"
pending_restore_file="${MEMORY_DIR}/pending-restore-${session_id}.txt"

# Pre-initialize pidfile_info to "none" so STEP 4 branching is safe in the early-skip path.
# The early-skip path (sentinel already exists) skips the else block entirely, so pidfile
# detection inside the else block never runs — pidfile_info stays "none" → block.
# This is the intentional conservative behavior: if the user ran /checkpoint manually,
# they are managing the session themselves. The else block overwrites this "none" if
# pidfiles are found in the full checkpoint path.
pidfile_info="none"

# STEP 2: Save checkpoint state (paths-not-content rule)
# Skip entirely if voluntary /checkpoint already ran this session — preserve the better sentinel
# and avoid creating an orphaned -precompact.md file (A3 fix)
if [ -f "$pending_restore_file" ]; then
  printf '[quoin-precompact] INFO: pending-restore sentinel already exists (voluntary /checkpoint was run earlier in this session); skipping checkpoint write to avoid orphaned -precompact.md file\n' >&2
else

CHECKPOINT_DIR="${cwd}/.workflow_artifacts/memory/checkpoints"
mkdir -p "$CHECKPOINT_DIR" 2>/dev/null || {
  printf '[quoin-precompact] WARNING: cannot create checkpoint dir; falling back fail-OPEN\n' >&2
  exit 0
}

checkpoint_date=$(date -u +%Y-%m-%d 2>/dev/null) || checkpoint_date="unknown-date"

# Determine active task name from session-state filenames (best-effort)
session_state_dir="${cwd}/.workflow_artifacts/memory/sessions"
active_task="unknown-task"
latest_session=""
if [ -d "$session_state_dir" ]; then
  # Most recently modified session state file (ls -t) — mtime-most-recent
  latest_session=$(ls -t "$session_state_dir"/*.md 2>/dev/null | head -1)
  if [ -n "$latest_session" ]; then
    # Extract task name from filename pattern: YYYY-MM-DD-<task-name>.md
    session_base=$(basename "$latest_session" .md)
    # Strip leading date prefix (YYYY-MM-DD-)
    active_task=$(printf '%s' "$session_base" | sed 's/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-//')
  fi
fi

# Collect active pidfiles (overwrite pre-initialized "none" if any are found)
if ls "$session_state_dir"/*.pidfile.lock > /dev/null 2>&1; then
  pidfile_info=$(ls "$session_state_dir"/*.pidfile.lock 2>/dev/null | xargs -I{} basename {} 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
  [ -z "$pidfile_info" ] && pidfile_info="none"
fi

# Determine current git branch (best-effort)
current_branch="unknown"
if command -v git > /dev/null 2>&1; then
  branch_out=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null) && current_branch="$branch_out"
fi

# Find most recent plan, architecture, critic-response, and review files
# Uses find -exec ls -t {} + for mtime sort — whitespace-safe (no word-splitting on paths)
# and no BSD-xargs empty-stdin hazard (A1 fix)
current_plan_path="(none found)"
architecture_path="(none found)"
latest_critic="(none found)"
latest_review="(none found)"
if [ -d "${cwd}/.workflow_artifacts" ]; then
  found_plan=$(find "${cwd}/.workflow_artifacts" -name "current-plan.md" \
    -exec ls -t {} + 2>/dev/null | head -1)
  [ -n "$found_plan" ] && current_plan_path="$found_plan"
  found_arch=$(find "${cwd}/.workflow_artifacts" -name "architecture.md" \
    -exec ls -t {} + 2>/dev/null | head -1)
  [ -n "$found_arch" ] && architecture_path="$found_arch"
  c=$(find "${cwd}/.workflow_artifacts" -name "critic-response-*.md" \
    -exec ls -t {} + 2>/dev/null | head -1)
  [ -n "$c" ] && latest_critic="$c"
  r=$(find "${cwd}/.workflow_artifacts" -name "review-*.md" \
    -exec ls -t {} + 2>/dev/null | head -1)
  [ -n "$r" ] && latest_review="$r"
fi

# Extract current phase from session-state ## Cost block (A2 fix)
# Handles bulleted format: - Phase: implement
current_phase="unknown"
if [ -n "$latest_session" ] && [ -f "$latest_session" ]; then
  current_phase=$(awk '/^## Cost/{f=1;next} f && /^[[:space:]]*-?[[:space:]]*Phase:/{sub(/^[[:space:]]*-?[[:space:]]*Phase:[[:space:]]*/,""); print; exit} f && /^## /{exit}' \
    "$latest_session" 2>/dev/null)
  [ -z "$current_phase" ] && current_phase="unknown"
fi

# Extract open questions and unfinished work from session-state (A2 fix)
# Guards: /^## / exits section; /^pollution_score:/ prevents trailing score line from leaking
open_questions=""
if [ -n "$latest_session" ] && [ -f "$latest_session" ]; then
  block=$(awk '/^## Open questions/{f=1;next} /^## /{if(f)exit} /^pollution_score:/{if(f)exit} f{print}' \
    "$latest_session" 2>/dev/null | sed '/^[[:space:]]*$/d')
  [ -n "$block" ] && open_questions="$block"
fi

unfinished_work=""
if [ -n "$latest_session" ] && [ -f "$latest_session" ]; then
  block=$(awk '/^## Unfinished work/{f=1;next} /^## /{if(f)exit} /^pollution_score:/{if(f)exit} f{print}' \
    "$latest_session" 2>/dev/null | sed '/^[[:space:]]*$/d')
  [ -n "$block" ] && unfinished_work="$block"
fi

checkpoint_file="${CHECKPOINT_DIR}/${checkpoint_date}-${active_task}-precompact.md"

# Write checkpoint (paths-not-content — never carry file contents)
# User-content fields (open_questions, unfinished_work) use placeholders to prevent
# shell expansion of $varname, backticks, or ${...} from session-state free-form text (A2 fix)
cat > "$checkpoint_file" 2>/dev/null << CPEOF
## Status
precompact-hook save (auto-compaction intercepted)

## Current stage
${current_phase}

## Active task
${active_task}

## Branch
${current_branch}

## Session ID
${session_id}

## Trigger
auto (active pidfiles at save time: ${pidfile_info})

## Active skills (pidfiles)
${pidfile_info}

## In-flight artifacts
- current-plan.md: ${current_plan_path}
- architecture.md: ${architecture_path}
- latest critic-response: ${latest_critic}
- latest review: ${latest_review}
- session-state: ${latest_session:-"(none found)"}
- transcript: ${transcript_path}

## Open questions
__OPEN_QUESTIONS_PLACEHOLDER__

## Unfinished work
__UNFINISHED_WORK_PLACEHOLDER__

## Restore hint
Run /checkpoint --restore in a fresh session to resume task '${active_task}' from branch '${current_branch}'.
CPEOF

# Substitute user-content placeholders via awk -v (no shell expansion of user content)
# Primary fix: atomic write with visible-failure discipline — no '|| true' swallowing.
# On any fill failure the heredoc-written file (with placeholders) is RETAINED (D-06):
# better to have a visible placeholder than to lose the checkpoint entirely.
_oq="${open_questions:-(none)}"
_uw="${unfinished_work:-(none)}"

awk -v oq="$_oq" -v uw="$_uw" '
  /^__OPEN_QUESTIONS_PLACEHOLDER__$/{print (oq=="" ? "(none)" : oq); next}
  /^__UNFINISHED_WORK_PLACEHOLDER__$/{print (uw=="" ? "(none)" : uw); next}
  {print}
' "$checkpoint_file" > "${checkpoint_file}.tmp" 2>/dev/null
_awk_exit=$?

if [ $_awk_exit -eq 0 ] && [ -s "${checkpoint_file}.tmp" ]; then
  # Temp file is non-empty and awk succeeded — rename with explicit error capture
  if mv -f "${checkpoint_file}.tmp" "$checkpoint_file" 2>/dev/null; then
    # SUCCESS: verify no placeholders remain (anchored grep)
    if grep -qE '^(__OPEN_QUESTIONS_PLACEHOLDER__|__UNFINISHED_WORK_PLACEHOLDER__)$' \
        "$checkpoint_file" 2>/dev/null; then
      # Rare: placeholders still in file after mv (content-check failure)
      printf '[quoin-precompact] WARNING: placeholder substitution incomplete in %s; checkpoint retained with placeholders (better than losing it)\n' "$checkpoint_file" >&2
      # Do NOT trash-move — user keeps the file, placeholders are visible
    fi
    # FALL THROUGH: success path, checkpoint_file is valid
  else
    # mv failed — clean up temp, warn, but KEEP the heredoc-written file with placeholders
    _mv_exit=$?
    printf '[quoin-precompact] WARNING: mv failed (exit %d) renaming %s; checkpoint retained with placeholder tokens\n' \
      "$_mv_exit" "${checkpoint_file}.tmp" >&2
    rm -f "${checkpoint_file}.tmp" 2>/dev/null || true
    # checkpoint_file remains as-is (with placeholders) — sentinel write still runs below
  fi
else
  # awk produced empty output or failed — compute tmp size safely
  _tmp_size=$(wc -c < "${checkpoint_file}.tmp" 2>/dev/null || echo 0)
  _tmp_size=${_tmp_size:-0}
  printf '[quoin-precompact] WARNING: placeholder fill failed (awk exit %d, tmp size %s); checkpoint retained with placeholder tokens\n' \
    "$_awk_exit" "$_tmp_size" >&2
  rm -f "${checkpoint_file}.tmp" 2>/dev/null || true
  # checkpoint_file remains as-is — sentinel write still runs below
fi

# Check if write succeeded
if [ ! -f "$checkpoint_file" ]; then
  printf '[quoin-precompact] WARNING: checkpoint write failed; proceeding fail-OPEN\n' >&2
  exit 0
fi

fi  # end: if [ ! -f "$pending_restore_file" ]

# STEP 4: Branch on pidfile presence
# If skills are running (pidfiles present): allow compact — workflow must continue.
# If no pidfiles (direct conversation): block — user must manually restore in fresh session.
# NOTE: when the pending_restore_file already exists (early-skip path at the top), pidfile_info
# stays "none" because the pidfile-collection block was skipped. The decision always falls
# through to block in that path — intentional conservative behavior: the user already ran
# /checkpoint manually, so they knew what they were doing.
#
# KNOWN LIMITATION: stale pidfiles
# The pidfile liveness check is NOT performed. If a skill crashed without releasing its
# .pidfile.lock file, pidfile_info will be non-"none" and the hook will emit "allow".
# Rationale: liveness checking (kill -0 <pid>) requires parsing the PID from the filename,
# a POSIX loop, and fragile format coupling. The crash-without-cleanup failure mode is rare
# and bounded — the checkpoint saved in STEP 2 is always available for recovery.
# To clean up after a crash: rm .workflow_artifacts/memory/sessions/*.pidfile.lock
if [ "$pidfile_info" != "none" ]; then
  printf '[quoin-precompact] INFO: skills running (%s); allowing auto-compact; checkpoint saved at %s\n' "$pidfile_info" "${checkpoint_file:-unknown}" >&2
  printf '{"decision": "allow"}\n'
else
  # Block path: no active skills detected (direct conversation mode).
  # STEP 3 (block path only): Write pending-restore sentinel.
  # Guard: [ -n "$checkpoint_file" ] ensures we only write in the full checkpoint path,
  # not the early-skip path where checkpoint_file is unset and the existing sentinel
  # is already correct — no need to overwrite it.
  if [ -n "$checkpoint_file" ]; then
    mkdir -p "$MEMORY_DIR" 2>/dev/null || true
    printf '%s\n' "$checkpoint_file" > "$pending_restore_file" 2>/dev/null || {
      printf '[quoin-precompact] WARNING: cannot write pending-restore sentinel; sessionstart hook cannot surface restore banner\n' >&2
      # Still block — checkpoint was written, just sentinel is missing
    }
  fi
  printf '[quoin-precompact] INFO: no active pidfiles → blocking auto-compaction (direct conversation mode); checkpoint saved at %s\n' "${checkpoint_file:-unknown}" >&2
  printf '{"decision": "block", "reason": "auto-compaction intercepted; session state saved automatically; start a fresh session and run /checkpoint --restore to resume"}\n'
fi
