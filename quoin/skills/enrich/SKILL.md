---
name: enrich
description: "Sharpens a raw task prompt into a clearer, better-grounded one before /specify — fills genuine gaps via a small set of targeted questions, writes enriched-prompt.md, and echoes it in chat. Use this skill for: /enrich, 'sharpen this prompt', 'tighten this task description', 'fill in the gaps before we spec this'. Distinct from /specify (which elicits a full structured spec) and /triage (which only routes); /enrich never writes a spec/plan and never invokes a downstream phase."
model: opus
---

# Enrich (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/enrich/SKILL.md`
> (runtime-portability migration). The runtime-neutral intent doc lives
> at `quoin/core/skills/enrich.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/enrich/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
>
> NOTE: `quoin/skills/enrich/preamble.md` MUST remain at this path.
> `install.sh` copies it to `~/.claude/skills/enrich/preamble.md`.
> Do NOT delete or move preamble.md — it is required for cache-warming.
