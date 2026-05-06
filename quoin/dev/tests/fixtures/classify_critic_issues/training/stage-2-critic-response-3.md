---
task: quoin-foundation / stage-2
phase: critic
round: 3
date: 2026-04-27
target: .workflow_artifacts/quoin-foundation/stage-2/current-plan.md
model: claude-opus-4-7
class: A
---

## Verdict: PASS

## Summary

Round-2 issues all closed. MAJ-1-r2 (path-agnostic gate): D-02b branch (b) is now path-agnostic ("After ccusage execution completes — whichever of the per-UUID loop or the bulk `--since` call was taken"); T-07 case 2 asserts a path-agnostic phrase via OR-set ("regardless of" / "whichever of" / "either" / "path-agnostic"). MIN-1-r2 (ledger-date placeholder): T-04 (c) now uses `<earliest-date-from-ledger>` matching SKILL.md line 160 style, with a derivation note ("min of column-2 dates across all data lines in cost-ledger.md — preserve existing SKILL.md derivation"). MIN-2-r2 (asymmetry note): T-04 (g) added prose explaining the structural asymmetry, plus the in-SKILL comment text `# (Binary-check + all-failed-gate are structurally separate per D-02b — same fallback semantics as cost_snapshot Step 2's single conflated branch.)`.

Round-1 fixes still hold (project_hash regex, anchor texts, bulk wiring, D-02a/b split, Wayback URL, anchor-order). One NIT only: frontmatter `revision: 2` and the For-human block reference round-2 even though round-3 history is in the body — known stale metadata, not a content defect.

## Issues

### Critical (blocks implementation)
- (none)

### Major (significant gap, should address)
- (none)

### Minor (improvement, use judgment)
- (none)

### Nit
- **[NIT-1-r3] Frontmatter revision counter and For-human block are stale by one round**
  - What: Plan frontmatter line 8 reads `revision: 2`; the For-human block (lines 10-20) describes the round-2 revision and says "Run /critic round 2 to confirm…". The Revision history at the bottom (lines 396-400) correctly logs Round 3 — 2026-04-27 with the MAJ-1-r2 / MIN-1-r2 / MIN-2-r2 fixes, so the body content is current. Only the metadata header and human summary lag.
  - Why it matters: cosmetic / archaeology only. No implementation impact — the implementer reads the Tasks section and the Revision history, both of which are correct. But future readers picking up just the For-human block will think this is round-2.
  - Suggestion: bump frontmatter to `revision: 3`; rewrite the For-human block to summarize the round-3 closures (MAJ-1-r2 path-agnostic gate, MIN-1-r2 placeholder fix, MIN-2-r2 asymmetry note) and update "What's needed to make progress" to reference round-3 critic. NOT worth a round-4 cycle — fold into the next /revise pass IF round-4 is triggered for some other reason; otherwise let `/implement` carry forward as-is.

## Round-2 issue ledger (closed vs open)

| ID | Round-2 status | Round-3 verification | Status |
|----|----------------|---------------------|--------|
| MAJ-1-r2 | D-02b gate (b) anchored to per-UUID loop only — bulk-mode failure had no fallback gate | Plan T-04 (b) lines 213-221 rewritten path-agnostic ("After ccusage execution completes — whichever of the per-UUID loop or the bulk `--since` call was taken"); D-02b decision (line 337) says "PATH-AGNOSTIC all-failed gate placed AFTER ccusage execution completes — regardless of which path was taken (per-UUID loop or bulk `--since` call)"; T-07 case 2 (plan line 309) asserts an OR-set of path-agnostic phrases AND adds the test rationale "Substring-only assertion on 'every UUID' or 'all UUIDs' is INSUFFICIENT — it cannot distinguish a correctly placed path-agnostic gate from a per-UUID-loop-only gate" | CLOSED |
| MIN-1-r2 | T-04 (c) bulk-mode placeholder `EARLIEST-DATE-FROM-LEDGER` not parseable | Plan T-04 (c) line 228 now uses `<earliest-date-from-ledger>` (matching SKILL.md line 160 style); lines 229-231 add the derivation note "Compute earliest-date-from-ledger as the min of column-2 dates across all data lines in cost-ledger.md (the same expression Step 6 already uses for the bulk ccusage call — preserve the existing SKILL.md derivation)" | CLOSED |
| MIN-2-r2 | Structural asymmetry between cost_snapshot's single conflated branch and end_of_task's two separated branches not flagged in prose | Plan T-04 (g) line 242 adds the prose-level note explaining the asymmetry; the in-SKILL comment `# (Binary-check + all-failed-gate are structurally separate per D-02b — same fallback semantics as cost_snapshot Step 2's single conflated branch.)` is specified for insertion inside the path-agnostic gate text in branch (b) at line 220; D-02b (line 337) closes with a back-reference to T-04(g) | CLOSED |

## Round-1 fixes — regression check

