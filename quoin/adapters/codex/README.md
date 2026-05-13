# Codex Adapter

The Codex adapter starts as a thin repo-local instruction and readiness layer.

Codex should use Quoin's portable artifact workflow:

- `.workflow_artifacts/`
- task and stage folders
- architecture, planning, critic, review, gate, session, lessons, and cost artifacts
- shared artifact validation and path-resolution rules

The Quoin project root is the repository root containing `AGENTS.md`. Codex must create and read `.workflow_artifacts/` there, even when the code being changed lives in a nested subdirectory.

Codex should also use native Codex behavior where it already exists:

- planning and progress tracking
- approvals
- sandboxing
- repo-scoped instructions
- model and reasoning-effort controls

Quoin must not guess Codex global install paths, create a custom approval system, or duplicate sandbox enforcement.

The initial Codex entrypoint is the repository `AGENTS.md`. There is no verified
stable Codex global install target in this repository, so there is no Codex
installer in this pass.

Per-skill portable intent docs now exist for all 21 migrated skills under
`quoin/core/skills/`. Codex facing adapter docs are generated/scaffolded under
`quoin/adapters/codex/skills/<skill>/README.md`. Codex performs these phases
natively against project-root `.workflow_artifacts/`, following the
runtime-neutral contract in the portable core docs. No Codex command files, no
Codex installer, and no global Codex paths are introduced.

Execution-loop skills (implement, gate, run) and lifecycle/setup/support skills
(end_of_task, end_of_day, weekly_review, cost_snapshot, init_workflow, discover,
expand, rollback) remain future work.

## Repo-local setup scaffold

A repo-local setup scaffold is available under this directory:

- `installable-feature.md` — feature contract (scope, generated outputs, unsupported outputs)
- `feature-manifest.json` — machine-readable manifest referencing `quoin/core/workflow/skills.json`
- `generate_codex_assets.py` — generates `<project-root>/AGENTS.md` and, when requested, Codex skill adapter docs from portable skill metadata
- `verify_codex_readiness.py` — verifies the repo-local Codex setup contract without inspecting global Codex locations
- `smoke_codex_workflow.py` — follows the repo-local Codex setup path through
  adapter docs and portable core workflow docs to prove a minimal workflow is
  coherent
- `skills/` — generated/scaffolded Codex adapter docs for all portable skills
- `unsupported-claude-behavior.md` — shared notes for Claude-only behavior that is not translated into Codex

Usage:

```
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path> --check
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets --check
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .
```

The default generator path writes only to the given `--project-root`. The
`--adapter-assets` option writes generated/scaffolded docs under the
repo-local Codex adapter directory (or an explicit `--adapter-root`). The
readiness and smoke checks read repository files only. No global Codex install
paths or command files are produced.
