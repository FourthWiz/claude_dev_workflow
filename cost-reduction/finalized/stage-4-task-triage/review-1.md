# Code Review -- Stage 4: Task Triage and Shortcut Paths

**Reviewer:** Opus (fresh session)
**Date:** 2026-04-12
**Files reviewed:**
- `dev-workflow/skills/thorough_plan/SKILL.md`
- `dev-workflow/skills/gate/SKILL.md`
- `dev-workflow/CLAUDE.md`

## Summary

Stage 4 is well-implemented. All seven plan tasks (T1-T7) are addressed. The three modified files are internally consistent with each other -- triage criteria, profile tables, gate levels, and convergence summary format all align across files. The `strict:` backward compatibility is preserved. The CRITICAL RULE paragraph survived the edit intact. Critic issues from both rounds were addressed in the implementation.

Two minor issues found; no critical or major issues.

## Verdict: APPROVED

## Plan Compliance

### Task 1: Add triage parsing and routing to `/thorough_plan` -- PASS

The entire "Parse runtime overrides" section (SKILL.md lines 30-64) has been replaced with the plan's specified content. Verified:
- Step 1 (`strict:`) sets Large profile and skips step 1b -- correct
- Step 1b (`small:`, `medium:`, `large:`) parses profile tags -- correct
- Step 1c (auto-classification with user confirmation) -- correct, includes "default to Medium" rule
- Step 2 (`max_rounds: N`) with profile-specific defaults (4 for Medium, 5 for Large) -- correct
- Step 3 (profile defaults table) matches plan exactly: Small/Medium/Large rows with model mode, max_rounds, critic loop, gate level columns
- "Important" note about Small discarding `max_rounds` -- present
- Auto-classification latency note -- present
- All 8 examples from the plan are present verbatim

Section 3b (Task triage criteria) is present at lines 66-91 with Small/Medium/Large criteria matching the plan.

Small-profile routing section at lines 110-118 matches the plan: single `/plan` pass, smoke gate, convergence summary, STOP.

"Medium and Large profiles" heading at line 120 correctly scopes the existing loop diagram.

**Acceptance criteria:** All 6 criteria from the plan are satisfied.

### Task 2: Update `/gate` skill to support gate levels -- PASS

Gate levels section added at lines 18-56 of `gate/SKILL.md`:
- Smoke gate definition (lines 22-26) -- matches plan
- Standard gate definition (lines 28-34) -- matches plan
- Full gate definition (lines 36-44) -- matches plan
- Determination table (lines 50-55) with Previous/Next phase matrix -- matches plan exactly
- "Default to Full" fallback rule -- present at line 56

Step 2 automated checks (lines 79-116) replaced with gate-level-aware version:
- After /architect check preserved as-is (no gate level concept) -- correct
- After /thorough_plan -> before /implement now uses Smoke gate -- correct
- After /implement -> before /review split into Standard (Small/Medium) and Full (Large) -- correct
- After /review -> before /end_of_task always Full -- correct

Note: The plan's old text header said "lines 41-70" but the actual content in the file started at line 43. The critic flagged this as MIN-R2-1. The implementation correctly matched on content rather than line numbers, so this was a non-issue.

**Acceptance criteria:** All 5 criteria from the plan are satisfied.

### Task 3: Update `dev-workflow/CLAUDE.md` -- PASS

**Change 1 (Workflow sequence):** Lines 49-100 of CLAUDE.md contain the updated workflow sequence. Verified:
- "Full flow (Medium and Large tasks)" heading with the original flow diagram -- present
- "Shortcut flow (Small tasks)" heading with the `/thorough_plan` -> GATE -> `/implement` flow -- present
- Task profiles table with all three profiles (Small/Medium/Large) including trigger, planning, critic loop, gate intensity, typical cost -- present and matches plan
- Triage criteria "at a glance" summary -- present
- Updated stage descriptions with profile-aware routing for `/thorough_plan` bullet -- present
- Updated gate descriptions showing Standard for Small/Medium, Full for Large -- present
- "Not every task needs every stage" updated to "Small tasks typically skip `/architect` entirely. Bug fixes might only need `/implement` + `/review` (bypassing `/thorough_plan` entirely)." -- present, matches plan's MIN-3 fix

