import * as os from 'node:os';
import * as path from 'node:path';
import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { SessionsTreeProvider } from './sessionsTree';
import { registerCommands } from './commands';
import { checkScriptRoots } from './scriptRootCheck';
import { CommandRunner } from './commandRunner';
import { ControlPanelViewProvider } from './controlPanel';
import { DataService, DataServiceOptions } from './dataService';
import { WorkflowTreeViewProvider } from './workflowTree';
import { SessionsArchiveViewProvider } from './sessionsArchive';
import { CostViewProvider } from './costView';

function expandTilde(p: string): string {
  if (p.startsWith('~/') || p === '~') {
    return path.join(os.homedir(), p.slice(2));
  }
  return p;
}

function readQuoinSettings(): DataServiceOptions & { projectRoot: string } {
  const cfg = vscode.workspace.getConfiguration('quoin');
  const scriptRoots = cfg.get<{ adapter?: string; core?: string }>('scriptRoots') ?? {};
  return {
    adapterRoot: expandTilde(scriptRoots.adapter ?? '~/.claude/scripts'),
    coreRoot: expandTilde(scriptRoots.core ?? '~/.claude/core/scripts'),
    watcherDebounceMs: cfg.get<number>('watcherDebounceMs') ?? 500,
    projectRoot: cfg.get<string>('projectRoot') ?? '',
  };
}

export function activate(context: vscode.ExtensionContext): void {
  // T-05 activation ordering: commands BEFORE TreeDataProvider so the viewsWelcome
  // button (quoin.newSession) is functional when the view is first revealed.
  const manager = new SessionManager(context, vscode.window.onDidCloseTerminal);

  // Register commands first (T-05 ordering requirement from plan)
  registerCommands(context, manager);

  // Register the Sessions tree view (T-06)
  const treeProvider = new SessionsTreeProvider(manager);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('quoin.sessions', treeProvider)
  );

  // Register the Control Panel webview view (S-2)
  const commandRunner = new CommandRunner();
  const controlPanelProvider = new ControlPanelViewProvider(
    context.extensionUri,
    manager,
    commandRunner
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.controlPanel', controlPanelProvider)
  );

  // Register the Workflow Tree webview view (S-3)
  const settings = readQuoinSettings();
  const dataService = new DataService({
    adapterRoot: settings.adapterRoot,
    coreRoot: settings.coreRoot,
    watcherDebounceMs: settings.watcherDebounceMs,
  });
  const workflowProvider = new WorkflowTreeViewProvider(
    context.extensionUri,
    dataService,
    manager,
    controlPanelProvider,
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.workflowTree', workflowProvider)
  );
  context.subscriptions.push(dataService);

  // Register the Sessions Archive webview view (S-4)
  // Reuses the same dataService instance (shared watcher + onDidChange emitter; see S4-3).
  const archiveProvider = new SessionsArchiveViewProvider(
    context.extensionUri, manager, dataService,
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.sessionsArchive', archiveProvider)
  );

  // Register the Cost webview view (S-5)
  // Reuses the SAME dataService instance (shared watcher + onDidChange emitter).
  const costProvider = new CostViewProvider(context.extensionUri, dataService);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.cost', costProvider)
  );

  // Load persisted sessions from prior window (T-04 reload behavior).
  // Collect roots from workspace folders (common case) plus the stored fallback
  // for no-workspace scenarios, then dedup and load each.
  const rootsToLoad = new Set<string>();
  vscode.workspace.workspaceFolders?.forEach(f => rootsToLoad.add(f.uri.fsPath));
  const lastRoot = context.globalState.get<string>('quoin.lastProjectRoot');
  if (lastRoot) {
    rootsToLoad.add(lastRoot);
  }
  for (const root of rootsToLoad) {
    manager.loadPersisted(root);
  }

  context.subscriptions.push({ dispose: () => manager.dispose() });

  // T-03: activation-time script-root check (non-fatal)
  void checkScriptRoots();
}

export function deactivate(): void {
  // Cleanup handled via context.subscriptions
}
