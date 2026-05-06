# PROVENANCE — v2-historical baseline fixtures

Extracted from git history for Stage 5 cost proxy (T-01a). All files are real pre-v3
workflow artifacts — no hand-curation. Session type has no pre-v3 git history (gitignored
from project inception), so it is marked INSUFFICIENT_HISTORICAL_DATA.

**Comparison note:** v2 artifacts below were produced by larger/more-complex tasks than
the v3 smoke artifacts used as the v3 side. The byte deltas are therefore NOT matched-task
comparisons. The proxy script emits `SAVINGS_INDETERMINATE` when this caveat applies.
The decision report (T-03) discusses this limitation and whether architectural-cleanup
benefits justify v3 independent of byte savings.

| File | Commit | Original path | Bytes |
|------|--------|---------------|-------|
| current-plan.md | be9c51d | cost-reduction/stage-0-measure/current-plan.md | 38585 |
| critic-response.md | be9c51d | cost-reduction/stage-0-measure/critic-response-1.md | 18440 |
| architecture.md | be9c51d | cost-reduction/architecture.md | 75225 |
| review.md | 905cf11 | cost-reduction/stage-3-model-tiering/review-1.md | 10628 |
| gate.md | 8f50650 | cost-reduction/stage-1-caching/gate-thorough-plan-2026-04-12.md | 3677 |
| session.md | N/A | INSUFFICIENT_HISTORICAL_DATA — session files were gitignored pre-v3 | 29 |
