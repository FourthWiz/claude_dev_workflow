# weekly_review

Runtime-neutral intent for the weekly_review skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Aggregate the meaningful work of a calendar week into a single rendered briefing
under `.workflow_artifacts/memory/weekly/<YYYY-Www>.md`, where the briefing captures
highlights, completed tasks, in-progress tasks, decisions made, lessons learned, git
activity, metrics, and a per-task session cost summary. Never makes commits, never
edits source files, never invokes another workflow phase.

## When to use

- End of a working week.
- User says "weekly summary", "what did I do this week", "week recap", "friday
  review", "weekly standup", or "weekly report".
- Any time the user wants a week-level view.

## Inputs

- Daily-cache files for each date in the week range:
  `.workflow_artifacts/memory/daily/<date>.md`.
- Session-state files for dates in the range:
  `.workflow_artifacts/memory/sessions/<date>-*.md`.
- Rolling git-log: `.workflow_artifacts/memory/git-log.md`.
- Lessons-learned file (advisory): `.workflow_artifacts/memory/lessons-learned.md`.
- Per-task cost-ledger row counts: each active task's
  `.workflow_artifacts/<task-name>/cost-ledger.md` (advisory; session-count
  aggregation only).
- Current version-control state across project repos (recent commits per repo, for
  the week range).
- Optional user override: explicit week range overriding the default
  Monday-through-today.

## Output

- One weekly-review file at `.workflow_artifacts/memory/weekly/<YYYY-Www>.md`
  (Class B per format-kit; `## For human` block composed by the runtime adapter's
  summarization mechanism, written directly in the same generation as the body — no
  separate post-processing script).
- Zero-or-more new lessons appended to `.workflow_artifacts/memory/lessons-learned.md`
  after user confirmation.
- A short rendered report displayed to the user.

## Behavior contract

- Read once: today's daily caches, session files, and git-log are read once per
  invocation; never re-evaluated during the same run.
- Error-tolerant: every input lookup MUST tolerate missing or unreadable files as "no
  signal" and continue. A missing daily cache for a date is a no-op, not an error;
  the skill MUST handle sparse weeks gracefully.
- Sparse-data discipline: if very little data exists for the week, the briefing MUST
  stay short rather than padded with interpretation; the skill MUST NOT fabricate
  activity for a date.
- Multi-week-task handling: in-progress items that started before this week note their
  start date but describe ONLY this week's progress; the briefing MUST NOT replay full
  task history.
- Highlights discipline: each highlight bullet states a concrete outcome or
  deliverable, not a process step. Pattern: "<what was delivered/decided> — <why it
  matters or what it unblocks>". Tasks still in progress are NOT highlights unless a
  significant milestone was hit.
- Honesty on pace: if a task is taking longer than expected, the briefing MUST say so.
  The skill MUST NOT infer mood, intent, or momentum; relate connections between tasks
  factually only.
- Weekly briefing file is Class B per format-kit: it MUST include a `## For human`
  block (5-8 lines, plain English) composed by the runtime adapter's summarization
  mechanism, written in the same generation as the body. The block is placed
  immediately after the H1 heading.
- Weekly cost summary is built from per-task cost-ledger row counts (this week's rows
  only); the skill MUST NOT invoke a version-control cost-reporting tool to compute
  dollar amounts. Dollar amounts come from each task's end-of-task report and from any
  out-of-band cost-reporting tool the user runs manually.
- The skill MUST NOT push, commit, or modify source files.
- The skill MUST NOT auto-invoke another workflow phase.
- User-confirmation gate for lessons promotion: any new lesson appended to
  lessons-learned MUST be confirmed by the user first.
- Cost-ledger writes by this skill itself are conditional: only when a task context is
  unambiguously named by the user or unambiguously implied by an active session-state
  file (mirror end_of_day.md cost-ledger semantics).

## Out of scope

- Model tier and dispatch mechanism — the runtime adapter handles these.
- The §0 self-dispatch grammar — runtime-specific.
- Per-runtime session-file enumeration (Claude reads JSONL session IDs; other runtimes
  may use different mechanisms).
- The exact shell invocations for version-control status, log, and per-repo
  enumeration (e.g., the specific date-range flags supported by the local
  version-control CLI).
- Cost-CLI invocations and dollar-amount computation.
- The specific reformatting rules for the briefing body beyond "Class B per format-kit"
  and the closed section list (see Notes).

## Notes

- The briefing section set is closed: `## For human`, `## Highlights`,
  `## Completed Work`, `## In Progress`, `## Decisions Made`,
  `## Lessons Learned This Week`, `## Git Activity`, `## Metrics`,
  `## Weekly cost summary`, `## Next Week`. Adapters MUST NOT silently introduce new
  top-level sections.
- The week range defaults to Monday-through-today (ISO week). The user MAY override
  with an explicit range.
- The week-file filename uses ISO week number: `<YYYY-Www>.md` (e.g., `2026-W12`).
- The Highlights section caps at 3-5 bullets; the briefing as a whole MUST be
  scannable (tables, bullet points, clear headers; no walls of text).
- The `.workflow_artifacts/<task-name>/` path pattern is the canonical location for
  per-task artifacts; the skill reads per-task cost-ledger files there.
