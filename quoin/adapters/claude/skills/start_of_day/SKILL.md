---
name: start_of_day
description: "Restores context from the daily cache and unfinished sessions so you can resume where you left off. Use this skill for: /start_of_day, 'what was I working on', 'resume', 'pick up where I left off', 'morning standup', 'SOD', 'start of day'. Reads the latest daily cache, checks git state, and presents a clear picture of what to do next."
model: haiku
---

# Start of Day

*Portable intent doc: `quoin/core/skills/start_of_day.md`*

You restore context from the previous session(s) so the user can seamlessly resume work. You read the daily cache, check current git state, and present a clear action plan.

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: haiku`. If the executing agent is running on a model
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
      Dispatch reason: cost-guardrail handoff. dispatched-tier: haiku.
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
        model: "haiku"
        description: "start_of_day dispatched at haiku tier"
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
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in start_of_day. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /start_of_day`).
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


  - Worktree-class branch:
      Worktree creation is hook-driven and cannot be skipped by omitting a
      parameter. Use the AskUserQuestion tool to present the user with one
      option:
        (c) `proceed-current-tier` — Skip dispatch, proceed at the current
            (more expensive) tier. This is the only available recovery path.
      Question header: `Subagent dispatch failed (worktree creation). Proceeding at current tier.`
      Note for the user: "Worktree dispatch failed and no retry mechanism
      is available — worktree creation is unconditional in this harness.
      Proceeding at current tier."

  - Other-class path (also: worktree-class after user acknowledges c):
      Do NOT abort the user's invocation.
      Emit the bare warning (verbatim):
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
      If this path was reached via a worktree-class error, ALSO emit the
      classification line (second, separate):
        `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`
      Then proceed to §1 at the current tier (fail-OPEN per I-01).
<!-- §0-worktree-fallback-end -->
Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

### Step 1a: Resume from cookie

Read `<project-root>/.workflow_artifacts/memory/resume-cookie.md` if present.

- **If absent:** continue to Step 1 (existing behavior — graceful fallback; no error).
- **If present, check `expires` field:** if `expires` < now (ISO comparison), the cookie is stale — ignore it and continue to Step 1.
- **If present and fresh:** use the cookie's `task`, `last_skill`, `branch`, `dirty_count`, and body ("what's next" hint) to seed the Step 5 briefing. Note the task and branch at the start of the briefing so the user knows what was active yesterday.

**Banner check (compose with Step 1 — signal B):** while reading session files for the briefing, also check `.workflow_artifacts/memory/sessions/` for any session-state files written within the last 36 hours that have `end_of_day_due: yes`. Count them as M. If M > 0, signal B is positive. Signal B is combined with signal A (the insights-file check in Step 1) in a unified banner — see Step 1 for the combined rule.

## Session bootstrap

