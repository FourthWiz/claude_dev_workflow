# Runtime Portability Status

This page tracks the current migration state.

## Claude Code

Status: installable.

- `bash quoin/install.sh` remains the supported install command.
- Active Claude rules remain in `quoin/CLAUDE.md`.
- Active Claude skills remain in `quoin/skills/`, EXCEPT `capture_insight`,
  which installs from `quoin/adapters/claude/skills/capture_insight/SKILL.md`
  (Phase 6 pilot of the runtime-portable adapter pattern).
- The portable intent doc for `capture_insight` lives at `quoin/core/skills/capture_insight.md`.
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
- Split shared skill intent from runtime overlays — partial: `capture_insight` shipped under the adapter pattern in Phase 6.
- Runtime-neutral cost capture.
- Codex install target verification.
