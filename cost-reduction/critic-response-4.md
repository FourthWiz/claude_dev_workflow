# Critic Response — Round 4

## Verdict: PASS

## Summary

The Round 4 revision resolves all Round 3 issues cleanly: the E0 session-isolation fix is now explicitly assigned to Stage 2, the `strict:` / `max_rounds: N` interaction semantics are consistent, the Caveats section is current, Stage 0 has a measurement methodology, the `plan-fast` "sources" language is corrected, and Stage 4 flags the CLAUDE.md update. No CRITICAL or MAJOR issues remain. Two MINORs are noted below for optional polish — neither blocks planning or implementation.

---

## Issues

### Critical (blocks implementation)

None.

---

### Major (significant gap, should address)

None.

---

### Minor (improvement, use judgment)

- **[MIN-1] Section 2.2 loop economics table still shows 5 rounds as worst-case**
  - Section 2.2 says "The convergence rule allows up to 5 rounds, which means the worst case is much worse." After Stage 2 (max_rounds 5→4), the worst case is 4 rounds. This is a pre-Stage-2 description of the current state, so it is technically correct *right now* — but a reader could be confused by seeing "5" in Section 2 and "4" everywhere in Sections 5+. The Stage 2 changelist doesn't flag this as a line that changes.
  - **Suggestion:** Either leave it as-is (it describes today's state, and the architecture is about changing that state — no confusion for a careful reader) or add a parenthetical: "allows up to 5 rounds (lowered to 4 by Stage 2)."

- **[MIN-2] Stage 0 methodology mentions `console.anthropic.com` — may not apply to Claude Code harness users**
  - The measurement methodology paragraph points to the Anthropic Console's usage view. Users running Claude Code through the CLI (which uses its own authentication and billing) may not have the same Console visibility as direct API users. Claude Code's `/cost` or session-end cost display gives aggregates; per-skill breakdowns may require enabling verbose logging (`--verbose` or similar). The methodology should hedge: "If using Claude Code CLI directly (not via API proxy), check whether session-level logging or the `--verbose` flag exposes per-call token detail; otherwise, the aggregate session cost display can be used as a coarser baseline."
  - **Suggestion:** Add one hedging sentence after the Console paragraph. This is not a blocker — the Stage 0 implementer will figure out the methodology during the run — but a hint saves time.

---

## What's good

- **MAJ-1 fix is the right call.** Moving the E0 session-isolation fix to Stage 2 is better than leaving it in Stage 3 for two reasons: (1) Stage 2 already touches `thorough_plan/SKILL.md`, so bundling is natural; (2) shipping the correctness fix early means every `/thorough_plan` run after Stage 2 benefits from fresh `/revise` context, independent of whether Stage 3 ever ships. The integration-analysis table correctly splits the E0 concern into two rows (Stage 2 session-isolation vs. Stage 3 full subagent isolation), making the risk profile legible.

- **`strict:` / `max_rounds: N` semantics are now clean.** `max_rounds: N` is the single cap-control mechanism; `strict:` controls model selection only and defaults the cap to 5. The two protocols compose naturally: `/thorough_plan strict: max_rounds: 7 this is gnarly` forces all-Opus with a 7-round cap. Both the Stage 3 convergence line and the `strict:` protocol description now say the same thing. The Round 3 critic's MIN-1 wording tension is fully resolved.

- **Caveats section is current and honest.** The stale "most needing Opus re-validation" language is replaced with an accurate summary: conceptual direction validated across three Opus critic rounds; empirical confirmation (Stage 0) still required. This is the right epistemic posture — validated-but-not-measured is different from both "validated" and "unreviewed."

- **Stage 0 measurement methodology is useful.** Naming `usage.input_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens` as the specific API response fields is exactly the level of detail a Stage 0 implementer needs. The Console vs. API-metadata distinction is correct.

- **`plan-fast` language is now accurate.** "Content copy with model frontmatter changed" is what the implementation will actually do. R9's diff-based mitigation is consistent with this description.

- **Stage 4 CLAUDE.md update bullet is precise.** It names the specific contradiction ("CLAUDE.md says small tasks go to `/thorough_plan`; Stage 4 skips it") and assigns the fix. Prevents a future implementer from shipping Stage 4 with a conflicting CLAUDE.md.

- **The architecture document as a whole, after four rounds, is internally consistent, grounded in verified facts, and correctly staged.** The progression from Round 1 (4 CRITICAL, 8 MAJOR) to Round 4 (0 CRITICAL, 0 MAJOR) demonstrates genuine convergence. The document's shape — billing gate → current state → design space → evaluation → staged rollout → integration analysis → risk register → de-risking — is the right structure for an architecture that feeds into per-stage `/thorough_plan` cycles.

---

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Correctness | good | All source-file references verified: `thorough_plan/SKILL.md:63` (inline instruction exists), `revise/SKILL.md:13` (fresh session exists), `critic/SKILL.md` model: opus (confirmed), `thorough_plan/SKILL.md:47,72` (max_rounds 5 exists and is correctly identified as the Stage 2 target). Anthropic caching facts verified. `plan-fast` copy language now matches reality. |
| Completeness | good | All stages have concrete deliverables. All Round 3 issues addressed. E0 fix is now staged. CLAUDE.md update is flagged for Stage 4. No remaining gaps that would block a Stage 0 `/thorough_plan`. |
| Logic | good | `strict:` and `max_rounds: N` semantics are consistent throughout. Stage dependencies are correct. The escalation ladder is coherent. The billing-plan gate correctly scopes the rest of the document. |
| Risk coverage | good | R1–R9 (excluding retired R3, R7) cover the real risks. The new E0 session-isolation row in the integration-analysis table is the right addition. Mitigations are concrete and actionable. |
| Testability | good | Architecture doc — test strategy correctly deferred to per-stage `/thorough_plan`. Stage 0's measurement methodology is now specified. |
| Implementability | good | Every stage has named files to edit, named levers to pull, and named escape hatches. Stage 3's two-skill-file mechanism is concrete. Stage 2's E0 fix is a one-line edit with clear before/after. |
| De-risking | good | Stage 0 gates everything risky. `strict:` and `max_rounds: N` are working escape hatches. Stage 3 prototype-before-commit is the right shape. The re-measure-after-each-stage discipline is stated. |
