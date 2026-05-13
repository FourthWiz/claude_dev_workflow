# revise-fast

Lightweight cost-efficient variant of the `revise` skill. The behavior
contract is identical to `revise.md` — see that document for the full
contract. This file documents only the variance points.

## Purpose

Update an existing planning artifact in response to a critic round, using
a lower-cost model tier. The artifact-format contract, input set, output set,
and behavior contract are identical to the `revise` skill.

## When to use

When the runtime orchestrator routes lower-risk revision rounds to a
cheaper-model variant. Typically used in normal (non-strict) planning
convergence mode when the critic issues are moderate in complexity and the
risk profile does not require the strongest model. The routing heuristic is
runtime-specific; this document does not prescribe it.

The runtime adapter MUST escalate to the full `revise` skill (or trigger
another critic round with the full-strength model) when uncertainty or risk
is high. The threshold for escalation is runtime-specific and not portable.

## Variance from revise

The only differences from `revise.md` are:

1. **Model tier** — this variant runs on a cheaper model tier than the full
   `revise` skill. The specific model name is the runtime adapter's choice.
2. **Orchestrator routing** — this variant is invoked by the orchestrator
   when it determines that the current round's issues are low-risk enough
   to use a cheaper model. The orchestrator's routing logic is runtime-specific.

All other aspects of the skill — the artifact-format contract, the closed
section set of the output, the `## Revision history` changelog format, the
v3-format detection rule, the behavior contract (surgical revision, preserve
what was praised, mandatory cost-ledger writes, do not auto-invoke downstream
phases) — are byte-identical to `revise.md`.

## Notes

- This skill is internal and orchestrator-only; it is not intended for direct
  user invocation. Users who want to revise a plan should use the full `revise`
  skill.
- The full behavior contract, input set, output set, and Notes section live
  in `revise.md`. Adapters MUST implement the contract from that document,
  not from this one.
- The runtime adapter is responsible for the scope-cap behavior (e.g., stream-
  idle timeout avoidance via tool-use limits) — that is a runtime-mechanic-
  specific concern, not a portable contract item.
- The `.workflow_artifacts/<task-name>/current-plan.md` path convention and
  the stage-resolved subdirectory layout are inherited from `revise.md`
  unchanged.
