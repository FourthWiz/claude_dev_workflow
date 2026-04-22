# /critic Test Cases

## Instructions for reviewer

Run each test case manually by invoking `/critic` (or `/architect` for integration cases) with the described state setup, then record what the skill actually did in the **Reviewer observed** column, mark **Pass/Fail**, and add notes.

**All 7 cases must Pass** for the PR to be considered ready for `/review`. TC1 and TC2 are tripwire regression tests — failure on either blocks merge.

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

## Non-deterministic field allow-list

The following fields are **excluded from structural comparison** in TC1 and TC2. Variation in these fields does NOT constitute a test failure:

- Issue title prose (any variation is acceptable)
- Issue body prose
- MINOR issue count (allowed to vary freely)
- Timestamps, session UUIDs
- Ordering of issues within a severity tier
- Exact wording of "What's good" section

These fields ARE compared and must match within tolerance:

- **Verdict** (PASS or REVISE) — must be identical
- **CRITICAL issue count** — must be within ±1 of reference
- **MAJOR issue count** — must be within ±1 of reference
- **Scorecard criterion names** — all 7 must be present
- **Scorecard ratings** (good/fair/poor) — at least 5 of 7 must match the reference
- **Output sections** — all three must be present: Issues, What's good, Scorecard

---

## Structural-equivalence checklist (for TC1 and TC2)

For each tripwire test, answer all 6 questions. All must be "yes" for the test to pass.

