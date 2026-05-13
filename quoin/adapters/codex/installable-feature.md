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

The generated output is repo-local: an `AGENTS.md` at the project root. Nothing is
written outside the project root.

## Supported first feature: repo-local workflow bundle

The generator (`quoin/adapters/codex/generate_codex_assets.py`) produces one file:

- `<project-root>/AGENTS.md` — Codex repo instructions for using Quoin workflow
  phases, portable artifact conventions, and the `.workflow_artifacts/` layout

The generated content preserves the architectural boundaries already present in the
root `AGENTS.md`:

- Codex performs planning, architecture, review, and session-handoff phases natively
- Quoin artifact paths and conventions are shared with the Claude adapter
- No Claude slash-command compatibility is implied or emulated
- No global Codex paths are assumed

## What the feature installs

Project assets only:

- Root `AGENTS.md` content (workflow guidance, artifact conventions, phase reference)
- Quoin artifact layout guidance (`.workflow_artifacts/` structure and naming)
- Skill metadata references (drawn from `quoin/core/workflow/skills.json`)
- Validation commands (pytest invocation from the project root)

## What the feature does NOT install

- Global Codex install paths or package registry entries — unresolved until verified
- Codex command files — format and discovery mechanism not yet confirmed
- Codex-specific approval or sandboxing logic — use Codex native behavior
- Claude slash-command wrappers

## Readiness verification

The repo-local readiness check is:

```
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
```

It verifies root `AGENTS.md`, portable workflow docs, Codex adapter docs,
manifest scope, absence of guessed global Codex paths in active Codex-facing
docs, and isolation of the Claude installer. It does not inspect or write a
global Codex runtime.

## Generator usage

```
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path> --check
```

Default output writes to `<project-root>/AGENTS.md`. The `--check` flag compares
rendered content against the existing file and exits nonzero on drift.

## Manifest

The machine-readable feature manifest lives at
`quoin/adapters/codex/feature-manifest.json`. It records entrypoints, portable
inputs, generated outputs, and unsupported outputs. Skill names and effort values
are referenced from `quoin/core/workflow/skills.json` — not duplicated inline.

## Related documents

- Runtime-portability boundary: `quoin/docs/runtime-portability.md`
- Codex adapter setup: `quoin/adapters/codex/setup.md`
- Portable skill metadata: `quoin/core/workflow/skills.json`
