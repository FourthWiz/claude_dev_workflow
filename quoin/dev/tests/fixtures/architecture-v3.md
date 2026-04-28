---
task: fixture-task
profile: medium
branch: feat/fixture-branch
architecture_round: 1
date: 2026-04-25
---
## For human

Stage 3 fixture architecture for a no-op scratch task. Two stages: Stage 1
ships a helper function; Stage 2 adds a unit test. No cross-service calls.
Risk R-01 (env isolation) is the only non-trivial concern. Ready for /plan.

## Context

This architecture describes a minimal scratch task used as a v3-format fixture.
The project is a single-repo Python codebase. No external service dependencies.

## Current state

No `scripts/scratch.py` or `tests/` directory exists. The repository is otherwise
fully functional with all Stage 2 v3-format artifacts in place.

## Proposed architecture

Add a `print_noop()` helper to `scripts/scratch.py` that accepts any args and
returns `None`. Add `tests/test_scratch.py` with a single pytest assertion.
No config changes. No new dependencies.

## Risk register

| id | risk | likelihood | impact | mitigation | rollback |
|----|------|-----------|--------|------------|----------|
| R-01 | Missing `tests/` directory | medium | low | create with `__init__.py` if absent | delete created dirs |
| R-02 | `scripts/` directory missing | low | low | create if absent | delete created dirs |

## Stage decomposition

1. Stage 1 — add `print_noop()` to `scripts/scratch.py` ⏳
   - acceptance: function exists, returns None, imports cleanly
2. Stage 2 — add `tests/test_scratch.py` ⏳
   - acceptance: `pytest tests/test_scratch.py` passes
