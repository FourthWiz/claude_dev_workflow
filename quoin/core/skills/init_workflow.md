# init_workflow

Runtime-neutral intent for the init_workflow skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Bootstrap the per-project workflow structure so that all downstream skills
(planning, architecture review, gating, cost tracking, session handoff) have
a consistent foundation to operate against. This means creating the standard
`.workflow_artifacts/` directory tree, initializing memory placeholder files,
adding `.workflow_artifacts/` to the project's `.gitignore`, detecting and
offering migration for any legacy layouts found, and handing off to the
discover skill so downstream skills have a baseline inventory immediately.
The skill is per-project, not per-machine. Machine-level setup (deploying
skills to the host runtime's global skills directory, writing global rules
files, configuring global permissions) is out of scope.

## When to use

- First-time setup: the project folder exists but has no `.workflow_artifacts/`
  structure yet.
- Re-initialization: `.workflow_artifacts/` exists but the user explicitly
  requests a re-init (existing memory files are preserved).
- The user invokes this skill by name or asks to "initialize the workflow",
  "set up the workflow", or "bootstrap the workflow" in a project.

## Prerequisites

The host runtime's project-level bootstrap must have been run before this
skill is invoked. For example, the host runtime may require a project-config
file (such as a project-level instructions file) to be present before
per-project skills can operate. This skill is responsible only for the
workflow-layer setup that sits on top of that foundation. If the prerequisite
is missing, the skill MUST stop and instruct the user to complete the
host-runtime bootstrap first, then re-invoke this skill.

## Inputs

- Project root path: the directory in which `.workflow_artifacts/` will be
  created. Typically the current working directory; confirmed with the user
  when ambiguous.
- Optional pre-existing paths that indicate legacy layouts (any combination
  may be present):
  - `memory/` at the project root (old layout before the `.workflow_artifacts/`
    consolidation).
  - `finalized/` at the project root (companion to the legacy `memory/`).
  - `quoin/memory/` (layout where memory was nested inside the quoin source
    directory).
  - `dev-workflow/QUICKSTART.md` (legacy quickstart location).
  - Host-runtime-specific symlink residue in global skill directories.
- Existing task folders at the project root that qualify for migration into
  `.workflow_artifacts/` (directories containing workflow plan files).

All reads MUST tolerate missing files — their absence is a "no signal"
outcome, not an error.

## Output

After a successful run, the following artifacts exist in the project:

Standard memory tree under `.workflow_artifacts/memory/`:
- `sessions/` — directory; holds per-session state files.
- `daily/` — directory; holds daily rollup files.
- `weekly/` — directory; holds weekly rollup files.
- `repos-inventory.md` — placeholder; populated by the discover skill.
- `architecture-overview.md` — placeholder; populated by the discover skill.
- `dependencies-map.md` — placeholder; populated by the discover skill.
- `git-log.md` — placeholder; populated by the discover skill.
- `lessons-learned.md` — initialized with the template header; accumulates
  over time.
- `workflow-rules.md` — initialized with a header; reference summary of the
  workflow system.
- `workflow-suggestions.md` — initialized with the template header; captures
  Tier 3 suggestions.

Additional output:
- `.workflow_artifacts/QUICKSTART.md` — command reference, copied from the
  location where the host runtime's installer deployed it. If the deployed
  copy is not found, a fallback stub is written so the project is still
  usable.
- `.gitignore` augmentation — `.workflow_artifacts/` is added to the project's
  `.gitignore` if not already present; the file is created if it does not
  exist.

