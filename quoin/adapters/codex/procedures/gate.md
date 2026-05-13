# Codex Procedure: gate

Portable contract: `quoin/core/skills/gate.md`

Shared workflow docs:

- `quoin/core/workflow/rules.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/cost-ledger.md`
- `quoin/adapters/codex/handoff.md`

## Purpose

Run a checkpoint for a completed phase, present the result to the user, and
write an audit log only after explicit user approval.

## Codex Procedure

1. Identify the phase boundary being checked: post-discovery, post-planning,
   post-implementation, or post-review.
2. Resolve the task directory from project-root `.workflow_artifacts/` when the
   gate is task-scoped. Standalone discovery gates may only update memory and
   session state.
3. Read the phase artifacts relevant to the boundary:
   - `.workflow_artifacts/discovery-map.json`, when present
   - `.workflow_artifacts/<task-name>/architecture.md`, when present
   - resolved `<task-dir>/current-plan.md`, when present
   - resolved `<task-dir>/review-*.md`, when present
   - version-control status and diffs, when implementation or review is in
     scope
4. Choose the gate level from `quoin/core/skills/gate.md`: smoke, standard, or
   full. If the right level is unclear, use the full gate.
5. Run the automated checks before presenting a verdict. Use the repository's
   configured test, lint, type, and validation commands where they exist.
6. Present a plain-prose checkpoint summary with:
   - checks run
   - pass/fail status
   - blocking failures
   - warnings
   - produced artifacts
   - recommended next phase
7. Stop for explicit user approval. Do not write the gate audit log when the
   user rejects the gate.
8. After approval, write
   `.workflow_artifacts/<task-name>/gate-{phase}-{date}.md` or the
   stage-resolved equivalent required by the portable contract.
9. Update session state and append a conditional cost-ledger row when a task
   context is determinable.
10. When yielding or closing the session, write a Codex handoff file under
    `.workflow_artifacts/memory/sessions/` and validate it with
    `quoin/adapters/codex/validate_codex_handoff.py`.
11. Stop after the audit log. Do not start the next phase automatically.

## Codex Native Notes

- Use Codex native tool execution and approval behavior for checks.
- Report checks that were not run and why.
- Do not duplicate Codex sandboxing or permissions in Quoin docs.
- Do not introduce command files, global paths, or runtime install claims.
