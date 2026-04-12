# Critic Response — Round 3

## Verdict: REVISE

## Summary

The Round 3 revision is surgical and correct — all five Round 2 MINORs are addressed precisely, and MAJ-1's Stage-2-native escape hatch (`max_rounds: N`) is cleanly resolved without Stage 3 dependency. The architecture is now internally consistent, mathematically honest, and correctly staged. One MAJOR remains: the concrete fix to `thorough_plan/SKILL.md:63` ("invoke in original session context") is described in E0 but never assigned to any stage in Section 5, creating a real risk that a Stage 3 implementer misses it. Four MINORs round out the findings, all surgical.

---

## Issues

### Critical (blocks implementation)

None.

---

### Major (significant gap, should address)

- **[MAJ-1] The `thorough_plan/SKILL.md:63` inline-revise fix is described in E0 but assigned to no stage**
  - **What:** Section 3, E0 identifies a concrete source-file contradiction — `dev-workflow/skills/thorough_plan/SKILL.md:63` says "Invoke in the original session context (it needs to understand the plan's intent)" while `dev-workflow/skills/revise/SKILL.md:13` says "This skill may run in a fresh session." E0 provides the resolution: "update thorough_plan/SKILL.md to drop the 'invoke in original session context' language; spawn `/revise` as a subagent." But scanning Section 5's stage descriptions, no stage says to make this edit. Stage 3 says "Update `/thorough_plan` to invoke `/plan` (round 1 only) and `/revise` (rounds 2 and 3) on Sonnet by default" — which implies a mechanical change — but does not explicitly list "remove line 63's inline language" as a deliverable. A planner synthesizing Stage 3 tasks from Section 5 (without re-reading all of Section 3 / E0) would miss this fix.
  - **Why it matters:** Until this line is removed, every `/thorough_plan` run today is ambiguous: the orchestrator has a live instruction to run `/revise` inline that contradicts the architecture's recommendation. After Stage 3 ships the two-skill-file infrastructure, if the old inline-language is still there, the orchestrator may ignore the new subagent spawn and run revise in-session, silently defeating both the quality benefit (fresh planner context) and the tiering benefit (Sonnet for rounds 2-3). Worse, a new developer reading `thorough_plan/SKILL.md` would get a different instruction than what Stage 3 intended.
  - **Where:** `dev-workflow/skills/thorough_plan/SKILL.md:62-65` (the `/revise` invocation block); Section 5 / Stage 3 description (missing the edit).
  - **Suggestion:** Add to Stage 3's Section 5 description — as an explicit bullet before the model-tiering bullets — that the Stage 3 changeset must also update `thorough_plan/SKILL.md` to remove the "invoke in original session context" instruction and replace it with the subagent spawn pattern described in E0. Alternatively, if this is truly independent of model tiering (it is — it's just a session-isolation fix), assign it to Stage 2 instead, since Stage 2 already touches `thorough_plan/SKILL.md` for the `max_rounds` change. Bundling it into Stage 2 means the fix ships earlier and doesn't wait for the riskier Stage 3.

---

### Minor (improvement, use judgment)

- **[MIN-1] `strict:` "unconditionally" vs. `max_rounds: N` override — slight tension**
  - Stage 3 says "`strict:` mode raises the cap back to 5 unconditionally." Stage 2 says "if Stage 3 also ships later, the `strict:` protocol coexists (a `strict:`-prefixed run also defaults max_rounds to 5, which the user can still override upward via `max_rounds: N`)." "Unconditionally" implies `max_rounds: N` cannot override `strict:`'s cap — but Stage 2 says it can. The two sentences are contradictory on whether `max_rounds: N` can raise the cap above what `strict:` sets.
  - **Suggestion:** Pick one semantics and state it in one place. The cleaner design is: `strict:` forces all-Opus for model selection; `max_rounds: N` (if present) controls the round cap regardless of strict mode. Change "unconditionally" in Stage 3 to "by default to 5, overridable by `max_rounds: N` as usual." This makes `max_rounds: N` the single cap-control mechanism and `strict:` purely a model-selection override.

- **[MIN-2] Caveats section's "most needing Opus re-validation" note is stale after three critic rounds**
  - The Caveats section still says: "the single item that most needs an Opus re-validation is CRIT-1 from the Round 1 critic: the subagent-economics and per-spawn-overhead reasoning in E0." That was true after Round 1. After three rounds of Opus critique that reviewed E0, validated the reframing (quality/enabling, not direct cost win), and confirmed that Stage 0 gates the spawn-overhead question, the note is now stale. A reader of the Round 3 document would think the E0 reasoning is still unreviewed.
  - **Suggestion:** Update the Caveats section to note that E0's subagent economics have now been reviewed across three Opus critic rounds; the "Opus re-validation" item is resolved. The remaining caveat is that E0's direction has been validated conceptually but not empirically — Stage 0's per-spawn measurement is still required before Stage 3 commits.

- **[MIN-3] Stage 0 measurement methodology is unspecified**
  - Stage 0 says "capture: tokens in/out per skill invocation, model used, cache-hit ratio per call." It does not say *how* to capture this. Claude Code's standard UI does not expose per-call token counts or cache-hit ratios to the user during a run. The methodology (e.g., use the Anthropic Console's usage dashboard after the run, pipe through a proxy that logs API responses, inspect Claude Code's debug output, etc.) is not mentioned. A developer tasked with running Stage 0 would not know where to look.
  - **Suggestion:** Add one sentence to Stage 0: "Methodology: token counts and cache-hit ratios are available in the Anthropic Console's usage view at console.anthropic.com → Usage after the run, or via API response metadata if requests are proxied. Identify the calls by timestamp and model to correlate them with skill invocations." If the harness exposes this differently, note that explicitly. Stage 0's value is entirely in the numbers it produces — if the measurement approach is unclear, the stage may produce no output.

