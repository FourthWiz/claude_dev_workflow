# Implementation Plan: Stage 4 — Task Triage and Shortcut Paths

## Convergence Summary
- **Rounds:** 2
- **Final verdict:** PASS
- **Key revisions:** Round 1 critic found 2 CRITICAL and 4 MAJOR issues — architecture deviation from Sonnet `/plan` for Small tasks not acknowledged (CRIT-1), ambiguous edit instructions with fragmented replacement blocks (CRIT-2), imprecise CLAUDE.md replacement boundaries (MAJ-1), missing exact old_text for gate edits (MAJ-2), implicit `small: max_rounds:` interaction (MAJ-3), and imprecise insertion point for triage criteria (MAJ-4). All addressed in revision: added DD6 justifying Opus `/plan` for all profiles, rewrote Task 1 as single contiguous replacement, provided exact old_text for all Edit operations, added explicit "max_rounds ignored for Small" rule.
- **Remaining concerns:** MAJ-R2-1 (Task 3 line-number metadata says "49-81" but quoted text covers 49-75 — Edit tool matches on text not line numbers, so non-blocking), MIN-R2-1 (gate old_text header line number off by 2), MIN-R2-2 (nested code fences may need escaping), MIN-R2-3 (D3 smoke gate deviation from architecture not explicitly acknowledged as DD7)

## Objective

Implement task-size triage (Small / Medium / Large) so that the workflow automatically selects the right cost/quality profile for each task. Small tasks skip the critic loop entirely, Medium tasks use the Stage-3 tiered loop, and Large tasks force all-Opus strict mode. This also introduces smoke gates (lighter checks) for Small tasks and updates documentation to reflect the new shortcut path.

## Scope

**In scope:**
- D1: Task-size triage logic in `/thorough_plan` with `small:`, `medium:`, `large:` prefix parsing + auto-classification with user confirmation
- D2: Documentation of the single-pass plan mode (`/plan` -> `/implement` -> `/review`) for Small tasks — mechanism already exists, needs triage routing + docs
- D3: Smoke gate vs full gate — lighter checks for pre-implement gates on Small/Medium tasks, full checks reserved for pre-merge gates
- Triage criteria definitions in `dev-workflow/CLAUDE.md`
- Update workflow sequence documentation to reflect Small-profile shortcut
- Update model assignment table to document Small-profile `/review` behavior

**Out of scope:**
- Creating a `/review-fast` Sonnet skill (decision: Small tasks still use Opus `/review` — it is the safety net that justifies skipping the critic loop)
- Changes to `/plan`, `/critic`, `/revise`, `/revise-fast` skill files (those are stable from Stage 3)
- Stage 5 (Haiku for state skills)
- Any changes to `/architect` or `/discover`

## Design Decisions

### DD1: Where does triage happen?

**Decision: Inside `/thorough_plan`, as a routing step before the loop starts.**

The architecture says "at the top of `/thorough_plan`." The apparent contradiction — Small tasks skip `/thorough_plan` — resolves cleanly: `/thorough_plan` becomes the triage entry point for ALL planned tasks. When it classifies a task as Small, it does not run the critic loop; instead it spawns `/plan` (Opus) as a single pass and exits, telling the user the plan is ready. The user never needs to decide whether to invoke `/plan` or `/thorough_plan` — they always invoke `/thorough_plan`, and the triage routes appropriately.

Why not make the user choose `/plan` vs `/thorough_plan` manually? Because that requires the user to self-classify task size before invoking, which is exactly the cognitive overhead triage is supposed to remove. Making `/thorough_plan` the universal entry point keeps the user's interface simple: one command for all planned work.

### DD2: How does the user specify size?

**Decision: Optional prefix tag (`small:`, `medium:`, `large:`) OR auto-classification with user confirmation. Medium is the default if the user says nothing and declines to confirm.**

