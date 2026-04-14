---
name: weekly_review
description: "Aggregates the week's meaningful work into a structured review. Use this skill for: /weekly_review, 'weekly summary', 'what did I do this week', 'week recap', 'friday review', 'weekly standup', 'weekly report'. Reads daily caches, session files, git history, and lessons learned to produce a comprehensive but concise picture of the week's progress, decisions, and outcomes."
model: haiku
---

# Weekly Review

You produce a structured summary of the week's meaningful work — what was accomplished, what's still in flight, key decisions made, and lessons learned. Designed to run on Friday (or whenever the user wants a week-level view).

## Process

### Step 1: Determine the week range

Default to the current week (Monday through today). If the user specifies a different range, use that.

```bash
# Monday of this week
date -v-Mon +%Y-%m-%d 2>/dev/null || date -d 'last monday' +%Y-%m-%d
```

### Step 2: Gather sources

Read these in parallel:

1. **Daily caches** — `.workflow_artifacts/memory/daily/<date>.md` for each day in the range. These are the primary source — they contain completed work, unfinished carry-forwards, decisions, and git summaries.

2. **Session files** — `.workflow_artifacts/memory/sessions/<date>-*.md` for dates in the range. These have finer-grained detail on individual tasks.

3. **Git history** — for each repo in the project folder:
   ```bash
   git -C <repo> log --all --oneline --after="<monday>" --before="<saturday>" --date=short --format="%h %s — %ad (%an)"
   ```
   Count commits, identify active branches, note merged PRs.

4. **Git log** — `.workflow_artifacts/memory/git-log.md` for the rolling commit log with context.

5. **Lessons learned** — `.workflow_artifacts/memory/lessons-learned.md` — filter for entries dated within this week.

6. **Task folders** — scan `.workflow_artifacts/` for task subfolders that were created or modified this week. Check for `architecture.md`, `current-plan.md`, `review-*.md` artifacts to understand what stages tasks went through.

7. **Cost data** — from the daily caches (source 1), read the `## Cost summary` section for each day. Aggregate session counts per task across the week. Do NOT run `npx ccusage` — Haiku does not orchestrate cost lookups. Dollar amounts come from `/end_of_task` reports.

### Step 3: Build the review

Produce the weekly review in this format:

```markdown
# Weekly Review — <YYYY-MM-DD> to <YYYY-MM-DD>

## Highlights
<3-5 bullet points: the most important things that happened this week. Lead with outcomes, not activity.>

## Completed Work

### <task-name>
- **What:** <1-2 sentence description of the deliverable>
- **Stages:** <which workflow stages it went through, e.g., architect -> plan -> implement -> review>
- **Branch/PR:** <branch name, PR URL if available>
- **Key commits:** <most significant commits with short descriptions>
- **Impact:** <what this unblocks or enables>

### <task-name-2>
...

## In Progress

### <task-name>
- **Current stage:** <where it's at in the workflow>
- **Progress:** <what's done vs what remains, e.g., "4 of 7 tasks implemented">
- **Branch:** <branch name>
- **Blockers:** <if any>
- **ETA signal:** <is it on track, slower than expected, or blocked?>

### <task-name-2>
...

## Decisions Made
| Decision | Rationale | Task | Date |
|----------|-----------|------|------|
| <what was decided> | <why> | <which task> | <when> |

## Lessons Learned This Week
<entries from lessons-learned.md dated this week, or new insights from reviewing the week>

## Git Activity
- **Commits:** <total> across <N> repos
- **Active branches:** <list>
- **Merged:** <branches merged this week>
- **Repos touched:** <which repos had activity>

## Metrics (if available)
- Tasks completed: <N>
- Tasks started: <N>
- Critic-revise rounds (avg): <N> (if thorough_plan was used)
- Rollbacks: <N>

## Weekly cost summary
<!-- Derived from daily cache cost summaries — no ccusage calls -->
| Task | Sessions | Notes |
|------|----------|-------|
| <task-name> | <N> | phases: <plan, critic, implement, review> |
| <task-name-2> | <N> | phases: <plan, implement> |
| **Week total** | **<N>** | across <M> tasks |

*Dollar amounts: check each task's /end_of_task report, or run `npx ccusage` manually.*

## Next Week
<List the in-progress tasks that should continue, any blockers to resolve, and any new work the user mentioned. Do not speculate about priorities beyond what the data shows.>
```

For the Highlights section: each bullet should state a concrete outcome or deliverable, not a process step. Use this pattern: "<What was delivered/decided> — <why it matters or what it unblocks>". If a task is still in progress, it is not a highlight unless it hit a significant milestone.

### Step 4: Save the review

Write the review to:
```
.workflow_artifacts/memory/weekly/<YYYY-WNN>.md
```

Where `WNN` is the ISO week number (e.g., `2026-W12`). Create the `.workflow_artifacts/memory/weekly/` directory if it doesn't exist.

### Step 5: Present to the user

Display the review and ask:

> "Anything to add or correct? Any wins or frustrations I missed?"

If the user adds context, update the review file.

Then ask:

> "Want me to capture any lessons from this week?"

If yes, append to `.workflow_artifacts/memory/lessons-learned.md`.

## Handling sparse data

Not every day will have a daily cache (maybe the user didn't run `/end_of_day` every day). That's fine — fill gaps from:

1. Session files for that date
2. Git history for that date
3. Task folder modification timestamps

If there's very little data for the week, say so honestly. Don't inflate thin activity into a long report. A short week gets a short review.

## Handling multi-week tasks

Some tasks span multiple weeks. For in-progress items that started before this week:
- Note when they started
- Describe only this week's progress, not the full history
- Reference previous weekly reviews if they exist

## Important behaviors

- **Lead with outcomes, not activity.** "Shipped payment retry logic — reduces failed transactions by handling Stripe timeouts" beats "Modified 14 files across 3 services."
- **Be honest about pace.** If a task is taking longer than expected, say so. This helps the user calibrate.
- **Keep it scannable.** This review might be shared with a manager or team. Use tables, bullet points, and clear headers. No walls of text.
- **Connect related work factually.** If tasks are related, note the observable connection (e.g., "Task B was created as a follow-up to Task A"). Do not infer intent, mood, or momentum. When data is sparse, keep the review short rather than padding with interpretation.
- **Don't fabricate.** If you don't have data for a day, say "no recorded activity" rather than guessing.
