# Codex Effort Mapping

The Codex adapter should consume the portable `effort` field from `quoin/core/workflow/skills.json`.

It should not consume `claude_model` except for migration audits.

## Effort Levels

| Effort | Codex intent |
| --- | --- |
| `low` | Summaries, routing, snapshots, and small workflow maintenance. |
| `medium` | Bounded implementation, rollback, expansion, and routine gates. |
| `high` | Planning, review, architecture, and cross-module implementation. |
| `max` | Strict planning, large tasks, high-risk architecture, and end-to-end orchestration. |

## Runtime Rule

Codex model and reasoning selection should use native Codex controls. Quoin should not hardcode Codex model names, guess local install paths, or duplicate Codex approval and sandbox behavior.

The adapter may use effort as intent metadata when deciding how much reasoning to apply, but exact runtime selection stays outside the portable core.
