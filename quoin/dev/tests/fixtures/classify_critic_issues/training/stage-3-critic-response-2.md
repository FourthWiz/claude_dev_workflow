---
round: 2
date: 2026-04-26
target: stage-3/current-plan.md
task: quoin-foundation
class: A
---

## Verdict: REVISE

## Summary

Round 1's nine issues are largely well-resolved (8 of 12 fully resolved; 1 insufficient; 3 partially). The reviser's deviation on plan/SKILL.md line 16 was correct after independent verification — the round-1 critic was wrong. However, the round-2 sweep introduces (or exposes) two new findings: (a) `rollback/SKILL.md` ALSO hardcodes `<task-name>/current-plan.md` at lines 53 and 65 and is missing from the T-05 edit list — same class as round-1 C1 (orchestration/operational skill drops a load-bearing read of the plan after stage-3 lands); (b) the C3 fix for gate/SKILL.md line 116 promises a "verbatim quote + suggested rewrite immediately below this table" but no such rewrite text is actually present in the plan — the implementer is left to invent it, which contradicts the "exact edit boundaries" rationale that motivated C3 in the first place.

## Round 1 issue resolution table

| ID | Title (round 1) | Status | Notes |
|----|-----------------|--------|-------|
| C1 | `/run` and `/architect` SKILL.md missing from T-05 edit list | Insufficient | Resolves run + architect (good), but the same audit applied to the rest of `dev-workflow/skills/` reveals `rollback/SKILL.md` is ALSO missing — see new C-A. |
| C2 | `mixed/` fixture mismatched real production case | Resolved | Renamed `mixed/` → `mixed-with-decomp-only/` w/ explicit synthetic-worst-case classification; added `arch-no-decomp/` (matches caveman) and `arch-absent-with-stage-folder/` (matches artifact-format-architecture); per-folder shape-fingerprint asserts in T-08 case (e). Verified production shapes by direct ls/grep — they match the fixtures byte-for-byte. |
| C3 | Anchor-line precision (plan/SKILL.md, critic/SKILL.md:113, gate/SKILL.md:116) | Partially resolved | (a) plan/SKILL.md line 16: VERIFIED CORRECT by direct read — reviser was right, round-1 critic was wrong (lines 14=L1, 15=L2, 16=L3 "Read the task subfolder", 17=L4 cost-ledger). (b) critic/SKILL.md line 113 dropped — correct. (c) gate/SKILL.md line 116: rewrite promised "see verbatim quote + suggested rewrite immediately below this table" but the rewrite text is NOT present in the plan — see new MAJ-A. |
| M1 | Resolver error contract under-specified | Resolved | Six exception sub-paths (rule-1, 2a, 2b, 2c, 2d, 3); CLI exit codes enumerated; per-file edit template includes explicit error-handling clause (display stderr, fall back to root, ask user — exit-2 ≠ fatal). |
| M2 | Real-repo tests silently skip | Resolved | Snapshot file `_inflight-snapshot.txt` (Tier 1 via MAJ-5 carve-out); case (s) hard-asserts each row matches live FS w/ "did this task get finalized?" diagnostic; T-08 case (e) loud-fails on missing dir (no silent skip). |
| M3 | CLAUDE.md grep doc carve-out unbounded | Resolved | T-09 split into a1/a2/a3 with bounded-line-range check (matches must fall inside `### Multi-stage tasks` heading line range); a3 detects gate/SKILL.md prose form. Machine-verifiable, not verbal. |
| M4 | architecture-critic-N.md routing silent | Resolved | Pre-resolved as task-root-always; per-file edit template explicit; T-09 grep (c) carves out; architect/SKILL.md line 303 inline comment specified; Q-01 documents the explicit S-04 forward-pointer with scope boundary. |
| M5 | Tier 1 fixture carve-out missing | Resolved | T-03 Edit B adds `- dev-workflow/scripts/tests/fixtures/path_resolve/**` to Tier 1 Source-files block; the `**` glob covers the snapshot file too. Anchor (immediately after `verify_subagent_dispatch.md` bullet) is precise. |
| M6 | Substring multi-match silent first-match | Resolved | `_lookup_stage_by_name` collects ALL matches and raises ValueError on `len > 1` w/ explicit diagnostic ("matches N stages: ... — disambiguate by using --stage <integer>"); T-04 case (v) and T-08 case (g) cover unit + CLI paths; D-04 updated; R-03 mitigation column rewritten. |
| m1 | T-10 abort criteria verbal-only | Resolved | Three explicit numeric criteria (phase-creep substring detection, 90s wall-clock cap, $1.00 cost cap); explicit `verified-with-abort` outcome for partial-completion case. |
| m2 | Naming convention rename for case (s) | Resolved | Renamed to `test_inflight_task_grandfathering_real_repo`. |
| m3 | install.sh line-content anchors | Resolved | Anchor 1 + 2 reformulated as line-content (`for script_file in summarize_for_human.py validate_artifact.py; do`) — robust to parent-stage-2 merge ordering. |

