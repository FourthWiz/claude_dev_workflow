# Autonomous mode reference (`--autonomous`)

Verbose Tier-1 reference for the opt-in `--autonomous` span on `/run`
(IVG-153, `autonomous-run-mode` Stage 1). This file holds the full
auto-resolution table, the sentinel/propagation rule, the Formulation
quality bar, and the halt-sentinel contract. `run/SKILL.md` and the
per-skill `SKILL.md` bodies carry the operative branches; this file is
the single place that documents the whole surface in one pass.

## The `[autonomous]` sentinel and propagation

Propagation is a `[autonomous]` prompt sentinel prefixed onto every
sub-phase spawn prompt — mirroring the existing `[no-session-age-guard]`
and `[no-redispatch]` sentinel conventions — rather than an env var, so
it stays greppable and deterministic. Leading sentinels stack (e.g.
`[no-redispatch] [autonomous]`).

- `run` prefixes `[autonomous]` directly onto every sub-phase spawn it
  issues: discover, enrich, specify, architect, thorough_plan,
  implement, review, **`end_of_task`** (the terminal Phase-6 spawn),
  and every subagent-mode `gate` boundary.
- Propagation is **transitive**: every spawning skill re-prefixes
  `[autonomous]` onto the deeper spawns it issues, so the sentinel
  reaches the full transitive spawn set. Concretely, `thorough_plan`
  re-prefixes it onto its `plan`/`critic`/`revise`/`revise-fast`
  spawns, and `review` re-prefixes it onto its Large-fan-out
  `security_review` + dimension subagent spawns.
- Each sub-skill parses/strips `[autonomous]` at bootstrap into its own
  `_AUTONOMOUS` state.
- For **inline** gates (post-implement, post-review) there is no spawn
  prompt to carry a sentinel — the orchestrator applies autonomous gate
  behavior directly from its own `AUTONOMOUS` state.
- The run→`end_of_task` edge is a direct edge, not a deeper one: `run`
  spawns `end_of_task` itself as the terminal Execution phase, so the
  sentinel is prefixed onto that spawn exactly like any other direct
  sub-phase.

## Formulation quality bar

The Formulation→Execution bar is the sole safety substitute for the
human checkpoints that autonomous mode removes. It sits between the
planning phase and Execution (implementation onward); failing it is a
hard stop, never a silent proceed.

- **Medium/Large:** the bar requires the `thorough_plan` critic loop to
  have converged with a PASS verdict — not merely exhausted its round
  cap while still holding a REVISE verdict.
- **Small:** the bar requires the smoke gate to PASS **and** a
  confidence signal at or above `QUOIN_AUTONOMOUS_CONFIDENCE_THRESHOLD`
  (default `0.7`). On the Small path `/specify` and `/architect` are
  skipped, so the confidence signal is sourced from the single-pass
  `/plan` skill's own `confidence` line — optionally augmented by an
  `enrich`-emitted `confidence` value, in which case the bar takes the
  **minimum** of the two. The underlying number is an Opus
  self-assessment, a soft signal by nature; the smoke-gate PASS
  requirement is the harder half of the bar.
- Below the bar: hard stop via the halt-sentinel contract below. The
  run never enters Execution on a formulation that hasn't cleared the
  bar.

## Halt-sentinel contract

Every hard stop writes a halt-sentinel (with reason) **before exit**,
then stops. Stage 1 only *writes* the sentinel — consuming it (resume,
a future supervisor, cross-session pickup) is Stage 2, out of scope
here; this is forward-compatible groundwork only.

- **Location:** `.workflow_artifacts/memory/autonomous-halt-{task}.md`
  — deliberately **outside** the task folder, because `/end_of_task`
  archives the task folder into `finalized/` and a future supervisor
  needs the halt record to survive that move.
- **Schema:** `task`, `phase`, `reason`, `timestamp`, `resume_hint`
  (one line).
- **Hard-stop sites (all six):** review BLOCKED; gate FAIL after the
  retry cap; review CHANGES_REQUESTED after 3 rounds; git conflict;
  branch-hygiene violation; below-bar formulation (the Formulation
  quality bar above).
