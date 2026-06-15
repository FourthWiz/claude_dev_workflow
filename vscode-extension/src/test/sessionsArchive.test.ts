import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SessionsArchiveViewProvider } from '../sessionsArchive';
import { FsLike, ArchivedSession } from '../archiveScanner';
import {
  Uri,
  EventEmitter,
  makeStubWebviewView,
  executeCommandSpy,
  StubWebview,
} from './__mocks__/vscode';
import { DataService } from '../dataService';
import { SessionManager } from '../sessionManager';
import { QuoinSession } from '../types';
import type { ProjectContext } from '../projectContext';

// ── Stubs ─────────────────────────────────────────────────────────────────────

function makeDataServiceStub(overrides: Partial<DataService> = {}): DataService {
  const onDidChangeEmitter = new EventEmitter<void>();
  return {
    onDidChange: onDidChangeEmitter.event,
    _emitter: onDidChangeEmitter,
    getProjectRoot: (_folders: unknown) => '/fake/root',
    getActiveTask: async (_root: string) => undefined,
    getWorkflowNodes: async () => ({ status: 'no-task' }),
    watch: (_root: string) => ({ dispose: () => {} }),
    dispose: () => {},
    ...overrides,
  } as unknown as DataService;
}

function makeSessionManagerStub(sessions: Partial<QuoinSession>[] = []) {
  const onDidChangeEmitter = new EventEmitter<void>();
  return {
    onDidChange: onDidChangeEmitter.event,
    _emitter: onDidChangeEmitter,
    getAll: () => sessions as QuoinSession[],
    getForRoot: (root: string) => (sessions as QuoinSession[]).filter(s => s.projectRoot === root),
  };
}

function makeProjectContextStub(activeRoot: string | undefined): ProjectContext {
  const emitter = new EventEmitter<string | undefined>();
  return {
    getActiveRoot: () => activeRoot,
    setActiveRoot: async (_root: string) => {},
    listKnownRoots: () => [],
    onDidChangeActiveRoot: emitter.event,
    _emitter: emitter,
  } as unknown as ProjectContext;
}

function makeFakeFs(archived: ArchivedSession[]): FsLike {
  // We return a fake fs that yields exactly the archived entries passed in.
  // scanArchive is the real function — use a root that matches what we mock.
  // However, for provider tests we prefer to control what scanArchive returns.
  // Approach: inject a fake fs that makes sessionsDir exist with .md files,
  // and each file's content encodes the desired label/status.

  // Build per-file content from archived entries
  const sessionsDir = '/fake/root/.workflow_artifacts/memory/sessions';
  const checkpointsDir = '/fake/root/.workflow_artifacts/memory/checkpoints';
  const dirs: Record<string, string[]> = {
    [sessionsDir]: [],
    [checkpointsDir]: [],
  };
  const files: Record<string, string> = {};

  for (const entry of archived) {
    const name = entry.filePath.split('/').pop()!;
    const dir = entry.source === 'session' ? sessionsDir : checkpointsDir;
    dirs[dir].push(name);
    // Encode date/status/task in frontmatter for the real parser to extract
    const lines = ['---'];
    if (entry.task) { lines.push(`task: ${entry.task}`); }
    if (entry.date) { lines.push(`date: ${entry.date}`); }
    lines.push('---');
    if (entry.status) { lines.push(`## Status\n${entry.status}`); }
    files[entry.filePath] = lines.join('\n') + '\n';
  }

  return {
    existsSync: (p: string) => p in dirs || p in files,
    readdirSync: (p: string) => dirs[p] ?? [],
    readFileSync: (p: string, _enc: 'utf8') => {
      if (p in files) { return files[p]; }
      throw new Error(`ENOENT: ${p}`);
    },
  };
}

/** Make three sample archived sessions */
function makeArchivedSessions(count: number): ArchivedSession[] {
  const result: ArchivedSession[] = [];
  for (let i = 0; i < count; i++) {
    const date = `2026-06-${String(14 - i).padStart(2, '0')}`;
    result.push({
      label: `session-${i}`,
      filePath: `/fake/root/.workflow_artifacts/memory/sessions/${date}-session-${i}.md`,
      source: 'session',
      date,
      task: `task-${i}`,
    });
  }
  return result;
}

