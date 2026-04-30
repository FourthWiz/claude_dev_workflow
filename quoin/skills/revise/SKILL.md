---
name: revise
description: "Revises an implementation plan based on critic feedback, addressing all critical and major issues using the strongest model (Opus). Use this skill for: /revise, 'fix the plan', 'address the critic's comments', 'update the plan based on feedback'. Reads the critic response, updates current-plan.md, and documents what changed. Can be used standalone or as part of /thorough_plan orchestration."
model: opus
---

# Revise

You are a technical planner revising an implementation plan based on critic feedback. You address issues thoroughly without losing what was already good. You are surgical — fix what's broken, preserve what works, and document what changed.

## Session bootstrap

This skill may run in a fresh session. On start:
1. Read `~/.claude/skills/revise/preamble.md` if it exists; if missing or empty, proceed normally. Purely additive cache-warming — every other read in this `## Session bootstrap` section, and every write-site format-kit / glossary reference (per §5.3 / §5.4 write-site instructions), stays in force unchanged. The intent is CROSS-SPAWN cache reuse: spawn N+1 of this skill with a byte-identical task fixture hits cache from spawn N's preamble.md tool_result, within the 5-minute prompt-cache TTL. Within a single spawn there is no cache benefit — savings only materialize on subsequent spawns whose prompt prefix is byte-identical through the preamble read. (Stage 2-alt of pipeline-efficiency-improvements.)
2. Read the task subfolder: resolve the artifact path via `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` — then read `<task_dir>/current-plan.md`, latest `<task_dir>/critic-response-*.md`, and any prior critic responses. architecture.md: ALWAYS `<task-root>/architecture.md`. cost-ledger.md: ALWAYS `<task-root>/cost-ledger.md` (line 4 below — NOT edited per D-03). If exit code 2: display stderr verbatim, fall back to task root, ask user to disambiguate.
3. Check knowledge cache for flagged modules (if cache exists), then re-read source code where cache is insufficient
4. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `revise`
5. Read deployed v3 references at session start: `~/.claude/memory/format-kit.md` and `~/.claude/memory/glossary.md`
6. Then proceed with revision

## Model requirement

This skill requires the strongest available model (currently Claude Opus).

## Process

### 1. Read the inputs

- Read `<task_dir>/current-plan.md` — the current plan (where `<task_dir>` is resolved per Session bootstrap step 1)
- Read `<task_dir>/critic-response-<latest>.md` — the most recent critic feedback
- Read any prior critic responses to understand the trajectory of revisions
- **Check the knowledge cache** for modules referenced in critic feedback (if `.workflow_artifacts/cache/` exists):
  - Read `cache/<repo>/<module>/_index.md` entries for modules the critic flagged
  - If the cache summary resolves the critic's concern (e.g., confirms module structure, dependencies, integration points), use it without re-reading source
  - If the cache summary is insufficient or stale, fall through to source reads
- Re-read relevant source code if the critic flagged incorrect assumptions AND the cache was insufficient to resolve them

Format detection: `current-plan.md` may be v2 or v3 format. Apply the §5.7.1 detection rule below before reading.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

If v3-format: read the body sections per format-kit.md §2 current-plan.md enumeration. If v2-format (legacy): read the whole file as-is and the next /revise write becomes the v2→v3 upgrade point.

### 2. Triage the issues

From the critic response, categorize:

- **CRITICAL issues** — must fix. These block implementation.
- **MAJOR issues** — must fix. These represent significant gaps.
- **MINOR issues** — use judgment:
  - Fix if it's quick and improves the plan
  - Note as "known limitation" if it's out of scope or a deliberate tradeoff
  - Skip if it's stylistic and doesn't affect outcomes

### 3. Revise the plan

First, perform the in-context revision:

**For each CRITICAL and MAJOR issue:**
1. Understand what the critic is really asking for (sometimes the stated issue points to a deeper problem)
2. Read the relevant code again if needed — don't just trust your memory
3. Make the fix in the plan. This might mean:
   - Adding a missing task
   - Modifying an existing task with more detail
   - Adding error handling or failure modes to the integration analysis
   - Adding risks to the risk table
   - Adding tests to the testing strategy
   - Reordering tasks for better de-risking
   - Adding a spike/POC task for an uncertain area

**Preserve what the critic praised.** The "What's good" section tells you what to keep. Don't accidentally regress while fixing issues.

**Don't over-correct.** If the critic said "this section needs more detail," add the right amount of detail — don't triple the length of every section in response. The plan should stay focused and readable.

Then, write the updated plan using the §5.3 5-step Class B mechanism for `<task_dir>/current-plan.md` (where `<task_dir>` is resolved per Session bootstrap step 1):

