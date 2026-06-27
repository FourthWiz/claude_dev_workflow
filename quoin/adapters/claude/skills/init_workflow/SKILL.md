---
name: init_workflow
description: "Initializes the development workflow in a project folder. Creates the .workflow_artifacts/ structure, runs /discover to scan the codebase, and generates a quickstart guide. Requires install.sh to have been run first (installs skills to __QUOIN_HOME__/skills/ and workflow rules to __QUOIN_HOME__/CLAUDE.md). Use this skill for: /init_workflow, 'initialize workflow', 'set up dev workflow', 'install workflow', 'bootstrap workflow'. Run this once per project."
model: opus
---

# Initialize Development Workflow


*Portable intent doc: `quoin/core/skills/init_workflow.md`*

You set up the complete development workflow system in a project folder. This is the one-time bootstrap that makes all workflow commands available for a project.

## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)

This skill runs in the user's current session. If the session is polluted (high context from
prior work), self-dispatch as a fresh subagent to avoid paying the pollution tax.

Detection:
  - Read the most-recent session-state file: `.workflow_artifacts/memory/sessions/<today>-<task>.md`
    OR the fallback `.workflow_artifacts/memory/pollution-score-latest.txt`.
  - Parse the `pollution_score: N` field (integer).
  - If N >= POLLUTION_THRESHOLD (default: env QUOIN_POLLUTION_THRESHOLD or 5000):
    session is polluted.
  - Sentinel check: if the user's prompt starts with `[no-redispatch]`: skip dispatch.
  - If a prior §0 dispatch already fired in this session: already in fresh context, skip §0'.

Dispatch action (when pollution detected AND no sentinel AND no prior §0 dispatch):
  Determine dispatch contract fields:
    - Use the current working directory as the project root absolute path.

  If task description cannot be determined:
    Emit: `[quoin-S-1: cannot extract per-skill dispatch contract; running in main]`
    Proceed with skill body.

  Otherwise spawn an Agent subagent:
    model: "opus"
    description: "init_workflow — pollution-isolated dispatch"
    prompt: "[no-redispatch]\n/init_workflow <project root absolute path>"

  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path:
  If Agent tool unavailable or errors — classify the error first:
  - 1M-credit-class: if the error text contains the substring
      `Usage credits required for 1M context`:
      The §0' opus dispatch hit a 1M-context credit mismatch (IVG-89). Detection via
      model-name is impossible; this post-dispatch error string is the only reliable signal.
      Issue an `AskUserQuestion`:
        Question: "§0' opus dispatch failed with a 1M-context credit mismatch for /init_workflow.
        The parent session carries the 1M-context beta header which propagates to all
        subagent calls; Opus lacks 1M credits. How would you like to proceed?"
        Header: "1M credit mismatch"
        multiSelect: false
        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch to a
          standard-context model (e.g., /model opus), then re-invoke /init_workflow.
          The §0' dispatch will then land on standard Opus successfully."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the §0' dispatch this once. /init_workflow runs in the
          current session (may be polluted, but works). Emits a one-line advisory."
      On Option 1: print `[quoin: 1M-context credit mismatch; abort per user choice —
      switch with /model and re-invoke /init_workflow]` and STOP. Do NOT proceed to skill body.
      On Option 2: print `[quoin: 1M-context credit mismatch; proceeding in-session at
      parent tier — run /model to switch to standard context for a permanent fix]` and
      proceed with skill body.
  - Any other error (non-1M): Issue an `AskUserQuestion` (generic wording):
      Question: "§0' pollution dispatch failed for /init_workflow. Would you like to proceed
      in the current (polluted) session, or abort?"
      Header: "Dispatch error"
      multiSelect: false
      Option 1:
        label: "Abort — I'll diagnose and retry"
        description: "Stop here. Investigate the dispatch error, then re-invoke /init_workflow."
      Option 2:
        label: "Proceed in-session (polluted)"
        description: "Continue in the current session despite the dispatch failure.
        Performance may be degraded due to context pollution."
      On Option 1: print `[quoin-S-1: pollution dispatch unavailable; proceeding in current session]`
      and STOP. Do NOT proceed to skill body.
      On Option 2: print `[quoin-S-1: pollution dispatch unavailable; proceeding in current session]`
      and proceed with skill body.

Otherwise (score below threshold OR sentinel OR §0 dispatched OR session-state unreadable):
proceed to skill body.

