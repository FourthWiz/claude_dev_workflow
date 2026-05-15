# Dispatch guide — §0 and §0' verbose reference

## §0 Model dispatch preamble (verbose reference)

The 15 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast, sleep, next_steps, checkpoint) carry a `## §0 Model dispatch (FIRST STEP — execute before anything else)` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with the bare `[no-redispatch]` sentinel to prevent infinite recursion. The counter form `[no-redispatch:N]` is reserved for an abort signal: if a child sees N≥2, it aborts instead of proceeding (the bare form is the normal parent-emit; counter forms catch buggy parents or mistaken manual overrides). The 9 Opus-tier skills do NOT carry the preamble — they should run on Opus regardless of session model.

If the harness's subagent-spawn tool is unavailable or returns an error, dispatch falls back to a fail-OPEN path (proceed at current tier, emit a one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning). This is intentional per architecture I-01: cost guardrail is best-effort, not load-bearing for correctness.

Worktree-class errors (substring match: `Cannot create agent worktree` OR `worktree` + `not in a git repository`) are classified BEFORE the fail-OPEN warning is emitted. The skill uses the AskUserQuestion tool (always available in the parent session where §0 fires) to present recovery options. Available options depend on harness support (resolved by the pre-implementation spike): `retry-no-isolation` (if the harness exposes an isolation parameter that can be omitted), `retry-with-base <path>` (if the harness exposes a per-call base-path parameter), and `proceed-current-tier` (always available). A `[worktree-retry]` sentinel is prepended as the FIRST LINE of the retry prompt to prevent re-prompting on retry failure. Retry failures and other-class errors fall through to the bare fail-OPEN path. When the worktree branch was taken, a second classification line is also emitted: `[quoin-stage-1: error-class=worktree; user-choice=<a|b|c|retry-failed>; proceeding at current tier]`. The bare warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` is always emitted verbatim first so downstream string-matching consumers are unaffected.

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
