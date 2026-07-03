# start_of_day

Runtime-neutral intent for the start_of_day skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

At the start of a working session, restore the user's prior context from on-disk
artifacts and the version-control history, surface drift between the captured
state and the current repository state, and present a concise resumption
briefing. The skill never makes commits, never edits source files, and never
invokes another workflow phase.

## When to use

- User is starting a new working session.
- User asks "what was I working on".
- User asks to resume or pick up where they left off.
- User requests a morning standup or SOD briefing.

## Inputs

- The latest daily cache file under `.workflow_artifacts/memory/daily/` (the
  most recent `.md` filename, lexicographically; missing-file = no-op fallback
  to session files).
- Active session-state files under `.workflow_artifacts/memory/sessions/`
  (those with `Status: in_progress` or `Status: blocked`).
- The optional resume-cookie at `.workflow_artifacts/memory/resume-cookie.md`
  — its `expires` field gates whether the cookie's `task`, `last_skill`,
  `branch`, and `dirty_count` hints seed the briefing.
- Workflow-state signals under `.workflow_artifacts/memory/` (insights
  scratchpad presence, session-file `end_of_day_due` field, daily cache
  filename for yesterday).
- Current version-control state — for each repo in the project folder: the
  working-tree status, the current branch, and the recent commit history.
- Optional: open-pull-request state from the version-control history hosting
  service if a hosting CLI is available; absence MUST be treated as a
  non-fatal skipped check.

## Output

A single rendered briefing in the runtime adapter's chosen output channel. The
briefing is read-only — no file writes happen during normal operation. Briefing
structure (closed shape): yesterday's summary, what changed since the last
session, unfinished work per task, blocked items, suggested priority. The
yesterday-summary content is sourced from the v3-format `## For human` block of
the latest daily cache when present, and from the leading 2 KB of the file
otherwise.

## Behavior contract

- Read once: workflow-state signals are evaluated once per invocation and never
  re-evaluated during the same briefing.
- Read-only: the skill MUST NOT write any files outside the optional cost-ledger
  row described below.
- Error-tolerant: every input lookup MUST tolerate a missing or unreadable file
  as a "no signal" outcome and continue. A failed signal contributes to the
  briefing as a one-line "skipped — <reason>" note rather than aborting.
- Reconciliation report: every unfinished task from the daily cache is checked
  against current version-control state for branch match, new remote commits,
  uncommitted local changes, and stale review state. Each check produces a
  one-line outcome in the briefing's "since last session" section.
- Format detection MUST be a deterministic string comparison against the
  v3-format detection rule below; no language-model call participates in the
  detection decision (per `lessons-learned.md` 2026-04-23 entry on replay
  non-determinism).
- Cost-ledger writes are conditional and only occur when a task context is
  unambiguously named by the user or unambiguously implied by an active
  session-state file.

## Out of scope

- Any commit, push, or working-tree mutation.
- Decisions about what to work on next — the skill suggests priority based on
  signal scoring but never auto-invokes a downstream workflow phase.
- Promotion of insights to the lessons-learned file (that belongs to the
  daily-rollup phase).
- Any persistence outside the optional cost-ledger row and the briefing output
  channel.
- Any dependency on a specific runtime, model tier, dispatch mechanism, or
  version-control hosting CLI.

## v3-format detection rule

The format of the daily cache file is determined by the following verbatim rule.
Every runtime adapter that reads a v3 daily cache MUST apply this rule
identically.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

Daily cache files have no YAML frontmatter — scan the first 50 lines of the
file directly (no frontmatter to skip).

## Discovery & Serena staleness check (Step 1c)

After Step 1b (sentinel-health check), run `discovery_staleness.py <project-root> --json`
(fail-open: absent script or errors → skip silently). Parse JSON for:
- `verdict == "stale" | "absent"` → discovery needs refresh; fold one-line advisory into Step 1 banner.
- `serena.present_marker=true AND serena.stale=true` → Serena re-onboarding may be needed.
- `serena.present_marker=false` → absent marker (may need first-time onboarding).

This step is **read-only**. Store the result for Step 6b. Use `QUOIN_DISCOVERY_STALE_DAYS`
(do NOT introduce `QUOIN_SOD_DISCOVERY_STALE_DAYS`). `QUOIN_DISCOVERY_AUTOREFRESH=1`
allows this skill to invoke the discover skill inline without asking. Serena refresh is
NEVER auto-run interactively.

## Staleness refresh picker (Step 6b)

A separate AskUserQuestion (after the Step 6 task-resume picker) fires only when Step 1c
detected staleness. Options are built dynamically:
- Discovery stale/absent: `"Refresh discovery"` → invoke the discover skill.
- Serena stale OR absent-marker AND ToolSearch probe succeeds: `"Set up / Refresh Serena memory"` →
  run the §Refresh procedure from serena-activation.md then write/update `serena-onboarded.md`.
- Always: `"Skip refresh"`.
- Graceful Absence: if ToolSearch probe loads no schema → omit Serena option entirely.
- If no staleness in Step 1c → skip Step 6b entirely.

## Notes

- The set of briefing sections is closed (yesterday-summary, since-last-session,
  unfinished-work, blocked, suggested-priority). A runtime adapter must not
  silently introduce new top-level sections.
- The decision of which version-control hosting CLI (if any) to consult is
  runtime-specific and lives in the runtime adapter's own skill definition, not
  in this contract doc.
- The exact reconciliation commands (working-tree-status, branch query, log
  query, optional hosting-service query) are runtime-specific shell invocations
  and live in the runtime adapter's own skill definition. The contract here is
  the per-task one-line outcome shape.