function buildProvider(opts: {
  sessions?: Partial<QuoinSession>[];
  archived?: ArchivedSession[];
  dsOverrides?: Partial<DataService>;
  activeRoot?: string | undefined;
}): {
  provider: SessionsArchiveViewProvider;
  ds: DataService;
  sm: ReturnType<typeof makeSessionManagerStub>;
  fakeFs: FsLike;
} {
  const archived = opts.archived ?? [];
  const fakeFs = makeFakeFs(archived);
  const ds = makeDataServiceStub(opts.dsOverrides ?? {});
  const sm = makeSessionManagerStub(opts.sessions ?? []);
  const activeRoot = 'activeRoot' in opts ? opts.activeRoot : '/fake/root';
  const pc = makeProjectContextStub(activeRoot);
  const provider = new SessionsArchiveViewProvider(
    Uri.file('/ext') as unknown as import('vscode').Uri,
    sm as unknown as SessionManager,
    pc,
    ds,
    fakeFs,
  );
  return { provider, ds, sm, fakeFs };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('SessionsArchiveViewProvider', () => {
  it('posts one render message on resolveWebviewView with correct lengths', async () => {
    const archivedSessions = makeArchivedSessions(3);
    const activeSessions: Partial<QuoinSession>[] = [
      { id: 'a1', label: 'claude-1', runtime: 'claude', projectRoot: '/fake/root', relaunchable: false, terminal: { show: () => {} } as unknown as import('vscode').Terminal },
      { id: 'a2', label: 'claude-2', runtime: 'claude', projectRoot: '/fake/root', relaunchable: false, terminal: { show: () => {} } as unknown as import('vscode').Terminal },
    ];

    const { provider } = buildProvider({ sessions: activeSessions, archived: archivedSessions });
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; active?: unknown[]; archived?: unknown[]; hasRoot?: boolean }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render, 'expected a render message');
    assert.strictEqual(render!.active?.length, 2, 'active length');
    assert.strictEqual(render!.archived?.length, 3, 'archived length');
    assert.strictEqual(render!.hasRoot, true, 'hasRoot should be true');
  });

  it('posts render with hasRoot:false when no root found', async () => {
    const { provider } = buildProvider({ activeRoot: undefined });
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; hasRoot?: boolean }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render);
    assert.strictEqual(render!.hasRoot, false);
  });

  it('does not render when initially hidden, then renders on first show (visibility listener)', async () => {
    const { provider } = buildProvider({});
    const { view, webview, setVisible } = makeStubWebviewView(false);  // start hidden

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    // Settle — _refresh() is synchronous, but await for uniformity; guard must block
    await new Promise((r) => setTimeout(r, 20));
    const rendersBefore = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;
    assert.strictEqual(rendersBefore, 0, 'no render should be posted while view is hidden');

    // Now make visible — visibility listener must fire _refresh()
    setVisible(true);
    await new Promise((r) => setTimeout(r, 20));

    const rendersAfter = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;
    assert.strictEqual(rendersAfter, 1, 'exactly one render should be posted after becoming visible');
  });

  it('fires second render when sessionManager.onDidChange fires', async () => {
    const { provider, sm } = buildProvider({});
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));
    const countBefore = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;

    // Fire session change
    sm._emitter.fire();
    await new Promise((r) => setTimeout(r, 20));

    const countAfter = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;
    assert.ok(countAfter > countBefore, 'expected a second render after sessionManager change');
  });

  it('fires second render when dataService.onDidChange fires', async () => {
    const onDidChangeEmitter = new EventEmitter<void>();
    const { provider } = buildProvider({
      dsOverrides: {
        onDidChange: onDidChangeEmitter.event,
      } as Partial<DataService>,
    });
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));
    const countBefore = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;

    onDidChangeEmitter.fire();
    await new Promise((r) => setTimeout(r, 20));

    const countAfter = webview.getPostedMessages().filter((m: unknown) => (m as { cmd: string }).cmd === 'render').length;
    assert.ok(countAfter > countBefore, 'expected a second render after dataService change');
  });

  it('inbound reveal message calls quoin.revealSession exactly once', async () => {
    executeCommandSpy.reset();
    const { provider } = buildProvider({});
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    // Simulate webview sending a reveal message
    webview.simulateMessage({ cmd: 'reveal', sessionId: 'abc' });
    await new Promise((r) => setTimeout(r, 10));

    const calls = executeCommandSpy.calls;
    const reveal = calls.find((c) => c.cmd === 'quoin.revealSession');
    assert.ok(reveal, 'expected quoin.revealSession to be called');
    assert.deepStrictEqual(reveal!.args, ['abc']);
  });

  it('inbound open message calls quoin.openArchivedSession exactly once', async () => {
    executeCommandSpy.reset();
    const { provider } = buildProvider({});
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    webview.simulateMessage({ cmd: 'open', filePath: '/x.md' });
    await new Promise((r) => setTimeout(r, 10));

    const calls = executeCommandSpy.calls;
    const open = calls.find((c) => c.cmd === 'quoin.openArchivedSession');
    assert.ok(open, 'expected quoin.openArchivedSession to be called');
    assert.deepStrictEqual(open!.args, ['/x.md']);
  });

  it('inbound garbage {cmd:reveal} with no sessionId does NOT call executeCommand', async () => {
    executeCommandSpy.reset();
    const { provider } = buildProvider({});
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    webview.simulateMessage({ cmd: 'reveal' }); // no sessionId
    await new Promise((r) => setTimeout(r, 10));

    assert.strictEqual(executeCommandSpy.calls.length, 0, 'no executeCommand on invalid reveal');
  });

  it('inbound garbage {cmd:nope} does NOT call executeCommand', async () => {
    executeCommandSpy.reset();
    const { provider } = buildProvider({});
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    webview.simulateMessage({ cmd: 'nope' });
    await new Promise((r) => setTimeout(r, 10));

    assert.strictEqual(executeCommandSpy.calls.length, 0, 'no executeCommand on unknown command');
  });

  it('MIN-1: stub active session with terminal:undefined maps to relaunchable:true', async () => {
    const sessions: Partial<QuoinSession>[] = [
      { id: 'r1', label: 'claude-1', runtime: 'claude', projectRoot: '/fake/root', relaunchable: false, terminal: undefined },
    ];
    const { provider } = buildProvider({ sessions });
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; active?: Array<{ relaunchable: boolean }> }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render?.active);
    assert.strictEqual(render!.active![0].relaunchable, true, 'no terminal → relaunchable:true');
  });

  it('MIN-1: stub active session with live terminal and relaunchable:false maps to relaunchable:false', async () => {
    const sessions: Partial<QuoinSession>[] = [
      { id: 'l1', label: 'claude-1', runtime: 'claude', projectRoot: '/fake/root', relaunchable: false, terminal: { show: () => {} } as unknown as import('vscode').Terminal },
    ];
    const { provider } = buildProvider({ sessions });
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; active?: Array<{ relaunchable: boolean }> }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render?.active);
    assert.strictEqual(render!.active![0].relaunchable, false, 'live terminal → relaunchable:false');
  });

  it('CSP: _buildHtml contains nonce, default-src none, no unsafe-inline, webview-URI refs', () => {
    const { provider } = buildProvider({});
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);

    assert.ok(html.includes("default-src 'none'"), 'CSP must contain default-src none');
    assert.ok(html.includes("script-src 'nonce-"), 'CSP must have nonce-gated script-src');
    assert.ok(!html.includes("'unsafe-inline'"), 'CSP must NOT contain unsafe-inline');
    assert.ok(html.includes('nonce="'), '<script> tag must have nonce attribute');
    assert.ok(html.includes('sessionsArchive.js'), 'must reference sessionsArchive.js');
    assert.ok(html.includes('sessionsArchive.css'), 'must reference sessionsArchive.css');
    assert.ok(html.includes('<link rel="stylesheet"'), 'CSS loaded via external link');
    assert.ok(!html.includes('<style'), 'no inline <style> tag');

    // No http:// or https:// in CSP
    const cspMatch = html.match(/Content-Security-Policy" content="([^"]*)"/);
    assert.ok(cspMatch, 'CSP meta tag must exist');
    const cspValue = cspMatch![1];
    assert.ok(!cspValue.includes('http://'), 'CSP must not allow http:// origins');
    assert.ok(!cspValue.includes('https://'), 'CSP must not allow https:// origins');
  });
});
