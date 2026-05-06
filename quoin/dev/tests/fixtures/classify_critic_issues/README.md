# Training Corpus — classify_critic_issues.py

**TRAINING DATA — NOT a regression baseline.**

This directory contains 17 finalized critic-response files used to tune the
classifier's regex/keyword list in `classify_critic_issues.py`. These files are
the training corpus for the bullet-shape union parser (Shapes A–E) and the
structural/mechanical classifier.

Per lessons-learned 2026-04-22: historical LLM output is not a stable contract
under upstream revision. The regression baseline is the held-out 5+ post-merge
corpus in `regression_baseline/`, NOT this directory.

## Corpus composition

Corpus size: 17 critic-response files

| Stage | Files | Stage name |
|-------|-------|------------|
| stage-1 | 3 | quoin-foundation Stage 1 (§0 model dispatch preamble) |
| stage-2 | 3 | quoin-foundation Stage 2 (Class B writer wiring) |
| stage-3 | 5 | quoin-foundation Stage 3 (path-resolver) |
| stage-4 | 3 | quoin-foundation Stage 4 (fixture filename auto-detection) |
| stage-5 | 3 | quoin-foundation Stage 5 (native Haiku summarizer) |

Total: 17 files; ≈108 CRIT+MAJ+MIN+NIT bullets total (bracket≈30, no-bracket-em-dash≈39,
Issue-prefix≈33, full-word-severity≈6, colon-form≈2 — empirically verified by
`audit_corpus_coverage.py` at /implement time).

## Disagreement headroom

Per plan T-04 spec: ≥95% per-issue agreement on CRIT+MAJ bullets.

Per `labels.json`, there are approximately 46 CRIT+MAJ issues across the corpus.
At 46 issues, ≥95% = ≤2 disagreements allowed (floor(46×0.05)=2).

(Update this count after `labels.json` is finalized with actual numbers from the
labeling pass.)

## Ambiguity policy

See `labels.notes.md` for rationale on ambiguous calls. Labeler: IvGor, 2026-04-28.

Subsequent labelers adding held-out corpus files to `regression_baseline/` should
follow the same policy documented in `labels.notes.md`.
