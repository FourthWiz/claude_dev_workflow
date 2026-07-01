# checkpoint

Runtime-neutral intent for the checkpoint skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Save session-restore state (file paths, not file contents) mid-session so a
fresh session can resume exactly where the current session left off. Also
surfaces and applies pending-restore state when invoked with `--restore`. Does
NOT roll up daily insights, does NOT modify source files, does NOT touch
`lessons-learned.md`.

## When to use

- Before context compaction (to enable restore in a fresh session).
- Between heavy tasks so context can be handed off cleanly.
- User says "checkpoint", "save my place", "save session", "resume", "/checkpoint --restore".
- Auto-fires as the first sub-step of `/cleanup` (default-on; `--no-cleanup` to suppress).

## Save modes

Three modes, selected by `--mode` flag:

- `restore` (default) — write a pending-restore sentinel; the next session reads
  it via `--restore` to re-hydrate context.
- `load-as-reference` — write state as a reference document for other skills to
  read without triggering a restore flow.
- `mid-agent` — lightweight save during an active subagent run; skips cleanup
  and sentinel operations that would disturb in-flight state.

## Inputs

- Current session state: active task name, current phase, recent commits, branch state.
- `.workflow_artifacts/memory/sessions/` — prior session-state files (for reading
  context to save, not modification).
- `.workflow_artifacts/<task-name>/current-plan.md` (advisory; skip if absent).
- Git state across all repos in the project root (branch names, dirty state,
  commits ahead of upstream).

## Output

- A checkpoint state file at `.workflow_artifacts/memory/sessions/<date>-<task>.md`
  (updated with current progress).
- A pending-restore sentinel at `.workflow_artifacts/memory/checkpoint-pending.txt`
  (written on `--mode restore`; absent on other modes).
- On `--restore`: reads the sentinel, re-hydrates the named session file, presents
  the user with a summary of what was in progress, and removes the sentinel.

## Behavior contract

- Paths-not-content: the checkpoint file stores FILE PATHS and TASK NAMES, never
  raw file content. This keeps the file small and avoids stale-content drift.
- Auto-cleanup: unless `--no-cleanup` is passed, invoke the cleanup skill as the
  first sub-step to trash stale sentinels before writing new ones.
- Tolerate missing inputs: all reads MUST handle missing files gracefully (no abort).
- `--restore` MUST NOT overwrite uncommitted source changes in any repo.
- Never commit, push, or modify source files.
- Cost-ledger write is conditional: only when a task context is unambiguously active.

## Out of scope

- Daily-cache consolidation (that is `/end_of_day`).
- Lessons-learned promotion (that is `/sleep`).
- Model tier and §0 dispatch grammar — runtime adapter concerns.
- The specific sentinel file format beyond "a text file marking restore-pending state".
