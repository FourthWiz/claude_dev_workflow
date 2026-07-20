# enrich

Runtime-neutral intent for the enrich skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Sharpen a raw, loosely-worded task prompt into a clearer, better-grounded one,
upstream of the specify skill. The skill grounds its analysis in real workflow
and codebase context (discovery output, dependency map, any prior task spec),
identifies genuine gaps in the raw prompt, fills them through a small set of
targeted questions, and produces a single enriched-prompt artifact that
downstream intent-capture and planning can consume as a sharper starting
point than the original prompt.

## When to use

- When a user has a loose, ambiguous, or under-specified task description and
  wants it tightened before intent elicitation or architecture begins.
- When a raw prompt makes an assumption that may not hold against the real
  repository structure or dependency graph, and that assumption should be
  surfaced before downstream work proceeds.
- When the user wants a quick sharpening pass without the full structured
  elicitation of a task specification.

## Inputs

- The user's raw task description or prompt (from the invocation).
- Grounding context: discovery output (repository inventory, architecture
  overview, dependency map) and any prior task specification, when present.
- Interactive answers gathered during gap-filling, when the runtime supports
  interactive elicitation.
- Active session state under `.workflow_artifacts/memory/sessions/` — used to
  detect prior enrichment context for this task.

All reads MUST tolerate missing files. The skill MUST ground its gap analysis
in real, available context rather than inventing gaps that are not backed by
something concrete.

## Output

A single artifact named `enriched-prompt.md`, at the task root (Class A per
the artifact-format contract — always-English, no terse body). It ALWAYS
lives at the task root, mirroring the task specification's task-root
invariant: under `.workflow_artifacts/<task-name>/`, filename
`enriched-prompt.md`.

The closed top-level section set is:

- `## Enriched prompt` — the sharpened task description.
- `## Assumptions` — assumptions made to fill a gap, or none.
- `## Open questions` — questions that would have been asked, or genuinely
  unresolved ambiguity the user deferred, or none.
- `## Grounding sources` — which discovery or prior-spec context informed the
  enrichment, or none.

The sharpened prompt MUST also be echoed back to the user directly, not only
written to the file, so the result is visible without an extra file read.

## Behavior contract

- The skill MUST ground its gap analysis in real, available context (discovery
  output, dependency map, prior task specification) rather than inventing
  gaps that are not backed by something concrete.
- When the raw prompt is already clear and well-grounded, the skill MUST say
  so and produce a near-identity enrichment rather than manufacturing changes
  for their own sake.
- When genuine gaps exist and interactive elicitation is available, the skill
  MUST ask a small, targeted set of questions — not a long form, and never a
  question the raw prompt already answers.
- When interactive elicitation is not available, the skill MUST degrade to a
  best-effort rewrite, explicitly flag every assumption made to fill a gap,
  and list the questions it would have asked instead of silently guessing.
- The skill MUST NOT write a task specification, an architecture document, or
  an implementation plan. Its only output artifact is the enriched prompt.
- The skill MUST NOT auto-invoke any downstream phase (specify, architect,
  thorough-plan, plan, implement, or any other skill).
- The skill MUST tolerate missing optional inputs (discovery output, prior
  spec, session state) without aborting.
- Cost-ledger writes are mandatory when a task context is active. The ledger
  lives at `.workflow_artifacts/<task-name>/cost-ledger.md`.

## Out of scope

- Writing a task specification, architecture document, or implementation
  plan — those remain the specify, architect, and planning skills'
  responsibility.
- Auto-invoking any downstream phase.
- Routing or skill selection — that is the triage skill's job, not this
  skill's; enrich only sharpens the prompt it is given, it does not decide
  which skill should run next.
- Runtime-specific dispatch mechanism, model tier choice, or interactive
  elicitation UI — all adapter-specific.
- Consumers of `enriched-prompt.md` (how a user or downstream skill reads it)
  — out of scope for this skill's contract.

## Notes

- `enriched-prompt.md` ALWAYS lives at the task root, under
  `.workflow_artifacts/<task-name>/`, never under a stage subdirectory,
  mirroring the task specification and architecture document task-root
  invariant.
- This skill sits upstream of, and is distinct from, the specify skill: specify
  performs full structured intent elicitation (user stories, functional
  requirements, acceptance criteria); enrich only sharpens the raw prompt
  before that elicitation begins, and is a materially lighter-weight pass.
- It is also distinct from a routing skill: a routing skill proposes which
  skill to run next without changing the prompt's content; this skill changes
  and sharpens the prompt's content but never proposes or invokes a next
  skill itself.
- The closed section set above is the contract; adapters MUST NOT silently
  introduce non-standard top-level sections.
- The runtime adapter chooses the interactive elicitation mechanism, the
  model tier, and the writer/validation mechanism; all are out of scope for
  this contract doc.
