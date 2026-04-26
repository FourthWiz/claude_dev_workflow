---
task: quoin-foundation / stage-1
phase: plan
date: 2026-04-25
model: claude-opus-4-7
class: B
profile: large
revision: 3
---
## For human

**Current status:** Stage 1 plan is ready for implementation; it adds a self-dispatch preamble (§0 block) to 12 cheap-tier skills to route invocations to their declared model tier when called from a more expensive tier, with a recursion guard and fail-graceful fallback.

**Biggest open risk:** The harness may not support the `model:` parameter in the Agent subagent-spawn tool, causing dispatch to silently no-op and burn tokens at the parent tier instead of the declared tier; this is caught by T-00 pilot verification on a single skill before T-02 touches the remaining 11.

**What's needed to make progress:** Run T-00 (pilot verification on `triage/SKILL.md`) to confirm the harness supports model-parameter dispatch; only after T-00 passes with result `verified` should T-02 proceed to batch-insert the §0 block into the other 11 skills.

**What comes next:** After T-02 completes, run the full test suite (T-08) to confirm structural consistency, then perform manual smoke testing (T-09) on the deployed skills to verify all four dispatch phases (normal dispatch, manual override, recursion abort, and /run-orchestration lineage preservation) work as designed.

## Convergence Summary

- Task profile: Large (strict mode, all-Opus)
- Rounds: 3
- Final verdict: PASS
- Round 1: 3 CRITICAL, 7 MAJOR, 6 MINOR — addressed harness model-param unverified, frontmatter test collision, sentinel-form drift
- Round 2: 0 CRITICAL, 2 MAJOR, 5 MINOR, 1 NIT — addressed model-param-as-actual-arg regression, T-00 restructured into HITL pilot
- Round 3: 0 CRITICAL, 0 MAJOR, 2 MINOR, 1 NIT (advisory) — PASS
- Key revisions across rounds: dispatch contract restored to architecture-canonical bare sentinel; T-00 moved before T-02 as a single-skill pilot gate; structural test slicer prevents YAML frontmatter false-pass
- Remaining concerns: 2 MINOR + 1 NIT advisory items not addressed (cost-discipline cutoff per lesson 2026-04-22); D-08 fail-graceful runtime safeguard provides defense-in-depth for any harness behavior we cannot pre-verify

## State

```yaml
task: quoin-foundation
stage: stage-1
title: Self-dispatch preamble for 12 cheap-tier SKILL.md files
profile: large
model: claude-opus-4-7
session_uuid: 07d7193e-32a8-4aca-993b-0d522d94ce9f
parent_architecture: .workflow_artifacts/quoin-foundation/architecture.md
target_branch: feat/quoin-stage-1
prerequisite_stages: none
dependent_stages: stage-5 (S-05 native Haiku summarizer depends on Agent-tool dispatch validated here)
revision_round: 3
```

## Tasks

1. ✓ T-00: Pilot-verify subagent dispatch on a SINGLE skill (HITL; PRECEDES T-02; STOP-and-rewrite gate per D-07)
   - rationale (per round-2 MAJ-2): the round-2 plan made T-00 a doc-template generator that ran AFTER `bash install.sh` deployed all 12 edits; if dispatch silently no-op'd in production, the user had to revert 12 files. Pre-merge de-risking value was zero. This task is now restructured: T-00 verifies dispatch on ONE skill before T-02 touches the other 11. If T-00 fails, STOP — do not proceed with T-02.
   - pilot skill: `dev-workflow/skills/triage/SKILL.md` — chosen b/c (a) declared `model: haiku` (smallest tier, biggest dispatch signal — opus parent dispatching to haiku child is unmistakable in cost ledger), (b) no intro prose between H1 and first H2 (cleanest insertion site per T-02 anchor table row 4), (c) not heavily wired into other skills (rollback risk minimal if pilot fails).
   - procedure (HITL — runs as part of stage-1 implementation, BEFORE T-02 batch insertion):
     a. Author the §0 fixture per T-01 first (T-01 is allowed to run before T-00; the fixture is the source of truth the pilot insertion uses).
     b. Manually insert §0 into ONLY `dev-workflow/skills/triage/SKILL.md` per T-02's per-file procedure for the triage row. Do NOT touch the other 11 SKILL.md files yet.
     c. Run `bash install.sh` to deploy the modified `triage/SKILL.md` to `~/.claude/skills/triage/SKILL.md`.
     d. Open Claude Code on Opus 1M (verify with `/model` or harness banner "powered by the model named X").
     e. Type `/triage what should I run next?` (a benign /triage invocation that exercises §0 dispatch).
     f. Observe the response for ONE of the three signals defined in T-09 Phase A:
        (i) "Spawning subagent" banner OR equivalent model-handoff signal AND the cost-ledger row for the triage subagent records `claude-haiku` (not opus) in the model column → DISPATCH VERIFIED → T-00 PASS, proceed to T-02.
        (ii) Fail-graceful warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` followed by triage's normal output on Opus → harness does not support model parameter → T-00 FAIL → STOP (do NOT proceed to T-02). Per D-07: stage-1 is rewritten before any further insertion.
        (iii) NEITHER signal visible AND the response is generated on Opus (cost-ledger row records opus) → SILENT NO-OP → T-00 FAIL → STOP. This is the C1 worst case the fail-graceful path was designed to surface; if it surfaces here, the §0 prose itself is mis-specified — revisit T-01.
     g. Record observation in `dev-workflow/scripts/verify_subagent_dispatch.md` (template generated by sub-step h below). Specifically: which signal (i/ii/iii) was visible, the model column observed in the cost-ledger row for the triage child, the harness banner string read in step d, and any tool-error message from the dispatch attempt.
     h. Generate the verification template at `dev-workflow/scripts/verify_subagent_dispatch.md` via a small companion script `dev-workflow/scripts/verify_subagent_dispatch.py` (~30 lines, pure-stdlib; runs only when invoked, never in CI; exit 0 always — it's a documentation generator). Sections: `## Procedure` (the steps a–g above, as documentation for future re-verification on harness updates), `## Observed` (filled in by user during step g), `## Result` (`verified` | `failed` | `untested` — user picks one).
     i. If T-00 result is `failed`: capture the exact harness banner, the dispatch tool's error message (if any), the cost-ledger row for the child, and any alternative mechanism tried (Task tool? Skill tool? bare Agent invocation?). Stage-1 STOP-and-rewrite per D-07 — the architecture's §0 dispatch mechanism needs replanning before T-02 can run.
   - acceptance:
     - `dev-workflow/scripts/verify_subagent_dispatch.py` exists; `python3 dev-workflow/scripts/verify_subagent_dispatch.py` exits 0; produces `dev-workflow/scripts/verify_subagent_dispatch.md` w/ the three sections
     - `triage/SKILL.md` has §0 inserted (manually, per T-02 row 4 procedure)
     - `~/.claude/skills/triage/SKILL.md` reflects the insertion after `bash install.sh`
     - `verify_subagent_dispatch.md` `## Result` section is `verified` (NOT `failed` or `untested`) BEFORE T-02 runs on the remaining 11 files
     - both new files (`.py` + `.md`) checked into git (`git status --short` per lesson 2026-04-23 gitignored-parent-dirs)
   - design choice (per D-07 + MAJ-2 fix): pre-merge live-LLM dispatch verification on a single pilot skill catches the silent-failure mode at the cost of one Opus→Haiku round-trip (~$0.05) — vastly cheaper than the round-2 plan's "edit 12 files, install, then discover" path which required full revert if dispatch failed. The script-plus-template-plus-pilot-observation pattern preserves the lesson 2026-04-23 LLM-replay non-determinism principle (no automated CI dispatch test) while moving verification to the earliest possible point in the implementation timeline.

