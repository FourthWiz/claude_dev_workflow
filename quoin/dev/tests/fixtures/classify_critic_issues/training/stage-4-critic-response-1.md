---
task: quoin-foundation
stage: 4
stage_name: architect-critic-phase
phase: critic
date: 2026-04-26
model: claude-opus-4-7
class: A
round: 1
target: current-plan.md
---

## Verdict: REVISE

## Summary

The plan is well-structured, accurately diagnoses the round-detection bug at critic/SKILL.md L14/L51, and correctly leverages stage-3 deliverables (path_resolve.py, the task-root corollary). The cost guard and recursive-self-critique guard are both hard mechanisms (AskUserQuestion + string-match grep), not theater. However, three issues block /implement: (1) the cross-skill permission gap from lesson 2026-04-13 — critic/SKILL.md's "Critical rule: Fresh context" enumerates only `/thorough_plan` as the spawner, and stage 4 introduces `/architect` as a new spawner without the matching exception clause; (2) the recursive-self-critique grep scope (the parent plan's open question on broadening) is dangerously narrow and reproduces exactly the audit-grep narrowness pattern that cost stage-3 multiple critic rounds; (3) the loop detection code path is dead in normal mode (max_rounds=2 means the round-2 branch only fires on the LAST round). Several MAJOR gaps around `/run` orchestration, single-stage invocation, and explicit Phase 4 dispatch-model assertions.

## Issues

### Critical (blocks implementation)

- **CRIT-1 — Cross-skill permission gap: critic/SKILL.md "Critical rule: Fresh context" never names /architect as a spawner**
  - What: The plan modifies critic/SKILL.md L14, L51, L122 to handle architecture-critic-N.md output paths and round detection, but does NOT update the "Critical rule: Fresh context" block at critic/SKILL.md L25-27, which currently reads: "When invoked as part of `/thorough_plan`, you MUST run in a fresh agent session." Stage 4 introduces `/architect` Phase 4 as a NEW spawner of `/critic`. Per lesson 2026-04-13 ("when one skill changes invocation rules of another, update the *target* skill's SKILL.md too — the subagent reads its own SKILL.md, not CLAUDE.md"), the target skill must explicitly enumerate the new spawner.
  - Why it matters: The /critic subagent spawned by /architect Phase 4 reads its own SKILL.md on bootstrap. The current L25-27 wording could be interpreted by the subagent as "fresh context only required for /thorough_plan invocations" — a subtle-but-real semantic gap. More importantly, lesson 2026-04-14 (task-cost-tracking) explicitly notes that "/critic should explicitly check all files that the newly-added skill (or orchestrator) references by name — especially for permission/invocation exception clauses." This is the same class of bug.
  - Where: critic/SKILL.md L25-27 (target file); the parent plan's task two (caller-side change is documented but target-side update is missing).
  - Suggestion: Add a sub-task (call it task two-b, or fold into task two) that updates critic/SKILL.md L25-27 to read: "When invoked as part of `/thorough_plan` OR by `/architect` Phase 4, you MUST run in a fresh agent session." Acceptance: a grep for the substrings "thorough_plan.*OR.*architect" or "architect.*Phase 4" in dev-workflow/skills/critic/SKILL.md returns at least one hit at the L25-27 region.