| ID | Round-1 fix | Round-3 status |
|----|-------------|----------------|
| CRIT-1 | project_hash regex `re.sub(r'[^A-Za-z0-9-]', '-', path)` | Still present at T-02 lines 92-93; T-06 line 288 golden value unchanged. NO REGRESSION. |
| CRIT-2 | end_of_task Step 6 missing-binary pre-flight + all-fail gate added | Both branches still present in T-04 (a)+(b); the all-fail gate became MORE robust in round-3 (path-agnostic). NO REGRESSION. |
| MAJ-1 | end_of_task bulk `--since` wired into fallback block + T-07 grep | T-04 (c) lines 224-232 retain bulk variant; T-07 case 2 line 309 retains both substrings (`-i` and `--since`). NO REGRESSION. |
| MAJ-2 | D-02 split into D-02a / D-02b | Still split at lines 335-337; D-02b expanded to clarify path-agnostic semantics, not regressed. NO REGRESSION. |
| MAJ-3 | T-01 commit body requires Wayback URL + four rates + halt-if-drift | T-01 lines 65-69 retain all three requirements verbatim. NO REGRESSION. |
| MIN-1 / MIN-2 / MIN-4 / NIT-1 / NIT-3 | parametrize idiom, anchor-text refs, anchor-order assertions, cd prefix, version-stable count | All present, unchanged. NO REGRESSION. |

## Stuck-loop signals

None. Round-3 closes a different defect than round-1 (CRIT-2 was the per-UUID-loop missing-binary path; MAJ-1-r2 was the bulk-call leg of the same gate concept; round-3's path-agnostic rewrite addresses a structurally distinct case from CRIT-2). The round-3 fix is also the canonical resolution (single path-agnostic gate at the convergence point), not a third round of patching the same site. MAJ-1-r2 is now CLOSED at the trigger level (path-agnostic phrase) AND the test level (OR-set of phrases in T-07 case 2). Three-round trajectory shows monotonic narrowing: CRIT/MAJ count decreased every round (round-1: 2 CRIT + 3 MAJ + 5 MIN; round-2: 0 CRIT + 1 MAJ + 2 MIN; round-3: 0 CRIT + 0 MAJ + 0 MIN + 1 NIT). Convergence achieved.

## Empirical verifications performed

- `dev-workflow/skills/end_of_task/SKILL.md` Step 6 area read (lines 143-178): Step 6 has a per-UUID loop branch (line 151 anchor `Run \`npx ccusage session -i <UUID> --json\` for each UUID, sequentially:`) AND a bulk `--since` branch (lines 159-161, "For tasks with 5 or more sessions"), both converging on "Aggregate results (hold in memory for Step 8):" at line 174. The path-agnostic gate's specified insertion point ("AFTER the ccusage execution block — REGARDLESS OF PATH — before 'Aggregate results'") maps to a real call-site convergence point — one gate at the convergence covers both legs without duplication.
- Architecture lines 92-123 (S-02 contract) and 351-358 (stage-2 block + de-risking step 2) re-read: plan stays within scope (script + fallback wiring + parity test), no contract drift. Architecture line 121 ("call ccusage first, fall back to `cost_from_jsonl.py` on missing-binary or non-zero exit") is exactly the semantics the plan's path-agnostic gate implements.
- Plan T-04 (b) text "whichever of the per-UUID loop or the bulk `--since` call was taken" is the round-2 critic's option (ii) verbatim ("After ccusage execution completes (whichever of per-UUID loop or bulk call was taken), if NO ledger UUID was successfully resolved, fall back").
- Plan T-07 case 2 OR-set assertion ("regardless of" OR "whichever of" OR "either" OR "path-agnostic") will MATCH the gate text (the gate text contains "whichever of"). Round-3 wording test will pass. The fallback-to-two-separate-gates option is also explicitly accepted by T-07, giving the implementer flexibility.

## What's good

- Round-3 fix is the canonical, single-gate-at-convergence solution — structurally simpler than the round-2 critic's option (i) (extra gate b'). Plan correctly chose option (ii).
- T-07 case 2 was strengthened with EXPLICIT rationale text ("Substring-only assertion ... is INSUFFICIENT") quoting the round-2 critic's MAJ-1-r2 lesson. Forward-defensive: future critics or revisers reading T-07 will see the lesson encoded in the test, not just the plan body.
- D-02b decision text now reads as a self-contained justification of the path-agnostic shape; future archaeology is well-served.
- The MIN-2-r2 fix did NOT just add a prose note — it ALSO specified the literal in-SKILL comment text for insertion. This makes T-04 less ambiguous and protects the rationale at the deployment surface, not just in the plan.
- Revision history (line 400) explicitly enumerates the round-2-to-round-3 deltas with anchor references — full audit trail across three rounds.
- All round-1 fixes verified intact; no regression introduced by round-3 edits (which were narrowly scoped to T-04 (b) wording, T-04 (c) placeholder, T-04 (g) prose, and D-02b clarification).

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | good | All round-1 and round-2 issues closed; only metadata-staleness NIT remains |
| Correctness | good | Empirical regex still verified; anchor texts unchanged; path-agnostic gate maps to real convergence point in SKILL.md Step 6 |
| Integration safety | good | Bulk-mode and per-UUID failure both covered by single path-agnostic gate; missing-binary pre-flight intact |
| Risk coverage | good | R-01..R-08 unchanged; R-03 mitigation now consistent with path-agnostic trigger |
| Testability | good | T-07 case 2 OR-set + rationale text encodes the MAJ-1-r2 lesson at the test boundary |
| Implementability | good | Plan is implementation-ready; only known-stale frontmatter/For-human metadata, not blocking |
| De-risking | good | Three-UUID baseline, malformed-JSONL + unknown-model defensive cases all preserved |
