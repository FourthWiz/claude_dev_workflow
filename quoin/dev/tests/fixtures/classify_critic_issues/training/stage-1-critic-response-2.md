---
round: 2
date: 2026-04-25
target: stage-1/current-plan.md
task: quoin-foundation
class: A
---

## Verdict: REVISE

## Summary

The round-2 revision genuinely addresses 3/3 CRITICAL and 7/7 MAJOR issues from round 1 — the per-file insertion-anchor table is real, the `extract_preamble_block` slicer plus `dispatched-tier:` distinctive token is a sound two-layer defense against frontmatter collision, the bare-sentinel canonical form is now consistent across plan/architecture/tests, and D-08's fail-graceful runtime safeguard is a legitimately new architectural protection (not a paper-over). However, the CRIT-2 fix introduced a new MAJOR by accident: in defining the §0 dispatch-action prose to embed `dispatched-tier: model: "<declared>"` INSIDE the Agent tool's `description:` string, the revision deleted the real `model:` parameter from the dispatch invocation entirely — the harness now receives no model argument, only a descriptive string mentioning a tier. The recursion-guard contract is now consistent, but the dispatch contract itself was broken in the same edit. Two smaller new issues: T-00 produces a static template that does not itself verify anything (the verification is wholly deferred to T-09 Phase A, post-implement, post-install — leaving the de-risking pre-merge value of T-00 unclear), and the install.sh "no diff in this stage" claim collides with the Notes paragraph that punts a possible install.sh edit for verify_subagent_dispatch.md deployment to T-10's "inspection only" step.

## Issues

### Critical (blocks implementation)

(none — CRIT-1/2/3 from round 1 are addressed; no new CRITICAL.)

### Major (significant gap, should address)

- **MAJ-1 (NEW) — `dispatched-tier:` collision fix lost the actual `model:` parameter on the Agent invocation**
  - What: Architecture line 73-83's §0 prose specifies the dispatch with `model: "<declared>"` as a SEPARATE parameter on the Agent subagent invocation (alongside `description:` and `prompt:`). Round-2 plan T-01 sub-bullet at lines 71-72 rewrites the dispatch-action prose to: `Spawn an Agent subagent w/ description: "<skill name> dispatched-tier: model: \"<declared>\"" and prompt: "[no-redispatch]\n<original user input verbatim>"`. The literal `model:` parameter on its own line (architecture line 73) is GONE — the only mention of `model:` is now embedded inside the `description:` string as a unique-token marker for the structural test. The Agent tool will see `description="<skill> dispatched-tier: model: \"haiku\""` and `prompt=...` — but NO `model` argument. The harness will dispatch the subagent at the parent's tier (Opus 1M), defeating the entire stage. The CRIT-2 fix solved the frontmatter-collision test problem but accidentally deleted the load-bearing dispatch parameter.
  - Why it matters: This is exactly the C1 silent-failure mode that round-1 critic flagged, now caused by the round-2 edit rather than by harness incompatibility. T-04 case (c) (`assert slice contains 'dispatched-tier: model: "<value>"'`) will PASS even though the §0 prose tells the harness to dispatch at no specific tier. The structural test would mark green while the cost guardrail no-ops in production. T-09 Phase A is the only thing that catches this — and only catches it post-implement-post-install. The fail-graceful path (D-08) won't even fire here, because the harness doesn't ERROR — it silently runs the subagent at the parent tier with a missing model argument (or treats `model` as undefined and uses default). Worst-case the user sees a "Spawning subagent..." banner (Phase A signal i) but the response is generated on Opus 1M anyway, and Phase A is satisfied incorrectly.
  - Where: T-01 acceptance lines 71-72 (full dispatch action prose); T-04 case (c) at plan line 146 (assertion satisfied by string match alone, not by real dispatch behavior); architecture.md lines 73-83 (the canonical form the round-2 revision drifted from).
  - Suggestion: Restore the explicit `model: "<declared>"` parameter on its own line in the dispatch action prose (matching architecture lines 73-83 verbatim). Use `dispatched-tier:` as a SEPARATE distinctive marker — e.g., place it on a comment line or a separate prose phrase like "Dispatch reason: dispatched-tier handoff to <declared> tier." The structural test should slice the §0 block and assert two things separately: (i) `model: "<declared>"` appears as a parameter line (matching frontmatter is fine post-slicing, since the slicer excludes frontmatter), AND (ii) the unique `dispatched-tier:` marker appears somewhere in the slice. Two-layer defense as D-06 envisions: the slicer is the load-bearing isolation; the marker is the secondary signal. The slicer alone makes `model: "haiku"` safe to assert because it cannot collide with frontmatter (which is not in the slice).

