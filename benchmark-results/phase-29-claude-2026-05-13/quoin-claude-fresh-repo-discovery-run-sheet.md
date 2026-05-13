# Benchmark Run Sheet

## Run Identity

- Run id: phase-29-claude-fresh-repo-discovery-quoin-2026-05-13
- Scenario id: fresh-repo-discovery
- Comparison mode: quoin-claude
- Fixture repository: `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow/quoin`
- Fixture revision: `d98792d`
- Runtime: Claude Code
- Runtime version: claude-sonnet-4-6
- Model or effort setting: claude-sonnet-4-6
- Operator: Claude Code (operator-run in active session)
- Date: 2026-05-13

## Setup

- Starting state: active checkout with untracked/modified Phase 29 files; not a
  clean reset.
- Setup commands: no dependency install; repository inspection and Quoin memory
  reads only.
- Quoin enabled: yes (Claude adapter with existing `.workflow_artifacts/` in repo)
- Quoin setup evidence: read `.workflow_artifacts/memory/lessons-learned.md` and
  session-state files; wrote portable evidence to
  `.workflow_artifacts/phase-29-claude-fresh-repo-discovery/discovery-report.md`.
- Known unavailable telemetry: per-mode turn count, elapsed wall-clock time,
  monetary cost.

## Execution Log

- Start time: not available
- End time: not available
- Turn count: not captured independently per mode; executed within one
  operator session alongside the simple-claude trial.
- Restarts or interruptions: none observed
- Commands/checks run:
  - `find` (directory listing)
  - `git rev-parse --short HEAD`, `git log --oneline -5`, `git status --short`
  - `ls` at multiple levels
  - File reads: `README.md`, `AGENTS.md`, `quoin/CLAUDE.md`, `lessons-learned.md`,
    session state files, benchmark templates, scenario docs, Codex adapter files
  - `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
  - `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
  - `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
  - `python3 -m pytest quoin/dev/tests/test_benchmarks.py`
  - `python3 -m pytest quoin/dev/tests/ -q`
  - `python3 quoin/scripts/build_preambles.py --check`
- Files changed: no source files changed; benchmark evidence files and Quoin
  artifact written after discovery.

## Evidence Collected

- Final answer or summary: `quoin-claude-fresh-repo-discovery-final-report.md`
- Transcript location: not available
- Diff location: not applicable; only evidence files created
- Test output location: result Verification section
- Quoin artifact location:
  `.workflow_artifacts/phase-29-claude-fresh-repo-discovery/discovery-report.md`
- Cost source: not available
- Cost value: not available

## Notes

- Deviations from scenario prompt: not an isolated clean checkout; full `/discover`
  memory/cache writes were intentionally skipped to preserve active project state.
- Runtime issues: no failures; two modes share one session so per-mode telemetry
  is not independently measured.
- Reviewer notes: quoin-claude mode read Quoin memory artifacts as additional
  context and produced a portable discovery report artifact per Quoin contract.
