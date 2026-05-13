# Session State

Quoin uses files for handoff between stateless agent sessions.

## Location

Session state lives under:

```text
.workflow_artifacts/memory/sessions/
```

Daily and weekly rollups live under:

```text
.workflow_artifacts/memory/daily/
.workflow_artifacts/memory/weekly/
```

## Required Intent

Any runtime adapter doing meaningful workflow work should update session state at natural checkpoints.

At minimum, record:

- status
- current stage
- completed work
- unfinished work
- decisions made
- finalized artifacts or explicit "none"
- continuation context for the next session
- lesson candidates or explicit "none"
- cost recording status when available

The exact runtime session identifier may be adapter-specific.

## Continuation

Session state should let a later runtime session continue without relying on
chat history. A continuation reader should be able to identify:

- the task folder under `.workflow_artifacts/`
- the latest relevant planning, review, gate, and session artifacts
- the first next action
- any blocker, open risk, or check that was not run

Adapters may add deterministic validators for their concrete handoff shape.
Those validators should check repo-local `.workflow_artifacts/` paths and avoid
runtime-global path assumptions.

## Lessons

Reusable lessons belong in:

```text
.workflow_artifacts/memory/lessons-learned.md
```

Lessons should be concise and actionable. They should describe what happened, the reusable takeaway, and which workflow phases should care.

## Daily Insights

Short-lived observations belong in daily insight files:

```text
.workflow_artifacts/memory/daily/insights-<YYYY-MM-DD>.md
```

These are scratchpad entries. They should not replace task progress tracking.
