# Codex Setup

Codex support is repo-local in this pass. There is no verified stable Codex
global install target in this repository, so Quoin does not provide a Codex
installer.

## What Setup Means

For Codex, setup means:

- keep `AGENTS.md` at the repository root
- use Quoin's shared `.workflow_artifacts/` conventions
- treat the repository root containing `AGENTS.md` as the Quoin project root
- create and read `.workflow_artifacts/` at that project root, not inside a nested application or package directory
- follow `quoin/docs/runtime-portability.md`
- use `quoin/core/workflow/` for shared workflow semantics
- use `quoin/core/workflow/skills.json` for portable skill metadata
- use `quoin/adapters/codex/skills/<skill>/README.md` as Codex facing
  per-skill guidance generated/scaffolded from the portable core
- use `quoin/adapters/codex/workflow.md` and
  `quoin/adapters/codex/procedures/` for repo-local execution procedures for
  `discover`, `plan`, `implement`, `review`, and `gate`
- use `quoin/adapters/codex/handoff.md` and
  `quoin/adapters/codex/validate_codex_handoff.py` for repo-local session
  handoff artifacts under `.workflow_artifacts/memory/sessions/`
- use `quoin/adapters/codex/cost.md` and
  `quoin/adapters/codex/cost_event.py` for repo-local cost ledger rows that
  mark unavailable token and dollar telemetry as `not_available`

## What Setup Does Not Mean

Codex setup does not include:

- a global install
- copied command files
- guessed local runtime paths
- replacement approval logic
- replacement sandbox logic
- Claude slash-command compatibility

Codex should use native planning, approvals, sandboxing, repo-scoped instructions, and model or reasoning controls.

## Readiness Check

The repo-local readiness check verifies only evidence Quoin can inspect:

- `AGENTS.md` exists at the project root and points workflow artifacts to that root
- portable workflow docs and `quoin/core/workflow/skills.json` exist
- Codex adapter docs and manifest exist
- every portable skill has a Codex adapter doc under `quoin/adapters/codex/skills/`
- Codex procedure docs exist for `discover`, `plan`, `implement`, `review`,
  and `gate`, and each links to its portable core skill contract
- Codex handoff docs and the deterministic handoff validator exist and point to
  portable session-state and task-layout contracts
- Codex cost docs and writer/checker exist and use the portable cost core
- generated Codex outputs are scoped to `repo-local`
- Codex docs avoid guessed global paths and command packaging claims
- `quoin/install.sh` remains Claude-only

Run from the repository root:

```
quoin doctor --runtime codex
```

This is a thin CLI wrapper around the existing deterministic readiness script:

```
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
```

Passing this check means the repository is ready for Codex to use Quoin's
repo-local artifact workflow. It does not mean Quoin has installed anything into
a global Codex runtime.

## Runtime Smoke Test

Phase 27 adds a deterministic repo-local smoke test for the Codex path:

```
python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .
```

The smoke test follows the documented path from `AGENTS.md` and Codex adapter
setup docs to `quoin/adapters/codex/skills/`, `quoin/core/skills/`, and
`quoin/core/workflow/`. It verifies that minimal architecture, plan, review,
and cost-ledger artifact semantics are reachable without Claude global paths,
Claude slash-command requirements, Claude install routing, or `ccusage` as a
required Codex dependency.

Passing this smoke test means the files and assumptions needed for a minimal
repo-local Codex Quoin workflow are coherent. It still does not automate live
Codex runtime behavior or install a Codex extension.

## Handoff Validation

Phase 34 adds a deterministic handoff checker:

```
python3 quoin/adapters/codex/validate_codex_handoff.py --self-test
python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/<date>-<task>-codex.md
```

The checker validates that the file lives under project-root
`.workflow_artifacts/memory/sessions/`, uses the required Codex handoff
sections, identifies task artifacts with repo-relative `.workflow_artifacts/`
paths, and avoids unsupported runtime path assumptions. It does not install or
invoke live Codex hooks.

## Cost Event Validation

Phase 35 adds a deterministic Codex cost writer/checker:

```
python3 quoin/adapters/codex/cost_event.py --self-test
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task> --phase <phase> --effort <low|medium|high|max|unknown>
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task> --expect-codex
```

The writer appends the existing portable seven-column cost ledger row. It
records runtime, task, phase, timestamp, session id when supplied, effort, and
fallback fires. It records token counts, dollar cost, and telemetry source as
`not_available` because no verified Codex local telemetry interface exists in
this repository.

## Generating AGENTS.md

A generator script produces a repo-local `AGENTS.md` from portable skill metadata:

```
quoin codex init --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
```

Use `--check` to verify an existing `AGENTS.md` is up to date (exits nonzero on drift):

```
quoin codex init --project-root . --check
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --check
```

The feature contract and manifest are at `quoin/adapters/codex/installable-feature.md`
and `quoin/adapters/codex/feature-manifest.json`.

## Generating Codex Skill Docs

Codex adapter skill docs are generated/scaffolded from portable skill metadata
and core skill docs:

```
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets --check
```

These docs live under `quoin/adapters/codex/skills/`. They are not Codex command
files and do not imply a global runtime install target.

## Current Use

When using Codex in this repo, ask for Quoin workflow phases in natural language, for example:

- "Use Quoin to create an architecture artifact for this task."
- "Use Quoin to write a current plan under `.workflow_artifacts/`."
- "Use Quoin to review this implementation against the current plan."
- "Update Quoin session handoff and lessons learned."
- "Validate the Codex handoff for this task."
- "Record a Codex cost event for this task."

The adapter should preserve Quoin artifacts, not emulate Claude slash commands.

If Codex changes into a nested subdirectory to inspect or edit code, it should still write Quoin artifacts relative to the original project root.

For the full Phase 33 execution loop, use
`quoin/adapters/codex/workflow.md` and the per-phase docs under
`quoin/adapters/codex/procedures/`.
