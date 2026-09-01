#!/bin/sh
# POSIX-sh reader for run-state-{task}.json records. No python3, no jq.
#
# Usage: run_state_read.sh MEMORY_DIR KEY [KEY...]
#
# Scans MEMORY_DIR for run-state-*.json records, filters to those that are
# both fresh (mtime) and eligible (active + schema known), picks the
# freshest eligible record, reads it once, then extracts the requested keys
# in order as "key=value" lines on stdout.
#
# Absence (no eligible record) prints nothing and exits 0 -- callers fall
# through to the next precedence tier. Any unexpected condition is also
# fail-open: nothing on stdout, exit 0.

MEMORY_DIR="$1"
shift

STALE_DAYS="${QUOIN_RUN_STATE_STALE_DAYS:-1}"

[ -n "$MEMORY_DIR" ] || exit 0
[ -d "$MEMORY_DIR" ] || exit 0

# 1. day-granular freshness pre-filter (deliberately over-inclusive; the
#    exact gate lives in run_state.py --max-age-days). mtime, not
#    updated_at -- no date arithmetic in sh.
candidates=$(find "$MEMORY_DIR" -maxdepth 1 -name 'run-state-*.json' -mtime -$((STALE_DAYS + 1)) 2>/dev/null)

# 2. candidate filter -- active AND schema-known, both here, before
#    selection. A schema-forward record is skipped like any other
#    non-candidate; it never aborts the scan.
#    NOTE: MEMORY_DIR can contain spaces (a nested-project-root path does in
#    this environment). Default IFS word-splitting on $candidates/$eligible
#    would silently break such paths, so IFS is pinned to newline-only for
#    every unquoted expansion of a find-produced file list below, and
#    restored immediately after each such use.
NL='
'
eligible=""
OLD_IFS=$IFS
IFS=$NL
for f in $candidates; do
    IFS=$OLD_IFS
    grep -q '"active": true' "$f" 2>/dev/null || { IFS=$NL; continue; }
    sch=$(sed -n '/"schema"/{p;q;}' "$f" 2>/dev/null | tr -dc '0-9')
    if [ -z "$sch" ]; then IFS=$NL; continue; fi
    if ! [ "$sch" -le 1 ] 2>/dev/null; then IFS=$NL; continue; fi
    if [ -z "$eligible" ]; then
        eligible="$f"
    else
        eligible="$eligible$NL$f"
    fi
    IFS=$NL
done
IFS=$OLD_IFS

[ -n "$eligible" ] || exit 0

# 3. freshest eligible wins. IFS=newline-only so `ls -t $eligible` splits on
#    the record separators only, never on spaces inside a path.
IFS=$NL
best=$(ls -t $eligible 2>/dev/null | head -n 1)
IFS=$OLD_IFS

[ -n "$best" ] || exit 0

# 4. one read of the chosen file into a variable -- never re-open per key.
snapshot=$(cat "$best" 2>/dev/null)

[ -n "$snapshot" ] || exit 0

# 5. extract each requested key from the snapshot, one key per line, in
#    the order requested on the command line.
#    ALPHABET: the writer's sanitization guarantees the file contains no
#    backslash byte at all -- '"' -> "'", '\' -> '/', every C0/DEL char ->
#    space, ensure_ascii=False -- so this extractor never meets an escape
#    sequence and does no unescaping.
#    ORDERING: strip the structural trailing comma BEFORE the quotes. The
#    closing quote is what distinguishes a structural comma from a comma
#    that is the last character of the value itself; stripping quotes
#    first silently truncates any value ending in ','.
for key in "$@"; do
    val=$(printf '%s\n' "$snapshot" | sed -n "/\"$key\"/{p;q;}" | sed 's/^[^:]*: *//; s/,$//; s/^"//; s/"$//')
    printf '%s=%s\n' "$key" "$val"
done

exit 0
