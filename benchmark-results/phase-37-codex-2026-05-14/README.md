# Phase 37 Codex Fixture Benchmark Trials

This folder records live Codex-side Phase 37 benchmark evidence separate from
`quoin/benchmarks/`, which remains design-only.

## Scenario

- Scenario: `fresh-repo-discovery`
- Modes run: `simple-codex`, `quoin-codex`
- Fixture: `/private/tmp/quoin-phase37-fixture.vQUn26`
- Fixture source revision: `90745111078a06f090a37e91ea3c13382c3de24f`
- Fixture isolation: isolated temporary copy, but copied at run time from a
  dirty working tree with uncommitted Phase 34-36 Codex changes.

## Result Files

- `simple-codex-fresh-repo-discovery-run-sheet.md`
- `simple-codex-fresh-repo-discovery-final-report.md`
- `simple-codex-fresh-repo-discovery-result.md`
- `quoin-codex-fresh-repo-discovery-run-sheet.md`
- `quoin-codex-fresh-repo-discovery-final-report.md`
- `quoin-codex-fresh-repo-discovery-result.md`

## Limitations

- These are not clean-checkout parity results.
- No Codex token or dollar telemetry was available through a verified
  repository interface; cost is recorded as `not_available`.
- Pytest required explicit Python 3.10.15 selection. Default `python3` had no
  pytest module, and the `pytest` shim used Python 3.8, which could not collect
  one Python 3.10+ test file.
- Two installer-equivalence tests failed because they attempted network access
  for the `hatchling` build dependency in the fixture environment.

## Post-Recording Validation

Run from the source checkout after result files were written:

- `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` - passed
- `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` - passed
- `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` - passed
- `/Users/ivgo/.pyenv/versions/3.10.15/bin/python -m pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py` - 14 passed
- `/Users/ivgo/.pyenv/versions/3.10.15/bin/python -m pytest quoin/dev/tests/test_quoin_cli.py -k codex` - 4 passed, 21 deselected
