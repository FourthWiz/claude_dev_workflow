# Claude Adapter

The Claude Code adapter is the current production implementation.

For backward compatibility, its active files still live at the existing paths:

- `quoin/install.sh`
- `quoin/CLAUDE.md`
- `quoin/skills/`
- `quoin/memory/`
- `quoin/scripts/`
- `quoin/core/scripts/`

The supported Claude install command remains:

```bash
bash quoin/install.sh
```

This adapter owns Claude-specific behavior:

- deployment to `~/.claude`
- slash commands
- Claude skill frontmatter
- Haiku, Sonnet, and Opus model tiers
- Agent and Skill dispatch
- prompt-cache preambles
- Claude JSONL session lookup
- `ccusage` and Claude cost fallback plumbing

`install.sh` deploys compatibility wrappers to `~/.claude/scripts/` and portable core implementations to `~/.claude/core/scripts/` for the extracted shared scripts.

The first runtime-portability pass must not change Claude install behavior.

## Per-skill adapter files

The following per-skill adapter files live under this directory and are the
install source for the Claude runtime. `bash quoin/install.sh` deploys each
to `~/.claude/skills/<name>/SKILL.md` instead of the legacy stub at
`quoin/skills/<name>/SKILL.md`.

- `skills/capture_insight/SKILL.md` — Phase 6 pilot of the runtime-portable adapter pattern.
- `skills/triage/SKILL.md` — Phase 7 migration.
- `skills/start_of_day/SKILL.md` — Phase 7 migration.

The runtime-neutral intent docs for these skills live at
`quoin/core/skills/<name>.md`. The legacy stubs at
`quoin/skills/<name>/SKILL.md` remain only so glob-based tests and the
manifest frontmatter parser continue to find a valid SKILL.md at each path.
