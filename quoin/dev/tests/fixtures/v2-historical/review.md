# Review 1 — Stage 3: Planner-Side Model Tiering

**Reviewer:** /review (Opus)
**Date:** 2026-04-12
**Branch:** feat/stage-2-loop-discipline (commit b7f371a)
**Verdict:** APPROVED

---

## Summary

Stage 3 is implemented correctly. All 10 planned tasks are accounted for, the -fast skill files are properly synced with their Opus originals, the orchestrator's model selection logic is sound, and the `strict:` escape hatch interacts correctly with `max_rounds: N`. Task 8 (`~/.claude/CLAUDE.md` update) was correctly reverted per user feedback. No blocking issues found.

---

## Task-by-task verification

### Task 1: Create `/plan-fast` skill file -- PASS

- File exists at `dev-workflow/skills/plan-fast/SKILL.md`
- Frontmatter: `name: plan-fast`, `model: sonnet`, description mentions "Fast variant" and "Not intended for direct user invocation"
- Body sync verified: `diff` of body content (from `# Plan` onward) shows exactly ONE difference -- the "Model requirement" section. Plan body is otherwise character-identical to `plan/SKILL.md`.

### Task 2: Create `/revise-fast` skill file -- PASS

- File exists at `dev-workflow/skills/revise-fast/SKILL.md`
- Frontmatter: `name: revise-fast`, `model: sonnet`, description correct
- Body sync verified: `diff` shows only the "Model requirement" section differs from `revise/SKILL.md`

### Task 3: `strict:` parsing in runtime overrides -- PASS

- Section "### 3. Parse runtime overrides" correctly updated
- Parse order is explicit: `strict:` first (item 1), `max_rounds: N` second (item 2)
- `strict:` description: begins with literal token, case-insensitive, stripped from description, defaults max_rounds to 5, user can override with max_rounds: N
- MAJ-3 fix confirmed: now says "before passing it to the planner skill" (model-agnostic) instead of "before passing it to `/plan`"
- Three examples provided covering normal, strict, and strict+max_rounds combinations

### Task 4: Model selection per round table -- PASS

- New section "### 4. Model selection per round" inserted between overrides and loop
- Table covers all round/mode combinations:
  - Round 1: `/plan-fast` (normal) / `/plan` (strict)
  - Rounds 2-3: `/revise-fast` (normal) / `/revise` (strict)
  - Round 4+ (final): `/revise` Opus in both modes
  - Critic: always Opus in all rows
- Key rules section is clear and unambiguous
- Final-round escalation correctly generalized: "only the final allowed round escalates `/revise` to Opus"

### Task 5: "Invoking each agent" section -- PASS

- Headers updated to: `**\`/plan\` or \`/plan-fast\` (Round 1 only)**` and `**\`/revise\` or \`/revise-fast\` (rounds 2+)**`
- MAJ-2 fix confirmed: headers use slash-command format, consistent with rest of file
- Critic subsection now explicitly says "Always Opus. Never tiered. This is non-negotiable."
- Revise subsection correctly describes Sonnet for rounds 2 through max_rounds-1, Opus for final round, always Opus in strict mode

### Task 5a: Update remaining stale references -- PASS

- **Change 1 (line 9 intro):** Updated from "three sub-skills in sequence: `/plan`, `/critic`, and `/revise`" to "sub-skills -- `/plan` (or `/plan-fast`), `/critic`, and `/revise` (or `/revise-fast`) -- based on mode and round" with reference to model selection section. MAJ-1 fix confirmed.
- **Change 2 (loop diagram note):** Blockquote note added after the diagram: "The diagram above shows `/plan` and `/revise` generically. The actual skill variant spawned each round depends on mode (normal vs. strict)..." MAJ-1 fix confirmed.
- **Change 3 (important behaviors):** Updated from "invoke `/plan`, `/critic`, `/revise`" to "invoke `/plan` (or `/plan-fast`), `/critic`, `/revise` (or `/revise-fast`)". MAJ-1 fix confirmed.

### Task 6: Frontmatter description update -- PASS

- Old: "...using the strongest model (Opus)"
- New: "...Uses Sonnet for planning/revision and Opus for critique by default; use 'strict:' prefix for all-Opus"
- Added mention of "strict:" and "5 rounds" to the description

### Task 7: `dev-workflow/CLAUDE.md` model assignments -- PASS

- `/plan-fast` and `/revise-fast` rows added to the table
- Existing `/plan`, `/critic`, `/revise`, `/thorough_plan` rows updated with parenthetical context (e.g., "used in strict mode and standalone", "never tiered", "used in strict mode and final round")
- All 18 skills now represented in the table

### Task 8: `~/.claude/CLAUDE.md` update -- CORRECTLY REVERTED

- Verified: `~/.claude/CLAUDE.md` does NOT contain `/plan-fast` or `/revise-fast`
- The global config was NOT modified by Stage 3, per user's explicit instruction that feature branch work should not touch `~/.claude/CLAUDE.md`
- This is correct behavior -- the global file should only be updated when the feature merges

### Task 9: Sync warning comments -- PASS

- `plan-fast/SKILL.md` has sync warning HTML comment after frontmatter
- `revise-fast/SKILL.md` has sync warning HTML comment after frontmatter
- Both include: description of intentional differences, bidirectional edit guidance, diff command for verification, expected diff output
- MIN-4 fix confirmed: diff commands use full paths from project root (`dev-workflow/skills/plan/SKILL.md` etc.)

