# Verify-Fix Loop (Two-Task Seeded Failure)

## Purpose

Evaluate whether the automated post-task verify-fix loop (IVG-126) correctly
detects and repairs both defect classes it was hardened against during
planning: touched-files scoping anchored to the wrong root, and
untracked-new-file omission from the touched-files computation.

## Starting State

Fixture repository nested one level under a non-git project root (a
`.workflow_artifacts/`-holding directory whose child directory is the actual
git repository), matching the layout the verify loop's REPO_ROOT resolution
targets. Two sequential implementation tasks are staged:

- Task 1: a small, well-scoped change with its own passing test. This task
  is implemented, its verify step passes, and it is committed cleanly before
  task 2 begins.
- Task 2: introduces a seeded failing test as a NEW, UNTRACKED file (not a
  modification of an existing tracked file), alongside the corresponding new,
  untracked source change the failing test targets.

## Prompt

Implement task 1 first; verify it passes and commit it. Then implement task
2, which is expected to fail its own tests initially. Run the automated
verify-fix loop after task 2's code and tests are written, before marking it
complete, and fix the seeded failure using the loop's retry mechanism.

## Mode Notes

- Simple Claude: no verify-fix loop; report whatever ad hoc verification is
  performed manually.
- Quoin + Claude: `/implement` runs the automated verify-fix loop described
  under `### Automated verify-fix loop (post-task)` in the adapter SKILL.md.
- Simple Codex: use native Codex implementation workflow; no bounded
  verify-fix loop.
- Quoin + Codex: Codex procedure verify-fix loop extension, per the portable
  contract in `quoin/core/skills/implement.md` (`## Automated verify-fix
  loop`).

## Expected Evidence

- Per-retry cost-ledger rows for the task 2 verify attempt(s), in the
  7-column ledger shape (`implement | sonnet | task | ...`).
- A green affected-area test suite for task 2 once the fix is applied.
- The fix applied without user intervention beyond the loop's own retry (no
  user-supplied diagnostic needed).
- Evidence the loop scoped its touched-files set to task 2's own edits —
  not the already-committed task 1 diff, and not silently missing the
  untracked new file task 2 adds.

## Evaluation Notes

This scenario exercises two regression classes in one seeded run. Seeding
the failure only in task 2, after task 1 is already committed, targets a
touched-files-scoping regression where the loop's diff basis falls back to a
whole-repo or committed-only diff instead of task 2's own uncommitted edits.
Seeding the failure in a brand-new, untracked file — rather than a
modification of an existing tracked file — targets a regression where the
loop's touched-files computation omits untracked files entirely. A loop
implementation that regresses on either point would silently report a clean
result for task 2 despite the seeded failure being present. Score for
whether the collected evidence demonstrates detection and repair of the
seeded failure, not merely completion of task 2. This is a forward-looking
evaluation procedure; no run of this scenario has been conducted as part of
authoring it.
