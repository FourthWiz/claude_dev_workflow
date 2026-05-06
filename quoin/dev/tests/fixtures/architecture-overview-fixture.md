---
updated: 2026-04-25
---

## System purpose
Single-repo Quoin workflow toolchain. Provides planning, implementation, review, and daily-cache skills for software engineering tasks.

## Service map

```
/thorough_plan → /implement → /review → /end_of_task
     ↑
/architect
```

## Communication patterns
All skills communicate via file-based artifacts in `.workflow_artifacts/`. No network calls between skills.

## Request flows
User invokes skill → skill reads artifacts → skill writes artifacts → user reviews gate.

## Key architectural decisions
Artifacts use v3 format (Class A/B distinction). Validator enforces section invariants. Haiku summarizes Class B artifacts for human readers.

## Deployment topology
Single-machine CLI. Skills run as Claude Code subagents. No distributed components.
