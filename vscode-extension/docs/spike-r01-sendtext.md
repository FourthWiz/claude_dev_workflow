# Spike R-01: `terminal.sendText` Reliability for Slash-Command Injection

**Status:** PENDING — requires manual test in Extension Development Host (F5)

## Purpose

Prove (or disprove) that `vscode.window.Terminal.sendText("/skill prompt", true)` reliably
injects a slash command into a running `claude` interactive TUI session.

The worst case is injection while the user has unsent text already sitting in the TUI input
box — `sendText` may concatenate with the half-typed buffer and submit garbage.

## Test cases

Run each case in the Extension Development Host (F5). Open a Claude session via `quoin.newSession`.
Let the `claude` TUI fully start before each test.

### Case A — Inject into idle, empty input
- **Setup:** TUI is idle with an empty input box.
- **Action:** Call `terminal.sendText("/status", true)` from the extension.
- **Expected:** `/status` runs.
- **Observed:** _(fill in after running)_

### Case B — Inject while unsent text sits in input
- **Setup:** Type some partial text in the TUI WITHOUT submitting.
- **Action A (no pre-clear):** Call `terminal.sendText("/status", true)`.
  - **Observed:** _(does the buffer concatenate? does it submit garbage?)_
- **Action B (Ctrl-U pre-clear):** Send `\x15` (Ctrl-U, kill-line) then `terminal.sendText("/status", true)`.
  - **Observed:** _(does Ctrl-U clear the buffer first?)_
- **Action C (empty+text pattern):** Call `terminal.sendText("" + "/status", true)` with an empty first sendText call.
  - **Observed:** _(does this pattern help?)_

### Case C — Inject while `claude` is mid-response (busy)
- **Setup:** Trigger a long-running response in the TUI.
- **Action:** Call `terminal.sendText("/status", true)` while the response streams.
- **Observed:** _(does it queue, drop, or corrupt?)_

### Case D — `addNewLine=true` vs `false` + pre-clear combos
- **Action A:** `sendText("/status", false)` into idle input.
  - **Observed:** _(is the newline submitted or not?)_
- **Action B:** `sendText("/status", true)` into idle input (should be same as Case A).
  - **Observed:** _(confirm)_
- **Action C:** `sendText("\x15/status", true)` (Ctrl-U + command in one call).
  - **Observed:** _(does the Ctrl-U clear before the command runs?)_

## Decision

Based on the above cases, choose one:

### Option 1: Direct `sendText` is reliable
- **Chosen pre-clear prefix:** _(one of `''` or `'\x15'` — must be in `SANCTIONED_CLEAR_PREFIXES`)_
- **Recipe:** `terminal.sendText(CLEAR_PREFIX + "/skill prompt", true)`
- **Set in `src/injectionRecipe.ts`:** `INJECTION_MODE = 'sendText'`, `CLEAR_PREFIX = <chosen prefix>`

### Option 2: `sendText` unreliable (unsent-text case cannot be fixed)
- **Fallback:** Run = "copy command to clipboard + reveal terminal"
- **Set in `src/injectionRecipe.ts`:** `INJECTION_MODE = 'clipboard'`, `CLEAR_PREFIX = ''`

## Outcome

_(Fill in after running: which option was chosen, what exact values for `INJECTION_MODE` and
`CLEAR_PREFIX`, and any notes on the reliability of the chosen recipe.)_

After completing the spike, update `src/injectionRecipe.ts` with the verified constants
and commit both files together.
