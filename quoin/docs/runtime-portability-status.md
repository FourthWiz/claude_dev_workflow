# Runtime Portability Status

This page tracks the current migration state.

## Claude Code

Status: installable.

- `bash quoin/install.sh` remains the supported install command.
- Active Claude rules remain in `quoin/CLAUDE.md`.
- Active Claude skills remain in `quoin/skills/`, EXCEPT the ten skills
  migrated across Phases 6–10 (`capture_insight`, `triage`, `start_of_day`,
  `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`,
  `thorough_plan`), which install from
  `quoin/adapters/claude/skills/<name>/SKILL.md`.
- Portable intent docs for the migrated skills live at
  `quoin/core/skills/capture_insight.md`,
  `quoin/core/skills/triage.md`,
  `quoin/core/skills/start_of_day.md`,
  `quoin/core/skills/review.md`,
  `quoin/core/skills/plan.md`,
  `quoin/core/skills/critic.md`,
  `quoin/core/skills/revise.md`,
  `quoin/core/skills/revise-fast.md`,
  `quoin/core/skills/architect.md`, and
  `quoin/core/skills/thorough_plan.md`.
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

- Skill bodies in `quoin/skills/` (stubs only for the 10 migrated skills; full bodies now in `quoin/adapters/claude/skills/<name>/SKILL.md`).
- Slash-command invocation model.
- Agent and Skill dispatch instructions.
- Prompt-cache preamble generation.
- Claude model frontmatter.
- Claude JSONL session and cost plumbing.
- `ccusage` integration.

## Not Started

- Generated Claude skill files.
- Generated Codex adapter files.
- Split shared skill intent from runtime overlays — partial: `capture_insight`, `triage`, `start_of_day`, `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`, and `thorough_plan` shipped under the adapter pattern across Phases 6–10.
- Execution-loop skills (`implement`, `gate`, `run`) and lifecycle/setup/support skills (`end_of_task`, `end_of_day`, `weekly_review`, `cost_snapshot`, `init_workflow`, `discover`, `expand`, `rollback`) remain future work; each warrants its own migration pass.
- Runtime-neutral cost capture.
- Codex install target verification.
