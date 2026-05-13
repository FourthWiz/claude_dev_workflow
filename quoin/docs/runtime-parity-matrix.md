# Cross-Runtime Parity Matrix

Phase 28 records the current Quoin runtime parity boundary. This matrix is
evidence-based: each claim points to repository files, tests, or scripts that
exist today. It does not treat planned adapter work as implemented behavior.

Status vocabulary:

- `Portable core` - runtime-neutral contract under `quoin/core/` or shared
  docs/memory.
- `Claude-supported` - implemented or installed by the Claude adapter today.
- `Codex-supported` - supported by repo-local Codex instructions, generated
  adapter docs, readiness checks, or deterministic smoke tests.
- `Unsupported` - intentionally not provided for that runtime.
- `Planned` - future work; not implemented yet.

No global Codex installer is supported. No Codex command files, global Codex
paths, approval layer, sandbox layer, model-dispatch mechanism, or live runtime
automation are implemented in this repository today. Codex cost events are
repo-local ledger rows only; token counts and dollar cost are recorded as
`not_available`.

Phase 29 adds a design-only benchmark framework at `quoin/benchmarks/` for
comparing simple Claude, Quoin + Claude, simple Codex, and Quoin + Codex
workflows. The framework captures scenarios, metrics, run sheets, and result
templates; it does not include measured results or cross-runtime claims.

## Workflow Semantics

