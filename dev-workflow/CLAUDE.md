# Development Workflow — Shared Rules

This file defines the common rules and behaviors shared across all development workflow skills: `/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan` (orchestrator), `/run` (end-to-end orchestrator), `/gate`, `/implement`, `/review`, `/rollback`, `/end_of_task`, `/end_of_day`, `/start_of_day`, `/weekly_review`, `/cost_snapshot`, and `/capture_insight`.

## Working Rules

### Git & PR Safety
- **Never push to remote or create PRs outside of `/end_of_task`.** During implementation and review, only commit locally. Push happens as part of `/end_of_task` (which requires `/review` first). PR creation is always a separate explicit user action — never auto-create PRs.
- **Always start each new task on a fresh branch.** Commit current work, switch to main, fetch latest, then create the new branch.

### Communication
- **Keep multi-step workflow progress verbose.** When working through plans, implementations, or multi-round processes, provide status updates at each step. Don't go silent during long operations.

### Dev Workflow
- **Never place stage plans into `.workflow_artifacts/finalized/` until `/end_of_task` is explicitly run.** Plans stay in their working location until the user triggers finalization.

## Project structure

This workspace uses a multi-repo layout. Multiple repositories are cloned side-by-side in the project folder. When exploring the codebase, scan all directories at the root level to discover all repos/services.

## Task subfolder convention

All planning and review artifacts are stored under `.workflow_artifacts/` at the project root:
```
<project-folder>/.workflow_artifacts/<task-name>/
```

Task names are descriptive, kebab-case, derived from the task description (e.g., `auth-refactor`, `payment-v2-migration`, `api-rate-limiting`). Ask the user for a name when it's not obvious from context.

When running parallel tasks, each gets its own subfolder. Never mix artifacts from different tasks in the same folder.

### Archiving completed work

When a task is finalized via `/end_of_task`, its folder is moved into `.workflow_artifacts/finalized/`:

- **Sub-task completed** — moves into `.workflow_artifacts/<parent-feature>/finalized/`:
  ```
  .workflow_artifacts/payment-v2/auth-retry/  →  .workflow_artifacts/payment-v2/finalized/auth-retry/
  ```
- **Entire feature completed** — moves into `.workflow_artifacts/finalized/`:
  ```
  .workflow_artifacts/payment-v2/  →  .workflow_artifacts/finalized/payment-v2/
  ```

This keeps both the project root and `.workflow_artifacts/` clean — only active task folders are visible at the top of `.workflow_artifacts/`. Completed work is preserved in `.workflow_artifacts/finalized/` for reference.

**IMPORTANT: Never move task folders into `.workflow_artifacts/finalized/` during planning or implementation.** Keep them in their working location throughout the entire workflow. The `finalized/` directory is reserved for completed, shipped work only. Artifacts are moved there exclusively when `/end_of_task` is explicitly invoked by the user.

## Workflow sequence

The intended flow depends on the task profile (Small / Medium / Large). `/thorough_plan` is the universal entry point — it triages and routes automatically.

### Full flow (Medium and Large tasks)

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

### Shortcut flow (Small tasks)

```
/thorough_plan (auto-routes to single-pass /plan) → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Small tasks skip `/architect` and the critic loop. `/thorough_plan` detects the Small profile (via `small:` tag or auto-classification) and runs a single `/plan` pass without critic review.

### Automated flow (`/run`)

```
/run → (discover?) → (architect?) → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

`/run` chains all phases automatically, pausing at each GATE for user confirmation. It accepts the same profile tags as `/thorough_plan` (`small:`, `medium:`, `large:`, `strict:`, `max_rounds: N`). Discover is skipped if recent (<7 days) discovery files exist. Architect is skipped for Small tasks. Each phase runs in its own subagent session.

### Task profiles

| Profile | Triggered by | Planning | Critic loop | Gate intensity | Typical cost |
|---------|-------------|----------|-------------|---------------|-------------|
| **Small** | `small:` prefix, or auto-classified + confirmed | Single `/plan` pass (Opus) | Skipped | Smoke → Standard → Full | ~$2.49 |
| **Medium** | `medium:` prefix, auto-classified, or no tag (default) | `/plan` (Opus) + critic loop with Sonnet `/revise-fast` | Up to 4 rounds | Smoke → Standard → Full | ~$2.99–$4.00 |
| **Large** | `large:` or `strict:` prefix | `/plan` (Opus) + critic loop with Opus `/revise` | Up to 5 rounds | Smoke → Full → Full | ~$4.65+ |

