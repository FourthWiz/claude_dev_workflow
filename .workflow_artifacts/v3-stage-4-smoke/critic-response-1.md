---
path: .workflow_artifacts/v3-stage-4-smoke/critic-response-1.md
hash: HEAD
updated: 2026-04-25T00:00:00Z
updated_by: /critic
tokens: 1100
round: 1
target: .workflow_artifacts/v3-stage-4-smoke/current-plan.md
date: 2026-04-25
---

## Target
Round 1 critique of `.workflow_artifacts/v3-stage-4-smoke/current-plan.md` (Medium-profile smoke plan; underlying work is a no-op `scratch.py`; real unit under test is the v3 Class A writer pipeline).

## Verdict: REVISE

## Summary
Plan correctly scopes the synthetic smoke and stays minimal (two tasks, no over-testing of `scratch.py`). Two MAJOR issues: the `/review`-fallback risk row's rollback would falsify the acceptance signal it is meant to recover, and the smoke-results "Class A write success rate" line lacks a defined denominator so the line is not falsifiable. Three Minor issues on procedure-cwd specificity, deferred-action placement, and a missing primary-path mitigation.

## Issues

### Critical (blocks implementation)

(none)

### Major (significant gap, should address)

1. **[CRIT-1] /review-fallback rollback path falsifies the smoke acceptance signal.**
   - What: The plan's risk row for the `/review` `with_env.sh` hang lists rollback as "Edit `review-1.md` post-hoc to add `## For human` block sourced from a manual Haiku call." If `/review` falls back to v2 because of the `with_env.sh` hang, manually patching the artifact does not exercise the Class B v3 writer mechanism — it produces a v3-shaped file without the writer ever taking the v3 path.
   - Why it matters: The parent Stage 4 plan's acceptance smoke task requires the smoke to record per-step verdicts including whether the writer itself emitted v3. A post-hoc patched `review-1.md` would be indistinguishable from a successful v3 write at file-shape level, but the success-rate metric (writes that passed validator on first attempt vs. fallbacks) would be silently inflated. Smoke result becomes misleading.
   - Where: current-plan.md `## Risks` table, third risk row (the one about `/review` hitting the same wrapper hang), "Rollback" column.
   - Suggestion: Replace the rollback with "re-run `/review` after applying the architect-phase `with_env.sh` workaround (`bash -c '. ~/.zshrc 2>/dev/null; export ANTHROPIC_API_KEY; python3 ...'`); if a second attempt also falls back, record as v2 fallback in the smoke-result file and let the ≥95% budget absorb it. Do NOT post-hoc edit `review-1.md`."

2. **[CRIT-2] Smoke-results "Class A write success rate" denominator is undefined.**
   - What: The plan's second task acceptance requires a "Class A write success rate" line with a percentage, but neither the task nor the architecture defines the denominator (the count of Class A writes the smoke is expected to produce). Architecture `## Proposed architecture` enumerates five Class A writers exercised naturally plus `/capture_insight` (six invocations), but the parent Stage 4 plan's acceptance smoke task step 8 sets the target denominator at 12-15 writes.
   - Why it matters: Without a defined denominator the percentage is gameable (e.g., 4/4 = 100% if you only count the gate audit logs). Acceptance is not falsifiable. Reviewers cannot tell whether a reported 100% means "all writers succeeded" or "we only counted half the writers."
   - Where: current-plan.md `## Tasks` second task acceptance bullet "Section contains a 'Class A write success rate' line with a percentage."
   - Suggestion: Specify the denominator explicitly in the second task acceptance — for this smoke, expected Class A writes are: four `/gate` audit logs (Checkpoints A through D), two session-state writes (one from `/implement`, one from `/review`), one `critic-response-1.md` (more if convergence requires round 2), one `/capture_insight` insights-append → expected eight to nine Class A writes. Add an acceptance bullet: "Section names the denominator and lists each counted write by filename." Also reconcile with the parent plan's "12-15 writes" target (the parent count includes Class B writes; clarify which class the rate covers).

