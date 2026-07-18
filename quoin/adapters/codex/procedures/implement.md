# Codex Procedure: implement

Portable contract: `quoin/core/skills/implement.md`

Shared workflow docs:

- `quoin/core/workflow/rules.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/cost-ledger.md`
- `quoin/adapters/codex/handoff.md`

## Purpose

Execute the approved plan with focused source edits, tests, artifact updates,
and a post-implementation checkpoint.

## Codex Procedure

1. Confirm implementation was explicitly requested and that the relevant gate or
   checkpoint has approved moving from planning to implementation.
2. Resolve the task directory from project-root `.workflow_artifacts/` using the
   stage-aware layout.
3. Read the complete resolved `<task-dir>/current-plan.md` before editing.
4. Read advisory context when present:
   - `.workflow_artifacts/discovery-map.json`
   - `.workflow_artifacts/cache/`
   - `.workflow_artifacts/memory/lessons-learned.md`
   - `.workflow_artifacts/memory/sessions/`
5. Use Codex native planning/progress tracking to mirror the plan tasks during
   the live implementation.
6. Edit source files with Codex native tools. Follow the existing code style and
   keep changes scoped to the current plan.
7. Run relevant tests and static checks as tasks complete. Broaden checks when
   the change touches shared contracts or cross-module behavior.
7a. After each task's code and tests are written, and before marking the task
    complete, run a bounded verify-fix loop per the portable contract in
    `quoin/core/skills/implement.md` (`## Automated verify-fix loop`): run
    Codex-native linters and the tests covering the task's affected area;
    on a real failure, retry with a targeted fix up to a bounded number of
    attempts; if no linter or test runner is available, fail-OPEN and degrade
    to the prior behavior with a one-line note; if retries are exhausted
    without a clean result, do not mark the task complete — record the
    residual failures in session state and the handoff so the next session
    sees them.
8. Update `<task-dir>/current-plan.md` task statuses as work completes.
9. Update affected advisory cache entries under `.workflow_artifacts/cache/`
   when a cache exists. Cache updates are best-effort.
10. Update session state and append an implementation cost-ledger row when a
    task context is active.
11. When yielding or closing the session, write a Codex handoff file under
    `.workflow_artifacts/memory/sessions/` and validate it with
    `quoin/adapters/codex/validate_codex_handoff.py`.
12. Run the gate procedure as a post-implementation checkpoint. Present the
    check results and stop; do not begin review until the user explicitly
    approves proceeding.

## Codex Native Notes

- If the plan is wrong or incomplete, stop and report the deviation instead of
  silently redesigning the work.
- Use Codex native approval and sandbox behavior for file edits and commands.
- Commit behavior is governed by the user's instruction and repository policy;
  this procedure does not invent Codex-specific publishing behavior.
- Do not create global setup, command files, or adapter-owned permission logic.
