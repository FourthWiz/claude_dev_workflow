# Quoin Codex Instructions

Quoin is being refactored toward runtime portability. When working in this repository with Codex, preserve the artifact-centric workflow and avoid adding Codex-specific runtime assumptions that are not verified from the repo.

Use these rules:

- Treat `.workflow_artifacts/` semantics as the portable core: task folders, stage subfolders, architecture/planning/review artifacts, lessons learned, session handoff, and cost ledger.
- Treat the directory where Codex was launched, containing this `AGENTS.md`, as the Quoin project root. Create and read `.workflow_artifacts/` at that root, not inside a nested application or package subdirectory.
- Use native Codex planning, approvals, sandboxing, and repo-scoped instructions.
- Do not assume Claude slash commands exist when describing Codex behavior.
- Do not add guessed Codex global install paths.
- Do not rebuild Codex approvals or sandboxing inside Quoin.
- Keep existing Claude behavior backward compatible unless a task explicitly asks to change it.

Reference `quoin/docs/runtime-portability.md` before changing runtime boundaries.