**Change 2 (Triage criteria section):** Lines 111-136 contain the new "Task triage criteria" section. Placement is correct -- after the "Multiple sessions can run in a day..." paragraph (line 109) and before "## Session independence" (line 138). Criteria match the plan and `thorough_plan/SKILL.md` section 3b.

**Change 3 (Model assignment table):** Line 332 contains the updated `/thorough_plan` row: "Orchestrates task triage and plan->critic->revise loop. Routes Small tasks to single-pass /plan; Medium uses Sonnet /revise-fast; Large/strict: uses all-Opus. Critic always Opus." -- matches plan.

**CRITICAL RULE preservation:** Line 102 reads: `**CRITICAL RULE: /implement and /end_of_task require explicit user commands.**` -- intact and correctly positioned immediately after the workflow sequence section.

**Acceptance criteria:** All 5 criteria from the plan are satisfied.

### Task 4: Update convergence summary to include task profile -- PASS

SKILL.md lines 181-190 contain the updated convergence summary template:
- `Task profile:` field added as the first bullet -- correct
- `Rounds:` now includes "(Small tasks: 1, single pass)" note -- correct
- `Key revisions:` includes "or 'N/A -- single-pass plan' for Small" -- correct
- Post-template note about Small-profile plans at line 190 -- present

**Acceptance criteria:** All 3 criteria satisfied.

### Task 5: Update examples section -- PASS (no-op)

Correctly marked as covered by Task 1. The examples in the Task 1 replacement block include all triage prefix combinations. No separate action needed.

### Task 6: Update frontmatter description -- PASS

SKILL.md line 3 contains the updated description mentioning triage, all three profiles, size tags, `strict:` prefix, `max_rounds:` override, and "Always the entry point for planned work." Matches the plan.

The trigger phrase overlap note from the plan (`'plan this'` overlapping with `/plan`) is acknowledged in the plan text. The implementation includes it as specified.

### Task 7: REMOVED -- PASS (acknowledged)

Correctly removed per plan. Global `~/.claude/CLAUDE.md` is updated via `install.sh`, not directly.

## Cross-File Consistency Checks

### 1. Triage criteria consistency: `thorough_plan/SKILL.md` section 3b vs `CLAUDE.md` "Task triage criteria"

**PASS.** Both files have substantively identical criteria:

- **Small:** Both list: 1-3 files single module, no integration points, well-understood pattern (bug fix, config change, etc.), localized failure, no data/auth/shared-state changes.
- **Medium:** Both list: multiple files across 1-2 modules, backward-compatible integration changes, some unknowns, subsystem-level failure, includes new features/refactors/retry logic.
- **Large:** Both list: multiple services/repos/layers, data consistency/auth/contracts, significant unknowns/migrations, multi-service/all-user failure, includes DB migrations/auth overhauls/API versioning.

The "when ambiguous" rule differs slightly in wording but is semantically equivalent:
- `thorough_plan/SKILL.md`: "choose the more cautious (larger) profile"
- `CLAUDE.md`: "choose Medium"

Both are correct in their context: the SKILL.md rule is general (could mean Small->Medium or Medium->Large), while CLAUDE.md's simplified version defaults to the safe middle. No functional conflict.

### 2. Profile behavior consistency: `thorough_plan/SKILL.md` step 3 table vs `CLAUDE.md` task profiles table

**PASS.** The two tables are consistent:

| Attribute | SKILL.md step 3 | CLAUDE.md profiles table |
|-----------|-----------------|--------------------------|
| Small model | N/A (single pass) | Single `/plan` pass (Opus) |
| Small max_rounds | N/A | (not shown -- implicit skip) |
| Small critic | Skip | Skipped |
| Small gate | Smoke + Standard + Full | Smoke -> Standard -> Full |
| Medium model | Normal (Opus /plan, Sonnet /revise-fast, Opus /critic) | `/plan` (Opus) + critic loop with Sonnet `/revise-fast` |
| Medium max_rounds | 4 | Up to 4 rounds |
| Medium gate | Smoke + Standard + Full | Smoke -> Standard -> Full |
| Large model | Strict (all Opus) | `/plan` (Opus) + critic loop with Opus `/revise` |
| Large max_rounds | 5 | Up to 5 rounds |
| Large gate | Smoke + Full + Full | Smoke -> Full -> Full |

