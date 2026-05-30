---
name: checkpoint
description: "General-purpose state-saving — save session-restore state mid-session before context exhaustion, between tasks, between sessions, or before starting new heavy work. Writes a pending-restore sentinel so a fresh session can resume exactly where you left off. Also surfaces pending-restore state on --restore. Use for: /checkpoint, 'save my place', 'checkpoint', 'save session', '/checkpoint --restore', 'restore checkpoint', 'resume from checkpoint'. Does NOT roll up dailies, does NOT touch lessons-learned.md or forgotten/."
model: haiku
---

# Checkpoint

You save session-restore state (paths-not-content) so a fresh session can resume after context compaction or voluntary save. You also provide `--restore` to re-hydrate that state in a new session.

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: haiku`. If the executing agent is running on a model
strictly more expensive than the declared tier, you MUST self-dispatch before doing the
skill's actual work.

Detection:
  - Read your current model from the system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus.
  - Sentinel parsing: the user's prompt is checked for the `[no-redispatch]` family.
      * Bare `[no-redispatch]` (parent-emit form AND user manual override): skip dispatch, proceed to §0c at the current tier.
      * Counter form `[no-redispatch:N]` where N is a positive integer ≥ 2: ABORT (see "Abort rule" below).
      * Counter form `[no-redispatch:1]` is reserved and treated as bare `[no-redispatch]` for forward-compatibility; do not emit it.
  - If current_tier > declared_tier AND prompt does NOT start with any `[no-redispatch]` form:
      Dispatch reason: cost-guardrail handoff. dispatched-tier: haiku.
      Spawn an Agent subagent with the following arguments:
        model: "haiku"
        description: "checkpoint dispatched at haiku tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in checkpoint. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §0c.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /checkpoint`).
  - This is the user-facing escape hatch. Both the parent-emit form and manual override share the same syntax — both want the same proceed-to-§0c outcome.
  - Use only when intentionally overriding the cost guardrail.

<!-- §0-worktree-fallback-begin -->
Fail-graceful path with error-class triage (per architecture I-01):
  - If the Agent tool returns an error during dispatch, classify the error
    message text BEFORE proceeding:

  - Error classification:
      * Worktree-class: the error text contains the substring
        `Cannot create agent worktree`, OR (the substring `worktree` AND
        the substring `not in a git repository`). This is recoverable —
        the harness tried to create a git worktree for isolation and the
        project root is not a git repo. Continue to Worktree-class branch.
      * Other-class: any other tool error, exception, or harness rejection
        — skip to Other-class path below (existing fail-OPEN behavior).

  - Worktree-class branch:
      Worktree creation is hook-driven and cannot be skipped by omitting a
      parameter. Use the AskUserQuestion tool to present the user with one
      option:
        (c) `proceed-current-tier` — Skip dispatch, proceed at the current
            (more expensive) tier. This is the only available recovery path.
      Question header: `Subagent dispatch failed (worktree creation). Proceeding at current tier.`
      Note for the user: "Worktree dispatch failed and no retry mechanism
      is available — worktree creation is unconditional in this harness.
      Proceeding at current tier."

  - Other-class path (also: worktree-class after user acknowledges c):
      Do NOT abort the user's invocation.
      Emit the bare warning (verbatim):
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
      If this path was reached via a worktree-class error, ALSO emit the
      classification line (second, separate):
        `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`
      Then proceed to §1 at the current tier (fail-OPEN per I-01).
<!-- §0-worktree-fallback-end -->
Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §0c.

## When to use

`/checkpoint` is a general-purpose state-save. Run it in any of these four cases:

1. **Mid-session before context exhaustion** — when the context-utilization advisory fires (`UserPromptSubmit` hook warns), save state so the next session can pick up from disk.
2. **Between tasks** — finished one task and starting another in the same session; checkpoint the prior task's in-flight state before pivoting.
3. **Between sessions** — closing a session with work still in flight; checkpoint so the next session can `/checkpoint --restore` and resume.
4. **Before starting new heavy work** — proactively save your current place before a long subagent run, large refactor, or multi-file edit that may pollute context.

`/checkpoint` does NOT promote insights to `lessons-learned.md`, does NOT roll up daily caches, and does NOT auto-invoke `/sleep`. For end-of-workday rollup (insight promotion + daily cache + `/sleep`), run `/end_of_day` instead.

## §0c Pidfile lifecycle (FIRST STEP after §0 dispatch)

At entry — immediately after §0 dispatch resolves:

```
. __QUOIN_HOME__/scripts/pidfile_helpers.sh && pidfile_acquire checkpoint
```

If the script is missing or fails (e.g., fresh install before Step 2b has run):
emit one-line warning `[quoin-S-2: pidfile helpers unavailable; proceeding without lifecycle protection]` and continue without abort (fail-OPEN).

At exit — call from every completion path AND every error/abort path:
```
pidfile_release checkpoint
```

Use a trap when the skill body involves bash-driven subagents:
```
trap 'pidfile_release checkpoint' EXIT
```

Purpose: lets `precompact.sh` hook know a `/checkpoint` session is active (for escalation from "block with warning" to "block with confidence").

## Save mode (default — no `--restore` argument)

Detect mode: if the user's invocation does NOT include `--restore`, run save mode.

**Arg parsing (first in save mode):** Scan the user's prompt for these flags:
- `--mode restore` | `--mode load-as-reference` | `--mode mid-agent` → sets SELECTED_MODE
- `--after-compact` → sets AFTER_COMPACT_FLAG_PRESENT=true (deprecated — see Step 0.5)
- If no `--mode` flag: SELECTED_MODE will be determined by auto-detection in Step 1.5

### Step 0.5: Post-compact flag (deprecated) and stale-marker cleanup

Detect flag: if the user's invocation includes `--after-compact`, set AFTER_COMPACT_FLAG_PRESENT=true.

If AFTER_COMPACT_FLAG_PRESENT is true:
  - Emit one-line INFO: `[checkpoint] --after-compact flag is deprecated as of this release; it now has no effect — compact-already-ran detection is automatic via the compact-happened sentinel. Proceeding to normal save.`
  - Trash-move any stale `checkpoint-pending-compact-${session_id}.txt` marker for cleanup (if it exists):
    ```sh
    _cwd=$(from stdin JSON .cwd field)
    _sid=$(current session UUID via Step 1.1 acquisition procedure)
    _stale="${_cwd}/.workflow_artifacts/memory/checkpoint-pending-compact-${_sid}.txt"
    [ -f "$_stale" ] && . __QUOIN_HOME__/hooks/_lib.sh && trash_move "$_stale" "${_cwd}/.workflow_artifacts/memory" 2>/dev/null || true
    ```
  - Do NOT stop or defer. Continue to Step 1.4.
  - Because AFTER_COMPACT_FLAG_PRESENT=true, the Step 1.4 explicit-flag guard fires and skips
    auto-detection — the save always runs.
  - At Step 5 (Report to user): append `Mode: --after-compact flag (deprecated; proceeded to normal save).`

If AFTER_COMPACT_FLAG_PRESENT is false (flag absent):
  - Proceed to Step 1.4.

Note: The exemption for /checkpoint from BLOCK_BPS context blocking is at
userpromptsubmit.sh lines 71-82. The --after-compact flag is retained for backward-compat
only; compact-already-ran detection is now automatic via the dual-sentinel check in Step 1.4.

