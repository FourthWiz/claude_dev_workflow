# Plan: workflow-fixes

## Convergence Summary
- **Rounds:** 3
- **Final verdict:** PASS
- **Key revisions:** Round 1 identified `claude init` doesn't exist as a CLI subcommand → redesigned to use `/init` slash command. Round 2 identified skills can't invoke slash commands → changed to a gatekeeper pattern (check for CLAUDE.md, stop and instruct user if missing). Round 2 also tightened the sibling-pattern heuristic in Task 1 to require both conditions.
- **Remaining concerns:** None

## Summary

Two targeted improvements to dev-workflow skill instructions:

1. **`/end_of_task` subtask detection** -- Replace the "ask the user if ambiguous" logic with concrete heuristics that automatically detect parent-child folder relationships, so subtasks get archived into `<parent>/finalized/` without prompting.

2. **`/init_workflow` `/init` prerequisite** — Add a new Step 1 that checks for `CLAUDE.md` and tells the user to run `/init` first if missing, ensuring the standard Claude Code foundation exists before workflow setup.

Both changes are edits to markdown instruction files (SKILL.md), not code. Low risk, no tests to run.

---

## Task 1: Improve subtask detection in `/end_of_task`

**File:** `dev-workflow/skills/end_of_task/SKILL.md` (repo source of truth)
**Section:** Step 6: Archive the task folder (lines 100-130)

**What to change:**

Replace the current "How to decide" paragraph (lines 116-119) with explicit detection heuristics. The new instructions should tell Claude to:

1. Resolve the task folder's absolute path.
2. Check if the task folder's **parent directory** is itself a task folder (contains planning artifacts like `current-plan.md`, `architecture.md`, or other task subfolders). If yes, that parent is the feature folder — this is a subtask.
3. Also check if the task folder name matches a stage/phase pattern (e.g., `stage-1a-*`, `phase-2-*`, `part-1-*`) AND the parent contains at least one other sibling matching a similar pattern — strong signal of a subtask. Both conditions (pattern match + sibling) are required to avoid false positives.
4. If a parent-child relationship is detected, automatically archive to `<parent>/finalized/<subtask>/` without asking.
5. Only ask the user when the folder is at the project root level and it's genuinely ambiguous whether the entire feature is done.

**Specific edit:**

Replace lines 116-119 (the "How to decide" block):

```markdown
**How to decide:** Ask the user if it's not obvious:
> "Is the parent feature `<feature-name>` fully done, or just this sub-task?"

If just a sub-task, archive into the parent's `finalized/`. If the whole feature is done, archive the entire feature folder to the project root `finalized/`.
```

With:

```markdown
**How to detect automatically:**

1. **Resolve the task folder path** relative to the project root. For example, if the task folder is `cost-reduction/stage-1a-caching/`, the parent is `cost-reduction/`.
2. **Check if the parent directory is a task folder** — look for planning artifacts (`current-plan.md`, `architecture.md`, `review-*.md`, `critic-response-*.md`) or other task subfolders in the parent. If the parent contains these, this is a sub-task within that parent feature.
3. **Check for stage/phase naming patterns** — if the task folder name matches patterns like `stage-*`, `phase-*`, `part-*`, `step-*`, or `sprint-*`, AND the parent contains at least one other sibling matching a similar pattern, it is a sub-task. Both conditions are required to avoid false positives on unrelated folders.
4. **If either check (2) or (3) matches**, archive as a sub-task: move to `<parent>/finalized/<subtask>/`. Do not ask.
5. **If the task folder is directly under the project root** (no parent task folder), ask the user:
   > "Is the feature `<task-name>` fully complete, or is there more work planned under this folder?"

   If fully complete, move to `finalized/<task-name>/`. If more work remains, do not archive yet.
```

**Why:** The current instructions rely on Claude's judgment with a fallback to asking the user. But Claude frequently fails to notice the nesting. Explicit path-based heuristics make detection reliable and deterministic.

---

## Task 2: Add `/init` prerequisite check to `/init_workflow`

**File:** `dev-workflow/skills/init_workflow/SKILL.md` (repo source of truth)
**Section:** Between the Prerequisites section and Step 1

**What to change:**

Insert a new step before the current Step 1. Renumber all subsequent steps (Step 1 becomes Step 2, etc.).

**New step to insert (before current Step 1):**

```markdown
### Step 1: Ensure project is initialized with `/init`

Check if the project has a `CLAUDE.md` file at its root. If it does NOT exist:

1. **STOP** and tell the user:
   > "This project hasn't been initialized with Claude Code yet. Please run `/init` first to create a `CLAUDE.md`, then re-run `/init_workflow`."
2. Do not proceed with subsequent steps. The `/init` command sets up the project-level `CLAUDE.md` and `.claude/` directory that the workflow depends on.

If `CLAUDE.md` already exists, skip this step — the project is already initialized. Proceed to Step 2.

This ensures the standard Claude Code foundation is in place before layering on the dev-workflow setup.
```

**Renumbering:** Current Steps 1-7 become Steps 2-8. Update all `### Step N:` headers accordingly.

**Why:** Users expect `/init_workflow` to be a complete bootstrap. Having to remember to run `/init` separately is friction that leads to incomplete setups. Checking for `CLAUDE.md` as the gate condition is a reliable, concrete check.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Subtask heuristics misfire on unusual folder structures | Low | Low | Fallback to asking the user is preserved for root-level folders |
| `/init` slash command unavailable or changed | Low | Low | Falls back to checking for CLAUDE.md; workflow setup proceeds regardless |
| Renumbering errors in init_workflow | Low | Low | Mechanical change, easy to verify |

**Overall risk: Low.** These are documentation/instruction edits with no code impact. If the instructions are wrong, the worst case is Claude asks the user (current behavior) rather than auto-detecting.

---

## Implementation checklist

- [x] Task 1: Edit `dev-workflow/skills/end_of_task/SKILL.md` Step 6 — replace "How to decide" block with automatic detection heuristics ✅
- [x] Task 2: Edit `dev-workflow/skills/init_workflow/SKILL.md` — insert new Step 1 for `/init` check, renumber Steps 1-7 to 2-8 ✅
- [x] Task 3: Re-run `install.sh` to propagate changes to `~/.claude/skills/` — 16 skills installed ✅
- [ ] Verify: Read both files after editing to confirm formatting is correct
