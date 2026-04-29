# Session — 2026-04-29 — pipeline-efficiency-improvements — stage-2

## Status
completed — Stage 2-alt /review round 2 verdict APPROVED; ready for /end_of_task

## Current stage
review

## Completed in this session

- ✓ **T-01** `quoin/scripts/build_preambles.py` — builder script; commit `3c7d157` + fix `4dc1846` (lazy-import yaml, drop generated_at).
- ✓ **T-02** `quoin/dev/tests/test_preamble_freshness.py` — 21 parametrized CI tests; commit `3c7d157`.
- ✓ **T-03** Generated 7 preamble.md files (post-fix sizes: critic=4384B, revise=4384B, revise-fast=4389B, plan=4382B, review=4384B, architect=4387B, gate=270B).
- ✓ **T-04** Additive bootstrap step in 7 child SKILL.md files; pre/post grep parity verified; commit `d9a3d89` + `f6a8fa6` (sync contract test fix) + `4dc1846` (cross-ref bumps).
- ✓ **T-05** install.sh integration; commit `5c4ed32`.
- ⏳ **T-06** DEFERRED — soak measurement; documented in post-implement-soak-2026-04-29.md; post-merge follow-up.
- ✓ **T-07** quoin/CLAUDE.md docs; commit `d3a0c3f`.
- ✓ **T-08** Smoke verification: 432 passed / 8 failed (all pre-existing) / 1 skipped; Stage 2-alt 67/67 pass; commit `8c2a6bc`.
- ✓ **/review round 1** — verdict CHANGES_REQUESTED; review-1.md.
- ✓ **fix commit** `4dc1846` — addressed MAJOR-1 + 5 MINOR.
- ✓ **/review round 2** — verdict APPROVED; review-2.md.

## Unfinished work

Post-merge follow-ups (non-blocking):

1. **Soak measurement** — run 5 cross-spawn /critic invocations within a 5-minute TTL window; update post-implement-soak-2026-04-29.md with empirical cache-read / cache-creation deltas.
2. **`total_bytes` rename** — to `body_bytes` (or add `file_bytes`); coordinate with freshness-hash invalidation.
3. **Doc-hygiene sweep** — fix pre-existing "above"/"below" directional typo in critic/SKILL.md:16 (round-2 MINOR-1; cosmetic).

## Commits

- `3c7d157` T-01/T-02/T-03: builder + CI test + 7 preambles
- `d9a3d89` T-04: additive bootstrap step + bootstrap step test
- `5c4ed32` T-05: install.sh 4-edit integration
- `d3a0c3f` T-07: CLAUDE.md documentation + test
- `f6a8fa6` fix: revise/revise-fast sync contract test update
- `8c2a6bc` chore: T-08 mark all tasks complete
- `4dc1846` fix: address /review-1 MAJOR-1 + 5 MINOR findings

## Cost
- Session UUID: 0e58a4c8-dbf3-4a95-9619-77cc72222211
- Phase: review
- Recorded in cost ledger: yes (rows for round 1 and round 2)

## Decisions made

- Round-2 verdict APPROVED. The MAJOR install.sh pyyaml regression is fully resolved by lazy-importing yaml only in --check mode and emitting frontmatter via stdlib templating. End-to-end verified: subprocess invocation with yaml import blocked exits 0; `--check` returns 7 with a clear `pip install pyyaml` message.
- `generated_at` field removed from preamble frontmatter — eliminates non-determinism and stops `bash install.sh` from dirtying the working tree on every run. The TestDeterminism test is now stricter (full byte comparison) and still passes.
- Round-2 MINOR (pre-existing "above"/"below" typo in critic/SKILL.md) deferred — not introduced by Stage 2-alt; cosmetic.
- Plan T-06 soak DEFERRED stays acceptable per plan's measurement-inconclusive escape hatch; mechanism is correctness-neutral.