## §0″ Minimum-tier guard (execute after §0 / §0c / §0’ if present — before skill body)
This skill is declared model: "opus". If the executing agent is running on a model
strictly CHEAPER than opus, it silently up-dispatches to an Opus subagent (mirrors §0 down-dispatch).

<!-- §0doubleprime-begin -->
Detection:
  - Read your current model from system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus. declared_tier = opus.
  - Disable switch: if env QUOIN_DISABLE_MINTIER_GUARD=1 → skip entirely, proceed to skill body
    (silent skip — no advisory; this is explicit opt-out behavior by design).
  - Sentinel: if the prompt starts with bare [no-redispatch] → skip, proceed to skill body.
  - Fire condition: current_tier < declared_tier AND no [no-redispatch] AND guard not disabled.

On fire (happy path — silent up-dispatch):
  spawn an Agent subagent:
    model: "opus"
    description: "init_workflow — min-tier up-dispatch"
    prompt: "[no-redispatch]\n<original user input verbatim>"
  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path (fires only when Agent dispatch fails):
  Classify the error text BEFORE proceeding:

  - 1M-credit-class: if error text contains `Usage credits required for 1M context`:
      Issue AskUserQuestion:
        Question: "§0″ up-dispatch to opus failed with a 1M-context credit mismatch for /init_workflow.
        The parent session carries the 1M-context beta header; Opus lacks 1M credits. How would you like to proceed?"
        Header: "1M credit mismatch"
        multiSelect: false
        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch to a standard-context
          model (e.g., /model opus), then re-invoke /init_workflow."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the up-dispatch this once. /init_workflow runs in the current session
          (below Opus, but works). Emits a one-line advisory."
      On Option 1: print `[quoin-mintier: 1M-context credit mismatch; abort per user choice —
      switch with /model and re-invoke /init_workflow]` and STOP.
      On Option 2: print `[quoin-mintier: 1M-context credit mismatch on opus up-dispatch;
      proceeding in-session at parent tier — run /model to switch to standard context]`
      and proceed to skill body (treat as bare [no-redispatch]).

  - Any other error: Issue AskUserQuestion (labels verbatim — drift relies on equality):
      Question: "/init_workflow requires Opus but this session is below Opus. Auto-dispatch to Opus failed. How would you like to proceed?"
      Header: "Min-tier"
      multiSelect: false
      Option 1:
        label: "Abort — run from an Opus session"
        description: "Stop here. Switch the session to Opus (/model opus) and re-invoke /init_workflow."
      Option 2:
        label: "Proceed at current tier (under-powered)"
        description: "Run /init_workflow on the current cheaper model. Quality may be reduced;
        emits a one-line advisory."
    Then:
      - Option 1: print `[quoin-mintier: aborted; re-invoke /init_workflow from an Opus session]` and STOP.
      - Option 2: print `[quoin-mintier: min-tier up-dispatch unavailable; proceeding at current tier per user choice]`, then proceed to skill body (treat as bare [no-redispatch]).
<!-- §0doubleprime-end -->

## When to use

- First time setting up the workflow in a new project
- User says `/init_workflow`, "set up the workflow", "initialize", etc.
- A project folder exists but has no `quoin/` structure yet

## Prerequisites

`install.sh` must have been run first. It installs skills to `__QUOIN_HOME__/skills/` and writes workflow rules to `__QUOIN_HOME__/CLAUDE.md`. This skill handles per-project initialization only — not the one-time machine setup.

## Session bootstrap

Note: `/init_workflow` initializes a project, not a task. Cost tracking requires a task context. Append to the cost ledger only if you were invoked as part of a task (e.g., via `/run`). Otherwise, skip cost recording.

If a task context is active: append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `init-workflow`.

## Process

### Step 1: Ensure project is initialized with `/init`

Check if the project has a `CLAUDE.md` file at its root. If it does NOT exist:

1. **STOP** and tell the user:
   > "This project hasn't been initialized with Claude Code yet. Please run `/init` first to create a `CLAUDE.md`, then re-run `/init_workflow`."
2. Do not proceed with subsequent steps. The `/init` command sets up the project-level `CLAUDE.md` and `.claude/` directory that the workflow depends on.

If `CLAUDE.md` already exists, skip this step — the project is already initialized. Proceed to Step 2.

This ensures the standard Claude Code foundation is in place before layering on the quoin setup.

### Step 2: Detect project root

Identify the project root. This is typically:
- The current working directory
- Or the folder the user specified

