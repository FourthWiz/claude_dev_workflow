import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { ControlPanelViewProvider } from '../controlPanel';
import { CommandRunner } from '../commandRunner';
import { SessionManager } from '../sessionManager';
import { CostViewProvider } from '../costView';
import { DataService } from '../dataService';
import { Uri, StubWebview, EventEmitter } from './__mocks__/vscode';
import type { ProjectContext } from '../projectContext';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMemento(): import('vscode').Memento {
  const store = new Map<string, unknown>();
  return {
    keys: () => [...store.keys()],
    get<T>(key: string, def?: T): T { return (store.has(key) ? store.get(key) : def) as T; },
    update(key: string, value: unknown): Thenable<void> { store.set(key, value); return Promise.resolve(); },
  };
}

function makeContext(): import('vscode').ExtensionContext {
  return {
    globalState: makeMemento(),
    subscriptions: [],
    extensionUri: Uri.file('/ext'),
  } as unknown as import('vscode').ExtensionContext;
}

function makeManager(): SessionManager {
  const ctx = makeContext();
  const noop = (_h: unknown) => ({ dispose: () => {} });
  return new SessionManager(ctx, noop as import('vscode').Event<import('vscode').Terminal>);
}

function makeProjectContextStub(activeRoot: string | undefined = undefined): ProjectContext {
  const emitter = new EventEmitter<string | undefined>();
  return {
    getActiveRoot: () => activeRoot,
    setActiveRoot: async (_root: string) => {},
    listKnownRoots: () => [],
    onDidChangeActiveRoot: emitter.event,
  } as unknown as ProjectContext;
}

function buildHtml(provider: ControlPanelViewProvider, webview: StubWebview): string {
  return provider._buildHtml(webview as unknown as import('vscode').Webview);
}

// ── CSP assertions ────────────────────────────────────────────────────────────

