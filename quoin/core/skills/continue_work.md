# continue_work

Runtime-neutral intent for the continue_work skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Revive the context from a prior working session. Presents a list of recent sessions
the user can pick from, then extracts the checkpoint summary and recent messages from
that session to re-establish working context in the current session.

## When to use

- User says "/continue_work", "resume prior session", "where was I", "revive old session",
  "switch to last session".
- At the start of a session when there is an existing checkpoint to resume.

## Inputs

- `.workflow_artifacts/memory/recent-sessions.md` — index of recent sessions (written
  by hooks and `/checkpoint`).
- Session JSONL files for the sessions listed in `recent-sessions.md` (to extract last
  checkpoint summary and recent messages).
- `.workflow_artifacts/<task-name>/current-plan.md` (advisory, to show task context).

## Output

- A session picker presented to the user showing available recent sessions.
- On selection: a rendered summary in chat of what the session was doing, the last
  checkpoint state, and any unfinished tasks — enabling the user to continue work
  without re-reading all artifacts manually.

## Behavior contract

- Paths-not-content: reference session files by path; read only enough to extract
  checkpoint summaries and the last ~10 messages.
- Tolerate missing JSONL: if a session JSONL file is missing, show a degraded summary
  from the session-state `.md` file instead.
- Never modify source files, never commit, never invoke another workflow phase.
- Graceful no-op if `recent-sessions.md` is absent or empty.

## Out of scope

- Daily-cache consolidation — that is `/end_of_day`.
- Full session transcript replay — only the summary and recent messages are surfaced.
- Model tier and §0 dispatch grammar — runtime adapter concerns.
