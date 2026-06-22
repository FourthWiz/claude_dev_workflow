# Development Workflow — Shared Rules

## Open-model routing (opt-in)

Two launch modes exist for quoin users who have set up claude-code-router (CCR):

- **Open models via CCR:** `ccr code` — auto-starts the local proxy and launches the
  real `claude` binary in your terminal. Quoin's slash commands and skills work normally
  (the proxy uses `stdio: "inherit"`, preserving the interactive PTY).
- **Native Anthropic:** `claude` — launches Claude Code directly with your Anthropic key.

**Sanity-check:** inside a `ccr code` session, type `/help`. The quoin skill list should
resolve. If it doesn't, run `quoin router status` and check proxy liveness.
The model shown in the Claude Code header (e.g. "Sonnet 4.6") remains unchanged — CCR
routes requests transparently at the HTTP layer; the Claude Code UI has no visibility
into the substitution. The actual invoked model is what CCR maps to.

Setup: `export OPENROUTER_API_KEY=sk-or-... && quoin router setup`

Note: the `__QUOIN_HOME__` placeholder refers to the quoin deploy root (installed by
`quoin install`). CCR's own config lives in `$HOME/.claude-code-router/` and quoin's
model defaults are in `$HOME/.config/quoin/models.json` — these are NOT deploy-tree
paths and are never substituted by the installer.

This file defines the common rules and behaviors shared across all development workflow skills: `/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan` (orchestrator), `/run` (end-to-end orchestrator), `/gate`, `/implement`, `/review`, `/rollback`, `/end_of_task`, `/pr`, `/end_of_day`, `/start_of_day`, `/weekly_review`, `/cost_snapshot`, `/capture_insight`, `/next-steps`, `/triage`, and `/continue_work`.

Runtime portability note: shared workflow semantics are being extracted under `quoin/core/workflow/` (`rules.md`, `task-layout.md`, `session-state.md`, `cost-ledger.md`). This file remains the active Claude Code runtime rules file installed by `bash quoin/install.sh`; do not treat it as generated yet.

## Working Rules

### Git & PR Safety
- **Never push to remote or create PRs outside of `/end_of_task` and `/pr`.** During implementation and review, only commit locally. Push happens as part of `/end_of_task` (which requires `/review` first). PR creation is handled by `/pr`, invoked explicitly by the user after `/end_of_task`. PR creation is always a separate explicit user action — never auto-create PRs.
- **Use `/pr` to create pull requests.** After `/end_of_task` finalizes and pushes the branch, invoke `/pr` to create the PR (with optional version bump), wait for merge, and switch to the merge target branch.
- **Always start each new task on a fresh branch.** Commit current work, switch to main, fetch latest, then create the new branch. This is now ENFORCED, not just advisory: `/implement` runs a branch-hygiene precheck at dispatch entry (prompts if on a protected branch), `/gate` FAILS if task commits land on a protected branch (commits ahead of upstream on main/master), and `/review` flags it as a diff-independent backstop. See `branch_hygiene.py`.