Confirm with the user if ambiguous:
> "I'll set up the workflow in `<path>`. Is this the right project root?"

### Step 2b: Ancestor .workflow_artifacts/ check

Before creating or using `.workflow_artifacts/` at the detected root, walk upward
from the project root, checking each ancestor directory (up to $HOME exclusive) for
a `.workflow_artifacts/` subdirectory: check `../.workflow_artifacts`,
`../../.workflow_artifacts`, and so on. (Note: the Python `_find_nested_ancestor()` in
`path_resolve.py` has no $HOME cap; this $HOME bound applies only to the SKILL.md
guidance for human-readable clarity. The cap is an adapter-layer policy — see D-04.)

If any ancestor directory contains `.workflow_artifacts/`, a parent project already
owns the artifact tree. In this case:

1. Warn the user:
   > ⚠️ A parent-level `.workflow_artifacts/` already exists at `<ancestor-path>`.
   > Using that as the project root to avoid creating nested artifact directories.
2. Set the **effective project root** to `<ancestor-path>` for all subsequent steps.
3. Do NOT create a new `.workflow_artifacts/` at the originally-detected root.

If no ancestor has `.workflow_artifacts/`, proceed normally with the detected root.

### Step 3: Check for existing setup and detect legacy layout

**Case: current layout (`memory/` at project root)**
If `memory/` exists at the project root (but `.workflow_artifacts/` does not), offer migration:

> ⚠️  Legacy layout detected: `memory/` exists at project root.
> The new layout consolidates all workflow artifacts under `.workflow_artifacts/`.
> I can migrate now:
>   - `memory/` → `.workflow_artifacts/memory/`
>   - `finalized/` → `.workflow_artifacts/finalized/` (if it exists)
> Your accumulated knowledge will be preserved.
> Migrate now? (yes/no)

Migration commands (on yes):
```bash
mkdir -p .workflow_artifacts
mv memory .workflow_artifacts/memory
[ -d finalized ] && mv finalized .workflow_artifacts/finalized
```

**Task folder detection** — also scan the project root for task folders to migrate:
- Candidate: any directory at project root that is NOT a git repo (`[ ! -d "$dir/.git" ]`) and NOT `.workflow_artifacts` itself
- Qualifies as a task folder if it contains BOTH `current-plan.md` AND at least one of `critic-response-*.md` or `review-*.md`
- Also qualifies: any non-git-repo directory containing a `finalized/` subdirectory (parent task container)
- Present detected list to user, ask confirmation per folder before moving
- Move confirmed folders: `mv <task-name> .workflow_artifacts/<task-name>`

**Legacy detection:** Check for `quoin/memory/` — this is the old layout where memory was nested inside quoin. If found:

```
⚠️  Legacy layout detected: quoin/memory/ exists.
    The new layout keeps memory/ under .workflow_artifacts/ at the project root.
    I can migrate it now: move quoin/memory/ → .workflow_artifacts/memory/
    Your accumulated knowledge (lessons, sessions, etc.) will be preserved.
    Migrate now? (yes/no)
```

If the user confirms, run:
```bash
mkdir -p .workflow_artifacts
mv quoin/memory .workflow_artifacts/memory
```

If `.workflow_artifacts/memory/` already exists (partial migration), merge by copying missing files only — never overwrite existing ones.

**Old symlinks cleanup:** Check for `.claude/skills/` containing symlinks into `quoin/skills/`. If found, remove them — skills are now global at `__QUOIN_HOME__/skills/`:
```bash
for f in .claude/skills/*/; do
  [ -L "${f%/}" ] && rm "${f%/}"
done
```

**Old skills directory:** If `quoin/skills/` exists, it is no longer needed. Offer to remove it:
```
quoin/skills/ is no longer needed (skills live at __QUOIN_HOME__/skills/).
Remove it? (yes/no)
```

**Re-init of current layout:** If `.workflow_artifacts/` already exists at the project root, tell the user:
> "This project already has a .workflow_artifacts/ setup. Re-initializing will preserve all memory files. Continue?"

**Never overwrite `.workflow_artifacts/memory/`.** It contains accumulated knowledge.

### Step 4: Configure Claude Code permissions

Create or update `.claude/settings.json` at the project root to allow workflow tool usage and deny destructive commands:

```bash
mkdir -p .claude
```

Then write `.claude/settings.json` using python3 (merge with existing if present):