Cost estimates in CLAUDE.md (~$2.49, ~$2.99-$4.00, ~$4.65+) match the plan's DD5/DD6 analysis.

### 3. Gate level consistency across all three files

**PASS.** 

- `gate/SKILL.md` determination table (line 50-55): `/thorough_plan`->/implement = Smoke for all; /implement->/review = Standard/Standard/Full; /review->/end_of_task = Full/Full/Full.
- `CLAUDE.md` (line 94): "Standard for Small/Medium, Full for Large" for post-implement gate; (line 96): "Full checks" for post-review gate.
- `thorough_plan/SKILL.md` step 3 table: Small = "Smoke (plan) + Standard (post-implement) + Full (pre-merge)"; same pattern for Medium; Large = "Smoke (plan) + Full (post-implement) + Full (pre-merge)".

All three files agree on every gate level assignment.

### 4. `strict:` backward compatibility

**PASS.** `strict:` is preserved exactly:
- SKILL.md step 1 (line 34): "If `strict:` is present, set task profile to **Large** and skip step 1b."
- SKILL.md step 1b (line 36): "`large:` is specified, it is equivalent to `strict:` (all-Opus, max 5)"
- SKILL.md step 3 table: Large = "Strict (all Opus)", max 5
- CLAUDE.md profiles table (line 73): Large triggered by "`large:` or `strict:` prefix"
- Examples demonstrate `strict:` working as before (lines 62-63)

`large:` is a new alias for `strict:`. `strict:` behavior is unchanged. Full backward compatibility.

### 5. Convergence summary format: `thorough_plan/SKILL.md` template vs `gate/SKILL.md` reading

**PASS.**
- SKILL.md template (line 183): `- **Task profile:** <Small | Medium | Large>`
- gate/SKILL.md (line 48): "Read the task profile from the convergence summary at the top of `current-plan.md` (look for 'Task profile: Small/Medium/Large')"

The gate's reading instruction matches the template format. The parenthetical "(look for 'Task profile: Small/Medium/Large')" is explicit enough for an AI reader.

### 6. CRITICAL RULE preservation

**PASS.** CLAUDE.md line 102: `**CRITICAL RULE: /implement and /end_of_task require explicit user commands.** No skill may auto-invoke either. After /thorough_plan converges, the workflow STOPS and waits for /implement. After /review approves and the gate passes, the workflow STOPS and waits for /end_of_task. The user must consciously decide to start writing code AND to ship it.`

Present and correctly positioned immediately after the workflow sequence section, before session lifecycle bullets.

## Architecture Compliance

### D1 (Explicit task-size triage) -- IMPLEMENTED
Task profiles (Small/Medium/Large) with user tags and auto-classification at the top of `/thorough_plan`. Matches D1.

### D2 (Single-pass plan mode) -- IMPLEMENTED
Small tasks route to single `/plan` pass without critic loop. The plan correctly uses `/thorough_plan` as the entry point (DD1) rather than requiring users to invoke `/plan` directly, which is a UX improvement over the architecture's literal wording.

### D3 (Cheap gates by default) -- IMPLEMENTED
Smoke/Standard/Full gate levels. The smoke gate checks plan artifacts rather than "lint + affected tests" as the architecture originally stated -- this is a justified deviation since you cannot lint code that hasn't been written yet. The plan's DD4 explains the rationale.

### Justified deviations documented:
- **DD5:** `/review` stays on Opus for all task sizes (architecture said Sonnet for Small). Documented with cost analysis.
- **DD6:** `/plan` stays on Opus for all task sizes (architecture said Sonnet for Small). Documented with rationale that Stage 3 eliminated `/plan-fast` and cost savings from skipping the critic loop are sufficient.

