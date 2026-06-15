import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { ProjectContext } from '../projectContext';
import { makeContext } from './__mocks__/vscode';

// In-memory fs stub: only paths explicitly added report existsSync true
function makeFsStub(existing: string[] = []): { existsSync: (p: string) => boolean } {
  const set = new Set(existing);
  return { existsSync: (p: string) => set.has(p) };
}

const noop = (_h: unknown) => ({ dispose: () => {} });

describe('ProjectContext — precedence (T-12a)', () => {
  it('returns activeProjectRoot override when it exists', () => {
    const ctx = makeContext();
    ctx.globalState.update('quoin.activeProjectRoot', '/a');
    const fsImpl = makeFsStub(['/a/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    assert.strictEqual(pc.getActiveRoot(), '/a');
  });

  it('falls through to workspace walk-up when override path has no .workflow_artifacts', () => {
    const ctx = makeContext();
    ctx.globalState.update('quoin.activeProjectRoot', '/stale');
    const fsImpl = makeFsStub(['/repo/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, {
      fsImpl,
      workspaceFoldersProvider: () => [{ uri: { fsPath: '/repo/packages/app' } }],
    });
    assert.strictEqual(pc.getActiveRoot(), '/repo');
  });

  it('falls through to lastProjectRoot when no workspace and no valid override', () => {
    const ctx = makeContext();
    ctx.globalState.update('quoin.lastProjectRoot', '/last');
    const fsImpl = makeFsStub(['/last/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    assert.strictEqual(pc.getActiveRoot(), '/last');
  });

  it('returns undefined when no root is discoverable', () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub([]);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    assert.strictEqual(pc.getActiveRoot(), undefined);
  });
});

describe('ProjectContext — setActiveRoot (T-12a)', () => {
  it('persists the root and fires onDidChangeActiveRoot exactly once', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub(['/b/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });

    const fired: Array<string | undefined> = [];
    pc.onDidChangeActiveRoot((root) => fired.push(root));

    await pc.setActiveRoot('/b');

    assert.strictEqual(fired.length, 1);
    assert.strictEqual(fired[0], '/b');
    assert.strictEqual(ctx.globalState.get('quoin.activeProjectRoot'), '/b');
  });

  it('persisted root is returned by getActiveRoot in a fresh instance', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub(['/b/.workflow_artifacts']);
    const pc1 = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    await pc1.setActiveRoot('/b');

    const pc2 = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    assert.strictEqual(pc2.getActiveRoot(), '/b');
  });
});

describe('ProjectContext — listKnownRoots dedup (T-12a)', () => {
  it('returns deduped workspace + persisted roots', () => {
    const ctx = makeContext();
    ctx.globalState.update('quoin.activeProjectRoot', '/a');
    const fsImpl = makeFsStub(['/a/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, {
      fsImpl,
      workspaceFoldersProvider: () => [{ uri: { fsPath: '/a' } }],
    });
    const roots = pc.listKnownRoots();
    // /a should appear only once despite being in both workspace and override
    assert.strictEqual(roots.filter(r => r === '/a').length, 1);
  });

  it('collapses legacy raw nested-path session keys to walk-up root', () => {
    const ctx = makeContext();
    // Simulate a pre-fix session stored under the raw nested path
    ctx.globalState.update('quoin.sessions::/repo/packages/app', []);
    const fsImpl = makeFsStub(['/repo/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    const roots = pc.listKnownRoots();
    // Should include /repo (collapsed), NOT /repo/packages/app
    assert.ok(roots.includes('/repo'), 'should contain collapsed root /repo');
    assert.ok(!roots.includes('/repo/packages/app'), 'should NOT contain raw nested path');
  });
});

describe('ProjectContext — nested-folder create path (T-12 nested fixture)', () => {
  it('walk-up from nested workspace folder returns the artifacts root', () => {
    const fsImpl = makeFsStub(['/repo/.workflow_artifacts']);
    const ctx = makeContext();
    const pc = new ProjectContext(ctx, {
      fsImpl,
      workspaceFoldersProvider: () => [{ uri: { fsPath: '/repo/packages/app' } }],
    });
    // Confirms that getActiveRoot() returns the walk-up root, not the raw folder path
    assert.strictEqual(pc.getActiveRoot(), '/repo');
  });
});

describe('SessionManager.getForRoot — root isolation (T-12b)', () => {
  it('getForRoot excludes sessions from other roots', async () => {
    const { SessionManager } = await import('../sessionManager');
    const ctx = makeContext();
    const manager = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    const termA = { name: 'a', show: () => {}, sendText: () => {}, dispose: () => {} } as unknown as import('vscode').Terminal;
    const termB = { name: 'b', show: () => {}, sendText: () => {}, dispose: () => {} } as unknown as import('vscode').Terminal;

    manager.create('claude', '/a', () => termA);
    manager.create('claude', '/b', () => termB);

    const rootA = manager.getForRoot('/a');
    assert.strictEqual(rootA.length, 1);
    assert.strictEqual(rootA[0].projectRoot, '/a');

    const rootB = manager.getForRoot('/b');
    assert.strictEqual(rootB.length, 1);
    assert.strictEqual(rootB[0].projectRoot, '/b');

    assert.strictEqual(manager.getForRoot('/unknown').length, 0);
  });
});
