# end_of_task

Runtime-neutral intent for the end_of_task skill. Any runtime adapter that
implements this skill should match the contract described here.

## Purpose

Finalize a completed task by committing remaining changes, pushing to a remote
branch, capturing lessons learned, aggregating per-session cost across the
task's full life, and archiving the task folder. Marks the task as the user's
explicit acceptance of reviewed work. Does not create pull requests.

## When to use

- Only after the review skill has produced an APPROVED verdict, the final
  quality gate has passed, and the user has explicitly requested finalization.
- Never auto-invoked except by the end-to-end orchestrator after its own
  user-confirmed finalization checkpoint.
- Always a conscious user decision — explicit invocation is required.

## Inputs

- Review artifact(s) under `.workflow_artifacts/<task-name>/` — the skill must
  refuse to proceed if no APPROVED review exists.
- The task's cost ledger at `.workflow_artifacts/<task-name>/cost-ledger.md`.
- Prior session-state files under `.workflow_artifacts/memory/sessions/`
  (advisory).
- The lessons-learned scratchpad at `.workflow_artifacts/memory/lessons-learned.md`
  (advisory; created if absent).
- An interactive lessons-text capture from the user (may be empty).
- The user's commit-or-abort decision and archive type (interactive; captured
  before any sub-phase delegation).

All reads MUST tolerate missing optional inputs. Path lookups MUST use the
stage-aware resolver.

## Output

- Branch pushed to its remote (no force push; no pull-request creation).
- Lessons appended to `.workflow_artifacts/memory/lessons-learned.md` when the
  user supplied non-empty text.
- The per-task session-state file updated to status `completed` with branch and
  commit metadata.
- An aggregated cost summary at `.workflow_artifacts/<task-name>/cost-summary.json`
  recording per-phase, per-model, and grand totals.
- A finalization preflight record at `.workflow_artifacts/<task-name>/eot-preflights.json`
  written before any sub-phase delegation and overwriting any prior copy.
- The task folder archived under `.workflow_artifacts/finalized/<task-name>/`
  (feature-complete) or under the parent feature's `finalized/` directory
  (sub-task-complete), unless the user declared more work is planned.
- A final completion report printed to the user.
- A new entry appended to the cost ledger at
  `.workflow_artifacts/<task-name>/cost-ledger.md` (phase: `end-of-task`).

## Behavior contract

- The skill MUST refuse to proceed if no review artifact with verdict APPROVED
  exists at the resolved task path.
- The skill MUST be invoked explicitly by the user; MUST NOT be auto-invoked
  except by the end-to-end orchestrator under a prior user finalization
  confirmation.
- The skill MUST run tests one final time before any commit or push.
- The skill MUST scan the staged diff for obvious secrets (passwords, API keys,
  tokens) and refuse to proceed if any are found.
- The skill MUST NOT force-push. MUST use a non-rewriting push.
- The skill MUST NOT create a pull request as part of finalization.
- The skill MUST collect interactive answers (commit-or-abort decision, lessons
  text, archive type) BEFORE writing the finalization preflight record and
  BEFORE delegating to any internal sub-phase.
- The skill MUST persist the finalization preflight record at the fixed path
  `.workflow_artifacts/<task-name>/eot-preflights.json` and overwrite any prior
  copy; sub-phase steps MUST read this file rather than re-deriving inputs.
- The skill MUST aggregate cost from the task's cost ledger across ALL sessions
  in the ledger, falling back to a runtime-neutral cost reader when the primary
  reader is unavailable, and MUST persist the result to
  `.workflow_artifacts/<task-name>/cost-summary.json` BEFORE archiving (the
  ledger lives inside the folder about to be moved).
- The skill MUST read `cost-summary.json` BEFORE archiving the folder.
- The skill MUST archive the folder per the user's declared archive type:
  feature-complete moves to `.workflow_artifacts/finalized/<task-name>/`,
  sub-task-complete moves into the parent feature's `finalized/` directory,
  "more work planned" skips the archive entirely.
- The skill MUST append the session's cost-ledger row at phase `end-of-task`
  at session open per shared cost-tracking rules.
- The skill MUST tolerate missing optional inputs (missing prior lessons file,
  missing prior session state, empty cost ledger) without aborting.

## Out of scope

- The specific model tier used to execute the skill — adapter-specific.
- The self-dispatch / cost-guardrail mechanism (sentinel grammar, child-prompt
  prefixes, abort rules) — adapter-specific.
- Session-age guard or long-session warnings — adapter-specific.
- Git CLI surface (binary name, sandbox/approval prompts, push retry policy,
  remote credential handling) — adapter-specific.
- JSONL-based cost capture, third-party cost-reporting CLIs, and the
  per-runtime fallback chain — adapter-specific.
- Per-runtime session lookup (e.g., chat-history file format, project hash
  derivation) — adapter-specific.
- Sub-phase decomposition and inter-phase dispatch mechanics — adapters MAY
  implement the contract as a single pass or as multiple delegated steps.
- Pull-request creation — explicitly a separate user-initiated action, NEVER
  performed here.
- Cost-ledger row format — adapter-specific plumbing.

## Notes

- Finalization is intentionally heavyweight: tests, secret scan, commit, push,
  lessons, session-state update, cost aggregation, and archive must all
  complete. Adapters SHOULD recommend running this skill in a fresh session to
  avoid context-compaction skipping steps.
- The aggregated cost is informational; the cost ledger is the source of truth.
  Cost aggregation MAY produce partial data on failure — partial is better than
  none.
- Archiving never touches planning artifacts of OTHER active tasks; only the
  resolved task folder moves.
- The runtime adapter owns: model tier, dispatch mechanism, git CLI invocation,
  cost-ledger plumbing, session-state writer atomicity, and any sub-phase
  decomposition strategy.
