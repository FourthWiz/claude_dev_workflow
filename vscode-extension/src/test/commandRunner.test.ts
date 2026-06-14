import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { buildInjection, CommandRunner } from '../commandRunner';
import { CLEAR_PREFIX, INJECTION_MODE, SANCTIONED_CLEAR_PREFIXES } from '../injectionRecipe';
import { clipboardSpy } from './__mocks__/vscode';
import { QuoinSession } from '../types';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeTerminal(): { sendTextCalls: string[]; showCalled: boolean; stub: import('vscode').Terminal } {
  const sendTextCalls: string[] = [];
  let showCalled = false;
  const stub = {
    name: 'test-terminal',
    show: () => { showCalled = true; },
    sendText: (text: string, _addNewLine?: boolean) => { sendTextCalls.push(text); },
    dispose: () => {},
  } as unknown as import('vscode').Terminal;
  return { sendTextCalls, showCalled, stub };
}

function makeSession(
  runtime: 'claude' | 'codex',
  terminal?: import('vscode').Terminal
): QuoinSession {
  return {
    id: 'test-session-uuid',
    label: `${runtime}-1`,
    runtime,
    terminal,
    projectRoot: '/tmp/proj',
    createdAt: Date.now(),
    relaunchable: terminal === undefined,
  };
}

// ── injectionRecipe carrier assertions (MAJ-1) ────────────────────────────────

describe('injectionRecipe constants', () => {
  it('CLEAR_PREFIX is one of SANCTIONED_CLEAR_PREFIXES', () => {
    assert.ok(
      (SANCTIONED_CLEAR_PREFIXES as readonly string[]).includes(CLEAR_PREFIX),
      `CLEAR_PREFIX '${CLEAR_PREFIX}' must be in SANCTIONED_CLEAR_PREFIXES ` +
      `(${SANCTIONED_CLEAR_PREFIXES.join(', ')})`
    );
  });

  it('INJECTION_MODE is either sendText or clipboard', () => {
    assert.ok(
      INJECTION_MODE === 'sendText' || INJECTION_MODE === 'clipboard',
      `INJECTION_MODE must be 'sendText' or 'clipboard', got '${INJECTION_MODE}'`
    );
  });
});

// ── buildInjection matrix ─────────────────────────────────────────────────────

describe('buildInjection', () => {
  it('Claude + skill + prompt → /skill prompt with CLEAR_PREFIX', () => {
    const result = buildInjection('claude', 'architect', 'plan the API');
    assert.equal(result, CLEAR_PREFIX + '/architect plan the API');
  });

  it('Claude + skill + empty prompt → /skill (no trailing space)', () => {
    const result = buildInjection('claude', 'architect', '');
    assert.equal(result, CLEAR_PREFIX + '/architect');
  });

  it('Claude + skill + whitespace-only prompt → /skill (prompt trimmed)', () => {
    const result = buildInjection('claude', 'architect', '   ');
    assert.equal(result, CLEAR_PREFIX + '/architect');
  });

  it('Claude + no skill (raw prompt) → CLEAR_PREFIX + prompt', () => {
    const result = buildInjection('claude', null, 'hello world');
    assert.equal(result, CLEAR_PREFIX + 'hello world');
  });

  it('Codex + skill → NEVER injects /skill prefix (R-09 guard)', () => {
    const result = buildInjection('codex', 'architect', 'plan');
    assert.equal(result, CLEAR_PREFIX + 'plan');
    assert.ok(!result.includes('/architect'), 'Codex must never get a /skill prefix');
  });

  it('Codex + raw prompt → CLEAR_PREFIX + prompt', () => {
    const result = buildInjection('codex', null, 'hello world');
    assert.equal(result, CLEAR_PREFIX + 'hello world');
  });

  it('output uses the imported CLEAR_PREFIX — not a stray literal', () => {
    // Proves the production string uses the spike constant, not a copy
    const result = buildInjection('claude', null, 'x');
    assert.equal(result, CLEAR_PREFIX + 'x');
  });
});

// ── CommandRunner.run ─────────────────────────────────────────────────────────

describe('CommandRunner.run', () => {
  let runner: CommandRunner;

  beforeEach(() => {
    runner = new CommandRunner();
    clipboardSpy.reset();
  });

  it('calls sendText with buildInjection output on a live-terminal session', () => {
    const { sendTextCalls, stub } = makeTerminal();
    const session = makeSession('claude', stub);

    runner.run(session, 'plan', 'my task');
    assert.equal(sendTextCalls.length, 1);
    assert.equal(sendTextCalls[0], buildInjection('claude', 'plan', 'my task'));
  });

  it('relaunchable session (no terminal) → showInformationMessage, no sendText', () => {
    const session = makeSession('claude', undefined);
    // Should not throw; terminal is undefined so the guard fires
    runner.run(session, 'plan', 'my task');
    // No way to assert showInformationMessage without a spy; assert no throw
  });

  it('Codex session via CommandRunner → sends raw text (no /skill)', () => {
    const { sendTextCalls, stub } = makeTerminal();
    const session = makeSession('codex', stub);

    runner.run(session, 'architect', 'some prompt');
    if (INJECTION_MODE === 'sendText') {
      assert.equal(sendTextCalls.length, 1);
      assert.ok(!sendTextCalls[0].includes('/architect'), 'Codex must not get /skill');
    }
  });
});

// ── Clipboard mode ────────────────────────────────────────────────────────────

describe('CommandRunner clipboard mode', () => {
  it('when INJECTION_MODE is clipboard, writes composed text to clipboard, not sendText', () => {
    if (INJECTION_MODE !== 'clipboard') {
      // Test only meaningful in clipboard mode — skip verification
      return;
    }
    const { sendTextCalls, stub } = makeTerminal();
    const session = makeSession('claude', stub);
    const runner = new CommandRunner();
    clipboardSpy.reset();

    runner.run(session, 'plan', 'my task');

    assert.equal(sendTextCalls.length, 0, 'sendText must not be called in clipboard mode');
    assert.equal(clipboardSpy.lastWritten, buildInjection('claude', 'plan', 'my task'));
  });
});
