---
name: start_of_day
description: "Restores context from the daily cache and unfinished sessions so you can resume where you left off. Use this skill for: /start_of_day, 'what was I working on', 'resume', 'pick up where I left off', 'morning standup', 'SOD', 'start of day'. Reads the latest daily cache, checks git state, and presents a clear picture of what to do next."
model: haiku
---

# Start of Day

You restore context from the previous session(s) so the user can seamlessly resume work. You read the daily cache, check current git state, and present a clear action plan.

## Session bootstrap

Cost tracking note: `/start_of_day` is a lightweight daily-orientation skill. Append to the cost ledger only if a specific task context is clearly active (the user mentioned a task name or there's a clear active task from session state). If in doubt, skip cost recording — don't guess a task name.

If a task context is active: append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `start-of-day`.

## Process

### Step 1: Check for un-promoted insights

Look for `.workflow_artifacts/memory/daily/insights-<yesterday>.md` (yesterday's date). If it exists:
- Count entries tagged `Promote?: yes` or `Promote?: maybe`
- If any exist, tell the user at the start of the briefing:
  > "Yesterday's insight scratchpad has N un-promoted entries — looks like `/end_of_day` wasn't run. Want to review them now or skip?"
  - If they want to review: run the promotion flow from `/end_of_day` Step 3b inline before continuing
  - If they skip: proceed normally (entries stay in the file for next time)

If the file doesn't exist or has no promotable entries, skip this step silently.

### Step 2: Find the latest daily cache

Look in `.workflow_artifacts/memory/daily/` for the most recent `.md` file. This is what `/end_of_day` saved. If there's no daily cache, check `.workflow_artifacts/memory/sessions/` for any session files and work from those directly.

If neither exists, tell the user there's no saved state and suggest running `/discover` to set up fresh context.

### Step 3: Read context

Read these files in parallel:

1. **Daily cache** — `.workflow_artifacts/memory/daily/<latest>.md` — the consolidated state
2. **Git log** — `.workflow_artifacts/memory/git-log.md` — recent commit history and logic
3. **Active session files** — any `.workflow_artifacts/memory/sessions/*` files with status `in_progress` or `blocked`
4. **Current git state** — for each repo in the project folder:
   ```bash
   git -C <repo> status --short
   git -C <repo> branch --show-current
   git -C <repo> log --oneline -5
   ```
   Check for uncommitted changes, stale branches, open PRs.

### Step 4: Reconcile

For each unfinished task from the daily cache, run these checks and report the result:

1. **Branch match** — Is the repo on the branch the daily cache says? If not, report the actual branch.
2. **New remote commits** — Run `git log HEAD..origin/<branch> --oneline`. If output is non-empty, report "N new commits from remote."
3. **Uncommitted local changes** — Check `git status --short`. If non-empty, list the changed files.
4. **Stale PRs** — If `gh` is available, run `gh pr list --head <branch> --json number,title,reviewDecision,statusCheckRollup --limit 5`. Report any PRs with new reviews or failed checks. If `gh` is not available, report "PR check skipped — gh CLI not installed."

Report each check result in the briefing's "## Since last session" section (matching the existing Step 5 template). If everything matches the daily cache, say "Git state matches cached state — no drift detected."

### Step 5: Present the briefing

Output a clear, concise briefing:

```markdown
# Good morning 👋

## Since last session
- <any new commits from others, PR reviews, CI results>
- <any drift or changes to note>

## Unfinished work

### 1. <task-name> — <stage>
**Branch:** `<branch-name>`
**Resume at:** <exactly where to pick up>
**Context:** <key decisions and rationale from last session>
**Next steps:**
1. <first thing to do>
2. <second thing>

### 2. <task-name-2> — <stage>
...

## Blocked items
- <task>: <blocker> — <suggested resolution>

## Suggested priority
<Based on urgency, dependencies, and momentum — what to tackle first and why>
```

Keep the briefing factual. Report what you found in each step — do not speculate about what the user might want to do beyond what the daily cache and git state suggest. Let the user decide priorities.

### Step 6: Offer to resume

After presenting the briefing, ask the user what they want to work on:
- Resume a specific unfinished task (invoke the appropriate skill — `/implement`, `/review`, etc.)
- Start something new
- Check on a blocked item

## Handling multiple unfinished sessions

If the daily cache has multiple unfinished tasks:
- Present them all, ordered by suggested priority
- Note any dependencies between them (e.g., "Task B depends on Task A's review passing")
- Let the user pick which to resume

## No daily cache found

If there's no daily cache but the project has session files or git history:
- Read the most recent session files from `.workflow_artifacts/memory/sessions/`
- Read `.workflow_artifacts/memory/git-log.md` if it exists
- Reconstruct what was likely happening
- Present what you found and suggest next steps

If nothing exists at all:
- Suggest `/discover` to index the repos
- Ask the user what they'd like to work on

## Important behaviors

- **Be concise.** This is a morning briefing, not a novel. The user wants to know what to do, not re-read everything.
- **Surface surprises.** If overnight CI broke, or someone force-pushed to a branch, or a PR got rejected — lead with that.
- **Respect the user's time.** Don't make them re-read the entire plan. Summarize the resumption point in 2-3 sentences with the exact file/task/line to start at.
- **Check git for real.** The daily cache is what *should* be true. Git state is what *is* true. Always reconcile.
