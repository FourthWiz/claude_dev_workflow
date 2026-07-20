# specify

Runtime-neutral intent for the specify skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Elicit a feature's intent from the user interactively and produce a single,
always-English task specification (`spec.md`) that downstream planning
(`/architect`, `/thorough_plan`, `/plan`) can consume as an authoritative
statement of what the task should accomplish. The skill turns a loose idea
or short problem statement into a structured spec covering context, user
stories, functional requirements, acceptance criteria, and explicit
out-of-scope boundaries.

## When to use

- When a user has a feature idea or problem statement but no structured
  spec yet, and wants to capture intent before architecture or planning
  begins.
- When a task needs a durable, reviewable statement of scope that
  `/architect` and `/thorough_plan` can read as ground truth for what
  "done" means.
- When prior `spec.md` is absent and downstream planning phases need an
  authoritative description of user stories and acceptance criteria.

## Inputs

- The user's stated task description or feature idea (from the invocation).
- Interactive answers gathered during intent elicitation (goals, user
  stories, functional scope, out-of-scope boundaries, underlying intuition).
- Active session state under `.workflow_artifacts/memory/sessions/` — used
  to detect prior specify context and avoid redundant elicitation.
- Optional prior `spec.md` at `<task-root>/spec.md` — when present, the
  skill revises rather than creates from scratch.

All reads MUST tolerate missing files. The skill MUST ask the user for
clarification when intent is ambiguous before writing the spec.

## Output

A single artifact at `<task-root>/spec.md` (Class A per the artifact-format
contract — always-English, no terse body, no `## For human` truncation).
`spec.md` ALWAYS lives at the task root regardless of stage layout:
`.workflow_artifacts/<task-name>/spec.md`

The closed top-level section set is:

- `## Context` — caveman prose: the problem, why it matters, constraints.
- `## User stories` — caveman prose or terse list: who wants what and why.
- `## Functional requirements` — caveman prose or terse list: what the
  feature must do.
- `## Acceptance criteria` — caveman prose or terse list: how "done" is
  verified.
- `## Out of scope` — caveman prose or terse list: explicit exclusions to
  prevent scope creep.

## Behavior contract

- The skill MUST elicit intent interactively (goals, user stories,
  functional scope, out-of-scope boundaries, underlying intuition) before
  writing the spec. It MUST NOT fabricate user stories or acceptance
  criteria the user has not confirmed.
- The skill MUST NOT auto-invoke downstream phases (`/architect`,
  `/thorough_plan`, `/plan`, `/implement`, or any other skill).
- The skill MUST tolerate missing optional inputs (prior spec, session
  state) without aborting.
- Cost-ledger writes are mandatory when a task context is active. The
  ledger lives at `.workflow_artifacts/<task-name>/cost-ledger.md`.
- The skill MUST validate the written spec against the `spec` artifact
  type before considering the task complete.
- The skill MUST, after writing the task spec, check whether the task shifts
  the repo's overall purpose against the repo main spec
  (`.workflow_artifacts/spec.md`, distinct from the task's own `spec.md`).
  When a repo main spec exists and a shift is detected, the skill MUST
  propose a gated, user-approved, diff-surfaced update to it. The skill
  MUST NOT write the repo spec automatically, and MUST NOT create one when
  absent — creating a repo spec from nothing is out of scope for this
  skill (owned by the init-workflow and discover skills).
- When requirements are ambiguous the skill MUST ask the user before
  proceeding.
- **Autonomous non-interactive degrade:** when invoked in an autonomous span
  (a sentinel carried on the invocation, adapter-specific in form), the skill
  MUST NOT block on interactive elicitation. Instead it synthesizes the spec
  from the raw task description plus any available upstream artifacts (a
  prior enriched-prompt document, a prior architecture document, or an
  existing task spec), explicitly records every filled gap as an assumption
  in `## Context`, and adds a self-assessed `confidence` field (0..1) to the
  frontmatter reflecting how well-grounded the synthesis is. The repo-main-spec
  update proposal (below) MUST auto-reject rather than auto-approve in this
  mode — the repo main spec stays human-owned even when task-spec elicitation
  is non-interactive.

## Out of scope

- Implementation of any code.
- Architecture, planning, critic, or review decisions.
- The diff/merge UI mechanism for repo-spec updates — adapter-specific.
  Creating a repo main spec from nothing stays with the init-workflow and
  discover skills, not this skill.
- Runtime-specific dispatch mechanism, model tier choice, or interactive
  elicitation UI — all adapter-specific.
- Consumers of `spec.md` (how `/architect` or `/thorough_plan` read it) —
  out of scope for this skill's contract; consumption is defined by the
  consuming skill's own contract.

## Notes

- `spec.md` ALWAYS lives at the task root
  (`.workflow_artifacts/<task-name>/spec.md`); it is never placed under a
  stage subdirectory. This mirrors the `architecture.md` and
  `cost-ledger.md` task-root invariant.
- The closed section set above is the contract; adapters MUST NOT silently
  introduce non-standard top-level sections.
- The runtime adapter chooses the interactive elicitation mechanism (e.g.
  `AskUserQuestion`), the model tier, and the writer/validation mechanism;
  all are out of scope for this contract doc.
- Unlike `architecture.md` (Class B, English summary + structured body),
  `spec.md` is Class A — the entire document stays always-English prose;
  there is no terse body and no summary-generation step.
