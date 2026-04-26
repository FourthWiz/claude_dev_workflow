## §0 Model dispatch (FIRST STEP — execute before anything else)

<!-- Reference template for review only. The 12 SKILL.md blocks are the source of truth for downstream tests. Per Quoin foundation Stage 1 plan R-07: this fixture is documentation-only and is intentionally NOT byte-equal to inserted blocks (placeholders `<declared>` and `<skill name>` are substituted at insert time per D-05). -->

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

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).