- **CRIT-2 — Recursive-self-critique grep scope is dangerously narrow; reproduces stage-3 audit-grep pattern**
  - What: The parent plan's task four-c and decision six specify grep against architecture.md body for literal strings `architect/SKILL.md` and `critic/SKILL.md` ONLY. The parent plan's first open question is OPEN about broadening. But this stage-4 task ITSELF references `dev-workflow/skills/architect/SKILL.md` (with the dev-workflow/ prefix), `~/.claude/skills/architect/SKILL.md` (the deployed copy), and `architect/SKILL.md` (bare form) interchangeably across architecture.md, current-plan.md, and lesson entries.
  - Why it matters: Per the stage-3 round-3/round-4 critic battery (referenced in the current-plan task header context), "audit-grep narrowness" was a class-level pattern that cost multiple revise rounds. The narrow scope here means a future architecture.md that says only `dev-workflow/skills/architect/SKILL.md` (the natural form when describing a source path) would FAIL to trigger the recursive guard — exactly the case where the parent plan's recursive-self-critique-risk mitigation is most needed. False negatives here mean uncapped Opus spend (lesson 2026-04-22 anti-target).
  - Where: The parent plan's task four-c ("grep the in-progress architecture.md body for literal strings `architect/SKILL.md` or `critic/SKILL.md`"), decision six, first open question.
  - Suggestion: Resolve the open question NOW (do not defer to user during /implement) — broaden the grep alternation to: `architect/SKILL.md|critic/SKILL.md|dev-workflow/skills/(architect|critic)/SKILL.md|~/\.claude/skills/(architect|critic)/SKILL.md`. False positives on docs-only refs (the open-question worry) are a feature, not a bug — recursive-self-critique cost is the explicit anti-target. Acceptance: extend the parent plan's task nine fixture to include both bare and prefixed forms; assert guard fires on each.

- **CRIT-3 — Loop detection code path is DEAD in normal mode (max_rounds=2)**
  - What: The parent plan's task four-d and the Procedures pseudocode (L235-241) say loop detection runs "if round greater-or-equal to 2". With max_rounds=2 default (the parent plan's decision two), round 2 IS the last round — when loop detection would fire, the loop is about to exit on max-rounds anyway. Loop detection only does meaningful work in strict mode (max_rounds=4).
  - Why it matters: The parent plan's task four acceptance criterion lists 4 grep hits expected (max_rounds, cost guard, recursive-self-critique, loop detection); the prose will be present but the runtime behavior is a no-op in nearly every normal-mode invocation. Worse, a future maintainer reading the SKILL.md sees loop detection "implemented" and won't add it for the round-1 to round-2 transition where it actually matters in normal mode (e.g., "round 2 critic flags same CRITICAL title from round 1's REVISE, escalate to user before re-running synthesis"). Currently with max=2 there is no inter-round revision attempted on loop detection — the loop just exits.
  - Where: The parent plan's task four-d, Procedures block L235-241.
  - Suggestion: Either (a) move loop detection to fire on round-1 critic output BEFORE re-synthesis (compare round 1 CRIT/MAJ titles against any prior architecture-critic from a previous /architect invocation if one exists — narrow but correct), OR (b) explicitly document "loop detection is a strict-mode-only feature; normal mode relies on max_rounds=2 hard cap" and remove the dead "if round greater-or-equal 2" branch from the normal-mode pseudocode. Either way, do not ship pseudocode that pretends to do something it does not.

### Major (significant gap, should address)

