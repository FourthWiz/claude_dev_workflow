# Critic Response — Round 2

## Verdict: REVISE

## Summary

The Round 2 revision resolves all four Round 1 CRITICALs cleanly — the caching math is now honest, E0 is correctly framed as a quality/enabling lever, Stage 3 keeps the critic on Opus, and the billing-plan gate is front-and-center where it belongs. One new MAJOR was introduced by the revision itself: Stage 2 ships a lower `max_rounds` cap with a promised "override available" that has no mechanism until Stage 3's `strict:` protocol is also shipped — leaving a gap window where users whose tasks need >3 rounds have no escape hatch. Four MINORs round out the findings, all surgical. This is a substantially sound document; the REVISE verdict is a narrow one.

---

## Issues

### Critical (blocks implementation)

None.

---

### Major (significant gap, should address)

- **[MAJ-1] Stage 2 ships a lower cap with a promised escape hatch that doesn't exist until Stage 3**
  - **What:** Stage 2 (Section 5, "Loop discipline") lowers `max_rounds` from 5 → 3 and says "Override remains available." But the only override mechanism in the document is the `strict:` prefix protocol defined in Stage 3. If Stage 2 ships without Stage 3 (which the Stage Summary Table explicitly allows — Stage 2 depends only on Stage 0), users whose hard tasks need more than 3 rounds have no escape. The orchestrator will hit the cap, inform the user of remaining issues, and stop — which is technically correct behavior, but there is no way for the user to re-invoke with a higher cap without manually editing `thorough_plan/SKILL.md`. "Override remains available" is a promise that cannot be kept without Stage 3.
  - **Why it matters:** Someone implementing Stages 0 + 2 (a plausible fast-track path for a team that doesn't want Stage 3's model-tiering risk yet) will ship a max_rounds=3 system with no documented user-facing override. When a genuinely hard plan fails to converge in 3 rounds, the team must choose between manual SKILL.md edits (fragile, drift risk) or discovering Stage 3 is now required. The "Stage 2 is independently deployable" claim in Section 9 is misleading.
  - **Suggestion:** One of:
    - (a) Define a *simpler* interim override mechanism as part of Stage 2 itself: e.g., the user can append `"max_rounds: N"` anywhere in their task description, and `/thorough_plan` parses it. That's one line of logic to add to the SKILL.md, no two-skill-file infrastructure required, and it fulfills the "override available" promise before Stage 3 exists.
    - (b) Merge Stage 2 into Stage 3 (ship them together, document the dependency). Remove the claim that Stage 2 is independently deployable.
    - (c) Change the Stage 2 language from "Override remains available" to "Override will be available when Stage 3 ships; until then, reach-the-cap tasks get the existing orchestrator escalation." Honest, not misleading.
    Option (a) is cleanest — simple, safe, and lets Stage 2 ship independently as intended.

---

### Minor (improvement, use judgment)

- **[MIN-1] Cache TTL claim is wrong for real-workload runs**
  - The document says (Section 3.C, verified facts): "A multi-round `/thorough_plan` run is well under 5 minutes, so TTL is not the constraint." This is not true for real heavy tasks. A `/plan` invocation that reads a large codebase, runs web searches, and produces a long document can take 10–25 minutes. A full two-round loop is 30–60+ minutes for complex plans. The 5-minute default TTL will expire between rounds in these cases, silently turning every cache write into wasted cost. The 1-hour TTL requires explicit `cache_control` with the longer TTL, and it is not known whether the harness sets it. This doesn't change the "caching ≈ 2% savings, do it as hygiene" conclusion — but it does mean the C1 audit (Stage 0 task) must specifically check: what TTL does the harness use, and do cross-round cache hits actually land? Without that check, Stage 1's C1 work may have no measurable effect.
  - **Suggestion:** Change "TTL is not the constraint" to "TTL *may* be a constraint for long-running loops — Stage 0's C1 audit must check what TTL the harness sets and whether cross-round cache hits actually land."

- **[MIN-2] Proposal D's "12k stable prefix cached between critic rounds" is overstated**
  - Section 4's Proposal D calculation credits a 12k cached prefix for `/critic` round 2 (lessons-learned + architecture + current-plan). But `current-plan.md` *changes* between round 1 and round 2 (it is revised). The byte-identical prefix between `/critic` round 1 and `/critic` round 2 is only system-prompt + lessons-learned (≈ 6–8k, mostly the SKILL.md and CLAUDE.md), not 12k. This makes Proposal D's savings even smaller than the already-small ~2% estimate — probably ~1% or less. The conclusion ("Proposal D is hygiene, not a free lunch") is correct and unchanged, so this is minor, but the math should be corrected so the C1 audit doesn't chase savings that aren't there.
  - **Suggestion:** Correct the cross-round caching claim: the stable prefix across `/critic` round boundaries is system-prompt + lessons-learned (≈ 6–8k), NOT the plan (which changes). The 12k prefix is only stable *within* a single round (e.g., if `/revise` re-reads the plan multiple times), not across critic round boundaries.

- **[MIN-3] Proposal B round 3 terminology: "plan/revise" is wrong — it's "revise" only**
  - Section 4's Proposal B describes round 3 as "round 3 `/plan`/`/revise` Opus, round 3 `/critic` Opus." In a normal 3-round escalation, round 3 does NOT re-run `/plan` from scratch — it runs `/revise` (updating the existing plan based on round-2 critic feedback) + `/critic`. A fresh `/plan` call would discard the accumulated round-1 and round-2 work. The terminology conflates "plan" (the initial plan-writing action) with "revise" (the update action for subsequent rounds). This is also inconsistent with Section 5's Stage 3 ("Round 3 (final allowed): `/plan`/`/revise` escalate to Opus") — which has the same error.
  - **Suggestion:** In both Proposal B and Stage 3, round 3's planner action is `/revise` on Opus (not `/plan`). `/plan` only runs in round 1. Correct both occurrences.

