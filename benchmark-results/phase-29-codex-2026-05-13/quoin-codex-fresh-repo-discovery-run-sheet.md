# Benchmark Run Sheet

## Run Identity

- Run id: phase-29-codex-fresh-repo-discovery-quoin-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: quoin-codex
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Codex
- Runtime version: not available
- Model or effort setting: not available
- Operator: Codex
- Date: 2026-05-13

## Setup

- Starting state: active checkout, not a clean reset; existing modified and
  untracked Phase 29 files were present before this trial.
- Setup commands: repository inspection commands only; no dependency install.
- Quoin enabled: yes, via repo-local `AGENTS.md`, `quoin/adapters/codex/README.md`,
  and portable `.workflow_artifacts/` semantics.
- Quoin setup evidence: `.workflow_artifacts/phase-29-codex-fresh-repo-discovery/discovery-report.md`
- Known unavailable telemetry: exact runtime version, exact model/effort,
  runtime cost, independent transcript-level turn count.

## Execution Log

- Start time: not available
- End time: not available
- Turn count: not available for this simulated sub-trial; executed within one
  broader Codex assistant turn.
- Restarts or interruptions: none observed
- Commands/checks run: see final report command list
- Files changed: no source files changed by the scenario; benchmark evidence and
  Quoin-mode workflow evidence were written after the discovery output.

## Evidence Collected

- Final answer or summary: `quoin-codex-fresh-repo-discovery-final-report.md`
- Transcript location: not available
- Diff location: not applicable to the scenario; evidence files are in this
  folder.
- Test output location: final assistant report
- Quoin artifact location: `.workflow_artifacts/phase-29-codex-fresh-repo-discovery/discovery-report.md`
- Cost source: not available
- Cost value: not available

## Notes

- Deviations from scenario prompt: this was an operator-run simulation in the
  current active repository, not an isolated fresh clean checkout.
- Runtime issues: no runtime issue observed; Codex-specific cost capture was not
  available.
- Reviewer notes: full Quoin `discover` cache/memory output was not generated to
  avoid overwriting existing project workflow memory.
