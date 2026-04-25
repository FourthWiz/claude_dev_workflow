# v2→v3 Savings Measurement Report

Script SHA: b1a9c50f3ae90d1bc07422ba9b155d14b7a2d944

**Comparison caveat:** v2 baselines are real historical artifacts from the cost-reduction project (tasks of greater complexity than the v3 Stage 4 smoke). The byte deltas are NOT matched-task. See `dev-workflow/scripts/tests/fixtures/v2-historical/PROVENANCE.md`.

## Per-artifact results

| Type | v2 bytes | v3 bytes | delta | EST_reads | savings/task |
|------|----------|----------|-------|-----------|-------------|
| current-plan | 38585 | 12775 | +25810 | 8 | $0.08 |
| architecture | 75225 | 9417 | +65808 | 6 | $0.15 |
| critic-response | 18440 | 8199 | +10241 | 3 | $0.01 |
| review | 10628 | 5701 | +4927 | 4 | $0.01 |
| gate | 3677 | 2150 | +1527 | 2 | $0.00 |
| session | INSUFFICIENT_HISTORICAL_DATA | 498 | N/A | 12 | N/A |
| Total | — | — | — | — | $0.25 |

## Sensitivity

Total savings at different EST_READS_PER_TASK scaling factors (addresses R-01 noise floor):

| Scale | Total savings/task | Threshold met (≥ $1.00)? |
|-------|--------------------|--------------------------|
| EST × 0.5 (pessimistic) | $0.12 | NO |
| EST × 1.0 (central) | $0.25 | NO |
| EST × 2.0 (optimistic) | $0.49 | NO |

## Notes

- Rows excluded from total (INSUFFICIENT): 1
- Rows with negative delta (v3 > v2): 0

## Decision

<decision>SAVINGS_MISS</decision>

All three Sensitivity rows are below $1.00/task (EST×0.5: $0.12, EST×1.0: $0.25, EST×2.0: $0.49).
The dominant artifact type is architecture (contributes $0.15 of the $0.25 total), but the v2
baseline for architecture (75 KB from the cost-reduction project) is from a much more complex task
than the v3 Stage 4 smoke architecture (9 KB) — this comparison overstates the savings. If the
baselines were matched by task complexity, the deltas would be smaller and the result would still
be SAVINGS_MISS, or possibly SAVINGS_INDETERMINATE.

See the Sensitivity section: even at 2× optimistic read counts, the total reaches only $0.49/task —
still well below the $1.00/task threshold. The $1.00 threshold is therefore not met under any
plausible estimate.

**Architectural-cleanup benefits justify v3 independent of cost savings.** v3 format delivers:
consistent structural validation (V-01..V-07), machine-readable `## For human` summaries for gate
review, deterministic artifact-type detection, and a common section vocabulary across all skills.
These benefits stand regardless of this SAVINGS_MISS verdict. A future Stage 6 (matched-task
re-measurement after 2-3 months of production use) is recommended to get cleaner data.
