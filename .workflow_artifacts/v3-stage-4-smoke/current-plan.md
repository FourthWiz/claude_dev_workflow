---
path: .workflow_artifacts/v3-stage-4-smoke/current-plan.md
hash: HEAD
updated: 2026-04-25T00:00:00Z
updated_by: /revise-fast
tokens: 1100
plan_round: 2
---

## For human

**Current status:** Plan is in round 2 (revised once), awaiting implementation of two tasks: write a trivial no-op Python file and later update the smoke-results ledger after the pipeline completes.

**Biggest open risk:** The `with_env.sh` wrapper may hang again during the `/review` step (medium likelihood), though a workaround command has been proven and the fallback is budgeted.

**What's needed to make progress:** Execute T-01 (create `scratch/scratch.py` with a single no-op function ≤10 lines) and run it through the full v3 pipeline (`/implement` → `/review` → Checkpoint D `/gate`).

**What comes next:** After Checkpoint D passes, manually update the smoke-results ledger file with per-step verdicts, Class A write success rate, and any findings, then commit separately from the T-01 code commit.

## State
```yaml
task: v3-stage-4-smoke
profile: medium
current_stage: plan-round-2-converged
model: opus
plan_round: 2
session_uuid: f0866bc5-f096-4f20-9e78-deb461d9f570
parent_task: artifact-format-architecture
parent_stage: stage-4
purpose: drive Class A v3 writers end-to-end via a synthetic trivial code change
```

## Convergence Summary
- **Task profile:** Medium
- **Rounds:** 2
- **Final verdict:** PASS
- **Key revisions:** Round 2 closed five round-1 issues (2 MAJOR + 3 MINOR): (a) corrected the `/review`-fallback rollback wording in R-03 to re-run with the proven workaround instead of post-hoc patching the artifact; (b) defined an explicit Class A write denominator (8–9 writes, enumerated by filename) for T-02's success-rate acceptance, distinguishing Class A scope from the parent Stage 4 plan's broader 12–15-write target; (c) added cwd to T-01's importlib acceptance bullet; (d) added an instruction to add the deferred ledger update to session-state `## Unfinished work` at `/implement` time; (e) embedded the verbatim `with_env.sh` workaround command into R-03's mitigation column.
- **Remaining concerns:** None blocking. The known Stage 5 follow-up (deployed `with_env.sh` wrapper hangs on `. ~/.zshrc` under bash subshell with `set -eu`) is acknowledged in R-03 with a proven workaround; the pipeline tolerates one v2 fallback within the ≥95% budget.

## Tasks

1. ⏳ T-01: Write `scratch/scratch.py` containing a single no-op function.
   - File: `.workflow_artifacts/v3-stage-4-smoke/scratch/scratch.py`
   - Content: one Python function `noop()` that takes no arguments, does nothing (a `return` or `pass` statement; no I/O, no logging, no side effects), plus an `if __name__ == "__main__": noop()` guard so the file is directly runnable.
   - Why: gives the workflow a real (but trivial) code change to operate on, so `/implement`, `/review`, `/gate` (post-implement Standard) all have something to inspect. Mirrors the parent Stage 3 smoke pattern of using a no-op as the unit of work.
   - Acceptance:
     - File exists at the specified path.
     - Running from cwd `.workflow_artifacts/v3-stage-4-smoke/`, `python3 -c "from importlib import import_module; m = import_module('scratch.scratch'); m.noop()"` exits 0.
     - File is ≤10 lines including the guard.
     - No imports beyond the standard library; ideally no imports at all.

