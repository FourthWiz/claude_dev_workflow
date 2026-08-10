---
name: gate
description: "Automated quality gate that runs checks and requires explicit human approval before the next phase. Use for: /gate, 'check before proceeding', 'run the gate', 'verify before next step'. The workflow STOPS here until the user says go."
model: sonnet
---

# Gate (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/gate/SKILL.md`
> (Phase 11 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/gate.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/gate/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
>
> NOTE: `quoin/skills/gate/preamble.md` MUST remain at this path.
> `install.sh` copies it to `~/.claude/skills/gate/preamble.md`.
> Do NOT delete or move preamble.md — it is required for §0 model
> dispatch cost-guardrail and audit-log cache-warming.
