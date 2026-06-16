---
name: pr
description: "Create a pull request: optional version bump, push branch if not already pushed, create PR via gh, wait for merge, switch to merge target. Use this skill for: /pr, 'create a PR', 'open a pull request', 'submit for review'. Triggers when the user wants to create a PR from a feature branch."
model: sonnet
---

# PR

*Portable intent doc: `quoin/core/skills/pr.md`*

## §0 Model dispatch (FIRST STEP — execute before anything else)

This skill is declared `model: sonnet`. If the executing agent is running on a model
strictly more expensive than the declared tier, you MUST self-dispatch before doing the
skill's actual work.

Detection:
  - Read your current model from the system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus.
  - Sentinel parsing: the user's prompt is checked for the `[no-redispatch]` family.
      * Bare `[no-redispatch]` (parent-emit form AND user manual override): skip dispatch, proceed to §1 at the current tier.
      * Counter form `[no-redispatch:N]` where N is a positive integer ≥ 2: ABORT (see "Abort rule" below).
      * Counter form `[no-redispatch:1]` is reserved and treated as bare `[no-redispatch]` for forward-compatibility; do not emit it.
<!-- §0-1m-context-precheck-begin -->
  - 1M-context precheck (parent-credit-mismatch guardrail):
    BEFORE evaluating the tier comparison, inspect the parent model name read from system context.
    If the model name string contains any of the substrings `1m`, `1M`, `(1M context)`, or
    `context-1m` (case-insensitive match on the literal substring), the parent session is using
    the 1M context beta. The Claude Code CLI propagates the `context-1m-2025-08-07` beta header
    to ALL subagent API calls; if the user has parent-tier 1M credits but lacks declared-tier
    1M credits, the Agent tool dispatch will fail with:
      `API Error: Usage credits required for 1M context · run /usage-credits to turn them
      on, or /model to switch to standard context`
    quoin cannot drop the beta header from the Agent call — the Agent tool exposes only
    `model: "sonnet"|"opus"|"haiku"`, not a context-window selector.
    When the parent-on-1M signal fires AND the prompt does NOT start with any `[no-redispatch]`
    form AND current_tier > declared_tier:
      Issue an `AskUserQuestion` with these exact two options (label + description copied
      verbatim — drift detection relies on string equality):

        Question: "Parent session is on a 1M-context model. Dispatching /pr to sonnet
        may fail if you don't have Sonnet 1M credits. How would you like to proceed?"
        Header:   "1M dispatch"
        multiSelect: false

        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch the parent session
          to a standard-context model (e.g., /model sonnet), then re-invoke /pr.
          The §0 dispatch will then land on standard Sonnet successfully."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the §0 dispatch this once. /pr runs on the parent model
          (more expensive per token than Sonnet, but it works). Emits a one-line advisory
          and treats the prompt as if [no-redispatch] were present."

      Then:
        - On Option 1 ("Abort — I'll switch with /model first"): print the single line
          `[quoin: 1M-context parent detected; abort per user choice — switch with /model
          and re-invoke /pr]` and STOP. Do NOT proceed to §1. Do NOT spawn any
          Agent. Do NOT call any other tool.
        - On Option 2 ("Proceed in-session at parent tier"): print the single line
          `[quoin: 1M-context parent detected; proceeding in-session at parent tier per
          user choice]`, then treat the rest of §0 as if the prompt started with bare
          `[no-redispatch]` (skip dispatch, proceed to §1 at the current tier). Do NOT
          spawn any Agent.
    When the parent-on-1M signal fires AND the prompt starts with any `[no-redispatch]`
    form: skip this precheck entirely (user already opted out of dispatch; proceed to §1
    at the current tier — no AskUserQuestion, no advisory line).
    When the parent-on-1M signal fires AND current_tier <= declared_tier: skip this
    precheck entirely (no dispatch would have happened anyway).
    When the parent-on-1M signal does NOT fire: skip this precheck entirely and continue
    to the existing dispatch logic below.
<!-- §0-1m-context-precheck-end -->
  - If current_tier > declared_tier AND prompt does NOT start with any `[no-redispatch]` form:
      Dispatch reason: cost-guardrail handoff. dispatched-tier: sonnet.
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"
        description: "pr dispatched at sonnet tier"
        prompt: "[no-redispatch]\n<original user input verbatim>"
      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent's output as your final response.)