- **Invariant, restated:** autonomous mode never auto-creates a PR, in
  any mode, at any hard stop or otherwise.

## Auto-resolution table — full transitive spawn set (15 skills)

The transitive spawn closure resolves to 15 skills: `run`, `discover`,
`enrich`, `specify`, `architect`, `thorough_plan`, `plan`, `critic`,
`revise`, `revise-fast`, `implement`, `gate`, `review`,
`security_review`, `end_of_task`. Every genuine interactive site across
that closure has a documented autonomous resolution below. (The live
structural-canary lint that enforces this table against the actual
`SKILL.md` sources is `test_autonomous_askuserquestion_coverage.py`;
it live-derives the spawn closure at test time rather than trusting a
frozen count.)

| Skill | Site | Autonomous resolution |
|---|---|---|
| run | Checkpoints A0/A/B/C/D | PASS auto-continues with no wait; non-PASS routes to the hard-stop/halt-sentinel path, never a silent proceed |
| discover | repo-spec draft offer (`.workflow_artifacts/spec.md` absent) | auto-SKIP the offer; never auto-writes the repo main spec |
| discover | repo-spec refresh offer (spec.md present) | auto-SKIP the offer |
| discover | §0'/§0″ dispatch-failure / 1M-credit prompts (4 sites) | generated fail-OPEN clause — see "§0'/§0″ generated fail-OPEN rows" below |
| enrich | gap-questions prompt | best-effort; flags assumptions in `enriched-prompt.md`; never blocks |
| enrich | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| specify | intent-elicitation prompt | skipped; synthesizes a confidence-scored spec from the raw prompt + `enriched-prompt.md` + `architecture.md`, records assumptions in `## Context` |
| specify | repo-main-spec-update gate | auto-"Reject" — never auto-writes the repo main spec |
| specify | §0'/§0″ dispatch prompts (4 sites) | generated fail-OPEN clause |
| architect | spec pre-flight prompt | proceed |
| architect | scan-ambiguity / scan-failure prompts | proceed best-effort, flag |
| architect | Phase-4 round-2 cost guard | proceed |
| architect | same-class escalation | continue revising |
| architect | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| thorough_plan | §1b resume prompt (2-option and same-session 3-option variants) | auto-select "Resume" (parse `## Current stage`, continue) — **never** "Resume in a new session"/STOP |
| thorough_plan | enrich pre-step prompt | skip (already run at Phase 1.4) or best-effort |
| thorough_plan | spec pre-flight prompt | skip if task-root `spec.md` exists, else non-interactive |
| thorough_plan | auto-classify confirm (prose, not an `AskUserQuestion` token) | accept the auto-classification |
| thorough_plan | same-class escalation (prose, not an `AskUserQuestion` token) | continue revising to `max_rounds` |
| thorough_plan | deeper spawns | re-prefixes `[autonomous]` onto `plan`/`critic`/`revise`/`revise-fast` spawns (transitive propagation) |
| plan | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| critic | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| revise | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| revise-fast | §0-worktree-fallback prompt (artifact-only block) | hand-synced fail-OPEN clause — see "§0-worktree hand-synced fail-OPEN rows" below |
| implement | branch-hygiene precheck (protected-branch prompt) | auto-create `feat/{task}` feature branch, no `AskUserQuestion` |
| implement | task-confirm prompt | auto-select "All remaining tasks" |
| implement | §0-worktree-fallback sidecar prompt (source-mutating block) | hand-synced fail-OPEN clause |
| gate | checks-PASS path | auto-approve, proceed to Step 5 audit-log persistence; **FAIL is never auto-approved** — returns the verdict to the orchestrator, which owns the retry/hard-stop decision |
| gate | §0-worktree-fallback prompt | hand-synced fail-OPEN clause |
| review | §0'/§0″ dispatch prompts | generated fail-OPEN clause |
| review | fan-out spawns | re-prefixes `[autonomous]` onto the Large-only `security_review` spawn and the Medium/Large dimension subagents (transitive propagation); verdict emission (APPROVED / CHANGES_REQUESTED / BLOCKED) itself is unchanged — BLOCKED handling stays a `run`-level hard stop |
| security_review | §0'/§0″ dispatch prompts | generated fail-OPEN clause (reached transitively via review's Large fan-out) |
| end_of_task | Step 1 garbage-files prompt | auto-proceed with the cleanup default |
| end_of_task | Step 2 commit-decision prompt | auto-select "Commit" — **never** "Abort" |
| end_of_task | Step 3 lessons-learned prompt | auto-capture via the existing capture triggers, or skip cleanly; no `AskUserQuestion` |
| end_of_task | Step 4 archive-type prompt | auto-select the safe default ("Fully complete" / top-level archive) |
| end_of_task | §0-worktree-fallback sidecar prompt | hand-synced fail-OPEN clause |
| end_of_task | (all sites, restated) | never auto-creates a PR, in any mode |

