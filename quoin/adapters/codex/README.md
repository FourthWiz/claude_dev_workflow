# Codex Adapter

The Codex adapter starts as a thin repo-local instruction, procedure, and
readiness layer.

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

Phase 33 adds repo-local Codex execution procedures for the practical workflow
loop:

```text
discover -> plan -> implement -> review -> gate
```

The guide lives at `quoin/adapters/codex/workflow.md`. Per-phase procedures live
under `quoin/adapters/codex/procedures/` and link back to the portable
contracts in `quoin/core/skills/`.

Phase 34 adds explicit repo-local Codex session handoff guidance and a
deterministic validator. Codex writes handoff state under
`.workflow_artifacts/memory/sessions/`, validates it with
`validate_codex_handoff.py`, and the next Codex session reads that artifact
before continuing work. This is documentation plus validation; it does not claim
live Codex hooks.

Phase 35 adds a repo-local Codex cost event writer and validator. Codex can
append portable cost-ledger rows with known task, phase, timestamp, session id,
and effort values, while marking token and dollar telemetry as `not_available`
because this repository has no verified Codex runtime telemetry interface.

## Repo-local setup scaffold

A repo-local setup scaffold is available under this directory:

- `installable-feature.md` — feature contract (scope, generated outputs, unsupported outputs)
- `feature-manifest.json` — machine-readable manifest referencing `quoin/core/workflow/skills.json`
- `generate_codex_assets.py` — generates `<project-root>/AGENTS.md` and, when requested, Codex skill adapter docs from portable skill metadata
- `verify_codex_readiness.py` — verifies the repo-local Codex setup contract without inspecting global Codex locations
- `smoke_codex_workflow.py` — follows the repo-local Codex setup path through
  adapter docs and portable core workflow docs to prove a minimal workflow is
  coherent
- `handoff.md` — repo-local session/handoff procedure for Codex continuation
- `validate_codex_handoff.py` — deterministic checker for Codex handoff
  artifact shape under `.workflow_artifacts/memory/sessions/`
- `cost.md` — Codex cost event behavior and unavailable telemetry contract
- `cost_event.py` — repo-local writer/checker for Codex cost ledger rows using
  the portable cost core
- `workflow.md` — repo-local Codex guide for executing the workflow loop with
  native Codex behavior and portable artifacts
- `procedures/` — per-phase procedures for `discover`, `plan`, `implement`,
  `review`, and `gate`
- `skills/` — generated/scaffolded Codex adapter docs for all portable skills
- `unsupported-claude-behavior.md` — shared notes for Claude-only behavior that is not translated into Codex

Usage:

```
quoin codex init --project-root <path>
quoin codex init --project-root <path> --check
quoin doctor --runtime codex
quoin doctor --runtime codex --smoke
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path> --check
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets --check
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .
python3 quoin/adapters/codex/validate_codex_handoff.py --self-test
python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/<date>-<task>-codex.md
python3 quoin/adapters/codex/cost_event.py --self-test
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task> --phase <phase> --effort <low|medium|high|max|unknown>
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task> --expect-codex
```

The default generator path writes only to the given `--project-root`. The
`--adapter-assets` option writes generated/scaffolded docs under the
repo-local Codex adapter directory (or an explicit `--adapter-root`). The
readiness and smoke checks read repository files only. No global Codex install
paths or command files are produced.
