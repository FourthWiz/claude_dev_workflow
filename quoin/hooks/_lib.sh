#!/bin/sh
# _lib.sh — shared helper library for quoin hook scripts
# Sourced by userpromptsubmit.sh, precompact.sh, sessionstart.sh via:
#   . "$(dirname "$0")/_lib.sh"
#
# NOTE: This file is sourced, not executed — the shebang is a cosmetic uniformity
# hint for editor highlighting and CI uniformity, not execution semantics.
# Per MIN-4: sourced-file invariant is cosmetic; assertion is:
#   head -1 quoin/hooks/_lib.sh | grep -qE '^#!/bin/sh( |$)'
#
# FAIL-OPEN contract: every helper returns non-zero on failure so callers can
# exit 0 (no JSON output, no block). Do NOT use `set -e` in this file —
# set -e would propagate errors past fail-OPEN catch points in callers.
# If defensive scripting is desired, prefer per-statement `|| true` over set -e.

# SINGLE SOURCE OF TRUTH for the 9 sentinel families.
# Consumed by sessionstart.sh STEP 2. cleanup/SKILL.md and sleep/SKILL.md document
# the same list and MUST stay byte-identical (drift test: test_sentinel_family_parity.py).
#
# sentinel_globs — echo the 9 canonical family globs, one per line (no quoting).
# Order matches the cleanup allow-list order.
sentinel_globs() {
    printf '%s\n' \
        'pending-restore-*.txt' \
        'pending-prompt-*.txt' \
        'compact-happened-*.txt' \
        'mid-agent-handoff-*.txt' \
        'pending-resume-ref-*.txt' \
        'checkpoint-defer-*.txt' \
        'postcompact-reset-*.txt' \
        'checkpoint-pending-compact-*.txt' \
        'idle-advisory-pending-*.txt'  # orphans on idle-then-abandoned sessions (written userpromptsubmit.sh:99, deleted only on the next prompt of the SAME session at :144); included here so it is reclaimable — see plan D-06
}

# read_constants — sources env-var defaults for tunable constants.
# After calling, the following are exported:
#   BPT            — bytes per token (e.g., "8.0")
#   LIMIT          — effective context limit in tokens (e.g., 150000)
#   STOP_BPS       — stop/advisory threshold in basis-points (e.g., 7000)
#   BLOCK_BPS      — block threshold in basis-points (e.g., 9500)
#   STALE_DAYS     — sentinel staleness threshold in days (e.g., 7)
#   SESSIONSTART_SWEEP_DAYS — UUID-aware tight sweep window for sessionstart (default 1)
#   COMPACT_FIRST_BPS — /checkpoint high-util notice tier (e.g., 9000 = 90.00%)
#   PANIC_BPS      — /checkpoint panic/degraded-save tier (default 10000 = 100.00%)
#                    compute_utilization is unclamped so values >10000 are normal;
#                    PANIC_BPS=10000 correctly fires for all true overflow (>=100%).
read_constants() {
    BPT=${QUOIN_BYTES_PER_TOKEN:-8.0}
    LIMIT=${QUOIN_EFFECTIVE_CONTEXT_LIMIT:-150000}
    STOP_BPS=${QUOIN_STOP_BPS:-7000}
    BLOCK_BPS=${QUOIN_BLOCK_BPS:-9500}
    STALE_DAYS=${QUOIN_STALE_SENTINEL_DAYS:-7}
    SESSIONSTART_SWEEP_DAYS=${QUOIN_SESSIONSTART_SWEEP_DAYS:-1}
    COMPACT_FIRST_BPS=${QUOIN_COMPACT_FIRST_BPS:-9000}
    PANIC_BPS=${QUOIN_PANIC_BPS:-10000}
    export BPT LIMIT STOP_BPS BLOCK_BPS STALE_DAYS SESSIONSTART_SWEEP_DAYS COMPACT_FIRST_BPS PANIC_BPS
}

