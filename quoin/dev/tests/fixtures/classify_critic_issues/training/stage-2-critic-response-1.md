---
task: quoin-foundation / stage-2
phase: critic
round: 1
date: 2026-04-27
target: .workflow_artifacts/quoin-foundation/stage-2/current-plan.md
model: claude-opus-4-7
class: A
---

## Verdict: REVISE

## Summary

Stage-2 plan covers the cost_from_jsonl.py fallback with a sound 8-task graph, well-thought-out pricing-table provenance (T-01), and a live-comparison parity test design that correctly applies lesson 2026-04-22 (no frozen ccusage snapshot). The critic-loop-and-Opus-cost lesson is not directly applicable here (this is a code/script change, not a docs-only revision).

However, **two CRITICAL spec defects would cause the script to be unusable on the developer's machine**: (a) the `project_hash` function only replaces `/`, but the actual `~/.claude/projects/<hash>/` directory on this disk shows `.`, `@`, `_`, and spaces ALL transformed to `-`; (b) the plan's wiring of `/end_of_task` Step 6 only patches the per-UUID error branch and never adds a missing-binary OR all-UUIDs-failed gate, so the architecture-mandated fallback wouldn't actually fire there in production. Three MAJ items (`--since` mode wiring scope, missing acceptance for D-02 decision-table sharpness, fallback for the BULK ccusage call path) and several MIN items round it out.

## Issues

### Critical (blocks implementation)

- **[CRIT-1] `project_hash` transform is wrong: must replace `/`, `.`, `@`, `_`, and spaces — not only `/`**
  - What: T-02's `project_hash(path)` does `return project_path.replace("/", "-")`. The accompanying `test_project_hash_function` (T-06) asserts `project_hash("/Users/x/My Drive") == "-Users-x-My Drive"` (spaces preserved, only slashes replaced). CLAUDE.md does say "project-hash = absolute project path with `/` replaced by `-`" — but this is empirically wrong for the actual on-disk format Claude Code uses.
  - Why it matters: spot-check on this very machine: real project path is `/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Claude_workflow`; actual on-disk directory is `~/.claude/projects/-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com-My-Drive-Storage-Claude-workflow/`. Transformations observed empirically: `/` → `-`, `.` → `-`, `@` → `-`, `_` → `-`, ` ` (space) → `-`. The plan's transform would compute `-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan.gorban@gmail.com-My Drive-Storage-Claude_workflow`, which **does not exist on disk**. Result: `cost_from_jsonl.py session -i <UUID>` always exits 2 (UUID-not-found), and the parity test in T-06 is permanently SKIPPED on the developer's machine ("UUID jsonl not found locally") — silently. The whole stage ships green but doesn't work.
  - Where: T-02 `project_hash` definition (lines 76-80 of the plan); T-06 `test_project_hash_function` (lines 241).
  - Suggestion: (a) replace the implementation with a transform that also maps `.`, `@`, `_`, and ` ` to `-`. The exact rule used by Claude Code in practice (verifiable by listing `~/.claude/projects/` and reverse-mapping the entries) appears to be "replace any non-`[A-Za-z0-9-]` character with `-`" — confirm empirically, then encode that. (b) Update the test to assert the empirical rule, e.g. `project_hash("/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Claude_workflow") == "-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com-My-Drive-Storage-Claude-workflow"`. (c) Update CLAUDE.md's "project-hash = project path with `/` replaced by `-`" rule to reflect the empirical transform, OR explicitly note that CLAUDE.md's rule is a simplification and the script must use the empirical rule. (d) Make T-06's parity test FAIL (not skip) when the JSONL is not found AND `~/.claude/projects/` has matching directories — silent skips on this exact failure mode are how the bug would ship green.