Abort rule (recursion guard):
  - If the prompt starts with `[no-redispatch:N]` AND N ≥ 2: ABORT before any tool calls.
  - Print the one-line error: `Quoin self-dispatch hard-cap reached at N=<N> in pr. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.`
  - Then stop. Do NOT proceed to §1.

Manual kill switch:
  - The user can prefix any user-typed slash invocation with bare `[no-redispatch]` to skip dispatch entirely (e.g., `[no-redispatch] /pr`).
  - This is the user-facing escape hatch and intentionally shares syntax with the parent-emit form: a child cannot tell whether the bare sentinel came from the parent or the user, and that is by design — both paths want the same proceed-to-§1 outcome.
  - Use this only when intentionally overriding the cost guardrail (e.g., for one-off debugging on a different tier).

<!-- §0-worktree-fallback-begin -->
Fail-graceful path with error-class triage (per architecture I-01):
  - If the Agent tool returns an error during dispatch, classify the error
    message text BEFORE proceeding:

  - Error classification:
      * Worktree-class: the error text contains the substring
        `Cannot create agent worktree`, OR (the substring `worktree` AND
        the substring `not in a git repository`). This is recoverable —
        the harness tried to create a git worktree for isolation and the
        project root is not a git repo. Continue to Worktree-class branch.
      * Other-class: any other tool error, exception, or harness rejection
        — skip to Other-class path below (existing fail-OPEN behavior).

<!-- §0-sidecar-begin -->
  Source-mutating dispatch — two-phase worktree isolation (D-08):

  STEP A — Write the dispatch sidecar BEFORE calling the Agent tool:
     Run via Bash:
       PROJECT_ROOT="$(python3 __QUOIN_HOME__/scripts/path_resolve.py --project-root)"
       python3 __QUOIN_HOME__/scripts/dispatch_sidecar.py \
           --skill <skill-name> \
           --project-root "$PROJECT_ROOT" \
           --plan "<resolved-plan-path-or-empty>"
     (The WorktreeCreate hook reads this sidecar to resolve the nested git root.)

  STEP B — Phase 1: Agent dispatch WITH isolation: "worktree" (normal path):
     Call the Agent tool with isolation: "worktree" at the declared cheap-tier
     model (sonnet for this skill). The deployed WorktreeCreate hook at
     __QUOIN_HOME__/hooks/worktreecreate.sh reads the sidecar, runs
     git_root_for_dispatch.py, and (when a single nested repo resolves)
     creates a worktree IN the nested git root and returns its path.

  STEP C — Phase 2 retry WITHOUT isolation (on Worktree-class error):
     If Phase 1 fails with a Worktree-class error (regex above), the hook
     either returned skip (no stdout → harness fails) or encountered an error.
     Re-dispatch the Agent call WITHOUT isolation: "worktree", at the SAME
     declared cheap-tier model (sonnet). Do NOT escalate to parent tier.
     Emit one-line audit:
       [quoin-stage-1: worktree dispatch skipped; proceeding at sonnet without isolation]

  STEP D — Done:
     No child-side coordination required. The harness handles cwd correctly:
     on Phase 1 success, child sees the worktree as cwd; on Phase 2, child
     inherits the parent's session cwd (today's behavior, unchanged).
<!-- §0-sidecar-end -->

  - Worktree-class branch: handled by Phase 2 (§0-sidecar block above).
    Phase 2 retries at the declared cheap-tier model without isolation.
    Do NOT use AskUserQuestion or proceed-current-tier for source-mutating skills.

  - Other-class path (non-worktree Agent errors):
      Do NOT abort the user's invocation.
      Emit the bare warning (verbatim):
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
      If this path was reached via a worktree-class error, ALSO emit the
      classification line (second, separate):
        `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`
      Then proceed to §1 at the current tier (fail-OPEN per I-01).
<!-- §0-worktree-fallback-end -->
Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).

<!-- §0b: intentionally omitted — /pr has no sub-phase dispatch -->

## When to use

After `/end_of_task` finalizes and pushes the feature branch (or after any local
commit when you want to create a PR). The user explicitly invokes `/pr`.

This skill is **never auto-invoked** by any orchestrator or skill.

## Session bootstrap

