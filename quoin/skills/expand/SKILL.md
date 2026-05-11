---
name: expand
model: sonnet
description: "Expands compressed (terse) workflow artifacts back to English for human reading. Use for: /expand <path>, 'show me the English version of', 'expand this file', 'what does this terse file say'. Dispatches: Class B summary detection (reads ## For human block at top of v3 artifacts), no-op display (Tier 1 English files), LLM re-expansion (Tier 3 ephemeral files — lossy, banner-flagged). Never used as a contract approval path."
---
# Expand (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/expand/SKILL.md`
> (Phase 19 runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/expand.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/expand/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
