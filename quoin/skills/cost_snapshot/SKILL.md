---
name: cost_snapshot
description: "Returns a live cost summary showing today's cost, project lifetime cost, and per-open-task breakdown. Use for: /cost_snapshot, 'how much have I spent', 'cost report', 'show costs', 'what's the project cost', 'how much has this task cost'. Read-only — no file artifacts produced."
model: haiku
---

# Cost Snapshot

You return a live cost summary for the current project. You read cost ledger files to identify sessions, call `ccusage` to get dollar amounts, and print a concise terminal-friendly report.

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
        description: "cost_snapshot dispatched at haiku tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in cost_snapshot. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /cost_snapshot`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## Session bootstrap

Cost tracking note: `/cost_snapshot` is a read-only reporting skill. Append to the cost ledger only if a task context is clearly active (e.g., you were invoked mid-task and the task name is unambiguous). If in doubt, skip cost recording. Phase: `cost-snapshot`.

## Process

### Step 1: Collect ledger data

Determine the project root (the directory containing `.workflow_artifacts/`). Then:

- **Active tasks:** scan `.workflow_artifacts/*/cost-ledger.md` (non-finalized task folders)
- **Finalized tasks:** scan `.workflow_artifacts/finalized/*/cost-ledger.md`

For each ledger file found, parse every data line (skip lines starting with `#` and blank lines). Split each line on `|` (bare pipe, NOT ` | `), strip each field. Require at least 6 fields. If exactly 7 fields, take the 7th as `fallback_fires` (parse as int; on parse failure treat as `0` and emit stderr WARN `cost_snapshot.WARN: malformed fallback_fires column at <ledger>:<lineno>`). If more than 7 fields, treat the 7th as `fallback_fires` and ignore the rest with a stderr WARN. The format is:

```
<uuid> | <date> | <phase> | <model> | <category> | <notes> [| <fallback_fires>]
```

The 7th column is OPTIONAL (Stage 4+ only); 6-column rows are always valid with `fallback_fires=0`.

Build three collections:

- **`today_entries`** — entries where `date` matches today's date (YYYY-MM-DD), from ALL ledgers
- **`all_entries`** — every entry from ALL ledgers (active + finalized), deduplicated by UUID
- **`open_task_entries`** — entries grouped by task name, from active (non-finalized) ledgers only

Also scan today's session-state files at `.workflow_artifacts/memory/sessions/<today>-*.md` for each active task. For each file, read the `## Cost` block and extract the `fallback_fires:` field via regex `^- fallback_fires:\s*(\d+)\s*$`. Sum per task. Store as **`today_fallback_by_task`** (task-name → int). Sessions lacking the `fallback_fires` line (pre-Stage-4) are treated as 0 — no warning emitted.

If no ledger files are found anywhere, print:

```
No cost ledgers found.
Cost tracking starts when skills record sessions to .workflow_artifacts/<task>/cost-ledger.md
```

Then stop.

### Step 2: Run ccusage for each unique UUID

Collect all unique UUIDs from all three collections. Skip any UUID starting with `unknown-` (these are fallback entries with no real session to look up).

**For fewer than 5 unique UUIDs**, run sequentially with a 15-second timeout per call:

```bash
timeout 15 npx ccusage session -i <UUID> --json
```

**For 5 or more unique UUIDs**, use a single bulk call to reduce overhead:

```bash
timeout 30 npx ccusage session --json --since <earliest-date-across-all-entries>
```

Then filter the returned results to only the UUIDs present in your collections.

Parse each JSON response: `{"sessionId": "...", "totalCost": 1.23, "totalTokens": 123456, "entries": [...]}`. Extract `totalCost` per UUID.

If `npx` or `ccusage` is not available (binary not found), OR every ccusage
call returns non-zero, fall back to `cost_from_jsonl.py`:

  # Per-UUID mode (parallel with the ccusage `-i UUID --json` path):
  python3 ~/.claude/scripts/cost_from_jsonl.py session -i UUID --json

  # Bulk mode (parallel with `ccusage session --since DATE --json`):
  python3 ~/.claude/scripts/cost_from_jsonl.py session --json --since DATE

The output JSON shape is identical to ccusage (see /cost_snapshot Step 2
parser). Parse it the same way.

Before printing the cost summary in Step 3, prepend ONE line of context:

  [fallback: cost_from_jsonl.py — prices as of LAST_UPDATED]

Read LAST_UPDATED from the script via:
  python3 -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path.home() / '.claude' / 'scripts')); \
    import cost_from_jsonl; print(cost_from_jsonl.LAST_UPDATED)"

If even the fallback fails (script missing OR exit code 1 on all UUIDs),
print:
  cost tracking unavailable — neither ccusage nor cost_from_jsonl.py
  could resolve session costs. Session counts: N total across M tasks
Then stop.

For individual call timeouts or errors, record cost as `null` for that UUID and continue — do not abort.

### Step 3: Print summary

Using the UUID-to-cost map from Step 2, compute:

- **Today total** — sum costs for UUIDs in `today_entries` (skip nulls and unknown- entries)
- **Lifetime total** — sum costs for all UUIDs in `all_entries` (skip nulls and unknown- entries)
- **Per open task** — for each task in `open_task_entries`, sum costs for that task's UUIDs

Print in this format:

```
Cost Snapshot — <YYYY-MM-DD>

Today:            $X.XX  (<N> sessions)
Project lifetime: $X.XX  (<N> sessions, <M> tasks)

Open tasks:
  <task-name-1>    $X.XX  (<N> sessions)
  <task-name-2>    $X.XX  (<N> sessions)

[<K> sessions with unknown cost — ccusage lookup failed or timed out]
```

When today's fallback total (from `today_fallback_by_task`) is > 0 for a task, append ` (<K> fallback fires today)` after the session count for that task in the "Open tasks" block. When 0, no marker is shown. Similarly, if the lifetime 7th-column sum across all ledgers is > 0, append ` (<K> fallback fires)` after the lifetime session count. If today's total fallback fires across all tasks is > 0, append ` (<K> fallback fires today)` after the Today session count. Never print fallback-fire markers when the count is 0.

Formatting rules:
- Right-align the dollar amounts (pad task names to consistent width)
- Omit the "Open tasks" section entirely if there are no active tasks
- Omit the `[K sessions with unknown cost]` line if all lookups succeeded
- Show `$0.00` if a total is zero (not blank)

## Important behaviors

- **Read-only.** Never write files (except optionally appending to the cost ledger per bootstrap rules). This is a reporting tool only.
- **Fast.** Aim for under 30 seconds. Use the bulk ccusage call when 5+ UUIDs are needed.
- **Graceful degradation.** If ccusage fails or is unavailable, print what you can (session counts, task names) with a clear explanation of what's missing. Do not error out silently.
- **No double-counting.** Deduplicate UUIDs before summing. A UUID appearing in both active and finalized ledgers (shouldn't happen, but possible) counts only once toward the lifetime total.
- **Project root detection.** If invoked from a subdirectory, walk up to find the directory containing `.workflow_artifacts/`. If not found, tell the user and stop.