- **[CRIT-2] T-04 wiring of `/end_of_task` Step 6 is structurally insufficient — Step 6 has no missing-binary OR all-UUIDs-failed branches today, plan only patches the per-UUID error line**
  - What: T-04 says "replace the 'If a lookup times out or returns an error' block — line 172 — with the same fallback flow, BUT scoped to the per-task ledger UUIDs" and "the fallback is only triggered when the BINARY is missing or every UUID failed (the 'all calls fail' case)." Verified against `dev-workflow/skills/end_of_task/SKILL.md` Step 6 (lines 143-178): there is **no current branch** for "binary missing" OR "every UUID failed" — Step 6 only handles per-UUID timeout/error (line 172) and bulk-mode (lines 158-161). The plan's edit instructions describe what to do but never explicitly say: "introduce a NEW pre-flight check for `command -v npx` (or the equivalent) at the top of Step 6 that, if absent, falls into the cost_from_jsonl.py path; introduce a NEW post-loop check that, if every per-UUID call returned non-zero, invokes the fallback for those same UUIDs."
  - Why it matters: the most likely outcome is the implementer applies a surgical sed-style edit to line 172 only, leaving Step 6 with the OLD ccusage-only entry path. On this machine `npx` is present (per stage-5 lessons), so the per-UUID error branch fires and writes "cost unknown" — same as today. The fallback NEVER runs. Stage-2 ships green and `/end_of_task` still reports "cost unknown" exactly like before — the architecture's whole point is unmet. T-07's wiring smoke test (substring match on `cost_from_jsonl.py session -i`) would still pass because the literal text was inserted somewhere in Step 6, just at the wrong control-flow site.
  - Where: T-04 lines 191-194 of the plan; verify against `dev-workflow/skills/end_of_task/SKILL.md` lines 143-178.
  - Suggestion: rewrite T-04's end_of_task block as a structural insertion, not a line-172 replace. Explicitly: (a) "Add a pre-flight branch at the top of Step 6: `if ! command -v npx` (or `shutil.which`-equivalent narration), invoke fallback for ALL ledger UUIDs, prepend the [fallback: ...] notice, skip ccusage entirely." (b) "After the per-UUID loop, count non-zero exits. If ALL N UUIDs returned non-zero (and binary was present), re-invoke ALL N UUIDs through fallback; prepend the same notice." (c) "Leave the per-UUID line-172 'cost unknown' branch in place for partial failures — the fallback fires only on **all-failed**, per D-02." Update T-07's wiring test from substring-match to a structural assertion that the fallback appears under BOTH a "missing binary" anchor AND an "all UUIDs failed" anchor — substring match alone gives a false-positive on the wrong-anchor edit.

### Major (significant gap, should address)

- **[MAJ-1] Bulk-mode (`--since`) ccusage path has no fallback wiring spec — the cost_snapshot 5+ UUID hot path silently skips fallback**
  - What: cost_snapshot SKILL.md Step 2 has TWO ccusage call patterns: per-UUID (`-i UUID --json`, line 91) for <5 UUIDs and bulk (`session --json --since DATE`, line 97) for ≥5 UUIDs. T-04's wiring for cost_snapshot does include both modes in its AFTER text (lines 168-172 of the plan: "Per-UUID mode" and "Bulk mode"). Good — for cost_snapshot. But end_of_task SKILL.md Step 6 ALSO has a bulk-mode branch (lines 158-161 of `end_of_task/SKILL.md`: `npx ccusage session --json --since <earliest-date-from-ledger>`), and T-04's end_of_task block (lines 191-194 of the plan) only mentions per-UUID fallback (`session -i <UUID> --json`). If a task has 5+ ledger entries, end_of_task takes the bulk path; if `npx` is missing or the bulk call fails, the per-UUID fallback never gets a chance.
  - Why it matters: this stage already had cost-aggregation lessons (lesson 2026-04-22, $140 task with 35× cost-band overrun); long-running tasks like quoin-foundation itself have many sessions, so the bulk path is the realistic failure mode the fallback is supposed to catch.
  - Where: T-04, end_of_task block (plan lines 191-194); cost_from_jsonl.py CLI contract (T-03, lines 130-132 — has `--since YYYY-MM-DD`).
  - Suggestion: extend the end_of_task fallback wiring to include the bulk variant, mirroring the cost_snapshot AFTER text. Update T-04 acceptance: `grep -c "cost_from_jsonl.py" dev-workflow/skills/end_of_task/SKILL.md` returns ≥ 2 (per-UUID + bulk), not ≥ 1. Update T-07 case `test_end_of_task_has_fallback_wiring` to assert BOTH `cost_from_jsonl.py session -i` AND `cost_from_jsonl.py session --json --since` substrings.