The cost-ledger row at `.workflow_artifacts/<task-name>/cost-ledger.md` is
written ONLY when a task context is active for this invocation (see "Behavior
contract" — conditional cost recording below). Standalone invocations skip
cost recording.

Note: inventory content (`repos-inventory.md`, `architecture-overview.md`,
`dependencies-map.md`, `git-log.md`) is produced by the discover skill during
the mandatory handoff at the end of bootstrap — NOT by this skill directly.

## Behavior contract

- MUST never overwrite `.workflow_artifacts/memory/` contents on re-init.
  Accumulated knowledge (lessons, sessions, weekly rollups) is preserved
  across re-runs. Missing placeholder files are created; existing files are
  left intact.
- MUST be idempotent on re-init: existing files are preserved, missing files
  are created, existing directories are not re-created.
- MUST add `.workflow_artifacts/` to the project's `.gitignore` if the entry
  is not already present. Creates the `.gitignore` file if it does not exist.
- MUST detect and offer migration for legacy layouts:
  - Root-level `memory/` → `.workflow_artifacts/memory/` (with companion
    `finalized/` if present).
  - Root-level task folders with workflow plan files → `.workflow_artifacts/`
    (confirmed per folder before moving).
  - `quoin/memory/` → `.workflow_artifacts/memory/` (merging missing files
    only; never overwriting existing ones).
  - `dev-workflow/QUICKSTART.md` legacy location — offer move, delete, or
    keep, with a safety check: if the directory also contains an installer
    or setup file, it is likely the cloned source repo and the default action
    is keep.
  - Host-runtime-specific symlink residue in global skill directories — the
    adapter may extend this detection; the contract describes only the
    detection intent, not the cleanup command syntax.
  All migrations are opt-in per detected case; the skill MUST prompt the user
  before moving or deleting any file.
- MUST invoke the discover skill at the end of bootstrap so downstream skills
  have a baseline inventory. This handoff is mandatory and synchronous; the
  user expects a ready-to-use setup at end of bootstrap. If the discover skill
  finds no repositories, that is a valid outcome — memory files remain as
  placeholders.
- MUST NOT auto-invoke any downstream phase after discover (the architect
  skill, planning, gating, implementation, review, finalization, or any other
  workflow step). After the discover handoff completes, control returns to the
  user.
- Cost-ledger writes are CONDITIONAL. The skill MAY run standalone (no task
  context — invoked by a user setting up the workflow for the first time) or
  as part of an active task (invoked by the run orchestrator or by a user
  inside an open task folder). The skill MUST append a row to
  `.workflow_artifacts/<task-name>/cost-ledger.md` only when a task name is
  determinable from the invocation context or active session state; otherwise
  it MUST skip cost recording. init_workflow joins the set of conditional
  cost-ledger skills (the other conditional skills per the shared rules are
  the discover, gate, start-of-day, capture-insight, and triage skills).

## Out of scope

- Host-runtime install mechanics: deploying skills or scripts to the host
  runtime's global directories, writing global rules files, or configuring
  global permissions.
- Permission model wiring: creating or updating host-runtime-specific
  permission configuration files (e.g., access-control JSON files in global
  config directories).
- Slash-command vs. other-invocation grammar: the contract does not specify
  how the host runtime maps user input to this skill.
- Model-tier selection and the self-dispatch concern: the runtime adapter
  chooses the model tier and dispatch mechanism.
- The prompt-cache preamble mechanism: a runtime adapter concern.
- The specific path at which the host runtime deploys the quickstart reference
  file: the adapter knows its own deployment paths.
- Codex command files, Codex approvals, or Codex sandboxing.
- Runtime-neutral cost capture: still in the "Not Started" list post-Phase 21.
- Codex install-target verification: still in the "Not Started" list post-Phase 21.

## Notes

- init_workflow joins the conditional cost-ledger skills (per the shared
  workflow rules "Cost tracking → Conditional skills"). When no task is active,
  every other behavior in this contract still applies — only the cost-ledger
  row is suppressed.
- Legacy-layout migration is opt-in per detected case. The skill MUST detect
  legacy signals and surface them to the user, but MUST NOT move or delete
  files without explicit confirmation.
- The discover handoff is mandatory and synchronous. "Synchronous" here means
  the skill does not return control to the user until discover has run and
  produced its output. The user expects a ready-to-use setup at end of
  bootstrap, not a deferred background scan.
- The QUICKSTART fallback stub is intentional: it ensures the project has a
  usable command reference even when the host runtime's installer has not been
  run. The adapter should make the fallback stub clearly indicate that a fresh
  install of the host runtime will produce a richer version.
- This skill is the 21st and final Phase 6–21 migration in the runtime-
  portability effort. All 28 skills now have a portable intent doc in
  `quoin/core/skills/` and a Claude adapter in
  `quoin/adapters/claude/skills/`. The `.workflow_artifacts/<task-name>/`
  path convention is the universal artifact storage layout shared across all
  runtimes.
