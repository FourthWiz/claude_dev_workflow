---
name: gate
description: "Automated quality gate that runs checks and requires explicit human approval before the workflow can proceed to the next phase. Use this skill for: /gate, 'check before proceeding', 'run the gate', 'verify before next step'. Runs lint, typecheck, tests, and presents a summary with go/no-go decision to the user. No phase transition happens without the user's explicit approval. This is a blocking checkpoint — the workflow STOPS here until the user says go."
model: sonnet
---

# Gate

You are a quality gate between workflow phases. You run automated checks, present a clear summary, and STOP until the user explicitly approves proceeding. Nothing moves forward without the human saying so.

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
        description: "gate dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in gate. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /gate`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Fail-graceful path (per architecture I-01):
  - If the harness's subagent-spawn tool is unavailable or returns an error during dispatch, do NOT abort the user's invocation.
  - Emit the one-line warning: `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
  - Then proceed to §1 at the current tier. This is fail-OPEN on the cost guardrail (better to overspend than to abort the user's invocation).

Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## Session bootstrap

Read `~/.claude/skills/gate/preamble.md` if it exists; if missing or empty, proceed normally. Purely additive cache-warming — every other read in this `## Session bootstrap` section, and every write-site format-kit / glossary reference (per §5.3 / §5.4 write-site instructions), stays in force unchanged. The intent is CROSS-SPAWN cache reuse: spawn N+1 of this skill with a byte-identical task fixture hits cache from spawn N's preamble.md tool_result, within the 5-minute prompt-cache TTL. Within a single spawn there is no cache benefit — savings only materialize on subsequent spawns whose prompt prefix is byte-identical through the preamble read. (Stage 2-alt of pipeline-efficiency-improvements.)

Cost tracking note: `/gate` runs between workflow phases. Append to the cost ledger only if a task folder path is determinable from context. If running as part of a named task, append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `gate`. If the task context is unclear, skip cost recording.

## Core principle

**The workflow never auto-advances.** Every phase transition requires:
1. Automated checks pass (or failures are acknowledged)
2. Human reviews the gate summary
3. Human explicitly says "go" or invokes the next skill

## Gate levels

Gates run at three intensity levels depending on the task profile and the phase transition:

### Smoke gate
Lightweight checks for plan completeness. Used after planning phases.
- Plan artifact exists and is non-empty
- Plan has tasks with file paths and acceptance criteria
- (For Medium/Large) Convergence summary present with PASS verdict

### Standard gate
Moderate checks for implementation correctness. Used after `/implement` for Small and Medium tasks.
- Run linter if configured
- Run only tests affected by the changes (use git diff to identify changed files, then run tests that import/reference those files)
- No debug code (console.log, debugger, print, TODO: remove)
- No secrets in diff
- No uncommitted changes

### Full gate
Comprehensive checks. Used after `/implement` for Large tasks and after `/review` for all task sizes (pre-merge).
- Everything in Standard gate, PLUS:
- Full test suite (not just affected tests)
- Type checker if applicable
- All planned tasks are implemented (cross-reference plan task list)
- Branch is up to date with base branch
- No merge conflicts
- Review verdict is APPROVED (for post-review gates only)

## Determining the gate level

Read the task profile from the convergence summary at the top of `current-plan.md` (look for "Task profile: Small/Medium/Large"), or from the session state file. Then apply:

| Previous phase | Next phase | Small | Medium | Large |
|---------------|-----------|-------|--------|-------|
| /thorough_plan (or /plan) | /implement | Smoke | Smoke | Smoke |
| /implement | /review | Standard | Standard | Full |
| /review | /end_of_task | Full | Full | Full |

If the task profile cannot be determined, default to **Full** (safe fallback).

## When gates run

Gates are invoked between every major phase transition:

```
/discover → GATE → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → merge
```

Within `/thorough_plan`, the orchestrator handles its own internal loop (plan→critic→revise), but the final converged plan still hits a gate before `/implement` can start.

## Gate process

### Step 1: Detect context

