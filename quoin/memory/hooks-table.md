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

All hooks fail-OPEN (exit 0 on any error). jq is a soft-required dependency (`brew install jq`). Tunable constants (`QUOIN_BYTES_PER_TOKEN`, `QUOIN_EFFECTIVE_CONTEXT_LIMIT`, `QUOIN_STOP_BPS`, `QUOIN_BLOCK_BPS`, `QUOIN_COMPACT_FIRST_BPS`, etc.) use `${QUOIN_*:-default}` expansion; thresholds use integer basis-points arithmetic (e.g., `8500` = 85.00%, `9000` = 90.00%). `QUOIN_COMPACT_FIRST_BPS` (default 9000 = 90.00%) controls the threshold at which `/checkpoint` prompts the user to run `/compact` before saving. Verbose details: `quoin/docs/hooks-guide.md`.
