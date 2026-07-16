# run

Runtime-neutral intent for the run skill. Any runtime adapter that
implements this skill should match the contract described here.

## Purpose

End-to-end orchestration of the development workflow from discovery
through finalization. The skill coordinates other skills in sequence —
discover, architect, plan, implement, review, and finalize — and
pauses at every phase boundary for an explicit user confirmation. It
does not perform the work of those phases itself; it sequences, hands
off, and gates.

## When to use

- When the user wants the full pipeline in one invocation rather than
  manually advancing through each phase.
- Never auto-invoked by any other skill; always a deliberate user
  choice.
- The orchestrator is the documented exception that may invoke the
  implementation and finalization skills on the user's behalf, but
  only after the user confirms at the relevant checkpoint. The user's
  invocation constitutes the conscious decision; checkpoint
  confirmations are the safety net.

## Inputs

- Task description (required).
- Profile and round-cap overrides parsed from the task description
  (optional; adapter-specific syntax).
- Prior discovery outputs under `.workflow_artifacts/memory/` (optional;
  adapter checks staleness and skips rediscovery when recent).
- Per-stage artifacts under `.workflow_artifacts/<task-name>/` (optional;
  used for resume support).
- Session-state file under `.workflow_artifacts/memory/sessions/` (optional;
  used to identify the last completed phase on resume).
- Knowledge cache under `.workflow_artifacts/cache/` (optional; advisory).

All reads MUST tolerate missing files. The stage-aware path resolver MUST
be honored when locating per-stage artifacts.

## Output

- A task folder at `.workflow_artifacts/<task-name>/` populated with all
  phase artifacts produced by the orchestrated skills.
- A cost ledger at `.workflow_artifacts/<task-name>/cost-ledger.md` with
  one row per phase session, including the orchestrator's own session.
- A session-state file under `.workflow_artifacts/memory/sessions/`
  tracking current phase, outcomes, and checkpoint history.
- A final completion report rendered to the user after finalization.

## Behavior contract

- The skill MUST chain phases in this order: discover (conditional —
  skip if recent), spec (conditional — skip if Small or if a task spec
  already exists), architect (conditional — skip if Small profile),
  planning (always), implementation, review, finalization.
- After discovery, when no task feature spec exists at
  `<task-root>/spec.md` and the task is not Small, the skill SHOULD
  offer/run the spec phase, gated at its own checkpoint; the skill
  MUST forward the task spec path to the downstream design and review
  phases when present; absence of a spec is always a valid,
  non-blocking outcome (grandfather).
- The skill MUST pause at every phase boundary and wait for explicit
  user confirmation before advancing to the next phase.
- The skill MUST treat each phase as a separate session; the
  orchestrator's own context must remain lean across the full pipeline.
- The skill MUST honor profile triage (Small / Medium / Large) when
  routing sub-skills.
- The skill MUST NOT auto-invoke implementation or finalization without
  a prior user confirmation at the dedicated checkpoint for each phase.
- The skill MUST preserve all artifacts if the user stops the pipeline
  at any checkpoint; partial results remain under
  `.workflow_artifacts/<task-name>/` and can be resumed.
- The skill MUST run finalization in a fresh context for unbiased
  assessment downstream.
- The skill MUST tolerate missing optional inputs (stale or absent
  discovery files, absent architecture, absent prior session state).
- The skill MUST update the session-state file after each phase
  completes so that a resume invocation can identify the next phase
  without rerunning completed work.
- Cost-ledger writes are mandatory when a task context is active.

## Out of scope

- Model tier per phase — adapter-specific.
- Subagent dispatch mechanism — adapter-specific.
- Gate invocation modes (inline vs. subagent) — adapter-specific.
- Session-age guard and long-session warnings — adapter-specific.
- Stream-idle timeout retry policy — adapter-specific.
- JSONL-based cost capture and per-runtime fallback chain —
  adapter-specific.
- CLI mechanics and project-hash derivation — adapter-specific.
- The specific names of the sub-skills invoked at runtime — those are
  adapter-specific.

## Notes

- The orchestrator owns coordination only, never artifact content;
  runtime adapters own model tiers, dispatch mechanisms, cost plumbing,
  and any retry or fail-OPEN behavior.
- Checkpoints are non-optional even when the user invoked the skill
  with a "run everything" intent. Every phase boundary requires a
  conscious confirmation.
- All artifacts produced before a stop are preserved under
  `.workflow_artifacts/<task-name>/` and can be resumed individually or
  via a resume subcommand.
