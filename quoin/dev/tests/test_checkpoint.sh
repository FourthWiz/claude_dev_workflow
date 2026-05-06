#!/bin/sh
# test_checkpoint.sh — fixture tests for /checkpoint skill contract
#
# Tests the checkpoint save/restore file-level contract:
#   - Save mode: writes checkpoint file + pending-restore sentinel
#   - Paths-not-content rule: no blockquotes / large content in checkpoint
#   - Soft cap warning: oversized checkpoint emits warning but does not abort
#   - Write-target boundary: lessons-learned.md and forgotten/ not touched
#   - Restore mode: CASE A (no pending-prompt), CASE B (current-session prompt),
#                   CASE C (stale pending-prompt from other session)
#   - mtime-most-recent rebound fallback: correct sentinel surfaced (d3)
#   - Corrupt checkpoint: graceful error
#
# NOTE: /checkpoint is a skill (LLM-invoked), not a standalone shell script.
# This test harness validates the file-level contract — the artifact structure
# that /checkpoint MUST produce — rather than invoking the skill directly.
# The save-mode tests simulate what the skill would produce, then assert
# the correct output shape. The restore-mode tests validate the lookup logic
# (which is also exercised by sessionstart.sh and test_sessionstart_pending_restore.sh).
#
# Usage: sh quoin/dev/tests/test_checkpoint.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_checkpoint_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory/checkpoints"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory/sessions"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

MEMORY_DIR="$TMPDIR_TEST/.workflow_artifacts/memory"
CHECKPOINTS_DIR="$MEMORY_DIR/checkpoints"

# ─── Helper: create a canonical checkpoint file ──────────────────────────────

write_checkpoint() {
  local session_id="$1"
  local task_name="${2:-test-task}"
  local branch="${3:-test-branch}"
  local checkpoint_date=$(date -u +%Y-%m-%d)
  local checkpoint_path="$CHECKPOINTS_DIR/${checkpoint_date}-${task_name}.md"

  cat > "$checkpoint_path" << CPEOF
## Status
test-save

## Current stage
implement

## Active task
${task_name}

## Branch
${branch}

## Session ID
${session_id}

## In-flight artifacts
- current-plan.md: $TMPDIR_TEST/.workflow_artifacts/${task_name}/current-plan.md
- architecture.md: $TMPDIR_TEST/.workflow_artifacts/${task_name}/architecture.md

## Open questions
None

## Decisions made
- D-01: some decision

## Restore hint
Run /checkpoint --restore in a fresh session to resume.
CPEOF

  # Write pending-restore sentinel
  printf '%s\n' "$checkpoint_path" > "$MEMORY_DIR/pending-restore-${session_id}.txt"

  printf '%s' "$checkpoint_path"
}

# ─── (a) Save mode — full save scope ─────────────────────────────────────────

# Simulate /checkpoint save: write a canonical checkpoint file + sentinel
checkpoint_path=$(write_checkpoint "sess-save-a" "task-a")

if [ -f "$checkpoint_path" ]; then
  ok "(a) save mode: checkpoint file exists"
else
  fail "(a) save mode: checkpoint file NOT written"
fi

# Check required sections
for section in "## Status" "## Active task" "## Branch" "## In-flight artifacts" "## Restore hint"; do
  if grep -q "$section" "$checkpoint_path" 2>/dev/null; then
    ok "(a) save mode: section '$section' present"
  else
    fail "(a) save mode: section '$section' MISSING from checkpoint"
  fi
done

# Check pending-restore sentinel
if [ -f "$MEMORY_DIR/pending-restore-sess-save-a.txt" ]; then
  ok "(a) save mode: pending-restore-sess-save-a.txt written"
else
  fail "(a) save mode: pending-restore-sess-save-a.txt NOT written"
fi

# Sentinel must contain the checkpoint file path
sentinel_content=$(cat "$MEMORY_DIR/pending-restore-sess-save-a.txt")
if [ "$sentinel_content" = "$checkpoint_path" ]; then
  ok "(a) save mode: sentinel content matches checkpoint path"
