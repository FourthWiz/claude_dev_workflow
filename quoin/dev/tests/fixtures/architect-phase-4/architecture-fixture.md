---
task: architect-phase-4-fixture
stage: 1
phase: architecture
date: 2026-04-27
model: claude-opus-4-6
class: B
---
## For human

This is a throwaway fixture for the T-09 recursive-self-critique guard smoke test.
It deliberately contains references to architect/SKILL.md and critic/SKILL.md in all
three form variants to exercise the broadened 4-form alternation guard.

## Stage decomposition

| Stage | Name | Status |
|-------|------|--------|
| 1 | test-stage | planned |

## Integration analysis

This fixture modifies quoin/skills/architect/SKILL.md and
quoin/skills/critic/SKILL.md — both are target files for this hypothetical task.
Additionally, the deployed copies at ~/.claude/skills/architect/SKILL.md and
~/.claude/skills/critic/SKILL.md will be updated via install.sh.

Bare form references: architect/SKILL.md and critic/SKILL.md are also present.
