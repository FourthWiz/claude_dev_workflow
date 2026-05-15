# Manual Verification Guide — §0 Subagent Dispatch

This document describes how to manually verify that §0 model-dispatch behavior is
working correctly in a running Claude Code session. It covers:

1. Baseline dispatch (cheap-tier skill invoked from an Opus session)
2. Worktree-class error fallback (dispatch from a non-git project root)
3. Test-file reference

---

## Section 1 — Baseline dispatch verification

**Goal:** Confirm that a cheap-tier skill self-dispatches to its declared model when
invoked from a session running on a more expensive model (e.g., Opus-3 session
invoking `/implement`, which is declared at Sonnet tier).

### Prerequisites

- Claude Code running with an Opus-tier model (e.g., claude-opus-4).
- A project with quoin installed (`bash quoin/install.sh` has been run).
- The project root is a git repository (no worktree error expected).

### Steps

1. Open a Claude Code session; confirm the model is Opus-tier (check the session
   header or `claude --version`).
2. Invoke a cheap-tier skill, e.g. `/implement` with a trivial prompt:
   ```
   /implement Say hello in Python
   ```
3. Observe the session output. The §0 dispatch preamble runs as the FIRST step of the
   skill body, before any session bootstrap reads.

### Expected output (dispatch fires)

- The skill emits a subagent dispatch note. The child subagent runs at the declared
  model (Sonnet for `/implement`).
- The child prompt begins with `[no-redispatch]` as the FIRST LINE. You can confirm
  this by inspecting the child conversation transcript (if the harness exposes it) or
  by checking for the `dispatched-tier:` marker in the parent output.
- No bare `[quoin-stage-1: subagent dispatch unavailable; ...]` warning appears
  (that warning only fires when dispatch FAILS).

### Expected output (no-redispatch path)

- If `[no-redispatch]` already appears at the FIRST LINE of the prompt (i.e., the
  child already carries the sentinel), the §0 block detects this and proceeds directly
  to §1 without re-dispatching. No dispatch note is emitted.

### Expected output (abort path — N≥2)

- If the incoming prompt begins with `[no-redispatch:N]` where N≥2, the skill aborts
  instead of proceeding. This catches runaway recursion from a buggy parent. The
  abort message includes: `Quoin self-dispatch hard-cap reached at N=<N>`.

---

## Section 2 — Worktree-class error fallback verification

**Goal:** Confirm that when the Agent tool fails with a worktree-creation error, the
§0 block classifies the error, presents recovery options via AskUserQuestion, and then
falls through to the fail-OPEN path with both warning lines emitted.

This scenario arises when invoking a cheap-tier skill from a project root that is NOT
a git repository (e.g., a bare folder without `.git/`). The harness tries to create a
git worktree for isolation and fails.

### Setup — reproduce the Personal_Site scenario

```bash
# Create a temporary non-git directory
mkdir /tmp/not-a-repo
cd /tmp/not-a-repo
# Do NOT run git init — this must be a plain directory
```

Open a Claude Code session from `/tmp/not-a-repo`. Confirm quoin skills are installed
globally (`~/.claude/skills/` is on the skill path).

### Steps

1. From the `/tmp/not-a-repo` session, invoke `/implement` (or any other cheap-tier
   skill) at normal Opus tier:
   ```
   /implement Say hello in Python
   ```
2. §0 fires first and attempts to spawn a subagent at Sonnet tier.
3. The harness tries to create a git worktree and fails because `/tmp/not-a-repo` is
   not a git repository.

### Expected behavior — Variant A-1 (worktree creation is hook-driven, c-only)

This is the behavior confirmed by the T-01 spike (`worktree_a_skippable=false`,
`worktree_b_available=false`). Worktree creation is unconditional in the harness;
no isolation parameter can be omitted or overridden.

1. **AskUserQuestion fires** with the header:
   ```
   Subagent dispatch failed (worktree creation). Proceeding at current tier.
   ```
   The prompt presents exactly ONE option:
   ```
   (c) proceed-current-tier — Skip dispatch, proceed at the current
       (more expensive) tier. This is the only available recovery path.
   ```
   And a note:
   ```
   Worktree dispatch failed and no retry mechanism is available — worktree creation
   is unconditional in this harness. Proceeding at current tier.
   ```

