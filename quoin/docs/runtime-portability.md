# Runtime Portability

Quoin is moving from a Claude-specific workflow toolkit to a runtime-portable workflow system. The portable value is the artifact-centric workflow, not any single agent runtime.

This document defines the boundary for the first migration pass. It is intentionally conservative: existing Claude Code behavior remains the compatibility baseline.

For the current evidence-based feature-by-feature status, see
`quoin/docs/runtime-parity-matrix.md`.

For the Phase 29 benchmark design, see `quoin/benchmarks/`. The benchmark
framework compares simple Claude, Quoin + Claude, simple Codex, and Quoin +
Codex workflows across repeatable workflow-usefulness scenarios. It is a design
and evidence-capture framework only; it does not record results or claim
cross-runtime performance before actual runs exist.

## Portable Core

The portable core is the workflow contract that every runtime adapter should preserve:

- `.workflow_artifacts/` as the project-local workflow state directory.
- Task folders under `.workflow_artifacts/<task-name>/`.
- Stage-aware task layout with `stage-N/` subfolders.
- Root-level `architecture.md` and `cost-ledger.md` for staged tasks.
- `finalized/` archive semantics.
- Memory folders for sessions, daily rollups, weekly reviews, lessons learned, workflow rules, and workflow suggestions.
- Artifact formats for `architecture.md`, `current-plan.md`, `critic-response-N.md`, `review-N.md`, `gate-*.md`, and session state.
- Runtime-neutral helper behavior now lives in `quoin/core/scripts/`, with compatibility wrappers left under `quoin/scripts/`:
  - `path_resolve.py` is portable because it resolves task and stage artifact paths from `.workflow_artifacts`.
  - `validate_artifact.py` is portable because it validates markdown artifact structure.
  - `classify_critic_issues.py` is portable unless future changes add runtime-specific assumptions.
  - `cost_event.py` is portable because it provides the typed cost-event schema (`CostEvent` dataclass) and pure functions `parse_row`, `format_row`, and `iter_events` for reading and writing cost-ledger rows. It has no runtime-specific dependencies: no pricing tables, no session-log parsing, no UUID-acquisition logic. Canonical implementation at `quoin/core/scripts/cost_event.py`; compat wrapper at `quoin/scripts/cost_event.py`.
  - `validate_discovery_map.py` is portable because it validates the additive structured-data discovery-map schema. Canonical implementation at `quoin/core/scripts/validate_discovery_map.py`; compat wrapper at `quoin/scripts/validate_discovery_map.py`.
- Runtime-neutral workflow semantics now live in `quoin/core/workflow/`:
  - `rules.md` defines shared phase and safety rules.
  - `task-layout.md` defines task, stage, and finalization layout.
  - `session-state.md` defines handoff, lessons, and daily insight semantics.
  - `cost-ledger.md` defines portable ledger shape while leaving runtime cost capture to adapters.
  - `skills.json` defines runtime-neutral skill metadata while preserving current Claude model mappings.
- Shared reference material in `quoin/memory/`, including `format-kit.md`, `format-kit.sections.json`, `glossary.md`, `terse-rubric.md`, `summary-prompt.md`, `workflow-rules.md`, and `lessons-learned.md`.

The portable core should not know where a runtime stores global instructions, commands, sessions, approvals, or sandbox settings.

## Discovery Map (additive structured-data layer)

Phase 30 adds a portable structured snapshot format for quoin project state. The schema, validator,
and example fixture are implemented now. The generator integration with `/discover` is FUTURE WORK
and out of scope for Phase 30.

**Implemented files (Phase 30):**
- `quoin/core/schemas/discovery-map.schema.json` — JSON Schema Draft-07 contract for `discovery-map.json`
- `quoin/core/schemas/discovery-map.md` — prose schema reference (field types, path conventions, timestamp conventions, extensions namespace, versioning)
- `quoin/dev/tests/fixtures/discovery-map/example-map.json` — valid example fixture modeled on the Codex_workflow project
- `quoin/core/scripts/validate_discovery_map.py` — stdlib-only validator (9 invariants DM-01..DM-09); compat wrapper at `quoin/scripts/validate_discovery_map.py`

**Non-goals for Phase 30 (future work):**
- No Markdown artifact changes — existing `.workflow_artifacts/` layout is unchanged
- No `/discover` SKILL.md modifications — `/discover` continues to write existing Markdown outputs
- No new external dependencies — validator is pure stdlib
- No `.workflow_artifacts/` layout changes — schema is additive

**Future generator integration:** A future generator would be invoked (or called) by `/discover` after
the Markdown inventory scan is complete. It would read `.workflow_artifacts/` structure, `git` state,
and the knowledge cache to populate and emit `discovery-map.json` at the project root. The generator
is FUTURE WORK; the schema and validator are in place to validate output when it exists. Per Phase 30
plan D-09, a future third JSON validator (if added) should extract shared scaffolding into
`quoin/core/scripts/_validator_common.py` rather than duplicating exit-code/CLI conventions.