```python
import json, os

path = ".claude/settings.json"
settings = json.load(open(path)) if os.path.exists(path) else {}

perms = settings.setdefault("permissions", {})
allow = perms.setdefault("allow", [])
deny = perms.setdefault("deny", [])

for p in ["Read", "Glob", "Grep", "Edit", "Write", "Bash(*)", "WebFetch", "WebSearch",
          "Bash(rm:*.tmp)", "Bash(rm:*.body.tmp)"]:
    if p not in allow: allow.append(p)

for p in [
    "Bash(rm:*)", "Bash(rm -rf:*)", "Bash(rmdir:*)",
    "Bash(git push --force:*)", "Bash(git push -f:*)",
    "Bash(git reset --hard:*)", "Bash(git clean -f:*)", "Bash(git clean -fd:*)",
    "Bash(git checkout -- .:*)", "Bash(git branch -D:*)",
    "Bash(chmod:*)", "Bash(chown:*)", "Bash(kill -9:*)",
    "Bash(killall:*)", "Bash(mkfs:*)", "Bash(dd:*)"
]:
    if p not in deny: deny.append(p)

# json.dump never emits trailing commas; if a human later hand-edits this file, run python3 -m json.tool to validate.
json.dump(settings, open(path, "w"), indent=2)
```

Run this with `python3 -c "..."` or write the file directly if python3 is unavailable. Tell the user what was configured.

### Step 5: Create the directory structure

Create the memory structure under `.workflow_artifacts/` at the project root:

```
<project-root>/
├── .workflow_artifacts/
│   ├── QUICKSTART.md              ← command reference (copied from user-level path, deployed by install.sh)
│   ├── memory/
│   │   ├── sessions/                  ← per-session state files
│   │   ├── daily/                     ← daily rollup from /end_of_day
│   │   ├── weekly/                    ← weekly rollup from /weekly_review
│   │   ├── repos-inventory.md         ← filled by /discover
│   │   ├── architecture-overview.md   ← filled by /discover
│   │   ├── dependencies-map.md        ← filled by /discover
│   │   ├── git-log.md                 ← filled by /discover, updated by /end_of_day
│   │   ├── lessons-learned.md         ← accumulates over time
│   │   ├── workflow-rules.md          ← workflow memory for Claude
│   │   └── workflow-suggestions.md   ← Tier 3 insight suggestions
```

Note: Skills live at `__QUOIN_HOME__/skills/` (installed by `install.sh`), and the QUICKSTART command
reference is deployed by `install.sh` to `__QUOIN_HOME__/QUICKSTART.md`. The interactive HTML guide lives
in your Quoin source clone at `<your-quoin-clone>/Workflow-User-Guide.html` — the only artifact
/init_workflow still references from the source clone.

Skills are already at `__QUOIN_HOME__/skills/` (installed by `install.sh`). Do not create a `skills/` directory in the project.

```bash
mkdir -p .workflow_artifacts/memory/sessions .workflow_artifacts/memory/daily .workflow_artifacts/memory/weekly
```

For files that should start empty but exist as placeholders:
- `.workflow_artifacts/memory/lessons-learned.md` — create with the template header:
  ```markdown
  # Lessons Learned

  Accumulated insights from completed tasks. Read by /plan and /critic at the start of every session.

  <!-- Add entries using the format:
  ## <date> — <task-name>
  **What happened:** <the surprise, failure, or insight>
  **Lesson:** <the reusable takeaway>
  **Applies to:** <which skills should pay attention>
  -->
  ```
- `.workflow_artifacts/memory/workflow-rules.md` — copy from `quoin/memory/workflow-rules.md` if it exists in the source, or create with header:
  ```markdown
  # Workflow Rules

  Reference summary of the quoin system for Claude.
  See __QUOIN_HOME__/CLAUDE.md for the full rules.
  ```
- `.workflow_artifacts/memory/workflow-suggestions.md` — create with the template header:
  ```markdown
  # Workflow Suggestions

  Suggestions for improvements to the quoin itself, surfaced during project work.
  These are Tier 3 insights — things that would benefit the workflow repo, not just this project.

  **Claude writes here automatically.** You decide whether to apply changes to the workflow repo manually.
  Review suggestions, then update the Status field: `accepted | rejected | deferred`.

  <!-- Entry format:
  ## <YYYY-MM-DD> — <source-task>
  **Suggestion:** <what should change in the workflow>
  **Why:** <the observation that triggered this>
  **Affects:** <which SKILL.md file or CLAUDE.md section>
  **Status:** surfaced
  -->
  ```
