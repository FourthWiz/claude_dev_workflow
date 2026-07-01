---
name: checkpoint
description: "General-purpose state-saving — save session-restore state mid-session before context exhaustion, between tasks, between sessions, or before starting new heavy work. Writes a pending-restore sentinel so a fresh session can resume exactly where you left off. Also surfaces pending-restore state on --restore. Auto-runs /cleanup on save (trash-moves stale sentinels/old checkpoints) unless --no-cleanup. Use for: /checkpoint, 'save my place', 'checkpoint', 'save session', '/checkpoint --restore', 'restore checkpoint', 'resume from checkpoint'. Does NOT roll up dailies, does NOT touch lessons-learned.md or forgotten/."
model: sonnet
---

# Checkpoint (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/checkpoint/SKILL.md`
> (Phase 22 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/checkpoint.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/checkpoint/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
