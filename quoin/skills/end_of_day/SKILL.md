---
name: end_of_day
description: "Consolidates all of today's work across all sessions into a daily cache for next-day resumption. Works in any session — fresh or active. Use this skill for: /end_of_day, 'wrapping up', 'done for the day', 'save my progress', 'end of day', 'EOD'. Captures what was worked on, what's unfinished, blockers, decisions made, and recent git activity. The daily cache feeds into /start_of_day for seamless resumption."
model: haiku
---

# End of Day

You consolidate all of today's work into a daily cache that `/start_of_day` can restore tomorrow. This skill works in any session — you can run it in a fresh session at end of day, or from inside an active working session. Everything except Step 1 reads from disk, so no prior context is needed.

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
      Spawn an Agent subagent with the following arguments:
        model: "haiku"
        description: "end_of_day dispatched at haiku tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in end_of_day. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /end_of_day`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## How sessions and daily caches work

```
.workflow_artifacts/
├── memory/
│   ├── sessions/
│   │   ├── 2026-03-17-auth-refactor.md       ← individual session states
│   │   ├── 2026-03-17-payment-migration.md
│   │   └── 2026-03-18-auth-refactor.md
│   ├── daily/
│   │   ├── 2026-03-17.md                      ← daily rollup (from end_of_day)
│   │   └── 2026-03-18.md
│   ├── git-log.md                             ← rolling log of recent commits
│   ├── repos-inventory.md
│   ├── architecture-overview.md
│   └── dependencies-map.md
├── <task-name>/                               ← active task artifacts
└── finalized/                                 ← completed task archives
```

Multiple sessions can run in a day (parallel tasks, or revisiting a task). Each session writes its own state file. `/end_of_day` reads ALL session files for today, picks out the unfinished ones, and rolls them into one daily cache.

## Process

### Step 1: Save current session state (skip if no active task)

# V-05 reminder: T-NN/D-NN/R-NN/F-NN/Q-NN/S-NN are FILE-LOCAL.
# When referring to a sibling artifact's task or risk, use plain English (e.g., "the parent plan's T-04"), NOT a bare T-NN token. See format-kit.md §1 / glossary.md.
Write session-state files in v3 format per the §5.4 Class A writer mechanism (reference format-kit.md / glossary.md / terse-rubric.md at the body write-site; session artifact type per format-kit §2; validate via validate_artifact.py with retry-once-then-English-fallback). Write `daily/insights-{date}.md` in v3 format per the §5.4 Class A mechanism — append-only structure (each insight as an entry per the template at Step 3 of /capture_insight); body uses caveman prose with terse-rubric for the entry content; no V-02 section-set strict-match (insights file uses the default minimal section set since each entry is its own implicit "section"); validate via validate_artifact.py and accept default fallback semantics on V-failure. `daily/{date}.md` (the rendered daily briefing) remains Class B per parent Stage 3 work — the file gets a `## For human` block prepended (composed directly by Haiku in the same generation as the body — no script invocation). The terse-rubric applies inside prose-shaped sections only (composed with format-kit per format-kit §5).

**If this session has no active task** (e.g. you opened a fresh session just to run `/end_of_day`), skip the session-state write and proceed to Step 2. The existing session files on disk are the source of truth.

**If there is active work in this session**, create or update a session file at `.workflow_artifacts/memory/sessions/<date>-<task-name>.md`.

The session file MUST include these required sections (per format-kit.sections.json session.required_sections):
- **## Status:** `in_progress` | `completed` | `blocked`
- **## Current stage:** which workflow step (architect / plan / critic / revise / implement / review)
- **## Completed in this session:** terse numbered list with status glyphs ✓/⏳/🚫 + commit hashes
- **## Unfinished work:** remaining tasks; where exactly to pick up (file paths, task numbers, branch names)
- **## Cost:** YAML block — Session UUID, Phase, Recorded in cost ledger (see CLAUDE.md "Session state tracking")

Optional sections: `## Decisions made` (important decisions and rationale), `## Open questions` (blockers, unclear requirements).

### Step 2: Update git-log.md

Scan all repos in the project folder and update `.workflow_artifacts/memory/git-log.md` with recent commits. This is a rolling window — keep the last ~50 commits across all repos, newest first.

```markdown
# Recent Git Activity

Last updated: <datetime>

## <repo-name>
### <branch-name>
- `<short-hash>` <commit message> — <date>
  <1-line summary of what the commit actually changed and why>
- `<short-hash>` <commit message> — <date>
  <1-line summary>

## <other-repo>
...
```

To build this:
```bash
# For each repo directory
git -C <repo-path> log --all --oneline --date=short --format="%h %s — %ad" -20
```

Then for each commit, briefly describe what it changed (read the diff summary, not the full diff):
```bash
git -C <repo-path> diff-tree --no-commit-id --name-status -r <hash>
```

Keep commit descriptions to one sentence. Base them on the commit message and diff summary — do not speculate about intent beyond what the message states.

The goal is to capture the *logic* of recent changes — not just file lists but *why* things changed. This helps `/start_of_day` and `/architect` understand momentum and recent direction.