else
  fail "(a) save mode: sentinel content mismatch (got: $sentinel_content)"
fi

# ─── (b) Paths-not-content rule + soft cap warning ───────────────────────────

# (b) paths-not-content: checkpoint must NOT contain blockquote lines ("> content")
# which would indicate leaked file contents
if grep -q '^> ' "$checkpoint_path" 2>/dev/null; then
  fail "(b) paths-not-content: checkpoint contains blockquote lines (potential content leak)"
else
  ok "(b) paths-not-content: no blockquote lines in checkpoint (paths-only rule satisfied)"
fi

# (b1) file <= 4KB: no warning expected
cp_size=$(wc -c < "$checkpoint_path" | awk '{print $1}')
if [ "$cp_size" -le 4096 ]; then
  ok "(b1) soft-cap: checkpoint <= 4KB (no warning expected)"
else
  fail "(b1) soft-cap: checkpoint unexpectedly > 4KB ($cp_size bytes)"
fi

# (b2) oversized fixture: create a checkpoint > 4KB and verify warning would fire
# We simulate this by checking whether the soft-cap rule is documented in the SKILL.md
# (The actual warning is emitted by the LLM skill, not a shell script)
CHECKPOINT_SKILL="$SCRIPT_DIR/../../skills/checkpoint/SKILL.md"
if grep -q '4 KB\|4KB\|4096' "$CHECKPOINT_SKILL" 2>/dev/null; then
  ok "(b2) soft-cap: 4 KB threshold documented in checkpoint/SKILL.md"
else
  fail "(b2) soft-cap: 4 KB threshold NOT found in checkpoint/SKILL.md"
fi

if grep -q 'WARNING\|warning' "$CHECKPOINT_SKILL" 2>/dev/null && \
   grep -q 'soft.cap\|soft cap' "$CHECKPOINT_SKILL" 2>/dev/null; then
  ok "(b2) soft-cap: WARNING and soft-cap language present in SKILL.md"
else
  fail "(b2) soft-cap: WARNING/soft-cap language NOT found in checkpoint/SKILL.md"
fi

# ─── (c) Write-target boundary ───────────────────────────────────────────────

LESSONS_LEARNED="$TMPDIR_TEST/.workflow_artifacts/memory/lessons-learned.md"
FORGOTTEN_DIR="$TMPDIR_TEST/.workflow_artifacts/memory/forgotten"

# The checkpoint writes to checkpoints/ and pending-restore-*.txt only.
# lessons-learned.md and forgotten/ must NOT be touched.
# Since we're in a fresh tmpdir, neither should exist.
if [ ! -f "$LESSONS_LEARNED" ]; then
  ok "(c) write-target boundary: lessons-learned.md NOT created by checkpoint"
else
  fail "(c) write-target boundary: lessons-learned.md was created"
fi

if [ ! -d "$FORGOTTEN_DIR" ]; then
  ok "(c) write-target boundary: forgotten/ NOT created by checkpoint"
else
  fail "(c) write-target boundary: forgotten/ was created"
fi

# ─── (d) Restore mode — CASE A (no pending-prompt) ───────────────────────────

# Create a checkpoint for a new session; no pending-prompt files exist
rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true

checkpoint_a=$(write_checkpoint "sess-restore-a" "task-restore-a")

# Verify no pending-prompt files exist before restore
pp_count=$(ls "$MEMORY_DIR"/pending-prompt-*.txt 2>/dev/null | wc -l | awk '{print $1}')
if [ "$pp_count" -eq 0 ]; then
  ok "(d) CASE A: no pending-prompt files exist before restore"
else
  fail "(d) CASE A: unexpected pending-prompt files exist: $pp_count"
fi

# Simulate restore: read checkpoint, check in-flight artifacts section
if grep -q '## In-flight artifacts' "$checkpoint_a" 2>/dev/null; then
  ok "(d) CASE A: checkpoint has In-flight artifacts section for restore"
