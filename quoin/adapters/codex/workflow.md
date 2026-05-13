# Codex Workflow Execution Guide

This guide describes how Codex should execute Quoin's repo-local workflow loop
using portable artifacts and native Codex behavior.

It is documentation for a Codex session working inside a repository. It is not a
global Codex installer, a command-file format, an approval layer, a sandbox
layer, or a model-dispatch mechanism.

## Portable Sources

Codex procedures preserve the contracts in:

- `quoin/core/workflow/rules.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/cost-ledger.md`
- `quoin/core/workflow/skills.json`
- `quoin/core/skills/discover.md`
- `quoin/core/skills/plan.md`
- `quoin/core/skills/implement.md`
- `quoin/core/skills/review.md`
- `quoin/core/skills/gate.md`

## Core Loop

The practical Codex loop covered by Phase 33 is:

```text
discover -> plan -> implement -> review -> gate
```

The portable gate contract may also be used between earlier phase transitions
when the task requires a checkpoint. A gate always stops for explicit user
approval before the next phase begins.

## Project Root

The Quoin project root is the repository root containing `AGENTS.md`. Codex
reads and writes workflow artifacts relative to that root:

```text
.workflow_artifacts/
  discovery-map.json
  <task-name>/
    architecture.md
    current-plan.md
    review-1.md
    gate-*.md
    cost-ledger.md
  memory/
    lessons-learned.md
    sessions/
      <YYYY-MM-DD>-<task-name>-codex.md
    daily/
    weekly/
  cache/
```

When work happens inside a nested package, Codex still treats the project root
as the owner of `.workflow_artifacts/`.

## Procedure Index

Use these repo-local procedure docs for the five Phase 33 phases:

| Phase | Codex procedure | Portable contract |
|---|---|---|
| `discover` | `quoin/adapters/codex/procedures/discover.md` | `quoin/core/skills/discover.md` |
| `plan` | `quoin/adapters/codex/procedures/plan.md` | `quoin/core/skills/plan.md` |
| `implement` | `quoin/adapters/codex/procedures/implement.md` | `quoin/core/skills/implement.md` |
| `review` | `quoin/adapters/codex/procedures/review.md` | `quoin/core/skills/review.md` |
| `gate` | `quoin/adapters/codex/procedures/gate.md` | `quoin/core/skills/gate.md` |

## Codex Native Execution Rules

- Ask for phases in natural language and name the desired phase.
- Use Codex native planning and progress tracking for live work, while treating
  Quoin artifacts as persistent workflow state.
- Use Codex native tools for file reads, edits, tests, and checks.
- Use Codex native approvals and sandboxing. Quoin does not define replacement
  permission behavior.
- Use Codex native model or reasoning controls. Do not route from
  `claude_model` metadata.
- Read `discovery-map.json` when it exists. It is advisory structured context,
  not a replacement for required source reads or markdown artifacts.
- Keep `.workflow_artifacts/cache/` advisory. Missing cache entries never block
  a phase.
- Update session handoff files under `.workflow_artifacts/memory/sessions/` at
  natural checkpoints.
- For Codex continuation, follow `quoin/adapters/codex/handoff.md` and validate
  the handoff file with `quoin/adapters/codex/validate_codex_handoff.py`.
- When a task context exists, write Codex cost rows with
  `quoin/adapters/codex/cost_event.py`. The row uses the portable ledger
  contract and marks unavailable token and dollar telemetry as `not_available`.

## Session Handoff

Codex should write a handoff artifact before ending a meaningful workflow
session or before a context boundary. The file lives under:

```text
.workflow_artifacts/memory/sessions/<YYYY-MM-DD>-<task-name>-codex.md
```

The handoff records task status, current stage, completed work, unfinished
work, decisions, finalized artifact paths, continuation context, lesson
candidates, and cost recording status. The next Codex session reads and
validates this file before resuming:

```text
python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/<YYYY-MM-DD>-<task-name>-codex.md
```

This is deterministic validation, not runtime hook automation.

## Cost Events

Codex cost recording is explicit and repo-local. Use
`quoin/adapters/codex/cost.md` for the behavior contract and
`quoin/adapters/codex/cost_event.py` for deterministic writing and validation:

```text
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task-name> --phase <phase> --effort <low|medium|high|max|unknown>
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task-name> --expect-codex
```

The writer records known local values: runtime, task, phase, timestamp, session
id if supplied, effort, and fallback fires. It records token counts, dollar
cost, and telemetry source as `not_available` because no verified Codex local
telemetry source is present in this repository.

## Boundaries

Codex procedures intentionally avoid:

- Claude runtime command syntax.
- Claude skill frontmatter and model tier routing.
- Claude installer routing.
- Global Codex path or package assumptions.
- Codex command-file claims.
- Reimplementation of Codex approvals, sandboxing, or repo instruction loading.
