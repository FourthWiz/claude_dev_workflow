---
name: end_of_task
description: "Finalizes a completed task: ensures all changes are committed, pushes branch to remote, prompts for lessons learned, aggregates task cost across all sessions, and marks the task as complete. Requires /review to have been run first. Does NOT create a PR — that's a separate explicit action. Use this skill for: /end_of_task, 'finalize this', 'we're done', 'ship it', 'task complete', 'wrap up this task'. This is the explicit user acceptance of completed, reviewed work — the last step before moving on."
model: sonnet
---

# End of Task

You finalize a completed task. This is the user's explicit acceptance that the work is done — reviewed, approved, and ready to ship. You handle the git ceremony (commit, push to branch), capture lessons, aggregate task cost, and close out the task cleanly. **You do NOT create a PR** — that's a separate, explicit action the user takes when they're ready.

**CRITICAL: You must verify that `/review` was run before proceeding.** If no `review-*.md` file exists in the task folder, STOP and tell the user to run `/review` first.

**IMPORTANT: Fresh session recommended.** This skill has 8 sequential steps that must all complete (pre-flight, commit, push, lessons, session state, cost aggregation, archive, report). If the current session has been through heavy work (`/thorough_plan`, `/implement`, `/review`), start a fresh session for `/end_of_task` — context compaction mid-skill can silently skip steps like archiving.

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: sonnet`. If the executing agent is running on a model
strictly more expensive than the declared tier, you MUST self-dispatch before doing the
skill's actual work.

Detection:
  - Read your current model from the system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus.
  - Sentinel parsing: the user's prompt is checked for the `[no-redispatch]` family.
      * Bare `[no-redispatch]` (parent-emit form AND user manual override): skip dispatch, proceed to §1 at the current tier.
      * Counter form `[no-redispatch:N]` where N is a positive integer ≥ 2: ABORT (see "Abort rule" below).
      * Counter form `[no-redispatch:1]` is reserved and treated as bare `[no-redispatch]` for forward-compatibility; do not emit it.
  - If current_tier > declared_tier AND prompt does NOT start with any `[no-redispatch]` form:
      Dispatch reason: cost-guardrail handoff. dispatched-tier: sonnet.
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "end_of_task dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in end_of_task. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /end_of_task`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## When to use

Only after:
1. `/review` has given an APPROVED verdict
2. The final `/gate` has passed
3. The user explicitly says to finalize (e.g., `/end_of_task`, "ship it", "we're done")

This skill is never auto-invoked. The user must consciously accept the work.

**Exception: `/run` orchestrator.** When this skill is spawned by `/run` as a subagent, the user has already confirmed the finalization checkpoint ("yes, finalize and push"). This constitutes explicit user acceptance — the user consciously chose to run the full pipeline and confirmed at Checkpoint D. All preconditions (APPROVED review, passed gate) are still enforced. If you see evidence that you were spawned by `/run`, proceed normally through all 8 steps.

## Process

### Step 1: Pre-flight checks

Before touching git, verify everything is clean:

1. **Review status** — resolve the artifact path via `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` (or stage=None for legacy tasks), then look for `<task_dir>/review-*.md`. If exit code 2: display stderr verbatim, fall back to task root, ask user to disambiguate. If no review file exists at the resolved path, STOP and tell the user: "No review found — please run `/review` first." If a review exists, read the latest one and confirm verdict is APPROVED. If not approved, stop and tell the user. (architecture.md and cost-ledger.md ALWAYS at task root per D-03 — see lines below.)
2. **Tests pass** — run the test suite one final time. If anything fails, stop.
3. **No uncommitted changes** — run `git status`. If there are unstaged/uncommitted changes:
   - Show them to the user
   - Ask: commit these too, or stash them?
4. **Branch state** — check if the branch is up to date with the base branch. If behind, rebase/merge and re-run tests.
5. **No secrets** — quick scan of the diff for passwords, API keys, tokens.

Present a pre-flight summary:

```
Pre-flight: end_of_task
✅ Review: APPROVED (review-2.md)
✅ Tests: 47 passed, 0 failed
✅ Working tree: clean
✅ Branch: feat/refund-flow, up to date with main
✅ No secrets detected
Ready to finalize.
```

### Step 2: Commit any remaining changes

If there are uncommitted changes the user wants to include:

- Stage the relevant files (not blanket `git add .`)
- Write a conventional commit message:
  ```
  <type>(<scope>): <description>

  <why this change was made>
  ```
