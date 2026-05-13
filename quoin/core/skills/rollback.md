# rollback

Runtime-neutral intent for the rollback skill. Any runtime adapter that
implements this skill should match the contract described here.

## Purpose

Safely undo implementation work by mapping commits to plan tasks and reverting
cleanly. The skill shows a preview of what will change and requires explicit
user confirmation before executing any destructive git operation.

## When to use

- When the user wants to undo the last commit, revert specific tasks from a
  completed implement phase, or roll back an entire implementation phase.
- Available at any point in the workflow but most useful between or after
  implementation phases.
- Never auto-invoked; always requires an explicit user request.

## Inputs

- Converged `current-plan.md` from the resolved task subfolder under
  `.workflow_artifacts/<task-name>/`.
- Git log and diff for the affected repositories.
- Session state under `.workflow_artifacts/memory/sessions/` (advisory).

All reads MUST tolerate missing optional inputs. The skill MUST apply the
stage-aware path resolver when locating phase artifacts.

## Output

- A "rollback preview" showing scope, commits to revert, affected files,
  post-rollback branch state, and dependencies to check — rendered to the user
  before any action.
- On confirmation: executed git operations (revert or reset); the branch left
  in a clean, known state.
- Updated session-state file under `.workflow_artifacts/memory/sessions/`
  marking rolled-back tasks as pending and noting the rollback in the decision
  log.
- Updated git-log memory under `.workflow_artifacts/memory/git-log.md` with
  the revert commits.
- A new entry appended to the cost ledger at
  `.workflow_artifacts/<task-name>/cost-ledger.md` (phase: `rollback`).

Planning artifacts — `current-plan.md`, critic responses, review docs — MUST
remain intact after rollback; the skill reverts code, not plans.

## Behavior contract

- The skill MUST show the rollback preview before executing anything.
- The skill MUST wait for explicit user confirmation before performing any
  destructive git operation.
- The skill MUST stash uncommitted changes before resetting.
- The skill MUST prefer non-destructive operations (revert) on shared branches
  over destructive ones (reset).
- The skill MUST warn the user when other branches or open PRs depend on the
  commits being reverted.
- The skill MUST NOT force-push.
- The skill MUST preserve planning artifacts.
- The skill MUST append a rollback record to the session-state decision log and
  to the git-log memory file.
- The skill MUST tolerate missing optional inputs without aborting.
- The skill MUST apply the stage-aware path resolver when locating phase
  artifacts.
- Cost-ledger writes are mandatory at session open (phase: `rollback`).

## Out of scope

- The specific model tier used to execute the skill — adapter-specific.
- The self-dispatch / cost-guardrail mechanism (sentinel grammar, child-prompt
  prefixes, abort rules) — adapter-specific.
- The git tool invocation surface (CLI binary names, sandbox/approval prompts,
  repo-walk mechanics) — adapter-specific. The contract specifies that
  destructive git operations MUST be preceded by user confirmation, not the
  precise CLI a runtime uses.
- Cost-ledger row format — adapter-specific plumbing.
- Session-state Class A writer mechanism — adapter-specific.

## Notes

- Cross-repo rollback: present full cross-repo impact before any single-repo
  action.
- Database migrations: warn user that code rollback does not undo schema
  changes. List any migration files in rolled-back commits and suggest
  down-migrations if they exist.
- PR/merge-aware: if commits were already pushed or merged, use revert (not
  reset); if a PR was merged, suggest a revert PR.
- The runtime adapter owns: model tier, dispatch mechanism, git CLI invocation,
  cost-ledger plumbing, session-state writer atomicity.