| Dimension | Portable core | Claude-supported | Codex-supported | Unsupported / planned | Evidence |
|---|---|---|---|---|---|
| Artifact layout | Portable core defines `.workflow_artifacts/`, task folders, `stage-N/`, root `architecture.md`, root `cost-ledger.md`, and `finalized/` semantics. | Claude skills read/write the same artifact layout through installed skills and path helpers. | Repo-local Codex docs instruct Codex to use the project-root `.workflow_artifacts/` layout. Smoke test verifies the minimal path reaches artifact docs. | Live Codex runtime enforcement is not automated. | `quoin/core/workflow/task-layout.md`, `quoin/docs/runtime-portability.md`, `quoin/adapters/codex/setup.md`, `quoin/adapters/codex/smoke_codex_workflow.py`, `quoin/dev/tests/test_codex_runtime_smoke.py` |
| Planning and review artifacts | Portable skill contracts define `architecture.md`, `current-plan.md`, `critic-response-N.md`, `review-N.md`, and `gate-*.md` semantics. | Claude adapter skills implement the active runtime prompts for architecture, planning, critic, review, gate, and related phases. | Codex adapter skill docs exist for all migrated skills and point to portable contracts; smoke test covers `architect`, `plan`, and `review`. | Codex does not receive generated command files or Claude slash-command compatibility. | `quoin/core/skills/*.md`, `quoin/adapters/claude/skills/*/SKILL.md`, `quoin/adapters/codex/skills/`, `quoin/adapters/codex/smoke_codex_workflow.py` |
| Codex workflow procedures | Portable contracts define the discover, plan, implement, review, and gate phase semantics. | Claude continues to use its existing adapter skills and install path. | Codex has repo-local procedure docs for `discover`, `plan`, `implement`, `review`, and `gate` that use native Codex planning/tool/check behavior and project-root `.workflow_artifacts/`. | Global Codex install support and Codex command files remain unsupported until a stable extension point is verified. | `quoin/adapters/codex/workflow.md`, `quoin/adapters/codex/procedures/`, `quoin/dev/tests/test_codex_installable_feature.py`, `quoin/adapters/codex/verify_codex_readiness.py` |
| Memory and session handoff | Portable session docs define sessions, daily rollups, weekly rollups, lessons learned, workflow rules, and workflow suggestions. | Claude lifecycle skills use these files and Claude-specific session lookup where needed. | Codex docs instruct repo-local use of the same memory/session files and define a validated handoff shape under `.workflow_artifacts/memory/sessions/`. | Codex has no runtime-specific session identifier acquisition or live hook automation beyond docs and deterministic validation. | `quoin/core/workflow/session-state.md`, `quoin/memory/`, `quoin/adapters/codex/handoff.md`, `quoin/adapters/codex/validate_codex_handoff.py`, `quoin/adapters/codex/setup.md` |
| Codex handoff validation | Portable session and task-layout contracts define what continuation state must preserve. | Claude keeps its existing lifecycle skill and hook behavior unchanged. | Codex has `handoff.md`, a fixture-backed `validate_codex_handoff.py` checker, and smoke/readiness coverage for repo-local handoff files. | Live Codex hook automation remains unsupported until an extension point is verified. | `quoin/core/workflow/session-state.md`, `quoin/core/workflow/task-layout.md`, `quoin/adapters/codex/handoff.md`, `quoin/adapters/codex/validate_codex_handoff.py`, `quoin/adapters/codex/fixtures/valid-handoff.md` |
| Cost ledger row shape | Portable ledger shape and parser live in the core. | Claude cost capture uses `ccusage` and Claude JSONL fallback through adapter-owned scripts. | Codex docs preserve the portable ledger contract, smoke test checks `cost-ledger.md` reachability, and the Codex writer appends rows through the portable `CostEvent` formatter. | Codex pricing, token telemetry, and fallback chains remain unavailable until a verified local telemetry source exists. | `quoin/core/workflow/cost-ledger.md`, `quoin/core/scripts/cost_event.py`, `quoin/scripts/cost_from_jsonl.py`, `quoin/adapters/codex/cost.md`, `quoin/adapters/codex/cost_event.py`, `quoin/adapters/codex/smoke_codex_workflow.py` |
| Codex cost events | Portable `CostEvent` rows support runtime-neutral phase, effort, task category, note, and fallback fields. | Claude cost behavior is unchanged and remains adapter-owned. | Codex has a repo-local writer/checker that records runtime, task, phase, timestamp, session id when supplied, effort, and fallback fires, while marking token counts, dollar cost, and telemetry source as `not_available`. | Live Codex telemetry collection and Codex pricing are unsupported. | `quoin/adapters/codex/cost.md`, `quoin/adapters/codex/cost_event.py`, `quoin/dev/tests/test_codex_cost_event.py`, `quoin/adapters/codex/verify_codex_readiness.py` |
| Runtime-neutral helper scripts | `path_resolve.py`, `validate_artifact.py`, `classify_critic_issues.py`, and `cost_event.py` have portable core implementations where documented. | Claude install keeps compatibility wrappers under `quoin/scripts/` and deploys extracted core scripts where applicable. | Codex docs can reference shared behavior, but there is no Codex-specific helper installer. | Runtime-specific helper deployment for Codex is planned only after a stable extension point is verified. | `quoin/core/scripts/`, `quoin/scripts/`, `quoin/docs/runtime-portability.md`, `quoin/dev/tests/test_runtime_portability_docs.py` |
| Skill metadata and effort | `skills.json` defines runtime-neutral skill names, phases, effort levels, user-facing status, and Claude compatibility metadata. | Claude adapter frontmatter is validated against `claude_model`; install routing is guarded by adapter drift tests. | Codex skill docs are generated/scaffolded from `skills.json` and use native Codex controls for effort/model choices. | Non-Claude adapters must not consume `claude_model` as model routing. | `quoin/core/workflow/skills.json`, `quoin/core/workflow/skills.md`, `quoin/adapters/codex/generate_codex_assets.py`, `quoin/dev/tests/test_validate_adapter_drift.py` |
| Skill invocation | Portable core defines intent, inputs, outputs, and behavior contracts, not invocation syntax. | Claude supports slash-command and Skill invocation through installed Claude skills. | Codex supports natural-language repo-local invocation guidance in `AGENTS.md` and per-skill adapter docs. | Codex command files and Claude slash-command compatibility are unsupported. | `quoin/CLAUDE.md`, `quoin/adapters/claude/skills/*/SKILL.md`, `AGENTS.md`, `quoin/adapters/codex/skills/*/README.md`, `quoin/adapters/codex/unsupported-claude-behavior.md` |
| Install and setup | Portable core does not own global runtime install paths. | `bash quoin/install.sh` remains the supported Claude install path and deploys to Claude locations. | Codex setup is repo-local only: `quoin codex init` generates/checks `AGENTS.md`, `quoin doctor --runtime codex` runs readiness, and the underlying adapter docs/smoke tests remain script-backed. | Global Codex install, Codex package registry behavior, and Codex command packaging are unsupported until verified. | `src/quoin/cli.py`, `quoin/install.sh`, `quoin/SETUP.md`, `quoin/adapters/claude/README.md`, `quoin/adapters/codex/installable-feature.md`, `quoin/adapters/codex/feature-manifest.json` |
| Runtime permissions and approvals | Portable core intentionally does not duplicate runtime approvals or sandboxing. | Claude project setup may configure Claude permission files through Claude workflow behavior. | Codex docs require native Codex approvals, sandboxing, and repo-scoped instructions. | Replacement Codex approval or sandbox logic is unsupported. | `quoin/docs/runtime-portability.md`, `quoin/adapters/codex/setup.md`, `quoin/adapters/codex/feature-manifest.json` |
| Subagents / agents | Portable core may mark spawn-target metadata but does not define a universal subagent mechanism. | Claude supports Agent/Skill dispatch and prompt-cache preambles for declared spawn targets. | Codex adapter docs explicitly do not translate Claude subagent dispatch into Codex requirements. | Codex subagent parity is unsupported unless a runtime-specific contract is later defined. | `quoin/core/workflow/skills.json`, `quoin/core/workflow/skills.md`, `quoin/scripts/build_preambles.py`, `quoin/adapters/codex/unsupported-claude-behavior.md` |
| Preambles and model dispatch | Portable effort levels exist; runtime-specific dispatch is adapter-owned. | Claude owns section 0 model dispatch, Haiku/Sonnet/Opus frontmatter, and prompt-cache preamble generation. | Codex uses native model or reasoning controls; Codex docs do not hardcode Codex model names. | Codex preamble generation and model-dispatch mechanics are unsupported. | `quoin/adapters/claude/models.md`, `quoin/core/workflow/skills.md`, `quoin/adapters/codex/effort.md`, `quoin/dev/tests/test_runtime_portability_docs.py` |
| Generated adapter coverage | Portable core has 21 migrated skill contracts. | Claude adapter has per-skill `SKILL.md` files and install routing for the 21 migrated skills. | Codex adapter has generated/scaffolded per-skill README docs for all 21 migrated skills. | Generated active Claude skill files and active Codex runtime command files are not implemented. | `quoin/core/skills/`, `quoin/adapters/claude/skills/`, `quoin/adapters/codex/skills/`, `quoin/core/scripts/validate_adapter_drift.py`, `quoin/adapters/codex/generate_codex_assets.py` |
| Smoke-test coverage | Portable docs and scripts have pytest coverage for structure and contracts. | Claude adapter drift validator and install-related tests guard Claude compatibility. | Codex readiness, smoke, and handoff validator scripts guard repo-local setup, skill docs, procedure docs, handoff shape, and the discover-plan-implement-review-gate path. | Live Codex runtime execution is manual and not smoke-tested by this repository. | `quoin/dev/tests/test_runtime_portability_docs.py`, `quoin/dev/tests/test_validate_adapter_drift.py`, `quoin/dev/tests/test_codex_installable_feature.py`, `quoin/dev/tests/test_codex_runtime_smoke.py` |
| Benchmark framework | `quoin/benchmarks/` defines runtime-neutral workflow-usefulness scenarios, metrics, run sheets, result templates, and a structure validator. | Claude can be benchmarked in simple mode or with the existing Quoin Claude adapter. | Codex can be benchmarked in simple mode or with repo-local Quoin guidance; Codex cost rows can record unavailable telemetry explicitly. | The framework has no bundled benchmark results or live runtime automation. | `quoin/benchmarks/benchmark-suite.json`, `quoin/benchmarks/README.md`, `quoin/benchmarks/scripts/validate_benchmarks.py`, `quoin/dev/tests/test_benchmarks.py` |

