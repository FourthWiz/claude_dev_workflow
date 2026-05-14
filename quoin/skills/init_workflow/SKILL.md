---
name: init_workflow
description: "Initializes the development workflow in a project folder. Creates the .workflow_artifacts/ structure, runs /discover to scan the codebase, and generates a quickstart guide. Requires install.sh to have been run first (installs skills to __QUOIN_HOME__/skills/ and workflow rules to __QUOIN_HOME__/CLAUDE.md). Use this skill for: /init_workflow, 'initialize workflow', 'set up dev workflow', 'install workflow', 'bootstrap workflow'. Run this once per project."
model: opus
---
# Initialize Development Workflow (deprecated stub)

> **DEPRECATED LOCATION.** The active Claude adapter SKILL.md for this
> skill lives at `quoin/adapters/claude/skills/init_workflow/SKILL.md`
> (Phase 21 runtime-portability migration). The runtime-neutral
> intent doc lives at `quoin/core/skills/init_workflow.md`.
>
> `bash quoin/install.sh` deploys the adapter file (not this stub) to
> `~/.claude/skills/init_workflow/SKILL.md`.
>
> Do NOT add behavior here. Edit the adapter file. This stub remains only
> so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
> frontmatter parser continue to find a valid SKILL.md at this path.