On start:
1. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` — phase: `pr`
2. Write session state to `.workflow_artifacts/memory/sessions/<date>-<task-name>.md`

## Process

### Step 1: Pre-flight checks

1. **Branch check** — run `git branch --show-current` and verify the result is NOT
   `main` or `master`. If it is, STOP with:
   "Cannot create a PR from main/master. Switch to a feature branch first."

2. **gh CLI check** — run `command -v gh`. If not found, STOP with:
   "GitHub CLI (gh) is not installed. Install it from: https://cli.github.com/"

3. **gh auth check** — run `gh auth status`. If it fails, STOP with:
   "Not authenticated with GitHub CLI. Run: gh auth login"

4. **Uncommitted changes check** — run `git status --porcelain`. If output is
   non-empty, STOP with:
   "There are uncommitted changes. Please commit or stash them before running /pr."

5. **Push state check** — run:
   `git ls-remote --exit-code origin "$(git branch --show-current)" 2>/dev/null`
   - Exit 0: branch is already pushed on remote. Set `already_pushed=true`.
   - Exit 2: branch is not on remote. Set `already_pushed=false`.

### Step 2: Version bump (conditional)

1. Scan for version files in the repo root and immediate subdirectories:
   - `pyproject.toml` — look for `version = "X.Y.Z"` under `[project]` or `[tool.poetry]`
   - `package.json` — look for `"version": "X.Y.Z"`
   - `setup.cfg` — look for `version = X.Y.Z`
   - `Cargo.toml` — look for `version = "X.Y.Z"` under `[package]`
   - `__about__.py` or `_version.py` — look for `__version__ = "X.Y.Z"`

2. If no version file is found, skip to Step 3.

3. If a version file is found, ask the user:
   ```
   Version file detected: <file> (current version: X.Y.Z)
   Bump type?
   - patch → X.Y.(Z+1)
   - minor → X.(Y+1).0
   - major → (X+1).0.0
   - skip  → do not bump
   ```
   Use AskUserQuestion with these 4 options.

4. If the user chooses patch/minor/major:
   - Edit the version string in the file using the correct regex for that file type.
   - Commit: `git commit -m "chore: bump version to X.Y.Z"`
   - Set `version_bump_committed=true`.

5. If the user chooses skip: set `version_bump_committed=false`.

### Step 3: Push to remote (conditional)

1. If `already_pushed=true` AND `version_bump_committed=false`: **skip** this step.
2. Otherwise: run `git push -u origin "$(git branch --show-current)"`.
   - If push fails, report the error and STOP.

### Step 4: Create PR

1. **Determine base branch:**
   - Default: `main`. Verify it exists on remote:
     `git ls-remote --heads origin main`
   - If `main` doesn't exist, fall back to `master`.
   - If the user explicitly passed `--base <branch>` in their invocation, use that.

2. **Gather PR content:**
   - Commits: `git log --oneline <base>..HEAD`
   - Changed files: `git diff <base>...HEAD --stat`

3. **Derive PR title:**
   - Take the current branch name (e.g., `feat/IVG-53-pr-skill` or `fix/null-check-auth`).
   - Strip common prefixes: `feat/`, `fix/`, `chore/`, `refactor/`, `test/`, `docs/`.
   - Convert kebab-case to title case (split on `-`, capitalize each word).
   - If the branch has a ticket prefix (e.g., `IVG-53`), keep it: `IVG-53: Pr Skill`.
   - If the derived title looks wrong or ambiguous, ask the user to confirm or override.

4. **Create PR:**
   ```bash
   gh pr create \
     --base <base-branch> \
     --title "<derived title>" \
     --body "$(cat <<'EOF'
   ## Summary
   <2-3 sentence summary of what this PR does>

   ## Changes
   <bullet list of key changes, derived from git log>

   ## Tests
   <brief note — "all tests pass" or list relevant test files>

   ## Related
   - Branch: <branch-name>

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```
   Fill the Summary and Changes sections from the git log output. Do not invent facts.

5. Print the PR URL to the user.

### Step 5: Wait for merge

Tell the user:
```
PR created: <URL>

Please review and merge when ready. Tell me 'merged' (or similar) when it's done.
```

Wait for the user's confirmation before proceeding to Step 6.

### Step 6: Post-merge cleanup

1. Determine the merge target branch (the base from Step 4).
2. Run: `git checkout <merge-target>`
3. Run: `git pull`
4. Confirm to the user:
   "Switched to <merge-target> and pulled latest. Ready for the next task."

## Cost tracking

Append to the task's cost ledger at `.workflow_artifacts/<task-name>/cost-ledger.md`
with phase `pr` (see cost tracking rules in CLAUDE.md).

## Session state

Write to `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` after the PR
is created and after post-merge cleanup.
