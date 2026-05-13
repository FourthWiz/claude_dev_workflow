# Simple Codex Fresh Repo Discovery Report

## Project Map

Quoin is a workflow-memory toolkit for coding agents. The project centers on a
portable `.workflow_artifacts/` contract for plans, reviews, session handoff,
lessons, and cost ledgers, with thin runtime adapters for specific agent
environments.

Main locations:

- `src/quoin/`: Python package and CLI entrypoint. Phase 36 adds Codex-oriented
  CLI paths in `src/quoin/cli.py`.
- `quoin/core/`: portable skill contracts, workflow docs, schemas, and shared
  scripts.
- `quoin/adapters/claude/`: installable Claude adapter behavior.
- `quoin/adapters/codex/`: repo-local Codex setup docs, generated skill docs,
  workflow procedures, readiness/smoke checks, handoff validation, and cost
  event handling.
- `quoin/benchmarks/`: Phase 29 design-only benchmark framework.
- `quoin/dev/tests/`: deterministic unit, smoke, adapter, CLI, and fixture tests.
- `benchmark-results/`: measured benchmark evidence folders, intentionally
  outside `quoin/benchmarks/`.

## How To Check It

Useful checks observed in this fixture:

- `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
- `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
- `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
- `/Users/ivgo/.pyenv/versions/3.10.15/bin/python -m pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py quoin/dev/tests/test_quoin_cli.py`

## Codex Support Observed

Codex support is repo-local and scaffolded, not globally installed. It can:

- Use `AGENTS.md` for repo-local instructions.
- Validate Codex readiness and smoke paths.
- Use documented workflow procedures for `discover`, `plan`, `implement`,
  `review`, and `gate`.
- Validate handoff artifacts.
- Write Codex cost events with unavailable token/dollar fields explicitly marked
  `not_available`.
- Expose setup/readiness through `quoin codex init` and
  `quoin doctor --runtime codex`.

It does not currently provide:

- Codex global install behavior.
- Codex command files.
- Live Codex hooks.
- Verified Codex token or dollar telemetry.
- Automatic parity with the Claude adapter.

## Risks And Unknowns

- The fixture was isolated but dirty; Phase 34-36 files were uncommitted.
- Existing `.workflow_artifacts/` in the fixture meant this was not a blank
  fresh-memory repo.
- Targeted pytest did not fully pass because two installer-equivalence tests
  attempted to fetch `hatchling` without network access.
- Default interpreter paths were inconsistent: `/usr/local/bin/python3` was
  Python 3.12 without pytest; `pytest` shim used Python 3.8; Python 3.10.15 was
  needed for test collection.