# compute_utilization <transcript_path> — returns a basis-point INTEGER (0..10000)
# representing the utilization of the effective context limit.
# Example: returns "8540" for 85.40% utilization.
#
# Uses POSIX awk for arithmetic (NOT bc — bc is not in POSIX core).
# 64-bit awk integers required: POSIX awk on darwin AND GNU defaults to 64-bit
# since ~2010, so no special configuration needed. Verified via boundary fixture:
# a 2.1 GB transcript size synthetic input produces a valid basis-point integer
# without overflow.
#
# Portability: wc -c < FILE works on darwin BSD AND GNU; do NOT use stat -c %s
# (GNU-only — explicitly rejected per architecture rev-6.1 MIN-1).
#
# Returns non-zero if transcript_path is empty or file is unreadable.
compute_utilization() {
    _transcript_path="$1"
    if [ -z "$_transcript_path" ] || ! [ -r "$_transcript_path" ]; then
        return 1
    fi
    _bytes=$(wc -c < "$_transcript_path" 2>/dev/null) || return 1
    # Remove leading whitespace from wc output (BSD wc includes leading spaces)
    _bytes=$(printf '%s' "$_bytes" | awk '{print $1}')
    # awk arithmetic: (bytes / bpt / limit) * 10000 → basis-point integer
    # BPT may be a decimal like "8.0"; awk handles floating-point naturally
    awk -v b="$_bytes" -v bpt="$BPT" -v lim="$LIMIT" \
        'BEGIN{ printf "%d\n", (b / bpt / lim) * 10000 }'
}

# compute_pollution_score <transcript_path> — returns an integer score.
# Formula: byte_size_kb + (agent_returns × 5) + (read_calls × 1) + (bash_calls × 1)
# where byte_size_kb = bytes / 1000 (integer division).
# Default threshold 5000 corresponds to ~5MB transcript or ~1MB + heavy tool use.
# jq preferred for precision; grep is the stdlib-only fallback.
# Returns non-zero exit if transcript_path is empty or unreadable.
compute_pollution_score() {
    _tp="$1"
    if [ -z "$_tp" ] || ! [ -r "$_tp" ]; then
        return 1
    fi
    _bytes=$(wc -c < "$_tp" 2>/dev/null) || return 1
    _bytes=$(printf '%s' "$_bytes" | awk '{print $1}')
    _kb=$((_bytes / 1000))

    _agent_count=0
    _read_count=0
    _bash_count=0
    if command -v jq > /dev/null 2>&1; then
        # Real Claude Code JSONL: tool_use entries are nested under assistant messages at
        # .message.content[].type == "tool_use" with .name (not a flat tool_result/tool_name).
        # Single jq pass extracts all tool names, then awk counts per name.
        _counts=$(jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "tool_use") | .name' "$_tp" 2>/dev/null | sort | uniq -c) || true
        _agent_count=$(printf '%s\n' "$_counts" | awk 'BEGIN{n=0} $2=="Agent"{n=$1} END{print n}')
        _read_count=$(printf '%s\n' "$_counts" | awk 'BEGIN{n=0} $2=="Read"{n=$1} END{print n}')
        _bash_count=$(printf '%s\n' "$_counts" | awk 'BEGIN{n=0} $2=="Bash"{n=$1} END{print n}')
    else
        # grep fallback: real transcripts have "name":"Agent" inside tool_use objects
        _agent_count=$(grep -c '"name"[[:space:]]*:[[:space:]]*"Agent"' "$_tp" 2>/dev/null || printf '0')
        _read_count=$(grep -c '"name"[[:space:]]*:[[:space:]]*"Read"' "$_tp" 2>/dev/null || printf '0')
        _bash_count=$(grep -c '"name"[[:space:]]*:[[:space:]]*"Bash"' "$_tp" 2>/dev/null || printf '0')
    fi

    awk -v kb="$_kb" -v ag="$_agent_count" -v rd="$_read_count" -v ba="$_bash_count" \
        'BEGIN{ printf "%d\n", kb + (ag * 5) + (rd * 1) + (ba * 1) }'
}

