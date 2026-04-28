---
name: expand
model: sonnet
description: "Expands compressed (terse) workflow artifacts back to English for human reading. Use for: /expand <path>, 'show me the English version of', 'expand this file', 'what does this terse file say'. Dispatches: Class B summary detection (reads ## For human block at top of v3 artifacts), no-op display (Tier 1 English files), LLM re-expansion (Tier 3 ephemeral files — lossy, banner-flagged). Never used as a contract approval path."
---

# Expand

Expands a caveman-compressed (terse) workflow artifact back into human-readable English. Dispatches to one of three paths: no-op display for Tier 1 English files, Class B summary detection (reads `## For human` block at top of v3 contract artifacts), or LLM re-expansion for Tier 3 ephemeral files (lossy, banner-flagged). Invoke as `/expand <path>` or `/expand <path> --save`.

This skill implements architecture §5.6's 7-step pipeline. It is the user-facing escape hatch for the caveman-token-optimization v2 architecture — not a contract-approval path.

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: sonnet`. If the executing agent is running on a model
strictly more expensive than the declared tier, you MUST self-dispatch before doing the
skill's actual work.

Detection:
  - Read your current model from the system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus.
  - Sentinel parsing: the user's prompt is checked for the `[no-redispatch]` family.
      * Bare `[no-redispatch]` (parent-emit form AND user manual override): skip dispatch, proceed to §1 at the current tier.
      * Counter form `[no-redispatch:N]` where N is a positive integer ≥ 2: ABORT (see "Abort rule" below).
      * Counter form `[no-redispatch:1]` is reserved and treated as bare `[no-redispatch]` for forward-compatibility; do not emit it.
  - If current_tier > declared_tier AND prompt does NOT start with any `[no-redispatch]` form:
      Dispatch reason: cost-guardrail handoff. dispatched-tier: sonnet.
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "expand dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in expand. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /expand`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## Session bootstrap

Cost ledger: if a task context is determinable from the path or active session, append a row with phase `expand` to `.workflow_artifacts/<task-name>/cost-ledger.md`. Row format per CLAUDE.md cost-tracking rules. If no task context is active, skip cost recording.

`/expand` does NOT write session state (architecture §5.4 explicit).

## Hardcoded Tier 1 path list

Files matching any entry below are always English — display as-is with the Tier 1 banner. Never send them through LLM re-expansion.

```
# Exact paths:
quoin/CLAUDE.md
quoin/memory/terse-rubric.md
.claude/memory/terse-rubric.md
.workflow_artifacts/memory/MEMORY.md
.workflow_artifacts/memory/lessons-learned.md

# Per-task paths (resolve <task> to the active task name at runtime):
.workflow_artifacts/<task>/architecture.md
.workflow_artifacts/<task>/review-*.md
.workflow_artifacts/<task>/cost-ledger.md

# Glob patterns:
.workflow_artifacts/memory/weekly/*.md
.workflow_artifacts/memory/daily/<date>.md   # daily briefings — NOT insights-<date>.md
```

**Note:** Adding a Tier 1 path requires updating this file — this is an exception pattern per lesson 2026-04-13 (`run-skill`) and is documented inline here so it is discoverable when other Tier 1 additions are made.

## 7-step pipeline

Execute steps in order. Stop at the first step that produces output.

### Step 1: Resolve path

Attempt to resolve `<path>` to an absolute file. Try in order: (a) as an absolute path, (b) relative to the project root (the directory containing `.workflow_artifacts/`), (c) relative to `.workflow_artifacts/`.

If the file does not exist after all resolution attempts → print `/expand: path not found: <path>` and exit. No LLM call.

### Step 2: Empty-file check

Read the file. If it is 0 bytes → print `/expand: <path> is empty, nothing to expand` and exit. No LLM call.

### Step 3: Binary-content check

Attempt to decode the first 1024 bytes as UTF-8. If decoding fails (non-UTF-8 content) → print `/expand: <path> is not UTF-8 text; /expand operates on markdown only` and exit. No LLM call.

### Step 4: Class B summary detection

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

