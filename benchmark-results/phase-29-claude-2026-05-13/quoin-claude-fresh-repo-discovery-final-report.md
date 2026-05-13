# Quoin + Claude Fresh Repo Discovery Report

## Project Purpose

Quoin is an artifact-centric workflow-memory toolkit for stateless coding agents.
Sessions start cold; Quoin gives them accumulated knowledge through structured
artifacts: `architecture.md`, `current-plan.md`, `critic-response-N.md`,
`review-N.md`, `cost-ledger.md`, and session-state files under
`.workflow_artifacts/`. The repository is being refactored toward a portable
core plus thin runtime adapters. Claude Code is the supported runtime; Codex
support is repo-local and scaffolded.

## Repository Map

- **Root guidance**: `AGENTS.md` defines Codex-side constraints; `README.md`
  and `CHANGELOG.md` are user-facing.
- **Claude adapter user docs**: `quoin/QUICKSTART.md` (command reference),
  `quoin/SETUP.md`, `quoin/CLAUDE.md` (full runtime rules).
- **Installer**: `quoin/install.sh` copies skills, memory files, and scripts to
  `~/.claude/`.
- **Skills**: `quoin/skills/<name>/SKILL.md` — 21 slash commands covering the
  full discover → architect → plan → implement → review → end-of-task pipeline.
- **Portable core**: `quoin/core/workflow/` (runtime-neutral rules, task-layout,
  session-state, cost-ledger, skills metadata); `quoin/core/skills/` (21 intent
  docs); `quoin/core/scripts/` (canonical validation, path-resolve, cost, drift
  scripts).
- **Wrapper scripts**: `quoin/scripts/` — thin wrappers delegating to
  `quoin/core/scripts/`; also contains Claude-specific scripts
  (build_preambles.py, cost_from_jsonl.py, session_age_guard.py).
- **Adapters**: `quoin/adapters/claude/` (models, skills docs);
  `quoin/adapters/codex/` (setup, readiness, smoke, feature-manifest, generated
  skill docs).
- **Benchmarks**: `quoin/benchmarks/` — Phase 29 design-only benchmark framework;
  scenarios, templates, rubric, validator. No results live here.
- **Tests**: `quoin/dev/tests/` — ~62 pytest files, ~845 passing, 13 known
  pre-existing failures.
- **Memory**: `quoin/memory/` (Tier 1 hand-edited reference files deployed by
  installer); `.workflow_artifacts/memory/` (active project workflow memory).

## Quoin Workflow Context Read

The quoin-claude mode read existing Quoin memory artifacts as additional context:
- `lessons-learned.md`: one entry (2026-05-07) about model-field sync across
  legacy stub and adapter source files.
- Session state files noted (not loaded as task-relevant for this benchmark).

Full `/discover` memory/cache writes (repos-inventory, architecture-overview,
cache entries) were intentionally skipped to avoid overwriting active project
state. Evidence scoped to:

`.workflow_artifacts/phase-29-claude-fresh-repo-discovery/discovery-report.md`

## Relevant Checks

```bash
python3 -m pytest quoin/dev/tests/                               # 845 pass / 13 fail (pre-existing)
python3 -m pytest quoin/dev/tests/test_benchmarks.py             # 6/6 pass
python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .   # 6/6 ok
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .    # READY
python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .      # SMOKE PASS
python3 quoin/scripts/build_preambles.py --check                 # exit 0
```

## Risks And Unknowns

1. **Pre-existing test failures (13)**: cost/jsonl parity (3), v3-savings missing
   fixture (5), path-resolve e2e inflight assertions (5). All pre-date this trial.
2. **Dirty fixture**: Phase 29 benchmark files and portability docs are untracked
   or modified; benchmark evidence must not be treated as from a clean run.
3. **Packaging unclear**: `src/quoin/` contains only bytecode; no package
   manifest found.
4. **Cost capture not available**: runtime cost requires post-session JSONL
   parsing.
5. **Codex adapter scaffolded only**: execution-loop and lifecycle skills are
   marked future work in the adapter README.
6. **§0 preamble sections generated**: hand-editing them without running
   `build_preambles.py` causes CI drift.

## Recent Git Activity

- `d98792d` Add runtime parity matrix
- `5a11b92` feat(codex): add runtime smoke test
- `8ba36d1` feat(codex): generate adapter skill docs
- `12c3aa9` feat(codex): verify repo-local setup readiness
- `a15fff0` feat(codex): add repo-local installable feature scaffold

## Commands Used For Discovery

- `find` — directory listing at multiple levels
- `git rev-parse --short HEAD`, `git log --oneline -5`, `git status --short`
- `ls` at multiple levels
- File reads: README, AGENTS, CLAUDE.md, lessons-learned.md, session state files
- `python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .`
- `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .`
- `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .`
- `python3 -m pytest quoin/dev/tests/test_benchmarks.py`
- `python3 -m pytest quoin/dev/tests/ -q`
- `python3 quoin/scripts/build_preambles.py --check`
