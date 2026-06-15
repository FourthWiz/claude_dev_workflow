import * as vscode from 'vscode';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { SessionManager } from './sessionManager';
import { ProjectContext } from './projectContext';
import { Runtime } from './types';
import { findArtifactsRoot } from './artifactsRoot';

const LAST_ROOT_KEY = 'quoin.lastProjectRoot';

async function resolveProjectRoot(context: vscode.ExtensionContext): Promise<string | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (folders && folders.length === 1) {
    // CRIT-1 fix: walk up to the artifacts root so session.projectRoot is always
    // the .workflow_artifacts/ ancestor, never the raw workspace folder path.
    const root = findArtifactsRoot(folders[0].uri.fsPath, { existsSync: fs.existsSync })
      ?? folders[0].uri.fsPath;
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

export function registerStatusBar(
  context: vscode.ExtensionContext,
  projectContext: ProjectContext,
): vscode.StatusBarItem {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  item.command = 'quoin.switchProject';
  item.tooltip = 'Switch Quoin project root';

  function update(root: string | undefined): void {
    if (root) {
      item.text = `$(folder) ${path.basename(root)}`;
      item.show();
    } else {
      item.text = '$(folder) Quoin';
      item.show();
    }
  }

  update(projectContext.getActiveRoot());
  context.subscriptions.push(
    projectContext.onDidChangeActiveRoot((root) => update(root)),
  );
  context.subscriptions.push(item);
  return item;
}

export function registerCommands(
  context: vscode.ExtensionContext,
  manager: SessionManager,
  projectContext?: ProjectContext,
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
    }),

    // quoin.switchProject: QuickPick project-switcher (T-09)
    vscode.commands.registerCommand('quoin.switchProject', async () => {
      if (!projectContext) { return; }

      // Check if already on a known root — avoid double-prompt if only one root
      const known = projectContext.listKnownRoots();
      if (known.length === 0) {
        void vscode.window.showInformationMessage('Quoin: No known project roots yet. Open a workspace folder containing .workflow_artifacts/.');
        return;
      }

      const picks = known.map((r) => ({
        label: path.basename(r),
        detail: r,
      }));

      const selected = await vscode.window.showQuickPick(picks, {
        placeHolder: 'Select Quoin project root',
        matchOnDetail: true,
      });

      if (selected?.detail) {
        await projectContext.setActiveRoot(selected.detail);
      }
    }),
  );
}
