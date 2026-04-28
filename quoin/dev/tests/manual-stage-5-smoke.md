# Manual Stage 5 Smoke — T-10

Date: 2026-04-27
Branch: feat/quoin-stage-5

## Phase 1 — V-06/V-07 regression smoke (3 synthetic Class B artifacts)

Haiku Agent subagent dispatched for each summary. `validate_artifact.py --type <type>` used
(filename-based detection does not match synthetic prefixes; `--type` override is the
correct production analog since real Class B writers invoke the validator on `<path>.tmp`
which always has the canonical filename).

| Artifact | Type | validate_artifact.py exit | ## For human lines | V-06 IN_RANGE |
|----------|------|--------------------------|-------------------|---------------|
| synthetic-a-plan.md | current-plan | 0 (PASS) | 1 (single para) | ✓ |
| synthetic-b-arch.md | architecture | 0 (PASS) | 1 (single para) | ✓ |
| synthetic-c-review.md | review | 0 (PASS) | 1 (single para) | ✓ |

All 3 PASS. Summary blocks are dense single paragraphs — 1 physical line each, within [1,12].

Haiku character counts: A=397, B=475, C=469.

## Phase 2 — Canonicalized Step-2 cross-check

Command run:
```
canon() { sed -n '/^\*\*Step 2:/,/^\*\*Step 3:/p' "$1" | sed '$d' | sed 's/<plan-path>/<path>/g'; }
# compare plan, revise, revise-fast, review vs architect
```

Results:
- architect vs plan: IDENTICAL ✓
- architect vs revise: IDENTICAL ✓
- architect vs revise-fast: IDENTICAL ✓
- architect vs review: IDENTICAL ✓
- revise vs revise-fast (raw, pre-sed): IDENTICAL ✓

Extracted block size: 27 lines (architect). All 4 canonicalized diffs = 0 lines. PASS.

## Phase 3 — Stability check (synthetic A, 3 runs)

Same fixture body (synthetic-a current-plan). All 3 runs dispatched to Haiku Agent subagent.

| Run | Line count | Char count | V-06 |
|-----|------------|------------|------|
| 1 | 6 | 397 | ✓ |
| 2 | 6 | 397 | ✓ |
| 3 | 6 | 397 | ✓ |

Variance: 0 lines (well within ±2 acceptance threshold). Runs 2 and 3 byte-identical to run 1.
PASS — no drift observed.

Note: "6 lines" above counts logical sentences in the Haiku output (the summary is a 6-sentence
paragraph delivered as a single physical line). validate_artifact.py V-06 counts non-blank
physical lines → 1, which satisfies the [1,12] constraint.

## Optional: Agent overhead

Not instrumented in this run (JSONL parsing not done). Noted per plan as optional; no block.

## Summary

All T-10 acceptance criteria MET:
- [x] validate_artifact.py exits 0 on all 3 fresh artifacts
- [x] ## For human block has 1-12 non-blank lines (V-06 hard cap)
- [x] First ## heading after frontmatter is ## For human (V-06 ordering)
- [x] Canonicalized Step-2 cross-check returns 0 diff lines across all 4 comparisons
- [x] Stability check passes — 3-run variance = 0 lines, all 3 PASS V-06
