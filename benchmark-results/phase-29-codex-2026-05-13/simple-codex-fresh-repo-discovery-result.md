# Benchmark Result Template

This file is a filled result for a simulated/operator-run benchmark trial.

## Run Identity

- Run id: phase-29-codex-fresh-repo-discovery-simple-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: simple-codex
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Codex
- Model or effort setting: not available
- Date: 2026-05-13

## Outcome Summary

- Completed: yes, for the `fresh-repo-discovery` scenario only.
- Main outcome: produced a concise repository discovery report without invoking
  Quoin workflow artifacts.
- Important limitations: not an isolated clean checkout; exact runtime version,
  model/effort, transcript, elapsed time, and cost telemetry were unavailable.

## Metric Scores

| Metric | Score / value | Evidence |
|---|---:|---|
| Task completion quality | 3 | The report identifies project purpose, main code/docs, checks, inspected files, and risks. Minor limitation: active dirty fixture, not clean checkout. |
| Correctness / tests | 3 | Discovery was grounded in file reads and git commands. Relevant benchmark checks were run after evidence recording. No source behavior was tested because scenario was read-only. |
| Artifact quality | 3 | Final report and run sheet are reusable, but no transcript is available. |
| Context reuse | 2 | Used repo instructions and inspected benchmark docs. No prior handoff context was part of this scenario. |
| Time / turn count | not available | Executed inside one broader Codex turn; independent start/end and turn count were not captured. |
| Cost if available | not available | Codex cost collector is not implemented in this repository and runtime cost was not exposed. |
| Setup overhead | 3 | Setup was limited to inspecting benchmark instructions and repository structure. Clean fixture reset was unavailable. |

## Verification

- Checks run: `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` passed; `pytest quoin/dev/tests/test_benchmarks.py` passed 6 tests; `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` passed; `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` passed; `pytest quoin/dev/tests/` ran with failures; `python3 quoin/scripts/build_preambles.py --check` ran with a dependency failure; `python3 -m pytest quoin/dev/tests/test_benchmarks.py` was attempted and failed because `/usr/local/bin/python3` has no `pytest` module.
- Checks not run: no dependency installation was attempted; no isolated clean-checkout rerun was performed.
- Failures observed: `python3 -m pytest quoin/dev/tests/test_benchmarks.py` failed with `No module named pytest`; `python3 quoin/scripts/build_preambles.py --check` failed because `pyyaml` is missing; full `pytest quoin/dev/tests/` reported 13 failed, 845 passed, 2 skipped, 1 warning, with failures in `test_cost_from_jsonl.py` ccusage version timeouts, `test_measure_v3_savings.py` missing `.workflow_artifacts/v3-stage-4-smoke/current-plan.md`, and `test_path_resolve_e2e.py` existing resolver/inflight fixture assertions.
- Residual risk: this was not a clean, isolated benchmark run, so cross-mode
  comparisons should be treated as provisional evidence only.

## Artifacts

- Final answer: `simple-codex-fresh-repo-discovery-final-report.md`
- Transcript: not available
- Diff: not applicable to scenario output; benchmark evidence files changed
- Tests: final assistant report
- Quoin artifacts: not applicable
- Cost evidence: not available

## Reviewer Assessment

- Score rationale: The simple Codex workflow produced the requested repository
  map with reasonable scope control and explicit unknowns, but lacks isolated
  transcript and timing evidence.
- Cross-mode comparison notes: compare only against the paired Quoin Codex result
  in this folder and only for the same `fresh-repo-discovery` scenario.
- Follow-up needed before using this result: rerun in an isolated clean checkout
  with transcript and timing capture.