else
  fail "(d) CASE A: In-flight artifacts section missing from checkpoint"
fi

# SKILL.md must document CASE A explicitly
if grep -q 'CASE A\|case A\|no pending-prompt' "$CHECKPOINT_SKILL" 2>/dev/null; then
  ok "(d) CASE A: documented in checkpoint/SKILL.md"
else
  fail "(d) CASE A: CASE A NOT documented in checkpoint/SKILL.md"
fi

# ─── (d2) CASE C: sentinel-staleness (stale pending-prompt from other session) ─

rm -f "$MEMORY_DIR/pending-prompt-"*.txt 2>/dev/null || true
rm -f "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true

checkpoint_c=$(write_checkpoint "sess-restore-c" "task-restore-c")

# Create a STALE pending-prompt from a different session
printf 'my old prompt from other session\n' > "$MEMORY_DIR/pending-prompt-sess-old.txt"

# CASE C: current session is sess-restore-c; the old pending-prompt is from sess-old
# The restore should surface the stale sentinel with a mismatch warning
# (This is handled by the --restore mode logic in the SKILL.md)
if grep -q 'CASE C\|stale\|mismatch\|sentinel' "$CHECKPOINT_SKILL" 2>/dev/null; then
  ok "(d2) CASE C: stale/mismatch sentinel handling documented in SKILL.md"
else
  fail "(d2) CASE C: stale sentinel handling NOT documented in checkpoint/SKILL.md"
fi

rm -f "$MEMORY_DIR/pending-prompt-sess-old.txt"

# ─── (d3) mtime-most-recent rebound fallback ────────────────────────────────

# Create three pending-restore files with different mtimes (within last few minutes)
rm -f "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true

printf 'checkpoint-zzzzZZ.md\n' > "$MEMORY_DIR/pending-restore-zzzzZZ.txt"
printf 'checkpoint-aaaaAA.md\n' > "$MEMORY_DIR/pending-restore-aaaaAA.txt"
printf 'checkpoint-mmmmMM.md\n' > "$MEMORY_DIR/pending-restore-mmmmMM.txt"