- **[MAJ-2] D-02 decision table is asymmetric: cost_snapshot already conflates "missing-binary OR all-fail", but `/end_of_task` doesn't — D-02 needs to spell out per-skill semantics**
  - What: D-02 says "Fallback fires only on missing-binary OR all-UUIDs-failed, not on individual-UUID errors." Verified: cost_snapshot Step 2 line 104 already has `If npx or ccusage is not available, or all calls fail, print: ...` — already a single conflated branch. So replacing line 104 with the fallback flow is correct AND minimal. But end_of_task Step 6 has NO such conflated branch — it has only per-UUID (line 172) and a separate bulk-mode (line 158-161). D-02 currently reads as a single uniform decision; in practice it requires DIFFERENT structural edits per skill (one substitution in cost_snapshot; two new branches in end_of_task).
  - Why it matters: an implementer reading D-02 in isolation may make the cost_snapshot edit cleanly and then attempt the same surgical pattern on end_of_task — find no matching anchor — and either skip the edit or insert wrongly. This is exactly the failure mode described in CRIT-2.
  - Where: Decisions section, D-02 (plan line 287); paired with T-04 plan lines 161-194.
  - Suggestion: split D-02 into D-02a (cost_snapshot — single branch substitution at line 104) and D-02b (end_of_task — TWO new branches: missing-binary at top of Step 6, all-UUIDs-failed after the loop). The plan's T-04 block should reference D-02a/D-02b explicitly, and T-04's two acceptance grep counts should reflect the asymmetric structure.

- **[MAJ-3] Pricing-table sourcing for Sonnet + Haiku is procedurally specified but not architecturally pinned — the architecture doesn't carry these numbers, and a price-page change between plan-write and implement-time silently rewrites the constants**
  - What: architecture lines 110-117 ONLY pin Opus rates verbatim (15.00 / 75.00 / 18.75 / 1.50). Sonnet and Haiku are stub `{...}`. The plan's T-01 lists Sonnet (3.00 / 15.00 / 3.75 / 0.30) and Haiku (1.00 / 5.00 / 1.25 / 0.10) inline. The plan's procedure says "Sonnet + Haiku rates come from anthropic.com/pricing on 2026-04-25; if pricing-page values differ from those in the constants block at implement time, the implementer halts and asks." This puts a stable Opus baseline in architecture but leaves Sonnet/Haiku numbers in a per-revision plan artifact — the plan that gets archived and superseded.
  - Why it matters: Anthropic occasionally adjusts cache prices between minor model versions. If `/critic` round 2 or 3 lands and the pricing page has shifted by then, the implementer halts at T-01, asks, and the Sonnet/Haiku numbers get bumped — but the plan's listed numbers stay stale, so future archaeology to reconstruct the price-source-of-truth becomes harder. Lesson 2026-04-22 (cost theater) explicitly calls out price drift as a multi-month invisible failure mode.
  - Where: T-01 PRICES block (plan lines 53-61); architecture lines 110-117.
  - Suggestion: (a) require the T-01 commit body to embed a Wayback Machine URL snapshot (`https://web.archive.org/web/2026*/https://www.anthropic.com/pricing`) of the pricing page on the implementation date — a stable archival reference, not the live page that will drift. (b) After T-01 lands, append a one-row entry to architecture.md's pricing block (or a new "Pricing source-of-truth" reference section) with the snapshot URL and the four-rate-per-model table — moving the source-of-truth into a Tier 1 file. (c) If updating architecture.md mid-stage is out of scope, at minimum require the T-01 commit body to BOTH (i) record the four rates per model AND (ii) explicitly note "if these differ from the architecture's Opus baseline OR from anthropic.com/pricing on the implementation date, halt and ask before committing." Currently the procedure exists in the plan; the commit body trail does not.

### Minor (improvement, use judgment)

- **[MIN-1] T-06 pytest parametrize idiom is named in D-05 but not specified in T-06 acceptance — implementer may pick the wrong shape**
  - What: D-05 says "T-06 test_parity_against_ccusage iterates the three UUIDs in a parametrize loop." T-06 itself doesn't show the parametrize decorator pattern; the test naming convention in D-05 is `test_parity_against_ccusage` (singular), which `@pytest.mark.parametrize` would expand to `test_parity_against_ccusage[UUID-1]`, `test_parity_against_ccusage[UUID-2]`, etc. The plan's open-question 1 (pytest parametrize idiom for T-06) is the user's flagged gap.
  - Why it matters: an implementer might write a single test that loops internally over the 3 UUIDs (one fail = whole test fails, no per-UUID granularity) instead of a parametrized test (one fail = one case fails, others still report). The latter is the right pattern for cost-drift surfacing.
  - Where: T-06 (plan lines 230-247); D-05 (plan line 293).
  - Suggestion: in T-06, name the decorator pattern explicitly: `@pytest.mark.parametrize("uuid", FIXTURE_UUIDS)` where `FIXTURE_UUIDS` is read from `tests/fixtures/cost_from_jsonl/uuids.txt` at module import time. Each parametrized case skips independently if the UUID's JSONL is absent. This is the architecture's "1% tolerance per UUID" intent — three independent assertions, not one combined.

