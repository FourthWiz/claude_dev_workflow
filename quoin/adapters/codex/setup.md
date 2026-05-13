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
- generated Codex outputs are scoped to `repo-local`
- Codex docs avoid guessed global paths and command packaging claims
- `quoin/install.sh` remains Claude-only

Run from the repository root:

```
python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
```

Passing this check means the repository is ready for Codex to use Quoin's
repo-local artifact workflow. It does not mean Quoin has installed anything into
a global Codex runtime.

## Generating AGENTS.md

A generator script produces a repo-local `AGENTS.md` from portable skill metadata:

```
python3 quoin/adapters/codex/generate_codex_assets.py --project-root <path>
```

Use `--check` to verify an existing `AGENTS.md` is up to date (exits nonzero on drift):

```
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

The adapter should preserve Quoin artifacts, not emulate Claude slash commands.

If Codex changes into a nested subdirectory to inspect or edit code, it should still write Quoin artifacts relative to the original project root.
