---
name: thorough_plan
description: "Triages tasks by size (Small/Medium/Large) and orchestrates the appropriate planning path. Small tasks get a single-pass /plan (no critic loop). Medium tasks run the plan→critic→revise cycle with Sonnet revision. Large tasks (or 'strict:' prefix) run all-Opus with up to 5 rounds. Use this skill for: /thorough_plan, 'plan this', 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Supports size tags (small:/medium:/large:), strict: prefix, and max_rounds: N override. Always the entry point for planned work — routes automatically based on task size."
model: opus
---

# Thorough Plan — Orchestrator

This skill orchestrates the planning convergence loop by invoking sub-skills — `/plan`, `/critic`, and `/revise` (or `/revise-fast`) — based on mode and round. See "Model selection per round" for details. It does not do the planning, critiquing, or revising itself — it coordinates the agents that do.

## Session bootstrap

On start:
1. Read `.workflow_artifacts/memory/lessons-learned.md` for past insights
2. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `thorough-plan`

## Setup

### 1. Determine the task subfolder and stage

Before starting the loop, establish the working directory:

- Ask the user for a descriptive task name if not obvious. Use kebab-case
  (`auth-refactor`, `payment-migration`, `api-v2-endpoints`).
- Detect whether the user's invocation includes a stage qualifier:
  - Explicit form: `stage <N> of <task>` (e.g., `stage 3 of quoin-foundation`)
    → set `<stage>` = N (integer).
  - Named form: `stage <name> of <task>` (e.g., `stage model-dispatch of quoin`)
    → set `<stage>` = name (string); the resolver looks up N from
    `<task-name>/architecture.md`'s `## Stage decomposition` section.
  - No qualifier → `<stage>` = None (legacy / single-stage layout).
- Compute the working directory by running:
    `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]`
  This returns an absolute path. Create the folder if it doesn't exist:
    `mkdir -p "<task_dir>"`
- The architecture and cost-ledger always live at the task root, regardless of
  stage: `.workflow_artifacts/<task-name>/architecture.md` and
  `.workflow_artifacts/<task-name>/cost-ledger.md`.
- Pass `<task_dir>` (NOT the bare task name) to `/plan`, `/critic`, `/revise`,
  `/revise-fast` so they all write into the same resolved subfolder.

Error handling: if `path_resolve.py` exits with code 2 (any rule-1/2/2a/2b/2c/2d
ValueError), interpret the stderr message as "user-recoverable input ambiguity" and:
  (a) display the stderr message verbatim to the user;
  (b) fall back to the task root (rule-3 path: `<project_root>/.workflow_artifacts/<task-name>/`);
  (c) ask the user to disambiguate by re-invoking with the integer form `stage <N> of <task>`.
Do NOT abort the orchestration on exit-code-2.

### 2. Gather initial context

Collect and pass to `/plan`:

- The user's description of what needs to be built
- Path to `architecture.md` if `/architect` was run first
- Paths to all relevant repositories in the project folder
- Any constraints, preferences, or context the user mentioned

### 3. Parse runtime overrides and determine task profile

Before starting the loop, scan the user's task description for runtime overrides. Parse in this order:

1. **`strict:`** (case-insensitive): If the task description begins with the literal token `strict:`, enable strict mode for this run. Strip the `strict:` token from the description. Strict mode is equivalent to the Large task profile (all-Opus model selection, `max_rounds` defaults to 5). The user can still override `max_rounds` via the `max_rounds: N` token even in strict mode. If `strict:` is present, set task profile to **Large** and skip step 1b.

1b. **Task profile tag** (`small:`, `medium:`, `large:`, case-insensitive): If the task description begins with one of these tokens, set the task profile accordingly and strip the token. If `large:` is specified, it is equivalent to `strict:` (all-Opus, max 5). If no profile tag is found and `strict:` was not found, proceed to step 1c.

