---
name: expand
model: sonnet
description: "Expands compressed (terse) workflow artifacts back to English for human reading. Use for: /expand <path>, 'show me the English version of', 'expand this file', 'what does this terse file say'. Dispatches: file-switch (reads .original.md side-file for Tier 2 contract files), no-op display (Tier 1 English files), LLM re-expansion (Tier 3 ephemeral files — lossy, banner-flagged). Never used as a contract approval path."
---

# Expand

Expands a caveman-compressed (terse) workflow artifact back into human-readable English. Dispatches to one of three paths: no-op display for Tier 1 English files, file-switch for Tier 2 contract files (reads `.original.md`), or LLM re-expansion for Tier 3 ephemeral files (lossy, banner-flagged). Invoke as `/expand <path>` or `/expand <path> --save`.

This skill implements architecture §5.4's 8-step pipeline. It is the user-facing escape hatch for the caveman-token-optimization v2 architecture — not a contract-approval path.

## Session bootstrap

Cost ledger: if a task context is determinable from the path or active session, append a row with phase `expand` to `.workflow_artifacts/<task-name>/cost-ledger.md`. Row format per CLAUDE.md cost-tracking rules. If no task context is active, skip cost recording.

`/expand` does NOT write session state (architecture §5.4 explicit).

## Hardcoded Tier 1 path list

Files matching any entry below are always English — display as-is with the Tier 1 banner. Never send them through LLM re-expansion.

```
# Exact paths:
dev-workflow/CLAUDE.md
dev-workflow/memory/terse-rubric.md
.workflow_artifacts/memory/MEMORY.md
.workflow_artifacts/memory/lessons-learned.md

# Per-task paths (resolve <task> to the active task name at runtime):
.workflow_artifacts/<task>/architecture.md
.workflow_artifacts/<task>/review-*.md
.workflow_artifacts/<task>/cost-ledger.md
.workflow_artifacts/<task>/*.original.md

# Glob patterns:
.workflow_artifacts/memory/weekly/*.md
.workflow_artifacts/memory/daily/<date>.md   # daily briefings — NOT insights-<date>.md
```

**Note:** Adding a Tier 1 path requires updating this file — this is an exception pattern per lesson 2026-04-13 (`run-skill`) and is documented inline here so it is discoverable when other Tier 1 additions are made.

## 8-step pipeline

Execute steps in order. Stop at the first step that produces output.

### Step 1: Resolve path

Attempt to resolve `<path>` to an absolute file. Try in order: (a) as an absolute path, (b) relative to the project root (the directory containing `.workflow_artifacts/`), (c) relative to `.workflow_artifacts/`.

If the file does not exist after all resolution attempts → print `/expand: path not found: <path>` and exit. No LLM call.

### Step 2: Empty-file check

Read the file. If it is 0 bytes → print `/expand: <path> is empty, nothing to expand` and exit. No LLM call.

### Step 3: Binary-content check

Attempt to decode the first 1024 bytes as UTF-8. If decoding fails (non-UTF-8 content) → print `/expand: <path> is not UTF-8 text; /expand operates on markdown only` and exit. No LLM call.

### Step 4: `.original.md` suffix check

If `<path>` ends in `.original.md` → display the file content as-is. Print banner:

```
Already expanded (.original.md side-file)
```

Done — no LLM call.

### Step 5: Tier 1 path match

Check whether the resolved path matches any entry in the Tier 1 path list above. Matching rules:

- **Exact paths:** compare the resolved absolute path's suffix against each exact entry (e.g., `dev-workflow/CLAUDE.md` matches any resolved path ending in `dev-workflow/CLAUDE.md`).
- **Per-task patterns:** resolve `<task>` to the active task name if determinable from context or current session state; otherwise match with the literal pattern `<task>` as a wildcard segment. `review-*.md` and `*.original.md` are glob-style wildcards within the segment.
- **Glob patterns:** match using standard shell-glob semantics (`*` matches within a directory segment; `<date>` matches any `YYYY-MM-DD`-shaped segment).

If the path matches any entry → display the file content as-is. Print banner:

```
Already English (Tier 1 file: <matching-pattern>)
```

Done — no LLM call.

### Step 6: File-switch check

If `<path>.original.md` exists alongside the target file → display the contents of `<path>.original.md`. Print banner:

```
File-switch expansion (exact — reads <path>.original.md)
```

Done — no LLM call.

### Step 7: Size warning

If the file is larger than 500 KB → print:

```
/expand: <path> is <size> KB; LLM re-expansion will cost approximately $<estimate>. Proceed? (y/n)
```

Cost estimate formula: `(size_bytes / 4) * 1.5 * 15 / 1_000_000` dollars (bytes→tokens via /4, expansion factor 1.5, Sonnet output price $15/M tokens).

Wait for user input. On `n` → exit with no action.

### Step 8: LLM re-expansion

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

> ⚠️ **LLM re-expansion.** This is a best-effort reconstruction from the terse source. The reconstructed text is not byte-identical to what other skills read. Do NOT use this expansion to approve a contract artifact like `current-plan.md` — for contract artifacts, `/gate` reads `.original.md` directly.

(Emoji is explicitly permitted in this banner — it is a UX signal, not content decoration, per architecture §5.4.)

## Important behaviors

- **Never use re-expansion for contract approval.** The user-approved version of any contract artifact is the `.original.md` side-file (Tier 2), not a lossy LLM reconstruction. If a user tries to approve `current-plan.md` via `/expand`, warn them to use the `.original.md` file with `/gate` instead.
- **`--save` is opt-in.** Without `--save`, no file is written to disk. The expansion is displayed to the user only. Do not auto-save.
- **Path ambiguity resolution:** prefer project-root-relative resolution over `.workflow_artifacts/`-relative. If both resolve to existing files, use the project-root-relative match and note the ambiguity to the user.
