# Claude Dev Workflow

A structured, multi-agent development workflow for [Claude Code](https://claude.com/claude-code). It turns Claude into a disciplined engineering partner that plans before coding, critiques its own plans, requires your approval at every stage, and learns from past mistakes.

## Why

Claude Code is powerful but unstructured. Without guardrails, it tends to jump straight to implementation, miss integration issues, and forget lessons from previous tasks. This workflow fixes that by enforcing a deliberate process:

- **Plan before you code** — architecture and detailed planning with critic review
- **Human gates at every transition** — you approve before the next phase starts
- **File-based memory** — context survives across sessions, tasks, and days
- **Accumulated learning** — lessons from past tasks feed into future planning

## How It Works

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Each slash command is a Claude Code skill. Gates are explicit checkpoints where you review and approve. `/implement` and `/end_of_task` never run automatically — you must type them.

Not every task needs every stage. A bug fix might only need `/plan` → `/implement` → `/review` → `/end_of_task`.

## Installation

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (`claude` command available)
- Git
- GitHub CLI (`gh`) — optional, for PR creation

### Quick install

```bash
# From inside your project directory
bash /path/to/dev-workflow/install.sh

# Or targeting a specific project
bash /path/to/dev-workflow/install.sh /path/to/your/project
```

The installer copies workflow files, symlinks skills into `.claude/skills/`, sets up `CLAUDE.md`, and configures `.gitignore`.

### First run

```bash
cd /path/to/your/project
claude
# Type: /init_workflow
```

`/init_workflow` scans your repositories, maps the architecture, and populates the memory files.

### Manual installation

If you prefer not to use the script, see [SETUP.md](dev-workflow/SETUP.md) for step-by-step instructions.

## Skills Reference

The workflow includes 14 skills, each assigned to the optimal Claude model.

### Discovery & Design

| Skill | Model | Purpose |
|-------|-------|---------|
| `/discover` | Opus | Scans all repos, maps architecture, dependencies, and recent git activity into memory files |
| `/architect` | Opus | Deep architectural analysis — explores the codebase, researches best practices, produces a staged design |

### Planning

| Skill | Model | Purpose |
|-------|-------|---------|
| `/plan` | Opus | Creates a detailed, implementation-ready plan with tasks, integration analysis, and risk assessment |
| `/critic` | Opus | Reviews the plan against actual code in a fresh session — finds gaps, risks, and integration issues |
| `/revise` | Opus | Addresses critic feedback, updates the plan surgically without rewriting what's already good |
| `/thorough_plan` | Opus | Orchestrates the full plan → critic → revise loop (up to 5 rounds) until convergence |

### Implementation & Review

| Skill | Model | Purpose |
|-------|-------|---------|
| `/implement` | Sonnet | Executes tasks from the plan — writes code and tests. **Requires explicit user command** |
| `/review` | Opus | Post-implementation deep review — verifies code matches the plan, checks quality and safety |
| `/gate` | Sonnet | Automated quality checkpoint between phases — runs checks, then stops for your approval |

### Task Lifecycle

| Skill | Model | Purpose |
|-------|-------|---------|
| `/end_of_task` | Sonnet | Finalizes accepted work — commits, pushes branch, archives artifacts, captures lessons. **Requires explicit user command** |
| `/rollback` | Sonnet | Safely undoes implementation work — maps commits to plan tasks, shows impact before acting |

### Session Management

| Skill | Model | Purpose |
|-------|-------|---------|
| `/start_of_day` | Sonnet | Morning briefing — restores context from daily cache, checks git state, shows what needs attention |
| `/end_of_day` | Sonnet | Saves session state, consolidates unfinished work into daily cache, prompts for lessons |
| `/init_workflow` | Opus | One-time project bootstrap — creates directory structure, runs `/discover`, generates guides |

## Project Structure

After installation, your project looks like this:

```
your-project/
├── .claude/skills/              ← symlinks to workflow skills
├── CLAUDE.md                    ← references dev-workflow rules
├── dev-workflow/
│   ├── CLAUDE.md                ← shared rules all skills follow
│   ├── QUICKSTART.md            ← command reference card
│   ├── SETUP.md                 ← installation guide
│   ├── Workflow-User-Guide.html ← interactive walkthrough
│   ├── install.sh               ← installer script
│   ├── memory/
│   │   ├── sessions/            ← per-session state files
│   │   ├── daily/               ← daily rollups from /end_of_day
│   │   ├── repos-inventory.md   ← populated by /discover
│   │   ├── architecture-overview.md
│   │   ├── dependencies-map.md
│   │   ├── git-log.md           ← recent commits with rationale
│   │   ├── lessons-learned.md   ← accumulated insights
│   │   └── workflow-rules.md    ← workflow memory for Claude
│   └── skills/
│       └── <14 skill directories, each with SKILL.md>
├── service-a/                   ← your repos (multi-repo layout)
├── service-b/
└── frontend/
```

## Feature → Task Hierarchy

Work is organized hierarchically. Large work items are **features** containing multiple **tasks**:

```
your-project/
├── auth-refactor/                   ← feature (in progress)
│   ├── architecture.md              ← feature-level architecture
│   ├── add-jwt-validation/          ← active task
│   │   ├── current-plan.md
│   │   ├── critic-response-1.md
│   │   └── review-1.md
│   └── implemented/                 ← completed tasks
│       └── remove-legacy-sessions/
├── implemented/                     ← completed features & standalone tasks
│   └── fix-login-redirect/
└── dev-workflow/
```

- When a **task** is finalized via `/end_of_task`, its artifact folder moves to `<feature>/implemented/`
- When all tasks in a **feature** are complete, the feature folder moves to `<project>/implemented/`
- **Standalone tasks** (not part of a feature) move directly to `<project>/implemented/`

This keeps the project root clean — only active work is visible.

## Workflow Details

### The Planning Loop

`/thorough_plan` orchestrates a convergence loop:

1. `/plan` creates `current-plan.md` with concrete, implementable tasks
2. `/critic` reviews the plan in a **fresh session** (unbiased) against the actual codebase
3. If issues found → `/revise` addresses them → back to step 2
4. Loop repeats up to 5 rounds until the critic finds no critical or major issues
5. The workflow **stops** — you must explicitly type `/implement`

The critic always reads real code, not just the plan. This catches mismatches between what the plan assumes and what actually exists.

### Gates

Every phase transition goes through `/gate`:

- Runs automated checks appropriate to the phase (lint, typecheck, tests, plan completeness)
- Presents a clear pass/fail summary
- **Always stops for your explicit approval** — never auto-proceeds

### Session Independence

Each skill is designed to run in its own chat session. When context windows fill up (expected for heavy work), start a new session. The file-based artifacts are the shared memory:

- `current-plan.md`, `architecture.md`, `critic-response-N.md` — planning artifacts
- `memory/sessions/<date>-<task>.md` — session state for handoff
- `memory/daily/<date>.md` — daily rollups
- `memory/lessons-learned.md` — institutional knowledge

Every skill self-bootstraps by reading these files at startup. You never need to re-explain context.

### Lessons Learned

The workflow accumulates knowledge over time:

- `/plan` and `/critic` read `lessons-learned.md` at the start of every session
- `/end_of_task` and `/end_of_day` prompt you for new lessons
- Auto-captured when: critic-revise loops run 3+ rounds, reviews request changes, or rollbacks happen
- Entries are concise — what happened, the reusable takeaway, which skills should pay attention

## Typical Flows

### Large feature

```
/discover          → scan repos (if not already done)
/architect         → design the architecture
  /gate            → review architecture, approve
/thorough_plan     → plan → critic → revise loop
  /gate            → review plan, approve
/implement         → write code and tests
  /gate            → verify tests, lint, no secrets
/review            → deep code review
  /gate            → review verdict, approve
/end_of_task       → commit, push, archive, capture lessons
```

### Bug fix

```
/plan              → quick plan (skip architect)
/implement         → fix the bug
/review            → verify the fix
/end_of_task       → ship it
```

### Daily routine

```
/start_of_day      → morning briefing: what's in progress, what needs attention
... work ...
/end_of_day        → save state, consolidate unfinished work, capture lessons
```

## Key Principles

1. **Explicit human control** — `/implement` and `/end_of_task` never auto-run. Gates require your approval at every transition.
2. **Integration safety** — every planning and review skill analyzes integration points, failure modes, backward compatibility, and data consistency.
3. **De-risking** — identify unknowns early, propose spikes/POCs, use feature flags, plan rollbacks.
4. **File-based memory** — context survives across sessions and days. No reliance on chat history.
5. **Learning from mistakes** — lessons-learned accumulates and feeds back into planning.
6. **Clean git history** — conventional commits, thorough PR descriptions with risk assessment.

## Updating

Re-run the installer to update skills and rules. Your `memory/` directory is always preserved:

```bash
bash /path/to/new/dev-workflow/install.sh /path/to/your/project
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Skills not recognized | Check symlinks: `ls -la .claude/skills/` should point into `dev-workflow/skills/` |
| Claude ignores workflow rules | Verify root `CLAUDE.md` references `dev-workflow/CLAUDE.md` |
| `/discover` finds nothing | Repos must be git repositories (`.git/` folder) inside the project root |
| Context filling up mid-task | Normal — start a new session. File artifacts carry state between sessions |
| Gate blocks unexpectedly | Read the failure output. Fix the issue, then re-run `/gate` |

## License

MIT
