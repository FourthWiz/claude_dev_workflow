# Runtime Portability Status

This page tracks the current migration state.

## Claude Code

Status: installable.

- `bash quoin/install.sh` remains the supported install command.
- Active Claude rules remain in `quoin/CLAUDE.md`.
- Active Claude skills remain in `quoin/skills/`, EXCEPT the twenty skills
  migrated across Phases 6–20 (`capture_insight`, `triage`, `start_of_day`,
  `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`,
  `thorough_plan`, `gate`, `implement`, `rollback`, `end_of_task`, `run`,
  `end_of_day`, `weekly_review`, `cost_snapshot`, `expand`, `discover`), which install from
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
  `quoin/core/skills/architect.md`,
  `quoin/core/skills/gate.md`,
  `quoin/core/skills/thorough_plan.md`,
  `quoin/core/skills/implement.md`,
  `quoin/core/skills/rollback.md`,
  `quoin/core/skills/end_of_task.md`,
  `quoin/core/skills/run.md`,
  `quoin/core/skills/end_of_day.md`,
  `quoin/core/skills/weekly_review.md`,
  `quoin/core/skills/cost_snapshot.md`,
  `quoin/core/skills/expand.md`, and
  `quoin/core/skills/discover.md`.
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

- Skill bodies in `quoin/skills/` (stubs only for the 20 migrated skills; full bodies now in `quoin/adapters/claude/skills/<name>/SKILL.md`).
- Slash-command invocation model.
- Agent and Skill dispatch instructions.
- Prompt-cache preamble generation.
- Claude model frontmatter.
- Claude JSONL session and cost plumbing.
- `ccusage` integration.

## Not Started

- Generated Claude skill files.
- Generated Codex adapter files.
- Split shared skill intent from runtime overlays — partial: `capture_insight`, `triage`, `start_of_day`, `review`, `plan`, `critic`, `revise`, `revise-fast`, `architect`, `thorough_plan`, `gate`, `implement`, `rollback`, `end_of_task`, `run`, `end_of_day`, `weekly_review`, `cost_snapshot`, `expand`, and `discover` shipped under the adapter pattern across Phases 6–20.
- Lifecycle/setup/support skill (`init_workflow`) remains future work; it warrants its own migration pass.
- Runtime-neutral cost capture.
- Codex install target verification.