- **[MIN-4] `plan-fast` "sources" language describes a mechanism that doesn't exist**
  - Stage 3 says: "`dev-workflow/skills/plan-fast/SKILL.md` — new file, `model: sonnet`. Body is a minimal 'call `/plan`'s instructions on Sonnet' header that *sources* the Opus version's content, or a copy with the model pinned differently." SKILL.md files are markdown documents read by Claude — there is no `source` or `include` directive. In practice, `plan-fast` would be a content-copy of `plan/SKILL.md` with the model frontmatter changed to `model: sonnet`. The R9 mitigation correctly says "CI/lint rule that... diffs them on commit" — a diff-based check is only meaningful if they are copies, not if one sources the other.
  - **Suggestion:** Replace "sources the Opus version's content" with "is a content copy of `plan/SKILL.md` with `model: sonnet` in the frontmatter." Update R9 accordingly: "CI/lint rule that diffs `/plan-fast/SKILL.md` against `/plan/SKILL.md` on commit and fails if they diverge beyond the model line."

- **[MIN-5] Stage 4's "Small → no critic loop" implies a CLAUDE.md workflow-sequence update that is not mentioned**
  - Stage 4 says: "Small → `/plan` (Sonnet) + `/implement` + `/review` (Sonnet, smoke gate). No critic loop." The workflow sequence in `dev-workflow/CLAUDE.md` says: "Not every task needs every stage. Small, well-understood changes can skip `/architect` and go straight to `/thorough_plan`." This implies Small tasks always use `/thorough_plan` (the critic loop). Stage 4's Small profile skips the critic entirely, which is a meaningful change to the stated workflow. If Stage 4 ships without updating CLAUDE.md, the two documents conflict, and a developer following CLAUDE.md for a Small task would still run the full loop.
  - **Suggestion:** Add to Stage 4's description: "Stage 4 requires updating `dev-workflow/CLAUDE.md`'s workflow sequence section to reflect the Small profile's skip of `/thorough_plan`." One sentence in Stage 4's scope list is enough — the actual wording change can be left for the Stage 4 `/thorough_plan` cycle.

---

## What's good

- **All Round 2 issues genuinely resolved.** MAJ-1 (Stage-2-native override) is cleanly fixed with the inline `max_rounds: N` parsing rule — it's simple, self-contained, and truly decoupled from Stage 3. All five MINORs are addressed precisely: the TTL caveat is now correctly hedged, the Proposal D cross-round prefix math is corrected to 6-8k, the "plan/revise" round-3 terminology is fixed in both locations, Stage 1 complexity is now M-L with the split suggestion, and the flat-rate caching framing is honest (latency, not rate-limit headroom).
- **The `max_rounds: N` override mechanism is the right shape.** A few lines in one SKILL.md, no new files, no Stage 3 dependency. It fulfills the "override remains available" promise cleanly. The coexistence rule with `strict:` (modulo the MIN-1 wording issue) is correct.
- **The cap-at-4 change (from the user's direction) is correctly integrated everywhere.** All seven places where "5" or "3" appeared have been updated to "4" consistently across Section 3, Section 4, Section 5, Section 6, Section 7, and Section 9.
- **Round 3 terminology fix is correct and in both places.** Proposal B and Stage 3 now both correctly say round-3+ uses `/revise`, not `/plan`. The two-skill-file note clarifying that `/plan-fast` is round-1-only is a useful precision addition.
- **Stage 1 M-L with the 1a/1b split option is the right framing.** Correctly names C7 as the heavy item while leaving the split decision to the Stage 1 `/thorough_plan` cycle.
- **The architecture's overall shape and staging order are sound.** Three rounds of Opus critique have converged on no CRITICAL issues, and the remaining issues are refinements. The "measure before changing, free wins before risky tiering" discipline is correct and well-argued.

---

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Correctness | good | Source files verified: `thorough_plan/SKILL.md` and `revise/SKILL.md` match the architecture's claims about the current contradiction. `critic/SKILL.md` is `model: opus` — correctly kept on Opus by the architecture. `plan/SKILL.md` and `architect/SKILL.md` match their described roles. MIN-4 (`plan-fast` "sources" language) is a terminology inaccuracy. |
| Completeness | good | All Round 2 issues addressed. MAJ-1 (inline-revise fix unassigned to a stage) is the remaining gap. MIN-5 (CLAUDE.md update not mentioned for Stage 4) is a small completeness gap. |
| Logic | good | `max_rounds: N` + `strict:` coexistence logic is mostly clear; MIN-1 wording tension is minor. The escalation ladder, model-tiering direction, and staging order are internally consistent. |
| Risk coverage | good | R8 and R9 are well-specified. The MAJ-1 risk (implementer misses the SKILL.md:63 fix) is not in the register. Stage 0 methodology gap (MIN-3) is a risk to Stage 0's ability to produce useful output. |
| Testability | good | This is an architecture document — test strategy is correctly deferred to each stage's `/thorough_plan`. Stage 5's "one-week side-by-side validation" for Haiku is the right form. |
| Implementability | good | Substantially improved from Round 1's "poor." Stage 3's two-skill-file mechanism is now concrete. The one remaining implementability gap is MAJ-1: Stage 3's task list is missing the `thorough_plan/SKILL.md:63` line removal. |
| De-risking | good | Stage 0 measurement gates Stage 3. `strict:` and `max_rounds: N` are working escape hatches. The Stage 3 prototype-before-commit requirement is the right shape. Stage 0's measurement methodology gap (MIN-3) is the one de-risking hole. |
