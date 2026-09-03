# Hooks deployed by quoin — full reference table

`bash install.sh` deploys hook scripts to `__QUOIN_HOME__/hooks/` and registers seven (event, matcher) stanzas in `__QUOIN_HOME__/settings.json`:

| Event | Matcher | Script | Timeout | Contract |
|-------|---------|--------|---------|----------|
| UserPromptSubmit | `*` | `userpromptsubmit.sh` | 5s | Context utilization check; advisory only — never blocks a prompt |
| PreCompact | `auto` | `precompact.sh` | 10s | ALWAYS allows auto-compaction; appends the STEP 1b `recent-sessions.md` record and a `telemetry/compaction-events.jsonl` pre-event on every row; writes a deterministic checkpoint when a fresh active run-state record matches the session or skill pidfiles are present; a plain conversation (no run, no pidfiles) writes no checkpoint and no sentinel — the recent-sessions and telemetry appends still happen on every row; `QUOIN_PRECOMPACT_NORUN_CHECKPOINT=1` restores the checkpoint-plus-`pending-restore` sentinel for that case; `/continue_work` (fed by `recent-sessions.md`) is the recovery path when nothing is written |
| PostCompact | `auto` | `postcompact.sh` | 5s | Writes `postcompact-reset-${session_id}.txt` sentinel; `userpromptsubmit.sh` STEP 0.5 consumes it to confirm compaction occurred and trash-moves the sentinel |
| SessionStart | `startup` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionStart | `resume` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionEnd | `*` | `sessionend.sh` | 5s | EOD nudge if `end_of_day_due: yes` |
| WorktreeCreate | `*` | `worktreecreate.sh` | 10s | Nested-git worktree isolation for source-mutating skills. Reads the dispatch sidecar; when a single nested repo resolves and the harness omits path/branch, self-generates `quoin/wt-<ts>-<pid>` + a worktree under `${TMPDIR:-/tmp}/quoin-worktrees` (outside the Drive tree; project `.worktrees/` fallback) and runs `git worktree add` (bounded by `QUOIN_SUBPROCESS_TIMEOUT`), printing the path to stdout. Fail-OPEN (exits 0, no stdout on any skip/error); audit log records `selfgen=1`. Opt-out: `QUOIN_WORKTREE_SELFGEN=0`. |

All hooks fail-OPEN (exit 0 on any error). jq is a soft-required dependency (`brew install jq`). Tunable constants (`QUOIN_BYTES_PER_TOKEN`, `QUOIN_EFFECTIVE_CONTEXT_LIMIT`, `QUOIN_STOP_BPS`, `QUOIN_BLOCK_BPS`, `QUOIN_COMPACT_FIRST_BPS`, `QUOIN_PANIC_BPS`, etc.) use `${QUOIN_*:-default}` expansion; thresholds use integer basis-points arithmetic (e.g., `8500` = 85.00%, `9000` = 90.00%).

Hook-side tunable constants (defined in `_lib.sh:read_constants()` and exported to all hook scripts):
- `QUOIN_COMPACT_FIRST_BPS` (default 9000 = 90.00%) — threshold at which `/checkpoint` emits a high-util notice and prompts the user to run `/compact` before saving.
- `QUOIN_PANIC_BPS` (default 10000 = 100.00%) — threshold at which `/checkpoint` switches to a minimal panic/degraded-save path, skipping heavy session-state gathering and AskUserQuestion, writing only a skeleton checkpoint + pending-restore sentinel. `compute_utilization` is unclamped so values >10000 are normal; PANIC_BPS=10000 correctly fires for all true overflow (>=100%).
- `QUOIN_STALE_SENTINEL_DAYS` (pre-existing, default 7) — sentinel age threshold used by `sessionstart.sh` as the fallback sweep window when `session_id` is empty (defense-in-depth, per IVG-95 D-02). Also consumed by `/cleanup` and `/sleep --purge --sentinels`.
- `QUOIN_SESSIONSTART_SWEEP_DAYS` (NEW IVG-95, default 1) — UUID-aware tight sweep window for `sessionstart.sh` STEP 2. When `session_id` is known, files older than this window AND not matching the current session's UUID are trash-moved. Also narrows the STEP 4 cross-session `pending-restore` restore-banner fallback window (intentional per IVG-95 D-08).
- `QUOIN_SOD_SENTINEL_WARN` (NEW IVG-95, default 3) — `start_of_day` Step 1b sentinel-health check threshold. Emits a one-line advisory banner if the count of stale sentinels in `memory/` exceeds this value. Read-only — `start_of_day` never mutates files.
- `QUOIN_PRECOMPACT_NORUN_CHECKPOINT` (NEW IVG-258 S-3, default 0) — opt-in: when 1, `precompact.sh` restores the deterministic checkpoint-plus-`pending-restore` sentinel for a plain conversation (no active run-state record, no skill pidfiles); when 0, that row writes nothing.
- `QUOIN_RUN_STATE_STALE_DAYS` (pre-existing, default 1) — freshness window for `run-state-*.json` records, already documented for `/run` Step 0c's `--max-age-days` reads; IVG-258 S-3 adds a hook-side read site in `precompact.sh`'s run-state selection (day-granular, deliberately over-inclusive).

Skill-side picker knobs (read inline in `checkpoint/SKILL.md`, NOT hook constants — do NOT add to `_lib.sh`):
- `QUOIN_RESTORE_SENTINEL_WINDOW` (default 7 days) — mtime filter for pending-restore sentinel enumeration.
- `QUOIN_SESSION_FALLBACK_WINDOW` (default 7 days) — mtime filter for session-state fallback (B3).
- `QUOIN_RESTORE_STALE_DAYS` (default 1 day) — maximum age for a checkpoint to be silently auto-picked; candidates older than this trigger a loud warning and prefer B3 synthesis. **NOT a hook constant** — read inline at the picker site in `checkpoint/SKILL.md` as `${QUOIN_RESTORE_STALE_DAYS:-1}`; no hook reads it; do NOT add to `_lib.sh`.
- `QUOIN_PICKER_DEDUP_WINDOW` (default 7 days) — window for deduplicating voluntary vs precompact checkpoint pairs.

Skill-side opt-out knobs (IVG-137, read inline in `end_of_day/SKILL.md` / `end_of_task/SKILL.md`, NOT hook constants — do NOT add to `_lib.sh`):
- `QUOIN_DISABLE_EOD_RECONCILE=1` — skips `/end_of_day --recover-orphans`'s Step 0a covered-but-due
  auto-flip pre-pass (falls through to today's Step 0 orphan-only behavior).
- `QUOIN_DISABLE_EOT_FLAG_FLIP=1` — skips `/end_of_task` Sub-phase B's single-invocation
  `--flip-finalized-task` flag-flip + `finalized_by_end_of_task` marker step (finalized sessions
  remain `end_of_day_due: yes` and surface as ordinary backlog on the next `/end_of_day`).

Verbose details: `quoin/docs/hooks-guide.md`.
