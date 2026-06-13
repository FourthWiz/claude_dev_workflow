import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SessionManager } from '../sessionManager';
import { PersistedSession, QuoinSession } from '../types';

// Minimal Memento stub
function makeMemento(): import('vscode').Memento {
  const store = new Map<string, unknown>();
  return {
    keys: () => [...store.keys()],
    get<T>(key: string, defaultValue?: T): T {
      return (store.has(key) ? store.get(key) : defaultValue) as T;
    },
    update(key: string, value: unknown): Thenable<void> {
      store.set(key, value);
      return Promise.resolve();
    },
  };
}

// Minimal vscode.Terminal stub
function makeTerminal(name: string): import('vscode').Terminal {
  return { name, show: () => {}, sendText: () => {}, dispose: () => {} } as unknown as import('vscode').Terminal;
}

// Minimal ExtensionContext stub
function makeContext(): import('vscode').ExtensionContext {
  const gs = makeMemento();
  return {
    globalState: gs,
    subscriptions: [] as { dispose(): unknown }[],
  } as unknown as import('vscode').ExtensionContext;
}

describe('SessionManager.rehydrate', () => {
  it('maps persisted entries to sessions with terminal=undefined and relaunchable=true', () => {
    const persisted: PersistedSession[] = [
      { id: 'abc', label: 'claude-1', runtime: 'claude', projectRoot: '/tmp/proj', createdAt: 1000, relaunchable: false },
      { id: 'def', label: 'codex-1', runtime: 'codex', projectRoot: '/tmp/proj', createdAt: 2000, relaunchable: false },
    ];
    const sessions = SessionManager.rehydrate(persisted);
    assert.equal(sessions.length, 2);
    for (const s of sessions) {
      assert.equal(s.terminal, undefined);
      assert.equal(s.relaunchable, true);
    }
  });

  it('preserves id, label, runtime, projectRoot, createdAt', () => {
    const persisted: PersistedSession[] = [
      { id: 'xyz', label: 'claude-3', runtime: 'claude', projectRoot: '/foo/bar', createdAt: 42, relaunchable: false },
    ];
    const [s] = SessionManager.rehydrate(persisted);
    assert.equal(s.id, 'xyz');
    assert.equal(s.label, 'claude-3');
    assert.equal(s.runtime, 'claude');
    assert.equal(s.projectRoot, '/foo/bar');
    assert.equal(s.createdAt, 42);
  });
});

describe('SessionManager persistence', () => {
  it('round-trips sessions through globalState', async () => {
    const ctx = makeContext();
    const closeEmitter = { event: (_h: (t: import('vscode').Terminal) => void) => ({ dispose: () => {} }) };
    const manager = new SessionManager(ctx, closeEmitter.event as import('vscode').Event<import('vscode').Terminal>);

    manager.create('claude', '/tmp/proj', (_opts) => makeTerminal('claude-1'));
    manager.create('codex', '/tmp/proj', (_opts) => makeTerminal('codex-1'));

    // Simulate reload: new manager loads persisted state
    const manager2 = new SessionManager(ctx, closeEmitter.event as import('vscode').Event<import('vscode').Terminal>);
    manager2.loadPersisted('/tmp/proj');
    const sessions = manager2.getAll();

    assert.equal(sessions.length, 2);
    for (const s of sessions) {
      assert.equal(s.terminal, undefined);
      assert.equal(s.relaunchable, true);
    }
  });

  it('namespaces globalState key by projectRoot', async () => {
    const ctx = makeContext();
    const noop = (_h: unknown) => ({ dispose: () => {} });
    const m = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    m.create('claude', '/project/a', (_opts) => makeTerminal('t1'));
    m.create('claude', '/project/b', (_opts) => makeTerminal('t2'));

    const m2 = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);
    m2.loadPersisted('/project/a');
    assert.equal(m2.getAll().length, 1);
    assert.equal(m2.getAll()[0].projectRoot, '/project/a');
  });

  it('increments label counter per runtime per projectRoot', () => {
    const ctx = makeContext();
    const noop = (_h: unknown) => ({ dispose: () => {} });
    const m = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    const s1 = m.create('claude', '/p', (_opts) => makeTerminal('t'));
    const s2 = m.create('claude', '/p', (_opts) => makeTerminal('t'));
    const s3 = m.create('codex', '/p', (_opts) => makeTerminal('t'));

    assert.equal(s1.label, 'claude-1');
    assert.equal(s2.label, 'claude-2');
    assert.equal(s3.label, 'codex-1');
  });
});
