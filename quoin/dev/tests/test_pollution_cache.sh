#!/bin/sh
# test_pollution_cache.sh — fixture tests for the counts+offset cache in
# compute_pollution_score's jq path (quoin/hooks/_lib.sh, Stage 3, IVG-163).
#
# Mirrors the test_userpromptsubmit_hook.sh pattern: set -eu, PASS/FAIL
# counters, ok()/fail(), a per-run TMPDIR_TEST with a cleanup trap, sh (not
# bash). This file is NOT collected by pytest (python_files = "test_*.py")
# — test_pollution_score_extraction.py::TestPollutionCache is the
# suite-enforced guard for the same 5 cases; this file exercises the real
# platform's sh/dd/tail/sed/awk idioms directly.
#
# Requires: jq on PATH (the optimization is jq-only — skips with exit 0 and
# a printed notice if jq is absent), sh (POSIX).
#
# Usage: sh quoin/dev/tests/test_pollution_cache.sh
# Exit 0 if all tests pass (or jq is absent); non-zero with a failure list
# otherwise.

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

if ! command -v jq > /dev/null 2>&1; then
  printf 'SKIP: jq not on PATH; the pollution cache lives only on the jq path\n'
  exit 0
fi

TMPDIR_TEST="${TMPDIR:-/tmp}/test_pollution_cache_$$"
mkdir -p "$TMPDIR_TEST"
cleanup() { rm -rf "$TMPDIR_TEST"; }
trap cleanup EXIT

# ─── helpers ──────────────────────────────────────────────────────────────────

# tool_line <name> — one real-shape assistant tool_use JSONL line.
tool_line() {
  printf '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"toolu_01","name":"%s","input":{}}]}}\n' "$1"
}

# build_fixture <outfile> <agent_n> <read_n> <bash_n> — write N tool_use
# lines of each kind to outfile (truncates any existing content).
build_fixture() {
  outfile="$1"
  agent_n="$2"
  read_n="$3"
  bash_n="$4"
  : > "$outfile"
  i=0
  while [ "$i" -lt "$agent_n" ]; do tool_line Agent >> "$outfile"; i=$((i + 1)); done
  i=0
  while [ "$i" -lt "$read_n" ]; do tool_line Read >> "$outfile"; i=$((i + 1)); done
  i=0
  while [ "$i" -lt "$bash_n" ]; do tool_line Bash >> "$outfile"; i=$((i + 1)); done
}

# score_in <cache_dir> <transcript> — echo the score, using cache_dir as TMPDIR.
score_in() {
  cache_dir="$1"
  transcript="$2"
  TMPDIR="$cache_dir" sh -c ". \"$LIB\" && compute_pollution_score \"$transcript\""
}

# cold_score <transcript> — score with a brand-new isolated TMPDIR (no cache reuse).
cold_score() {
  transcript="$1"
  cold_dir="$TMPDIR_TEST/cold_$$_$RANDOM_SEED"
  RANDOM_SEED=$((RANDOM_SEED + 1))
  mkdir -p "$cold_dir"
  score_in "$cold_dir" "$transcript"
}
RANDOM_SEED=0

# cache_file_in <cache_dir> — echo the single quoin-pollution-*.cache path.
cache_file_in() {
  cache_dir="$1"
  found=""
  for f in "$cache_dir"/quoin-pollution-*.cache; do
    [ -e "$f" ] || continue
    if [ -n "$found" ]; then
      printf 'MULTIPLE_CACHE_FILES\n'
      return 1
    fi
    found="$f"
  done
  [ -n "$found" ] || { printf 'NO_CACHE_FILE\n'; return 1; }
  printf '%s\n' "$found"
}

# ─── (1) cold ─────────────────────────────────────────────────────────────────

CD1="$TMPDIR_TEST/case1"
mkdir -p "$CD1"
F1="$TMPDIR_TEST/cold.jsonl"
build_fixture "$F1" 1 2 3
s1=$(score_in "$CD1" "$F1")
cf1=$(cache_file_in "$CD1") || { fail "(cold) cache file not created"; cf1=""; }
if [ -n "$cf1" ]; then
  nfields=$(awk '{print NF}' "$cf1")
  if [ "$nfields" -eq 5 ]; then
    ok "(cold) cache file has exactly 5 fields"
  else
    fail "(cold) cache file has $nfields fields, expected 5"
  fi
  off1=$(awk '{print $1}' "$cf1")
  sz1=$(wc -c < "$F1" | awk '{print $1}')
  if [ "$off1" -le "$sz1" ]; then
    ok "(cold) offset ($off1) <= file size ($sz1)"
  else
    fail "(cold) offset ($off1) > file size ($sz1)"
  fi
