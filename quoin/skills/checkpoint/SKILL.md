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

### Step 0.5: Post-compact flag (optional bypass documentation)

Detect flag: if the user's invocation includes `--after-compact`, set POST_COMPACT=true.

If POST_COMPACT is true:
  - Continue to Step 1 normally (no blocking precondition gate exists today —
    this flag is documentation of intent, not a runtime bypass).
  - Emit one-line stderr INFO: "[checkpoint] --after-compact flag noted; proceeding to save."
  - At Step 5 (Report to user): append "Mode: post-compact save (--after-compact flag was set)."

If POST_COMPACT is false (flag absent):
  - Continue to Step 1 normally.

Note for implementers: The 'compaction needed first' nudge described in older bug reports
does NOT exist in the current deployed SKILL.md or userpromptsubmit.sh. The exemption
for /checkpoint from BLOCK_BPS context blocking is at userpromptsubmit.sh lines 71-82.
The --after-compact flag is provided as an explicit intent signal for future maintainers
and for users who want to document their workflow.

### Step 1: Gather session context

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

### Step 2: Write checkpoint file

Write to: `.workflow_artifacts/memory/checkpoints/<YYYY-MM-DD>-<task-name>.md`

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

**Paths-not-content rule (D-04):** NEVER carry the actual file contents into the checkpoint. Only paths. Restore re-fires the Read tool on disk artifacts in the new session.

**Soft size cap:** If the written checkpoint file is larger than 4 KB, emit one-line stderr warning:
`[quoin checkpoint] WARNING: checkpoint file <PATH> exceeds 4 KB soft cap (<N> bytes) — paths-not-content rule may be violated; check for accidentally-included content.`
Continue; do NOT abort.

### Step 3: Write pending-restore sentinel

Write the checkpoint file path (single line) to:
`.workflow_artifacts/memory/pending-restore-${session_id}.txt`

Where `session_id` is the current session's UUID (read from the session-state `## Cost` block → `Session UUID:` line, or from the harness system context if available).

If session_id cannot be determined: emit warning and skip sentinel write (checkpoint file still kept).

The `sessionstart.sh` hook surfaces this sentinel on next session start.

### Step 4: Append cost-ledger row

Append a row to `.workflow_artifacts/<task-name>/cost-ledger.md`:

```
<uuid> | <date> | checkpoint | haiku | task | save | 0
```

UUID: read the most-recently-modified `~/.claude/projects/<project-hash>/<uuid>.jsonl`.
The ledger row is written ONCE — either by the Haiku-dispatched subagent (§0 dispatch path) OR by the parent (if already at Haiku tier). Never by both.

### Step 5: Report to user

Print a brief confirmation:
- Checkpoint saved to: `<path>`
- Sentinel written: `<pending-restore-session_id.txt path>`
- To resume: `/checkpoint --restore` in a fresh session

If `--after-compact` was set (POST_COMPACT=true), append:
`Mode: post-compact save (--after-compact flag was explicitly set).`

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

**Fast path (sub-second, bypass all enumeration):**
Before building the candidate list, check for a current-session sentinel:
```
if exists pending-restore-${current_session_id}.txt:
  read its single-line content (cp_path)
  verify cp_path exists; if yes: return cp_path immediately (skip enumeration entirely)
```
`current_session_id` is obtained via the same UUID-acquisition procedure as Step 1.1 (harness-provided UUID; else most recently modified JSONL filename stem).

**Full enumeration path** (fires only when fast path finds nothing):

1. Build a candidate list from two sources, de-duplicated by checkpoint-file path:
   - **All sentinels:** `.workflow_artifacts/memory/pending-restore-*.txt` — each contains a checkpoint path on line 1.
   - **All checkpoints (30-day window):** use `find .../checkpoints/ -maxdepth 1 -name '*.md' ! -name '*.tmp' -mtime -30 -print0 | while IFS= read -r -d '' cp; do ...` (null-delimited, space-safe for Google Drive paths with spaces). Skip any file whose byte-size < 100 bytes: `[ $(wc -c < "$cp") -ge 100 ] || continue`. This guards against 0-byte corrupt entries.

2. Annotate each candidate: task name (from `## Active task`), branch (from `## Branch`), date (from filename prefix), source (`sentinel` or `disk-only`). Awk extraction: `awk '/^## Active task[[:space:]]*$/{getline; gsub(/\r$/,""); print; exit}'` — strips trailing CR and handles value-on-next-line form. If `## Active task` cannot be extracted (parse failure), drop the candidate silently.

3. De-duplication: prefer the non-`-precompact` file over the `-precompact` file when one filename equals the other minus `-precompact.md` AND their mtimes are within `${QUOIN_PICKER_DEDUP_WINDOW:-7d}` (7 days) of each other. Pairs older than 7 days apart are treated as independent entries.

4. Backward-compat reader: tolerate missing `## Session ID` (older voluntary checkpoints). When absent, display `(legacy)` in the picker source column.

5. Auto-pick rules:
   - **Zero candidates:** fall through to Step 3 (graceful error message: no checkpoints found).
   - **Exactly 1 candidate:** auto-pick with session-id mismatch warning.
   - **Two or more:** present the numbered picker:
     ```
     Multiple recent checkpoints found. Which session do you want to restore?
       1. * Task: TASK_1  Branch: BRANCH_1  Date: DATE_1  (sentinel)
       2.   Task: TASK_2  Branch: BRANCH_2  Date: DATE_2  (disk-only)
       ...
     Enter number, or 'skip' to proceed to direct checkpoint lookup:
     ```
     `*` marks sentinel-backed entries. Cap at 10 items (mtime descending). If more: `... and <N> older. Use --defer to skip.`
     - On a valid number: use that entry's checkpoint file.
     - On `skip`: fall through to Step 3.
     - On invalid input: re-prompt once; on second invalid input, fall through to Step 3.

### Step 2: Surface checkpoint state to user

Read the checkpoint file. Parse its sections. Surface as a structured prompt:

```
Resuming task: <TASK>. Branch: <BRANCH>. Last intent: <INTENT>.
In-flight artifacts: <N paths>.
Open questions: <N items>.
Re-fire reads on artifacts now? [y / n]
```

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

  Surface a numbered list:
  ```
  <N> blocked prompt(s) were saved while context was overloaded:
    1. [<timestamp_1>] <first 80 chars of prompt_1>...
    2. [<timestamp_2>] <first 80 chars of prompt_2>...
    ...
  Replay which? [all / 1 / 2 / 1,3 / edit 1 / none]
  ```

  - `all`: emit all entries in chronological order (oldest first, separated by a blank line).
  - A single number (e.g. `2`): emit only that entry.
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

Use the `trash_move` helper from `__QUOIN_HOME__/hooks/_lib.sh` (fail-OPEN — if the move fails, warn and leave in place):
```bash
. __QUOIN_HOME__/hooks/_lib.sh && trash_move "<sentinel-path>" "$(pwd)/.workflow_artifacts/memory"
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