- `.workflow_artifacts/memory/repos-inventory.md` — create empty, will be populated by /discover
- `.workflow_artifacts/memory/architecture-overview.md` — create empty, will be populated by /discover
- `.workflow_artifacts/memory/dependencies-map.md` — create empty, will be populated by /discover
- `.workflow_artifacts/memory/git-log.md` — create empty, will be populated by /discover

### Step 5.5: Add `.workflow_artifacts` to project's `.gitignore`

```bash
if [ -f .gitignore ]; then
  grep -qxF '.workflow_artifacts/' .gitignore || echo '.workflow_artifacts/' >> .gitignore
else
  echo '.workflow_artifacts/' > .gitignore
fi
```

This ensures `.workflow_artifacts/` is gitignored in every project.

### Step 6: Run /discover

Automatically invoke `/discover` to scan all repositories in the project folder. This populates:
- `.workflow_artifacts/memory/repos-inventory.md`
- `.workflow_artifacts/memory/architecture-overview.md`
- `.workflow_artifacts/memory/dependencies-map.md`
- `.workflow_artifacts/memory/git-log.md`

Tell the user:
> "Running /discover to scan your codebase..."

If /discover finds no repos (no git repositories in the project folder), that's fine — the memory files stay empty and will be populated when repos are added.

### Step 6.5: Offer/activate Serena code-intelligence

**Read `.workflow_artifacts/.serena-skip` first.** If this sentinel file exists, the user previously chose to skip Serena setup for this project — print one line `[quoin: Serena setup skipped per prior choice]` and proceed to Step 7.

Otherwise, detect Serena using `ToolSearch select:mcp__serena__activate_project`:

**Branch (a) — Serena ABSENT (no schema AND no plugin file):**

If the ToolSearch probe returns no schema, run a filesystem pre-check:
- Plugin file: `__QUOIN_HOME__/plugins/marketplaces/claude-plugins-official/external_plugins/serena/.mcp.json`
- `uvx` on PATH: `command -v uvx`

If neither the schema nor the plugin file is found, offer installation:

```
AskUserQuestion(
  header="Serena",
  question="Serena gives Claude symbol-level code intelligence (find/rename symbols, references). It's not installed. Install it?",
  multiSelect=false,
  options=[
    {label: "Install Serena", description: "Walk me through installing Serena (requires uv/uvx)."},
    {label: "Skip for now",   description: "Skip Serena setup for this project."}
  ]
)
```

On **"Skip for now"**: write `.workflow_artifacts/.serena-skip` (creates the file, empty is fine) so Step 6.5 short-circuits on any re-run of `/init_workflow` for this project. Print `[quoin: Serena setup skipped per user choice]` and proceed to Step 7.

On **"Install Serena"**: guide the user through the following steps (Serena is a Claude Code plugin launched via `uvx` — quoin cannot install it unattended):

1. **Install `uv`/`uvx`** (if not already present — `command -v uvx` fails):
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # then restart your shell, OR:
   brew install uv
   ```

2. **Install the Serena plugin** in Claude Code. Preferred: run `/plugin` in your Claude Code session, browse to `claude-plugins-official`, and install `serena`. Manual fallback — add to `__QUOIN_HOME__/.mcp.json` (or the project `.mcp.json`):
   ```json
   {
     "mcpServers": {
       "serena": {
         "command": "uvx",
         "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
       }
     }
   }
   ```

3. **⚠️ SESSION RESTART REQUIRED.** MCP servers load only at session start. Serena tools will NOT be available until you restart Claude Code. After restarting, re-run `/init_workflow` — Step 6.5 will detect Serena as present (branch b) and complete onboarding automatically.

Also idempotently append `.serena/` to the target project's `.gitignore` (see below) on this path, so the user's Serena config isn't accidentally committed before onboarding runs.

**Branch (b) — Serena PRESENT, not yet onboarded:**

If the ToolSearch probe succeeds and `activate_project` returns a message containing "Onboarding has not been performed":

```python
# Load all needed Serena tools
ToolSearch select:mcp__serena__activate_project,mcp__serena__onboarding,mcp__serena__initial_instructions

# Bind the project (pass bare dirname or the name from .serena/project.yml if present)
mcp__serena__activate_project(project="<project-dirname>")

# Run onboarding to generate project memories
mcp__serena__onboarding()   # follow its steps

