# Codex Procedure: review

Portable contract: `quoin/core/skills/review.md`

Shared workflow docs:

- `quoin/core/workflow/rules.md`
- `quoin/core/workflow/task-layout.md`
- `quoin/core/workflow/session-state.md`
- `quoin/core/workflow/cost-ledger.md`
- `quoin/adapters/codex/handoff.md`

## Purpose

Review the implementation against the converged plan and write a persistent
`review-N.md` verdict artifact.

## Codex Procedure

1. Resolve the task directory from project-root `.workflow_artifacts/` using the
   stage-aware layout.
2. Read the required resolved `<task-dir>/current-plan.md`.
3. Read supporting context when present:
   - `.workflow_artifacts/<task-name>/architecture.md`
   - prior `<task-dir>/review-*.md`
   - prior `<task-dir>/critic-response-*.md`
   - `.workflow_artifacts/discovery-map.json`
   - `.workflow_artifacts/cache/`
   - `.workflow_artifacts/memory/sessions/`
4. Read the full version-control diff for the implementation. Read full source
   files selectively where the diff, plan, integration points, security issues,
   or prior findings require more context.
5. Run the tests and checks needed to support the review verdict. Report any
   checks that could not be run.
6. Write the next `<task-dir>/review-N.md` artifact with the closed verdict set:
   `APPROVED`, `CHANGES_REQUESTED`, or `BLOCKED`.
7. Cite each issue with a file and line reference and a concrete remediation.
8. Update session state and append a review cost-ledger row when a task context
   is active.
9. When yielding or closing the session, write a Codex handoff file under
   `.workflow_artifacts/memory/sessions/` and validate it with
   `quoin/adapters/codex/validate_codex_handoff.py`.
10. Stop after the review. On `APPROVED`, recommend the gate procedure. On
   `CHANGES_REQUESTED` or `BLOCKED`, return control to implementation or
   re-planning as appropriate.

## Codex Native Notes

- Use a code-review stance: findings first, ordered by severity.
- Do not edit source files while reviewing.
- Do not publish, push, or create remote artifacts unless the user separately
  requests that action.
- Do not rely on Claude runtime command syntax, frontmatter, or installer
  behavior.
