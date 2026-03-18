# Development Workflow Memory

## Workflow commands

Ivan uses a structured development workflow:

- `/init_workflow` — one-time project bootstrap (Opus). Creates dev-workflow/ structure, copies skills, runs /discover, generates quickstart guide.
- `/discover` — scans all repos (Opus). Produces inventory, architecture, dependencies, git-log in `memory/`.
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

Large work uses a **feature → task** hierarchy. Each feature has a folder with task subfolders inside:

```
<project-folder>/<feature-name>/
├── architecture.md                  ← feature-level
├── <task-name>/
│   ├── current-plan.md
│   ├── critic-response-1.md ... N
│   └── review-1.md ... N
├── implemented/                     ← completed tasks archived here
│   └── <done-task>/
```

Standalone tasks (no parent feature) use a flat structure: `<project-folder>/<task-name>/`.

### Archiving completed work

- **Task done** → moves to `<feature-folder>/implemented/<task-name>/`
- **Feature done** (all tasks complete) → moves to `<project-folder>/implemented/<feature-name>/`
- **Standalone task done** → moves to `<project-folder>/implemented/<task-name>/`

This keeps only active work visible at the project root.

Task names are descriptive kebab-case derived from the task (e.g., `auth-refactor`). Ask Ivan for a name when not obvious.

## Session management

Ivan works in multiple sessions per day, sometimes on parallel tasks. The workflow tracks state per session:

```
memory/
├── sessions/          ← per-session state (date-taskname.md)
├── daily/             ← daily rollup from /end_of_day
├── git-log.md         ← rolling log of recent commits with logic/rationale
├── lessons-learned.md ← accumulated insights from past tasks (read by /plan, /critic)
├── repos-inventory.md
├── architecture-overview.md
└── dependencies-map.md
```

- `/start_of_day` — reads daily cache + git state, presents briefing
- `/end_of_day` — saves current session, consolidates unfinished sessions into daily cache
- Daily cache only includes unfinished sessions (completed sessions are noted but not carried forward)
- Git-log.md captures commit *logic* (why things changed), not just file lists — rolling ~50 commits across all repos

## Preferences

- Task subfolder names: descriptive kebab-case (ask user when unclear)
- Critic-revise max rounds: 5
- Convergence: critic finds no CRITICAL or MAJOR issues
- Commit format: conventional commits (<type>(<scope>): <description>)
- PR creation: always run tests first, check for missing tests, self-review diff