- **MAJ-2 — T-09 Phase A is the SOLE pre-merge-checked verification of the dispatch parameter, AND it runs after install**
  - What: T-00 produces a markdown template (`verify_subagent_dispatch.md`) and a 30-line script that just writes the template (T-00 procedure at plan lines 278-296). The script does NOT itself spawn a subagent; it documents the procedure for the user to follow in T-09 Phase A. So T-00's actual verification value is zero pre-merge — it's a documentation generator. The real verification is T-09 Phase A: open Claude Code on Opus 1M, type `/gate`, observe banner. T-09 runs after `/implement` finishes AND after `bash install.sh` redeploys (procedure step 1 at plan line 334). By the time T-09 fires, the 12 SKILL.md files are committed and live in `~/.claude/skills/`; if Phase A reveals the silent-failure mode, the user must `git revert` AND re-run install.sh to undo. The plan's stage-1 acceptance (line 375) requires `verify_subagent_dispatch.md` `## Result` = `verified`, not `failed`/`untested` — but if it's `failed`, we are already past the deployment.
  - Why it matters: The architecture's R-01 (recursion bug) hardlock is "Low likelihood / High impact." But MAJ-1 (above) is essentially "High likelihood / High impact" until corrected — the dispatch-parameter regression is silent. Combined with T-09's post-install ordering, the failure mode is "ship code, redeploy, observe failure, revert, redeploy." This is a worse de-risking posture than round 1 had — round 1 at least had the manual-smoke task as a documented HITL gate. Round 2 added T-00 which the critic explicitly asked for as a "one-shot diagnostic that the user runs once at install" (round-1 MAJ-3 suggestion text at critic-response-1.md:59) — but the plan implements T-00 as a documentation generator, not a runnable diagnostic. The script could be made to actually invoke an Agent subagent (the script is run BY the user inside Claude Code, so it has access to the harness — though admittedly only the model itself can invoke Agent, not a subprocess). At minimum, T-09 Phase A should run BEFORE the install.sh redeploy: invoke `/gate` on a single-skill manual edit (e.g., copy the §0 block into `~/.claude/skills/gate/SKILL.md` directly), observe behavior, then proceed to T-02 only if Phase A succeeds.
  - Where: T-00 procedure at plan lines 278-296; T-09 procedure step 1 at plan line 334 (install.sh runs first); stage-1 acceptance at plan line 375.
  - Suggestion: Either (a) reorder T-00 + T-09 Phase A to run BEFORE T-02 — manually edit ONE skill (e.g., `~/.claude/skills/gate/SKILL.md`) with the §0 block, run `/gate`, observe Phase A signal, only then proceed with the 12-file insertion via T-02; OR (b) make T-00 actually testable by writing a Python script that uses the Anthropic SDK to call Haiku directly and confirm round-trip — though this re-introduces the lesson 2026-04-25 set-u-rc-hang and lesson 2026-04-23 LLM-replay non-determinism cost concerns. Option (a) is cheaper and addresses the ordering. Update T-09 Phase A to specify "run BEFORE T-02" as the canonical de-risking ordering.

### Minor (improvement, use judgment)

- **MIN-1 — install.sh "no diff in this stage" claim conflicts with verify_subagent_dispatch.md deployment paragraph**
  - What: T-10 acceptance at plan line 240 says `no install.sh diff in this stage's commits`. But Notes at plan line 366 says "verify the .md template gets deployed alongside the .py script (if install.sh's script-deploy loop only matches .py, the .md goes alongside via a parallel copy line; if needed, add the copy line in T-10's inspection step rather than as a separate task)." The hedge "if needed" punts a potential install.sh edit to T-10 which is "inspection only" and acceptance "no install.sh diff." Either install.sh's script-deploy loop matches `*.md` already (in which case the hedge should be removed), or it doesn't (in which case the install.sh edit is real and should be its own task with its own acceptance). The plan should resolve this before /implement, not at T-10 inspection time when scope is supposed to be locked.
  - Suggestion: Add a 2-line plan check: `grep -n 'for script' dev-workflow/install.sh | head -5` to determine the loop's glob pattern. If `.md` is included, delete the hedge from Notes. If not, add a small T-10b task (or extend T-10 to include the install.sh edit) with explicit acceptance.

