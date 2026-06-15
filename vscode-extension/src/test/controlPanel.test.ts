import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { ControlPanelViewProvider } from '../controlPanel';
import { CommandRunner } from '../commandRunner';
import { SessionManager } from '../sessionManager';
import { Uri, makeStubWebviewView, makeMemento, makeContext, EventEmitter } from './__mocks__/vscode';
import type { ProjectContext } from '../projectContext';

function makeTerminal(name: string): import('vscode').Terminal {
  const calls: { text: string; addNewLine: boolean }[] = [];
  const t = {
    name,
    show: () => {},
    sendText: (text: string, addNewLine = true) => calls.push({ text, addNewLine }),
    dispose: () => {},
    _calls: calls,
  } as unknown as import('vscode').Terminal;
  return t;
}

type TerminalWithCalls = import('vscode').Terminal & { _calls: { text: string; addNewLine: boolean }[] };

function makeManager() {
  const ctx = makeContext();
  const noop = (_h: unknown) => ({ dispose: () => {} });
  return new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);
}

function makeProjectContext(activeRoot: string | undefined): ProjectContext {
  const emitter = new EventEmitter<string | undefined>();
  return {
    getActiveRoot: () => activeRoot,
    setActiveRoot: async (_root: string) => {},
    listKnownRoots: () => [],
    onDidChangeActiveRoot: emitter.event,
  } as unknown as ProjectContext;
}

function simulateRun(
  provider: ControlPanelViewProvider,
  webview: { simulateMessage: (msg: unknown) => void },
  payload: { skill: string | null; prompt: string; sessionId: string }
): void {
  webview.simulateMessage({ cmd: 'run', ...payload });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('ControlPanelViewProvider — Codex guard (T-04)', () => {
  it('Codex session: host forces skill=null even when webview sends a non-null skill', () => {
    const manager = makeManager();
    const terminal = makeTerminal('codex-1') as TerminalWithCalls;
    const session = manager.create('codex', '/tmp/proj', () => terminal);

    const commandRunner = new CommandRunner();
    const provider = new ControlPanelViewProvider(
      Uri.file('/ext') as unknown as import('vscode').Uri,
      manager,
      makeProjectContext('/tmp/proj'),
      commandRunner
    );

    const { view, webview } = makeStubWebviewView();
    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as import('vscode').CancellationToken
    );

    // Webview sends a run message with a non-null skill for a Codex session
    // Host must force skill=null → buildInjection('codex', null, 'hello') = '' + 'hello'
    simulateRun(provider, webview, {
      skill: 'architect',
      prompt: 'hello',
      sessionId: session.id,
    });

    // Terminal should have received the raw prompt WITHOUT the /architect prefix
    const calls = (terminal as TerminalWithCalls)._calls;
    assert.ok(calls.length > 0, 'sendText should have been called');
    const text = calls[calls.length - 1].text;
    assert.ok(!text.includes('/architect'),
      `Expected no /architect prefix for Codex session, got: "${text}"`);
  });

  it('Claude session: host preserves skill value from webview', () => {
    const manager = makeManager();
    const terminal = makeTerminal('claude-1') as TerminalWithCalls;
    const session = manager.create('claude', '/tmp/proj', () => terminal);

    const provider = new ControlPanelViewProvider(
      Uri.file('/ext') as unknown as import('vscode').Uri,
      manager,
      makeProjectContext('/tmp/proj'),
      new CommandRunner()
    );

    const { view, webview } = makeStubWebviewView();
    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as import('vscode').CancellationToken
    );

    simulateRun(provider, webview, {
      skill: 'plan',
      prompt: 'my feature',
      sessionId: session.id,
    });

    const calls = (terminal as TerminalWithCalls)._calls;
    assert.ok(calls.length > 0, 'sendText should have been called');
    const text = calls[calls.length - 1].text;
    assert.ok(text.includes('/plan'), `Expected /plan in injected text, got: "${text}"`);
  });

  it('unknown sessionId → no sendText, no crash', () => {
    const manager = makeManager();
    const provider = new ControlPanelViewProvider(
      Uri.file('/ext') as unknown as import('vscode').Uri,
      manager,
      makeProjectContext(undefined),
      new CommandRunner()
    );

    const { view, webview } = makeStubWebviewView();
    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as import('vscode').CancellationToken
    );

    // Should not throw; session lookup returns undefined
    assert.doesNotThrow(() => {
      simulateRun(provider, webview, {
        skill: 'plan',
        prompt: 'test',
        sessionId: 'nonexistent-uuid-1234',
      });
    });
  });
});
