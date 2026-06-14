import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { Runtime } from './types';

const LAST_ROOT_KEY = 'quoin.lastProjectRoot';

async function resolveProjectRoot(context: vscode.ExtensionContext): Promise<string | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length === 1) {
    const root = folders[0].uri.fsPath;
    await context.globalState.update(LAST_ROOT_KEY, root);
    return root;
  }
  if (folders && folders.length > 1) {
    const pick = await vscode.window.showWorkspaceFolderPick({ placeHolder: 'Select Quoin project root' });
    if (pick) {
      await context.globalState.update(LAST_ROOT_KEY, pick.uri.fsPath);
    }
    return pick?.uri.fsPath;
  }
  // No workspace — prompt with persisted default
  const last = context.globalState.get<string>(LAST_ROOT_KEY);
  const picked = await vscode.window.showInputBox({
    value: last ?? process.cwd(),
    prompt: 'Quoin project root (full path)',
  });
  if (picked) {
    await context.globalState.update(LAST_ROOT_KEY, picked);
  }
  return picked;
}

export function registerCommands(
  context: vscode.ExtensionContext,
  manager: SessionManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand('quoin.newSession', async () => {
      const runtimeLabel = await vscode.window.showQuickPick(['Claude', 'Codex'], {
        placeHolder: 'Select runtime',
      });
      if (!runtimeLabel) return;

      const runtime: Runtime = runtimeLabel.toLowerCase() as Runtime;
      const root = await resolveProjectRoot(context);
      if (!root) return;

      manager.create(runtime, root);
    }),

    vscode.commands.registerCommand('quoin.revealSession', (id: string) => {
      const session = manager.get(id);
      session?.terminal?.show();
    }),

    vscode.commands.registerCommand('quoin.relaunchSession', (id: string) => {
      manager.relaunch(id);
    }),

    // quoin.openArchivedSession: opens an archived .md file in an editor tab.
    // The active-row click path reuses the existing quoin.revealSession command.
    // Note (D-02): the archive view's active-row click maps to revealSession (live terminal)
    // and does NOT relaunch; relaunch remains available from the S-1 quoin.sessions tree.
    vscode.commands.registerCommand('quoin.openArchivedSession', async (filePath: string) => {
      if (typeof filePath !== 'string' || !filePath) { return; }
      try {
        const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
        await vscode.window.showTextDocument(doc, { preview: true });
      } catch {
        void vscode.window.showErrorMessage(`Quoin: could not open session file: ${filePath}`);
      }
    })
  );
}
