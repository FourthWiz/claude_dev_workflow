# Development Workflow — Shared Rules

This file defines the common rules and behaviors shared across all development workflow skills: `/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan` (orchestrator), `/run` (end-to-end orchestrator), `/gate`, `/implement`, `/review`, `/rollback`, `/end_of_task`, `/end_of_day`, `/start_of_day`, `/weekly_review`, `/cost_snapshot`, `/capture_insight`, `/next-steps`, and `/triage`.

Runtime portability note: shared workflow semantics are being extracted under `quoin/core/workflow/` (`rules.md`, `task-layout.md`, `session-state.md`, `cost-ledger.md`). This file remains the active Claude Code runtime rules file installed by `bash quoin/install.sh`; do not treat it as generated yet.

## Working Rules

### Git & PR Safety
- **Never push to remote or create PRs outside of `/end_of_task`.** During implementation and review, only commit locally. Push happens as part of `/end_of_task` (which requires `/review` first). PR creation is always a separate explicit user action — never auto-create PRs.
- **Always start each new task on a fresh branch.** Commit current work, switch to main, fetch latest, then create the new branch.

### Communication
- **Keep multi-step workflow progress verbose.** When working through plans, implementations, or multi-round processes, provide status updates at each step. Don't go silent during long operations.

### Workflow conventions
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

### Multi-stage tasks

When a task has multiple stages, create per-stage subfolders inside the task folder:

```
PROJECT-FOLDER/.workflow_artifacts/TASK-NAME/
├── architecture.md           ← parent-level (single source of truth)
├── cost-ledger.md            ← parent-level (single ledger across all stages)
├── stage-1/
│   ├── current-plan.md
│   ├── critic-response-1.md
│   ├── review-1.md
│   └── gate-*.md
├── stage-2/
│   └── ...
└── ...
```

A task is "multi-stage" when its `architecture.md` has a `## Stage decomposition` section. Single-stage tasks keep the legacy root-level layout.

Skills resolve the artifact path via `quoin/scripts/path_resolve.py`. Resolution order:
1. **Explicit:** `stage N of <task>` → `<task-name>/stage-N/`.
2. **By name:** stage descriptive name + `## Stage decomposition` in architecture.md → resolver looks up stage number → `<task-name>/stage-N/`.
3. **Default:** `<task-name>/` (legacy / single-stage / mixed-layout grandfathering).

**Grandfathering:** existing folders with root-level `current-plan.md` and no `## Stage decomposition` continue using root-level layout. Resolver does NOT auto-migrate — migration is opt-in via a future `/thorough_plan stage N of <task>`. Two artifacts always stay at task root: `architecture.md` and `cost-ledger.md`.

### Archiving completed work

`/end_of_task` moves the task folder into `.workflow_artifacts/finalized/` (sub-task → `<parent>/finalized/`; top-level task → `finalized/<task>/`). **IMPORTANT: Never move to `finalized/` during planning or implementation** — only when `/end_of_task` is explicitly invoked.

## Workflow sequence

The intended flow depends on the task profile (Small / Medium / Large). `/thorough_plan` is the universal entry point — it triages and routes automatically.

### Canonical flow

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Variations: (a) Small tasks skip `/architect` and the critic loop — `/thorough_plan` auto-routes to a single `/plan` pass. (b) `/run` chains every phase automatically, each phase in its own subagent session, pausing at each GATE for confirmation; accepts the same profile tags as `/thorough_plan`. (c) Discover is skipped if a recent (<7 days) discovery file exists.

**Note on `/architect`:** Phase 4 critic loop is INTERNAL to `/architect` — the canonical flow string above is unchanged. `/architect` internally runs a critic loop (max 2 rounds default, max 4 in strict mode) before returning `architecture.md` as final. This does not add a visible step to the flow.

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
- `/architect` produces `architecture.md` with stages decomposed for planning (uses `/discover` output as baseline context); runs an internal Phase 4 critic loop (max 2 rounds default, 4 in strict mode) before returning architecture.md as final
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