### Step 3: Produce the daily cache

Read all session files for today from `.workflow_artifacts/memory/sessions/<today>-*.md`. For each:
- If status is `completed` → note it as done, no action needed
- If status is `in_progress` or `blocked` → include in the daily cache

Write the daily cache to `.workflow_artifacts/memory/daily/<date>.md`:

```markdown
# Daily Cache — <YYYY-MM-DD>

## For human

<5-8 line plain-English summary: what was the day's focus; which tasks made progress; what is the biggest open blocker; what to do tomorrow. Written directly by the Haiku writer in the same generation as the body — NOT via a summary script>

## Summary
<1-2 sentences: what was the day's focus, what got done, what's left>

## Completed today
- **<task-name>**: <what was finished>

## Unfinished — carry forward

### <task-name-1>
**Stage:** <architect / plan round 3 / implement task 4 of 7 / review>
**Branch:** <branch-name>
**Pick up at:** <exactly where to resume — file, task number, next step>
**Key context:**
- <decisions made that affect next steps>
- <blockers to resolve>
- <relevant file paths and PR URLs>
**Remaining work:**
- <specific next actions>

### <task-name-2>
...

## Decisions log
<All decisions made today across all sessions, with rationale>

## Git activity summary
<High-level: N commits across M repos. Key changes: ...>
<Reference .workflow_artifacts/memory/git-log.md for details>

## Cost summary
<!-- Session counts from cost-ledger.md files — no ccusage calls -->
- **<task-name>**: <N> sessions tracked today (phases: <plan, implement, ...>)
- **<task-name-2>**: <N> sessions tracked today (phases: ...)
- **Day total**: <N> sessions across <M> tasks
*Dollar amounts: run /end_of_task for each completed task to see the full cost breakdown.*

## Tomorrow's priorities
<Based on what's unfinished, suggest what to tackle first>
```

To populate the **Cost summary** section: for each active task today, check if `.workflow_artifacts/<task-name>/cost-ledger.md` exists. If it does, count the data lines (non-header, non-blank) where the date column matches today's date, and list the unique phase values. Do NOT run `npx ccusage` — Haiku does not orchestrate cost lookups. Just report counts and phases. Dollar amounts are computed by `/end_of_task`.

Also scan today's session-state files at `.workflow_artifacts/memory/sessions/<today>-*.md` for each active task. For each file, read the `## Cost` block and extract the `fallback_fires:` field via regex `^- fallback_fires:\s*(\d+)\s*$`. Sum per task. For each task with today's fallback total > 0, append the suffix `; <K> fallback fires today` to that task's Cost summary line. Add a `## Day total` line at the bottom of the Cost summary block when the day's fallback sum > 0: `Day total fallback fires: <K>`. After the Day total line, add: "A non-zero fallback count indicates one or more Class B writers fell back to v2-style write (no `## For human` summary, no validator gate). Investigate which skill emitted `[format-kit-skipped]` and triage before next session." Sessions lacking the `fallback_fires` line (pre-Stage-4) are treated as 0 — no warning emitted.

### Step 3b: Review and promote daily insights

Check if `.workflow_artifacts/memory/daily/insights-<today>.md` exists. If it does:

**Pass 1 — Filter:**
- Skip entries tagged `Promote?: no`
- Collect entries tagged `yes` (high-confidence) and `maybe` (review needed)

**Pass 2 — Deduplicate:**
- Read `.workflow_artifacts/memory/lessons-learned.md`
- If a collected entry is substantially similar to an existing lesson, drop it or flag it as a duplicate
- An entry is a duplicate if it describes the same root cause AND the same takeaway as an existing lesson. Entries about the same topic but with different lessons are NOT duplicates — keep both and note the connection.

**Pass 3 — Tier 3 check:**
- Any entry with `Applies to: workflow` or type `workflow-friction` is a Tier 3 candidate
- Append those to `.workflow_artifacts/memory/workflow-suggestions.md` in this format:
  ```markdown
  ## <date> — <source-task>
  **Suggestion:** <what should change in the workflow>
  **Why:** <the observation from the insight entry>
  **Affects:** <relevant SKILL.md or CLAUDE.md section>
  **Status:** surfaced
  ```
- Tell the user: "I've added N workflow improvement suggestion(s) to `.workflow_artifacts/memory/workflow-suggestions.md`."

**Promotion confirmation:**
If there are entries to promote (after filtering and dedup), present a compact list:

```
I captured N insights today worth keeping. Confirm which to add to lessons-learned:

1. [yes] <insight summary, 1 line>
2. [maybe] <insight summary, 1 line>
3. [maybe] <insight summary, 1 line>

Reply with the numbers to keep (e.g. "1 3"), "all", or "none".
```

Wait for the user's response, then append confirmed entries to `.workflow_artifacts/memory/lessons-learned.md`:

```markdown
## <date> — <task-name>
**What happened:** <the insight>
**Lesson:** <the reusable takeaway>
**Applies to:** <relevant skills>
```

If the insights file doesn't exist or has no promotable entries, skip this step silently.

