# Quoin Stage 1 — Subagent dispatch verification

## Procedure

Pre-merge HITL pilot (T-00) and post-install re-confirmation (T-09 Phase A).

1. Author the §0 fixture (T-01 acceptance must pass).
2. Insert §0 into ONLY `quoin/skills/triage/SKILL.md` per T-02
   per-file procedure (row "pilot" in the anchor table).
3. Run `bash install.sh` to deploy the modified `triage/SKILL.md`.
4. Open Claude Code on Opus 1M. Verify the model with `/model` or by
   reading the harness banner ("powered by the model named X").
5. Type: `/triage what should I run next?`
6. Observe ONE of three signals:
   (i)  "Spawning subagent" banner (or equivalent model-handoff signal)
        AND the cost-ledger row for the triage subagent records
        `claude-haiku` in the model column → DISPATCH VERIFIED.
   (ii) Fail-graceful warning
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
        followed by triage's normal output on Opus → harness does not
        support `model` parameter on subagent spawn.
   (iii) NEITHER signal AND response generated on Opus (cost-ledger row
         records opus) → SILENT NO-OP. The §0 prose is mis-specified.
7. Record the observation below in ## Observed.
8. Set ## Result to one of: `verified`, `failed`, or `untested`.
9. T-09 Phase A re-confirmation (post-install, full-set deploy): repeat
   steps 4-7 with `/gate` (no arguments) instead of `/triage` and append
   a "Phase A re-confirmation" subsection under ## Observed.

## Observed

### T-00 pilot (2026-04-26)

- Date / time of run: 2026-04-26
- Parent tier: Opus 4.7 (claude-opus-4-7, 1M context)
- Invocation: `/triage what should I run next?`
- Signal seen: **(i)** — Agent subagent dispatch banner appeared and the triage response was generated at the declared Haiku tier
- Cost-ledger / model attribution: child subagent ran at `haiku` (not the opus parent)
- Tool-error message: none
- Notes: the §0 block's `Spawn an Agent subagent` instruction with `model: "haiku"` was honored by the harness; the fail-graceful warning did NOT fire. Pilot confirms the Agent tool accepts the `model:` parameter.

### T-09 Phase A re-confirmation (2026-04-26)

- Date / time of run: 2026-04-26
- Parent tier: Opus 4.7 (1M context)
- Invocation: `/gate` (no args) on the full deployed set (all 12 cheap-tier skills carry §0)
- Signal seen: **(i)** — Agent subagent dispatch banner appeared, `model: "sonnet"`, `description: "gate dispatched at sonnet tier"`; child returned a rendered gate summary that became the parent's final response
- Cost-ledger / model attribution: child ran at the declared `sonnet` tier
- Tool-error message: none
- Notes: confirms the §0 dispatch mechanism works for sonnet-tier as well as haiku-tier (T-00 covered haiku via /triage). Full T-09 four-phase smoke captured at `.workflow_artifacts/quoin-foundation/stage-1/manual-smoke-2026-04-26.md`. Verdict: **PASS** — all four phases behaved as designed.

## Result

<!--
One of: verified | failed | untested
T-02 batch insertion is gated on this being `verified`.
If `failed`, capture diagnostic detail above and STOP — stage-1 is
rewritten before any T-02 work proceeds.
-->

verified
