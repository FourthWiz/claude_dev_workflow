# Stage 2 — Loop Discipline: Implementation Plan

## Convergence Summary
- **Rounds:** 1
- **Final verdict:** PASS
- **Key revisions:** None needed — plan passed on first review
- **Remaining concerns:** 4 MINOR items from critic (addressed below in addendum)

---

## Summary

**Scope:** Four changes to a single file — `dev-workflow/skills/thorough_plan/SKILL.md` (124 lines). No other files are modified.

**Goals:**
1. Fix the `/revise` session-isolation contradiction (E0) — spawn `/revise` as its own subagent instead of running inline
2. Lower default max_rounds from 5 to 4 (B1) — trim worst-case tail cost
3. Add inline `max_rounds: N` override — user escape hatch for hard tasks
4. Tighten loop detection (B3) — make stuck-loop escalation concrete and actionable

**Why now:** These are risk-free configuration/instruction changes that enable Stage 3 (model tiering requires subagent isolation) and reduce worst-case loop cost. No code, no new files, no behavioral risk.

---

## Tasks

### Task 1: E0 — /revise session-isolation fix

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`
**Lines:** 62-65

**Old text (exact):**
```
**`/revise` (rounds 2+)**
- Invoke in the original session context (it needs to understand the plan's intent)
- Pass: path to `current-plan.md`, path to latest `critic-response-<N>.md`
- Output: updated `current-plan.md` (in place)
```

**New text:**
```
**`/revise` (rounds 2+)**
- **MUST spawn as a new agent session** — fresh context prevents anchoring on prior orchestrator chatter. The plan document (`current-plan.md`) encodes the plan's intent; a fresh reviser reading it + critic feedback is strictly better than one carrying stale context.
- Pass: path to `current-plan.md`, path to latest `critic-response-<N>.md`, and paths to any files the critic flagged as needing re-examination
- Output: updated `current-plan.md` (in place)
```

**Rationale:** Resolves the contradiction between `thorough_plan/SKILL.md` ("invoke inline") and `revise/SKILL.md` ("may run in a fresh session"). The revise skill already has a "Session bootstrap" section (lines 13-16) that handles fresh session startup — no changes needed there. This also enables Stage 3's model tiering, which requires subagent isolation to switch models per round.

---

### Task 2: B1 — Lower max_rounds from 5 to 4

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`

Two locations need updating:

#### 2a: Frontmatter description (line 3)

**Old text (exact):**
```
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning using the strongest model (Opus). Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 5 rounds until convergence. Use this when you want the highest-quality plan, not just a quick one."
```

**New text:**
```
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning using the strongest model (Opus). Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 4 rounds until convergence (override with max_rounds: N). Use this when you want the highest-quality plan, not just a quick one."
```

#### 2b: Loop description (line 47)

**Old text (exact):**
```
...repeat up to Round 5
```

**New text:**
```
...repeat up to Round 4 (or max_rounds if overridden)
```

#### 2c: Convergence rule #2 (line 72)

**Old text (exact):**
```
2. **5 rounds reached** — inform the user of remaining issues. The plan may have inherent constraints.
```

**New text:**
```
2. **Max rounds reached (default: 4)** — inform the user of remaining issues. The plan may have inherent constraints.
```

---

### Task 3: Inline max_rounds: N override

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`

Insert a new subsection after "### 2. Gather initial context" (after line 28, before "## The loop" on line 31).

**Insert after line 28 (after the last bullet of section 2):**

```

### 3. Parse runtime overrides

Before starting the loop, scan the user's task description for runtime overrides:

- **`max_rounds: N`** (case-insensitive, N = positive integer): If found, use N as the maximum round cap for this run. Strip the `max_rounds: N` token from the description before passing it to `/plan`. If not found, use the default cap of 4.

Example: `/thorough_plan max_rounds: 6 this migration is gnarly, give it room` sets the cap to 6 and passes "this migration is gnarly, give it room" to `/plan`.

```

**Side effect:** The existing "## The loop" section becomes unnumbered relative to the Setup subsections, but since "The loop" is its own top-level section (## level), this is fine. The Setup section now has subsections 1, 2, 3 instead of 1, 2.

---

### Task 4: B3 — Tighter loop detection

**File:** `dev-workflow/skills/thorough_plan/SKILL.md`

Two locations need updating:

#### 4a: Convergence rule #3 (line 73)

**Old text (exact):**
```
3. **Stuck in a loop** — the critic flags the same issues repeatedly despite revisions. Escalate to the user — this usually means a requirement is ambiguous or there's a genuine tradeoff to decide.
```

**New text:**
```
3. **Stuck in a loop** — if round N's critic flags the same top-level issue category as round N-1 (same CRITICAL or MAJOR issue title reappearing despite revision), escalate to the user with the specific repeated issues and ask whether to continue or accept the plan as-is. This usually means a requirement is ambiguous or there's a genuine tradeoff to decide.
```

#### 4b: "Between rounds" loop detection guidance (lines 80 and 122)

**Old text (exact, line 80):**
```
- Check if the same issues keep appearing (loop detection)
```

**New text:**
```
- Check if the same issues keep appearing (loop detection: compare round N's CRITICAL/MAJOR issue titles against round N-1's — if any title reappears, flag it)
```

**Old text (exact, line 122):**
```
- **Detect loops early.** If round 3's critic response looks like round 1's, stop and involve the user.
```

**New text:**
```
- **Detect loops early.** After each critic round, compare CRITICAL/MAJOR issue titles against the previous round. If any title reappears, stop and present the repeated issues to the user — ask whether to continue revising or accept the plan as-is.
```

---

## Dependency / Ordering

These four tasks are independent in terms of correctness — they touch different lines and can be applied in any order. However, the recommended implementation order is:

1. **Task 3 (max_rounds override)** — insert the new section first, since it shifts line numbers for everything below it
2. **Task 2 (lower max_rounds)** — update the three "5 rounds" references to "4 rounds"
3. **Task 1 (E0 /revise isolation)** — update the /revise invocation block
4. **Task 4 (B3 loop detection)** — update the three loop-detection references

Rationale: Task 3 inserts new lines, so doing it first avoids stale line references for the other tasks. Tasks 1, 2, and 4 are pure replacements (no insertions) and are order-independent relative to each other.

---

## Integration Analysis

### Skills that interact with /thorough_plan

| Skill | Interaction | Impact of Stage 2 changes |
|-------|------------|--------------------------|
| `/plan` | Invoked by `/thorough_plan` in round 1 | **No impact.** Task 3 strips `max_rounds: N` before passing the description to `/plan`, so `/plan` never sees it. |
| `/critic` | Spawned as fresh agent every round | **No impact.** Already runs as a subagent. The max_rounds change doesn't affect `/critic` behavior. |
| `/revise` | Invoked by `/thorough_plan` in rounds 2+ | **Task 1 changes invocation from inline to subagent.** `/revise` already has a "Session bootstrap" section (lines 13-16) that handles fresh session startup. No changes needed in `revise/SKILL.md`. |
| `/gate` | Run after convergence | **No impact.** Gate runs the same regardless of round count or how sub-skills were invoked. |
| CLAUDE.md (shared rules) | References "up to 5 rounds" in workflow sequence section | **Needs a follow-up update.** The CLAUDE.md file (both global `~/.claude/CLAUDE.md` and `dev-workflow/CLAUDE.md`) says "Loop repeats up to 5 rounds until convergence." This should be updated to match, but is documentation-only, not behavioral. |

### Cross-reference: CLAUDE.md "5 rounds" mention

Both `~/.claude/CLAUDE.md` and `dev-workflow/CLAUDE.md` contain:
```
  - `/revise` addresses critic feedback → updates `current-plan.md`
  - Loop repeats up to 5 rounds until convergence
```

These are informational references in the workflow overview. They should be updated to say "up to 4 rounds" for consistency, but this is a documentation follow-up — the SKILL.md is the authoritative source that controls behavior.

**Recommendation:** Include a follow-up task (non-blocking) to update both CLAUDE.md files after the SKILL.md changes are verified. This can be done in the same commit or as a separate one.

---

## Risk Table

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| E0: Subagent `/revise` misses context that inline `/revise` had | Low | Medium | `current-plan.md` + critic response + flagged files provide full context. `revise/SKILL.md` already handles fresh sessions (lines 13-16). If insufficient, the right fix is an explicit `intent.md` handoff artifact, not reverting to inline. |
| B1: 4 rounds insufficient for genuinely complex tasks | Low | Low | `max_rounds: N` override lets users raise the cap per-run. Convergence-driven termination (PASS verdict) still exits early — only worst-case tail is trimmed. |
| max_rounds override: User typo (e.g., `max_rounds: -1` or `max_rounds: abc`) | Low | Low | Instruction says "positive integer." An LLM-executed parsing rule handles this naturally — non-integer or negative values would be ignored and default used. |
| B3: Overly aggressive loop detection false-positives | Low | Medium | Detection requires same CRITICAL/MAJOR issue *title* reappearing, not just same *category*. Human is always in the loop — the escalation asks the user whether to continue, never auto-terminates. |
| CLAUDE.md desync: "5 rounds" reference remains after SKILL.md says "4" | Medium | Low | Include CLAUDE.md update in the same commit. The SKILL.md is authoritative for behavior; CLAUDE.md is informational. |

---

## Testing Strategy

Since these are changes to an LLM instruction file (not executable code), testing is behavioral verification through dry runs.

### Test 1: E0 — /revise subagent isolation
- **Method:** Run `/thorough_plan` on a small task that requires at least one revision round.
- **Verify:** The orchestrator spawns `/revise` as a fresh subagent (not inline). Check that the reviser successfully reads `current-plan.md` and the critic response without needing orchestrator context.
- **Pass criteria:** Plan converges normally. The revision addresses critic feedback correctly.

### Test 2: B1 — Max rounds = 4
- **Method:** Run `/thorough_plan` on a task that would normally take multiple rounds.
- **Verify:** The loop stops at round 4 if it hasn't converged. Check the convergence rule message says "Max rounds reached" not "5 rounds reached."
- **Pass criteria:** Loop respects the 4-round cap.

### Test 3: max_rounds override
- **Method:** Run `/thorough_plan max_rounds: 2 <simple task description>`.
- **Verify:** (a) The orchestrator parses `max_rounds: 2` and strips it from the task description. (b) `/plan` receives only the task description without `max_rounds: 2`. (c) The loop stops at round 2 if it hasn't converged.
- **Pass criteria:** Override is parsed, stripped, and respected.

### Test 4: B3 — Loop detection
- **Method:** This is harder to trigger intentionally. Best tested by reviewing the text of the instruction change for clarity and completeness.
- **Verify:** Read the updated SKILL.md and confirm the loop-detection instructions are unambiguous: the orchestrator should compare CRITICAL/MAJOR issue titles between consecutive rounds and escalate if any title reappears.
- **Pass criteria:** Instructions are clear enough that an LLM reading them would know exactly what to compare and when to escalate.

### Test 5: Integration — Full dry run
- **Method:** Run `/thorough_plan` end-to-end on a real (small) task after all four changes are applied.
- **Verify:** The full loop works: `/plan` produces a plan, `/critic` reviews it (fresh subagent), `/revise` revises it (fresh subagent per E0), convergence or max-rounds terminates the loop, `/gate` presents the result.
- **Pass criteria:** No regressions. The workflow completes successfully.

---

## Rollback Plan

All changes are to a single file (`dev-workflow/skills/thorough_plan/SKILL.md`). Rollback is straightforward:

1. **Git revert:** `git revert <commit-hash>` — restores the file to its pre-Stage-2 state.
2. **Partial rollback:** If only one change causes issues, manually revert that specific text block. Each task's old/new text is documented above for surgical reversal.
3. **CLAUDE.md desync:** If the SKILL.md is reverted but CLAUDE.md was already updated to say "4 rounds," update CLAUDE.md back to "5 rounds" in the same revert.

No downstream state is affected — these are instruction changes, not data migrations. A revert takes effect immediately on the next `/thorough_plan` invocation.

---

## Addendum: Critic Minor Items (Round 1)

**[MIN-1] Task 1 subagent mechanism vagueness** — Accepted. Add parenthetical "(same mechanism used for /critic above)" to the E0 new text to make the parallel explicit. Updated Task 1 new text accordingly:
```
- **MUST spawn as a new agent session** (same mechanism used for /critic above) — fresh context prevents anchoring on prior orchestrator chatter.
```

**[MIN-2] max_rounds override edge-case handling** — Accepted. Add one sentence to Task 3: "If the value is not a positive integer (e.g., zero, negative, or non-numeric), ignore the override and use the default."

**[MIN-3] CLAUDE.md "5 rounds" update should be bundled** — Accepted. Added as Task 5 below.

**[MIN-4] Task 4b section title mislabeling** — Accepted. Rename subtask 4b to "Loop detection guidance (lines 80 and 122)" without the "Between rounds" prefix.

---

### Task 5: Update CLAUDE.md "5 rounds" references

**Files:**
- `~/.claude/CLAUDE.md` (global)
- `dev-workflow/CLAUDE.md`

Both contain:
```
  - Loop repeats up to 5 rounds until convergence
```

**Change to:**
```
  - Loop repeats up to 4 rounds until convergence (override with max_rounds: N)
```

This is a one-line change in each file. Bundle with the SKILL.md commit to avoid documentation desync.
