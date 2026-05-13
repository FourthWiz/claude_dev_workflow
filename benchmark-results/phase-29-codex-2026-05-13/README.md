# Phase 29 Codex Benchmark Trials

This folder records Codex-side Phase 29 benchmark evidence separate from
`quoin/benchmarks/`, which remains design-only.

## Scope

- Fixture repository: this Quoin checkout.
- Fixture revision: `d98792d`.
- Scenario attempted: `fresh-repo-discovery`.
- Comparison modes attempted: `simple-codex`, `quoin-codex`.
- Execution style: simulated/operator-run inside one Codex session, because
  Phase 29 provides benchmark design and templates but no runtime automation.

## Unattempted Scenarios

The remaining Phase 29 scenarios were not run because their required fixture
inputs were not supplied:

- `medium-refactor-plan`: needs a documented target module or subsystem.
- `scoped-code-change`: needs a small issue with a clear behavioral target.
- `review-changes`: needs a prepared review patch with known fixture setup.
- `session-handoff-memory-reuse`: needs a plain or Quoin handoff fixture.

No scores or metrics are inferred for unattempted scenarios.

## Files

- `simple-codex-fresh-repo-discovery-run-sheet.md`
- `simple-codex-fresh-repo-discovery-result.md`
- `simple-codex-fresh-repo-discovery-final-report.md`
- `quoin-codex-fresh-repo-discovery-run-sheet.md`
- `quoin-codex-fresh-repo-discovery-result.md`
- `quoin-codex-fresh-repo-discovery-final-report.md`

Quoin-mode portable evidence is also recorded at
`.workflow_artifacts/phase-29-codex-fresh-repo-discovery/discovery-report.md`.
