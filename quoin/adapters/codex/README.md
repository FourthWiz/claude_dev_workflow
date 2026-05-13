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

Per-skill portable intent docs now exist at
`quoin/core/skills/capture_insight.md`,
`quoin/core/skills/triage.md`,
`quoin/core/skills/start_of_day.md`,
`quoin/core/skills/review.md`,
`quoin/core/skills/plan.md`,
`quoin/core/skills/critic.md`,
`quoin/core/skills/revise.md`,
`quoin/core/skills/revise-fast.md`,
`quoin/core/skills/architect.md`, and
`quoin/core/skills/thorough_plan.md`. Codex performs each of these phases
natively against project-root `.workflow_artifacts/`, following the
runtime-neutral contract in those docs. No Codex command files, no Codex
installer, and no global Codex paths are introduced.

Execution-loop skills (implement, gate, run) and lifecycle/setup/support skills
(end_of_task, end_of_day, weekly_review, cost_snapshot, init_workflow, discover,
expand, rollback) remain future work.

## Repo-local setup scaffold

A repo-local setup scaffold is available under this directory:

- `installable-feature.md` — feature contract (scope, generated outputs, unsupported outputs)
- `feature-manifest.json` — machine-readable manifest referencing `quoin/core/workflow/skills.json`
- `generate_codex_assets.py` — generates `<project-root>/AGENTS.md` from portable skill metadata
- `verify_codex_readiness.py` — verifies the repo-local Codex setup contract without inspecting global Codex locations

Usage:

```
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path> --check
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
```

The generator writes only to the given `--project-root`. The readiness check
reads repository files only. No global Codex install paths or command files are
produced.
