# Development Workflow — Shared Rules

This file defines the common rules and behaviors shared across all development workflow skills: `/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan` (orchestrator), `/gate`, `/implement`, `/review`, `/rollback`, `/end_of_task`, `/end_of_day`, and `/start_of_day`.

## Project structure

This workspace uses a multi-repo layout. Multiple repositories are cloned side-by-side in the project folder. When exploring the codebase, scan all directories at the root level to discover all repos/services.

## Task subfolder convention

### Feature → Task hierarchy

Large work is organized as **features** containing **tasks**. Each feature gets a top-level folder, and each task within it gets a subfolder:

```
<project-folder>/<feature-name>/
├── architecture.md              ← feature-level architecture
├── <task-1>/
│   ├── current-plan.md
│   ├── critic-response-1.md
│   ├── review-1.md
│   └── ...
├── <task-2>/
│   └── ...
└── implemented/                 ← completed tasks move here
    ├── <task-1>/
    └── ...
```

For standalone tasks (no parent feature), the structure is flat:
```
<project-folder>/<task-name>/
```

### Archiving completed work

When a **task** within a feature is finalized (`/end_of_task`), its artifact folder moves to `<feature-folder>/implemented/`.

When an entire **feature** is complete (all tasks done), the feature folder moves to `<project-folder>/implemented/`.

```
<project-folder>/
├── <active-feature>/            ← in-progress feature
│   ├── <active-task>/
│   └── implemented/
│       └── <done-task>/
├── <active-standalone-task>/    ← standalone task
└── implemented/                 ← completed features and standalone tasks
    ├── <done-feature>/
    └── <done-standalone-task>/
```

This keeps the project root clean — only active work is visible at the top level.

### Naming

Names are descriptive, kebab-case, derived from the description (e.g., `auth-refactor`, `payment-v2-migration`, `api-rate-limiting`). Ask the user for a name when it's not obvious from context.

When running parallel tasks, each gets its own subfolder. Never mix artifacts from different tasks in the same folder.

## Workflow sequence

The intended flow is:

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Each stage feeds into the next, with `/gate` checkpoints requiring explicit human approval:
- `/init_workflow` bootstraps the entire workflow in a new project. Creates directory structure, copies skills, runs `/discover`, generates quickstart guide. Run once per project.
- `/discover` scans all repos and saves inventory, architecture overview, and dependency map to `memory/`. Run once on setup, re-run when repos change.
- `/architect` produces `architecture.md` with stages decomposed for planning (uses `/discover` output as baseline context)
- **GATE** — user reviews architecture, explicitly approves
- `/thorough_plan` orchestrates the plan→critic→revise convergence loop:
  - `/plan` produces the initial `current-plan.md` with implementable tasks
  - `/critic` (fresh session) reviews plan against actual codebase → `critic-response-N.md`
  - `/revise` addresses critic feedback → updates `current-plan.md`
  - Loop repeats up to 5 rounds until convergence
- **GATE** — automated checks (plan completeness, risk coverage), user reviews plan, explicitly approves
- `/implement` executes tasks from the converged plan, writing code and tests
- **GATE** — automated checks (tests, lint, typecheck, no debug code, no secrets), user reviews
- `/review` verifies implementation against the plan, checking quality and safety
- **GATE** — review verdict is APPROVED, tests pass, no conflicts, user approves
- `/end_of_task` — user explicitly accepts the work. Commits remaining changes, pushes branch to remote, prompts for lessons learned, marks task complete. Does NOT create a PR — that's a separate explicit action.
- `/rollback` is available at any point to safely undo implementation work

Not every task needs every stage. Small, well-understood changes can skip `/architect` and go straight to `/thorough_plan`. Bug fixes might only need `/implement` + `/review`. But gates ALWAYS run between phases.

**CRITICAL RULE: `/implement` and `/end_of_task` require explicit user commands.** No skill may auto-invoke either. After `/thorough_plan` converges, the workflow STOPS and waits for `/implement`. After `/review` approves and the gate passes, the workflow STOPS and waits for `/end_of_task`. The user must consciously decide to start writing code AND to ship it.

Session lifecycle:
- `/start_of_day` — restores context from daily cache and checks git state. Run at the beginning of a work session.
- `/end_of_day` — saves session state and consolidates unfinished work into a daily cache. Run when wrapping up.

Multiple sessions can run in a day (parallel tasks). Each session writes its own state to `memory/sessions/`. `/end_of_day` rolls unfinished sessions into `memory/daily/<date>.md`.

## Session independence

**Each skill is designed to run in its own chat session.** Context windows fill up — this is expected. The file-based artifacts (`current-plan.md`, `critic-response-N.md`, session state, `architecture.md`, etc.) ARE the shared memory between sessions.

**Recommended session pattern:**
- One command per session for heavy work (`/architect`, `/thorough_plan`, `/implement`, `/review`)
- Short flows can share a session (`/plan` → `/implement` → `/review` for a small bug fix)
- Use your judgment: when context feels heavy, close and start fresh

**Every skill must be self-bootstrapping.** When a skill starts in a fresh session, it must:
1. Read `CLAUDE.md` for shared rules
2. Read `memory/lessons-learned.md` for past insights (planning/review skills)
3. Read the task subfolder artifacts it needs (`current-plan.md`, `architecture.md`, `critic-response-N.md`, etc.)
4. Read `memory/sessions/<latest>` for current session state if resuming
5. Read actual source code — never rely on a previous session's memory of the code

The user should never have to re-explain context that's already in the files. If a skill can't find what it needs, it asks the user — but the default is to read from disk.