1c. **Auto-classification** (only if no explicit tag from steps 1 or 1b): Based on the task description and any available context (architecture docs, referenced files), classify the task as Small, Medium, or Large using the triage criteria (see "Task triage criteria" section below). Present the classification to the user with a brief rationale and ask for confirmation. If the user disagrees, use their choice. If the user does not respond or says "ok" / "yes" / "go", use the auto-classification. **When in doubt, default to Medium** — it is the safe middle ground.

2. **`max_rounds: N`** (case-insensitive, N = positive integer): If found, use N as the maximum round cap for this run. Strip the `max_rounds: N` token from the description before passing it to the planner skill. If not found, use the default cap (4 for Medium, 5 for Large/strict). If the value is not a positive integer (e.g., zero, negative, or non-numeric), ignore the override and use the default.

3. **Apply task profile defaults.** Based on the determined profile, set defaults that were not already overridden:

   | Profile | Model mode | Default max_rounds | Critic loop | Gate level |
   |---------|-----------|-------------------|-------------|------------|
   | Small | N/A (single pass) | N/A | Skip | Smoke (plan) + Standard (post-implement) + Full (pre-merge) |
   | Medium | Normal (Opus /plan, Sonnet /revise-fast, Opus /critic) | 4 | Full | Smoke (plan) + Standard (post-implement) + Full (pre-merge) |
   | Large | Strict (all Opus) | 5 | Full | Smoke (plan) + Full (post-implement) + Full (pre-merge) |

   If `max_rounds: N` was explicitly provided, it overrides the profile's default.

   **Important:** For Small-profile tasks, `max_rounds` is ignored — there is no critic loop and therefore no round cap applies. If `max_rounds: N` was parsed in step 2, discard it when the profile is Small.

   **Note on auto-classification latency:** Auto-classification (step 1c) adds one user confirmation round-trip before planning begins. Users who want to skip this delay can use explicit tags (`small:`, `medium:`, `large:`).

Examples:
- `/thorough_plan fix the null check in auth.ts` — auto-classifies (likely Small), asks for confirmation
- `/thorough_plan small: fix the null check in auth.ts` — Small profile, single-pass plan, no critic loop
- `/thorough_plan medium: add retry logic to the payment client` — Medium profile, standard critic loop (max 4)
- `/thorough_plan large: redesign the auth token refresh flow` — Large profile (= strict mode), all-Opus, max 5
- `/thorough_plan max_rounds: 6 this migration is gnarly` — auto-classified, cap overridden to 6
- `/thorough_plan strict: handle the auth migration carefully` — Large profile (strict mode), cap = 5
- `/thorough_plan strict: max_rounds: 3 quick but safe` — Large profile, cap = 3
- `/thorough_plan small: max_rounds: 2 add the config endpoint` — Small profile; max_rounds parsed then discarded (no loop)

### 3b. Task triage criteria

Use these criteria when auto-classifying a task (step 1c above) or when verifying a user's explicit tag makes sense:

**Small** — Single-concern, localized changes with no integration risk:
- Touches 1-3 closely related files in a single module
- No integration points affected (no API contract changes, no cross-service calls)
- Well-understood pattern: bug fix, config change, add simple endpoint, rename, typo fix
- Failure is localized — affects one feature, easy to detect and revert
- No data model changes, no auth changes, no shared-state modifications

**Medium** — Multi-file changes with moderate complexity or some integration risk:
- Touches multiple files across 1-2 modules or services
- May affect integration points but contracts remain backward-compatible
- Some unknowns but similar work has been done in this codebase before
- Failure affects a subsystem but is contained and recoverable
- Includes adding a new feature with tests, refactoring a module, adding retry/resilience logic

**Large** — Cross-cutting, high-risk, or architecturally significant changes:
- Touches multiple services, repos, or architectural layers
- Affects data consistency, authentication, authorization, or multi-service contracts
- Significant unknowns, new patterns, or involves migration of existing data/systems
- Failure could affect multiple services or all users
- Includes database migrations, auth overhauls, API versioning, payment flow changes