1. Is the verdict (PASS/REVISE) identical to the reference?
2. Is the CRITICAL issue count within ±1 of the reference?
3. Is the MAJOR issue count within ±1 of the reference?
4. Are all 7 scorecard criterion names present (Completeness, Correctness, Integration safety, Risk coverage, Testability, Implementability, De-risking)?
5. Do at least 5 of the 7 scorecard ratings (good/fair/poor) match the reference?
6. Are all three output sections present (Issues, What's good, Scorecard)?

---

## Reference fingerprint instructions

Reference fingerprints are stored in `test-fixtures/`. Each fingerprint records the **structural skeleton** of a pre-change critic run — verdict, CRIT/MAJ counts, scorecard ratings. All prose is discarded.

**To record a fingerprint:**
1. Copy the target plan to a scratch task folder (e.g., `.workflow_artifacts/scratch-test/`).
2. Run `/critic` in a fresh session against the scratch folder.
3. From `critic-response-1.md`, extract:
   - Verdict (PASS or REVISE)
   - Count of CRITICAL issues
   - Count of MAJOR issues
   - All 7 scorecard criterion names and ratings
4. Write only that structural skeleton to the reference file. Discard all prose.
5. Commit the reference file BEFORE any SKILL.md changes.

**To re-record fingerprints** (e.g., after a model version bump or rubric change):
1. Re-run `/critic` against the same historical plan.
2. Extract the structural skeleton as above.
3. Update the reference file.
4. Open a small PR to update the fixtures — do not mix fixture updates with SKILL.md changes.

---

| # | Type | Input | State setup | Expected output | Pass criterion | Reviewer observed | Pass/Fail | Notes |
|---|------|-------|-------------|-----------------|----------------|-------------------|-----------|-------|
| 1 | Regression (tripwire) | `/critic` (no `--target`) | Copy `.workflow_artifacts/finalized/claude-md-trim/current-plan.md` to a scratch task folder (e.g., `.workflow_artifacts/scratch-tc1/`). Run `/critic` in a fresh session pointed at that folder. | Writes `critic-response-1.md`. Uses 7-criterion plan rubric. | **Structural equivalence** vs `test-fixtures/claude-md-trim-critic-1.ref.md`. All 6 structural checks pass. **TRIPWIRE — structural failure blocks merge.** | | | Verifies default-target behavior is unchanged after `--target` addition. |
| 2 | Regression (tripwire) | `/critic` (no `--target`) | Copy `.workflow_artifacts/finalized/task-cost-tracking/current-plan.md` to a scratch task folder. Run `/critic` in a fresh session. | Writes `critic-response-1.md`. Uses 7-criterion plan rubric. | Same structural-equivalence check vs `test-fixtures/task-cost-tracking-critic-1.ref.md`. All 6 structural checks pass. **TRIPWIRE — structural failure blocks merge.** | | | Second regression case; different plan profile; confirms no rubric crossover. |
| 3 | Positive (architecture) | `/critic --target=architecture.md` | Copy `.workflow_artifacts/critic-on-architecture/architecture.md` into a scratch task folder. Run `/critic --target=architecture.md` in a fresh session. | Writes `architecture-critic-1.md`. Uses 6-axis architecture rubric. Produces at least one concrete finding. | Reviewer confirms: (a) output filename is `architecture-critic-1.md`, (b) scorecard lists all 6 axes (Component boundaries, Integration coverage, Stage decomposition quality, Risk register completeness, Operability, Alternatives considered), (c) findings reference specific sections with heading citations rather than generic observations. | | | |
| 4 | Positive (architecture) | `/critic --target=architecture.md` | Copy `.workflow_artifacts/finalized/memory-cache/architecture.md` into a scratch task folder. Run `/critic --target=architecture.md` in a fresh session. | Writes `architecture-critic-1.md` with 6-axis rubric output. | Same as TC3. Confirms rubric works on a second distinct architecture. | | | |
| 5 | Cap-hit simulation | `/critic --target=architecture.md` × 3 rounds — **~$1–$4 per run; do not re-run casually** | Construct a deliberately flawed architecture (missing failure modes, vague risk register, no alternatives considered). Run `/critic --target=architecture.md` manually three times, using a fixed `architecture.md` that is intentionally not revised between rounds. Confirm each run produces `architecture-critic-<N>.md`. Then simulate Phase 4 cap-hit escalation by running a minimal `/architect` session against this bad architecture doc. | `architecture-critic-1.md`, `architecture-critic-2.md`, `architecture-critic-3.md` all exist with REVISE verdicts. `/architect` writes `_architect-cap-hit.md`. Escalation message matches Task 5 verbatim. Session state `Status: needs_user_decision`. | Reviewer confirms: escalation message contains "Architecture critic did not converge after 3 rounds", lists unresolved CRIT/MAJ issue titles from round 3, includes "type 'no' at Checkpoint A" instruction; `_architect-cap-hit.md` exists; cost ledger has a row with note `/architect cap-hit (3 rounds elapsed, unresolved)`; session state Status is `needs_user_decision`. | | | |
| 6 | Permission audit | `/architect` full run (with auto-critic) — **~$1–$4 per run; do not re-run casually** | Run a real `/architect` session against a small, well-formed task. | Critic completes Phase 4 without refusal. `architecture-critic-1.md` is written. `/architect` proceeds to session-state save. | Reviewer confirms: no "I cannot be invoked" refusal; `architecture-critic-1.md` exists; `/architect` session completes normally. | | | Verifies the new "Invokers" clause in `/critic/SKILL.md` is present and the subagent accepts the `/architect` invocation. |
| 7 | Re-run state | `/architect` re-run on folder with prior `architecture-critic-*.md` | Create `.workflow_artifacts/scratch-tc7/` containing `architecture.md`, `architecture-critic-1.md`, and `architecture-critic-2.md` from a prior session. Run `/architect` on this folder. | Prior files renamed with timestamp suffix (e.g., `architecture-critic-1.2026-04-21T1200Z.md`). New `architecture-critic-1.md` written by fresh Phase 4. | Reviewer confirms: old files have a timestamp suffix in their names; a new `architecture-critic-1.md` without suffix exists; its content is from the new Phase 4 run (not the old run). | | | Tests re-run state handling specified in Task 5 step 2. |
