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

`skills/capture_insight/SKILL.md` is the first per-skill adapter file under this
directory. It is the install source for the Claude runtime (Phase 6 pilot of the
runtime-portable adapter pattern). `bash quoin/install.sh` deploys it to
`~/.claude/skills/capture_insight/SKILL.md` instead of the legacy stub at
`quoin/skills/capture_insight/SKILL.md`.
