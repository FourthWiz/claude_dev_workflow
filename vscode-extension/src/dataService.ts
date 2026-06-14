import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { WorkflowNode, PIPELINE, PHASE_TO_NODE } from './workflowMapping';

export const WATCH_DEBOUNCE_MS = 500;

export interface DataResult {
  status: 'ok' | 'no-task' | 'no-scripts' | 'error';
  nodes?: WorkflowNode[];
  task?: string;
  stage?: string | null;
  message?: string;
}

/**
 * Pure function — classifies stdout/stderr/exitErr from a --emit-nodes invocation.
 * Exported for unit testing without a live Python process.
 */
export function parseNodesPayload(
  stdout: string,
  stderr: string,
  exitErr: Error | null,
): DataResult {
  const noScriptsPattern = /ModuleNotFoundError|FileNotFoundError|ImportError|No module named/i;
  if (noScriptsPattern.test(stderr)) {
    return { status: 'no-scripts', message: stderr.trim() };
  }

  if (exitErr && !stdout.trim()) {
    return { status: 'error', message: stderr.trim() || exitErr.message };
  }

  const trimmed = stdout.trim();
  if (
    trimmed === '' ||
    trimmed.startsWith('No active task found')
  ) {
    return { status: 'no-task' };
  }

  let data: Record<string, unknown>;
  try {
    data = JSON.parse(trimmed) as Record<string, unknown>;
  } catch {
    return { status: 'error', message: `JSON parse error: ${trimmed.slice(0, 120)}` };
  }

  const task = typeof data['task'] === 'string' ? data['task'] : undefined;
  const stage = data['stage'] != null ? String(data['stage']) : null;

  if (!Array.isArray(data['nodes'])) {
    // --emit-nodes flag not recognised by older script — build fallback from phase
    const phase = typeof data['phase'] === 'string' ? data['phase'] : 'discover';
    const activeNode = PHASE_TO_NODE[phase] ?? 'discover';
    const activeIdx = PIPELINE.indexOf(activeNode);
    const nodes: WorkflowNode[] = PIPELINE.map((node, i) => ({
      node,
      state: i < activeIdx ? 'done' : i === activeIdx ? 'active' : 'future',
    }));
    return { status: 'ok', nodes, task, stage };
  }

  return { status: 'ok', nodes: data['nodes'] as WorkflowNode[], task, stage };
}

export class DataService implements vscode.Disposable {
  private readonly _onDidChange = new vscode.EventEmitter<void>();
  readonly onDidChange = this._onDidChange.event;

  private _watcher: vscode.FileSystemWatcher | undefined;
  private _debounceTimer: ReturnType<typeof setTimeout> | undefined;

  dispose(): void {
    this._watcher?.dispose();
    this._watcher = undefined;
    if (this._debounceTimer !== undefined) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = undefined;
    }
    this._onDidChange.dispose();
  }

  /** Install (or re-install) a watcher on .workflow_artifacts/** under projectRoot. */
  watch(projectRoot: string): vscode.Disposable {
    this._watcher?.dispose();
    this._watcher = undefined;

    const pattern = new vscode.RelativePattern(projectRoot, '.workflow_artifacts/**');
    const watcher = vscode.workspace.createFileSystemWatcher(pattern);
    this._watcher = watcher;

    const fire = (): void => {
      if (this._debounceTimer !== undefined) {
        clearTimeout(this._debounceTimer);
      }
      this._debounceTimer = setTimeout(() => {
        this._debounceTimer = undefined;
        this._onDidChange.fire();
      }, WATCH_DEBOUNCE_MS);
    };

    watcher.onDidCreate(fire);
    watcher.onDidChange(fire);
    watcher.onDidDelete(fire);

    return watcher;
  }

  /** Walk up from the first workspace folder (or provided list) to find .workflow_artifacts/ */
  getProjectRoot(
    folders: readonly { uri: { fsPath: string } }[] | undefined,
  ): string | undefined {
    if (!folders || folders.length === 0) { return undefined; }
    let dir = folders[0].uri.fsPath;
    for (let i = 0; i < 20; i++) {
      if (fs.existsSync(path.join(dir, '.workflow_artifacts'))) {
        return dir;
      }
      const parent = path.dirname(dir);
      if (parent === dir) { break; }
      dir = parent;
    }
    return undefined;
  }

  /** Resolve the path to status_graph.py; prefer core copy over adapter wrapper. */
  private _resolveScriptPath(): string | null {
    const home = process.env['HOME'] ?? '';
    const corePath = path.join(home, '.claude', 'core', 'scripts', 'status_graph.py');
    if (fs.existsSync(corePath)) { return corePath; }
    const adapterPath = path.join(home, '.claude', 'scripts', 'status_graph.py');
    if (fs.existsSync(adapterPath)) { return adapterPath; }
    return null;
  }

  /** Run status_graph.py --json and return the active task name, or undefined. */
  async getActiveTask(projectRoot: string): Promise<string | undefined> {
    const scriptPath = this._resolveScriptPath();
    if (!scriptPath) { return undefined; }

    return new Promise((resolve) => {
      execFile(
        'python3',
        [scriptPath, '--json', '--project-root', projectRoot],
        { timeout: 8000 },
        (_err, stdout, _stderr) => {
          const trimmed = stdout.trim();
          if (!trimmed || trimmed.startsWith('No active task found')) {
            resolve(undefined);
            return;
          }
          try {
            const data = JSON.parse(trimmed) as Record<string, unknown>;
            resolve(typeof data['task'] === 'string' ? data['task'] : undefined);
          } catch {
            resolve(undefined);
          }
        },
      );
    });
  }

  /**
   * Fetch pipeline nodes for the given task.
   * Falls back gracefully when the script is absent or lacks --emit-nodes.
   */
  async getWorkflowNodes(
    task: string,
    projectRoot: string,
    stage?: string,
  ): Promise<DataResult> {
    const scriptPath = this._resolveScriptPath();
    if (!scriptPath) {
      return { status: 'no-scripts', message: 'status_graph.py not found' };
    }

    const baseArgs = ['--emit-nodes', '--json', '--project-root', projectRoot, '--task', task];
    if (stage) { baseArgs.push('--stage', stage); }

    return new Promise((resolve) => {
      execFile(
        'python3',
        [scriptPath, ...baseArgs],
        { timeout: 8000 },
        (err, stdout, stderr) => {
          // Unrecognised flag → older script; retry without --emit-nodes
          if (/unrecognized arguments|--emit-nodes/.test(stderr)) {
            const fallbackArgs = baseArgs.filter((a) => a !== '--emit-nodes');
            execFile(
              'python3',
              [scriptPath, ...fallbackArgs],
              { timeout: 8000 },
              (err2, stdout2, stderr2) => {
                resolve(parseNodesPayload(stdout2, stderr2, err2));
              },
            );
            return;
          }
          resolve(parseNodesPayload(stdout, stderr, err));
        },
      );
    });
  }
}
