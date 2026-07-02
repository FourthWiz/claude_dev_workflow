---
name: end_of_task
description: "Finalizes a completed task: ensures all changes are committed, pushes branch to remote, prompts for lessons learned, aggregates task cost across all sessions, and marks the task as complete. Requires /review to have been run first. Does NOT create a PR — that's a separate explicit action. Use this skill for: /end_of_task, 'finalize this', 'we're done', 'ship it', 'task complete', 'wrap up this task'. This is the explicit user acceptance of completed, reviewed work — the last step before moving on."
model: sonnet
---

# End of Task

*Portable intent doc: `quoin/core/skills/end_of_task.md`*

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
<!-- §0-1m-decide-begin -->
Pre-dispatch 1M check (IVG-90 Layer 1+2):
  - Run: python3 __QUOIN_HOME__/scripts/dispatch_config.py --decide --tier <declared_tier> --verbose
    where <declared_tier> is the tier declared for this skill (e.g. "sonnet" or "haiku",
    as shown in the dispatched-tier line immediately above).
  - If the command returns "safe-path" on line 1:
      Read the reason token from line 2 (config|cache|probe).
      Emit the one-line advisory (verbatim, substituting <reason> with the line-2 token):
        `[quoin: 1M-unsafe declared-tier per <reason>; running SAFE PATH without dispatch]`
      Then proceed to §1/§0c at the current tier (treat as if [no-redispatch] were present).
      Do NOT call the Agent dispatch. Do NOT call AskUserQuestion.
  - If the command returns "dispatch" on line 1, OR if the script is missing / errors:
      Continue to the Agent dispatch call below (today's path — fail-OPEN).
<!-- §0-1m-decide-end -->
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "end_of_task dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent.
<!-- §0-1m-cachewrite-begin -->
      Cache the safe result (best-effort):
        python3 __QUOIN_HOME__/scripts/dispatch_config.py --write-cache --tier <declared_tier> --result safe
      (Fail-OPEN: if the script errors or is missing, silently skip and continue.)
<!-- §0-1m-cachewrite-end -->
      Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in end_of_task. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /end_of_task`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

<!-- §0-worktree-fallback-begin -->
Fail-graceful path with error-class triage (per architecture I-01):
  - If the Agent tool returns an error during dispatch, classify the error
    message text BEFORE proceeding:

  - Error classification:
      * Worktree-class: the error text contains the substring
        `Cannot create agent worktree`, OR (the substring `worktree` AND
        the substring `not in a git repository`). This is recoverable —
        the harness tried to create a git worktree for isolation and the
        project root is not a git repo. Continue to Worktree-class branch.
      * Other-class: any other tool error, exception, or harness rejection
        — skip to Other-class path below (existing fail-OPEN behavior).

  - 1M-credit-class: if the error text contains the substring
      `Usage credits required for 1M context`:
      This is the 1M-context credit mismatch (IVG-89). The parent session carries
      the `context-1m-2025-08-07` beta header which propagates to all subagent calls;
      the declared-tier model lacks 1M credits. Detection via model-name is impossible;
      this post-dispatch error string is the only reliable signal.
      Emit (verbatim):
        `[quoin: 1M-context credit mismatch on <tier> subagent dispatch; proceeding in-session at parent tier — run /model to switch this session to standard context for a permanent fix]`
<!-- §0-1m-cachewrite-begin -->
      Cache the unsafe result (best-effort):
        python3 __QUOIN_HOME__/scripts/dispatch_config.py --write-cache --tier <declared_tier> --result unsafe
      (Fail-OPEN: if the script errors or is missing, silently skip and continue.)
<!-- §0-1m-cachewrite-end -->
      Then proceed to §1 at the current tier (treat as if `[no-redispatch]` were present).
      Do NOT retry the Agent dispatch. Do NOT call AskUserQuestion.


<!-- §0-sidecar-begin -->
  Source-mutating dispatch — two-phase worktree isolation (D-08):

  STEP A — Write the dispatch sidecar BEFORE calling the Agent tool:
     Run via Bash:
       PROJECT_ROOT="$(python3 __QUOIN_HOME__/scripts/path_resolve.py --project-root)"
       python3 __QUOIN_HOME__/scripts/dispatch_sidecar.py \
           --skill <skill-name> \
           --project-root "$PROJECT_ROOT" \
           --plan "<resolved-plan-path-or-empty>"
     (The WorktreeCreate hook reads this sidecar to resolve the nested git root.)

  STEP B — Phase 1: Agent dispatch WITH isolation: "worktree" (normal path):
     Call the Agent tool with isolation: "worktree" at the declared cheap-tier
     model (sonnet for this skill). The deployed WorktreeCreate hook at
     __QUOIN_HOME__/hooks/worktreecreate.sh reads the sidecar, runs
     git_root_for_dispatch.py, and (when a single nested repo resolves)
     creates a worktree IN the nested git root and returns its path.

  STEP C — Phase 2 retry WITHOUT isolation (on Worktree-class error):
     If Phase 1 fails with a Worktree-class error (regex above), the hook
     either returned skip (no stdout → harness fails) or encountered an error.
     Re-dispatch the Agent call WITHOUT isolation: "worktree", at the SAME
     declared cheap-tier model (sonnet). Do NOT escalate to parent tier.
     Emit one-line audit:
       [quoin-stage-1: worktree dispatch skipped; proceeding at sonnet without isolation]

  STEP D — Done:
     No child-side coordination required. The harness handles cwd correctly:
     on Phase 1 success, child sees the worktree as cwd; on Phase 2, child
     inherits the parent's session cwd (today's behavior, unchanged).
<!-- §0-sidecar-end -->

  - Worktree-class branch: handled by Phase 2 (§0-sidecar block above).
    Phase 2 retries at the declared cheap-tier model without isolation.
    Do NOT use AskUserQuestion or proceed-current-tier for source-mutating skills.

  - Other-class path (non-worktree Agent errors):
      Do NOT abort the user's invocation.
      Emit the bare warning (verbatim):
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
      If this path was reached via a worktree-class error, ALSO emit the
      classification line (second, separate):
        `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`
      Then proceed to §1 at the current tier (fail-OPEN per I-01).
<!-- §0-worktree-fallback-end -->
Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## §0b Session-age guard (FIRST STEP after §0 dispatch)

This skill has 8 sequential steps; running it in a heavy / long-lived
session is a known cause of stream-idle timeouts (Apr 28 18:13 incident).
Before doing any work, check session activity age:

```
python3 __QUOIN_HOME__/scripts/session_age_guard.py --threshold-hours 6.0 --project-root "$(pwd)"
```

If exit 1 (`OVER|...`): STOP. Tell the user verbatim:
  "Current session has been active for Xh — over the 6h soft cap.
   /end_of_task is failure-prone in long sessions. Please:
     1. Run /end_of_day to save state
     2. Open a fresh chat and re-run /end_of_task
   Override at your own risk by re-invoking with prefix
   [no-session-age-guard] /end_of_task"

If exit 0 (`OK|...`): continue to ## When to use.

If the helper is missing OR exits with a non-0/1 code: emit the warning
`[session-age-guard: helper unavailable; proceeding]` and continue
(fail-OPEN, mirrors §0 dispatch fail-OPEN per architecture I-01).

Manual override: prefix the user invocation with `[no-session-age-guard]`
to skip the check entirely. Strip the sentinel before processing.

## When to use

Only after:
1. `/review` has given an APPROVED verdict
2. The final `/gate` has passed
3. The user explicitly says to finalize (e.g., `/end_of_task`, "ship it", "we're done")

This skill is never auto-invoked. The user must consciously accept the work.

**Exception: `/run` orchestrator.** When this skill is spawned by `/run` as a subagent, the user has already confirmed the finalization checkpoint ("yes, finalize and push"). This constitutes explicit user acceptance — the user consciously chose to run the full pipeline and confirmed at Checkpoint D. All preconditions (APPROVED review, passed gate) are still enforced. If you see evidence that you were spawned by `/run`, proceed normally through all 8 steps.

## Process

This skill uses a 3-sub-phase Agent dispatch architecture to limit blast radius per
call. Interactive prompts are handled inline (parent session) BEFORE any sub-phase
is dispatched. Sub-phases receive deterministic file-based inputs only.

### Orchestrator pre-flight (inline — parent session handles all interactive prompts)

Execute these steps inline (never dispatch for interactive steps):

**Step 1: Pre-flight checks**

Before touching git, verify everything is clean:

1. **Review status** — resolve the artifact path via `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` (or stage=None for legacy tasks), then look for `<task_dir>/review-*.md`. If exit code 2: display stderr verbatim, fall back to task root, ask user to disambiguate. If no review file exists at the resolved path, STOP and tell the user: "No review found — please run `/review` first." If a review exists, read the latest one and confirm verdict is APPROVED. If not approved, stop and tell the user. (architecture.md and cost-ledger.md ALWAYS at task root per D-03.)
2. **Tests pass** — run the test suite one final time. If anything fails, stop.
3. **Branch state** — check if the branch is up to date with the base branch. If behind, rebase/merge and re-run tests. If push is blocked because task commits are on a protected branch (main/master), do NOT force-push; instead follow the safe reset-to-origin recipe at `__QUOIN_HOME__/memory/branch-recovery.md` — move the mis-placed commits onto a feature branch first, then run the recipe to restore the protected branch to origin.
4. **No secrets** — quick scan of the diff for passwords, API keys, tokens.

Present a pre-flight summary:

```
Pre-flight: end_of_task
✅ Review: APPROVED (review-2.md)
✅ Tests: 47 passed, 0 failed
✅ Branch: feat/refund-flow, up to date with main
✅ No secrets detected
Ready to finalize.
```

**Step 1b: Working-tree cleanup scan**

Before committing, scan the main repo working tree for files that should not
be shipped. Run these checks from the repo root (the nested git root, not the
project root):

1. **Untracked files that match garbage patterns** — run `git ls-files --others --exclude-standard`
   and flag any file matching these patterns:
   - `*.tmp`, `*.bak`, `*.orig`, `*.swp`, `*.swo`
   - `* 2.*`, `* 3.*` (macOS/iCloud duplicates, e.g., "README 2.md")
   - `.planner-trace.md` (Tier-3 ephemeral — CLAUDE.md says "deleted by /end_of_task before archive"; run `rm -f .planner-trace.md` to clean up)
   - `.expanded-*.md` (expand --save scratch output)
   - `.DS_Store` (if not gitignored)
   - `__pycache__/` directories or `*.pyc` files (if not gitignored)
   - `*.log` files at the repo root
   - Any file or directory whose name starts with `.workflow_artifacts` inside the repo tree
     (these should never leak into the repo — they belong at the project root)

2. **Tracked files that look like debug leftovers** — run `git diff --name-only` (unstaged)
   and `git diff --cached --name-only` (staged) and flag:
   - Files containing `console.log`, `debugger`, `breakpoint()`, `import pdb`, or
     `print("DEBUG` in their diff hunks (use `git diff -G` or read the diff output)
   - This is advisory only — some repos legitimately use these. Flag, don't block.

3. **Present findings** — if anything was found, show a categorized summary:

   ```
   Working-tree cleanup scan:
   ⚠️  Garbage files found (recommend deleting before commit):
      - README 2.md (macOS duplicate)
      - .planner-trace.md (workflow ephemeral)

   ⚠️  Debug leftovers in diff (review before commit):
      - quoin/scripts/foo.py: contains `breakpoint()` (line 42)

   ✅ No .workflow_artifacts/ leak detected.

   ```

   Use AskUserQuestion before continuing to Step 2:
   ```
   AskUserQuestion(
     question="Garbage files or debug leftovers found. How would you like to proceed?",
     options=[
       {label: "Delete garbage files", description: "Remove the flagged files before committing."},
       {label: "Proceed as-is", description: "Keep all files; commit everything shown."}
     ]
   )
   ```

4. **If nothing found** — print one line and continue:
   ```
   Working-tree cleanup scan: ✅ clean
   ```

**Step 2: Commit decision (interactive — must resolve before dispatching sub-phases)**

Run `git status`. If there are uncommitted changes:
- Show them to the user
- Use AskUserQuestion to get the commit decision (no stash option — stash manually then re-invoke if needed):
  ```
  AskUserQuestion(
    question="There are uncommitted changes. Commit them now or abort?",
    options=[
      {label: "Commit", description: "Commit all uncommitted changes with a conventional message."},
      {label: "Abort", description: "Stop here. Stash manually then re-invoke /end_of_task."}
    ]
  )
  ```
- If **Commit**: collect a conventional commit message inline.
- If **Abort**: STOP. Tell the user: "Stash manually then re-invoke /end_of_task."
Capture the answer as `commit_or_abort` (`"commit"` or `"abort"`).
If no uncommitted changes: set `commit_or_abort = "commit"` (nothing to do) and skip.

**Step 3: Lessons learned (interactive — capture inline)**

Use AskUserQuestion to check for lessons:
```
AskUserQuestion(
  question="Task complete. Anything that surprised you, or that the workflow should handle differently next time?",
  options=[
    {label: "Nothing to add", description: "No lessons to record for this task."},
    {label: "Yes, let me share", description: "I have something to add to lessons-learned."}
  ]
)
```

If the user selects "Nothing to add": set `lessons_text = ""`.
If the user selects "Yes, let me share" or uses the "Other" free-text option: capture their input as `lessons_text`.
Capture the response as `lessons_text` (may be empty string if nothing to share).

Auto-capture lessons if:
- The critic-revise loop ran more than 3 rounds (what made convergence hard?)
- The review requested changes (what did /implement miss?)
- A rollback happened during this task (what went wrong?)

**Step 4: Archive type (interactive — capture inline)**

If the task folder lives directly under `.workflow_artifacts/` (not inside a parent feature folder), use AskUserQuestion:
```
AskUserQuestion(
  question="Is the feature '<task-name>' fully complete, or is there more work planned under this folder?",
  options=[
    {label: "Fully complete", description: "Archive the task folder to finalized/."},
    {label: "More work planned", description: "Keep the task folder active; do not archive."}
  ]
)
```

Capture as `archive_type`: `"feature"` (fully complete) or `"none"` (more work planned — do not archive).

If the task folder is inside a parent feature folder (detected by presence of planning artifacts or stage-* sibling folders in the parent), set `archive_type = "subtask"` without asking.

**Step 5: Write `eot-preflights.json` — MUST happen BEFORE dispatching any sub-phase**

Write `.workflow_artifacts/<task-name>/eot-preflights.json` (fixed name — no date stamp):

```json
{
  "task_name": "<task-name>",
  "task_dir": "<absolute-path-to-task-dir>",
  "commit_list": ["<file1>", "<file2>"],
  "commit_message": "<conventional commit message or empty string>",
  "commit_or_abort": "commit",
  "lessons_text": "<what the user said, or empty string>",
  "archive_type": "feature"
}
```

The orchestrator OVERWRITES any stale file from a prior run. Each `/end_of_task`
invocation produces exactly one `eot-preflights.json`. Sub-phases MUST NOT
re-derive or re-timestamp the filename — they read the path given inline.

If `commit_or_abort` is `"abort"`: STOP here. Do not dispatch any sub-phase.

**Step 6: Dispatch Sub-phase A (commit + push)**

Spawn an Agent subagent:
- model: `"sonnet"`
- description: `"end_of_task Sub-phase A: commit and push"`
- prompt: |
    You are Sub-phase A of /end_of_task. Your job: commit remaining changes (if any)
    and push the branch to remote. Read the hand-off file, execute, report results.

    Hand-off file: `<absolute-path-to-task-dir>/eot-preflights.json`

    Steps:
    1. Read `eot-preflights.json`. Defensive check: if `commit_or_abort` is `"abort"`,
       exit immediately with "Orchestrator sent abort — Sub-phase A exiting."
    2. If `commit_list` is non-empty and `commit_message` is non-empty:
       - Stage the listed files (`git add <file>` for each, not `git add .`)
       - Commit with the provided `commit_message`
    3. Push: `git push -u origin <current-branch-name>`
       If push fails: report the error clearly; do NOT retry. The user will resolve.
    4. Run `git rev-parse HEAD` and append `"commit_hash": "<sha>"` to `eot-preflights.json`.
    5. Report: branch pushed, commit hash, any errors.

    Scope cap: at most ~15 tool uses. If blocked, write what you have to disk and return.

Wait for Sub-phase A result. If it reports a fatal error (push failed, etc.): report to
the user and stop. Do NOT proceed to Sub-phase B if the push failed.

**Step 7: Dispatch Sub-phase B (lessons + session state + cost aggregation)**

Spawn an Agent subagent:
- model: `"sonnet"`
- description: `"end_of_task Sub-phase B: lessons, session state, cost"`
- prompt: |
    You are Sub-phase B of /end_of_task. Your jobs: append lessons to lessons-learned.md,
    update session state to completed, and aggregate task cost. Write cost summary to disk.

    Hand-off file: `<absolute-path-to-task-dir>/eot-preflights.json`
    Cost ledger: `<absolute-path-to-task-dir>/cost-ledger.md`
    Lessons-learned: `.workflow_artifacts/memory/lessons-learned.md`
    Session state dir: `.workflow_artifacts/memory/sessions/`

    Steps:
    1. Read `eot-preflights.json` for `lessons_text` and `task_name`.
    2. If `lessons_text` is non-empty: append to lessons-learned.md:
       ```
       ## <date> — <task_name>
       **What happened:** <lessons_text>
       **Lesson:** <reusable takeaway>
       **Applies to:** <relevant skills>
       ```
    3. Update `.workflow_artifacts/memory/sessions/<date>-<task_name>.md`:
       set status to `completed`, record branch name and commit hash from eot-preflights.json.
    4. Cost aggregation — read cost-ledger.md and compute:
       a. Binary check: `command -v npx` — if unavailable, skip ccusage and use
          cost_from_jsonl.py fallback for ALL UUIDs (see below).
       b. For each UUID in ledger (<5 sessions): `timeout 15 npx ccusage session -i <UUID> --json`
          For ≥5 sessions (bulk): `npx ccusage session --json --since <earliest-date-from-ledger>`
          then filter returned sessions against the UUIDs in the ledger.
          Parsing bulk responses: ccusage v20+ wraps results as
          `{"session": [{"period": "UUID", "totalCost": ..., ...}, ...], "totals": {...}}`.
          The UUID is in `period`; the array is under top-level key `session`.
          If the response instead has a `sessionId` field (v18 shape) or is a bare array, use `sessionId`.
          Version-detection: presence of top-level `session` key (array) → v20; else v18 fallback.
          Extract `totalCost` per UUID. Filter to ledger UUIDs only.
          Path-agnostic all-failed gate: whichever of the per-UUID loop or bulk call was taken,
          if NO ledger UUID was successfully resolved, fall back to cost_from_jsonl.py for all UUIDs.
       c. Fallback (from binary-check branch OR all-failed gate):
          Per-UUID mode: `python3 __QUOIN_HOME__/scripts/cost_from_jsonl.py session -i UUID --json`
          Bulk mode: `python3 __QUOIN_HOME__/scripts/cost_from_jsonl.py session --json --since <date>`
          Filter results to only UUIDs in the ledger. Parse output identically to ccusage.
          Prepend: `[fallback: cost_from_jsonl.py — prices as of <LAST_UPDATED>]`
          Read LAST_UPDATED via: `python3 -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path.home() / '.claude' / 'scripts')); import cost_from_jsonl; print(cost_from_jsonl.LAST_UPDATED)"`
       d. Aggregate: per-phase totals, per-model totals, grand total.
    5. Write `.workflow_artifacts/<task_name>/cost-summary.json` (fixed name, overwritten):
       ```json
       {
         "per_phase": {"plan": 1.23, "implement": 0.45, ...},
         "per_model": {"opus": 1.23, "sonnet": 0.45, "haiku": 0.00},
         "task_total": 1.68,
         "off_topic_total": 0.00,
         "grand_total": 1.68,
         "fallback_used": false,
         "fallback_note": ""
       }
       ```
       NOTE: `fallback_used=true` means "partial estimate — some ledger UUIDs did not
       resolve to JSONL sessions". It does NOT mean the cost is unavailable. A present
       `grand_total` with `fallback_used=true` should be rendered as `~$X (partial)`.
       Only a null or absent total key means unavailable. Consumer map: this file is
       consumed only by `costService.ts` (extension). `/cost_snapshot` and
       `dashboard_model.py` consume `cost-ledger.md` instead — do NOT wire them to
       this file.
    6. Report: lessons appended (yes/no), session state updated, cost summary written.

    Scope cap: at most ~15 tool uses. If blocked on cost aggregation, write partial
    data to cost-summary.json and return — partial cost data is better than none.

**Step 8: Dispatch Sub-phase C (archive + final report)**

Spawn an Agent subagent:
- model: `"sonnet"`
- description: `"end_of_task Sub-phase C: archive and report"`
- prompt: |
    You are Sub-phase C of /end_of_task. Your jobs: archive the task folder and
    print the final completion report.

    Hand-off files:
    - `<absolute-path-to-task-dir>/eot-preflights.json` (for archive_type, task_name)
    - `<absolute-path-to-task-dir>/cost-summary.json` (read BEFORE the mv — it lives
      inside the task folder which you are about to move)
    Task dir: `<absolute-path-to-task-dir>`

    Steps:
    1. Read `cost-summary.json` from the task dir (BEFORE any mv).
    2. Read `eot-preflights.json` for `archive_type` and `task_name`.
    3. Delete planner trace breadcrumb (if present):
       Run: rm -f "<task_dir>/.planner-trace.md" 2>/dev/null || true
       Tier-3 ephemeral — must not persist in the finalized archive; runs BEFORE the archive mv.
    4. Archive based on `archive_type`:
       - `"subtask"`: mv task folder into `.workflow_artifacts/<parent>/finalized/<subtask>/`
       - `"feature"`: mv task folder into `.workflow_artifacts/finalized/<task_name>/`
       - `"none"`: skip the mv entirely.
       Create target dir with `mkdir -p` before the mv.
    4. Print the final report:
       ```
       Task finalized: <task_name>

       Branch: <branch> → pushed to origin
       Review: APPROVED
       Archived: <task-folder> → <finalized-path>   (or "not archived — more work planned")

       Cost breakdown:
         Phase          | Cost
         ---------------|--------
         plan           | $X.XX
         implement      | $X.XX
         ...
         ---------------|--------
         Task total     | $X.XX
         Grand total    | $X.XX

       Model breakdown: opus: $X.XX | sonnet: $X.XX | haiku: $X.XX
       <fallback note if applicable>

       Lessons captured: <yes/no>
       Session marked as completed.

       Next: when you're ready, create a PR from the branch.
       ```

    Scope cap: at most ~15 tool uses. If blocked, write what you have to disk and return.

## Important behaviors

- **Run tests one last time.** Even if they passed 5 minutes ago. Code might have changed.
- **Never force-push.** Use regular `git push`. If the branch has diverged, tell the user and let them decide how to resolve.
- **No PR creation.** This skill pushes the branch only. The user creates the PR separately when they're ready. Remind them at the end.
- **Cost aggregation runs before archive.** The ledger file is inside the task folder — it must be read before the folder is moved.
- **This is a celebration, not a chore.** The task is done. Keep the output clean and satisfying.
