import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { Runtime } from './types';

const LAST_ROOT_KEY = 'quoin.lastProjectRoot';

async function resolveProjectRoot(context: vscode.ExtensionContext): Promise<string | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length === 1) {
    return folders[0].uri.fsPath;
  }
  if (folders && folders.length > 1) {
    const pick = await vscode.window.showWorkspaceFolderPick({ placeHolder: 'Select Quoin project root' });
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

    vscode.commands.registerCommand('quoin.relaunchSession', async (id: string) => {
      const session = manager.get(id);
      if (!session) return;
      manager.create(session.runtime, session.projectRoot);
    })
  );
}
