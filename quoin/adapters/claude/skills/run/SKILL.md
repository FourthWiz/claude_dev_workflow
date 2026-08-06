---
name: run
description: "End-to-end workflow orchestrator that chains all development phases together: discover, architect, plan, implement, review, and end_of_task. Pauses at major phase boundaries for user confirmation. Use this skill for: /run, 'run the full workflow', 'end to end', 'do everything', 'full pipeline'. Accepts task profile tags (small:, medium:, large:, strict:) and max_rounds: N. Skips discover if recent scan exists, skips architect for Small tasks."
model: opus
---

# Run — End-to-End Orchestrator

*Portable intent doc: `quoin/core/skills/run.md`*

You are the user's single entry point for running the entire development workflow end-to-end — chaining every phase together and pausing only at major phase boundaries for user confirmation, instead of invoking each skill by hand.

**You are the conductor, not the performer.** Each phase runs in its own subagent session — you coordinate the flow, present checkpoint summaries, and wait for the user's go-ahead.

**You ARE an explicit user invocation.** Because the user consciously chose to run the full pipeline with `/run`, you may invoke `/implement` and `/end_of_task` on their behalf after they confirm at the relevant checkpoint — the explicit exception to the critical rule in `CLAUDE.md` and to the "Explicit invocation only" rules in `implement/SKILL.md` and `end_of_task/SKILL.md`. The `/run` invocation is the conscious decision; checkpoint confirmations are the safety net.

## Session bootstrap

When starting:
1. Read `CLAUDE.md` for shared workflow rules
2. Read `.workflow_artifacts/memory/lessons-learned.md` for relevant insights (if it exists)
3. Read `.workflow_artifacts/memory/sessions/` for any in-progress state for this task
4. Check git state across all repos

Note: the cost ledger initializes during Setup ("Initialize cost ledger" below); the orchestrator's own session is its first entry.

## Setup

### Parse `--autonomous` flag (opt-in, default off)

Before profile-tag parsing, scan the task description for the `--autonomous` token. This is **opt-in** — omitting it preserves today's fully-interactive `/run` behavior unchanged (default off).

- If present: strip the `--autonomous` token from the task description **before profile classification** — the same treatment as the existing `[no-session-age-guard]` sentinel and the `strict:`/`max_rounds:` tokens below, none of which are allowed to pollute triage or the derived task name. Set an internal state flag `AUTONOMOUS=true` for the remainder of this session.
- If absent: `AUTONOMOUS=false`. Every autonomous branch documented in this file is inert when `AUTONOMOUS=false`; plain `/run` stays byte-behavior-unchanged.

Record `autonomous: true` in the session-state file (`.workflow_artifacts/memory/sessions/<date>-<task-name>.md`) once created, and append `[autonomous]` to the NOTE field of the orchestrator's own cost-ledger row (see "Initialize cost ledger" below) so the ledger reflects the run mode.

### Write the autonomous-span marker (T-10 — only under `AUTONOMOUS`)

Immediately after `AUTONOMOUS=true` is set above, write the T-05 marker sentinel
`autonomous-run-{task}.marker` atomically. This fires on EVERY autonomous entry —
a fresh `--autonomous` invocation and a resumed `--resume --autonomous` relaunch
alike — because the write is idempotent (an overwrite is a no-op-equivalent), so
there is no need to distinguish fresh-vs-resumed at this site:

```bash
mkdir -p .workflow_artifacts/memory
printf 'task: <task-name>\ntimestamp: <ISO-8601 now>\nautonomous: true\n' \
  > .workflow_artifacts/memory/autonomous-run-<task-name>.marker.tmp \
  && mv .workflow_artifacts/memory/autonomous-run-<task-name>.marker.tmp \
        .workflow_artifacts/memory/autonomous-run-<task-name>.marker
```

Plain `/run` (no `--autonomous`, `AUTONOMOUS=false`) never writes this marker — the
write is entirely inert when `AUTONOMOUS=false`, mirroring every other autonomous
branch in this file. The read side of this contract (a resumed session re-establishing
`AUTONOMOUS=true` from this marker before its own first decision point) is documented
in `## Resume` below.

### Parse input and determine task profile

Scan the task description (with `--autonomous` already stripped, if present) for profile tags and runtime overrides, in this order:

1. **`strict:`** prefix → Large profile (all-Opus, max 5 rounds). Strip token.
2. **`fast:`** prefix (anywhere in the input) → set an internal `ROUTE_FORCED=fast` flag. Strip the token before profile classification (step 3 below) and before the derived task name (Determine task name, next section) — same non-pollution treatment as `--autonomous`, `strict:`, and `max_rounds:` above. ORTHOGONAL to the profile tags below: a combination like `fast: large: …` keeps Large as the profile AND forces the fast-path route to be evaluated in Phase 1.6.
3. **`small:` / `medium:` / `large:`** prefix → set profile accordingly. Strip token.
4. **No tag** → auto-classify using triage criteria, present classification with rationale, ask for user confirmation. **Under `AUTONOMOUS`:** skip the wait — auto-accept the classification and proceed (see `## Checkpoint interaction protocol`).
5. **`max_rounds: N`** → override the round cap. Strip token. Ignored for Small. **Under `AUTONOMOUS`:** if not explicitly given, `max_rounds` defaults per profile — see "Perfectionist depth-within-profile (autonomous)" below.

See `/thorough_plan` SKILL.md section 3 for full parsing rules and triage criteria.

### Determine task name

Derive a descriptive kebab-case name from the task description (e.g., `auth-token-refresh`, `add-retry-logic`). Ask the user if it's not obvious. Create `.workflow_artifacts/<task-name>/`.

### Initialize cost ledger

After creating the task folder, initialize the cost ledger:

1. Create `.workflow_artifacts/<task-name>/cost-ledger.md` with the header (format/rules: `__QUOIN_HOME__/memory/cost-ledger-format.md`):
   ```
   # Cost Ledger — <task-name>
   ```
If your incoming prompt contains `[quoin-onbehalf]`: SKIP this cost-ledger self-write — the spawning orchestrator records this row on your behalf (D-1). Strip `[quoin-onbehalf]` at bootstrap step 0 (per-spawn, non-inherited — do not propagate to children).

2. Record the orchestrator's own session as the first entry (see cost tracking rules in CLAUDE.md for UUID acquisition):
   ```
   <session-uuid> | <YYYY-MM-DD> | run-orchestrator | opus | task | /run pipeline start

<!-- quoin:ledger-self-write -->
   ```

### Pre-flight: session-age guard

/run pipelines span every phase and are even more failure-prone than /end_of_task
when run from a long-lived session. Before starting the pipeline, check session age:

<!-- decision-gate: best-effort site=run-session-age reason=orchestrator-preflight-stops-safely-with-no-session-age-guard-bypass -->
```
python3 __QUOIN_HOME__/scripts/session_age_guard.py --threshold-hours 6.0 --project-root "$(pwd)"
```

If exit 1 (`OVER|...`): STOP. Tell the user verbatim:
  "Current session has been active for Xh — over the 6h soft cap.
   /run pipelines are even more failure-prone than /end_of_task because they
   span every phase. Please open a fresh chat to start a long pipeline.
   Override at your own risk by re-invoking with prefix [no-session-age-guard] /run"

If exit 0 (`OK|...`): continue to ### Check git state.

If the helper is missing OR exits with a non-0/1 code: emit the warning
`[session-age-guard: helper unavailable; proceeding]` and continue
(fail-OPEN, mirrors §0 dispatch fail-OPEN per architecture I-01).

