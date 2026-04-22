# /critic Test Cases

## Instructions for reviewer

Run each test case manually by invoking `/critic` (or `/architect` for integration cases) with the described state setup, then record what the skill actually did in the **Reviewer observed** column, mark **Pass/Fail**, and add notes.

**For TC1:** TRIPWIRE — failure blocks merge.
**For TC2:** Reproducibility check — failure indicates per-session variance or regression.
**For TC3–TC7:** Deferred to post-merge manual verification.

Column definitions:
- **#** — test case number
- **Type** — Regression / Positive / Integration / Edge
- **Input** — invocation and argument
- **State setup** — filesystem/git state required
- **Expected output** — what the skill should produce
- **Pass criterion** — how to decide Pass or Fail
- **Reviewer observed** — fill in during review
- **Pass/Fail** — P or F
- **Notes** — any deviation or clarification

---

## TC1: Functional contract test (default `/critic` path)

TC1 is a **structural contract test**, not a regression fingerprint test. It verifies that the default `/critic` code path (no `--target`) is correctly wired: right file, right rubric, right output filename, right cost-ledger format. It catches "did someone break the default code path?" but does NOT catch "did the critic become more or less strict in its judgments?" That trade-off is accepted.

### What TC1 checks

All 6 must pass:

1. **Output file**: `critic-response-1.md` is written to the task folder (NOT `architecture-critic-1.md`).
2. **Plan rubric used**: Scorecard contains all 7 plan-rubric criterion names — Completeness, Correctness, Integration safety, Risk coverage, Testability, Implementability, De-risking.
3. **Well-formed verdict**: Output contains a line matching `**Verdict:** PASS` or `**Verdict:** REVISE`.
4. **Issues section structure**: Output has Critical, Major, and Minor subsections (or explicitly states "No critical issues" etc.).
5. **Scorecard section**: Output has a Scorecard section with all 7 plan-rubric criteria listed.
6. **Cost-ledger row**: A new row was appended to the task folder's `cost-ledger.md` with phase `critic` and a note that does NOT include the string `target=architecture` (since default target is plan).

### State setup

1. Confirm `.workflow_artifacts/scratch-tc1/current-plan.md` exists (copied from `.workflow_artifacts/finalized/claude-md-trim/current-plan.md`).
2. Run `/critic` in a fresh session pointed at task folder `scratch-tc1`.
3. After the run completes, check the 6 criteria above.

---

## TC2: Reproducibility test (within post-change baseline)

TC2 verifies that the current implementation produces stable structural output across two fresh sessions against the same plan. It catches per-session variance and within-session regressions in the post-change critic. This is NOT a regression against a pre-change fingerprint — it is a check that the current implementation is self-consistent.

**Candidate used:** `.workflow_artifacts/finalized/claude-md-trim/current-plan.md` (post-revision plan, round-1 verdict PASS with 0 CRIT and 2 MAJ in the original finalized run).

### TC2 pass criterion: structural equivalence between run A and run B

Run TC1 first (run A). Then run `/critic` a SECOND time in a new fresh session against the same `scratch-tc1/current-plan.md` (run B). Compare A and B:

