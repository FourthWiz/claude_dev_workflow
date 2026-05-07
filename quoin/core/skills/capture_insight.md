# capture_insight

Runtime-neutral intent for the capture_insight skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Capture a single short, reusable insight while keeping the user's main task flow
uninterrupted. The skill writes one entry to a daily scratchpad and returns
control immediately.

## When to use

- A gotcha that cost time and would cost time again.
- A non-obvious pattern in the codebase worth remembering.
- A decision whose rationale will be forgotten by tomorrow.
- An unexpected behavior surfaced during work.
- A workflow step that felt slow or wrong (workflow friction).

## Output location

Append entries to a project-relative path under .workflow_artifacts:

    .workflow_artifacts/memory/daily/insights-<YYYY-MM-DD>.md

The file is created on first append of the day with a short header. Subsequent
calls append entries below the header.

## Entry shape

Each entry is a section keyed by capture time and task context, followed by:

- type: pattern | gotcha | decision-rationale | surprise | workflow-friction
- insight: one to three sentences describing the observation
- applies-to: skill names, technology, or "general" (or "workflow" for friction)
- promote: yes | maybe | no — whether to surface for end-of-day review

For workflow-friction entries, promote is always yes (these become Tier 3
suggestions at end of day).

## Behavior contract

- The skill must complete in seconds. No analysis pass, no follow-up questions.
- The skill must not block the caller's main task flow.
- The skill makes a reasonable judgment about type and promote-flag without
  asking the user. The user can always edit or delete the entry afterwards.
- The skill confirms with a single short sentence describing what was captured.

## Out of scope

- Task progress tracking — that lives in session-state files, not in the
  insights scratchpad.
- Any persistence outside .workflow_artifacts/memory/daily/.
- Any dependency on a specific runtime, model tier, or dispatch mechanism.

## Notes

- The set of insight types listed above is closed; a runtime adapter must not
  silently introduce new types.
- The promote field's three values are closed; runtime adapters must not
  introduce new values.
