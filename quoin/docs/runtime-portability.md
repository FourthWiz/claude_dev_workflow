# Runtime Portability

Quoin is moving from a Claude-specific workflow toolkit to a runtime-portable workflow system. The portable value is the artifact-centric workflow, not any single agent runtime.

This document defines the boundary for the first migration pass. It is intentionally conservative: existing Claude Code behavior remains the compatibility baseline.

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
- Runtime-neutral workflow semantics now live in `quoin/core/workflow/`:
  - `rules.md` defines shared phase and safety rules.
  - `task-layout.md` defines task, stage, and finalization layout.
  - `session-state.md` defines handoff, lessons, and daily insight semantics.
  - `cost-ledger.md` defines portable ledger shape while leaving runtime cost capture to adapters.
  - `skills.json` defines runtime-neutral skill metadata while preserving current Claude model mappings.
- Shared reference material in `quoin/memory/`, including `format-kit.md`, `format-kit.sections.json`, `glossary.md`, `terse-rubric.md`, `summary-prompt.md`, `workflow-rules.md`, and `lessons-learned.md`.

The portable core should not know where a runtime stores global instructions, commands, sessions, approvals, or sandbox settings.

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
- `cost_from_jsonl.py` is Claude-specific because it reads Claude Code JSONL sessions and Claude model pricing.
- `session_age_guard.py` is Claude-specific because it inspects Claude Code session JSONL files.
- `build_preambles.py` is Claude-specific because it generates Claude skill preambles under `~/.claude`.
- `verify_spawn_prompt_prefix.py` is Claude-specific because it verifies Claude Agent spawn behavior.

The first migration pass must not break `bash quoin/install.sh` or change the installed Claude workflow.

## Codex Adapter

The initial Codex adapter is intentionally thin:

- Root-level `AGENTS.md` provides repo-local Codex guidance.
- Codex uses the same `.workflow_artifacts/` conventions as the portable core.
- Codex should use native planning, approvals, sandboxing, and repo-scoped instruction handling.
- Quoin should not create a Codex global installer until a supported Codex extension point is verified.
- Quoin should not guess local Codex installation paths.
- Quoin should not duplicate Codex approvals or sandbox enforcement.

Codex support starts as instructions and workflow discipline around shared artifacts, not as feature parity with Claude slash commands.

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