**Triage criteria at a glance:**
- **Small** — 1-3 files, single module, no integration risk, well-understood pattern (bug fix, config change, simple endpoint)
- **Medium** — multiple files across 1-2 modules, moderate complexity, some integration points
- **Large** — cross-service/cross-repo, high risk, data migrations, auth changes, significant unknowns

When in doubt, default to Medium. The user can always override with an explicit tag.

Each stage feeds into the next, with `/gate` checkpoints requiring explicit human approval:
- `/init_workflow` bootstraps the workflow in a new project. Creates `.workflow_artifacts/` structure, configures permissions, runs `/discover`, generates quickstart guide. Run once per project. (Skills and rules are installed separately via `bash install.sh`.)
- `/discover` scans all repos and saves inventory, architecture overview, and dependency map to `.workflow_artifacts/memory/`. Run once on setup, re-run when repos change.
- `/architect` produces `architecture.md` with stages decomposed for planning (uses `/discover` output as baseline context)
- **GATE** — user reviews architecture, explicitly approves
- `/thorough_plan` triages the task and routes accordingly:
  - **Small:** runs `/plan` (Opus) as a single pass → produces `current-plan.md` → smoke gate → done
  - **Medium:** runs the plan→critic→revise convergence loop (Opus plan, Sonnet revise, Opus critic, max 4 rounds)
  - **Large:** runs the convergence loop in strict mode (all Opus, max 5 rounds)
  - Override with `max_rounds: N` for any profile (ignored for Small)
- `/run` chains the entire workflow end-to-end: discover (if stale) → architect (if not Small) → thorough_plan → implement → review → end_of_task. Pauses at each gate for user confirmation. Accepts same profile tags as `/thorough_plan`. Use when you want the full pipeline in one command.
- **GATE** — automated checks (plan completeness, risk coverage), user reviews plan, explicitly approves
- `/implement` executes tasks from the converged plan, writing code and tests
- **GATE** — automated checks (scope depends on task profile — Standard for Small/Medium, Full for Large)
- `/review` verifies implementation against the plan, checking quality and safety (always Opus)
- **GATE** — Full checks: review verdict is APPROVED, full test suite passes, no conflicts, user approves
- `/end_of_task` — user explicitly accepts the work. Commits remaining changes, pushes branch to remote, prompts for lessons learned, marks task complete. Does NOT create a PR — that's a separate explicit action.
- `/rollback` is available at any point to safely undo implementation work

Not every task needs every stage. Small tasks typically skip `/architect` entirely. Bug fixes might only need `/implement` + `/review` (bypassing `/thorough_plan` entirely). But gates ALWAYS run between phases.

**CRITICAL RULE: `/implement` and `/end_of_task` require explicit user commands.** No skill may auto-invoke either. After `/thorough_plan` converges, the workflow STOPS and waits for `/implement`. After `/review` approves and the gate passes, the workflow STOPS and waits for `/end_of_task`. The user must consciously decide to start writing code AND to ship it.

**Exception: `/run` orchestrator.** When the user invokes `/run`, they have explicitly requested the full end-to-end pipeline. `/run` may invoke `/implement` and `/end_of_task` on the user's behalf, but still pauses at each gate checkpoint for confirmation before proceeding. The user's `/run` invocation constitutes the conscious decision; the gate confirmations provide the safety checkpoints.

Session lifecycle:
- `/start_of_day` — restores context from daily cache and checks git state. Run at the beginning of a work session.
- `/end_of_day` — saves session state and consolidates unfinished work into a daily cache. Run when wrapping up.
- `/weekly_review` — aggregates the week's progress into a structured review. Run on Friday (or whenever you want a week-level summary). Saves to `.workflow_artifacts/memory/weekly/`.

Multiple sessions can run in a day (parallel tasks). Each session writes its own state to `.workflow_artifacts/memory/sessions/`. `/end_of_day` rolls unfinished sessions into `.workflow_artifacts/memory/daily/<date>.md`.

## Task triage criteria

These criteria guide the auto-classification in `/thorough_plan` and help users choose the right explicit tag.

### Small
- Touches 1-3 closely related files in a single module
- No integration points affected (no API contract changes, no cross-service calls)
- Well-understood pattern: bug fix, config change, add simple endpoint, rename, typo fix
- Failure is localized — affects one feature, easy to detect and revert
- No data model changes, no auth changes, no shared-state modifications

### Medium (default when uncertain)
- Touches multiple files across 1-2 modules or services
- May affect integration points but contracts remain backward-compatible
- Some unknowns but similar work has been done in this codebase before
- Failure affects a subsystem but is contained and recoverable
- Adding a new feature with tests, refactoring a module, adding retry/resilience logic

