---
name: checkpoint
description: "General-purpose state-saving — save session-restore state mid-session before context exhaustion, between tasks, between sessions, or before starting new heavy work. Writes a pending-restore sentinel so a fresh session can resume exactly where you left off. Also surfaces pending-restore state on --restore. Use for: /checkpoint, 'save my place', 'checkpoint', 'save session', '/checkpoint --restore', 'restore checkpoint', 'resume from checkpoint'. Does NOT roll up dailies, does NOT touch lessons-learned.md or forgotten/."
model: haiku
---

# Checkpoint

You save session-restore state (paths-not-content) so a fresh session can resume after context compaction or voluntary save. You also provide `--restore` to re-hydrate that state in a new session.

## When to use

`/checkpoint` is a general-purpose state-save. Run it in any of these four cases:

1. **Mid-session before context exhaustion** — when the context-utilization advisory fires (`UserPromptSubmit` hook warns), save state so the next session can pick up from disk.
2. **Between tasks** — finished one task and starting another in the same session; checkpoint the prior task's in-flight state before pivoting.
3. **Between sessions** — closing a session with work still in flight; checkpoint so the next session can `/checkpoint --restore` and resume.
4. **Before starting new heavy work** — proactively save your current place before a long subagent run, large refactor, or multi-file edit that may pollute context.

`/checkpoint` does NOT promote insights to `lessons-learned.md`, does NOT roll up daily caches, and does NOT auto-invoke `/sleep`. For end-of-workday rollup (insight promotion + daily cache + `/sleep`), run `/end_of_day` instead.

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

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §0c at the current tier. Fail-OPEN on the cost guardrail.

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §0c.

## §0c Pidfile lifecycle (FIRST STEP after §0 dispatch)

At entry — immediately after §0 dispatch resolves:

```
. ~/.claude/scripts/pidfile_helpers.sh && pidfile_acquire checkpoint
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

### Step 1: Gather session context

Read the following sources (best-effort; skip gracefully if any file is absent):

1. **Session state file** — most recently modified `<cwd>/.workflow_artifacts/memory/sessions/*.md` file (use `ls -t` mtime ordering; lex order is NOT reliable for UUID-shaped session names). Extract:
   - Active task name (from filename pattern `YYYY-MM-DD-<task-name>.md` — strip the date prefix)
   - Current phase (from `## Cost` block → `Phase:` line)
   - Open questions (from `## Open questions` block)
   - Decisions made this session (from `## Decisions made` block, if present)
   - Unfinished work list (from `## Unfinished work` block)

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

## Last user intent
<one-sentence restatement of what the user was working on>

## In-flight artifacts
- current-plan.md: <path or "(none found)">
- architecture.md: <path or "(none found)">
- latest critic-response: <path or "(none found)">
- latest review: <path or "(none found)">
- session-state: <path or "(none found)">

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

### Step 6: Release pidfile

```
pidfile_release checkpoint
```

## Restore mode (`--restore` argument present)

Detect mode: if the user's invocation includes `--restore`, run restore mode.

### Step 1: Locate checkpoint

Enumerate `.workflow_artifacts/memory/pending-restore-*.txt`:

1. **Preferred:** check for `pending-restore-${session_id}.txt` matching the current session's session_id. If found, read its content to get the checkpoint file path.

2. **Fallback (disambiguation):** if no current-session match, enumerate all sentinels sorted by mtime:

   ```
   sentinel_list=$(ls -t .workflow_artifacts/memory/pending-restore-*.txt 2>/dev/null)
   ```

   - **0 sentinels:** fall through to Step 3 directly (no pending-restore files exist).

   - **Exactly 1 sentinel:** use it automatically. Tag with a session-id mismatch warning:
     `Session-id mismatch: sentinel is from a prior session. Using it anyway.`

   - **2 or more sentinels:** do NOT auto-pick. Read each sentinel file to get the checkpoint path it contains, then read `## Active task` and `## Branch` from that checkpoint file. Surface a numbered list to the user:

     ```
     Multiple pending-restore sentinels found. Which session do you want to restore?
       1. Task: <TASK_1>  Branch: <BRANCH_1>  (checkpoint: <DATE_1>)
       2. Task: <TASK_2>  Branch: <BRANCH_2>  (checkpoint: <DATE_2>)
     Enter number, or 'skip' to proceed to direct checkpoint lookup:
     ```

     Where `<DATE_N>` is the `YYYY-MM-DD` prefix from the checkpoint filename.

     - On a valid number: use that sentinel's checkpoint file; tag with mismatch warning.
     - On `skip`: fall through to Step 3 (direct checkpoint lookup by date).
     - On invalid input: re-prompt once; on second invalid input, fall through to Step 3.

3. **Direct checkpoint lookup:** if no pending-restore sentinel exists at all, fall back to the most recent `checkpoints/<YYYY-MM-DD>-*.md` sorted by mtime. If both `<date>-<task>.md` and `<date>-<task>-precompact.md` exist with the same date prefix, prefer the non-`-precompact` file (voluntary checkpoint takes precedence over the automatic precompact one). Tie-break by mtime.

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

Use the `trash_move` helper from `~/.claude/hooks/_lib.sh` (fail-OPEN — if the move fails, warn and leave in place):
```bash
. ~/.claude/hooks/_lib.sh && trash_move "<sentinel-path>" "$(pwd)/.workflow_artifacts/memory"
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
