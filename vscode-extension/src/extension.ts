import * as os from 'node:os';
import * as path from 'node:path';
import * as fs from 'node:fs';
import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { SessionsTreeProvider } from './sessionsTree';
import { registerCommands, registerStatusBar } from './commands';
import { checkScriptRoots } from './scriptRootCheck';
import { CommandRunner } from './commandRunner';
import { ControlPanelViewProvider } from './controlPanel';
import { DataService, DataServiceOptions } from './dataService';
import { WorkflowTreeViewProvider } from './workflowTree';
import { SessionsArchiveViewProvider } from './sessionsArchive';
import { CostViewProvider } from './costView';
import { ProjectContext } from './projectContext';
import { findArtifactsRoot } from './artifactsRoot';

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

  // ProjectContext — single source of truth for the active project root (T-11 D-01)
  const projectContext = new ProjectContext(context);

  // Register commands first (T-05 ordering requirement from plan)
  registerCommands(context, manager, projectContext);

  // Status bar indicator + project switcher (T-09)
  registerStatusBar(context, projectContext);

  // Register the Sessions tree view — scoped to active project root (T-03)
  const treeProvider = new SessionsTreeProvider(manager, projectContext);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('quoin.sessions', treeProvider)
  );

  // Register the Control Panel webview view — session list scoped to active root (T-04)
  const commandRunner = new CommandRunner();
  const controlPanelProvider = new ControlPanelViewProvider(
    context.extensionUri,
    manager,
    projectContext,
    commandRunner
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.controlPanel', controlPanelProvider)
  );

  // Register the Workflow Tree webview view — uses ProjectContext for root (T-05)
  const settings = readQuoinSettings();
  const dataService = new DataService({
    adapterRoot: settings.adapterRoot,
    coreRoot: settings.coreRoot,
    watcherDebounceMs: settings.watcherDebounceMs,
  });
  const workflowProvider = new WorkflowTreeViewProvider(
    context.extensionUri,
    dataService,
    projectContext,
    controlPanelProvider,
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.workflowTree', workflowProvider)
  );
  context.subscriptions.push(dataService);

  // Register the Sessions Archive webview view — scoped to active root (T-06)
  const archiveProvider = new SessionsArchiveViewProvider(
    context.extensionUri, manager, projectContext, dataService,
  );
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.sessionsArchive', archiveProvider)
  );

  // Register the Cost webview view — scoped to active root (T-07)
  const costProvider = new CostViewProvider(context.extensionUri, dataService, projectContext);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('quoin.cost', costProvider)
  );

  // Central watcher (T-11 D-06): owned here; per-view self-watches removed.
  // Start watching the active root; update on project switches.
  const activeRoot = projectContext.getActiveRoot();
  if (activeRoot) {
    context.subscriptions.push(dataService.watch(activeRoot));
  }
  context.subscriptions.push(
    projectContext.onDidChangeActiveRoot((newRoot) => {
      if (newRoot) {
        context.subscriptions.push(dataService.watch(newRoot));
      } else {
        dataService.unwatch();
      }
    })
  );

  // Load persisted sessions from prior window (MAJ-1 fix: canonicalize via findArtifactsRoot
  // so reload keys match creation keys for nested-folder workspaces).
  const rootsToLoad = new Set<string>();
  vscode.workspace.workspaceFolders?.forEach(f => {
    const canonicalRoot = findArtifactsRoot(f.uri.fsPath, { existsSync: fs.existsSync });
    rootsToLoad.add(canonicalRoot ?? f.uri.fsPath);
  });
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
