# Implementation Plan: Stage 3 — Planner-Side Model Tiering

## Convergence Summary
- **Rounds:** 2
- **Final verdict:** PASS
- **Key revisions:** Round 1 critic found 3 MAJOR issues — missing `-fast` references in intro/loop diagram/important behaviors (MAJ-1), inconsistent subsection header naming (MAJ-2), stale `/plan` reference in max_rounds stripping (MAJ-3). All addressed in revision. Round 2 critic verified all fixes, found 2 new MINOR issues (markdown nesting cosmetics, line number staleness after insertions — both non-blocking).
- **Remaining concerns:** MIN-R2-1 (triple-backtick nesting in Task 5a — verify during implementation), MIN-R2-2 (line numbers shift after Tasks 3-4 — old_text matching handles this correctly)

## Objective

Reduce `/thorough_plan` loop cost by running `/plan` (round 1) and `/revise` (rounds 2-3) on Sonnet instead of Opus, while keeping `/critic` on Opus every round. Provide a `strict:` escape hatch for all-Opus when quality demands it. The mechanism is two new skill files (`plan-fast`, `revise-fast`) plus orchestrator changes in `thorough_plan/SKILL.md`.

## Scope

**In scope:**
- Create `dev-workflow/skills/plan-fast/SKILL.md` (Sonnet copy of `/plan`)
- Create `dev-workflow/skills/revise-fast/SKILL.md` (Sonnet copy of `/revise`)
- Update `dev-workflow/skills/thorough_plan/SKILL.md` with `strict:` parsing and per-round model selection
- Update `dev-workflow/CLAUDE.md` and `~/.claude/CLAUDE.md` model assignment tables

**Out of scope:**
- Critic tiering (critic stays on Opus always)
- Task triage / shortcut paths (Stage 4)
- `/architect` scan/synthesize split (Stage 1, C7)
- Haiku for state-management skills (Stage 5)

## Pre-implementation checklist

- [x] Stage 2 changes (E0, B1, B3) are merged and in production
- [x] `/revise` already spawns as a subagent (E0 fix enables model switching)
- [x] `max_rounds: N` override is working (Stage 2)
- [ ] Verify current branch is clean and up to date with main

---

## Tasks

### Task 1: Create `/plan-fast` skill file

**Description:** Create a new skill directory and SKILL.md that is a content copy of `/plan` with `model: sonnet` frontmatter. The body instructions are identical to `plan/SKILL.md` except the model requirement section is updated.

**Files:** Create `dev-workflow/skills/plan-fast/SKILL.md`

**Content:** Copy of `dev-workflow/skills/plan/SKILL.md` with these changes:

1. Frontmatter `model:` changed from `opus` to `sonnet`
2. Frontmatter `name:` changed from `plan` to `plan-fast`
3. Frontmatter `description:` updated to reflect Sonnet and its role
4. "Model requirement" section updated

**Exact file content:**

```markdown
---
name: plan-fast
description: "Fast variant of /plan using Sonnet for cost-efficient planning. Content-identical to /plan but runs on Sonnet instead of Opus. Used by /thorough_plan in default (non-strict) mode for round 1. Not intended for direct user invocation — use /plan for standalone planning."
model: sonnet
---

# Plan

You are a senior technical planner. You produce detailed, implementation-ready plans that a developer can follow without ambiguity. You are concrete (file paths, function names, schemas), thorough (edge cases, failure modes), and practical (ordered for early feedback and risk reduction).

## Session bootstrap

This skill may run in a fresh chat session. On start:
1. Read `memory/lessons-learned.md` for past insights — apply relevant lessons
2. Read `memory/sessions/` for active session state
3. Read the task subfolder (`architecture.md`, any prior `current-plan.md`, `critic-response-*.md`)
4. Then proceed with planning

## Model requirement

This skill runs on Sonnet for cost efficiency. It is a fast variant of `/plan` (Opus). The instructions and output format are identical — only the model differs.

## Inputs

The plan may start from:

- An architectural document produced by `/architect` (preferred — read it first)
- A stage description from an architecture decomposition
- A direct user request describing what needs to be built
- An existing codebase that needs modification
- A previous critic response that prompted revision (see `/revise`)

Regardless of input, always read the relevant code and documents before planning. Don't plan in a vacuum.

## Planning process

### 1. Gather context

Before writing anything:

- Read `memory/lessons-learned.md` — apply past insights to avoid repeating mistakes
- Read architecture docs if they exist (`<task-folder>/architecture.md`)
- Read the existing codebase — scan relevant source files, tests, configs
- Read any critic responses from prior rounds if this is part of a `/thorough_plan` cycle
- Search the web if you need to understand external APIs, library behavior, or best practices
- Ask the user clarifying questions if requirements are ambiguous

### 2. Produce the plan

Save to `<project-folder>/<task-name>/current-plan.md`:

```markdown
# Implementation Plan: <title>

## Objective
<What we're building and why, in 2-3 sentences>

