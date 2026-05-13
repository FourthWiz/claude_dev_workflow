## Purpose
This repository contains Quoin, a workflow-memory toolkit. Its core value is the
artifact-centric workflow system, not any single coding agent runtime.

## Architectural intent
- Maintain one repository with a shared portable core plus thin runtime adapters.
- Preserve shared workflow semantics: `.workflow_artifacts/`, planning/review
  artifacts, stage-aware task structure, lessons learned, session handoff, and
  cost ledger.
- Do not duplicate Codex-native functionality such as approvals, sandboxing, or
  repo-scoped instruction handling.
- Prefer configuration and adapter boundaries over vendor-specific branching
  scattered throughout the codebase.

## Workflow conventions
Quoin stores all planning and review artifacts under `.workflow_artifacts/` at the
project root. Use this layout:

```
.workflow_artifacts/
  <task-name>/
    architecture.md
    current-plan.md
    cost-ledger.md
    review-1.md
  memory/
    lessons-learned.md
    sessions/
    daily/
```

Ask for Quoin workflow phases in natural language, for example:
- "Use Quoin to create an architecture artifact for this task."
- "Use Quoin to write a current plan under `.workflow_artifacts/`."
- "Use Quoin to review this implementation against the current plan."
- "Update Quoin session handoff and lessons learned."

## Portable skill reference
User-facing workflow skills with effort levels (from `quoin/core/workflow/skills.json`):

| Skill | Phase | Effort |
|-------|-------|--------|
| `architect` | architecture | max |
| `capture_insight` | memory | low |
| `cost_snapshot` | cost | low |
| `critic` | critic | high |
| `discover` | discovery | high |
| `end_of_day` | session-lifecycle | low |
| `end_of_task` | task-finalization | medium |
| `expand` | utility | medium |
| `gate` | gate | medium |
| `implement` | implementation | medium |
| `init_workflow` | project-bootstrap | high |
| `plan` | planning | high |
| `review` | review | high |
| `revise` | planning | high |
| `rollback` | rollback | medium |
| `run` | orchestration | max |
| `start_of_day` | session-lifecycle | low |
| `thorough_plan` | planning | max |
| `triage` | routing | low |
| `weekly_review` | session-lifecycle | low |

Codex performs each phase natively using its own planning and reasoning capabilities.
Use native Codex behavior for planning, progress tracking, approvals, sandboxing,
repo-scoped instructions, and model or reasoning controls.
No Claude slash-command compatibility is required or implied.

## Refactor guidance
- Separate portable workflow logic from Claude-specific runtime integration.
- Keep Claude-specific assumptions isolated in the Claude adapter (`quoin/adapters/claude/`).
- Build only thin Codex adapter scaffolding unless repository evidence supports more.
- Do not invent unverified Codex local install paths or packaging details.
- If a runtime detail is uncertain, define an interface, placeholder, or documentation
  note instead of hardcoding a guess.

## Editing principles
- Prefer incremental refactors over broad renames.
- Preserve backward compatibility where reasonable.
- Minimize duplication of templates, scripts, and rules.
- Keep documentation honest about implemented vs planned behavior.

## Discovery map (structured project index)

The portable generator `quoin/scripts/generate_discovery_map.py` produces a structured
`discovery-map.json` index at `<project_root>/.workflow_artifacts/discovery-map.json`.
Codex can run it directly without any global-path assumption:

- `python3 quoin/scripts/generate_discovery_map.py "$PROJECT_ROOT" --quiet`

The generator is optional; `discover` MUST NOT fail if it errors.

## Validation
- Run relevant checks after making changes.
- Report exactly which checks were run and which were not.
- Key validation commands:
  ```
  python3 -m pytest quoin/dev/tests/
  python3 quoin/scripts/build_preambles.py --check
  python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
  ```
