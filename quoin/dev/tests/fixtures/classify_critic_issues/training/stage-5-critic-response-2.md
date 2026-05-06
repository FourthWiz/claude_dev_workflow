---
task: quoin-foundation
stage: 5
phase: critic
round: 2
date: 2026-04-27
loop_signal: none
model: claude-opus-4-7
class: A
target: current-plan.md
---
## Verdict: REVISE

## Summary

Round-2 revision resolves all 8 round-1 issues (1 CRIT, 4 MAJ, 3 MIN) — verified empirically file-by-file: the new task that scrubs weekly_review/SKILL.md keeps the negative-instruction intent without the dead script names; the precondition gate vs branch hygiene split hard-stops before any branch op; the install.sh task adds explicit `rm -f` cleanup with a ≥2 acceptance grep; the smoke task gains both a byte-equality cross-check phase and a 3-run Haiku stability phase. However, one new MAJOR contradiction was introduced by the byte-equality phase: the assertion across the 5 Class B writer Step 2 blocks cannot pass given the documented variable substitution ("path" for architect/review vs "plan-path" for plan/revise/revise-fast) — the diff will show 1-2 lines of variable-name divergence on every comparison. Plus 3 minor issues (letter-suffixed task IDs invisible to validator V-05; the file-deletion task lacks a pre-existence guard for the auxiliary POC doc; the install-sync task's absence-test does not catch a regression of the cleanup loop). No loop signal: every round-1 issue title is genuinely resolved, not re-litigated. Round-2 strict decrease (1 CRIT + 4 MAJ + 3 MIN to 0 CRIT + 1 MAJ + 3 MIN). Critic, plan, revise, revise-fast, review, weekly review skill files were all read empirically against the source tree.

## Issues

### Critical (blocks implementation)

(none)

### Major (significant gap, should address)

- **MAJOR — byte-equality cross-check phase contradicts the canonical Step 2 procedure block's documented variable substitution**
  - What: The smoke task's byte-equality phase asserts `for s in plan revise revise-fast review; do diff <(sed -n '/^\*\*Step 2:/,/^\*\*Step 3:/p' dev-workflow/skills/$s/SKILL.md) <(sed -n '/^\*\*Step 2:/,/^\*\*Step 3:/p' dev-workflow/skills/architect/SKILL.md); done` returns empty (zero diff lines) across all 4 comparisons. But the canonical procedure block itself documents (line 268 of current-plan.md): "variable substitution at the variable marker (path for architect/review; plan-path for plan/revise/revise-fast)". The architect-wiring task and the review-wiring task explicitly use the path marker; the plan-wiring task and the revise-wiring task explicitly use the plan-path marker. After /implement runs, the actual deployed Step 2 blocks WILL contain `path.body.tmp` references in 2 files and `plan-path.body.tmp` references in 3 — so the diff against architect from any of plan/revise/revise-fast will produce at least 2 lines of variable-name delta (the "Read the artifact body from path.body.tmp" line and the prompt-composition line). The byte-equality phase acceptance gate will FAIL on every implementation run.
  - Why it matters: the byte-equality phase is the entire mechanism by which the smoke task claims to cover all 5 Class B writers from a smoke on 3 fresh artifacts. Decision four cites it explicitly: "Step-2 byte-equality cross-check proves smoke-on-3 covers all 5 writers because the Step 2 mechanism is byte-identical across them". If that phase fails, /implement halts at the smoke task. The deeper failure: decision four's claim that smoke-on-3 covers all 5 is itself wrong, because byte-identity of Step 2 was never the design — the prose around the variable marker IS divergent by design. This is the round-1 MAJOR issue on smoke coverage resurfacing in a new shape (the new phase doesn't actually prove what it claims).
  - Where: current-plan.md byte-equality phase (lines 175 and 388-393); the canonical procedure block (line 268); decision four (line 221); also referenced in the revise-wiring task acceptance line 96 (revise vs revise-fast diff — that ONE works because both use the plan-path marker).
  - Suggestion: Either (a) **normalize the variable marker** — pick one (e.g., `<artifact-path>` everywhere; the writers can interpret it locally). Update the canonical procedure block to drop the variable-substitution clause; update the four Step-2 wiring tasks each to use the chosen marker. Then byte-equality is achievable AND meaningful. OR (b) **change the byte-equality contract** — instead of asserting full Step 2 block byte-equality, assert byte-equality of an EXTRACTED canonical block: e.g., `sed -e 's/<plan-path>/<path>/g'` on each Step 2 block before diffing. The canonicalized blocks should be byte-equal modulo the path-variable name. This preserves the smoke-on-3-covers-5 claim. Option (a) is cleaner; option (b) is a smaller diff. Either way, the byte-equality phase text needs to change before /implement runs.

### Minor (improvement, use judgment)