2. ✓ T-01: Author the frozen §0 preamble template fixture (allowed to run before T-00; T-00 reads this fixture)
   - file: `dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md`
   - content: the exact §0 preamble text (heading `## §0 Model dispatch (FIRST STEP — execute before anything else)` through the closing line that hands off to §1) — model the wording on architecture.md "Self-dispatch preamble (item #1)" §0 block (lines 64–88 of `.workflow_artifacts/quoin-foundation/architecture.md`).
   - canonical sentinel-form contract (per architecture I-02 and per CRIT-3 fix; ALIGNED with architecture.md, not the round-1 plan's drift):
     * **Bare `[no-redispatch]` is the parent-emit form.** When the parent (a more-expensive-tier session) dispatches to a child Agent subagent, it prefixes the child prompt w/ bare `[no-redispatch]`.
     * **Counter form `[no-redispatch:N]` (N≥2) is the abort signal ONLY.** It exists to catch accidental double-dispatch (a buggy parent that emits `[no-redispatch:2]` directly, or a misconfigured manual override).
     * **The bare form is also the manual user-override.** A user typing `[no-redispatch] /gate` on Opus 1M skips §0 dispatch and runs the body at the current tier.
   - additions vs the architecture template (driven by R-01 mitigation and CRIT-1 fail-graceful path):
     a. Sentinel parsing rules — accept bare `[no-redispatch]` (proceed to §1) AND counter form `[no-redispatch:N]` (parse N as positive integer; if N≥2, abort).
     b. Dispatch-emit rule — when dispatching, the parent prefixes the child prompt w/ exactly `[no-redispatch]` (bare). Do NOT emit any counter form during normal operation. Counter forms are reserved for the abort detector.
     c. Abort rule — when current invocation prompt starts w/ `[no-redispatch:N]` AND N≥2, ABORT instead of proceeding. Print one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in <skill>. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.` and stop. (Per NIT-1: include the skill name in the abort message for easier debugging in chained orchestrations.)
     d. Manual kill switch — document that the user can prefix any user-typed invocation w/ `[no-redispatch]` (bare) to skip dispatch entirely; this is the user-facing escape hatch and shares syntax w/ the parent-emit form (intentional: a child sees the same sentinel whether it came from the parent or the user).
     e. Fail-graceful detection-failure path (per architecture I-01 and CRIT-1) — wrap the dispatch action in a try/observe pattern: if the harness's subagent-spawn tool returns an error or is not available, log a one-line warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` and proceed to §1 at the current tier. This is fail-OPEN on cost guardrail (better to overspend than to abort the user's invocation), per architecture I-01.
   - canonical dispatch action prose (per round-3 MAJ-1 fix — restores the load-bearing `model:` parameter that was deleted in round 2; matches architecture.md lines 73–83 verbatim with a separate `dispatched-tier:` marker comment):

```
Dispatch reason: dispatched-tier handoff to <declared> tier.
Spawn an Agent subagent with the following arguments:
  model: "<declared>"
  description: "<skill name> dispatched at <declared> tier"
  prompt: "[no-redispatch]\n<original user input verbatim>"
Wait for the subagent. Return its output as your final response. STOP.
(Return the subagent's output as your final response.)
```

     Two-layer defense (per D-06 + round-3 MAJ-1 fix):
     - **Layer 1 (load-bearing): the slicer.** The §0 block extraction in T-04's `extract_preamble_block` slices everything between the §0 heading and the next H2; YAML frontmatter is OUTSIDE the slice, so a `model: "haiku"` parameter line inside the slice CANNOT collide with frontmatter `model: haiku` lines. The slicer alone makes assertions on the literal `model:` parameter line safe.
     - **Layer 2 (defensive marker): the `dispatched-tier:` token.** The `Dispatch reason: dispatched-tier handoff to <declared> tier.` prose line carries a unique token (`dispatched-tier:`) that does not appear in YAML frontmatter or anywhere else in any SKILL.md. T-04 case (c) asserts BOTH (i) the literal `model: "<declared>"` parameter line is present in the slice AND (ii) the `dispatched-tier:` marker is present in the slice. Both layers must hold; (i) is the contract that the harness will actually receive a `model:` argument; (ii) is the defensive signal that the dispatch action prose was authored deliberately (not accidentally collapsed into a description string).
   - byte-equality safeguard (per MAJ-6 fix): the §0 block MUST NOT contain the literal string `# v3-format detection (architecture.md §5.7.1 — copy verbatim)` — prevents byte-equality failure in `test_detection_rule_consistency.py` first-line uniqueness check.
   - acceptance:
     - file exists at `dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md`
     - first line is exactly `## §0 Model dispatch (FIRST STEP — execute before anything else)`
     - file contains the literal substrings `[no-redispatch]`, `[no-redispatch:N]`, `Quoin self-dispatch hard-cap reached at N=`, `STOP.`, `dispatched-tier:`, `model: "<declared>"` (the literal parameter form including the angle-bracket placeholder; substitution happens at T-02 insert time), and `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
     - file does NOT contain the literal string `# v3-format detection (architecture.md §5.7.1 — copy verbatim)` (one-line negative-grep assertion per MAJ-6)
     - file ends with a hand-off line that begins `Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1`
     - file is checked into git (`dev-workflow/scripts/tests/fixtures/` directory is already tracked — verify w/ `git status --short` per lesson 2026-04-23)

3. ✓ T-02: Insert the §0 preamble verbatim into the remaining 11 cheap-tier SKILL.md files (PRECEDED by T-00 pilot pass; STOP if T-00 failed)
   - **execution gate (per round-3 MAJ-2 fix):** T-02 MUST NOT begin until T-00's `verify_subagent_dispatch.md` `## Result` section reads `verified`. If T-00 result is `failed` or `untested`, /implement STOPS — stage-1 is rewritten before any T-02 work.
   - target files: `triage/SKILL.md` was already modified in T-00 (pilot); the remaining 11 files are processed in T-02:
     1. `dev-workflow/skills/gate/SKILL.md` (declared sonnet)
     2. `dev-workflow/skills/end_of_day/SKILL.md` (declared haiku)
     3. `dev-workflow/skills/start_of_day/SKILL.md` (declared haiku)
     4. `dev-workflow/skills/capture_insight/SKILL.md` (declared haiku)
     5. `dev-workflow/skills/cost_snapshot/SKILL.md` (declared haiku)
     6. `dev-workflow/skills/weekly_review/SKILL.md` (declared haiku)
     7. `dev-workflow/skills/end_of_task/SKILL.md` (declared sonnet)
     8. `dev-workflow/skills/implement/SKILL.md` (declared sonnet)
     9. `dev-workflow/skills/rollback/SKILL.md` (declared sonnet)
     10. `dev-workflow/skills/expand/SKILL.md` (declared sonnet)
     11. `dev-workflow/skills/revise-fast/SKILL.md` (declared sonnet)
   - per-file insertion-anchor table (per MAJ-1 fix — surveyed empirically; a couple of entries may need anchor adjustment during /implement if files have shifted, in which case fall back to the procedure step 6 fallback):

   | # | file (in order; T-00 pilot row repeated for reference) | declared tier | first body H2 (current) | insert-anchor `old_string` strategy |
   |---|-----------------|---------------|--------------------------|--------------------------------------|
   | pilot | triage/SKILL.md (done in T-00) | haiku | `## Summary` | H1 `# Triage — Prompt-to-Skill Router` + first H2 directly (no intro prose); insert §0 between H1 and first H2 |
   | 1 | gate/SKILL.md | sonnet | `## Session bootstrap` | H1 `# Gate` + 2 lines of "You are a quality gate..." prose + first H2 `## Session bootstrap` (file has prose between H1 and first H2; insert §0 BEFORE the prose to match D-04 first-step rule) |
   | 2 | end_of_day/SKILL.md | haiku | `## How sessions and daily caches work` | H1 `# End of Day` + intro prose paragraph + first H2; insert §0 BEFORE the intro prose |
   | 3 | start_of_day/SKILL.md | haiku | `## Session bootstrap` | H1 `# Start of Day` + intro prose + first H2; insert §0 BEFORE intro prose |
   | 4 | capture_insight/SKILL.md | haiku | `## Session bootstrap` | H1 + intro + first H2; insert §0 BEFORE intro |
   | 5 | cost_snapshot/SKILL.md | haiku | `## Session bootstrap` | H1 + intro + first H2; insert §0 BEFORE intro |
   | 6 | weekly_review/SKILL.md | haiku | `## Process` | H1 + intro + first H2; insert §0 BEFORE intro |
   | 7 | end_of_task/SKILL.md | sonnet | `## When to use` | H1 + intro w/ **CRITICAL**/**IMPORTANT** prose + first H2; insert §0 BEFORE intro |
   | 8 | implement/SKILL.md | sonnet | `## Explicit invocation only` | H1 + intro + first H2 (which is load-bearing per MAJ-2); insert §0 BEFORE intro AND verify w/ T-04 case (g) below that the load-bearing rule is preserved |
   | 9 | rollback/SKILL.md | sonnet | `## Session bootstrap` (verify) | H1 + intro + first H2 |
   | 10 | expand/SKILL.md | sonnet | `## Hardcoded Tier 1 path list` | H1 + intro + first H2 (load-bearing per MAJ-2); insert §0 BEFORE intro AND verify w/ T-04 case (g) |
   | 11 | revise-fast/SKILL.md | sonnet | (after SYNC WARNING block + frontmatter + H1 `# Revise`) | special — insertion goes AFTER the SYNC WARNING comment block (which precedes frontmatter); precise anchor: H1 `# Revise` line + the next 5 chars of the existing first body line |

   - insertion point in each file: AFTER the closing `---` of YAML frontmatter AND AFTER the `# <Skill Name>` H1 heading line (and any blank line that follows the H1) AND AFTER any pre-H2 intro prose (PRESERVE the intro prose unchanged), BEFORE the first existing body H2 section.
   - per-skill template substitution: in the inserted block, replace the placeholder `<declared>` with the literal model name from the file's YAML `model:` field (`haiku` or `sonnet`). Verify the substitution by reading the YAML before edit, NOT by guessing. Replace `<skill name>` with the file's YAML `name:` field.
   - per-skill verification: after each Edit, read 30 lines starting at line 1 of the modified file and confirm:
     a. frontmatter still intact (lines 1–N where N is the closing `---` of YAML)
     b. `# <Skill Name>` H1 still present immediately after frontmatter
     c. all pre-H2 intro prose preserved unchanged (no inadvertent deletion)
     d. `## §0 Model dispatch (FIRST STEP — execute before anything else)` heading appears exactly once and BEFORE the first non-§0 H2 in the body
     e. `<declared>` placeholder is replaced (no literal `<declared>` substring remains in §0 slice)
     f. `<skill name>` placeholder is replaced (no literal `<skill name>` substring remains in §0 slice)
     g. the dispatch invocation contains BOTH the literal `model: "<resolved-tier>"` parameter line AND the `dispatched-tier:` marker token (per round-3 MAJ-1 fix)
   - acceptance:
     - all 12 files modified (1 from T-00 pilot + 11 from T-02 batch)
     - per-file structural assertions above all hold
     - `grep -c "## §0 Model dispatch (FIRST STEP — execute before anything else)" dev-workflow/skills/<each>/SKILL.md` returns `1` for each of the 12; returns `0` for the 9 Opus-tier skills (architect, plan, critic, revise, thorough_plan, run, init_workflow, discover, review)
     - `git diff --stat` shows exactly 12 SKILL.md files changed across T-00+T-02 (1 from T-00, 11 from T-02)

4. ✓ T-03: Resolve revise/SKILL.md ↔ revise-fast/SKILL.md sync constraint
   - context: `dev-workflow/skills/revise-fast/SKILL.md` opens with a `<!-- SYNC WARNING: -->` block stating the intentional differences vs `revise/SKILL.md` are limited to "frontmatter (name, description, model) and the 'Model requirement' section." Adding §0 to `revise-fast` only without updating the SYNC WARNING creates an undocumented intentional difference and burns future maintainer time.
   - decision (D-01 below): extend the SYNC WARNING to add `## §0 Model dispatch (FIRST STEP — execute before anything else)` to the list of intentional differences. Do NOT add §0 to `revise/SKILL.md` (revise is Opus-declared; the §0 dispatch rule short-circuits to no-op anyway, but the parent architecture's resolved open question on stage-1 scope explicitly limits it to the 12 cheap-tier skills — adding to revise broadens scope).
   - sub-edits inside `dev-workflow/skills/revise-fast/SKILL.md`:
     a. Update the SYNC WARNING comment block: change "The ONLY intentional differences are: frontmatter (name, description, model) and the 'Model requirement' section." to "The ONLY intentional differences are: frontmatter (name, description, model), the 'Model requirement' section, and the §0 self-dispatch preamble (revise-fast is sonnet-declared and ships w/ the Quoin Stage 1 preamble; revise is opus-declared and does not need it)."
     b. Update the "To check" diff command — current expected diff hint says "Expected diff: only the 'Model requirement' section." Update to: "Expected diff: the 'Model requirement' section AND the §0 self-dispatch preamble block."
   - automated SYNC contract test (per MAJ-5 fix — promotes acceptance to automated assertion): see T-04 case (h) below.
   - acceptance:
     - SYNC WARNING text updated as above
     - T-04 case (h) passes (asserts revise vs revise-fast diff matches expected structural pattern)

5. ✓ T-04: Author structural-consistency test for the §0 preamble across the 12 skills
   - file: `dev-workflow/scripts/tests/test_quoin_stage1_preamble.py`
   - model the test on `dev-workflow/scripts/tests/test_detection_rule_consistency.py` (parametrized fixture-equality pattern; same fixture-as-source-of-truth design).
   - shared helper (per CRIT-2 fix): a module-level helper function `extract_preamble_block(skill_path: Path) -> str` reads the SKILL.md file, slices everything between the `## §0 Model dispatch` heading line (inclusive) and the next `## ` heading line (exclusive). All §0-content assertions in this test file MUST operate on the sliced result, NEVER on the full file (this prevents YAML-frontmatter `model: sonnet`/`model: haiku` collision).
   - test cases:
     a. `test_each_skill_has_preamble_heading` — for each of the 12 SKILL.md files, assert the literal heading `## §0 Model dispatch (FIRST STEP — execute before anything else)` appears EXACTLY ONCE.
     b. `test_each_skill_first_body_h2_is_preamble` (per MAJ-7 fix — durable phrasing) — for each of the 12 files, assert the FIRST `## ` heading appearing AFTER the H1 `# <Title>` line is exactly the §0 heading literal. This is the contract: §0 is the first H2. Phrasing this as "first H2 after H1" survives a future maintainer who inserts a documentation H2 (e.g., `## Note: renamed in 2027`) — the test fails LOUDLY w/ a clear message about the documentation-H2 ordering rather than for an unrelated reason.
     c. `test_each_skill_preamble_substitutes_declared_model` (per round-3 MAJ-1 fix — TWO-LAYER assertion: actual `model:` parameter + `dispatched-tier:` marker) — for each of the 12 files, parse YAML frontmatter to extract `model:` value (must be `haiku` or `sonnet`), then call `extract_preamble_block(skill_path)` and assert ALL of the following on the slice:
        - **(i) actual dispatch parameter — load-bearing**: the slice contains the literal substring `model: "<that value>"` as a parameter line in the dispatch invocation block. This is the contract that the Agent tool receives a real `model:` argument (not a description-string match). A regex like `re.search(r'^\s*model:\s*"' + re.escape(value) + r'"\s*$', slice, re.MULTILINE)` makes the line-form requirement explicit.
        - **(ii) defensive marker — guards against accidental description-only embedding**: the slice contains the literal substring `dispatched-tier:` somewhere (the round-3 marker that signals the dispatch action was authored deliberately).
        - **(iii) negative substitution check**: the slice does NOT contain `<declared>` or `<skill name>` (placeholder substitution complete).
        - **(iv) frontmatter-collision discrimination proof**: `'dispatched-tier' not in skill_path.read_text().split('## §0', 1)[0]` — confirms the `dispatched-tier:` token does not appear OUTSIDE the §0 slice (i.e., proves the test's discrimination claim is real).
       Failure of (i) is a CRITICAL test failure — it means the round-3 MAJ-1 regression has recurred and the dispatch will silently no-op in production.
     d. `test_no_opus_tier_skill_has_preamble` — for each of the 9 Opus-tier skills (architect, plan, critic, revise, thorough_plan, run, init_workflow, discover, review), assert the heading `## §0 Model dispatch` does NOT appear (catches accidental over-application).
     e. `test_recursion_abort_sentinel_present` (per CRIT-3 alignment — assertions match aligned contract) — for each of the 12 files, slice the §0 block and assert the slice contains ALL these literal substrings: `[no-redispatch]` (bare), `[no-redispatch:N]` (counter form, in the abort-rule prose), `Quoin self-dispatch hard-cap reached at N=` (abort message; per NIT-1 the abort message also contains the skill name in the abort-rule prose, but the test asserts only the leading constant), AND `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]` (fail-graceful path per CRIT-1 fix).
     f. `test_no_inter_h2_prose_deleted_by_insertion` (per MAJ-1 fix) — for each of the 12 files, count the lines between the H1 line and the §0 heading line (i.e., the pre-§0 intro region). Assert the count is ≥ 0 (i.e., §0 is at or after H1+1). This is a smoke check that the per-file Edit anchor preserved any pre-existing intro prose — the actual content equality is checked by git diff in T-08, not here.
     g. `test_load_bearing_rules_preserved` (per MAJ-2 fix) — for `implement/SKILL.md`, assert that BOTH the §0 heading AND the literal heading `## Explicit invocation only` are present and that §0 precedes `## Explicit invocation only` in line order. Same dual-assertion for `expand/SKILL.md` (heading `## Hardcoded Tier 1 path list`) and `end_of_task/SKILL.md` (heading `## When to use`). This catches accidental deletion of load-bearing rules during §0 insertion.
     h. `test_revise_revise_fast_sync_contract` (per MAJ-5 fix — promote SYNC WARNING acceptance to automated assertion) — read both `dev-workflow/skills/revise/SKILL.md` and `dev-workflow/skills/revise-fast/SKILL.md`. Slice both files from the H1 `# Revise` line to EOF. Compute `difflib.unified_diff` line-by-line. Assert the only differing line groups are: (1) lines inside the `## Model requirement` section, AND (2) lines inside the `## §0 Model dispatch (FIRST STEP — execute before anything else)` block (which exists ONLY in revise-fast). Any other diff line fails the test w/ a message naming the unexpected diff line and its line range.
   - determinism: pure pathlib + string operations + PyYAML for frontmatter parsing + stdlib `difflib`. NO LLM calls, NO subprocess, NO network. Per lesson 2026-04-23 LLM-replay non-determinism, this is the right pattern for a §0 verification test.
   - acceptance:
     - `python3 -m pytest dev-workflow/scripts/tests/test_quoin_stage1_preamble.py -v` passes 8 test functions × N parametrized cases each
     - test file uses the same `pathlib.Path(__file__).parent` resolution pattern as `test_detection_rule_consistency.py` (no hardcoded absolute paths)
     - test file is checked into git

6. ✓ T-05: Author synthetic-recursion abort test (R-01 dominant-risk test)
   - file: `dev-workflow/scripts/tests/test_quoin_stage1_recursion_abort.py`
   - purpose: provide a deterministic functional test that the abort branch in the §0 block is correctly described (abort fires when the counter-form sentinel is present at N≥2). This is the test that satisfies architecture.md `## De-risking strategy` step 1.
   - approach: import the same `extract_preamble_block` helper from `test_quoin_stage1_preamble.py` (or duplicate locally if cross-file import is awkward). Run a small grammar check that confirms the prose in the slice contains the expected branch descriptions.
   - test cases (per CRIT-3 alignment — bare-sentinel canonical contract):
     a. `test_block_describes_dispatch_branch` — assert the §0 block slice contains the substring `Spawn an Agent subagent` AND `dispatched-tier:` AND a literal `model: "` parameter form (per round-3 MAJ-1 fix — confirms the dispatch action contains a real `model:` argument, not just a description string).
     b. `test_block_describes_proceed_branch` — assert the §0 block slice contains both `Otherwise` AND `proceed to §1`.
     c. `test_block_describes_abort_branch` — assert the §0 block slice contains BOTH `[no-redispatch:N]` AND the literal abort message `Quoin self-dispatch hard-cap reached at N=`. This is the load-bearing recursion-guard test.
     d. `test_block_describes_manual_kill_switch` (per CRIT-3 — bare-form is BOTH parent-emit AND user-override, intentionally) — assert the §0 block slice contains the substring `[no-redispatch]` (bare) used in TWO distinct contexts: (i) parent-emit context (the dispatch action's prompt-prefix line) AND (ii) user-override context (the manual-kill-switch documentation paragraph). Acceptance: count occurrences of the bare token `[no-redispatch]` in the slice; require count ≥ 2 (one for parent's prepend rule, one for the user's manual override). This is a deliberate sharing of syntax — a child cannot tell whether the bare sentinel came from the parent or the user, and that's by design.
     e. `test_block_describes_fail_graceful_branch` (per CRIT-1 fix) — assert the §0 block slice contains the literal warning string `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`. This guards that the architecture-I-01 fail-open path is documented.
     f. `test_synthetic_abort_branch_simulation` (per CRIT-3 suggestion (c)) — given a §0 block slice and a simulated incoming-prompt string `[no-redispatch:2] /gate`, assert (purely via string matching against the documented branch tree) that the documented outcome for that input is the abort branch. Implementation: parse the slice for the rule "if prompt starts w/ `[no-redispatch:N]` AND N≥2, ABORT", then simulate by checking the rule's grep targets match the synthetic input. This is a deterministic functional test — it does not invoke any LLM; it confirms the branch tree as documented covers the abort case.
     g. `test_block_present_in_all_12_skills` — assert that all 12 cheap-tier SKILL.md files have a non-empty §0 block slice (`extract_preamble_block(...) != ''`). Marked w/ `pytest.mark.smoke` to make the redundancy w/ T-04 case (a) intentional per MAJ-7 fix (avoids the silent-deletion regression class without fully duplicating the consistency check).
   - determinism: pure pathlib + string operations. No LLM calls, no subprocess.
   - acceptance:
     - `python3 -m pytest dev-workflow/scripts/tests/test_quoin_stage1_recursion_abort.py -v` passes
     - test file documents in its module docstring that this test is the architecture R-01 mitigation per `.workflow_artifacts/quoin-foundation/architecture.md` "## De-risking strategy" step 1

7. ✓ T-06: Add §0 preamble file class to dev-workflow/CLAUDE.md model-assignments table footnote
   - file: `dev-workflow/CLAUDE.md`
   - edit location: `## Model assignments` table (currently the last section in the "Dev Workflow" block before `# === DEV WORKFLOW END ===`). Add a new short subsection BELOW the table:

```markdown
### §0 Model dispatch preamble (Quoin foundation Stage 1)

The 12 cheap-tier skills (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast) carry a `## §0 Model dispatch (FIRST STEP — execute before anything else)` block as the first body H2 after the H1. When invoked from a session running on a model strictly more expensive than the declared tier, the skill self-dispatches via the Agent tool to its declared model and prefixes the child prompt with the bare `[no-redispatch]` sentinel to prevent infinite recursion. The counter form `[no-redispatch:N]` is reserved for an abort signal: if a child sees N≥2, it aborts instead of proceeding (the bare form is the normal parent-emit; counter forms catch buggy parents or mistaken manual overrides). The 9 Opus-tier skills do NOT carry the preamble — they should run on Opus regardless of session model.

If the harness's subagent-spawn tool is unavailable or returns an error, dispatch falls back to a fail-OPEN path (proceed at current tier, emit a one-line `[quoin-stage-1: subagent dispatch unavailable; ...]` warning). This is intentional per architecture I-01: cost guardrail is best-effort, not load-bearing for correctness.

Manual override: prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely. Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

Mechanical drift detection lives in `dev-workflow/scripts/tests/test_quoin_stage1_preamble.py` and `dev-workflow/scripts/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification lives in T-00 (pilot, before T-02) and T-09 (full four-phase smoke after T-02 + install) of the stage-1 plan and is captured in `dev-workflow/scripts/verify_subagent_dispatch.md`. (Note for the future Quoin-rebrand stage: this subsection's "Quoin foundation Stage 1" reference becomes stale post-rebrand — update the wording to a stage-tracker-stable reference at that time.)
```

   - acceptance:
     - the new subsection appears immediately after the `## Model assignments` table
     - subsection contains the exact phrases `## §0 Model dispatch (FIRST STEP — execute before anything else)`, `[no-redispatch]`, `[no-redispatch:N]`, `Manual override:`, AND a literal cross-reference to both test files (per MAJ-4 fix)
     - `## Model assignments` table itself is unchanged (no row additions or deletions)

8. ✓ T-07: Append a Tier 1 entry for the test fixture file to dev-workflow/CLAUDE.md
   - file: `dev-workflow/CLAUDE.md`
   - rationale: the fixture authored in T-01 (`dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md`) is the source-of-truth template for the §0 block. It is hand-edited and would be corrupted by terse-style compression (it contains exact phrases that downstream tests grep). Per CLAUDE.md `### Tier 1 — files that always stay English` rule, it must be added to the Tier 1 carve-out list.
   - edit location: under the `### Tier 1 — files that always stay English` section, in the appropriate sub-list (likely "Source files" or a new sub-list). Add:
     - `dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md` (Quoin Stage 1 §0 preamble template; hand-edited Tier 1; source of truth for the 12 cheap-tier SKILL.md preambles).
     - `dev-workflow/scripts/verify_subagent_dispatch.md` (Quoin Stage 1 subagent-dispatch verification template; hand-filled by user during T-00 pilot and T-09 smoke; lives at `dev-workflow/scripts/` only — NOT deployed to `~/.claude/scripts/` per round-3 MIN-1 fix; one-shot diagnostic, not a runtime tool).
   - acceptance:
     - both new bullets appear in the Tier 1 list
     - paths are verbatim correct
     - no other Tier 1 entries are removed or reordered

9. ✓ T-08: Run the full Stage 1 test suite locally and confirm no regressions in pre-existing tests
   - command: `cd "<project-root>" && python3 -m pytest dev-workflow/scripts/tests/ -v`
   - expectation:
     - new tests from T-04 + T-05 pass
     - pre-existing 9 test files still pass (in particular `test_detection_rule_consistency.py` is unchanged scope — it tests a different fixture, not the §0 preamble)
     - no test errors / collection errors
   - if any pre-existing test fails: STOP and investigate; do not paper over by modifying the failing test. Failure here means T-02 edits accidentally broke a different invariant (e.g., the verbatim §5.7.1 detection comment in gate/implement/expand/revise-fast/start_of_day was shifted by the §0 insertion).
   - acceptance (per MIN-4 fix — concrete numbers, not vague "pre-existing-count + new"):
     - pytest exits 0
     - pre-existing-collected-count baseline: **111 tests** (measured 2026-04-26 via `pytest --collect-only -q | tail -1`); post-implementation collected count MUST be at least `111 + 8 (T-04 cases) + 7 (T-05 cases) = 126 tests`. If T-04 or T-05 tests are parametrized, the count rises proportionally and the assertion becomes `≥ 126 + (parametrize_factor − 1) × parametrized_function_count` — record the actual count in the T-08 acceptance log.

10. ✓ T-09: Manual smoke test of self-dispatch in a real session — full four-phase check (HITL; runs AFTER T-00 pilot pass, AFTER T-02 batch insertion, AFTER `bash install.sh` redeploys all 12 skills)
    - this is a HUMAN-IN-THE-LOOP step that complements T-00. T-00 verified dispatch on ONE skill BEFORE T-02. T-09 verifies all four phases (dispatch, manual override, abort, /run-orchestration) on the FULL set of 12 deployed skills AFTER install.
    - cannot be fully automated b/c it depends on Claude Code's Agent tool dispatch behavior in production AND on whether the harness exposes a model-parameter-respecting subagent tool.
    - procedure (document in plan; user runs after `/implement` finishes T-02 + T-03 + T-06 + T-07 and after `bash install.sh` redeploys):
      a. Open Claude Code on Opus 1M. Verify w/ `/model` or by reading the harness banner ("powered by the model named X").
      b. Phase A — re-confirm harness verification on a different skill (T-00 used /triage; T-09 Phase A uses /gate to confirm dispatch works for sonnet-tier as well as haiku-tier): type `/gate` (no arguments). Observe whether the response shows: (i) a "Spawning subagent" banner OR equivalent model-handoff signal, (ii) the eventual response was generated by sonnet (not Opus, verifiable via cost-ledger row's model column), OR (iii) the fail-graceful warning `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`. Record observation in `dev-workflow/scripts/verify_subagent_dispatch.md` `## Observed` section (append a "Phase A re-confirmation" line below the T-00 observation). If the dispatch is silently no-op'd (none of i/ii/iii visible), STOP — that is the C1 silent-failure mode; do not proceed to merge until the prose is rewritten to use a verified mechanism.
      c. Phase B — manual override test: type `[no-redispatch] /gate`. Observe: gate skill should skip dispatch and run the body directly on Opus 1M. No subagent spawn; gate's normal output appears.
      d. Phase C — deep recursion-guard test: type `[no-redispatch:2] /gate`. Observe: gate skill should print the abort message `Quoin self-dispatch hard-cap reached at N=2 in /gate` and stop without running the body.
      e. Phase D (per MAJ-2 fix — load-bearing rule preservation under Section-zero dispatch): type `/run` followed by a small task that exercises `/implement`. Observe: when /run dispatches into /implement (which has the load-bearing `## Explicit invocation only` rule w/ /run exception clause), the child correctly recognizes its lineage. Specifically: the child does NOT bail out w/ "explicit invocation required" error. If it does, the §0 dispatch broke the implement-skill's lineage detection — in which case implement/SKILL.md needs an explicit note that "If invoked through Section-zero dispatch from /run, the dispatching parent's invocation context is preserved via the bare `[no-redispatch]` sentinel — the child does NOT re-evaluate /run lineage, it inherits it from the parent's decision."
      f. Capture all observations in `.workflow_artifacts/quoin-foundation/stage-1/manual-smoke-$(date +%Y-%m-%d).md` (per MIN-2 fix — use shell command-substitution for the date, not a literal `2026-04-NN` placeholder).
      g. If any phase fails: STOP, do NOT merge; capture the failure mode and revisit T-01/T-02 prose.
    - acceptance:
      - all four phases (A–D) match expectations
      - `dev-workflow/scripts/verify_subagent_dispatch.md` `## Result` section is `verified` (set during T-00 pilot, re-confirmed during T-09 Phase A)
      - failure mode captured in eventual `review-1.md` Risk Assessment section if any phase fails

11. ✓ T-10: Verify install.sh redeploys updated SKILL.md files (no script edits needed — round-3 MIN-1 fix definitively closes the install.sh hedge)
    - inspection only — no edit
    - read `dev-workflow/install.sh` Step 2: it iterates `for skill_dir in "$SCRIPT_DIR/skills"/*/` and copies `SKILL.md` from each. This glob auto-picks up the 12 modified files; no edit required.
    - **definitive resolution per round-3 MIN-1 fix:** install.sh's separate script-deploy loop (line 125: `for script_file in summarize_for_human.py validate_artifact.py; do`) is a hardcoded list, not a glob — so a NEW script (`verify_subagent_dispatch.py`) would normally need an explicit edit to deploy. We are NOT making that edit. The verify script and template (`verify_subagent_dispatch.py` + `verify_subagent_dispatch.md`) live at `dev-workflow/scripts/` only; they are NOT deployed to `~/.claude/scripts/`. Rationale: the verify script is a one-shot diagnostic run during T-00 (and re-runnable during T-09 Phase A), invoked directly from `dev-workflow/scripts/` via `python3 dev-workflow/scripts/verify_subagent_dispatch.py`. It is not a runtime tool that any deployed skill depends on. Keeping it un-deployed avoids both (a) an install.sh edit that broadens stage-1 scope and (b) a runtime-vs-source-of-truth ambiguity about which copy of the verify template captures the install observation. This closes the round-2 MIN-1 hedge definitively: zero install.sh diff in this stage's commits.
    - run-step verification: after `bash install.sh`, confirm `~/.claude/skills/gate/SKILL.md` (and the other 11) contains the §0 block. Spot-check 3 of 12: gate (first), end_of_day (haiku), revise-fast (last).
    - acceptance:
      - `grep -l "## §0 Model dispatch" ~/.claude/skills/*/SKILL.md | wc -l` returns 12
      - `grep -L "## §0 Model dispatch" ~/.claude/skills/*/SKILL.md | wc -l` returns the count of remaining (Opus-tier) skills (currently 9 in `~/.claude/skills/`)
      - no install.sh diff in this stage's commits
      - `~/.claude/scripts/verify_subagent_dispatch.py` does NOT exist (intentional; the script lives at `dev-workflow/scripts/` only)

## Decisions

D-01: Add §0 to `revise-fast/SKILL.md` only; do NOT add to `revise/SKILL.md`. Update the existing SYNC WARNING comment block in `revise-fast/SKILL.md` to declare §0 as a third intentional difference. Rationale: the parent architecture's resolved open question on stage-1 scope explicitly limits Stage 1 to the 12 cheap-tier skills; `revise` is Opus-declared and the §0 detection rule is a no-op there (current_tier == declared_tier never triggers dispatch). Adding §0 to `revise` would broaden scope and create a meaningless block in an Opus-tier skill. Cost of this decision: a one-line SYNC WARNING update plus a slightly larger expected diff between the two files. Benefit: keeps Stage 1 scope tight per the architecture's resolution. Mechanical enforcement: T-04 case (h) automates the SYNC WARNING contract via `difflib`.

D-02 (REVISED per CRIT-3 alignment): Use the **bare** sentinel form `[no-redispatch]` as the parent-emit form (matching architecture.md line 88 verbatim). Reserve the counter form `[no-redispatch:N]` (N≥2) as the abort signal ONLY — it exists to catch a buggy parent that emits `[no-redispatch:2]` directly or a misconfigured manual override (e.g., user typing `[no-redispatch:5] /gate`). This preserves the architecture's canonical contract; the round-1 plan's "every dispatch produces `[no-redispatch:1]`" formulation drifted from the architecture and made the counter useless as a recursion detector (since no parent in the design ever emits `:2`). The bare form is intentionally shared between parent-emit and user-override — a child seeing `[no-redispatch]` cannot distinguish whether it came from the parent or the user, and that's the correct design (both cases want the same proceed-to-§1 outcome). The abort branch is the safety net for a programming error (someone manually invoking `[no-redispatch:2]` or a future skill change accidentally emitting it).

D-03: Test the §0 block via structural string-matching on the sliced §0 block, NOT via live LLM replay. Rationale: lesson 2026-04-23 LLM-replay non-determinism. A structural test asserts the prose-level contract (the block exists, contains the right tokens, branches the right way). T-00 (pilot, single skill) and T-09 (full four-phase) are the human-in-the-loop functional smokes that complement the structural tests. Together, structural + HITL pilot + HITL full-smoke cover the safety property without burning $30 per CI run.

D-04: Insert §0 BEFORE every other H2 body section (immediately after H1 + any pre-H2 intro prose; PRESERVE intro prose). Rationale: the §0 block's first phrase ("FIRST STEP — execute before anything else") is load-bearing instruction prose. If §0 followed `## Session bootstrap` or `## Process`, the model would have already read setup instructions and possibly started cost-ledger writes BEFORE deciding to dispatch — defeating the cost guardrail. T-04 case (b) is the regression test for this ordering invariant; case (f) verifies pre-§0 intro prose was preserved (per MAJ-1). Note (per round-2 MIN-2 deferral): pre-H2 intro prose IS read before §0 in 9 of 12 files; this is acceptable because intro prose is descriptive (no tool calls, no cost-ledger writes) — the cost-guardrail rationale is preserved (§0 fires before any tool call), and moving §0 above H1+intro-prose would risk visually orphaning the §0 block from skill identity. The "FIRST STEP — execute before anything else" framing in the §0 heading is the load-bearing signal that the model must execute §0 before any subsequent skill body work, and that contract holds whether intro prose is read before or not.

D-05: Per-skill substitution of `<declared>` placeholder happens at INSERT time (T-02), not at runtime via a literal placeholder + skill self-introspection. Rationale: keeping the placeholder runtime-dynamic would require each skill to re-parse its own YAML frontmatter, adding ~5–10 lines of pseudo-code per skill. Substituting at insert time is one Edit per skill and the resulting block is greppable across the codebase by literal model name. Trade-off: if a skill changes its declared tier in the future (e.g., `expand` is upgraded from sonnet to opus), the §0 block must be re-edited — but this is a rare event and is caught by T-04 case (c) which asserts the substitution matches the YAML.

D-06 (REVISED per round-3 MAJ-1 fix): Two-layer defense for the dispatch-action contract. **Layer 1 (load-bearing): the slicer.** SKILL.md YAML frontmatter contains literal `model: sonnet`/`model: haiku` lines (verified empirically — e.g., `dev-workflow/skills/gate/SKILL.md:4:model: sonnet`). T-04 case (c) calls `extract_preamble_block` to slice the §0 block first; YAML frontmatter is OUTSIDE the slice, so any `model: "<declared>"` parameter line inside the slice CANNOT collide with frontmatter. The slicer is the structural guarantee that makes assertions on the literal `model:` parameter line safe. **Layer 2 (defensive marker): the `dispatched-tier:` token.** A comment-style line `Dispatch reason: dispatched-tier handoff to <declared> tier.` precedes the parameter block; the unique `dispatched-tier:` token provides a secondary signal that the dispatch action was authored deliberately (not accidentally collapsed into a description string, as happened in round 2). Both layers must hold; (1) is the load-bearing guarantee that the harness will receive a real `model:` argument; (2) is the defensive signal that the dispatch invocation was authored intentionally. The round-2 plan's bug was deleting the actual `model:` parameter and putting `dispatched-tier: model: "<declared>"` INSIDE the description string — round 3 restores the parameter to its own line and keeps the marker as a separate prose phrase.

D-07 (REVISED per round-3 MAJ-2 fix + round-2 CRIT-1 fix + MAJ-3 fix): T-00 is a HITL pilot diagnostic that verifies dispatch on a SINGLE skill (`triage/SKILL.md`) BEFORE T-02 batches the §0 insertion across the other 11 skills. Rationale: a pre-merge live-LLM dispatch call would (a) violate lesson 2026-04-23 LLM-replay non-determinism if automated in CI, (b) require ANTHROPIC_API_KEY in CI which lesson 2026-04-25 set-u-rc-hang flagged as fragile, (c) cost ~$0.50 per run × every CI run if run as a pre-commit hook. The pilot-skill HITL pattern (T-00) restores meaningful pre-merge de-risking value (the round-2 plan made T-00 a doc generator that ran post-install, leaving 12 broken files to revert if dispatch failed). Cost: one Opus→Haiku dispatch attempt (~$0.05) at install time. The verify script + template (`verify_subagent_dispatch.py` + `verify_subagent_dispatch.md`) live at `dev-workflow/scripts/` only and are run directly from there — they are NOT deployed to `~/.claude/scripts/` (per round-3 MIN-1 fix; one-shot diagnostic, not a runtime tool). The result is captured in a file under `dev-workflow/scripts/verify_subagent_dispatch.md`. The §0 prose's fail-graceful path (D-08) is the runtime safety net for cases where verification was skipped or for production sessions where the harness regresses post-install.

D-08 (NEW per CRIT-1 fix — fail-graceful runtime safeguard): If the dispatch tool returns an error or is unavailable, the §0 block falls back to "proceed at current tier; emit a one-line warning". This is fail-OPEN on cost guardrail (better to overspend than to abort the user's invocation) per architecture I-01 ("Default to no-dispatch (proceed at current tier) on detection failure"). Trade-off: silent-no-op masquerading as dispatch is no longer possible — either dispatch happens (visible subagent banner) or the fail-graceful warning fires (visible log line). This makes the C1 silent-failure mode surface as an observable event in the harness rather than as a token-burn that the user only notices in the cost ledger.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |
|----|------|-----------|--------|------------|----------|
| R-01 | §0 preamble has a recursion bug that bypasses both sentinel and counter, burning tokens infinitely on every cheap-tier invocation | Low | High | Bare sentinel + counter-form abort per D-02 (architecture-aligned); T-04 case (e) and T-05 case (c) assert the abort-message string is present in every block; T-09 Phase C manually verifies the abort path actually fires | `git revert` the T-02 commit; redeploy via `bash install.sh`; the 11 batch-edited skills lose the §0 block and behave as they did before Stage 1; T-00's pilot triage edit is also reverted in the same commit |
| R-02 | T-02 insertion accidentally shifts the verbatim §5.7.1 detection-comment block in 5 of the 12 skills (gate, implement, expand, revise-fast, start_of_day all carry it per `test_detection_rule_consistency.py` SKILL_FILES), breaking byte-equality | Medium | Medium | T-08 runs the FULL test suite, including `test_detection_rule_consistency.py`; failure surfaces immediately. Per-skill verification in T-02 acceptance includes a re-read after edit. Per MAJ-6 fix: T-01 acceptance explicitly forbids the §0 fixture from containing the literal `# v3-format detection (architecture.md §5.7.1 — copy verbatim)` first-line string — prevents the `_first_line_bytes()` count-based test from drifting into failure | Re-edit affected files: the §0 block goes BEFORE the §5.7.1 detection-comment block (insertion at the top of the body). The §5.7.1 block stays verbatim and in its original position in the file's body; only its line number shifts (which the byte-equality test is robust to — it tests substring presence, not absolute line position) |
| R-03 | Per-skill placeholder substitution in T-02 fails for one or more files (forgetting to swap `<declared>` for `haiku` or `sonnet`), producing a §0 block that dispatches to a non-existent model name | Low | High (skill never runs because dispatch fails) | T-04 case (c) parses each file's YAML and asserts the §0 block slice (NOT the full file — per CRIT-2 fix, frontmatter collision is real) contains the substituted literal `model: "haiku"` or `model: "sonnet"` parameter line AND the `dispatched-tier:` marker (per round-3 MAJ-1 two-layer fix); also asserts no literal `<declared>` substring remains in slice. Per D-08 fail-graceful path, even a wrong-model dispatch surfaces as a visible warning rather than silent failure | Re-edit the affected file(s) with the correct substitution; T-04 fails until fixed |
| R-04 | The §0 block prose itself is misinterpreted by the model in production (e.g., it dispatches when it shouldn't, or doesn't dispatch when it should) | Medium | Medium (cost overrun if it fails-open; functionality break if it fails-closed) | T-09 manual smoke covers all four phases (dispatch, proceed, abort, /run-orchestration preservation) on Opus 1M against the deployed `~/.claude/skills/gate/SKILL.md`; T-00 pilot smoke catches the worst-case dispatch-no-op BEFORE T-02 touches the other 11 files (per round-3 MAJ-2 fix). Per CRIT-1 + D-08 fail-graceful path: any harness incompatibility or dispatch error surfaces as a `[quoin-stage-1: subagent dispatch unavailable; ...]` warning rather than a silent no-op. If T-09 reveals incorrect dispatch behavior, freeze the prose and revisit before merge | Same as R-01 (revert T-02 commit and the T-00 pilot commit) |
| R-05 | Adding §0 to a 12th skill (`revise-fast`) creates undocumented drift vs `revise/SKILL.md`, breaking the existing SYNC WARNING contract | Low | Low | T-03 explicitly updates the SYNC WARNING text to add §0 as a third documented intentional difference; D-01 captures the rationale. Per MAJ-5 fix: T-04 case (h) automates the SYNC contract via `difflib` — any unexpected drift between revise and revise-fast (other than `## Model requirement` and `## §0 Model dispatch ...`) fails the test on day one | Either (a) revert T-03 and remove §0 from `revise-fast`, OR (b) add §0 to `revise/SKILL.md` as a no-op block (incompatible with the parent architecture's stage-1 scope resolution) |
| R-06 | The `<skill name>` placeholder substitution in T-02 produces inconsistent skill names across files (e.g., `gate` vs `Gate` vs `/gate`) and downstream audits break | Low | Low | The §0 prose only uses the skill name in a `description:` field of the dispatch instruction — purely descriptive, not load-bearing. Use the YAML `name:` field verbatim (lowercase, no slash) for consistency. T-04 case (c) asserts no literal `<skill name>` remains in slice | Re-edit affected files |
| R-07 | The fixture file (T-01) and the inserted §0 blocks (T-02) drift apart over time (someone edits a SKILL.md §0 block without updating the fixture, OR vice versa) | Medium (over months) | Low (only matters if someone re-runs a fixture-based test that depends on equivalence) | Stage 1 test design intentionally does NOT use byte-equality between fixture and inserted blocks (substitution makes that impossible). Fixture is documentation-only; T-04 tests are the actual contract. Document this in the fixture file's first comment line: "Reference template for review only. The 12 SKILL.md blocks are the source of truth for downstream tests." | None needed — fixture is advisory |
| R-08 | The `## §0` heading (with the section symbol) trips up some downstream tooling that doesn't handle non-ASCII headings cleanly | Low | Low | The `§` character is already used elsewhere in CLAUDE.md and architecture.md (e.g., "v3 §5.1") and existing tests parse those files without issue. UTF-8 is the default encoding everywhere | If a real tooling break surfaces, replace `## §0` with `## Section 0` across all 12 files and the fixture — one-shot find/replace |
| R-09 (REVISED per round-3 MAJ-1 + MAJ-2 fixes) | The harness's subagent-spawn mechanism does not support a model parameter (or supports it incompletely) — every "dispatch" silently runs at the parent tier, OR the §0 prose accidentally collapses the `model:` parameter into a description string (the round-2 regression) | Medium (harness side) / Low (prose side post-MAJ-1 fix) | High (cost guardrail no-op) | T-00 pilot HITL verification on triage/SKILL.md catches harness-side failure BEFORE T-02 batch insertion (per round-3 MAJ-2 fix — pre-merge de-risking, not post-install). T-04 case (c) two-layer assertion (actual `model: "<declared>"` line + `dispatched-tier:` marker) catches the prose-side regression statically (per round-3 MAJ-1 fix). T-09 Phase A re-confirms dispatch on the full deployed set after install. Per D-08, the §0 prose's fail-graceful path emits an observable warning when dispatch fails, so silent no-op is replaced by visible-warning-no-op. The remaining failure mode is "harness lies about supporting model parameter and silently downgrades to current tier without erroring" — T-00 + T-09 inspection of the cost-ledger row's model column catches this. | Same as R-01 (revert T-02 commit AND T-00 pilot commit; ship a follow-up stage that uses a different mechanism, e.g., user must manually `/model haiku` before invoking) |
| R-10 (NEW per MAJ-2 fix) | §0 dispatch breaks load-bearing rules in `implement/SKILL.md` (`## Explicit invocation only` w/ /run exception), `expand/SKILL.md` (`## Hardcoded Tier 1 path list`), or `end_of_task/SKILL.md` (`## When to use` post-/review-only) by either deleting the rule, reordering it before the §0 dispatch decision, or breaking lineage detection in /run-orchestrated dispatch | Low | High (rule bypass would let the wrong skills run in the wrong contexts) | T-04 case (g) asserts the load-bearing headings are present AND ordered after §0 in implement, expand, end_of_task. T-09 Phase D exercises /run-orchestrated dispatch into /implement and verifies lineage is preserved (the bare `[no-redispatch]` sentinel is shared between parent-emit and user-override; the child cannot tell the difference and that's intentional, but it must not falsely reject a legitimate /run invocation). If T-09 Phase D fails, add a note in implement/SKILL.md `## Explicit invocation only` documenting the §0-dispatch lineage-inheritance rule | Re-edit affected SKILL.md files; or revert T-02 for affected file and ship a follow-up that handles lineage explicitly |

## Procedures

```
PROCEDURE T-00 pilot-verify subagent dispatch (HITL; runs BEFORE T-02):

1. Author the §0 fixture per T-01 first (T-01 acceptance criteria all pass).
2. Generate the verification template: write a small ~30-line stdlib Python script
   `dev-workflow/scripts/verify_subagent_dispatch.py` that emits a markdown template
   to `dev-workflow/scripts/verify_subagent_dispatch.md` w/ three sections
   (## Procedure / ## Observed / ## Result). Exit 0 always.
3. Manually insert §0 into ONLY `dev-workflow/skills/triage/SKILL.md` per the T-02
   per-file procedure for row "pilot" in the anchor table.
   Verify per T-02 step 7 (re-read 30 lines, all six structural assertions hold,
   plus the round-3 MAJ-1 dispatch-parameter check: literal `model: "haiku"` line
   AND `dispatched-tier:` token both present in the §0 slice).
4. Run `bash install.sh` to deploy ONLY the modified triage/SKILL.md (the install.sh
   skill loop will pick up all 12 SKILL.md files; only triage has been changed at
   this point, so the redeploy is effectively a single-file deploy for our purposes).
5. Open Claude Code on Opus 1M. Verify w/ /model or harness banner.
6. Type: `/triage what should I run next?`
7. Observe ONE of the three signals:
     (i) "Spawning subagent" banner + cost-ledger row for triage child shows
         claude-haiku in model column → DISPATCH VERIFIED → mark `## Result: verified`
         in verify_subagent_dispatch.md → T-00 PASS → proceed to T-02.
     (ii) Fail-graceful warning `[quoin-stage-1: subagent dispatch unavailable;
          proceeding at current tier]` followed by triage's normal output on Opus
          → harness does not support model parameter → mark `## Result: failed`
          → STOP. Stage-1 rewrite per D-07. Capture exact harness banner, dispatch
          tool error, and any alternative-mechanism attempts.
     (iii) NEITHER signal AND response on Opus → SILENT NO-OP → mark `## Result: failed`
           → STOP. The §0 prose itself is mis-specified — revisit T-01.
8. Record observation in verify_subagent_dispatch.md `## Observed`: which signal,
   the cost-ledger row's model column, the harness banner string from step 5, and
   any tool-error message.
9. Commit: triage/SKILL.md (modified) + verify_subagent_dispatch.py (new) +
   verify_subagent_dispatch.md (new w/ ## Result filled in) → git status --short
   verifies all three files tracked.
```

```
PROCEDURE T-02 per-skill insertion (run for each of the 11 remaining SKILL.md files
AFTER T-00 pilot pass; STOP if T-00 result is `failed` or `untested`):

0. Pre-flight: read dev-workflow/scripts/verify_subagent_dispatch.md `## Result`
   section. If not `verified`, ABORT — do not run T-02.
1. Read the file's YAML frontmatter (first lines from `---` to closing `---`).
2. Extract `name:` value (lowercase string, e.g., "gate") and `model:` value
   (e.g., "sonnet" or "haiku").
3. Read the fixture file dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md.
4. In a string buffer, replace the placeholder `<declared>` with the extracted
   model value, and `<skill name>` with the extracted name value.
5. Identify the insertion point in the SKILL.md file: line index immediately after
   the H1 (`# Title`) line, after any blank line that follows the H1, AFTER any
   pre-H2 intro prose, BEFORE the first `## ` heading. Use the per-file
   insertion-anchor table in T-02 above as the primary anchor; fall back to step 6
   fallback if the anchor doesn't match.
6. Use the Edit tool: old_string = the H1 line + the trailing blank line + the
   FIRST 5–10 chars of the existing first body line OR the first H2 heading literal
   (whichever is uniquely matchable per the per-file table); new_string = the same
   content with the substituted §0 block inserted in between (H1 + blank +
   intro-prose-preserved + blank + §0 block + blank + existing first H2 line).
   - alternative (if intro prose is empty for that file): old_string = the H1 line
     + blank, new_string = H1 + blank + §0 block + blank.
7. Read 30 lines from line 1 of the modified file. Confirm:
   - line 1: `---` (start of frontmatter)
   - frontmatter YAML intact
   - line N+1 (where N = closing `---`): blank
   - line N+2: `# <Title>`
   - line N+3: blank or first line of preserved intro prose
   - first H2 line in file body: `## §0 Model dispatch (FIRST STEP — execute before anything else)`
   - body of §0 block follows; specifically: literal `model: "<resolved-tier>"`
     parameter line is present AND `dispatched-tier:` marker token is present
     (round-3 MAJ-1 dual check)
   - blank line then the next `## ` heading begins the original body
8. If verification fails, revert the file (`git checkout dev-workflow/skills/<name>/SKILL.md`)
   and retry from step 5 with a more-specific old_string anchor (cross-reference the
   per-file table).
```

```
PROCEDURE T-08 full test suite verification:

1. cd to project root.
2. Run: python3 -m pytest dev-workflow/scripts/tests/ -v --tb=short
3. Expect zero failures.
4. If `test_detection_rule_consistency.py` fails: 5 of the 12 modified files (gate,
   implement, expand, revise-fast, start_of_day) carry the §5.7.1 detection-comment
   block. The byte-equality test treats the fixture as a contiguous substring;
   insertion of §0 BEFORE the body section that contains the block does NOT break
   the test (substring is still present). If the test fails, the §0 insertion landed
   inside or split the §5.7.1 block — re-edit to insert OUTSIDE the §5.7.1 block.
   Per MAJ-6 fix and T-01 acceptance: the §0 fixture must NOT contain the literal
   `# v3-format detection (architecture.md §5.7.1 — copy verbatim)` first-line string,
   which prevents the `_first_line_bytes()` count-based test from being tripped by
   quoted text.
5. If a brand-new test failure surfaces in any other test file, investigate before
   merging.
6. Per MIN-4 fix: post-implementation collected test count should be ≥ 126 (baseline
   111 + T-04's 8 cases + T-05's 7 cases). Record actual count in T-08 acceptance log.
```

```
PROCEDURE T-09 manual smoke (human-in-the-loop, post-implement,
runs AFTER T-00 pilot pass and AFTER T-02 batch + install):

1. Run `bash install.sh` to redeploy the 12 modified SKILL.md files to ~/.claude/skills/.
2. Open Claude Code on Opus 1M (verify with /model or by reading the harness banner).
3. Phase A — re-confirm dispatch on a sonnet-tier skill (T-00 used haiku-tier triage;
   Phase A uses sonnet-tier gate to confirm both tiers dispatch correctly):
   type `/gate` w/o preceding sentinel.
   Expected (one of):
     (i) "Spawning subagent" banner + eventual response generated by sonnet
         (cost-ledger row records claude-sonnet) — DISPATCH VERIFIED.
     (ii) Fail-graceful warning `[quoin-stage-1: subagent dispatch unavailable;
          proceeding at current tier]` followed by gate's normal output on Opus
          — STOP and rewrite §0 prose. (Should not happen if T-00 passed; if it
          DOES happen here but T-00 passed on haiku, that's a tier-specific harness
          regression.)
     (iii) NEITHER signal AND response on Opus — silent no-op — STOP and rewrite
           §0 prose. (Same caveat as ii.)
   Append observation as a "Phase A re-confirmation" line in
   verify_subagent_dispatch.md `## Observed`.
4. Phase B — manual override: type `[no-redispatch] /gate`.
   Expected: gate skips dispatch and runs the body directly on Opus 1M. No subagent
   spawn; gate's normal output appears.
5. Phase C — deep recursion guard: type `[no-redispatch:2] /gate`.
   Expected: gate prints `Quoin self-dispatch hard-cap reached at N=2 in /gate...`
   and stops. No body execution, no subagent spawn.
6. Phase D — /run-orchestrated dispatch into /implement: invoke /run on a small
   prepared task that triggers /implement in the orchestration. Verify: child
   /implement does NOT bail w/ "explicit invocation required"; the bare
   `[no-redispatch]` sentinel correctly preserves /run lineage. If it bails, add
   the lineage-inheritance note to implement/SKILL.md.
7. Capture observations in
   `.workflow_artifacts/quoin-foundation/stage-1/manual-smoke-$(date +%Y-%m-%d).md`
   (use shell command-substitution, do NOT hardcode a date).
8. If any phase fails: STOP, document the failure, do NOT proceed to /review.
```

## References

- `.workflow_artifacts/quoin-foundation/architecture.md` — parent architecture document; specifically the "Self-dispatch preamble (item #1)" subsection of `## Proposed architecture` (lines 64–88; CANONICAL — bare sentinel form, separate `model: "<declared>"` parameter line), the `## Risk register` rows on self-dispatch recursion and recursive self-critique, the `## Stage decomposition` Stage 1 entry, the `## Integration analysis` rows I-01 (fail-graceful default) and I-02 (sentinel counter), and the open-questions resolution that scopes Stage 1 to the 12 cheap-tier skills.
- `dev-workflow/skills/architect/SKILL.md` line 104 — documents that "model specification is not supported in the current harness version" is a real failure mode (CRIT-1 source citation; T-00 pilot directly addresses this caveat).
- `dev-workflow/scripts/tests/test_detection_rule_consistency.py` — pattern model for T-04 structural test (parametrized fixture-equality across multiple SKILL.md files).
- `dev-workflow/CLAUDE.md` — `## Model assignments` table (T-06 edit target); `### Tier 1 — files that always stay English` section (T-07 edit target).
- `dev-workflow/install.sh` — Step 2 skill-deployment loop (T-10 verification target; no edit; line 81 glob auto-picks up 12 modified SKILL.md files; line 125 hardcoded script-deploy list intentionally omits `verify_subagent_dispatch.py` per round-3 MIN-1 fix).
- `.workflow_artifacts/memory/lessons-learned.md` — 2026-04-23 (LLM-replay non-determinism — informs D-03 and D-07), 2026-04-23 (gitignored-parent-dirs — informs T-01 and T-00 acceptance), 2026-04-13 (cross-skill permission audit — informs why §0 needs to be IN each SKILL.md, AND informs MAJ-2 cross-skill contract preservation in implement/expand/end_of_task), 2026-04-25 (`set -u` rc hang — informs D-07 rationale for not using API-key-dependent CI tests), 2026-04-22 (cost runaway from recursive critic — informs revision discipline: no scope creep beyond critic-issue resolution), 2026-04-25 (V-07 prefix-match — informs why writer-format vs validator-invariant must be designed together; informs MAJ-1 + MAJ-7 test phrasing).

## Notes

Stage 1 is the foundation for Stage 5 (native Haiku summarizer). Stage 5 replaces `bash with_env.sh python3 summarize_for_human.py` with an Agent subagent dispatch on `model: haiku`. The Agent-dispatch mechanism that Stage 1 wires for §0 self-dispatch is the SAME mechanism Stage 5 will use for the summarizer — so a successful T-00 pilot in Stage 1 also de-risks Stage 5's core hypothesis. Conversely, if T-00 reveals the harness does not support model-parameter dispatch, Stage 5 inherits the same risk and must be replanned before it can ship.

Cache write-through (per round-2 MIN-3 fix + round-3 MIN-5 fix — unconditional procedural update; CLAUDE.md cache rule (b) is the canonical guidance): rather than hardcoding the "currently `architect`, `critic`, `triage` only" list (which can shift between planning and implementation), use the procedural form. Before /implement starts T-02, run `ls .workflow_artifacts/cache/dev-workflow/skills/ 2>/dev/null` and intersect the result with the 12-skill list (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast). For each intersected entry, append a single line to the cache entry's `## Notes` (or equivalent) section: `Section-zero self-dispatch added per Quoin Stage 1 (model: <declared>); body purpose, exports, and integration points unchanged.` (Substitute `<declared>` with the file's YAML model value.) This is the correct CLAUDE.md cache rule (b) wording — unconditional update for any modified source, not a hardcoded list.

Stage 1 produces no new install.sh deployment surface. The 12 SKILL.md files are picked up by the existing `for skill_dir in "$SCRIPT_DIR/skills"/*/` glob (no edit). The fixture file (T-01) lives under `dev-workflow/scripts/tests/fixtures/` and is consumed only by tests via `pathlib.Path(__file__).parent / "fixtures" / "..."`; it is NOT deployed. The new test files (T-04, T-05) are also test-only, not deployed. The verify script + template (T-00: `verify_subagent_dispatch.py` + `verify_subagent_dispatch.md`) live at `dev-workflow/scripts/` only and are NOT deployed to `~/.claude/scripts/` (per round-3 MIN-1 fix — definitive resolution: install.sh's hardcoded script list at line 125 is intentionally NOT extended; the verify script is a one-shot diagnostic, not a runtime tool, and is invoked directly from `dev-workflow/scripts/`). Zero install.sh diff in this stage's commits.

Stage-1 acceptance (rolls up the per-task acceptance criteria into a stage-level go/no-go for the gate after /review):
- T-00 pilot verification passed BEFORE T-02 ran on the remaining 11 files (verify_subagent_dispatch.md `## Result` = `verified`)
- All 12 SKILL.md files carry the §0 block (T-00 pilot + T-02 batch + T-08)
- All structural tests pass (T-04 + T-05 + T-08), including round-3 MAJ-1 two-layer dispatch-parameter assertion in T-04 case (c)
- Pre-existing test suite still passes (T-08, baseline 111 tests; post-impl ≥ 126)
- Manual smoke verifies all four phases A–D (T-09)
- CLAUDE.md updates land cleanly (T-06 + T-07)
- install.sh redeploys without modification (T-10); no `verify_subagent_dispatch.py` in `~/.claude/scripts/`
- Total scope (per MIN-6 fix — corrected file-count math): 12 SKILL.md edits (T-00 pilot is row 1; T-02 batch is rows 2–12; SYNC WARNING update in T-03 is a sub-edit of the same revise-fast/SKILL.md file as #12, NOT a separate file change) + 1 CLAUDE.md edit (T-06 + T-07 are both sub-edits of the same file) + 1 fixture file (T-01) + 1 verify_subagent_dispatch.py + 1 verify_subagent_dispatch.md (T-00) + 2 new test files (T-04, T-05) + 1 cache update procedure (intersected entries; ≥1 update for triage/_index.md) = **18 files touched (typical, with one cache update)**, of which 12 are SKILL.md and 6 are new or non-SKILL edits.

## Revision history

1. Round 1 — 2026-04-26 — claude-opus-4-7 — Initial plan; 10 tasks; covered §0 dispatch, structural test, recursion abort, CLAUDE.md updates, manual smoke. Critic verdict: REVISE w/ 3 CRITICAL, 7 MAJOR, 6 MINOR.
2. Round 2 — 2026-04-26 — claude-opus-4-7 — Critic verdict: REVISE. Issues addressed (CRIT-1, CRIT-2, CRIT-3, MAJ-1..MAJ-7, MIN-1..MIN-4, MIN-6); deferred MIN-5 (install.sh per-install log) w/ D-08 runtime-warning subsumes rationale. Round-2 revision introduced two NEW issues (round-3 critic): (a) the CRIT-2 fix for frontmatter-collision deleted the actual `model:` parameter from the dispatch invocation prose and embedded `dispatched-tier: model:` inside the description string, breaking the dispatch contract while preserving the test; (b) T-00 became a documentation generator that ran post-install, removing pre-merge de-risking value.
3. Round 3 — 2026-04-25 — claude-opus-4-7 — Critic verdict (round 2): REVISE w/ 0 CRITICAL, 2 MAJOR, 5 MINOR, 1 NIT. Issues addressed:
   - **MAJ-1 (round-2 NEW; dispatch-parameter regression)** — restored the explicit `model: "<declared>"` parameter on its own line in the dispatch action prose (matches architecture.md lines 73–83 verbatim). Kept `dispatched-tier:` as a SEPARATE marker on a comment-style line (`Dispatch reason: dispatched-tier handoff to <declared> tier.`). T-04 case (c) rewritten to assert TWO things separately on the §0 slice: (i) a regex-anchored `model: "<declared>"` parameter line is present (load-bearing — guarantees harness gets a real `model:` argument), AND (ii) the unique `dispatched-tier:` marker is present (defensive — guards against accidental description-only embedding). T-05 case (a) updated to match. D-06 revised to document the two-layer defense; R-09 mitigation column updated.
   - **MAJ-2 (round-2 NEW; T-00 was post-install doc generator)** — restructured T-00 from a documentation generator into a HITL pilot diagnostic that verifies dispatch on a SINGLE skill (`triage/SKILL.md` — chosen per the round-2 critic's suggestion: smallest haiku tier, no intro prose, not heavily wired) BEFORE T-02 batches the §0 insertion. T-02 now has an explicit pre-flight check that aborts if T-00 result is not `verified`. T-09 was renamed/repurposed as a four-phase post-install smoke that re-confirms dispatch on a sonnet-tier skill (gate) and exercises the manual-override, abort, and /run-orchestration phases. D-07 revised to document the pilot-skill HITL pattern and its pre-merge de-risking value. R-04 mitigation column updated to cite T-00 as the pre-T-02 catch.
   - **MIN-1 (round-2 NEW; install.sh hedge)** — resolved definitively: NO install.sh edit. The verify script + template (`verify_subagent_dispatch.py` + `verify_subagent_dispatch.md`) live at `dev-workflow/scripts/` only and are run directly from there; they are NOT deployed to `~/.claude/scripts/`. Rationale: one-shot diagnostic, not a runtime tool. Notes section + T-10 acceptance + T-07 Tier 1 entry all updated to state this explicitly. The round-2 hedge in T-10 Notes that punted the install.sh decision to /implement is removed.
   - **MIN-2 (round-2; D-04 rationale gap for files w/ pre-H2 intro prose)** — addressed via D-04 expansion: pre-H2 intro prose IS read before §0 in 9 of 12 files; this is acceptable because intro prose is descriptive (no tool calls, no cost-ledger writes) — the cost-guardrail rationale is preserved (§0 fires before any tool call). Documented as a deliberate trade-off rather than left ambiguous.
   - **MIN-4 (round-2; D-07 typo "fileunder")** — fixed in D-07: "captured in a fileunder dev-workflow/scripts/..." → "captured in a file under `dev-workflow/scripts/verify_subagent_dispatch.md`".
   - **MIN-5 (round-2; cache list snapshot vs procedure)** — Notes section's cache write-through guidance rewritten as a procedure: intersect `.workflow_artifacts/cache/dev-workflow/skills/` listing w/ the 12-skill list at /implement time and update each intersected entry; no hardcoded snapshot.
   - **NIT-1 (round-2; abort message lacks skill name)** — addressed: T-01 sub-bullet (c) abort message format updated to `Quoin self-dispatch hard-cap reached at N=<N> in <skill>. ...` (skill name appears between N and the rest); T-04 case (e) and T-05 case (c) phrased to assert only the leading constant `Quoin self-dispatch hard-cap reached at N=` so skill-name variation does not break the test; T-09 Phase C expected output updated to show `N=2 in /gate`.
   - **MIN-3 (round-2; T-00 marginal value)** — addressed by the MAJ-2 restructure: T-00 is no longer a doc generator that adds maintenance surface for marginal value; it is now a load-bearing pre-T-02 pilot that catches the C1 silent-failure mode at the earliest possible point. The two new files (verify_subagent_dispatch.py + .md) are now justified by real pre-merge de-risking value.