Cost tracking note: `/start_of_day` is a lightweight daily-orientation skill. Append to the cost ledger only if a specific task context is clearly active (the user mentioned a task name or there's a clear active task from session state). If in doubt, skip cost recording — don't guess a task name.

If a task context is active: append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `start-of-day`.

## Process

### Step 1: Check for missing-EOD signals

**Signal A:** look for `.workflow_artifacts/memory/daily/insights-<yesterday>.md` (yesterday's date). If it exists, count entries tagged `Promote?: yes` or `Promote?: maybe`. Let N = that count (0 if none or file absent).

**Signal B:** (set in Step 1a) — count of session-state files written in the last 36 hours with `end_of_day_due: yes`. Let M = that count.

**Unified banner (fire if A OR B is positive, i.e. N > 0 OR M > 0):**
> "⚠ Yesterday's `/end_of_day` did not fire — [N insight(s) pending and/or M session(s) unflushed]. Recommend running `/end_of_day` before continuing."
> "Want to run `/end_of_day` now or skip?"
- If they want to run it: invoke `/end_of_day` inline before continuing (promotion flow from `/end_of_day` Step 3b)
- If they skip: proceed normally

If neither signal is positive (N = 0 AND M = 0), skip this step silently.

### Step 2: Find the latest daily cache

Look in `.workflow_artifacts/memory/daily/` for the most recent `.md` file. This is what `/end_of_day` saved. If there's no daily cache, check `.workflow_artifacts/memory/sessions/` for any session files and work from those directly.

If neither exists, tell the user there's no saved state and suggest running `/discover` to set up fresh context.

### Step 3: Read context

Read these files in parallel:

1. **Daily cache** — `.workflow_artifacts/memory/daily/<latest>.md` — the consolidated state
2. **Git log** — `.workflow_artifacts/memory/git-log.md` — recent commit history and logic
3. **Active session files** — any `.workflow_artifacts/memory/sessions/*` files with status `in_progress` or `blocked`
4. **Current git state** — for each repo in the project folder:
   ```bash
   git -C <repo> status --short
   git -C <repo> branch --show-current
   git -C <repo> log --oneline -5
   ```
   Check for uncommitted changes, stale branches, open PRs.

### Step 3a: Detect daily-cache format (v2 vs v3)

After reading the daily cache in Step 3, determine its format using the §5.7.1 detection rule below. This governs how to extract the human-facing summary for display in Step 5.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

Daily cache files have no YAML frontmatter — scan the first 50 lines of the file directly (no frontmatter to skip).

- **v3-format** (file contains `## For human` within the first 50 lines): extract the lines from the line after `## For human` until the next `## ` heading. Pass this text to Step 5 as `<yesterday-summary>`.
- **v2-format** (no `## For human` in the first 50 lines): use the first 2 KB of the file as `<yesterday-summary>` (legacy fallback).

### Step 4: Reconcile

For each unfinished task from the daily cache, run these checks and report the result:

1. **Branch match** — Is the repo on the branch the daily cache says? If not, report the actual branch.
2. **New remote commits** — Run `git log HEAD..origin/<branch> --oneline`. If output is non-empty, report "N new commits from remote."
3. **Uncommitted local changes** — Check `git status --short`. If non-empty, list the changed files.
4. **Stale PRs** — If `gh` is available, run `gh pr list --head <branch> --json number,title,reviewDecision,statusCheckRollup --limit 5`. Report any PRs with new reviews or failed checks. If `gh` is not available, report "PR check skipped — gh CLI not installed."

Report each check result in the briefing's "## Since last session" section (matching the existing Step 5 template). If everything matches the daily cache, say "Git state matches cached state — no drift detected."

### Step 5: Present the briefing

Output a clear, concise briefing:

```markdown
# Good morning 👋

## Yesterday's summary
<yesterday-summary extracted from ## For human block (v3) or first 2 KB of daily cache (v2)>

## Since last session
- <any new commits from others, PR reviews, CI results>
- <any drift or changes to note>

## Unfinished work

### 1. <task-name> — <stage>
**Branch:** `<branch-name>`
**Resume at:** <exactly where to pick up>
**Context:** <key decisions and rationale from last session>
**Next steps:**
1. <first thing to do>
2. <second thing>

### 2. <task-name-2> — <stage>
...

## Blocked items
- <task>: <blocker> — <suggested resolution>

## Suggested priority
<Based on urgency, dependencies, and momentum — what to tackle first and why>
```

Keep the briefing factual. Report what you found in each step — do not speculate about what the user might want to do beyond what the daily cache and git state suggest. Let the user decide priorities.

### Step 6: Offer to resume

After presenting the briefing, use AskUserQuestion to ask the user what they want to work on. Dynamically populate options from the daily cache:

- If unfinished tasks exist: include one option per task (capped at 3), ordered by suggested priority. Label = task name; description = current stage + 1-line resume point. Always include "Start something new" as the last option.
- If no unfinished tasks: show only "Start something new" and "Run /discover" (if no discovery data).
- If >3 unfinished tasks: show top 3 by priority and note the rest in chat.

Example (2 unfinished tasks):
```
AskUserQuestion(
  question="What would you like to work on today?",
  options=[
    {label: "auth-refactor", description: "implement — resume at T-04: update token refresh logic"},
    {label: "payment-v2", description: "review — run /review to verify the implementation"},
    {label: "Start something new", description: "Begin a new task not listed above."}
  ]
)
```

Example (no tasks):
```
AskUserQuestion(
  question="What would you like to work on today?",
  options=[
    {label: "Start something new", description: "Begin a new task."},
    {label: "Run /discover", description: "Index the repos first."}
  ]
)
```

## Handling multiple unfinished sessions

If the daily cache has multiple unfinished tasks:
- Present them all, ordered by suggested priority
- Note any dependencies between them (e.g., "Task B depends on Task A's review passing")
- Let the user pick which to resume

## No daily cache found

If there's no daily cache but the project has session files or git history:
- Read the most recent session files from `.workflow_artifacts/memory/sessions/`
- Read `.workflow_artifacts/memory/git-log.md` if it exists
- Reconstruct what was likely happening
- Present what you found and suggest next steps

If nothing exists at all:
- Suggest `/discover` to index the repos
- Ask the user what they'd like to work on

## Important behaviors

- **Be concise.** This is a morning briefing, not a novel. The user wants to know what to do, not re-read everything.
- **Surface surprises.** If overnight CI broke, or someone force-pushed to a branch, or a PR got rejected — lead with that.
- **Respect the user's time.** Don't make them re-read the entire plan. Summarize the resumption point in 2-3 sentences with the exact file/task/line to start at.
- **Check git for real.** The daily cache is what *should* be true. Git state is what *is* true. Always reconcile.
- **Prefer the `## For human` block.** If the daily cache is v3-format, display the `## For human` content as the primary orientation summary — it was written by the previous session's Haiku specifically to orient the next reader. Don't pad or paraphrase it; present it directly.
