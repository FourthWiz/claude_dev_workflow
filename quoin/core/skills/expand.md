# expand

Runtime-neutral intent for the expand skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Expand a caveman-compressed workflow artifact back into human-readable English
for human reading. Dispatches across three artifact tiers: no-op display for
Tier 1 English files; built-in summary block read for Class B contract
artifacts; lossy LLM re-expansion (banner-flagged) for Tier 3 ephemeral files.
Never used as a contract-approval path.

## When to use

- A user asks "what does this terse file say".
- A user wants the English version of a contract artifact for review (route
  them to the gate skill if it is a contract file requiring approval).
- A user wants to inspect a Tier 3 ephemeral file.

## Output behavior

A chat message containing one of:

- The file's `## For human` block (Class B contract artifact).
- The file's full English body displayed as-is (Tier 1 file).
- An LLM-reconstructed English rendering prefixed by a lossy-warning banner
  (Tier 3 ephemeral file).

Optionally, when `--save` is passed, write the rendering to
`<path>.expanded-<ISO-timestamp>.md` in the same directory as the source file,
without ever overwriting the source. Without `--save`, no file artifact is
produced.

## 7-step pipeline (runtime-neutral)

Execute steps in order. Stop at the first step that produces output.

1. **Resolve path** — try absolute path, then project-root-relative, then
   `.workflow_artifacts/`-relative. If no file is found: exit with a "path not
   found" message; no LLM call.
2. **Empty-file early-exit** — if the file is 0 bytes: exit with a "nothing to
   expand" message; no LLM call.
3. **Binary-content early-exit** — attempt to decode the first 1024 bytes as
   UTF-8; if decoding fails: exit with a "not UTF-8 text" message; no LLM
   call.
4. **Class B summary detection** — if the file has v3-format frontmatter AND a
   `## For human` heading within the first 50 lines after the closing `---`,
   display that block and exit. Detection MUST be a deterministic string
   comparison, never an LLM call.
5. **Tier 1 path match** — if the resolved path matches any entry in the
   hardcoded Tier 1 list (see next section), display the file as-is with an
   "Already English" banner and exit; no LLM call.
6. **Size warning** — if the file exceeds 500 KB, prompt the user for
   confirmation before invoking the runtime-provided LLM expander; the runtime
   may surface an estimated cost when a pricing reference is available.
7. **LLM re-expansion** — call the runtime-provided expander with the verbatim
   re-expansion prompt; display the output prefixed by the lossy-warning
   banner; on `--save`, also write the rendering to
   `<path>.expanded-<ISO-timestamp>.md`.

## Tier 1 path list semantics

The Tier 1 list is the closed enumeration of file paths that are always
English and must be displayed verbatim — no LLM call. The categories are:

- Hand-edited rules and rubrics (e.g., the shared rules file, terse-rubric,
  format-kit references).
- In-task contract files: `.workflow_artifacts/<task-name>/architecture.md`,
  `.workflow_artifacts/<task-name>/review-*.md`,
  `.workflow_artifacts/<task-name>/cost-ledger.md`.
- Rendered briefings: `memory/weekly/*.md`, `memory/daily/<date>.md` (daily
  briefings, not insights files).
- The memory index.

Matching uses path-suffix exact match, glob (`*` within a segment), or
`<date>` matching `YYYY-MM-DD` shaped segments. Adding a Tier 1 entry requires
editing the adapter SKILL.md inline — this is an established exception to the
rule that paths live outside skill bodies.

## Optional --save semantics

Passing `--save` writes the rendered output to
`<path>.expanded-<ISO-timestamp>.md` in the same directory as the source. The
flag never overwrites the source file. Files matching `*.expanded-*.md` are
gitignored. This flag is opt-in by design: without `--save`, no file artifact
is produced.

## Behavior contract

- Never used for contract-approval. Class B contract artifacts route to the
  gate skill for approval, not to expand.
- Empty-file, binary-file, Class B-detected, and Tier 1-matched paths MUST NOT
  invoke the LLM expander.
- The v3-format detection rule is byte-equal to the rule used by the writer
  skills (one shared fixture per the test suite).
- The re-expansion prompt preserves verbatim: file paths, identifiers, code
  blocks, URLs, commands, version numbers, headings, section markers, issue
  identifiers, negations, quantifiers, and numeric counts. The expander MUST
  NOT invent facts not present in the source.
- The lossy-warning banner is shown on every Tier 3 expansion output. The
  banner explicitly states the expansion is not byte-identical to the source
  and MUST NOT be used to approve a contract artifact.
- The `--save` flag is opt-in. Without it, no file is written. The skill
  never auto-saves.
- Path-ambiguity rule: prefer project-root-relative resolution over
  `.workflow_artifacts/`-relative; when both resolve, use the
  project-root-relative match and surface the ambiguity to the user.

## Out of scope

The following are adapter-owned, runtime-specific concerns — not part of this
portable contract:

- The §0 self-dispatch grammar (a runtime cost-guardrail concern).
- The specific LLM the runtime uses to perform re-expansion, its model name,
  or any tier-tagged identifier.
- The specific subagent-spawn mechanism (the runtime decides how to invoke its
  expander).
- The cost-estimate pricing formula (per-token rate is adapter-provided).
- Any per-runtime session-state writing (expand does NOT write session state —
  this is explicit in the adapter SKILL.md and remains explicit there).

## Notes

- The rendered-output shape is intentionally open beyond the four mandatory
  display modes (Class B summary, Tier 1 display, Tier 3 expansion,
  error-message exit). Runtime adapters may add advisory lines but MUST NOT
  replace any of the four.
- The Tier 1 path list is a closed enumeration at any given moment; growing it
  requires editing the adapter skill body inline (an established carve-out per
  the lessons-learned history).