## Scope
**In scope:** <explicit list>
**Out of scope:** <explicit exclusions>

## Pre-implementation checklist
- [ ] <Required access, permissions, API keys>
- [ ] <Dependencies to install or upgrade>
- [ ] <Environment setup>
- [ ] <Feature flags to create>

## Tasks

### Task 1: <title>
**Description:** <what to do>
**Files:** <create or modify — specific paths>
**Acceptance criteria:**
- <How you know it's done>
**Effort:** small | medium | large
**Depends on:** none | Task N

### Task 2: ...
(continue for all tasks)

## Integration analysis

### <Integration point 1>
- **Current behavior:** <how it works now>
- **New behavior:** <what changes>
- **Failure modes:** <what can go wrong, how to handle>
- **Backward compatibility:** <can this deploy independently?>
- **Coordination:** <teams/services to notify>

## Risk analysis

| Risk | Likelihood | Impact | Mitigation | Rollback |
|------|-----------|--------|------------|----------|
| <risk> | low/med/high | low/med/high | <how to prevent> | <how to undo> |

## Testing strategy

### Unit tests
- <function/module>: <what to test>

### Integration tests
- <interaction>: <what to verify>

### E2E tests
- <user flow>: <what to exercise>

### Edge cases
- <specific scenario to cover>

## Implementation order
<Numbered sequence optimized for early feedback, risk reduction, minimal WIP>
```

## Task subfolder naming

Derive a descriptive kebab-case name from the task. Ask the user if not obvious. Examples: `auth-refactor`, `payment-migration`, `api-v2-endpoints`.

## Save session state

Before finishing, write or update `memory/sessions/<date>-<task-name>.md` with:
- **Status:** `in_progress`
- **Current stage:** `plan`
- **Completed in this session:** what the plan covers
- **Unfinished work:** anything deferred or not yet planned
- **Decisions made:** key choices and their rationale

This is what `/end_of_day` reads to consolidate the day's work. Without it, this session is invisible to the daily rollup.

## Important behaviors

- **Be concrete.** File paths, function signatures, data shapes. "Add a new service" is not a task. "Create `src/services/payment.service.ts` implementing `processRefund(orderId: string): Promise<RefundResult>`" is a task.
- **Read actual code.** Verify your assumptions against the codebase. Don't guess at file structures or API shapes.
- **Integration points get extra scrutiny.** Most production incidents come from integration failures. Trace data flows end-to-end.
- **Each task is independently reviewable.** No mega-tasks. Each produces a testable, reviewable unit of work.
- **De-risk upfront.** If something is uncertain, the plan should include a spike/POC as an early task, not hand-wave over it.
- **Testing is not optional.** Every task that touches code should have corresponding test expectations.
```

**Acceptance criteria:**
- File exists at `dev-workflow/skills/plan-fast/SKILL.md`
- Frontmatter has `model: sonnet`, `name: plan-fast`
- Body is identical to `plan/SKILL.md` except the "Model requirement" section
- The skill appears in Claude Code's skill listing

**Effort:** small
**Depends on:** none

---

### Task 2: Create `/revise-fast` skill file

**Description:** Create a new skill directory and SKILL.md that is a content copy of `/revise` with `model: sonnet` frontmatter.

**Files:** Create `dev-workflow/skills/revise-fast/SKILL.md`

**Exact file content:**

```markdown
---
name: revise-fast
description: "Fast variant of /revise using Sonnet for cost-efficient plan revision. Content-identical to /revise but runs on Sonnet instead of Opus. Used by /thorough_plan in default (non-strict) mode for rounds 2-3. Not intended for direct user invocation — use /revise for standalone revision."
model: sonnet
---

# Revise

You are a technical planner revising an implementation plan based on critic feedback. You address issues thoroughly without losing what was already good. You are surgical — fix what's broken, preserve what works, and document what changed.

## Session bootstrap

This skill may run in a fresh session. On start:
1. Read the task subfolder: `current-plan.md`, latest `critic-response-*.md`, and any prior critic responses
2. Re-read relevant source code if the critic flagged incorrect assumptions
3. Then proceed with revision

## Model requirement

This skill runs on Sonnet for cost efficiency. It is a fast variant of `/revise` (Opus). The instructions and output format are identical — only the model differs.

## Process

### 1. Read the inputs

- Read `<project-folder>/<task-name>/current-plan.md` — the current plan
- Read `<project-folder>/<task-name>/critic-response-<latest>.md` — the most recent critic feedback
- Read any prior critic responses to understand the trajectory of revisions
- Re-read relevant source code if the critic flagged incorrect assumptions about the codebase

### 2. Triage the issues

From the critic response, categorize:

- **CRITICAL issues** — must fix. These block implementation.
- **MAJOR issues** — must fix. These represent significant gaps.
- **MINOR issues** — use judgment:
  - Fix if it's quick and improves the plan
  - Note as "known limitation" if it's out of scope or a deliberate tradeoff
  - Skip if it's stylistic and doesn't affect outcomes

### 3. Revise the plan

Update `current-plan.md` with the following approach:

**For each CRITICAL and MAJOR issue:**
1. Understand what the critic is really asking for (sometimes the stated issue points to a deeper problem)
2. Read the relevant code again if needed — don't just trust your memory
3. Make the fix in the plan. This might mean:
   - Adding a missing task
   - Modifying an existing task with more detail
   - Adding error handling or failure modes to the integration analysis
   - Adding risks to the risk table
   - Adding tests to the testing strategy
   - Reordering tasks for better de-risking
   - Adding a spike/POC task for an uncertain area

**Preserve what the critic praised.** The "What's good" section tells you what to keep. Don't accidentally regress while fixing issues.

**Don't over-correct.** If the critic said "this section needs more detail," add the right amount of detail — don't triple the length of every section in response. The plan should stay focused and readable.

### 4. Add the changelog

Append a changelog entry at the bottom of `current-plan.md`:

```markdown
---