### Step 3c: Prune lessons-learned if oversized

Check `.workflow_artifacts/memory/lessons-learned.md`. Count the number of lesson entries by matching lines that begin with `## ` followed by a date pattern (YYYY-MM-DD) — i.e., lines matching the regex `^## \d{4}-\d{2}-\d{2}`. Ignore any such patterns inside HTML comments (`<!-- -->`), code blocks, or template examples.

**If the count exceeds 30 entries**, present a pruning prompt to the user:

> "lessons-learned.md has grown to N entries (~X tokens). Large files add a fixed token cost to every /plan, /critic, and /architect session. Would you like to prune?"
>
> Options:
> 1. **Auto-prune** — I'll merge related entries, remove entries older than 90 days that haven't been referenced, and consolidate duplicates. You review before I save.
> 2. **Manual prune** — I'll list all entries with a 1-line summary; you pick which to keep.
> 3. **Skip** — keep the file as-is.

**Auto-prune rules** (if selected):
1. Group entries by `Applies to:` tag. If 3+ entries have the same tag and similar content, merge them into one consolidated entry preserving all unique information.
2. Entries older than 90 days that are generic advice (e.g., "always run tests", "check error handling") can be removed — the behavior should be internalized by now.
3. Entries that reference specific files or functions that no longer exist in the codebase can be removed (check with a quick file-existence test).
4. Always preserve: entries tagged as applying to `/architect` or `/critic` (highest-leverage skills), entries less than 30 days old, entries the user explicitly marked as important.
5. Show the proposed changes to the user in a before/after summary and wait for explicit confirmation before overwriting.

**If the count is 30 or fewer**, skip this step silently.

### Step 3d: Write resume cookie + flip end_of_day_due

**After** the daily-cache write (Step 3) succeeds, do two things:

**1. Flip `end_of_day_due: no`** in each session-state file that was rolled into the daily cache:
- For each session file processed in Step 3 (those read from `.workflow_artifacts/memory/sessions/<today>-*.md`), edit the file in place to set `end_of_day_due: no`.
- Use an atomic write: open the file, replace the `end_of_day_due: yes` line with `end_of_day_due: no`, write to `<path>.tmp`, then `os.rename(tmp, path)`.
- Flip ONLY after the daily-cache write succeeded — a crashed `/end_of_day` must NOT mark sessions as processed.
- This is one of two signals `/start_of_day` reads to detect a missing-EOD condition (the other is the existing insights-file check).

**2. Write resume cookie** to `<project-root>/.workflow_artifacts/memory/resume-cookie.md`:
- Cookie size cap: 2 KB. If the body would exceed 2 KB, truncate the "what's next" hint to ≤2 lines.
- Cookie content (Tier 3, terse-only):
  ```yaml
  ---
  task: <active-task-name or empty>
  last_skill: end_of_day
  branch: <current git branch>
  dirty_count: <N uncommitted changes>
  expires: <now + 24h ISO datetime, e.g. if now is 2026-04-30T14:00:00Z then expires is 2026-05-01T14:00:00Z>
  ---
  <1-2 line "what's next" hint, free text>
  ```
- **Field allowlist** (hardcoded): `task`, `last_skill`, `branch`, `dirty_count`, `expires`. The writer MUST refuse to include any field not in this list. This prevents sensitive data from leaking into the cookie.
- **Atomic-rename pattern**: write to `resume-cookie.md.tmp` via Python `open(path, 'w')`, then `os.rename(tmp_path, final_path)`. Do NOT use shell `mv` in Python contexts — use `os.rename`.
- Cookie path: `<project-root>/.workflow_artifacts/memory/resume-cookie.md` (under `.workflow_artifacts/` which is gitignored — cookie is never committed).

### Step 4: Prompt for lessons learned

Ask the user:

> "Anything else that surprised you today, or that should work differently next time?"

(If insights were already promoted in Step 3b, this catches anything Claude missed.)

If they share something, append it to `.workflow_artifacts/memory/lessons-learned.md` in the same format. If they say "nothing" or skip, that's fine.

Also: if any tasks were rolled back today, or if the critic-revise loop ran more than 3 rounds, auto-add a lesson capturing what made it difficult.

### Step 5: Report to user

Tell the user:
- What was saved
- How many sessions were active today, how many completed vs unfinished
- What the daily cache recommends for tomorrow
- Remind them to run `/start_of_day` when they resume

## Important behaviors

- **Capture decisions.** The hardest thing to remember across days isn't *what* you were doing — it's *why* you made certain choices. Always capture decision rationale.
- **Be specific about resumption points.** "Continue implementing" is useless. "Continue with Task 4 (add retry logic to payment.service.ts:processRefund), branch `feat/payment-retry`, tests for Tasks 1-3 passing" is useful.
- **Don't overwrite previous sessions.** If there's already a session file for this task today (from an earlier session), update it rather than replacing it — preserve the history of what was done earlier.
- **Git log captures logic, not just files.** "Modified 3 files" tells you nothing. "Added exponential backoff to payment retries because Stripe recommends it for idempotent requests" tells you everything.
