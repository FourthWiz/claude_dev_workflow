# Development Workflow — Quickstart

## Your commands

| Command | What it does |
|---------|-------------|
| `/init_workflow` | One-time project bootstrap — creates .workflow_artifacts/, configures permissions, runs /discover |
| `/discover` | Scans all repos, maps architecture and dependencies |
| `/architect` | Designs solution architecture for a feature/change; runs architecture critic + up to 3 revision rounds before returning |
| `/thorough_plan` | Creates detailed implementation plan (with critic review) |
| `/implement` | Writes code from the plan (explicit command only) |
| `/review` | Verifies implementation against the plan |
| `/end_of_task` | Pushes branch, captures lessons (explicit command only) |
| `/rollback` | Safely undoes implementation work |
| `/gate` | Quality checkpoint (runs automatically between phases) |
| `/start_of_day` | Morning briefing — restores context |
| `/end_of_day` | Saves session state, promotes captured insights |
| `/weekly_review` | Aggregates the week's progress into a structured review |
| `/capture_insight` | Logs a pattern or gotcha to the daily scratchpad |
| `/run` | End-to-end pipeline: discover → architect → plan → implement → review → end_of_task |
| `/cost_snapshot` | Shows today's cost, project lifetime cost, and per-task breakdown |
| `/triage` | Suggests which skill fits your request; type the command to confirm |

## Typical flows

**Large feature:**
`/discover` → `/architect` → `/thorough_plan` → `/implement` → `/review` → `/end_of_task`

**Bug fix:**
`/plan` → `/implement` → `/review` → `/end_of_task`

**Starting your day:**
`/start_of_day`

**Ending your day:**
`/end_of_day`

## Key rules

1. **`/implement` and `/end_of_task` never run automatically.** You must type them.
2. **Quality gates run between every phase.** Claude stops and asks for your approval.
3. **Each heavy command works best in its own chat session.** Context windows fill up — the file artifacts are the shared memory.
4. **`/end_of_task` pushes the branch only.** Create your PR separately when ready.
5. **Lessons accumulate.** The more you use the workflow, the smarter it gets about your codebase.
6. **`/architect` now auto-runs a critic pass.** Expect 1–4 additional minutes and slightly higher cost per `/architect` run (roughly +$1 to +$4).

## Knowledge cache

The workflow maintains a structured summary cache of your code under `.workflow_artifacts/cache/`, so subsequent runs of `/plan`, `/critic`, `/implement`, and `/review` don't re-read unchanged files from scratch.

- `/discover` populates the cache. `/implement` updates entries for files it modifies. Other skills read from it; none require it to exist.
- Safe to delete at any time — skills fall back to reading source directly, and the next `/discover` rebuilds the cache.
- Benefits on larger projects: faster `/architect` runs, reduced re-reads across planning rounds, lower token cost per lifecycle.

## Files

- `~/.claude/CLAUDE.md` — shared rules all skills follow (user-level)
- `.workflow_artifacts/` — all workflow artifacts: memory, task plans, session state (gitignored)
- `.workflow_artifacts/cache/` — auto-maintained code summary cache (knowledge cache)
- `~/.claude/skills/` — all workflow skill definitions (user-level)
- `Workflow-User-Guide.html` — detailed interactive guide with scenarios

## First time?

Open `Workflow-User-Guide.html` in your browser for a full walkthrough with example conversations.
