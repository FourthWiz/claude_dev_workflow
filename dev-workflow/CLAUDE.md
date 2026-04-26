# Development Workflow — Shared Rules

This file defines the common rules and behaviors shared across all development workflow skills: `/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan` (orchestrator), `/run` (end-to-end orchestrator), `/gate`, `/implement`, `/review`, `/rollback`, `/end_of_task`, `/end_of_day`, `/start_of_day`, `/weekly_review`, `/cost_snapshot`, `/capture_insight`, and `/triage`.

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

### Canonical flow

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Variations: (a) Small tasks skip `/architect` and the critic loop — `/thorough_plan` auto-routes to a single `/plan` pass. (b) `/run` chains every phase automatically, each phase in its own subagent session, pausing at each GATE for confirmation; accepts the same profile tags as `/thorough_plan`. (c) Discover is skipped if a recent (<7 days) discovery file exists.

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

## Session independence

**Each skill is designed to run in its own chat session.** Context windows fill up — this is expected. The file-based artifacts (`current-plan.md`, `critic-response-N.md`, session state, `architecture.md`, etc.) ARE the shared memory between sessions.

**Recommended session pattern:**
- One command per session for heavy work (`/architect`, `/thorough_plan`, `/implement`, `/review`)
- **`/run` gets its own session.** It orchestrates subagent sessions for each phase, so it stays lean — but start it fresh so the orchestrator has maximum context for managing the full pipeline.
- **Always run `/end_of_task` in a fresh session** if the current session has been through heavy work. The skill has 8 sequential steps that must all complete — context compaction mid-skill can silently skip steps like archiving.
- Short flows can share a session (`/plan` → `/implement` → `/review` for a small bug fix)
- Use your judgment: when context feels heavy, close and start fresh

**Every skill must be self-bootstrapping:** on a fresh-session start, it reads CLAUDE.md, `.workflow_artifacts/memory/lessons-learned.md` (planning/review skills), the relevant task subfolder artifacts, the latest session state, and the actual source code — never relying on a previous session's memory. The per-skill SKILL.md lists the exact files for that skill.

The user should never have to re-explain context that's already in the files. If a skill can't find what it needs, it asks the user — but the default is to read from disk.

