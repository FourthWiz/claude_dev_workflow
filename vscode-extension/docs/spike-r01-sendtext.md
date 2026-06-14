# Spike R-01: `terminal.sendText` Reliability for Slash-Command Injection

**Status:** COMPLETE — 2026-06-14

## Purpose

Prove (or disprove) that `vscode.window.Terminal.sendText("/skill prompt", true)` reliably
injects a slash command into a running `claude` interactive TUI session.

The worst case is injection while the user has unsent text already sitting in the TUI input
box — `sendText` may concatenate with the half-typed buffer and submit garbage.

## Test cases

### Case A — Inject into idle, empty input
- **Setup:** TUI is idle with an empty input box.
- **Action:** `terminal.sendText("/status", true)`
- **Observed:** Works. `/status` runs cleanly.

### Case B — Inject while unsent text sits in input
- **Setup:** Typed partial text in the TUI WITHOUT submitting.
- **Action (no pre-clear):** `terminal.sendText("/status", true)`
- **Observed:** Injected AFTER the existing text — concatenates and submits garbage.
- **Conclusion:** A pre-clear sequence is required before injection.
- **Chosen pre-clear:** `\x15` (Ctrl-U / kill-line) — clears the readline buffer before injection.

### Case C — Inject while `claude` is mid-response (busy)
- **Observed:** Queues cleanly. Command runs after the current response finishes.

### Case D — `addNewLine` variants
- **Skipped.** Cases A-C provided sufficient signal.

## Decision: Option 1 — direct `sendText` is reliable with pre-clear

- **Recipe:** send `\x15` (Ctrl-U) + command in a single `sendText(..., true)` call
- **Chosen prefix:** `'\x15'`
- **`INJECTION_MODE`:** `'sendText'`
- **`CLEAR_PREFIX`:** `'\x15'`

The Ctrl-U kill-line sequence is standard readline behavior and works in the `claude` TUI.
It clears any unsent text in the input buffer before the slash command is injected.

## Verified constants (committed in `src/injectionRecipe.ts`)

```ts
export const INJECTION_MODE = 'sendText';
export const CLEAR_PREFIX = '\x15';
```
