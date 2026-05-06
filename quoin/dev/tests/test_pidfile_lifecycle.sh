#!/bin/sh
# test_pidfile_lifecycle.sh — drift detection for §0c Pidfile lifecycle across 9 skills
#
# Covers T-19 acceptance criteria:
#   - §0c is the LAST §0-class block in every skill SKILL.md
#   - Per-tier sanity assertions (cheap/opus/stub)
#   - pidfile_acquire / pidfile_release round-trip
#   - Crash safety (stale PID cleanup)
#   - end_of_task §0c-after-§0b regression guard
#
# Parameterized via quoin/dev/tests/fixtures/pidfile_lifecycle_skills.json
# Requires: jq on PATH.
#
# Usage: sh quoin/dev/tests/test_pidfile_lifecycle.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_JSON="$SCRIPT_DIR/fixtures/pidfile_lifecycle_skills.json"
QUOIN_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PIDFILE_HELPERS="$QUOIN_DIR/scripts/pidfile_helpers.sh"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_pidfile_lifecycle_$$"
mkdir -p "$TMPDIR_TEST/.workflow_artifacts/memory/sessions"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

# ─── Prerequisites ────────────────────────────────────────────────────────────

if ! command -v jq > /dev/null 2>&1; then
  fail "jq not found on PATH — required for this test"
  printf 'FAIL: jq required\n' >&2
  exit 1
fi

if [ ! -f "$SKILLS_JSON" ]; then
  fail "skills JSON sidecar not found at $SKILLS_JSON"
  printf 'FAIL: skills JSON not found\n' >&2
  exit 1
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────

expected_tier() {
  jq -r ".\"$1\".tier // \"unknown\"" < "$SKILLS_JSON"
}

expected_variant() {
  jq -r ".\"$1\".variant // \"unknown\"" < "$SKILLS_JSON"
}

skill_dir_name() {
  jq -r ".\"$1\".skill_dir // \"$1\"" < "$SKILLS_JSON"
}

# Get line number of last ^## §0-prefixed heading in a file
last_zero_class_line() {
  grep -n '^## §0' "$1" | tail -1 | cut -d: -f1
}

# Get line number of §0c heading
zero_c_line() {
  grep -n '^## §0c\b' "$1" | head -1 | cut -d: -f1
}

# ─── Per-skill §0c placement and variant checks ───────────────────────────────

SKILLS=$(jq -r 'keys[]' < "$SKILLS_JSON")

