# Quoin + Codex Fresh Repo Discovery Report

## Project Map

Quoin is a workflow-memory toolkit for coding agents. Its durable value is the
portable artifact workflow under `.workflow_artifacts/`, not a single runtime.
The repository currently has a portable core plus adapters:

- `quoin/core/`: shared workflow contracts, skill intent docs, scripts, and
  schemas.
- `quoin/adapters/claude/`: supported Claude adapter behavior and skill bodies.
- `quoin/adapters/codex/`: repo-local Codex scaffold with setup/readiness,
  workflow procedures, handoff validation, and cost-event handling.
- `src/quoin/cli.py`: package CLI. Phase 36 adds `quoin codex init` and
  `quoin doctor --runtime codex`.
- `quoin/benchmarks/`: design-only benchmark framework.
- `benchmark-results/`: measured result evidence.

## Quoin Artifacts Produced

In the isolated fixture, the Codex discover procedure produced:

- `.workflow_artifacts/memory/repos-inventory.md`
- `.workflow_artifacts/memory/architecture-overview.md`
- `.workflow_artifacts/memory/dependencies-map.md`
- `.workflow_artifacts/memory/git-log.md`
- `.workflow_artifacts/cache/_staleness.md`
- `.workflow_artifacts/discovery-map.json`
- `.workflow_artifacts/memory/sessions/2026-05-14-phase-37-live-codex-fixture-benchmarks-codex.md`
- `.workflow_artifacts/phase-37-live-codex-fixture-benchmarks/cost-ledger.md`

The handoff validator passed. The cost validator passed and confirmed one valid
Codex cost event row.

## Checks

Passed:

- `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
- `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
- `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
- `python3 quoin/scripts/generate_discovery_map.py /private/tmp/quoin-phase37-fixture.vQUn26 --quiet`
- `python3 quoin/scripts/validate_discovery_map.py .workflow_artifacts/discovery-map.json`
- `python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/2026-05-14-phase-37-live-codex-fixture-benchmarks-codex.md`
- `python3 quoin/adapters/codex/cost_event.py validate --project-root . --task phase-37-live-codex-fixture-benchmarks --expect-codex`

Targeted pytest:

- Python 3.10.15: 36 passed, 1 skipped, 2 failed.
- The two failures were installer tests that attempted to resolve the
  `hatchling` build dependency over the network.

## What Codex Support Can Do Now

Observed in this run:

- Codex can follow repo-local Quoin procedure docs for discovery.
- Codex can create portable discovery/memory artifacts in `.workflow_artifacts/`.
- Codex can generate and validate a structured discovery map.
- Codex can write and validate explicit session handoff artifacts.
- Codex can append and validate portable cost-ledger rows with unavailable
  telemetry represented as `not_available`.
- Codex readiness/smoke tooling can detect whether the repo-local setup
  contract is coherent.

Still not implemented:

- A global Codex installer.
- Codex command files.
- Live Codex hooks for automatic handoff or cost capture.
- Verified Codex token or dollar telemetry.
- Automated end-to-end Codex workflow execution equivalent to Claude slash
  commands.

## Risks And Unknowns

- Fixture was isolated but dirty, so results should not be used for clean
  release claims.
- Existing `.workflow_artifacts/` state predated the run.
- No cross-runtime parity claim is supported by this evidence.
- Validation is partly environment-sensitive because pytest and build
  dependencies differ across local Python installations.
