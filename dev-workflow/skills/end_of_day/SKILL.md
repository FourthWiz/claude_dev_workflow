---
name: end_of_day
description: "Consolidates all of today's work across all sessions into a daily cache for next-day resumption. Works in any session — fresh or active. Use this skill for: /end_of_day, 'wrapping up', 'done for the day', 'save my progress', 'end of day', 'EOD'. Captures what was worked on, what's unfinished, blockers, decisions made, and recent git activity. The daily cache feeds into /start_of_day for seamless resumption."
model: haiku
---

# End of Day

You consolidate all of today's work into a daily cache that `/start_of_day` can restore tomorrow. This skill works in any session — you can run it in a fresh session at end of day, or from inside an active working session. Everything except Step 1 reads from disk, so no prior context is needed.

## How sessions and daily caches work

```
.workflow_artifacts/
├── memory/
│   ├── sessions/
│   │   ├── 2026-03-17-auth-refactor.md       ← individual session states
│   │   ├── 2026-03-17-payment-migration.md
│   │   └── 2026-03-18-auth-refactor.md
│   ├── daily/
│   │   ├── 2026-03-17.md                      ← daily rollup (from end_of_day)
│   │   └── 2026-03-18.md
│   ├── git-log.md                             ← rolling log of recent commits
│   ├── repos-inventory.md
│   ├── architecture-overview.md
│   └── dependencies-map.md
├── <task-name>/                               ← active task artifacts
└── finalized/                                 ← completed task archives
```

Multiple sessions can run in a day (parallel tasks, or revisiting a task). Each session writes its own state file. `/end_of_day` reads ALL session files for today, picks out the unfinished ones, and rolls them into one daily cache.

## Process

### Step 1: Save current session state (skip if no active task)

**If this session has no active task** (e.g. you opened a fresh session just to run `/end_of_day`), skip this step entirely and proceed to Step 2. The existing session files on disk are the source of truth.

**If there is active work in this session**, create or update a session file at:
```
.workflow_artifacts/memory/sessions/<date>-<task-name>.md
```

The session file captures:

```markdown
# Session: <task-name>
**Date:** <YYYY-MM-DD>
**Status:** in_progress | completed | blocked

## What was worked on
<Brief description of what this session accomplished>

## Current stage
<Which workflow step we're at: architect / plan / critic / revise / implement / review>
**Round:** <if in critic-revise loop, which round>

## Completed in this session
- <specific things done — tasks implemented, files created, reviews passed>

## Unfinished work
- <what remains — specific tasks, next steps>
- <where exactly to pick up: file paths, task numbers, branch names>

## Decisions made
- <important decisions and their rationale — these are easy to forget overnight>

## Blockers
- <anything blocking progress — waiting on someone, unclear requirement, technical issue>

## Key context
- <branch name>
- <relevant file paths>
- <open PR URLs if any>
- <environment or config notes>

## Recent commits in this session
<list of commits made during this session with their messages and what they did>
```

### Step 2: Update git-log.md

Scan all repos in the project folder and update `.workflow_artifacts/memory/git-log.md` with recent commits. This is a rolling window — keep the last ~50 commits across all repos, newest first.

```markdown
# Recent Git Activity

Last updated: <datetime>

## <repo-name>
### <branch-name>
- `<short-hash>` <commit message> — <date>
  <1-line summary of what the commit actually changed and why>
- `<short-hash>` <commit message> — <date>
  <1-line summary>

## <other-repo>
...
```

To build this:
```bash
# For each repo directory
git -C <repo-path> log --all --oneline --date=short --format="%h %s — %ad" -20
```

Then for each commit, briefly describe what it changed (read the diff summary, not the full diff):
```bash
git -C <repo-path> diff-tree --no-commit-id --name-status -r <hash>
```

Keep commit descriptions to one sentence. Base them on the commit message and diff summary — do not speculate about intent beyond what the message states.

The goal is to capture the *logic* of recent changes — not just file lists but *why* things changed. This helps `/start_of_day` and `/architect` understand momentum and recent direction.

### Step 3: Produce the daily cache

Read all session files for today from `.workflow_artifacts/memory/sessions/<today>-*.md`. For each:
- If status is `completed` → note it as done, no action needed
- If status is `in_progress` or `blocked` → include in the daily cache

Write the daily cache to `.workflow_artifacts/memory/daily/<date>.md`:

```markdown
# Daily Cache — <YYYY-MM-DD>

## Summary
<1-2 sentences: what was the day's focus, what got done, what's left>

## Completed today
- **<task-name>**: <what was finished>

## Unfinished — carry forward

### <task-name-1>
**Stage:** <architect / plan round 3 / implement task 4 of 7 / review>
**Branch:** <branch-name>
**Pick up at:** <exactly where to resume — file, task number, next step>
**Key context:**
- <decisions made that affect next steps>
- <blockers to resolve>
- <relevant file paths and PR URLs>
**Remaining work:**
- <specific next actions>

### <task-name-2>
...

## Decisions log
<All decisions made today across all sessions, with rationale>

## Git activity summary
<High-level: N commits across M repos. Key changes: ...>
<Reference .workflow_artifacts/memory/git-log.md for details>

## Cost summary
<!-- Session counts from cost-ledger.md files — no ccusage calls -->
- **<task-name>**: <N> sessions tracked today (phases: <plan, implement, ...>)
- **<task-name-2>**: <N> sessions tracked today (phases: ...)
- **Day total**: <N> sessions across <M> tasks
*Dollar amounts: run /end_of_task for each completed task to see the full cost breakdown.*

## Tomorrow's priorities
<Based on what's unfinished, suggest what to tackle first>
```

