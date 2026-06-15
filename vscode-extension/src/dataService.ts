import * as vscode from 'vscode';
import { execFile } from 'node:child_process';
import * as os from 'node:os';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { findArtifactsRoot } from './artifactsRoot';
import { WorkflowNode, PIPELINE, PHASE_TO_NODE } from './workflowMapping';
import {
  LiveSpend,
  CostView,
  SummaryResult,
  parseLiveSpend,
  parseTaskCounts,
  parseCostSummary,
  mergeCostView,
} from './costService';
import { FsLike } from './archiveScanner';

export const WATCH_DEBOUNCE_MS = 500;

export interface DataServiceOptions {
  adapterRoot?: string;
  coreRoot?: string;
  watcherDebounceMs?: number;
}

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

  private readonly _adapterRoot: string;
  private readonly _coreRoot: string;
  private readonly _debounceMs: number;

  constructor(opts: DataServiceOptions = {}) {
    const home = os.homedir();
    this._adapterRoot = opts.adapterRoot ?? path.join(home, '.claude', 'scripts');
    this._coreRoot = opts.coreRoot ?? path.join(home, '.claude', 'core', 'scripts');
    this._debounceMs = opts.watcherDebounceMs ?? WATCH_DEBOUNCE_MS;
  }

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
      }, this._debounceMs);
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
    return findArtifactsRoot(folders[0].uri.fsPath, { existsSync: fs.existsSync });
  }

  /** Dispose the current watcher without starting a new one (used when switching to no-root). */
  unwatch(): void {
    this._watcher?.dispose();
    this._watcher = undefined;
  }

  /** Resolve the path to status_graph.py; prefer core copy over adapter wrapper. */
  private _resolveScriptPath(): string | null {
    const corePath = path.join(this._coreRoot, 'status_graph.py');
    if (fs.existsSync(corePath)) { return corePath; }
    const adapterPath = path.join(this._adapterRoot, 'status_graph.py');
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

  // ── Cost script resolution (mirrors _resolveScriptPath; core-first/adapter-fallback) ──

  /**
   * Resolve the path to a cost-related script by name.
   * Prefers core copy; falls back to adapter wrapper.
   * Both spend_monitor.py and dashboard_model.py are in core; spend_monitor.py
   * also has an adapter wrapper (MIN-1).
   */
  _resolveCostScript(name: string): string | null {
    const corePath = path.join(this._coreRoot, name);
    if (fs.existsSync(corePath)) { return corePath; }
    const adapterPath = path.join(this._adapterRoot, name);
    if (fs.existsSync(adapterPath)) { return adapterPath; }
    return null;
  }

  /**
   * Invoke spend_monitor.py --json --scope project with cwd=projectRoot.
   * D-03: spend_monitor derives root from cwd (no --project-root flag).
   * D-05: --scope project ensures by_task is populated and aligns with today_usd.
   */
  async liveSpend(projectRoot: string): Promise<LiveSpend | null> {
    const scriptPath = this._resolveCostScript('spend_monitor.py');
    if (!scriptPath) { return null; }
    return new Promise((resolve) => {
      execFile(
        'python3',
        [scriptPath, '--json', '--scope', 'project'],
        { cwd: projectRoot, timeout: 8000 },
        (err, stdout, stderr) => {
          resolve(parseLiveSpend(stdout, stderr, err));
        },
      );
    });
  }

  /**
   * Invoke dashboard_model.py --json (counts-mode) with --project-root.
   * D-01: NO --with-cost flag; usd is always null in counts-mode.
   */
  async taskCounts(projectRoot: string): Promise<Array<{ task: string; usd: number | null }>> {
    const scriptPath = this._resolveCostScript('dashboard_model.py');
    if (!scriptPath) { return []; }
    return new Promise((resolve) => {
      execFile(
        'python3',
        [scriptPath, '--json', '--project-root', projectRoot],
        { timeout: 8000 },
        (err, stdout, stderr) => {
          resolve(parseTaskCounts(stdout, stderr, err));
        },
      );
    });
  }

  /**
   * Scan all cost-summary.json files under .workflow_artifacts (top-level and finalized).
   * Uses injectable FsLike seam. Skips unreadable / malformed files silently.
   */
  readCostSummaries(
    projectRoot: string,
    fsImpl: FsLike = {
      existsSync: fs.existsSync,
      readdirSync: (p: string) => fs.readdirSync(p) as string[],
      readFileSync: (p: string, enc: 'utf8') => fs.readFileSync(p, enc),
    },
  ): SummaryResult[] {
    const results: SummaryResult[] = [];
    const artifactsDir = path.join(projectRoot, '.workflow_artifacts');

    if (!fsImpl.existsSync(artifactsDir)) { return results; }

    let topLevelEntries: string[] = [];
    try {
      topLevelEntries = fsImpl.readdirSync(artifactsDir);
    } catch {
      return results;
    }

    // Scan top-level task dirs
    for (const entry of topLevelEntries) {
      if (entry === 'finalized' || entry === 'memory' || entry === 'cache') { continue; }
      const summaryPath = path.join(artifactsDir, entry, 'cost-summary.json');
      if (fsImpl.existsSync(summaryPath)) {
        try {
          const text = fsImpl.readFileSync(summaryPath, 'utf8');
          results.push(parseCostSummary(text, entry));
        } catch {
          // skip unreadable file
        }
      }
    }

    // Scan finalized/*/cost-summary.json
    const finalizedDir = path.join(artifactsDir, 'finalized');
    if (fsImpl.existsSync(finalizedDir)) {
      let finalizedEntries: string[] = [];
      try {
        finalizedEntries = fsImpl.readdirSync(finalizedDir);
      } catch {
        // skip
      }
      for (const entry of finalizedEntries) {
        const summaryPath = path.join(finalizedDir, entry, 'cost-summary.json');
        if (fsImpl.existsSync(summaryPath)) {
          try {
            const text = fsImpl.readFileSync(summaryPath, 'utf8');
            results.push(parseCostSummary(text, entry));
          } catch {
            // skip unreadable file
          }
        }
      }
    }

    return results;
  }

  /**
   * Orchestrate all three cost fetches and return a merged CostView.
   * Safe on no-scripts: returns an empty CostView with live:null and no tasks.
   */
  async getCostView(projectRoot: string): Promise<CostView> {
    const [live, counts, summaries] = await Promise.all([
      this.liveSpend(projectRoot),
      this.taskCounts(projectRoot),
      Promise.resolve(this.readCostSummaries(projectRoot)),
    ]);
    return mergeCostView(live, counts, summaries);
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