fi

# ─── (2) warm-append + cold-vs-warm equivalence ───────────────────────────────

CD2="$TMPDIR_TEST/case2"
mkdir -p "$CD2"
F2="$TMPDIR_TEST/warm.jsonl"
build_fixture "$F2" 1 1 1
w_first=$(score_in "$CD2" "$F2")
{
  tool_line Agent
  tool_line Agent
  tool_line Read
} >> "$F2"
w_warm=$(score_in "$CD2" "$F2")
w_cold=$(cold_score "$F2")
if [ "$w_warm" -eq "$w_cold" ]; then
  ok "(warm-append) warm score ($w_warm) equals cold score of final file ($w_cold)"
else
  fail "(warm-append) warm score ($w_warm) != cold score ($w_cold)"
fi

# ─── (3) truncate-rotation ─────────────────────────────────────────────────────

CD3="$TMPDIR_TEST/case3"
mkdir -p "$CD3"
F3="$TMPDIR_TEST/rotate.jsonl"
build_fixture "$F3" 5 5 5
score_in "$CD3" "$F3" > /dev/null
build_fixture "$F3" 1 0 0
r_after=$(score_in "$CD3" "$F3")
r_cold=$(cold_score "$F3")
if [ "$r_after" -eq "$r_cold" ]; then
  ok "(truncate-rotation) post-rotation score ($r_after) equals fresh cold score ($r_cold)"
else
  fail "(truncate-rotation) post-rotation score ($r_after) != fresh cold score ($r_cold)"
fi

# ─── (4) corrupt-cache ──────────────────────────────────────────────────────────

CD4="$TMPDIR_TEST/case4"
mkdir -p "$CD4"
F4="$TMPDIR_TEST/corrupt.jsonl"
build_fixture "$F4" 2 2 2
score_in "$CD4" "$F4" > /dev/null
cf4=$(cache_file_in "$CD4") || { fail "(corrupt-cache) no cache file to corrupt"; cf4=""; }
if [ -n "$cf4" ]; then
  printf 'not a cache line at all' > "$cf4"
  c_after=$(score_in "$CD4" "$F4")
  c_cold=$(cold_score "$F4")
  if [ "$c_after" -eq "$c_cold" ]; then
    ok "(corrupt-cache) garbage-content re-score ($c_after) equals cold score ($c_cold)"
  else
    fail "(corrupt-cache) garbage-content re-score ($c_after) != cold score ($c_cold)"
  fi
fi

# ─── (5) in-place-rewrite (head-fingerprint mismatch) ──────────────────────────

CD5="$TMPDIR_TEST/case5"
mkdir -p "$CD5"
F5="$TMPDIR_TEST/rewrite.jsonl"
build_fixture "$F5" 1 1 1
score_in "$CD5" "$F5" > /dev/null
orig_size=$(wc -c < "$F5" | awk '{print $1}')
build_fixture "$F5" 3 0 0
new_size=$(wc -c < "$F5" | awk '{print $1}')
if [ "$new_size" -lt "$orig_size" ]; then
  pad=$((orig_size - new_size))
  awk -v n="$pad" 'BEGIN{ s=""; for (i=0;i<n;i++) s = s "x"; printf "%s", s }' >> "$F5"
elif [ "$new_size" -gt "$orig_size" ]; then
  cp "$F5" "$F5.tmp"
  head -c "$orig_size" "$F5.tmp" > "$F5"
  rm -f "$F5.tmp"
fi
final_size=$(wc -c < "$F5" | awk '{print $1}')
if [ "$final_size" -eq "$orig_size" ]; then
  ok "(in-place-rewrite) rewrite kept the same byte length ($final_size)"
else
  fail "(in-place-rewrite) rewrite length ($final_size) != original length ($orig_size)"
fi
rw_after=$(score_in "$CD5" "$F5")
rw_cold=$(cold_score "$F5")
if [ "$rw_after" -eq "$rw_cold" ]; then
  ok "(in-place-rewrite) re-score ($rw_after) equals cold score ($rw_cold)"
else
  fail "(in-place-rewrite) re-score ($rw_after) != cold score ($rw_cold)"
fi

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
