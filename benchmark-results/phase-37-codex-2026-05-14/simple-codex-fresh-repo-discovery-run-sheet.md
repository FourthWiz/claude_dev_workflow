# Benchmark Run Sheet

## Run Identity

- Run id: phase-37-simple-codex-fresh-repo-discovery-2026-05-14
- Scenario id: fresh-repo-discovery
- Comparison mode: simple-codex
- Fixture repository: `/private/tmp/quoin-phase37-fixture.vQUn26`
- Fixture revision: `90745111078a06f090a37e91ea3c13382c3de24f` plus dirty working tree snapshot
- Runtime: Codex
- Runtime version: not_available
- Model or effort setting: not_available
- Operator: Codex
- Date: 2026-05-14

## Setup

- Starting state: isolated temporary copy of the Quoin checkout; dirty because Phase 34-36 Codex changes were uncommitted in the source checkout.
- Setup commands:
  - `mktemp -d /private/tmp/quoin-phase37-fixture.XXXXXX`
  - `rsync -a --exclude __pycache__ ./ /private/tmp/quoin-phase37-fixture.vQUn26/`
- Quoin enabled: no
- Quoin setup evidence: not applicable for simple-codex; no Quoin artifacts were intentionally written during the simple-mode scenario.
- Known unavailable telemetry: Codex runtime version, model/effort, turn count, token counts, and dollar cost.

## Execution Log

- Start time: 2026-05-14 01:05:48 +04
- End time: 2026-05-14 01:07:15 +04
- Turn count: not_available
- Restarts or interruptions: none
- Commands/checks run:
  - `sed -n '1,180p' README.md`
  - `sed -n '1,180p' AGENTS.md`
  - `sed -n '1,220p' pyproject.toml`
  - `rg --files src quoin/core quoin/adapters/codex quoin/benchmarks quoin/dev/tests`
  - `sed -n '1,220p' quoin/adapters/codex/README.md`
  - `sed -n '1,220p' quoin/docs/runtime-portability-status.md`
  - `sed -n '1,520p' src/quoin/cli.py`
  - `sed -n '1,220p' quoin/core/workflow/task-layout.md`
  - `sed -n '1,220p' quoin/core/workflow/cost-ledger.md`
  - `sed -n '1,220p' quoin/adapters/codex/procedures/discover.md`
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` - passed
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` - passed
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` - passed
  - `python3 -m pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py quoin/dev/tests/test_quoin_cli.py` - failed, `/usr/local/bin/python3: No module named pytest`
  - `pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py quoin/dev/tests/test_quoin_cli.py` - failed under Python 3.8 with SyntaxError collecting `test_quoin_cli.py`
  - `/Users/ivgo/.pyenv/versions/3.10.15/bin/python -m pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py quoin/dev/tests/test_quoin_cli.py` - 36 passed, 1 skipped, 2 failed
- Files changed: no source files changed by the simple-mode scenario; pytest wrote cache files inside the isolated fixture.

## Evidence Collected

- Final answer or summary: `simple-codex-fresh-repo-discovery-final-report.md`
- Transcript location: not_available
- Diff location: not applicable; no source edits
- Test output location: this run sheet and result verification section
- Quoin artifact location: not applicable for simple-codex
- Cost source: not_available
- Cost value: not_available

## Notes

- Deviations from scenario prompt: deterministic Codex readiness/smoke checks were also run because Phase 37 specifically asks to exercise current Codex support.
- Runtime issues: no live Codex telemetry surface was available in-repo.
- Reviewer notes: result is useful as live Codex fixture evidence, not as a clean parity benchmark.