- **MAJ-1 — /run interaction with Phase 4 is unaddressed; cost-ledger verification at run/SKILL.md:98 may misfire**
  - What: `/run` Phase 2 (run/SKILL.md L91-98) spawns `/architect` as a subagent and at L98 verifies the cost ledger has a new entry for the `architect` phase. Stage 4's Phase 4 introduces 1-2 NEW critic-phase rows (one per round) inside the architect subagent's session. The plan does NOT update `/run` SKILL.md — neither to expect the new rows nor to validate them. Run-orchestrator phase summary at L100-115 (Checkpoint A) summarizes architecture but says nothing about critic verdict.
  - Why it matters: After stage-4 lands, every `/run` invocation that goes through `/architect` will produce architecture plus N critic-rows with no acknowledgment in the run UI. Worse, if Phase 4 hits the cost-guard pause-for-user (the parent plan's task four-b AskUserQuestion), `/run`'s subagent dispatch may stall waiting for input that the user is not seeing prominently. /run's checkpoint logic does not currently surface "Phase 4 paused for cost-guard confirmation". This is a UX regression.
  - Where: `dev-workflow/skills/run/SKILL.md` L91-115 (Phase 2 — Architect plus Checkpoint A); the parent plan does not list run/SKILL.md as an affected file.
  - Suggestion: Add a sub-task (call it task seven-b or new task twelve) that updates run/SKILL.md Phase 2 to: (a) document that /architect now includes Phase 4; (b) update Checkpoint A summary to surface critic verdict if Phase 4 ran; (c) add a one-line note that the cost-guard prompt may pause subagent dispatch and the user should watch for it. Acceptance: a grep for "Phase 4" or "architecture-critic" in dev-workflow/skills/run/SKILL.md returns at least 2 hits.

- **MAJ-2 — Phase 4 dispatch-model assertion (model opus) has no acceptance grep**
  - What: The parent plan's task four acceptance lists 4 grep hits but does not require an explicit grep for the model-opus directive inside the new Phase 4 section. The Procedures pseudocode at L227 says spawn_critic_subagent with `model="opus"`, but pseudocode in Procedures may not survive translation into SKILL.md prose. Per critic/SKILL.md L21-23 plus CLAUDE.md "/critic always Opus, never tiered" non-negotiable rule, the Phase 4 spawn site MUST explicitly carry the model assertion.
  - Why it matters: Without an acceptance grep, the parent plan's task one body could land with the model spec missing or buried. /architect's parent session could be on Sonnet (e.g., if user manually downgraded), and a missing explicit model-opus directive would silently degrade the critic to inherit-parent-model. This is exactly the model-dispatch defect that stage-1 fixed for cheap-tier skills, in reverse. Lesson 2026-04-22 (the 140-dollar incident) was driven partly by recursive Opus critic; this is the inverse risk (a non-Opus critic that should be Opus).
  - Where: The parent plan's task four acceptance criteria (L78-82).
  - Suggestion: Add acceptance criterion: a grep for the regex matching `model[\s:=]+["']?opus` against dev-workflow/skills/architect/SKILL.md returns at least one hit inside the new Phase 4 section (verify by line range awk between Phase 4 heading and Output format heading). Also add a sentence to the parent plan's task one body content guidance: Phase 4 spawn instruction MUST include the literal "model: opus" directive for the critic subagent.

- **MAJ-3 — Single-stage /architect invocation is not explicitly handled in the plan**
  - What: The plan assumes stage-4 context (multi-stage architect runs). But `/architect` can be invoked on single-stage tasks too (no stage qualifier). Procedures pseudocode does not branch on this. Where does architecture-critic-N.md land? Per the parent plan's decision three corollary, ALWAYS at task root regardless of stage layout — but the plan's prose only states this for multi-stage tasks. The parent plan's task four acceptance for max_rounds parsing ("scan invocation for max_rounds: N token") does not specify behavior when there is no stage qualifier in the invocation.
  - Why it matters: A user running `/architect <task>` (no stage) on a single-stage task would still trigger Phase 4. If max_rounds parsing or recursive-guard logic depends on stage-qualifier presence, single-stage runs may behave differently than multi-stage. /architect is most commonly invoked on single-stage tasks (initial architecture before stage decomposition). This is the more frequent case, not the edge case.
  - Where: The parent plan's Procedures block L206-247 (no single-stage branch); decision three (only addresses multi-stage); task four acceptance.
  - Suggestion: Add an explicit single-stage clause to decision three or the Procedures preamble: "Phase 4 runs identically for single-stage and multi-stage tasks. architecture-critic-N.md ALWAYS lands at .workflow_artifacts/TASK_NAME/architecture-critic-N.md (task root, never stage subfolder), per the decision-three corollary already encoded in architect/SKILL.md L304." Update the parent plan's task nine fixture to cover BOTH single-stage and multi-stage cases. Add task ten acceptance: confirm fixture-task path placement matches the corollary regardless of architecture.md having a "Stage decomposition" section or not.

- **MAJ-4 — format-kit.sections.json claim is correct but the diff-check acceptance is too narrow**
  - What: The parent plan's task six acceptance (a) verifies architecture-critic match-paths globs are in match_paths — VERIFIED CORRECT at format-kit.sections.json L83. Acceptance (b) requires a diff between the source and deployed copies to be empty. However, task six does NOT verify that the critic-response artifact-type's required_sections and allowed_sections accommodate architecture-critic-N.md content (heading-line-form `## Verdict: PASS` per lesson 2026-04-25 V-07 prefix-match relaxation). If a future schema change drops the `## Verdict: PASS` and `## Verdict: REVISE` heading-line-form alternates from allowed_sections (currently L93-95), every architecture-critic-N.md write would fail V-02.
  - Why it matters: Task six says "no edit expected" — but if a downstream architecture-format change (e.g., a future stage 5 task) silently drops the heading-line-form alternates, stage 4's Phase 4 critic writes will start failing post-merge. The plan's task six only catches gross removal of architecture-critic match_paths, not subtler allowed_sections regressions.
  - Where: The parent plan's task six (L95-102), decision four.
  - Suggestion: Extend task six acceptance to include a Python one-liner that loads format-kit.sections.json, asserts that both heading-line-form alternates are in the critic-response allowed_sections list, and prints OK. Add a regression note in task six prose: "If allowed_sections drops heading-line-form alternates in a future change, stage 4's Phase 4 critic writes break."

- **MAJ-5 — Task nine fixture smoke acceptance does not specify a deterministic PASS criterion**
  - What: The parent plan's task nine acceptance bullet 1 says "Test runner exits 0" but the test runner is described as "structured grep plus manual prompt-replay, mirroring the stage-1 verify-subagent-dispatch pilot pattern" — there is no actual test runner script defined. The fixture is a markdown file; the "test" is hand-filled per stage-1 pattern. "Exits 0" is meaningless for a hand-filled markdown record.
  - Why it matters: Lesson 2026-04-23 (LLM-replay non-determinism) explicitly warns against tests with non-deterministic PASS criteria. The actual structure is OK (it mirrors the stage-3 grep-battery / stage-1 verify-subagent-dispatch pattern), but the acceptance prose gives a false impression of automation. Reviewers and gate skills will look for an exit-0 signal that does not exist.
  - Where: The parent plan's task nine acceptance bullets 1 and 3.
  - Suggestion: Rephrase task nine acceptance bullets to mirror stage-3 task nine grep-battery: "Test runner is dev-workflow/scripts/tests/test_architect_phase_4_smoke.md, a hand-filled grep battery and prompt-replay record. Acceptance is: (a) all grep checks documented in the file return the expected counts (recorded in the markdown); (b) recursive-self-critique guard verified by string-match against fixture body; (c) cost-guard string verified verbatim including em-dash (use grep dash-F for fixed-string match to assert exact ASCII)." Drop "exits 0" — there is no script.

### Minor (improvement, use judgment)

- **MIN-1 — Convergence rules omit the "REVISE in normal mode after max-rounds" nuance**
  - Suggestion: Architecture L189-192 distinguishes "max-rounds reached AND verdict equals REVISE in normal mode, STOP and inform user (do not loop)" from "max-rounds reached AND verdict equals PASS, done". The parent plan's task five collapses these into one bullet. Add a sentence: "On normal-mode max-rounds-reached with verdict equals REVISE, the Phase 4 body MUST emit the user-visible message: 'Architecture critic reached max_rounds=N with REVISE verdict, remaining concerns enumerated below. Architecture is final-as-is. To force more rounds, re-invoke with strict: or max_rounds: 4.'"

- **MIN-2 — CLAUDE.md Canonical flow section line range is approximate**
  - Suggestion: The parent plan's task seven says "Add the footnote bullet under Canonical flow section in dev-workflow/CLAUDE.md lines 86-94 region". Verified: Canonical flow header is at L87 (not L86); the flow string itself is at L91. Use heading-anchor reference instead of line numbers (mirrors the parent plan's R-B mitigation: "Use anchor-based references, NOT line numbers, in all new prose").