- Commit

If everything is already committed, skip this step.

### Step 3: Push

Push the branch to the remote:

```bash
git push -u origin <branch-name>
```

If the push fails (e.g., remote rejected, auth issue), report the error and let the user resolve it.

### Step 4: Prompt for lessons learned

Ask the user:

> "Task complete. Anything that surprised you, or that the workflow should handle differently next time?"

If they share something, append to `.workflow_artifacts/memory/lessons-learned.md`:

```markdown
## <date> — <task-name>
**What happened:** <what the user described>
**Lesson:** <the reusable takeaway>
**Applies to:** <relevant skills>
```

Also auto-capture lessons if:
- The critic-revise loop ran more than 3 rounds (what made convergence hard?)
- The review requested changes (what did /implement miss?)
- A rollback happened during this task (what went wrong?)

### Step 5: Update session state

Update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md`:
- Set status to `completed`
- Record the final branch name and commit hash
- Note any lessons captured

### Step 6: Cost aggregation

Read `.workflow_artifacts/<task-name>/cost-ledger.md`.

**If the file doesn't exist:** note "no cost ledger found — cost tracking was not active for this task" and proceed to Step 7.

For each data line in the ledger (skip lines starting with `#` and blank lines), parse the pipe-delimited fields: `<uuid> | <date> | <phase> | <model> | <category> | <notes>`

**Binary check:** Before running ccusage, verify `npx` is available. If it is NOT
(`command -v npx` returns non-zero, or `npx --version` fails), skip ccusage entirely
and fall back to cost_from_jsonl.py for ALL ledger UUIDs (see fallback block below).

Run `npx ccusage session -i <UUID> --json` for each UUID, sequentially. Apply a 15-second timeout per call:

```bash
timeout 15 npx ccusage session -i <UUID> --json
```

**For tasks with 5 or more sessions**, prefer a single call to reduce overhead:

```bash
npx ccusage session --json --since <earliest-date-from-ledger>
```

Then filter the returned sessions against the UUIDs in the ledger.

**Parse the JSON output.** The structure is:
```json
{"sessionId": "...", "totalCost": 1.23, "totalTokens": 123456, "entries": [...]}
```

From `entries`, aggregate per-model cost: group entries by the `model` field and sum `costUSD` per model. If all entry-level `costUSD` values are 0 (cached calls), use `totalCost` as the session total and mark model breakdown as "unavailable".

**If a lookup times out or returns an error**, note "cost unknown" for that phase and continue.

**Fallback gate (path-agnostic):** After ccusage execution completes — whichever of the
per-UUID loop or the bulk `--since` call was taken — if NO ledger UUID was successfully
resolved (every per-UUID call returned non-zero, OR the bulk call returned non-zero or an
empty/unmatched result set), fall back to cost_from_jsonl.py for all ledger UUIDs.
This catches the "ccusage binary present but completely broken" case (e.g., npm install failure).
# (Path-agnostic gate: covers per-UUID loop failure AND bulk-call failure — per D-02b rationale.)
# (Binary-check + all-failed-gate are structurally separate per D-02b — same fallback semantics as cost_snapshot Step 2's single conflated branch.)

**Fallback (fires from either the binary-check branch above or the path-agnostic all-failed gate above):**
For per-UUID mode (< 5 sessions in ledger):
  python3 ~/.claude/scripts/cost_from_jsonl.py session -i UUID --json
For bulk mode (≥ 5 sessions in ledger, mirroring ccusage's bulk path):
  python3 ~/.claude/scripts/cost_from_jsonl.py session --json --since <earliest-date-from-ledger>
  Compute earliest-date-from-ledger as the min of column-2 dates across all data lines in
  cost-ledger.md (the same expression Step 6 already uses for the bulk ccusage call —
  preserve the existing SKILL.md derivation). Then filter returned results to only the
  UUIDs present in the ledger.
Parse the JSON output identically to ccusage output — the shape is identical.
Before recording the cost breakdown in Step 8, prepend ONE line:
  [fallback: cost_from_jsonl.py — prices as of <LAST_UPDATED>]
Read LAST_UPDATED via:
  python3 -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path.home() / '.claude' / 'scripts')); import cost_from_jsonl; print(cost_from_jsonl.LAST_UPDATED)"