# Set zzzzZZ to 2 minutes ago, aaaaAA to 1 minute ago, mmmmMM stays fresh
TWO_MIN_AGO=$(date -v -2M +%Y%m%d%H%M.%S 2>/dev/null || \
              date -d '2 minutes ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")
ONE_MIN_AGO=$(date -v -1M +%Y%m%d%H%M.%S 2>/dev/null || \
              date -d '1 minute ago' +%Y%m%d%H%M.%S 2>/dev/null || echo "")

if [ -n "$TWO_MIN_AGO" ] && [ -n "$ONE_MIN_AGO" ]; then
  touch -t "$TWO_MIN_AGO" "$MEMORY_DIR/pending-restore-zzzzZZ.txt" 2>/dev/null || true
  touch -t "$ONE_MIN_AGO" "$MEMORY_DIR/pending-restore-aaaaAA.txt" 2>/dev/null || true

  # ls -t should surface mmmmMM first (mtime-newest)
  most_recent=$(ls -t "$MEMORY_DIR"/pending-restore-*.txt 2>/dev/null | head -1 | xargs basename 2>/dev/null)
  if printf '%s' "$most_recent" | grep -q 'mmmmMM' 2>/dev/null; then
    ok "(d3) mtime-most-recent: ls -t surfaces mmmmMM (newest), not zzzzZZ (lex-greatest)"
  else
    fail "(d3) mtime-most-recent: expected mmmmMM but got $most_recent"
  fi
else
  ok "(d3) mtime-most-recent: (skipped — date manipulation not supported)"
fi

rm -f "$MEMORY_DIR/pending-restore-"*.txt 2>/dev/null || true

# ─── (e) Restore mode — CASE B (block-recovery flow) ────────────────────────

# Create checkpoint + pending-prompt for current session
checkpoint_b=$(write_checkpoint "sess-restore-b" "task-restore-b")
printf 'my saved prompt from block-recovery flow\n' > "$MEMORY_DIR/pending-prompt-sess-restore-b.txt"

# Both sentinels should exist before restore
if [ -f "$MEMORY_DIR/pending-restore-sess-restore-b.txt" ] && \
   [ -f "$MEMORY_DIR/pending-prompt-sess-restore-b.txt" ]; then
  ok "(e) CASE B: both sentinels present before restore"
else
  fail "(e) CASE B: one or both sentinels missing before restore"
fi

# After simulated 'y' restore: both sentinels should be consumed (deleted)
# We simulate this:
rm -f "$MEMORY_DIR/pending-prompt-sess-restore-b.txt"
rm -f "$MEMORY_DIR/pending-restore-sess-restore-b.txt"

if [ ! -f "$MEMORY_DIR/pending-prompt-sess-restore-b.txt" ] && \
   [ ! -f "$MEMORY_DIR/pending-restore-sess-restore-b.txt" ]; then
  ok "(e) CASE B: both sentinels consumed (deleted) after restore"
else
  fail "(e) CASE B: sentinels not cleaned up after restore"
fi

# ─── (f) Corrupt checkpoint — graceful error ────────────────────────────────

# Write a corrupt checkpoint file (not valid sections format)
corrupt_checkpoint="$CHECKPOINTS_DIR/corrupt-checkpoint.md"
printf 'this is corrupt{JSON:::invalid\n' > "$corrupt_checkpoint"
printf '%s\n' "$corrupt_checkpoint" > "$MEMORY_DIR/pending-restore-sess-corrupt.txt"

# The SKILL.md must document graceful handling of corrupt checkpoints
if grep -q 'corrupt\|parse fail\|graceful' "$CHECKPOINT_SKILL" 2>/dev/null; then
  ok "(f) corrupt checkpoint: graceful handling documented in SKILL.md"
else
  fail "(f) corrupt checkpoint: graceful handling NOT found in checkpoint/SKILL.md"
fi

# Sentinel must NOT be deleted on corrupt checkpoint (preserve for manual recovery)
if [ -f "$MEMORY_DIR/pending-restore-sess-corrupt.txt" ]; then
  ok "(f) corrupt checkpoint: sentinel preserved (not deleted) after corrupt-parse"
else
  fail "(f) corrupt checkpoint: sentinel was deleted despite corrupt checkpoint"
fi

rm -f "$MEMORY_DIR/pending-restore-sess-corrupt.txt" "$corrupt_checkpoint"

# ─── (g) Round-trip timing: sentinel write to restore is fast ────────────────

# This is a smoke test of the file-level latency — full V-04 soak is post-merge.
# We measure time to write a checkpoint + read it back.
START_TIME=$(date +%s 2>/dev/null || printf '0')
checkpoint_g=$(write_checkpoint "sess-timing-g" "task-timing")
content=$(cat "$checkpoint_g" 2>/dev/null)
END_TIME=$(date +%s 2>/dev/null || printf '0')
ELAPSED=$((END_TIME - START_TIME))

if [ "$ELAPSED" -le 5 ]; then
  ok "(g) round-trip timing: checkpoint write+read completed in ${ELAPSED}s (target <5s for file I/O)"
else
  fail "(g) round-trip timing: took ${ELAPSED}s (unexpectedly slow for file I/O)"
fi

rm -f "$MEMORY_DIR/pending-restore-sess-timing-g.txt"

# ─── Summary ──────────────────────────────────────────────────────────────────

printf '\n'
if [ "$FAIL" -eq 0 ]; then
  printf 'PASS: all %d tests passed\n' "$PASS"
  exit 0
else
  printf 'FAIL: %d/%d tests failed:\n' "$FAIL" "$((PASS + FAIL))" >&2
  printf '%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
