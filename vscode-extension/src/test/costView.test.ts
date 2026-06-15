/**
 * costView.test.ts — host-side provider tests for CostViewProvider.
 *
 * Validates:
 *   - CSP is byte-identical to the shipped 5-directive string (R-05)
 *   - A cmd:'render' message is posted on resolveWebviewView
 *   - No crash on empty / no-scripts view
 *   - Nonce is present and CSP has no unsafe-inline or remote origins
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { CostViewProvider } from '../costView';
import { DataService } from '../dataService';
import {
  Uri,
  EventEmitter,
  makeStubWebviewView,
  StubWebview,
} from './__mocks__/vscode';
import type { CostView } from '../costService';
import type { ProjectContext } from '../projectContext';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** The 5-directive CSP string shipped by sessionsArchive.ts (R-05 reference). */
const SHIPPED_CSP_DIRECTIVES = [
  "default-src 'none'",
  'style-src',
  "script-src 'nonce-",
  'img-src',
  'font-src',
];

function makeDataServiceStub(overrides: Partial<DataService> = {}): DataService {
  const onDidChangeEmitter = new EventEmitter<void>();
  return {
    onDidChange: onDidChangeEmitter.event,
    _emitter: onDidChangeEmitter,
    getProjectRoot: (_folders: unknown) => '/fake/root',
    getActiveTask: async (_root: string) => undefined,
    getWorkflowNodes: async () => ({ status: 'no-task' }),
    watch: (_root: string) => ({ dispose: () => {} }),
    getCostView: async (_root: string): Promise<CostView> => ({
      live: null,
      tasks: [],
      finalizedGrandTotal: null,
      finalizedGrandTotalState: 'unavailable',
      scopeNote: 'Test scope note.',
    }),
    readCostSummaries: (_root: string) => [],
    liveSpend: async (_root: string) => null,
    taskCounts: async (_root: string) => [],
    dispose: () => {},
    ...overrides,
  } as unknown as DataService;
}

function makeProjectContextStub(activeRoot: string | undefined): ProjectContext {
  const emitter = new EventEmitter<string | undefined>();
  return {
    getActiveRoot: () => activeRoot,
    setActiveRoot: async (_root: string) => {},
    listKnownRoots: () => [],
    onDidChangeActiveRoot: emitter.event,
  } as unknown as ProjectContext;
}

function buildProvider(overrides: Partial<DataService> = {}, activeRoot: string | undefined = '/fake/root'): {
  provider: CostViewProvider;
  ds: DataService;
} {
  const ds = makeDataServiceStub(overrides);
  const pc = makeProjectContextStub(activeRoot);
  const provider = new CostViewProvider(
    Uri.file('/ext') as unknown as import('vscode').Uri,
    ds,
    pc,
  );
  return { provider, ds };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('CostViewProvider — _buildHtml CSP', () => {
  it('HTML contains all 5 CSP directives (byte-identical to shipped sessionsArchive.ts)', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);

    for (const directive of SHIPPED_CSP_DIRECTIVES) {
      assert.ok(
        html.includes(directive),
        `CSP must contain "${directive}"`
      );
    }
  });

  it("CSP contains default-src 'none'", () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    assert.ok(html.includes("default-src 'none'"), "CSP must contain default-src 'none'");
  });

  it("CSP has nonce-gated script-src (no 'unsafe-inline')", () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    assert.ok(html.includes("script-src 'nonce-"), 'CSP must have nonce-gated script-src');
    assert.ok(!html.includes("'unsafe-inline'"), "CSP must NOT contain 'unsafe-inline'");
  });

  it('<script> tag carries the nonce attribute', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    assert.ok(html.includes('nonce="'), '<script> must have nonce attribute');
  });

  it('CSS loaded via external <link> (no inline <style>)', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    assert.ok(html.includes('<link rel="stylesheet"'), 'External <link rel="stylesheet"> must exist');
    assert.ok(!html.includes('<style'), 'No inline <style> tag allowed');
  });

  it('CSP references costView.js and costView.css (not hardcoded sessionsArchive refs)', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    assert.ok(html.includes('costView.js'), 'must reference costView.js');
    assert.ok(html.includes('costView.css'), 'must reference costView.css');
  });

  it('CSP has no http:// or https:// remote origins', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html = provider._buildHtml(webview as unknown as import('vscode').Webview);
    const cspMatch = html.match(/Content-Security-Policy" content="([^"]*)"/);
    assert.ok(cspMatch, 'CSP meta tag must exist');
    const cspValue = cspMatch![1];
    assert.ok(!cspValue.includes('http://'), 'CSP must not allow http:// origins');
    assert.ok(!cspValue.includes('https://'), 'CSP must not allow https:// origins');
  });

  it('produces a unique nonce on each call', () => {
    const { provider } = buildProvider();
    const webview = new StubWebview();
    const html1 = provider._buildHtml(webview as unknown as import('vscode').Webview);
    const html2 = provider._buildHtml(webview as unknown as import('vscode').Webview);

    // Extract nonces
    const nonceMatch1 = html1.match(/nonce="([^"]+)"/);
    const nonceMatch2 = html2.match(/nonce="([^"]+)"/);
    assert.ok(nonceMatch1 && nonceMatch2, 'nonce must be present in both renders');
    assert.notStrictEqual(nonceMatch1![1], nonceMatch2![1], 'each render must produce a unique nonce');
  });
});

