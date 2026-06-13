import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { QuoinSession } from './types';

export class SessionsTreeProvider implements vscode.TreeDataProvider<QuoinSession> {
  private _onDidChangeTreeData = new vscode.EventEmitter<QuoinSession | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly manager: SessionManager) {
    manager.onDidChange(() => this._onDidChangeTreeData.fire());
  }

  getTreeItem(session: QuoinSession): vscode.TreeItem {
    const item = new vscode.TreeItem(session.label, vscode.TreeItemCollapsibleState.None);
    item.description = session.runtime;
    item.tooltip = `${session.runtime} · ${session.projectRoot}`;

    if (session.relaunchable || !session.terminal) {
      item.iconPath = new vscode.ThemeIcon('debug-disconnect');
      item.description += '  (relaunchable)';
      item.command = {
        command: 'quoin.relaunchSession',
        title: 'Relaunch',
        arguments: [session.id],
      };
    } else {
      item.iconPath = new vscode.ThemeIcon('terminal');
      item.command = {
        command: 'quoin.revealSession',
        title: 'Reveal Terminal',
        arguments: [session.id],
      };
    }

    return item;
  }

  getChildren(): QuoinSession[] {
    return this.manager.getAll();
  }
}
