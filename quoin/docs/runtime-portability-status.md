# Runtime Portability Status

This page tracks the current migration state.

## Claude Code

Status: installable.

- `bash quoin/install.sh` remains the supported install command.
- Active Claude rules remain in `quoin/CLAUDE.md`.
- Active Claude skills remain in `quoin/skills/`, EXCEPT the twenty-one skills
  migrated across Phases 6–21 (`capture_insight`, `triage`, `start_of_day`,
  `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`,
  `thorough_plan`, `gate`, `implement`, `rollback`, `end_of_task`, `run`,
  `end_of_day`, `weekly_review`, `cost_snapshot`, `expand`, `discover`, `init_workflow`), which install from
  `quoin/adapters/claude/skills/<name>/SKILL.md`.
- Portable intent docs for the migrated skills live at
  `quoin/core/skills/capture_insight.md`,
  `quoin/core/skills/triage.md`,
  `quoin/core/skills/start_of_day.md`,
  `quoin/core/skills/review.md`,
  `quoin/core/skills/plan.md`,
  `quoin/core/skills/critic.md`,
  `quoin/core/skills/revise.md`,
  `quoin/core/skills/revise-fast.md`,
  `quoin/core/skills/architect.md`,
  `quoin/core/skills/gate.md`,
  `quoin/core/skills/thorough_plan.md`,
  `quoin/core/skills/implement.md`,
  `quoin/core/skills/rollback.md`,
  `quoin/core/skills/end_of_task.md`,
  `quoin/core/skills/run.md`,
  `quoin/core/skills/end_of_day.md`,
  `quoin/core/skills/weekly_review.md`,
  `quoin/core/skills/cost_snapshot.md`,
  `quoin/core/skills/expand.md`,
  `quoin/core/skills/discover.md`, and
  `quoin/core/skills/init_workflow.md`.
- Compatibility wrappers deploy to `~/.claude/scripts/`.
- Extracted portable implementations deploy to `~/.claude/core/scripts/`.

## Codex

Status: repo-local setup/readiness only; no verified global install target.

- Root `AGENTS.md` provides repo-local instructions.
- Codex adapter docs live under `quoin/adapters/codex/`.
- Codex setup is documented in `quoin/adapters/codex/setup.md`.
- A repo-local setup scaffold is now available:
  - Feature contract: `quoin/adapters/codex/installable-feature.md`
  - Machine-readable manifest: `quoin/adapters/codex/feature-manifest.json`
  - Generator script: `quoin/adapters/codex/generate_codex_assets.py`
  - Readiness script: `quoin/adapters/codex/verify_codex_readiness.py`
  - Runtime smoke script: `quoin/adapters/codex/smoke_codex_workflow.py`
  - Skill adapter docs: `quoin/adapters/codex/skills/<skill>/README.md`
  - Unsupported behavior notes: `quoin/adapters/codex/unsupported-claude-behavior.md`
  - Run `python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>` to generate `AGENTS.md`.
  - Run with `--check` to verify an existing `AGENTS.md` is up to date.
  - Run `python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets --check` to verify generated Codex adapter skill docs.
  - Run `python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .` to verify repo-local readiness.
  - Run `python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .` to verify the repo-local Codex setup path reaches portable workflow docs and avoids Claude-only runtime requirements.
- There is no global Codex installer.
- There are no Codex command files.
- No global Codex paths are assumed.
- Passing readiness means Codex can use Quoin's repo-local artifact workflow; it
  does not mean a Codex runtime extension has been installed.

## Portable Core

Status: partially extracted.

- Portable scripts live under `quoin/core/scripts/`.
- Core workflow docs live under `quoin/core/workflow/`.
- Skill metadata lives in `quoin/core/workflow/skills.json`.
- Shared reference material still lives under `quoin/memory/`.

**Phase 23 (2026-05-12):** Extracted the portable cost-event schema (`quoin/core/scripts/cost_event.py`) with a `CostEvent` dataclass and pure functions `parse_row`, `format_row`, and `iter_events`. Expanded the portable cost-ledger contract (`quoin/core/workflow/cost-ledger.md`) from a 35-line stub into a full ~110-line portable contract covering row shape, append-only invariant, schema mapping, tolerated variations, malformed inputs, and out-of-scope boundaries. Runtime-specific cost collection (Claude session-log parsing, ccusage, model pricing) remains adapter-owned at `quoin/scripts/cost_from_jsonl.py`, `session_age_guard.py`, and `measure_revise_crossover_cost.py`, each annotated with a CLAUDE-ADAPTER-OWNED banner. A Codex cost collector is explicitly future work; no Codex pricing or session-ID acquisition is implemented in this phase.

**Phase 25 (2026-05-13):** Verified that this repository contains no stable
Codex global install target or command packaging contract. Codex remains
repo-local setup/readiness only. Added `verify_codex_readiness.py` to check root
instructions, portable workflow docs, Codex adapter docs, manifest scope, no
guessed global Codex paths, and Claude install isolation.

**Phase 26 (2026-05-13):** Generated/scaffolded Codex facing adapter docs for
all 21 migrated portable skills under `quoin/adapters/codex/skills/`. Each doc
references its portable `quoin/core/skills/<skill>.md` contract, records phase
and effort metadata from `quoin/core/workflow/skills.json`, and documents
unsupported Claude-only translations without introducing Codex command files or
global install paths. Extended the Codex generator, manifest, readiness check,
and tests to guard coverage and leakage.

**Phase 27 (2026-05-13):** Added a deterministic repo-local Codex runtime smoke
test at `quoin/adapters/codex/smoke_codex_workflow.py`. The smoke test follows
the documented Codex path from root `AGENTS.md` through Codex adapter setup and
skill docs to portable core skill/workflow docs for a minimal
architecture-plan-review workflow. It verifies `.workflow_artifacts/`,
`architecture.md`, `current-plan.md`, `review-1.md`, and `cost-ledger.md`
semantics are reachable without Claude global paths, Claude slash-command
requirements, Claude install routing, guessed Codex global paths, or `ccusage`
as a required Codex dependency. This is a deterministic repository smoke test;
live Codex runtime execution remains manual and no global Codex installer or
command packaging is implemented.

## Still Claude-Specific

- Skill bodies in `quoin/skills/` (stubs only for the 21 migrated skills; full bodies now in `quoin/adapters/claude/skills/<name>/SKILL.md`).
- Slash-command invocation model.
- Agent and Skill dispatch instructions.
- Prompt-cache preamble generation.
- Claude model frontmatter.
- Claude JSONL session and cost plumbing.
- `ccusage` integration.

## Not Started

- Generated Claude skill files.
- Split shared skill intent from runtime overlays — partial: `capture_insight`, `triage`, `start_of_day`, `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`, `thorough_plan`, `gate`, `implement`, `rollback`, `end_of_task`, `run`, `end_of_day`, `weekly_review`, `cost_snapshot`, `expand`, `discover`, and `init_workflow` shipped under the adapter pattern across Phases 6–21.
- Runtime-neutral cost capture (schema extracted in Phase 23; full SKILL.md-narrowing to call `cost_event.parse_row` is deferred to a future phase).
