# Changelog

All notable changes to Quoin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **`/end_of_day` orphan-reconciliation pre-pass + `/end_of_task` flag-fold, orchestrator-suffix-aware** (IVG-137; v0.11.42). Two new session-lifecycle mechanisms close the "already-covered session still nags as an orphan" gap: (1) `/end_of_day --recover-orphans` gains a Step 0a covered-but-due reconciliation pre-pass — `find_covered_due_sessions()` (new, in `select_unprocessed_sessions.py`) auto-flips `end_of_day_due: no` on sessions whose base task slug already appears in a daily body, before the existing flag=NO orphan detection runs, so a covered session is never surfaced as an orphan in the same run; (2) `/end_of_task` gains a Step 3a single-CLI flip (`flip_finalized_task_sessions()` / `--flip-finalized-task`) that marks a finalized task's sessions `end_of_day_due: no` with a `finalized_by_end_of_task` provenance marker, consumed by a new `find_finalized_marked()` producer (`--include-finalized-marked`, riding the existing `--show-window` call) so finalized work still appears in the next same-window `/end_of_day` digest instead of silently vanishing. Both paths share a guarded `_base_slug()` helper (also folded into the pre-existing `find_orphans()`, closing a Step 0a↔Step 0 same-run self-contradiction for the orchestrator-suffixed case) that strips a trailing `-orchestrator` only when a bare sibling session exists, so a genuinely `...-orchestrator`-named task is never misclassified. Opt out with `QUOIN_DISABLE_EOD_RECONCILE` (reconcile pre-pass) and `QUOIN_DISABLE_EOT_FLAG_FLIP` (end_of_task flip). **Scope note (honesty, not a bug):** this round's fix covers only the `-orchestrator` suffix family (19 of ~105 known-affected files in the reference project home, roughly 18% of the false-orphan wall) — the much larger phase/stage-suffixed population (`-review`, `-implement`, `-sN`, `-stage-a`, etc., ~86 files) is deliberately out of scope this round (an unsafe naive generalization was identified and rejected — see the plan's Decisions) and continues to surface as orphans under `--recover-orphans` exactly as before, whether the underlying session was reconciled via the Step 0a pre-pass or flipped via the `/end_of_task` fold — the same phase/stage-suffix limitation applies to both paths, not just the reconcile pre-pass. A follow-up generalization is recommended as a separate ticket.
- **`/start_of_day` / session-start missing-EOD banner: same-day vs cross-day recommendation split** (IVG-137; v0.11.42). The missing-EOD banner in `sessionstart.sh`, the nudge in `sessionend.sh`, and `/start_of_day` Step 1 now branch on the flagged session's date: if every flagged session is dated today, the banner recommends `/checkpoint`; if any predates today, it recommends `/end_of_day`. The pending-insights-only signal (no dated session to branch on) keeps the prior unconditional `/end_of_day` wording unchanged.
- **`eod-refresh-routine.md` opt-in cron doc, registered for deployment** (IVG-137; v0.11.42). Mirrors `discovery-refresh-routine.md`; documents that unattended cloud `/schedule` EOD is best-effort (sandboxed cron likely cannot read the Drive-mounted `.workflow_artifacts/`) and that the `/end_of_task` flag-fold above is the primary, reliable mechanism. Registered in `installer.py`'s `TIER1_MEMORY_FILES` so it actually deploys via `install.sh`/`deploy_drift_check.py` rather than being silently skipped.
- **`/cleanup` sweeps stale `sessions/*.body.tmp` / `*.tmp` leftovers** (IVG-137; v0.11.42). Crashed Class-A-writer temp files under `memory/sessions/` are now trash-moved (recoverable) by the existing `/cleanup` sentinel sweep; `.md` session files are never touched.

### Changed

- **checkpoint: `/checkpoint --restore` decision now delegates to `checkpoint_picker.py`** (IVG-139, S-3; v0.11.37). The interactive restore picker's ~430 lines of decision prose (Step 1.0) in `quoin/adapters/claude/skills/checkpoint/SKILL.md` now shells out to the deployed `checkpoint_picker.py` module (landed in S-2) and renders its JSON Verdict into the unchanged interactive flow (same-session `AskUserQuestion`, Read re-fire, pending-prompt rehydrate), instead of re-deriving the decision inline. The Verdict is parsed with a `python3 -c` one-liner (no `jq` dependency) whose fields are joined on the ASCII Unit Separator (`\x1f`) rather than tab — TAB is an IFS-whitespace character, so `IFS=$'\t' read` collapses empty fields on bash 3.2.57 (the macOS default) and silently mis-binds `consumed_sentinel_path`/`derived_task`/`reason` on nearly every real Verdict. The entire prose picker is retained verbatim as a labelled **fail-OPEN fallback** for one release, so a bad module deploy degrades to today's exact behavior rather than to nothing. Three consciously-ratified behavior deltas ship with the rewire: (1) the module auto-picks the single freshest winner and no longer offers the interactive numbered picker when 2+ candidates exist and the freshest is suppressed — it routes to B3 session-state synthesis, bypassing a valid older same-task candidate (now regression-guarded by a characterization fixture); (2) a net-new `kind=='thorough-plan-progress'` route that STOPs restore and points the user to `/thorough_plan`; (3) reduced-detail suppression warnings on the module path (`auto-pick suppressed (${reason})`), since the module discards the suppressed candidate's task/path/age — full detail survives only in the prose fallback.

### Added

- **`/specify` wired into the pipeline** (IVG-127, stage 4) — `/run` gains a SPECIFY phase (Phase 1.5) + Checkpoint A0 between discover and architect; `/gate` gains a spec→architect document gate; `/architect` and `/thorough_plan` offer an advisory, non-blocking "produce a spec?" prompt (Medium/Large only, Small skips); `/architect` and `/plan` read the task-root `spec.md` at bootstrap when present; `/review` gains a `## Spec Compliance` output section (grandfathered "No spec — verified against plan only." when absent). Canonical flow (`CLAUDE.md`) and the portable `rules.md` flow string updated to include `specify`. Absence of `spec.md` remains a no-op everywhere (grandfather, AC-3).
- **post-merge deploy-drift guard: `/gate` detects stale deployed `~/.claude` copies vs quoin source** (IVG-136). A new adapter CLI `deploy_drift_check.py` (deployed to `~/.claude/scripts/`) compares the deployed skills / scripts / core-scripts / Tier-1 memory files against what `bash quoin/install.sh` would write, reusing the installer's own manifest tuples and substitution logic (`compute_drift` + `expected_deployed_content` in `installer.py`) so the checker can never disagree with the deploy path. It fires only when the diff touches `quoin/**` or `src/quoin/**` (out-of-scope diffs exit 0 without importing the `quoin` package at all). `/gate` wires it into three checklist regions: post-implement it is a non-blocking ⚠️ WARN; post-review it is a **blocking FAIL** (stale deployed copies at the pre-merge gate mean review smoke-testing ran against old code). Exit-code contract is strictly fail-OPEN — only exit 1 (drift found) can ever block; quoin-unimportable, unresolvable source, git errors, and any unexpected exception all degrade to exit 3 (WARN). A clean PASS names exactly which categories were checked vs. NOT covered (hooks, `CLAUDE.md`, `settings.json`, dashboard assets, `QUICKSTART.md` are out of v1 scope) so a broad-trigger PASS can't be misread as full deploy-tree parity. Opt out with `QUOIN_DISABLE_DEPLOY_DRIFT=1`.
- **spec.md artifact type — Class A validator type + Tier-1 registration for per-task and repo-level spec.md** (IVG-127, stage 1). No skill/flow changes yet; grandfathered (absence never an error).
- **`/specify` skill (standalone)** (IVG-127, stage 2) — Opus-tier interactive intent-elicitation skill producing a Class-A per-task `spec.md` (Context / User stories / Functional requirements / Acceptance criteria / Out of scope). Full adapter surface (core + Claude + legacy stub + Codex README) + §0′/§0″ dispatch + preamble + all drift registrations. Consumers and repo main spec are later stages.
- Repo main spec lifecycle (IVG-127, stage 3) — `/init_workflow` seeds `.workflow_artifacts/spec.md` via a post-discover "what is this repo about?" prompt; `/discover` offers an optional post-scan draft/refresh (diff-surfaced); `/specify` detects repo-purpose shifts and proposes a gated, user-approved repo-spec update. No new skill; grandfathered — absence of `spec.md` is never an error.

## [0.11.29] — 2026-07-06

### Fixed

- **agentdesk: fix "session name must be less than 0 characters" error on every launch** (IVG-135). Zellij has an upstream bug (zellij-org/zellij#4211, #2817) where an overly long default socket-dir path (e.g. macOS's `$TMPDIR`, which resolves to a long `/var/folders/<hash>/<hash>/T/` path) miscomputes zellij's remaining path budget, causing it to reject session names of ANY length with a cryptic, unrelated error. `agentdesk`/`setup-agentdesk.sh` now pin a short `ZELLIJ_SOCKET_DIR` (`${XDG_RUNTIME_DIR:-/tmp}/zellij-agentdesk-$(id -u)`) at module scope, guarded so a pre-set value is never clobbered. **Blast radius, stated honestly:** because this export is module-scope and `agentdesk.zsh` is sourced unconditionally from `~/.zshrc`, it redirects the zellij socket location for ALL zellij usage in any shell where agentdesk is installed — not only agentdesk-launched sessions. Pre-existing sessions created before this fix live under the old default dir and become invisible to `agentdesk`/`zellij attach` afterward; recover them with `ZELLIJ_SOCKET_DIR= zellij attach <name>` against the old dir, or start fresh. Any independent, non-agentdesk `zellij` usage in an agentdesk-installed shell will also land in the new dir going forward. Opt out per-shell with `unset ZELLIJ_SOCKET_DIR`. Also adds a required pre-flight guard that rejects (with a clear, actionable error) a session whose resolved socket path would still overflow the ~104/108-byte `AF_UNIX` limit even with the pinned short base (e.g. a pathologically long project-directory name) — instead of calling zellij and surfacing its cryptic error. The fix is synced into `setup-agentdesk.sh`'s legacy standalone-install heredoc fallback as well as its primary copy-from-source path.

## [0.11.25] — 2026-07-04

### Fixed

- **agentdesk: session-name collision now offers to attach (default) or start new, instead of always auto-suffixing** (IVG-109). Re-running `agentdesk` in a folder with a live same-named Zellij session now prompts to attach to it (the default, and the fix for the reported "always creates a new session" complaint) or start a fresh suffixed session (`_1`, `_2`, …) by replying `n`/`new`. Non-interactive callers (no TTY, e.g. scripts/CI) are unaffected — they always start a new suffixed session exactly as before. The standalone-installer fallback heredoc in `setup-agentdesk.sh` was synced to match.

## [0.11.22] — 2026-07-02

### Fixed

- **init_workflow: suppress Serena dashboard auto-open** (IVG-108). The Serena `start-mcp-server` snippet in Step 6.5 now includes `--open-web-dashboard false`, preventing the browser from auto-opening on every Claude Code session start. The dashboard remains accessible at its local URL; use `--enable-web-dashboard false` to disable it entirely.

## [0.11.17] — 2026-06-28

### Fixed

- **Permissions: remove invalid `Bash(rm:*.tmp)` allow rules from `/init_workflow`** (IVG-101). `/init_workflow` Step 4 was generating `"Bash(rm:*.tmp)"` and `"Bash(rm:*.body.tmp)"` entries in project `settings.json`. Claude Code rejects these at startup ("Invalid permission rule: :* pattern must be at the end") and they were semantically dead anyway (the deny list already has `Bash(rm:*)`). The rules are no longer generated; a regression test guards against reintroduction.

## [0.11.16] — 2026-06-28

### Added

- **Architect and plan: feature-existence pre-flight** (IVG-94). `/architect` and `/plan` now verify that features referenced in the task description actually exist in the codebase before writing `current-plan.md`. The check runs as a pre-flight step and surfaces missing features to the user for correction before planning proceeds, preventing plans built on phantom capabilities.

## [0.11.15] — 2026-06-27

### Added

- **Path resolve: nested `.workflow_artifacts/` guard** (IVG-97). `path_resolve.py` gained a `--verify-root` flag and guards against nested `.workflow_artifacts/` directories (e.g. a subproject inside the workspace). The resolver now aborts with a clear error rather than silently resolving to the wrong root, preventing artifact contamination across project boundaries.

## [0.11.13] — 2026-06-27

### Added

- **Dashboard: instrument-panel amber theme redesign** (IVG-87 T-07). Full visual redesign of the quoin dashboard with an amber instrument-panel color scheme. Scroll state and memory list selection are preserved across three-second poll cycles. Cost and activity heading labels corrected in counts mode. Added `memory.js` to the dashboard asset bundle so the memory tab loads correctly.

### Fixed

- **Dashboard: ETag cleared on memory tab switch** (IVG-87 T-09). Switching away from the memory tab and returning was returning a stale empty list because the old ETag was reused. The client now clears the ETag on tab change, forcing a fresh fetch on return.
- **Sentinel cleanup: UUID-aware 9-family sweep** (IVG-95). Session-start hook sentinel sweep was missing five of nine sentinel families, causing stale sentinels to pile up and trigger false-positive lifecycle events. The sweep now covers all nine families and uses a UUID-aware skip rule so it never removes the current or freshest session's sentinels. `/start_of_day` gains a Step 1b sentinel-health check that reports pile-up before the user's first prompt. `/cleanup` and `/sleep` allow-lists updated to match.
- **CLAUDE.md: Tier-1 catalog extracted to `tier1-files.md`** (PR #169). The always-English file catalog (previously inline in `CLAUDE.md`) was extracted into its own Tier-1 memory file, reducing `CLAUDE.md` size by the catalog's footprint while keeping the catalog independently testable.

## [0.11.7] — 2026-06-23

### Added

- **Proactive 1M-context dispatch precheck for all 19 §0 skills** (IVG-90). When Claude Code is running on a 1M-context SKU, the model name does not match what §0 expects, causing silent dispatch failures. All 19 cheap-tier skills now include a proactive precheck that detects the 1M SKU before dispatch and routes correctly. A `dispatch_config.py` module centralizes the config and per-tier sentinel cache. A `propagate_1m_s0_edit.py` script regenerates the precheck block from a single template across all 19 files.

### Changed

- **Minimum-tier guard: silent up-dispatch instead of `AskUserQuestion`** (IVG-91). The §0″ minimum-tier guard previously interrupted the user with a dialog when a skill was invoked on a cheaper model than it requires. It now silently re-dispatches to Opus without any prompt.

### Fixed

- **1M-context SKU recovery in §0 and §0' fail-open paths** (IVG-89). Dead precheck code in §0 and §0' was removed; 1M-context recovery is now handled in the fail-open path after dispatch, not as a pre-dispatch gate. Tests rewritten to match the post-dispatch recovery contract.
- **CLAUDE.md → `affected_tests.py` mapping for CLAUDE.md edits** (IVG-92). Edits to `CLAUDE.md` and format-kit/glossary files now correctly trigger the size-ceiling and affected-area tests in CI.
- **AgentDesk: `.kdl` rename step in dashboard layout temp file** (IVG-88). `mktemp` on macOS was generating a temp file without the `.kdl` suffix required by Zellij, causing layout load failures. The file is now explicitly renamed with the correct extension.

## [0.11.0] — 2026-06-20

### Added

- **Serena code-intelligence integration** (PR #158). When the Serena MCP server is present in a session (detected via a `ToolSearch` probe at task start), skills now automatically activate it and prefer Serena's symbol-level tools (find/rename symbols, cross-reference search, language-server navigation) over raw grep. The activation protocol is documented in `serena-activation.md` (a new Tier-1 memory file). The integration is strictly conditional: if Serena is absent, skills do nothing differently.
- **Python 3.10+ interpreter preference in `install.sh`** (PR #158). The installer now probes for a Python 3.10+ interpreter via pyenv before falling back to the system default, avoiding silent failures on machines where the default Python is 3.8 or 3.9.

## [0.10.3] — 2026-06-19

### Added

- **Dashboard: read-only memory browser pane** (IVG-50 S-4). A fourth tab in the quoin dashboard lists `lessons-learned.md` entries, daily briefings, and session archives. The pane is read-only and searchable in the browser; it uses a `memory.js` endpoint served by the dashboard server.

## [0.10.2] — 2026-06-18

### Added

- **Memory maintenance patterns** (IVG-50 S-3). A `memory-maintenance.yaml` config file defines protected-source patterns — entries that should never be auto-promoted to `lessons-learned.md` by `/sleep` because they are project-specific, transient, or already captured elsewhere. `/sleep` reads this file and skips entries matching any maintenance pattern before scoring. `memory-maintenance.md` added as a Tier-1 reference file.

## [0.10.1] — 2026-06-18

### Added

- **Selective lessons retrieval for planning and review skills** (IVG-50 S-1). `memory_select.py` computes relevance scores for `lessons-learned.md` entries against the active task description and returns only the relevant subset. `/plan`, `/architect`, and `/review` now inject only the matched lessons rather than the full file, reducing context-window pressure for repos with large lesson histories.
- **Memory referential-integrity checker** (IVG-50 S-2). `memory_check.py` scans all memory files for broken `[[link]]` cross-references, session files pointing to tasks that have moved to `finalized/`, and stale entries. Can be run standalone or wired into CI.

## [0.10.0] — 2026-06-18

### Added

- **Dashboard: ETag/If-None-Match/304 conditional polling** (IVG-76). The dashboard client now sends a hash of its last response; the server returns HTTP 304 if the state hasn't changed. This eliminates unnecessary DOM repaints and JSON parsing on the three-second poll cycle.

### Fixed

- **AgentDesk: dashboard server tied to Zellij session lifetime** (IVG-85). The dashboard server was continuing to run after the Zellij session exited, leaving a dangling process until the next desk launch. The EXIT trap now terminates the server on session end. `EXIT` traps are combined to prevent layout temp-file leaks.

## [0.9.28] — 2026-06-17

### Added

- **Branch-recovery recipe** (IVG-77). `branch-recovery.md` added as a Tier-1 memory file documenting the safe canonical recipe for recovering mis-placed commits from a protected branch. Pointers to this file added in `/implement`, `/gate`, `/review`, and `/end_of_task` skill files.

### Fixed

- **`validate_artifact`: exempt backtick-quoted IDs from V-05** (IVG-78). The V-05 validator was incorrectly rejecting backtick-quoted artifact IDs as bare cross-artifact references. Quoted IDs are now exempt.
- **`/sleep`: suppress stale-30-days penalty when `user_marked_yes`** (PR #150). An entry explicitly marked to keep was still being penalized for age. The scoring logic now checks the `user_marked_yes` flag before applying the staleness penalty.
- **Checkpoint: project-hash derivation corrected** (IVG-84). `/checkpoint --restore` was computing the wrong project hash on machines where the project root contains a symlink component. The derivation now uses the resolved absolute path.

## [0.9.21] — 2026-06-16

### Added

- **VS Code extension: full release** (IVG-54). Six stages shipped across June 13–15:
  - S-1: `SessionManager`, script-root detection, Activity Bar registration.
  - S-2: Control-panel webview with skill palette. Clicking a skill name sends the slash command to the Claude Code terminal via `sendText` with a Ctrl-U pre-clear.
  - S-3: Workflow tree view with current-phase highlighting; backed by a new `--emit-nodes` flag on `status_graph.py`.
  - S-4: Sessions-archive view — browse completed sessions without leaving VS Code.
  - S-5: Cost tab webview — shows the cost ledger for the active task.
  - S-6: Packaging (`vsce`), settings, CI, Marketplace publish. Extension published as `igorban.quoin-vscode` with a quoin cube+Q logo.
  - `ProjectContext` module handles multi-workspace roots; a project switcher overrides which project's artifacts are shown.
- **Drive conflict-copy detection** (IVG-75). `find_drive_conflicts.py` scans the workspace for Google Drive sync-conflict copies (e.g. `file (Ivan's conflicted copy).md`) and reports them. `status_graph.py` and `get_session_uuid.py` now ignore conflict copies when enumerating session files.
- **`get_session_uuid.py` core script** (PR #133). Replaces the previous `uuidgen`-based approach in cost-ledger generation, which produced different UUID formats on different platforms. The script reads the Claude session UUID directly from the JSONL stream.

### Changed

- **License: MIT → PolyForm Noncommercial 1.0.0** (IVG-83). Quoin is free for personal, research, and non-commercial use. Commercial use requires a separate license.

## [0.9.14] — 2026-06-12

### Added

- **AgentDesk: layout persistence** (IVG-82). AgentDesk remembers the layout you selected at first setup and uses it on subsequent launches without asking. A `--reset-layout` flag re-prompts when you want to change it.
- **Real-time token spend monitor + Spend tab** (IVG-62). A `spend_monitor.py` sidecar reads live token counts from `ccusage` output and exposes them to the AgentDesk spend pane. A dedicated Spend tab is added to both the Standard layout and dynamic layouts; the AgentDesk always includes it even when other tab sets vary.

### Fixed

- **Checkpoint: all path sites use resolved project root** (IVG-61). Multiple places in the checkpoint skill were using relative `.workflow_artifacts` paths that broke when the skill was invoked from a subdirectory. A `_PROJECT_ROOT` variable is now resolved once at script entry and used at every path site. A canary prose-form path test detects regressions.
- **§0' Pollution dispatch restored to 7 Opus-tier skills** (IVG-69). The §0' block had been accidentally stripped from the Opus-tier adapter SKILL.md files during a prior regeneration pass. Restored and guarded by a parity drift test.
- **AgentDesk: auto-suffix session names to avoid attaching to existing sessions** (PR #125). AgentDesk was sometimes attaching to an existing Zellij session with a matching name rather than creating a fresh one, causing layout confusion.

## [0.9.7] — 2026-06-08

### Added

- **Branch hygiene enforcement: three-layer guard** (IVG-70). Work can no longer silently land on `main` or `master`:
  1. `/implement` runs `branch_hygiene.py` at dispatch entry and prompts to create a feature branch if any repo involved is on a protected branch.
  2. `/gate` hard-fails if commits are detected ahead of upstream on a protected branch (commits-ahead signal, not bare on-main status).
  3. `/review` flags on-main commits as a diff-independent backstop.
  Configurable via `QUOIN_PROTECTED_BRANCHES` (csv, default `main,master`) and `QUOIN_DISABLE_BRANCH_HYGIENE=1`.
- **Affected-area test suite as hard gate precondition** (IVG-71). `affected_tests.py` maps changed files to test files using a configurable matcher. `/gate` and `/review` now run the affected-area suite as a hard precondition for APPROVED; an untested or failing affected suite blocks the APPROVED verdict. A base-branch merge-base diff closes the gap where committed-but-clean branches were incorrectly passing.
- **`/cleanup` skill** (IVG-68). Trash-moves stale sentinels and old checkpoint files into a recoverable `trash/<date>/` archive using a UUID-aware skip rule (never removes the current or freshest session's sentinels). Fires automatically as the first step of `/checkpoint` unless `--no-cleanup` is passed.

### Fixed

- **Dispatch sidecar and `git_root_for_dispatch.py` added to `CORE_SCRIPTS`** (PR #122). Both scripts were missing from the installer's core-scripts list, causing `quoin doctor` false negatives and deployment gaps.

## [0.9.2] — 2026-06-06

### Added

- **Quoin dashboard MVP** (IVG-63). A standalone local web server (`quoin dashboard`) that shows workflow state in a browser tab:
  - `dashboard_model.py` — portable core script that scans `.workflow_artifacts/`, identifies tasks and stages, reads cost ledgers, and returns structured JSON. Runtime-neutral; no adapter-specific imports.
  - `dashboard_server.py` — `ThreadingHTTPServer` wrapper serving the SPA and the model API.
  - Vanilla-JS single-page app with task cards, stage tabs, phase timeline, and cost breakdown. Scroll state preserved across poll cycles. Favicon embedded as base64 SVG.
  - `quoin dashboard` CLI subcommand; installer wiring for all assets.
  - AgentDesk gains an opt-in dashboard prompt at desk launch (saved after first answer).
- **`quoin router` command group** (IVG-64). `quoin router setup` configures Claude Code Router (CCR) with an OpenRouter API key and writes the proxy config. `quoin router status` shows proxy liveness. `ccr code` launches Claude Code through the proxy. AgentDesk gains a `ccr` window-type token so the proxy window appears in the desk layout.
- **`quoin models` command** (IVG-65). Shows the tier-to-open-model mapping (haiku-, sonnet-, and opus-equivalent open models available via CCR/OpenRouter).

## [0.7.2] — 2026-06-04

### Added

- **`/status` slash command** (IVG-59). Lightweight Haiku-tier skill that reads `.workflow_artifacts/` and emits a pipeline graph showing which phases are complete, active, and pending. Wired into AgentDesk: the status pane refreshes on each session start. The VS Code extension's workflow tree view reads the `--emit-nodes` JSON output from the same `status_graph.py` script.
- **AgentDesk: Zellij `copy_command` setup** (PR #111). `agentdesk setup` now configures Zellij's `copy_command` for the host OS during first-time setup, so terminal copy-paste works without manual KDL editing.

### Fixed

- **Checkpoint: fast-path `--restore` applies cross-task guard** (PR #112). The fast-path restore was bypassing the cross-task guard that prevents restoring a checkpoint from a different task into the current context.
- **AgentDesk: `mktemp` template fixed for macOS** (PR #113). The generated KDL layout temp file used a GNU `mktemp` template syntax that fails on BSD/macOS. Corrected to use a macOS-compatible template.

## [0.6.0] — 2026-05-30

### Added

- **AgentDesk with dynamic layout support** (IVG-60, PR #107). `agentdesk` is a Zellij-based terminal workspace for AI work. Running `agentdesk setup` creates a Zellij session with configurable panes for the agent terminal, spend monitor, workflow status, and (optionally) the quoin dashboard. Dynamic layouts are generated from a template at launch; static layouts can also be used. First-time setup runs interactively; subsequent launches reuse the saved layout.

  Added to the quoin repo under `quoin/tools/agentdesk/`. Documented in README.

## [0.5.19] — 2026-05-30

### Added

- **`/pr` skill: full pull request lifecycle** (IVG-53, PR #98). Handles pre-flight checks (not on main, `gh` CLI available and authenticated), optional version bump detection, push to remote, `gh pr create` with structured title and body, wait for merge, and switch to the merge target branch after merge. Invoked explicitly after `/end_of_task` — never auto-created.
- **`AskUserQuestion` option lists for multi-choice prompts** (IVG-55, PR #100). Workflow skills that previously asked free-text questions (e.g. "which stage?", "restore or reference?") now surface structured option lists via `AskUserQuestion`, eliminating ambiguous text parsing.
- **Inline step summaries required from major skills** (IVG-52, PR #102). `/thorough_plan`, `/implement`, and `/review` now print a concise human-readable English summary at the end of each run (what was produced, main components, remaining concerns, artifact location). This is a REQUIRED rule in `CLAUDE.md` — the summary is a chat message, never written to disk.

### Fixed

- **ccusage v20 bulk format compatibility** (IVG-58). The cost tracking parser broke when `ccusage` changed its output to a bulk per-session format in v20. Both the old per-session format and the new bulk format are now handled.
- **Checkpoint: restore picker staleness fixes** (PR #105). Three staleness bugs (B1, B2, B3) in the restore picker were fixed — incorrect ordering of candidates when multiple checkpoints exist for the same session date, and stale entries surfacing above fresh ones.
- **Checkpoint: panic save on context-block** (PR #105). When the userpromptsubmit hook fires the block branch (context utilization above `QUOIN_BLOCK_BPS`), the hook now forces a skeleton checkpoint save before blocking, so no session state is lost even if the user closes the terminal.

## [0.5.0] — 2026-05-15

### Added

- **Checkpoint: non-blocking precompact flow and three save modes** (PR #85). Previously, the precompact hook blocked the conversation while saving state. The new design is non-blocking: the hook records utilization state asynchronously, and Claude decides whether to compact or save based on the threshold. Three explicit save modes:
  - `--mode restore` (default): saves state and writes a pending-restore sentinel.
  - `--mode load-as-reference`: saves state as reference-only; a fresh session can consult it without fully restoring.
  - `--mode mid-agent`: saves state mid-flight inside a long-running agent without touching session banners.
  `COMPACT_FIRST_BPS` tunable controls at which utilization level checkpoint recommends compacting before saving.
- **Checkpoint: compact-ordering fixes** (PR #88). A Step 1.4 "compact-already-ran skip path" detects a `compact-happened` sentinel written by the new `postcompact.sh` hook and skips a redundant save after auto-compact. The `--after-compact` flag is deprecated in favour of sentinel-based detection.
- **Worktree dispatch for nested-git contexts** (PR #95). The `WorktreeCreate` hook now supports nested-git worktree isolation for subagent dispatch, preventing Git operations in one subagent from interfering with another.
- **`skillOverrides` injection in `deploy_hooks`** (PR #91). The installer can inject custom skill overrides into `settings.json` during install, allowing site-specific skill behaviour (custom `/review` templates, modified `/gate` thresholds) without forking the core.
- **`/end_of_task` working-tree cleanup scan** (PR #97). Before committing, `/end_of_task` now scans for common dirty-state artefacts (debug files, `.tmp` files, unreferenced test fixtures) and reports them for the user to review.
- **CLAUDE.md: verbose sections extracted to memory files** (PR #86). `cost-ledger-format.md`, `dispatch-guide.md`, `hooks-table.md`, and `lifecycle-guide.md` extracted from `CLAUDE.md` into `~/.claude/memory/`. Skills read the relevant file during bootstrap. Net reduction of ~10,500 characters in installed `CLAUDE.md` size.

### Fixed

- **`/implement`: 1M-context SKU-mismatch precheck** (PR #96). Added a §0-1m-context-precheck to avoid dispatch failures when `implement` is invoked on a 1M-context model.
- **End-of-day rollup: date-window session selection** (PR #87). Session selection now uses a date-window + shared helper that covers all unprocessed sessions since the last daily cache, not just today's files. A `merge_daily()` function handles the double-rollup edge case idempotently.

## [0.3.3] — 2026-05-14

### Fixed

- **Checkpoint bug trio:** Three `/checkpoint` + precompact hook bugs fixed via a shared UUID identity model. The checkpoint restore now verifies task context matches the active task before loading artifacts. The `userpromptsubmit` hook correctly surfaces pending-restore state. See PR #82.
- **Installer deny rules:** `installer.py` now writes `rm -rf` deny rules to `settings.json` during install, preventing accidental destructive operations.
- **Test suite:** Restored `pytestmark skipif` on `test_install_fresh_clone`; added T-06 behavioral tests for the checkpoint-bug-trio fixes.

## [1.0.0] — 2026-04-27

### Added

The initial Quoin release consolidates six foundation stages built over the quoin-foundation task. Each stage added a concrete, user-visible capability:

- **Stage 1 — §0 Model dispatch preamble:** The 12 cheap-tier skills (gate, implement, rollback, etc.) self-dispatch to their declared model tier (Haiku or Sonnet) when invoked from a more expensive session. Fail-open: if dispatch is unavailable, the skill proceeds at the current tier with a one-line warning rather than aborting. Two stable runtime diagnostic strings are preserved verbatim across all 12 SKILL.md files as stable identifiers. See `.workflow_artifacts/quoin-foundation/finalized/stage-1/`.

- **Stage 2 — ccusage fallback for cost tracking:** `/cost_snapshot` and `/end_of_task` now call `cost_from_jsonl.py` when `npx ccusage` is unavailable. The script reads raw Claude session `.jsonl` files directly, so cost reporting works without the ccusage npm package. See `.workflow_artifacts/quoin-foundation/finalized/stage-2/`.

- **Stage 3 — Stage-subfolder convention + `path_resolve.py`:** Multi-stage tasks store per-stage artifacts under `<task>/stage-N/` subfolders. `path_resolve.py` resolves the correct subfolder from a plain-language invocation (`/implement stage 3 of my-task`). Covers 7 fixture cases including legacy grandfathering. See `.workflow_artifacts/quoin-foundation/finalized/stage-3/`.

- **Stage 4 — Architect Phase 4 critic loop:** `/architect` runs an internal critic loop (up to 2 rounds by default, 4 in strict mode) before returning `architecture.md` as final. The architecture is now a converged artifact, not a first draft. See `.workflow_artifacts/quoin-foundation/finalized/stage-4/`.

- **Stage 5 — Native Haiku summarizer:** The Class B v3 artifact writer uses a native Haiku Agent subagent (Step 2) instead of the deprecated `summarize_for_human.py` Python script. `summary-prompt.md` is a Tier 1 hand-edited prompt template deployed to `~/.claude/memory/`. The obsolete script and its test are removed from both the source tree and `install.sh`. See `.workflow_artifacts/quoin-foundation/finalized/stage-5/`.

- **Stage 6 — Quoin rebrand + QUICKSTART relocation + README:** `dev-workflow/` renamed to `quoin/` (140 internal references updated via mass-sed with v2-historical fixture excluded). `/init_workflow` Step 7 now copies `QUICKSTART.md` from the Quoin source clone to `.workflow_artifacts/QUICKSTART.md` (the new location); the old inline template is removed. `QUICKSTART.md` updated to enumerate all 21 canonical skills. Top-level `README.md` rewritten with Quoin branding and hero/architecture images. This CHANGELOG added. See `.workflow_artifacts/quoin-foundation/stage-6/`.

### Upgrade notes

**GitHub repository rename:**
The GitHub repository has been renamed from `FourthWiz/claude_dev_workflow` to `FourthWiz/quoin`.
GitHub automatically redirects all existing `git clone`, `git pull`, and `git fetch` operations from the old URL — your local clone continues to work without any changes.

Optional cleanup (non-blocking):
```bash
git remote set-url origin git@github.com:FourthWiz/quoin.git
```

Verify with `git ls-remote origin` — returns exit code 0 either way (auto-redirect or updated URL).

**`~/.claude/CLAUDE.md` markers stay unchanged:**
The install.sh markers used to inject workflow rules into `~/.claude/CLAUDE.md` remain:
```
# === DEV WORKFLOW START ===
# === DEV WORKFLOW END ===
```
These markers are intentionally preserved verbatim for backward compatibility with any tooling that scans for them. A seeded-upgrade test (`test_install_seeded_claude_md.py`) verifies that re-running `install.sh` replaces — never appends — the marker section.

**Old QUICKSTART location:**
If you have `(project)/dev-workflow/QUICKSTART.md` from a previous install, `/init_workflow` will detect it and prompt for migration with three options: move, delete, or keep. The new canonical location is `.workflow_artifacts/QUICKSTART.md` (copied from `<your-quoin-clone>/QUICKSTART.md` during `/init_workflow`).

**Manual verification step (post-rename):**
Run `git remote -v` after the rename to confirm your remote URL. Run `git ls-remote origin` to confirm GitHub auto-redirect is active (exit code 0 = working).
