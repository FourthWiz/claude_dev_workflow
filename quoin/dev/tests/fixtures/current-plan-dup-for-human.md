---
task: dedup-test
profile: small
branch: feat/dedup
plan_round: 1
date: 2026-04-24
---
## For human

Single summary sentence here.

## For human

Duplicate heading that should not appear in a well-assembled file.

## State

```yaml
phase: planned
last_task: ~
blockers: []
gate_position: thorough_plan→implement
```

## Tasks

- T-01: Test dedup ⏳
  - acceptance: no duplicate headings

## Risks

| id | risk | likelihood | impact | mitigation | rollback |
|----|------|-----------|--------|------------|----------|
| R-01 | none | low | low | n/a | revert |

## References

- dedup fixture