## Revision history

### Round <N> — <date>
**Critic verdict:** REVISE
**Issues addressed:**
- [CRIT-1] <title> — <how it was addressed>
- [MAJ-1] <title> — <how it was addressed>
- [MAJ-2] <title> — <how it was addressed>
**Issues noted but deferred:**
- [MIN-1] <title> — <why deferred>
**Changes summary:** <1-2 sentence overview of what changed>
```

### 5. Signal readiness

After updating the plan, the file is ready for the next critic round. If this is part of `/thorough_plan` orchestration, the orchestrator will invoke `/critic` next.

If running standalone, tell the user:
- What issues were addressed
- What was deferred and why
- Whether you recommend another critic round or if the plan feels ready

## Save session state

Before finishing, write or update `memory/sessions/<date>-<task-name>.md` with:
- **Status:** `in_progress`
- **Current stage:** `revise` (note the round number, e.g. `revise round 2`)
- **Completed in this session:** which critic issues were addressed
- **Unfinished work:** deferred issues, or "ready for /implement" if converged
- **Decisions made:** rationale for any choices made while addressing feedback

This is what `/end_of_day` reads to consolidate the day's work. Without it, this session is invisible to the daily rollup.

## Important behaviors

- **Be surgical.** Don't rewrite sections that were fine. Targeted fixes, not scorched earth.
- **Re-read code when flagged.** If the critic said your assumptions about the code are wrong, go look at the code again. Don't just rephrase the same wrong thing.
- **Maintain plan coherence.** After multiple rounds of revision, the plan can get inconsistent. Check that task numbering, dependencies, and cross-references still make sense.
- **Track what changed.** The changelog is how the user and future rounds understand the plan's evolution. Don't skip it.
- **Know when to escalate.** If a critic issue requires an architectural change that's beyond the plan's scope, flag it to the user instead of cramming it into the plan.
```

**Acceptance criteria:**
- File exists at `dev-workflow/skills/revise-fast/SKILL.md`
- Frontmatter has `model: sonnet`, `name: revise-fast`
- Body is identical to `revise/SKILL.md` except the "Model requirement" section

**Effort:** small
**Depends on:** none

---

### Task 3: Update `/thorough_plan` — add `strict:` parsing

**Description:** Add `strict:` prefix detection to the runtime overrides section of `thorough_plan/SKILL.md`. This is parsed alongside the existing `max_rounds: N` override from Stage 2.

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`
**Section:** "### 3. Parse runtime overrides" (lines 32-38)

**Old text (exact):**
```
### 3. Parse runtime overrides

Before starting the loop, scan the user's task description for runtime overrides:

- **`max_rounds: N`** (case-insensitive, N = positive integer): If found, use N as the maximum round cap for this run. Strip the `max_rounds: N` token from the description before passing it to `/plan`. If not found, use the default cap of 4. If the value is not a positive integer (e.g., zero, negative, or non-numeric), ignore the override and use the default.

Example: `/thorough_plan max_rounds: 6 this migration is gnarly, give it room` sets the cap to 6 and passes "this migration is gnarly, give it room" to `/plan`.
```

**New text:**
```
### 3. Parse runtime overrides

Before starting the loop, scan the user's task description for runtime overrides. Parse in this order:

1. **`strict:`** (case-insensitive): If the task description begins with the literal token `strict:`, enable strict mode for this run. Strip the `strict:` token from the description. Strict mode forces all-Opus model selection (see "Model selection per round" below) and defaults `max_rounds` to 5 (instead of the normal default of 4). The user can still override `max_rounds` via the `max_rounds: N` token even in strict mode.

2. **`max_rounds: N`** (case-insensitive, N = positive integer): If found, use N as the maximum round cap for this run. Strip the `max_rounds: N` token from the description before passing it to the planner skill. If not found, use the default cap (4 in normal mode, 5 in strict mode). If the value is not a positive integer (e.g., zero, negative, or non-numeric), ignore the override and use the default.

