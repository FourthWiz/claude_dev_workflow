---
name: revise-fast
description: "Fast variant of /revise using Sonnet for cost-efficient plan revision. Content-identical to /revise but runs on Sonnet instead of Opus. Used by /thorough_plan in default (non-strict) mode for rounds 2-3. Not intended for direct user invocation — use /revise for standalone revision."
model: sonnet
---

# Revise-Fast (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/revise-fast/SKILL.md`
> (Phase 9 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/revise.md` (with variance
> documented at `quoin/core/skills/revise-fast.md`).
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/revise-fast/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