### Minor (improvement, use judgment)

1. **[MIN-1] Acceptance bullet for the scratch.py task does not state the cwd that the importlib invocation depends on.**
   - Suggestion: The plan's first task acceptance command works only when cwd is `.workflow_artifacts/v3-stage-4-smoke/` (cwd auto-added to `sys.path`). The procedures pseudo-code shows the `cd`, but the acceptance bullet does not — implementer reading acceptance alone could miss it. Add cwd to the acceptance bullet, e.g., "running from `.workflow_artifacts/v3-stage-4-smoke/`, `python3 -c '...'` exits 0."

2. **[MIN-2] Deferred ledger-update belongs in the session-state Unfinished work section, not just Decisions.**
   - Suggestion: The plan's `## Decisions` paragraph notes the second task is performed after Checkpoint D and "logged in the session-state Decisions section so it is not forgotten." But the implementer reading session state checks `## Unfinished work` for resume hints, not `## Decisions made`. Add the ledger-update task explicitly to `## Unfinished work` of the session-state file at /implement time, with the resume condition "after Checkpoint D /gate passes."

3. **[MIN-3] /review-fallback risk's mitigation should call out the proven primary-path workaround.**
   - Suggestion: The `/review`-hang risk's mitigation says "Pre-emptive workaround already known: invoke summary script via direct env-load." That workaround is already proven in this session (architect step 2 retry). Make the mitigation actionable by naming the exact form: "If `with_env.sh` hangs, /review should swap to `bash -c '. ~/.zshrc 2>/dev/null; export ANTHROPIC_API_KEY; python3 summarize_for_human.py ...'` for that single invocation." This makes the mitigation copy-pasteable rather than aspirational.

## What's good

1. Scope discipline. Plan resists the temptation to add "more rigorous testing" of `scratch.py` (`## Notes` flags this explicitly). Smoke-as-unit-under-test framing is correct and matches the parent Stage 4 plan's acceptance-smoke-task intent.
2. Use of `importlib.import_module` in the scratch-py-acceptance bullet avoids relative-import edge cases. Verified independently in this critic session (test exit 0).
3. Risk inventory is concrete and lifecycle-relevant (the `/review` wrapper-hang risk, the commit-pollution risk, the convergence-cap risks) rather than generic boilerplate.
4. The deliberate post-Checkpoint-D timing for the ledger update avoids polluting the `/implement` commit. Sequencing decision is correct.
5. References section names every prerequisite artifact (architecture, parent plan, pre-flight stub, prior smoke template, session-state). Implementer has all the bootstrap context.
6. Convention compliance: the canonical `1. ⏳ task-id: ...` form (status glyph before identifier) is used throughout — confirmed to validate cleanly under deployed V-05 regex per session-state record.

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | fair | Three writers (`/architect` Tier 3, `/end_of_day`, `/discover`) explicitly out of scope but Class A coverage gaps are not reflected in the success-rate denominator. |
| Correctness | good | File paths, importlib invocation, parent-plan references all verified. The scratch-py acceptance command runs exit-0. |
| Integration safety | good | No production code change. Smoke isolated to `.workflow_artifacts/v3-stage-4-smoke/` per architecture risk-register row five. |
| Risk coverage | fair | Six risks identified with mitigations + rollbacks. The `/review`-hang rollback is misleading; that risk's mitigation also lacks the primary-path detail. |
| Testability | good | Acceptance bullets are concrete and runnable for the scratch-py task. The smoke-results denominator gap is the lone exception. |
| Implementability | good | Two trivial tasks, dependencies clear (the ledger-update task depends on full pipeline). Implementer can follow without major decisions. |
| De-risking | good | Known `with_env.sh` regression acknowledged; convergence-round budget acknowledged. Synthetic-task minimality acknowledged in `## Notes`. |
