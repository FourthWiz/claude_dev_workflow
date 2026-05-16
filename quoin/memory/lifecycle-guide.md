# Lifecycle skills — full reference

## Consumer audit (extracted 2026-05-15)

Pre-edit audit finding: `checkpoint/SKILL.md` contains a full self-contained specification of mode auto-detection logic (Step 1.5, pidfile checks, COMPACT_FIRST_BPS). It does NOT rely on CLAUDE.md as the authoritative source for that logic. The condensed CLAUDE.md text acts as a human-readable summary only; skills bootstrap from their own SKILL.md. No SKILL.md update needed.

## /checkpoint — full reference

Three skills handle session lifecycle at different granularities (v3 lifecycle separation per architecture):

**`/checkpoint`** — general-purpose state-save (mid-session, between tasks, between sessions). Supports three save modes via `--mode <name>` (auto-detected if omitted):
- `--mode restore` (default): writes the full checkpoint file and `pending-restore-${session_id}.txt` sentinel; use for standard resume-in-new-session flow.
- `--mode load-as-reference`: writes the full checkpoint AND `pending-resume-ref-${session_id}.txt`; instruct user to start a new session with `claude --resume SESSION_ID --fork-session`. The forked session sees the prior transcript as background context; sessionstart.sh emits a banner.
- `--mode mid-agent`: writes a minimal `mid-agent-handoff-${session_id}.txt` only (skips full checkpoint write); for use when another skill is actively running. User can type `/clear` then `/checkpoint --restore` in the same session, or `claude --resume SESSION_ID` in a new terminal.

Does NOT roll up dailies, does NOT touch `lessons-learned.md`, does NOT touch `forgotten/`. Use it mid-session before context exhaustion (when the context-utilization advisory fires), between tasks, between sessions, or proactively before starting new heavy work. **Paths-not-content rule (D-04):** checkpoint files record only PATHS to in-flight artifacts — never file contents. Restore re-fires Read tool on disk artifacts in the new session.

Auto-detection at invocation time: (1) if context utilization >= `COMPACT_FIRST_BPS` (default 90.00%), prompt user to run `/compact` then `/checkpoint --after-compact` (compact-first flow); (2) if other skills are detected via pidfiles, default to mid-agent mode; (3) otherwise, ask user to choose restore vs load-as-reference.

**`--restore` subcommand:** Run `/checkpoint --restore` in a fresh session to re-hydrate state. Locates the most recent checkpoint (or follows the `pending-restore-${session_id}.txt` sentinel from the compaction-block flow), surfaces task state, and optionally re-fires the saved pending prompt. Sentinel cleanup happens on restore. Voluntary `/checkpoint` now records `## Session ID` (UUID-anchored; two-line form) to disambiguate session-state lookup; restore picker now covers both pending-restore sentinels and recent (<= 30 day) checkpoint files (with fast-path bypass when current-session sentinel exists); `--defer` writes a marker that suppresses the userpromptsubmit advisory until the next compact or successful voluntary save; `--after-compact` is an explicit intent flag for the post-compact bypass case (also trash-moves the `checkpoint-pending-compact-${session_id}.txt` deferred-compact marker).

## /end_of_day and /sleep — full reference

**`/end_of_day`** — rolls up daily session state into `.workflow_artifacts/memory/daily/<date>.md`. Touches `lessons-learned.md` if insights are promoted. Run at end of each work session.

**Session hooks (S-4):** `/start_of_day` checks `end_of_day_due: yes` in session files (Signal B, 36 h window). The `sessionstart.sh` hook provides the same check unconditionally at session-open (no need to invoke `/start_of_day`). The `sessionend.sh` hook nudges at session-close if the active session still has `end_of_day_due: yes`. Both hooks are non-blocking (exit 0) and informational only. Dedup: the sentinel file prevents duplicate banners within a 5-minute window.

**`/sleep`** — Haiku-tier. Auto-invoked by `/end_of_day` as its final step (opt-out via `--skip-sleep`). Scans daily insights + session files within a 30-day window. Three-bucket decisions:
- Promote → `lessons-learned.md` (per-entry user confirmation)
- Soft-Forget → `forgotten/<date>.md` archive (per-entry user confirmation in default mode; skipped above `forget_quiet_floor` score with `--quiet-forget`)
- Middle-Band → deferred

First 30 days of production: `/sleep --dry-run` mode only (no writes); inspect proposed decisions to tune weights.

