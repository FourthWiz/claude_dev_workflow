# Development Workflow Memory

## Workflow commands

Ivan uses a structured development workflow:

- `/init_workflow` — one-time project bootstrap (Opus). Creates `.workflow_artifacts/` structure at project root (gitignored), configures `.claude/settings.json`, runs /discover, generates quickstart guide. (Skills are installed user-level via `bash install.sh`, not per-project.)
- `/discover` — scans all repos (Opus). Produces inventory, architecture, dependencies, git-log in `.workflow_artifacts/memory/`.
- `/architect` — deep exploration and architectural design (Opus). Produces architecture.md.
- `/thorough_plan` — orchestrator (Opus) for plan→critic→revise loop (up to 5 rounds):
  - `/plan` — creates initial plan (Opus). Reads lessons-learned.md.
  - `/critic` — reviews plan in FRESH session (Opus). Reads lessons-learned.md + actual code.
  - `/revise` — addresses critic feedback (Opus). Updates current-plan.md.
- `/gate` — quality checkpoint (Sonnet). Runs automated checks, STOPS for human approval. Runs between every phase.
- `/implement` — code implementation (Sonnet). **REQUIRES EXPLICIT USER COMMAND — never auto-invoked.**
- `/review` — post-implementation review (Opus). Checks code vs plan, integration safety, risk.
- `/rollback` — safely undoes implementation work (Sonnet). Maps commits to plan tasks, shows before acting.
- `/end_of_task` — finalizes accepted work (Sonnet). **REQUIRES EXPLICIT USER COMMAND.** Commits, pushes branch to remote (no PR — that's a separate explicit action), prompts for lessons, marks task complete.
- `/end_of_day` — saves session state, consolidates unfinished work, prompts for lessons learned.
- `/start_of_day` — restores context from daily cache, reconciles with git state.

## Workflow sequence

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Small changes can skip `/architect`. Bug fixes may only need `/implement` + `/review`. Gates ALWAYS run. `/implement` and `/end_of_task` ALWAYS require explicit user command.

## Key principles Ivan cares about

1. **Explicit human control** — `/implement` is never auto-invoked. Gates run between every phase. The human decides when to proceed.
2. **Integration safety** — always analyze integration points, failure modes, backward compatibility. Most production issues come from integration failures.
3. **De-risking** — identify unknowns early, use spikes/POCs, feature flags, parallel running, monitoring. Never go into implementation with unresolved uncertainties.
4. **Thorough planning** — plans go through critic-revise cycles. The critic must read actual code, not just the plan.
5. **Tests before PRs** — always verify tests exist for new code before creating a PR. If tests are missing, plan and write them.
6. **Clean git history** — conventional commit messages, clear PR descriptions with risk assessment and rollback plan.
7. **Learning from mistakes** — lessons-learned.md accumulates insights. /plan and /critic read it. /end_of_day prompts for new lessons. Rollbacks and long critic loops auto-generate lessons.

## Project structure

Ivan works with multiple repositories cloned side-by-side in the project folder (multi-repo layout). When exploring, scan all root-level directories.

## Task artifacts

All planning artifacts go in descriptive subfolders under `.workflow_artifacts/`:
```
<project-folder>/.workflow_artifacts/<task-name>/
├── architecture.md
├── current-plan.md
├── critic-response-1.md ... critic-response-N.md
├── review-1.md ... review-N.md
```

Task names are descriptive kebab-case derived from the task (e.g., `auth-refactor`). Ask Ivan for a name when not obvious.

## Session management

Ivan works in multiple sessions per day, sometimes on parallel tasks. The workflow tracks state per session:

```
.workflow_artifacts/
├── memory/
│   ├── sessions/                    ← per-session task progress (date-taskname.md)
│   ├── daily/
│   │   ├── <date>.md                ← daily rollup from /end_of_day
│   │   └── insights-<date>.md       ← Tier 1: daily knowledge scratchpad
│   ├── weekly/                      ← weekly rollup from /weekly_review
│   ├── git-log.md                   ← rolling log of recent commits
│   ├── lessons-learned.md           ← Tier 2: promoted project-level insights
│   ├── workflow-suggestions.md      ← Tier 3: suggestions for improving the workflow
│   ├── repos-inventory.md
│   ├── architecture-overview.md
│   └── dependencies-map.md
├── <task-name>/                     ← active task artifacts
└── finalized/                       ← completed task archives
```

### Three-tier memory system

- **Tier 1 — Daily scratchpad** (`.workflow_artifacts/memory/daily/insights-<date>.md`): Claude writes here freely during task work — patterns, gotchas, decision rationale, surprises. Written without asking the user.
- **Tier 2 — Project long-term** (`.workflow_artifacts/memory/lessons-learned.md`): Promoted from Tier 1 at `/end_of_day` with user confirmation. Read by `/plan` and `/critic` at session start.
- **Tier 3 — Workflow-wide** (`.workflow_artifacts/memory/workflow-suggestions.md`): Insights that belong in the workflow repo itself (not project-specific). Claude surfaces these; the user applies them to the workflow repo manually.

- `/start_of_day` — reads daily cache + git state, presents briefing; checks for un-promoted yesterday insights if `/end_of_day` was skipped
- `/end_of_day` — saves current session, consolidates unfinished sessions into daily cache, promotes Tier 1 insights to Tier 2, surfaces Tier 3 suggestions
- Daily cache only includes unfinished sessions (completed sessions are noted but not carried forward)
- Git-log.md captures commit *logic* (why things changed), not just file lists — rolling ~50 commits across all repos

## Preferences

- Task subfolder names: descriptive kebab-case (ask user when unclear)
- Critic-revise max rounds: 5
- Convergence: critic finds no CRITICAL or MAJOR issues
- Commit format: conventional commits (<type>(<scope>): <description>)
- PR creation: always run tests first, check for missing tests, self-review diff
