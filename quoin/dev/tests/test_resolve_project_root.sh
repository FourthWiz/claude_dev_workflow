#!/bin/sh
# test_resolve_project_root.sh — unit tests for resolve_project_root in _lib.sh
#
# Tests the D-01 resolution rule:
#   OUTERMOST .workflow_artifacts/ STRICTLY BELOW $HOME
#   > NEAREST .git STRICTLY BELOW $HOME
#   > start dir (fall-back)
# $HOME and / are EXCLUSIVE hard stops (CRIT-3, CRIT-4).
#
# Usage: sh quoin/dev/tests/test_resolve_project_root.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

LIB_SH="$(cd "$(dirname "$0")" && pwd)/../../hooks/_lib.sh"

ok()   { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

assert_eq() {
  # assert_eq <label> <expected> <actual>
  if [ "$2" = "$3" ]; then
    ok "$1"
  else
    fail "$1 — expected='$2' got='$3'"
  fi
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_rpr_$$"
mkdir -p "$TMPDIR_TEST"

cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

# Helper: source _lib.sh with an overridden HOME in a subshell, call
# resolve_project_root, and print the result.
rpr() {
  # rpr <fake_home> <start_dir>
  _fake_home="$1"
  _start="$2"
  (
    HOME="$_fake_home"
    export HOME
    # shellcheck source=/dev/null
    . "$LIB_SH"
    resolve_project_root "$_start"
  )
}

# ─── Source sanity ────────────────────────────────────────────────────────────
if [ -r "$LIB_SH" ]; then
  ok "_lib.sh readable"
else
  fail "_lib.sh not found at $LIB_SH — abort"
  printf '\nFAIL: 1  PASS: 0\n'
  exit 1
fi

# ─── (a) Basic: nested dir, single artifacts owner ───────────────────────────
T="$TMPDIR_TEST/a"
FAKE_HOME="$TMPDIR_TEST/fake_home_a"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.workflow_artifacts"
mkdir -p "$T/sub/sub2"
result=$(rpr "$FAKE_HOME" "$T/sub/sub2")
assert_eq "(a) single artifacts owner: resolves to owner" "$T" "$result"

# ─── (b) CRIT-1 stale-subdir: outermost wins ─────────────────────────────────
T="$TMPDIR_TEST/b"
FAKE_HOME="$TMPDIR_TEST/fake_home_b"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.workflow_artifacts"
mkdir -p "$T/sub/.workflow_artifacts"        # stale inner
mkdir -p "$T/sub/sub2/.workflow_artifacts"   # even deeper stale
result=$(rpr "$FAKE_HOME" "$T/sub/sub2")
assert_eq "(b) CRIT-1 stale-subdir: outermost below fake HOME wins" "$T" "$result"
# Also assert stale inner does NOT win
if [ "$result" = "$T/sub/sub2" ] || [ "$result" = "$T/sub" ]; then
  fail "(b) CRIT-1 regression: resolved to stale inner dir instead of outermost"
else
  ok "(b) CRIT-1 confirmed: NOT stale inner dir"
fi

# ─── (c) Git fallback: no .workflow_artifacts/, nearest .git wins ─────────────
T="$TMPDIR_TEST/c"
FAKE_HOME="$TMPDIR_TEST/fake_home_c"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.git"
mkdir -p "$T/sub/sub2"
result=$(rpr "$FAKE_HOME" "$T/sub/sub2")
assert_eq "(c) git fallback: nearest .git returned" "$T" "$result"

# ─── (d) Precedence: artifacts beats git ─────────────────────────────────────
T="$TMPDIR_TEST/d"
FAKE_HOME="$TMPDIR_TEST/fake_home_d"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.workflow_artifacts"
mkdir -p "$T/sub/.git"   # nested .git — should NOT win
mkdir -p "$T/sub/sub2"
result=$(rpr "$FAKE_HOME" "$T/sub/sub2")
assert_eq "(d) artifacts beats nested .git" "$T" "$result"

# ─── (e) CRIT-3: $HOME itself owns .workflow_artifacts/; project subdir wins ─
FAKE_HOME="$TMPDIR_TEST/fake_home_e"
PROJECT="$FAKE_HOME/project"
mkdir -p "$FAKE_HOME/.workflow_artifacts"     # fake HOME owns artifacts (the real bug)
mkdir -p "$PROJECT/.workflow_artifacts"
mkdir -p "$PROJECT/sub"
result=$(rpr "$FAKE_HOME" "$PROJECT/sub")
assert_eq "(e) CRIT-3: project below fake-HOME returned, not fake-HOME" "$PROJECT" "$result"
if [ "$result" = "$FAKE_HOME" ]; then
  fail "(e) CRIT-3 REGRESSION: returned fake-HOME (exclusive ceiling not applied)"
else
  ok "(e) CRIT-3 confirmed: result != fake-HOME"
fi
# Assert strict descendant of fake_home
case "$result" in
  "$FAKE_HOME/"*) ok "(e) result is strict descendant of fake-HOME (not HOME itself)" ;;
  *) fail "(e) result is not a descendant of fake-HOME: $result" ;;
