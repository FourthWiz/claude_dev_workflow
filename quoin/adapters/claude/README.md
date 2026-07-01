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

Per-skill adapter SKILL.md files live under `skills/<name>/SKILL.md` in this
directory and are the install source for the Claude runtime.
`bash quoin/install.sh` deploys each to `~/.claude/skills/<name>/SKILL.md`
instead of the legacy stub at `quoin/skills/<name>/SKILL.md`.

**Authoritative source for the full skill list:** `quoin/core/workflow/skills.json`
(`skills[].name` array). This README previously maintained a per-skill enumeration
that inevitably drifted; the manifest is now the single source of truth.
Currently 28 skills are registered. To inspect:

```bash
python3 -c "import json; d=json.load(open('quoin/core/workflow/skills.json')); [print(s['name']) for s in d['skills']]"
```

The runtime-neutral intent docs for each skill live at
`quoin/core/skills/<name>.md`. Legacy stubs at `quoin/skills/<name>/SKILL.md`
remain only so glob-based tests and the manifest frontmatter parser continue
to find a valid SKILL.md at each path.