Examples:
- `/thorough_plan max_rounds: 6 this migration is gnarly` — normal mode, cap = 6
- `/thorough_plan strict: handle the auth migration carefully` — strict mode, cap = 5
- `/thorough_plan strict: max_rounds: 3 quick but safe` — strict mode, cap = 3
```

**Effort:** small
**Depends on:** none

---

### Task 4: Update `/thorough_plan` — model selection per round

**Description:** Add a new section to `thorough_plan/SKILL.md` that defines which skill variant to spawn based on (round number, strict flag). This goes between the "Parse runtime overrides" section and "The loop" section.

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`

**Insert after the end of section "### 3. Parse runtime overrides" (after the examples line), before "## The loop":**

**New text to insert:**
```

### 4. Model selection per round

The orchestrator selects which skill variant to spawn based on the round number and whether strict mode is active:

| Round | Role | Normal mode (default) | Strict mode |
|-------|------|-----------------------|-------------|
| 1 | Planner | `/plan-fast` (Sonnet) | `/plan` (Opus) |
| 1 | Critic | `/critic` (Opus) | `/critic` (Opus) |
| 2-3 | Reviser | `/revise-fast` (Sonnet) | `/revise` (Opus) |
| 2-3 | Critic | `/critic` (Opus) | `/critic` (Opus) |
| 4+ (final) | Reviser | `/revise` (Opus) | `/revise` (Opus) |
| 4+ (final) | Critic | `/critic` (Opus) | `/critic` (Opus) |

**Key rules:**
- `/critic` is ALWAYS Opus, every round, in every mode. Never tiered.
- In normal mode, only the final allowed round escalates `/revise` to Opus. If `max_rounds` is overridden to a value less than 4, the final round still uses Opus `/revise`.
- In strict mode, every role uses its Opus variant. This is the "pay full price for maximum quality" option.
- The `-fast` variants (`/plan-fast`, `/revise-fast`) are content-identical to their Opus counterparts — same instructions, same output format, different model.

```

**Effort:** small
**Depends on:** Task 1, Task 2 (the -fast skill files must exist for the orchestrator to reference them)

---

### Task 5: Update `/thorough_plan` — invoking each agent section

**Description:** Update the "Invoking each agent" subsection to reflect model tiering. The current text hardcodes "Invoke with the strongest model (Opus)" — it needs to reference the model selection table.

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`
**Section:** "### Invoking each agent" (lines 59-73 in current file)

**Old text (exact):**
```
### Invoking each agent

**`/plan` (Round 1 only)**
- Invoke with the strongest model (Opus)
- Pass all context: architecture docs, user requirements, repo paths
- Output: `<task-folder>/current-plan.md`

**`/critic` (every round)**
- **MUST spawn as a new agent session** — fresh context is essential for unbiased critique
- Pass: path to `current-plan.md`, path to the project folder (so it can read actual code)
- Output: `<task-folder>/critic-response-<round>.md`

**`/revise` (rounds 2+)**
- **MUST spawn as a new agent session** (same mechanism used for /critic above) — fresh context prevents anchoring on prior orchestrator chatter. The plan document (`current-plan.md`) encodes the plan's intent; a fresh reviser reading it + critic feedback is strictly better than one carrying stale context.
- Pass: path to `current-plan.md`, path to latest `critic-response-<N>.md`, and paths to any files the critic flagged as needing re-examination
- Output: updated `current-plan.md` (in place)
```

**New text:**
```
### Invoking each agent

**`/plan` or `/plan-fast` (Round 1 only)**
- Spawn `/plan-fast` (Sonnet) in normal mode, or `/plan` (Opus) in strict mode — see "Model selection per round" table above
- Pass all context: architecture docs, user requirements, repo paths
- Output: `<task-folder>/current-plan.md`

**`/critic` (every round)**
- **MUST spawn as a new agent session** — fresh context is essential for unbiased critique
- Always Opus. Never tiered. This is non-negotiable.
- Pass: path to `current-plan.md`, path to the project folder (so it can read actual code)
- Output: `<task-folder>/critic-response-<round>.md`

**`/revise` or `/revise-fast` (rounds 2+)**
- **MUST spawn as a new agent session** (same mechanism used for /critic above) — fresh context prevents anchoring on prior orchestrator chatter
- Spawn `/revise-fast` (Sonnet) for rounds 2 through max_rounds-1, or `/revise` (Opus) for the final allowed round — see "Model selection per round" table above. In strict mode, always `/revise` (Opus).
- Pass: path to `current-plan.md`, path to latest `critic-response-<N>.md`, and paths to any files the critic flagged as needing re-examination
- Output: updated `current-plan.md` (in place)
```

**Effort:** small
**Depends on:** Task 4 (references the model selection table)

---

### Task 5a: Update remaining `/plan` and `/revise` references in `thorough_plan/SKILL.md`

**Description:** Three other locations in `thorough_plan/SKILL.md` reference `/plan` and `/revise` by name without acknowledging the `-fast` variants. After Tasks 3-5, these will be contradictory. Update them for consistency.

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`

