# critic

Runtime-neutral intent for the critic skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Review a planning artifact (`current-plan.md` or `architecture.md`) critically
against the actual codebase. Identify gaps, incorrect assumptions, integration
risks, and missing tests. Classify each issue by severity and emit a
PASS/REVISE verdict. The critic runs with fresh context — separate from the
agent that produced the plan — to avoid cognitive bias.

## When to use

- After a plan or revise round produces or updates `<task_dir>/current-plan.md`
  and the planning convergence loop needs an independent review.
- When an architecture artifact at `.workflow_artifacts/<task-name>/architecture.md`
  requires a critical review (the runtime adapter's architect Phase 4 inner loop).
- When a user explicitly requests a critical review of an existing plan.

## Inputs

- `<task_dir>/current-plan.md` (required when critiquing a plan) OR
  `.workflow_artifacts/<task-name>/architecture.md` (required when critiquing
  an architecture). Exactly one of these is the primary target per invocation.
- Prior `<task_dir>/critic-response-*.md` files — for round detection and
  trajectory awareness; missing files mean this is round 1.
- `.workflow_artifacts/memory/lessons-learned.md` — round 1 only; skip on
  rounds 2+ (file cannot change mid-loop; re-reading wastes tokens).
- The actual source code referenced by the plan — verified directly, not
  trusted from the plan's own claims.
- Optional knowledge cache under `.workflow_artifacts/cache/` — advisory;
  absence is a non-fatal skip. Stale cache entries MUST NOT be used for
  verification; fall through to source reads.

All optional inputs MUST be tolerated as absent. The primary target (plan or
architecture) is required; a missing primary target is an error.

## Output

A single artifact named `critic-response-{round}.md` (when target is a plan)
or `architecture-critic-{round}.md` (when target is an architecture), placed
at the task directory path resolved by the runtime adapter. Architecture-critic
files ALWAYS live at the task root regardless of stage layout.

The artifact is Class A (no `## For human` block). Closed section set:

- `## Verdict: PASS | REVISE` — heading-line form; one of two closed values.
- `## Summary` — 2-3 sentence overview of plan quality and main concerns.
- `## Issues` — grouped by severity subsection:
  - `### Critical (blocks implementation)` — each issue: title, What, Why it
    matters, Where (file:line), Suggestion, Class field (see below).
  - `### Major (significant gap, should address)` — same shape.
  - `### Minor (improvement, use judgment)` — title + Suggestion only.
- `## What's good` — acknowledge strengths; guides the reviser on what to keep.
- `## Scorecard` — markdown table: Criterion / Score (good/fair/poor) / Notes.
  Criteria: Completeness, Correctness, Integration safety, Risk coverage,
  Testability, Implementability, De-risking.

**Per-issue `Class:` field** is REQUIRED for every Critical and Major issue.
The value MUST be one of this closed whitelist (verify exact set against
`classify_critic_issues.py` before writing):

  `enumeration` | `regex-breadth` | `audit-method` | `integration` |
  `risk-coverage` | `testability` | `implementability` |
  `structural-fallback` | `other` | `unknown`

Omitting the `Class:` field or using a value outside this whitelist causes
downstream classifier errors.

## Behavior contract

- The critic MUST run with fresh context — no carry-over from the session
  that wrote the plan. The runtime adapter is responsible for spawning a
  fresh agent; the mechanism is adapter-specific.
- The critic MUST verify claims against actual source code, not just the
  plan's description. Reading the codebase is the most important step.
- The critic MUST emit only `PASS` or `REVISE` as the verdict. The value
  `BAIL-TO-IMPLEMENT` is NOT emitted by the critic; it is synthesized by
  the runtime orchestrator when it determines all remaining CRITICAL and
  MAJOR issues are mechanical.
- Each CRITICAL and MAJOR issue MUST cite a specific location (file:line or
  plan task reference) and include a constructive suggestion.
- The critic MUST acknowledge what is good; the "What's good" section is
  not optional.
- Cost-ledger writes are mandatory when a task context is active.
  The ledger lives at `.workflow_artifacts/<task-name>/cost-ledger.md`.

## Out of scope

- Code edits of any kind.
- Auto-invoking the revise skill or any downstream phase.
- Orchestrating the convergence loop — that is the runtime adapter's
  responsibility.
- Choosing the model tier — that is the runtime adapter's responsibility.

## v3-format detection rule

The format of `current-plan.md` is determined by the following verbatim rule.
Every runtime adapter that reads a v3 plan MUST apply this rule identically.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

When the target is `architecture.md`, apply the same detection rule before
reading (architecture.md may also be v2 or v3 format).

## Notes

- The verdict set is closed (`PASS` / `REVISE`); a runtime adapter must not
  silently introduce new verdict values.
- The `Class:` field whitelist is closed; the canonical source of truth is
  `classify_critic_issues.py`. Adapters should verify the whitelist against
  that file before writing.
- The "fresh context" invariant is runtime-neutral; the adapter decides how
  to spawn a fresh agent and what mechanism to use.
- `architecture-critic-N.md` always lives at the task root
  (`.workflow_artifacts/<task-name>/`), never under a stage subdirectory.
  This is a D-03 corollary applied to critic artifacts.
- On round 1, the critic reads `.workflow_artifacts/memory/lessons-learned.md`.
  On rounds 2+, skip this read — the file cannot change mid-loop.
