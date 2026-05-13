# Benchmark Result Template

This file is a filled result for an operator-run benchmark trial.

## Run Identity

- Run id: phase-37-quoin-codex-fresh-repo-discovery-2026-05-14
- Scenario id: fresh-repo-discovery
- Comparison mode: quoin-codex
- Fixture repository: `/private/tmp/quoin-phase37-fixture.vQUn26`
- Fixture revision: `90745111078a06f090a37e91ea3c13382c3de24f` plus dirty working tree snapshot
- Runtime: Codex
- Model or effort setting: high effort recorded in Codex cost row; live model/effort telemetry not_available
- Date: 2026-05-14 local time; cost row date 2026-05-13 UTC

## Outcome Summary

- Completed: yes
- Main outcome: ran the Codex discover procedure against an isolated fixture, wrote reusable Quoin discovery artifacts, generated a discovery map, validated handoff, and recorded a Codex cost row with unavailable telemetry explicitly marked.
- Important limitations: dirty fixture; prior `.workflow_artifacts/` existed; no live Codex token/dollar telemetry; targeted pytest had two network-dependent installer failures.

## Metric Scores

| Metric | Score / value | Evidence |
|---|---:|---|
| Task completion quality | 3 | Completed the discovery scenario and exercised Phase 33-36 procedures/tools. Minor gaps remain from dirty fixture state and non-transcripted turn count. |
| Correctness / tests | 3 | Benchmark validator, Codex readiness, smoke, discovery-map validation, handoff validation, and cost validation passed. Targeted pytest had 36 passed, 1 skipped, 2 environment/network failures. |
| Artifact quality | 4 | Produced coherent, reusable discovery memory artifacts, staleness cache, structured discovery map, handoff file, and cost ledger row. Artifacts clearly label dirty fixture limitations. |
| Context reuse | 3 | Reused existing `.workflow_artifacts/` presence and Codex procedure docs while writing Phase 37-specific continuation evidence. Existing prior artifacts make the run less clean. |
| Time / turn count | observed 1m55s; turn count not_available | Start 2026-05-14 01:07:26 +04; end 2026-05-14 01:09:21 +04. Codex turn count was not exposed. |
| Cost if available | not_available | One Codex cost event row was recorded, but token counts, dollar cost, and telemetry source are explicitly `not_available`. |
| Setup overhead | 2 | Procedure and artifact setup was workable but heavier than simple mode; dirty fixture and prior artifact state added review overhead. |

## Verification

- Checks run:
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .` - passed
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` - passed
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` - passed
  - `python3 quoin/scripts/generate_discovery_map.py /private/tmp/quoin-phase37-fixture.vQUn26 --quiet` - passed
  - `python3 quoin/scripts/validate_discovery_map.py .workflow_artifacts/discovery-map.json` - passed
  - `python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/2026-05-14-phase-37-live-codex-fixture-benchmarks-codex.md` - passed
  - `python3 quoin/adapters/codex/cost_event.py validate --project-root . --task phase-37-live-codex-fixture-benchmarks --expect-codex` - passed
  - `/Users/ivgo/.pyenv/versions/3.10.15/bin/python -m pytest quoin/dev/tests/test_benchmarks.py quoin/dev/tests/test_codex_runtime_smoke.py quoin/dev/tests/test_codex_cost_event.py quoin/dev/tests/test_quoin_cli.py` - 36 passed, 1 skipped, 2 failed
- Checks not run:
  - Full test suite.
  - Clean-checkout rerun.
  - Live Codex telemetry extraction, because no verified in-repo interface exists.
- Failures observed:
  - Same pytest environment failures as simple-codex: default Python lacked pytest, pyenv pytest used Python 3.8, and Python 3.10.15 pytest had two network-dependent installer failures.
- Residual risk: artifacts prove the current Codex scaffold can be exercised, but do not prove stable performance, clean-fixture behavior, or Claude parity.

## Artifacts

- Final answer: `quoin-codex-fresh-repo-discovery-final-report.md`
- Transcript: not_available
- Diff: isolated fixture workflow artifacts only
- Tests: run sheet and verification section
- Quoin artifacts: `/private/tmp/quoin-phase37-fixture.vQUn26/.workflow_artifacts/`
- Cost evidence: `/private/tmp/quoin-phase37-fixture.vQUn26/.workflow_artifacts/phase-37-live-codex-fixture-benchmarks/cost-ledger.md`

## Reviewer Assessment

- Score rationale: Quoin + Codex produced stronger continuation and audit evidence than simple Codex, especially handoff and cost rows. It also required more setup and remains manual/repo-local.
- Cross-mode comparison notes: compared with simple-codex, artifact quality improves materially; setup overhead worsens. Correctness is similar because deterministic checks are the same and pytest failures are environmental.
- Follow-up needed before using this result: rerun from a clean fixture checkout with committed Phase 34-36 changes and stable local test dependencies.
