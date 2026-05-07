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
- cost recording status when available

The exact runtime session identifier may be adapter-specific.

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
