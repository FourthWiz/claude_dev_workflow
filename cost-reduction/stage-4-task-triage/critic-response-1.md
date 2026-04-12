# Critic Response — Round 1

**Plan reviewed:** Stage 4 — Task Triage and Shortcut Paths
**Date:** 2026-04-12

## Verdict: REVISE

## CRITICAL issues

### CRIT-1: Architecture specifies Small tasks use Sonnet `/plan`, but the plan uses Opus `/plan`

The architecture document (line 382) says:

> Small -> `/plan` (Sonnet) + `/implement` + `/review` (Sonnet, smoke gate). No critic loop.

The plan (DD5, line 68-73) explicitly overrides this: Small tasks use Opus `/plan` and Opus `/review`. The plan provides a reasoned justification for keeping `/review` on Opus (safety net argument), but it also silently keeps `/plan` on Opus for Small tasks without acknowledging this is a deviation from the architecture spec.

This matters because the architecture's cost model for Small tasks assumed Sonnet for both `/plan` and `/review`. The plan's cost estimate of "~$2.49" (line 73) uses Opus `/plan` (~$1.32) + Opus `/review` (~$1.17), which is significantly more expensive than the architecture's intended Sonnet `/plan` + Sonnet `/review` path.

**Required fix:** Either:
(a) Acknowledge the deviation explicitly in a "Design Decisions" section (e.g., "DD6: Small tasks still use Opus `/plan`") with rationale for why Sonnet `/plan` was rejected, OR
(b) Create a `/plan-fast` (Sonnet) variant for Small tasks, which is what the architecture intended.

Option (a) is strongly recommended — the plan's reasoning about `/review` quality applies equally to `/plan` quality (a bad plan from Sonnet means a worse implementation regardless of review quality), and the infrastructure was deliberately simplified in Stage 3 by eliminating `/plan-fast`. Re-introducing it for Stage 4 would undo that simplification. But the deviation must be called out, not silently adopted.

### CRIT-2: Plan quotes wrong "old text" for the parsing section replacement

Task 1 states the old text to replace is lines 33-36:

```
### 3. Parse runtime overrides

Before starting the loop, scan the user's task description for runtime overrides. Parse in this order:

1. **`strict:`** (case-insensitive): If the task description begins with the literal token `strict:`, enable strict mode for this run. Strip the `strict:` token from the description. Strict mode forces all-Opus model selection (see "Model selection per round" below) and defaults `max_rounds` to 5 (instead of the normal default of 4). The user can still override `max_rounds` via the `max_rounds: N` token even in strict mode.
```

