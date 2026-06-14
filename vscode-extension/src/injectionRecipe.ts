/**
 * Injection recipe constants — single source of truth for the R-01 sendText spike verdict.
 *
 * These values are determined by the manual spike documented in:
 *   docs/spike-r01-sendtext.md
 *
 * EDIT THIS FILE after running the spike:
 *   1. Set INJECTION_MODE to 'sendText' (direct injection) or 'clipboard' (fallback).
 *   2. Set CLEAR_PREFIX to the chosen pre-clear sequence (MUST be in SANCTIONED_CLEAR_PREFIXES).
 *   3. If a new pre-clear sequence is discovered, add it to SANCTIONED_CLEAR_PREFIXES AND
 *      document it in docs/spike-r01-sendtext.md (same commit).
 *
 * Both CommandRunner (production) and tests (T-07) import these constants — no second copy.
 *
 * STATUS: PENDING — defaults set to 'sendText' / '' (no pre-clear) until the spike is run.
 * Update after completing the manual test in Extension Development Host.
 */

/** Enumerated allowed pre-clear sequences (widen only with a matching findings-doc entry). */
export const SANCTIONED_CLEAR_PREFIXES = [
  '',      // no pre-clear (works when input is already empty)
  '\x15',  // Ctrl-U (kill-line) — clears the readline buffer before injection
] as const;

/**
 * How to inject the command into the terminal.
 * 'sendText' — direct injection via terminal.sendText() (preferred if reliable).
 * 'clipboard' — copy to clipboard + reveal terminal (R-01 fallback if sendText is fragile).
 */
export const INJECTION_MODE: 'sendText' | 'clipboard' = 'sendText';

/**
 * Pre-clear sequence prepended to every injected command.
 * Must be one of SANCTIONED_CLEAR_PREFIXES.
 * Set to '' if no pre-clear is needed (empty input case is reliable).
 * Set to '\x15' (Ctrl-U) if the spike shows unsent-text concatenation is a problem.
 */
export const CLEAR_PREFIX: string = '';
