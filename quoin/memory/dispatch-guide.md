# Dispatch guide — §0 and §0' verbose reference

## §0 Model dispatch preamble (verbose reference)

The 16 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast, sleep, next_steps, checkpoint, continue_work) carry a `## §0 Model dispatch (FIRST STEP — execute before anything else)` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with the bare `[no-redispatch]` sentinel to prevent infinite recursion. The counter form `[no-redispatch:N]` is reserved for an abort signal: if a child sees N≥2, it aborts instead of proceeding (the bare form is the normal parent-emit; counter forms catch buggy parents or mistaken manual overrides). The 9 Opus-tier skills do NOT carry the preamble — they should run on Opus regardless of session model.

If the harness's subagent-spawn tool is unavailable or returns an error, dispatch falls back to a fail-OPEN path (proceed at current tier, emit a one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning). This is intentional per architecture I-01: cost guardrail is best-effort, not load-bearing for correctness.

**WorktreeCreate hook and two-phase dispatch (source-mutating skills only, 2026-05-21):**
The three source-mutating cheap-tier skills (`/implement`, `/rollback`, `/end_of_task`) use a two-phase worktree isolation mechanism. Before calling the Agent tool, the skill runs `dispatch_sidecar.py` to write a sidecar JSON at `<project_root>/.workflow_artifacts/.dispatch-hint.json` containing the skill name, project root, plan path, and session ID. Phase 1 dispatches with `isolation: "worktree"`; the deployed WorktreeCreate hook at `__QUOIN_HOME__/hooks/worktreecreate.sh` reads the sidecar, calls `git_root_for_dispatch.py --sidecar`, and (when a single nested git repo resolves) runs `git worktree add` anchored at the nested repo and prints the created worktree path to stdout. The hook always exits 0 (fail-OPEN); if it skips (no stdout → harness worktree fails) or Phase 1 returns a worktree-class error, the skill retries as Phase 2 without `isolation: "worktree"` at the same cheap-tier model. No AskUserQuestion prompt is needed for these three skills; Phase 2 retry is fully automated.

**Worktree-class errors in artifact-only skills (unchanged, 2026-05-21):**
The 12 artifact-only cheap-tier skills still use the original worktree-class recovery path. Worktree-class errors (substring match: `Cannot create agent worktree` OR `worktree` + `not in a git repository`) are classified BEFORE the fail-OPEN warning is emitted. The skill uses the AskUserQuestion tool to present one recovery option: `(c) proceed-current-tier`. A second classification line is emitted: `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`. The bare warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` is always emitted verbatim first.

Manual override: prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely. Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Mechanical drift detection lives in `quoin/dev/tests/test_quoin_stage1_preamble.py` and `quoin/dev/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification is captured in `quoin/dev/verify_subagent_dispatch.md`.

## §0' Pollution dispatch (verbose reference)

The 7 Opus-tier skills that are NOT orchestrators (architect, plan, critic, revise, review, init_workflow, discover) carry a `## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)` block. When `pollution_score` exceeds `POLLUTION_THRESHOLD`, the skill self-dispatches as a fresh Agent subagent carrying per-skill paths (not content).

**Detection:** reads `pollution_score: N` from session-state file or `pollution-score-latest.txt`. Fires if N >= threshold AND no `[no-redispatch]` AND no prior §0 dispatch. Score formula: `transcript_kb + (agent_returns × 5) + (read_calls × 1) + (bash_calls × 1)` — implemented in `quoin/hooks/_lib.sh`. Written by `userpromptsubmit.sh` STEP 0.5 on every prompt submit.

**Per-skill dispatch contract:**

| Skill | What the dispatch prompt carries |
|-------|----------------------------------|
| /architect | task description + paths to /discover output |
| /plan | task description + path to architecture.md + stage identifier |
| /critic | absolute path to target artifact |
| /revise | path to current-plan.md + path to critic-response-N.md |
| /review | path to current-plan.md + branch ref |
| /init_workflow | project root absolute path |
| /discover | project root absolute path |

**Ordering:** §0 fires FIRST; §0' fires only if no §0 dispatch. For §0c skills (architect, review): §0c → §0' → body. **Excluded:** /run and /thorough_plan. **Threshold:** `QUOIN_POLLUTION_THRESHOLD` (default 5000). Fail-OPEN on Agent unavailable. `[no-redispatch]` skips. Drift detection: `test_quoin_pollution_preamble.py`; verification: `quoin/dev/verify_pollution_dispatch.md`.

## §0″ Minimum-tier guard (verbose reference)

The 7 Opus-tier leaf skills (architect, plan, critic, revise, review, init_workflow, discover) carry a `## §0″ Minimum-tier guard (execute after §0 / §0c / §0' if present — before skill body)` block. Fires when the executing session is running on a model cheaper than Opus (inverse of §0's over-tier trigger: `current_tier < declared_tier`). Orchestrators /run and /thorough_plan are excluded (D-04: they route via correctly-tiered phase children; up-dispatching the orchestrator shell does not improve child tiers). Generated by `inject_pollution_dispatch.py`. Drift test: `test_mintier_guard.py`.

**Detection:** Read model name from system context. Tier order: haiku < sonnet < opus. Declared tier = opus. Fire conditions: `current_tier < declared_tier` AND no `[no-redispatch]` sentinel AND `QUOIN_DISABLE_MINTIER_GUARD` not set.

**Decision tree (Option A — up-dispatch confirmed, not yet active):** Step 1: spawn Agent subagent `model: "opus"` with `[no-redispatch]` prefix. Return child output. STOP. Step 2 (Agent unavailable or error): fail-open leaf below.

**Decision tree (Option B — current default, spike not confirmed):** Skip Agent spawn. Go directly to fail-open leaf.

**Fail-open leaf (both options):** Issue AskUserQuestion: Option 1 "Abort — run from an Opus session" → print `[quoin-mintier: aborted; re-invoke /{skill} from an Opus session]` and STOP. Option 2 "Proceed at current tier (under-powered)" → print `[quoin-mintier: min-tier up-dispatch unavailable; proceeding at current tier per user choice]` and fall through to skill body.

**Env knob:** `QUOIN_DISABLE_MINTIER_GUARD=1` → silent skip (no advisory). Intentional silence: explicit opt-out is user-controlled, not an unexpected error state.

**1M-context precheck:** Not implemented in v1 (D-06, R-03). The fail-open leaf catches resulting Agent errors and degrades gracefully. This is a conscious omission, not an oversight.

**Recursion guard:** In Option A, child has current==declared; `[no-redispatch]` prefix is belt-and-suspenders. No counter form needed.

**Spike result (2026-06-16):** Up-dispatch was not confirmed in the IVG-72 implement session (Sonnet parent; live API not available during automated implementation). Option B ships as default. Re-run `quoin/dev/spike_mintier_updispatch.py` from a Sonnet Claude Code session to confirm up-dispatch behavior.
