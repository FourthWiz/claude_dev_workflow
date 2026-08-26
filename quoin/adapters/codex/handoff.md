# Codex Session Handoff

Codex does not currently have a verified Quoin hook surface in this repository.
Session continuity is therefore explicit and repo-local: Codex writes a handoff
artifact before yielding, and the next Codex session reads it before resuming.

Portable contracts:

- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/rules.md`
- `quoin/core/skills/start_of_day.md`
- `quoin/core/skills/end_of_day.md`
- `quoin/core/skills/weekly_review.md`
- `quoin/adapters/codex/cost.md`
- `quoin/core/workflow/handoff-format.md` — the inter-agent dispatch/return envelope between an orchestrator and a subagent; this file governs session continuation between one Codex session and its successor, a different artifact.

## Location

Write Codex handoff files under the project-root artifact tree:

```text
.workflow_artifacts/memory/sessions/<YYYY-MM-DD>-<task-name>-codex.md
```

The project root is the repository root containing `AGENTS.md`. If Codex works
inside a nested package, the handoff file still lives under the project-root
`.workflow_artifacts/` directory.

## Required Shape

Use this markdown section set:

```markdown
# Codex Session Handoff: <task-name>

## Metadata
- runtime: codex
- handoff_version: 1
- task: <task-name>
- task_path: .workflow_artifacts/<task-name>/
- artifact_root: .workflow_artifacts/
- session_date: <YYYY-MM-DD>
- last_phase: <discover|plan|implement|review|gate|handoff|end_of_day|end_of_task|other>
- end_of_day_due: <yes|no>

## Status
<in_progress|completed|blocked>

## Current stage
<current workflow stage, stage folder, branch, and checkpoint>

## Completed in this session
- <artifact, source edit, decision, or check completed in this session>

## Unfinished work
- <specific next action, owner context, path, or blocker>

## Decisions made
- <decision and rationale, or "None">

## Finalized artifacts
- <repo-relative .workflow_artifacts/ path finalized during this session, or "None">

## Continuation context
- Next step: <the first action for the next Codex session>
- Resume from: <file path, plan task, review finding, or gate result>
- Open risks: <known blocker or "None">
- Checks run: <commands and results, or "Not run">

## Lessons learned candidates
- <candidate lesson to ask the user about, or "None">

## Cost
- cost_ledger: .workflow_artifacts/<task-name>/cost-ledger.md
- recorded: <yes|no|not-available>
- fallback_fires: <integer, usually 0 for Codex>
```

## Writing Procedure

1. Resolve the active task path using `quoin/core/workflow/task-layout.md`.
2. Read the current task artifacts, current version-control status, and any
   existing session files for the task.
3. Write or update one handoff file for the current date and task under
   `.workflow_artifacts/memory/sessions/`.
4. Summarize current task status from artifacts, not chat memory:
   - last completed phase
   - current stage or stage folder
   - latest plan/review/gate artifact
   - branch or dirty state when relevant
   - checks run and checks not run
5. Record unfinished work as concrete continuation actions. Prefer file paths,
   plan task identifiers, review finding labels, and exact commands over prose.
6. List finalized artifacts by repo-relative `.workflow_artifacts/` path. Here
   "finalized artifacts" means artifacts whose content is final for this
   session; it does not mean moving a task to `.workflow_artifacts/finalized/`.
7. Add lesson candidates only when there is a reusable takeaway. Append to
   `.workflow_artifacts/memory/lessons-learned.md` only after user confirmation.
8. If recording a Codex cost row, use the repo-local writer. It records known
   task, phase, timestamp, session id, and effort values while marking token and
   dollar telemetry as `not_available`:

```text
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task-name> --phase <phase> --effort <low|medium|high|max|unknown>
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task-name> --expect-codex
```

9. Validate the handoff:

```text
python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/<YYYY-MM-DD>-<task-name>-codex.md
```

## Reading Procedure

At the start of a continuation session:

1. Read `AGENTS.md`, then this handoff guide.
2. Read `.workflow_artifacts/memory/sessions/` and choose the latest relevant
   `<date>-<task-name>-codex.md` file for the user's task.
3. Validate it with `validate_codex_handoff.py`.
4. Read the paths named in `task_path`, `Finalized artifacts`, and
   `Continuation context`.
5. Resume from the first `Next step` unless the user gives newer instructions.
6. If validation fails, report the missing or malformed fields and reconstruct
   the handoff from on-disk artifacts before continuing.

## Boundaries

- This is a deterministic repo-local procedure, not a live Codex hook.
- Codex token counts and dollar costs are not available through a verified
  repository interface; record `not_available`, not estimates.
- Do not introduce global Codex install paths or command files.
- Do not route Codex through Claude installers, prompt-cache preambles, session
  logs, or slash-command mechanics.
- Do not move task folders into `.workflow_artifacts/finalized/` unless the
  user explicitly requests task finalization.
