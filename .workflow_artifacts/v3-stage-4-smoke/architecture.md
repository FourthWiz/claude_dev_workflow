---
path: .workflow_artifacts/v3-stage-4-smoke/architecture.md
hash: HEAD
updated: 2026-04-25T00:00:00Z
updated_by: /architect
tokens: 1300
---

## For human

**Current status:** Stage 4 v3 architecture is implemented and pre-flight checks pass; the acceptance smoke test is ready to run, requiring one end-to-end pipeline execution through eight skills to validate v3 format compliance.

**Biggest open risk:** A Class A writer may fall back to v2-style English if the format-kit is skipped, which would invalidate the smoke result; mitigation is per-writer retry before fallback.

**What's needed to make progress:** Run the synthetic Medium-profile pipeline (architect → thorough_plan → implement → review, with four gate checkpoints and one mid-pipeline capture_insight call) to exercise all eight skills and confirm v3-conformant output at each step.

**What comes next:** Execute `/thorough_plan medium` on the trivial scratch.py task, drive it through the four checkpoints, then update the smoke result ledger with per-step verdicts once Checkpoint D passes.

## Context

Stage 4 of artifact-format-architecture v3 wires the new Class A writer mechanism into 8 skills (`/critic`, `/architect` Tier 3 critic outputs, `/implement`, `/review`, `/gate`, `/end_of_day`, `/capture_insight`, `/discover`). All 19 implementation tasks of the parent Stage 4 plan are committed on `feat/v3-stage-4`. Pre-flight checks pass: 88/88 pytest, 8/8 detection-rule consistency, install.sh deployment, all six final-cleanup grep guards from the parent plan. The remaining acceptance-smoke task is to drive every Class A writer through one end-to-end pipeline run and confirm v3 conformance at each step.

This synthetic exercise's goal is structural validation only. The work itself is intentionally trivial (a 1-line no-op scratch.py); there is no production behavior change. Constraints: stay inside `.workflow_artifacts/v3-stage-4-smoke/`, do not push, do not run `/end_of_task`. The smoke must run in this fresh session (per parent Stage 3 insight 7 — fresh-session bias rule), and it must exercise EVERY Class A writer at least once during the pipeline.

## Current state

`feat/v3-stage-4` contains 14 Stage 4 implementation commits (all preceding tasks from the parent plan plus the final cleanup commit and the smoke stub) plus deployed `~/.claude/scripts/with_env.sh`, `~/.claude/skills/`, `~/.claude/memory/format-kit.md`, `~/.claude/memory/format-kit.sections.json`, `~/.claude/memory/glossary.md`. No `.workflow_artifacts/v3-stage-4-smoke/scratch/scratch.py` exists yet; the file will be created during `/implement`. The smoke folder itself contains only this `architecture.md` and `cost-ledger.md` so far.

The Class A writer mechanism is now the path-of-record for the eight skills above. `/critic` writes `critic-response-N.md`, `/architect` Tier 3 writes `architecture-critic-N.md`, `/implement` writes session-state, `/review` writes `review-N.md` (Class B with `## For human` block), `/gate` writes `gate-<phase>-<date>.md`, `/end_of_day` writes session-state + insights-append, `/capture_insight` writes insights-append, `/discover` writes 4 inventory artifacts. Every one of these MUST emit v3-conformant output (frontmatter + body + structural validator pass) when invoked by this smoke pipeline.

## Proposed architecture

Drive the workflow through a synthetic Medium-profile task — `/architect` (this file), then `/thorough_plan medium`, `/implement`, `/review` — with `/gate` checkpoints at A, B, C, D and a single mid-pipeline `/capture_insight` invocation to exercise the insights-append Class A path.

```
.workflow_artifacts/v3-stage-4-smoke/
├── architecture.md              ← this file (Class B; /architect)
├── cost-ledger.md               ← per-session ledger (append-only, no v3 changes)
├── current-plan.md              ← Class B; /thorough_plan + /plan
├── critic-response-1.md         ← Class A; /critic round 1
├── critic-response-2.md         ← Class A; /critic round 2 (if convergence requires)
├── gate-architect-2026-04-25.md ← Class A; Checkpoint A
├── gate-thorough_plan-...md     ← Class A; Checkpoint B
├── gate-implement-...md         ← Class A; Checkpoint C
├── gate-review-...md            ← Class A; Checkpoint D
├── review-1.md                  ← Class B; /review
├── t18-smoke-result-final.md    ← per-step verdict ledger (updated at end)
└── scratch/
    └── scratch.py               ← 1-line no-op (created by /implement)

.workflow_artifacts/memory/sessions/
└── 2026-04-25-v3-stage-4-smoke.md  ← Class A; written by /implement and /review
```