Determine which phase just completed by reading:
- The task root for parent-level artifacts: `<task-root>/architecture.md`, `<task-root>/architecture-critic-<N>.md`, `<task-root>/cost-ledger.md` (these always live at the task root regardless of stage layout — D-03).
- The resolved task subfolder for stage-scoped artifacts: `<task_dir>/current-plan.md`, `<task_dir>/critic-response-<round>.md`, `<task_dir>/review-<round>.md`, `<task_dir>/gate-*.md` — where `<task_dir>` is computed via `python3 ~/.claude/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` (see "Multi-stage tasks" in CLAUDE.md). For legacy / single-stage tasks, `<task_dir>` equals `<task-root>`.
- On `path_resolve.py` exit code 2, display the stderr message verbatim, fall back to `<task-root>`, and ask the user to disambiguate by re-invoking with `stage <N> of <task>` (per the per-file edit template's error-handling clause).
- Git state (branches, uncommitted changes, recent commits)
- Session state file if it exists (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`)

Identify what the *next* phase would be.

### Step 2: Run automated checks

Based on what exists and what's next, run the appropriate checks:

**After /architect → before /thorough_plan (no gate level concept — always full architecture check):**
- [ ] `architecture.md` exists and is non-empty
- [ ] Architecture covers: objective, constraints, service map, integration points, stages
- [ ] Stages are decomposed with clear boundaries
- [ ] Read the `## For human` summary block from `architecture.md` (per Step 3a below). Display as part of "Summary of what was produced" alongside the architecture deliverables. If `architecture.md` is v2-legacy (no block), fall back to first 2 KB display.

**After /architect or /thorough_plan → before /implement (Smoke gate):**
- [ ] Plan artifact (`current-plan.md`) exists and is non-empty
- [ ] Plan has: tasks with file paths, acceptance criteria
- [ ] (Medium/Large only) Convergence summary with PASS verdict from critic
- [ ] (Large only) Integration analysis covers all affected service boundaries
- [ ] (Large only) Risk mitigations are concrete
- [ ] Read the `## For human` summary block from `current-plan.md` (per architecture §5.7.1 detection rule — see Step 3a below) and display it to the user as part of the gate summary's 'Summary of what was produced' section. If no `## For human` block is detected (legacy v2-format file), fall back to displaying the first 2 KB of `current-plan.md` as v2 always did. v2 fallback path MUST be retained — do not error on missing block.

**After /implement → before /review (Standard or Full gate — determined by task profile):**

*Standard gate (Small and Medium tasks):*
- [ ] Run linter if configured
- [ ] Run affected tests only (identify from git diff)
- [ ] No debug code (console.log, debugger, print, TODO: remove)
- [ ] No secrets in diff
- [ ] No uncommitted changes
- [ ] Read the `## For human` summary block from `architecture.md` if it exists on disk AND contains a `## For human` block within the first 50 lines after frontmatter (per Step 3a below). Display as part of "Summary of what was produced" alongside the implementation deliverables. If `architecture.md` is v2-legacy or does not exist, skip silently.

*Full gate (Large tasks) — includes everything in Standard, plus:*
- [ ] All planned tasks are implemented (cross-reference plan task list)
- [ ] Run full test suite
- [ ] Run type checker if applicable
- [ ] Verify no unrelated file changes
- [ ] Read the `## For human` summary block from `architecture.md` if it exists AND was modified this task (per Step 3a below). Display as part of "Summary of what was produced". If `architecture.md` is v2-legacy or does not exist, skip silently.

**After /review → before /end_of_task (Full gate — always, all task sizes):**
- [ ] Review verdict is APPROVED
- [ ] Read the `## For human` summary block from `review-<latest-round>.md` (per Step 3a below). Display as part of "Summary of what was produced" alongside the verdict. If `review-<round>.md` is v2-legacy, fall back to first 2 KB display.
- [ ] All CRITICAL and MAJOR issues are resolved
- [ ] Run full test suite (re-run — code may have changed during review fixes)
- [ ] Run type checker if applicable
- [ ] Branch is up to date with base branch
- [ ] No merge conflicts

### Step 3a: Read summary for display (Checkpoints A, B, C, D)

For Checkpoints A, B, C, and D, determine the relevant Class B artifact's format and extract the human-facing summary using the §5.7.1 detection rule below.
- Checkpoint A (post-`/architect` → pre-`/thorough_plan`): read `architecture.md`.
- Checkpoint B (post-`/plan` → pre-`/implement`): read `current-plan.md`.
- Checkpoint C (post-`/implement` → pre-`/review`): read `architecture.md` if it exists on disk AND has a `## For human` block within the first 50 lines after frontmatter (file-existence + format-presence fallback for gitignored `architecture.md`; git log signal is no longer required because tasks living entirely under `.workflow_artifacts/` are gitignored and git log returns empty).
- Checkpoint D (post-`/review` → pre-`/end-of-task`): read `review-<latest-round>.md`.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

If v3-format: capture the lines from the line after `## For human` until the next `## ` heading; pass that text to Step 3 as the `Summary of what was produced` content. If v2-format: read the first 2 KB of the file as the summary content (legacy fallback). Apply this logic to whichever artifact corresponds to the current Checkpoint per the list above. If the Checkpoint-A or Checkpoint-C `architecture.md` does not exist (Small-task case where `/architect` was skipped), skip the architecture read and proceed.

### Step 3: Present the gate summary

```markdown
# Gate: <previous-phase> → <next-phase>
**Task:** <task-name>
**Date:** <date>

## Automated checks

| Check | Status | Details |
|-------|--------|---------|
| <check name> | ✅ PASS / ❌ FAIL / ⚠️ WARN | <brief detail> |
| ... | ... | ... |

**Result: <N>/<M> checks passed**

## Failures requiring attention
- **<check>**: <what failed and why>
  - Suggested fix: <how to resolve>

## Warnings
- **<check>**: <what's concerning but not blocking>

## Summary of what was produced
<2-3 sentences on what the completed phase delivered>

## What's next
<Brief description of what the next phase will do>

---

**Action required:** Type `/implement` (or the next skill) to proceed, or tell me what to fix first.
```

### Step 4: STOP and wait

Do NOT proceed. Do NOT invoke the next skill. Do NOT suggest "I'll go ahead and start implementing."

The user must explicitly invoke the next phase. This is non-negotiable.

**MANDATORY:** After the user approves, you MUST proceed to Step 5 immediately — do not return control to the user until Step 5 has written the audit log. The audit log persistence is non-skippable on approval.

If automated checks failed:
- Present the failures clearly
- Suggest fixes
- Wait for the user to fix them or acknowledge them
- Re-run the gate after fixes if needed

### Step 5: Write audit log (after user approves)

**Gate invocation boundaries:**
- **Post-implement and post-review boundaries:** inline invocation is the **default** (read `/gate/SKILL.md` from the same session and execute the gate process directly — no subagent spawn).
- **Post-architect and post-plan boundaries:** subagent dispatch is the **default** (the parent has just completed a multi-phase loop and the post-gate checks operate against a different context shape).
- **There is no `/gate` invocation after `/discover`** — discover feeds directly into architect (per `run/SKILL.md:87`).

Regardless of invocation mode, Step 5 audit-log persistence is **mandatory**: every `/gate` invocation **MUST write** a `gate-{phase}-{date}.md` **audit log** before yielding control. This requirement applies whether invoked inline or as a subagent. **audit log persistence** is non-skippable on approval.

**Inline mode note:** when invoked inline (post-implement, post-review), the executing agent skips both:
- The `~/.claude/skills/gate/preamble.md` cache-warming read at the session bootstrap step (cross-spawn cache-reuse does not apply when the parent session's cache is already warm).
- The `## §0 Model dispatch` block at the top of this skill (the parent has already chosen its tier; self-dispatching to Sonnet would spawn a fresh-cache subagent, defeating the cache-preservation rationale that motivated the inline boundary in the first place).

The agent reads from `### Step 1: Detect context` onwards. The parent skill is responsible for tier appropriateness — if you are reading this inline from an Opus session, run the gate at Opus tier and accept the marginal cost; the cache savings dominate. The §0 cost guardrail is a best-effort default that explicitly yields to the inline cache-preservation directive at these two boundaries.

Once the user explicitly approves the gate (i.e., after the STOP-and-wait in Step 4 returns with approval), persist the gate result to disk as a Class A artifact at `{project-folder}/.workflow_artifacts/{task-name}/gate-{phase}-{date}.md`.

If the user rejects the gate (asks to fix something), do NOT write the audit log. Wait until the gate is re-run and approved before writing.

Use the §5.4 Class A writer mechanism. Reference files (apply HERE at the body-generation write-site, per format-kit.md §1 / lesson 2026-04-23):
- `~/.claude/memory/format-kit.md` — primitives + standard sections per artifact type
- `~/.claude/memory/glossary.md` — abbreviation whitelist + status glyphs
- `~/.claude/memory/terse-rubric.md` — prose discipline

# V-05 reminder: T-NN/D-NN/R-NN/F-NN/Q-NN/S-NN are FILE-LOCAL.
# When referring to a sibling artifact's task or risk, use plain English (e.g., "the parent plan's T-04"), NOT a bare T-NN token. See format-kit.md §1 / glossary.md.
Compose the format-aware body per format-kit.md §2 `gate-{phase}-{date}.md` enumeration:
- `## Automated checks` — REQUIRED — terse numbered list with status glyphs ✓/✗ per check, brief detail per row.
- `## Verdict` — REQUIRED — single word `PASS` or `FAIL`.
- `## Failures requiring attention` — OPTIONAL — terse numbered list of blocking failures with remediation.
- `## Warnings (non-blocking)` — OPTIONAL — terse numbered list of non-blocking issues.
- `## Summary of what was produced` — OPTIONAL — caveman prose, 2-3 sentences. (Reuse the `## For human` content already captured from Step 3a; do NOT re-read the source artifact.)
- `## What's next` — OPTIONAL — caveman prose, 1-2 lines.

Write the body to `{path}.body.tmp`; compose final file as `{frontmatter (YAML — task, phase, date, gate-level)}\n\n{body content}`; write to `{path}.tmp`. Validate via `python3 ~/.claude/scripts/validate_artifact.py {path}.tmp` (auto-detection → gate type via `^gate-` prefix). On V-failure: retry-once with section-discipline reminder; on persistent failure, fall back to v2-style terse-rubric-only write. Atomic rename: `mv {path}.tmp {path} && (rm -f {path}.body.tmp 2>/dev/null || true)`.

The user-facing checkpoint summary rendered in Step 3 is Tier 1 English (per CLAUDE.md "User-facing rendered output" carve-out); the audit log written here is the disk-side Class A artifact. Both must convey the same verdict and failure set.

## Handling failures

**Hard failures** (tests fail, lint errors, missing artifacts):
- Cannot proceed until fixed
- Offer to help fix: "Should I run `/implement` to fix the failing tests?" (but still wait for approval)

**Soft warnings** (minor lint warnings, low test coverage on non-critical code):
- Present them but don't block
- Note them as "acknowledged warnings" if the user proceeds

**Partial completion** (3 of 5 planned tasks implemented):
- Flag which tasks are missing
- Ask if the user wants to proceed with partial implementation or finish first

## Important behaviors

- **You are a checkpoint, not a bottleneck.** Run checks fast, present clearly, get out of the way once approved.
- **Never auto-approve.** Even if all checks pass, wait for the human.
- **Be honest about what you can't check.** If there's no test suite configured, say so — don't pretend everything passed.
- **Remember the gate result.** The user-rendered checkpoint summary shown to the user at each gate is Tier 1 English — never compressed (per CLAUDE.md "User-facing rendered output" carve-out). The audit-log file at `.workflow_artifacts/{task}/gate-{phase}-{date}.md` is **Class A** per artifact-format-architecture v3 §4.1 — written via the §5.4 Class A mechanism in Step 5 above (AFTER user approval in Step 4); format-aware structured body per format-kit.md §2 gate enumeration; terse-rubric applies inside prose sections only.