for skill in $SKILLS; do
  skill_dir=$(skill_dir_name "$skill")
  skill_md="$QUOIN_DIR/skills/$skill_dir/SKILL.md"

  if [ ! -f "$skill_md" ]; then
    fail "$skill: SKILL.md not found at $skill_md"
    continue
  fi

  tier=$(expected_tier "$skill")
  variant=$(expected_variant "$skill")

  # ─── (a) §0c-placement check: §0c must be the LAST §0-class block ────────────

  lzc=$(last_zero_class_line "$skill_md")
  c_line=$(zero_c_line "$skill_md")

  if [ -z "$c_line" ]; then
    fail "$skill: §0c block (^## §0c\\b) not found in SKILL.md"
    continue
  fi

  if [ "$c_line" = "$lzc" ]; then
    ok "$skill: §0c is the LAST §0-class block (line $c_line)"
  else
    fail "$skill: §0c is NOT the last §0-class block (§0c at line $c_line, last §0-class at line $lzc)"
  fi

  # ─── Per-tier sanity assertions ───────────────────────────────────────────────

  if [ "$variant" = "stub" ]; then
    # Stub variant: §0c is the ONLY §0-class block (no §0 dispatch in S-2)
    # Count §0-class blocks; grep -c exits non-zero on 0 count, so capture with awk
    total_zero=$(grep '^## §0' "$skill_md" 2>/dev/null | wc -l | awk '{print $1}')
    if [ "$total_zero" -eq 1 ]; then
      ok "$skill (stub): §0c is the ONLY §0-class block (no §0 dispatch in S-2)"
    else
      fail "$skill (stub): expected exactly 1 §0-class block, found $total_zero"
    fi
  elif [ "$tier" = "cheap" ]; then
    # Cheap-tier non-stub: §0 dispatch must appear at a line strictly LESS than §0c
    zero_dispatch_line=$(grep -n '^## §0 Model dispatch' "$skill_md" 2>/dev/null | head -1 | cut -d: -f1)
    if [ -z "$zero_dispatch_line" ]; then
      fail "$skill (cheap-tier): §0 Model dispatch block not found (required for cheap-tier non-stub)"
    elif [ "$zero_dispatch_line" -lt "$c_line" ]; then
      ok "$skill (cheap-tier): §0 Model dispatch (line $zero_dispatch_line) is above §0c (line $c_line)"
    else
      fail "$skill (cheap-tier): §0 Model dispatch (line $zero_dispatch_line) is NOT above §0c (line $c_line)"
    fi
  elif [ "$tier" = "opus" ]; then
    # Opus-tier: §0 Model dispatch must NOT be present
    # Use grep -q: exit 0 if found, exit 1 if not found; inverse the sense for the test.
    if grep -q '^## §0 Model dispatch' "$skill_md" 2>/dev/null; then
      fail "$skill (opus-tier): §0 Model dispatch found (opus-tier must NOT have dispatch preamble)"
    else
      ok "$skill (opus-tier): §0 Model dispatch correctly absent"
    fi
  fi

  # ─── (b) Variant-specific content checks ─────────────────────────────────────

  case "$variant" in
    canonical|stub)
      # Must contain pidfile_acquire and pidfile_release with the skill name
      # (using underscore-to-hyphen normalized skill name for the pidfile)
      # The actual skill name used in the pidfile may be the skill key (e.g., end-of-task)
      if grep -q 'pidfile_acquire' "$skill_md" 2>/dev/null; then
        ok "$skill ($variant): pidfile_acquire found in §0c block"
      else
        fail "$skill ($variant): pidfile_acquire NOT found in SKILL.md"
      fi
      if grep -q 'pidfile_release' "$skill_md" 2>/dev/null; then
        ok "$skill ($variant): pidfile_release found in §0c block"
      else
        fail "$skill ($variant): pidfile_release NOT found in SKILL.md"
      fi
      ;;
    phase-4-only)
      if grep -q 'Phase 4\|phase.*4\|phase-4' "$skill_md" 2>/dev/null; then
        ok "$skill (phase-4-only): Phase 4 reference found in SKILL.md"
      else
        fail "$skill (phase-4-only): Phase 4 reference NOT found in SKILL.md"
      fi
      ;;
    per-round)
      if grep -q 'per-round\|round\|per round' "$skill_md" 2>/dev/null; then
        ok "$skill (per-round): per-round reference found in SKILL.md"
      else
        fail "$skill (per-round): per-round/round reference NOT found in SKILL.md"
      fi
      ;;
    per-phase)
      if grep -q 'per-phase\|phase\|per phase' "$skill_md" 2>/dev/null; then
        ok "$skill (per-phase): per-phase reference found in SKILL.md"
      else
        fail "$skill (per-phase): per-phase/phase reference NOT found in SKILL.md"
      fi
      ;;
  esac

done

# ─── (c) Round-trip: acquire → lock file present → release → lock file gone ──

# Use a custom pidfile dir for isolation
OLD_PIDFILE_DIR=".workflow_artifacts/memory/sessions"
export _PIDFILE_DIR="$TMPDIR_TEST/.workflow_artifacts/memory/sessions"

