# Benchmark Run Sheet

## Run Identity

- Run id: phase-29-claude-fresh-repo-discovery-simple-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: simple-claude
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Claude Code
- Runtime version: claude-sonnet-4-6
- Model or effort setting: claude-sonnet-4-6
- Operator: Claude Code (operator-run in active session)
- Date: 2026-05-13

## Setup

- Starting state: active checkout with untracked/modified Phase 29 files; not a
  clean reset. Dirty state was present before trial start.
- Setup commands: no dependency install; repository inspection commands only.
- Quoin enabled: no
- Quoin setup evidence: not applicable — simple mode intentionally avoids Quoin
  artifacts.
- Known unavailable telemetry: independent per-mode turn count, exact elapsed
  wall-clock time, and monetary cost (cost capture reads JSONL post-session).

## Execution Log

- Start time: not available (embedded in larger operator session)
- End time: not available
- Turn count: not captured independently per mode; executed within one
  operator session alongside the quoin-claude trial.
- Restarts or interruptions: none observed
- Commands/checks run:
  - `find` (top-level and sub-directory listing)
  - `git rev-parse --short HEAD`, `git log --oneline -5`, `git status --short`
  - `ls` at multiple directory levels
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
  - `python3 -m pytest quoin/dev/tests/test_benchmarks.py`
  - `python3 -m pytest quoin/dev/tests/ -q`
  - `python3 quoin/scripts/build_preambles.py --check`
- Files changed: no source files changed; benchmark evidence files written after
  discovery.

## Evidence Collected

- Final answer or summary: `simple-claude-fresh-repo-discovery-final-report.md`
- Transcript location: not available (embedded in operator session context)
- Diff location: not applicable to scenario; only benchmark evidence files created
- Test output location: final report section "How To Run Relevant Checks"
- Quoin artifact location: not applicable
- Cost source: not available
- Cost value: not available

## Notes

- Deviations from scenario prompt: not an isolated fresh clean checkout;
  existing Phase 29 benchmark files and docs were already modified or untracked.
- Runtime issues: no runtime failures; two modes share one session, so turn
  counts are not independently measured.
- Reviewer notes: simple mode relied solely on standard Claude Code file-read
  and shell tools; no Quoin slash commands or artifacts were involved.