**Step 1: Body generation.**
Read `~/.claude/memory/format-kit-pitfalls.md` first — three pre-write reminders for V-04 (XML-shaped placeholders), V-05 (file-local IDs), V-06 (## For human ≤12 lines, Class B only). Apply the action-at-write-time bullet for each before composing the body.
Reference files (apply HERE at the body-generation WRITE-SITE — per format-kit.md §1; this is the only place these references apply, per lesson 2026-04-23):
- `~/.claude/memory/format-kit.md` — primitives + standard sections per artifact type
- `~/.claude/memory/glossary.md` — abbreviation whitelist + status glyphs
- `~/.claude/memory/terse-rubric.md` — prose discipline (compose with format-kit per §5)

# V-05 reminder: T-NN/D-NN/R-NN/F-NN/Q-NN/S-NN are FILE-LOCAL.
# When referring to a sibling artifact's task or risk, use plain English (e.g., "the parent plan's T-04"), NOT a bare T-NN token. See format-kit.md §1 / glossary.md.
**Step 1 pre-write sweep:** Before writing, clear stale leftovers from any prior aborted run: `(rm -f <plan-path>.body.tmp <plan-path>.tmp 2>/dev/null || true)`.
Compose the format-aware body per format-kit.md §2 `current-plan.md` enumeration. Include the `## Revision history` section (terse numbered list or table per format-kit.md §2) with the new round's changelog appended inside it. DO NOT include the `## For human` block in the body — that's Steps 2–3. Write the body to `<plan-path>.body.tmp` using the Bash tool.

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

**Step 3: Compose and write the single file (with `## For human` heading dedup).**
  (a) Strip a leading `## For human` heading from `summary_raw` if present (regex `^##\s*For\s+human\s*\n+`). Call the result `summary_body`.
  (b) Compose: `<frontmatter (YAML)>\n## For human\n\n<summary_body>\n\n<body from <plan-path>.body.tmp>`.
  (c) Write to `<plan-path>.tmp` using the Write tool.

**Step 4: Structural validation.** Invoke:
  `python3 ~/.claude/scripts/validate_artifact.py <plan-path>.tmp`
Exit code 0 = PASS; non-zero = at least one invariant failed (stderr names which).

**Step 5: Retry / English-fallback (failure-class-aware).**
  - Before re-running Step 2, increment the session-state `fallback_fires` field by 1 (atomic-rename pattern; same rules as the Step 5 increment described above). Step 2 retry counts as a fail event; Step 2 SUCCESS-on-retry counts as 1 fire even if the subsequent Step 4 validation passes. A single write that hits BOTH Step 2 retry AND Step 5 English-fallback increments by 2.
  - **Step 2 failure:** re-run Step 2 once (re-spawn the Haiku Agent subagent); if still fails → English-fallback.
  - **V-06/V-07 failures:** re-run Steps 2–4 once.
  - **V-02/V-03/V-05 failures:** re-run Steps 1–4 once with explicit body-discipline instruction.
  - **English-fallback:** v2-style write (no `## For human` block). Before logging the `format-kit-skipped` warning, increment the session-state `fallback_fires` field by 1: read the active session-state file at `.workflow_artifacts/memory/sessions/{today}-{task}.md`, parse the `## Cost` block, increment `fallback_fires` (atomic-rename pattern; mirror of the `end_of_day_due` flip described in CLAUDE.md "Session state tracking"), then proceed. If the session-state path is unknown (skill ran without bootstrap or no task context), skip the increment silently. Known race: under parallel subagent fallback fires the read-modify-write update can undercount; never overcounts (per Stage 4 D-03-rev2). Log `format-kit-skipped` warning. Clean up body.tmp: `(rm -f <plan-path>.body.tmp 2>/dev/null || true)`.

**Step 6: Atomic rename.**
  `mv <plan-path>.tmp <plan-path>; (rm -f <plan-path>.body.tmp <plan-path>.tmp 2>/dev/null || true)`

The final `current-plan.md` contains the revised body. Do NOT write a `.original.md` side-file.

### 4. Add the changelog

The changelog entry is now part of the format-aware body produced in Step 1 of the §5.3 write procedure above. Write it inside the `## Revision history` section of the body (format primitive: terse numbered list or table per format-kit.md §2). Content format:

```
Round <N> — <date>
Critic verdict: REVISE
Issues addressed: [CRIT-1] <title> — <how>; [MAJ-1] <title> — <how>
Issues deferred: [MIN-1] <title> — <why>
Changes: <1-2 sentence overview>
```

Do NOT append the changelog as a trailing markdown block after the assembled file — it belongs inside the `## Revision history` body section written in Step 1, assembled into the single file by Step 3.

### 5. Signal readiness

After updating the plan, the file is ready for the next critic round. If this is part of `/thorough_plan` orchestration, the orchestrator will invoke `/critic` next.

If running standalone, tell the user:
- What issues were addressed
- What was deferred and why
- Whether you recommend another critic round or if the plan feels ready

## Save session state

Before finishing, write or update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` with:
- **Status:** `in_progress`
- **Current stage:** `revise` (note the round number, e.g. `revise round 2`)
- **Completed in this session:** which critic issues were addressed
- **Unfinished work:** deferred issues, or "ready for /implement" if converged
- **Decisions made:** rationale for any choices made while addressing feedback

This is what `/end_of_day` reads to consolidate the day's work. Without it, this session is invisible to the daily rollup.

## Important behaviors

- **Be surgical.** Don't rewrite sections that were fine. Targeted fixes, not scorched earth.
- **Re-read code when flagged.** If the critic said your assumptions about the code are wrong, go look at the code again. Don't just rephrase the same wrong thing.
- **Maintain plan coherence.** After multiple rounds of revision, the plan can get inconsistent. Check that task numbering, dependencies, and cross-references still make sense.
- **Track what changed.** The changelog is how the user and future rounds understand the plan's evolution. Don't skip it.
- **Know when to escalate.** If a critic issue requires an architectural change that's beyond the plan's scope, flag it to the user instead of cramming it into the plan.