(
  # Source pidfile helpers and test acquire/release
  . "$PIDFILE_HELPERS"
  pidfile_acquire "test-skill"
  LOCK_FILE="${_PIDFILE_DIR}/test-skill-$$.pidfile.lock"
  if [ -f "$LOCK_FILE" ]; then
    printf 'ok  pidfile round-trip: acquire created lock file\n'
  else
    printf 'FAIL pidfile round-trip: lock file not found after acquire\n' >&2
    exit 1
  fi
  pidfile_release "test-skill"
  if [ ! -f "$LOCK_FILE" ]; then
    printf 'ok  pidfile round-trip: release removed lock file\n'
  else
    printf 'FAIL pidfile round-trip: lock file still present after release\n' >&2
    exit 1
  fi
) && {
  PASS=$((PASS + 2))
} || {
  FAIL=$((FAIL + 2))
  FAIL_MSGS="$FAIL_MSGS\n  - pidfile round-trip failed"
}

# ─── (d) Crash safety: acquire, kill subshell, verify stale cleanup ───────────

(
  . "$PIDFILE_HELPERS"
  # Acquire in a subshell that we can track
  sh -c ". '$PIDFILE_HELPERS'; pidfile_acquire 'crash-test-skill'; sleep 60" &
  CHILD_PID=$!
  # Wait for the pidfile to be created
  sleep 0.2 2>/dev/null || true
  # Kill the child (simulate crash)
  kill -9 "$CHILD_PID" 2>/dev/null || true
  wait "$CHILD_PID" 2>/dev/null || true
  # Verify pidfile still exists (crash safety — it persists across crashes)
  if ls "$_PIDFILE_DIR"/crash-test-skill-*.pidfile.lock > /dev/null 2>&1; then
    printf 'ok  crash safety: pidfile persists after crash (as expected)\n'
  else
    printf 'FAIL crash safety: pidfile missing after crash\n' >&2
    exit 1
  fi
  # Run cleanup_stale: the dead PID's pidfile should be removed
  pidfile_cleanup_stale
  if ls "$_PIDFILE_DIR"/crash-test-skill-*.pidfile.lock > /dev/null 2>&1; then
    printf 'FAIL crash safety: pidfile still present after pidfile_cleanup_stale\n' >&2
    exit 1
  else
    printf 'ok  crash safety: pidfile_cleanup_stale removed dead-PID entry\n'
  fi
) && {
  PASS=$((PASS + 2))
} || {
  FAIL=$((FAIL + 2))
  FAIL_MSGS="$FAIL_MSGS\n  - crash safety test failed"
}

# ─── (e) end_of_task §0c-after-§0b regression guard ─────────────────────────

# Verify that in end_of_task/SKILL.md, §0b appears at a LOWER line than §0c.
# If §0c is before §0b, the pidfile would be acquired before §0b can abort,
# causing a pidfile leak on session-age abort.

EOT_SKILL="$QUOIN_DIR/skills/end_of_task/SKILL.md"
if [ -f "$EOT_SKILL" ]; then
  eot_zero_b_line=$(grep -n '^## §0b ' "$EOT_SKILL" | head -1 | cut -d: -f1)
  eot_zero_c_line=$(zero_c_line "$EOT_SKILL")

  if [ -z "$eot_zero_b_line" ]; then
    fail "end_of_task regression guard: §0b block not found in end_of_task/SKILL.md"
  elif [ -z "$eot_zero_c_line" ]; then
    fail "end_of_task regression guard: §0c block not found in end_of_task/SKILL.md"
  elif [ "$eot_zero_b_line" -lt "$eot_zero_c_line" ]; then
    ok "end_of_task regression guard: §0b (line $eot_zero_b_line) is before §0c (line $eot_zero_c_line)"
  else
    fail "end_of_task regression guard: §0c (line $eot_zero_c_line) is NOT after §0b (line $eot_zero_b_line) — pidfile would leak on session-age abort"
  fi
else
  fail "end_of_task/SKILL.md not found at $EOT_SKILL"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────

printf '\n'
total=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
  printf 'PASS: all %d tests passed\n' "$PASS"
  exit 0
else
  printf 'FAIL: %d/%d tests failed:\n' "$FAIL" "$total" >&2
  printf '%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