## Issues

### Critical (blocks implementation)

- **Issue C-A — `rollback/SKILL.md` ALSO hardcodes plan path; missing from T-05's expanded 10-file edit list**
  - What: Round-1 C1 expanded T-05 from 8 to 10 files (added run + architect). An independent grep across `dev-workflow/skills/` for `<task-name>/current-plan.md` references reveals an 11th omission: `dev-workflow/skills/rollback/SKILL.md` line 53 (`Read .workflow_artifacts/<task-name>/current-plan.md to understand task structure`) and line 65 (same prose, in Step 1 of Process). These are LOAD-BEARING reads — `/rollback` reads the plan to understand task structure and map commits to plan tasks.
  - Where: T-05 SKILL-edit task table (rows 1–10); T-09 grep (a1) ("expected: EXACTLY 0 matches"); session-state record.
  - Why it matters: After stage-3 ships, if a user invokes `/rollback stage 3 of <task>`, the rollback agent's session-bootstrap step 1 (and Process Step 1) will read `<task>/current-plan.md` from the task root, NOT from `<task>/stage-3/current-plan.md`. For a stage-N task, the task-root path either (a) does not contain a plan, OR (b) contains a stale parent-feature plan from a different stage. The agent then builds an INCORRECT commit-to-task map and may revert the wrong commits. This is exactly the same class of bug round-1 C1 named: "an orchestration/operational skill referencing the plan by name silently breaks after the resolver lands." Lesson 2026-04-13 ("when changing how a skill resolves paths, the orchestrator skills referencing it by name must also be updated") applies again — to a DIFFERENT skill this time. Lesson 2026-04-14 ("/critic should explicitly check all files that the newly-added skill references by name") is the canary that should have caught this; round-2 audit was incomplete in the same way round 1 was.
  - Suggestion: Expand T-05 from 10 to 11 rows. Add `rollback/SKILL.md` (2 anchors: line 53 bootstrap step 1; line 65 Process Step 1). The per-file edit template (resolver-prose w/ error-handling clause + D-03 carve-outs) applies directly — same template as the other ten. Update T-09 grep (d) lower bound from "≥10 matches" to "≥11 matches"; update T-08 case (b) "for each of the 10 SKILL.md files" → "for each of the 11"; update T-08 case (c) similarly. Update R-02 row text from "10 SKILL.md files (...expanded from 8 to 10...)" to "11 SKILL.md files (...expanded from 8 to 11 — round-2 added run + architect; round-3 added rollback...)." Also explicitly DOCUMENT the audit method in the Decisions section: how T-05's enumeration was verified exhaustive (e.g., "ran `grep -rn '<task-name>/current-plan' dev-workflow/skills/' AND `grep -rn '<task-name>/critic-response' dev-workflow/skills/' AND `grep -rn '<task-name>/review-' dev-workflow/skills/'; deduplicated by file; cross-referenced against this 11-row list"). The audit-method documentation is the canary against future omission of this same class of file.

### Major (significant gap, should address)