- **MINOR — letter-suffixed task IDs are invisible to validate_artifact.py V-05**
  - Suggestion: Empirically verified — V-05's regex never matches the letter-suffixed task identifiers (precondition gate, branch hygiene, weekly-review scrub) because the trailing letter blocks the word-boundary; the definition-line regex similarly skips them. The current plan validates clean only because the orphan-ref check is silently bypassed for these three identifiers. The plan body references the suffixed identifiers from other tasks (e.g., risk nine mentions the branch-hygiene task, risk thirteen mentions the precondition-gate task, the file-deletion task acceptance mentions "post-weekly-review-scrub", the install-sync verification mentions "post-weekly-review-scrub propagation") — every one of those references is invisible to V-05. If a future round misspells the weekly-review-scrub identifier, the validator will not catch it. Two robust options: (a) renumber the 3 letter-suffixed tasks to plain integer IDs and document execution order separately (cheap fix; preserves V-05 coverage); (b) accept the gap and add a single sentence to decision three documenting that V-05 does not validate letter-suffixed identifiers (low-cost transparency). Option (a) is preferred for new plans going forward; this plan is well-tested enough that (b) is acceptable round-2.

- **MINOR — the file-deletion task deletes the auxiliary POC doc without a pre-existence guard**
  - Suggestion: The file-deletion task runs `git rm dev-workflow/scripts/tests/manual-summarize-poc.md` unconditionally. If that file is ever deleted before /implement runs (e.g., by a manual cleanup or a previous Stage 5 attempt that aborted partway), `git rm` exits non-zero and the task stops. The other 4 `git rm` targets (summarize_for_human.py, with_env.sh, test_summarize_for_human.py, test_with_env_sh.py) have the same exposure but they are core deliverables; the POC doc is auxiliary. Add `git rm` invocations with `--ignore-unmatch` flag for the auxiliary doc, OR add a pre-existence check: `test -e <file> && git rm <file> || true`. Low-impact, but a cheap robustness improvement. Same pattern would help if the file-deletion task is ever re-run on a partially-completed working tree.

- **MINOR — the install-sync task does not actually catch a regression of the cleanup loop**
  - Suggestion: The install-sync task step 1 runs install.sh and verifies that `~/.claude/scripts/summarize_for_human.py` does NOT exist post-run (lines 161-163). This indirectly verifies the install.sh cleanup block fired. But if install.sh's cleanup-loop is silently skipped (e.g., a future regression deletes the loop), the absence test passes ONLY on machines that didn't have the script in the first place. To make the install-sync task catch a regression of the install.sh task, add a positive contract: pre-create a stub file at `~/.claude/scripts/summarize_for_human.py` BEFORE running install.sh, and then assert it's removed afterward. This converts the install-sync task from "absence test" to "removal test". Belt-and-suspenders against silent-deploy failures.

## What's good

- The split of the round-1 single task zero into a precondition gate (no working-tree mutation, queries `origin/main` via `git show`) and a branch-hygiene task (commit-stash, checkout main, fetch, create branch) is exactly the right shape — addresses the round-1 sequencing-bug critique precisely. The new precondition-gate procedure block is well-scoped (set -e; two `git show` checks; clear STOP messages naming which parent stage to merge); decision eight documents the rationale; risk thirteen catches the bypass risk.
- The weekly-review scrub wording is empirically validated against the source: lines 53 and 120 of weekly_review/SKILL.md genuinely contain the script names; the rewrite preserves the negative-instruction intent ("the Haiku writer", "no separate summarizer call", "do not invoke any separate summarizer or validator script") without the deletion-collision string.
- The install.sh cleanup-loop block is clean shell, idempotent, and the ≥2 acceptance grep contract is precisely-stated; decision seven codifies it as a reusable pattern.
- The smoke task's stability check is well-bounded (3 runs, ±2 lines, all in [1, 12]) — converts decision six from wishful to verified.
- The file-deletion task acceptance is correctly split into source-tree sweep + install.sh allow-list (decision-seven corollary) — preserves the contract while accommodating the legitimate `rm -f` mentions.
- The author-summary-prompt task's switch from `eval()` byte-equality to SHA-256 in the commit message body is durable across the script's deletion (the round-1 brittleness is genuinely gone).
- The lessons-capture task's blocked glyph correctly signals to /implement that lessons-capture is owned by /end_of_task.
- Cost discipline is exemplary: round 2 produced 1 MAJOR + 3 MINOR (vs round 1's 1 CRIT + 4 MAJ + 3 MIN) — strict decrease; lesson 2026-04-22's anti-target is honored.

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | good | All 8 round-1 issues genuinely addressed; new MAJOR (byte-equality phase contradiction) is a fresh finding, not a regression |
| Correctness | fair | Canonical procedure vs byte-equality phase internal contradiction on variable substitution; weekly-review scrub wording empirically verified to match source |
| Integration safety | good | Precondition-gate vs branch-hygiene sequencing fix is correct; install.sh cleanup is robust; cleanup-pattern decision reusable |
| Risk coverage | good | Stability gate (variance bound + V-06 hard cap) is the right shape; bypass risk is documented; install-sh cleanup-failure risk correctly downgraded |
| Testability | fair | Stability check well-defined; byte-equality phase contradicts canonical procedure (see MAJOR above) |
| Implementability | good | Tasks sequenced; commit messages templated; acceptance grep-able; letter-suffixed task IDs are V-05-invisible (see MINOR) but V-05 still passes |
| De-risking | good | Precondition gate fires BEFORE branch creation; install.sh self-cleans; lesson capture defers to /end_of_task |