Manual override: prefix the user invocation with `[no-session-age-guard]`
to skip the check entirely. Strip the sentinel before processing.

### Check git state

Before any work begins:
1. Run `git status` and `git branch` on all affected repos
2. If dirty state: commit or stash before proceeding
3. Switch to main/master, fetch and pull
4. Create a fresh branch for the task: `feat/<task-name>` or similar

Under `AUTONOMOUS`: a branch-hygiene violation — task commits landing on a protected branch, or the branch-hygiene precheck failing at any downstream phase (e.g. `implement`'s §0b precheck) — is Hard-stop #5. Write the halt-sentinel per "## Autonomous hard stops" before exit, then stop.

## Perfectionist depth-within-profile (autonomous)

Under `AUTONOMOUS`, tune DEPTH knobs WITHIN the classified/tagged profile — never upgrade the profile itself. Autonomous never maps a `small:` input to Medium or Large: `--autonomous small:` stays a Small, single-pass `/plan` (no critic loop), exactly as plain `small:` does.

- **Gate level → Full at every gate** (post-implement, post-review), regardless of profile — including Small, which under plain `/run` only gets Standard. This is a strictness upgrade only; it does not touch planning depth or the profile tag.
- **`max_rounds` → the profile default** (Medium 4 rounds, Large 5 rounds) unless the user's explicit `max_rounds: N` token overrides it (the override still applies verbatim). Small has no critic loop, so this knob is inert for Small.
- **Revise model → all-Opus revise** (strict-mode `/revise`, not the cost-efficient `/revise-fast`) for Medium and Large under autonomous.
- Propagate these depth parameters to the `/thorough_plan` spawn (Phase 3) and to both `/gate` invocations (Phase 4 inline, Phase 5 inline).

Net effect: `--autonomous small:` → Small stays single-pass, gate goes Full. `--autonomous medium:` / `--autonomous large:` (or auto-classified Medium/Large) → Full gate + profile-default max_rounds + all-Opus revise, profile itself unchanged.

## Autonomous propagation (`[autonomous]` sentinel)

Under `AUTONOMOUS`, `/run` prefixes the `[autonomous]` sentinel onto EVERY sub-phase spawn prompt it issues directly — mirroring the existing `[no-session-age-guard]`/`[no-redispatch]` sentinel convention. This covers all 9 direct sub-phase spawns:

1. **discover** (Phase 1) — prefix `[autonomous]` onto the `/discover` spawn prompt.
2. **enrich** (Phase 1.4) — prefix `[autonomous]` onto the `/enrich` spawn prompt.
3. **specify** (Phase 1.5) — prefix `[autonomous]` onto the `/specify` spawn prompt.
4. **architect** (Phase 2) — prefix `[autonomous]` onto the `/architect` spawn prompt.
5. **thorough_plan** (Phase 3) — prefix `[autonomous]` onto the `/thorough_plan` spawn prompt.
6. **implement** (Phase 4) — prefix `[autonomous]` onto the `/implement` spawn prompt.
7. **review** (Phase 5) — prefix `[autonomous]` onto the `/review` spawn prompt.
8. **end_of_task** (Phase 6, the terminal `/end_of_task` spawn) — prefix `[autonomous]` onto the `/end_of_task` spawn prompt.
9. **gate** (every subagent-mode `/gate` spawn — post-specify, post-architect, post-plan boundaries) — prefix `[autonomous]` onto the `/gate` spawn prompt.

**Inline gates** (post-implement, post-review — see "Gate boundaries reference") have no spawn prompt to prefix. For inline gates, the orchestrator applies autonomous gate behavior directly from its own `AUTONOMOUS` state instead of prefixing a sentinel.

**Transitive propagation rule:** propagation is not limited to `/run`'s direct spawns — every spawning skill that itself spawns a deeper skill MUST re-prefix `[autonomous]` onto that deeper spawn, so the sentinel reaches the full transitive spawn set. Concretely: `thorough_plan` re-prefixes `[autonomous]` onto its `/plan`/`/critic`/`/revise`/`/revise-fast` spawns, and `review` re-prefixes `[autonomous]` onto its Large-fan-out `/security_review` and dimension-subagent spawns. Each sub-skill parses and strips `[autonomous]` at its own bootstrap into a local `_AUTONOMOUS` state.

**Stacking:** leading sentinels stack — a spawn prompt may read `[no-redispatch] [autonomous] <task description>`. Each sentinel is parsed and stripped independently; order does not matter.

## Non-interactive fail-closed propagation (`[no-interactive]` sentinel)

When `/run` is NOT autonomous (`AUTONOMOUS` is false), a phase spawned as an Agent subagent
cannot reach a human — `AskUserQuestion` is not provisioned to subagents (POC finding, see
`__QUOIN_HOME__/memory/decision-gate-guard.md`). So a decision-gating phase (`/end_of_task`,
`/gate`, `/implement`, `/rollback`) spawned by a non-autonomous `/run` would silently stall or
proceed on a default. To prevent that, `/run` prefixes the `[no-interactive]` sentinel onto
EVERY non-autonomous phase-subagent spawn prompt (the same 9 direct sub-phase spawns listed
under Autonomous propagation, PLUS every subagent-mode `/gate` spawn), so any decision gate
reached in a spawned phase FAILS CLOSED (writes `needs-decision-{task}.md`, emits
`gate-result: NEEDS-DECISION`) instead of stalling.

- **Mutual exclusivity:** `[autonomous]` and `[no-interactive]` are mutually exclusive per
  spawn. Under `AUTONOMOUS`, `/run` injects `[autonomous]` (pre-authorized answers); when NOT
  autonomous, `/run` injects `[no-interactive]` (fail-closed). Never both on the same spawn.
- **INLINE-GATE EXCLUSION:** the injection applies ONLY to phase-subagent spawns and
  subagent-mode `/gate` spawns. The inline post-implement and post-review gates run in the
  FOREGROUND `/run` session where a human IS reachable — `/run` MUST NOT inject
  `[no-interactive]` onto them, or a normal interactive `/run` would wrongly fail-close its own
  inline gate. (This mirrors the inline-vs-spawn boundary the Autonomous propagation section
  states for `[autonomous]` inline gates.)
- **`/thorough_plan` is excluded:** `/run` does NOT inject `[no-interactive]` onto the
  `/thorough_plan` spawn — `/thorough_plan` spawns no fail-closed skill (its deeper
  `/plan`/`/critic`/`/revise` spawns have no decision gate), so injecting it would be a
  false-positive with no benefit (R-06 containment).
- **Stacking:** a spawn prompt may read `[no-redispatch] [no-interactive] <task description>`.

## Routing a NEEDS-DECISION phase return

A spawned phase subagent that fails closed emits a structured
`gate-result: NEEDS-DECISION` block as its final message (and has already written
`needs-decision-{task}.md` under `.workflow_artifacts/memory/`). `/run` MUST recognize
`NEEDS-DECISION` as a phase-return token alongside review-`BLOCKED` and gate-`FAIL`, and route
it the SAME way: surface the block to the user, STOP the pipeline, and do NOT silent-proceed to
the next phase. Under `AUTONOMOUS` this composes with the existing hard-stop/halt-sentinel path
— the phase already wrote its own `needs-decision-{task}.md`, and `/run` treats the
NEEDS-DECISION return as a hard stop (it never auto-resolves a decision the phase could not
surface).

## Autonomous hard stops (halt-sentinel)

Under `AUTONOMOUS`, every hard stop writes a halt-sentinel **before exit**, then stops — Stage 1 forward-compatible groundwork for a future Stage 2 supervisor. Stage 1 only *writes* the sentinel; it never consumes one.

- **Location:** `.workflow_artifacts/memory/autonomous-halt-{task}.md` — deliberately OUTSIDE the task folder, so the record survives `/end_of_task`'s later move of the task folder into `finalized/`.
- **Schema (one line each):** `task`, `phase`, `reason`, `timestamp`, `resume_hint`.
- **The six hard-stop sites** (each documented at its own phase section below; all resolve here):
  1. **Review BLOCKED** (Phase 5) — `phase: review`, `reason: <blocking issues summary>`.
  2. **Gate FAIL after the retry cap** (Checkpoint C, Phase 4) — `phase: gate`, `reason: <failing checks summary>`.
  3. **Review CHANGES_REQUESTED after 3 rounds** (Phase 5) — `phase: review`, `reason: exceeded 3 review rounds without APPROVED`.
  4. **Git conflict** (any phase) — `phase: <phase where the conflict surfaced>`, `reason: <conflict summary>`.
  5. **Branch-hygiene violation** (Setup / any downstream precheck) — `phase: <phase where the violation was detected>`, `reason: <violation summary, e.g. protected-branch commits>`.
  6. **Below-bar formulation** (Formulation quality bar, between Phase 3 and Phase 4) — `phase: formulation`, `reason: <bar failure detail — critic REVISE at cap, or below-threshold Small confidence/smoke gate>`.
- **Never auto-creates a PR.** At every one of the six sites, and everywhere else in this file, the orchestrator NEVER auto-creates a pull request — identical in interactive and autonomous mode. PR creation stays `/pr`, a separate explicit user action.
- **Only under `AUTONOMOUS`.** In plain (non-autonomous) `/run`, these six situations still halt the workflow exactly as documented in their own phase sections — they present the existing interactive prompt instead of writing a halt-sentinel.

## Autonomous progress sentinels (Stage 2 sentinel contract)

Under `AUTONOMOUS`, the completion of each of the 9 resumable phases below is recorded by a per-phase completion sentinel, so a future resumed session (or an external supervisor relaunching one) can tell exactly which phases already finished without re-deriving it from session-state prose. This section is the T-05 contract declaration — the entry-marker write (Setup) and the resume-side read/idempotency logic (the later "Resume" section) land in a later Stage-2 task; this section fixes the write-site map they both consume.

- **Directory:** `.workflow_artifacts/memory/autonomous-progress-{task}/` — same OUTSIDE-the-task-folder rationale as the halt-sentinel above.
- **Write-site map** (phase → completion sentinel, all 9 resumable phases, atomic write `printf > f.tmp && mv f.tmp f`):
  1. **discover** (Phase 1) → writes `autonomous-progress-{task}/discover.done`.
  2. **enrich** (Phase 1.4) → writes `autonomous-progress-{task}/enrich.done`.
  3. **specify** (Phase 1.5) → writes `autonomous-progress-{task}/specify.done`.
  4. **fast_path_triage** (Phase 1.6) → writes `autonomous-progress-{task}/fast_path_triage.done`.
  5. **architect** (Phase 2) → writes `autonomous-progress-{task}/architect.done`.
  6. **thorough_plan** (Phase 3) → writes `autonomous-progress-{task}/thorough_plan.done`.
  7. **implement** (Phase 4) → writes `autonomous-progress-{task}/implement.done`.
  8. **review** (Phase 5) → writes `autonomous-progress-{task}/review.done`.
  9. **end_of_task** (Phase 6) → writes `autonomous-progress-{task}/end_of_task.done`.
- **Sub-phase granularity (optional):** a phase MAY additionally write `autonomous-progress-{task}/{phase}.{subphase}.done` for finer-grained progress within itself (e.g. a long `implement` phase checkpointing partial task batches). The counting glob `autonomous-progress-{task}/*.done` is the UNION of both forms.
- **Marker:** `autonomous-run-{task}.marker`, written once at autonomous-span entry (Setup, right after `AUTONOMOUS` is set) — the read/re-establish-on-resume side of this contract is Stage-2 groundwork, documented alongside the later "Resume" section.
- **Done sentinel:** `autonomous-done-{task}.md`, written by `end_of_task` LAST, after its other terminal side effects, outside the archived folder — same rationale as the halt-sentinel.

## Phase sequence

```
Phase 1: DISCOVER     (conditional — skip if recent)
Phase 1.4: ENRICH     (default-on prompt — user chooses run/skip each time)
Phase 1.5: SPECIFY    (conditional — skip if Small OR task spec.md exists)
          ↓ Checkpoint A0: user confirms spec
Phase 1.6: FAST_PATH_TRIAGE (conditional — evaluates only on Small or `fast:`; silent otherwise)
Phase 2: ARCHITECT    (conditional — skip if Small)
          ↓ Checkpoint A: user confirms architecture
Phase 3: THOROUGH_PLAN
          ↓ Checkpoint B: user confirms plan
Phase 4: IMPLEMENT
          ↓ Checkpoint C: user confirms implementation
Phase 5: REVIEW
          ↓ Checkpoint D: user confirms review outcome
Phase 6: END_OF_TASK
```

## Pre-phase context budget (per heavy phase spawn) — IVG-141

Before each HEAVY phase spawn — Phase 2 (architect), Phase 3 (thorough_plan),
Phase 4 (implement), Phase 5 (review) — run the on-demand context-budget guard in
the FOREGROUND top-level `/run` session (this is the PRIMARY / authoritative
measurement point; it measures the context that is about to spawn the phase). Do
NOT run it before the lighter Phase 1 / 1.4 / 1.5 / 1.6 / 6 (Phase 1.6 is inline, `D-12`, and never spawned; heavy-phase-only scope).
This is additive to the existing checkpoints; it never lowers or touches any hook
threshold.

**Bypass:** if the incoming prompt carries `[no-phase-budget]` (strip at
bootstrap) OR `QUOIN_DISABLE_PHASE_BUDGET=1` is set, SKIP the guard entirely
(power-user path, mirrors `[no-session-age-guard]`) and spawn the phase as today.

**Run the guard (foreground):**
```bash
python3 __QUOIN_HOME__/scripts/context_budget_guard.py --project-root "$PROJECT_ROOT"
```
- Exit 0 (`OK|...|` or `OK|disabled|`, incl. the `OK|0|` fail-OPEN path) → proceed
  with the phase spawn. On the fail-OPEN/missing-helper `OK|0|` path emit
  `[quoin-budget: guard unavailable; proceeding]`; otherwise emit nothing.
- Exit 1 (`OVER|util|path`) → run the ORDERED, NON-BLOCKING over-budget sequence
  (identical in interactive AND autonomous; NO prompt, NO `AskUserQuestion`, NO
  decision-gate marker):
  1. ALWAYS save the boundary checkpoint (durable resume point):
     ```bash
     python3 __QUOIN_HOME__/scripts/boundary_checkpoint.py \
       --project-root "$PROJECT_ROOT" --task "<task>" --skill run \
       --sid "$CLAUDE_CODE_SESSION_ID" --branch "<branch>" \
       --resume-command "/run --resume <task>" \
       --phase-label "before Phase N spawn" --plan-path "<current-plan.md>" || true
     ```
  2. Emit the one-line advisory:
     `[quoin-budget: util NN% ≥ threshold at run boundary; checkpoint saved → /run --resume <task>]`
  3. Then react (this is the ONLY branch that can halt, and only on opt-in):
     - **default** → PROCEED with the phase spawn. Never prompts, never blocks.
       Identical in interactive and autonomous.
     - **`QUOIN_PHASE_BUDGET_BLOCK=1`** (opt-in, default off) → print a
       fresh-session resume instruction (`/run --resume <task>`) and STOP. A
       printed instruction, NOT an `AskUserQuestion`.
  4. **`_AUTONOMOUS`** (`[autonomous]` / `--autonomous`) → the SAME non-blocking
     path as (1)-(3), and ADDITIONALLY perform the existing Hook-cooperation
     self-checkpoint + supervisor relaunch via `/run --resume --autonomous`
     (reuse the "Hook cooperation (autonomous)" contract — no new mechanism).
     Interactive has no supervisor → it continues in-session with the checkpoint
     as a clean-recovery backstop.

This adds NO new `AskUserQuestion` site and NO decision-gate `best-effort` marker
(the over-budget path is non-blocking). It also does NOT touch `/run`'s existing
`[no-interactive]` injection / `/thorough_plan` exclusion wiring — those are
unrelated to this non-blocking budget check and stay exactly as documented above.

## On-behalf cost capture (`QUOIN_INLINE_COST_CAPTURE`, flag-gated, D-1/D-2/D-3, IVG-111 stage 3)

When `QUOIN_INLINE_COST_CAPTURE=1`, this applies at EVERY managed phase spawn below — discover,
enrich, specify, architect, thorough_plan, implement, review, end_of_task — and the two post-phase
`/gate` subagent spawns (spec→architect boundary at Checkpoint A0, architecture boundary at
Checkpoint A). The implement-phase inline gate (no spawn) is NOT managed — it runs in-session,
nothing to suppress. The fast-path triage step (Phase 1.6) is likewise NOT in this roster — it
runs inline (`D-12`), never as a spawned subagent, so there is no child session to suppress the
self-write for; this list is deliberately unchanged.

At each spawn: (1) prepend `[quoin-onbehalf]` to the spawn prompt — stacks with
`[autonomous]`/`[no-interactive]`/`[no-redispatch]` per the existing propagation rules
(order-independent, each leaf strips its own copy) — so the child SKIPS its own session-start
cost-ledger self-write (T-06 predicate); (2) bind `AID`/`TUID` per `proc:agentid-capture` (stage-3
plan) — `AID` is the `agentId` field from the Agent tool's return for that spawn, transcribed
literally by this orchestrator (model-in-the-loop, not a shell capture); `TUID` is this spawn's own
Agent tool_use id; fallback (agentId absent/empty, R-12): `AID = TUID` if present, else
`"<parent-session-uuid>-<phase>-<utc-ts>"`, forcing `ATTR="src=unresolved"` (discard any sidecar
hit once agentId capture failed); (3) AFTER the subagent returns and its phase artifact is
verified on disk, run this on-behalf ledger write with that phase's model and `uuid=<AID>` —
REPLACES each phase's existing "verify the cost ledger has a new entry... if not, best-effort
append" step, and REPLACES the suppressed child self-write (D-2), net exactly one row per managed
phase:
```bash
SID="$CLAUDE_CODE_SESSION_ID"
ATTR="$(python3 __QUOIN_HOME__/scripts/agent_transcript_cost.py \
          --sid "$SID" --agent-id "$AID" --tool-use-id "$TUID" 2>/dev/null)"
[ -z "$ATTR" ] && ATTR="src=unresolved"   # MIN-1: key on empty stdout, not exit code
printf '%s | %s | %s | %s | task | %s | %s | %s\n' \
  "$AID" "$(date -u +%Y-%m-%d)" "PHASE" "MODEL" \
  "on-behalf: PHASE via /run" "0" "$ATTR" >> "$LEDGER"
```
Nested-orchestrator case is correct by construction: `/run` prepends `[quoin-onbehalf]` to the
`/architect` and `/thorough_plan` spawns; those children strip their own marker (skip their own
self-write, per T-06/D-9) and independently prepend a FRESH `[quoin-onbehalf]` to THEIR OWN
children (the architect critic spawn; thorough_plan's plan/critic/revise/enrich spawns) — per-spawn,
non-inherited, no double-suppression.

**`end_of_task` note:** `end_of_task` is spawned in Phase 6 but is NOT a bootstrap cost-ledger
self-writer today (it aggregates at task close rather than self-writing a session-start row), so
there is no child self-write to suppress for it — the on-behalf write above still fires for the
`end-of-task` phase (parity with the other 7 phases); it simply has no corresponding T-06 skip
predicate to pair with. This "7" counts the on-behalf MANAGED phase roster (the 8 spawned phases
enumerated above, of which `end_of_task` is one) — the fast-path triage step runs inline (`D-12`)
and is never spawned, so it is deliberately outside this mechanism and this count is unchanged.

**Flag unset:** none of the above applies — every phase spawn behaves as documented today (child
self-writes, or `end_of_task` aggregates as today; each phase's existing best-effort ledger-verify
fallback stays in effect unchanged).

## Phase 1 — Discover (conditional)

**Skip condition:** Check if `.workflow_artifacts/cache/_staleness.md` exists AND its modification time is less than 7 days old. Fall back to `.workflow_artifacts/memory/repo-heads.md` if `_staleness.md` does not exist:
```bash
find .workflow_artifacts/cache/_staleness.md -mtime -7 2>/dev/null || find .workflow_artifacts/memory/repo-heads.md -mtime -7 2>/dev/null
```
Also check for `repos-inventory.md` (plural) as secondary confirmation.

- **If skipping:** tell the user "Discovery files are recent (<N> days old) — skipping /discover. Say 'rediscover' to force a fresh scan."
- **If running:** spawn `/discover` as a subagent session (same mechanism as `/thorough_plan` uses for `/critic` — see its "Invoking each agent" section). Pass the project folder path. No gate runs after discover — it feeds directly into architect.

After the phase, verify the cost ledger has a new entry for the `discover` phase. If not (subagent didn't record), append a best-effort entry: `unknown-discover-<timestamp> | <date> | discover | opus | task | /run subagent (no UUID recorded)`. Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=discover, model=opus).

Under `AUTONOMOUS`, also write the phase's completion sentinel `autonomous-progress-{task}/discover.done` (atomic write — T-05/T-10 write-site map) — the T-09 resume-reader depends on this file's presence to know Phase 1 finished.

## Phase 1.4 — Enrich (default-on prompt)

On entry, PROMPT via `AskUserQuestion`: "Run prompt enrichment on this task, or skip?"

- Header: "Enrich"; multiSelect: false
- Option 1: label "Run /enrich" — description: "Sharpen the raw task prompt before specify/architect (fills genuine gaps, writes enriched-prompt.md)."
- Option 2: label "Skip" — description: "Proceed straight to the next phase without enrichment."

- **If skipping:** tell the user "Skipping /enrich per your choice." and proceed to Phase 1.5.
- **If running:** spawn `/enrich` as a subagent session (same mechanism as the Phase 1.5 specify spawn). Pass the raw task description and the task folder path.

After the phase, verify the cost ledger has a new entry for the `enrich` phase. If not (subagent didn't record), append a best-effort entry: `unknown-enrich-<timestamp> | <date> | enrich | opus | task | /run subagent (no UUID recorded)` (mirrors the Phase 1/Phase 1.5 best-effort append pattern). Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=enrich, model=opus).

Under `AUTONOMOUS`, also write the phase's completion sentinel `autonomous-progress-{task}/enrich.done` (atomic write — T-05/T-10 write-site map) — including when enrich was skipped via the AskUserQuestion prompt above (a skipped phase still counts as reaching this point in the pipeline; resume must not re-offer the prompt).

**No `/gate` spawn after enrich** — proceed straight to Phase 1.5 (Q-1: enrich is a lightweight upstream sharpening pass, not a phase boundary that needs a quality gate).

Under non-interactive dispatch (no way to present `AskUserQuestion`), degrade to best-effort: run `/enrich` anyway and flag assumptions, never block the pipeline waiting for an answer that can't be given.

## Phase 1.5 — Specify (conditional)

**Skip condition:** Task profile is Small OR `<task-root>/spec.md` already exists.

- **If skipping:** tell the user "Skipping /specify (Small task | spec already exists)."
- **If running:** spawn `/specify` as a subagent session (same mechanism as the Phase 2 architect spawn). Pass the task description and the task folder path.

After the phase, verify the cost ledger has a new entry for the `specify` phase. If not (subagent didn't record), append a best-effort entry: `unknown-specify-<timestamp> | <date> | specify | opus | task | /run subagent (no UUID recorded)` (mirrors the Phase 1/Phase 2 best-effort append pattern). Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=specify, model=opus).

After specify completes, spawn `/gate` as a subagent session (spec→architect boundary — subagent dispatch, mirrors the post-architect gate at Phase 2; audit-log persistence mandatory). Under `QUOIN_INLINE_COST_CAPTURE=1`, this gate spawn also follows "On-behalf cost capture" above (phase=gate, model=sonnet).

Under `AUTONOMOUS`, also write the phase's completion sentinel `autonomous-progress-{task}/specify.done` (atomic write — T-05/T-10 write-site map), including when specify was skipped by its own skip condition.

**Checkpoint A0:**
```
Phase complete: Specify
Artifact: .workflow_artifacts/{task-name}/spec.md   (task feature spec — task root)

Summary:
- {goals / user stories — 2-3 bullets}
- {key acceptance criteria}

Gate: PASSED / FAILED

Continue to architecture? (yes / no / show spec)
```

## Phase 1.6 — Fast-path triage (conditional)

`profile` (Small/Medium/Large) keeps today's meaning and classification. `route` is a separate,
orthogonal concept — `full` (default) or `fast`. This phase always executes, so its place in the
resumable-phase roster and its sentinel contract stay whole — but it has two behavioral modes:

- **Silent no-op mode.** Setup profile is Medium or Large AND no `fast:` tag was given → emit
  `route=full` with zero user-facing output, zero prompts, zero extra model calls, and no
  `triage-decision.md`. This mirrors the existing skip behavior at Phase 1.4 and Phase 1.5 exactly.
  A plain (non-autonomous) run adds zero artifacts and zero behavior delta here; an autonomous run
  adds exactly one thing — its own completion sentinel (below) — and nothing else.
- **Evaluating mode.** Fires when the Setup profile is Small, or a `fast:` tag was given from any
  profile. Only in this mode is eligibility assessed, Checkpoint A1 raised (see below), and
  `triage-decision.md` written.

**Evidence ladder.** Read the strongest available input, in this precedence order:
- `<task-root>/spec.md`, when it exists.
- else `<task-root>/enriched-prompt.md`.
- else the raw task description.

A raw task description alone can never satisfy eligibility criterion 5 below, so evaluating mode
with no spec and no enriched prompt degrades to `route=full` — silently, like any other ineligible
evaluation.

**Eligibility — all five must hold:**
- Bounded file set inside a single module.
- No new cross-module or cross-repo integration point.
- Matches a pattern already present in the codebase.
- No data migration, auth change, or public-contract change.
- The evidence's acceptance criteria are already concrete enough to serve directly as an
  implementation checklist.

This is visibly stricter than the existing Small-task threshold: Small alone does not require all
five of these, fast-path eligibility does.

A Small task that evaluates to ineligible is ALSO silent: it emits `route=full`, raises no
checkpoint, and writes no decision artifact.

**Checkpoint A1.** Fires in evaluating mode only, and only once eligibility has passed (an
ineligible evaluation stays silent, per above — no checkpoint, no artifact). Raised inline by the
orchestrator via `AskUserQuestion`, never by a subagent — `AskUserQuestion` is not provisioned to
subagents.

Prompt: "Fast-path triage found this task eligible for the fast route (confidence {confidence}).
Take the fast path, take the full path, or see why?"

- Header: "Fast-path triage"; multiSelect: false
- Take the fast path — label "Take fast path" — description: "Skip the architecture and planning
  phases; dispatch `/implement` directly against a mechanically-derived plan stub."
- Take the full path — label "Take full path" — description: "Ignore the fast-route recommendation
  and run the full pipeline exactly as today."
- Show rationale — label "Show rationale" — description: "Print the eligibility reasoning and
  evidence tier used, then re-ask this same question."

When a `fast:` tag was supplied, the checkpoint still fires — evaluating mode is entered by
either trigger — but with "Take fast path" pre-selected as the default option (`D-07`); the user
may still override to the full path.

**If the classified profile is Large:** the prompt text must also warn BY NAME that taking the
fast path drops the dedicated `/security_review` OWASP pass — that pass only runs on Large-profile
reviews today, per `/review`'s own fan-out contract — so the user sees this tradeoff before
choosing. The full-path option remains available at this same prompt.

Under `[no-interactive]` (no human reachable to answer): fail closed to `route=full`. A route is
never guessed as "fast" without a human confirming it at this checkpoint.

Under `[autonomous]`: Checkpoint A1 is skipped entirely — no `AskUserQuestion` is raised — and the
route already produced by eligibility evaluation is taken as-is, subject to the formulation
quality bar described later in this file.

Refer to the existing yes/no checkpoint table only in plain English (e.g. "the existing yes/no
checkpoint table") anywhere near this checkpoint's description — never reproduce its heading text.

**Ledger row.** Write phase `triage` (the cost-ledger's fixed phase vocabulary is not extended) —
note this is deliberately a DIFFERENT string from the roster/sentinel/heading name
`fast_path_triage` used everywhere else in this file; do not write `fast_path_triage` into the
ledger. Written inline by the orchestrator, since this step runs inline and never as a subagent.

**Session state.** Gains the chosen route, its confidence, and the evidence tier that fed the
decision, recorded at this phase boundary like every other phase.

Under `AUTONOMOUS`, once evaluated (both modes), also write the phase's completion sentinel
`autonomous-progress-{task}/fast_path_triage.done` (atomic write — T-05/T-10 write-site map). A
plain (non-autonomous) run never writes this file, in either mode.

## Phase 2 — Architect (conditional)

**Skip condition:** Task profile is Small.

- **If Small:** tell the user "Small task — skipping /architect, proceeding directly to planning."
- **If running:** spawn `/architect` as a subagent session, passing the task description, paths to discovery output files (`repos-inventory.md`, `architecture-overview.md`, `dependencies-map.md`), and the path to `<task-root>/spec.md` if it exists (read-if-exists).
  - **Note:** `/architect` now includes a Phase 4 critic loop (max 2 rounds default, 4 in strict mode); expect 1-2 additional `critic` phase rows in the cost ledger per round. If Phase 4 triggers the cost-guard confirmation (pre-round-2), the architect subagent will pause for user input — watch for the prompt `[critic round 2 starting — ~$10-30 estimated based on body size]` in the subagent output.

After the phase, verify the cost ledger has a new entry for the `architect` phase. If not, append a best-effort entry with `unknown-architect-<timestamp>`. Also check for `critic` phase rows from Phase 4 (1-2 expected; accept their absence if Phase 4 was skipped via `max_rounds: 0`). Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=architect, model=opus) — the Phase 4 critic-round rows are architect's OWN on-behalf writes, per its own on-behalf mechanism, independent of this one.

Under `AUTONOMOUS`, also write the phase's completion sentinel `autonomous-progress-{task}/architect.done` (atomic write — T-05/T-10 write-site map), including when architect was skipped for a Small task.

After architect completes, spawn `/gate` as a subagent session (architecture gate — subagent dispatch required for audit-log persistence). Under `QUOIN_INLINE_COST_CAPTURE=1`, this gate spawn also follows "On-behalf cost capture" above (phase=gate, model=sonnet).

**Checkpoint A:**
```
Phase complete: Architecture
Artifact: .workflow_artifacts/<task-name>/architecture.md

Summary:
- <key architectural decisions>
- <stages identified>
- <integration points>
- Critic verdict (Phase 4): PASS / REVISE / skipped

Gate: PASSED / FAILED

Continue to planning? (yes / no / show architecture)
```

## Phase 3 — Thorough Plan

Spawn `/thorough_plan` as a subagent session, passing:
- Task profile and max_rounds
- Task description (with tokens stripped)
- Path to `architecture.md` (if it exists)
- Path to `spec.md` (if it exists)
- Repo paths

`/thorough_plan` handles its own internal plan→critic→revise loop and runs its own post-plan smoke gate.

After the phase, verify the cost ledger has new entries for `thorough-plan`, `plan`, `critic`, and (if applicable) `revise` phases. If not, append best-effort entries with `unknown-<phase>-<timestamp>`. Under `QUOIN_INLINE_COST_CAPTURE=1`, the `thorough-plan` row is instead the on-behalf write per "On-behalf cost capture" above (phase=thorough-plan, model=opus) — the plan/critic/revise/enrich rows are thorough_plan's OWN on-behalf writes, per its own on-behalf mechanism, independent of this one.

Under `AUTONOMOUS`, also write the phase's completion sentinel `autonomous-progress-{task}/thorough_plan.done` (atomic write — T-05/T-10 write-site map).

**Checkpoint B:**
```
Phase complete: Planning
Artifact: <task_dir>/current-plan.md (where <task_dir> = `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]`; architecture.md ALWAYS at task root per D-03)
Profile: <Small|Medium|Large>, <N> round(s), verdict: PASS

Summary:
- <what will be built — 3-5 bullets>
- <files affected>
- <key risks noted>

Continue to implementation? (yes / no / show plan)
```

## Formulation quality bar (autonomous)

Only evaluated under `AUTONOMOUS` — plain `/run` never evaluates this bar and proceeds straight from Checkpoint B to Phase 4 exactly as it does today. This bar sits between Phase 3 (Thorough Plan) and Phase 4 (Implement); it is the sole safety substitute for the human checkpoint that autonomous mode removes at Checkpoint B.

- **Medium/Large:** require the `thorough_plan` critic loop to have converged with a **PASS** verdict. Read the verdict `thorough_plan` returns (or its session-state `## Current stage` trail) — exhausting `max_rounds` while the last critic verdict is still REVISE does **NOT** pass the bar, even though `thorough_plan` itself terminates normally at the round cap.
- **Small:** require BOTH (a) the post-plan smoke gate to PASS, AND (b) the confidence signal to be `>= QUOIN_AUTONOMOUS_CONFIDENCE_THRESHOLD` (default `0.7`). Small skips `/specify` and `/architect`, so the confidence signal comes from the single-pass `/plan` skill's own `confidence: <float 0..1>` line (see `plan/SKILL.md`) — optionally combined with an `enrich`-emitted confidence value (if enrich ran and emitted one), in which case take the **minimum** of the two.
- **Below the bar → HARD STOP.** This is Hard-stop #6 (below-bar formulation) in "## Autonomous hard stops" above — write the halt-sentinel (`phase: formulation`) before exit, then stop. Do **NOT** enter Phase 4 / Execution on a formulation that hasn't cleared the bar.
- The runtime-neutral shape of this bar is mirrored in `quoin/core/skills/run.md`'s "Autonomous mode (opt-in)" section.

## Phase 4 — Implement

Spawn `/implement` as a subagent session, passing path to `<task_dir>/current-plan.md` (where `<task_dir>` is resolved via `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]` in Setup §) and all repo paths. Because the user invoked `/run` and confirmed at Checkpoint B, the `/run` exception in `implement/SKILL.md` applies.

After the phase, verify the cost ledger has a new entry for the `implement` phase. If not, append a best-effort entry with `unknown-implement-<timestamp>`. Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=implement, model=sonnet).

Under `AUTONOMOUS`, once Checkpoint C confirms (gate passed, continuing to review), also write the phase's completion sentinel `autonomous-progress-{task}/implement.done` (atomic write — T-05/T-10 write-site map).

After implement completes, run `/gate` inline (read `/gate/SKILL.md` from the same session and execute the gate process directly — do not spawn a subagent). Step 5 audit-log persistence applies in inline mode per the gate skill's existing rule.
- Standard level for Small/Medium
- Full level for Large

**Checkpoint C:**
```
Phase complete: Implementation
Gate: PASSED / FAILED

Summary:
- <files created/modified>
- <tests written/passing>
- <any deviations from plan>

Continue to review? (yes / no / show changes)
```

If the gate **failed**: present the failures and ask "Fix and retry, or stop?"
- "fix" → spawn `/implement` again for the failing items, then re-run `/gate` inline (post-implement boundary — same inline mechanism as the primary path; audit-log persistence applies per `/gate/SKILL.md`)
- "stop" → halt, preserve artifacts

Under `AUTONOMOUS`: auto-select "fix" and retry once (retry cap = 1 automatic retry). If the gate still fails after that one retry, this is Hard-stop #2 (Gate FAIL after the retry cap) — write the halt-sentinel per "## Autonomous hard stops" before exit, then stop. Never fall back to a silent proceed, and never ask.

If the user says "show changes": run `git diff --stat` and display, then re-ask.

## Phase 5 — Review

Spawn `/review` as a **fresh subagent session** (unbiased assessment requires clean context). Pass plan path, architecture path, spec path (if it exists), and repo paths.

Read the review output (`review-*.md`) and check the verdict.

After the phase, verify the cost ledger has a new entry for the `review` phase. If not, append a best-effort entry with `unknown-review-<timestamp>`. Under `QUOIN_INLINE_COST_CAPTURE=1`, this step is instead the on-behalf write per "On-behalf cost capture" above (phase=review, model=opus).

Under `AUTONOMOUS`, once Checkpoint D confirms (APPROVED or accepted, gate passed), also write the phase's completion sentinel `autonomous-progress-{task}/review.done` (atomic write — T-05/T-10 write-site map).

**If APPROVED:** run `/gate` inline (Full level, post-review — read `/gate/SKILL.md` from the same session and execute the gate process directly). Step 5 audit-log persistence applies in inline mode per the gate skill's existing rule. Proceed to Checkpoint D.

**If CHANGES_REQUESTED:** present the issues to the user. Offer:
1. **"fix"** → spawn `/implement` again with the review issues as the spec. After fix-implement completes, re-run the post-implementation gate inline (same level as before; audit-log persistence per `/gate/SKILL.md`). Then re-spawn `/review`. Cap at 3 review rounds to prevent infinite cycling.
2. **"accept"** → treat as approved despite requested changes. Log this decision in session state. Proceed to Checkpoint D.

Under `AUTONOMOUS`: auto-select "fix" at each round — never auto-select "accept". If still CHANGES_REQUESTED after the 3-round cap, this is Hard-stop #3 (Review CHANGES_REQUESTED after 3 rounds) — write the halt-sentinel per "## Autonomous hard stops" before exit, then stop.

**If BLOCKED:** present the blocking issues. **STOP.** Do not offer to continue. Tell the user: "Review found blocking issues. The workflow cannot continue until these are resolved. Artifacts are preserved at `.workflow_artifacts/<task-name>/`."

Under `AUTONOMOUS`: this is Hard-stop #1 (Review BLOCKED) — write the halt-sentinel per "## Autonomous hard stops" before exit, then stop (no `AskUserQuestion`, no silent proceed).

**Checkpoint D** (after APPROVED or accepted):
```
Phase complete: Review
Verdict: APPROVED
Artifact: <task_dir>/review-<N>.md (where <task_dir> = `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name> [--stage <N-or-name>]`; architecture.md ALWAYS at task root per D-03)
Gate: PASSED

Summary:
- <key findings>
- <issues flagged (if any)>

Finalize and push? (yes / no / show review)
```

## Phase 6 — End of Task

Spawn `/end_of_task` as a subagent session. Because the user invoked `/run` and confirmed at Checkpoint D, the `/run` exception in `end_of_task/SKILL.md` applies. All 8 steps run as normal (pre-flight, commit, push, lessons, session state, cost aggregation, archive, report). Under `QUOIN_INLINE_COST_CAPTURE=1`, this spawn also follows "On-behalf cost capture" above (phase=end-of-task, model=sonnet) — see the `end_of_task` note there (no T-06 skip predicate to pair with; this write is additive, not a suppression-replace).

Under `AUTONOMOUS`, once `/end_of_task` returns successfully, also write the phase's completion sentinel `autonomous-progress-{task}/end_of_task.done` (atomic write — T-05/T-10 write-site map). This is a separate sentinel from `end_of_task`'s own terminal `autonomous-done-{task}.md` (T-11) — this one records phase-level progress consistent with the other 8 phases; the done-sentinel is the overall supervisor-loop terminal signal.

After completion, present the final report:
```
Task complete: <task-name>

Branch: <branch-name> → pushed to origin
Profile: <Small|Medium|Large>
Phases: discover(<skipped|ran>), architect(<skipped|ran>), plan(<N> rounds), implement, review(APPROVED), finalized
Archived: .workflow_artifacts/<task-name>/ → finalized/
Cost ledger: .workflow_artifacts/<task-name>/cost-ledger.md (<N> sessions tracked)

Next: run /pr to create a pull request from the branch.
```

## Checkpoint interaction protocol

At every checkpoint, the orchestrator presents a concise summary and waits for explicit user input:

| Response | Action |
|----------|--------|
| `yes` / `y` / `continue` / `go` | Proceed to next phase |
| `no` / `n` / `stop` | Halt workflow; preserve all artifacts; tell user how to resume manually |
| `show <artifact>` | Display the artifact (architecture / plan / changes / review / discover), then re-ask |
| `skip` | Skip the next phase (only valid for optional phases: discover, specify, architect) |
| Any other input | Treat as feedback or clarification; answer and re-ask |
| **Autonomous** (`AUTONOMOUS=true`) | A checkpoint whose gate/verdict is PASS auto-resolves to "continue" — NO `AskUserQuestion` is called and NO wait for user input. A non-PASS checkpoint (gate FAILED, review CHANGES_REQUESTED/BLOCKED, below-bar formulation) is NEVER a silent proceed — it routes to the hard-stop / halt-sentinel logic instead. |

**Never proceed without explicit confirmation** (non-autonomous mode). Ambiguous responses → ask for clarification. Under `AUTONOMOUS`, confirmation is auto-supplied per the row above — but a non-PASS result is never a silent proceed.

## Resume

If invoked as `/run --resume <task-name>` (or "resume the run for <task-name>"):

**Step 0 (T-09) — re-establish autonomous mode from the marker, BEFORE any other
decision point.** Read `.workflow_artifacts/memory/autonomous-run-{task}.marker`
(the T-05/T-10 marker sentinel) for `<task-name>` FIRST — before reading session
state, before checking completion sentinels, before anything else:
- If the marker exists: set `AUTONOMOUS=true` immediately, whether or not the
  resume invocation's own text carries `--autonomous` (belt-and-suspenders, D-06).
  This is what guarantees a headless `claude -p "/run --resume --autonomous
  {task}"` relaunch never reverts to interactive and stalls waiting on a prompt
  no one is present to answer.
- If the marker is absent: `AUTONOMOUS` is determined normally from the invocation
  text — plain (non-autonomous) resume, unchanged from pre-T-09 behavior.

**Step 1 (T-09) — determine the next phase from completion sentinels, never from
session-state prose alone, when the sentinel contract is present.** Read
`.workflow_artifacts/memory/autonomous-progress-{task}/` (the T-05/T-10 write-site
directory) for `<task-name>`:
- A phase whose `{phase}.done` sentinel EXISTS is finished — never re-run it, even
  if session-state prose about that phase is ambiguous, stale, or missing.
- A phase whose `{phase}.done` sentinel is ABSENT is not finished — never skip it.
- If a phase's sentinels are only PARTIALLY present at sub-phase granularity
  (`{phase}.{subphase}.done` for some but not all sub-phases of one phase — e.g. a
  long `implement` phase that checkpointed partial task batches), resume that phase
  at the first sub-phase lacking its own completion sentinel, rather than
  restarting the whole phase from scratch.
- If NO `autonomous-progress-{task}/` directory exists for the task (a resume that
  predates the sentinel contract, or a non-autonomous run that never wrote one),
  fall back to the pre-T-09 behavior:
  1. Read `.workflow_artifacts/memory/sessions/<latest>-<task-name>.md` to find the last completed phase.
  2. Identify the next phase.

**Step 2 — announce and proceed.** Tell the user: "Resuming `<task-name>` from
Phase N (`<phase-name>`). Phases 1–M already completed." Start from the next
uncompleted phase — do not re-run completed phases.

**Headless autonomous path (T-09):** when Step 0 established `AUTONOMOUS=true`
from the marker, resume proceeds directly into Phase N with ZERO
`AskUserQuestion` calls — the sentinel-derived phase selection above IS the
decision, so there is nothing left to ask. A headless
`/run --resume --autonomous {task}` relaunch with the marker present therefore
raises zero `AskUserQuestion` prompts by construction.

Note: `--resume` is a convention the skill checks for in the input, not a CLI flag.

## Session state tracking

Update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` after each phase completes. Track:
- Current phase and status
- Completed phases and their outcomes (gate results, review verdicts, rounds taken)
- Any stopped-at checkpoint (so the user can resume manually)

## Subagent session management

Each phase runs as a separate subagent session — never inline. This keeps the orchestrator's context lean across a full pipeline run.

- Pass only file paths and parameters to each subagent — never raw content
- After each subagent completes, read its output artifacts from disk
- Spawning mechanism: same as `/thorough_plan`'s "Invoking each agent" section — the `Skill` tool invokes each subagent as a fresh session. Phases are sequential (not parallel).
- Known gate/SKILL.md diagram inconsistency: `gate/SKILL.md` shows a gate after discover, but `CLAUDE.md`'s workflow sequence does not. This skill follows `CLAUDE.md` — no gate after discover. The gate skill determines context from disk artifacts, so the discrepancy has no runtime effect.
- **Within-phase isolation, autonomous (T-12).** Under `AUTONOMOUS`, the "paths and parameters only" rule above is a HARD requirement, not just a lean-context preference: a phase subagent returns a PATH plus a short summary, never raw file content, so the orchestrator's own transcript stays bounded across a multi-relaunch autonomous span. A phase subagent that nears its own limit writes a checkpoint to disk and returns a structured `PARTIAL` signal instead of exhausting itself mid-phase; the orchestrator responds by dispatching a FRESH subagent to CONTINUE that same phase from the checkpoint (see "Within-phase PARTIAL continuation" under "## Error handling" below). This keeps orchestrator context bounded WITHIN a phase, complementing the cross-phase relaunch a supervisor performs between phases.
- **Self-utilization vs. scope-cap fallback.** A phase subagent SHOULD attempt to read its own transcript utilization to decide when to checkpoint-and-return-`PARTIAL` proactively, before it is forced to stop mid-tool-call. When a subagent cannot resolve its own transcript utilization, it MUST fall back to a fixed tool-use scope cap (mirroring `end_of_task`'s existing "Scope cap: ~N tool uses; if blocked, write to disk and return" pattern) so `PARTIAL` is still returned deterministically rather than the subagent silently running until it is killed.

## Parallel tasks

Multiple `/run` sessions can operate simultaneously on different tasks — each uses its own `.workflow_artifacts/<task-name>/` subfolder. Start each in a separate chat session to avoid shared context. There is no interference as long as tasks target different repos or non-overlapping files.

## Cost estimate

Rough estimates only — `/end_of_task` computes actual costs from the cost ledger and presents them in the final report.

| Profile | Approximate total |
|---------|------------------|
| Small | ~$2.75–$3.50 |
| Medium | ~$3.75–$5.50 |
| Large | ~$6.00–$8.50+ |

## Error handling

- **Subagent failure:** inform the user, offer to retry the phase
- **Gate failure:** present failures, offer to fix (re-run the phase) or stop
- **Git errors:** report and let the user resolve. **Git conflict (Hard-stop #4, autonomous):** under `AUTONOMOUS`, a git conflict (merge/rebase/push conflict, at any phase) is a hard stop — write the halt-sentinel per "## Autonomous hard stops" before exit, then stop; never attempt automatic conflict resolution.
- **Context exhaustion:** save state, instruct user to resume with `/run --resume <task-name>`
- **Stream-idle timeout recovery (orchestrator-only).** If a spawned subagent
  returns a tool_result whose content contains `Stream idle timeout - partial response received`:
  do NOT use SendMessage to resume the dead child (this also
  times out — Apr 28 10:19 incident). Instead, re-dispatch a
  FRESH narrower child:
    a. Halve the scope: if the round was processing N critic
       issues, dispatch a new /revise(-fast) targeting the first
       ⌈N/2⌉ issues only; queue the rest for a follow-up dispatch
       in the same round counter.
    b. Pass the partial output (if any artifact was written to
       disk) to the new child as additional context.
    c. Cap retries at 2 per round; on a third stream-idle
       timeout, escalate to the user with the partial artifact
       and ask whether to proceed to the next phase with a flagged
       artifact, or stop.
  NOTE: This retry only fires for subagents dispatched BY /run.
  Standalone invocations of sub-skills have no automatic retry.
- **Within-phase PARTIAL continuation (autonomous, T-12).** When a phase
  subagent returns a structured `PARTIAL` signal (see "Subagent session
  management" above) instead of its normal phase-complete summary:
    a. Read the checkpoint path the subagent wrote to disk (paths-not-content
       — the orchestrator never reads the subagent's raw transcript).
    b. Dispatch a FRESH subagent for the SAME phase, passing the checkpoint
       path so it resumes the phase's own remaining work rather than
       restarting the phase from scratch.
    c. Repeat until the phase returns its normal phase-complete summary
       (not `PARTIAL`) or a hard-stop condition fires.
  This is a WITHIN-phase mechanism — distinct from a supervisor's
  cross-phase relaunch (`autonomous-progress-{task}/{phase}.done`
  sentinels), and distinct from the stream-idle recovery above (which
  responds to a dead/unresponsive child, not a self-reported `PARTIAL`).
  Only fires under `AUTONOMOUS`; a non-autonomous phase subagent that runs
  long is handled by the existing context-exhaustion path above ("save
  state, instruct user to resume").

## Hook cooperation (autonomous)

Under `AUTONOMOUS`, the orchestrator COOPERATES with the existing
context-utilization hooks — it never disables, edits, or lowers any of
their thresholds. This section documents the cooperation mechanism only;
the threshold values themselves live in `hooks/_lib.sh`'s
`read_constants()` and are read here, never redefined.

- **Self-checkpoint before the advisory band.** At `COMPACT_FIRST_BPS`
  (90% utilization) — BEFORE the 70–95% advisory band and well before the
  95% block — the orchestrator self-invokes a checkpoint save and writes a
  `checkpoint-defer-{sid}` marker so the mid-phase advisory in the 70–95%
  band does not re-prompt for a checkpoint the orchestrator already took.
- **Catch the block JSON if it fires anyway.** If utilization still
  reaches the block threshold (`BLOCK_BPS`, 95%), the hook returns a
  `"decision": "block"` response, and the in-flight prompt is already
  saved to `pending-prompt-{sid}.txt` by the hook itself. The
  orchestrator's block-catch logic MUST key on the `"decision"` and
  `"block"` tokens (not a byte-exact no-space literal — the live response
  uses spaces after each colon) so it recognizes the block regardless of
  incidental JSON formatting. On a caught block, the orchestrator stops
  cleanly; an external supervisor (if one is driving this span) relaunches
  a fresh session with `/run --resume --autonomous <task-name>`, which
  re-reads the prompt from `pending-prompt-{sid}.txt` and the
  marker/sentinel contract to resume exactly where it left off.
- **Hooks fail open; the orchestrator never assumes otherwise.** The
  compaction hook never blocks by design — it only ever allows. If a block
  is not observable in a given dispatch shape, the orchestrator relies on
  automatic compaction plus a supervisor's cross-phase relaunch instead of
  waiting on a block signal that may never arrive.
- **Hard constraint.** Autonomous mode NEVER writes to any file under
  `hooks/`, and NEVER modifies or lowers a `QUOIN_*_BPS` constant or any
  other hook threshold — anywhere, under any condition. The cooperation
  described above is entirely additive branches in this document; it adds
  no new hook script and changes no existing one.

## Gate boundaries reference

**Post-architect (Phase 2 boundary):** subagent dispatch (not modified by Stage 3). **Post-implement (Phase 4 boundary primary; recursive recovery paths in the same phase):** all inline — preserve the parent's prompt cache. **Post-review (Phase 5 boundary):** inline. **Post-plan (handled by `/thorough_plan/SKILL.md`):** subagent dispatch. **Post-specify (Phase 1.5 boundary):** subagent dispatch (mirrors post-architect). **There is no `/gate` invocation after `/discover`** (discover feeds directly into specify/architect). Audit-log persistence (`gate-{phase}-{date}.md`) is mandatory at every boundary regardless of mode per `/gate/SKILL.md`.

## Important behaviors

- **Orchestrate, don't perform.** Never write plan content, code, or review findings yourself. Always spawn the appropriate subagent skill.
- **Checkpoints are mandatory.** Even when the user said "run everything" at the start — every phase boundary requires a conscious confirmation.
- **Preserve artifacts on stop.** All work produced before a stop stays in `.workflow_artifacts/<task-name>/`. The user can resume with individual skills or `/run --resume`.
- **Gates are blocking.** Never skip a gate. If a gate fails, do not proceed.
- **Fresh session for review.** `/review` must be a fresh subagent session for unbiased assessment.
- **Keep checkpoint summaries concise.** Key facts only — offer "show <artifact>" for details.
