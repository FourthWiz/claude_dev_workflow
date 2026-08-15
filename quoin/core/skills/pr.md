# pr

Runtime-neutral intent for the pr skill. Any runtime adapter that
implements this skill should match the contract described here.

## Purpose

Create a pull request after a feature branch has been committed and (optionally)
pushed: check the branch is not main/master, optionally bump the package version,
push the branch if not already pushed, create a structured PR via the host
platform's CLI (e.g., `gh pr create`), wait for the user to merge, then switch
to the merge target branch and pull latest.

## When to use

- After `/end_of_task` has committed and pushed the feature branch, when the
  user wants to create a pull request.
- Also works on an unpushed branch — the skill checks push state and pushes if
  needed before creating the PR.
- Always explicitly invoked by the user. Never auto-invoked by any skill or
  orchestrator.

## Inputs

- The current git branch (must not be main or master).
- The target base branch (default: main).
- Optional: a user-specified PR title override.
- Optional: a user-specified base branch override (for stacked PRs).

## Outputs

- A version bump commit (if a versioned package is detected and the user
  chooses to bump).
- A pushed branch on the remote.
- A PR created on the hosting platform with a structured message (summary,
  changes, tests, related links).
- User-confirmed merge acknowledgement.
- A branch switch to the merge target branch with latest pulled.

## Preconditions

- Work committed on a feature branch (not main/master).
- The host CLI is installed and authenticated (e.g., `gh auth status` passes).
- No uncommitted changes in the working tree.
- The branch may already be pushed (e.g., by `/end_of_task`) or not yet pushed.

## Contract

- Shipped authored content (the PR description) MUST follow the clean-authored-content rule: plain engineering language, no plan/decision/finding IDs, severities, review-round narration, gate verdicts, or planning-artifact paths.

1. **Pre-flight:** Refuse on main/master. Verify CLI present and authenticated.
   Check for uncommitted changes. Determine if branch is already pushed.
2. **Version bump (conditional):** Scan for version files (pyproject.toml,
   package.json, Cargo.toml, setup.cfg, __about__.py, _version.py). If found,
   offer patch/minor/major/skip bump options. Commit and push the bump if chosen.
3. **Push (conditional):** Push branch if not already pushed, or if a version
   bump added a new commit.
4. **PR creation:** Derive title from branch name (kebab → title case, preserve
   ticket prefix). Build structured body: summary, changes (from git log),
   tests summary. Create PR targeting the base branch.
5. **Wait for merge:** Tell the user the PR URL and wait for confirmation.
6. **Post-merge cleanup:** Switch to merge target branch and pull latest.

## Key design decision

`/end_of_task` retains responsibility for pushing the branch (the `/run`
orchestrator depends on this). `/pr` is additive — it handles the PR lifecycle
on top of whatever push state exists. The two skills complement each other:
`/end_of_task` (commit + push + archive), then `/pr` (PR + merge + cleanup).
