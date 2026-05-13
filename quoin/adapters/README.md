# Runtime Adapters

Adapters connect the portable Quoin workflow to a specific agent runtime.

The portable workflow contract lives in `quoin/docs/runtime-portability.md`. Runtime adapters own invocation syntax, install behavior, model mapping, session/cost plumbing, and runtime-specific instructions.

Current adapter status:

- Claude Code: supported today through the existing `quoin/install.sh`, `quoin/CLAUDE.md`, and `quoin/skills/` layout.
- Codex: scaffolded through repo-local instructions and documentation.

Do not duplicate shared memory files, scripts, or skill templates into adapter folders until the shared core has been split from runtime overlays.
