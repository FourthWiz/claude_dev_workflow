#!/bin/sh
# pidfile_helpers.sh — shared pidfile lifecycle helper for quoin skills
# Sourced by SKILL.md §0c blocks via:
#   . ~/.claude/scripts/pidfile_helpers.sh
#
# NOTE: This file is sourced, not executed — the shebang is a cosmetic uniformity
# hint for editor highlighting and CI uniformity, not execution semantics.
# Per MIN-4: sourced-file invariant is cosmetic; assertion is:
#   head -1 quoin/scripts/pidfile_helpers.sh | grep -qE '^#!/bin/sh( |$)'
#
# Pidfile directory: .workflow_artifacts/memory/sessions/
# Pidfile format: <skill-name>-<PID>.pidfile.lock
# Purpose: let precompact.sh hook know which heavy skills are active.
# precompact.sh never blocks — it always allows auto-compaction
# (precompact.sh:5-6, :14); pidfile presence instead selects row 2 of its
# three-row truth table (precompact.sh:323, :506-507): a deterministic
# checkpoint is written, with no pending-restore sentinel, so the workflow
# continues uninterrupted.
#
# FAIL-OPEN: all functions return 0 on failure (non-blocking) EXCEPT
# pidfile_acquire, which returns 0 always (callers proceed without pidfile
# protection if acquire fails — logged to stderr).

_PIDFILE_DIR=".workflow_artifacts/memory/sessions"

# pidfile_acquire <skill-name> — write a pidfile for this skill + PID.
# Creates .workflow_artifacts/memory/sessions/<skill-name>-$$.pidfile.lock
# with current PID + timestamp + skill name.
# Race-safe: uses mkdir-style atomicity (creates a unique PID-keyed file;
# no two processes share the same PID at the same time on a single host).
# Returns 0 always (fail-OPEN: even if the write fails, the caller proceeds).
pidfile_acquire() {
    _skill="$1"
    if [ -z "$_skill" ]; then
        printf '[quoin-S-2: pidfile_acquire: skill name required; proceeding without lifecycle protection]\n' >&2
        return 0
    fi
    _pidfile="${_PIDFILE_DIR}/${_skill}-$$.pidfile.lock"
    # Ensure directory exists (best-effort)
    mkdir -p "$_PIDFILE_DIR" 2>/dev/null || true
    # Write pidfile atomically (each PID gets its own file — no collision)
    printf 'skill=%s\npid=%d\ntimestamp=%s\n' \
        "$_skill" "$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        > "$_pidfile" 2>/dev/null || {
        printf '[quoin-S-2: pidfile_helpers unavailable; proceeding without lifecycle protection]\n' >&2
    }
    return 0
}

# pidfile_release <skill-name> — delete this skill's pidfile (by PID).
# Idempotent: no-op if pidfile is missing.
pidfile_release() {
    _skill="$1"
    if [ -z "$_skill" ]; then
        return 0
    fi
    _pidfile="${_PIDFILE_DIR}/${_skill}-$$.pidfile.lock"
    rm -f "$_pidfile" 2>/dev/null || true
    return 0
}

# pidfile_active_skills — prints lines of the form "skill PID" for each
# currently-held pidfile entry. Used by precompact.sh for escalation.
# Silently ignores unreadable files.
pidfile_active_skills() {
    _pattern="${_PIDFILE_DIR}/*.pidfile.lock"
    # shellcheck disable=SC2086
    for _f in $_pattern; do
        [ -f "$_f" ] || continue
        _s=$(grep '^skill=' "$_f" 2>/dev/null | cut -d= -f2)
        _p=$(grep '^pid=' "$_f" 2>/dev/null | cut -d= -f2)
        if [ -n "$_s" ] && [ -n "$_p" ]; then
            printf '%s %s\n' "$_s" "$_p"
        fi
    done
}

# pidfile_cleanup_stale — deletes pidfiles whose PID is no longer running.
# Uses `kill -0 <PID>` to check liveness (POSIX; non-destructive signal).
# Called opportunistically on acquire or explicitly.
pidfile_cleanup_stale() {
    _pattern="${_PIDFILE_DIR}/*.pidfile.lock"
    # shellcheck disable=SC2086
    for _f in $_pattern; do
        [ -f "$_f" ] || continue
        _p=$(grep '^pid=' "$_f" 2>/dev/null | cut -d= -f2)
        if [ -n "$_p" ] && ! kill -0 "$_p" 2>/dev/null; then
            rm -f "$_f" 2>/dev/null || true
        fi
    done
}