2. **User selects (c)** (or acknowledges). The skill then falls through to the
   Other-class path.

3. **Two warning lines are emitted** (in this order):
   ```
   [quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]
   [quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]
   ```

4. **Skill continues at the current (Opus) tier** — the user's invocation is not
   aborted. This is the fail-OPEN behavior per architecture I-01.

### Expected behavior — Variant A-2 (retry-no-isolation available, c also available)

If a future harness update exposes an isolation parameter (`worktree_a_skippable=true`,
`worktree_b_available=false`), the AskUserQuestion prompt changes to:

```
Subagent dispatch failed (worktree creation). How to proceed?
```

Options:
```
(a) retry-no-isolation — Retry dispatch with worktree isolation omitted or
    disabled. DEFAULT.
(c) proceed-current-tier — Skip dispatch, proceed at the current tier.
```

If the user selects (a), the retry Agent call's prompt begins with:
```
[worktree-retry]
[no-redispatch]
<original user input verbatim>
```

`[worktree-retry]` MUST be the FIRST LINE (position-anchored — not a substring
anywhere in the prompt). If the retry also fails, the skill falls through to
Other-class with `user-choice=retry-failed` in the second warning line.

### Expected behavior — Variant B (retry-no-isolation and retry-with-base available)

If the harness also exposes a per-call base-path parameter (`worktree_b_available=true`),
a third option is presented:

```
(b) retry-with-base <path> — Retry dispatch rooted at a user-supplied git-repo path.
```

The verifier should confirm that selecting (b) causes the retry prompt to carry
`[worktree-retry]` as the FIRST LINE, and that the `retry-with-base` path argument
is set to the user-supplied value.

### Verification checklist (Variant A-1)

- [ ] AskUserQuestion fires with the exact header shown above.
- [ ] Only option (c) `proceed-current-tier` is presented.
- [ ] After acknowledging (c), both warning lines appear in the output (bare warning
      first, classification line second).
- [ ] The bare warning text is verbatim:
      `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
- [ ] The classification line is verbatim:
      `[quoin-stage-1: error-class=worktree; user-choice=c; proceeding at current tier]`
- [ ] The skill continues and completes the user's request (fail-OPEN — does not abort).

### Notes

- This scenario only fires when §0 attempts dispatch AND the harness fails to create a
  worktree. If the project root IS a git repository, the harness creates the worktree
  successfully and §0 dispatch completes normally.
- The `[worktree-retry]` sentinel is currently RESERVED for Variant A-2 / B only.
  Do NOT expect it to appear in Variant A-1 flows.
- The classification line `error-class=worktree` distinguishes worktree failures from
  other Agent tool errors (network errors, model quota, etc.), which fall through to
  the Other-class path with only the bare warning line (no second classification line).

---

## Section 3 — Test file reference

Automated CI coverage for §0 dispatch contract:

| Test file | What it covers |
|-----------|----------------|
| `quoin/dev/tests/test_quoin_stage1_preamble.py` | §0 structural tokens present in all 15 cheap-tier skills; `[no-redispatch]` family; abort message |
| `quoin/dev/tests/test_quoin_stage1_recursion_abort.py` | Recursion abort tokens; fail-OPEN warning string; `[no-redispatch:N]` counter form |
| `quoin/dev/tests/test_quoin_stage1_worktree_fallback.py` | Worktree-fallback contract: error-class triage section, option labels, extended warning string, byte-equality across all 15 skills, `[worktree-retry]` sentinel first-line grammar |

To run all three suites:
```bash
python3 -m pytest quoin/dev/tests/test_quoin_stage1_preamble.py \
                  quoin/dev/tests/test_quoin_stage1_recursion_abort.py \
                  quoin/dev/tests/test_quoin_stage1_worktree_fallback.py -v
```

To run the full suite (540+ tests):
```bash
python3 -m pytest
```
