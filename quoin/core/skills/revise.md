# revise

Runtime-neutral intent for the revise skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Update an existing planning artifact (`current-plan.md`) in response to a
critic round. Address all CRITICAL and MAJOR issues without losing what was
praised. Document the changes in a `## Revision history` section. Preserve
evidence, decision history, and task numbering coherence across rounds.

## When to use

- After a critic round produces a `REVISE`-verdict response and the planning
  artifact at `.workflow_artifacts/<task-name>/current-plan.md` (or its
  stage-resolved path) needs targeted updates.
- When a user explicitly supplies critic feedback and requests that the plan
  be updated to address it.
- Standalone when the orchestrator routes a revision request outside the
  normal convergence loop (e.g., after a manual review).

## Inputs

- `<task_dir>/current-plan.md` (required) — the plan to revise. Path
  resolved by the runtime adapter's path-resolution mechanism.
- The latest `<task_dir>/critic-response-*.md` (required) — the critic
  feedback to address.
- Prior `<task_dir>/critic-response-*.md` files — for trajectory awareness
  and understanding the evolution of the plan; missing files are a no-op.
- Source code re-reads when the critic flagged incorrect assumptions and the
  knowledge cache is insufficient to resolve the concern.
- Optional knowledge cache under `.workflow_artifacts/cache/` — advisory;
  absence is a non-fatal skip.

`current-plan.md` and the latest critic response are required. All other
inputs MUST be tolerated as absent.

## Output

An updated `<task_dir>/current-plan.md` with a `## Revision history` section
containing the new round's changelog entry. The output format is identical to
the plan skill's output (Class B artifact, same closed section set). The
`## Revision history` section is part of the body; it is not a trailing block.

The changelog entry format inside `## Revision history`:

```
Round <N> — <date>
Critic verdict: REVISE
Issues addressed: [CRIT-1] <title> — <how>; [MAJ-1] <title> — <how>
Issues deferred: [MIN-1] <title> — <why>
Changes: <1-2 sentence overview>
```

The skill also updates a session-state file under
`.workflow_artifacts/memory/sessions/`.

## Behavior contract

- Revision MUST be surgical: fix what the critic flagged, preserve what was
  praised. Do not rewrite sections the critic approved.
- The `## What's good` section of the critic response identifies what to keep.
  Accidental regression of praised content is an implementation defect.
- CRITICAL and MAJOR issues MUST be addressed. MINOR issues are handled with
  judgment: fix if quick, note as "known limitation" if out of scope, skip if
  purely stylistic.
- If a CRITICAL or MAJOR issue cannot be resolved within the plan's current
  scope (it requires an architectural change), the skill MUST flag this to
  the user rather than cramming an inadequate fix into the plan.
- Deferred critic issues MUST be clearly marked in `## Revision history` with
  a `[deferred to next round]` note, not silently dropped.
- Task numbering, cross-references, and dependency relationships MUST remain
  coherent after each revision round.
- The skill MUST NOT auto-invoke the next critic round or any downstream phase.
- Cost-ledger writes are mandatory when a task context is active.
  The ledger lives at `.workflow_artifacts/<task-name>/cost-ledger.md`.

## Out of scope

- Re-writing the architecture document.
- Auto-invoking the next critic round or any orchestrator phase.
- Inventing new artifact types or output paths.
- Scope-cap behavior — stream-idle timeout avoidance is a runtime-mechanic-
  specific concern; the runtime adapter declares any tool-use cap.
- Choosing the model tier or summary-generation mechanism — those are the
  runtime adapter's responsibility.

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

If the plan is v2-format, the next write by this skill becomes the v2→v3
upgrade point (the skill writes v3 output regardless of the input format).

## Notes

- The `## Revision history` section name is closed; runtime adapters MUST use
  this exact heading.
- The closed section set of the output artifact is identical to the plan
  skill's output; see `plan.md` for the full enumeration.
- The runtime adapter chooses the model tier. This skill's portable name is
  `revise`; a cost-efficient variant of this skill is documented in
  `revise-fast.md` — see that document for the variance contract.
- `architecture.md` always lives at the task root
  (`.workflow_artifacts/<task-name>/architecture.md`); `current-plan.md`
  lives at the stage-resolved path.
