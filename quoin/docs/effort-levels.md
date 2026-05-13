# Effort Levels

Quoin should describe model needs with runtime-neutral effort levels. Runtime adapters map these levels to their own model controls.

## Levels

| Effort | Intended use |
| --- | --- |
| `low` | Short summaries, routing, snapshots, status checks, and routine memory capture. |
| `medium` | Implementation, rollback, expansion, routine gates, and bounded operational work. |
| `high` | Architecture, planning, critic review, production review, and tasks with meaningful integration risk. |
| `max` | Strict or large planning loops, high-risk architecture review, and work where the adapter should use its strongest available reasoning. |

## Claude Mapping

The current Claude adapter maps the existing model tiers this way:

| Claude tier | Effort |
| --- | --- |
| Haiku | `low` |
| Sonnet | `medium` |
| Opus | `high` or `max`, depending on strictness and risk |

This mapping is documentation only in the first pass. Existing Claude skill frontmatter remains unchanged.

## Codex Mapping

The Codex adapter should defer to Codex-native model and reasoning-effort controls. Quoin should not hardcode local Codex model names or installation paths.

For Codex-facing instructions, use the effort level to communicate task intent:

- Use `low` for cheap, mostly mechanical workflow maintenance.
- Use `medium` for bounded code or documentation changes.
- Use `high` for planning, review, architecture, and cross-module implementation.
- Use `max` only when the task is large, high-risk, or deliberately strict.