# trash_move <file> <trash_base> — move a file to the trash archive instead of deleting it.
# Creates <trash_base>/trash/<YYYY-MM-DD>/ and moves the file there.
# If a file with the same basename already exists in trash today, appends -1, -2, etc.
# Returns 0 on success. On failure: emits a one-line stderr warning and returns 1.
# POSIX sh compatible (no bash-isms).
# <trash_base> is typically ${cwd}/.workflow_artifacts/memory
trash_move() {
    _tm_file="$1"
    _tm_base="$2"
    [ -f "$_tm_file" ] || {
        printf '[quoin-trash] WARNING: trash-move failed for %s; source not found\n' "$_tm_file" >&2
        return 1
    }
    _tm_date=$(date -u +%Y-%m-%d 2>/dev/null) || _tm_date=$(date +%Y-%m-%d)
    _tm_dir="${_tm_base}/trash/${_tm_date}"
    mkdir -p "$_tm_dir" 2>/dev/null || true
    _tm_name=$(basename "$_tm_file")
    _tm_dest="${_tm_dir}/${_tm_name}"
    if [ -e "$_tm_dest" ]; then
        _tm_n=1
        while [ -e "${_tm_dir}/${_tm_name}-${_tm_n}" ]; do
            _tm_n=$((_tm_n + 1))
        done
        _tm_dest="${_tm_dir}/${_tm_name}-${_tm_n}"
    fi
    if mv "$_tm_file" "$_tm_dest" 2>/dev/null; then
        return 0
    else
        printf '[quoin-trash] WARNING: trash-move failed for %s; leaving in place\n' "$_tm_file" >&2
        return 1
    fi
}

# safe_jq_or_passthrough [jq-args]... — jq invocation with fail-OPEN.
# If jq is not on PATH, returns 1; caller should exit 0 (fail-OPEN).
# Usage: output=$(printf '%s' "$STDIN" | safe_jq_or_passthrough -r '.field // empty')
safe_jq_or_passthrough() {
    if ! command -v jq > /dev/null 2>&1; then
        return 1
    fi
    jq "$@"
}

# resolve_project_root <start_dir> — echo effective project root; always return 0.
# Precedence: OUTERMOST .workflow_artifacts/ (strictly < $HOME) > NEAREST .git (strictly < $HOME) > start_dir.
# EXCLUSIVE ceiling: $HOME and / bound the walk but are NEVER inspected as owners, NEVER returned.
resolve_project_root() {
    _rpr_start="$1"
    [ -n "$_rpr_start" ] || { printf '%s\n' "$_rpr_start"; return 0; }
    _rpr_ceiling="${HOME:-/}"
    # Pass 1: OUTERMOST artifacts owner STRICTLY BELOW ceiling.
    # Walk the FULL eligible chain, remembering the HIGHEST eligible hit.
    _rpr_best=""
    _rpr_cur="$_rpr_start"
    while [ -n "$_rpr_cur" ]; do
        [ "$_rpr_cur" = "$_rpr_ceiling" ] && break       # EXCLUSIVE: stop BEFORE inspecting $HOME
        [ "$_rpr_cur" = "/" ] && break                   # EXCLUSIVE: never inspect /
        [ -d "$_rpr_cur/.workflow_artifacts" ] && _rpr_best="$_rpr_cur"
        _rpr_parent=$(dirname "$_rpr_cur")
        [ "$_rpr_parent" = "$_rpr_cur" ] && break        # fixedpoint loop guard
        _rpr_cur="$_rpr_parent"
    done
    [ -n "$_rpr_best" ] && { printf '%s\n' "$_rpr_best"; return 0; }
    # Pass 2: NEAREST .git (dir OR file) STRICTLY BELOW ceiling.
    _rpr_cur="$_rpr_start"
    while [ -n "$_rpr_cur" ]; do
        [ "$_rpr_cur" = "$_rpr_ceiling" ] && break       # EXCLUSIVE: $HOME's .git never returned (CRIT-4)
        [ "$_rpr_cur" = "/" ] && break
        [ -e "$_rpr_cur/.git" ] && { printf '%s\n' "$_rpr_cur"; return 0; }
        _rpr_parent=$(dirname "$_rpr_cur")
        [ "$_rpr_parent" = "$_rpr_cur" ] && break
        _rpr_cur="$_rpr_parent"
    done
    # Pass 3: fall back to start (today's behavior; NEVER $HOME, NEVER /).
    printf '%s\n' "$_rpr_start"
    return 0
}
