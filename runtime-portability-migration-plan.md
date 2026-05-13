# Incremental Quoin Runtime-Portability Plan

## Summary

Refactor Quoin in small, low-risk steps. Each step should leave Claude Code behavior intact and make one boundary clearer. Codex support starts as repo-local instructions and documentation, not a runtime installer.

Status note: this was the first-pass migration plan. As of Phase 26, Codex
support still has no global installer or command-file contract, but it now also
includes generated/scaffolded repo-local skill adapter docs under
`quoin/adapters/codex/skills/` for all 21 portable skills.

## Step 1: Add The Boundary Docs

Create documentation only.

- Add `quoin/docs/runtime-portability.md`.
- Define three buckets:
  - Portable core: `.workflow_artifacts`, task/stage layout, artifact formats, memory, validation, path resolution.
  - Claude adapter: `install.sh`, `CLAUDE.md`, slash commands, `~/.claude`, Agent/Skill dispatch, preambles, JSONL, `ccusage`.
  - Codex adapter: `AGENTS.md` and repo-local workflow guidance.
- Add `quoin/docs/effort-levels.md`.
- Define `low`, `medium`, `high`, `max` effort levels.
- Map current Claude tiers in docs only: Haiku -> low, Sonnet -> medium, Opus -> high/max.

## Step 2: Add Adapter Scaffolding

Create directories and README files only.

- Add `quoin/adapters/README.md`.
- Add `quoin/adapters/claude/README.md`.
  - State that current Claude implementation still lives at existing paths.
  - State that `bash quoin/install.sh` remains the supported Claude install path.
- Add `quoin/adapters/codex/README.md`.
  - State that Codex uses native repo instructions and native approval/sandbox behavior.
  - State that Quoin must not guess Codex global install paths.

## Step 3: Add Codex Instructions

Add one root instruction file.

- Create root `AGENTS.md`.
- Keep it short.
- Tell Codex:
  - Preserve `.workflow_artifacts` workflow semantics.
  - Use native Codex planning, approvals, sandboxing, and repo instructions.
  - Do not assume Claude slash commands exist.
  - Do not write guessed Codex install paths.
  - Refer to `quoin/docs/runtime-portability.md`.

## Step 4: Light README Update

Make the public positioning accurate without overstating Codex support.

- Change "for Claude Code" framing to "for coding agents."
- Add "Runtime Support":
  - Claude Code: supported today.
  - Codex: scaffolded, repo-local instructions only.
- Keep existing Claude install commands unchanged.
- Keep `quoin/CLAUDE.md` references for Claude users.

## Step 5: Add Small Guard Tests

Add docs-level tests only.

- Assert `AGENTS.md` exists.
- Assert adapter docs exist.
- Assert `runtime-portability.md` classifies:
  - `path_resolve.py` as portable.
  - `validate_artifact.py` as portable.
  - `cost_from_jsonl.py` as Claude-specific.
  - `session_age_guard.py` as Claude-specific.
  - `build_preambles.py` as Claude-specific.
- Assert Codex docs do not mention guessed install paths like `~/.codex`.
- Assert README still contains `bash quoin/install.sh`.

## Step 6: Run Checks

Run only focused checks.

- `python3 -m pytest quoin/dev/tests/test_path_resolve.py`
- `python3 -m pytest quoin/dev/tests/test_validate_artifact.py`
- `python3 quoin/scripts/build_preambles.py --check`
- New docs tests from Step 5.

## Not In This Pass

- No moving `skills/`.
- No moving scripts into `core/`.
- No Codex installer.
- No generated skill system.
- No rewrite of all `SKILL.md` files.
- No behavior change to `install.sh`.
- No change to existing Claude user workflow.

## Assumptions

- First pass optimizes for clarity and reversibility.
- Claude compatibility is mandatory.
- Codex support begins as thin repo-local guidance.
- Physical file moves happen only after the boundary docs and tests are in place.