### Large
- Touches multiple services, repos, or architectural layers
- Affects data consistency, authentication, authorization, or multi-service contracts
- Significant unknowns, new patterns, or involves migration of existing data/systems
- Failure could affect multiple services or all users
- Database migrations, auth overhauls, API versioning, payment flow changes

**Rule: when the classification is ambiguous, choose Medium.** It is the safe default — the critic loop catches issues that a single-pass plan might miss, at a modest cost premium.

## Session independence

**Each skill is designed to run in its own chat session.** Context windows fill up — this is expected. The file-based artifacts (`current-plan.md`, `critic-response-N.md`, session state, `architecture.md`, etc.) ARE the shared memory between sessions.

**Recommended session pattern:**
- One command per session for heavy work (`/architect`, `/thorough_plan`, `/implement`, `/review`)
- **`/run` gets its own session.** It orchestrates subagent sessions for each phase, so it stays lean — but start it fresh so the orchestrator has maximum context for managing the full pipeline.
- **Always run `/end_of_task` in a fresh session** if the current session has been through heavy work. The skill has 8 sequential steps that must all complete — context compaction mid-skill can silently skip steps like archiving.
- Short flows can share a session (`/plan` → `/implement` → `/review` for a small bug fix)
- Use your judgment: when context feels heavy, close and start fresh

**Every skill must be self-bootstrapping.** When a skill starts in a fresh session, it must:
1. Read `CLAUDE.md` for shared rules
2. Read `.workflow_artifacts/memory/lessons-learned.md` for past insights (planning/review skills)
3. Read the task subfolder artifacts it needs (`.workflow_artifacts/<task-name>/current-plan.md`, `architecture.md`, `critic-response-N.md`, etc.)
4. Read `.workflow_artifacts/memory/sessions/<latest>` for current session state if resuming
5. Read actual source code — never rely on a previous session's memory of the code

The user should never have to re-explain context that's already in the files. If a skill can't find what it needs, it asks the user — but the default is to read from disk.