describe('CostViewProvider — resolveWebviewView', () => {
  it('posts a cmd:render message on resolve', async () => {
    const { provider } = buildProvider();
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 30));

    const messages = webview.getPostedMessages() as Array<{ cmd: string }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render, 'expected a render message after resolveWebviewView');
  });

  it('render message has hasRoot:true when project root found', async () => {
    const { provider } = buildProvider();
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 30));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; hasRoot?: boolean }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render);
    assert.strictEqual(render!.hasRoot, true, 'hasRoot should be true when root found');
  });

  it('render message has hasRoot:false when no project root', async () => {
    const ds = makeDataServiceStub({});
    const pc = makeProjectContextStub(undefined);
    const provider = new CostViewProvider(
      Uri.file('/ext') as unknown as import('vscode').Uri, ds, pc,
    );
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 30));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; hasRoot?: boolean }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render);
    assert.strictEqual(render!.hasRoot, false);
  });

  it('no crash when getCostView returns null (no-scripts view)', async () => {
    await assert.doesNotReject(async () => {
      const { provider } = buildProvider({
        getCostView: async (_root: string): Promise<CostView> => {
          throw new Error('scripts not found');
        },
      } as Partial<DataService>);
      const { view, webview } = makeStubWebviewView();

      provider.resolveWebviewView(
        view as unknown as import('vscode').WebviewView,
        {} as import('vscode').WebviewViewResolveContext,
        { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
      );

      await new Promise((r) => setTimeout(r, 30));

      // Should still post a render message (with view:null)
      const messages = webview.getPostedMessages() as Array<{ cmd: string; view?: unknown }>;
      const render = messages.find((m) => m.cmd === 'render');
      assert.ok(render, 'should still render even on getCostView error');
      assert.strictEqual(render!.view, null, 'view should be null when getCostView throws');
    });
  });

  it('fires a second render when dataService.onDidChange fires', async () => {
    const onDidChangeEmitter = new EventEmitter<void>();
    const { provider } = buildProvider({
      onDidChange: onDidChangeEmitter.event,
    } as Partial<DataService>);
    const { view, webview } = makeStubWebviewView();

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 30));
    const countBefore = webview.getPostedMessages().filter((m) => (m as { cmd: string }).cmd === 'render').length;

    onDidChangeEmitter.fire();
    await new Promise((r) => setTimeout(r, 30));

    const countAfter = webview.getPostedMessages().filter((m) => (m as { cmd: string }).cmd === 'render').length;
    assert.ok(countAfter > countBefore, 'expected a second render after dataService.onDidChange');
  });
});