Subcommands:
- `/sleep --restore <pattern>`: moves entries back from `forgotten/` to their source (or today's insights if source gone)
- `/sleep --purge --older-than 90d`: true-deletes archive files; per-file confirmation; never auto-run
- `/sleep --escalate`: re-examines middle-band candidates on Opus for deeper reasoning

**Boundary:** `/sleep` writes ONLY to `lessons-learned.md` and `forgotten/<date>.md`. Does NOT touch `~/.claude/projects/<hash>/memory/` (auto-memory). Distinct from `/checkpoint` (general-purpose state-save) and `/end_of_day` (end-of-workday rollup).

**Boundary summary:**
- `/checkpoint` → general-purpose state-save (`checkpoints/`, `sessions/`, `pending-*` sentinels — mid-session, between tasks, between sessions)
- `/end_of_day` → end-of-workday only — daily rollup (`daily/`, `lessons-learned.md`) + auto-invokes `/sleep`
- `/sleep` → long-term memory promote/forget (S-3 scope)

## Memory layout

Directory tree and `forgotten/<date>.md` entry format:

```
.workflow_artifacts/memory/
├── sessions/          ← per-session state files
├── daily/             ← rendered briefings + insights scratchpads
├── weekly/            ← weekly review summaries
├── checkpoints/       ← /checkpoint restore sentinels
├── forgotten/         ← soft-forget archive (NEW — S-3)
│   └── <date>.md      ← one file per day /sleep ran with forgets
├── trash/             ← recoverable delete archive (sentinel trash-moves land here)
│   └── <YYYY-MM-DD>/  ←   dated subdirs, one per trash day
└── lessons-learned.md ← long-term institutional memory
```

Note: `trash/` accumulates sentinel files moved by `trash_move()` (in `_lib.sh`) instead of hard-deleted. The `/sleep --purge --older-than 90d` scope does not yet include `trash/` — this is a known gap (R-7); a follow-up task will extend `/sleep --purge` to cover `trash/`.

Each `forgotten/<date>.md` file is append-only. Each entry block follows this format:

```
> Source: <absolute-path-to-source-file>:<start-line>..<end-line>
> Forgotten: <ISO timestamp>
> Score: forget=<N>, promote=<N>

<original entry text verbatim>

---
```

The `> Source:` line is the restore anchor for `/sleep --restore`. Use `/sleep --restore <pattern>` to search `forgotten/` and move entries back to their source location.

## Session state: fallback_fires and end_of_day_due — verbose reference

The `end_of_day_due` field defaults to `yes` at every session-state write. `/end_of_day` Step 3d flips it to `no` for each session the hybrid selection rule produced (NOT only today's files — all files in the processed window that had `end_of_day_due: yes`, plus any orphan-recovery files confirmed in Step 0). The flip happens ONLY after the daily-cache write succeeds; a crashed `/end_of_day` run MUST NOT mark sessions as processed. `/start_of_day` reads this field (in addition to the existing insights-file check) as a second signal for the missing-EOD banner — if any session file written within the last 36 hours has `end_of_day_due: yes`, the banner fires.

**Orphaned sessions** (flag=no, never rolled up): If a session-state file already has `end_of_day_due: no` AND was never included in a daily-cache body (because `/end_of_day` ran after it was written and used the old `<today>-*.md` glob), that session is silently skipped by the normal hybrid rule — the existing `no` flag is treated as authoritative. Use `/end_of_day --recover-orphans` to surface these sessions. The subcommand partitions orphans into two groups by file date: RECENT (within last 7 days) and HISTORICAL (older). The user confirms each group separately. Orphan detection uses a word-boundary-aware slug match: a session is an orphan iff its task-name slug (post-date portion of filename) is absent from the body of every daily-cache file, using `r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])"` — hyphens count as part of the slug token so prefix collisions like `json-discovery-map` vs `json-discovery-map-review` do not produce false-positive coverage. Alternatively, manually flip any orphaned session's `end_of_day_due` field back to `yes` and re-run `/end_of_day`.

The `fallback_fires` field counts Class B writer Step 5 English-fallback invocations and Step 2 Haiku dispatch retries during this session. The active skill increments the field in place (atomic-rename pattern, mirror of end_of_day_due flip) immediately before emitting the `format-kit-skipped` warning. Default value is `0` at every session-state write; never decremented. KNOWN ISSUE: under parallel subagent fallback fires (rare; <1/day in practice given pre-Stage-4 finalized-artifact data), the read-modify-write update can undercount — it never overcounts. For low-frequency telemetry visibility this undercounting is acceptable; if a future post-merge measurement shows >5% undercounting, escalate to a per-skill append-only counter file (per Stage 4 D-03-rev2 option 3 — currently deferred).