## Claude Adapter

The current active Claude adapter still lives at the existing paths for backward compatibility.

Claude-specific behavior includes:

- `quoin/install.sh`.
- `quoin/CLAUDE.md`.
- Slash-command invocation such as `/plan`, `/implement`, `/review`, and `/end_of_task`.
- Deployment under `~/.claude/skills`, `~/.claude/memory`, `~/.claude/scripts`, and `~/.claude/CLAUDE.md`.
- Claude Agent and Skill dispatch behavior.
- Prompt-cache preamble generation.
- Claude model tier names: Haiku, Sonnet, and Opus.
- Claude session JSONL lookup.
- `ccusage` integration and the fallback cost parser.
- `cost_from_jsonl.py` is Claude-specific because it reads Claude Code session logs and Claude model pricing. Despite living at `quoin/scripts/` (alongside portable wrappers), its adapter scope is declared by a CLAUDE-ADAPTER-OWNED banner at the top of the file. The portable cost-event schema belongs in `quoin/core/scripts/cost_event.py`; runtime-specific cost collection stays here.
- `session_age_guard.py` is Claude-specific because it inspects Claude Code session files. A CLAUDE-ADAPTER-OWNED banner at the top of the file declares this scope explicitly.
- `measure_revise_crossover_cost.py` is Claude-specific because it imports `cost_from_jsonl` and references Claude model names. A CLAUDE-ADAPTER-OWNED banner at the top of the file declares this scope explicitly.
- `build_preambles.py` is Claude-specific because it generates Claude skill preambles under `~/.claude`.
- `verify_spawn_prompt_prefix.py` is Claude-specific because it verifies Claude Agent spawn behavior.
- `validate_adapter_drift.py` is Claude-specific because it validates `## §0 Model dispatch` headings, `adapters/claude/` paths, and install.sh routing — all Claude-specific adapter mechanics. Despite living in `core/scripts/` for wrapper-pattern symmetry with `path_resolve.py`, it checks Claude-only concepts. A future Codex adapter drift validator would be a parallel script (`validate_adapter_drift_codex.py`) rather than a generalization of this one.

The first migration pass must not break `bash quoin/install.sh` or change the installed Claude workflow.

## Codex Adapter

The initial Codex adapter is intentionally thin and repo-local:

- Root-level `AGENTS.md` provides repo-local Codex guidance.
- Codex uses the same `.workflow_artifacts/` conventions as the portable core.
- Codex should use native planning, approvals, sandboxing, and repo-scoped instruction handling.
- Quoin should not create a Codex global installer until a supported Codex extension point is verified.
- Quoin should not guess local Codex installation paths.
- Quoin should not duplicate Codex approvals or sandbox enforcement.

Codex support starts as instructions, readiness verification, and workflow
discipline around shared artifacts, not as feature parity with Claude slash
commands.

### Codex repo-local setup

A repo-local setup scaffold ships under `quoin/adapters/codex/`:

- `installable-feature.md` — feature contract (what is and is not supported)
- `feature-manifest.json` — machine-readable manifest; references `quoin/core/workflow/skills.json` by path, not by inline duplication
- `generate_codex_assets.py` — generates `AGENTS.md` at a given `--project-root`
- `verify_codex_readiness.py` — verifies root instructions, portable core docs, Codex adapter docs, manifest scope, no guessed global Codex paths, and Claude install isolation
- `smoke_codex_workflow.py` — validates the documented repo-local Codex path
  from setup instructions to portable workflow artifacts

The generator produces only repo-local output. The readiness check reads only
repo-local files. Global Codex install paths, package registry behavior, and
Codex command file formats remain unresolved until a stable extension point is
verified.

### Phase 26 — Codex adapter skill docs

Phase 26 adds generated/scaffolded Codex facing docs for all 21 migrated
portable skills:

- `quoin/adapters/codex/skills/<skill>/README.md` references the corresponding
  `quoin/core/skills/<skill>.md` contract and records the skill phase, effort,
  and user-facing status from `quoin/core/workflow/skills.json`.
- `quoin/adapters/codex/skills/README.md` indexes the 21 skill docs.
- `quoin/adapters/codex/unsupported-claude-behavior.md` documents Claude-only
  behavior that is intentionally not translated into Codex.

These files are adapter docs, not Codex command files. They do not define global
Codex install paths, approval behavior, sandbox behavior, or model-dispatch
mechanics. Codex still uses native runtime behavior and preserves Quoin only at
the artifact/workflow layer.

### Phase 27 — Codex runtime smoke test

Phase 27 adds `quoin/adapters/codex/smoke_codex_workflow.py`, a deterministic
repository smoke test for the minimal Codex workflow path. It does not attempt
to automate live Codex runtime behavior. Instead, it checks that the files and
links a Codex session would need are present and coherent:

