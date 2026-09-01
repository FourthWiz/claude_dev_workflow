#!/bin/sh
# Fixture builder / timer / correctness harness for run_state_read.sh (T-02,
# retimed post-review-1 rework -- see spike-run-state-read.md "Rework" section).
# Not committed as part of the reader contract -- invokes the reader as a
# subprocess and never sources it, per D-60.
#
# Deliberately unrouted in affected_tests.py's _DOCS_TO_TESTS: this is a
# standalone, manually-invoked timing/fixture harness, not a pytest fixture
# or anything another test file imports or shells out to -- nothing in the
# suite references it, so an edit here has no test to select and correctly
# falls into the "ignored" bucket (unlike run_state_read.sh itself, which IS
# routed because test_run_state_writer.py round-trips against its bytes).
#
# Usage: run_state_read_spike.sh [--iterations N] [--sibling-count N]

set -e

ITERATIONS=20
SIBLING_COUNT=200
while [ $# -gt 0 ]; do
    case "$1" in
        --iterations) ITERATIONS="$2"; shift 2 ;;
        --sibling-count) SIBLING_COUNT="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
READER="$SCRIPT_DIR/run_state_read.sh"
FAIL=0

# Production key set exactly as requested by Resume Step 1b in run/SKILL.md
# -- earlier evidence timed 6 keys against a harness reproduction while
# Step 1b as shipped requests eleven; use the real set here so the
# recorded numbers describe the read that ships.
PROD_KEYS="schema active phase phase_index subphase step at_stage_boundary next_action notes_path resume_command updated_at"

# --- record writer -----------------------------------------------------
# Hand-rolled, matching the on-disk shape T-03 freezes: one key per line,
# exactly `"key": value` (one space after the colon), fixed field order.
write_record() {
    path="$1"; task="$2"; active="$3"; schema="$4"
    cat > "$path" <<EOF
{
  "schema": $schema,
  "task": "$task",
  "session_id": "spike-session",
  "active": $active,
  "phase": "implement",
  "phase_index": 5,
  "subphase": "",
  "step": "",
  "at_stage_boundary": true,
  "route": "full",
  "profile": "Large",
  "artifacts": ["a/b"],
  "next_action": "start review",
  "resume_command": "/run --resume $task",
  "notes_path": "memory/run-notes-$task.md",
  "updated_at": "2026-09-01T00:00:00Z"
}
EOF
}

check() {
    label="$1"; got="$2"; want="$3"
    if [ "$got" = "$want" ]; then
        echo "PASS: $label"
    else
        echo "FAIL: $label -- got [$got] want [$want]"
        FAIL=1
    fi
}

# =========================================================================
# Fixture: one target-task record plus SIBLING_COUNT decoy records for
# OTHER tasks (some active, some not, some schema-forward). Since the
# reworked reader addresses run-state-$TASK.json directly (no directory
# scan), none of these siblings should be
# touched at all, regardless of count.
# =========================================================================
MEMDIR=$(mktemp -d)
NOW_TS=$(date +%Y%m%d%H%M.%S)

i=1
while [ "$i" -le "$SIBLING_COUNT" ]; do
    f="$MEMDIR/run-state-decoy-$i.json"
    case $((i % 3)) in
        0) write_record "$f" "decoy-$i" "false" 1 ;;
        1) write_record "$f" "decoy-$i" "true" 1 ;;
        *) write_record "$f" "decoy-$i" "true" 2 ;;
    esac
    i=$((i + 1))
done

TARGET="$MEMDIR/run-state-target-task.json"
write_record "$TARGET" "target-task" "true" 1

NOTES="$MEMDIR/run-notes-target-task.md"
echo "## notes" > "$NOTES"

FILE_COUNT=$(find "$MEMDIR" -maxdepth 1 -type f | wc -l | tr -d ' ')
echo "fixture file count: $FILE_COUNT (expect $((SIBLING_COUNT + 2)): $SIBLING_COUNT decoy + 1 target + 1 run-notes)"

# =========================================================================
# Correctness (a): task-scoped read of the target record ignores every
# decoy for another task, regardless of decoy count or freshness -- the
# decoys are never even opened, since the reader addresses the target
# file by name.
# =========================================================================
got=$(sh "$READER" "$MEMDIR" target-task resume_command)
check "correctness (a): task-scoped read selects the addressed task" "$got" "resume_command=/run --resume target-task"

# =========================================================================
# Correctness (b): a schema-forward record for the SAME task is treated as
# absent -- empty stdout, exit 0 (whole-record absence, falls through to
# the next precedence tier). Isolated fixture: the addressed task's own
# record is schema-forward.
# =========================================================================
SCHEMA2DIR=$(mktemp -d)
write_record "$SCHEMA2DIR/run-state-schema2-task.json" "schema2-task" "true" 2
out=$(sh "$READER" "$SCHEMA2DIR" schema2-task resume_command)
rc=$?
if [ -z "$out" ] && [ "$rc" -eq 0 ]; then
    echo "PASS: correctness (b): schema-forward record for the addressed task yields empty stdout, exit 0"
else
    echo "FAIL: correctness (b) -- got [$out] rc=$rc"
    FAIL=1
