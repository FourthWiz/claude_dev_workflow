---
name: thorough_plan
description: "Triages tasks by size (Small/Medium/Large) and orchestrates the appropriate planning path. Small tasks get a single-pass /plan (no critic loop). Medium tasks run the plan→critic→revise cycle with Sonnet revision. Large tasks (or 'strict:' prefix) run all-Opus with up to 5 rounds. Use this skill for: /thorough_plan, 'plan this', 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Supports size tags (small:/medium:/large:), strict: prefix, and max_rounds: N override. Always the entry point for planned work — routes automatically based on task size."
model: opus
---

# Thorough Plan — Orchestrator (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/thorough_plan/SKILL.md`
> (Phase 10 of the runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/thorough_plan.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/thorough_plan/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
