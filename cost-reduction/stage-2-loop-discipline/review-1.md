# Code Review — Stage 2: Loop Discipline

## Summary
All 5 tasks from the plan are correctly implemented. The changes to `thorough_plan/SKILL.md` are precise, match the plan's old/new text exactly, and the file reads coherently end-to-end. Both CLAUDE.md files are updated. One minor residual doc desync found in an HTML guide file.

## Verdict: APPROVED

## Plan Compliance

| Task | Status | Notes |
|------|--------|-------|
| Task 1 (E0 — /revise session isolation) | ✅ Complete | Matches plan + MIN-1 fix (parenthetical added) |
| Task 2 (B1 — max_rounds 5→4) | ✅ Complete | All 3 locations updated |
| Task 3 (max_rounds: N override) | ✅ Complete | Section inserted correctly + MIN-2 edge-case sentence added |
| Task 4 (B3 — tighter loop detection) | ✅ Complete | All 3 locations updated |
| Task 5 (CLAUDE.md sync) | ✅ Complete | Both `dev-workflow/CLAUDE.md` and `~/.claude/CLAUDE.md` updated |

No deviations from the plan. All 4 critic MINOR items were addressed in the implementation.

## Issues Found

### Critical (blocks merge)
None.

### Major (should fix before merge)
None.

### Minor (nice to have)
- **[MIN-1]** `dev-workflow/Workflow-User-Guide.html` still references "up to 5 rounds" in two places (lines 102 and 392). This is a generated HTML guide file — lower priority than the SKILL.md and CLAUDE.md sources, but worth updating for consistency.
  - Suggestion: Update the two references in the same commit, or defer as a known desync if the HTML is auto-generated from another source.

## Integration Safety

**Low risk.** All changes are to LLM instruction files, not executable code. The integration surface is:

1. **`/revise` invocation change (E0):** The `/revise` skill already has a "Session bootstrap" section (lines 13-16) that handles fresh session startup. No code changes needed in `revise/SKILL.md`. The orchestrator simply needs to spawn it as a subagent instead of running inline — the same pattern already used for `/critic`.

2. **`max_rounds` override parsing:** This is a new LLM-interpreted parsing rule. The instruction is clear: scan for `max_rounds: N`, strip it, use the value. Edge cases (non-positive, non-integer) are handled with an explicit fallback-to-default instruction.

3. **Loop detection tightening (B3):** The new instructions are strictly more specific than the old ones. The old "same issues repeatedly" is now "same CRITICAL/MAJOR issue title reappearing." This can only improve detection precision, not break anything — and the human is always in the loop (escalation asks, never auto-terminates).

4. **CLAUDE.md updates:** Documentation-only. The SKILL.md is authoritative for behavior.

## Test Coverage

These are instruction-file changes — no executable tests apply. The plan's testing strategy (5 behavioral tests) is appropriate:
- Tests 1-4 will be verified on the next real `/thorough_plan` run
- Test 5 (full dry run) is the most meaningful validation

## Risk Assessment

- **What could break:** Almost nothing. The only behavioral change with any risk is E0 (revise as subagent instead of inline). If the fresh reviser somehow misses context, the critic in the next round will catch it.
- **Blast radius:** Only affects `/thorough_plan` loop behavior. No other skills are impacted.
- **Detection:** The next `/thorough_plan` invocation will exercise all changes.
- **Rollback:** Single `git revert` restores the SKILL.md. `~/.claude/CLAUDE.md` needs manual revert (not in repo).

## Recommendations

1. Fix **MIN-1** (HTML guide "5 rounds") if the file is hand-maintained. Skip if it's auto-generated.
2. Proceed to `/end_of_task`.
