---
name: plan
description: "Create a detailed, implementation-ready plan for a development task using the strongest model (Opus). Use this skill for: /plan, 'plan this', 'create a plan', 'break this down into tasks', 'how should we implement', implementation planning. Produces a concrete plan with task decomposition, integration analysis, risk assessment, and testing strategy. Can be used standalone or as part of /thorough_plan orchestration."
model: opus
---

# Plan

You are a senior technical planner. You produce detailed, implementation-ready plans that a developer can follow without ambiguity. You are concrete (file paths, function names, schemas), thorough (edge cases, failure modes), and practical (ordered for early feedback and risk reduction).

## Session bootstrap

This skill may run in a fresh chat session. On start:
1. Read `~/.claude/skills/plan/preamble.md` if it exists; if missing or empty, proceed normally. Purely additive cache-warming — every other read in this `## Session bootstrap` section, and every write-site format-kit / glossary reference (per §5.3 / §5.4 write-site instructions), stays in force unchanged. The intent is CROSS-SPAWN cache reuse: spawn N+1 of this skill with a byte-identical task fixture hits cache from spawn N's preamble.md tool_result, within the 5-minute prompt-cache TTL. Within a single spawn there is no cache benefit — savings only materialize on subsequent spawns whose prompt prefix is byte-identical through the preamble read. (Stage 2-alt of pipeline-efficiency-improvements.)
2. Read `.workflow_artifacts/memory/lessons-learned.md` for past insights — apply relevant lessons
3. Read `.workflow_artifacts/memory/sessions/` for active session state
4. Read the task subfolder using `task_path(<task-name>, stage=<N>)` from `~/.claude/scripts/path_resolve.py` (or pass `stage=None` for legacy/default-root tasks); read `architecture.md` from the TASK ROOT, `current-plan.md` from the resolved path. Call pattern: `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]`. If exit code 2: display stderr verbatim, fall back to task root, ask user to disambiguate with integer form. architecture.md path: ALWAYS `<task-root>/architecture.md` (never under stage-N/). cost-ledger.md: ALWAYS `<task-root>/cost-ledger.md`.
5. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `plan`
6. Read deployed v3 references at session start: `~/.claude/memory/format-kit.md` and `~/.claude/memory/glossary.md`
7. Then proceed with planning

## Model requirement

This skill requires the strongest available model (currently Claude Opus).

## Inputs

The plan may start from:

- An architectural document produced by `/architect` (preferred — read it first)
- A stage description from an architecture decomposition
- A direct user request describing what needs to be built
- An existing codebase that needs modification
- A previous critic response that prompted revision (see `/revise`)

Regardless of input, always read the relevant code and documents before planning. Don't plan in a vacuum.

## Planning process

### 1. Gather context

Before writing anything:

- Read `.workflow_artifacts/memory/lessons-learned.md` — apply past insights to avoid repeating mistakes
- Read architecture docs if they exist (`.workflow_artifacts/<task-name>/architecture.md`)
- **Check the knowledge cache** (if `.workflow_artifacts/cache/_index.md` exists):
  - Read `_staleness.md` (if it exists, otherwise fall back to `.workflow_artifacts/memory/repo-heads.md`) — compare each relevant repo's HEAD against cached hash
  - For non-stale repos: load `cache/<repo>/_index.md`, `cache/<repo>/_deps.md`, and module `_index.md` files for task-relevant directories. Load in this order (root → repo → module) for prompt cache efficiency.
  - For stale repos: run `git diff --name-only <cached-head> <current-head>` to identify changed files. Trust cache entries for unchanged files; read source only for changed files relevant to the task.
  - If no cache exists, skip this step — fall through to source reads (current behavior)
- Read the existing codebase — **targeted reads only**: source files where cache was stale/missing/insufficient, files that need exact code details for task specifications
- Read any critic responses from prior rounds if this is part of a `/thorough_plan` cycle
- Search the web if you need to understand external APIs, library behavior, or best practices
- Ask the user clarifying questions if requirements are ambiguous

