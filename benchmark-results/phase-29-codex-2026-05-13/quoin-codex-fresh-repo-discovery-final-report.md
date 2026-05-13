# Quoin + Codex Fresh Repo Discovery Report

## Project Purpose

Quoin is an artifact-centric workflow-memory toolkit for stateless coding
agents. The repository is being refactored toward a portable core plus thin
runtime adapters. The shared core defines workflow semantics and artifact
contracts; adapters translate those semantics to runtime-specific invocation,
setup, model, approval, sandbox, and cost behavior.

## Repository Map

- Root guidance: `AGENTS.md` defines Codex-side constraints, including keeping
  Codex support repo-local, using native Codex mechanics, and avoiding guessed
  global Codex paths.
- User docs: `README.md`, `CHANGELOG.md`, `quoin/QUICKSTART.md`,
  `quoin/SETUP.md`, and `quoin/Workflow-User-Guide.html`.
- Portable core: `quoin/core/workflow/` contains runtime-neutral rules,
  artifact layout, session-state, cost-ledger, and skill metadata; `quoin/core/skills/`
  contains the 21 skill intent documents.
- Scripts: `quoin/core/scripts/` and `quoin/scripts/` contain validation,
  path-resolution, cost-event, cost-from-jsonl, preamble-build, and adapter-drift
  support.
- Runtime adapters: `quoin/adapters/claude/` is the supported Claude adapter;
  `quoin/adapters/codex/` is scaffolded with repo-local setup, readiness, smoke,
  feature-manifest, and generated skill docs.
- Benchmark framework: `quoin/benchmarks/` defines Phase 29 benchmark design,
  scenarios, templates, scoring rubric, and structure validator. It intentionally
  does not contain benchmark results.
- Tests: `quoin/dev/tests/` contains pytest coverage for adapter docs,
  runtime portability, benchmark structure, artifact validation, path resolution,
  cost parsing, and workflow behavior. `quoin/scripts/tests/` contains script
  tests.

## Relevant Checks

- Benchmark framework structure: `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
- Focused benchmark tests: `python3 -m pytest quoin/dev/tests/test_benchmarks.py`
- Codex readiness: `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
- Codex workflow smoke: `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
- Broader repo checks from `AGENTS.md`: `python3 -m pytest quoin/dev/tests/` and
  `python3 quoin/scripts/build_preambles.py --check`

## Quoin Artifact Evidence

This assisted trial wrote portable evidence under:

`.workflow_artifacts/phase-29-codex-fresh-repo-discovery/discovery-report.md`

The artifact is task-scoped to avoid overwriting existing global discovery or
memory artifacts in `.workflow_artifacts/memory/`. That is a benchmark-specific
deviation from the full `discover` skill contract, which normally writes memory
and cache artifacts.

## Risks And Unknowns

- The benchmark framework has no automation for independent runtime sessions;
  this run is simulated/operator-run.
- The repository was not reset to a clean fixture state before the trial.
- Existing Phase 29 files were already modified or untracked before this work.
- Codex runtime cost capture is unavailable in the current repo.
- The Codex adapter is scaffolded and documented, but its README marks multiple
  execution-loop and lifecycle skills as future work.
- Packaging status is unclear from this checkout: no Python package manifest was
  found and `src/quoin/` contains only cached bytecode.

## Recent Git Activity

Recent commits show active runtime-portability work:

- `d98792d` Add runtime parity matrix
- `5a11b92` feat(codex): add runtime smoke test
- `8ba36d1` feat(codex): generate adapter skill docs
- `12c3aa9` feat(codex): verify repo-local setup readiness
- `a15fff0` feat(codex): add repo-local installable feature scaffold

## Commands Used For Discovery

- `rg --files`
- `rg -n "Phase 29|benchmark|Codex workflow|Quoin \\+ Codex|result template|benchmark result" .`
- `sed -n` reads of benchmark templates, scenarios, adapter docs, workflow docs,
  `README.md`, `AGENTS.md`, and selected tests.
- `find` over source, artifact, adapter, benchmark, and test directories.
- `git -C quoin status --short`
- `git -C quoin rev-parse --short HEAD`
- `git -C quoin log --oneline -5`
- `git -C quoin ls-files`
