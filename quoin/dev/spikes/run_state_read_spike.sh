#!/bin/sh
# Fixture builder / timer / correctness harness for run_state_read.sh (T-02).
# Not committed as part of the reader contract -- invokes the reader as a
# subprocess and never sources it, per D-60.
#
# Usage: run_state_read_spike.sh [--iterations N]

set -e

ITERATIONS=20
while [ $# -gt 0 ]; do
    case "$1" in
        --iterations) ITERATIONS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
READER="$SCRIPT_DIR/run_state_read.sh"
FAIL=0

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
# Main 48-file fixture
# =========================================================================
MEMDIR=$(mktemp -d)
NOW_TS=$(date +%Y%m%d%H%M.%S)

i=1
while [ "$i" -le 40 ]; do
    f="$MEMDIR/run-state-decoy-$i.json"
    write_record "$f" "decoy-$i" "false" 1
    touch -t "$(date -v-30d +%Y%m%d%H%M.%S 2>/dev/null || date -d '30 days ago' +%Y%m%d%H%M.%S)" "$f"
    i=$((i + 1))
done

i=1
while [ "$i" -le 5 ]; do
    f="$MEMDIR/run-state-stale-$i.json"
    write_record "$f" "stale-$i" "true" 1
    touch -t "$(date -v-3d +%Y%m%d%H%M.%S 2>/dev/null || date -d '3 days ago' +%Y%m%d%H%M.%S)" "$f"
    i=$((i + 1))
done

TARGET="$MEMDIR/run-state-target-task.json"
write_record "$TARGET" "target-task" "true" 1

SCHEMA2="$MEMDIR/run-state-schema2-task.json"
write_record "$SCHEMA2" "schema2-task" "true" 2

NOTES="$MEMDIR/run-notes-target-task.md"
echo "## notes" > "$NOTES"

FILE_COUNT=$(find "$MEMDIR" -maxdepth 1 -type f | wc -l | tr -d ' ')
echo "fixture file count: $FILE_COUNT (expect 48: 40 decoy + 5 stale-active + 1 target + 1 schema-2 + 1 run-notes)"

# =========================================================================
# Correctness (a): target newest -> reader selects the target record;
# skips all 40 decoys and all 5 stale-active records.
# =========================================================================
touch "$TARGET"
touch -t "$(date -v-1S +%Y%m%d%H%M.%S 2>/dev/null || date -d '1 second ago' +%Y%m%d%H%M.%S)" "$SCHEMA2"

got=$(sh "$READER" "$MEMDIR" resume_command)
check "correctness (a): target newest selects target" "$got" "resume_command=/run --resume target-task"

# =========================================================================
# Correctness (b): schema-2 newest -> reader still selects the target
# (schema-forward is SKIPPED, not an abort of the scan).
# =========================================================================
touch "$SCHEMA2"
touch -t "$(date -v-1S +%Y%m%d%H%M.%S 2>/dev/null || date -d '1 second ago' +%Y%m%d%H%M.%S)" "$TARGET"

got=$(sh "$READER" "$MEMDIR" resume_command)
check "correctness (b): schema-2 newest still selects target (skip not abort)" "$got" "resume_command=/run --resume target-task"

# restore target as newest for the timing run below
touch "$TARGET"

# =========================================================================
# Correctness (c): schema-2 as the ONLY active candidate -> empty stdout,
# exit 0. Build an isolated fixture: everything else inactive.
# =========================================================================
ONLYDIR=$(mktemp -d)
write_record "$ONLYDIR/run-state-schema2-only.json" "schema2-only" "true" 2
write_record "$ONLYDIR/run-state-inactive-1.json" "inactive-1" "false" 1
write_record "$ONLYDIR/run-state-inactive-2.json" "inactive-2" "false" 1

out=$(sh "$READER" "$ONLYDIR" resume_command)
rc=$?
if [ -z "$out" ] && [ "$rc" -eq 0 ]; then
    echo "PASS: correctness (c): schema-2-only candidate yields empty stdout, exit 0"
else
    echo "FAIL: correctness (c) -- got [$out] rc=$rc"
    FAIL=1
fi
rm -rf "$ONLYDIR"

# =========================================================================
# Correctness (d): one key=value line per requested key, in requested
# order, from a single read (design property: the reader's step 4 does
# exactly one `cat "$best"` into a shell variable before any extraction;
# verified here observably via multi-key ordering/values).
# =========================================================================
out=$(sh "$READER" "$MEMDIR" phase active step)
expected="phase=implement
active=true
step="
check "correctness (d): multi-key order and values from single read" "$out" "$expected"

# =========================================================================
# Window probes: 12h / 30h / 40h single-record fixtures in separate dirs.
# Record PASS (selected) / SKIP (not selected) per probe under the default
# STALE_DAYS=1 gate (find -mtime -2, "age < 48h" on this find binary).
# =========================================================================
FIND_VERSION=$(find --version 2>&1 | head -1 || echo "(no --version support)")

probe() {
    hours="$1"
    d=$(mktemp -d)
    f="$d/run-state-probe-$hours.json"
    write_record "$f" "probe-$hours" "true" 1
    ts=$(date -v-"${hours}"H +%Y%m%d%H%M.%S 2>/dev/null || date -d "$hours hours ago" +%Y%m%d%H%M.%S)
    touch -t "$ts" "$f"
    out=$(sh "$READER" "$d" resume_command)
    if [ -n "$out" ]; then
        echo "WINDOW $hours h: PASS (selected)"
    else
        echo "WINDOW $hours h: SKIP (not selected)"
    fi
    rm -rf "$d"
}

probe 12
probe 30
probe 40

# =========================================================================
# Timing: N iterations of a full read over the 48-file fixture.
# =========================================================================
touch "$TARGET"
i=0
TIMES_FILE=$(mktemp)
while [ "$i" -lt "$ITERATIONS" ]; do
    start=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    sh "$READER" "$MEMDIR" schema active phase step notes_path updated_at > /dev/null
    end=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1e9))')
    ms=$(( (end - start) / 1000000 ))
    echo "$ms" >> "$TIMES_FILE"
    i=$((i + 1))
done

sorted=$(sort -n "$TIMES_FILE")
median=$(printf '%s\n' "$sorted" | awk '{a[NR]=$1} END{n=NR; if(n%2==1) print a[(n+1)/2]; else print int((a[n/2]+a[n/2+1])/2)}')
worst=$(printf '%s\n' "$sorted" | tail -1)

echo "timings (ms): $(tr '\n' ' ' < "$TIMES_FILE")"
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

echo "find --version: $FIND_VERSION"

rm -rf "$MEMDIR" "$TIMES_FILE"

if [ "$FAIL" -eq 0 ]; then
    echo "SPIKE RESULT: PASS"
    exit 0
else
    echo "SPIKE RESULT: FAIL"
    exit 1
fi
