# Codex Repo-Local Setup Contract

This document describes the Codex setup surface Quoin can honestly verify today:
a repo-local workflow bundle that materializes Codex-ready scaffolding without
guessing global Codex install paths.

## What "installable" means here

"Installable" in this context means the setup can be generated into and checked
inside a project repository from known sources in the Quoin codebase. It does not
mean:

- a global Codex package install
- a Codex extension point or command file (not yet verified)
- replacement approval, sandboxing, or model-selection logic

The default generated project output is repo-local: an `AGENTS.md` at the
project root. Phase 26 also generates/scaffolds Codex adapter docs under
`quoin/adapters/codex/` from portable core metadata. Phase 33 adds repo-local
workflow execution procedure docs under the same adapter directory. Phase 34
adds repo-local handoff guidance and validation. Phase 35 adds a repo-local
Codex cost event writer/checker that records unavailable telemetry explicitly.
Nothing is written to a global Codex runtime.

## Supported first feature: repo-local workflow bundle

The generator (`quoin/adapters/codex/generate_codex_assets.py`) produces:

- `<project-root>/AGENTS.md` — Codex repo instructions for using Quoin workflow
  phases, portable artifact conventions, and the `.workflow_artifacts/` layout
- `quoin/adapters/codex/skills/<skill>/README.md` — Codex facing adapter docs
  for all 21 portable skills when `--adapter-assets` is used
- `quoin/adapters/codex/skills/README.md` — generated skill index
- `quoin/adapters/codex/unsupported-claude-behavior.md` — shared unsupported
  behavior notes for Claude-only runtime mechanics
- `quoin/adapters/codex/workflow.md` — repo-local Codex guide for the
  `discover -> plan -> implement -> review -> gate` loop
- `quoin/adapters/codex/procedures/<phase>.md` — per-phase procedure docs for
  `discover`, `plan`, `implement`, `review`, and `gate`
- `quoin/adapters/codex/handoff.md` — repo-local Codex handoff/session
  procedure for continuation files under `.workflow_artifacts/memory/sessions/`
- `quoin/adapters/codex/validate_codex_handoff.py` — deterministic checker for
  Codex handoff markdown shape and repo-local artifact paths
- `quoin/adapters/codex/cost.md` — Codex cost event behavior and explicit
  unavailable telemetry contract
- `quoin/adapters/codex/cost_event.py` — repo-local writer/checker for portable
  Codex cost ledger rows

The generated content preserves the architectural boundaries already present in the
root `AGENTS.md`:

- Codex performs planning, architecture, review, and session-handoff phases natively
- Quoin artifact paths and conventions are shared with the Claude adapter
- No Claude slash-command compatibility is implied or emulated
- No global Codex paths are assumed

## What the feature installs

Project assets only:

- Root `AGENTS.md` content (workflow guidance, artifact conventions, phase reference)
- Codex adapter skill docs under `quoin/adapters/codex/skills/`
- Codex workflow guide and procedure docs under `quoin/adapters/codex/`
- Codex handoff guide, fixture, and validator under `quoin/adapters/codex/`
- Codex cost event guide and writer/checker under `quoin/adapters/codex/`
- Unsupported Claude-only behavior notes
- Quoin artifact layout guidance (`.workflow_artifacts/` structure and naming)
- Skill metadata references (drawn from `quoin/core/workflow/skills.json`)
- Validation commands (pytest invocation from the project root)

## What the feature does NOT install

- Global Codex install paths or package registry entries — unresolved until verified
- Codex command files — format and discovery mechanism not yet confirmed
- Codex-specific approval or sandboxing logic — use Codex native behavior
- Claude slash-command wrappers

## Readiness verification

The repo-local readiness check is exposed through the Quoin CLI:

```
quoin doctor --runtime codex
```

That command delegates to the existing readiness script:

```
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
```

It verifies root `AGENTS.md`, portable workflow docs, Codex adapter docs,
workflow procedure coverage, handoff contract coverage, manifest scope, absence
of guessed global Codex paths in active Codex facing docs, and isolation of the
Claude installer. It does not inspect or write a global Codex runtime.

The Phase 27 smoke test is:

```
python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .
```

It validates the repo-local path a Codex session would need for the Phase 33
Quoin workflow loop: root `AGENTS.md`, Codex setup docs, Codex skill adapter
docs, Codex procedure docs, portable skill contracts, and portable workflow
artifact docs. It also checks that this path does not require Claude global
paths, Claude slash-command invocation, Claude install routing, or `ccusage`
for Codex.

The Phase 34 handoff validator can self-test against its bundled fixture:

```
python3 quoin/adapters/codex/validate_codex_handoff.py --self-test
```

To validate a real Codex handoff file, pass the project root and session file
path:

```
python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/<date>-<task>-codex.md
```

The Phase 35 Codex cost writer/checker can self-test without live runtime
telemetry:

```
python3 quoin/adapters/codex/cost_event.py --self-test
```

To append and validate a task cost row:

```
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task> --phase <phase> --effort <low|medium|high|max|unknown>
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task> --expect-codex
```

The writer records known local values and marks token counts, dollar cost, and
telemetry source as `not_available`; it does not infer unavailable Codex usage.

## Generator usage

```
quoin codex init --project-root <path>
quoin codex init --project-root <path> --check
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path> --check
python3 quoin/adapters/codex/generate_codex_assets.py --project-root . --adapter-assets --check
```

Default output writes to `<project-root>/AGENTS.md`. The
`--adapter-assets` option also writes/checks generated adapter docs under
`quoin/adapters/codex/` (or an explicit `--adapter-root`). The `--check` flag
compares rendered content against existing files and exits nonzero on drift.

## Manifest

The machine-readable feature manifest lives at
`quoin/adapters/codex/feature-manifest.json`. It records entrypoints, portable
inputs, generated outputs, and unsupported outputs. Skill names and effort values
are referenced from `quoin/core/workflow/skills.json` — not duplicated inline.

## Related documents

- Runtime-portability boundary: `quoin/docs/runtime-portability.md`
- Codex adapter setup: `quoin/adapters/codex/setup.md`
- Codex workflow guide: `quoin/adapters/codex/workflow.md`
- Codex handoff guide: `quoin/adapters/codex/handoff.md`
- Codex cost event guide: `quoin/adapters/codex/cost.md`
- Portable skill metadata: `quoin/core/workflow/skills.json`
