import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { WorkflowTreeViewProvider } from '../workflowTree';
import { DataService, DataResult } from '../dataService';
import { Uri, EventEmitter, makeStubWebviewView } from './__mocks__/vscode';
import type { ProjectContext } from '../projectContext';

// ---------------------------------------------------------------------------
// Stubs
// ---------------------------------------------------------------------------

function makeDataServiceStub(overrides: Partial<DataService> = {}): DataService {
  const onDidChangeEmitter = new EventEmitter<void>();
  return {
    onDidChange: onDidChangeEmitter.event,
    _emitter: onDidChangeEmitter,
    getProjectRoot: (_folders: unknown) => '/fake/root',
    getActiveTask: async (_root: string) => 'my-task',
    getWorkflowNodes: async (_task: string, _root: string): Promise<DataResult> => ({
      status: 'ok',
      nodes: [
        { node: 'discover', state: 'done' },
        { node: 'architect', state: 'done' },
        { node: 'thorough_plan', state: 'active' },
        { node: 'implement', state: 'future' },
        { node: 'review', state: 'future' },
        { node: 'end_of_task', state: 'future' },
      ],
      task: 'my-task',
      stage: null,
    }),
    watch: (_root: string) => ({ dispose: () => {} }),
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
    _emitter: emitter,
  } as unknown as ProjectContext;
}

function makeControlPanelStub(): { highlighted: (string | null)[]; postHighlight(n: string | null): void } {
  const highlighted: (string | null)[] = [];
  return {
    highlighted,
    postHighlight(n: string | null) { highlighted.push(n); },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkflowTreeViewProvider', () => {
  it('posts a render message on resolveWebviewView', async () => {
    const ds = makeDataServiceStub();
const cp = makeControlPanelStub();
    const { view, webview } = makeStubWebviewView();

    const provider = new WorkflowTreeViewProvider(
      Uri.file('/ext'),
      ds,
      makeProjectContextStub('/fake/root'),
      cp,
    );

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    // Let the async _refresh settle
    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; status?: string; nodes?: unknown[] }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render, 'expected a render message');
    assert.strictEqual(render!.status, 'ok');
    assert.ok(Array.isArray(render!.nodes));
    assert.strictEqual(render!.nodes!.length, 6);
  });

  it('posts highlight with next skill after render', async () => {
    const ds = makeDataServiceStub();
const cp = makeControlPanelStub();
    const { view } = makeStubWebviewView();

    const provider = new WorkflowTreeViewProvider(
      Uri.file('/ext'),
      ds,
      makeProjectContextStub('/fake/root'),
      cp,
    );

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    // thorough_plan is active → next skill is implement
    assert.ok(cp.highlighted.includes('implement'), `expected 'implement' in ${JSON.stringify(cp.highlighted)}`);
  });

  it('posts no-task when getActiveTask returns undefined', async () => {
    const ds = makeDataServiceStub({
      getActiveTask: async () => undefined,
    } as Partial<DataService>);
const cp = makeControlPanelStub();
    const { view, webview } = makeStubWebviewView();

    const provider = new WorkflowTreeViewProvider(
      Uri.file('/ext'),
      ds,
      makeProjectContextStub('/fake/root'),
      cp,
    );

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));

    const messages = webview.getPostedMessages() as Array<{ cmd: string; status?: string }>;
    const render = messages.find((m) => m.cmd === 'render');
    assert.ok(render);
    assert.strictEqual(render!.status, 'no-task');
  });

  it('triggers _refresh when dataService.onDidChange fires', async () => {
    const onDidChangeEmitter = new EventEmitter<void>();
    let refreshCount = 0;
    const ds = makeDataServiceStub({
      onDidChange: onDidChangeEmitter.event,
      getWorkflowNodes: async () => {
        refreshCount++;
        return { status: 'no-task' };
      },
    } as Partial<DataService>);
    const cp = makeControlPanelStub();
    const { view } = makeStubWebviewView();

    const provider = new WorkflowTreeViewProvider(
      Uri.file('/ext'),
      ds,
      makeProjectContextStub('/fake/root'),
      cp,
    );

    provider.resolveWebviewView(
      view as unknown as import('vscode').WebviewView,
      {} as import('vscode').WebviewViewResolveContext,
      { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) } as unknown as import('vscode').CancellationToken,
    );

    await new Promise((r) => setTimeout(r, 20));
    const initialCount = refreshCount;

    // Fire a change event
    onDidChangeEmitter.fire();
    await new Promise((r) => setTimeout(r, 20));

    assert.ok(refreshCount > initialCount, 'expected another refresh after onDidChange');
  });
});
