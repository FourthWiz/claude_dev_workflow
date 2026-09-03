#!/bin/sh
# test_lib_run_state_probe.sh — direct unit tests for run_state_probe() in
# quoin/hooks/_lib.sh.
#
# Sources _lib.sh in a tmpdir and exercises the probe directly (not through a
# hook script). Single-mode probe (D-26/D-27): no at_stage_boundary
# distinction, SESSION_ID argument optional and currently uncalled by every
# consumer (D-27) but still asserted here for forward compatibility.
#
# Usage: sh quoin/dev/tests/test_lib_run_state_probe.sh
# Exit 0 if all tests pass; non-zero otherwise.

set -eu

PASS=0
FAIL=0
FAIL_MSGS=""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../../hooks/_lib.sh"

ok() { PASS=$((PASS + 1)); printf 'ok  %s\n' "$1"; }
fail() {
  FAIL=$((FAIL + 1))
  printf 'FAIL %s\n' "$1" >&2
  FAIL_MSGS="$FAIL_MSGS\n  - $1"
}

TMPDIR_TEST="${TMPDIR:-/tmp}/test_lib_rsp_$$"
MEMDIR="$TMPDIR_TEST/.workflow_artifacts/memory"
mkdir -p "$MEMDIR"

cleanup() { rm -rf "$TMPDIR_TEST" "$PWN_MARKER" 2>/dev/null || true; }
trap cleanup EXIT

PWN_MARKER="${TMPDIR:-/tmp}/quoin-pwn-rsp-test-$$"
STDOUT_CAP="$TMPDIR_TEST/.stdout"
STDERR_CAP="$TMPDIR_TEST/.stderr"

. "$LIB"

# call_probe DIR [SID] — runs run_state_probe, capturing rc/stdout/stderr into
# CP_RC / CP_OUT / CP_ERR. Every call site doubles as case (k)'s emits-nothing
# assertion via assert_silent below.
call_probe() {
  set +e
  run_state_probe "$1" "${2:-}" >"$STDOUT_CAP" 2>"$STDERR_CAP"
  CP_RC=$?
  set -e
  CP_OUT=$(cat "$STDOUT_CAP")
  CP_ERR=$(cat "$STDERR_CAP")
}

assert_silent() {
  # $1 — case label, used only in the failure message
  if [ -n "$CP_OUT" ] || [ -n "$CP_ERR" ]; then
    fail "(k) $1: probe emitted output — stdout=[$CP_OUT] stderr=[$CP_ERR]"
  else
    ok "(k) $1: silent stdout/stderr"
  fi
}

record() {
  # record PATH ACTIVE SCHEMA AT_STAGE_BOUNDARY [SESSION_ID]
  _r_path="$1"
  _r_active="$2"
  _r_schema="$3"
  _r_boundary="$4"
  _r_sid="${5:-}"
  {
    printf '{\n'
    printf '  "task": "canary",\n'
    printf '  "active": %s,\n' "$_r_active"
    printf '  "schema": %s,\n' "$_r_schema"
    printf '  "at_stage_boundary": %s' "$_r_boundary"
    if [ -n "$_r_sid" ]; then
      printf ',\n  "session_id": "%s"\n' "$_r_sid"
    else
      printf '\n'
    fi
    printf '}\n'
  } > "$_r_path"
}

stale_touch() {
  # stale_touch PATH DAYS_AGO — force mtime N days in the past, portable
  # between BSD (darwin) and GNU touch/date.
  _st_path="$1"
  _st_days="$2"
  _st_ts=$(date -v-"${_st_days}"d +%Y%m%d0000 2>/dev/null || date -d "${_st_days} days ago" +%Y%m%d0000)
  touch -t "$_st_ts" "$_st_path"
}

# ─── (a) no memory dir ─────────────────────────────────────────────────────

call_probe "$TMPDIR_TEST/does-not-exist"
[ "$CP_RC" -ne 0 ] && ok "(a) no memory dir -> 1" || fail "(a) no memory dir should return 1"
assert_silent "(a)"

# ─── (b) memory dir, no record ─────────────────────────────────────────────

call_probe "$MEMDIR"
[ "$CP_RC" -ne 0 ] && ok "(b) memory dir, no record -> 1" || fail "(b) memory dir, no record should return 1"
assert_silent "(b)"

# ─── (c) fresh record, active: true — boundary false AND boundary true ────

REC="$MEMDIR/run-state-canary.json"
record "$REC" true 1 false
call_probe "$MEMDIR"
[ "$CP_RC" -eq 0 ] && ok "(c) fresh active, at_stage_boundary:false -> 0" || fail "(c) fresh active, boundary:false should return 0"
assert_silent "(c) boundary:false"