- **[MIN-2] install.sh deploy edit is line-shift-fragile — plan pins line 125 and line 201, but stage-1 changes already shifted those**
  - What: T-05 says "line 125 currently reads: `for script_file in validate_artifact.py path_resolve.py; do`" — verified, exact match today. But the plan also says "the rest of the deploy loop (`SCRIPT_SRC`/`SCRIPT_DST`/`cp`/`chmod +x`/`success` echo at lines 126-134) is invariant." Line numbers in install.sh shift with every prior stage's edits; pinning the line number is fragile. The user's flagged open-question 3 (install.sh line-shift defensive framing for T-05) is exactly this.
  - Why it matters: if a stage-1.1 hotfix or stage-3 prereq lands before stage-2 implements, line 125 is no longer the for-loop. The implementer's grep-for-context becomes the only safety net.
  - Where: T-05 (plan lines 207-219).
  - Suggestion: replace line-number references with anchor-text references. Example: "Locate the line `for script_file in validate_artifact.py path_resolve.py; do` (currently around line 125)." Same for the summary echo: "Locate the line containing `v3 scripts copied to ~/.claude/scripts/`." Anchor-text is line-shift-stable; line numbers are not. (Lesson 2026-04-26 dispatches the same kind of fragility around grep mismatches.)

- **[MIN-3] `--since` timestamp parsing is timezone-naive against UTC ISO timestamps — boundary cases will misclassify**
  - What: T-03 says "for each file, read FIRST line's timestamp ... parse as ISO date; include if `>= since`". Spot-checked: actual JSONL row 1 of an existing session is `{"type":"queue-operation","operation":"enqueue","timestamp":"2026-04-25T17:10:10.400Z","sessionId":"..."}`. The timestamp is UTC (`Z` suffix). The user-supplied `--since YYYY-MM-DD` is timezone-naive. A session started at 23:30 local time on 2026-04-25 (= 06:30 UTC on 2026-04-26) would have a UTC `Z` timestamp on 2026-04-26 — and `--since 2026-04-26` would include it, while a user mentally thinking "since yesterday" might expect it filed under 2026-04-25.
  - Why it matters: edge case, low impact (off-by-one-day on bulk mode); but ccusage almost certainly behaves the same way (UTC), so parity test is fine. Document the convention.
  - Suggestion: T-03 docstring says "comparison is in UTC; --since YYYY-MM-DD is interpreted as YYYY-MM-DDT00:00:00Z." Add a unit test asserting boundary inclusion at midnight UTC.

- **[MIN-4] Q-02 ("fallback only in stage 2") respected, but no explicit guardrail test**
  - What: per architecture line 411 + the parent's resolved Q-02, cost_from_jsonl.py is FALLBACK ONLY in stage 2 (no primary callsite). The plan's T-04 enforces this prose-level (ccusage is tried first). T-07 case `test_no_fallback_in_other_skills` asserts cost_from_jsonl.py doesn't appear in unrelated SKILL.md files — good. But there is no explicit assertion that the wiring text in cost_snapshot AND end_of_task says "try ccusage first" — only that cost_from_jsonl.py appears.
  - Why it matters: a future revision could accidentally swap the order (call fallback first, ccusage second) without any test firing — the fallback's stage-2-only constraint becomes prose-level only.
  - Suggestion: add a wiring-test assertion that the literal substring "ccusage" appears BEFORE the literal substring "cost_from_jsonl.py" in both SKILL.md files (anchor-order test, not anchor-presence test). One-line change to T-07 case 1 and 2.

- **[MIN-5] R-04 mitigation is acceptance-grep based; lesson 2026-04-26 (acceptance grep must match implementation pattern) suggests verifying the grep pattern**
  - What: R-04 mitigation says "explicit acceptance grep that `## §0 Model dispatch` still appears once and is still first body H2." The grep `grep -c "## §0 Model dispatch (FIRST STEP — execute before anything else)" SKILL.md` returning 1 is the literal acceptance check (T-04 line 202). Verified: cost_snapshot and end_of_task BOTH carry this exact heading at H2 position. The grep is correct as written today.
  - Why it matters: lesson 2026-04-26-C is "plan acceptance grep must match implementation patterns" — defensive read says verify the grep pattern matches even when the §0 heading is surrounded by surgical edits to Step 2/Step 6.
  - Suggestion: T-04 acceptance adds: "After the edit, run `awk '/^## /{c++; if (c==1 && !/§0 Model dispatch/) print FILENAME\": §0 not first H2\"; }' dev-workflow/skills/cost_snapshot/SKILL.md dev-workflow/skills/end_of_task/SKILL.md` — must produce zero lines." This catches the case where the surgical edit accidentally inserts a new H2 above §0 (the architecture-mandated invariant from stage-1).

