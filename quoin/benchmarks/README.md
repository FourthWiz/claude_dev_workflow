# Cross-Runtime Benchmarks

Phase 29 defines a small benchmark framework for comparing Quoin-assisted
workflows with simple Claude and Codex workflows. The suite evaluates workflow
usefulness: quality of decisions, correctness, reusable artifacts, continuity,
and overhead.

This directory contains benchmark design only. It does not contain measured results,
rankings, or claims that Quoin improves outcomes. A result exists only after a
human or automated run fills out `templates/result-template.md` with run
evidence.

## Comparison Modes

Run each scenario in the same fixture repository under four modes:

- `simple-claude` - Claude Code used normally, without Quoin phases or Quoin
  workflow artifacts.
- `quoin-claude` - Claude Code with the supported Claude adapter and Quoin
  artifacts under `.workflow_artifacts/`.
- `simple-codex` - Codex used normally with native planning, approvals,
  sandboxing, and repo-scoped instructions, without Quoin artifacts.
- `quoin-codex` - Codex with repo-local Quoin guidance and portable artifacts,
  without Codex global install assumptions or generated command files.

Simple modes may still keep ordinary notes or final answers, but they should
not be prompted to create Quoin-specific artifacts. Quoin modes should use the
same portable artifact contract documented in `quoin/core/workflow/`.

## Scenario Suite

The suite is intentionally small:

- Fresh repo discovery: orientation and useful first-pass repository map.
- Planning a medium refactor: risk discovery, staging, and validation strategy.
- Implementing a scoped code change: bounded implementation plus relevant checks.
- Reviewing changes: concrete findings, test gaps, and plan mismatch detection.
- Session handoff / memory reuse: continuation quality after prior-session context.

The machine-readable source of truth is `benchmark-suite.json`. Human scenario
instructions live under `scenarios/`.

## Metrics

The required scoring dimensions are:

- Task completion quality.
- Correctness / tests.
- Artifact quality.
- Context reuse.
- Time / turn count.
- Setup overhead.

Cost is optional because runtime cost capture is not equally implemented across
Claude and Codex. When cost is unavailable, record `not available` instead of
estimating it.

## Running A Benchmark

1. Choose a fixture repository and reset it to the same starting revision for
   every mode.
2. Select one scenario from `benchmark-suite.json`.
3. Copy `templates/run-sheet.md` into the run evidence folder and fill in the
   runtime, model or effort setting, start time, and setup steps.
4. Execute the scenario prompt exactly once per mode unless the run sheet
   records a restart.
5. Record raw evidence: final response, transcript or turn count, changed files,
   tests/checks, relevant Quoin artifacts for Quoin modes, and cost if the
   runtime exposes it.
6. Fill out `templates/result-template.md` after the run. Keep observations and
   scores separate from the design files in this directory.
7. Compare modes only after all four mode results for the same scenario and
   fixture are complete.

## Validation

Run the deterministic structure check from the repository root:

```bash
python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .
```

This check validates the manifest, scenario files, templates, comparison modes,
and metric coverage. It does not execute benchmark tasks or infer results.