- **Issue MAJ-A — gate/SKILL.md line 116 rewrite text promised but not actually provided in the plan**
  - What: T-05's row 8 (gate/SKILL.md) says line 116 needs "REWRITE prose for grep-detectability — see verbatim quote + suggested rewrite immediately below this table." However, no verbatim quote or suggested rewrite text appears below the table. The text below the table is the GENERIC per-file edit template applied to all 10 (now 11) files. The plan has T-09 grep (a3) checking that `task subfolder for artifacts` does NOT appear in gate/SKILL.md after the edit, AND T-08 case (c) checking the same. But neither test specifies what the new line 116 prose SHOULD look like in positive form — only what it should NOT contain. An implementer running through T-05 row 8 will read the table, scroll down, and find nothing matching "see verbatim quote + suggested rewrite immediately below this table." Two possible failure modes: (a) the implementer writes a rewrite that satisfies grep (a3) but does NOT make `<task-name>/current-plan.md` adjacent (the original C3 motivation — making the residual-hardcode grep CAN catch future regressions); (b) the implementer just inserts the per-file template at line 116 and the surrounding prose loses its meaning ("The task subfolder for artifacts (...) — Resolve the artifact path via ~/.claude/scripts/path_resolve.py..." — not idiomatic for that section's gate-checks-list context).
  - Where: T-05 row 8; the gap immediately below the SKILL-edit table.
  - Why it matters: The whole point of the C3 round-2 fix was to give the implementer EXACT edit boundaries (per round-1 C3's Lesson 2026-04-23 + 2026-04-13 framing). Promising a rewrite then not delivering it RECREATES the C3 ambiguity in a different form. Specifically: T-09 grep (a3) is the canary, but a canary that asserts a NEGATIVE (the old prose is gone) without specifying the POSITIVE replacement is half-broken — the implementer can satisfy grep (a3) by simply DELETING line 116 entirely, which would also break the gate's bullet list at that point.
  - Suggestion: Add a verbatim-rewrite block immediately below the SKILL-edit table. Quote the current line 116 verbatim:
    ```
    Current: - The task subfolder for artifacts (all under `.workflow_artifacts/<task-name>/`: architecture.md, current-plan.md, critic responses, review docs)
    ```
    Then specify the exact replacement in a fenced block, e.g.:
    ```
    Suggested rewrite: - The task subfolder for artifacts: `<task-root>/architecture.md`, `<task-root>/cost-ledger.md`, plus `<task_dir>/current-plan.md`, `<task_dir>/critic-response-<round>.md`, `<task_dir>/review-<round>.md`, `<task_dir>/gate-*.md` — where `<task_dir>` is computed via `path_resolve.py` (see "Multi-stage tasks" in CLAUDE.md).
    ```
    The replacement satisfies BOTH (i) T-09 grep (a3) (no `task subfolder for artifacts` substring), AND (ii) T-08 case (c) (no `<task-name>/current-plan` literal — the new form uses `<task_dir>/current-plan.md` which would not match the regex), AND (iii) preserves the bullet-list semantics of that gate-checks section.

- **Issue MAJ-B — T-05's audit-method gap repeats round-1 C1's incompleteness in a new direction**
  - What: Round-1 C1 found that the architecture's 8-file sketch was incomplete (missed run + architect). Round 2 added those two; C-A above shows the round-2 audit ALSO missed rollback. Three rounds of incompleteness on the same enumeration suggests the AUDIT METHOD itself is the failure mode, not the specific file count. The plan currently provides no explicit reproducible audit script (e.g., `grep -rln '<task-name>/current-plan' dev-workflow/skills/`) that future maintainers can re-run. The 11-row table (after C-A) is a static enumeration that will go stale the next time someone adds a new skill, OR adds a new artifact (like `architecture-critic-N.md`) that lives at the task root, OR extends an existing skill with a new path reference.
  - Where: T-05 prose; T-09 grep procedure; Decisions section.
  - Why it matters: Lesson 2026-04-22 (fixture-first traps when baselines rot) — the static 11-file enumeration IS a baseline that will rot. The structural test (T-08 case (c)) already greps the file list — but the file list itself is hardcoded into the test (the implicit "10 files" / "11 files" loop). When a NEW skill is added next quarter, the test loop won't pick it up. This is a S-04+ / future-stage concern, but the round-2 plan can address it by: (a) computing the file list dynamically (`dev-workflow/skills/*/SKILL.md`) inside the test rather than hardcoding 10/11 paths, AND (b) adding a positive assertion ("each SKILL.md that contains `<task-name>/current-plan.md` MUST also contain `path_resolve.py`") that doesn't depend on a static enumeration.
  - Suggestion: (a) Modify T-08 case (b) and (c) to enumerate `dev-workflow/skills/*/SKILL.md` dynamically (use `glob.glob` or `pathlib.Path.glob`). Each loop iteration: assert that IF `<task-name>/current-plan.md` appears in the file's body, THEN `path_resolve.py` ALSO appears in the same file. (b) Add explicit text to the Decisions section (a new D-07 or extend D-01): "T-05's 11-file enumeration was derived by grep audit on date 2026-04-26; future maintainers MUST re-run `grep -rln '<task-name>/current-plan' dev-workflow/skills/` before adding new SKILL.md files and update the test loop accordingly. The dynamic enumeration in T-08 case (b)/(c) is the canary against drift." (c) This converts a static-enumeration anti-pattern into a structural property the test enforces — same lesson as 2026-04-22 fixture-stability applied to the path-residual sweep.

### Minor (improvement, use judgment)

- **Issue min-A — Q-03's SYNC WARNING confirmation flagged as "plan assumes" — should be a positive confirmation, not implicit**
  - Suggestion: Q-03 in Notes says "Plan assumes 'yes — no SYNC WARNING update needed' per the principle that path-resolution is a body edit applied identically to both files. Confirm?" — but Q-03 is in the user-attention list, so the answer is technically deferred to the user. Round 2 should either (a) make this an explicit Decision (D-XX: "Path-resolver edits land in revise/SKILL.md and revise-fast/SKILL.md at the same anchors; SYNC WARNING does NOT need extension because path resolution is a body edit, not an intentional difference") and remove Q-03 from the user-attention list, OR (b) ADD a T-05 acceptance check that grep `revise-fast/SKILL.md` for the existing SYNC WARNING block and confirms it does not list the path-resolver edit as an intentional difference. Cosmetic — does not block implementation.

- **Issue min-B — D-07 absent: the audit method itself should be a Decision**
  - Suggestion: If MAJ-B is fixed via the dynamic-enumeration approach, document the new audit method as D-07 explicitly. This makes the rationale discoverable from the Decisions section (which is what reviewers and future maintainers read) rather than buried in T-05 prose.

## Notes

### What's good (preserve in round 3)

- Round-2 production-shape verification (caveman has arch.md WITHOUT decomp; artifact-format-architecture has NO arch.md; v3-stage-3/4-smoke have arch.md WITH decomp) was done correctly — all four production folders' shapes match the new fixture corpus byte-for-byte. C2 is genuinely closed.
- The deviation flag on plan/SKILL.md line 16 was the correct call. Independent verification confirms line 16 = "Read the task subfolder", line 17 = "Append your session to the cost ledger". The round-1 critic was wrong on this anchor; the reviser was right to push back. This is exactly the lesson 2026-04-26 pattern (deviation-from-critic-suggestion documented in revision history with verification).
- The `_inflight-snapshot.txt` mechanism (M2 fix) is structurally sound — the snapshot IS the contract, the live test fails LOUDLY on mismatch with a "did this task get finalized?" diagnostic. Tier-1 carve-out via the `**` glob in MAJ-5 covers the snapshot transitively. Architecture R-09's "fails LOUDLY" is now actually enforced.
- The T-09 grep tightening (M3 fix) — three structured greps with explicit bounded-line-range check on CLAUDE.md — is a real upgrade over round-1's verbal "may legitimately contain" hedge. Machine-verifiable doc carve-out.
- M4's pre-resolution of architecture-critic-N.md routing as task-root-always is the right call. It removes an S-04 dependency on revisiting S-03's edits.
- M6's transition from silent first-match to error-on-multi-match is the correct UX: it converts a UX-visible silent-routing failure into a user-recoverable input ambiguity with a clear error message.
- T-10's three numeric abort criteria (m1 fix) are appropriately calibrated: 90s wall-clock + $1.00 cost + phase-creep substring detection. The `verified-with-abort` outcome covers the realistic case where the path observation completes before the orchestrator drifts.

### Loop-detection signal

Round-1 issue titles: C1 "/run and /architect SKILL.md missing"; C2 "mixed/ fixture doesn't match"; C3 "anchor-line precision"; M1–M6 + m1–m3.

Round-2 NEW issue titles: C-A "rollback/SKILL.md ALSO hardcodes plan path; missing from T-05's expanded 10-file edit list"; MAJ-A "gate/SKILL.md line 116 rewrite text promised but not actually provided"; MAJ-B "T-05's audit-method gap repeats round-1 C1's incompleteness in a new direction".

**No same-title reappearance.** C-A is a same-CLASS reappearance (orchestration-skill omission) but the specific skill (`rollback/`) is different from the round-1 omissions (`run/` + `architect/`). The orchestrator's `/thorough_plan` loop-detection rule keys on title equality, not class. The class-level pattern IS a signal for the human reviewer / future planner: "C1 was 8→10, round 2 audit found 11; the audit method is the failure mode, not the count" — this is what MAJ-B captures explicitly. Recommend MAJ-B's audit-method fix as a permanent guardrail; if accepted, round 3 should converge in one pass (C-A is mechanical; MAJ-A is mechanical; MAJ-B is small).

Round 1: 3 CRIT + 6 MAJ + 3 MIN = 12 issues. Round 2: 1 CRIT + 2 MAJ + 2 MIN = 5 issues. **Strict decrease in count + severity** — round 1 found systemic gaps; round 2 finds residuals + a meta-finding (audit method). This matches the expected convergence trajectory for a Large-profile task. Recommend ONE more revision round to clear C-A + MAJ-A + MAJ-B; if round-3 produces fewer than 2 new issues with no same-title-or-class repeat, the orchestrator can advance to /implement.

### Calibration note

Round 1 was thorough. Round 2 surfaces a smaller set, mostly mechanical fixes plus one meta-finding (MAJ-B) about the audit method itself. The plan is not in danger of escalating to "fundamentally wrong"; it is in the normal large-profile convergence regime. Round-3 verdict prediction: PASS likely if C-A + MAJ-A are addressed AND MAJ-B's dynamic-enumeration suggestion is adopted (or explicitly rejected with rationale).

## Scorecard

| Criterion | Score | Notes |
|-----------|-------|-------|
| Completeness | fair | C-A: rollback/SKILL.md still missing from T-05 list. Audit-method gap (MAJ-B) is the systemic root cause. |
| Correctness | good | Anchor lines re-verified (plan/SKILL.md line 16 confirmed correct against round-1 critic's mistake); production fixture shapes match real folders byte-for-byte; resolver semantics complete (rule 1/2a/2b/2c/2d/3 enumeration + CLI exit codes). |
| Integration safety | good | D-03 + D-03 corollary (architecture-critic-N.md task-root) well-anchored; M4 pre-resolves Q-01 cleanly; cost-ledger and architecture.md both explicitly carved out. |
| Risk coverage | good | R-01..R-10 each map to a test or grep; R-09's snapshot-based hard-assert closes the silent-skip gap; R-03's multi-match raise closes the silent-route gap. |
| Testability | good | 22 unit cases + 7 e2e cases; case (s) and case (e) both fail loudly on snapshot mismatch; case (v) and case (g) cover multi-match. Only weakness: dynamic SKILL.md enumeration (MAJ-B) would tighten further. |
| Implementability | fair | C-A leaves a missing edit row; MAJ-A leaves an undefined rewrite text; the implementer would need to invent the line-116 prose. Both are mechanical to fix in round 3. |
| De-risking | good | T-10 cost cap is concrete (3 numeric criteria); fixture-first ordering preserved; SKILL-edit gated on T-04 PASS; the resolver's exception contract is fully enumerated. |
