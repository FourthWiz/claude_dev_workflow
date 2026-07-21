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

## Autonomous mode (opt-in)

- Adapters MAY support an opt-in autonomous span: a single explicit
  user-supplied flag that, once accepted, carries the run from
  formulation through finalization with zero prompts.
- Entering the autonomous span still requires clearing a documented
  quality bar via a non-interactive formulation before execution
  begins. A formulation that fails the bar is a hard stop, not a
  silent proceed.
- Every hard stop already defined in this contract — a blocked
  downstream verdict, a failed check past its retry cap, a git
  conflict, a branch-hygiene violation, or a below-bar formulation —
  remains in force under the autonomous span. A hard stop halts the
  run and records the reason for a later resume rather than prompting.
- A hard stop records its reason in a stable sentinel file before the
  run exits. The sentinel schema is five one-line fields: `task`,
  `phase`, `reason`, `timestamp`, `resume_hint`. The sentinel's
  location is stable and lives outside the task-scoped artifact
  folder, so the record survives that folder's later archival.
- The autonomous span MUST NOT create a pull request under any
  circumstance; PR creation stays a separate, explicit user action
  outside this skill's scope, in both interactive and autonomous
  modes.
- Which prompt each downstream phase auto-resolves to, and how
  formulation confidence is scored, is adapter-specific and documented
  in the adapter's own reference material.

## Autonomous durability contract (opt-in supervisor)

An adapter MAY implement an external supervisor that relaunches fresh
sessions to carry an autonomous span across a context-window boundary
that a single session cannot fit in. When it does, the relaunch and
resume MUST agree on the following sentinel path templates, all of
which resolve under `.workflow_artifacts/memory/` — deliberately
outside the task-scoped artifact folder, so each sentinel survives
that folder's later archival:

- **Marker** — `autonomous-run-{task}.marker`, one line, written once
  at autonomous-span entry, before the first phase begins. A resumed
  session reads this marker first, before its own first decision
  point, to re-establish the autonomous span rather than reverting to
  an interactive default and stalling.
- **Per-phase completion sentinels** — `autonomous-progress-{task}/{phase}.done`,
  one file per completed phase. The phase set is the full resumable
  roster documented under "Phase sequence" above; every phase named
  there gets a completion sentinel, none silently excluded. Finer
  progress within a single long-running phase MAY additionally write
  `autonomous-progress-{task}/{phase}.{subphase}.done`. The counting
  glob `autonomous-progress-{task}/*.done` is the union of both forms,
  so either kind of new sentinel counts as forward progress for a
  supervisor's no-progress guard.
- **Done sentinel** — `autonomous-done-{task}.md`, written last, after
  finalization's other side effects complete, so a relaunch after a
  kill mid-finalization can tell the span already reached its terminal
  step and stop without redoing that work.
- **Halt sentinel** — the hard-stop record already defined above
  (`autonomous-halt-{task}.md`); a resuming supervisor checks it after
  the done sentinel, before deciding whether to relaunch again.

This document fixes only the path templates and the phase-roster
coverage rule, so independently implemented supervisors and resumers
agree on the contract shape; the supervisor loop mechanics themselves
(relaunch cap, backoff, launcher) are adapter-specific.

A within-phase mechanism complements the cross-phase relaunch above: a
phase subagent MUST exchange only paths and short summaries with the
orchestrator, never raw content, so the orchestrator's own context stays
bounded across the whole span. A phase subagent nearing its own limit
writes a checkpoint to disk and reports a partial-completion signal
instead of exhausting itself; the orchestrator answers by dispatching a
fresh subagent to continue the same phase from that checkpoint, repeating
until the phase reports normal completion. Whether a subagent detects its
own nearness-to-limit or falls back to a fixed work-unit cap is
adapter-specific.

A resume that honors this contract MUST read the marker before any
other decision point, so a relaunch never reverts to an interactive
default and stalls; MUST derive the next phase from the completion
sentinels rather than from prose state alone, treating a present
sentinel as never-re-run and an absent one as never-skip; and MAY use
sub-phase sentinels to resume partway through a single long phase
rather than restarting it. Each resumable phase is responsible for
writing its own completion sentinel once its work is done, so the
reader and writer sides of this contract stay independently
verifiable.

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
