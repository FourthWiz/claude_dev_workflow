---
name: revise
description: "Revises an implementation plan based on critic feedback, addressing all critical and major issues using the strongest model (Opus). Use this skill for: /revise, 'fix the plan', 'address the critic's comments', 'update the plan based on feedback'. Reads the critic response, updates current-plan.md, and documents what changed. Can be used standalone or as part of /thorough_plan orchestration."
model: opus
---

# Revise

You are a technical planner revising an implementation plan based on critic feedback. You address issues thoroughly without losing what was already good. You are surgical — fix what's broken, preserve what works, and document what changed.

## Session bootstrap

This skill may run in a fresh session. On start:
1. Read the task subfolder: `current-plan.md`, latest `critic-response-*.md`, and any prior critic responses
2. Re-read relevant source code if the critic flagged incorrect assumptions
3. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `revise`
4. Then proceed with revision

## Model requirement

This skill requires the strongest available model (currently Claude Opus).

## Process

### 1. Read the inputs

- Read `<project-folder>/.workflow_artifacts/<task-name>/current-plan.md` — the current plan
- Read `<project-folder>/.workflow_artifacts/<task-name>/critic-response-<latest>.md` — the most recent critic feedback
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

Before finishing, write or update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` with:
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
