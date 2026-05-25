---
name: pr
description: "Create a pull request: optional version bump, push branch if not already pushed, create PR via gh, wait for merge, switch to merge target. Use this skill for: /pr, 'create a PR', 'open a pull request', 'submit for review'. Triggers when the user wants to create a PR from a feature branch."
model: sonnet
---

# PR

*Portable intent doc: `quoin/core/skills/pr.md`*

Adapter override: the active Claude adapter SKILL.md for this skill lives at
`quoin/adapters/claude/skills/pr/SKILL.md`. The runtime-neutral intent doc
lives at `quoin/core/skills/pr.md`.

`bash quoin/install.sh` deploys the adapter file (not this stub) to
`~/.claude/skills/pr/SKILL.md`.

Do NOT add behavior here. Edit the adapter file. This stub remains only
so that `quoin/skills/*/SKILL.md` glob-based tests and the manifest
frontmatter parser continue to find a valid SKILL.md at this path.
