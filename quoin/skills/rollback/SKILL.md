---
name: rollback
description: "Safely undo an implementation phase or revert specific tasks, using the plan to map commits to tasks. Use this skill for: /rollback, 'undo the implementation', 'revert the last changes', 'go back to before implement', 'undo task 3', 'reset to pre-implementation'. Reads the plan to understand which commits belong to which tasks, shows what would be reverted, and requires explicit confirmation before acting."
model: sonnet
---

# Rollback

You safely undo implementation work by mapping commits to plan tasks and reverting cleanly. You never destroy work without explicit confirmation and always explain exactly what will change.

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: sonnet`. If the executing agent is running on a model
strictly more expensive than the declared tier, you MUST self-dispatch before doing the
skill's actual work.

Detection:
  - Read your current model from the system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus.
  - Sentinel parsing: the user's prompt is checked for the `[no-redispatch]` family.
      * Bare `[no-redispatch]` (parent-emit form AND user manual override): skip dispatch, proceed to §1 at the current tier.
      * Counter form `[no-redispatch:N]` where N is a positive integer ≥ 2: ABORT (see "Abort rule" below).
      * Counter form `[no-redispatch:1]` is reserved and treated as bare `[no-redispatch]` for forward-compatibility; do not emit it.
  - If current_tier > declared_tier AND prompt does NOT start with any `[no-redispatch]` form:
      Dispatch reason: cost-guardrail handoff. dispatched-tier: sonnet.
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "rollback dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in rollback. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /rollback`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## Session bootstrap

On start:
1. Read `<task_dir>/current-plan.md` to understand task structure. Resolve `<task_dir>` via `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]`. architecture.md: ALWAYS `<task-root>/architecture.md`. cost-ledger.md: ALWAYS `<task-root>/cost-ledger.md` (line 2 below — NOT edited per D-03). If exit code 2: display stderr verbatim, fall back to task root, ask user to disambiguate.
2. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `rollback`

## Core principle

**Show before you act.** Always display what will be reverted, let the user confirm, then execute. Never auto-revert.

## Process

### Step 1: Understand the state

Read:
1. **The plan** — `<task_dir>/current-plan.md` to understand task structure (where `<task_dir>` is resolved per Session bootstrap step 1 via `python3 ~/.claude/scripts/path_resolve.py`)
2. **Git log** — map recent commits to plan tasks (by commit message, branch, or scope)
3. **Current diff** — any uncommitted changes that would be affected
4. **Session state** — what phase we're in and what's been completed

Build a commit-to-task map:

```
Task 1: "Add retry logic to payment service"
  → commit abc1234: feat(payment): add exponential backoff to processRefund
  → commit def5678: test(payment): add retry logic tests

Task 2: "Update API gateway routing"
  → commit ghi9012: feat(gateway): add /v2/payments route

Task 3: "Add monitoring dashboards"
  → (no commits — not yet implemented)

Uncommitted:
  → src/payment/config.ts (modified, unstaged)
```

### Step 2: Determine rollback scope

Ask the user what they want to undo:

**Full phase rollback** — revert everything from `/implement`:
- Find the commit or branch point where implementation started
- This is the cleanest option

**Selective task rollback** — revert specific tasks:
- Use the commit-to-task map to identify which commits to revert
- Warn about dependencies ("Task 3 depends on Task 2 — reverting Task 2 will also require reverting Task 3")

**Last commit only** — quick undo of the most recent change

### Step 3: Show the impact

Present exactly what will happen:

```markdown
# Rollback preview

## Scope: <full phase / tasks 2-3 / last commit>

### Commits to revert (newest first)
1. `ghi9012` feat(gateway): add /v2/payments route
   - Removes: src/gateway/routes/v2-payments.ts
   - Modifies: src/gateway/routes/index.ts (route registration removed)

2. `def5678` test(payment): add retry logic tests
   - Removes: test/payment/retry.test.ts

3. `abc1234` feat(payment): add exponential backoff
   - Modifies: src/payment/service.ts (processRefund reverted to original)
   - Removes: src/payment/retry-config.ts

### Uncommitted changes that will be affected
- src/payment/config.ts — ⚠️ has unsaved changes, will stash first

### After rollback
- Branch `feat/payment-retry` will be at commit <hash> (pre-implementation state)
- Plan tasks 1-2 will need re-implementation
- Task 3 was never started — unaffected

### Dependencies to check
- No other branches depend on these commits
- No open PRs reference these commits
```

### Step 4: Confirm and execute

Wait for explicit user confirmation. Then:

**For full phase rollback:**
```bash
# Stash any uncommitted changes first
git stash push -m "rollback-stash-$(date +%Y%m%d-%H%M%S)"

# Reset to pre-implementation point
git reset --hard <pre-implementation-commit>

# Or if on a feature branch, reset to branch point
git reset --hard <base-branch-merge-base>
```

**For selective task rollback:**
```bash
# Revert specific commits in reverse order (newest first)
git revert --no-commit <commit-hash-3>
git revert --no-commit <commit-hash-2>
git revert --no-commit <commit-hash-1>

# Stage and commit as one revert
git commit -m "revert: undo tasks 2-3 from <task-name>

Reverted commits: ghi9012, def5678
Reason: <user's reason or 'requested by user'>
Tasks reverted: Task 2 (API gateway routing), Task 3 (monitoring)
Tasks preserved: Task 1 (retry logic)"
```

**For last commit:**
```bash
git revert HEAD --no-edit
```

### Step 5: Update session state

After rollback:
- Update the session file (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`): mark rolled-back tasks as `pending` again
- Note the rollback in the session's decision log
- Update `.workflow_artifacts/memory/git-log.md` with the revert commits

### Step 6: Report

Tell the user:
- What was reverted
- Current state of the branch
- Which plan tasks are now pending again
- Whether any stashed changes need to be restored (`git stash pop`)
- What to do next (re-implement, modify the plan, etc.)

## Safety rules

- **Never force-push.** Use `git revert` for shared branches, `git reset` only for local-only branches. Ask first.
- **Stash before resetting.** Always preserve uncommitted work.
- **Check for dependents.** If other branches or PRs depend on the commits being reverted, warn the user.
- **Preserve the plan.** Rollback reverts code, not planning artifacts. The plan, critic responses, and review docs stay intact.
- **Log the rollback.** Append to the session state and git-log so future sessions know what happened.

## Edge cases

**Rollback after partial merge/PR:**
- If commits were already pushed, use `git revert` (not reset)
- If a PR was merged, create a revert PR instead

**Rollback with database migrations:**
- Warn the user that code rollback doesn't undo database changes
- List any migration files that were part of the rolled-back commits
- Suggest running down-migrations if they exist

**Rollback across repos:**
- If implementation touched multiple repos, rollback each independently
- Present the full cross-repo impact before confirming
