---
updated: 2026-04-25
---

## Dependency graph
| From | To | Protocol | Notes |
|------|-----|----------|-------|
| /plan | validate_artifact.py | subprocess | V-01..V-07 checks |
| /critic | format-kit.sections.json | file read | section whitelist |
| /implement | .workflow_artifacts/ | file write | artifacts dir |

## Shared resources
- `.workflow_artifacts/memory/` — shared across all skills
- `~/.claude/memory/format-kit.md` — deployed reference, all skills read

## Deployment order constraints
- install.sh must run before any skill is used
- validate_artifact.py must exist before Class B/A writers call it

## Integration risks
- format-kit.sections.json schema changes require redeployment via install.sh
- Validator updates may break existing fixtures if section sets change
