## Section 1 — Measurement

Profile filter: medium
Tasks analysed — Opus track: 0, Fast (Sonnet) track: 5

| Metric | Opus (/revise) | Fast (/revise-fast) |
|--------|---------------|---------------------|
| Tasks  | 0 | 5 |
| Mean revise cost | $0.0000 | $21.5652 |
| Stderr revise cost | $0.0000 | $3.3472 |
| Mean round count | 0.0 | 1.2 |

**Task name / stage count:**

- init-workflow-quickstart-decoupling (Fast, 1 stage(s))
- dev-install-decoupling (Fast, 1 stage(s))
- critic-on-architecture (Fast, 1 stage(s))
- claude-md-trim (Fast, 1 stage(s))
- triage (Fast, 1 stage(s))

**Recommendation:** INSUFFICIENT DATA

**Caveats:** Need ≥3 tasks per track. Have 0 opus, 5 fast. Re-run after 5 more Medium tasks land.

<!-- AUTO-GENERATED — do not edit below -->

## Section 2 — Decision

**Verdict: INSUFFICIENT DATA — preserve `/revise-fast` and re-measure.**

As of 2026-04-30, the discovery glob finds 8 Medium-profile finalized tasks (with `*.bak` and dot-prefixed directories filtered out); the script samples the 5 most recent by root-ledger mtime (the default `--max-tasks 5` cap). Of those 5 sampled tasks, all 5 used `/revise-fast` (Sonnet); the remaining 3 (`task-cost-tracking`, `run-skill`, `artifact-consolidation`) fall outside the sample window or have no revise-phase ledger rows. There are zero finalized Medium tasks (sampled or otherwise) that used `/revise` (Opus). The comparison requires ≥3 opus-track tasks; re-run this script after the next 5 Medium tasks land (some may use strict mode, which would add opus-track entries). Until then, the default Medium mode (Sonnet `/revise-fast`, rounds 2+) is preserved unchanged.

**Crossover count audit (folded from plan T-09 / MIN-4):** The `mean_fast_rounds` for the 5 fast-track tasks is 1.2, meaning an average of 1.2 revise-fast sessions per task. Each revise-fast round introduces one model crossover (Sonnet revise → Opus critic). The critic-to-implement boundary also crosses tiers. So a typical Medium task with 1-2 revise-fast rounds has 2-3 total model crossovers. This is the minimum achievable given the Medium-profile architecture (Opus plan → Sonnet revise-fast × N → Opus critic × N → Sonnet implement). No reordering of the critic loop would reduce this below 2 crossovers. Conclusion: the crossover count is inherent to the design and NOT a candidate for round-reordering optimization. No follow-on T-11 work is needed.
