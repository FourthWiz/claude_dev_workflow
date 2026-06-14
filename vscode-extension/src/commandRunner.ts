import * as vscode from 'vscode';
import { QuoinSession, Runtime } from './types';
import { INJECTION_MODE, CLEAR_PREFIX } from './injectionRecipe';

/**
 * Pure function — builds the text to inject into the terminal.
 * No vscode dependency; fully unit-testable.
 *
 * @param runtime  - The session runtime ('claude' | 'codex')
 * @param skill    - Selected skill name, or null for raw-prompt run
 * @param prompt   - The user's prompt text (may be empty)
 * @returns The string to send to the terminal
 */
export function buildInjection(runtime: Runtime, skill: string | null, prompt: string): string {
  const p = prompt.trim();

  // Codex: NEVER inject a /skill prefix (R-09 guard)
  if (runtime === 'codex') {
    return CLEAR_PREFIX + p;
  }

  // Claude, no skill selected (raw-prompt Run)
  if (!skill) {
    return CLEAR_PREFIX + p;
  }

  // Claude with skill, no prompt
  if (p === '') {
    return CLEAR_PREFIX + '/' + skill;
  }

  // Claude with skill and prompt
  return CLEAR_PREFIX + '/' + skill + ' ' + p;
}

/**
 * CommandRunner — dispatches a command to a session terminal.
 * Imports INJECTION_MODE and CLEAR_PREFIX from injectionRecipe.ts
 * (the R-01 spike verdict) rather than redeclaring them.
 */
export class CommandRunner {
  /**
   * Run a skill/prompt combo in the given session.
   *
   * @param session - The target QuoinSession
   * @param skill   - The skill name to run, or null for raw prompt
   * @param prompt  - The user's prompt text
   */
  run(session: QuoinSession, skill: string | null, prompt: string): void {
    // Guard: relaunchable session has no live terminal handle
    if (session.terminal === undefined) {
      void vscode.window.showInformationMessage(
        'Quoin: Session has no live terminal — relaunch it first'
      );
      return;
    }

    const text = buildInjection(session.runtime, skill, prompt);

    if (INJECTION_MODE === 'clipboard') {
      // R-01 fallback: copy to clipboard + reveal terminal
      void vscode.env.clipboard.writeText(text);
      session.terminal.show();
      void vscode.window.showInformationMessage(
        'Quoin: Command copied to clipboard — paste into the terminal'
      );
      return;
    }

    // Default: direct sendText injection
    session.terminal.show();
    session.terminal.sendText(text, true);
  }
}
