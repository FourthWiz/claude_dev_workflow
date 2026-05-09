---
name: architect
description: "Deep architectural analysis and planning using the strongest available model (Opus), with a scan/synthesize split for efficiency. Spawns Sonnet subagents in parallel to read repos, then synthesizes findings on Opus. Use this skill whenever the user needs to explore a complex system, understand how multiple repositories interact, design a new architecture, decompose a large problem into implementable stages, or answer hard cross-cutting questions about a codebase. Triggers on: /architect, architecture design, system design, technical exploration, cross-repo analysis, complex technical questions, 'how should we build this', 'what's the best approach for', deep code exploration, multi-service design. Even if the user just says 'I need to think through X' where X is technical — use this skill."
model: opus
---

# Architect (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/architect/SKILL.md`
> (Phase 10 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/architect.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/architect/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
>
> NOTE: `quoin/skills/architect/preamble.md` MUST remain at this path.
> `install.sh` copies it to `~/.claude/skills/architect/preamble.md`.
> Do NOT delete or move preamble.md — it is required for cache-warming.