- **[MIN-4] Stage 1 complexity "M" underestimates C7**
  - Stage 1 is rated Complexity "M" in Section 9's Stage Summary Table. But Stage 1 includes C7 — the `/architect` scan/synthesize split — which requires adding new subagent-spawning logic to `architect/SKILL.md`, defining a structured-findings format that scan subagents emit, writing a synthesizer pass that consumes those findings, and validating that the synthesis step doesn't miss things a unified Opus read would have caught. That's real new infrastructure. The rest of Stage 1 (C1 audit, C3, C4, C5, C6) is M by themselves. C7 alone is an M or L. Combined, Stage 1 is M-L or should be split into Stage 1a (caching hygiene: C1, C3, C4, C5, C6) and Stage 1b (architect split: C7). This matters for planning — "M" implies one `/thorough_plan` cycle of moderate effort; an M-L or L Stage 1 needs more careful scoping.
  - **Suggestion:** Either rate Stage 1 as "M-L" in the table, or split it into Stage 1a (hygiene, M) and Stage 1b (C7 architect split, M-L). The Stage 0 `/architect` measurement must complete before Stage 1b scope can be finalized.

- **[MIN-5] Section 1.0 flat-rate framing overstates Stage 1's rate-limit benefit**
  - Section 1.0 lists "Stage 1 (caching) — fewer tokens means fewer rate-limit hits on heavy days" as a reason Stage 1 is still useful on flat-rate plans. But Stage 1's caching saves ~2% of tokens. A 2% token reduction produces a ~2% rate-limit reduction — negligible in practice, not a meaningful lever against Pro/Max rate limits. The honest framing for flat-rate plans is: Stage 1's value is **latency** (warm-prefix calls are faster) and **correctness/hygiene** (C3, C4, C5), not meaningful rate-limit headroom.
  - **Suggestion:** In Section 1.0, replace "fewer tokens means fewer rate-limit hits on heavy days" with "slightly faster wall-clock for warm-prefix calls (latency, not rate-limit headroom — the savings are too small to meaningfully move the rate-limit needle)."

---

## What's good

- **All four Round 1 CRITICALs are genuinely resolved.** E0's reframing (quality/enabling, not direct cost win) is correct and well-argued. The cost table rewrite with real dollars is the right calibration — it corrects inflated expectations without abandoning the analysis. Stage 3 keeping the critic on Opus restores internal consistency. The billing-plan gate in Section 1.0 is the right first thing to read.
- **The honest caveats section is a real strength.** The document naming "CRIT-1 from Round 1 is the thing most needing Opus re-validation" is precise and useful. "The table is a model, not a measurement" is the right epistemic posture.
- **C7 (/architect scan/synthesize) is a genuinely valuable new lever.** It correctly identifies that `/architect` is the heaviest single skill and doesn't benefit from the loop optimizations. The mechanism is plausible and the dependency on Stage 0 measurement is appropriate.
- **R8 and R9 are concrete and actionable.** The risk that per-spawn overhead eats Stage 3's savings (R8) is now in the register with a real fallback path. The two-skill-file drift risk (R9) is real and the CI/lint mitigation is the right shape.
- **The Stage 3 two-skill-file mechanism is concrete enough for an implementer.** Naming the new files (`/plan-fast`, `/revise-fast`) and the selection logic (round number + strict flag) is exactly the level of specificity needed to avoid the Round 1 "implementability: poor" score.
- **Proposal A vs Proposal B equivalence correction is correct.** Retracting the Round 1 "Proposal B is strictly better" claim and explaining why they're equivalent for the typical case is good intellectual hygiene.

---

## Scorecard

| Criterion | Score | Notes |
|---|---|---|
| Correctness | good | All CRIT-level claim corrections hold up against source verification. Minor: cross-round cache prefix overstated (MIN-2); TTL claim wrong for heavy runs (MIN-1); round-3 "plan/revise" terminology error (MIN-3). |
| Completeness | good | C7 covers the `/architect` gap. Billing gate covers the flat-rate case. Stage 4 dependency on Stage 3 infrastructure is captured in the dependency table. |
| Logic | fair | Internal logic is mostly sound. The Stage 2 "override available" promise without a mechanism is the main gap (MAJ-1). Proposal B round-3 "plan/revise" is a terminology inconsistency (MIN-3). |
| Risk coverage | good | R8 and R9 are well-specified. MAJ-1 gap (no override in Stage 2 gap window) is not in the risk register. TTL risk for C1 is not in the risk register. |
| Testability | good | This is an architecture doc, not an implementation plan — test strategy is appropriately deferred to `/thorough_plan` on each stage. Stage 8's prototype-before-commit guidance for Stage 3 is the right form of de-risking here. |
| Implementability | fair | Stage 3 mechanism is now concrete. Stage 2 "override available" is misleading (MAJ-1). Stage 1 complexity underestimated (MIN-4). Round 3 "plan" vs "revise" terminology would confuse an implementer (MIN-3). |
| De-risking | good | Stage 0 measurement requirements are now comprehensive and well-specified. The Stage 3 prototype-before-commit requirement is correct. All later stages depend on earlier ones appropriately. |
