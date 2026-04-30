# V-Trip-Rate Baseline — 2026-04-30

Stage 4 of pipeline-efficiency-improvements (T-14). This document captures:
1. The BEFORE baseline (manual hand-count from pre-Stage-4 finalized artifacts)
2. A dry-run of `measure_v_trip_rate.py` against pre-Stage-4 sessions (expected: all zeros)

## BEFORE Baseline (Manual Hand-Count)

Artifacts inspected: the last 5 finalized `critic-response-*.md` and `review-*.md` files
from stages 1–3. These artifacts were run through `validate_artifact.py`; any V-04/V-05/V-06
failures would have been documented as `format-kit-skipped` warnings.

### Artifacts Inspected

| Stage | Artifact | format-kit-skipped event? | V-NN |
|-------|----------|--------------------------|------|
| stage-1 | critic-response-1.md | No | — |
| stage-1 | critic-response-2.md | No | — |
| stage-1 | critic-response-3.md | No | — |
| stage-1 | review-1.md | **Yes** | V-06 (Step 2 Agent subagent unavailable; ## For human hand-written) |
| stage-1 | review-2.md | **Yes** | V-06 (Step 2 Agent subagent unavailable; ## For human hand-written) |
| stage-2 | critic-response-1.md | No | — |
| stage-2 | critic-response-2.md | No | — |
| stage-2 | critic-response-3.md | No | — |
| stage-2 | review-1.md | No | — |
| stage-2 | review-2.md | No | — |
| stage-3 | critic-response-1.md | No | — |
| stage-3 | critic-response-2.md | No | — |
| stage-3 | review-1.md | No | — |

### BEFORE Summary

- Total Class B write attempts inspected: 13
- format-kit-skipped events: **2** (both V-06; both in stage-1; root cause: Haiku Agent subagent unavailable in harness environment)
- BEFORE trip rate: **2/13 ≈ 15.4%**

Note: Both events share a single root cause (Step 2 Agent dispatch unavailable) rather
than V-04/V-05/V-06 author errors. Stage 4's pitfall reminder targets authoring errors;
Step 2 dispatch failure is tracked separately via the `fallback_fires` counter.

## Dry-Run Output (Script)

```
python3 quoin/scripts/measure_v_trip_rate.py --tasks pipeline-efficiency-improvements --json
```

Result (2026-04-30):
```json
[
  {
    "task": "pipeline-efficiency-improvements",
    "sessions": 1,
    "fallback_fires_after_stage4": 0,
    "total_b_writes": 1,
    "trip_rate": 0.0,
    "_surface2_col7_sum": 0
  }
]
```

Expected: all zeros (pre-Stage-4 sessions lack the `fallback_fires` field). Script ran
without error, demonstrating it is operational.

## AFTER Measurement Protocol

Run after 5 post-merge Class B writes (plan/architect/revise/revise-fast/review/critic/gate
invocations that produce validated artifacts):

```
python3 quoin/scripts/measure_v_trip_rate.py --since 2026-04-30 --json
```

Save output to `quoin/docs/v-trip-rate-baseline-2026-04-30-after-N.md`.
Acceptance gate (architecture stage-four): AFTER trip rate ≤ 50% of BEFORE trip rate.
BEFORE trip rate: **15.4%** → AFTER target: **≤ 7.7%**.

If BEFORE drop metric is dominated by Step 2 dispatch failures (not authoring errors),
the acceptance gate should be evaluated against authoring-error trips only (V-04/V-05/V-06
fires from body composition, not dispatch). Per-V-NN granularity is not available in Stage 4;
a future stage can add per-V-NN counter fields if this distinction becomes load-bearing.