- root `AGENTS.md`
- Codex setup and adapter docs
- Codex skill adapter docs for `architect`, `plan`, and `review`
- portable core skill docs
- portable workflow docs for task layout, session state, and cost ledger

The smoke test also guards the Codex path against Claude global paths,
Claude slash-command requirements, Claude install routing, guessed Codex global
paths, and `ccusage` as a required Codex dependency.

### Phase 29 — Cross-runtime workflow benchmarks

Phase 29 adds `quoin/benchmarks/`, a design-only benchmark framework for
comparing Quoin-assisted workflows against simple Claude and simple Codex
workflows. The suite covers fresh repo discovery, medium refactor planning,
scoped implementation, review, and session handoff / memory reuse. It defines
the four comparison modes, scoring metrics, run sheets, result templates, and a
deterministic structure validator at
`quoin/benchmarks/scripts/validate_benchmarks.py`.

This framework intentionally separates benchmark design from benchmark results.
No measured outcomes are bundled, and cost remains optional because runtime cost
capture is not equally implemented across Claude and Codex.

## Candidate Shared Skills

Most skill instructions contain portable workflow intent mixed with Claude runtime mechanics. For now, they stay in place as Claude skills.

Future work should split each skill into:

- Shared workflow intent: inputs, artifacts read, artifacts written, phase semantics, gates, and handoff rules.
- Runtime adapter overlay: invocation syntax, model selection, subagent mechanics, tool names, deployment paths, and runtime-specific cost/session handling.

Do not duplicate skill templates before this split exists. Duplication would make the shared workflow rules drift.

## First-Pass Rule

The first implementation pass established the boundary and guard tests. Portable script implementations may move into `quoin/core/scripts/` only when old `quoin/scripts/` entrypoints remain compatible for Claude installs and existing docs.

### Migrated skills (Phases 6–21)

Twenty-one skills now install from the Claude adapter path
(`quoin/adapters/claude/skills/<name>/SKILL.md`); the runtime-neutral
intents live at `quoin/core/skills/<name>.md`. All other skills still
install from `quoin/skills/<name>/SKILL.md`.

- `capture_insight` shipped in Phase 6 as the pilot.
- `triage` and `start_of_day` followed in Phase 7.
- `review` migrated in Phase 8.
- `plan`, `critic`, `revise`, and `revise-fast` migrated in Phase 9.
- `architect` and `thorough_plan` migrated in Phase 10.
- `gate` migrated in Phase 11.
- `implement` migrated in Phase 12.
- `rollback` migrated in Phase 13.
- `end_of_task` migrated in Phase 14.
- `run` migrated in Phase 15.
- `end_of_day` migrated in Phase 16.
- `weekly_review` migrated in Phase 17.
- `cost_snapshot` migrated in Phase 18.
- `expand` migrated in Phase 19.
- `discover` migrated in Phase 20.
- `init_workflow` migrated in Phase 21.

### Phase 22 — Adapter drift validator

Phase 22 added an adapter drift validator at `quoin/core/scripts/validate_adapter_drift.py` (compat wrapper at `quoin/scripts/validate_adapter_drift.py`) that asserts 16 structural invariants across the three-file adapter pattern. The validator is run by `pytest quoin/dev/tests/test_validate_adapter_drift.py` and can be invoked directly during development.

**What this phase did:**
- Extended `skills.json` `schema_version` from 1 to 2 with two new optional fields: `section_0` (bool) and `spawn_target` (bool).
- Added `validate_adapter_drift.py` in `quoin/core/scripts/` (canonical) and `quoin/scripts/` (compat wrapper), covering 16 invariants (AD-CO through AD-IO) over all 21 skills in the manifest.
- Added 23 tests in `quoin/dev/tests/test_validate_adapter_drift.py` (2 positive, 16 invariant negatives, 5 misc).
- Documented the invariants and new fields in `quoin/core/workflow/skills.md`.

**What this phase did NOT do:**
- Did not consolidate the 17 existing `test_*_adapter_pilot.py` files — they remain as point-in-time regression guards; the new validator is the forward-looking guard.
- Did not implement generator scaffolding (deferred per plan D-01).
- Did not add a Codex-adapter validator (D-09 documents the parallel-script pattern for future runtime adapters).
- Did not add path fields to the manifest (`portable_doc_path`, etc.) — paths are derivable by convention from `name` (D-02).
- Did not deploy `validate_adapter_drift.py` to `~/.claude/scripts/` — it is a repo-development tool invoked only by pytest and developers, not a runtime helper.
- Did not change `install.sh` — the validator is purely a dev/CI tool.

**How to extend for future runtime adapters:** per D-09, a Codex adapter drift validator would be a parallel script (`validate_adapter_drift_codex.py` in `quoin/core/scripts/`), not a generalization of this one. The Claude-specific concepts (§0 dispatch, `adapters/claude/` paths, install.sh routing) are intrinsic to the Claude adapter.