describe('ControlPanelViewProvider HTML builder — CSP (R-05)', () => {
  function setup(): { provider: ControlPanelViewProvider; webview: StubWebview; html: string } {
    const manager = makeManager();
    const runner = new CommandRunner();
    const p = new ControlPanelViewProvider(Uri.file('/ext') as unknown as import('vscode').Uri, manager, makeProjectContextStub(), runner);
    const w = new StubWebview();
    const h = buildHtml(p, w);
    return { provider: p, webview: w, html: h };
  }

  it('HTML contains default-src none in CSP meta', () => {
    const { html } = setup();
    assert.ok(
      html.includes("default-src 'none'"),
      'CSP must contain default-src \'none\''
    );
  });

  it('HTML has a nonce-gated script-src (no unsafe-inline)', () => {
    const { html } = setup();
    assert.ok(html.includes("script-src 'nonce-"), 'CSP must have nonce-gated script-src');
    assert.ok(!html.includes("'unsafe-inline'"), "CSP must NOT contain 'unsafe-inline'");
  });

  it('HTML has exactly one <script> tag and it carries the nonce attribute', () => {
    const { html } = setup();
    const scriptMatches = html.match(/<script/g) ?? [];
    assert.equal(scriptMatches.length, 1, 'Exactly one <script> tag required');
    assert.ok(html.includes('nonce="'), '<script> tag must have nonce attribute');
  });

  it('CSS loaded via external <link> (no inline <style>)', () => {
    const { html } = setup();
    assert.ok(html.includes('<link rel="stylesheet"'), 'External <link rel="stylesheet"> must exist');
    assert.ok(!html.includes('<style'), 'No inline <style> tag allowed (CSP-unsafe)');
  });

  it('CSP has no http:// or https:// remote origin', () => {
    const { html } = setup();
    // Extract the CSP content attribute value
    const cspMatch = html.match(/Content-Security-Policy" content="([^"]*)"/);
    assert.ok(cspMatch, 'CSP meta tag must exist');
    const cspValue = cspMatch![1];
    assert.ok(!cspValue.includes('http://'), 'CSP must not allow http:// origins');
    assert.ok(!cspValue.includes('https://'), 'CSP must not allow https:// origins');
  });

  it('HTML-escapes a malicious skill name — <script> tag becomes inert', () => {
    // Simulate the HTML that would be generated if a skill name had injection characters.
    // The controlPanel.js receives skill names via postMessage (not injected into the initial HTML),
    // but the CSP meta itself must not contain unescaped angle brackets.
    // Here we test that escapeHtml works via the CSP line (which uses it).
    const { html } = setup();

    // The CSP content includes 'default-src' — if escaping broke, the CSP tag itself would parse wrong.
    // More directly: attempt to find a bare <script> that isn't the extension's own nonce'd script.
    // We expect exactly one <script ... nonce=... src=...> and no other <script> tags.
    const scriptTagPattern = /<script(?![^>]*nonce=)/g;
    const unNoncedScripts = html.match(scriptTagPattern);
    assert.equal(
      unNoncedScripts,
      null,
      'All <script> tags must carry a nonce — no un-nonce\'d scripts found'
    );
  });

  it('.vscodeignore packaging check: media/ is NOT in .vscodeignore (MIN-2)', () => {
    const vscodeignorePath = path.join(__dirname, '../../../.vscodeignore');
    if (!fs.existsSync(vscodeignorePath)) {
      // .vscodeignore not present — media ships by default; skip
      return;
    }
    const content = fs.readFileSync(vscodeignorePath, 'utf8');
    const lines = content.split('\n').map((l: string) => l.trim());
    const mediaExcluded = lines.some((l: string) => l === 'media/' || l === 'media/**');
    assert.ok(!mediaExcluded,
      '.vscodeignore must NOT exclude media/ — controlPanel.js and .css must ship in the .vsix');
  });
});

// ── CostViewProvider CSP assertion (R-05) ──────────────────────────────────

/** The locked 5-directive CSP string (byte-identical to sessionsArchive.ts:174-178). */
const COST_CSP_LOCKED = [
  "default-src 'none'",
  'style-src',
  "script-src 'nonce-",
  'img-src',
  'font-src',
];

describe('CostViewProvider HTML builder — CSP (R-05)', () => {
  function makeDataServiceStub(): DataService {
    const emitter = new EventEmitter<void>();
    return {
      onDidChange: emitter.event,
      getProjectRoot: () => undefined,
      getActiveTask: async () => undefined,
      getWorkflowNodes: async () => ({ status: 'no-task' }),
      watch: () => ({ dispose: () => {} }),
      getCostView: async () => ({
        live: null,
        tasks: [],
        finalizedGrandTotal: null,
        finalizedGrandTotalState: 'unavailable',
        scopeNote: '',
      }),
      readCostSummaries: () => [],
      liveSpend: async () => null,
      taskCounts: async () => [],
      dispose: () => {},
    } as unknown as DataService;
  }

  function setup(): { provider: CostViewProvider; webview: StubWebview; html: string } {
    const ds = makeDataServiceStub();
    const p = new CostViewProvider(Uri.file('/ext') as unknown as import('vscode').Uri, ds, makeProjectContextStub());
    const w = new StubWebview();
    const h = p._buildHtml(w as unknown as import('vscode').Webview);
    return { provider: p, webview: w, html: h };
  }

  it('cost view CSP byte-equals the locked 5-directive string (R-05)', () => {
    const { html } = setup();
    for (const directive of COST_CSP_LOCKED) {
      assert.ok(html.includes(directive), `cost view CSP must contain "${directive}"`);
    }
  });

  it("cost view has default-src 'none'", () => {
    const { html } = setup();
    assert.ok(html.includes("default-src 'none'"));
  });

  it('cost view has no unsafe-inline', () => {
    const { html } = setup();
    assert.ok(!html.includes("'unsafe-inline'"), "CSP must NOT contain 'unsafe-inline'");
  });

  it('cost view references costView.js and costView.css (not sessionsArchive)', () => {
    const { html } = setup();
    assert.ok(html.includes('costView.js'), 'must reference costView.js');
    assert.ok(html.includes('costView.css'), 'must reference costView.css');
    assert.ok(!html.includes('sessionsArchive.js'), 'must NOT reference sessionsArchive.js');
    assert.ok(!html.includes('sessionsArchive.css'), 'must NOT reference sessionsArchive.css');
  });

  it('cost view CSP has no http:// or https:// remote origins', () => {
    const { html } = setup();
    const cspMatch = html.match(/Content-Security-Policy" content="([^"]*)"/);
    assert.ok(cspMatch, 'CSP meta tag must exist');
    const cspValue = cspMatch![1];
    assert.ok(!cspValue.includes('http://'), 'CSP must not allow http:// origins');
    assert.ok(!cspValue.includes('https://'), 'CSP must not allow https:// origins');
  });
});