**When closing a session:** any skill that did meaningful work should update the session state file (`memory/sessions/<date>-<task-name>.md`) before the session ends. This is the handoff to the next session.

## Common rules for all skills

### Integration analysis

Every skill that touches planning or review must analyze integrations. When a change affects how services, modules, or systems interact:

1. **Map the integration points** — identify every boundary crossed (HTTP calls, message queues, shared databases, file systems, event buses)
2. **Assess failure modes** — what happens when each integration fails? Timeout? Error? Stale data?
3. **Check backward compatibility** — can this change deploy independently, or does it require coordinated deployment?
4. **Verify contracts** — request/response formats, error codes, authentication headers
5. **Consider data consistency** — especially across multiple stores or services

### Risk de-risking

All planning and review work must actively de-risk:

- Identify unknowns and propose spikes/POCs to resolve them before full implementation
- Prefer feature flags for risky changes so they can be toggled without a deploy
- Plan for parallel running of old and new code paths during migration
- Ensure monitoring and alerting exist (or are planned) for new integration points
- Define rollback plans for every significant change

### Git workflow

#### Commit messages

When the user asks to commit changes, write clear, conventional commit messages:

```
<type>(<scope>): <short description>

<body — what changed and why, not what files were edited>

<footer — references, breaking changes>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`

The body should explain the "why" — the motivation for the change, not a list of files modified (the diff shows that).

#### Pull requests

PR creation is always an explicit, separate user action — never auto-created by `/end_of_task`. When the user asks to create a PR, before doing so:

1. **Run all tests** for the affected code areas
2. **Check for untested new code** — if tests are missing, flag it. If the plan specified tests, write them before the PR.
3. **Self-review the diff** — read `git diff <base>...HEAD` completely. Look for:
   - Debug code, console.logs, commented-out code
   - Missing error handling
   - Hardcoded values that should be configurable
   - Security issues (exposed secrets, injection vulnerabilities)
   - Accidental file inclusions (.env, node_modules, etc.)
4. **Call the planner for tests if needed** — if significant new code lacks tests and writing them is non-trivial, escalate to `/thorough_plan` to plan the test strategy before writing them

PR description format:
```markdown
## Summary
<What this PR does in 2-3 sentences>

## Changes
- <Specific change 1>
- <Specific change 2>

## Testing
- <What was tested and how>
- <How to run the tests>

## Integration impact
- <Affected services/components>
- <Deployment order if coordination needed>

## Risk assessment
- <What could break>
- <How to verify>
- <Rollback plan>

## Related
- Plan: <task-name>/current-plan.md
- Architecture: <task-name>/architecture.md (if applicable)
- Review: <task-name>/review-N.md (if applicable)
```

### Web research

When answering complex questions or designing systems:
- Search for best practices with specific technologies involved
- Check official documentation for APIs and frameworks
- Look for known issues, migration guides, or deprecation notices
- Find examples of similar architectures in open source

Don't guess about external system behavior — verify it.

### Lessons learned

The file `memory/lessons-learned.md` accumulates insights from completed tasks. It captures what surprised us, what went wrong, and what to do differently next time.

**Reading:** Every planning skill (`/plan`, `/critic`, `/architect`) should read `lessons-learned.md` at the start to avoid repeating known mistakes.

**Writing:** Append a new entry after each task reaches merge (or after a rollback, or when the user shares a lesson). Format:

```markdown
## <date> — <task-name>
**What happened:** <the surprise, failure, or insight>
**Lesson:** <the reusable takeaway>
**Applies to:** <which skills should pay attention — /plan, /critic, /implement, etc.>
```

Keep entries concise — 2-4 lines each. This file grows over time and becomes the team's institutional memory.

### Session state tracking

Every skill that does meaningful work (architect, plan, critic, revise, implement, review) should update the session state file as it progresses. Write or update:

```
memory/sessions/<date>-<task-name>.md
```

At minimum, update the `Current stage`, `Completed in this session`, and `Unfinished work` sections as tasks complete. This way, if the session is interrupted, `/end_of_day` (or the next `/start_of_day`) has accurate state to work from.

Don't obsess over keeping this perfectly up to date on every micro-step — update it at natural checkpoints (after completing a plan, finishing a critic round, implementing a task, etc.).

### Asking questions

It's always better to ask than to assume. Use the AskUserQuestion tool when:
- The requirement is ambiguous
- There are multiple valid approaches with different tradeoffs
- You need domain-specific knowledge the code doesn't reveal
- The decision has significant downstream impact

Keep questions specific and pointed. Don't ask "what do you want?" — ask "should the retry logic use exponential backoff (safer, slower recovery) or fixed intervals (simpler, faster recovery)?"

## Model assignments

| Skill | Model | Reasoning |
|-------|-------|-----------|
| /discover | Opus | Cross-repo scanning, understanding how services connect |
| /architect | Opus | Deep exploration, complex reasoning, cross-repo analysis |
| /plan | Opus | Detailed planning requires strong reasoning |
| /critic | Opus | Finding real issues requires deep understanding |
| /revise | Opus | Addressing critic feedback requires strong reasoning |
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop |
| /implement | Sonnet | Efficient code generation, plan already defines what to do |
| /review | Opus | Thorough analysis, integration safety, risk assessment |
| /gate | Sonnet | Automated checks and human approval checkpoint |
| /rollback | Sonnet | Safe undo of implementation phases |
| /end_of_task | Sonnet | Commit, push branch, lessons, mark complete |
| /end_of_day | Sonnet | Session state capture and daily cache consolidation |
| /init_workflow | Opus | Project bootstrap, /discover invocation, structure creation |
| /start_of_day | Sonnet | Context restoration and git state reconciliation |