**Change 1 — Introductory sentence (line 9):**

**Old text (exact):**
```
This skill orchestrates the planning convergence loop by invoking three sub-skills in sequence: `/plan`, `/critic`, and `/revise`. It does not do the planning, critiquing, or revising itself — it coordinates the agents that do.
```

**New text:**
```
This skill orchestrates the planning convergence loop by invoking sub-skills — `/plan` (or `/plan-fast`), `/critic`, and `/revise` (or `/revise-fast`) — based on mode and round. See "Model selection per round" for details. It does not do the planning, critiquing, or revising itself — it coordinates the agents that do.
```

**Change 2 — Loop diagram (lines 41-55). Add a note below the diagram:**

**Old text (exact):**
```
...repeat up to Round 4 (or max_rounds if overridden)
```
```

**New text:**
```
...repeat up to Round 4 (or max_rounds if overridden)
```

> **Note:** The diagram above shows `/plan` and `/revise` generically. The actual skill variant spawned each round depends on mode (normal vs. strict) — see the "Model selection per round" table.
```

**Change 3 — Important behaviors section (line 127):**

**Old text (exact):**
```
- **You are the orchestrator, not the planner.** Don't produce plan content yourself — invoke `/plan`, `/critic`, `/revise`.
```

**New text:**
```
- **You are the orchestrator, not the planner.** Don't produce plan content yourself — invoke `/plan` (or `/plan-fast`), `/critic`, `/revise` (or `/revise-fast`).
```

**Acceptance criteria:**
- Line 9 mentions both `/plan-fast` and `/revise-fast` variants and references the model selection section
- The loop diagram has a note pointing readers to the model selection table
- Line 127 mentions the `-fast` variants
- No other references to `/plan` or `/revise` in the file are left ambiguous (the "Invoking each agent" section is already handled by Task 5)

**Effort:** small
**Depends on:** Task 4 (the model selection table must exist for the references to make sense)

---

### Task 6: Update `/thorough_plan` frontmatter description

**Description:** Update the frontmatter description to mention model tiering and strict mode.

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`
**Line:** 3

**Old text (exact):**
```
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning using the strongest model (Opus). Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 4 rounds until convergence (override with max_rounds: N). Use this when you want the highest-quality plan, not just a quick one."
```

**New text:**
```
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning. Uses Sonnet for planning/revision and Opus for critique by default; use 'strict:' prefix for all-Opus. Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 4 rounds until convergence (override with max_rounds: N, or 'strict:' for all-Opus + 5 rounds). Use this when you want the highest-quality plan, not just a quick one."
```

**Effort:** small
**Depends on:** none

---

### Task 7: Update `dev-workflow/CLAUDE.md` model assignments table

**Description:** Add `/plan-fast` and `/revise-fast` to the model assignments table and add a note about `/thorough_plan`'s tiering behavior.

**File:** `dev-workflow/CLAUDE.md`
**Section:** "## Model assignments" table

**Old text (exact):**
```
| /plan | Opus | Detailed planning requires strong reasoning |
| /critic | Opus | Finding real issues requires deep understanding |
| /revise | Opus | Addressing critic feedback requires strong reasoning |
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop |
```

**New text:**
```
| /plan | Opus | Detailed planning requires strong reasoning (used in strict mode and standalone) |
| /plan-fast | Sonnet | Cost-efficient planning (used by /thorough_plan in normal mode, round 1) |
| /critic | Opus | Finding real issues requires deep understanding (never tiered) |
| /revise | Opus | Addressing critic feedback requires strong reasoning (used in strict mode and final round) |
| /revise-fast | Sonnet | Cost-efficient revision (used by /thorough_plan in normal mode, rounds 2-3) |
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop (tiers planner/reviser to Sonnet by default; use strict: for all-Opus) |
```

**Effort:** small
**Depends on:** none

---

### Task 8: Update `~/.claude/CLAUDE.md` model assignments table

**Description:** Same change as Task 7 but in the global CLAUDE.md.

**File:** `~/.claude/CLAUDE.md`
**Section:** "## Model assignments" table

**Old text (exact):**
```
| /plan | Opus | Detailed planning requires strong reasoning |
| /critic | Opus | Finding real issues requires deep understanding |
| /revise | Opus | Addressing critic feedback requires strong reasoning |
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop |
```

**New text:**
```
| /plan | Opus | Detailed planning requires strong reasoning (used in strict mode and standalone) |
| /plan-fast | Sonnet | Cost-efficient planning (used by /thorough_plan in normal mode, round 1) |
| /critic | Opus | Finding real issues requires deep understanding (never tiered) |
| /revise | Opus | Addressing critic feedback requires strong reasoning (used in strict mode and final round) |
| /revise-fast | Sonnet | Cost-efficient revision (used by /thorough_plan in normal mode, rounds 2-3) |
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop (tiers planner/reviser to Sonnet by default; use strict: for all-Opus) |
```

**Effort:** small
**Depends on:** none

---

### Task 9: Add sync-check documentation to both -fast skill files

**Description:** Add a comment block at the top of each -fast SKILL.md body (after the frontmatter) warning maintainers to keep the file in sync with its Opus counterpart. This addresses risk R9 (drift over time).

**File:** `dev-workflow/skills/plan-fast/SKILL.md` (add after frontmatter `---`)
**File:** `dev-workflow/skills/revise-fast/SKILL.md` (add after frontmatter `---`)

**Insert immediately after the closing `---` of the frontmatter in each file:**

For `plan-fast/SKILL.md`:
```