- **MIN-2 — D-04's "before any cost-ledger writes" rationale isn't fully delivered for skills with intro prose**
  - What: D-04 (plan line 250) justifies inserting §0 BEFORE every other H2 by saying "the model would have already read setup instructions and possibly started cost-ledger writes BEFORE deciding to dispatch." But for files with pre-H2 intro prose (e.g., `end_of_task/SKILL.md` lines 9-13 with **CRITICAL** and **IMPORTANT** directives, or `implement/SKILL.md` line 9 directive prose), the procedure step 5 (plan line 305) inserts §0 AFTER the intro prose. The intro prose for `end_of_task` includes "Fresh session recommended" — directive but no tool calls. The intro prose for `implement` says "You take a well-defined plan and turn it into working code." — descriptive. Neither triggers cost-ledger writes, but the model has already read 2-5 sentences of skill-specific framing before §0 fires. The cost-guardrail rationale is preserved (no tool calls before §0), but the "execute before anything else" framing in §0's heading is slightly weaker.
  - Suggestion: Either acknowledge in D-04 that "any pre-H2 intro prose is read before §0; this is acceptable because intro prose is descriptive (no tool calls)" — or move §0 BEFORE intro prose (which would tie to MAJ-1 critic round 1 about per-file anchor — solved cleanly if §0 is uniformly the FIRST line after the H1 + blank, with intro prose moved AFTER §0). Either way, document the choice. Current plan ambiguity is small but visible.

- **MIN-3 — T-00's value-add over a documented HITL procedure step is marginal**
  - What: Per lesson 2026-04-22 cost-discipline (cosmetic findings drive over-engineering), T-00 adds a 30-line stdlib Python script + a markdown template that the user fills in. The script does nothing the user couldn't do by reading T-09 Phase A's procedure directly. It's not load-bearing — the actual verification is T-09 Phase A. Keeping T-00 adds two new files (verify_subagent_dispatch.py + .md), one Tier 1 entry in CLAUDE.md (T-07), one cache update consideration, one test-suite collection-count adjustment. None of these is harmful, but each adds maintenance surface for marginal value over "the user reads T-09 Phase A and fills in observations in `manual-smoke-$(date +%Y-%m-%d).md`."
  - Suggestion: Consider folding T-00 into T-09 Phase A as a documentation step ("create `verify_subagent_dispatch.md` with these three sections: Procedure, Observed, Result; the template lives in T-09's procedure block of this plan, not in a separate script"). Saves two files, one Tier 1 entry, and one CLAUDE.md cross-reference. Counter-argument: the script is documentation that lives in the repo (not the plan), so future contributors find it. Use judgment.

- **MIN-4 — D-07 contains a typo "fileunder"**
  - What: D-07 at plan line 256: "moves verification to a one-shot user-run step at install time, with the result captured in a fileunder dev-workflow/scripts/verify_subagent_dispatch.md." Word-merge typo: "fileunder" should be "file under".
  - Suggestion: Fix typo.

- **MIN-5 — Cache write-through scope claim depends on cache state that may have shifted since planning**
  - What: Notes at plan line 364 says "`.workflow_artifacts/cache/dev-workflow/skills/` currently contains entries for `architect`, `critic`, and `triage`. Of these, only `triage` is in our 12-skill list." This was true at planning time. If the cache has been refreshed between planning and implementation (or another task added entries for, e.g., `gate` or `end_of_task`), more cache entries may need updating. The plan locks in a snapshot rather than a procedure.
  - Suggestion: Replace the static list with a procedure: "Before /implement starts, list `.workflow_artifacts/cache/dev-workflow/skills/` and intersect with the 12-skill list; update each intersected cache entry's `## Notes` section with the §0-self-dispatch line." This is the correct CLAUDE.md cache rule (b) wording — unconditional update for any modified source, not a hardcoded triage-only list.

### Nit

- **NIT-1 — "Quoin self-dispatch hard-cap reached at N=" abort message could include the skill name**
  - The abort message in T-01 sub-bullet (c) is `Quoin self-dispatch hard-cap reached at N=<N>. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.` Adding the skill name (`Quoin self-dispatch hard-cap reached at N=2 in /gate`) makes debugging easier when the user sees this in a chained orchestration. Optional.

## Round-1 issue status

Loop-detection check: NO round-1 issue title is repeated as the same root cause in this round-2 critique. CRIT-1's silent-dispatch concern reappears in MAJ-1 (NEW), but the root cause is different (round-1 = unverified harness; round-2 = self-inflicted by the CRIT-2 fix). Documenting this distinction so the orchestrator does NOT escalate as a stuck loop.