**When the classification is ambiguous, choose the more cautious (larger) profile.** A Medium task that runs the full critic loop costs a few extra dollars; a Large task misclassified as Small can ship bugs.

### 4. Model selection per round

The orchestrator selects which skill variant to spawn based on the round number and whether strict mode is active:

| Round | Role | Normal mode (default) | Strict mode |
|-------|------|-----------------------|-------------|
| 1 | Planner | `/plan` (Opus) | `/plan` (Opus) |
| 1 | Critic | `/critic` (Opus) | `/critic` (Opus) |
| 2+ | Reviser | `/revise-fast` (Sonnet) | `/revise` (Opus) |
| 2+ | Critic | `/critic` (Opus) | `/critic` (Opus) |

**Key rules:**
- `/plan` (round 1) is ALWAYS Opus, in every mode. The initial plan sets the structural foundation; a strong first plan reduces iteration.
- `/critic` is ALWAYS Opus, every round, in every mode. Never tiered.
- In normal mode, `/revise` rounds (2+) use Sonnet via `/revise-fast`. In strict mode, they use Opus `/revise`.
- The `-fast` variant (`/revise-fast`) is content-identical to its Opus counterpart — same instructions, same output format, different model.

## Small-profile routing (no loop)

If the task profile is Small, do NOT enter the critic loop. Instead:

1. Invoke `/plan` (Opus) — same as round 1 of the normal loop. Output: `current-plan.md`.
2. Run a smoke gate (plan artifact exists, has tasks with file paths and acceptance criteria).
3. Add the convergence summary to the top of `current-plan.md` with `Task profile: Small`, `Rounds: 1`, and `Key revisions: N/A — single-pass plan`.
4. Inform the user: "Task classified as Small — single-pass plan produced. Plan is ready at `<task_dir>/current-plan.md`." (where `<task_dir>` was resolved in Setup §1 via `path_resolve.py`)
5. **STOP.** Do not invoke `/implement`. Wait for the user.

## Medium and Large profiles (critic loop)

```
Round 1:
  /plan    → produces current-plan.md
  /critic  → (FRESH SESSION) reads plan + code → produces critic-response-1.md

  If verdict = PASS → done
  If verdict = REVISE → continue

Round 2:
  /revise  → reads critic-response-1.md → updates current-plan.md
  /critic  → (FRESH SESSION) reads updated plan + code → produces critic-response-2.md

  If verdict = PASS → done
  If verdict = REVISE → continue

...repeat up to Round 4 (or max_rounds if overridden)
```

> **Note:** The diagram above shows `/plan` and `/revise` generically. The actual skill variant spawned each round depends on mode (normal vs. strict) — see the "Model selection per round" table.

### Invoking each agent

**`/plan` (Round 1 only)**
- Always spawn `/plan` (Opus) — the initial plan is always Opus-quality regardless of mode
- Pass all context: architecture docs, user requirements, repo paths
- Output: `<task_dir>/current-plan.md` (where `<task_dir>` was resolved in Setup §1 via `path_resolve.py`)

**`/critic` (every round)**
- **MUST spawn as a new agent session** — fresh context is essential for unbiased critique
- Always Opus. Never tiered. This is non-negotiable.
- Pass: path to `current-plan.md`, path to the project folder (so it can read actual code)
- Output: `<task_dir>/critic-response-<round>.md`

**`/revise` or `/revise-fast` (rounds 2+)**
- **MUST spawn as a new agent session** (same mechanism used for /critic above) — fresh context prevents anchoring on prior orchestrator chatter
- Spawn `/revise-fast` (Sonnet) in normal mode, or `/revise` (Opus) in strict mode — see "Model selection per round" table above.
- Pass: path to `<task_dir>/current-plan.md`, path to latest `<task_dir>/critic-response-<N>.md`, and paths to any files the critic flagged as needing re-examination
- Output: updated `current-plan.md` (in place)

### Convergence rules

The loop stops when ANY of these is true:

