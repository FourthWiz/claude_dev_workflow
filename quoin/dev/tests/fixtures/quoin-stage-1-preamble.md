## §0 Model dispatch (FIRST STEP — execute before anything else)

<!-- Reference template for review only. The 15 SKILL.md blocks are the source of truth for downstream tests. Per Quoin foundation Stage 1 plan R-07: this fixture is documentation-only and is intentionally NOT byte-equal to inserted blocks (placeholders `<declared>` and `<skill name>` are substituted at insert time per D-05). Worktree-fallback expansion (T-02): fail-graceful path now includes error-class triage; Variant B (a + b + c) shown here as the fullest reference — actual files carry the variant selected by T-01 spike. -->

This skill is declared `model: <declared>`. If the executing agent is running on a model
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
      Dispatch reason: cost-guardrail handoff. dispatched-tier: <declared>.
      Spawn an Agent subagent with the following arguments:
        model: "<declared>"
        description: "<skill name> dispatched at <declared> tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in <skill name>. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /gate`).
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
      Use the AskUserQuestion tool to present options. Question header:
        `Subagent dispatch failed (worktree creation). How to proceed?`
      Options (verbatim labels — downstream tooling may grep them):
        (a) `retry-no-isolation` — Retry dispatch with worktree isolation
            omitted or disabled (the harness exposes an isolation parameter
            that can be omitted or set to a non-worktree value). DEFAULT.
        (b) `retry-with-base <path>` — Retry dispatch rooted at a
            user-supplied git-repo path (harness exposes a per-call
            base-path parameter confirmed by T-01; exact argument name
            per T-01 spike).
        (c) `proceed-current-tier` — Skip dispatch, proceed at the current
            (more expensive) tier. Equivalent to today's fail-OPEN path.
            Always presented.

  - Retry execution (options a and b):
      Sentinel grammar: prepend `[worktree-retry]` as the FIRST LINE of
      the retry Agent call's prompt (position-anchored, not substring match).
      `[no-redispatch]` follows on line 2; user prompt on line 3 onward.
      Prompt form:
        `[worktree-retry]\n[no-redispatch]\n<original user input verbatim>`
      No counter form (`[worktree-retry:N]`) is defined; it is RESERVED for
      future expansion but MUST NOT be emitted or parsed today.
      * Option (a): re-spawn with the same `model:` and `description:`, but
        OMIT the worktree-isolation argument (or set `isolation` to a
        non-worktree value per harness docs confirmed in T-01).
      * Option (b): re-spawn with the same arguments AND the worktree-base-path
        argument set to the user-supplied path (exact argument name per T-01).
      Retry-failed detection: if the incoming prompt's FIRST LINE is exactly
      `[worktree-retry]`, this IS the retry — do NOT re-prompt. Fall through
      to Other-class path with `user-choice=retry-failed`.

  - Other-class path (also: retry fall-through):
      Do NOT abort the user's invocation.
      Emit the bare warning (verbatim):
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
      If this path was reached via a worktree-class error (user choice or
      retry failure), ALSO emit the classification line (second, separate):
        `[quoin-stage-1: error-class=worktree; user-choice=<a|b|c|retry-failed>; proceeding at current tier]`
      Then proceed to §1 at the current tier (fail-OPEN per I-01).
<!-- §0-worktree-fallback-end -->

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).