### Step 1.4: Compact-already-ran skip check

(Conditional: SKIP this step entirely if SELECTED_MODE was explicitly passed via `--mode` OR if AFTER_COMPACT_FLAG_PRESENT=true. Proceed to Step 1.5.)

This step detects whether auto-compact already fired in this session AND wrote a precompact checkpoint. If so, the user's `/checkpoint` is redundant — the precompact hook already saved state.

**Session-id acquisition:** same procedure as Step 1.1.

```sh
_cwd=$(from stdin JSON .cwd field, same as Step 6 trash-move; NOT $(pwd))
_sid=$(current session UUID via Step 1.1 acquisition procedure)
```

If `_sid` is unavailable:
  - Emit WARNING: `[checkpoint] WARNING: session UUID unavailable for compact-happened check; skipping skip-path`
  - Proceed to Step 1.5.

```sh
_sentinel="${_cwd}/.workflow_artifacts/memory/compact-happened-${_sid}.txt"
_pending="${_cwd}/.workflow_artifacts/memory/pending-restore-${_sid}.txt"
```

**Dual-sentinel check:** BOTH `_sentinel` AND `_pending` must exist for the skip to fire.
- `compact-happened-*` alone (manual `/compact`) does NOT skip — user wants a real save; fall through to Step 1.5.
- `pending-restore-*` alone (no compact this session) does NOT skip — fall through to Step 1.5.

If `[ -f "$_sentinel" ] && [ -f "$_pending" ]`:
  - Read the checkpoint path from `_pending`:
    `_cp_path=$(head -1 "$_pending" 2>/dev/null)`
  - Inform user (verbatim):
    `[checkpoint] Auto-compact already ran in this session; precompact.sh wrote a checkpoint automatically. No additional /checkpoint needed. Auto-written checkpoint: ${_cp_path}`
  - Append cost-ledger row: `<uuid> | <date> | checkpoint | haiku | task | "skip (compact-already-ran)" | 0`
  - Release pidfile: `pidfile_release checkpoint`
  - STOP (do NOT proceed to Steps 1–6).

Otherwise (sentinel absent, or only `compact-happened-*` present): proceed to Step 1.45.

### Step 1.45: Panic/degraded save check

(Conditional: SKIP this step entirely if SELECTED_MODE was explicitly passed via `--mode` OR if AFTER_COMPACT_FLAG_PRESENT=true. Proceed directly to Step 1.5.)

This step detects whether the session is at or beyond the panic tier (≥ PANIC_BPS, default 10000 = 100.00%). At extreme utilization the heavy Step 1 gathering (UUID grep across sessions, multiple file reads, AskUserQuestion) may not complete before context exhaustion — as happened in the root-cause incident (115–127% utilization, 75s churn, no restore state saved). The panic path writes a minimal skeleton checkpoint + pending-restore sentinel using only cheap bash calls (git, find, printf) and STOPS immediately.

**PANIC_BPS tier:** `PANIC_BPS=${QUOIN_PANIC_BPS:-10000}`. Defined in `__QUOIN_HOME__/hooks/_lib.sh:read_constants()`. Tier ordering: `COMPACT_FIRST_BPS` (9000 = 90.00%, notice-only) < `PANIC_BPS` (10000 = 100.00%, degrade-to-minimal-save). Source and read constants:
```sh
. __QUOIN_HOME__/hooks/_lib.sh && read_constants && compute_utilization TRANSCRIPT_PATH
```
(same call already used in Step 1.5 sub-step A).

**Util-read failure contract:** If `compute_utilization` returns empty or non-numeric (e.g., `TRANSCRIPT_PATH` unavailable), the panic check MUST NOT error out:
```sh
if [ -z "$util_bps" ] || ! printf '%d' "$util_bps" >/dev/null 2>&1; then
  util_bps=0   # fail-safe: fall through to Step 1.5 (no crash)
fi
```
The hook forced-save (userpromptsubmit.sh STEP C2) is the independent backstop when both util-read and the normal skill save path are unavailable.

**If `util_bps >= PANIC_BPS`:** Skip ALL of: Step 1 deep gathering, mid-agent check, AskUserQuestion mode selection. Write a minimal skeleton checkpoint and pending-restore sentinel using only cheap operations:

1. **Session ID:** harness-provided context UUID; else newest `~/.claude/projects/<project-hash>/<uuid>.jsonl` filename stem (Step 1.1 acquisition — cheap stem only, no grep across session files).
2. **Task:** filename-derived from newest `<cwd>/.workflow_artifacts/memory/sessions/*.md` (strip `YYYY-MM-DD-` date prefix, strip `.md` suffix).
3. **Branch:** `git -C "$cwd" rev-parse --abbrev-ref HEAD` (|| `unknown`).
4. **In-flight paths:** `find "${cwd}/.workflow_artifacts" -name current-plan.md -exec ls -t {} + 2>/dev/null | head -1` (same for `architecture.md`).
5. Write skeleton checkpoint to `<cwd>/.workflow_artifacts/memory/checkpoints/<YYYY-MM-DD>T<HHMM>-<task>.md` (standard timestamped form). Use the same section set as the STEP C2 hook skeleton: `## Status`, `## Current stage`, `## Active task`, `## Branch`, `## Session ID`, `## Saved at`, `## In-flight artifacts`, `## Restore hint`.
6. Write `<cwd>/.workflow_artifacts/memory/pending-restore-<sid>.txt` containing the skeleton path on line 1.
7. Append cost-ledger row: `<uuid> | <date> | checkpoint | haiku | task | "save (panic mode)" | 0`
8. Release pidfile: `pidfile_release checkpoint`
9. Report:
   ```
   [checkpoint] PANIC tier (util >= 100%): context too full for full save. Minimal restore state saved.
   Checkpoint: <path>
   Sentinel: pending-restore-<sid>.txt
   Start a fresh session and run /checkpoint --restore to resume.
   ```
10. **STOP.** Do NOT proceed to Step 1.5 / Step 1 / Step 2 / normal save flow.

**If `util_bps < PANIC_BPS`:** Proceed to Step 1.5 (normal flow; existing COMPACT_FIRST_BPS high-util notice applies there).

### Step 1.5: Orchestrate mode (auto-detect if --mode not explicitly given)

This step determines which sentinel to write (restore, load-as-reference, or mid-agent).
If `--mode` was explicitly passed, skip auto-detection and go to the dispatch at the end.

**Auto-detection sequence (only when SELECTED_MODE is unset):**

**A. High-util check (inverted):** Read the current utilization. Invoke via Bash tool:
```sh
. __QUOIN_HOME__/hooks/_lib.sh && read_constants && compute_utilization TRANSCRIPT_PATH
```
Where `TRANSCRIPT_PATH` is the current session's JSONL path (obtain from the harness
system context, or from `~/.claude/projects/<project-hash>/<uuid>.jsonl`).

Compare the returned basis-point integer against `COMPACT_FIRST_BPS` (default 9000 = 90.00%).
This constant is defined in `_lib.sh:read_constants()` as:
  `COMPACT_FIRST_BPS=${QUOIN_COMPACT_FIRST_BPS:-9000}`