## §0'/§0″ generated fail-OPEN rows

The §0'/§0″ dispatch-failure and 1M-credit `AskUserQuestion` prompts are
**generated** per-skill by `inject_pollution_dispatch.py`
(`render_pollution_block` / `render_mintier_block`, `{skill}`
substitution) into the `<!-- §0doubleprime-begin/end -->` and §0'
blocks, across the 10 Opus-tier leaf skills: `architect`, `plan`,
`critic`, `revise`, `review`, `security_review`, `discover`, `specify`,
`enrich`, `init_workflow`. Under `[autonomous]`, the generated clause
reads: on any §0'/§0″ dispatch-failure or 1M-credit error, proceed at
current tier fail-OPEN and do **not** call `AskUserQuestion`. This
clause is added to the **generator template**, then every leaf skill's
`SKILL.md` is regenerated — the generated block is never hand-edited
directly (that would trip the generator's own drift guard).

## §0-worktree hand-synced fail-OPEN rows

The §0-worktree-fallback prompt (e.g. `revise-fast` L105) is **not**
generated by any script (`build_preambles.py` emits only `preamble.md`
warm-up files; `inject_pollution_dispatch.py` covers only §0'/§0″). It
is hand-maintained inline, delimited by
`<!-- §0-worktree-fallback-begin/end -->`, and byte-identity-enforced
across two classes:

- **12 artifact-only skills** — includes the reachable `revise-fast`
  and `gate`.
- **4 source-mutating skills** (sidecar variant) — `implement`,
  `rollback`, `end_of_task`, `pr` — includes the reachable `implement`
  and `end_of_task`.

Under `[autonomous]`, both block variants carry the same clause: on any
worktree-class dispatch error, proceed at current tier fail-OPEN and do
**not** call `AskUserQuestion`. The clause is propagated to **every**
member of both classes, not only the reachable ones, so the
byte-identity contracts stay green; on non-reachable skills the clause
is simply inert (conditional on the absent sentinel).

## Relocated: Exception: `/run` orchestrator

Moved here verbatim from `CLAUDE.md`'s "Workflow sequence" section
(IVG-153 T-17). `CLAUDE.md` now carries only a short pointer back to
this section, to stay under its size ceiling.

**Exception: `/run` orchestrator.** When the user invokes `/run`, they
have explicitly requested the full end-to-end pipeline. `/run` may
invoke `/implement` and `/end_of_task` on the user's behalf, but still
pauses at each gate checkpoint for confirmation before proceeding. The
user's `/run` invocation constitutes the conscious decision;
the gate confirmations provide the safety checkpoints.

Under `--autonomous`, this reliance extends one step further: once the
Formulation quality bar passes, the run stays unattended from that
point through `/end_of_task`, auto-resolving every interactive
checkpoint and body prompt per the auto-resolution table above instead
of pausing for confirmation. Every hard stop defined in the
halt-sentinel contract above still halts the run and records the
reason rather than proceeding silently, and a PR is never auto-created
in either mode.
