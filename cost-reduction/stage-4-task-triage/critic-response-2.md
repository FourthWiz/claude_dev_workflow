# Critic Response — Round 2

**Plan reviewed:** Stage 4 — Task Triage and Shortcut Paths (revised)
**Date:** 2026-04-12

## Verdict: PASS

## Round 1 issue resolution

### CRIT-1: Architecture specifies Sonnet `/plan` for Small tasks, plan uses Opus `/plan`
**RESOLVED.** DD6 (lines 74-93 of the revised plan) explicitly documents the deviation from the architecture spec, with a clear rationale (Stage 3 eliminated `/plan-fast`, critic loop is already skipped so plan quality matters more, cost savings still significant at 47% reduction). The cost comparison table makes the tradeoff concrete and visible. This is exactly what the critic asked for — option (a) from CRIT-1's required fix.

### CRIT-2: Plan quotes wrong/fragmented "old text" for parsing section replacement
**RESOLVED.** Task 1 now provides a single complete contiguous replacement block covering the entire "Parse runtime overrides" section from lines 30-42 of the actual file. The old text is quoted accurately (verified: the plan's quoted old text matches the file content character-for-character). Step numbering is coherent: 1, 1b, 1c, 2, 3. The `max_rounds: N` step is included and renumbered to step 2. The examples block is part of the same atomic replacement. Task 5 is correctly marked as "covered by Task 1."

### MAJ-1: CLAUDE.md replacement boundary ambiguity
**PARTIALLY RESOLVED.** The plan now explicitly states: "Stop before the blank line and the `**CRITICAL RULE:**` paragraph — that paragraph (line 83) and everything after it are **not** part of this replacement and must remain unchanged." This is clear guidance. However, the stated line range is still wrong — see NEW MAJOR issue MAJ-1 below.

### MAJ-2: Gate Step 2 replacement does not specify exact old text
**RESOLVED.** Task 2 now provides the exact old text for the four check blocks (lines 43-70 of `gate/SKILL.md`), quoted verbatim. Verified against the actual file: the quoted text matches character-for-character. The Edit tool can match on this text.

### MAJ-3: `small: max_rounds:` interaction not formally specified
**RESOLVED.** Step 3 of the parsing logic now includes an explicit "Important" note: "For Small-profile tasks, `max_rounds` is ignored — there is no critic loop and therefore no round cap applies. If `max_rounds: N` was parsed in step 2, discard it when the profile is Small." Test case 6 also reflects this behavior. Clear and unambiguous.

### MAJ-4: Insertion point for triage criteria in CLAUDE.md not precise
**RESOLVED.** Task 3, Change 2 now specifies: "Insert after this exact line: `Multiple sessions can run in a day (parallel tasks)...`" and "before the `## Session independence` heading (line 86)." The anchor line is quoted verbatim, enabling precise Edit tool placement. Verified against the actual file: line 84 matches the quoted text, line 86 is `## Session independence`.

## NEW CRITICAL issues

None.

## NEW MAJOR issues

### MAJ-1: CLAUDE.md replacement line range "49-81" does not match the quoted old text

Task 3, Change 1 says: "Replace lines 49-81 of CLAUDE.md — from the `## Workflow sequence` heading through the end of the 'Not every task needs every stage' paragraph."

However, the quoted old text ends with: "Not every task needs every stage. Small, well-understood changes can skip `/architect` and go straight to `/thorough_plan`. Bug fixes might only need `/implement` + `/review`. But gates ALWAYS run between phases."

That line is **line 75** in the actual file, not line 81. Lines 77-84 contain the `**CRITICAL RULE:**` paragraph and the session lifecycle content, which are explicitly stated to be preserved.

The stated range "49-81" would include:
- Line 77: `**CRITICAL RULE:**` paragraph
- Lines 79-81: Session lifecycle bullets (`/start_of_day`, `/end_of_day`, `/weekly_review`)

If an implementer follows the line numbers (49-81) rather than the quoted text, they would delete the CRITICAL RULE paragraph and the first three session lifecycle bullets. The plan's prose correctly says "Stop before the `**CRITICAL RULE:**` paragraph" but the line numbers contradict this.

**Required fix:** Change "lines 49-81" to "lines 49-75" throughout Task 3, Change 1. The quoted old text is correct; only the line numbers are wrong. Alternatively, remove the line numbers entirely and rely solely on the exact quoted text for Edit tool matching (which is how the Edit tool actually works — it matches on text content, not line numbers).

**Severity rationale:** This is MAJOR rather than CRITICAL because (a) the quoted old text is correct and an implementer who uses the Edit tool's text-matching will get the right result, and (b) the plan's prose explicitly says to stop before the CRITICAL RULE paragraph. The error is in the line number metadata, not the operational content. But it should be fixed to avoid any possibility of misinterpretation.

## NEW MINOR issues

### MIN-1: Gate old text line range says "lines 41-70" but quoted text starts at line 43

Task 2's "Old text (exact, lines 41-70)" header claims the block starts at line 41, but the quoted text begins with `**After /architect → before /thorough_plan:**` which is line 43 in the actual file. Lines 41-42 are:
```
Based on what exists and what's next, run the appropriate checks:

```
(The intro sentence and a blank line.) This is cosmetic — the Edit tool matches on content, and the intro sentence should remain as a lead-in to the new gate-level-aware checks. But the line number label is inaccurate.

**Suggestion:** Change to "lines 43-70" or remove line numbers and let the exact text match speak for itself.

### MIN-2: The new text for CLAUDE.md Change 1 includes nested code fences that may cause rendering issues

The plan's new text for the CLAUDE.md workflow sequence section contains two code fence blocks (for "Full flow" and "Shortcut flow") inside a larger code fence that delimits the replacement text. When rendered in markdown or when an implementer extracts the replacement text, the nested fences could cause confusion about where the replacement content ends.

This is a presentation concern, not a logic error. The implementer needs to be careful about which closing ``` marks the end of the replacement text vs. the end of an inner code block. The plan's structure makes this clear in context, but it could be cleaner.

**Suggestion:** Use different fence markers (e.g., ``````) for the outer plan-level code blocks, or add a clear "END OF REPLACEMENT TEXT" marker.

### MIN-3: Architecture deviation on smoke gate content should be noted

Round 1's MIN-4 noted that the architecture (D3, line 137) says a smoke gate should include "lint + the affected tests" while the plan's smoke gate is lighter (artifact existence + task list only). The Round 1 critic suggested adding a deviation note. The plan's revision notes (line 785-788) mention addressing MIN-4 but only reference MIN-1 through MIN-3. MIN-4's suggestion to acknowledge the deviation from D3's wording was not explicitly addressed in the plan text.

This is truly minor — the plan's smoke gate design is sensible (you cannot lint code that hasn't been written yet), and the architecture's D3 wording was imprecise about when lint runs. But a one-sentence note in DD4 or the integration analysis would close the loop cleanly.

**Suggestion:** Add to DD4: "Note: the architecture's D3 says the smoke gate includes 'lint + affected tests,' but lint and tests logically apply after implementation, not after planning. The pre-implement smoke gate checks plan artifact quality; lint and tests are part of the Standard gate (post-implement)."

## What the plan gets right

1. **DD6 is the right call.** Keeping Opus `/plan` for Small tasks is the defensible choice given that the critic loop is skipped. The explicit cost comparison (architecture's $1.30 vs. plan's $2.49 vs. baseline $4.65) makes the tradeoff transparent and lets the team revisit the decision later with data.

2. **The complete section replacement (Task 1) is much cleaner.** One atomic edit for the entire parsing section eliminates all ambiguity about step numbering, old/new text boundaries, and insertion points. This was the right structural fix for CRIT-2.

3. **The `max_rounds` discard note for Small tasks is clean.** The explicit "Important" callout in step 3 and the matching test case (test 6) make the behavior unambiguous. This was a subtle interaction that could have caused silent confusion; now it is explicitly documented.

4. **The revision notes section is valuable.** Having a clear audit trail of what changed and why (lines 767-788) makes it easy to verify that each Round 1 issue was addressed. This is good practice for multi-round revision workflows.

5. **The plan's overall coherence is strong.** All seven tasks tell a consistent story. The triage parsing (Task 1) produces a profile, the convergence summary (Task 4) propagates it, the gate (Task 2) consumes it, and the documentation (Tasks 3, 6, 7) describes it. No contradictions between tasks.

6. **Backward compatibility is well-handled.** `strict:` is preserved as an alias for `large:`. No-tag defaults to Medium (current behavior). Pre-Stage-4 plans trigger Full gate (safe fallback). The three rollback paths (full, gate-only, auto-classification-only) are concrete and independent.

7. **The auto-classification latency note (MIN-1 from Round 1) is addressed.** The note about explicit tags skipping the confirmation round-trip is a nice UX touch that was missing from the original plan.