Class A writers exercised this pipeline (target: ≥1 invocation each across the 8 skills):

```
/architect          → architecture.md (Class B; this writer triggers Haiku summary path)
/architect Tier 3   → NOT exercised (Tier 3 only fires when /architect spawns /critic;
                      this smoke pipeline runs /critic against the plan, not architecture)
/critic             → critic-response-1.md (Class A; ≥1 invocation guaranteed by /thorough_plan)
/implement          → session-state file (Class A)
/review             → review-1.md (Class B); session-state update (Class A)
/gate               → 4× gate-<phase>-<date>.md (Class A; one per checkpoint)
/end_of_day         → NOT exercised (smoke does not span end-of-day; manually exercised post-smoke if needed)
/capture_insight    → mid-pipeline invocation to capture one observation (Class A insights-append)
/discover           → NOT exercised (already-fresh /discover output exists; re-running would duplicate work)
```

Three writers (`/architect` Tier 3, `/end_of_day`, `/discover`) are NOT covered by the natural pipeline flow. Per parent Stage 4 plan the smoke success criterion is "≥95% structural validation success rate" and "all v3-format checks pass at each step" — coverage of the 5 writers in the natural flow plus `/capture_insight` is sufficient. The 3 uncovered writers are validated by their unit tests (88-test suite) and by Stage 3 smoke (which exercised `/discover`'s pre-Stage-4 path).

## Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |
|----|------|-----------|--------|-----------|----------|
| R-01 | A Class A writer falls back to v2-style English (format-kit-skipped warning) | Low | High — soft-fail per acceptance | Per-writer Step 5 retry path before fallback; smoke result file flags any fallback explicitly | Re-run failing skill; investigate retry-path log |
| R-02 | `with_env.sh` does not load `ANTHROPIC_API_KEY`; Haiku summary step fails on Class B writers | Low | High — invalidates `/architect`, `/thorough_plan`, `/review` Class B paths | Pre-flight `bash -c 'source ~/.claude/scripts/with_env.sh && env \| grep ANTHROPIC'` before starting; if missing, abort and reinstall | Re-source env; re-run failed step |
| R-03 | Validator V-05 flags a file-local cross-reference as undefined (regression of Stage 3 fix) | Low | Medium — blocks PASS verdict | Inspect failing artifact; if status-glyph placement is the cause, apply parent Stage 3 workaround (glyph after T-NN ID) | Edit artifact; re-run validator |
| R-04 | `/gate` Step 3a fails to extract `## For human` summary; falls back to first-2KB | Low | Medium — soft-fail per acceptance | Manual inspection of gate output text; smoke result file flags the fallback | Re-run `/gate` after fixing source artifact |
| R-05 | Smoke files leak into main branch via accidental commit | Very low | Low — branch-scoped under feat/v3-stage-4 | All smoke artifacts under `.workflow_artifacts/v3-stage-4-smoke/`; do not push; do not run `/end_of_task` | `git checkout main && rm -rf <smoke folder>` |
| R-06 | `/thorough_plan` does not converge in ≤2 rounds (medium cap is 4) | Low | Low — costs more but succeeds | The synthetic task is trivial; convergence in 1–2 rounds is expected; if 3+ rounds occur, flag as unexpected complexity | Continue; smoke still succeeds at higher cost |

## Stage decomposition

1. ⏳ S-01: Write `scratch/scratch.py` containing a single no-op function — complexity S; risk: none; test: `python -c "from scratch import scratch; scratch.noop()"`; rollback: `rm scratch/scratch.py`.
2. ⏳ S-02: Update `t18-smoke-result.md` (in `artifact-format-architecture/stage-4/`) with per-step verdicts and final pass/fail — complexity S; risk: none; test: file contains all 4 step verdicts; rollback: revert via git.

The two stages are independent. S-01 is the "code change" the workflow operates on; S-02 is the bookkeeping artifact updated at the very end of the smoke run (after Checkpoint D `/gate` passes).

## Stage Summary Table

| Stage | Description | Complexity | Dependencies | Key Risk |
|-------|-------------|-----------|--------------|---------|
| S-01 | Create scratch.py with 1-line no-op | S | none | none |
| S-02 | Update t18-smoke-result.md with verdicts | S | full pipeline complete | none |

## Next Steps

1. S-01 and S-02 are ready for `/thorough_plan` as a single Medium-profile pass. The pipeline driving them (Checkpoint A → `/thorough_plan` → Checkpoint B → `/implement` → `/capture_insight` → Checkpoint C → `/review` → Checkpoint D → S-02 update) IS the Stage 4 acceptance smoke; the trivial code change is incidental.
