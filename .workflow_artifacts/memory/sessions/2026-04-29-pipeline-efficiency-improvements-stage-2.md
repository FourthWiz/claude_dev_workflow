# Session — 2026-04-29 — pipeline-efficiency-improvements — stage-2

## Status
complete — Stage 2-alt (on-disk preamble read) fully implemented; ready for /review

## Current stage
Implementation complete

## Completed in this session

- **T-01** `quoin/scripts/build_preambles.py` — builder script with all 7 targets, exit codes 3/4/5/6/7, --dry-run/--check, atomic writes. 8 unit tests (test_build_preambles.py), all pass.
- **T-02** `quoin/dev/tests/test_preamble_freshness.py` — 21 parametrized CI tests (presence, freshness via git hash-object, size budget), all pass.
- **T-03** Generated 7 preamble.md files: critic=4421B, revise=4421B, revise-fast=4426B, plan=4419B, review=4421B, architect=4424B, gate=307B. All < 6144 budget. Committed with git add -f.
- **T-04** Additive bootstrap step edits to 7 child SKILL.md files. Pre/post grep counts verified unchanged. Cross-skill 7-count acceptance grep returns exactly 7. test_preamble_bootstrap_step.py (34 tests), all pass. Fixed revise/revise-fast sync contract test to allow intentional preamble-path diff.
- **T-05** install.sh: Step 2a, preamble.md conditional copy, build_preambles.py in v3-scripts loop, summary line (4 edits).
- **T-06** DEFERRED — soak requires live multi-spawn measurement; documented in post-implement-soak-2026-04-29.md.
- **T-07** quoin/CLAUDE.md: new subagent-preamble sub-section + Tier 1 carve-out disambiguation. test_claude_md_preamble_section.py (4 tests), all pass.
- **T-08** Smoke: 432 passed / 8 failed (all pre-existing) / 1 skipped. Stage 2-alt tests: 67/67. Rollback rehearsal: PASS.

## Commits

- `3c7d157` T-01/T-02/T-03: builder + CI test + 7 preambles
- `d9a3d89` T-04: additive bootstrap step in 7 SKILL.md files + bootstrap step test
- `5c4ed32` T-05: install.sh 4-edit integration
- `d3a0c3f` T-07: CLAUDE.md documentation + test
- `f6a8fa6` fix: revise/revise-fast sync contract test update

## Unfinished work

T-06 soak measurement (deferred, non-blocking) — requires fresh session post-merge, 5 consecutive /critic spawns within 5-min TTL window.

## Cost
- Session UUID: 0e58a4c8-dbf3-4a95-9619-77cc72222211
- Phase: implement
- Recorded in cost ledger: yes (row appended at session start)