Both deviations are well-reasoned. The architecture's Small-task cost estimate was ~$1.30; the plan's approach costs ~$2.49 -- still a 47% reduction from the pre-Stage-4 baseline of ~$4.65. The quality tradeoff is sound: since Small tasks skip the critic loop entirely, keeping both `/plan` and `/review` on Opus provides a stronger safety net.

## Issues Found

### Minor

**MIN-1: Ambiguity default wording divergence between `thorough_plan/SKILL.md` and `CLAUDE.md`**

`thorough_plan/SKILL.md` line 91: "When the classification is ambiguous, choose the more cautious (larger) profile."
`CLAUDE.md` line 136: "Rule: when the classification is ambiguous, choose Medium."

These are not contradictory (Medium is the "more cautious" choice when the ambiguity is between Small and Medium, which is the most common case), but they give different guidance for a Medium-vs-Large ambiguity. The SKILL.md wording would push toward Large; the CLAUDE.md wording would keep it at Medium.

The SKILL.md wording is the operationally correct one (it is the instruction the AI orchestrator actually follows during triage). The CLAUDE.md version is a user-facing summary. The practical risk is low since auto-classification asks for user confirmation, but the inconsistency could cause confusion if someone reads both.

**Suggestion:** Align CLAUDE.md line 136 to: "Rule: when the classification is ambiguous, choose the more cautious (larger) profile. Medium is the safe default for Small-vs-Medium ambiguity." Or keep the current wording and accept the minor inconsistency -- it does not affect runtime behavior since the SKILL.md instruction takes precedence.

**MIN-2: D3 smoke gate deviation from architecture not documented as a numbered DD**

The architecture (D3, line 137) says a smoke gate includes "lint + the affected tests." The implementation's smoke gate checks plan artifact existence and task list quality -- no lint or tests. This is the correct design (you cannot lint or test code that hasn't been written yet), and the plan's DD4 explains the rationale. However, Round 2 critic (MIN-R2-3) suggested adding an explicit deviation note, and it was not added.

**Suggestion:** Add one sentence to DD4 or to the integration analysis: "Note: the architecture's D3 describes the smoke gate as 'lint + the affected tests,' but those checks logically apply after implementation, not after planning. The pre-implement smoke gate checks plan artifact quality instead; lint and tests are part of the Standard gate (post-implement)." This is purely for documentation completeness.

## Integration Safety

**Safe.** The three modified files are all `.md` instruction files consumed by the AI at runtime. No code, no infrastructure, no data migrations.

- `/plan`, `/critic`, `/revise`, `/revise-fast` skill files are unchanged
- `/implement`, `/review` skill files are unchanged
- The gate's "default to Full when unknown" fallback ensures pre-Stage-4 plans are safe
- `strict:` behavior is preserved character-for-character in the parsing logic
- No new skill files were created (Stage 3's cleanup of `/plan-fast` was preserved)

The `plan-fast/SKILL.md` deletion noted in the gate results predates Stage 4 and should be committed separately as a cleanup.

## Risk Assessment

**Low risk overall.** The implementation:

1. Adds no new skill files -- only modifies three existing `.md` files
2. Preserves all backward compatibility paths (`strict:`, no-tag defaults to Medium, pre-Stage-4 plans trigger Full gate)
3. Provides three independent rollback levels (full, gate-only, auto-classification-only)
4. Keeps the two strongest safety nets unchanged: Opus `/review` and Full pre-merge gate for all task sizes

The highest-risk scenario (R5: misclassification of a Large task as Small) is mitigated by: user confirmation of auto-classification, Medium as the default, Opus `/review` as safety net, and Full pre-merge gate. This is well-reasoned.

## Recommendations

1. **Commit the `plan-fast/SKILL.md` deletion** as a separate cleanup commit before or alongside the Stage 4 commit. It is a pre-existing change from Stage 3 that has not been committed yet.

2. **(Optional) Align the ambiguity-default wording** between SKILL.md and CLAUDE.md per MIN-1 above. Low priority.

3. **(Optional) Add D3 deviation note** per MIN-2 above. Documentation completeness only.

4. **Test manually after merge** with at least the first 4 parsing scenarios from the plan's testing strategy (tests 1-4) to confirm the triage routing works end-to-end in a real session.
