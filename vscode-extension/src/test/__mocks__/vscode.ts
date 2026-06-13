/** Minimal vscode stub for node:test runner (no Electron host required). */

export class EventEmitter<T> {
  private handlers: Array<(e: T) => void> = [];
  readonly event = (handler: (e: T) => void) => {
    this.handlers.push(handler);
    return { dispose: () => { this.handlers = this.handlers.filter((h) => h !== handler); } };
  };
  fire(e: T): void { this.handlers.forEach((h) => h(e)); }
  dispose(): void { this.handlers = []; }
}

export class ThemeIcon {
  constructor(public readonly id: string) {}
}

export enum TreeItemCollapsibleState { None = 0, Collapsed = 1, Expanded = 2 }

export class TreeItem {
  label?: string;
  description?: string;
  tooltip?: string;
  iconPath?: ThemeIcon;
  command?: unknown;
  collapsibleState?: TreeItemCollapsibleState;
  constructor(label: string, collapsibleState?: TreeItemCollapsibleState) {
    this.label = label;
    this.collapsibleState = collapsibleState;
  }
}

export const window = {
  createTerminal: (_opts: unknown) => ({ name: 'stub', show: () => {}, sendText: () => {}, dispose: () => {} }),
  onDidCloseTerminal: (_h: unknown) => ({ dispose: () => {} }),
  showErrorMessage: async (_msg: string, ..._items: string[]) => undefined as string | undefined,
  showInformationMessage: async (_msg: string) => undefined,
  createOutputChannel: (_name: string) => ({ appendLine: () => {}, show: () => {} }),
};

export const commands = {
  executeCommand: async (_cmd: string, ..._args: unknown[]) => undefined,
  registerCommand: (_cmd: string, _handler: (...args: unknown[]) => unknown) => ({ dispose: () => {} }),
};

export const workspace = {
  workspaceFolders: undefined as undefined,
};