---

## Cross-cutting verification

### No unintended modifications -- PASS

Verified via `git diff 0a72a88...HEAD` (Stage 3 only, excluding prior Stage 2 changes):

- `dev-workflow/skills/plan/SKILL.md` -- **NOT modified** (confirmed zero diff)
- `dev-workflow/skills/revise/SKILL.md` -- **NOT modified** (confirmed zero diff)
- `dev-workflow/skills/critic/SKILL.md` -- **NOT modified** by Stage 3 (changes in full branch diff are from Stage 2's E0 fix, not Stage 3)
- `~/.claude/CLAUDE.md` -- **NOT modified** (not in repo, grep confirms no plan-fast/revise-fast)

Only 8 files changed in Stage 3 commit: the 3 planning artifacts, gate file, CLAUDE.md, plan-fast/SKILL.md, revise-fast/SKILL.md, thorough_plan/SKILL.md.

### Sync check: -fast files vs originals -- PASS

- `plan-fast` vs `plan`: body differs ONLY in the "Model requirement" section (1 line)
- `revise-fast` vs `revise`: body differs ONLY in the "Model requirement" section (1 line)
- No behavioral drift, no template differences, no missing sections

### `strict:` + `max_rounds: N` interaction -- PASS

The parsing order is explicit and correct:

1. `strict:` parsed first, stripped from description, sets default max_rounds to 5
2. `max_rounds: N` parsed second, overrides whatever default was set

Tested against examples in the plan:
- `strict: max_rounds: 3 quick but safe` -- strict mode on, cap = 3 (overrides 5)
- `strict: handle the auth migration carefully` -- strict mode on, cap = 5 (default)
- `max_rounds: 6 this migration is gnarly` -- normal mode, cap = 6

### Edge cases -- PASS

- **max_rounds: 1** -- Only round 1 runs: `/plan-fast` + `/critic`. No revise round. The "final round = Opus" rule applies to the reviser, which never runs. Acceptable -- the plan is critic-checked once and returned as-is if PASS.
- **max_rounds: 2** -- Round 1: `/plan-fast` + `/critic`. Round 2 is the final round, so `/revise` (Opus). Correct -- the key rule says "the final round still uses Opus `/revise`" regardless of cap value.
- **max_rounds: 2 in strict mode** -- All Opus: `/plan` round 1, `/revise` round 2. Correct.
- **max_rounds: 3 in normal mode** -- Round 1: `/plan-fast`. Round 2: `/revise-fast`. Round 3 (final): `/revise` (Opus). Correct per table (rounds 2-3 row says `/revise-fast`, but key rules say final round escalates).

One subtle point: the table says rounds "2-3" use `/revise-fast`, but if max_rounds is 3, round 3 is the final round and should use Opus `/revise`. The key rules section resolves this correctly: "only the final allowed round escalates `/revise` to Opus. If `max_rounds` is overridden to a value less than 4, the final round still uses Opus `/revise`." The key rules take precedence over the table row labels, and this is clear enough for an LLM orchestrator to follow.

### Architecture compliance -- PASS

Verified against architecture.md lines 348-374:
- Two-file approach for tiered roles: implemented correctly
- Critic always Opus: respected
- Round 4 final escalation generalized to "final allowed round": positive deviation, as noted by critic
- `strict:` escape hatch protocol: matches architecture specification exactly
- `max_rounds: N` continues to work as cap-control mechanism: confirmed

### Consistency of references -- PASS

All references to `/plan` and `/revise` in `thorough_plan/SKILL.md` now acknowledge the `-fast` variants:
- Line 9 (intro sentence)
- Section 3 (parse overrides)
- Section 4 (model selection table)
- Loop diagram (blockquote note)
- "Invoking each agent" section headers and bullets
- "Important behaviors" section

No stale references remain.

---

## Issues found

### MINOR

**MIN-1: Table row labels may cause confusion for edge case max_rounds values**

The model selection table labels rounds "2-3" as `/revise-fast` and "4+ (final)" as `/revise` Opus. With `max_rounds: 3`, round 3 is both "in the 2-3 range" and "the final round." The key rules section resolves this correctly, but the table alone could be misread.

Not blocking -- the key rules are explicit and take precedence. An LLM orchestrator reading the full section will get it right.

**MIN-2: `dev-workflow/CLAUDE.md` header skill listing does not include -fast variants**

Line 3 of `dev-workflow/CLAUDE.md` lists all skills but does not include `/plan-fast` or `/revise-fast`. This was noted by the critic (MIN-2 in round 1) and intentionally deferred since these are internal skills not meant for direct invocation. Acceptable.

---

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Plan compliance | Good | All 10 tasks implemented, Task 8 correctly reverted |
| Correctness | Good | All text matches plan specifications, sync verified |
| Consistency | Good | All stale references updated, naming conventions preserved |
| Edge case handling | Good | max_rounds interaction with strict: and final-round escalation are sound |
| No unintended changes | Good | Only expected files modified, protected files untouched |
| Architecture alignment | Good | Matches architecture spec, positive deviations noted |
| Maintainability | Good | Sync warnings, diff commands, clear model selection rules |

---

## Verdict: APPROVED

The implementation is clean, complete, and faithful to the converged plan. All critic issues from rounds 1 and 2 were addressed. The `strict:` escape hatch and model tiering logic are well-specified and handle edge cases correctly. No changes requested.