### Communication
- **Keep multi-step workflow progress verbose.** When working through plans, implementations, or multi-round processes, provide status updates at each step. Don't go silent during long operations.
- **End-of-step inline summary.** After `/thorough_plan`, `/implement`, or `/review` completes its major step, the skill MUST print a concise human-readable English summary in the chat as its **final user-facing message, before the STOP/next-step instruction**. The summary is a chat message (Tier 1 always-English), never terse, never written to disk. Canonical field set:
  1. **What this step produced** — one sentence (e.g., "Produced a converged Medium-profile plan in 1 round" / "Implemented tasks T-01 through T-04").
  2. **Main tasks or components** — 2–4 bullets in plain language, no terse glyphs.
  3. **Remaining concerns or decisions for the user** — one line; "none" if clean.
  4. **Artifact location** — the path to the written artifact, with a note that the body is terse and can be `/expand`-ed for detail.
  This rule is REQUIRED even when `/gate` will also render a summary — the skill's inline chat summary and the gate's `## For human` echo are complementary (the skill summary describes the step's work; the gate echo renders the stored artifact summary). Do NOT rely on the user reading terse artifacts — restate the substance in plain English in the chat. `/run` already satisfies this via its Checkpoint A–D summaries; the per-skill summaries additionally cover **standalone invocation** (skill run directly, not under `/run`).

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

After `/end_of_task`: the user explicitly invokes `/pr` to create a pull request. This is a separate user action — `/pr` is never auto-invoked by any skill or orchestrator.

- `/rollback` is available at any point to safely undo implementation work

Not every task needs every stage. Small tasks typically skip `/architect` entirely. Bug fixes might only need `/implement` + `/review` (bypassing `/thorough_plan` entirely). But gates ALWAYS run between phases.

**CRITICAL RULE: `/implement` and `/end_of_task` require explicit user commands.** No skill may auto-invoke either. After `/thorough_plan` converges, the workflow STOPS and waits for `/implement`. After `/review` approves and the gate passes, the workflow STOPS and waits for `/end_of_task`. The user must consciously decide to start writing code AND to ship it.

**Exception: `/run` orchestrator.** When the user invokes `/run`, they have explicitly requested the full end-to-end pipeline. `/run` may invoke `/implement` and `/end_of_task` on the user's behalf, but still pauses at each gate checkpoint for confirmation before proceeding. The user's `/run` invocation constitutes the conscious decision; the gate confirmations provide the safety checkpoints.

**Gate invocation modes:** Post-implement and post-review gates run **inline** by default (same session, no subagent spawn — preserves the parent session's prompt cache). Post-architect and post-plan gates spawn **subagent** by default (different context shape after those phases). There is no `/gate` after `/discover`. Audit-log persistence (`gate-{phase}-{date}.md`) is mandatory regardless of mode — see `/gate/SKILL.md`.

Session lifecycle:
- `/start_of_day` — restores context from daily cache and checks git state. Run at the beginning of a work session.
- `/end_of_day` — saves session state and consolidates unfinished work into a daily cache. Run when wrapping up.
- `/weekly_review` — aggregates the week's progress into a structured review. Run on Friday (or whenever you want a week-level summary). Saves to `.workflow_artifacts/memory/weekly/`.

Multiple sessions can run in a day (parallel tasks). Each session writes its own state to `.workflow_artifacts/memory/sessions/`. `/end_of_day` reads all unprocessed session files within the date window from the last daily-cache up to today (not only today's files) and rolls them into `.workflow_artifacts/memory/daily/<date>.md`.

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

This rule is enforced at three layers: (1) `/implement` §0b branch-hygiene precheck prompts to create a feature branch if any repo is on a protected branch before the first commit; (2) `/gate` FAILS if task commits (commits ahead of upstream on main/master, i.e., `has_task_commits: true`) are detected on a protected branch post-implement; (3) `/review` flags it as a diff-independent backstop. The gate keys on the commits-ahead signal, NOT bare on-main status — a clean repo sitting on main with no ahead commits is NOT a violation. Env knobs: `QUOIN_PROTECTED_BRANCHES` (csv, default `main,master`), `QUOIN_DISABLE_BRANCH_HYGIENE=1` (global opt-out). If recovery is needed (mis-placed commits on a protected branch), the canonical safe reset-main-to-origin recipe is at `__QUOIN_HOME__/memory/branch-recovery.md`.

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

PR creation is handled by the `/pr` skill. When the user asks to create a PR, invoke `/pr` which handles: pre-flight checks (branch ≠ main/master, gh CLI available and authenticated), optional version bump, push if not already pushed, PR creation via `gh pr create` with a structured message, waiting for the user to merge, and switching to the merge target branch after merge.

The manual PR review checklist below applies as a fallback when `/pr` is not available or when creating PRs outside the quoin workflow.

When creating a PR manually, before doing so:

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

### Serena (conditional)

If `ToolSearch select:mcp__serena__activate_project` loads a schema, run the activation protocol at task start (`activate_project` then `initial_instructions`) and prefer Serena symbol tools over grep. If no schema loads, do nothing — never call Serena tools that don't exist. Full protocol: `__QUOIN_HOME__/memory/serena-activation.md`.

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

Every skill that does meaningful work (architect, plan, critic, revise, implement, review, run) writes/updates `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` at natural checkpoints. Update `Current stage`, `Completed in this session`, `Unfinished work` so `/end_of_day` and `/start_of_day` see accurate state.

The session-state template includes a `## Cost` section:

```markdown
## Cost
- Session UUID: <UUID — see Cost tracking rules>
- Phase: <phase>
- Recorded in cost ledger: yes/no
- end_of_day_due: yes
- fallback_fires: 0
```

`end_of_day_due: yes` defaults at every write; `/end_of_day` Step 3d flips to `no` for each session in the processed window (all sessions selected by the hybrid date-window + flag rule, not only today's); `sessionstart.sh` + `/start_of_day` use it as the second signal for the missing-EOD banner (36 h window). `fallback_fires` counts Class B writer Step 5 English-fallback invocations + Step 2 Haiku-dispatch retries; atomic-rename increment; never decremented; under-counts under parallel subagents (acceptable per D-03-rev2). Full semantics: `__QUOIN_HOME__/memory/lifecycle-guide.md`.

The cost ledger (`.workflow_artifacts/<task-name>/cost-ledger.md`) is the source of truth for per-session costs.

### Cost tracking

Every skill records its session to the task's cost ledger at session start.

**Ledger path:** `.workflow_artifacts/<task-name>/cost-ledger.md`. Create with header `# Cost Ledger — <task-name>` if new. Columns: `UUID | DATE | PHASE | MODEL | task | NOTE | FALLBACK_FIRES` (7-col); 6-col rows (no FALLBACK_FIRES) remain valid forever — readers tolerate both. Append-only; never delete or rewrite rows.

**Phase values:** `discover`, `architect`, `plan`, `critic`, `revise`, `implement`, `review`, `gate`, `end-of-task`, `pr`, `run-orchestrator`, `thorough-plan`, `rollback`, `init-workflow`, `start-of-day`, `end-of-day`, `weekly-review`, `capture-insight`, `triage`, `expand`, `checkpoint`, `cleanup`, `sleep`, `session-close-hook`, `next-steps`, `ad-hoc`

**Category:** Always write `task`.

**Conditional skills:** `/discover`, `/gate`, `/start_of_day`, `/capture_insight`, and `/triage` skip cost recording if no task context is active.

Bash one-liner (7-col + 6-col), UUID acquisition rules, writer guidance, NOTE-quoting requirement, and parser tolerance details: `__QUOIN_HOME__/memory/cost-ledger-format.md` (and portable shape in `quoin/core/workflow/cost-ledger.md`).

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
- `quoin/memory/cost-ledger-format.md` (+ `__QUOIN_HOME__/memory/cost-ledger-format.md` deployed copy — extracted verbose Cost tracking row-format from CLAUDE.md 2026-05-15).
- `quoin/memory/dispatch-guide.md` (+ `__QUOIN_HOME__/memory/dispatch-guide.md` deployed copy — extracted verbose §0 / §0' dispatch details from CLAUDE.md 2026-05-15).
- `quoin/memory/hooks-table.md` (+ `__QUOIN_HOME__/memory/hooks-table.md` deployed copy — extracted hooks event/matcher table from CLAUDE.md 2026-05-15).
- `quoin/memory/lifecycle-guide.md` (+ `__QUOIN_HOME__/memory/lifecycle-guide.md` deployed copy — extracted verbose Lifecycle skills + memory-layers details from CLAUDE.md 2026-05-15).
- `quoin/memory/branch-recovery.md` (+ `__QUOIN_HOME__/memory/branch-recovery.md` deployed copy — canonical safe branch-reset recipe (`git update-ref`) for recovering from "commits on main"; added IVG-77 2026-06-17).
- `quoin/memory/preamble-guide.md` — subagent prompt-cache warm-up; added IVG-50 S-3.
- `quoin/memory/memory-maintenance.md` (+ `__QUOIN_HOME__/memory/memory-maintenance.md` deployed copy — Tier-1 reference doc for memory lifecycle: archive/soft-forget/delete policy, pattern schema, consumer contracts; added IVG-50 S-3 2026-06-18).
- `quoin/memory/memory-maintenance.yaml` (+ `__QUOIN_HOME__/memory/memory-maintenance.yaml` deployed copy — pattern config (ignore/archived/read_only globs) for memory_check.py and /sleep; token-free glob file; added IVG-50 S-3 2026-06-18).

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
| /pr | Sonnet | Procedural automation: version bump detection, PR creation, post-merge cleanup |
| /end_of_day | Haiku | Session state capture and daily cache consolidation (structured template work) |
| /init_workflow | Opus | Project bootstrap, /discover invocation, structure creation |
| /start_of_day | Haiku | Context restoration and git state reconciliation (structured checklist) |
| /weekly_review | Haiku | Aggregates weekly progress, decisions, and outcomes (template-driven) |
| /capture_insight | Haiku | Quick insight logging to daily scratchpad during task work |
| /cost_snapshot | Haiku | Read-only cost reporting from ledger files and ccusage (lightweight) |
| /status | Haiku | Read-only pipeline-graph reporting (shows active workflow phase) |
| /triage | Haiku | Lightweight routing: reads prompt, inspects state, proposes a skill. |
| /next-steps | Haiku | Lightweight queue management for future work items |
| /continue_work | Sonnet | Revive context from a prior session: reads recent-sessions.md, presents session picker, extracts checkpoint summary and recent messages from JSONL. |
| /cleanup | Haiku | Mechanical trash-move of stale sentinels/checkpoints (structured file ops). |

### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)

Purely additive prompt-cache warm-up for 7 spawn-target skills; generated by `build_preambles.py`; never hand-edit. Full details: `__QUOIN_HOME__/memory/preamble-guide.md`.

### §0 Model dispatch preamble

The 19 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cleanup, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast, sleep, next_steps, checkpoint, continue_work, pr, status) carry a `## §0 Model dispatch` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with `[no-redispatch]` to prevent recursion. Counter form `[no-redispatch:N]` (N≥2) is an abort signal. The 9 Opus-tier skills do NOT carry §0. The 7 Opus-tier leaf skills (architect, plan, critic, revise, review, init_workflow, discover) carry `## §0″ Minimum-tier guard` (under-tier protection) instead; orchestrators `/run` and `/thorough_plan` carry neither.

Fail-OPEN on Agent unavailable (one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning); architecture I-01 = best-effort cost guardrail. Worktree-class errors → AskUserQuestion recovery prompt. Manual override: prefix slash invocation with `[no-redispatch]`. Drift detection: `quoin/dev/tests/test_quoin_stage1_preamble.py`, `quoin/dev/tests/test_quoin_stage1_recursion_abort.py`. Verbose details (worktree-error classification, sentinel forms, recovery options): `__QUOIN_HOME__/memory/dispatch-guide.md`. 1M-context credit mismatch recovery (IVG-89): pre-dispatch model-name detection is impossible; recovery is folded into the EXISTING `§0-worktree-fallback` error-classification leaf as a new 1M-credit-class branch — when the dispatch error matches `Usage credits required for 1M context`, the skill emits a specific advisory (with `/model` remedy hint) and proceeds in-session at parent tier. The dead `§0-1m-context-precheck` marker blocks have been removed from all 19 §0 skills.

### §0' Pollution dispatch

The 7 Opus-tier non-orchestrator skills (architect, plan, critic, revise, review, init_workflow, discover) carry a `## §0' Pollution dispatch` block. Fires when `pollution_score >= QUOIN_POLLUTION_THRESHOLD` (default 5000) AND no `[no-redispatch]` AND no prior §0 dispatch. Score = `transcript_kb + (agent_returns × 5) + (read_calls × 1) + (bash_calls × 1)`; written by `userpromptsubmit.sh` STEP 0.5. Dispatches a fresh Agent subagent carrying per-skill paths (not content). §0 fires first; §0' fires only if no §0 dispatch. Excluded: `/run`, `/thorough_plan`. Fail-OPEN on Agent unavailable. Drift: `quoin/dev/tests/test_quoin_pollution_preamble.py`. Per-skill dispatch contract + verbose detection rules: `__QUOIN_HOME__/memory/dispatch-guide.md`. 1M-context credit mismatch recovery (IVG-89): pre-dispatch model-name detection is impossible (same finding as §0); recovery is folded into the `Fail-OPEN path` of the §0' block — when the dispatch error matches `Usage credits required for 1M context`, AskUserQuestion is issued (abort/proceed). For any other non-1M dispatch error, AskUserQuestion also fires (generic wording) so §0' never silently loses recovery. The dead `§0prime-1m-context-precheck` marker blocks have been removed from the generator template and all 7 §0' skills.

### §0″ Minimum-tier guard

The 7 Opus-tier leaf skills (architect, plan, critic, revise, review, init_workflow, discover) carry a `## §0″ Minimum-tier guard` block. Fires when `current_tier < declared_tier` (inverse of §0). Fail-open: AskUserQuestion with abort/proceed-under-powered options on Agent failure. Env knob `QUOIN_DISABLE_MINTIER_GUARD=1` → silent skip (explicit opt-out by design). Generated by `inject_pollution_dispatch.py`; drift test `quoin/dev/tests/test_mintier_guard.py`. Orchestrators `/run`, `/thorough_plan` excluded (D-04). Full decision tree, Option A/B variants, and precheck details: `__QUOIN_HOME__/memory/dispatch-guide.md`.

### Hooks deployed by quoin

`bash install.sh` deploys hook scripts to `__QUOIN_HOME__/hooks/` and registers six (event, matcher) stanzas in `__QUOIN_HOME__/settings.json`: UserPromptSubmit/`*`, PreCompact/`auto`, PostCompact/`auto`, SessionStart/`startup`, SessionStart/`resume`, SessionEnd/`*`. `userpromptsubmit.sh` enforces context-utilization advisory/block AND idle-session detection (STEP 0.7 appends to `recent-sessions.md`; STEP 0.9 emits an advisory when the session has been idle for >1 hour); `precompact.sh`/`postcompact.sh` manage compaction sentinels (STEP 1b also appends to `recent-sessions.md` before compaction); `sessionstart.sh`/`sessionend.sh` handle S-4 banners. The `recent-sessions.md` data file (written by hooks and `/checkpoint`, read by `/continue_work`) lives at `<cwd>/.workflow_artifacts/memory/recent-sessions.md`.

All hooks fail-OPEN (exit 0 on any error). jq is a soft-required dependency. Tunable constants (`QUOIN_BYTES_PER_TOKEN`, `QUOIN_EFFECTIVE_CONTEXT_LIMIT`, `QUOIN_STOP_BPS`, `QUOIN_BLOCK_BPS`, `QUOIN_COMPACT_FIRST_BPS`, etc.) use `${QUOIN_*:-default}` expansion with integer basis-points arithmetic. Full table + verbose details: `__QUOIN_HOME__/memory/hooks-table.md` and `quoin/docs/hooks-guide.md`.

### Lifecycle skills (checkpoint / end_of_day / sleep / cleanup)

Four skills handle session lifecycle at different granularities (v3 lifecycle separation):
- `/checkpoint` — general-purpose state-save (mid-session, between tasks, between sessions). Three save modes: `--mode restore` (default), `--mode load-as-reference`, `--mode mid-agent`. Auto-detects compact-already-ran (auto-compact+pending-restore skip path) and high-util state (save immediately + surface fresh-session-or-compact options); see lifecycle-guide.md for full rules. Paths-not-content rule (D-04). `/checkpoint --restore` re-hydrates in fresh session.
- `/end_of_day` — rolls up daily session state into `.workflow_artifacts/memory/daily/<date>.md`. Touches `lessons-learned.md` if insights promoted. Auto-invokes `/sleep`.
- `/sleep` — Haiku-tier. Scans daily insights + session files (30-day window). Three-bucket decisions: Promote → `lessons-learned.md`; Soft-Forget → `forgotten/<date>.md`; Middle-Band → deferred. Subcommands: `--restore <pattern>`, `--purge --older-than 90d`, `--escalate`, `--dry-run`. Writes ONLY to `lessons-learned.md` + `forgotten/`; never touches `~/.claude/projects/<hash>/memory/`.
- `/cleanup` — Haiku-tier. Trash-moves stale sentinels (all sessions except freshest/current, identified by UUID-suffix skip before any age check) and old checkpoints into recoverable `trash/<date>/` archive. Recovery via manual `mv` from `.workflow_artifacts/memory/trash/<date>/` — NOT `/sleep --restore` (which only reads `forgotten/` text entries). Auto-fires as the FIRST sub-block of `/checkpoint` Step 1.5 (default-on, `--no-cleanup` opt-out; skipped at high-util/mid-agent for compress-first ordering). Env knobs: `QUOIN_CLEANUP_SENTINEL_WINDOW` (default 1d), `QUOIN_CLEANUP_CKPT_WINDOW` (default 30d).

Session hooks (S-4): `sessionstart.sh` + `sessionend.sh` check `end_of_day_due: yes` (36 h window); non-blocking informational banners; 5-min sentinel dedup. Full subcommand contracts, mode auto-detection rules, restore-picker logic, and `--after-compact`/`--defer` semantics: `__QUOIN_HOME__/memory/lifecycle-guide.md`.

### /sleep importance signals

`/sleep` reads signals from `__QUOIN_HOME__/memory/sleep-signals.yaml` (source: `quoin/memory/sleep-signals.yaml`). Thresholds override via `QUOIN_SLEEP_<KEY>` env vars. Fallback if YAML absent: `sleep_score.py` parses this section, then hardcoded defaults.

### Workflow memory layers

The workflow uses several distinct memory layers, each with a different lifecycle:

| Memory layer | Purpose | Writer |
|---|---|---|
| auto-memory | user/feedback/project facts | Claude ad-hoc |
| `lessons-learned.md` | reusable engineering takeaways | `/end_of_task` + `/sleep` |
| `daily/insights-<date>.md` | in-session scratchpad | `/capture_insight` |
| `daily/<date>.md` | rendered daily briefing | `/end_of_day` |
| `weekly/<iso-week>.md` | rendered weekly review | `/weekly_review` |
| `forgotten/<date>.md` | soft-forget archive | `/sleep` |

**Hard boundary:** `/sleep` writes ONLY to `lessons-learned.md` and `forgotten/<date>.md`. Enforced by `test_sleep_write_boundary.py`. `trash/` directory is outside `/sleep --purge` scope (gap-seven narrowed: 8 live `*.txt` sentinel families under `memory/` are now covered via `/sleep --purge --sentinels`; `trash/<date>/` remains the residual gap). Directory tree + `forgotten/<date>.md` entry-format + `> Source:` restore anchor: `__QUOIN_HOME__/memory/lifecycle-guide.md`.
