# Codex Adapter

The Codex adapter starts as a thin repo-local instruction layer.

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

The initial Codex entrypoint is the repository `AGENTS.md`. There is no Codex installer in this pass.