**Gate invocation modes:** Post-implement and post-review gates run **inline** by default (same session, no subagent spawn — preserves the parent session's prompt cache). Post-architect and post-plan gates spawn **subagent** by default (different context shape after those phases). There is no `/gate` after `/discover`. Audit-log persistence (`gate-{phase}-{date}.md`) is mandatory regardless of mode — see `/gate/SKILL.md`.

Session lifecycle:
- `/start_of_day` — restores context from daily cache and checks git state. Run at the beginning of a work session.
- `/end_of_day` — saves session state and consolidates unfinished work into a daily cache. Run when wrapping up.
- `/weekly_review` — aggregates the week's progress into a structured review. Run on Friday (or whenever you want a week-level summary). Saves to `.workflow_artifacts/memory/weekly/`.

Multiple sessions can run in a day (parallel tasks). Each session writes its own state to `.workflow_artifacts/memory/sessions/`. `/end_of_day` rolls unfinished sessions into `.workflow_artifacts/memory/daily/<date>.md`.

## Session independence

**Each skill is designed to run in its own chat session.** File-based artifacts ARE the shared memory between sessions — never rely on a previous session's memory.

**Recommended session pattern:** One command per session for heavy work. `/run` gets its own session. Always run `/end_of_task` in a fresh session (8 sequential steps; compaction can silently skip steps). Short flows can share a session. When context feels heavy, close and start fresh.

**Every skill must be self-bootstrapping:** reads CLAUDE.md, lessons-learned.md, task subfolder artifacts, and session state on startup. Per-skill SKILL.md lists exact files. If a skill can't find what it needs, it asks the user.

**When closing a session:** update the session state file (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`) — this is the handoff to the next session.

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
- end_of_day_due: yes
- fallback_fires: 0
```

The `end_of_day_due` field defaults to `yes` at every session-state write. `/end_of_day` Step 3d flips it to `no` for each session it processes after the daily-cache write succeeds. `/start_of_day` reads this field (in addition to the existing insights-file check) as a second signal for the missing-EOD banner — if any session file written within the last 36 hours has `end_of_day_due: yes`, the banner fires.

The `fallback_fires` field counts Class B writer Step 5 English-fallback invocations and Step 2 Haiku dispatch retries during this session. The active skill increments the field in place (atomic-rename pattern, mirror of end_of_day_due flip) immediately before emitting the `format-kit-skipped` warning. Default value is `0` at every session-state write; never decremented. KNOWN ISSUE: under parallel subagent fallback fires (rare; <1/day in practice given pre-Stage-4 finalized-artifact data), the read-modify-write update can undercount — it never overcounts. For low-frequency telemetry visibility this undercounting is acceptable; if a future post-merge measurement shows >5% undercounting, escalate to a per-skill append-only counter file (per Stage 4 D-03-rev2 option 3 — currently deferred).

This is informational — the cost ledger (`.workflow_artifacts/<task-name>/cost-ledger.md`) is the source of truth for per-session costs.

### Cost tracking

Every skill that does meaningful work should record its session to the task's cost ledger at the start of the session. This enables `/end_of_task` to aggregate total cost across all sessions, including crashed sessions.

**Ledger path:** `.workflow_artifacts/<task-name>/cost-ledger.md`. Create with header `# Cost Ledger — <task-name>` if new.

**Row format — executable one-liner (7-column form):**

```bash
uuid=$(uuidgen) && printf '%s | %s | %s | %s | task | %s | %s\n' \
  "$uuid" "$(date -u +%Y-%m-%d)" "PHASE" "MODEL" "NOTE" "FALLBACK_FIRES" \
  >> "$LEDGER"
```

Substitute the bareword placeholders `PHASE`, `MODEL`, `NOTE`, `FALLBACK_FIRES` with session-specific values before running. `LEDGER` must be set to the ledger path (e.g., `.workflow_artifacts/<task-name>/cost-ledger.md`) before invocation. `NOTE` MUST be quoted — unquoted values containing spaces or pipes will produce malformed rows. Columns: `UUID | DATE | PHASE | MODEL | task | NOTE | FALLBACK_FIRES`.

**6-column form** (for Conditional skills `/discover`, `/triage` that omit `fallback_fires`):

```bash
uuid=$(uuidgen) && printf '%s | %s | %s | %s | task | %s\n' \
  "$uuid" "$(date -u +%Y-%m-%d)" "PHASE" "MODEL" "NOTE" \
  >> "$LEDGER"
```

The 7th column (`fallback_fires`) is OPTIONAL. Existing 6-column rows are valid forever; readers MUST tolerate both shapes. When present, the value is a non-negative integer (`0` if no fires occurred during the session). When absent, parsers treat it as `0`. Writers SHOULD emit the 7th column on new rows; readers MUST NOT fail on a missing 7th column. Append-only ledger semantics are unchanged.

**Writer guidance:** Skills emitting a new ledger row SHOULD include the 7th column when they have a session-state `fallback_fires` value available (typically at session-end emits, not session-open). Skills MAY emit a 6-column row when no session-state exists (e.g., `/discover`, `/triage`) or when `fallback_fires` is 0; readers tolerate both shapes per the row-format spec.

**UUID acquisition:** Most recently modified `<uuid>.jsonl` under `~/.claude/projects/<project-hash>/` (project-hash = project path with `/` replaced by `-`). Fall back to `unknown-<ISO-timestamp>` if none found.

**Phase values:** `discover`, `architect`, `plan`, `critic`, `revise`, `implement`, `review`, `gate`, `end-of-task`, `run-orchestrator`, `thorough-plan`, `rollback`, `init-workflow`, `start-of-day`, `end-of-day`, `weekly-review`, `capture-insight`, `triage`, `expand`, `checkpoint`, `sleep`, `session-close-hook`, `next-steps`, `ad-hoc`

**Category:** Always write `task`. The ledger is append-only — never delete or rewrite rows.

**Conditional skills:** `/discover`, `/gate`, `/start_of_day`, `/capture_insight`, and `/triage` skip cost recording if no task context is active.

### Knowledge cache

Cache lives under `.workflow_artifacts/cache/`. Three rules:
- **(a)** Cache is advisory; missing/stale entry is never an error.
- **(b)** Any skill that modifies source files MUST update the corresponding cache entry.
- **(c)** Rollback by deletion — deleting `.workflow_artifacts/cache/` fully restores pre-cache behavior.

Directory structure, entry format, and staleness tracking: see `__QUOIN_HOME__/memory/cache-guide.md` (deployed by install.sh from `quoin/memory/cache-guide.md`).

Per-skill patterns: cache-read bootstrap and write-through live inline in each skill's SKILL.md. Do not replace inline copies with a pointer — see lessons-learned 2026-04-13.

### Tier 1 — files that always stay English (caveman-token-optimization carve-out)

The following files are explicitly **excluded** from terse-style writing — they stay in human-readable English at all times:

**User-facing rendered output:** chat messages to the user; `/gate` rendered checkpoint summary.

**Hand-edited files:**
- `quoin/CLAUDE.md` (this file).
- `quoin/memory/lessons-learned.md`.
- `quoin/memory/terse-rubric.md` (+ deployed copy at `__QUOIN_HOME__/memory/`) — compressing recreates the v1 CRIT-2 circular dependency.
- `quoin/memory/format-kit.md` (+ deployed copy at `__QUOIN_HOME__/memory/`) — v3 content-type → primitive mapping.
- `quoin/memory/glossary.md` (+ deployed copy at `__QUOIN_HOME__/memory/`) — v3 abbreviation whitelist + status glyphs.
- `quoin/memory/format-kit.sections.json` (+ deployed copy at `__QUOIN_HOME__/memory/`) — machine-readable allowed/required sections sidecar.
- `quoin/memory/summary-prompt.md` (+ deployed copy at `__QUOIN_HOME__/memory/`) — frozen Haiku prompt template for Class B writer Step 2.
- `quoin/memory/format-kit-pitfalls.md` (+ deployed copy at `__QUOIN_HOME__/memory/`) — pre-write reminder block for Class B writers' Step 1.
- `quoin/memory/sleep-signals.yaml` (Tier 1 hand-edited source of truth for sleep importance signals)
- `__QUOIN_HOME__/memory/sleep-signals.yaml` (deployed copy — overwritten on re-install)
- `quoin/memory/cache-guide.md` (Tier 1 hand-edited cache entry format reference)
- `__QUOIN_HOME__/memory/cache-guide.md` (deployed copy — overwritten on re-install)

NOTE: QUICKSTART.md sits at `quoin/` root and deploys to `__QUOIN_HOME__/QUICKSTART.md` (NOT under `memory/`) — this is intentional. Do NOT normalize paths.
- `quoin/QUICKSTART.md` (+ `__QUOIN_HOME__/QUICKSTART.md` deployed copy).

**Contract-approval files (v3 format):**
- `<task>/architecture.md` — has an English `## For human` summary block at the top (read by humans and `/gate`); body is format-aware structured per `quoin/memory/format-kit.md` (read by skills).
- `<task>/review-<round>.md` — same v3 format as architecture.md.
- `<task>/cost-ledger.md` (structured, not prose; no v3 changes — append-only row format only).

**Rendered briefings:** `memory/weekly/*.md`; `memory/daily/<date>.md` (NOT `daily/insights-<date>.md`, which is Tier 3).

**Source files:** `MEMORY.md`; `quoin/skills/**/SKILL.md`; `quoin/dev/tests/fixtures/quoin-stage-1-preamble.md`; `quoin/dev/verify_subagent_dispatch.md`; `quoin/dev/tests/fixtures/path_resolve/**`; `quoin/skills/<skill>/preamble.md` (any of the 7 spawn targets — critic, revise, revise-fast, plan, review, gate, architect) — GENERATED by `quoin/scripts/build_preambles.py` at install time; never hand-edit. The file is machine-generated English content; listed here only for disambiguation — it is NOT a Tier 1 hand-edited source file.

`.planner-trace.md` is a Tier-3 ephemeral: machine-written by `/plan`, read by `/critic` as a search-prior only, deleted by `/end_of_task` before archive; no Haiku summary, no validator.

If adding a new file class: hand-edited or contract-approved → Tier 1; ephemeral or machine-only → Tier 3; user-approves-but-machine-reads → Tier 2.

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
| /next-steps | Haiku | Lightweight queue management for future work items |

### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)

The 7 spawn-target skills (critic, revise, revise-fast, plan, review, gate, architect) read `__QUOIN_HOME__/skills/<skill>/preamble.md` as the FIRST step of their `## Session bootstrap`. This pre-warms the prompt cache for the §3 slice of `format-kit.md` plus `glossary.md`, so the explicit format-kit / glossary reads later in the same bootstrap (and the references at write-sites per `format-kit.md` §1 / lesson 2026-04-23) hit cache rather than cold-loading. The preamble is purely additive — every other bootstrap read remains in force, the write-site references remain in force, and a missing preamble.md falls through to today's behavior (no error). The mechanism is purely a token-cost optimization; it MUST NOT change skill outputs. The preamble is GENERATED by `quoin/scripts/build_preambles.py` at install time; never hand-edit; see `quoin/docs/spawn-bootstrap-audit-2026-04-28.md` for membership rationale and `§Discrepancies` for why /implement is not a target. The full-preamble target size is ~4 KB (1.2 KB §3 slice + 2.8 KB glossary + frontmatter); gate gets a ~200-byte uniformity stub.

### §0 Model dispatch preamble

The 15 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast, sleep, next_steps, checkpoint) carry a `## §0 Model dispatch (FIRST STEP — execute before anything else)` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with the bare `[no-redispatch]` sentinel to prevent infinite recursion. The counter form `[no-redispatch:N]` is reserved for an abort signal: if a child sees N≥2, it aborts instead of proceeding (the bare form is the normal parent-emit; counter forms catch buggy parents or mistaken manual overrides). The 9 Opus-tier skills do NOT carry the preamble — they should run on Opus regardless of session model.

If the harness's subagent-spawn tool is unavailable or returns an error, dispatch falls back to a fail-OPEN path (proceed at current tier, emit a one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning). This is intentional per architecture I-01: cost guardrail is best-effort, not load-bearing for correctness.

Worktree-class errors (substring match: `Cannot create agent worktree` OR `worktree` + `not in a git repository`) are classified BEFORE the fail-OPEN warning is emitted. The skill uses the AskUserQuestion tool (always available in the parent session where §0 fires) to present recovery options. Available options depend on harness support (resolved by the pre-implementation spike): `retry-no-isolation` (if the harness exposes an isolation parameter that can be omitted), `retry-with-base <path>` (if the harness exposes a per-call base-path parameter), and `proceed-current-tier` (always available). A `[worktree-retry]` sentinel is prepended as the FIRST LINE of the retry prompt to prevent re-prompting on retry failure. Retry failures and other-class errors fall through to the bare fail-OPEN path. When the worktree branch was taken, a second classification line is also emitted: `[quoin-stage-1: error-class=worktree; user-choice=<a|b|c|retry-failed>; proceeding at current tier]`. The bare warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` is always emitted verbatim first so downstream string-matching consumers are unaffected.

Manual override: prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely. Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Mechanical drift detection lives in `quoin/dev/tests/test_quoin_stage1_preamble.py` and `quoin/dev/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification is captured in `quoin/dev/verify_subagent_dispatch.md`.

### §0' Pollution dispatch

The 7 Opus-tier skills that are NOT orchestrators (architect, plan, critic, revise, review, init_workflow, discover) carry a `## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)` block. When `pollution_score` exceeds `POLLUTION_THRESHOLD`, the skill self-dispatches as a fresh Agent subagent carrying per-skill paths (not content).

**Detection:** reads `pollution_score: N` from session-state file or `pollution-score-latest.txt`. Fires if N >= threshold AND no `[no-redispatch]` AND no prior §0 dispatch. Score formula: `transcript_kb + (agent_returns × 5) + (read_calls × 1) + (bash_calls × 1)` — implemented in `quoin/hooks/_lib.sh`. Written by `userpromptsubmit.sh` STEP 0.5 on every prompt submit.

**Per-skill dispatch contract:**

| Skill | What the dispatch prompt carries |
|-------|----------------------------------|
| /architect | task description + paths to /discover output |
| /plan | task description + path to architecture.md + stage identifier |
| /critic | absolute path to target artifact |
| /revise | path to current-plan.md + path to critic-response-N.md |
| /review | path to current-plan.md + branch ref |
| /init_workflow | project root absolute path |
| /discover | project root absolute path |

**Ordering:** §0 fires FIRST; §0' fires only if no §0 dispatch. For §0c skills (architect, review): §0c → §0' → body. **Excluded:** /run and /thorough_plan. **Threshold:** `QUOIN_POLLUTION_THRESHOLD` (default 5000). Fail-OPEN on Agent unavailable. `[no-redispatch]` skips. Drift detection: `test_quoin_pollution_preamble.py`; verification: `quoin/dev/verify_pollution_dispatch.md`.

### Hooks deployed by quoin

`bash install.sh` deploys hook scripts to `__QUOIN_HOME__/hooks/` and registers six (event, matcher) stanzas in `__QUOIN_HOME__/settings.json`:

| Event | Matcher | Script | Timeout | Contract |
|-------|---------|--------|---------|----------|
| UserPromptSubmit | `*` | `userpromptsubmit.sh` | 5s | Context utilization check; advisory or block |
| PreCompact | `auto` | `precompact.sh` | 10s | Last-resort save; blocks (direct conversation) or allows (skill pidfiles present) on auto-compaction |
| PostCompact | `auto` | `postcompact.sh` | 5s | Writes `postcompact-reset-${session_id}.txt` sentinel; `userpromptsubmit.sh` STEP 0.5 consumes it to confirm compaction occurred and trash-moves the sentinel |
| SessionStart | `startup` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionStart | `resume` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionEnd | `*` | `sessionend.sh` | 5s | EOD nudge if `end_of_day_due: yes` |

All hooks fail-OPEN (exit 0 on any error). jq is a soft-required dependency (`brew install jq`). Tunable constants (`QUOIN_BYTES_PER_TOKEN`, `QUOIN_EFFECTIVE_CONTEXT_LIMIT`, `QUOIN_STOP_BPS`, `QUOIN_BLOCK_BPS`, etc.) use `${QUOIN_*:-default}` expansion; thresholds use integer basis-points arithmetic (e.g., `8500` = 85.00%). Verbose details: `quoin/docs/hooks-guide.md`.

### Lifecycle skills (checkpoint / end_of_day / sleep)

Three skills handle session lifecycle at different granularities (v3 lifecycle separation per architecture):

**`/checkpoint`** — general-purpose state-save (mid-session, between tasks, between sessions). Writes session-restore state to `.workflow_artifacts/memory/checkpoints/<YYYY-MM-DD>-<task>.md` and a `pending-restore-${session_id}.txt` sentinel. Does NOT roll up dailies, does NOT touch `lessons-learned.md`, does NOT touch `forgotten/`. Use it mid-session before context exhaustion (when the context-utilization advisory fires), between tasks, between sessions, or proactively before starting new heavy work. **Paths-not-content rule (D-04):** checkpoint files record only PATHS to in-flight artifacts — never file contents. Restore re-fires Read tool on disk artifacts in the new session.

**`--restore` subcommand:** Run `/checkpoint --restore` in a fresh session to re-hydrate state. Locates the most recent checkpoint (or follows the `pending-restore-${session_id}.txt` sentinel from the compaction-block flow), surfaces task state, and optionally re-fires the saved pending prompt. Sentinel cleanup happens on restore. Voluntary `/checkpoint` now records `## Session ID` (UUID-anchored; two-line form) to disambiguate session-state lookup; restore picker now covers both pending-restore sentinels and recent (<= 30 day) checkpoint files (with fast-path bypass when current-session sentinel exists); `--defer` writes a marker that suppresses the userpromptsubmit advisory until the next compact or successful voluntary save; `--after-compact` is an explicit intent flag for the post-compact bypass case.

**`/end_of_day`** — rolls up daily session state into `.workflow_artifacts/memory/daily/<date>.md`. Touches `lessons-learned.md` if insights are promoted. Run at end of each work session.

**Session hooks (S-4):** `/start_of_day` checks `end_of_day_due: yes` in session files (Signal B, 36 h window). The `sessionstart.sh` hook provides the same check unconditionally at session-open (no need to invoke `/start_of_day`). The `sessionend.sh` hook nudges at session-close if the active session still has `end_of_day_due: yes`. Both hooks are non-blocking (exit 0) and informational only. Dedup: the sentinel file prevents duplicate banners within a 5-minute window.

**`/sleep`** — Haiku-tier. Auto-invoked by `/end_of_day` as its final step (opt-out via `--skip-sleep`). Scans daily insights + session files within a 30-day window. Three-bucket decisions:
- Promote → `lessons-learned.md` (per-entry user confirmation)
- Soft-Forget → `forgotten/<date>.md` archive (per-entry user confirmation in default mode; skipped above `forget_quiet_floor` score with `--quiet-forget`)
- Middle-Band → deferred

First 30 days of production: `/sleep --dry-run` mode only (no writes); inspect proposed decisions to tune weights.

Subcommands:
- `/sleep --restore <pattern>`: moves entries back from `forgotten/` to their source (or today's insights if source gone)
- `/sleep --purge --older-than 90d`: true-deletes archive files; per-file confirmation; never auto-run
- `/sleep --escalate`: re-examines middle-band candidates on Opus for deeper reasoning

**Boundary:** `/sleep` writes ONLY to `lessons-learned.md` and `forgotten/<date>.md`. Does NOT touch `~/.claude/projects/<hash>/memory/` (auto-memory). Distinct from `/checkpoint` (general-purpose state-save) and `/end_of_day` (end-of-workday rollup).

**Boundary summary:**
- `/checkpoint` → general-purpose state-save (`checkpoints/`, `sessions/`, `pending-*` sentinels — mid-session, between tasks, between sessions)
- `/end_of_day` → end-of-workday only — daily rollup (`daily/`, `lessons-learned.md`) + auto-invokes `/sleep`
- `/sleep` → long-term memory promote/forget (S-3 scope)

### /sleep importance signals

`/sleep` reads importance signals from `__QUOIN_HOME__/memory/sleep-signals.yaml` (deployed by install.sh from `quoin/memory/sleep-signals.yaml`). Source of truth: `quoin/memory/sleep-signals.yaml`. All thresholds override via `QUOIN_SLEEP_<KEY>` env vars. The `_source: claude_md` sentinel in the YAML distinguishes a live parse from hardcoded defaults. Fallback: if YAML absent, `sleep_score.py` parses from CLAUDE.md, then hardcoded defaults.

### Workflow memory layers

The workflow uses several distinct memory layers. Each has a different lifecycle, writer, and consumer:

| Memory layer | Purpose | Today's mechanism |
|---|---|---|
| auto-memory | user/feedback/project facts | written ad-hoc by Claude |
| `lessons-learned.md` | reusable engineering takeaways | `/end_of_task` + `/sleep` promote |
| `daily/insights-<date>.md` | in-session insight scratchpad | written ad-hoc via `/capture_insight` |
| `daily/<date>.md` | rendered daily briefing | written by `/end_of_day` |
| `weekly/<iso-week>.md` | rendered weekly review | written by `/weekly_review` |
| `forgotten/<date>.md` (NEW in S-3) | soft-forget archive | written by `/sleep` |

**Hard boundary:** `/sleep` writes ONLY to `lessons-learned.md` and `forgotten/<date>.md`. It does NOT touch `~/.claude/projects/<hash>/memory/` (auto-memory). This restriction is enforced by the write-target restriction in the `/sleep` SKILL.md and tested by the `test_sleep_write_boundary.py` test.

The `forgotten/` directory structure:
```
.workflow_artifacts/memory/
├── sessions/          ← per-session state files
├── daily/             ← rendered briefings + insights scratchpads
├── weekly/            ← weekly review summaries
├── checkpoints/       ← /checkpoint restore sentinels
├── forgotten/         ← soft-forget archive (NEW — S-3)
│   └── <date>.md      ← one file per day /sleep ran with forgets
├── trash/             ← recoverable delete archive (sentinel trash-moves land here)
│   └── <YYYY-MM-DD>/  ←   dated subdirs, one per trash day
└── lessons-learned.md ← long-term institutional memory
```

Note: `trash/` accumulates sentinel files moved by `trash_move()` (in `_lib.sh`) instead of hard-deleted. The `/sleep --purge --older-than 90d` scope does not yet include `trash/` — this is a known gap (R-7); a follow-up task will extend `/sleep --purge` to cover `trash/`.

Each `forgotten/<date>.md` file is append-only. Each entry block follows this format:

```
> Source: <absolute-path-to-source-file>:<start-line>..<end-line>
> Forgotten: <ISO timestamp>
> Score: forget=<N>, promote=<N>

<original entry text verbatim>

---
```

The `> Source:` line is the restore anchor for `/sleep --restore`. Use `/sleep --restore <pattern>` to search `forgotten/` and move entries back to their source location.
