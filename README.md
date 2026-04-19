# Claude Dev Workflow

A structured, multi-agent development workflow for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It turns Claude into a disciplined engineering partner with planning, architecture review, quality gates, and institutional memory.

## How It Works

The workflow breaks complex development tasks into discrete phases, each handled by a specialized skill running on the right model for the job. Quality gates between every phase require your explicit approval before proceeding.

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

**You stay in control.** `/implement` and `/end_of_task` never run automatically — you explicitly decide when to write code and when to ship.

## Task Profiles

Not every task needs every phase. `/thorough_plan` auto-triages tasks into three profiles:

| Profile | When | Planning | Critic loop | Typical cost |
|---------|------|----------|-------------|-------------|
| **Small** | 1–3 files, single module, no integration risk | Single `/plan` pass | Skipped | ~$2.49 |
| **Medium** | Multiple files, 1–2 modules, some integration | `/plan` + critic loop (Sonnet revise) | Up to 4 rounds | ~$2.99–$4.00 |
| **Large** | Cross-service, high risk, data migrations | `/plan` + critic loop (all Opus) | Up to 5 rounds | ~$4.65+ |

Override with a prefix: `small: add health endpoint`, `large: rewrite auth layer`. When in doubt, Medium is the default.

`/architect` is a separate, optional phase you run before `/thorough_plan` when the task needs system-level design (typically Large tasks). Small and Medium tasks usually go straight to `/thorough_plan`.

## Skills

20 skills organized by workflow phase:

### Planning & Design

| Skill | Purpose | Model |
|-------|---------|-------|
| `/init_workflow` | Bootstrap the workflow in a new project | Opus |
| `/discover` | Scan repos, map architecture and dependencies | Opus |
| `/architect` | Design solution architecture with parallel repo scanning | Opus |
| `/thorough_plan` | Orchestrate plan→critic→revise loop (auto-triages task size) | Opus |
| `/plan` | Generate detailed implementation plan | Opus |
| `/critic` | Review plan for gaps, risks, and integration issues | Opus |
| `/revise` | Address critic feedback (strict/Large mode) | Opus |
| `/revise-fast` | Address critic feedback (normal/Medium mode) | Sonnet |

### Execution & Review

| Skill | Purpose | Model |
|-------|---------|-------|
| `/implement` | Write code and tests from the plan | Sonnet |
| `/review` | Verify implementation against the plan | Opus |
| `/gate` | Quality checkpoint between phases | Sonnet |
| `/rollback` | Safely undo implementation work | Sonnet |
| `/end_of_task` | Commit, push branch, capture lessons | Sonnet |
| `/run` | End-to-end pipeline orchestrator (discover → end_of_task) | Opus |

### Session Lifecycle

| Skill | Purpose | Model |
|-------|---------|-------|
| `/start_of_day` | Restore context, check git state | Haiku |
| `/end_of_day` | Save session state, consolidate work | Haiku |
| `/weekly_review` | Aggregate week's progress into a review | Haiku |
| `/capture_insight` | Log a pattern or gotcha to the daily scratchpad | Haiku |
| `/cost_snapshot` | Live cost summary: today, lifetime, per-task | Haiku |
| `/triage` | Route a natural-language prompt to the right workflow skill | Haiku |

### Model Strategy

- **Opus** — planning, architecture, review, critic. Tasks where reasoning depth matters.
- **Sonnet** — implementation, gates, rollback, revise-fast. The plan already defines what to do; Sonnet executes efficiently.
- **Haiku** — session state, daily/weekly summaries, insight capture. Structured template work that doesn't need heavy reasoning.

## Installation

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- Git
- GitHub CLI (`gh`) — optional, for PR creation

### Step 1 — Clone and install (once per machine)

```bash
git clone https://github.com/FourthWiz/claude_dev_workflow.git
bash claude_dev_workflow/dev-workflow/install.sh
```

This is a one-time user-level setup that:
1. Copies all 20 skills to `~/.claude/skills/` — available in every project
2. Writes workflow rules to `~/.claude/CLAUDE.md` — auto-loaded by Claude Code everywhere

Re-running is safe — it updates skills and rules idempotently.

### Step 2 — Scaffold each project

```bash
cd /path/to/your/project
claude
```

Then type:
```
/init_workflow
```

This handles all project-level setup:
- Creates `.workflow_artifacts/` at the project root (gitignored) with memory, sessions, daily, weekly dirs and template files
- Configures `.claude/settings.json` permissions (allows reads/searches, denies destructive ops)
- Runs `/discover` to scan your repos and populate memory
- Generates a quickstart reference

## Typical Flows

**Large feature:**
```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

**Medium feature:**
```
/thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

**Small task / bug fix:**
```
/thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```
(Auto-triaged as Small — single-pass plan, no critic loop)

**Quick fix (skip planning):**
```
/implement → /review → /end_of_task
```

**Daily routine:**
```
/start_of_day    # morning — restores context from yesterday
... work ...
/end_of_day      # evening — saves state, promotes insights
```

## Key Concepts

### Quality Gates

Gates run between every phase. They perform automated checks (tests, lint, no debug code, no secrets) and require your explicit approval before proceeding. Gate intensity scales with task profile — smoke checks for Small, full checks for Large.

### Session Independence

Each skill is designed to work in its own chat session. Context windows fill up — this is expected. File-based artifacts (`current-plan.md`, `architecture.md`, `critic-response-N.md`, session state) are the shared memory between sessions. Start a fresh session for each heavy skill; short flows can share a session.

