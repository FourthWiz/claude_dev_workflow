# security_review

Runtime-neutral intent for the security_review skill. Any runtime adapter
(Claude, Codex, …) that implements this skill should match the contract
described here.

## Purpose

A standalone OWASP-style security pass over a branch's diff: injection,
secrets exposure, authorization gaps, and dependency risks. The skill reviews
the version-control diff against an OWASP-derived checklist and writes a
single security-review artifact recording verdict, findings, and risk
assessment. It never edits source code, never pushes to a remote, and never
invokes a downstream workflow phase. It also serves as the dedicated security
dimension when `/review` fans out for a Large-profile task.

## When to use

- Standalone: whenever a security-focused pass over the current branch's diff
  is wanted, independent of the full `/review` cycle.
- As the security dimension of a Large-profile `/review` fan-out, invoked with
  a focused dispatch contract (branch + plan path) rather than interactively.

## Inputs

- The current git branch and its diff against the merge base (required).
- The converged plan at `.workflow_artifacts/<task-name>/current-plan.md`, if a
  task context is resolvable (optional — see D-07 in the parent task's
  architecture for the no-task-resolvable fallback).
- `architecture.md` at the task root, if present (optional; missing = no-op).

All reads MUST tolerate a missing task context. When no task is resolvable,
the skill still runs against the current branch's diff and writes its
artifact to a standalone location (runtime-adapter-specific).

## Output

A single artifact named with the pattern `security-review-N.md` where N is
the round number starting at 1, written to the resolved task directory when
one exists, else a runtime-adapter-specific standalone location. Required
section set: For human, Summary, Verdict, Findings, Risk Assessment. Optional
sections: Recommendations, Scope.

Verdict is one of three closed values: `APPROVED`, `CHANGES_REQUESTED`,
`BLOCKED` — the identical enum used by `/review`'s own Verdict primitive, so a
standalone run and the fan-out dimension share one vocabulary with no mapping
table required anywhere.

## Behavior contract

- The diff MUST be read in full for the branch under review.
- Findings are checked against an OWASP-derived checklist: injection,
  secrets exposure, authorization gaps, dependency risk.
- Each finding MUST cite a specific file:line reference and propose a fix,
  tagged with severity (CRITICAL/MAJOR/MINOR).
- The skill MUST NOT edit source code, auto-create a pull request, push to a
  remote, or invoke a finalization phase.
- When invoked as the security dimension of a `/review` fan-out, the skill
  returns ONLY the verdict tag and its tagged findings — it does not
  synthesize the parent review's For human, Summary, Plan Compliance, Spec
  Compliance, or Test Coverage sections.
- Cost-ledger writes are mandatory when a task context is active; when no
  task is resolvable, writes go to a standalone ledger location.
- After the phase completes, the skill MUST emit a concise human-readable
  summary of the step's outcome to the user as its final message.

## Out of scope

- Code edits of any kind.
- Remote push or pull-request creation.
- Auto-invocation of any other workflow phase.
- Any dependency on a specific runtime, model tier, or dispatch mechanism.

## Notes

- The set of verdict values is closed (`APPROVED` / `CHANGES_REQUESTED` /
  `BLOCKED`); a runtime adapter must not silently introduce new values, and
  must not introduce a separate OWASP PASS/FAIL vocabulary.
- The runtime adapter uses the runtime adapter's strongest model tier for
  this skill (it is an Opus-tier leaf skill in the Claude adapter); the
  specific model name and dispatch mechanism are out of scope for this
  contract doc.
- Standalone artifact placement (when no task is resolvable) is a
  runtime-adapter concern; the Claude adapter uses
  `.workflow_artifacts/security-review/`.