Exit code 2 from cost_from_jsonl.py ("UUID not found") is a per-UUID recoverable failure.
Treat it the same as ccusage's per-UUID timeout: record cost-unknown for that UUID,
continue with the rest. Do NOT treat exit 2 as a fallback-level failure.

**Aggregate results (hold in memory for Step 8):**
- Per-phase breakdown: sum `totalCost` by phase field from ledger
- Per-model breakdown: sum across all sessions grouped by model
- Task vs off-topic: separate totals for `task` and `off-topic` category entries
- Grand total

### Step 7: Archive the task folder

Move the completed task folder into `.workflow_artifacts/finalized/` to keep the project root clean.

**Determine the scope:**

1. **Sub-task within a global task/feature** — if the task folder lives inside a parent feature folder (e.g., `.workflow_artifacts/payment-v2-migration/auth-retry/`), move it into `.workflow_artifacts/<parent-feature>/finalized/`:
   ```
   .workflow_artifacts/payment-v2-migration/auth-retry/  →  .workflow_artifacts/payment-v2-migration/finalized/auth-retry/
   ```

2. **Global task/feature completed entirely** — if this is the top-level task folder and all work is done, move the entire folder into `.workflow_artifacts/finalized/`:
   ```
   .workflow_artifacts/payment-v2-migration/  →  .workflow_artifacts/finalized/payment-v2-migration/
   ```

**How to detect automatically:**

1. **Resolve the task folder path** relative to `.workflow_artifacts/`. For example, if the task folder is `.workflow_artifacts/cost-reduction/stage-1a-caching/`, the parent is `.workflow_artifacts/cost-reduction/`.
2. **Check if the parent directory is a task folder** — look for planning artifacts (`current-plan.md`, `architecture.md`, `review-*.md`, `critic-response-*.md`) or other task subfolders in the parent. If the parent contains these, this is a sub-task within that parent feature.
3. **Check for stage/phase naming patterns** — if the task folder name matches patterns like `stage-*`, `phase-*`, `part-*`, `step-*`, or `sprint-*`, AND the parent contains at least one other sibling matching a similar pattern, it is a sub-task. Both conditions are required to avoid false positives on unrelated folders.
4. **If either check (2) or (3) matches**, archive as a sub-task: move to `.workflow_artifacts/<parent>/finalized/<subtask>/`. Do not ask.
5. **If the task folder is directly under `.workflow_artifacts/`** (no parent task folder detected), ask the user:
   > "Is the feature `<task-name>` fully complete, or is there more work planned under this folder?"

   If fully complete, move to `.workflow_artifacts/finalized/<task-name>/`. If more work remains, do not archive yet.

**Steps:**
```bash
# Create .workflow_artifacts/finalized/ if it doesn't exist
mkdir -p <target-finalized-dir>

# Move the task folder
mv <task-folder> <target-finalized-dir>/
```

**Note:** Only move planning/review artifacts (the task subfolder with `current-plan.md`, `architecture.md`, `review-*.md`, etc.). Never move source code repos — those stay where they are.

### Step 8: Report

Tell the user:

```
Task finalized: <task-name>

Branch: feat/refund-flow → pushed to origin
Commits: <N> commits
Tests: all passing
Review: APPROVED
Archived: <task-folder> → <finalized-path>

Cost breakdown:
  Phase          | Cost
  ---------------|--------
  plan           | $X.XX
  critic (xN)    | $X.XX
  implement      | $X.XX
  review         | $X.XX
  other          | $X.XX
  ---------------|--------
  Task total     | $X.XX
  Off-topic      | $X.XX
  Grand total    | $X.XX

Model breakdown: opus: $X.XX | sonnet: $X.XX | haiku: $X.XX

Lessons captured: <yes/no>
Session marked as completed.

Next: when you're ready, create a PR from the branch.
```

If no cost ledger was found or all lookups failed, show: `Cost tracking: not available (ledger missing or all lookups failed)`

Clean and done.

## Important behaviors

- **Run tests one last time.** Even if they passed 5 minutes ago. Code might have changed.
- **Never force-push.** Use regular `git push`. If the branch has diverged, tell the user and let them decide how to resolve.
- **No PR creation.** This skill pushes the branch only. The user creates the PR separately when they're ready. Remind them at the end.
- **Cost aggregation runs before archive.** The ledger file is inside the task folder — it must be read before the folder is moved.
- **This is a celebration, not a chore.** The task is done. Keep the output clean and satisfying.