fi
rm -f "$SCHEMA2DIR"/*.json
rmdir "$SCHEMA2DIR" 2>/dev/null || true

# =========================================================================
# Correctness (c): an unaddressed task (no record on disk for it at all)
# yields empty stdout, exit 0.
# =========================================================================
out=$(sh "$READER" "$MEMDIR" no-such-task resume_command)
rc=$?
if [ -z "$out" ] && [ "$rc" -eq 0 ]; then
    echo "PASS: correctness (c): unaddressed task yields empty stdout, exit 0"
else
    echo "FAIL: correctness (c) -- got [$out] rc=$rc"
    FAIL=1
fi

# =========================================================================
# Correctness (d): one key=value line per requested key, in requested
# order, from a single read (design property: the reader's step 3 does
# exactly one `cat "$best"` into a shell variable before extracting all
# requested keys in a single subsequent `awk` pass -- no per-key re-open,
# and no per-key re-stream of the file's content either).
# =========================================================================
out=$(sh "$READER" "$MEMDIR" target-task phase active step)
expected="phase=implement
active=true
step="
check "correctness (d): multi-key order and values from single read" "$out" "$expected"

# =========================================================================
# Window probes (12h / 30h / 40h), default STALE_DAYS=1 -- unchanged from
# the original spike; per-file mtime, independent of directory scanning.
# =========================================================================
FIND_VERSION=$(find --version 2>&1 | head -1 || echo "(no --version support)")

probe() {
    hours="$1"
    d=$(mktemp -d)
    f="$d/run-state-probe-$hours.json"
    write_record "$f" "probe-$hours" "true" 1
    ts=$(date -v-"${hours}"H +%Y%m%d%H%M.%S 2>/dev/null || date -d "$hours hours ago" +%Y%m%d%H%M.%S)
    touch -t "$ts" "$f"
    out=$(sh "$READER" "$d" "probe-$hours" resume_command)
    if [ -n "$out" ]; then
        echo "WINDOW $hours h: PASS (selected)"
    else
        echo "WINDOW $hours h: SKIP (not selected)"
    fi
    rm -f "$d"/*.json
    rmdir "$d" 2>/dev/null || true
}

probe 12
probe 30
probe 40

# =========================================================================
# Timing (a): N iterations of a full read of the target record, with
# SIBLING_COUNT unrelated records sharing the directory -- proves the
# reworked reader's cost is independent of sibling-file count (issue 9's
# fix), using the eleven production keys Resume Step 1b actually requests
# (issue 20 -- the original evidence timed six).
# =========================================================================
touch "$TARGET"
i=0
TIMES_FILE=$(mktemp)
while [ "$i" -lt "$ITERATIONS" ]; do
    start=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    sh "$READER" "$MEMDIR" target-task $PROD_KEYS > /dev/null
    end=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    ms=$(( (end - start) / 1000000 ))
    echo "$ms" >> "$TIMES_FILE"
    i=$((i + 1))
done

sorted=$(sort -n "$TIMES_FILE")
median=$(printf '%s\n' "$sorted" | awk '{a[NR]=$1} END{n=NR; if(n%2==1) print a[(n+1)/2]; else print int((a[n/2]+a[n/2+1])/2)}')
worst=$(printf '%s\n' "$sorted" | tail -1)

echo "timings with $SIBLING_COUNT siblings, 11 production keys (ms): $(tr '\n' ' ' < "$TIMES_FILE")"
echo "median_ms=$median worst_ms=$worst"

if [ "$median" -le 250 ]; then
    echo "PASS: budget median <= 250ms ($median)"
else
    echo "FAIL: budget median <= 250ms ($median)"
    FAIL=1
fi

if [ "$worst" -le 1000 ]; then
    echo "PASS: budget worst-of-$ITERATIONS <= 1000ms ($worst)"
else
    echo "FAIL: budget worst-of-$ITERATIONS <= 1000ms ($worst)"
    FAIL=1
fi

rm -f "$TIMES_FILE"

# =========================================================================
# Timing (b): the same eleven-key read with ZERO siblings in the directory
# -- shows the sibling-independence claim above is not an artifact of an
# already-tiny baseline.
# =========================================================================
LONEDIR=$(mktemp -d)
LONETARGET="$LONEDIR/run-state-target-task.json"
write_record "$LONETARGET" "target-task" "true" 1
i=0
TIMES_FILE2=$(mktemp)
while [ "$i" -lt "$ITERATIONS" ]; do
    start=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    sh "$READER" "$LONEDIR" target-task $PROD_KEYS > /dev/null
    end=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    ms=$(( (end - start) / 1000000 ))
    echo "$ms" >> "$TIMES_FILE2"
    i=$((i + 1))
done
sorted2=$(sort -n "$TIMES_FILE2")
median2=$(printf '%s\n' "$sorted2" | awk '{a[NR]=$1} END{n=NR; if(n%2==1) print a[(n+1)/2]; else print int((a[n/2]+a[n/2+1])/2)}')
worst2=$(printf '%s\n' "$sorted2" | tail -1)
echo "timings with 0 siblings, 11 production keys (ms): $(tr '\n' ' ' < "$TIMES_FILE2")"
echo "median_ms=$median2 worst_ms=$worst2"
rm -f "$TIMES_FILE2" "$LONETARGET"
rmdir "$LONEDIR" 2>/dev/null || true

echo "find --version: $FIND_VERSION"

rm -f "$MEMDIR"/*.json "$MEMDIR"/*.md

if [ "$FAIL" -eq 0 ]; then
    echo "SPIKE RESULT: PASS"
    exit 0
else
    echo "SPIKE RESULT: FAIL"
    exit 1
fi
