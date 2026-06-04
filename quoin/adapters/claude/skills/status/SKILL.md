---
name: status
description: "Renders the quoin workflow pipeline graph with the active phase marked. Use for: /status, 'where am I', 'what phase am I in', 'show workflow progress', 'pipeline graph', 'workflow status'. Read-only — no file artifacts produced."
model: haiku
---

# Status

You render a read-only ASCII pipeline graph showing the current quoin workflow stage for the active task.

*Portable intent doc: `quoin/core/skills/status.md`*

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
        description: "status dispatched at haiku tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in status. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /status`).
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

## Session bootstrap

Cost tracking note: `/status` is a read-only reporting skill. Do NOT append to the cost ledger. Phase: `status`. (Read-only skills skip cost recording — no task context write.)

## Process

Run the status script and print its output:

```
python3 __QUOIN_HOME__/scripts/status_graph.py [--task TASK_NAME]
```

If the user provided a task name, pass it via `--task`. Otherwise omit it and the script auto-selects the most-recently-modified task.

Optional flags the user may request:
- `--compact` — narrow-pane render (≤40 chars per line)
- `--json` — machine-readable JSON output
- `--watch [N]` — refresh every N seconds (default 5); note this runs indefinitely until Ctrl-C
- `--probe-git` — detect in-progress implement via git (slower)
- `--stage N-or-NAME` — for multi-stage tasks

Print the script's stdout directly to the user. If the script exits with code 1, print its stderr as an error message.

## Important behaviors

- **Read-only.** Never write any file. Never commit. Never push.
- **No phase invocation.** Do NOT auto-invoke /implement, /review, or any other skill.
- **Fast.** The script is read-only and cheap; it should return in well under 5 seconds (excluding --watch mode).
- **Project root.** The script walks up from cwd to find `.workflow_artifacts/`. If invoked from a subdirectory, it still finds the right root.