2. ⏳ T-02: Update `.workflow_artifacts/artifact-format-architecture/stage-4/t18-smoke-result.md` with per-step verdicts and the smoke findings.
   - File: existing pre-flight stub at `.workflow_artifacts/artifact-format-architecture/stage-4/t18-smoke-result.md` (read at the start of `/end_of_task` follow-up; NOT in this smoke folder).
   - Content: append a `## Live smoke results` section listing per-step verdicts (architect / Checkpoint A / thorough_plan / Checkpoint B / implement / capture_insight / Checkpoint C / review / Checkpoint D), the Class A write success-rate metric with denominator and per-filename list, and any findings (Stage 5 follow-ups). Existing pre-flight content is preserved.
   - Why: the parent Stage 4 plan's acceptance-smoke task requires an updated `t18-smoke-result.md` reflecting the live smoke. Without this update there is no evidence trail.
   - Acceptance:
     - File at the specified path contains a new `## Live smoke results` section.
     - Section contains ≥9 per-step verdict lines (one per pipeline step exercised).
     - Section contains a "Class A write success rate" line with a percentage, a named denominator of 8–9 Class A writes, and a per-filename list of each counted write. Expected Class A writes: four `/gate` audit logs (Checkpoint A through D), two session-state writes (one from `/implement`, one from `/review`), one `critic-response-1.md` (more if convergence requires additional rounds), one `/capture_insight` insights-append — totalling eight to nine Class A writes. (The parent Stage 4 plan's "12–15 writes" target includes Class B writes such as `architecture.md`, `current-plan.md`, and `review-1.md`; the rate reported here covers Class A writes only.)
     - Section contains a "Smoke findings" subsection listing the `with_env.sh` regression and any other surprises.
     - File is committed (separate commit; do NOT mix with T-01 commit; see R-04 below).

## Decisions

T-02 is performed at the very end of the smoke run, AFTER Checkpoint D `/gate` passes. It is not part of `/implement`'s output for T-01 — the bookkeeping update happens after the pipeline completes so it can record verdicts that don't exist yet at `/implement` time. This means T-01 is the only task that flows through `/implement` → `/review` → Checkpoint D; T-02 is a manual ledger update afterward. At `/implement` time, the implementer must add a row to session-state `## Unfinished work` with the resume condition "after Checkpoint D `/gate` passes" so the deferred action is not lost.

The plan deliberately ALLOWS the v2-fallback path to fire for any Class B writer if the deployed `with_env.sh` wrapper hangs again (the pre-`/architect` finding). The smoke records the fallback as a finding rather than aborting. This matches the parent Stage 4 plan's "≥95% structural validation success rate" acceptance: a single v2-fallback at `/architect` consumed in the prior step is still well below the 5% allowance.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |
|----|------|-----------|--------|-----------|----------|
| R-01 | T-01 acceptance test fails because of import-path quirks (Python relative-import edge cases) | Low | Low | Use `from importlib import import_module` form in acceptance check; place `scratch.py` directly under `scratch/` (no `__init__.py` needed when imported via importlib + `sys.path`) | Re-run with explicit `sys.path.insert(0, "<smoke-folder>")` |
| R-02 | `/implement` writes additional files beyond what T-01 specifies (scope creep) | Very low | Low — caught by `/review` and Checkpoint C diff inspection | Plan explicitly bounds T-01 to a single file ≤10 lines; `/review` will flag extra files | Manual `git rm` of extra files |
| R-03 | Class B writer (`/review`) hits the same `with_env.sh` hang and falls back to v2 | Medium | Medium — counts toward fallback budget (≤5%) | If `with_env.sh` hangs, swap to `bash -c '. ~/.zshrc 2>/dev/null; export ANTHROPIC_API_KEY; python3 summarize_for_human.py ...'` for that single invocation. Already proven in the architect step 2 retry. | Re-run `/review` after applying the workaround above; if a second attempt also falls back, record as v2 fallback in the smoke-result file and let the ≥95% budget absorb it. Do NOT post-hoc edit `review-1.md`. |
| R-04 | T-02 update gets committed together with T-01, polluting the implement-phase commit | Low | Low — bookkeeping only | T-02 explicitly deferred to post-Checkpoint-D in this plan's Decisions section; session-state captures the deferred action | `git reset --soft HEAD^ && git restore --staged t18-smoke-result.md` and recommit separately |
| R-05 | Convergence does not occur in ≤2 rounds (medium cap = 4) | Low | Low — costs more but succeeds | Plan is deliberately minimal (2 tasks, no integration risk); critic should have nothing to flag beyond minor wording | Continue rounds; smoke succeeds at higher cost |
| R-06 | `/critic` round 1 misclassifies the trivial nature of the work and demands more elaborate testing/decomposition | Low | Low — handled by the fast-revision path in round 2 | The architecture explicitly justifies the minimal scope; the reviser can cite that justification verbatim | Continue to round 2; if persistent, escalate to user |

## Procedures

```
# T-01 implementation pseudo-code
mkdir -p .workflow_artifacts/v3-stage-4-smoke/scratch
write file .workflow_artifacts/v3-stage-4-smoke/scratch/scratch.py:
  """No-op smoke test for v3-stage-4 Class A writer pipeline."""
  def noop():
      """Do nothing. Exists so /implement has a unit of work to flow through."""
      return None
  if __name__ == "__main__":
      noop()
verify (cwd = .workflow_artifacts/v3-stage-4-smoke/):
  python3 -c "from importlib import import_module; m = import_module('scratch.scratch'); m.noop()"
  expect exit 0
```

```
# T-02 ledger-update pseudo-code (executed AFTER Checkpoint D gate passes)
read .workflow_artifacts/artifact-format-architecture/stage-4/t18-smoke-result.md
append section:
  ## Live smoke results
  - architect: PASS / FAIL — <verdict + notes>
  - Checkpoint A: PASS / FAIL — ...
  - thorough_plan: PASS / FAIL — ...
  - Checkpoint B: PASS / FAIL — ...
  - implement: PASS / FAIL — ...
  - capture_insight: PASS / FAIL — ...
  - Checkpoint C: PASS / FAIL — ...
  - review: PASS / FAIL — ...
  - Checkpoint D: PASS / FAIL — ...
  ## Class A write success rate
  - Denominator: 8–9 Class A writes expected (4 gate audit logs for Checkpoints A–D,
    2 session-state writes from /implement and /review, 1 critic-response-1.md,
    1 /capture_insight insights-append)
  - Listed writes: <filename-1>, <filename-2>, ..., <filename-N>
  - Result: <N>/<M> writes passed validator on first attempt → <%>% (Class A only)
  ## Smoke findings
  1. <finding>: <severity> — <description> — <suggested follow-up>
git add -p (stage only the t18-smoke-result.md change)
git commit -m "docs(format-arch): T-18 — record Stage 4 smoke results"
```

## References

- Architecture: `.workflow_artifacts/v3-stage-4-smoke/architecture.md` (this smoke folder).
- Parent Stage 4 plan: `.workflow_artifacts/artifact-format-architecture/stage-4/current-plan.md` (defines the acceptance-smoke task criteria).
- Pre-flight stub: `.workflow_artifacts/artifact-format-architecture/stage-4/t18-smoke-result.md` (the ledger T-02 updates).
- Prior Stage 3 smoke as template: `.workflow_artifacts/v3-stage-3-smoke/` (mirror its structure where applicable).
- Session state for resume: `.workflow_artifacts/memory/sessions/2026-04-25-v3-stage-4-smoke.md`.

## Notes

The plan is deliberately minimal because the SMOKE PIPELINE itself is the unit under test; the underlying code change is incidental. Any temptation to add "more rigorous testing" or "additional safety" should be resisted — that would shift the smoke from "exercise the writers" to "exercise the writers PLUS test scratch.py", inflating cost without improving the acceptance signal.

## Revision history

1. Round 1 — 2026-04-25
   Critic verdict: REVISE
   Issues addressed: (none — plan written fresh by /plan)
   Changes: Initial plan; two tasks, six risks, pseudo-code procedures.

2. Round 2 — 2026-04-25
   Critic verdict: REVISE (2 MAJOR + 3 MINOR)
   Issues addressed: [round-1 MAJOR-1] /review-fallback rollback path — replaced post-hoc edit with re-run instruction + proven workaround command; [round-1 MAJOR-2] smoke-results denominator undefined — added named denominator (8–9 Class A writes), per-filename list requirement, and Class A vs. Class B rate clarification to T-02 acceptance; [round-1 MINOR-1] T-01 cwd not stated in acceptance bullet — added explicit cwd `.workflow_artifacts/v3-stage-4-smoke/`; [round-1 MINOR-2] deferred ledger-update not in session-state Unfinished work — added note to Decisions that implementer must add to session-state `## Unfinished work`; [round-1 MINOR-3] R-03 mitigation lacked proven primary-path command — replaced aspirational description with verbatim workaround command (already proven in architect step 2 retry).
   Changes: T-01 acceptance bullet, T-02 acceptance bullet (denominator + filename list + Class A/B clarification), Decisions paragraph (implementer duty at /implement time), R-03 Mitigation and Rollback columns, Procedures T-02 pseudo-code (denominator + listed-writes lines).