- **MIN-3 — Task eleven install.sh check is genuinely a no-op but should reference stage-3 precedent**
  - Suggestion: Task eleven says "post-implement bash install.sh exits 0; deployed architect SKILL.md contains the new Phase 4 section". This is good. Add a one-line cross-reference to stage-3 task six (which used the same install.sh deploy-then-grep pattern for path_resolve.py) so the test pattern is traceable.

- **MIN-4 — The three open questions are OPEN; should be RESOLVED before /implement entry**
  - Suggestion: The second open question (manual prompt-replay vs mocking) is already resolved by decision seven (manual replay). The third open question (fixture name "phase-4-smoke") needs user confirmation to avoid in-flight collision; fold into pre-/implement gate. The first open question (grep scope) is escalated to CRIT-2 above. After CRIT-2 is addressed, the first open question becomes resolved.

- **MIN-5 — Risk R-N (format-kit schema upstream change) duplicates R-G**
  - Suggestion: R-N at L199 ("format-kit.sections.json schema changes upstream") substantially overlaps R-G ("Deployed format-kit.sections.json drifts from source"). Consider merging into a single risk with two mitigations, or rename R-N to be specifically about match_paths or allowed_sections key structure changes (see MAJ-4 above for the more specific case).

## What's good

- **Accurate bug diagnosis** at critic/SKILL.md L14/L51 — verified by direct file read; the round-detection regex genuinely does not match `architecture-critic-*.md` files. The parent plan's task three fix is necessary AND correctly scoped.
- **Cost guard is a hard mechanism** — uses AskUserQuestion (verified pause-on-user), not a printed notice. The parent plan's task four-b explicitly specifies the verbatim string with em-dash, mitigating R-E (string drift).
- **Same-session re-synthesis vs fresh-critic-subagent distinction** is correctly drawn (decision three). Cites architecture L186-187 verbatim. Avoids the double-cost trap of fresh-session re-synthesis.
- **L304 architect/SKILL.md HTML comment is correctly leveraged** — the decision-three corollary that architecture-critic-N.md stays at task root regardless of stage layout is already encoded; the plan inherits this pre-resolution rather than introducing a new path.
- **format-kit.sections.json L83 alignment is verified correct** — both architecture-critic glob forms are in match_paths; task six is a true no-op verification.
- **Stage-3 deliverable (path_resolve.py) is leveraged** — the decision-three corollary plus the L304 comment plus critic/SKILL.md L122 branch all compose cleanly. Stage 4 makes minimal new path-resolution surface area.
- **Cache write-through no-op task correctly identifies that Phase 4 produces workflow artifacts, not source files** — no cache obligation. Cleanly closed.
- **Risk register is comprehensive** — 14 risks cover the cost-runaway/recursive-self-critique anti-target plus stage-specific hazards. R-M (subagent context bleed) explicitly cites Task-tool semantics.
- **Lesson 2026-04-22 anti-target is named explicitly** in decision two — default max_rounds=2 is THE direct fix for the 140-dollar incident.

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | fair | CRIT-1 (cross-skill permission gap), MAJ-1 (/run integration), MAJ-3 (single-stage handling) — meaningful surfaces unaddressed. |
| Correctness | good | Bug diagnoses verified; L83 format-kit claim verified; L304 leverage correct; L201/L203 anchor verified. |
| Integration safety | fair | MAJ-1 (/run UX regression), MAJ-2 (model-dispatch grep), CRIT-1 (target SKILL.md update). |
| Risk coverage | good | 14 risks; cost-runaway and recursive-self-critique explicit anti-targets named; rollbacks per-risk. MIN-5 noted. |
| Testability | fair | MAJ-5 (task nine acceptance prose misleading); task ten properly bounded by decision eight; task nine needs deterministic PASS criteria. |
| Implementability | good | 11 tasks with clear anchors, body content guidance, risks; pseudocode in Procedures aids /implement. |
| De-risking | fair | Cost guard plus recursive-self-critique guard are hard. CRIT-2 (grep scope narrow) and CRIT-3 (loop detection dead in normal mode) reduce de-risking effectiveness. |
