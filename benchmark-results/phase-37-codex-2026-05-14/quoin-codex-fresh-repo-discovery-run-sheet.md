# Benchmark Run Sheet

## Run Identity

- Run id: phase-37-quoin-codex-fresh-repo-discovery-2026-05-14
- Scenario id: fresh-repo-discovery
- Comparison mode: quoin-codex
- Fixture repository: `/private/tmp/quoin-phase37-fixture.vQUn26`
- Fixture revision: `90745111078a06f090a37e91ea3c13382c3de24f` plus dirty working tree snapshot
- Runtime: Codex
- Runtime version: not_available
- Model or effort setting: high effort recorded in Codex cost row; live model/effort telemetry not_available
- Operator: Codex
- Date: 2026-05-14 local time; Codex cost row timestamp is 2026-05-13 UTC

## Setup

- Starting state: same isolated dirty fixture used for simple-codex.
- Setup commands:
  - `mkdir -p .workflow_artifacts/memory/sessions .workflow_artifacts/cache .workflow_artifacts/phase-37-live-codex-fixture-benchmarks`
- Quoin enabled: yes
- Quoin setup evidence:
  - Read `quoin/adapters/codex/procedures/discover.md`
  - Wrote `.workflow_artifacts/memory/repos-inventory.md`
  - Wrote `.workflow_artifacts/memory/architecture-overview.md`
  - Wrote `.workflow_artifacts/memory/dependencies-map.md`
  - Wrote `.workflow_artifacts/memory/git-log.md`
  - Wrote `.workflow_artifacts/cache/_staleness.md`
  - Generated `.workflow_artifacts/discovery-map.json`
  - Wrote and validated `.workflow_artifacts/memory/sessions/2026-05-14-phase-37-live-codex-fixture-benchmarks-codex.md`
  - Wrote and validated `.workflow_artifacts/phase-37-live-codex-fixture-benchmarks/cost-ledger.md`
- Known unavailable telemetry: Codex runtime version, model/effort telemetry, turn count, token counts, and dollar cost.

## Execution Log

- Start time: 2026-05-14 01:07:26 +04
- End time: 2026-05-14 01:09:21 +04
- Turn count: not_available
- Restarts or interruptions: none
- Commands/checks run:
  - `rg --files .workflow_artifacts`
  - `git log --oneline -5`
  - `git status --short`
  - `python3 quoin/scripts/generate_discovery_map.py /private/tmp/quoin-phase37-fixture.vQUn26 --quiet` - passed
  - `python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/2026-05-14-phase-37-live-codex-fixture-benchmarks-codex.md` - passed
  - `python3 quoin/adapters/codex/cost_event.py write --project-root . --task phase-37-live-codex-fixture-benchmarks --phase discover --effort high` - wrote one row
  - `python3 quoin/adapters/codex/cost_event.py validate --project-root . --task phase-37-live-codex-fixture-benchmarks --expect-codex` - passed
  - `python3 quoin/scripts/validate_discovery_map.py .workflow_artifacts/discovery-map.json` - passed
- Files changed: only isolated fixture workflow artifacts.

## Evidence Collected

- Final answer or summary: `quoin-codex-fresh-repo-discovery-final-report.md`
- Transcript location: not_available
- Diff location: fixture artifact writes listed above
- Test output location: this run sheet and result verification section
- Quoin artifact location: `/private/tmp/quoin-phase37-fixture.vQUn26/.workflow_artifacts/`
- Cost source: `.workflow_artifacts/phase-37-live-codex-fixture-benchmarks/cost-ledger.md`
- Cost value: `not_available` for token and dollar telemetry; one valid Codex event row recorded

## Notes

- Deviations from scenario prompt: Quoin mode wrote workflow artifacts as required by Phase 33-36 procedures; existing fixture artifacts predated this run.
- Runtime issues: no live Codex telemetry surface was available in-repo.
- Reviewer notes: stronger continuation evidence than simple-codex, but not evidence of Claude parity.