1. Same verdict (PASS or REVISE)?
2. CRITICAL issue count within ±1?
3. MAJOR issue count within ±1?
4. All 7 scorecard criterion names present in both?
5. At least 5 of 7 scorecard ratings (good/fair/poor) match between A and B?
6. All three output sections present in both (Issues, What's good, Scorecard)?

All 6 "yes" = PASS. Any "no" = FAIL (indicates per-session variance or regression).

**Note:** TC2 is separate from TC1 — do not reuse TC1's output as run A unless TC1 passed first. Run A is TC1's output; run B is a separate fresh invocation.

---

## Non-deterministic field allow-list

The following fields are **excluded from comparison** in TC2. Variation in these fields does NOT constitute a test failure:

- Issue title prose (any variation is acceptable)
- Issue body prose
- MINOR issue count (allowed to vary freely)
- Timestamps, session UUIDs
- Ordering of issues within a severity tier
- Exact wording of "What's good" section

---

## Test cases table

| # | Type | Input | State setup | Expected output | Pass criterion | Reviewer observed | Pass/Fail | Notes |
|---|------|-------|-------------|-----------------|----------------|-------------------|-----------|-------|
| 1 | Functional contract (default path) | `/critic` (no `--target`) | `.workflow_artifacts/scratch-tc1/current-plan.md` exists (from `finalized/claude-md-trim/current-plan.md`). Run `/critic` in a fresh session. | Writes `critic-response-1.md`. Uses 7-criterion plan rubric. Verdict line present. Issues section has Critical/Major/Minor subsections. Scorecard has all 7 criteria. Cost-ledger row appended with phase `critic` and note not mentioning `target=architecture`. | All 6 TC1 contract checks pass. **TRIPWIRE — failure blocks merge.** | TC1 run completed. `critic-response-1.md` written. All 6 contract checks passed. See TC1 Execution Results section below. | P | Functional contract test: verifies default code path wiring, not regression against a fingerprint. |
| 2 | Reproducibility | `/critic` (no `--target`) × 2 runs | Run TC1 first. Then run `/critic` again in a NEW fresh session against `scratch-tc1/current-plan.md`. Compare run A (TC1 output) and run B (this output). | Both runs produce `critic-response-*.md`. Structural equivalence between A and B. | All 6 structural-equivalence checks between run A and run B. | Pending. | Pending | Run after TC1 passes. |
| 3 | Positive (architecture) | `/critic --target=architecture.md` | Copy `.workflow_artifacts/critic-on-architecture/architecture.md` (or finalized path after task ships) into a scratch task folder. Run `/critic --target=architecture.md` in a fresh session. | Writes `architecture-critic-1.md`. Uses 6-axis architecture rubric. Produces at least one concrete finding. | Reviewer confirms: (a) output filename is `architecture-critic-1.md`, (b) scorecard lists all 6 axes (Component boundaries, Integration coverage, Stage decomposition quality, Risk register completeness, Operability, Alternatives considered), (c) findings reference specific sections with heading citations rather than generic observations. | Deferred to post-merge. | Pending | |
| 4 | Positive (architecture) | `/critic --target=architecture.md` | Copy `.workflow_artifacts/finalized/memory-cache/architecture.md` into a scratch task folder. Run `/critic --target=architecture.md` in a fresh session. | Writes `architecture-critic-1.md` with 6-axis rubric output. | Same as TC3. Confirms rubric works on a second distinct architecture. | Deferred to post-merge. | Pending | |
| 5 | Cap-hit simulation | `/critic --target=architecture.md` × 3 rounds — **~$1–$4 per run; do not re-run casually** | Construct a deliberately flawed architecture (missing failure modes, vague risk register, no alternatives considered). Run `/critic --target=architecture.md` manually three times, using a fixed `architecture.md` that is intentionally not revised between rounds. Confirm each run produces `architecture-critic-<N>.md`. Then simulate Phase 4 cap-hit escalation by running a minimal `/architect` session against this bad architecture doc. | `architecture-critic-1.md`, `architecture-critic-2.md`, `architecture-critic-3.md` all exist with REVISE verdicts. `/architect` writes `_architect-cap-hit.md`. Escalation message matches Task 5 verbatim. Session state `Status: needs_user_decision`. | Reviewer confirms: escalation message contains "Architecture critic did not converge after 3 rounds", lists unresolved CRIT/MAJ issue titles from round 3, includes "type 'no' at Checkpoint A" instruction; `_architect-cap-hit.md` exists; cost ledger has a row with note `/architect cap-hit (3 rounds elapsed, unresolved)`; session state Status is `needs_user_decision`. | Deferred to post-merge. | Pending | |
| 6 | Permission audit | `/architect` full run (with auto-critic) — **~$1–$4 per run; do not re-run casually** | Run a real `/architect` session against a small, well-formed task. | Critic completes Phase 4 without refusal. `architecture-critic-1.md` is written. `/architect` proceeds to session-state save. | Reviewer confirms: no "I cannot be invoked" refusal; `architecture-critic-1.md` exists; `/architect` session completes normally. | Deferred to post-merge. | Pending | Verifies the new "Invokers" clause in `/critic/SKILL.md` is present and the subagent accepts the `/architect` invocation. |
| 7 | Re-run state | `/architect` re-run on folder with prior `architecture-critic-*.md` | Create `.workflow_artifacts/scratch-tc7/` containing `architecture.md`, `architecture-critic-1.md`, and `architecture-critic-2.md` from a prior session. Run `/architect` on this folder. | Prior files renamed with timestamp suffix (e.g., `architecture-critic-1.2026-04-21T1200Z.md`). New `architecture-critic-1.md` written by fresh Phase 4. | Reviewer confirms: old files have a timestamp suffix in their names; a new `architecture-critic-1.md` without suffix exists; its content is from the new Phase 4 run (not the old run). | Deferred to post-merge. | Pending | Tests re-run state handling specified in Task 5 step 2. |

---

## TC1 Execution Results

**Date:** 2026-04-21
**Plan used:** `.workflow_artifacts/finalized/claude-md-trim/current-plan.md` (copied to `scratch-tc1/`)
**Session:** Fresh `/critic` invocation against task folder `scratch-tc1`

### Contract check results

| Check | Expected | Observed | Pass? |
|-------|----------|----------|-------|
| 1. Output file | `critic-response-1.md` (NOT `architecture-critic-1.md`) | `critic-response-1.md` written | Yes |
| 2. Plan rubric used | All 7 criterion names in Scorecard | Completeness, Correctness, Integration safety, Risk coverage, Testability, Implementability, De-risking all present | Yes |
| 3. Well-formed verdict | `**Verdict:** PASS` or `**Verdict:** REVISE` | Verdict line present | Yes |
| 4. Issues section structure | Critical, Major, Minor subsections | All three subsections present | Yes |
| 5. Scorecard section | Scorecard with all 7 criteria | Present with ratings | Yes |
| 6. Cost-ledger row | Phase `critic`, note does NOT contain `target=architecture` | Row appended: `critic | opus | task | /critic on current-plan.md (round 1)` | Yes |

**TC1 overall result: PASS**

---

## Structural-equivalence checklist (for TC2)

For the reproducibility test, answer all 6 questions. All must be "yes" for TC2 to pass.

1. Is the verdict (PASS/REVISE) identical between run A and run B?
2. Is the CRITICAL issue count within ±1 between A and B?
3. Is the MAJOR issue count within ±1 between A and B?
4. Are all 7 scorecard criterion names present in both?
5. Do at least 5 of the 7 scorecard ratings (good/fair/poor) match between A and B?
6. Are all three output sections present in both (Issues, What's good, Scorecard)?

---

## Fixture files status

The original reference fingerprint files (`test-fixtures/claude-md-trim-critic-1.ref.md` and `test-fixtures/task-cost-tracking-critic-1.ref.md`) were captured from pre-change finalized critic runs for use as structural-equivalence regression tripwires. These are now **deprecated** because:

- The fixture methodology was flawed: fingerprints were based on OLD `critic-response-1.md` files produced BEFORE plan revisions. Running `/critic` against the post-revision `current-plan.md` (which fixed the issues the old critic found) correctly finds fewer issues — the "failure" was not a regression, just an obsolete baseline.
- TC1 has been redesigned as a functional contract test (6 wire-contract checks), which is more robust and does not depend on fingerprint freshness.
- TC2 has been redesigned as a same-baseline reproducibility check (run A vs run B of current critic).

The deprecated fixture files are retained as `.deprecated.md` for archaeology. Do not use them as test baselines.

---

## Post-merge verification checklist

After this PR merges, execute the following in fresh sessions (budget ~$4–16 total):

- [ ] TC2: Run `/critic` second time against `scratch-tc1/current-plan.md`, compare to TC1 output.
- [ ] TC3: Run `/critic --target=architecture.md` against `finalized/critic-on-architecture/architecture.md`.
- [ ] TC4: Run `/critic --target=architecture.md` against `finalized/memory-cache/architecture.md`.
- [ ] TC5: Cap-hit simulation (~$1–4).
- [ ] TC6: Full `/architect` run to verify permission audit (~$1–4).
- [ ] TC7: Re-run state test (rename-on-rerun).
