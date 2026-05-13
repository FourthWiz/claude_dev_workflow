# implement

Runtime-neutral intent for the implement skill. Any runtime adapter that
implements this skill should match the contract described here.

## Purpose

Execute a converged plan: turn task specifications into working code with
tests, commit incrementally, and leave the codebase in a working state after
every commit. The skill produces the concrete code changes that a prior
planning phase specified; it does not redesign the approach.

## When to use

- After planning has converged AND a gate has approved the transition to
  implementation.
- Never before the gate checkpoint; never as an auto-step inside another
  skill except an end-to-end orchestrator that has already received explicit
  user confirmation at the relevant gate.

## Inputs

- Converged `current-plan.md` from the resolved task subfolder under
  `.workflow_artifacts/<task-name>/`.
- Existing source code in the target repositories.
- Optional knowledge cache under `.workflow_artifacts/cache/` (advisory —
  absence is a non-fatal skip; cache aids understanding, not correctness).
- Session state under `.workflow_artifacts/memory/sessions/` (advisory).
- Lessons learned under `.workflow_artifacts/memory/lessons-learned.md`
  (advisory).

All reads MUST tolerate missing optional inputs. The skill MUST apply the
stage-aware path resolver when locating phase artifacts.

## Output

- Code changes in target repositories, committed incrementally; each commit
  leaves the codebase in a working state.
- Updated cache entries at `.workflow_artifacts/cache/<repo>/<dir>/<file-stem>.md`
  and an updated `_staleness.md` (best-effort; skipped if no cache exists).
- Updated `<task_dir>/current-plan.md` with task-status markers as tasks
  complete (file-local IDs per format-kit invariants).
- Updated session-state file under `.workflow_artifacts/memory/sessions/`.
- A new entry appended to the cost ledger at
  `.workflow_artifacts/<task-name>/cost-ledger.md` (phase: `implement`).
- A post-implementation gate audit-log artifact at
  `.workflow_artifacts/<task-name>/gate-implement-<date>.md` (Class A per
  the artifact-format contract; written after the gate runs).

## Behavior contract

- The skill MUST require explicit user invocation. No other skill may
  auto-invoke it. The single exception is an end-to-end orchestrator skill
  where the user has already confirmed entry to the implementation phase.
- The skill MUST read the converged plan completely before acting and confirm
  task scope with the user when the plan covers more than a single dispatch's
  worth of work.
- The skill MUST follow existing code style and conventions; respect existing
  abstractions; write tests alongside implementation; not swallow exceptions;
  not leave debug code.
- The skill MUST commit small, focused changes that leave the codebase in a
  working state at every commit.
- The skill MUST stop and flag plan deviations rather than silently diverging
  — re-planning is a separate explicit user action.
- The skill MUST update `<task_dir>/current-plan.md` with task-status markers
  as tasks complete (file-local IDs per format-kit invariants).
- The skill MUST update or create cache entries for files it modifies, creates,
  or deletes when a cache exists; cache writes are best-effort and never block
  a commit.
- The skill MUST run a post-implementation gate before yielding control. The
  gate produces an audit-log artifact at the task root.
- After the post-implementation gate, the skill MUST stop. The next phase
  requires explicit user invocation.
- Cost-ledger writes are mandatory at session open (phase: `implement`).
- All artifact reads MUST tolerate missing optional inputs (no architecture.md,
  no cache, no prior session state) without aborting.
- The skill MUST apply the stage-aware path resolver when locating phase
  artifacts.

## Bounded-dispatch handling

Large plans may exceed a single dispatch's safe scope: the implement phase
produces many tool calls, and long single-shot dispatches risk stream-level
interruptions in some runtimes. The skill MUST:

- (a) Implement only the tasks it can safely complete within its dispatch
  budget.
- (b) Mark remaining tasks `⏳` in `current-plan.md` with a continuation
  note.
- (c) Commit in-progress work before yielding.
- (d) Inform the orchestrator (or user, if standalone) that more dispatches
  are required.

The specific budget threshold and stream-handling mechanics are
adapter-specific.

## Large tool-result handling

When a tool result substantially exceeds typical sizes AND the task does not
require raw verbatim text, the skill MAY summarize the result for
context-efficiency. Summarization MUST:

- Preserve function/method signatures, error messages verbatim, file paths,
  and line numbers.
- Compress prose explanations, repeated boilerplate, and license headers.
- NOT invent facts.
- Be fail-OPEN: if the summarization mechanism is unavailable, the skill
  falls back to keeping the raw result and emits a one-line warning.

The specific threshold, summarization mechanism, and warning string are
adapter-specific.

## Plan-deviation handling

When the implementer discovers that:
- The plan's assumptions about the code are wrong,
- A task is materially more complex than estimated,
- A dependency works differently than the plan assumed, or
- The approach won't work for a reason not caught in review:

STOP, flag the discovery to the user with impact assessment, and let the user
decide whether to re-plan or proceed with a minor adjustment. The skill MUST
NOT silently deviate.

## Out of scope

- The specific model tier used for code generation — adapter-specific.
- The self-dispatch / cost-guardrail mechanism (sentinel grammar, child-prompt
  prefixes, abort rules) — adapter-specific.
- The dispatch-budget threshold and stream-idle handling — adapter-specific
  (the contract specifies that bounded-dispatch yielding MUST be supported,
  not the threshold value).
- The summarization mechanism for large tool results (subagent dispatch, model
  tier, prompt template, threshold) — adapter-specific.
- Class A artifact write mechanism for session state and cache entries
  (format-kit references, validator invocation, atomic-rename pattern) —
  adapter-specific.
- `path_resolve.py` invocation for locating stage artifacts — adapter-specific
  tooling.
- The post-implementation gate's invocation mode (inline vs. subagent) —
  adapter-specific (the contract specifies the gate MUST run, not how it
  dispatches).
- Cost-ledger row format — adapter-specific plumbing.
- Pull-request creation tooling — adapter-specific.

## v3-format detection rule

The format of phase artifacts is determined by the following verbatim rule.
Every runtime adapter that reads or writes a v3 artifact MUST apply this
rule identically.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

## Notes

- The post-implementation gate audit-log artifact lives at the task root:
  `.workflow_artifacts/<task-name>/gate-implement-<date>.md`.
- The runtime adapter owns: model tier, dispatch mechanism, scope-cap policy,
  large-result summarization, cache-write atomicity, and cost-ledger plumbing.
- The skill is one of the cost-cheapest workflow phases per call but the most
  expensive per-task because of repeated edits — efficient execution matters
  more than thorough exploration.