| Round-1 ID | Title | Round-2 status |
|---|---|---|
| CRIT-1 | Agent-tool model-param unverified | partially fixed (T-00 + D-08 fail-graceful path is real; T-00-as-template is weak; new MAJ-1 introduced by CRIT-2 fix) |
| CRIT-2 | Frontmatter-collision in test | fixed (slicer + distinctive token) — but introduced new MAJ-1 |
| CRIT-3 | Recursion-guard contract drift | fixed (bare-sentinel canonical, all sites aligned) |
| MAJ-1 | Insertion-site ambiguous | fixed (per-file anchor table) |
| MAJ-2 | Load-bearing rule collision | fixed (T-04 case g + T-09 Phase D) |
| MAJ-3 | Manual-smoke as sole production test | partially fixed (T-00 documentation generator; real verification still HITL post-install) |
| MAJ-4 | CLAUDE.md docs-only update needs test cross-reference | fixed (T-06 includes test-file refs + rebrand-update note) |
| MAJ-5 | SYNC-WARNING non-trivial diff | fixed (T-04 case h via difflib) |
| MAJ-6 | Byte-equality mitigation incomplete | fixed (T-01 negative-grep on §5.7.1 first-line literal) |
| MAJ-7 | Test redundancy + brittle ordering | fixed (T-04 case b rephrased; T-05 case g marked smoke) |
| MIN-1..MIN-4 | misc | fixed |
| MIN-5 (deferred) | install.sh per-install log | deferred-OK (D-08 runtime warning subsumes; revisit if scenario materializes — defensible rationale) |
| MIN-6 | File-count math | fixed (Stage-1 acceptance corrected to 18) |

## What's good

1. The CRIT-3 alignment to architecture's bare-sentinel canonical form is exemplary — D-02 explicitly documents the contract, T-04 case (e), T-05 case (d), and T-05 case (f) all assert the aligned contract, and the round-1 plan's drift is called out as the wrong path. This is what plan revision should look like.
2. D-08 (fail-graceful runtime safeguard) is a substantively new architectural protection wired to architecture I-01. It honors the lesson 2026-04-25 set-u-rc-hang philosophy of "make the failure mode observable, not silent." Good.
3. The per-file insertion-anchor table (T-02) is empirical, ordered, and assignable per-file — addressing MAJ-1 from round 1 with real per-file analysis (gate vs end_of_day vs triage all distinct entries).
4. T-04 case (h) automating the SYNC contract via `difflib` is a strong elevation of an acceptance-only check to a mechanical guarantee. Catches drift forever.
5. The new R-09 and R-10 risk rows are concrete, mitigation-paired, and rollback-paired — good risk-register hygiene.
6. The Revision history section enumerates each round-1 issue with the addressing change — making round-2 critique mechanical (this very critic ran in less time as a result). Good practice.
7. MIN-5 deferral rationale (D-08 runtime warning subsumes per-install log) is honest and defensible — not a hand-wave; the trade-off is documented.
8. T-09 Phase A's three-signal expectation tree (banner-and-sonnet-response / fail-graceful-warning / silent-no-op-STOP) explicitly enumerates the silent-failure case and gates merge on it. Stronger than round 1's eyeball-check.

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | good | All 10 round-1 issues addressed; new MAJ-1 was introduced by the CRIT-2 fix but is correctable. |
| Correctness | fair | MAJ-1 (deleted `model:` parameter) is a real production-breaking bug as currently specified; MIN-1 (install.sh diff hedge) is unresolved scope ambiguity. |
| Integration safety | good | T-04 case (g) and T-09 Phase D address /run-orchestrated dispatch into /implement — load-bearing rule preservation is now under test. |
| Risk coverage | good | R-09 and R-10 are concrete; D-08 is a new safety net. |
| Testability | fair | The structural tests are deterministic and well-scoped; but T-04 case (c) (asserting `dispatched-tier: model: "<value>"` substring) will PASS even when MAJ-1's deleted-parameter bug ships. The test was designed to catch frontmatter collision, not to verify the dispatch contract is well-formed. |
| Implementability | good | Per-file anchor table makes T-02 mechanical. Procedures are step-by-step. |
| De-risking | fair | T-00 is a template generator, not a verifier; T-09 Phase A is post-implement post-install — pre-merge de-risking value is weak. MAJ-2 suggests a reordering (Phase A on a single-skill manual edit, BEFORE T-02). |
