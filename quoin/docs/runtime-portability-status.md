# Runtime Portability Status

This page tracks the current migration state.

## Claude Code

Status: installable.

- `bash quoin/install.sh` remains the supported install command.
- Active Claude rules remain in `quoin/CLAUDE.md`.
- Active Claude skills remain in `quoin/skills/`.
- Compatibility wrappers deploy to `~/.claude/scripts/`.
- Extracted portable implementations deploy to `~/.claude/core/scripts/`.

## Codex

Status: scaffolded only.

- Root `AGENTS.md` provides repo-local instructions.
- Codex adapter docs live under `quoin/adapters/codex/`.
- Codex setup is documented in `quoin/adapters/codex/setup.md`.
- There is no Codex installer.
- There are no Codex command files.
- No global Codex paths are assumed.

## Portable Core

Status: partially extracted.

- Portable scripts live under `quoin/core/scripts/`.
- Core workflow docs live under `quoin/core/workflow/`.
- Skill metadata lives in `quoin/core/workflow/skills.json`.
- Shared reference material still lives under `quoin/memory/`.

## Still Claude-Specific

- Skill bodies in `quoin/skills/`.
- Slash-command invocation model.
- Agent and Skill dispatch instructions.
- Prompt-cache preamble generation.
- Claude model frontmatter.
- Claude JSONL session and cost plumbing.
- `ccusage` integration.

## Not Started

- Generated Claude skill files.
- Generated Codex adapter files.
- Split shared skill intent from runtime overlays.
- Runtime-neutral cost capture.
- Codex install target verification.
