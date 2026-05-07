# triage

Runtime-neutral intent for the triage skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Read a user's natural-language prompt and current workflow-state signals,
classify intent against a closed set of workflow phases, and propose the single
best-fit phase with a one-sentence rationale. The skill then tells the user
which command to type to invoke that phase. The skill never invokes a workflow
phase itself — it is propose-only, always.

## When to use

- User is unsure which workflow phase fits their situation.
- User asks "what should I run" or "which skill fits this".
- Ambiguous intent that needs routing before work begins.
- User says "I'm not sure what to do next" or "pick the right command for me".
- User types "route this" or similar open-ended dispatch requests.

## Inputs

- The user's natural-language request.
- Workflow-state signals read from `.workflow_artifacts/` — presence and
  recency of inventory files, plan files, review files, session files, gate
  logs, and daily cache. Missing or unreadable signal files contribute zero
  score (error-tolerant reads; no abort on I/O failure).

## Output

A single recommended workflow phase name, a one-sentence rationale citing the
top scoring signal(s), and a user-facing instruction telling the user how to
invoke that phase in their runtime. No file is written; the proposal is the
sole output.

## Behavior contract

- The routing decision is made once per invocation; signals are evaluated once.
- The skill is propose-only for every routable phase, not just high-impact
  ones. No phase is ever auto-invoked.
- The skill asks at most one clarifying question per invocation. If still
  ambiguous after one round, it hard-exits with a request to invoke the target
  phase directly.
- State-signal lookups MUST be error-tolerant — a failed read counts as zero
  contribution and must never cause an abort.
- Active-task-folder lookups MUST exclude the `finalized/`, `memory/`, and
  `cache/` subdirectories of `.workflow_artifacts/`.

## Out of scope

- Cost-ledger writes (lightweight routing skill; writes are conditional and
  only when a task context is unambiguously named by the user).
- Session-state writes (routing is not "meaningful work" in the session-state
  sense).
- Any persistence outside the proposal text.
- Any dependency on a specific runtime, model tier, or dispatch mechanism.

## Notes

- The set of routable workflow phases is closed (manifest-defined). A runtime
  adapter must not silently introduce new phases.
- The skill catalog and trigger-phrase tables are runtime-specific — they
  reference adapter-installed phase names — and live in the runtime adapter's
  own skill definition, not in this contract doc.