<!-- SYNC WARNING: This file must stay in sync with plan/SKILL.md.
     The ONLY intentional differences are: frontmatter (name, description, model) and the "Model requirement" section.
     When editing plan/SKILL.md, apply the same changes here. When editing this file's body, apply changes to plan/SKILL.md too.
     To check: diff <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan/SKILL.md) <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan-fast/SKILL.md)
     Expected diff: only the "Model requirement" section. -->

```

For `revise-fast/SKILL.md`:
```

<!-- SYNC WARNING: This file must stay in sync with revise/SKILL.md.
     The ONLY intentional differences are: frontmatter (name, description, model) and the "Model requirement" section.
     When editing revise/SKILL.md, apply the same changes here. When editing this file's body, apply changes to revise/SKILL.md too.
     To check: diff <(sed -n '/^# Revise/,$p' dev-workflow/skills/revise/SKILL.md) <(sed -n '/^# Revise/,$p' dev-workflow/skills/revise-fast/SKILL.md)
     Expected diff: only the "Model requirement" section. -->

```

**Effort:** small
**Depends on:** Task 1, Task 2

---

## Integration Analysis

### Integration point 1: `/thorough_plan` → `/plan-fast` / `/plan`

- **Current behavior:** `/thorough_plan` always spawns `/plan` (Opus) for round 1
- **New behavior:** Spawns `/plan-fast` (Sonnet) in normal mode, `/plan` (Opus) in strict mode
- **Failure modes:** (a) If `/plan-fast` skill file is missing or malformed, the spawn will fail. The orchestrator should fall back to `/plan` (Opus) and log a warning. (b) If Sonnet produces a lower-quality initial plan, the critic (Opus) catches issues in the same round — the loop self-corrects.
- **Backward compatibility:** Existing `/plan` skill is unchanged. Users who invoke `/plan` directly still get Opus. Only `/thorough_plan`'s internal routing changes.
- **Coordination:** None — single-repo change.

### Integration point 2: `/thorough_plan` → `/revise-fast` / `/revise`

- **Current behavior:** `/thorough_plan` always spawns `/revise` (Opus) for rounds 2+
- **New behavior:** Spawns `/revise-fast` (Sonnet) for rounds 2 through max_rounds-1, `/revise` (Opus) for the final round. In strict mode, always `/revise` (Opus).
- **Failure modes:** Same as above — missing skill file or lower quality. The critic catches quality issues; the final Opus round acts as a safety net.
- **Backward compatibility:** Existing `/revise` skill is unchanged.

### Integration point 3: `strict:` parsing interplay with `max_rounds: N`

- **Current behavior:** Only `max_rounds: N` is parsed (Stage 2)
- **New behavior:** `strict:` is parsed first, then `max_rounds: N`. `strict:` changes the default max_rounds from 4 to 5 but `max_rounds: N` can override it.
- **Failure modes:** Edge case — `strict:` appearing in the middle of the description (not at the start) should NOT trigger strict mode. The instruction says "begins with the literal token `strict:`" which is unambiguous.
- **Backward compatibility:** Existing invocations without `strict:` work identically to before. The `max_rounds: N` override from Stage 2 is unaffected.

### Integration point 4: Skill listing / discovery

- **Current behavior:** 16 skills listed
- **New behavior:** 18 skills listed (+ `plan-fast`, `revise-fast`)
- **Failure modes:** The -fast skills will appear in Claude Code's skill listing and could be invoked directly by users. The description says "Not intended for direct user invocation" which is sufficient — if a user invokes `/plan-fast` directly, it works fine (it's just Sonnet instead of Opus).
- **Backward compatibility:** No existing skills are modified in behavior. New skills are additive.

### Interaction with Stage 2 changes

Stage 2 is already in production:
- **E0 (subagent isolation):** Required for Stage 3. `/revise` already spawns as a subagent, enabling model switching.
- **B1 (max_rounds default = 4):** Stage 3 preserves this. `strict:` mode raises the default to 5.
- **B3 (loop detection):** Unchanged. Loop detection works the same regardless of which model runs each round.
- **`max_rounds: N` override:** Preserved. Stage 3 adds `strict:` as a second override that coexists with `max_rounds: N`.

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation | Rollback |
|------|-----------|--------|------------|----------|
| R1: Sonnet `/plan-fast` produces lower-quality initial plans than Opus `/plan` | Medium | Medium | Opus `/critic` catches gaps in the same round. The loop self-corrects. If quality is consistently worse, user can invoke `strict:` mode. | Revert Task 3-6 in `thorough_plan/SKILL.md` to remove tiering. Keep -fast files (harmless). |
| R2: Sonnet `/revise-fast` misses nuanced critic feedback | Medium | Medium | Final round always uses Opus `/revise` as a safety net. Opus `/critic` re-evaluates after each revision. | Same as R1. |
| R3: `strict:` parsing error — token not stripped correctly | Low | Medium | The parsing instruction is explicit: "begins with the literal token `strict:`" and "strip the `strict:` token." LLM-executed parsing handles this naturally. | Remove `strict:` parsing from Task 3. |
| R4: `-fast` skill files not found at runtime | Low | High | Verify file creation in Task 1 and Task 2. Test with a dry-run `/thorough_plan` invocation. | Orchestrator references unchanged `/plan` and `/revise` only. |
| R5: Extra skills clutter the skill listing | Low | Low | Description says "Not intended for direct user invocation." Users can ignore them. | Delete the -fast skill directories. |
| R9: `-fast` files drift out of sync with Opus originals over time | Medium | Medium | Sync warning comments (Task 9) document the relationship and provide a diff command. Future edits to `/plan` or `/revise` should be applied to both files. A CI lint rule could enforce this but is out of scope for Stage 3. | If drift causes issues, re-copy from the Opus original. |
| R10: `strict: max_rounds: N` parsing order ambiguity | Low | Low | The instruction explicitly says "parse in this order: strict: first, max_rounds: N second." Both tokens are stripped sequentially. | Test with the specific example in Task 3. |

---

## Testing Strategy

### Test 1: Skill file creation verification

- **Method:** After creating both -fast files, verify they load correctly
- **Commands:**
  - `ls dev-workflow/skills/plan-fast/SKILL.md` — file exists
  - `ls dev-workflow/skills/revise-fast/SKILL.md` — file exists
  - Verify frontmatter: `head -5 dev-workflow/skills/plan-fast/SKILL.md` shows `model: sonnet`
  - Verify body sync: `diff <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan/SKILL.md) <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan-fast/SKILL.md)` shows only "Model requirement" section differs
- **Pass criteria:** Files exist, frontmatter correct, body difference is only the Model requirement section

### Test 2: Normal mode — default tiering (end-to-end)

- **Method:** Run `/thorough_plan` on a small task (e.g., "add a sync-check comment to a file") without `strict:` prefix
- **Verify:**
  - Round 1 spawns `/plan-fast` (check skill name in orchestrator output)
  - Round 1 critic spawns `/critic` (Opus)
  - If round 2 needed: spawns `/revise-fast` (Sonnet)
  - If final round: spawns `/revise` (Opus)
  - Plan converges normally
- **Pass criteria:** Correct skill variants used per round, plan quality acceptable

### Test 3: Strict mode — all-Opus

- **Method:** Run `/thorough_plan strict: plan a small documentation update`
- **Verify:**
  - `strict:` token is stripped from description
  - Round 1 spawns `/plan` (Opus), not `/plan-fast`
  - Default max_rounds is 5 (visible if the task goes to 5 rounds, or by checking orchestrator behavior)
  - All revisers use `/revise` (Opus)
- **Pass criteria:** All-Opus routing, `strict:` stripped, max_rounds defaults to 5

### Test 4: Strict mode + max_rounds override

- **Method:** Run `/thorough_plan strict: max_rounds: 2 simple task`
- **Verify:**
  - Both tokens stripped from description
  - All-Opus routing (strict mode)
  - Loop caps at 2 rounds (max_rounds override beats strict default of 5)
- **Pass criteria:** Both overrides coexist correctly

### Test 5: Backward compatibility — no strict, no tiering mention

- **Method:** Run `/thorough_plan max_rounds: 3 regular task` (same as Stage 2 usage)
- **Verify:**
  - `max_rounds: N` override still works (cap = 3)
  - Normal mode tiering applies (Sonnet planners, Opus critics)
  - No behavior change from Stage 2 for the `max_rounds` feature
- **Pass criteria:** Stage 2 override still works, tiering is the only new behavior

### Test 6: Sync verification

- **Method:** After all changes, run the diff commands from the sync warning comments
- **Verify:** Only the "Model requirement" section differs between each pair
- **Pass criteria:** No unintended body differences

---

## Implementation Order

1. **Task 1 + Task 2** (parallel) — Create the two -fast skill files. No dependencies.
2. **Task 9** — Add sync warning comments to the -fast files. Depends on 1+2.
3. **Task 3** — Update `strict:` parsing in thorough_plan. No dependency on 1+2 (text change only).
4. **Task 4** — Add model selection table to thorough_plan. Depends on Task 3 (inserted after it).
5. **Task 5 + Task 5a** — Update "Invoking each agent" section and remaining `/plan`/`/revise` references. Depends on Task 4 (references the table).
6. **Task 6** — Update thorough_plan frontmatter. Independent but logical to do with 3-5a.
7. **Task 7 + Task 8** (parallel) — Update both CLAUDE.md model assignment tables. Independent of 1-6.

**Recommended single-pass order:** 1, 2, 9, 6, 3, 4, 5, 5a, 7, 8

---

## Rollback Plan

### Full rollback

All changes are to skill files (SKILL.md) and documentation (CLAUDE.md). No data migrations, no infrastructure changes.

1. **Delete -fast skill directories:**
   ```
   rm -rf dev-workflow/skills/plan-fast/
   rm -rf dev-workflow/skills/revise-fast/
   ```

2. **Revert `thorough_plan/SKILL.md`** to its Stage 2 state:
   ```
   git checkout <stage-2-commit> -- dev-workflow/skills/thorough_plan/SKILL.md
   ```

3. **Revert CLAUDE.md model tables** in both files — remove the `/plan-fast` and `/revise-fast` rows, remove the tiering notes from `/plan`, `/revise`, `/thorough_plan` rows.

4. **Verify:** Run `/thorough_plan` on a small task. It should behave exactly as it did after Stage 2 — all Opus, max_rounds default 4, no `strict:` parsing.

### Partial rollback (keep -fast files, revert orchestrator)

If the -fast files work fine but the orchestrator tiering logic has issues:

1. Revert only Tasks 3-6 in `thorough_plan/SKILL.md`
2. Keep the -fast skill files (they're harmless — no skill references them without the orchestrator changes)
3. Keep the CLAUDE.md updates or revert them — documentation only

### Partial rollback (revert strict: only)

If `strict:` parsing causes issues but normal tiering works:

1. Remove only the `strict:` paragraph from Task 3's new text
2. Remove the "Strict mode" column from Task 4's table (or simplify to "always Opus variant for /plan, /revise")
3. Keep normal-mode tiering intact

The staged rollback means issues can be addressed surgically without reverting the entire stage.

---

## Cost Impact Estimate

Based on the Stage 0 baseline ($10.66 for a 2-round loop):

- **Opus phases affected by tiering:** `/plan` (R1) and `/revise` (R2) — 2 of 4 subagent spawns
- **Savings source:** Sonnet is ~5x cheaper per token. However, 87.5% of tokens are cache reads (billed at 0.1x input rate for both models), so the savings apply primarily to:
  - Output tokens (2.1% of total): ~5x cheaper on Sonnet
  - Cache-write tokens (10.3% of total): ~5x cheaper on Sonnet
  - Uncached input tokens (0.3% of total): ~5x cheaper on Sonnet
- **Conservative estimate:** 20-35% reduction in total loop cost for a 2-round run ($2-4 saved per run)
- **Strict mode:** No savings (identical to current all-Opus behavior, with one extra allowed round)

The savings compound with round count — a 3-4 round run has more Sonnet phases relative to Opus phases, yielding proportionally higher savings.

---

## Revision History

### Round 1 — 2026-04-12
**Critic verdict:** REVISE
**Issues addressed:**
- [MAJ-1] Missing updates to loop diagram and introductory text — Added Task 5a with three targeted edits: intro sentence (line 9) now mentions `-fast` variants, loop diagram gets a note pointing to the model selection table, and important behaviors (line 127) mentions `-fast` variants.
- [MAJ-2] Task 5 heading naming inconsistency — Changed headers from generic "Planner"/"Reviser" back to slash-command format: `` **`/plan` or `/plan-fast` (Round 1 only)** `` and `` **`/revise` or `/revise-fast` (rounds 2+)** ``.
- [MAJ-3] Stale `/plan` reference in `max_rounds: N` stripping — Changed "before passing it to `/plan`" to "before passing it to the planner skill" in Task 3.
- [MIN-4] Sync warning diff commands assume wrong working directory — Updated diff paths from `plan/SKILL.md` to `dev-workflow/skills/plan/SKILL.md` (and same for revise) in Task 9.
**Issues noted but deferred:**
- [MIN-1] Section numbering gap — cosmetic, not a problem
- [MIN-2] No update to CLAUDE.md skill listing header — `-fast` skills are internal, not intended for direct user invocation; intentionally omitted from the header listing
- [MIN-3] Nested code fences in plan-fast content — to be verified during implementation
- [MIN-5] Architecture deviation on round 4 vs "final allowed round" — positive deviation, no fix needed
**Changes summary:** Added Task 5a for three missed reference updates in thorough_plan/SKILL.md. Fixed naming consistency in Task 5, stale reference in Task 3, and diff paths in Task 9. Updated implementation order to include Task 5a.
