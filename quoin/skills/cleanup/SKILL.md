---
name: cleanup
description: "Trash-move stale workflow sentinels and old checkpoints into recoverable archive. Keeps the freshest/current session's sentinels; trashes others older than QUOIN_CLEANUP_SENTINEL_WINDOW (default 1d). Trashes checkpoints older than QUOIN_CLEANUP_CKPT_WINDOW (default 30d). Auto-fires as the first sub-block of Step 1.5 in /checkpoint (default-on, --no-cleanup opt-out). Standalone: /cleanup [--dry-run]. Recovery via manual mv from .workflow_artifacts/memory/trash/<date>/ — NOT /sleep --restore."
model: haiku
---

# Cleanup (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/cleanup/SKILL.md`
> (Phase 22 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/cleanup.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/cleanup/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