## Migrated Skill Coverage

All 21 migrated skills have portable contracts, Claude adapter skill files, and
Codex adapter docs. Codex coverage here means repo-local documentation and
natural-language invocation guidance, not generated Codex commands.

| Skill | Portable core | Claude-supported | Codex-supported | Evidence |
|---|---|---|---|---|
| `architect` | `quoin/core/skills/architect.md` | `quoin/adapters/claude/skills/architect/SKILL.md` | `quoin/adapters/codex/skills/architect/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `capture_insight` | `quoin/core/skills/capture_insight.md` | `quoin/adapters/claude/skills/capture_insight/SKILL.md` | `quoin/adapters/codex/skills/capture_insight/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `cost_snapshot` | `quoin/core/skills/cost_snapshot.md` | `quoin/adapters/claude/skills/cost_snapshot/SKILL.md` | `quoin/adapters/codex/skills/cost_snapshot/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `critic` | `quoin/core/skills/critic.md` | `quoin/adapters/claude/skills/critic/SKILL.md` | `quoin/adapters/codex/skills/critic/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `discover` | `quoin/core/skills/discover.md` | `quoin/adapters/claude/skills/discover/SKILL.md` | `quoin/adapters/codex/skills/discover/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `end_of_day` | `quoin/core/skills/end_of_day.md` | `quoin/adapters/claude/skills/end_of_day/SKILL.md` | `quoin/adapters/codex/skills/end_of_day/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `end_of_task` | `quoin/core/skills/end_of_task.md` | `quoin/adapters/claude/skills/end_of_task/SKILL.md` | `quoin/adapters/codex/skills/end_of_task/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `expand` | `quoin/core/skills/expand.md` | `quoin/adapters/claude/skills/expand/SKILL.md` | `quoin/adapters/codex/skills/expand/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `gate` | `quoin/core/skills/gate.md` | `quoin/adapters/claude/skills/gate/SKILL.md` | `quoin/adapters/codex/skills/gate/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `implement` | `quoin/core/skills/implement.md` | `quoin/adapters/claude/skills/implement/SKILL.md` | `quoin/adapters/codex/skills/implement/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `init_workflow` | `quoin/core/skills/init_workflow.md` | `quoin/adapters/claude/skills/init_workflow/SKILL.md` | `quoin/adapters/codex/skills/init_workflow/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `plan` | `quoin/core/skills/plan.md` | `quoin/adapters/claude/skills/plan/SKILL.md` | `quoin/adapters/codex/skills/plan/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `review` | `quoin/core/skills/review.md` | `quoin/adapters/claude/skills/review/SKILL.md` | `quoin/adapters/codex/skills/review/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `revise` | `quoin/core/skills/revise.md` | `quoin/adapters/claude/skills/revise/SKILL.md` | `quoin/adapters/codex/skills/revise/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `revise-fast` | `quoin/core/skills/revise-fast.md` | `quoin/adapters/claude/skills/revise-fast/SKILL.md` | `quoin/adapters/codex/skills/revise-fast/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `rollback` | `quoin/core/skills/rollback.md` | `quoin/adapters/claude/skills/rollback/SKILL.md` | `quoin/adapters/codex/skills/rollback/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `run` | `quoin/core/skills/run.md` | `quoin/adapters/claude/skills/run/SKILL.md` | `quoin/adapters/codex/skills/run/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `start_of_day` | `quoin/core/skills/start_of_day.md` | `quoin/adapters/claude/skills/start_of_day/SKILL.md` | `quoin/adapters/codex/skills/start_of_day/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `thorough_plan` | `quoin/core/skills/thorough_plan.md` | `quoin/adapters/claude/skills/thorough_plan/SKILL.md` | `quoin/adapters/codex/skills/thorough_plan/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `triage` | `quoin/core/skills/triage.md` | `quoin/adapters/claude/skills/triage/SKILL.md` | `quoin/adapters/codex/skills/triage/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |
| `weekly_review` | `quoin/core/skills/weekly_review.md` | `quoin/adapters/claude/skills/weekly_review/SKILL.md` | `quoin/adapters/codex/skills/weekly_review/README.md` | `skills.json`, adapter drift validator, Codex generator/readiness tests |

## Claude-Only Runtime Mechanics

These are Claude-supported and intentionally not translated into Codex:

- Claude slash-command invocation.
- Claude skill frontmatter and Haiku/Sonnet/Opus model tier routing.
- Claude section 0 model dispatch.
- Claude Agent/subagent dispatch prompts.
- Claude prompt-cache preambles.
- Claude permission files for project setup.
- Claude session-log, usage, and cost-capture plumbing.
- Claude installer routing through `bash quoin/install.sh`.

Codex should use native planning, progress tracking, approvals, sandboxing,
repo-scoped instructions, and model or reasoning controls.

## Planned Work

- Codex global install or command-file support, only after a stable extension
  point is verified.
- Codex live runtime telemetry collection, pricing, and fallback chains after a
  stable local telemetry source is verified.
- A Codex adapter drift validator, if Codex gains active command/runtime files.
- Generated active Claude skill files, after compatibility tests cover the
  generated output.
- Live Codex runtime smoke coverage, if a deterministic runtime harness becomes
  available.
