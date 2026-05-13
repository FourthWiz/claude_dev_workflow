# Codex Procedure: plan

Portable contract: `quoin/core/skills/plan.md`

Shared workflow docs:

- `quoin/core/workflow/rules.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/cost-ledger.md`
- `quoin/adapters/codex/handoff.md`

## Purpose

Create or update an implementation-ready `current-plan.md` for a task, grounded
in source reads, portable artifacts, and the advisory discovery context.

## Codex Procedure

1. Resolve the task directory using the project-root `.workflow_artifacts/`
   layout and stage-aware rules from `quoin/core/workflow/task-layout.md`.
2. Read available task and memory context:
   - `.workflow_artifacts/<task-name>/architecture.md`
   - the resolved `<task-dir>/current-plan.md`, when revising
   - `.workflow_artifacts/discovery-map.json`, when present
   - `.workflow_artifacts/cache/`, when present
   - `.workflow_artifacts/memory/lessons-learned.md`
   - `.workflow_artifacts/memory/sessions/`
3. Read the relevant source files directly. The discovery map and cache are
   hints only; they do not replace source verification.
4. Use Codex native planning and progress tracking while working, but write the
   durable plan to `<task-dir>/current-plan.md`.
5. Produce the closed section set required by `quoin/core/skills/plan.md`,
   including concrete file paths, acceptance criteria, risks, and test
   expectations.
6. Update session state under `.workflow_artifacts/memory/sessions/`.
7. Append the cost-ledger row for the planning phase when a task context is
   active.
8. When yielding or closing the session, write a Codex handoff file under
   `.workflow_artifacts/memory/sessions/` and validate it with
   `quoin/adapters/codex/validate_codex_handoff.py`.
9. Stop after writing the plan. Present the next suggested gate/checkpoint, but
   do not begin implementation without explicit user direction.

## Codex Native Notes

- Ask the user before planning when requirements are materially ambiguous.
- Keep live Codex todo/progress state aligned with the artifact, but treat
  `current-plan.md` as the durable source of truth.
- For staged tasks, write the plan into the resolved stage directory, not
  blindly to the task root.
- Do not use Claude runtime command syntax, model frontmatter, global paths, or
  command-file assumptions.