**When closing a session:** any skill that did meaningful work should update the session state file (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`) before the session ends. This is the handoff to the next session.

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

#### Branch hygiene before new tasks

Before starting any new task on a repo, always:

1. Check if the repo is on another branch with uncommitted changes
2. Commit (or stash) those changes first
3. Switch to main/master
4. Fetch and pull to ensure it's up to date
5. Create a new branch for the task

Clean working state before each task avoids mixing unrelated changes and working on stale code. At the start of every implementation task, run `git status` + `git branch` on each affected repo. Handle any dirty state before proceeding. This applies to ALL repos involved, not just the primary one.

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
- Plan: .workflow_artifacts/<task-name>/current-plan.md
- Architecture: .workflow_artifacts/<task-name>/architecture.md (if applicable)
- Review: .workflow_artifacts/<task-name>/review-N.md (if applicable)
```

### Web research

When answering complex questions or designing systems:
- Search for best practices with specific technologies involved
- Check official documentation for APIs and frameworks
- Look for known issues, migration guides, or deprecation notices
- Find examples of similar architectures in open source

Don't guess about external system behavior — verify it.

### Daily insight capture

As you work through any task, watch for patterns, surprises, and friction points worth remembering. When you notice one, write it to the daily insights scratchpad immediately — do not wait for `/end_of_day`:

```
.workflow_artifacts/memory/daily/insights-<YYYY-MM-DD>.md
```

Write an entry when you encounter:
- A gotcha that cost time and would cost time again (e.g., "this API silently ignores malformed requests")
- A non-obvious pattern in this codebase (e.g., "all services use X pattern for Y")
- A decision whose rationale is non-obvious and will be forgotten by tomorrow
- A workflow step that felt wrong or slow (mark `Applies to: workflow` — this becomes a Tier 3 suggestion at end of day)
- Any moment you think "I wish I'd known this earlier in the session"

**Write without asking the user first.** This is your scratchpad. Keep entries short (2-4 sentences). Tag each with `Promote?: yes | maybe | no` based on how reusable it seems across future sessions.

Do NOT use the insights scratchpad for task progress tracking — that belongs in `.workflow_artifacts/memory/sessions/<date>-<task>.md`.

You can also invoke `/capture_insight` explicitly to log something the user calls out mid-task.

### Lessons learned

The file `.workflow_artifacts/memory/lessons-learned.md` accumulates insights from completed tasks. It captures what surprised us, what went wrong, and what to do differently next time.

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

Every skill that does meaningful work (architect, plan, critic, revise, implement, review, run) should update the session state file as it progresses. Write or update:

```
.workflow_artifacts/memory/sessions/<date>-<task-name>.md
```

At minimum, update the `Current stage`, `Completed in this session`, and `Unfinished work` sections as tasks complete. This way, if the session is interrupted, `/end_of_day` (or the next `/start_of_day`) has accurate state to work from.

Don't obsess over keeping this perfectly up to date on every micro-step — update it at natural checkpoints (after completing a plan, finishing a critic round, implementing a task, etc.).

The session state file template includes a `## Cost` section:

```markdown
## Cost
- Session UUID: <UUID obtained from JSONL filename approach — see Cost tracking rules>
- Phase: <phase>
- Recorded in cost ledger: yes/no
```

This is informational — the cost ledger (`.workflow_artifacts/<task-name>/cost-ledger.md`) is the source of truth for per-session costs.

### Cost tracking

Every skill that does meaningful work should record its session to the task's cost ledger at the start of the session. This enables `/end_of_task` to aggregate the total cost of a task across all sessions, including sessions that crashed or were force-closed.

**Step 1: Obtain the session UUID (JSONL filename approach — primary method)**

The Claude Code runtime writes a JSONL file for the active session at `~/.claude/projects/<project-hash>/`. The filename is `<uuid>.jsonl`. Since the active session's JSONL is written to continuously, it is always the most recently modified file:

```bash
# Determine project hash: project folder path with / replaced by -
# Example: /Users/alice/projects/myapp → Users-alice-projects-myapp
ls -t ~/.claude/projects/<project-hash>/*.jsonl 2>/dev/null | head -1
# Extract UUID: strip directory path and .jsonl extension
```

If no `.jsonl` file is found (rare — session hasn't made an API call yet), use `unknown-<ISO-timestamp>` as the UUID. If the `CLAUDE_SESSION_ID` environment variable is set (future Claude Code versions may add this), use it as an alternative — but do not depend on it being present.

**Step 2: Append to the cost ledger**

Append one line to `.workflow_artifacts/<task-name>/cost-ledger.md`:

```
<session-uuid> | <YYYY-MM-DD> | <phase> | <primary-model> | task | <brief note>
```

If the ledger file doesn't exist yet, create it with the header line first:
```
# Cost Ledger — <task-name>
```

**Phase values:** `discover`, `architect`, `plan`, `critic`, `revise`, `implement`, `review`, `gate`, `end-of-task`, `run-orchestrator`, `thorough-plan`, `rollback`, `init-workflow`, `start-of-day`, `end-of-day`, `weekly-review`, `capture-insight`, `ad-hoc`

**Category:** Always write `task`. The user may manually edit the ledger to change a row to `off-topic` if a session drifted from the task. Skills do NOT auto-detect off-topic work.

**The cost ledger is append-only during a task.** Never delete or rewrite rows.

**Conditional skills:** `/discover`, `/gate`, `/start_of_day`, and `/capture_insight` should only record to the cost ledger if a task name is clearly determinable from context (a task folder path or explicit task name was passed). If no task context is active, skip cost recording silently.

### Asking questions

It's always better to ask than to assume. Use the AskUserQuestion tool when:
- The requirement is ambiguous
- There are multiple valid approaches with different tradeoffs
- You need domain-specific knowledge the code doesn't reveal
- The decision has significant downstream impact

Keep questions specific and pointed. Don't ask "what do you want?" — ask "should the retry logic use exponential backoff (safer, slower recovery) or fixed intervals (simpler, faster recovery)?"

### Knowledge cache

The workflow maintains a hierarchical file-based knowledge cache under `.workflow_artifacts/cache/`. This cache provides structured summaries of source code files and modules, enabling skills to navigate the codebase without re-reading unchanged source files.

#### Cache directory structure

````
.workflow_artifacts/cache/
├── _index.md                     ← Root index: repo list, last-updated timestamps
├── _staleness.md                 ← Git HEAD tracking per repo (replaces repo-heads.md)
├── <repo-name>/
│   ├── _index.md                 ← Repo summary: purpose, stack, entry points, key patterns
│   ├── _deps.md                  ← External deps + internal cross-module deps
│   └── <directory>/
│       ├── _index.md             ← Module/directory summary: purpose, exports, patterns
│       └── <file-stem>.md        ← Per-file summary (key files only)
````

#### Cache entry format

Every `_index.md` and `<file-stem>.md` uses this structure:

````markdown
---
path: <relative path from project root to source file/directory>
hash: <git hash of file at time of caching, or HEAD for directories>
updated: <ISO timestamp>
updated_by: <skill that wrote/updated this entry>
tokens: <approximate token count of this cache entry>
---

## Purpose
<1-2 sentences>

## Key Exports
- `name(params)` — description

## Dependencies
- imports from: <internal modules>
- external: <key packages>

## Patterns
- <notable patterns>

## Integration Points
- exposes: <APIs, events, exports>
- consumes: <APIs, events, imports>

## Notes
<gotchas, tech debt, non-obvious details>
````

Sections may be omitted when not applicable (e.g., a config file has no Key Exports).

#### Token budgets

| Entry type | Target tokens | When to create |
|-----------|---------------|---------------|
| Root `_index.md` | 100-200 | Always (one per project) |
| Repo `_index.md` | 200-300 | Always (one per repo) |
| Repo `_deps.md` | 100-200 | Always (one per repo) |
| Module `_index.md` | 150-300 | Directories with 3+ source files |
| File `<stem>.md` | 50-150 | Key files only: entry points, APIs, models, configs, complex logic |

Rule of thumb: source files < 50 lines go into the module `_index.md` instead of getting their own entry. Source files > 500 lines may use up to 200 tokens.

#### Staleness tracking

`_staleness.md` tracks the git HEAD per repo at the time of last cache update:

````markdown
| Repo | HEAD | Updated |
|------|------|---------|
| <repo-name> | <full SHA> | <ISO timestamp> |
````

Skills check staleness by comparing `git rev-parse HEAD` against the stored value. If HEAD differs, `git diff --name-only <cached-head> <current-head>` identifies exactly which files changed. Cache entries for unchanged files remain valid.

#### Behavioral rules

1. **Cache is advisory, not authoritative.** Skills may always read source files directly. A missing or stale cache entry is never an error — the skill just reads from source (current behavior).
2. **Any skill that reads a source file and finds the cache entry stale or missing SHOULD update the cache entry.** This is best-effort, not mandatory.
3. **Cache writes must not block or fail the skill.** If a cache write fails (disk full, permission error), warn and continue.
4. **Skills should load cache entries in deterministic order** (root index, then repo indexes, then module indexes) to maximize prompt cache hits.
5. **`_staleness.md` is the successor to `repo-heads.md`.** Skills that previously read `repo-heads.md` should read `_staleness.md` instead. For backward compatibility, if `_staleness.md` does not exist, fall back to `repo-heads.md`.
6. **Rollback:** Deleting `.workflow_artifacts/cache/` restores pre-cache behavior. No skill should fail if the cache directory is missing.

## Model assignments

| Skill | Model | Reasoning |
|-------|-------|-----------|
| /discover | Opus | Cross-repo scanning, understanding how services connect |
| /architect | Opus | Deep exploration, complex reasoning, cross-repo analysis |
| /plan | Opus | Detailed planning requires strong reasoning (always Opus — strong foundation reduces iteration) |
| /critic | Opus | Finding real issues requires deep understanding (never tiered) |
| /revise | Opus | Addressing critic feedback requires strong reasoning (used in strict mode) |
| /revise-fast | Sonnet | Cost-efficient revision (used by /thorough_plan in normal mode, rounds 2+) |
| /thorough_plan | Opus | Orchestrates task triage and plan→critic→revise loop. Routes Small tasks to single-pass /plan; Medium uses Sonnet /revise-fast; Large/strict: uses all-Opus. Critic always Opus. |
| /run | Opus | End-to-end orchestrator managing phase transitions, user checkpoints, and subagent dispatch. Needs strong reasoning for conditional logic and error recovery. |
| /implement | Sonnet | Efficient code generation, plan already defines what to do |
| /review | Opus | Thorough analysis, integration safety, risk assessment |
| /gate | Sonnet | Automated checks and human approval checkpoint |
| /rollback | Sonnet | Safe undo of implementation phases |
| /end_of_task | Sonnet | Commit, push branch, lessons, mark complete |
| /end_of_day | Haiku | Session state capture and daily cache consolidation (structured template work) |
| /init_workflow | Opus | Project bootstrap, /discover invocation, structure creation |
| /start_of_day | Haiku | Context restoration and git state reconciliation (structured checklist) |
| /weekly_review | Haiku | Aggregates weekly progress, decisions, and outcomes (template-driven) |
| /capture_insight | Haiku | Quick insight logging to daily scratchpad during task work |
| /cost_snapshot | Haiku | Read-only cost reporting from ledger files and ccusage (lightweight) |