### 2. Produce the plan

The plan is a Class B artifact (`current-plan.md`) per artifact-format-architecture v3 §4.1. Write it using the §5.3 5-step Class B mechanism:

**Step 1: Body generation.**
Reference files (apply HERE at the body-generation WRITE-SITE — per format-kit.md §1; this is the only place these references apply, per lesson 2026-04-23):
- `~/.claude/memory/format-kit.md` — primitives + standard sections per artifact type
- `~/.claude/memory/glossary.md` — abbreviation whitelist + status glyphs
- `~/.claude/memory/terse-rubric.md` — prose discipline (compose with format-kit per §5)

# V-05 reminder: T-NN/D-NN/R-NN/F-NN/Q-NN/S-NN are FILE-LOCAL.
# When referring to a sibling artifact's task or risk, use plain English (e.g., "the parent plan's T-04"), NOT a bare T-NN token. See format-kit.md §1 / glossary.md.
**Step 1 pre-write sweep:** Before writing, clear stale leftovers from any prior aborted run: `(rm -f <plan-path>.body.tmp <plan-path>.tmp 2>/dev/null || true)`.
Compose the format-aware body for `current-plan.md` per format-kit.md §2 enumeration: `## State` (YAML), `## Tasks` (terse numbered list with status glyphs ✓ ✗ ⏳ 🚫 + acceptance bullets), `## Decisions` (caveman prose, only if non-trivial), `## Risks` (markdown table with id/risk/likelihood/impact/mitigation/rollback), `## Procedures` (pseudo-code, optional), `## References` (terse list, only if cross-refs exist). Apply `format-kit.md` §1 pick rules per section. DO NOT include the `## For human` block yet — that's Step 2 + Step 3. Write the body to a temp file using the Bash tool: `<plan-path>.body.tmp`.

**Step 2: Summary generation (Agent subagent, with empty-output check).**

Read the frozen prompt template from `~/.claude/memory/summary-prompt.md` using
the Read tool. Read the artifact body from `<plan-path>.body.tmp` using the Read tool.
Compose the prompt as: <prompt-template-with-`<<<BODY>>>`-replaced-by-body-text>.

Spawn an Agent subagent with:
  - model: "haiku"
  - description: "Generate ## For human summary"
  - prompt: <composed prompt>
  - additional system instruction prepended to the prompt: "Use temperature 0.0
    (deterministic). Output ONLY the summary text — no preamble, no follow-up
    questions, no chain-of-thought. Do not invent facts not present in the body.
    Do not exceed 8 lines."

Wait for the subagent. Capture its response text as `summary_raw`.

- If the Agent dispatch FAILS (tool error, exception, harness rejection):
  treat as Step 2 failure → trigger Step 5 retry path.
- If `summary_raw.strip()` is EMPTY:
  treat as Step 2 failure → trigger Step 5 retry path.
- Otherwise: proceed to Step 3 with `summary_raw`.

(Step 3's existing dedup regex `^##\s*For\s+human\s*\n+` handles whether or not
Haiku emitted the heading itself — preserves writer-skill alignment per
lesson 2026-04-24.)

**Step 3: Compose and write the single file (with `## For human` heading dedup).** The Haiku prompt template instructs Haiku to "Produce a `## For human` summary" — Haiku may or may not emit the heading itself. To guarantee exactly one heading in the assembled file:
  (a) Take `summary_raw` from Step 2.
  (b) Strip a leading `## For human` heading if present, using the regex `^##\s*For\s+human\s*\n+` (case-sensitive, greedy on trailing newlines). Call the result `summary_body`.
  (c) Compose the final `current-plan.md` content as: `<frontmatter (YAML)>\n## For human\n\n<summary_body>\n\n<body content read back from <plan-path>.body.tmp>`.
  (d) Write to `<plan-path>.tmp` using the Write tool.
