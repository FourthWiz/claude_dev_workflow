# Benchmark Result

This file is a filled result for an operator-run benchmark trial.

## Run Identity

- Run id: phase-29-claude-fresh-repo-discovery-quoin-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: quoin-claude
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Claude Code
- Model or effort setting: claude-sonnet-4-6
- Date: 2026-05-13

## Outcome Summary

- Completed: yes, for the `fresh-repo-discovery` scenario only.
- Main outcome: produced a repository discovery report using Quoin memory
  artifacts as context and preserved portable evidence under
  `.workflow_artifacts/phase-29-claude-fresh-repo-discovery/discovery-report.md`.
- Important limitations: not an isolated clean checkout; full `/discover`
  memory/cache output intentionally not generated to avoid overwriting active
  project state; per-mode turn count, elapsed time, and monetary cost not captured.

## Metric Scores

| Metric | Score / value | Evidence |
|---|---:|---|
| Task completion quality | 4 | Report covers project purpose, full structure map, all relevant checks, Quoin workflow context read, 6 risks with detail, recent git history. Slightly more traceable than simple-claude due to explicit Quoin context sourcing. |
| Correctness / tests | 4 | Grounded in direct file reads, shell commands, and Quoin memory artifacts. All six checks run with results recorded. 13 pre-existing failures confirmed. |
| Artifact quality | 4 | Run sheet, result, final report, and portable `.workflow_artifacts/` discovery artifact are coherent and reusable. Full memory/cache set not produced (benchmark-specific scoping). |
| Context reuse | 4 | Read existing `lessons-learned.md` and session-state files from `.workflow_artifacts/memory/`; used `AGENTS.md`, portable core docs, and Codex adapter docs as context beyond the code. |
| Time / turn count | not available | Shared session with simple-claude trial; per-mode turn count not independently captured. |
| Cost if available | not available | Requires post-session JSONL parse; not captured during run. |
| Setup overhead | 3 | Required reading Quoin memory artifacts and adapter guidance in addition to standard repo inspection; minor overhead vs. simple mode. Clean fixture reset unavailable. |

## Verification

- Checks run:
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` — PASSED (6/6 ok)
  - `python3 -m pytest quoin/dev/tests/test_benchmarks.py` — PASSED (6/6)
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` — PASSED (9/9 OK, READY)
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` — PASSED (5/5 OK, SMOKE PASS)
  - `python3 -m pytest quoin/dev/tests/ -q` — 845 passed, 13 failed, 2 skipped, 1 warning
  - `python3 quoin/scripts/build_preambles.py --check` — exit 0
- Checks not run: no dependency install; no isolated clean-checkout rerun.
- Failures observed: same 13 pre-existing failures as simple-claude trial:
  `test_cost_from_jsonl.py` (3), `test_measure_v3_savings.py` (5),
  `test_path_resolve_e2e.py` (5). All pre-date this trial.
- Residual risk: not a clean isolated benchmark run; cross-mode comparisons are
  provisional; full Quoin discover contract not executed (no memory/cache writes).

## Artifacts

- Final answer: `quoin-claude-fresh-repo-discovery-final-report.md`
- Transcript: not available
- Diff: not applicable; only benchmark evidence files created
- Tests: run output recorded in Verification section
- Quoin artifacts: `.workflow_artifacts/phase-29-claude-fresh-repo-discovery/discovery-report.md`
- Cost evidence: not available

## Reviewer Assessment

- Score rationale: The quoin-claude workflow produced a more traceable result
  than simple-claude because it explicitly sourced Quoin memory artifacts
  (lessons-learned, session state) and preserved a portable discovery artifact.
  Artifact quality is higher (4 vs. 3) due to the Quoin `.workflow_artifacts/`
  entry. Context reuse is higher (4 vs. 2) because quoin-claude actively consumed
  prior workflow state. Setup overhead is slightly lower score (3 vs. 4) because
  of the additional Quoin artifact reading step. Both modes ran the same checks
  and found the same failures.
- Cross-mode comparison notes: compare only against the paired simple-claude
  result in this folder and against the Codex modes in
  `phase-29-codex-2026-05-13/` for the same `fresh-repo-discovery` scenario.
  Claude modes score higher than Codex modes on task completion quality and
  correctness/tests because more checks were run and more detail was recorded.
  Quoin-claude scores higher on artifact quality and context reuse than
  simple-claude, as expected. Simple-claude scores higher on setup overhead
  than quoin-claude.
- Follow-up needed before using this result: rerun in an isolated clean checkout
  with per-mode transcript and timing; decide whether full Quoin `/discover`
  memory/cache writes should be enabled in future benchmark trials.
