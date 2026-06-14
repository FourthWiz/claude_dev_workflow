import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { parseNodesPayload, DataService, WATCH_DEBOUNCE_MS } from '../dataService';
import { workspace } from './__mocks__/vscode';

// ---------------------------------------------------------------------------
// parseNodesPayload — pure function tests (no live Python)
// ---------------------------------------------------------------------------

describe('parseNodesPayload', () => {
  it('no-task when stdout is empty', () => {
    const r = parseNodesPayload('', '', null);
    assert.strictEqual(r.status, 'no-task');
  });

  it('no-task when stdout is "No active task found…"', () => {
    const r = parseNodesPayload('No active task found under .workflow_artifacts/', '', null);
    assert.strictEqual(r.status, 'no-task');
  });

  it('no-scripts on ModuleNotFoundError in stderr', () => {
    const r = parseNodesPayload('', 'ModuleNotFoundError: No module named quoin', null);
    assert.strictEqual(r.status, 'no-scripts');
  });

  it('no-scripts on FileNotFoundError in stderr', () => {
    const r = parseNodesPayload('', 'FileNotFoundError: /some/path', null);
    assert.strictEqual(r.status, 'no-scripts');
  });

  it('no-scripts on ImportError in stderr', () => {
    const r = parseNodesPayload('', 'ImportError: cannot import', null);
    assert.strictEqual(r.status, 'no-scripts');
  });

  it('error on exit error with no stdout', () => {
    const err = new Error('exit code 1');
    const r = parseNodesPayload('', 'some stderr', err);
    assert.strictEqual(r.status, 'error');
  });

  it('ok with nodes array when present', () => {
    const nodes = [
      { node: 'discover', state: 'done' },
      { node: 'architect', state: 'active' },
    ];
    const stdout = JSON.stringify({ task: 'my-task', phase: 'architecture', critic_rounds: 0, review_rounds: 0, stage: null, task_dir: '/x', nodes });
    const r = parseNodesPayload(stdout, '', null);
    assert.strictEqual(r.status, 'ok');
    assert.deepStrictEqual(r.nodes, nodes);
    assert.strictEqual(r.task, 'my-task');
  });

  it('ok with fallback nodes when nodes key missing (older script)', () => {
    const stdout = JSON.stringify({ task: 'my-task', phase: 'planning', critic_rounds: 0, review_rounds: 0, stage: null, task_dir: '/x' });
    const r = parseNodesPayload(stdout, '', null);
    assert.strictEqual(r.status, 'ok');
    assert.ok(Array.isArray(r.nodes));
    assert.strictEqual(r.nodes!.length, 6);
    const active = r.nodes!.find((n) => n.state === 'active');
    assert.strictEqual(active?.node, 'thorough_plan');
  });

  it('error on invalid JSON', () => {
    const r = parseNodesPayload('not-json', '', null);
    assert.strictEqual(r.status, 'error');
  });
});

// ---------------------------------------------------------------------------
// DataService.getProjectRoot — unit test (no filesystem, just undefined)
// ---------------------------------------------------------------------------

describe('DataService.getProjectRoot', () => {
  it('returns undefined when folders is undefined', () => {
    const svc = new DataService();
    const root = svc.getProjectRoot(undefined);
    assert.strictEqual(root, undefined);
    svc.dispose();
  });

  it('returns undefined when folders is empty', () => {
    const svc = new DataService();
    const root = svc.getProjectRoot([]);
    assert.strictEqual(root, undefined);
    svc.dispose();
  });
});

// ---------------------------------------------------------------------------
// WATCH_DEBOUNCE_MS — exported constant
// ---------------------------------------------------------------------------

describe('WATCH_DEBOUNCE_MS', () => {
  it('is 500', () => {
    assert.strictEqual(WATCH_DEBOUNCE_MS, 500);
  });
});

// ---------------------------------------------------------------------------
// DataService.watch — debounce: 5 fires → 1 emit after WATCH_DEBOUNCE_MS
// ---------------------------------------------------------------------------

describe('DataService watch debounce', () => {
  it('5 rapid fires produce exactly 1 onDidChange emission after debounce', async () => {
    const svc = new DataService();
    let emitCount = 0;
    svc.onDidChange(() => { emitCount++; });

    // Install the watcher (uses mock createFileSystemWatcher)
    const dir = '/tmp/fake-project';
    svc.watch(dir);

    const emitters = workspace._lastWatcherEmitters;
    assert.ok(emitters, 'watcher emitters should be set after watch()');

    // Fire 5 events rapidly
    emitters!.create.fire();
    emitters!.change.fire();
    emitters!.change.fire();
    emitters!.delete.fire();
    emitters!.create.fire();

    // Before debounce settles: no emit yet
    assert.strictEqual(emitCount, 0);

    // Wait for debounce to settle
    await new Promise((resolve) => setTimeout(resolve, WATCH_DEBOUNCE_MS + 50));

    assert.strictEqual(emitCount, 1, 'expected exactly 1 emit after debounce');

    svc.dispose();
  });
});
