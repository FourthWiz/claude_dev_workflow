# Critic Response -- Round 1

**Verdict:** REVISE

## CRITICAL issues (must fix before implementation)

None.

## MAJOR issues (should fix, risk if ignored)

### MAJ-1: Missing updates to loop diagram and introductory text in `thorough_plan/SKILL.md`

The plan updates the "Invoking each agent" section (Task 5) and the frontmatter description (Task 6), but does NOT update three other references to `/plan` and `/revise` that will become misleading after Stage 3:

1. **Line 9** -- "This skill orchestrates the planning convergence loop by invoking three sub-skills in sequence: `/plan`, `/critic`, and `/revise`." After Stage 3 there are five skills involved (`/plan`, `/plan-fast`, `/critic`, `/revise`, `/revise-fast`). This sentence will be factually wrong.

2. **Lines 41-55** (the loop diagram) -- Shows `/plan` and `/revise` without any indication that different variants may be used per round. An LLM reading this diagram in a fresh session will see `/plan` and `/revise` and assume Opus for all, contradicting the model selection table inserted by Task 4.

3. **Line 127** -- "Don't produce plan content yourself -- invoke `/plan`, `/critic`, `/revise`." Same issue: doesn't mention the `-fast` variants.

**Impact:** The orchestrator is an LLM reading instructions. Contradictory instructions within the same file are a quality risk -- the LLM may follow the loop diagram (which says `/plan`) instead of the model selection table (which says `/plan-fast`). This is exactly the kind of source-file contradiction that E0 in Stage 2 was designed to fix.

**Fix:** Add a task that updates:
- Line 9: change to something like "...by invoking sub-skills: `/plan` (or `/plan-fast`), `/critic`, and `/revise` (or `/revise-fast`) based on mode and round -- see 'Model selection per round' for details."
- The loop diagram: add a parenthetical like `(variant per model selection table)` after `/plan` and `/revise`, or add a note below the diagram.
- Line 127: add "(or their `-fast` variants)" after the skill names.

### MAJ-2: Task 5 "Invoking each agent" old_string does not exactly match the file for the `/plan` subsection

Task 5's old text says:

```
**`/plan` (Round 1 only)**
- Invoke with the strongest model (Opus)
```

The actual file at line 60-61 says:

```
**`/plan` (Round 1 only)**
- Invoke with the strongest model (Opus)
```

These appear to match on inspection. However, the plan changes the heading from `**\`/plan\` (Round 1 only)**` to `**Planner (Round 1 only)**` and from `**\`/revise\` (rounds 2+)**` to `**Reviser (rounds 2+)**`. This name change breaks the internal consistency of the file -- everywhere else in the file (`/plan`, `/critic`, `/revise`) uses the slash-command name format. The critic and revise subsections use backtick-quoted skill names. Changing `/plan` to "Planner" and `/revise` to "Reviser" makes the "Invoking each agent" section use a different naming convention than the rest of the file.

**Impact:** Low-medium. The LLM orchestrator needs to translate "Planner" back to the actual skill name (`/plan-fast` or `/plan`). Since the body text does contain the skill names, this is unlikely to cause a failure, but it introduces an unnecessary inconsistency.

**Fix:** Keep the subsection headers using skill name format but indicate the variant. For example:
- `**\`/plan\` or \`/plan-fast\` (Round 1 only)**` instead of `**Planner (Round 1 only)**`
- `**\`/revise\` or \`/revise-fast\` (rounds 2+)**` instead of `**Reviser (rounds 2+)**`

Or simply keep `**\`/plan\` (Round 1 only)**` and add the variant selection info in the bullet points (which the plan already does).

### MAJ-3: `max_rounds: N` stripping instruction still says "before passing it to `/plan`" -- should reference `/plan-fast`

In Task 3's new text for the override parsing section, the `max_rounds: N` bullet says:

> "Strip the `max_rounds: N` token from the description before passing it to `/plan`."

After Stage 3, in normal mode, round 1 passes the description to `/plan-fast`, not `/plan`. This reference should say "before passing it to the planner" or "before passing it to `/plan` or `/plan-fast`" to be accurate.