This guarantees the assembled file contains exactly one `## For human` line, regardless of Haiku output shape.

**Step 4: Structural validation.** Invoke the deployed validator via the Bash tool:
  `python3 ~/.claude/scripts/validate_artifact.py <plan-path>.tmp`
(Filename auto-detection identifies the type as `current-plan`; the explicit `--type current-plan` flag is unnecessary.) Exit code 0 = PASS; non-zero = at least one V-01..V-07 invariant failed (stderr names which). The validator is deterministic and side-effect-free.

**Step 5: Retry / English-fallback (failure-class-aware).** Differentiate the retry path by which step failed:

  - **Step 2 failure path (Agent dispatch FAILS OR empty `summary_raw`):**
    (a) Re-run ONLY Step 2 once (re-spawn the Haiku Agent subagent against the unchanged `<plan-path>.body.tmp`). The prompt directive pins temperature 0.0; re-running may catch transient dispatch errors. Do NOT re-run Step 1.
    (b) If the re-run ALSO fails: fall back to v2-style single-file write (see fallback below).

  - **Step 4 validation failure path (non-zero validator exit):** parse validator stderr (each line begins `FAIL V-NN: ...`) to identify the failing invariant ID(s):
    (a) **V-06 / V-07 failures:** body is fine; summary/composition is wrong. Re-run Steps 2–4 once.
    (b) **V-02 / V-03 / V-05 failures:** re-run Steps 1–4 once with the explicit body-discipline instruction prepended: "all standard sections required, no inventions, summary 5–8 lines, do not output any heading".
    (c) **V-01 / V-04 failures:** treat as body issues (re-run Steps 1–4).

  - **English-fallback (after retry also fails):** fall back to v2-style single-file write — regenerate the body using terse-rubric only (no format-kit, no `## For human` block). Write to `<plan-path>.tmp` directly. Skip Step 4 validation. Log a `format-kit-skipped` warning to the user with the failing invariant ID(s). Clean up body.tmp: `(rm -f <plan-path>.body.tmp 2>/dev/null || true)`. The artifact still gets written; the safety property holds.

**Step 6: Atomic rename.** Move `<plan-path>.tmp` to `<plan-path>` (overwriting any prior `current-plan.md`). Clean up both temp files. Use the Bash tool: `mv <plan-path>.tmp <plan-path>; (rm -f <plan-path>.body.tmp <plan-path>.tmp 2>/dev/null || true)`.

The final file at `<plan-path>` IS what `/critic`, `/implement`, `/review`, `/gate` will read. Do NOT write a `.original.md` side-file.

## Task subfolder naming

Derive a descriptive kebab-case name from the task. Ask the user if not obvious. Examples: `auth-refactor`, `payment-migration`, `api-v2-endpoints`.

## Save session state

Before finishing, write or update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` with:
- **Status:** `in_progress`
- **Current stage:** `plan`
- **Completed in this session:** what the plan covers
- **Unfinished work:** anything deferred or not yet planned
- **Decisions made:** key choices and their rationale

This is what `/end_of_day` reads to consolidate the day's work. Without it, this session is invisible to the daily rollup.

## Important behaviors

- **Be concrete.** File paths, function signatures, data shapes. "Add a new service" is not a task. "Create `src/services/payment.service.ts` implementing `processRefund(orderId: string): Promise<RefundResult>`" is a task.
- **Read actual code.** Verify your assumptions against the codebase. Don't guess at file structures or API shapes.
- **Integration points get extra scrutiny.** Most production incidents come from integration failures. Trace data flows end-to-end.
- **Each task is independently reviewable.** No mega-tasks. Each produces a testable, reviewable unit of work.
- **De-risk upfront.** If something is uncertain, the plan should include a spike/POC as an early task, not hand-wave over it.
- **Testing is not optional.** Every task that touches code should have corresponding test expectations.
