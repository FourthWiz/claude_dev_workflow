# Benchmark Result

This file is a filled result for an operator-run benchmark trial.

## Run Identity

- Run id: phase-29-claude-fresh-repo-discovery-simple-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: simple-claude
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Claude Code
- Model or effort setting: claude-sonnet-4-6
- Date: 2026-05-13

## Outcome Summary

- Completed: yes, for the `fresh-repo-discovery` scenario only.
- Main outcome: produced a concise repository discovery report without invoking
  any Quoin workflow artifacts or slash commands.
- Important limitations: not an isolated clean checkout; Phase 29 untracked/modified
  files were present before trial start; per-mode turn count, elapsed time, and
  monetary cost were not captured independently.

## Metric Scores

| Metric | Score / value | Evidence |
|---|---:|---|
| Task completion quality | 4 | Report covers project purpose, all main code/doc areas, how to run checks, and 6 specific risks with detail. Coverage is broader and more precise than the Codex simple-mode equivalent. |
| Correctness / tests | 4 | Discovery grounded in direct file reads and shell commands. All six checks were run; results recorded including exact failure categories (13 pre-existing). No source behavior was tested (scenario is read-only). |
| Artifact quality | 3 | Run sheet, result, and final report are complete and reusable. No transcript available; two modes share a session so turn count is not independently measured. |
| Context reuse | 2 | Simple mode did not use any prior Quoin artifacts or session state. Context came entirely from live file reads in this session. |
| Time / turn count | not available | Executed inside one shared operator session alongside quoin-claude trial; per-mode turn count not independently captured. |
| Cost if available | not available | Monetary cost requires reading post-session JSONL; not captured during run. |
| Setup overhead | 4 | No install steps required; standard Claude Code file-read and shell tools sufficient. Clean fixture reset was unavailable, which counts as a minor limitation. |

## Verification

- Checks run:
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` — PASSED (6/6 ok)
  - `python3 -m pytest quoin/dev/tests/test_benchmarks.py` — PASSED (6/6)
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` — PASSED (9/9 OK, READY)
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` — PASSED (5/5 OK, SMOKE PASS)
  - `python3 -m pytest quoin/dev/tests/ -q` — 845 passed, 13 failed, 2 skipped, 1 warning
  - `python3 quoin/scripts/build_preambles.py --check` — exit 0 (no output = pass)
- Checks not run: no dependency installation was attempted; no isolated
  clean-checkout rerun was performed.
- Failures observed: 13 pre-existing failures in `test_cost_from_jsonl.py`
  (3 ccusage parity), `test_measure_v3_savings.py` (5 missing fixture), and
  `test_path_resolve_e2e.py` (5 resolver/inflight assertions). All confirmed
  pre-existing per matching Codex trial results.
- Residual risk: not a clean isolated benchmark run; cross-mode comparisons are
  provisional; per-mode telemetry (time, cost, turn count) not captured.

## Artifacts

- Final answer: `simple-claude-fresh-repo-discovery-final-report.md`
- Transcript: not available
- Diff: not applicable to scenario output; benchmark evidence files created
- Tests: run output recorded in result Verification section
- Quoin artifacts: not applicable
- Cost evidence: not available

## Reviewer Assessment

- Score rationale: Simple Claude workflow produced a thorough, well-structured
  repository map by using Claude Code's native file-read and shell tools directly.
  It identified all six major risk categories, ran all checks, and recorded exact
  failure counts. The main limitation is shared-session telemetry: per-mode turn
  count and elapsed time are unavailable.
- Cross-mode comparison notes: compare only against the paired quoin-claude
  result in this folder and against the Codex modes in
  `phase-29-codex-2026-05-13/` for the same `fresh-repo-discovery` scenario.
- Follow-up needed before using this result: rerun in an isolated clean checkout
  with per-mode transcript and timing capture.
