# Hooks Guide — Verbose Reference

This file contains detailed documentation for the hooks deployed by `bash install.sh`. See `quoin/CLAUDE.md` `### Hooks deployed by quoin` for the summary table.

## S-4 banner dedup

The SessionStart hook writes a sentinel file at `$TMPDIR/quoin-s4-eod-banner-<YYYY-MM-DD>.tmp` after firing the missing-EOD banner. If a sentinel from within the last 5 minutes exists, the banner is suppressed for the current session start. `/start_of_day` also reads this sentinel (see `/start_of_day/SKILL.md`) and skips its own banner if the hook fired within the last 5 minutes — preventing duplicate noise when both mechanisms are active.

## Fail-OPEN / non-aborting deploy contract

Every hook exits 0 on any error (no abort). If jq is absent, hooks fail-OPEN silently (zero protection — see jq soft-required dependency below). The `userpromptsubmit.sh` block JSON is only emitted AFTER the pending-prompt file is successfully written; if the write fails, the hook exits 0 (passthrough).

## Exact-token exempt-list for `userpromptsubmit.sh`

The hook splits the prompt on whitespace (after stripping ALL leading whitespace including newlines and carriage returns) and matches the FIRST token verbatim. Exempt commands (the hook exits 0 immediately without threshold check): `/checkpoint`, `/compact`, `/clear`, `/help`. These are exact string matches — not regex. `/checkpointfoo` and `/checkpoint--restore` are NOT exempt (different tokens). **Destructive-subcommand exception:** `/checkpoint --purge` is the ONE documented carve-out from the exempt-list — it is treated as NON-exempt despite the `/checkpoint` first-token match, and the hook falls through to threshold logic. The rationale: `/checkpoint --purge` should NOT be runnable under ≥95% context pressure (likely-mistaken at high utilization). All other `/checkpoint` subcommands (`--restore`, no-arg) remain exempt.

## STDIN capture pattern

All three event hooks open with `STDIN=$(cat)` to capture the JSON payload into a variable, then parse with `printf '%s' "$STDIN" | jq -r '<filter> // empty'`. The `// empty` jq filter handles missing fields by returning the empty string instead of `null`, supporting the fail-OPEN discipline.

## `bash install.sh --dry-run`

There is no installer dry-run today. `bash install.sh` does not accept a `--dry-run` flag. To preview the hook stanzas that will be written, read the six `_append_stanza(...)` calls at the bottom of `deploy_hooks()` in `quoin/src/quoin/installer.py`.

## jq soft-required dependency

Runtime hooks parse stdin JSON via `jq`. If `jq` is absent, hooks fail-OPEN silently (zero protection). Install via `brew install jq` (macOS), `apt-get install jq` (Debian), `apk add jq` (Alpine). Note: `jq` is a runtime dependency only — the deploy-time merge in `install.sh` uses the Python stdlib `json` module and does not require `jq` at install time.

## R-09 mitigation (settings.json corruption)

`install.sh` backs up `~/.claude/settings.json` to `settings.json.bak-<timestamp>` before any merge (valid files only; corrupt files are backed up separately on parse error). After writing the merged file, the installer validates the result with a `json.load()` round-trip (Python stdlib) and restores from the pre-merge `.bak` if validation fails, then exits with code 1.

## Tunable constants

Hook scripts read these values at runtime via `${QUOIN_*:-default}` parameter expansion. Defaults are baked into the scripts:

| Constant | Default | Env var override | Notes |
|----------|---------|-----------------|-------|
| `BYTES_PER_TOKEN_CONSTANT` | `8.0` | `QUOIN_BYTES_PER_TOKEN` | Bytes per token for byte-count utilization estimate (V-03 calibrated) |
| `EFFECTIVE_CONTEXT_LIMIT` | `150000` | `QUOIN_EFFECTIVE_CONTEXT_LIMIT` | Effective token limit used as 100% denominator |
| `STOP_THRESHOLD_BPS` | `7000` | `QUOIN_STOP_BPS` | Advisory threshold in basis-points (7000 = 70.00%) |
| `BLOCK_THRESHOLD_BPS` | `9500` | `QUOIN_BLOCK_BPS` | Block threshold in basis-points (9500 = 95.00%) |
| `STALE_SENTINEL_DAYS` | `7` | `QUOIN_STALE_SENTINEL_DAYS` | Days after which pending-prompt-*.txt / pending-restore-*.txt are swept; long-lived sessions may extend to 14+ |
| `POLLUTION_THRESHOLD` | `5000` | `QUOIN_POLLUTION_THRESHOLD` | Score threshold for pollution dispatch (score = transcript_kB + weighted tool-use count); 5000 ≈ 5MB transcript or ~1MB + heavy tool use |

**Basis-points convention:** Utilization values and threshold comparisons use INTEGER basis-points (0..10000) throughout. POSIX `[ ]` does integer comparison only; basis-points eliminate all floating-point comparison hazards. `compute_utilization()` in `_lib.sh` returns a basis-point integer (e.g., `8540` = 85.40% utilization).