**When closing a session:** any skill that did meaningful work should update the session state file (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`) before the session ends. This is the handoff to the next session.

## Common rules for all skills

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
- Session UUID: <UUID — see Cost tracking rules for acquisition>
- Phase: <phase>
- Recorded in cost ledger: yes/no
```

This is informational — the cost ledger (`.workflow_artifacts/<task-name>/cost-ledger.md`) is the source of truth for per-session costs.

### Cost tracking

Every skill that does meaningful work should record its session to the task's cost ledger at the start of the session. This enables `/end_of_task` to aggregate total cost across all sessions, including crashed sessions.

**Ledger path:** `.workflow_artifacts/<task-name>/cost-ledger.md`. Create with header `# Cost Ledger — <task-name>` if new.

**Row format:** `<session-uuid> | <YYYY-MM-DD> | <phase> | <primary-model> | task | <brief note>`

**UUID acquisition:** Most recently modified `<uuid>.jsonl` under `~/.claude/projects/<project-hash>/` (project-hash = project path with `/` replaced by `-`). Fall back to `unknown-<ISO-timestamp>` if none found.

**Phase values:** `discover`, `architect`, `plan`, `critic`, `revise`, `implement`, `review`, `gate`, `end-of-task`, `run-orchestrator`, `thorough-plan`, `rollback`, `init-workflow`, `start-of-day`, `end-of-day`, `weekly-review`, `capture-insight`, `triage`, `expand`, `ad-hoc`

**Category:** Always write `task`. The ledger is append-only — never delete or rewrite rows.

**Conditional skills:** `/discover`, `/gate`, `/start_of_day`, `/capture_insight`, and `/triage` skip cost recording if no task context is active.

### Knowledge cache

The cache lives under `.workflow_artifacts/cache/`. Three rules govern all skills:
- **(a) Cache is advisory, not authoritative** — a missing or stale cache entry is never an error; skills may always read source files directly.
- **(b) Any skill that modifies source files MUST update the corresponding cache entry** (enforced per-skill in each skill's inline "Cache write-through" section). The `.workflow_artifacts/cache/` directory is the host.
- **(c) Rollback by deletion** — deleting `.workflow_artifacts/cache/` fully restores pre-cache behavior; no skill should fail if the cache directory is absent.

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

#### Staleness tracking

`_staleness.md` stores repo-level HEAD; skills read it to decide which cache entries are still valid; successor to `repo-heads.md` (fall back if absent).

#### Per-skill patterns

Cache-read bootstrap and cache write-through patterns live inline in each skill's SKILL.md. Subagents read their own SKILL.md at startup, not this file — see lessons-learned 2026-04-13. Do not replace inline copies with a pointer.

### Tier 1 — files that always stay English (caveman-token-optimization carve-out)

The caveman-token-optimization v2 architecture (see `.workflow_artifacts/caveman-token-optimization/architecture.md`) introduces terse-style writing for many workflow artifacts. The following files are explicitly **excluded** from terse-style writing — they stay in human-readable English at all times:

**User-facing rendered output:**
- Chat messages to the user (progress, questions, conclusions).
- The `/gate` rendered checkpoint summary shown at each gate.

**Hand-edited files:**
- `dev-workflow/CLAUDE.md` (this file).
- `dev-workflow/memory/lessons-learned.md`.
- `dev-workflow/memory/terse-rubric.md` (the rubric itself — compressing it recreates the v1 CRIT-2 circular dependency).
- `~/.claude/memory/terse-rubric.md` (deployed copy — read by skills at runtime; overwritten on re-install from the source above).
- `dev-workflow/memory/format-kit.md` (v3 format-aware writing reference; content-type → primitive mapping; per artifact-format-architecture v3 §5.1).
- `~/.claude/memory/format-kit.md` (deployed copy — overwritten on re-install).
- `dev-workflow/memory/glossary.md` (v3 abbreviation whitelist + status glyphs; extends terse-rubric; per artifact-format-architecture v3 §5.2).
- `~/.claude/memory/glossary.md` (deployed copy — overwritten on re-install).
- `dev-workflow/memory/format-kit.sections.json` (v3 machine-readable sidecar enumerating allowed/required sections per artifact type; structured-not-prose; consumed by validate_artifact.py per v3 §5.3.2).
- `~/.claude/memory/format-kit.sections.json` (deployed copy — overwritten on re-install).

**Contract-approval files (v3 format):**
- `<task>/architecture.md` — has an English `## For human` summary block at the top (read by humans and `/gate`); body is format-aware structured per `dev-workflow/memory/format-kit.md` (read by skills).
- `<task>/review-<round>.md` — same v3 format as architecture.md.
- `<task>/cost-ledger.md` (structured, not prose; no v3 changes — append-only row format only).

**Rendered briefings:**
- `memory/weekly/*.md`.
- `memory/daily/<date>.md` (the rendered briefing — NOT `daily/insights-<date>.md`, which is Tier 3).

**Source files:**
- `MEMORY.md` (tiny — below any compression threshold).
- `dev-workflow/skills/**/SKILL.md` (skill source, not artifact).
- `dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md` (Quoin Stage 1 §0 preamble template; hand-edited Tier 1; source of truth for the 12 cheap-tier SKILL.md preambles).
- `dev-workflow/scripts/verify_subagent_dispatch.md` (Quoin Stage 1 subagent-dispatch verification template; hand-filled by user during T-00 pilot and T-09 smoke; lives at `dev-workflow/scripts/` only — NOT deployed to `~/.claude/scripts/` per round-3 MIN-1 fix; one-shot diagnostic, not a runtime tool).

Any other workflow artifact may be subject to terse-style writing (Tier 2 contract files use English + side-file; Tier 3 ephemeral files are terse-only with `/expand` for human reading).

If you are adding a new file class and unsure which tier applies: hand-edited or contract-approved → Tier 1; ephemeral or machine-only → Tier 3; user-approves-but-machine-reads → Tier 2.

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
| /triage | Haiku | Lightweight routing: reads prompt, inspects state, proposes a skill. |

### §0 Model dispatch preamble (Quoin foundation Stage 1)

The 12 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast) carry a `## §0 Model dispatch (FIRST STEP — execute before anything else)` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with the bare `[no-redispatch]` sentinel to prevent infinite recursion. The counter form `[no-redispatch:N]` is reserved for an abort signal: if a child sees N≥2, it aborts instead of proceeding (the bare form is the normal parent-emit; counter forms catch buggy parents or mistaken manual overrides). The 9 Opus-tier skills do NOT carry the preamble — they should run on Opus regardless of session model.

If the harness's subagent-spawn tool is unavailable or returns an error, dispatch falls back to a fail-OPEN path (proceed at current tier, emit a one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning). This is intentional per architecture I-01: cost guardrail is best-effort, not load-bearing for correctness.

Manual override: prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely. Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Mechanical drift detection lives in `dev-workflow/scripts/tests/test_quoin_stage1_preamble.py` and `dev-workflow/scripts/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification lives in T-00 (pilot, before T-02) and T-09 (full four-phase smoke after T-02 + install) of the stage-1 plan and is captured in `dev-workflow/scripts/verify_subagent_dispatch.md`. (Note for the future Quoin-rebrand stage: this subsection's "Quoin foundation Stage 1" reference becomes stale post-rebrand — update the wording to a stage-tracker-stable reference at that time.)
