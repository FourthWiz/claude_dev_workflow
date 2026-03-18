---
name: end_of_task
description: "Finalizes a completed task: ensures all changes are committed, pushes branch to remote, prompts for lessons learned, and marks the task as complete. Does NOT create a PR — that's a separate explicit action. Use this skill for: /end_of_task, 'finalize this', 'we're done', 'ship it', 'task complete', 'wrap up this task', 'accept and push'. This is the explicit user acceptance of completed, reviewed work — the last step before moving on."
model: sonnet
---

# End of Task

You finalize a completed task. This is the user's explicit acceptance that the work is done — reviewed, approved, and ready to ship. You handle the git ceremony (commit, push to branch), capture lessons, and close out the task cleanly. **You do NOT create a PR** — that's a separate, explicit action the user takes when they're ready.

## When to use

Only after:
1. `/review` has given an APPROVED verdict
2. The final `/gate` has passed
3. The user explicitly says to finalize (e.g., `/end_of_task`, "ship it", "we're done")

This skill is never auto-invoked. The user must consciously accept the work.

## Process

### Step 1: Pre-flight checks

Before touching git, verify everything is clean:

1. **Review status** — read the latest `<task-folder>/review-N.md`. Confirm verdict is APPROVED. If not, stop and tell the user.
2. **Tests pass** — run the test suite one final time. If anything fails, stop.
3. **No uncommitted changes** — run `git status`. If there are unstaged/uncommitted changes:
   - Show them to the user
   - Ask: commit these too, or stash them?
4. **Branch state** — check if the branch is up to date with the base branch. If behind, rebase/merge and re-run tests.
5. **No secrets** — quick scan of the diff for passwords, API keys, tokens.

Present a pre-flight summary:

```
Pre-flight: end_of_task
✅ Review: APPROVED (review-2.md)
✅ Tests: 47 passed, 0 failed
✅ Working tree: clean
✅ Branch: feat/refund-flow, up to date with main
✅ No secrets detected
Ready to finalize.
```

### Step 2: Commit any remaining changes

If there are uncommitted changes the user wants to include:

- Stage the relevant files (not blanket `git add .`)
- Write a conventional commit message:
  ```
  <type>(<scope>): <description>

  <why this change was made>
  ```
- Commit

If everything is already committed, skip this step.

### Step 3: Push

Push the branch to the remote:

```bash
git push -u origin <branch-name>
```

If the push fails (e.g., remote rejected, auth issue), report the error and let the user resolve it.

### Step 4: Prompt for lessons learned

Ask the user:

> "Task complete. Anything that surprised you, or that the workflow should handle differently next time?"

If they share something, append to `memory/lessons-learned.md`:

```markdown
## <date> — <task-name>
**What happened:** <what the user described>
**Lesson:** <the reusable takeaway>
**Applies to:** <relevant skills>
```

Also auto-capture lessons if:
- The critic-revise loop ran more than 3 rounds (what made convergence hard?)
- The review requested changes (what did /implement miss?)
- A rollback happened during this task (what went wrong?)

### Step 5: Archive task artifacts

Move the task's artifact folder to `implemented/`:

- **Task within a feature:** move `<feature-folder>/<task-name>/` → `<feature-folder>/implemented/<task-name>/`
- **Standalone task:** move `<project-folder>/<task-name>/` → `<project-folder>/implemented/<task-name>/`

Create the `implemented/` directory if it doesn't exist yet.

After moving, check if this was the last active task in a feature (no remaining task subfolders outside `implemented/`). If so, ask the user:
> "All tasks in `<feature-name>` are complete. Move the entire feature to `implemented/`?"

If yes, move `<project-folder>/<feature-name>/` → `<project-folder>/implemented/<feature-name>/`.

### Step 6: Update session state

Update `memory/sessions/<date>-<task-name>.md`:
- Set status to `completed`
- Record the final branch name and commit hash
- Note any lessons captured

### Step 7: Report

Tell the user:

```
Task finalized: <task-name>

Branch: feat/refund-flow → pushed to origin
Commits: <N> commits
Tests: all passing
Review: APPROVED

Archived: <task-name>/ → implemented/<task-name>/
Lessons captured: <yes/no>
Session marked as completed.

Next: when you're ready, create a PR from the branch.
```

Clean and done.

## Important behaviors

- **Run tests one last time.** Even if they passed 5 minutes ago. Code might have changed.
- **Never force-push.** Use regular `git push`. If the branch has diverged, tell the user and let them decide how to resolve.
- **No PR creation.** This skill pushes the branch only. The user creates the PR separately when they're ready. Remind them at the end.
- **This is a celebration, not a chore.** The task is done. Keep the output clean and satisfying.