record "$REC" true 1 true
call_probe "$MEMDIR"
[ "$CP_RC" -eq 0 ] && ok "(c) fresh active, at_stage_boundary:true -> 0" || fail "(c) fresh active, boundary:true should return 0 (probe does not distinguish boundary state, D-26)"
assert_silent "(c) boundary:true"

# ─── (d) active: false ──────────────────────────────────────────────────────

record "$REC" false 1 false
call_probe "$MEMDIR"
[ "$CP_RC" -ne 0 ] && ok "(d) active:false -> 1" || fail "(d) active:false should return 1"
assert_silent "(d)"

# ─── (e) schema: 2 ──────────────────────────────────────────────────────────

record "$REC" true 2 false
call_probe "$MEMDIR"
[ "$CP_RC" -ne 0 ] && ok "(e) schema:2 -> 1" || fail "(e) schema:2 (schema-forward) should return 1"
assert_silent "(e)"

# ─── (f) stale mtime, well past the widened default window ────────────────
# The probe's default window was widened from ~2 days to ~15 days — see (f2)
# below for the scenario that motivated the widening; 30 days is safely
# outside it either way.

record "$REC" true 1 false
stale_touch "$REC" 30
call_probe "$MEMDIR"
[ "$CP_RC" -ne 0 ] && ok "(f) stale record (30d, past the widened default window) -> 1" || fail "(f) stale record (30d) should return 1"
assert_silent "(f)"

# ─── (f2) active-but-moderately-stale record still probes ACTIVE ──────────
# 5 days exceeds the PRE-FIX ~2-day default window but sits well inside the
# widened default (~15 days) — the exact "long /implement, or a run paused
# over a weekend" scenario that motivated widening it: /run only refreshes
# the record at phase boundaries, so a phase or pause outliving a too-tight
# window would silently skip the 90% self-checkpoint even though the record
# was genuinely still active.

record "$REC" true 1 false
stale_touch "$REC" 5
call_probe "$MEMDIR"
[ "$CP_RC" -eq 0 ] && ok "(f2) active record aged 5d still probes ACTIVE under the widened default window" || fail "(f2) active record aged 5d should probe ACTIVE"
assert_silent "(f2)"

# ─── (g) knob injection regression ─────────────────────────────────────────
# No eligible record present (mirrors the spike's own guard test) — this
# case is purely about the knob's numeric validation rejecting the payload
# before it reaches $(( )) or find, not about record eligibility.

rm -f "$REC"
rm -f "$PWN_MARKER"
set +e
QUOIN_RUN_STATE_STALE_DAYS="q[\$(touch $PWN_MARKER)]" run_state_probe "$MEMDIR" >"$STDOUT_CAP" 2>"$STDERR_CAP"
CP_RC=$?
set -e
CP_OUT=$(cat "$STDOUT_CAP")
CP_ERR=$(cat "$STDERR_CAP")
[ "$CP_RC" -ne 0 ] && ok "(g) injection knob -> 1 (falls back to the default day count)" || fail "(g) injection knob should return 1"
if [ -f "$PWN_MARKER" ]; then
  fail "(g) injection knob executed — command injection regression"
else
  ok "(g) injection knob did not execute"
fi
assert_silent "(g)"

# ─── (h) leading-zero knob under bash-as-/bin/sh ───────────────────────────

record "$REC" true 1 false
set +e
QUOIN_RUN_STATE_STALE_DAYS=08 run_state_probe "$MEMDIR" >"$STDOUT_CAP" 2>"$STDERR_CAP"
CP_RC=$?
set -e
CP_OUT=$(cat "$STDOUT_CAP")
CP_ERR=$(cat "$STDERR_CAP")
if [ "$CP_RC" -eq 0 ] || [ "$CP_RC" -eq 1 ]; then
  ok "(h) leading-zero knob (08) does not error under bash-as-/bin/sh"
else
  fail "(h) leading-zero knob (08) produced an unexpected exit code ($CP_RC) — likely an arithmetic error"
fi
assert_silent "(h)"

# ─── (i) two records, one eligible ─────────────────────────────────────────

record "$MEMDIR/run-state-other-task.json" false 1 false
record "$REC" true 1 false
call_probe "$MEMDIR"
[ "$CP_RC" -eq 0 ] && ok "(i) two records, one eligible -> 0" || fail "(i) two records, one eligible should return 0"
assert_silent "(i)"
rm -f "$MEMDIR/run-state-other-task.json"

