#!/bin/sh
# POSIX-sh reader for a single run-state-{task}.json record. No python3, no jq.
#
# Usage: run_state_read.sh MEMORY_DIR TASK KEY [KEY...]
#
# Addresses run-state-$TASK.json directly (no directory scan across other
# tasks' records), checks it is fresh (mtime) and eligible (active + schema
# known), reads it once, then extracts the requested keys in order as
# "key=value" lines on stdout.
#
# Absence (no eligible record for TASK) prints nothing and exits 0 -- callers
# fall through to the next precedence tier. Any unexpected condition is also
# fail-open: nothing on stdout, exit 0.

MEMORY_DIR="$1"
shift
TASK="$1"
shift

# Numeric-validate the knob before it reaches a `find` predicate -- an
# unvalidated value here was an arithmetic-eval command-injection sink
# (`-mtime -$((STALE_DAYS + 1))`, e.g. `QUOIN_RUN_STATE_STALE_DAYS='q[$(...)]'`
# under a bash `/bin/sh`). Reject anything that is not a plain non-negative
# integer and fall back to the documented default of 1.
RAW_STALE_DAYS="${QUOIN_RUN_STATE_STALE_DAYS:-1}"
case "$RAW_STALE_DAYS" in
    ''|*[!0-9]*) STALE_DAYS=1 ;;
    *) STALE_DAYS="$RAW_STALE_DAYS" ;;
esac
# The character class above accepts a value like "08", which is a valid
# non-negative integer in decimal but not in the octal `$(( ))` treats a
# leading-zero literal as -- bash errors ("value too great for base") and
# dash silently misreads it ("010" as 8). Strip leading zeros (keeping a
# lone "0") before it reaches arithmetic expansion below. Pure-shell
# case/parameter-expansion loop -- no `printf | sed` fork, since this file's
# whole purpose is to stay cheap enough for a future hook stanza.
while true; do
    case "$STALE_DAYS" in
        0?*) STALE_DAYS="${STALE_DAYS#0}" ;;
        *) break ;;
    esac
done

[ -n "$MEMORY_DIR" ] || exit 0
[ -d "$MEMORY_DIR" ] || exit 0
[ -n "$TASK" ] || exit 0

best="$MEMORY_DIR/run-state-$TASK.json"

[ -f "$best" ] || exit 0

# 1. day-granular freshness pre-filter (deliberately over-inclusive; the
#    exact gate lives in run_state.py --max-age-days). mtime, not
#    updated_at -- no date arithmetic in sh. Single-file `-maxdepth 0` probe
#    -- O(1) regardless of how many other tasks' records share MEMORY_DIR.
fresh=$(find "$best" -maxdepth 0 -mtime -$((STALE_DAYS + 1)) 2>/dev/null)
[ -n "$fresh" ] || exit 0

# 2. eligibility -- active AND schema-known. A schema-forward record is
#    absent, like any other ineligible record, never an abort.
grep -q '"active": true' "$best" 2>/dev/null || exit 0
sch=$(sed -n '/"schema"/{p;q;}' "$best" 2>/dev/null | tr -dc '0-9')
[ -n "$sch" ] || exit 0
[ "$sch" -le 1 ] 2>/dev/null || exit 0

# 3. one read of the file into a variable -- never re-open per key.
snapshot=$(cat "$best" 2>/dev/null)
[ -n "$snapshot" ] || exit 0

# 4. extract every requested key in a single awk pass over the snapshot
#    (replaces the previous per-key `printf | sed | sed` re-pipe, which
#    re-streamed the whole record once per key), emitted in the order
#    requested on the command line.
#    ALPHABET: the writer's sanitization guarantees the file contains no
#    backslash byte at all -- '"' -> "'", '\' -> '/', every C0/DEL char ->
#    space, ensure_ascii=False -- so this extractor never meets an escape
#    sequence and does no unescaping.
#    ORDERING: strip the structural trailing comma BEFORE the quotes. The
#    closing quote is what distinguishes a structural comma from a comma
#    that is the last character of the value itself; stripping quotes
#    first silently truncates any value ending in ','.
printf '%s\n' "$snapshot" | awk -v keys="$*" '
BEGIN {
    n = split(keys, order, " ")
}
{
    line = $0
    if (!match(line, /^[ \t]*"[^"]*"/)) next
    key = substr(line, RSTART, RLENGTH)
    gsub(/^[ \t]*"/, "", key)
    gsub(/"$/, "", key)
    rest = substr(line, RSTART + RLENGTH)
    sub(/^: */, "", rest)
    sub(/,$/, "", rest)
    sub(/^"/, "", rest)
    sub(/"$/, "", rest)
    val[key] = rest
}
END {
    for (i = 1; i <= n; i++) {
        k = order[i]
        printf "%s=%s\n", k, (k in val ? val[k] : "")
    }
}
'

exit 0
