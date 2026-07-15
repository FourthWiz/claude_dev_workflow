---
task: sample-task
source: IVG-000
date: 2026-07-15
---

## Context
This feature spec describes a small, well-scoped addition to the sample task. It exists
purely as a validator fixture — the content is illustrative, not a real feature.

## User stories
As a user, I want to configure a preference so that the tool behaves the way I expect.

## Functional requirements
- The system must persist the preference across sessions.
- The system must validate the preference value before saving it.

## Acceptance criteria
- Setting a valid preference value succeeds and persists.
- Setting an invalid preference value is rejected with a clear error.

## Out of scope
- Migrating existing preferences from a prior format.