### Three-Tier Memory

The workflow accumulates knowledge at three levels:

- **Tier 1 — Daily scratchpad** (`.workflow_artifacts/memory/daily/insights-<date>.md`): Claude writes here automatically during task work — patterns, gotchas, decision rationale. Use `/capture_insight` to log something explicitly.
- **Tier 2 — Lessons learned** (`.workflow_artifacts/memory/lessons-learned.md`): Promoted from Tier 1 at `/end_of_day` with your confirmation. Planning and review skills read this to avoid repeating past mistakes.
- **Tier 3 — Workflow suggestions** (`.workflow_artifacts/memory/workflow-suggestions.md`): Insights about the workflow itself. Surfaced at `/end_of_day` for you to apply to the workflow repo manually.

### Plan-Critic-Revise Loop

`/thorough_plan` orchestrates a convergence loop:
1. `/plan` (Opus) creates the initial plan
2. `/critic` (Opus) reviews it against the actual codebase
3. `/revise` or `/revise-fast` addresses feedback
4. Repeat until the critic passes or the round limit is reached

Medium tasks use Sonnet for revision (up to 4 rounds). Large tasks use Opus throughout (up to 5 rounds). Small tasks skip the loop entirely.

### Task Subfolder Convention

All planning artifacts live under `.workflow_artifacts/` (gitignored, hidden at project root):
```
your-project/.workflow_artifacts/auth-refactor/          # active task
your-project/.workflow_artifacts/auth-refactor/current-plan.md
your-project/.workflow_artifacts/auth-refactor/critic-response-1.md
your-project/.workflow_artifacts/auth-refactor/review-1.md
```

When finalized via `/end_of_task`, the folder moves to `.workflow_artifacts/finalized/`:
```
your-project/.workflow_artifacts/finalized/auth-refactor/
```

## Project Structure After Install

```
~/.claude/                       ← user-level (shared across all projects)
├── CLAUDE.md                    ← workflow rules (auto-loaded everywhere)
└── skills/                      ← all 20 workflow skills
    ├── init_workflow/SKILL.md
    ├── discover/SKILL.md
    ├── architect/SKILL.md
    ├── thorough_plan/SKILL.md
    ├── plan/SKILL.md
    ├── critic/SKILL.md
    ├── revise/SKILL.md
    ├── revise-fast/SKILL.md
    ├── gate/SKILL.md
    ├── implement/SKILL.md
    ├── review/SKILL.md
    ├── rollback/SKILL.md
    ├── end_of_task/SKILL.md
    ├── run/SKILL.md
    ├── start_of_day/SKILL.md
    ├── end_of_day/SKILL.md
    ├── weekly_review/SKILL.md
    ├── capture_insight/SKILL.md
    ├── cost_snapshot/SKILL.md
    └── triage/SKILL.md

your-project/                    ← any project where you ran /init_workflow
├── .claude/
│   └── settings.json            ← project permissions
├── .workflow_artifacts/         ← all workflow artifacts (gitignored)
│   ├── memory/                  ← project memory
│   │   ├── sessions/            ← per-session task state
│   │   ├── daily/               ← daily insights scratchpads
│   │   ├── weekly/              ← weekly reviews
│   │   ├── lessons-learned.md   ← accumulated project insights
│   │   ├── workflow-suggestions.md
│   │   ├── repos-inventory.md   ← populated by /discover
│   │   ├── architecture-overview.md
│   │   └── dependencies-map.md
│   ├── my-feature/              ← active task artifacts
│   │   ├── current-plan.md
│   │   └── critic-response-1.md
│   └── finalized/               ← completed tasks (archived by /end_of_task)
├── service-a/                   ← your repos (clean root!)
├── service-b/
└── frontend/
```

## Scenarios

### New machine — first time setup
```bash
git clone https://github.com/FourthWiz/claude_dev_workflow.git
bash claude_dev_workflow/dev-workflow/install.sh
```
Then for each project: `cd project && claude` → `/init_workflow`

### Update the workflow
```bash
cd claude_dev_workflow && git pull
bash dev-workflow/install.sh
```
Skills and `~/.claude/CLAUDE.md` are updated. Project `.workflow_artifacts/` is never touched.

> **Important:** Always re-run `bash install.sh` after pulling updates. Without this step, Claude's global `~/.claude/CLAUDE.md` won't reflect path changes and will conflict with the updated skill files.

### Team member joining
Same as new machine. Clone the workflow repo, run `install.sh`. Each project's `.workflow_artifacts/` is local and gitignored. `/init_workflow` can re-scaffold any project that's missing its structure.

### Legacy project (old layout)
Run `/init_workflow` in the project. It detects old layouts (`memory/` at root, task folders at root, `finalized/` at root, or the oldest `dev-workflow/memory/` layout) and offers to migrate everything into `.workflow_artifacts/` with your confirmation.

## Documentation

- [SETUP.md](dev-workflow/SETUP.md) — detailed setup guide
- [QUICKSTART.md](dev-workflow/QUICKSTART.md) — quick command reference
- [Workflow-User-Guide.html](dev-workflow/Workflow-User-Guide.html) — interactive walkthrough with example conversations
- [CLAUDE.md](dev-workflow/CLAUDE.md) — full shared rules (the contract all skills follow)

## License

MIT
