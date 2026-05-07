# Codex Setup

Codex support is repo-local in this pass. There is no Codex installer.

## What Setup Means

For Codex, setup means:

- keep `AGENTS.md` at the repository root
- use Quoin's shared `.workflow_artifacts/` conventions
- follow `quoin/docs/runtime-portability.md`
- use `quoin/core/workflow/` for shared workflow semantics
- use `quoin/core/workflow/skills.json` for portable skill metadata

## What Setup Does Not Mean

Codex setup does not include:

- a global install
- copied command files
- guessed local runtime paths
- replacement approval logic
- replacement sandbox logic
- Claude slash-command compatibility

Codex should use native planning, approvals, sandboxing, repo-scoped instructions, and model or reasoning controls.

## Current Use

When using Codex in this repo, ask for Quoin workflow phases in natural language, for example:

- "Use Quoin to create an architecture artifact for this task."
- "Use Quoin to write a current plan under `.workflow_artifacts/`."
- "Use Quoin to review this implementation against the current plan."
- "Update Quoin session handoff and lessons learned."

The adapter should preserve Quoin artifacts, not emulate Claude slash commands.