If `util_bps >= COMPACT_FIRST_BPS`:
  - Set `_HIGH_UTIL_NOTICE=true`.
  - Compute `PCT_VALUE` from `util_bps` (e.g., "92.13" for 9213 basis points):
    `pct_int=$((util_bps / 100)); pct_dec=$(printf '%02d' $((util_bps % 100))); PCT_VALUE="${pct_int}.${pct_dec}"`
  - Continue to sub-step B. (Do NOT write a deferred-checkpoint marker. The save runs immediately
    in Steps 1–6; the high-util notice is surfaced in Step 5 only.)

If `util_bps < COMPACT_FIRST_BPS` OR if the compact-first check fails (e.g., transcript
path unavailable):
  - Set `_HIGH_UTIL_NOTICE=false`.
  - Continue to sub-step B.

**B. Mid-agent check:** Detect whether other skills are currently active (pidfiles present).
Invoke via Bash tool:
```sh
. __QUOIN_HOME__/scripts/pidfile_helpers.sh && pidfile_active_skills | awk -v me=$$ '$2 != me'
```
(Filter by PID `$$` — excludes this /checkpoint invocation's own pidfile only.)

If the output is non-empty (other skills are running):
  - Set SELECTED_MODE="mid-agent" (ask user to confirm via AskUserQuestion):
    ```
    AskUserQuestion(
      question="Active skills detected: SKILL_LIST. Save in mid-agent mode (minimal sentinel only)?",
      options=[
        {label: "Yes, save mid-agent", description: "Save a minimal sentinel; other skills are still running."},
        {label: "Choose different mode", description: "Pick restore or load-as-reference instead."}
      ]
    )
    ```
  - On "Choose different mode": fall through to sub-step C below.
  - On "Yes, save mid-agent": proceed with SELECTED_MODE="mid-agent".

**C. User choice:** If no mid-agent detection:
  - If invoked with a clear user intent from the prompt (e.g., "checkpoint for reference"),
    pick the matching mode.
  - Otherwise: use AskUserQuestion to ask the user to choose (default: restore):
    ```
    AskUserQuestion(
      question="How would you like to save this checkpoint?",
      options=[
        {label: "Restore", description: "Resume this exact session later."},
        {label: "Load as reference", description: "Open as read-only background in a new session."}
      ]
    )
    ```
  - Set SELECTED_MODE accordingly.

**Dispatch:** based on SELECTED_MODE:
- `restore` → proceed to Step 1 (full save), then Step 3 → Step 4a
- `load-as-reference` → proceed to Step 1 (full save), then skip Step 3 → Step 4b
- `mid-agent` → SKIP Steps 1 and 2, proceed directly to Step 4c

### Step 1: Gather session context

(Conditional: SKIP this step if SELECTED_MODE is "mid-agent")

Read the following sources (best-effort; skip gracefully if any file is absent):

Read the following sources (best-effort; skip gracefully if any file is absent):

1. **Session state file** — use UUID-anchored lookup (procedure below); fall back to mtime if UUID unavailable or unmatched. Extract:
   - Active task name (from filename pattern `YYYY-MM-DD-<task-name>.md` — strip the date prefix)
   - Current phase (from `## Cost` block → `Phase:` line)
   - Open questions (from `## Open questions` block)
   - Decisions made this session (from `## Decisions made` block, if present)
   - Unfinished work list (from `## Unfinished work` block)

   **UUID-anchored session-state lookup (Step 1.1):**
   (a) Obtain the current session UUID. Priority: harness-provided system context UUID; else most recently modified `~/.claude/projects/<project-hash>/<uuid>.jsonl` filename stem (same rule used for cost-ledger UUID acquisition). `<project-hash>` = project path with `/` replaced by `-`.
   (b) If a UUID is obtained, grep `.workflow_artifacts/memory/sessions/*.md` for the UUID. Use `grep -iE` (case-insensitive on the full pattern) because the live tree has both uppercase and lowercase UUID values. Pattern: `grep -iE "^([[:space:]]*-[[:space:]]*)?(Session UUID:[[:space:]]*)${session_id}"`. The session-state file template uses the bulleted form `- Session UUID: <UUID>` — the pattern must match both `Session UUID:` and `- Session UUID:` prefixes.
   (c) If exactly one match is found: use that file. Tag with INFO line `[checkpoint] session-state located by UUID anchor: <path>`.
   (d) If zero matches AND a UUID was obtained: emit one-line WARNING `[checkpoint] WARNING: no session-state file contains Session UUID '<UUID>'; falling back to mtime ordering`; then fall back to `ls -t` most-recently-modified.
   (e) If the UUID itself could not be obtained: skip the grep entirely; fall back to mtime ordering (current behavior). Tag with WARNING line `[checkpoint] WARNING: session UUID unavailable; using mtime fallback`.
   (f) If two or more matches are found (rare; concurrent session-state files for the same UUID): pick the most recent by mtime among the matches and emit one-line WARNING `[checkpoint] WARNING: multiple session-state files match UUID '<UUID>'; picked '<path>' by mtime`.

2. **Git branch** — `git rev-parse --abbrev-ref HEAD` in cwd. On failure, use `unknown`.

3. **Last user intent** — short restatement from the user at `/checkpoint` invocation time (extract from the user's prompt if they provided a note, or from the session-state `## Unfinished work` block if empty).

4. **In-flight artifact paths** — enumerate these (do NOT read their contents — paths-not-content rule D-04):
   - Most recent `current-plan.md` under `.workflow_artifacts/`
   - Most recent `architecture.md` under `.workflow_artifacts/`
   - Most recent `critic-response-N.md` under `.workflow_artifacts/` (highest N)
   - Most recent `review-N.md` under `.workflow_artifacts/` (highest N)
   - Active session-state file path

### Step 1.6: Append to recent-sessions.md

(Conditional: SKIP this step if SELECTED_MODE is "mid-agent")

Before writing the checkpoint file, append one record to
`<cwd>/.workflow_artifacts/memory/recent-sessions.md` (fail-OPEN — skip on any error).
Create the `memory/` directory if absent (the `checkpoints/` subdirectory is created in Step 2,
not `memory/`; this step must create `memory/` itself on first use).
Use the Bash tool:

```sh
_rs_now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
_rs_sid="<session_uuid from Step 1.1>"
_rs_cwd="<cwd — use .cwd from stdin JSON, not $(pwd)>"
mkdir -p "${_rs_cwd}/.workflow_artifacts/memory" 2>/dev/null || true
printf '%s | %s\n' "$_rs_now" "$_rs_sid" \
  >> "${_rs_cwd}/.workflow_artifacts/memory/recent-sessions.md" 2>/dev/null || true
```

### Step 2: Write checkpoint file

(Conditional: SKIP this step if SELECTED_MODE is "mid-agent". In mid-agent mode, no full checkpoint file is written — only the minimal sentinel in Step 4c.)

Write to: `.workflow_artifacts/memory/checkpoints/<YYYY-MM-DD>T<HHMM>-<task-name>.md`

Where `<YYYY-MM-DD>` is `$(date -u +%Y-%m-%d)` and `<HHMM>` is `$(date -u +%H%M)` (UTC wall-clock, e.g. `1423` for 14:23 UTC). Both timestamps must come from the same `date -u` invocation epoch to prevent date/time rollover skew at midnight UTC — use `_now=$(date -u +%Y-%m-%dT%H%M); _fname="${_now}-${task_name}.md"`.

Filename-collision note: two voluntary saves within the same UTC minute would overwrite. Accepted as theoretical given checkpoint save frequency (manual, infrequent) — do not engineer around this.

Create the `checkpoints/` directory if absent (best-effort; fail-OPEN on mkdir failure).

Checkpoint format (Class A artifact — plain sections, no `## For human` block):

```markdown
## Status
checkpoint save (voluntary)

## Current stage
<phase from session-state, e.g., "implement">

## Active task
<task-name>

## Branch
<git branch>

## Session ID
<session UUID from Step 1.1, or "unknown" if unavailable>

## Session link
- Resume: claude --resume <session_uuid>
- JSONL: ~/.claude/projects/<project-hash>/<session_uuid>.jsonl

## Last user intent
<one-sentence restatement of what the user was working on>

## In-flight artifacts
- current-plan.md: <path or "(none found)">
- architecture.md: <path or "(none found)">
- latest critic-response: <path or "(none found)">
- latest review: <path or "(none found)">
- session-state: <path or "(none found)">
- session-state-resolution: <uuid-anchor | mtime-fallback>

## Open questions
<content from session-state ## Open questions, or "(none)">

## Decisions made
<content from session-state ## Decisions made, or "(none)">

## Unfinished work
<content from session-state ## Unfinished work, or "(none)">

## Restore hint
Run /checkpoint --restore in a fresh session to resume task '<task-name>' from branch '<branch>'.
```

**`## Session link` field derivation:**
- `<session_uuid>` is the same value written to `## Session ID` (from Step 1.1 acquisition procedure).
- `<project-hash>` is the project's absolute path with `/` replaced by `-` (matches the cost-ledger JSONL-lookup convention used elsewhere in this skill). Compute: `_project_hash=$(printf '%s' "$_cwd" | tr '/' '-')` where `_cwd` is from stdin JSON `.cwd`.
- If `<session_uuid>` is `unknown` (UUID could not be acquired), write the section with both lines literally as `- Resume: (session UUID unavailable)` and `- JSONL: (session UUID unavailable)` rather than omitting the section — keeps parser shape stable.

**Paths-not-content rule (D-04):** NEVER carry the actual file contents into the checkpoint. Only paths. Restore re-fires the Read tool on disk artifacts in the new session.

**Soft size cap:** If the written checkpoint file is larger than 4 KB, emit one-line stderr warning:
`[quoin checkpoint] WARNING: checkpoint file <PATH> exceeds 4 KB soft cap (<N> bytes) — paths-not-content rule may be violated; check for accidentally-included content.`
Continue; do NOT abort.

### Step 3: Write pending-restore sentinel

(Conditional: run ONLY for SELECTED_MODE="restore". In "load-as-reference" mode, SKIP Step 3 and proceed to Step 4b. In "mid-agent" mode, Steps 1, 2, and 3 are all skipped.)

Write the checkpoint file path (single line) to:
`.workflow_artifacts/memory/pending-restore-${session_id}.txt`

Where `session_id` is the current session's UUID (read from the session-state `## Cost` block → `Session UUID:` line, or from the harness system context if available).

If session_id cannot be determined: emit warning and skip sentinel write (checkpoint file still kept).

The `sessionstart.sh` hook surfaces this sentinel on next session start.

### Step 4: Append cost-ledger row

Append a row to `.workflow_artifacts/<task-name>/cost-ledger.md`.
Include a mode tag in the NOTE column:
- "save (restore mode)"
- "save (load-as-reference mode)"
- "save (mid-agent mode)"

```
<uuid> | <date> | checkpoint | haiku | task | save (MODE mode) | 0
```

UUID: read the most-recently-modified `~/.claude/projects/<project-hash>/<uuid>.jsonl`.
The ledger row is written ONCE — either by the Haiku-dispatched subagent (§0 dispatch path) OR by the parent (if already at Haiku tier). Never by both.

### Step 4a: Restore mode sentinel

(Run only when SELECTED_MODE="restore")

The pending-restore sentinel was written in Step 3. No additional sentinel is needed.

Step 5 report mentions:
- "Sentinel written: pending-restore-SESSION_ID.txt"
- "To resume: /checkpoint --restore in a fresh session"

### Step 4b: Load-as-reference mode sentinel

(Run only when SELECTED_MODE="load-as-reference")

Write a reference sentinel file at:
`.workflow_artifacts/memory/pending-resume-ref-${session_id}.txt`

Content (two lines):
```
prior_session_uuid=SESSION_ID
checkpoint_path=CHECKPOINT_FILE_PATH
```

Where SESSION_ID is the current session's UUID and CHECKPOINT_FILE_PATH is the path
written in Step 2.

Step 5 report says:
"Reference sentinel written: pending-resume-ref-SESSION_ID.txt
Start a new session with: claude --resume SESSION_ID --fork-session
The new session will load this session as background context; sessionstart.sh will
emit a banner informing you of the reference checkpoint."

Note: Session-state file IS written in load-as-reference mode (Step 1+2 ran normally).
The user's prior session content is available as background reference in the forked session.

### Step 4c: Mid-agent mode sentinel

(Run only when SELECTED_MODE="mid-agent". Steps 1, 2, 3, 4b are all skipped.)

Write a minimal handoff sentinel at:
`.workflow_artifacts/memory/mid-agent-handoff-${session_id}.txt`

Content:
```
prior_session_uuid=SESSION_ID
task_name=TASK_NAME
active_skills=SKILL_LIST
timestamp=ISO_TIMESTAMP
```

Where:
- SESSION_ID is the current session's UUID
- TASK_NAME is extracted from the most-recent session-state filename (best-effort; "unknown" if unavailable)
- SKILL_LIST is the output of:
  `. __QUOIN_HOME__/scripts/pidfile_helpers.sh && pidfile_active_skills | awk -v me=$$ '$2 != me'`
  (filtered to exclude this /checkpoint invocation's own PID)
- ISO_TIMESTAMP is `$(date -u +%Y-%m-%dT%H:%M:%SZ)`

Do NOT write the full Step 2 checkpoint file. Rationale: a heavy skill is running; reading
session-state, plan, architecture, and critic files could itself fail or take too long.
The mid-agent path is intentionally minimal.

Note: Session-state file is NOT touched in mid-agent mode (intentional — a skill is in
flight; modifying its session-state file would race with the running skill).

Step 5 report says:
"Mid-agent handoff sentinel written: mid-agent-handoff-SESSION_ID.txt
Active skills at save time: SKILL_LIST

To resume this session:
Option 1: Type /clear to reset context in this same session, then run
  /checkpoint --restore to reload the mid-agent handoff.
Option 2: Start a new terminal session with: claude --resume SESSION_ID
  Then run /checkpoint --restore in that session."

### Step 5: Report to user

Print a brief confirmation. Content depends on SELECTED_MODE (see Steps 4a, 4b, 4c for
the mode-specific report text). Always include:
- Checkpoint saved to: `<path>` (or "(no checkpoint file — mid-agent mode)" for mid-agent)
- Mode: `<restore | load-as-reference | mid-agent>`
- Sentinel written: `<sentinel-path>`
- Next step instruction (mode-specific — see Steps 4a, 4b, 4c above)

If `_HIGH_UTIL_NOTICE=true`, append after the normal confirmation:
```
Context is at ${PCT_VALUE}% (>= COMPACT_FIRST_BPS=90.00%). Checkpoint saved. To free context, choose one:
  1. Start a fresh session (run /checkpoint --restore there).
  2. Run /compact in this session (the auto-written precompact checkpoint will subsume this save; you do not need to re-run /checkpoint after).
```

### Step 6: Release pidfile and invalidate defer marker

Release the pidfile:
```
pidfile_release checkpoint
```

Trash-move the defer marker for the current session_id (if it exists) — a successful voluntary save invalidates any pending defer:
```sh
_defer="${cwd}/.workflow_artifacts/memory/checkpoint-defer-${session_id}.txt"
[ -f "$_defer" ] && trash_move "$_defer" "${cwd}/.workflow_artifacts/memory" 2>/dev/null || true
```
Note: `${cwd}` is from stdin JSON `.cwd` (NOT `$(pwd)` — the shell's current directory can diverge if a tool ran `cd` earlier).

## Defer mode (`--defer` argument present)

Detect mode: if the user's invocation includes `--defer`, run defer mode.

**session_id acquisition** (same procedure as Save mode Step 1.1): priority is harness-provided system context UUID; else most recently modified `~/.claude/projects/<project-hash>/<uuid>.jsonl` filename stem. Case is preserved verbatim.

**Write a defer marker file:**
`.workflow_artifacts/memory/checkpoint-defer-${session_id}.txt`
containing a single line — the ISO-8601 UTC timestamp of when defer was set.

This marker is consumed by `userpromptsubmit.sh` STEP 3 advisory branch: when the marker is present for the current session_id, the advisory is suppressed (no "context at X%" advisory emitted).

The marker is automatically expired on:
- Post-compact (via `userpromptsubmit.sh` STEP 0.5 trash-move alongside the postcompact-reset sentinel)
- Successful voluntary `/checkpoint` save (via Save mode Step 6 above)

**Exit code:** 0.

**Print:** `[checkpoint] defer marker written; userpromptsubmit advisory suppressed until next compact or voluntary save.`

## Restore mode (`--restore` argument present)

Detect mode: if the user's invocation includes `--restore`, run restore mode.

### Step 1: Locate checkpoint

Use a unified picker that covers both pending-restore sentinels and recent checkpoint files on disk.

**Step 1.0 — Anchor selection (priority order)**

Before enumerating disk checkpoints, attempt to resolve a restore anchor from higher-priority signals. Proceed through tiers in order; stop at the first anchor found.

**Tier 1 — Fast path (current-session sentinel, sub-second):** check for `pending-restore-${current_session_id}.txt`. If it exists and its checkpoint path is valid: return that checkpoint immediately (skip all enumeration).

**Tier 2 — Pending-prompt cross-reference (fix #5):** when the fast path misses (fresh session: current_session_id has no pending-restore), enumerate ALL in-window `pending-prompt-<SID>.txt` sentinels. This automates the manual "look into pending prompts to find today's real session" recovery.

```sh
_w="${QUOIN_RESTORE_SENTINEL_WINDOW:-7}"
_mem_dir="${cwd}/.workflow_artifacts/memory"   # cwd-from-stdin, NOT bare 'memory'
_anchor=""
_anchor_task=""
# Iterate in mtime-descending order so the freshest pending-prompt is tried first
for pp in $(find "$_mem_dir" -maxdepth 1 -name 'pending-prompt-*.txt' \
              -mtime -"${_w}" -print0 2>/dev/null \
            | xargs -0 ls -t 2>/dev/null); do
  sid=$(basename "$pp" | sed 's/^pending-prompt-//; s/\.txt$//')
  _pr_candidate="${_mem_dir}/pending-restore-${sid}.txt"
  if [ -f "$_pr_candidate" ]; then
    _cp_candidate=$(head -1 "$_pr_candidate" 2>/dev/null)
    if [ -n "$_cp_candidate" ] && [ -f "$_cp_candidate" ]; then
      _anchor="$_cp_candidate"          # strongest: both hook sentinels present for this SID
      consumed_sentinel_path="$_pr_candidate"
      break
    fi
  fi
  # No pending-restore for this SID; extract task name from session-state to seed
  # the tier-3 cross-task guard (T-04) even when no pending-restore exists.
  # Use the existing Step 1.1 Session UUID grep to associate SID → session-state file:
  _implied_ss=$(grep -iEl "^([[:space:]]*-[[:space:]]*)?(Session UUID:[[:space:]]*)${sid}" \
                  "$_mem_dir/sessions/"*.md 2>/dev/null | head -1)
  if [ -z "$_implied_ss" ]; then
    # Fallback: most-recently-modified session-state file (mtime heuristic)
    _implied_ss=$(ls -t "$_mem_dir/sessions/"*.md 2>/dev/null | head -1)
  fi
  if [ -n "$_implied_ss" ] && [ -z "$_anchor_task" ]; then
    _basename=$(basename "$_implied_ss" .md)
    _anchor_task="${_basename#????-??-??-}"   # strip YYYY-MM-DD- date prefix
  fi
  # Do NOT break — keep scanning for a stronger (anchor) candidate
done
```

Explicit fallthrough behavior:
- `_anchor` set → present it (skip to Step 2).
- `_anchor` not set but `_anchor_task` set → feed `_anchor_task` to tier-3 freshest_task override; proceed to tier-3 full enumeration.
- Neither set → fall through to tier-3 full enumeration (no silent failure; the combined gate at auto-pick applies).

**Tier 3 — Full enumeration with combined gate:** standard B1 sentinel + 30d checkpoint scan below, with the cross-task + staleness combined gate applied at auto-pick (D-03). See "Normal picker" and "Combined auto-pick gate" below.

**Tier 4 — B3 session-state synthesis:** fires when tier-3 auto-pick is suppressed or candidate_count == 0. See "B3 session-state fallback" below.

---

**Fast path (sub-second, bypass all enumeration):**
Before building the candidate list, check for a current-session sentinel:
```
if exists pending-restore-${current_session_id}.txt:
  read its single-line content (cp_path)
  verify cp_path exists; if yes: return cp_path immediately (skip enumeration entirely)
```
`current_session_id` is obtained via the same UUID-acquisition procedure as Step 1.1 (harness-provided UUID; else most recently modified JSONL filename stem).

**Full enumeration path** (fires only when fast path finds nothing):

Initialize at picker entry (BEFORE all 6 picker paths below — defeats shell-variable carry-over from any prior iteration):
```
consumed_sentinel_path=""
```

1. Build a candidate list from two sources, de-duplicated by checkpoint-file path:
   - **All sentinels (B1 — mtime-filtered):** Use `find` with the `QUOIN_RESTORE_SENTINEL_WINDOW` env knob (default **7** days — narrows the long tail of orphaned sentinels; asymmetric with checkpoint-enum's 30d is INTENTIONAL: sentinels are transient pointers, not durable artifacts):
     ```sh
     _window="${QUOIN_RESTORE_SENTINEL_WINDOW:-7}"
     _sentinel_dir=".workflow_artifacts/memory"
     _total=$(find "$_sentinel_dir" -maxdepth 1 -name 'pending-restore-*.txt' | wc -l | tr -d ' ')
     find "$_sentinel_dir" -maxdepth 1 -name 'pending-restore-*.txt' \
       -mtime -"${_window}" -print0 \
       | while IFS= read -r -d '' f; do
           # each $f is a valid within-window sentinel; add to candidate list
           echo "$f"
         done
     _stale_count=$(( _total - candidate_sentinel_count ))
     if [ "$_stale_count" -gt 0 ]; then
       echo "[checkpoint] ${_stale_count} stale pending-restore-*.txt sentinels older than ${_window}d skipped"
     fi
     ```
     Each within-window sentinel contains a checkpoint path on line 1. Set `consumed_sentinel_path` to the absolute path of the chosen sentinel when the picker selects a sentinel-backed entry (see 6-path contract below).
   - **All checkpoints (30-day window):** use `find .../checkpoints/ -maxdepth 1 -name '*.md' ! -name '*.tmp' -mtime -30 -print0 | while IFS= read -r -d '' cp; do ...` (null-delimited, space-safe for Google Drive paths with spaces). Skip any file whose byte-size < 100 bytes: `[ $(wc -c < "$cp") -ge 100 ] || continue`. This guards against 0-byte corrupt entries.

   **`consumed_sentinel_path` 6-path contract** (implementer reference — ALWAYS initialize to `""` at picker entry):

   | # | Picker path | `consumed_sentinel_path` value |
   |---|-------------|-------------------------------|
   | 1 | Fast-path (current-session sentinel return) | `""` (empty) — current-session cleanup at Step 5 covers it |
   | 2 | Zero-candidates fall-through | `""` (empty) — no candidate, Step 5 unchanged |
   | 3 | Auto-pick (exactly-1 candidate), source=sentinel | absolute path of the chosen sentinel file |
   | 3a | Auto-pick (exactly-1 candidate), source=disk-only | `""` (empty) — no sentinel consumed |
   | 4 | Numbered picker, picked entry source=sentinel | absolute path of the chosen sentinel file |
   | 4a | Numbered picker, picked entry source=disk-only | `""` (empty) — no sentinel consumed |
   | 5 | B3 session-state fallback synthesis | `""` (empty) — no sentinel consumed |
   | 6 | Step-2 corrupt-file branch (read fails) | `""` (empty) — graceful surface (prints raw contents + "Manual recovery" prompt); Step 5 may still fire for current-session cleanup, which is safe because empty `consumed_sentinel_path` triggers only the existing cleanup path |

2. Annotate each candidate: task name (from `## Active task`), branch (from `## Branch`), saved-time (from filename prefix — see below), source (`sentinel` or `disk-only`). Awk extraction: `awk '/^## Active task[[:space:]]*$/{getline; gsub(/\r$/,""); print; exit}'` — strips trailing CR and handles value-on-next-line form. If `## Active task` cannot be extracted (parse failure), drop the candidate silently.

   **Saved-time extraction (handles both filename shapes):**
   - **Timestamped (new):** `<YYYY-MM-DD>T<HHMM>-<task-name>.md` → display as `YYYY-MM-DD HH:MM UTC` (insert colon between HH and MM).
   - **Legacy non-timestamped:** `<YYYY-MM-DD>-<task-name>.md` (no `T<HHMM>` between date and task name) → display as `YYYY-MM-DD (legacy)`.
   - **Precompact:** `<YYYY-MM-DD>-<task-name>-precompact.md` → display as `YYYY-MM-DD (precompact)`.

   Detection regex (POSIX bash): a basename matches the new form iff it matches `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-`. Otherwise treat as legacy. The `-precompact` suffix is orthogonal and detected separately on the basename before extension stripping.

3. De-duplication: prefer the non-`-precompact` file over the `-precompact` file when one filename equals the other minus `-precompact.md` AND their mtimes are within `${QUOIN_PICKER_DEDUP_WINDOW:-7d}` (7 days) of each other. Pairs older than 7 days apart are treated as independent entries. **Note on timestamped voluntary saves:** with the `<YYYY-MM-DD>T<HHMM>-<task>.md` format introduced for voluntary saves, this filename-equality match will no longer fire against precompact files written the same date (precompact files retain the legacy `<YYYY-MM-DD>-<task>-precompact.md` shape). The dedup rule remains in force to handle older non-timestamped voluntary checkpoints still on disk (pre-migration files); it is effectively a no-op for new files.

4. Backward-compat reader: tolerate missing `## Session ID` (older voluntary checkpoints). When absent, display `(legacy)` in the picker source column.

5. Auto-pick rules:

   After applying the B1 mtime filter, check the B3 session-state fallback trigger (two-clause OR):
   - **Clause A:** `candidate_count == 0` (zero candidates after B1 filter AND checkpoint enum).
   - **Clause B:** `candidate_count > 0` AND `max(ALL candidate mtimes) < max(sessions/*.md mtime within ${QUOIN_SESSION_FALLBACK_WINDOW:-7}d)`.
     Clause B is the same-day-symptom mitigation: when ALL candidates (both sentinel-backed and disk-only) are older than the user's freshest session-state file, that session-state file is a more relevant resume anchor. Using `max(ALL candidate mtimes)` prevents fresh disk-only checkpoints from being unfairly skipped when no sentinel file exists.
     Note: the B3 trigger (Clause A or B) is evaluated BEFORE the Normal picker's auto-pick step. The cross-task identity guard and staleness guard (see "Combined auto-pick gate" below) are SECOND, INDEPENDENT safety nets that apply within the Normal picker when B3 does not trigger. Together these two layers catch the incident scenario: a stale cross-task checkpoint auto-picked when Clause B did not fire because the candidate mtime appeared fresher than the sessions mtime (e.g., due to a timestamp bump or wrong cwd in the sessions lookup).

   **B3 trigger fires if EITHER clause holds** — see "B3 session-state fallback" below. If the trigger does NOT fire (candidate_count > 0 AND sessions are not fresher than candidates), proceed with the normal picker below.

   **Normal picker (when B3 does not fire):**
   - **Zero candidates:** fall through to Step 3 (graceful error message: no checkpoints found).
   - **Exactly 1 candidate:** apply the combined auto-pick gate (see "Combined auto-pick gate" below) BEFORE silently auto-picking. If the gate suppresses auto-pick, route to B3 synthesis. Otherwise auto-pick with session-id mismatch warning. Set `consumed_sentinel_path` to the sentinel path if source=sentinel; else leave `""`.
   - **Two or more:** present the numbered picker:
     ```
     Multiple recent checkpoints found. Which session do you want to restore?
       1. * Task: TASK_1  Branch: BRANCH_1  Saved: DATETIME_1  (sentinel)
       2.   Task: TASK_2  Branch: BRANCH_2  Saved: DATETIME_2  (disk-only)
       ...
     Enter number, or 'skip' to proceed to direct checkpoint lookup:
     ```
     Where `DATETIME_N` is the saved-time value derived per the filename-shape detection above (`YYYY-MM-DD HH:MM UTC`, `YYYY-MM-DD (legacy)`, or `YYYY-MM-DD (precompact)`).
     `*` marks sentinel-backed entries. Cap at 10 items (mtime descending). If more: `... and <N> older. Use --defer to skip.`
     - On a valid number: use that entry's checkpoint file. Apply the combined auto-pick gate before presenting (annotate the mismatch in the numbered list display; the user's explicit selection overrides the gate — they may still choose any entry). Set `consumed_sentinel_path` to the sentinel path if the chosen entry's source=sentinel; else leave `""`.
     - On `skip`: fall through to Step 3.
     - On invalid input: re-prompt once; on second invalid input, fall through to Step 3.

   **Combined auto-pick gate (D-03 — T-04 cross-task + T-05 staleness):**

   Before silently auto-picking a single candidate (or when annotating the numbered picker), apply both guards with OR semantics. A candidate is silently auto-picked ONLY IF it passes BOTH checks:

   ```sh
   # Resolve freshest_task: use tier-2 seed if available, else derive from freshest session-state
   freshest_ss=$(ls -t "${_mem_dir}/sessions/"*.md 2>/dev/null | head -1)
   freshest_task="${_anchor_task}"   # from tier-2 pending-prompt cross-ref (may be "")
   if [ -z "$freshest_task" ] && [ -n "$freshest_ss" ]; then
     _fs_basename=$(basename "$freshest_ss" .md)
     freshest_task="${_fs_basename#????-??-??-}"
   fi

   cand_task=$(awk '/^## Active task[[:space:]]*$/{getline; gsub(/\r$/,""); print; exit}' "$cand_cp_file")
   cand_age_days=$(python3 -c "
   import os, datetime, sys
   f = sys.argv[1]
   mtime = os.path.getmtime(f)
   age = (datetime.datetime.now().timestamp() - mtime) / 86400
   print(int(age))
   " "$cand_cp_file" 2>/dev/null || echo 999)

   _stale_days="${QUOIN_RESTORE_STALE_DAYS:-1}"
   stale=0
   cross_task=0
   [ -n "$freshest_ss" ] && [ "$cand_age_days" -gt "$_stale_days" ] && stale=1
   [ -n "$freshest_task" ] && [ "$cand_task" != "$freshest_task" ] && cross_task=1

   if [ "$stale" -eq 1 ] || [ "$cross_task" -eq 1 ]; then
     # LOUD WARNING — do NOT silently auto-pick
     echo "[checkpoint] WARNING: auto-pick suppressed."
     [ "$stale" -eq 1 ]      && echo "  Stale: candidate is ${cand_age_days}d old (threshold: ${_stale_days}d)."
     [ "$cross_task" -eq 1 ] && echo "  Cross-task: candidate task='${cand_task}' vs freshest session task='${freshest_task}'."
     echo "  Routing to session-state synthesis (B3). Run /checkpoint --restore and choose 'y' to synthesize from the freshest session-state."
     # Route to B3 session-state synthesis (same as Clause A/B trigger)
     <invoke B3 session-state fallback>
   else
     # Guards passed — silent auto-pick (current behavior)
     <auto-pick the candidate>
   fi
   ```

   **Key guarantee:** a candidate is suppressed (stale=1 OR cross_task=1) when EITHER condition holds. This prevents the incident scenario (5-day-old pep-mvp checkpoint auto-picked instead of today's dgp-price-interactions session) even when B3 Clause B does not fire. The `test_checkpoint_picker_incident_repro.py` test verifies this gate cannot be silently inverted.

   **B3 session-state fallback (fires when trigger is true — BEFORE Step 3 graceful-error path):**

   Enumerate recent session-state files:
   ```sh
   _fb_window="${QUOIN_SESSION_FALLBACK_WINDOW:-7}"
   _sessions_dir=".workflow_artifacts/memory/sessions"
   ```
   Use portable mtime (Python first, then `stat` fallbacks — mirrors `sessionstart.sh:39-41`):
   ```sh
   _get_mtime() {
     python3 -c "import os; print(int(os.path.getmtime('$1')))" 2>/dev/null \
       || stat -f '%m' "$1" 2>/dev/null \
       || stat -c '%Y' "$1" 2>/dev/null \
       || echo 0
   }
   ```
   ```sh
   _most_recent=$(find "$_sessions_dir" -maxdepth 1 -name '*.md' \
     -mtime -"${_fb_window}" -print0 \
     | xargs -0 ls -t 2>/dev/null | head -1)
   ```
   If no session-state file found: fall through to existing Step 3 graceful "no checkpoints found" path.

   Extract fields (REVISED: derive `active_task` from FILENAME — `## Active task` heading exists in only 2/46 session files; filename extraction mirrors `checkpoint/SKILL.md:249`):
   ```sh
   _basename=$(basename "$_most_recent")
   active_task="${_basename#????-??-??-}"   # strip YYYY-MM-DD- date prefix
   active_task="${active_task%.md}"          # strip .md suffix
   # Optional cross-check: parse YAML frontmatter `task:` field if present; assert equality.
   ```
   ```sh
   current_stage=$(awk '/^## Current stage[[:space:]]*$/{found=1; next} found && /^[^#]/ && /[^[:space:]]/{print; exit} found && /^##/{exit}' "$_most_recent")
   [ -z "$current_stage" ] && current_stage="(stage unknown)"
   unfinished=$(awk '/^## Unfinished work[[:space:]]*$/{found=1; next} found && /^[^#]/{print} found && /^##/{exit}' "$_most_recent")
   # Optional: open_questions (11/46 hit rate — omit from prompt if absent)
   open_questions=$(awk '/^## Open questions[[:space:]]*$/{found=1; next} found && /^[^#]/{print} found && /^##/{exit}' "$_most_recent")
   _mtime_display=$(_get_mtime "$_most_recent")
   ```

   Surface to user:
   ```
   No recent checkpoint files found, but a recent session-state file exists:
     `YYYY-MM-DD-TASKNAME.md`  (mtime: DATE TIME)
     Active task: ${active_task}
     Current stage: ${current_stage}
   Synthesize a minimal restore from session-state only? [y / n]
   ```

   On `y`:
   - Extract INTENT (strip list glyphs and status glyphs from first non-empty line of `## Unfinished work`):
     ```sh
     # Strip pattern (in order):
     #   1. leading whitespace
     #   2. one of: "- ", "* ", "<digit>+. ", "<digit>+) "
     #   3. one of the four status glyphs (✓ ✗ ⏳ 🚫) followed by optional whitespace
     #   4. trailing whitespace
     # Example: "- 1. ⏳ T-04 wire up X" → "T-04 wire up X"
     _raw_intent=$(echo "$unfinished" | grep -v '^[[:space:]]*$' | head -1)
     INTENT=$(echo "$_raw_intent" \
       | sed 's/^[[:space:]]*//' \
       | sed 's/^[-*][[:space:]]*//' \
       | sed 's/^[0-9][0-9]*[.)][[:space:]]*//' \
       | sed 's/^[✓✗⏳🚫][[:space:]]*//' \
       | sed 's/[[:space:]]*$//')
     ```
   - Synthesize structured prompt as Step 2 input (replaces checkpoint file fields):
     - `TASK = active_task`
     - `BRANCH = "(unknown — session-state has no branch field)"`
     - `INTENT = INTENT` (stripped as above)
     - `IN_FLIGHT_ARTIFACTS = []` (skip Step 3 re-fire — no `## In-flight artifacts` in session-state files; surface "no in-flight artifacts to re-fire (session-state synthesis)")
   - Set `consumed_sentinel_path = ""` (no sentinel was consumed — path 5 in the 6-path contract).
   - Proceed to Step 2 with the synthesized fields.
   - Proceed to Step 5 (no sentinel cleanup for the synthesized path; current-session cleanup still runs if a sentinel exists).

   On `n`: fall through to existing Step 3 graceful "no checkpoints found" path.

   **Note:** The session-state fallback fires BEFORE the Step 3 graceful-error path. Step 3 is only reached when both the normal picker and the B3 fallback are exhausted or declined.

### Step 2: Surface checkpoint state to user

Read the checkpoint file. Parse its sections. Surface as a structured prompt:

```
Resuming task: <TASK>. Branch: <BRANCH>. Last intent: <INTENT>.
Session: claude --resume <SESSION_UUID>
In-flight artifacts: <N paths>.
Open questions: <N items>.
Re-fire reads on artifacts now? [y / n]
```

`<SESSION_UUID>` is read from the checkpoint file's `## Session ID` section. If absent (legacy checkpoint without `## Session ID`), display `Session: (not recorded in this checkpoint — legacy format)`. If `## Session link` recorded "unavailable" at save time, display `Session: (session UUID was unavailable at save time)`. Do NOT block the restore on either case — the line is informational.

If the checkpoint file is corrupt or unreadable: surface a graceful error with raw file contents plus:
`Manual recovery — please paste the checkpoint content above and I will reconstruct state.`
Do NOT delete the sentinel on corrupt-file path.

### Step 3: Re-fire reads (on `y`)

For each in-flight artifact path in the checkpoint's `## In-flight artifacts` section: invoke the Read tool on that path. This is when content re-enters the context — not at save time (paths-not-content rule).

### Step 4: Pending-prompt rehydrate

Enumerate `.workflow_artifacts/memory/pending-prompt-*.txt`:

**CASE A — No `pending-prompt-*.txt` files exist at all (modal proactive save flow):**
This is the common path: user saved proactively, started fresh session, runs --restore.
Skip step 4 entirely. Surface ONLY the task-state restore from step 2/3.
Proceed directly to step 5 (sentinel cleanup — pending-restore only).

**CASE B — `pending-prompt-${session_id}.txt` exists for the current session (block-recovery flow):**

Read the file. Detect format by checking for `=== BLOCKED PROMPT [...]` headers:

- **Legacy format (no headers present):** treat the entire file content as a single prompt entry. Surface with the existing interface:
  ```
  Your previous prompt was: <PROMPT_TEXT>
  Run it now? [y / n / edit]
  ```
  - On `y`: emit the prompt as-if the user just typed it (rebound path).
  - On `n`: trash-move the sentinel (to `.workflow_artifacts/memory/trash/<date>/`) without surfacing the prompt content.
  - On `edit`: invite the user to paste an edited version; on save, submit it.

- **Multi-entry format (one or more `=== BLOCKED PROMPT [<timestamp>] ===` headers):**
  Parse all entries. Each entry is the text between one header line and the next header line (or end of file), with leading/trailing blank lines trimmed. Any text appearing before the first `=== BLOCKED PROMPT` header (e.g., legacy preamble from a migration-on-append) is treated as an implicit first entry with timestamp `legacy`.

  **Non-replayable detection:** if a header line contains the substring `[non-replayable:`, tag that entry as `non-replayable`. Example header: `=== BLOCKED PROMPT [2026-05-30T14:22:00Z] [non-replayable:task-notification] ===`. Non-replayable entries are background agent completions (task-notifications) that were blocked by the hook — they are preserved for audit purposes but excluded from `all` replay. A user who explicitly selects a non-replayable entry by number can still replay it.

  Surface a numbered list:
  ```
  <N> blocked prompt(s) were saved while context was overloaded:
    1. [<timestamp_1>] <first 80 chars of prompt_1>...
    2. [<timestamp_2>] [non-replayable] <first 80 chars of prompt_2>...
    ...
  Replay which? [all / 1 / 2 / 1,3 / edit 1 / none]
  (Note: 'all' skips non-replayable entries; select by number to replay them individually.)
  ```

  - `all`: emit all REPLAYABLE entries in chronological order (oldest first, separated by a blank line). **Skip** entries tagged `non-replayable` — they are background notifications, not user prompts.
  - A single number (e.g. `2`): emit only that entry (even if tagged `non-replayable` — explicit user selection overrides the tag).
  - Comma-separated numbers (e.g. `1,3`): emit those entries in ascending order.
  - `edit N`: surface entry N in full, invite the user to paste an edited version before submitting. Wait for the user to provide the edited text, then emit that instead of the stored entry.
  - `none` or `n`: trash-move the file without replaying any entry.
  - Invalid input: re-prompt once; on second invalid input, treat as `none`.

  After replaying the selected prompts, proceed to Step 5 (sentinel cleanup).

**CASE C — `pending-prompt-*.txt` exists but ONLY for a DIFFERENT session-id (sentinel-staleness):**
Surface a warning:
```
Stale pending-prompt sentinel detected (session-id MISMATCH: was <OLD_SID>, current <CUR_SID>).
```
Then apply the same multi-entry format detection as CASE B:
- **Legacy format:** surface as `Content: <PROMPT_TEXT>` and offer `[y / n / delete]`.
  - `y`: emit the prompt.
  - `delete`: trash-move the stale file to `.workflow_artifacts/memory/trash/<date>/`.
  - `n`: leave it for explicit user cleanup.
- **Multi-entry format:** surface the numbered list (same as CASE B multi-entry), prefixed with the mismatch warning. The `edit N` option applies here as well.
- On `delete`: trash-move the stale file regardless of format.

### Step 5: Sentinel cleanup

Trash-move consumed sentinels to `.workflow_artifacts/memory/trash/<YYYY-MM-DD>/` (recoverable):
- `pending-prompt-${session_id}.txt` — if it was CASE B and user chose `y` or `n`.
- `pending-restore-${session_id}.txt` — always on successful restore (CASE A or B).
- `consumed_sentinel_path` — if non-empty AND different from the current-session sentinel (B2 fix: cleans the actually-consumed orphan sentinel from a prior session).

Use the `trash_move` helper from `__QUOIN_HOME__/hooks/_lib.sh` (fail-OPEN — if the move fails, warn and leave in place):
```bash
. __QUOIN_HOME__/hooks/_lib.sh && trash_move "<sentinel-path>" "$(pwd)/.workflow_artifacts/memory"
```

**Cleanup logic (B2 — two-call pattern):**
```sh
_base=".workflow_artifacts/memory"

# 1. Existing current-session cleanup (unchanged):
if [ -f "${_base}/pending-restore-${current_session_id}.txt" ]; then
  trash_move "${_base}/pending-restore-${current_session_id}.txt" "$_base"
fi

# 2. New: clean the actually-consumed orphan sentinel (B2):
#    consumed_sentinel_path is set by the picker (6-path contract in Step 1).
#    The dedup guard prevents double-trash when picker picked the current-session sentinel.
if [ -n "$consumed_sentinel_path" ] && \
   [ "$consumed_sentinel_path" != "${_base}/pending-restore-${current_session_id}.txt" ]; then
  if [ -f "$consumed_sentinel_path" ]; then
    trash_move "$consumed_sentinel_path" "$_base"
  fi
fi
```

Stale CASE C pending-prompt files left alone unless user chose `delete` (see CASE C below).
Checkpoint artifact stays in `checkpoints/` until `/sleep --purge` (architecture S-3) or manual delete.

### Step 6: Append cost-ledger row

```
<uuid> | <date> | checkpoint | haiku | task | restore | 0
```

### Step 7: Release pidfile

```
pidfile_release checkpoint
```
