---
name: gate
description: "Automated quality gate that runs checks and requires explicit human approval before the workflow can proceed to the next phase. Use this skill for: /gate, 'check before proceeding', 'run the gate', 'verify before next step'. Runs lint, typecheck, tests, and presents a summary with go/no-go decision to the user. No phase transition happens without the user's explicit approval. This is a blocking checkpoint — the workflow STOPS here until the user says go."
model: sonnet
---

# Gate

*Portable intent doc: `quoin/core/skills/gate.md`*

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
<!-- §0-1m-decide-begin -->
Pre-dispatch 1M check (IVG-90 Layer 1+2):
  - Run: python3 __QUOIN_HOME__/scripts/dispatch_config.py --decide --tier <declared_tier> --verbose
    where <declared_tier> is the tier declared for this skill (e.g. "sonnet" or "haiku",
    as shown in the dispatched-tier line immediately above).
  - If the command returns "safe-path" on line 1:
      Read the reason token from line 2 (config|cache|probe).
      Emit the one-line advisory (verbatim, substituting <reason> with the line-2 token):
        `[quoin: 1M-unsafe declared-tier per <reason>; running SAFE PATH without dispatch]`
      Then proceed to §1/§0c at the current tier (treat as if [no-redispatch] were present).
      Do NOT call the Agent dispatch. Do NOT call AskUserQuestion.
  - If the command returns "dispatch" on line 1, OR if the script is missing / errors:
      Continue to the Agent dispatch call below (today's path — fail-OPEN).
<!-- §0-1m-decide-end -->
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "gate dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent.
<!-- §0-1m-cachewrite-begin -->
      Cache the safe result (best-effort):
        python3 __QUOIN_HOME__/scripts/dispatch_config.py --write-cache --tier <declared_tier> --result safe
      (Fail-OPEN: if the script errors or is missing, silently skip and continue.)
<!-- §0-1m-cachewrite-end -->
      Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in gate. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /gate`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

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

  - 1M-credit-class: if the error text contains the substring
      `Usage credits required for 1M context`:
      This is the 1M-context credit mismatch (IVG-89). The parent session carries
      the `context-1m-2025-08-07` beta header which propagates to all subagent calls;
      the declared-tier model lacks 1M credits. Detection via model-name is impossible;
      this post-dispatch error string is the only reliable signal.
      Emit (verbatim):
        `[quoin: 1M-context credit mismatch on <tier> subagent dispatch; proceeding in-session at parent tier — run /model to switch this session to standard context for a permanent fix]`
<!-- §0-1m-cachewrite-begin -->
      Cache the unsafe result (best-effort):
        python3 __QUOIN_HOME__/scripts/dispatch_config.py --write-cache --tier <declared_tier> --result unsafe
      (Fail-OPEN: if the script errors or is missing, silently skip and continue.)
<!-- §0-1m-cachewrite-end -->
      Then proceed to §1 at the current tier (treat as if `[no-redispatch]` were present).
      Do NOT retry the Agent dispatch. Do NOT call AskUserQuestion.


  - Worktree-class branch:
      Autonomous fail-OPEN (checked FIRST): if the incoming prompt carries
      the `[autonomous]` sentinel, then on this worktree-class dispatch
      error, proceed at current tier fail-OPEN and do NOT call
      AskUserQuestion — skip straight to the Other-class path below (it
      emits the bare warning and the `error-class=worktree` classification
      line), then proceed to §1 at the current tier. Otherwise (no
      `[autonomous]` sentinel — non-autonomous behavior unchanged):
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
Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

## §0‴ Minimum-tier guard (execute after §0 — before any §0-sidecar block and the skill body)
This skill is declared model: "sonnet". If the executing agent is running on a model
strictly CHEAPER than sonnet, it silently up-dispatches to a Sonnet subagent (mirrors §0 down-dispatch).

<!-- §0tripleprime-begin -->
Detection:
  - Read your current model from system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus. declared_tier = sonnet.
  - Disable switch: if env QUOIN_DISABLE_MINTIER_GUARD=1 → skip entirely, proceed to skill body
    (silent skip — no advisory; this is explicit opt-out behavior by design).
  - Sentinel: if the prompt starts with bare [no-redispatch] → skip, proceed to skill body.
  - Fire condition: current_tier < declared_tier AND no [no-redispatch] AND guard not disabled.
  - Recursion: counter form `[no-redispatch:N]` (N≥2) never reaches this block — §0 (earlier in this file) aborts on N≥2 before any §0‴ tool call.

On fire (happy path — silent up-dispatch):
  spawn an Agent subagent:
    model: "sonnet"
    description: "gate — min-tier up-dispatch"
    prompt: "[no-redispatch]\n<original user input verbatim>"
  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path (fires only when Agent dispatch fails):
  Classify the error text BEFORE proceeding:

  - Autonomous-class (checked FIRST, before 1M-credit or generic classification): if the
    incoming prompt carries the `[autonomous]` sentinel, then on ANY §0‴ dispatch-failure or
    1M-context-credit error, proceed at current tier fail-OPEN and DO NOT call `AskUserQuestion`
    — skip the 1M-credit-class and generic branches below entirely. Print
    `[quoin-mintier-autonomous: §0‴ dispatch failed; proceeding fail-OPEN at current tier]` and
    proceed to skill body (treat as bare [no-redispatch]).

  - 1M-credit-class: if error text contains `Usage credits required for 1M context`:
      Issue AskUserQuestion:
        Question: "§0‴ up-dispatch to sonnet failed with a 1M-context credit mismatch for /gate.
        The parent session carries the 1M-context beta header; Sonnet lacks 1M credits. How would you like to proceed?"
        Header: "1M credit mismatch"
        multiSelect: false
        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch to a standard-context
          model (e.g., /model sonnet), then re-invoke /gate."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the up-dispatch this once. /gate runs in the current session
          (below Sonnet, but works). Emits a one-line advisory."
      On Option 1: print `[quoin-mintier: 1M-context credit mismatch; abort per user choice —
      switch with /model and re-invoke /gate]` and STOP.
      On Option 2: print `[quoin-mintier: 1M-context credit mismatch on sonnet up-dispatch;
      proceeding in-session at parent tier — run /model to switch to standard context]`
      and proceed to skill body (treat as bare [no-redispatch]).

  - Any other error: Issue AskUserQuestion (labels verbatim — drift relies on equality):
      Question: "/gate requires Sonnet but this session is below Sonnet. Auto-dispatch to Sonnet failed. How would you like to proceed?"
      Header: "Min-tier"
      multiSelect: false
      Option 1:
        label: "Abort — run from a Sonnet session"
        description: "Stop here. Switch the session to Sonnet (/model sonnet) and re-invoke /gate."
      Option 2:
        label: "Proceed at current tier (under-powered)"
        description: "Run /gate on the current cheaper model. Quality may be reduced;
        emits a one-line advisory."
    Then:
      - Option 1: print `[quoin-mintier: aborted; re-invoke /gate from a Sonnet session]` and STOP.
      - Option 2: print `[quoin-mintier: min-tier up-dispatch unavailable; proceeding at current tier per user choice]`, then proceed to skill body (treat as bare [no-redispatch]).
<!-- §0tripleprime-end -->

## Session bootstrap

Read `__QUOIN_HOME__/skills/gate/preamble.md` if it exists; if missing or empty, proceed normally. Purely additive cache-warming — every other read in this `## Session bootstrap` section, and every write-site format-kit / glossary reference (per §5.3 / §5.4 write-site instructions), stays in force unchanged. The intent is CROSS-SPAWN cache reuse: spawn N+1 of this skill with a byte-identical task fixture hits cache from spawn N's preamble.md tool_result, within the 5-minute prompt-cache TTL. Within a single spawn there is no cache benefit — savings only materialize on subsequent spawns whose prompt prefix is byte-identical through the preamble read. (Stage 2-alt of pipeline-efficiency-improvements.)

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
- Run the affected-area test suite (BLOCKING hard precondition — see the `Affected-area test suite` checklist item in the post-implement Standard gate block below for invocation details and result mapping)
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
| /specify | /architect | (spec doc gate — no test level) | (spec doc gate) | (spec doc gate) |
| /thorough_plan (or /plan) | /implement | Smoke | Smoke | Smoke |
| /implement | /review | Standard | Standard | Full |
| /review | /end_of_task | Full | Full | Full |

If the task profile cannot be determined, default to **Full** (safe fallback).

## When gates run

Gates are invoked between every major phase transition:

```
/discover → /specify → GATE → /architect → GATE → /thorough_plan → GATE → /implement → GATE → /review → GATE → merge
```

Within `/thorough_plan`, the orchestrator handles its own internal loop (plan→critic→revise), but the final converged plan still hits a gate before `/implement` can start.

## Gate process

### Step 1: Detect context

Determine which phase just completed by reading:
- The task root for parent-level artifacts: `<task-root>/spec.md`, `<task-root>/architecture.md`, `<task-root>/architecture-critic-<N>.md`, `<task-root>/cost-ledger.md` (these always live at the task root regardless of stage layout — D-03). `spec.md` is read-if-exists: a fresh `spec.md` with no `architecture.md` yet present indicates the specify→architect phase boundary.
- The resolved task subfolder for stage-scoped artifacts: `<task_dir>/current-plan.md`, `<task_dir>/critic-response-<round>.md`, `<task_dir>/review-<round>.md`, `<task_dir>/gate-*.md` — where `<task_dir>` is computed via `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` (see "Multi-stage tasks" in CLAUDE.md). For legacy / single-stage tasks, `<task_dir>` equals `<task-root>`.
- On `path_resolve.py` exit code 2, display the stderr message verbatim, fall back to `<task-root>`, and ask the user to disambiguate by re-invoking with `stage <N> of <task>` (per the per-file edit template's error-handling clause).
- Git state (branches, uncommitted changes, recent commits)
- Session state file if it exists (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`)

Identify what the *next* phase would be.

### Step 2: Run automated checks

Based on what exists and what's next, run the appropriate checks:

**After /specify → before /architect (spec gate — no gate level concept — always full spec check):**
- [ ] `spec.md` exists and is non-empty
- [ ] spec.md has the required sections (`## Context`, `## Acceptance criteria`)
- [ ] Read spec.md for display (spec is **Class A** — NO `## For human` block; display the `## Acceptance criteria` section, or the first 2 KB, as the "Summary of what was produced").
- [ ] GRANDFATHER: if `spec.md` is ABSENT, this transition is not applicable — skip silently (never fail on a missing spec).

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
- [ ] Affected-area test suite (BLOCKING hard precondition for APPROVED): run:
  ```
  PROJECT_ROOT="$(pwd)"
  python3 __QUOIN_HOME__/scripts/affected_tests.py --project-root "$PROJECT_ROOT" --format text
  ```
  The helper resolves the git repo from `--project-root` itself (CRIT-1 fix: the outer project root is NOT a git repo; the caller does NOT run `git` directly). Result mapping:
  - exit 0 + `ran_pytest=true` → ✓ PASS: affected-area suite GREEN.
  - exit 0 + `ran_pytest=false` → ✓ PASS / N/A: no affected tests to run (docs-only changeset or clean tree — no affected tests ran). Report "N/A — no affected tests" (not "tests green").
  - exit 1 → ✗ BLOCKING FAIL: affected tests RED; verdict MUST be FAIL; gate MUST NOT pass.
  - exit 3 or 4 → ⚠️ BLOCKING-SURFACE: affected-area suite undeterminable / no affected tests found for changed `.py` sources. Surface to the user; do NOT auto-pass. The user must explicitly acknowledge before the gate can proceed (fail-CLOSED rule: detection failure does not silently green-light).
  - script missing (FileNotFoundError / not installed) → ⚠️ WARN non-blocking (fail-OPEN on absent binary only — a brand-new install lacking the script must not hard-block legacy tasks). This is the ONLY fail-OPEN carve-out; it is scoped strictly to "script binary absent", never to "script ran and could not confirm green".
- [ ] CI mirror (BLOCKING hard precondition for APPROVED when a non-Python deliverable is in the diff): run:
  ```
  PROJECT_ROOT="$(pwd)"
  python3 __QUOIN_HOME__/scripts/ci_mirror.py --project-root "$PROJECT_ROOT" --format text
  ```
  For non-Python deliverables (e.g. the `vscode-extension/` TS package) touched in the diff, this mirrors the CI job's correctness steps (compile/typecheck/lint/test). Result mapping (every exit code exactly one row):
  - exit 0 + `ran_steps=true` → ✓ PASS: CI-parity steps GREEN.
  - exit 0 + `ran_steps=false` → ✓ PASS / N/A: annotate by branching on the emitted `exit_reason` — `no-deliverable` → "N/A — no non-Python deliverable in diff"; `no-changes` → "N/A — clean tree, nothing changed".
  - exit 1 → ✗ BLOCKING FAIL: a CI-parity step is RED; verdict MUST be FAIL; gate MUST NOT pass.
  - exit 3 → ⚠️ BLOCKING-SURFACE: undeterminable (npm missing, install failed, no steps derivable, or the check disabled). Surface to the user; do NOT auto-pass. The user must explicitly acknowledge before the gate can proceed (fail-CLOSED rule: detection failure does not silently green-light).
  - exit 2 → ⚠️ WARN non-blocking (argparse/invocation error).
  - script missing (FileNotFoundError / not installed) → ⚠️ WARN non-blocking (fail-OPEN on absent binary only — a brand-new install lacking the script must not hard-block legacy tasks). This is the ONLY fail-OPEN carve-out; it is scoped strictly to "script binary absent", never to "script ran and could not confirm green".
- [ ] No debug code (console.log, debugger, print, TODO: remove)
- [ ] No secrets in diff
- [ ] No uncommitted changes
- [ ] Branch hygiene — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/branch_hygiene.py --project-root "$PROJECT_ROOT"`. Exit 1 means a repo has commits ahead of its upstream while on a protected branch (`has_task_commits: true`) — this is a **blocking FAIL** (verdict FAIL); the work is mis-placed and must be recovered before review. Exit 0 (no task commits on a protected branch, including a clean repo legitimately on main with zero ahead commits) → PASS. Exit 3 or script missing → non-blocking ⚠️ WARN ("branch hygiene undeterminable"), do not fail (fail-OPEN). (recovery recipe: `__QUOIN_HOME__/memory/branch-recovery.md`)
- [ ] Deploy drift — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/deploy_drift_check.py --project-root "$PROJECT_ROOT" --format text`. Detects deployed quoin copies that fell out of sync with source (fires only when the diff touches `quoin/**` or `src/quoin/**`). Result mapping (every exit code has exactly one row): exit 0 with `scope=out` → ✓ PASS (annotate "N/A — no quoin source touched"); exit 0 with drift==[] → ✓ PASS, annotate the checked/not-covered qualifier VERBATIM from the tool output (`checked: skills, scripts, core-scripts, memory; not covered: hooks, CLAUDE.md, settings.json, dashboard assets, QUICKSTART.md`) — do NOT compress to a bare "PASS"; exit 1 → ⚠️ **post-implement WARN** (non-blocking; reinstalling the deploy root is legitimately deferred mid-task — run `bash quoin/install.sh` before the post-review gate); exit 2 → ⚠️ WARN non-blocking (deploy drift check invocation error — undeterminable, not a signal about the source tree); exit 3 or script missing → ⚠️ WARN non-blocking (deploy drift undeterminable — fail-OPEN). Env `QUOIN_DISABLE_DEPLOY_DRIFT=1` → exit 0 (opt-out, mirrors `QUOIN_DISABLE_BRANCH_HYGIENE`).
- [ ] Nested memory roots — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/nested_root_check.py --project-root "$PROJECT_ROOT" --format text`. Detects accidental nested/duplicate `.workflow_artifacts` roots (IVG-119). Runs unconditionally (portable-core, not scope-gated). Result mapping (WARN-only, NEVER blocks at any gate phase incl. post-review): exit 0 → ✓ PASS (single canonical root); exit 1 → ⚠️ WARN non-blocking (list offending paths); exit 2 → ⚠️ WARN non-blocking (invocation error); exit 3 or script missing → ⚠️ WARN non-blocking (undeterminable — fail-OPEN). Env `QUOIN_DISABLE_NESTED_ROOT_CHECK=1` → exit 0 (opt-out).
- [ ] Read the `## For human` summary block from `architecture.md` if it exists on disk AND contains a `## For human` block within the first 50 lines after frontmatter (per Step 3a below). Display as part of "Summary of what was produced" alongside the implementation deliverables. If `architecture.md` is v2-legacy or does not exist, skip silently.

*Full gate (Large tasks) — includes everything in Standard, plus:*
- [ ] All planned tasks are implemented (cross-reference plan task list)
- [ ] Affected-area test suite (BLOCKING hard precondition — same invocation and result mapping as the Standard gate item above). The full repo suite (`pytest` whole tree) MAY carry pre-existing failures (e.g., `test_quoin_pollution_preamble.py`, `test_install_fresh_clone.py[bash]`) and is REPORTED but NON-BLOCKING for those known-baseline entries; the AFFECTED-AREA suite MUST be green and IS blocking. A red affected-area suite blocks even if the full suite is also red from known baselines.
- [ ] CI mirror (BLOCKING hard precondition — same invocation and result mapping as the Standard gate item above): run:
  ```
  PROJECT_ROOT="$(pwd)"
  python3 __QUOIN_HOME__/scripts/ci_mirror.py --project-root "$PROJECT_ROOT" --format text
  ```
  For non-Python deliverables (e.g. the `vscode-extension/` TS package) touched in the diff, this mirrors the CI job's correctness steps (compile/typecheck/lint/test). Result mapping (every exit code exactly one row):
  - exit 0 + `ran_steps=true` → ✓ PASS: CI-parity steps GREEN.
  - exit 0 + `ran_steps=false` → ✓ PASS / N/A: annotate by branching on the emitted `exit_reason` — `no-deliverable` → "N/A — no non-Python deliverable in diff"; `no-changes` → "N/A — clean tree, nothing changed".
  - exit 1 → ✗ BLOCKING FAIL: a CI-parity step is RED; verdict MUST be FAIL; gate MUST NOT pass.
  - exit 3 → ⚠️ BLOCKING-SURFACE: undeterminable (npm missing, install failed, no steps derivable, or the check disabled). Surface to the user; do NOT auto-pass. The user must explicitly acknowledge before the gate can proceed (fail-CLOSED rule: detection failure does not silently green-light).
  - exit 2 → ⚠️ WARN non-blocking (argparse/invocation error).
  - script missing (FileNotFoundError / not installed) → ⚠️ WARN non-blocking (fail-OPEN on absent binary only — a brand-new install lacking the script must not hard-block legacy tasks). This is the ONLY fail-OPEN carve-out; it is scoped strictly to "script binary absent", never to "script ran and could not confirm green".
- [ ] Run full test suite (non-blocking for known pre-existing baseline failures per IVG-66/IVG-69 — report but do not auto-fail on those specific tests; a red affected-area suite is the hard block)
- [ ] Run type checker if applicable
- [ ] Verify no unrelated file changes
- [ ] Branch hygiene — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/branch_hygiene.py --project-root "$PROJECT_ROOT"`. Exit 1 means a repo has commits ahead of its upstream while on a protected branch (`has_task_commits: true`) — this is a **blocking FAIL** (verdict FAIL); the work is mis-placed and must be recovered before review. Exit 0 (no task commits on a protected branch, including a clean repo legitimately on main with zero ahead commits) → PASS. Exit 3 or script missing → non-blocking ⚠️ WARN ("branch hygiene undeterminable"), do not fail (fail-OPEN). (recovery recipe: `__QUOIN_HOME__/memory/branch-recovery.md`)
- [ ] Deploy drift — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/deploy_drift_check.py --project-root "$PROJECT_ROOT" --format text` (same invocation and result mapping as the Standard gate item above; exit 1 is ⚠️ **post-implement WARN**, non-blocking here — the blocking FAIL is at the post-review gate). Annotate the checked/not-covered qualifier verbatim on a clean PASS; do NOT compress to a bare "PASS".
- [ ] Nested memory roots — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/nested_root_check.py --project-root "$PROJECT_ROOT" --format text`. Detects accidental nested/duplicate `.workflow_artifacts` roots (IVG-119). Runs unconditionally (portable-core, not scope-gated). Result mapping (WARN-only, NEVER blocks at any gate phase incl. post-review): exit 0 → ✓ PASS (single canonical root); exit 1 → ⚠️ WARN non-blocking (list offending paths); exit 2 → ⚠️ WARN non-blocking (invocation error); exit 3 or script missing → ⚠️ WARN non-blocking (undeterminable — fail-OPEN). Env `QUOIN_DISABLE_NESTED_ROOT_CHECK=1` → exit 0 (opt-out).
- [ ] Read the `## For human` summary block from `architecture.md` if it exists AND was modified this task (per Step 3a below). Display as part of "Summary of what was produced". If `architecture.md` is v2-legacy or does not exist, skip silently.

**After /review → before /end_of_task (Full gate — always, all task sizes):**
- [ ] Review verdict is APPROVED
- [ ] Read the `## For human` summary block from `review-<latest-round>.md` (per Step 3a below). Display as part of "Summary of what was produced" alongside the verdict. If `review-<round>.md` is v2-legacy, fall back to first 2 KB display.
- [ ] All CRITICAL and MAJOR issues are resolved
- [ ] Run full test suite (re-run — code may have changed during review fixes)
- [ ] Affected-area test suite (re-run — review fixes may have changed code): run `python3 __QUOIN_HOME__/scripts/affected_tests.py --project-root "$(pwd)" --format text`; exit 0 with `ran_pytest=true` → PASS (affected suite green); exit 0 with `ran_pytest=false` → PASS / N/A (docs-only or clean tree — no affected tests to run); exit 1 → BLOCKING FAIL; exit 3 or 4 → BLOCKING-SURFACE (undeterminable / no affected tests for CHANGED `.py` sources — user must acknowledge, do NOT auto-pass); script missing → WARN non-blocking.
- [ ] CI mirror (re-run — pre-merge; review fixes may have changed code): run `python3 __QUOIN_HOME__/scripts/ci_mirror.py --project-root "$(pwd)" --format text`; exit 0 with `ran_steps=true` → PASS (CI-parity steps green); exit 0 with `ran_steps=false` → PASS, annotate by branching on the emitted `exit_reason` — `no-deliverable` → "N/A — no non-Python deliverable in diff"; `no-changes` → "N/A — clean tree, nothing changed"; exit 1 → ✗ BLOCKING FAIL (a CI-parity step is red); exit 3 → ⚠️ BLOCKING-SURFACE (undeterminable — npm missing/install failed/no steps derivable/disabled; user must acknowledge, do NOT auto-pass); exit 2 → ⚠️ WARN non-blocking (invocation error); script missing → ⚠️ WARN non-blocking (fail-OPEN on absent binary only).
- [ ] Deploy drift — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/deploy_drift_check.py --project-root "$PROJECT_ROOT" --format text`. This is the pre-merge gate: stale deployed copies here mean any review smoke-testing ran against old code. Result mapping: exit 0 with `scope=out` → PASS ("N/A — no quoin source touched"); exit 0 with drift==[] → PASS, annotate the checked/not-covered qualifier VERBATIM (`checked: skills, scripts, core-scripts, memory; not covered: hooks, CLAUDE.md, settings.json, dashboard assets, QUICKSTART.md`); exit 1 → ✗ **BLOCKING FAIL** (run `bash quoin/install.sh`, then re-run the gate); exit 2 → ⚠️ WARN non-blocking (invocation error — undeterminable, not a signal about the source tree); exit 3 or script missing → ⚠️ WARN non-blocking (undeterminable — fail-OPEN). Env `QUOIN_DISABLE_DEPLOY_DRIFT=1` → exit 0.
- [ ] Nested memory roots — run `PROJECT_ROOT="$(pwd)"; python3 __QUOIN_HOME__/scripts/nested_root_check.py --project-root "$PROJECT_ROOT" --format text`. Detects accidental nested/duplicate `.workflow_artifacts` roots (IVG-119). Runs unconditionally (portable-core, not scope-gated). Result mapping (WARN-only, NEVER blocks at any gate phase incl. post-review): exit 0 → ✓ PASS (single canonical root); exit 1 → ⚠️ WARN non-blocking (list offending paths); exit 2 → ⚠️ WARN non-blocking (invocation error); exit 3 or script missing → ⚠️ WARN non-blocking (undeterminable — fail-OPEN). Env `QUOIN_DISABLE_NESTED_ROOT_CHECK=1` → exit 0 (opt-out).
- [ ] Run type checker if applicable
- [ ] Branch is up to date with base branch
- [ ] No merge conflicts

### Step 3a: Read summary for display (Checkpoints A, B, C, D)

For Checkpoints A, B, C, and D, determine the relevant Class B artifact's format and extract the human-facing summary using the §5.7.1 detection rule below.
- Checkpoint A0 (post-`/specify` → pre-`/architect`): read `spec.md`. spec is Class A (no `## For human` block) — display the `## Acceptance criteria` section (or first 2 KB) as the summary; if `spec.md` does not exist (Small-task / grandfather), skip the spec read and proceed.
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

### Step 3.5: Benchmark auto-approve check (runs BEFORE Step 4 STOP)

Before blocking on user input, check whether BOTH of the following environment
variables are set in the current process environment:

  - `QUOIN_GATE_AUTO_APPROVE=1`
  - `QUOIN_BENCHMARK_RUN` (any non-empty value)

Detection: read `os.environ` (or shell-equivalent) for both keys.

**If and only if BOTH are set:**

1. Do NOT block on user input. Do NOT call AskUserQuestion.
2. Emit a one-line notice to stdout (for run-manifest traceability):
   `[quoin-gate: auto-approved] QUOIN_GATE_AUTO_APPROVE=1 QUOIN_BENCHMARK_RUN=<value> — skipping human gate for benchmark run`
3. Treat this as an implicit user approval and proceed DIRECTLY to Step 5.
4. In Step 5, write the audit log with the following extra fields:
   - `auto_approved: true`
   - `env: QUOIN_GATE_AUTO_APPROVE=1 QUOIN_BENCHMARK_RUN=<run_id_value>`
   - `gate_encountered_at: <ISO timestamp>`
   - `benchmark_run_id: <QUOIN_BENCHMARK_RUN value>`

**Security rationale (dual-guard requirement):**
The dual env-var guard prevents accidental auto-approval in production user
sessions where only one variable might be set by accident. If only
`QUOIN_GATE_AUTO_APPROVE=1` is set (without `QUOIN_BENCHMARK_RUN`), the gate
behaves normally — it blocks and waits for human input. The `QUOIN_BENCHMARK_RUN`
variable is set by the benchmark orchestrator (`run_benchmark.py`) and is not
normally present in interactive user sessions.

**If only ONE or NEITHER variable is set:** proceed normally to Step 4 below.

### Step 3.6: Autonomous auto-approve check (runs BEFORE Step 4 STOP; independent of Step 3.5)

Applies when `/gate` is running under autonomous mode — either dispatched as a `[autonomous]`-subagent (the incoming prompt carries the `[autonomous]` sentinel), OR invoked **inline** by an orchestrator (`/run --autonomous`) whose own `AUTONOMOUS` state is set (no spawn prompt exists for inline invocation, so the orchestrator's own state is read directly — mirrors the inline-gate rule documented in `run/SKILL.md`).

Detection: parse `[autonomous]` from the incoming prompt (subagent mode), OR read the orchestrator's own `AUTONOMOUS` flag when this gate is executing inline (post-implement/post-review boundaries).

**If autonomous mode is active:**

1. **On checks PASS** (no blocking FAIL rows in the `## Automated checks` table): do NOT block on user input. Do NOT call `AskUserQuestion`. Emit a one-line notice: `[quoin-gate: autonomous auto-approved] checks PASS — skipping human gate under autonomous mode`. Treat this as an implicit approval and proceed DIRECTLY to Step 5 audit-log persistence. In Step 5, write the audit log with the extra fields `auto_approved: true` and `mode: autonomous`.
2. **On checks FAIL** (any blocking FAIL row present): do NOT auto-approve — this is the fail-closed branch. Do NOT write the audit log as an approval. Return the FAIL verdict to the orchestrator; the orchestrator (not `/gate`) owns the retry/hard-stop decision. Step 5 audit-log persistence still runs (mandatory in both modes — see "Gate invocation boundaries" below) and records `Verdict: FAIL`, never an auto-approval.

**If autonomous mode is NOT active:** proceed normally to Step 4 (unchanged).

This check is independent of the Step 3.5 benchmark dual-guard bypass — the two auto-approve paths are keyed on different signals and are not mutually exclusive gates on the same run.

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

Regardless of invocation mode, Step 5 audit-log persistence is **mandatory**: every `/gate` invocation **MUST write** a `gate-{phase}-{date}.md` **audit log** before yielding control. This requirement applies whether invoked inline or as a subagent. **audit log persistence** is non-skippable on approval. `specify` is a valid `{phase}` token for the spec→architect gate boundary (writes `gate-specify-<date>.md`), alongside the existing architect/plan/implement/review boundaries.

**Inline mode note:** when invoked inline (post-implement, post-review), the executing agent skips both:
- The `__QUOIN_HOME__/skills/gate/preamble.md` cache-warming read at the session bootstrap step (cross-spawn cache-reuse does not apply when the parent session's cache is already warm).
- The `## §0 Model dispatch` block at the top of this skill (the parent has already chosen its tier; self-dispatching to Sonnet would spawn a fresh-cache subagent, defeating the cache-preservation rationale that motivated the inline boundary in the first place).

The agent reads from `### Step 1: Detect context` onwards. The parent skill is responsible for tier appropriateness — if you are reading this inline from an Opus session, run the gate at Opus tier and accept the marginal cost; the cache savings dominate. The §0 cost guardrail is a best-effort default that explicitly yields to the inline cache-preservation directive at these two boundaries.

Once the user explicitly approves the gate (i.e., after the STOP-and-wait in Step 4 returns with approval), persist the gate result to disk as a Class A artifact at `{project-folder}/.workflow_artifacts/{task-name}/gate-{phase}-{date}.md`.

If the user rejects the gate (asks to fix something), do NOT write the audit log. Wait until the gate is re-run and approved before writing.

Use the §5.4 Class A writer mechanism.
Read `__QUOIN_HOME__/memory/format-kit-pitfalls.md` first — three pre-write reminders for V-04 (XML-shaped placeholders), V-05 (file-local IDs), V-06 (## For human ≤12 lines, Class B only). Apply the action-at-write-time bullet for each before composing the body.
Reference files (apply HERE at the body-generation write-site, per format-kit.md §1 / lesson 2026-04-23):
- `__QUOIN_HOME__/memory/format-kit.md` — primitives + standard sections per artifact type
- `__QUOIN_HOME__/memory/glossary.md` — abbreviation whitelist + status glyphs
- `__QUOIN_HOME__/memory/terse-rubric.md` — prose discipline

# V-05 reminder: T-NN/D-NN/R-NN/F-NN/Q-NN/S-NN are FILE-LOCAL.
# When referring to a sibling artifact's task or risk, use plain English (e.g., "the parent plan's T-04"), NOT a bare T-NN token. See format-kit.md §1 / glossary.md.
Compose the format-aware body per format-kit.md §2 `gate-{phase}-{date}.md` enumeration:
- `## Automated checks` — REQUIRED — terse numbered list with status glyphs ✓/✗/⚠️ per check, brief detail per row. For post-implement gates this list MUST include a `Branch hygiene` entry (the check name is the literal string `Branch hygiene` — identical in both the Standard/Full checklist above and here in the audit enumeration; these must not drift). For post-implement AND post-review gates this list MUST include an `Affected-area test suite` entry (the check name is the literal string `Affected-area test suite` — identical in the Standard gate checklist, Full gate checklist, post-review checklist, and here in the audit enumeration; these must not drift). The `Affected-area test suite` row is ALWAYS emitted (never silently dropped) regardless of exit code, including in the post-review gate audit log. Glyph mapping for the `Affected-area test suite` row: ✓ on exit 0 with `ran_pytest=true` (affected suite green); ✓ (annotate "N/A — no affected tests") on exit 0 with `ran_pytest=false` (docs-only or clean tree — still a PASS, but the row text MUST say "N/A — no affected tests" not "green", per MAJ-1); ✗ on exit 1 (red, blocking); ⚠️ on exit 3 or 4 (undeterminable / no affected tests for changed `.py` sources — blocking-surface); ⚠️ on script-missing (non-blocking warn). For post-implement AND post-review gates this list MUST also include a `Deploy drift` entry (the check name is the literal string `Deploy drift` — identical in the Standard gate checklist, Full gate checklist, post-review checklist, and here in the audit enumeration; these must not drift). Glyph mapping for the `Deploy drift` row: ✓ on exit 0 with `scope=out` (annotate "N/A — no quoin source touched"); ✓ on exit 0 with drift==[] — the row text MUST carry the checked/not-covered qualifier verbatim (`checked: skills, scripts, core-scripts, memory; not covered: hooks, CLAUDE.md, settings.json, dashboard assets, QUICKSTART.md`), NOT a bare "PASS"; ✗ on exit 1 at the post-review gate (drift found — blocking FAIL) / ⚠️ on exit 1 at the post-implement gate (WARN, non-blocking); ⚠️ on exit 2 (invocation error — undeterminable, not a source-tree signal); ⚠️ on exit 3 or script-missing (undeterminable — fail-OPEN, non-blocking). For post-implement AND post-review gates this list MUST also include a `CI mirror` entry (the check name is the literal string `CI mirror` — identical in the Standard gate checklist, Full gate checklist, post-review checklist, and here in the audit enumeration; these must not drift). The `CI mirror` row is ALWAYS emitted (never silently dropped) regardless of exit code. Glyph mapping for the `CI mirror` row: ✓ on exit 0 with `ran_steps=true` (CI-parity steps green); ✓ on exit 0 with `ran_steps=false` — annotate by branching on the emitted `exit_reason` ("N/A — no non-Python deliverable in diff" for `no-deliverable`; "N/A — clean tree, nothing changed" for `no-changes`), NOT a bare "PASS"; ✗ on exit 1 (a CI-parity step is red — blocking FAIL); ⚠️ on exit 3 (undeterminable — npm missing/install failed/no steps derivable/disabled — blocking-surface) and exit 2 (invocation error, non-blocking); ⚠️ on script-missing (undeterminable — fail-OPEN, non-blocking, scoped strictly to absent binary). For post-implement AND post-review gates this list MUST also include a `Nested memory roots` entry (the check name is the literal string `Nested memory roots` — identical in the Standard gate checklist, Full gate checklist, post-review checklist, and here in the audit enumeration; these must not drift). The `Nested memory roots` row is ALWAYS emitted (never silently dropped) regardless of exit code, and is WARN-only — it NEVER blocks the gate at any phase (including post-review). Glyph mapping for the `Nested memory roots` row: ✓ on exit 0 (single canonical `.workflow_artifacts` root); ⚠️ on exit 1 (accidental nested root(s) found — list offending paths, non-blocking); ⚠️ on exit 2 (invocation error, non-blocking); ⚠️ on exit 3 or script-missing (undeterminable — fail-OPEN, non-blocking).
- `## Verdict` — REQUIRED — single word `PASS` or `FAIL`.
- `## Failures requiring attention` — OPTIONAL — terse numbered list of blocking failures with remediation.
- `## Warnings (non-blocking)` — OPTIONAL — terse numbered list of non-blocking issues.
- `## Summary of what was produced` — OPTIONAL — caveman prose, 2-3 sentences. (Reuse the `## For human` content already captured from Step 3a; do NOT re-read the source artifact.)
- `## What's next` — OPTIONAL — caveman prose, 1-2 lines.

Write the body to `{path}.body.tmp`; compose final file as `{frontmatter (YAML — task, phase, date, gate-level)}\n\n{body content}`; write to `{path}.tmp`. Validate via `python3 __QUOIN_HOME__/scripts/validate_artifact.py {path}.tmp` (auto-detection → gate type via `^gate-` prefix). On V-failure: retry-once with section-discipline reminder; on persistent failure, Before falling back to v2-style write, increment the session-state `fallback_fires` field by 1 (atomic-rename pattern; same rules as the Step 5 increment described above), then fall back to v2-style terse-rubric-only write. Atomic rename: `mv {path}.tmp {path} && (rm -f {path}.body.tmp 2>/dev/null || true)`.

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
