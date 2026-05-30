# Hooks deployed by quoin — full reference table

`bash install.sh` deploys hook scripts to `__QUOIN_HOME__/hooks/` and registers six (event, matcher) stanzas in `__QUOIN_HOME__/settings.json`:

| Event | Matcher | Script | Timeout | Contract |
|-------|---------|--------|---------|----------|
| UserPromptSubmit | `*` | `userpromptsubmit.sh` | 5s | Context utilization check; advisory or block |
| PreCompact | `auto` | `precompact.sh` | 10s | Last-resort save; ALWAYS allows auto-compaction; writes pending-restore sentinel for direct-conversation case (no active pidfiles); sessionstart.sh surfaces the restore banner on next session start |
| PostCompact | `auto` | `postcompact.sh` | 5s | Writes `postcompact-reset-${session_id}.txt` sentinel; `userpromptsubmit.sh` STEP 0.5 consumes it to confirm compaction occurred and trash-moves the sentinel |
| SessionStart | `startup` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionStart | `resume` | `sessionstart.sh` | 5s | Pending-restore + missing-EOD banner (S-4) |
| SessionEnd | `*` | `sessionend.sh` | 5s | EOD nudge if `end_of_day_due: yes` |

All hooks fail-OPEN (exit 0 on any error). jq is a soft-required dependency (`brew install jq`). Tunable constants (`QUOIN_BYTES_PER_TOKEN`, `QUOIN_EFFECTIVE_CONTEXT_LIMIT`, `QUOIN_STOP_BPS`, `QUOIN_BLOCK_BPS`, `QUOIN_COMPACT_FIRST_BPS`, `QUOIN_PANIC_BPS`, etc.) use `${QUOIN_*:-default}` expansion; thresholds use integer basis-points arithmetic (e.g., `8500` = 85.00%, `9000` = 90.00%).

Hook-side tunable constants (defined in `_lib.sh:read_constants()` and exported to all hook scripts):
- `QUOIN_COMPACT_FIRST_BPS` (default 9000 = 90.00%) — threshold at which `/checkpoint` emits a high-util notice and prompts the user to run `/compact` before saving.
- `QUOIN_PANIC_BPS` (default 10000 = 100.00%) — threshold at which `/checkpoint` switches to a minimal panic/degraded-save path, skipping heavy session-state gathering and AskUserQuestion, writing only a skeleton checkpoint + pending-restore sentinel. `compute_utilization` is unclamped so values >10000 are normal; PANIC_BPS=10000 correctly fires for all true overflow (>=100%).

Skill-side picker knobs (read inline in `checkpoint/SKILL.md`, NOT hook constants — do NOT add to `_lib.sh`):
- `QUOIN_RESTORE_SENTINEL_WINDOW` (default 7 days) — mtime filter for pending-restore sentinel enumeration.
- `QUOIN_SESSION_FALLBACK_WINDOW` (default 7 days) — mtime filter for session-state fallback (B3).
- `QUOIN_RESTORE_STALE_DAYS` (default 1 day) — maximum age for a checkpoint to be silently auto-picked; candidates older than this trigger a loud warning and prefer B3 synthesis. **NOT a hook constant** — read inline at the picker site in `checkpoint/SKILL.md` as `${QUOIN_RESTORE_STALE_DAYS:-1}`; no hook reads it; do NOT add to `_lib.sh`.
- `QUOIN_PICKER_DEDUP_WINDOW` (default 7 days) — window for deduplicating voluntary vs precompact checkpoint pairs.

Verbose details: `quoin/docs/hooks-guide.md`.