# Confirm activation
mcp__serena__initial_instructions()
```

Tell the user onboarding is complete and Serena is now active for the project. This is the most common real-world case: Serena installed but never set up for the project.

**Branch (c) — Serena PRESENT, already onboarded:**

If the ToolSearch probe succeeds and `activate_project` does NOT report onboarding-needed, confirm activation silently:

```python
ToolSearch select:mcp__serena__activate_project
mcp__serena__activate_project(project="<project-dirname>")
```

Print one line: `[quoin: Serena active for <project-dirname> (already onboarded)]` and proceed to Step 7.

**Target-project `.gitignore` (all setup paths — a/install, b, c):**

On any Serena-setup path, idempotently append `.serena/` to the target project's `.gitignore`:
```bash
if [ -f .gitignore ]; then
  grep -qxF '.serena/' .gitignore || echo '.serena/' >> .gitignore
else
  echo '.serena/' >> .gitignore
fi
```
Serena config and memories are machine-local; they should not be committed to the project repo by default.

### Step 7: Copy quickstart guide + legacy detection

**Legacy QUICKSTART detection (run before copying):**

Check if `(project)/dev-workflow/QUICKSTART.md` exists:

```
Legacy QUICKSTART location detected: (project)/dev-workflow/QUICKSTART.md
The new location is .workflow_artifacts/QUICKSTART.md.
Options:
  [m] Move dev-workflow/QUICKSTART.md → .workflow_artifacts/QUICKSTART.md
  [d] Delete the legacy file (a fresh QUICKSTART will be copied below)
  [k] Keep it (you may have cloned the workflow source there — check first)
```

Safety check: if `(project)/dev-workflow/install.sh` OR `(project)/dev-workflow/SETUP.md` is also present, the directory is likely the cloned source repo — print a warning and default to `[k]`. Do NOT auto-delete.

**Copy QUICKSTART from the deployed location:**

`install.sh` deploys `quoin/QUICKSTART.md` to `__QUOIN_HOME__/QUICKSTART.md` at install time. Step 7 reads
from that stable path — no user prompt needed.

- **Source path:** `__QUOIN_HOME__/QUICKSTART.md` (deployed by `install.sh`)
- **Destination:** `.workflow_artifacts/QUICKSTART.md`

```bash
if [ -f "$HOME/.claude/QUICKSTART.md" ]; then
  cp "$HOME/.claude/QUICKSTART.md" .workflow_artifacts/QUICKSTART.md
else
  cat > .workflow_artifacts/QUICKSTART.md <<'EOF'
# Quoin — Quickstart (fallback)

The full QUICKSTART could not be found at __QUOIN_HOME__/QUICKSTART.md.
This means install.sh has not been run, or was run from an older version.

To get the full command reference, re-run install.sh from your Quoin source clone:
  bash <your-quoin-clone>/install.sh

In the meantime:
  - Type /help inside Claude Code to see available slash commands.
  - Browse the user skills directory at __QUOIN_HOME__/skills/ for per-skill SKILL.md files.
  - Open the interactive HTML guide at <your-quoin-clone>/Workflow-User-Guide.html in your browser.
EOF
fi
```

The interactive guide lives in the source clone:
```
<your-quoin-clone>/Workflow-User-Guide.html — open in your browser for full walkthrough scenarios.
```

### Step 8: Report

Tell the user:

```
Workflow initialized in <project-root>/.workflow_artifacts/

📁 Structure created:
  - .workflow_artifacts/memory/ (repos, architecture, dependencies, lessons, sessions)
  - .workflow_artifacts/QUICKSTART.md (command reference)
  - <your-quoin-clone>/Workflow-User-Guide.html (interactive guide — in your cloned source)

🔍 /discover completed:
  - Found <N> repositories
  - <brief summary of what was found>

Ready to go. Start with:
  - /start_of_day — if resuming existing work
  - /architect — if starting a new feature
  - /plan or /thorough_plan — if you know what to build
  - Open <your-quoin-clone>/Workflow-User-Guide.html for full scenarios
```

## Important behaviors

- **Never overwrite `.workflow_artifacts/memory/`.** If re-initializing, preserve all memory files. They contain accumulated knowledge.
- **Run /discover automatically.** Don't ask — just run it as part of init. The user expects a ready-to-use setup.
- **Keep it fast.** This should feel like a quick bootstrap, not a long ceremony.
- **The quickstart goes in the project folder.** Not buried in skills/ — the user should see it immediately.
