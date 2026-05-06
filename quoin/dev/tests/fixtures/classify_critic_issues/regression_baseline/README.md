# Held-out regression baseline

This directory is intentionally empty at Stage 1 ship time.

Post-merge soak (T-12, out of scope for Stage 1): once ≥5 real critic-responses
accumulate in production use, copy them here and flip `--enable-bailout=false` to
`--enable-bailout=true` in the SKILL.md edits only after accuracy on this corpus
reaches ≥95%.

Do NOT copy the training corpus (`../training/`) here — that would contaminate the
held-out baseline.