### Nit

- **[NIT-1] T-01 acceptance import-test uses `sys.path.insert(0, 'dev-workflow/scripts')` — fine for in-repo test, but plan never says "from project root" and `cd` matters.** Suggest: prefix the command with `cd "<project-root>" &&` to mirror T-08's framing.

- **[NIT-2] `cost_for_entry` returns `(0.0, sum(...))` for unknown models, summing both with `or 0`. The `or 0` is redundant once `usage.get(k, 0)` already provides a default; minor stylistic nit.**

- **[NIT-3] T-08 records pre-implementation count via `pytest --collect-only -q | tail -1` — `tail -1` of pytest output is brittle (varies by version: "55 tests collected" vs "55 collected"). Suggest using `pytest --collect-only -q | grep -E "^[0-9]+ test" | head -1` or `--co -q --no-header | wc -l` for a stable count.**

## What's good

- T-01 isolates pricing-table provenance into its own task with explicit URL + date acceptance — auditable price source. Aligns with R-02 / I-03.
- D-04 (live ccusage parity, no frozen snapshot) directly applies lesson 2026-04-22 (fixture-rot). Correct learning from prior critic round.
- D-02 codifies the all-UUIDs-failed semantics — pre-emptively answers the user's open question 2. (See MAJ-2 for the asymmetry refinement.)
- T-08 explicitly guards the §0 dispatch preamble against accidental edit (R-04 + lesson 2026-04-26 anti-archaeology).
- Task graph (Procedures section) and parallelization (T-04 / T-05 / T-06 fan out from T-03) are realistic and reflect dependencies accurately.
- T-06 case `test_unknown_model_does_not_crash` is forward-compatible (Anthropic adds new model names) — exactly the right test.
- Exit-code contract (0 / 1 / 2) per architecture line 119 is preserved: 0 = success, 1 = parse error, 2 = UUID-not-found. T-03 acceptance asserts each. Confirmed correct against architecture.
- JSON output shape matches `ccusage session ... --json` keys (`sessionId`, `totalCost`, `totalTokens`, `entries[{model, costUSD, tokens}]`) — drop-in compatible per architecture lines 103-106.
- `[fallback: cost_from_jsonl.py — prices as of YYYY-MM-DD]` notice is correctly delegated to the SKILL.md callers (D-03), not the script — preserves byte-for-byte ccusage drop-in compatibility on stdout.
- Exclusions respected: ledger row format unchanged (Procedures section silent on it = preserved); no new phases introduced; `/end_of_day` and `/weekly_review` correctly NOT touched (T-07 case 4 explicitly asserts this).
- Test design covers: ccusage parity (T-06 case 1, ≤1%), missing-binary (T-07 cases 1+2 — wiring-level), missing-UUID (T-06 case 2 — exit-code), malformed JSONL (T-06 case 3). Architecture-mandated four cases all present in some form.

## Open questions verdicts (independent)

1. **pytest parametrize idiom for T-06** — see MIN-1. Plan should pin the decorator pattern explicitly. NOT a blocker, but easy to state.

2. **Decision-table sharpness around "fallback fires only on all-UUIDs-failed"** — see MAJ-2. The decision is asymmetric across the two skills; it needs to be split. **This IS a blocker because CRIT-2 follows from it.**

3. **install.sh line-shift defensive framing for T-05** — see MIN-2. Anchor-text references over line numbers; trivial to fix.

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | fair | CRIT-1 + CRIT-2 + MAJ-1: structural edits to end_of_task missing; bulk-mode wiring missing; project_hash transform incomplete |
| Correctness | poor | CRIT-1: project_hash transform fails empirically on the developer's machine; T-06 test asserts the wrong rule |
| Integration safety | fair | T-04 wiring spec under-specifies end_of_task structural edits; T-07 substring tests give false-positives on wrong-anchor inserts |
| Risk coverage | good | R-01..R-08 well-stratified; R-04 (§0 preamble) explicitly guarded; R-07 (price-page drift) procedurally addressed |
| Testability | fair | T-06 + T-07 design is sound but project_hash test cements the bug; bulk-mode fallback path has no test; anchor-order assertion missing |
| Implementability | fair | T-01..T-03 well-specified; T-04 prose under-specifies the structural change; line-pinned anchors fragile |
| De-risking | good | Live parity test, three-UUID baseline, malformed-JSONL + unknown-model defensive cases all present at planning time |