1. **Critic gives PASS** — no CRITICAL or MAJOR issues. Plan is ready.
2. **Max rounds reached (default: 4)** — inform the user of remaining issues. The plan may have inherent constraints.
3. **Stuck in a loop** — if round N's critic has the same dominant `surface_family` class among structural CRIT/MAJ issues as round N-1 (same-class recurrence), escalate to the user with the repeated class, the specific issues, and three options: (a) continue revising, (b) add a structural canary task to the plan, (c) accept the plan as-is and proceed to implement. Do NOT auto-continue.

### After each critic round — classify and decide

After reading each critic response, run:

```
python3 ~/.claude/scripts/classify_critic_issues.py \
  --critic-response <task_dir>/critic-response-<N>.md
```

This emits a verdict (`CONTINUE-LOOP`) on line 1, then a JSON summary with fields `structural_count`, `mechanical_count`, and `issues[]` (each with `id`, `severity`, `title`, `surface_family`).

**Same-class detection:** If round N's `structural_count` > 0 AND round N-1's `structural_count` > 0 AND the dominant surface families match (both rounds share the same top-1 `surface_family` among structural CRIT/MAJ issues), escalate to the user as described in rule 3 above. Do NOT auto-continue.

### Between rounds

After each critic round, before continuing:

- Read the critic response yourself (as orchestrator)
- Run the classifier (see `### After each critic round — classify and decide` above) to detect same-class recurrence
- Briefly inform the user: "Round N complete — critic found X critical, Y major issues. Proceeding to revise." or "Round N complete — critic passed. Plan is ready."

## Final output

When converged, add a convergence summary to the top of `current-plan.md`:

```markdown
## Convergence Summary
- **Task profile:** <Small | Medium | Large>
- **Rounds:** <N> (Small tasks: 1, single pass)
- **Final verdict:** PASS
- **Key revisions:** <what the main themes of revision were across rounds, or "N/A — single-pass plan" for Small>
- **Remaining concerns:** <any MINOR issues not addressed, or none>
```

For Small-profile tasks that took the single-pass path, the convergence summary still appears at the top of `current-plan.md` but with `Rounds: 1` and `Key revisions: N/A — single-pass plan`. This signals to downstream skills that the plan was not critic-reviewed.

Then spawn `/gate` as a subagent session (never inline — subagent dispatch is required so gate/SKILL.md is read and Step 5 audit-log persistence fires) to present automated checks and a summary to the user.

After the gate, inform the user:
- The plan is ready at `<task_dir>/current-plan.md`
- Summary of what was planned (high-level, 3-5 bullet points)
- How many rounds it took and what the main themes were
- Any remaining concerns or decisions the user needs to make

**STOP HERE.** Do NOT invoke `/implement`. Do NOT offer to start implementing. The user must explicitly type `/implement` to proceed. This is a hard rule — implementation requires a conscious human decision.

## File structure at completion

```
<project-folder>/.workflow_artifacts/<task-name>/
├── architecture.md          (from /architect, if exists)
├── current-plan.md          (final converged plan)
├── critic-response-1.md     (round 1 critic)
├── critic-response-2.md     (round 2 critic, if needed)
├── ...
└── critic-response-N.md     (final round critic)
```

## Important behaviors

- **You are the orchestrator, not the planner.** Don't produce plan content yourself — invoke `/plan`, `/critic`, `/revise` (or `/revise-fast`).
- **Critic MUST be a fresh session.** This is non-negotiable. Same-agent critique is biased and weak.
- **Keep the user informed.** Brief status updates between rounds. Don't go silent for 10 minutes.
- **Detect loops early.** After each critic round, run `classify_critic_issues.py` (without `--enable-bailout`) and compare the dominant `surface_family` of structural issues against the previous round. If the same class recurs, escalate to the user — ask whether to continue revising, add a canary task, or accept the plan as-is.
- **Pass context explicitly.** Each agent starts with limited knowledge. Give them the file paths and repo locations they need.
