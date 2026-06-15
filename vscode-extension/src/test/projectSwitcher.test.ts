import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { ProjectContext } from '../projectContext';
import { registerStatusBar, registerCommands } from '../commands';
import { SessionManager } from '../sessionManager';
import {
  makeContext,
  showQuickPickSpy,
  _setShowQuickPickReturn,
  _getLastStatusBarItem,
  _getRegisteredCommand,
  _clearRegisteredCommands,
} from './__mocks__/vscode';

const noop = (_h: unknown) => ({ dispose: () => {} });

function makeFsStub(existing: string[]): { existsSync: (p: string) => boolean } {
  const set = new Set(existing);
  return { existsSync: (p: string) => set.has(p) };
}

describe('Project switcher — status bar + quoin.switchProject (T-13)', () => {
  beforeEach(() => {
    showQuickPickSpy.reset();
    _setShowQuickPickReturn(undefined);
    _clearRegisteredCommands();
  });

  it('registerStatusBar creates a StatusBarItem showing the active root basename', () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub(['/home/user/quoin/.workflow_artifacts']);
    ctx.globalState.update('quoin.activeProjectRoot', '/home/user/quoin');
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });

    registerStatusBar(ctx, pc);

    const item = _getLastStatusBarItem();
    assert.ok(item, 'status bar item should be created');
    assert.ok(item.text.includes('quoin'), `expected basename 'quoin' in text, got: ${item.text}`);
  });

  it('status bar text updates when onDidChangeActiveRoot fires', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub([
      '/proj/a/.workflow_artifacts',
      '/proj/b/.workflow_artifacts',
    ]);
    ctx.globalState.update('quoin.activeProjectRoot', '/proj/a');
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });

    registerStatusBar(ctx, pc);
    const item = _getLastStatusBarItem()!;
    assert.ok(item.text.includes('a'), 'initial: should show basename a');

    await pc.setActiveRoot('/proj/b');
    assert.ok(item.text.includes('b'), 'after switch: should show basename b');
  });

  it('quoin.switchProject reads pick.detail (full path) not pick.label (basename)', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub([
      '/proj/a/.workflow_artifacts',
      '/proj/b/.workflow_artifacts',
    ]);
    ctx.globalState.update('quoin.activeProjectRoot', '/proj/a');
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    const manager = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    registerCommands(ctx, manager, pc);
    const handler = _getRegisteredCommand('quoin.switchProject') as (() => Promise<void>) | undefined;
    assert.ok(handler, 'quoin.switchProject command should be registered');

    // Return an object pick {label: basename, detail: full path}
    _setShowQuickPickReturn({ label: 'b', detail: '/proj/b' });

    const fired: Array<string | undefined> = [];
    pc.onDidChangeActiveRoot((r) => fired.push(r));

    await handler();

    assert.strictEqual(fired.length, 1, 'onDidChangeActiveRoot should fire once');
    assert.strictEqual(fired[0], '/proj/b', 'should fire with the full path from pick.detail');
    assert.strictEqual(ctx.globalState.get('quoin.activeProjectRoot'), '/proj/b');
    assert.strictEqual(showQuickPickSpy.calls.length, 1, 'showQuickPick should be called once');
  });

  it('quoin.switchProject feeds listKnownRoots as {label, detail} items', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub(['/proj/a/.workflow_artifacts', '/proj/b/.workflow_artifacts']);
    ctx.globalState.update('quoin.activeProjectRoot', '/proj/a');
    ctx.globalState.update('quoin.sessions::/proj/b', []);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    const manager = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    registerCommands(ctx, manager, pc);
    const handler = _getRegisteredCommand('quoin.switchProject') as () => Promise<void>;

    _setShowQuickPickReturn(undefined); // user cancels
    await handler();

    assert.strictEqual(showQuickPickSpy.calls.length, 1);
    const items = showQuickPickSpy.calls[0][0] as Array<{ label: string; detail: string }>;
    assert.ok(Array.isArray(items), 'showQuickPick should receive an array');
    // Each item must have both label (basename) and detail (full path)
    for (const item of items) {
      assert.ok('label' in item, 'item should have label');
      assert.ok('detail' in item, 'item should have detail');
      assert.ok(item.detail.startsWith('/proj/'), `detail should be full path, got: ${item.detail}`);
    }
  });

  it('quoin.switchProject does nothing when no project roots are known', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub([]);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    const manager = new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);

    registerCommands(ctx, manager, pc);
    const handler = _getRegisteredCommand('quoin.switchProject') as () => Promise<void>;

    const fired: unknown[] = [];
    pc.onDidChangeActiveRoot((r) => fired.push(r));

    await handler();

    assert.strictEqual(showQuickPickSpy.calls.length, 0, 'showQuickPick should not be called with empty roots');
    assert.strictEqual(fired.length, 0, 'onDidChangeActiveRoot should not fire');
  });

  it('selection persists across a fresh ProjectContext instance', async () => {
    const ctx = makeContext();
    const fsImpl = makeFsStub(['/proj/b/.workflow_artifacts']);
    const pc = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    await pc.setActiveRoot('/proj/b');

    // Simulate reload
    const pc2 = new ProjectContext(ctx, { fsImpl, workspaceFoldersProvider: () => undefined });
    assert.strictEqual(pc2.getActiveRoot(), '/proj/b', 'selected root should survive reload');
  });
});