However, the actual file content at line 30 is `### 3. Parse runtime overrides` and the section header is at line 30 (from what's visible), not line 33. More importantly, the plan says to replace lines 33-36, but the quoted text spans 5 lines (header + blank + intro sentence + blank + step 1 paragraph). The actual `strict:` step is a single long paragraph at line 34. The plan's "old text" reference is imprecise — it includes the section header and step 1 but NOT step 2 (`max_rounds: N`), yet the "new text" completely restructures both steps. 

The plan says "replace the existing parsing instructions" but then the new text only covers step 1 (with additions of 1b and 1c). Step 2 (`max_rounds: N`) is not included in the old text, and the plan says to "Insert after the existing `max_rounds: N` paragraph" for step 3. This means the implementer must: (1) replace lines 30-34, (2) keep line 36 (`max_rounds: N` step) as-is but renumber it to step 2, (3) insert step 3 after it. The numbering will be inconsistent — the new text calls the first items "1", "1b", "1c" and then jumps to "3" without a "2". The `max_rounds: N` step is currently labeled "2" but the new step 3 comes right after it, implying the max_rounds step stays as "2" — but this is never stated.

**Required fix:** Provide the complete replacement text for the entire "Parse runtime overrides" section (steps 1 through 3, including the unchanged `max_rounds: N` step renumbered to fit), rather than separate insert/replace instructions. This eliminates ambiguity about what stays, what moves, and what the final numbering looks like.

## MAJOR issues

### MAJ-1: CLAUDE.md replacement text includes the CRITICAL RULE paragraph but the old_text does not

Task 3, Change 1 says to replace "Old text (lines 49-75)". Looking at the actual file:
- Line 49 = `## Workflow sequence`
- Line 75 = `Not every task needs every stage...`

But line 77 is the `**CRITICAL RULE: /implement and /end_of_task require explicit user commands.**` paragraph. The plan's old text ends at line 75 (after the "But gates ALWAYS run between phases." sentence), but the new text (lines 344-397) includes a replacement for the "Not every task needs every stage" line AND continues past where the old text ended. The critical rule paragraph on line 77 is not in the old text, so it would remain after the replacement — but the new text at line 396 already has a replacement version ("Not every task needs every stage. Small tasks typically skip `/architect` entirely...").

This means after the replacement, the file would have:
1. The new workflow sequence section (including the updated "Not every task needs every stage" text)
2. Immediately followed by the original CRITICAL RULE paragraph (line 77)

That is correct and intended — the CRITICAL RULE paragraph is preserved. However, the plan's old text quote stops at line 75 but the actual line 75 is `Not every task needs every stage. Small, well-understood changes can skip '/architect' and go straight to '/thorough_plan'. Bug fixes might only need '/implement' + '/review'. But gates ALWAYS run between phases.` which is a single line, not wrapped. The new text has "Not every task needs every stage. Small tasks typically skip `/architect` entirely. Bug fixes might only need `/implement` + `/review` (no planning at all). But gates ALWAYS run between phases." also as the last line of the replacement block.

**Required fix:** Verify the exact line boundaries of the replacement. The plan should explicitly state that lines 49-75 are replaced and that the CRITICAL RULE paragraph (line 77) remains unchanged. Currently the old text boundary is ambiguous because the closing triple-backtick in the plan's old text includes a line that looks like it might be line 75 or 76 depending on how the nested code fences are counted.

### MAJ-2: Gate "Step 2" replacement does not specify exact old text

Task 2 says: "Replace the four check blocks with" new text, referencing "the four 'After X -> before Y' blocks, lines 43-70." But it does not provide the exact old_text to match against. For an implementer using the Edit tool (which requires exact string matching), the instruction "replace the four check blocks" is insufficient.

The actual content at lines 43-70 includes section headers, checkbox items, and specific wording. The plan should either:
(a) Quote the exact old text to be replaced, or
(b) Provide explicit instructions like "Delete everything from line 43 through line 70 and insert the following."

**Required fix:** Provide the exact old text for the gate Step 2 replacement, or restructure as "delete lines X-Y, insert at line X."

### MAJ-3: `small: max_rounds:` interaction is mentioned but not formally specified in the parsing logic

Task 5's example says: "`/thorough_plan small: max_rounds: 2 add the config endpoint` -- Small profile ignores max_rounds (no loop), single pass"

But Task 1's parsing logic (the "Apply task profile defaults" table) says Small has `max_rounds: N/A`. The parsing sequence is: (1) strict, (1b) size tag, (2) max_rounds, (3) apply defaults. Step 2 would still parse and strip `max_rounds: 2`, but the Small routing ignores it. This is fine operationally, but the parsing logic in Task 1 never explicitly states "if profile is Small, ignore `max_rounds`." The behavior is implicit from the routing section ("Small-profile routing: do NOT enter the critic loop").

This could confuse the AI orchestrator — it parses `max_rounds: 2`, stores it, and then the Small routing section does not reference it. An explicit note is needed.

**Required fix:** Add to step 3 ("Apply task profile defaults") or to the Small routing section: "For Small-profile tasks, `max_rounds` is ignored since there is no critic loop. If `max_rounds: N` was parsed, it is discarded."

### MAJ-4: Plan does not address where the triage criteria section goes in `CLAUDE.md` relative to session independence

Task 3, Change 2 says: "After the updated 'Workflow sequence' section and before 'Session independence', add..."

Looking at the actual CLAUDE.md:
- Line 75 = end of "Not every task needs every stage..." paragraph
- Line 77 = CRITICAL RULE paragraph
- Lines 79-84 = Session lifecycle paragraph
- Line 86 = blank line
- Line 88 = `## Session independence`

The triage criteria section would be inserted between the session lifecycle bullets and the `## Session independence` heading. But the CRITICAL RULE paragraph and session lifecycle bullets are logically part of the workflow sequence — inserting a `## Task triage criteria` H2 heading between them and `## Session independence` makes sense structurally, but the plan should confirm this is between lines 85-87 (after the session lifecycle content, before Session independence).

**Required fix:** Specify the exact insertion point more precisely — "After the 'Multiple sessions can run in a day...' paragraph (line 84) and before '## Session independence' (line 88)."

## MINOR issues

### MIN-1: The plan's cost estimates may not account for auto-classification prompt overhead

The plan's cost table (line 367-369) shows Small tasks at ~$2.49. But when auto-classification is used (no explicit `small:` tag), the orchestrator must: (1) read the task description, (2) apply triage criteria, (3) present classification to user, (4) wait for confirmation. This adds a conversational round-trip that was not present before. The cost impact is negligible (the orchestrator is already running on Opus), but the latency impact should be acknowledged — auto-classification adds wall-clock time before planning starts.

**Suggestion:** Add a brief note to the integration analysis or risk section: "Auto-classification adds one user confirmation round-trip before planning begins. Users who want to skip this delay can use explicit tags."

### MIN-2: The new frontmatter description (Task 6) says "Use this skill for: /thorough_plan, 'plan this'" which overlaps with `/plan`'s trigger phrases

Task 6's new description includes "'plan this'" as a trigger phrase. The existing `/plan` skill (line 3 of plan/SKILL.md) also triggers on "'plan this'". This could cause skill routing ambiguity — when a user says "plan this," which skill fires?

**Suggestion:** Remove "'plan this'" from the new `/thorough_plan` description to avoid overlap, or accept the ambiguity since the skill registry likely resolves it by specificity.

### MIN-3: The `dev-workflow/CLAUDE.md` new text still says "Bug fixes might only need `/implement` + `/review` (no planning at all)"

This is accurate and preserved from the original, but it now slightly contradicts the triage system's premise that `/thorough_plan` is the "universal entry point for planned work." A bug fix that goes straight to `/implement` + `/review` bypasses triage entirely. This is fine — the plan correctly scopes triage to planned work only — but the parenthetical "(no planning at all)" could be clearer: "(bypassing `/thorough_plan` entirely)."

**Suggestion:** Minor wording tweak for clarity, not blocking.

### MIN-4: Architecture says D3's smoke gate is "lint + the affected tests" but the plan's smoke gate is lighter

Architecture line 137: "A 'smoke gate' (lint + the affected tests) before `/implement`"
Plan's smoke gate (Task 2): "Plan artifact exists and is non-empty; Plan has tasks with file paths and acceptance criteria"

The plan moved lint + affected tests to the "Standard" gate level, which runs after `/implement`, not before it. The pre-implement gate is now lighter than the architecture specified. This is a reasonable deviation (you cannot lint code that hasn't been written yet — lint before `/implement` doesn't make sense), but it should be noted as a deviation.

**Suggestion:** Add a brief note in the design decisions or integration analysis acknowledging this deviation from D3's original wording, with the rationale that lint/test checks logically belong after implementation, not before it.

## What the plan gets right

1. **DD1 (universal entry point) is excellent.** Making `/thorough_plan` the single entry point for all planned work, with automatic triage and routing, eliminates cognitive overhead for the user. This is the cleanest possible UX design.

2. **DD5 (keep `/review` on Opus) is well-reasoned.** The safety net argument is sound: since Small tasks skip the critic loop, downgrading the review as well would create a dangerous quality gap. The cost analysis ($2.49 total for Small with Opus review) makes the tradeoff clear.

3. **Backward compatibility is thoroughly analyzed.** The `strict:` prefix preservation, the "no profile found -> Full gate" fallback, and the explicit backward compatibility test cases (tests 13 and 14) show careful attention to not breaking existing workflows.

4. **The gate level design is pragmatic.** Three levels (smoke, standard, full) with a clear matrix of when each applies is simple to implement and easy to reason about. The "default to Full when uncertain" rule is the right safety default.

5. **The rollback plan is concrete and multi-level.** Full rollback, partial rollback (gate only), and partial rollback (auto-classification only) give three recovery paths at different granularities. All are simple git reverts since the changes are `.md` files only.

6. **Task ordering and dependency analysis are clear.** The implementation order correctly identifies Task 1 as the critical path and shows which tasks can be parallelized.

7. **The testing strategy covers the right edge cases.** The 14 manual verification scenarios cover parsing combinations, gate levels, backward compatibility, and the degenerate case (no description at all).
