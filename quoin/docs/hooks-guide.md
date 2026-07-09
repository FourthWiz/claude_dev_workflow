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

Runs the settings.json merge against a temp copy and prints the would-be merged JSON to stdout WITHOUT writing the live file or creating a `.bak` backup. Use this to preview the hook stanzas before committing to a live deploy: `bash install.sh --dry-run | jq '.hooks'`.

## jq soft-required dependency

Runtime hooks parse stdin JSON via `jq`. If `jq` is absent, hooks fail-OPEN silently (zero protection). Install via `brew install jq` (macOS), `apt-get install jq` (Debian), `apk add jq` (Alpine). `bash install.sh` emits a warning if jq is absent at deploy time AND writes `~/.claude/HOOK_MERGE_TODO.md` with manual-merge instructions; install proceeds but hooks will not function until jq is installed.

## R-09 mitigation (settings.json corruption)

install.sh backs up `~/.claude/settings.json` to `settings.json.bak-<timestamp>` before any merge, validates the result with `jq empty`, and restores from `.bak` if validation fails.

## WorktreeCreate hook (`worktreecreate.sh`, IVG-116)

Registered as the seventh stanza (`WorktreeCreate`/`*`, timeout 10s). Fires when a source-mutating skill (`/implement`, `/rollback`, `/end_of_task`, `/pr`) dispatches an Agent with `isolation: "worktree"`. The hook reads the dispatch sidecar (`<project_root>/.workflow_artifacts/.dispatch-hint.json`), calls `git_root_for_dispatch.py --sidecar`, and when a single nested git repo resolves it decides a worktree path:

- **Self-generation (the IVG-116 fix):** when the harness omits `worktree_path`/`branch_name` on the hook's stdin (the pre-fix 100%-skip cause on Google-Drive-synced projects), the hook SELF-GENERATES `BRANCH_NAME="quoin/wt-<ts>-<pid>"` and a `WORKTREE_PATH` under `${TMPDIR:-/tmp}/quoin-worktrees` (outside the Drive-synced tree; project `.worktrees/` fallback), then runs `git worktree add` and prints the created path to stdout. The audit log (`worktree-hook-audit.log`) records `selfgen=1`.
- **Timeout:** `git worktree add` is wrapped in `timeout "${QUOIN_SUBPROCESS_TIMEOUT:-30}s"` via a `git_wt()` helper; if the `timeout` binary is absent the command runs unwrapped (fail-OPEN).
- **Fail-OPEN:** any failure (no nested repo, timeout, git error) exits 0 with NO stdout, so the harness/skill falls back to a plain no-isolation dispatch.
- **Opt-out:** `QUOIN_WORKTREE_SELFGEN=0` restores the old `rc=skip result=missing-worktree-path-or-branch` behaviour.

Whether isolation is even attempted is gated UPSTREAM by the `worktree_isolation.py --decide` STEP A0 in the four source-mutating SKILL.md (default `skip`; see `dispatch-guide.md`). The authoritative hook source is `quoin/quoin/hooks/worktreecreate.sh`; the copy at `quoin/quoin/adapters/claude/hooks/worktreecreate.sh` is a mirror kept byte-identical by a `test_worktreecreate_hook.py` assertion.

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
| `SUBPROCESS_TIMEOUT` | `30` | `QUOIN_SUBPROCESS_TIMEOUT` | Seconds bounding `git worktree add` in `worktreecreate.sh` (and short git subprocesses in the core scripts); ~2× the observed Drive baseline. Fail-OPEN if the `timeout` binary is absent |
| `WORKTREE_SELFGEN` | `1` (on) | `QUOIN_WORKTREE_SELFGEN` | `0` disables hook self-generation of branch/worktree path (restores the old skip-when-harness-omits behaviour) |

**Basis-points convention:** Utilization values and threshold comparisons use INTEGER basis-points (0..10000) throughout. POSIX `[ ]` does integer comparison only; basis-points eliminate all floating-point comparison hazards. `compute_utilization()` in `_lib.sh` returns a basis-point integer (e.g., `8540` = 85.40% utilization).