**Impact:** Minor-to-medium. The LLM will likely do the right thing regardless since stripping happens before skill selection, but this is another internal contradiction that could cause confusion.

**Fix:** Change "before passing it to `/plan`" to "before passing it to the planner skill" or "before passing it to `/plan` (or `/plan-fast` in normal mode)."

## MINOR issues (nice to have, won't block)

### MIN-1: Section numbering gap -- "### 3. Parse runtime overrides" followed by "### 4. Model selection per round" but the next section is "## The loop"

After Task 4 inserts "### 4. Model selection per round" between "### 3. Parse runtime overrides" and "## The loop", the Setup section will have subsections 1, 2, 3, 4 under it. This is fine structurally but the Setup heading only exists implicitly (as "## Setup"). The growing number of subsections (1-4) under Setup before "The loop" makes the file front-heavy. Not a problem, just worth noting.

### MIN-2: No update to `dev-workflow/CLAUDE.md` skill listing in the header

Line 3 of `dev-workflow/CLAUDE.md` lists all skills: "...`/init_workflow`, `/discover`, `/architect`, `/plan`, `/critic`, `/revise`, `/thorough_plan`...". The plan adds `/plan-fast` and `/revise-fast` to the model assignments table (Tasks 7-8) but does not add them to this header listing. Same applies to `~/.claude/CLAUDE.md`.

**Fix:** Add `/plan-fast` and `/revise-fast` to the skill listing in the header of both CLAUDE.md files. Alternatively, since these are internal skills not intended for direct user invocation, document that they are intentionally omitted from the listing.

### MIN-3: The `plan-fast/SKILL.md` proposed content includes template markdown code blocks

The plan's "Exact file content" for Task 1 includes the full plan output template (with nested markdown code blocks). This is correct -- it's an exact copy of `plan/SKILL.md` -- but worth verifying during implementation that the nested code fences render correctly in the new file.

### MIN-4: Sync warning diff command assumes specific working directory

Task 9's sync warning comments include:
```
diff <(sed -n '/^# Plan/,$p' plan/SKILL.md) <(sed -n '/^# Plan/,$p' plan-fast/SKILL.md)
```

This assumes the working directory is `dev-workflow/skills/`. It would be more robust to use paths relative to the project root:
```
diff <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan/SKILL.md) <(sed -n '/^# Plan/,$p' dev-workflow/skills/plan-fast/SKILL.md)
```

### MIN-5: Architecture says round 4 specifically, but plan generalizes to "final allowed round"

The architecture (line 353) says: "Round 4 (final allowed): `/revise` escalates to Opus." The plan generalizes this to "the final allowed round uses Opus" which is a strictly better design (handles `max_rounds` overrides). This is a positive deviation from the architecture, not a problem -- just noting the difference for the record.

## What the plan gets right

1. **Clean separation of concerns.** New `-fast` skill files are content-identical copies with only model frontmatter changed, not behavioral forks. This minimizes the risk of drift.

2. **Correct handling of `strict:` + `max_rounds: N` interaction.** The parsing order (strict first, max_rounds second) and the default adjustment (strict defaults to 5, overridable) are well thought out and match the architecture specification.

3. **Critic stays on Opus unconditionally.** This correctly implements the architecture's strongest constraint -- no critic tiering. The plan is unambiguous about this.

4. **Final-round Opus escalation is generalized correctly.** Rather than hardcoding "round 4 = Opus", the plan says "final allowed round = Opus", which correctly handles custom `max_rounds` values.

5. **Rollback strategy is granular.** Three levels of rollback (full, orchestrator-only, strict-only) give good surgical options if different parts fail independently.

6. **Task 9 (sync warnings) proactively addresses the drift risk** that is the biggest long-term maintenance concern with the two-file approach.

7. **All old_string matches verified.** The plan's quoted old text for Tasks 3, 5, 6, 7, and 8 matches the actual file contents verbatim. Line number references are accurate for the current state of the file (post-Stage 2).

8. **Integration analysis is thorough.** The plan correctly identifies all four integration points and analyzes Stage 2 interaction. The backward compatibility analysis is correct.