esac

# ─── (f) CRIT-4: $HOME owns .git (dotfiles repo); cold start ─────────────────
FAKE_HOME="$TMPDIR_TEST/fake_home_f"
mkdir -p "$FAKE_HOME"
touch "$FAKE_HOME/.git"   # fake HOME owns .git (dotfiles pattern)
START="$FAKE_HOME/q/r"
mkdir -p "$START"
result=$(rpr "$FAKE_HOME" "$START")
assert_eq "(f) CRIT-4: cold-start with .git@HOME returns start dir, not fake-HOME" "$START" "$result"
if [ "$result" = "$FAKE_HOME" ]; then
  fail "(f) CRIT-4 REGRESSION: returned fake-HOME (git pass not excluding HOME)"
else
  ok "(f) CRIT-4 confirmed: result != fake-HOME"
fi

# ─── (g) Cold start: no markers anywhere → start dir returned ─────────────────
T="$TMPDIR_TEST/g"
FAKE_HOME="$TMPDIR_TEST/fake_home_g"
mkdir -p "$FAKE_HOME"
START="$T/deep/dir"
mkdir -p "$START"
result=$(rpr "$FAKE_HOME" "$START")
assert_eq "(g) cold-start: start dir returned unchanged" "$START" "$result"

# ─── (h) Path with spaces ─────────────────────────────────────────────────────
T="$TMPDIR_TEST/has space dir"
FAKE_HOME="$TMPDIR_TEST/fake_home_h"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.workflow_artifacts"
START="$T/sub dir/deep dir"
mkdir -p "$START"
result=$(rpr "$FAKE_HOME" "$START")
assert_eq "(h) path-with-spaces: resolves to artifacts owner" "$T" "$result"

# ─── (i) .git as a FILE (worktree/submodule form) ─────────────────────────────
T="$TMPDIR_TEST/i"
FAKE_HOME="$TMPDIR_TEST/fake_home_i"
mkdir -p "$FAKE_HOME"
mkdir -p "$T"
printf 'gitdir: ../.git/worktrees/sub\n' > "$T/.git"   # worktree .git file
START="$T/sub/sub2"
mkdir -p "$START"
result=$(rpr "$FAKE_HOME" "$START")
assert_eq "(i) .git as a file: git fallback matches -e .git" "$T" "$result"

# ─── Idempotency: already-resolved root re-resolves to itself ─────────────────
T="$TMPDIR_TEST/idempotent"
FAKE_HOME="$TMPDIR_TEST/fake_home_idem"
mkdir -p "$FAKE_HOME"
mkdir -p "$T/.workflow_artifacts"
result=$(rpr "$FAKE_HOME" "$T")
assert_eq "(idem) already-resolved root re-resolves to itself" "$T" "$result"

# ─── Empty start_dir: echoes empty string, returns 0 ─────────────────────────
FAKE_HOME="$TMPDIR_TEST/fake_home_empty"
mkdir -p "$FAKE_HOME"
result=$(rpr "$FAKE_HOME" "")
assert_eq "(empty) empty start_dir echoes empty string" "" "$result"

# ─── Summary ─────────────────────────────────────────────────────────────────
printf '\n---\n'
if [ "$FAIL" -eq 0 ]; then
  printf 'PASS: %d  FAIL: 0 — all tests passed\n' "$PASS"
  exit 0
else
  printf 'PASS: %d  FAIL: %d\n' "$PASS" "$FAIL"
  printf 'Failures:%b\n' "$FAIL_MSGS"
  exit 1
fi
