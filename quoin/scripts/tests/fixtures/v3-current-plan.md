---
task: scratch-task
profile: small
branch: feat/scratch
plan_round: 1
date: 2026-04-24
---
## For human

Add a no-op print helper to the scratch module.
One new function, zero risk, no integration points.
Single task, no dependencies, ready for /implement immediately.

## State

```yaml
phase: planned
last_task: ~
blockers: []
gate_position: thorough_plan→implement
```

## Tasks

- T-01: Add `print_noop()` to `scripts/tests/scratch.py` ⏳
  - acceptance: function exists, returns None, imports cleanly
  - effort: trivial
- T-02: Add smoke test for `print_noop()` in `test_scratch.py` ⏳
  - acceptance: pytest passes, asserts return value is None

## Risks

| id | risk | likelihood | impact | mitigation | rollback |
|----|------|-----------|--------|------------|----------|
| R-01 | name collision with stdlib | low | low | check existing names first | revert |
| R-02 | scratch.py does not exist | low | low | create file if missing | delete |

## References

- `quoin/scripts/tests/scratch.py` — target file
