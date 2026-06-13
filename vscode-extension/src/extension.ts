import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { SessionsTreeProvider } from './sessionsTree';
import { registerCommands } from './commands';
import { checkScriptRoots } from './scriptRootCheck';

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

  // Load any persisted sessions from a prior window (T-04 reload behavior)
  // We don't know projectRoot until the user opens a session, but we can
  // attempt to load from the last known root stored in globalState.
  const lastRoot = context.globalState.get<string>('quoin.lastProjectRoot');
  if (lastRoot) {
    manager.loadPersisted(lastRoot);
  }

  context.subscriptions.push({ dispose: () => manager.dispose() });

  // T-03: activation-time script-root check (non-fatal)
  void checkScriptRoots();
}

export function deactivate(): void {
  // Cleanup handled via context.subscriptions
}