Parse order (extends Stage 3's existing parsing):
1. `strict:` — if present, force Large profile (strip token)
2. `small:` / `medium:` / `large:` — if present, use that profile (strip token)
3. `max_rounds: N` — if present, override the profile's default cap (strip token)
4. If no size tag and no `strict:`, auto-classify based on the task description and present the classification to the user for confirmation before proceeding

The `strict:` prefix from Stage 3 becomes an alias for `large:` — both force all-Opus, max 5. This preserves backward compatibility.

### DD3: Triage criteria

| Signal | Small | Medium | Large |
|--------|-------|--------|-------|
| Scope | Single file or a handful of closely related files | Multiple files across 1-2 modules/services | Cross-service, cross-repo, or architectural changes |
| Risk | Low — no integration points affected, no data model changes | Moderate — touches integration points or shared APIs | High — affects data consistency, auth, or multi-service contracts |
| Novelty | Well-understood pattern (add endpoint, fix bug, config change) | Some unknowns but similar work has been done before | Significant unknowns, new patterns, or migration |
| Blast radius | Localized — failure affects one feature | Module-level — failure affects a subsystem | System-level — failure affects multiple services or all users |
| Examples | Fix a typo in error message; add a simple CRUD endpoint; update a config value; rename a variable | Add a new feature with tests; refactor a module; add retry logic to an API client; implement a new validation layer | Database migration with data transformation; auth system overhaul; cross-service API versioning; payment flow redesign |

### DD4: Smoke gate vs full gate

**Decision: Add a `gate_level` parameter concept to the gate skill. The gate checks its context to determine level.**

| Gate level | When used | Checks |
|------------|-----------|--------|
| Smoke | After `/thorough_plan` (or `/plan` for Small) -> before `/implement` | Plan artifact exists and is non-empty; plan has tasks with file paths and acceptance criteria |
| Standard | After `/implement` -> before `/review` (Small/Medium tasks) | Lint (if configured); affected tests only (not full suite); no debug code; no secrets in diff |
| Full | After `/implement` -> before `/review` (Large tasks); After `/review` -> before `/end_of_task` (all sizes) | Everything in Standard PLUS: full test suite; typecheck; all planned tasks implemented; branch up to date |

The key insight: the pre-implement gate (plan completeness check) is already lightweight. The real savings come from the post-implement gate, where Small/Medium tasks run only affected tests + lint instead of the full suite. The pre-merge gate (after `/review`) always runs the full suite regardless of size.

### DD5: Does `/review` run on Sonnet for Small tasks?

**Decision: No. `/review` stays on Opus for all task sizes.**

The architecture spec says "Sonnet, smoke gate" for Small tasks, but this creates a dangerous gap: Small tasks already skip the critic loop, so `/review` is the ONLY quality safety net. Downgrading the safety net for the same tasks that skip the primary quality check (critic loop) compounds the risk. R5 (misclassification) becomes much more dangerous if both the critic loop AND the review are weak.

`/review` on Opus is cheap relative to the savings from skipping the entire critic loop. A Small task that would have cost ~$4.65 (2-round all-Opus loop) or ~$2.99 (Stage-3 tiered loop) now costs ~$1.32 (single `/plan` pass) + ~$1.17 (`/review`) = ~$2.49 total — still cheaper than even the Stage-3 Medium path, and with Opus-quality review as the safety net.

### DD6: Why does `/plan` stay on Opus for Small tasks (deviation from architecture spec)?

**Decision: `/plan` stays on Opus for all task sizes, including Small.**

The architecture spec (line 382) says: "Small → `/plan` (Sonnet) + `/implement` + `/review` (Sonnet, smoke gate)." This plan deviates by keeping `/plan` on Opus for Small tasks, for the same reason as DD5:

- Small tasks skip the critic loop — a Sonnet `/plan` that produces a weak or incomplete plan has no safety net before implementation.
- Stage 3 deliberately eliminated `/plan-fast` (Sonnet planner) to simplify the infrastructure. Re-introducing it just for Small tasks adds complexity without clear benefit.
- The cost impact is small: Opus `/plan` for a Small task is ~$1.32. A Sonnet `/plan` might save ~$0.60-0.80, but the quality risk on tasks with no critic review is not worth it.
- The architecture spec was written before Stage 3's simplification decision; Stage 3's finalized design (archived in `finalized/`) documents why `/plan-fast` was removed.

The architecture's intended cost savings for Small come primarily from skipping the critic loop (saving ~$2-3 on critic+revise rounds), not from downgrading the planner. This plan achieves those savings while keeping plan quality consistent across all profiles.

**Cost comparison for Small tasks:**
- Architecture spec intention: ~$0.70 (Sonnet `/plan`) + ~$0.60 (Sonnet `/review`) ≈ ~$1.30
- This plan's approach: ~$1.32 (Opus `/plan`) + ~$1.17 (Opus `/review`) ≈ ~$2.49
- Pre-Stage-4 baseline (2-round all-Opus loop): ~$4.65
- Savings vs baseline: ~$2.16 per Small task (47% reduction) — still significant

If the team later decides Sonnet `/plan` quality is acceptable for Small tasks, re-introducing a `/plan-fast` skill is a contained future change. For now, simplicity and quality win.

## Pre-implementation checklist

- [ ] Stage 3 changes are merged and stable (branch `feat/stage-3-model-tiering` is in production)
- [ ] Verify `/thorough_plan` currently parses `strict:` and `max_rounds: N` correctly (read SKILL.md to confirm — already verified in context gathering)
- [ ] Verify `/plan` skill exists and works standalone (already confirmed)
- [ ] Verify `/gate` skill exists (already confirmed)

## Tasks

### Task 1: Add triage parsing and routing to `/thorough_plan` ✅

**Description:** Extend the existing `strict:` and `max_rounds:` parsing in `/thorough_plan/SKILL.md` to also parse `small:`, `medium:`, `large:` prefixes. Add auto-classification logic. Add routing behavior: Small skips the loop, Medium uses current default behavior, Large activates strict mode.

**Files:** Modify `dev-workflow/skills/thorough_plan/SKILL.md`

**Changes:**

Replace the entire "Parse runtime overrides" section (currently Section 3, lines 30-42 in the current SKILL.md). The replacement covers everything from the `### 3. Parse runtime overrides` heading through the end of the `max_rounds: N` step and the examples block — this is one complete contiguous replacement, not multiple separate operations.

**Old text (complete section, lines 30-42):**
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

**New text (complete replacement):**
```
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
```

Add a new section immediately after "Parse runtime overrides and determine task profile" and before "Model selection per round":

```
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
```

**Routing behavior — add to "The loop" section:**

Before the existing loop diagram (line 62), insert:

```
### Small-profile routing (no loop)

If the task profile is Small, do NOT enter the critic loop. Instead:

1. Invoke `/plan` (Opus) — same as round 1 of the normal loop. Output: `current-plan.md`.
2. Run a smoke gate (plan artifact exists, has tasks with file paths and acceptance criteria).
3. Inform the user: "Task classified as Small — single-pass plan produced. Plan is ready at `<task-folder>/current-plan.md`."
4. **STOP.** Do not invoke `/implement`. Wait for the user.

The rest of the loop section below applies only to Medium and Large profiles.

### Medium and Large profiles (critic loop)

```

**Acceptance criteria:**
- `/thorough_plan small: fix the typo in error.ts` parses the `small:` tag, runs single-pass `/plan`, skips critic loop
- `/thorough_plan large: redesign the auth flow` behaves identically to `/thorough_plan strict: redesign the auth flow`
- `/thorough_plan` with no tag auto-classifies, asks user to confirm, then routes
- `/thorough_plan strict: max_rounds: 3 quick safety check` still works (backward compat)
- `medium:` tag runs the standard Stage-3 loop (Opus plan, Sonnet revise-fast, Opus critic, max 4)
- `max_rounds: N` override still works with any profile except Small (where it is discarded)

**Effort:** medium

**Depends on:** none

---

### Task 2: Update `/gate` skill to support gate levels ✅

**Description:** Modify the gate skill to recognize task context and apply the appropriate check level (smoke, standard, full). The gate reads the task profile from the plan or session state and adjusts its checks accordingly.

**Files:** Modify `dev-workflow/skills/gate/SKILL.md`

**Changes:**

**Step 1: Add gate levels section**

After the "Core principle" section (ending with "3. Human explicitly says 'go' or invokes the next skill") and before the "## When gates run" heading, insert:

```
## Gate levels

Gates run at three intensity levels depending on the task profile and the phase transition:

### Smoke gate
Lightweight checks for plan completeness. Used after planning phases.
- Plan artifact exists and is non-empty
- Plan has tasks with file paths and acceptance criteria
- (For Medium/Large) Convergence summary present with PASS verdict

### Standard gate
Moderate checks for implementation correctness. Used after `/implement` for Small and Medium tasks.
- Run linter if configured
- Run only tests affected by the changes (use git diff to identify changed files, then run tests that import/reference those files)
- No debug code (console.log, debugger, print, TODO: remove)
- No secrets in diff
- No uncommitted changes

### Full gate
Comprehensive checks. Used after `/implement` for Large tasks and after `/review` for all task sizes (pre-merge).
- Everything in Standard gate, PLUS:
- Full test suite (not just affected tests)
- Type checker if applicable
- All planned tasks are implemented (cross-reference plan task list)
- Branch is up to date with base branch
- No merge conflicts
- Review verdict is APPROVED (for post-review gates only)

## Determining the gate level

Read the task profile from the convergence summary at the top of `current-plan.md` (which will include "Task profile: Small/Medium/Large" after Stage 4), or from the session state file. Then apply:

| Previous phase | Next phase | Small | Medium | Large |
|---------------|-----------|-------|--------|-------|
| /thorough_plan (or /plan) | /implement | Smoke | Smoke | Smoke |
| /implement | /review | Standard | Standard | Full |
| /review | /end_of_task | Full | Full | Full |

If the task profile cannot be determined, default to **Full** (safe fallback).
```

**Step 2: Replace the automated checks section**

In the "Step 2: Run automated checks" section, replace the entire block of four check lists with the gate-level-aware version. The exact text to replace is:

**Old text (exact, lines 41-70):**
```
**After /architect → before /thorough_plan:**
- [ ] `architecture.md` exists and is non-empty
- [ ] Architecture covers: objective, constraints, service map, integration points, stages
- [ ] Stages are decomposed with clear boundaries

**After /thorough_plan → before /implement:**
- [ ] `current-plan.md` exists with PASS verdict from critic
- [ ] Plan has: tasks with file paths, acceptance criteria, integration analysis, risk analysis, testing strategy
- [ ] Task dependencies are acyclic (no circular deps)
- [ ] All tasks have effort estimates
- [ ] Integration analysis covers all affected service boundaries
- [ ] Risk mitigations are concrete (not "we'll handle this later")

**After /implement → before /review:**
- [ ] All planned tasks are implemented (cross-reference plan task list)
- [ ] Run test suite: `npm test`, `go test ./...`, `pytest`, etc. (detect from project)
- [ ] Run linter if configured: `eslint`, `golint`, `ruff`, etc.
- [ ] Run type checker if applicable: `tsc --noEmit`, `mypy`, etc.
- [ ] No uncommitted changes left behind
- [ ] No debug code (search for `console.log`, `debugger`, `print(`, `TODO: remove`)
- [ ] No secrets in diff (`grep -i "password\|secret\|api_key\|token" --include="*.ts" --include="*.py" ...`)

**After /review → before merge/PR:**
- [ ] Review verdict is APPROVED
- [ ] All CRITICAL and MAJOR issues are resolved
- [ ] Tests pass (run again — code may have changed during review fixes)
- [ ] Branch is up to date with base branch
- [ ] No merge conflicts
```

**New text:**
```
**After /architect → before /thorough_plan (no gate level concept — always full architecture check):**
- [ ] `architecture.md` exists and is non-empty
- [ ] Architecture covers: objective, constraints, service map, integration points, stages
- [ ] Stages are decomposed with clear boundaries

**After /architect or /thorough_plan → before /implement (Smoke gate):**
- [ ] Plan artifact (`current-plan.md`) exists and is non-empty
- [ ] Plan has: tasks with file paths, acceptance criteria
- [ ] (Medium/Large only) Convergence summary with PASS verdict from critic
- [ ] (Large only) Integration analysis covers all affected service boundaries
- [ ] (Large only) Risk mitigations are concrete

**After /implement → before /review (Standard or Full gate — determined by task profile):**

*Standard gate (Small and Medium tasks):*
- [ ] Run linter if configured
- [ ] Run affected tests only (identify from git diff)
- [ ] No debug code (console.log, debugger, print, TODO: remove)
- [ ] No secrets in diff
- [ ] No uncommitted changes

*Full gate (Large tasks) — includes everything in Standard, plus:*
- [ ] All planned tasks are implemented (cross-reference plan task list)
- [ ] Run full test suite
- [ ] Run type checker if applicable
- [ ] Verify no unrelated file changes

**After /review → before /end_of_task (Full gate — always, all task sizes):**
- [ ] Review verdict is APPROVED
- [ ] All CRITICAL and MAJOR issues are resolved
- [ ] Run full test suite (re-run — code may have changed during review fixes)
- [ ] Run type checker if applicable
- [ ] Branch is up to date with base branch
- [ ] No merge conflicts
```

**Acceptance criteria:**
- Gate after a Small-profile plan runs only smoke checks (artifact exists, has tasks)
- Gate after `/implement` on a Medium task runs lint + affected tests, not full suite
- Gate after `/implement` on a Large task runs full suite + typecheck
- Gate after `/review` always runs full checks regardless of task size
- When task profile is unknown, gate defaults to Full

**Effort:** medium

**Depends on:** Task 1 (needs task profile to be set)

---

### Task 3: Update `dev-workflow/CLAUDE.md` — workflow sequence and triage documentation ✅

**Description:** Update the shared rules file to document task triage, the Small-profile shortcut path, and update the existing workflow sequence to reflect that Small tasks use `/plan` -> `/implement` -> `/review` without the critic loop. Also update the model assignment table.

**Files:** Modify `dev-workflow/CLAUDE.md`

**Changes:**

**Change 1: Update the workflow sequence section**

Replace lines 49-81 of CLAUDE.md — from the `## Workflow sequence` heading through the end of the "Not every task needs every stage" paragraph (ending with "But gates ALWAYS run between phases."). Stop before the blank line and the `**CRITICAL RULE:**` paragraph — that paragraph (line 83) and everything after it are **not** part of this replacement and must remain unchanged.

The exact replacement boundaries are:

**Old text (exact — from line 49 through line 81, inclusive):**
```
## Workflow sequence

The intended flow is:

```
/discover → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → /end_of_task
```

Each stage feeds into the next, with `/gate` checkpoints requiring explicit human approval:
- `/init_workflow` bootstraps the workflow in a new project. Creates `memory/` structure, configures permissions, runs `/discover`, generates quickstart guide. Run once per project. (Skills and rules are installed separately via `bash install.sh`.)
- `/discover` scans all repos and saves inventory, architecture overview, and dependency map to `memory/`. Run once on setup, re-run when repos change.
- `/architect` produces `architecture.md` with stages decomposed for planning (uses `/discover` output as baseline context)
- **GATE** — user reviews architecture, explicitly approves
- `/thorough_plan` orchestrates the plan→critic→revise convergence loop:
  - `/plan` produces the initial `current-plan.md` with implementable tasks
  - `/critic` (fresh session) reviews plan against actual codebase → `critic-response-N.md`
  - `/revise` addresses critic feedback → updates `current-plan.md`
  - Loop repeats up to 4 rounds until convergence (override with max_rounds: N)
- **GATE** — automated checks (plan completeness, risk coverage), user reviews plan, explicitly approves
- `/implement` executes tasks from the converged plan, writing code and tests
- **GATE** — automated checks (tests, lint, typecheck, no debug code, no secrets), user reviews
- `/review` verifies implementation against the plan, checking quality and safety
- **GATE** — review verdict is APPROVED, tests pass, no conflicts, user approves
- `/end_of_task` — user explicitly accepts the work. Commits remaining changes, pushes branch to remote, prompts for lessons learned, marks task complete. Does NOT create a PR — that's a separate explicit action.
- `/rollback` is available at any point to safely undo implementation work

Not every task needs every stage. Small, well-understood changes can skip `/architect` and go straight to `/thorough_plan`. Bug fixes might only need `/implement` + `/review`. But gates ALWAYS run between phases.
```

**New text:**
```
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
- `/init_workflow` bootstraps the workflow in a new project. Creates `memory/` structure, configures permissions, runs `/discover`, generates quickstart guide. Run once per project. (Skills and rules are installed separately via `bash install.sh`.)
- `/discover` scans all repos and saves inventory, architecture overview, and dependency map to `memory/`. Run once on setup, re-run when repos change.
- `/architect` produces `architecture.md` with stages decomposed for planning (uses `/discover` output as baseline context)
- **GATE** — user reviews architecture, explicitly approves
- `/thorough_plan` triages the task and routes accordingly:
  - **Small:** runs `/plan` (Opus) as a single pass → produces `current-plan.md` → smoke gate → done
  - **Medium:** runs the plan→critic→revise convergence loop (Opus plan, Sonnet revise, Opus critic, max 4 rounds)
  - **Large:** runs the convergence loop in strict mode (all Opus, max 5 rounds)
  - Override with `max_rounds: N` for any profile (ignored for Small)
- **GATE** — automated checks (plan completeness, risk coverage), user reviews plan, explicitly approves
- `/implement` executes tasks from the converged plan, writing code and tests
- **GATE** — automated checks (scope depends on task profile — Standard for Small/Medium, Full for Large)
- `/review` verifies implementation against the plan, checking quality and safety (always Opus)
- **GATE** — Full checks: review verdict is APPROVED, full test suite passes, no conflicts, user approves
- `/end_of_task` — user explicitly accepts the work. Commits remaining changes, pushes branch to remote, prompts for lessons learned, marks task complete. Does NOT create a PR — that's a separate explicit action.
- `/rollback` is available at any point to safely undo implementation work

Not every task needs every stage. Small tasks typically skip `/architect` entirely. Bug fixes might only need `/implement` + `/review` (bypassing `/thorough_plan` entirely). But gates ALWAYS run between phases.
```

After the replacement, the file continues with the unchanged `**CRITICAL RULE:**` paragraph, session lifecycle bullets, and the "Multiple sessions..." paragraph exactly as they are today.

**Change 2: Add triage criteria section**

Insert the following text after the "Multiple sessions can run in a day..." paragraph (line 84) and before the `## Session independence` heading (line 86). The insertion point is the blank line between those two blocks.

**Insert after this exact line:**
```
Multiple sessions can run in a day (parallel tasks). Each session writes its own state to `memory/sessions/`. `/end_of_day` rolls unfinished sessions into `memory/daily/<date>.md`.
```

**Text to insert:**
```

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
```

**Change 3: Update the model assignment table**

Replace the existing table entry for `/thorough_plan`:

**Old text:**
```
| /thorough_plan | Opus | Orchestrates plan→critic→revise loop (tiers /revise to Sonnet by default; use strict: for all-Opus /revise) |
```

**New text:**
```
| /thorough_plan | Opus | Orchestrates task triage and plan→critic→revise loop. Routes Small tasks to single-pass /plan; Medium uses Sonnet /revise-fast; Large/strict: uses all-Opus. Critic always Opus. |
```

**Acceptance criteria:**
- CLAUDE.md documents all three task profiles with triage criteria
- Workflow sequence section shows both the full flow and the Small shortcut flow
- The old "Small, well-understood changes can skip /architect and go straight to /thorough_plan" text is replaced with the new triage-aware language
- Model assignment table reflects `/thorough_plan`'s triage role
- The `**CRITICAL RULE:**` paragraph is unchanged after the edit (verify it still appears immediately after the new "But gates ALWAYS run between phases." line)

**Effort:** medium

**Depends on:** none (documentation can be written in parallel with Task 1)

---

### Task 4: Update `/thorough_plan` convergence summary to include task profile ✅

**Description:** When `/thorough_plan` completes (whether via single-pass for Small or via the full loop), include the task profile in the convergence summary written to `current-plan.md`. This allows downstream skills (`/gate`, `/implement`, `/review`) to know the task profile without re-reading the orchestrator's state.

**Files:** Modify `dev-workflow/skills/thorough_plan/SKILL.md`

**Changes:**

In the "Final output" section (lines 119-127), update the convergence summary template:

**Old text:**
````
```markdown
## Convergence Summary
- **Rounds:** <N>
- **Final verdict:** PASS
- **Key revisions:** <what the main themes of revision were across rounds>
- **Remaining concerns:** <any MINOR issues not addressed, or none>
```
````

**New text:**
````
```markdown
## Convergence Summary
- **Task profile:** <Small | Medium | Large>
- **Rounds:** <N> (Small tasks: 1, single pass)
- **Final verdict:** PASS
- **Key revisions:** <what the main themes of revision were across rounds, or "N/A — single-pass plan" for Small>
- **Remaining concerns:** <any MINOR issues not addressed, or none>
```
````

Also add a note for Small-profile completion: after the convergence summary template, add:

```
For Small-profile tasks that took the single-pass path, the convergence summary still appears at the top of `current-plan.md` but with `Rounds: 1` and `Key revisions: N/A — single-pass plan`. This signals to downstream skills that the plan was not critic-reviewed.
```

**Acceptance criteria:**
- Convergence summary includes "Task profile: Small/Medium/Large"
- Small-profile plans have "Rounds: 1" and "N/A — single-pass plan" in key revisions
- `/gate` can read the task profile from `current-plan.md`

**Effort:** small

**Depends on:** Task 1

---

### Task 5: Update the `/thorough_plan` examples section

**Description:** Update the examples in `/thorough_plan/SKILL.md` to include the new triage prefixes alongside the existing `strict:` and `max_rounds:` examples. The examples block is now part of the complete section replacement done in Task 1 — this task is superseded.

**Note:** Task 1's replacement block already includes the updated examples. No separate edit to the examples is needed. This task is retained for documentation completeness but requires no action beyond Task 1.

**Acceptance criteria:**
- Examples cover all three profiles plus combinations with `max_rounds:` and `strict:` — satisfied by Task 1's replacement block

**Effort:** none (covered by Task 1)

**Depends on:** Task 1

---

### Task 6: Update `/thorough_plan` description frontmatter ✅

**Description:** Update the skill description in the YAML frontmatter to mention task triage, so the skill registry correctly describes the skill's expanded role.

**Files:** Modify `dev-workflow/skills/thorough_plan/SKILL.md`

**Changes:**

**Old text (line 3):**
```
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning. Uses Sonnet for planning/revision and Opus for critique by default; use 'strict:' prefix for all-Opus. Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 4 rounds until convergence (override with max_rounds: N, or 'strict:' for all-Opus + 5 rounds). Use this when you want the highest-quality plan, not just a quick one."
```

**New text:**
```
description: "Triages tasks by size (Small/Medium/Large) and orchestrates the appropriate planning path. Small tasks get a single-pass /plan (no critic loop). Medium tasks run the plan→critic→revise cycle with Sonnet revision. Large tasks (or 'strict:' prefix) run all-Opus with up to 5 rounds. Use this skill for: /thorough_plan, 'plan this', 'plan this thoroughly', 'detailed plan with review'. Supports size tags (small:/medium:/large:), strict: prefix, and max_rounds: N override. Always the entry point for planned work — routes automatically based on task size."
```

**Note on trigger phrase overlap:** The new description includes `'plan this'` as a trigger phrase. This overlaps with `/plan`'s existing trigger phrase. Since `/thorough_plan` is the intended universal entry point and `/plan` is a sub-skill invoked by the orchestrator, the overlap is acceptable — `/thorough_plan` will be preferred by users invoking via natural language. If skill registry routing causes ambiguity, remove `'plan this'` from the description.

**Acceptance criteria:**
- Frontmatter description mentions triage, all three profiles, and that it's the universal planning entry point
- Skill registry shows the updated description

**Effort:** small

**Depends on:** none

---

### ~~Task 7: REMOVED~~

**Removed:** This project only modifies the `dev-workflow/` repo. The global `~/.claude/CLAUDE.md` is updated via `install.sh` after changes are merged — it is never edited directly in plans.

---

## Integration analysis

### Integration point 1: `/thorough_plan` <-> `/plan`

- **Current behavior:** `/thorough_plan` always invokes `/plan` as round 1 of the critic loop
- **New behavior:** For Small tasks, `/thorough_plan` invokes `/plan` as a single-pass operation and exits without entering the critic loop. `/plan` itself is unchanged — it still produces `current-plan.md` in the same format.
- **Failure modes:** `/plan` fails mid-generation → `current-plan.md` is incomplete. Same failure mode as today; no new risk.
- **Backward compatibility:** Full backward compat. `/plan` is not modified. `/thorough_plan` with no tag defaults to Medium, which is the current behavior.

### Integration point 2: `/thorough_plan` <-> `/gate`

- **Current behavior:** `/thorough_plan` runs `/gate` after convergence. Gate runs full plan-completeness checks.
- **New behavior:** Gate reads the task profile from `current-plan.md`'s convergence summary and adjusts check intensity. For Small tasks, the smoke gate does not check for convergence summary with critic PASS (since there was no critic).
- **Failure modes:** Gate cannot find task profile → defaults to Full (safe). Gate incorrectly reads profile → runs wrong check level. Mitigated by the Full default fallback.
- **Backward compatibility:** Plans created before Stage 4 (without task profile in convergence summary) will trigger the "profile not found" fallback → Full gate. Safe.

### Integration point 3: `/gate` <-> `/implement` <-> `/review`

- **Current behavior:** Post-implement gate runs all checks. `/review` always runs on Opus.
- **New behavior:** Post-implement gate runs Standard (lint + affected tests) for Small/Medium, Full for Large. `/review` is unchanged — always Opus.
- **Failure modes:** Standard gate misses an issue that Full would have caught → `/review` (Opus) is the safety net. Pre-merge gate after `/review` always runs Full, so issues caught by `/review` trigger a Full re-check.
- **Backward compatibility:** Full compat. `/review` and `/implement` skills are not modified.

### Integration point 4: `strict:` prefix backward compatibility

- **Current behavior:** `strict:` forces all-Opus and max 5 rounds.
- **New behavior:** `strict:` is now an alias for `large:` profile. Same behavior: all-Opus, max 5. `large:` is a new way to get the same thing.
- **Failure modes:** None — `strict:` behavior is preserved exactly. Users who already use `strict:` see no change.

## Risk analysis

| Risk | Likelihood | Impact | Mitigation | Rollback |
|------|-----------|--------|------------|----------|
| R5: Task misclassified as Small when it should be Medium/Large — no critic loop — bug ships | Medium | High | User confirms auto-classification; Medium is default for uncertain tasks; `/review` (Opus) is the safety net; pre-merge gate always runs Full | Revert `/thorough_plan` SKILL.md to pre-Stage-4 version; all tasks go through critic loop |
| Triage parsing conflicts with existing `strict:` / `max_rounds:` parsing | Low | Medium | Parse order is well-defined: strict → size tag → max_rounds → auto-classify. Unit-test-like manual verification of all tag combinations | Revert parsing changes in `/thorough_plan` SKILL.md |
| Standard gate misses issue that Full gate would catch | Low | Low | `/review` (Opus) catches code-level issues; pre-merge gate always runs Full regardless of profile | Revert `/gate` SKILL.md to run Full checks for all task sizes |
| Users ignore triage confirmation prompt and accept wrong classification | Medium | Medium | Prompt includes concrete rationale and criteria match; Medium is the default for ambiguous cases | Same as R5 rollback |
| Auto-classification logic is unreliable (Claude guesses wrong frequently) | Medium | Medium | Classification criteria are concrete and observable; user always confirms; default to Medium | Remove auto-classification, require explicit tags only |

## Testing strategy

### Manual verification (no automated test infrastructure for SKILL.md files)

**Parsing tests — run each of these as a `/thorough_plan` invocation and verify correct routing:**

1. `/thorough_plan small: fix the typo in error.ts`
   - Expected: Small profile, single-pass `/plan`, no critic loop, smoke gate
2. `/thorough_plan medium: add retry logic to payment client`
   - Expected: Medium profile, standard critic loop (max 4), standard post-implement gate
3. `/thorough_plan large: redesign the auth token refresh flow`
   - Expected: Large profile (= strict), all-Opus, max 5, full post-implement gate
4. `/thorough_plan strict: handle the auth migration`
   - Expected: Large profile (backward compat with strict:), all-Opus, max 5
5. `/thorough_plan strict: max_rounds: 3 quick safety check`
   - Expected: Large profile, all-Opus, max 3 (override)
6. `/thorough_plan small: max_rounds: 2 add config endpoint`
   - Expected: Small profile, single pass; max_rounds parsed then discarded (no loop)
7. `/thorough_plan refactor the error handling in the API layer`
   - Expected: Auto-classifies (likely Medium), asks user for confirmation
8. `/thorough_plan` with no description
   - Expected: Asks user for task description, then auto-classifies

**Gate level tests:**

9. After a Small-profile plan: gate should check only artifact existence + task list
10. After `/implement` on a Medium task: gate should run lint + affected tests only
11. After `/implement` on a Large task: gate should run full suite + typecheck
12. After `/review` on any task: gate should always run full checks

**Backward compatibility tests:**

13. A `/thorough_plan` invocation with NO size tag and NO strict: should behave identically to pre-Stage-4 (auto-classify defaults to Medium, which is the current behavior)
14. Plans created before Stage 4 (no task profile in convergence summary) should trigger Full gate (safe fallback)

## Implementation order

1. **Task 6** — Update `/thorough_plan` frontmatter (trivial, no dependencies)
2. **Task 1** — Add triage parsing and routing to `/thorough_plan` (core logic; also covers Task 5's examples)
3. **Task 4** — Update convergence summary to include task profile (depends on Task 1)
4. **Task 2** — Update `/gate` to support gate levels (depends on Task 1 for profile context)
5. **Task 3** — Update `dev-workflow/CLAUDE.md` (can be done in parallel with Tasks 2/4)

Tasks 2, 3, and 4 can be parallelized after Task 1 is done. Task 1 is the critical path. Task 5 requires no action (covered by Task 1). Task 7 removed (global `~/.claude/CLAUDE.md` is updated via `install.sh`, not directly).

## Rollback plan

**Full rollback:** Revert all changes to `thorough_plan/SKILL.md`, `gate/SKILL.md`, and `dev-workflow/CLAUDE.md` to their pre-Stage-4 state. All tasks route through the standard critic loop (Medium profile behavior). No user-facing impact beyond losing the triage shortcuts.

**Partial rollback (keep triage, revert gate changes):** If gate levels cause issues, revert only `gate/SKILL.md`. All gates run full checks. Triage still routes Small tasks to single-pass plan, but gate intensity is uniform.

**Partial rollback (keep gate levels, revert auto-classification):** If auto-classification is unreliable, remove step 1c from the parsing and require explicit `small:` / `medium:` / `large:` tags. Default behavior (no tag) becomes Medium with no confirmation prompt.

All changes are to `.md` instruction files — no code, no infrastructure, no data migrations. Rollback is always safe and instant via git revert.

---

## Revision notes

### Round 1 revision (2026-04-12)

**Changes made in response to critic-response-1.md:**

**CRIT-1 addressed:** Added **DD6** explicitly documenting the deviation from the architecture spec (line 382) which specified Sonnet `/plan` for Small tasks. DD6 explains why Opus `/plan` is kept: same quality-safety reasoning as DD5, Stage 3 already eliminated `/plan-fast` to simplify infrastructure, and cost savings from skipping the critic loop (~$2.16/task, 47% reduction) are still significant without downgrading the planner. Includes explicit cost comparison table.

**CRIT-2 addressed:** Task 1 now provides a single complete contiguous replacement block for the entire "Parse runtime overrides" section (lines 30-42), including the unchanged `max_rounds: N` step (renumbered to step 2) and the full updated examples. The previous fragmented approach (separate replace + insert) is replaced by one atomic edit. Task 5's examples update is now marked as "covered by Task 1 — no action required."

**MAJ-1 addressed:** Task 3 Change 1 now explicitly states the replacement boundary: "Replace lines 49-81 ... Stop before the blank line and the `**CRITICAL RULE:**` paragraph — that paragraph and everything after it are **not** part of this replacement and must remain unchanged." Acceptance criteria also include a verification step for the CRITICAL RULE paragraph.

**MAJ-2 addressed:** Task 2 now provides the **exact old text** for the gate Step 2 replacement (the complete four-block check list, verbatim), enabling precise Edit tool matching.

**MAJ-3 addressed:** Step 3 of the parsing logic now includes an explicit "Important" note: "For Small-profile tasks, `max_rounds` is ignored — there is no critic loop and therefore no round cap applies. If `max_rounds: N` was parsed in step 2, discard it when the profile is Small." Test case 6 also updated to reflect this explicit discard behavior.

**MAJ-4 addressed:** Task 3 Change 2 now specifies the exact insertion point: "after the 'Multiple sessions can run in a day...' paragraph and before the `## Session independence` heading," with the exact anchor line quoted for Edit tool use.

**Minor issues addressed:**
- MIN-1: Added a note in the parsing logic table about auto-classification adding a confirmation round-trip, with the suggestion that explicit tags skip this delay.
- MIN-2: Added a note in Task 6 about the `'plan this'` trigger overlap with `/plan`, with guidance to remove it if routing ambiguity occurs.
- MIN-3: Updated the CLAUDE.md new text's "Bug fixes" parenthetical from "(no planning at all)" to "(bypassing `/thorough_plan` entirely)" for clarity.
