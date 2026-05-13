# Codex Workflow Procedures

These docs make the Codex adapter usable for the core Quoin loop while staying
repo-local and artifact-centered.

Each procedure links to the portable skill contract in `quoin/core/skills/` and
uses shared workflow semantics from `quoin/core/workflow/`. They describe how a
Codex session should execute the phase with natural-language requests, native
Codex tools, and project-root `.workflow_artifacts/`.

| Phase | Procedure | Portable contract |
|---|---|---|
| `discover` | [`discover.md`](discover.md) | `quoin/core/skills/discover.md` |
| `plan` | [`plan.md`](plan.md) | `quoin/core/skills/plan.md` |
| `implement` | [`implement.md`](implement.md) | `quoin/core/skills/implement.md` |
| `review` | [`review.md`](review.md) | `quoin/core/skills/review.md` |
| `gate` | [`gate.md`](gate.md) | `quoin/core/skills/gate.md` |

Session continuation is covered by [`../handoff.md`](../handoff.md), grounded in
`quoin/core/workflow/session-state.md` and
`quoin/core/workflow/task-layout.md`. Validate Codex handoff artifacts with
`quoin/adapters/codex/validate_codex_handoff.py`.

These are procedure docs only. They do not define Codex command files, global
install behavior, approval behavior, sandbox behavior, or model dispatch.