# ─── (j) SESSION_ID equal / mismatched (incl. regex-metachar guard) ───────

record "$REC" true 1 false "sid-abc-123"
call_probe "$MEMDIR" "sid-abc-123"
[ "$CP_RC" -eq 0 ] && ok "(j) SESSION_ID equal to record's own -> 0" || fail "(j) SESSION_ID equal should return 0"
assert_silent "(j) equal"

call_probe "$MEMDIR" "sid-other-party"
[ "$CP_RC" -ne 0 ] && ok "(j) SESSION_ID mismatched -> 1" || fail "(j) SESSION_ID mismatched should return 1"
assert_silent "(j) mismatched"

# Fixed-string regression: eligible record's session_id has an 'X' where a
# regex '.' metacharacter, if unescaped, would wrongly match. A mismatched
# argument that substitutes '.' for that 'X' must NOT be treated as a
# wildcard by grep -qF.
record "$REC" true 1 false "sidXabc123"
call_probe "$MEMDIR" "sid.abc123"
[ "$CP_RC" -ne 0 ] && ok "(j) SESSION_ID with '.' metacharacter does not falsely match -> 1" || fail "(j) '.' in mismatched SESSION_ID must not act as a regex wildcard (grep -qF required)"
assert_silent "(j) dot-metachar mismatch"

# Newline regression: grep -F treats a multi-line pattern as a pattern
# LIST, so a session id containing a literal newline fragment-matches any
# record line equal to one of its lines — reproduced here with a trailing
# "schema" line fragment that collides with this record's own "schema": 1
# line. A session id arriving from hook stdin JSON can legally contain
# '\n'; plain string equality (post-fix) cannot fragment-match, so this
# must mismatch even though the eligible record's real session_id is
# unrelated.
record "$REC" true 1 false "sid-REAL"
call_probe "$MEMDIR" "$(printf 'zzz\nschema')"
[ "$CP_RC" -ne 0 ] && ok "(j) newline-bearing SESSION_ID does not fragment-match -> 1" || fail "(j) newline-bearing SESSION_ID must not match via grep -F pattern-list semantics"
assert_silent "(j) newline mismatch"

# ─── (l) knob clamp — 5+ digit day count does not reach unclamped arithmetic ──
# A record aged 30 days would probe ACTIVE if the knob's huge digit string
# reached $(( )) / find unclamped; the clamp caps it to 36500 by length
# alone, and 30 days is still comfortably inside a 100y window, so this only
# proves the knob did not error out or silently disable the whole window.

record "$REC" true 1 false
stale_touch "$REC" 30
set +e
QUOIN_RUN_STATE_STALE_DAYS="99999999999999999999" run_state_probe "$MEMDIR" >"$STDOUT_CAP" 2>"$STDERR_CAP"
CP_RC=$?
set -e
CP_OUT=$(cat "$STDOUT_CAP")
CP_ERR=$(cat "$STDERR_CAP")
[ "$CP_RC" -eq 0 ] && ok "(l) oversized digit-string knob clamps instead of erroring or overflowing" || fail "(l) oversized digit-string knob should clamp to a usable window, not error"
assert_silent "(l)"

# ─── (m) glob metacharacter in a candidate filename ────────────────────────
# `set -- $(find ...)` on its own suppresses word-splitting but not pathname
# expansion — a literal '*' in a run-state filename is a real (if unusual)
# possibility this record's own name self-matches under expansion, so this
# is a base-case robustness check for the `set -f`/`set +f` guard around the
# capture, not a differential exploit reproduction (the review's own
# characterization — "wrong candidate set, double-probe" — is a candidate-
# count/performance effect, not one directly observable via a single probe's
# exit code).

GLOB_REC="$MEMDIR/run-state-glob-*-task.json"
record "$GLOB_REC" true 1 false
call_probe "$MEMDIR"
[ "$CP_RC" -eq 0 ] && ok "(m) glob-metacharacter filename probes ACTIVE without re-expanding" || fail "(m) a '*' in a candidate filename must not re-expand against cwd/dir entries"
assert_silent "(m)"
rm -f "$GLOB_REC"

# ─── Summary ────────────────────────────────────────────────────────────────

printf '\n'
if [ "$FAIL" -eq 0 ]; then
  printf 'PASS: all %d tests passed\n' "$PASS"
  exit 0
else
  printf 'FAIL: %d/%d tests failed:\n' "$FAIL" "$((PASS + FAIL))" >&2
  printf '%b\n' "$FAIL_MSGS" >&2
  exit 1
fi
