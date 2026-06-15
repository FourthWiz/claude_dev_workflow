import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SessionsTreeProvider } from '../sessionsTree';
import { SessionManager } from '../sessionManager';
import { EventEmitter, makeMemento, makeContext } from './__mocks__/vscode';
import type { ProjectContext } from '../projectContext';

function makeManager() {
  const ctx = makeContext();
  const noop = (_h: unknown) => ({ dispose: () => {} });
  return new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);
}

function makeProjectContext(activeRoot: string | undefined): ProjectContext {
  const emitter = new EventEmitter<string | undefined>();
  return {
    getActiveRoot: () => activeRoot,
    setActiveRoot: async (_root: string) => { emitter.fire(_root); },
    listKnownRoots: () => [],
    onDidChangeActiveRoot: emitter.event,
  } as unknown as ProjectContext;
}

function makeTerminal(name: string): import('vscode').Terminal {
  return {
    name,
    show: () => {},
    sendText: () => {},
    dispose: () => {},
  } as unknown as import('vscode').Terminal;
}

describe('SessionsTreeProvider — project isolation (T-03)', () => {
  it('getChildren returns only sessions for the active project root', () => {
    const manager = makeManager();
    const termA = makeTerminal('a-1');
    const termB = makeTerminal('b-1');

    manager.create('claude', '/proj/a', () => termA);
    manager.create('claude', '/proj/b', () => termB);

    // Active root = /proj/a — should see only the /proj/a session
    const ctx = makeProjectContext('/proj/a');
    const provider = new SessionsTreeProvider(manager, ctx);
    const children = provider.getChildren();

    assert.strictEqual(children.length, 1, 'should return 1 session for /proj/a');
    assert.strictEqual(children[0].projectRoot, '/proj/a');
  });

  it('getChildren returns empty array when active root has no sessions', () => {
    const manager = makeManager();
    const termA = makeTerminal('a-1');
    manager.create('claude', '/proj/a', () => termA);

    const ctx = makeProjectContext('/proj/other');
    const provider = new SessionsTreeProvider(manager, ctx);
    const children = provider.getChildren();

    assert.strictEqual(children.length, 0, 'no sessions for /proj/other');
  });

  it('getChildren returns empty array when active root is undefined', () => {
    const manager = makeManager();
    const termA = makeTerminal('a-1');
    manager.create('claude', '/proj/a', () => termA);

    const ctx = makeProjectContext(undefined);
    const provider = new SessionsTreeProvider(manager, ctx);
    const children = provider.getChildren();

    assert.strictEqual(children.length, 0, 'undefined root should return empty');
  });
});