If `<path>` matches a Class B path (`current-plan.md`, `architecture.md`, `review-*.md`, `daily/<date>.md`, `weekly/*.md`) AND the file contains a `## For human` heading within the first 50 lines per the rule above → display the message:

  `<path>` is a Class B artifact with a built-in `## For human` summary at the top.
  Showing summary; pass `--full` to see the structured body.

Then display the `## For human` block content.

`/expand <path> --full` displays the full body.
`/expand <path> --section <name>` displays a single named section (works on Class A and Class B).

Done — no LLM call.

### Step 5: Tier 1 path match

Check whether the resolved path matches any entry in the Tier 1 path list above. Matching rules:

- **Exact paths:** compare the resolved absolute path's suffix against each exact entry (e.g., `quoin/CLAUDE.md` matches any resolved path ending in `quoin/CLAUDE.md`).
- **Per-task patterns:** resolve `<task>` to the active task name if determinable from context or current session state; otherwise match with the literal pattern `<task>` as a wildcard segment. `review-*.md` is a glob-style wildcard within the segment.
- **Glob patterns:** match using standard shell-glob semantics (`*` matches within a directory segment; `<date>` matches any `YYYY-MM-DD`-shaped segment).

If the path matches any entry → display the file content as-is. Print banner:

```
Already English (Tier 1 file: <matching-pattern>)
```

Done — no LLM call.

### Step 6: Size warning

If the file is larger than 500 KB → print:

```
/expand: <path> is <size> KB; LLM re-expansion will cost approximately $<estimate>. Proceed? (y/n)
```

Cost estimate formula: `(size_bytes / 4) * 1.5 * 15 / 1_000_000` dollars (bytes→tokens via /4, expansion factor 1.5, Sonnet output price $15/M tokens).

Wait for user input. On `n` → exit with no action.

### Step 7: LLM re-expansion

Invoke Sonnet with the re-expansion prompt below. Display the result with the warning banner:

```
⚠️ LLM re-expansion (lossy — may diverge from terse source). Do NOT use for contract-file approval.
```

## Re-expansion prompt

> You are expanding a caveman-style terse artifact back into full English prose for human reading. Preserve **verbatim**: all file paths, identifiers, code blocks, URLs, commands, version numbers, headings, section markers (CRITICAL, MAJOR, MINOR, PASS, REVISE), issue identifiers (CRIT-N, MAJ-N, MIN-N), negations, quantifiers, numeric counts. Do **not** introduce facts, examples, or reasoning not present in the source. If the source is ambiguous, flag "[ambiguous]" rather than inventing a reading. Write in plain English prose or bulleted lists, whichever matches the source's organization. Source content follows:
>
> ---
> {terse content}
> ---
>
> Expanded English version:

## Optional `--save` flag

`/expand <path> --save` writes the expansion to `<path>.expanded-<ISO-timestamp>.md` (e.g., `critic-response-1.expanded-2026-04-23T14:30:00.md`). Never overwrites the source file. The `--save` flag is deliberately opt-in to avoid accumulating expansion artifacts across sessions. Files matching `*.expanded-*.md` are gitignored (added in Task 9 of the caveman-token-optimization Stage 1 plan).

## Warning banner

Every LLM re-expansion output starts with:

> ⚠️ **LLM re-expansion.** This is a best-effort reconstruction from the terse source. The reconstructed text is not byte-identical to what other skills read. Do NOT use this expansion to approve a contract artifact like `current-plan.md` — for Class B contract artifacts, `/gate` reads the `## For human` summary block at the top of the artifact directly (per architecture v3 §5.5).

(Emoji is explicitly permitted in this banner — it is a UX signal, not content decoration, per architecture §5.4.)

## Important behaviors

- **Never use re-expansion for contract approval.** Class B contract artifacts (`current-plan.md`, `architecture.md`, `review-*.md`) carry their user-facing summary in a `## For human` block at the top of the file, read directly by `/gate`. If a user tries to approve a contract artifact via `/expand`, direct them to `/gate` instead — `/gate` reads the structural file, not a lossy LLM reconstruction.
- **`--save` is opt-in.** Without `--save`, no file is written to disk. The expansion is displayed to the user only. Do not auto-save.
- **Path ambiguity resolution:** prefer project-root-relative resolution over `.workflow_artifacts/`-relative. If both resolve to existing files, use the project-root-relative match and note the ambiguity to the user.