To populate the **Cost summary** section: for each active task today, check if `.workflow_artifacts/<task-name>/cost-ledger.md` exists. If it does, count the data lines (non-header, non-blank) where the date column matches today's date, and list the unique phase values. Do NOT run `npx ccusage` — Haiku does not orchestrate cost lookups. Just report counts and phases. Dollar amounts are computed by `/end_of_task`.

### Step 3b: Review and promote daily insights

Check if `.workflow_artifacts/memory/daily/insights-<today>.md` exists. If it does:

**Pass 1 — Filter:**
- Skip entries tagged `Promote?: no`
- Collect entries tagged `yes` (high-confidence) and `maybe` (review needed)

**Pass 2 — Deduplicate:**
- Read `.workflow_artifacts/memory/lessons-learned.md`
- If a collected entry is substantially similar to an existing lesson, drop it or flag it as a duplicate
- An entry is a duplicate if it describes the same root cause AND the same takeaway as an existing lesson. Entries about the same topic but with different lessons are NOT duplicates — keep both and note the connection.

**Pass 3 — Tier 3 check:**
- Any entry with `Applies to: workflow` or type `workflow-friction` is a Tier 3 candidate
- Append those to `.workflow_artifacts/memory/workflow-suggestions.md` in this format:
  ```markdown
  ## <date> — <source-task>
  **Suggestion:** <what should change in the workflow>
  **Why:** <the observation from the insight entry>
  **Affects:** <relevant SKILL.md or CLAUDE.md section>
  **Status:** surfaced
  ```
- Tell the user: "I've added N workflow improvement suggestion(s) to `.workflow_artifacts/memory/workflow-suggestions.md`."

**Promotion confirmation:**
If there are entries to promote (after filtering and dedup), present a compact list:

```
I captured N insights today worth keeping. Confirm which to add to lessons-learned:

1. [yes] <insight summary, 1 line>
2. [maybe] <insight summary, 1 line>
3. [maybe] <insight summary, 1 line>

Reply with the numbers to keep (e.g. "1 3"), "all", or "none".
```

Wait for the user's response, then append confirmed entries to `.workflow_artifacts/memory/lessons-learned.md`:

```markdown
## <date> — <task-name>
**What happened:** <the insight>
**Lesson:** <the reusable takeaway>
**Applies to:** <relevant skills>
```

If the insights file doesn't exist or has no promotable entries, skip this step silently.

### Step 3c: Prune lessons-learned if oversized

Check `.workflow_artifacts/memory/lessons-learned.md`. Count the number of lesson entries by matching lines that begin with `## ` followed by a date pattern (YYYY-MM-DD) — i.e., lines matching the regex `^## \d{4}-\d{2}-\d{2}`. Ignore any such patterns inside HTML comments (`<!-- -->`), code blocks, or template examples.

**If the count exceeds 30 entries**, present a pruning prompt to the user:

> "lessons-learned.md has grown to N entries (~X tokens). Large files add a fixed token cost to every /plan, /critic, and /architect session. Would you like to prune?"
>
> Options:
> 1. **Auto-prune** — I'll merge related entries, remove entries older than 90 days that haven't been referenced, and consolidate duplicates. You review before I save.
> 2. **Manual prune** — I'll list all entries with a 1-line summary; you pick which to keep.
> 3. **Skip** — keep the file as-is.

**Auto-prune rules** (if selected):
1. Group entries by `Applies to:` tag. If 3+ entries have the same tag and similar content, merge them into one consolidated entry preserving all unique information.
2. Entries older than 90 days that are generic advice (e.g., "always run tests", "check error handling") can be removed — the behavior should be internalized by now.
3. Entries that reference specific files or functions that no longer exist in the codebase can be removed (check with a quick file-existence test).
4. Always preserve: entries tagged as applying to `/architect` or `/critic` (highest-leverage skills), entries less than 30 days old, entries the user explicitly marked as important.
5. Show the proposed changes to the user in a before/after summary and wait for explicit confirmation before overwriting.

**If the count is 30 or fewer**, skip this step silently.

### Step 4: Prompt for lessons learned

Ask the user:

> "Anything else that surprised you today, or that should work differently next time?"

(If insights were already promoted in Step 3b, this catches anything Claude missed.)

If they share something, append it to `.workflow_artifacts/memory/lessons-learned.md` in the same format. If they say "nothing" or skip, that's fine.

Also: if any tasks were rolled back today, or if the critic-revise loop ran more than 3 rounds, auto-add a lesson capturing what made it difficult.

### Step 5: Report to user

Tell the user:
- What was saved
- How many sessions were active today, how many completed vs unfinished
- What the daily cache recommends for tomorrow
- Remind them to run `/start_of_day` when they resume

## Important behaviors

- **Capture decisions.** The hardest thing to remember across days isn't *what* you were doing — it's *why* you made certain choices. Always capture decision rationale.
- **Be specific about resumption points.** "Continue implementing" is useless. "Continue with Task 4 (add retry logic to payment.service.ts:processRefund), branch `feat/payment-retry`, tests for Tasks 1-3 passing" is useful.
- **Don't overwrite previous sessions.** If there's already a session file for this task today (from an earlier session), update it rather than replacing it — preserve the history of what was done earlier.
- **Git log captures logic, not just files.** "Modified 3 files" tells you nothing. "Added exponential backoff to payment retries because Stripe recommends it for idempotent requests" tells you everything.
