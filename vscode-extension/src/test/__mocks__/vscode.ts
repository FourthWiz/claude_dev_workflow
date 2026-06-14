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

// ── Uri stub (needed by ControlPanelViewProvider) ──────────────────────────

export class Uri {
  readonly fsPath: string;
  readonly scheme: string;
  readonly path: string;
  readonly authority: string = '';
  readonly query: string = '';
  readonly fragment: string = '';

  private constructor(fsPath: string, scheme = 'file') {
    this.fsPath = fsPath;
    this.path = fsPath;
    this.scheme = scheme;
  }

  static file(path: string): Uri {
    return new Uri(path, 'file');
  }

  static joinPath(base: Uri, ...segments: string[]): Uri {
    const joined = [base.fsPath, ...segments].join('/');
    return new Uri(joined, base.scheme);
  }

  with(_change: { scheme?: string; authority?: string; path?: string; query?: string; fragment?: string }): Uri {
    return new Uri(this.fsPath, this.scheme);
  }

  toJSON(): object {
    return { scheme: this.scheme, path: this.path, fsPath: this.fsPath };
  }

  toString(): string {
    return `${this.scheme}:${this.path}`;
  }
}

// ── Clipboard stub ─────────────────────────────────────────────────────────

let _clipboardContent = '';
export const clipboardSpy = {
  get lastWritten() { return _clipboardContent; },
  reset() { _clipboardContent = ''; },
};

// ── Window + env stubs ─────────────────────────────────────────────────────

export const window = {
  createTerminal: (_opts: unknown) => ({ name: 'stub', show: () => {}, sendText: () => {}, dispose: () => {} }),
  onDidCloseTerminal: (_h: unknown) => ({ dispose: () => {} }),
  showErrorMessage: async (_msg: string, ..._items: string[]) => undefined as string | undefined,
  showInformationMessage: async (_msg: string) => undefined,
  createOutputChannel: (_name: string) => ({ appendLine: () => {}, show: () => {} }),
  registerWebviewViewProvider: (_id: string, _provider: unknown) => ({ dispose: () => {} }),
};

export const env = {
  clipboard: {
    writeText: async (text: string): Promise<void> => {
      _clipboardContent = text;
    },
    readText: async (): Promise<string> => _clipboardContent,
  },
};

export const commands = {
  executeCommand: async (_cmd: string, ..._args: unknown[]) => undefined,
  registerCommand: (_cmd: string, _handler: (...args: unknown[]) => unknown) => ({ dispose: () => {} }),
};

export const workspace = {
  workspaceFolders: undefined as undefined,
};

// ── Webview stub (minimal surface for ControlPanelViewProvider) ────────────

export class StubWebview {
  html = '';
  options: unknown = {};
  cspSource = 'vscode-resource:';
  private messageHandlers: Array<(msg: unknown) => void> = [];
  private postedMessages: unknown[] = [];

  asWebviewUri(uri: Uri): Uri {
    return Uri.file('webview://' + uri.fsPath);
  }

  onDidReceiveMessage(handler: (msg: unknown) => void): { dispose(): void } {
    this.messageHandlers.push(handler);
    return { dispose: () => { this.messageHandlers = this.messageHandlers.filter(h => h !== handler); } };
  }

  postMessage(msg: unknown): Thenable<boolean> {
    this.postedMessages.push(msg);
    return Promise.resolve(true);
  }

  /** Simulate a message arriving FROM the webview */
  simulateMessage(msg: unknown): void {
    this.messageHandlers.forEach(h => h(msg));
  }

  getPostedMessages(): unknown[] {
    return [...this.postedMessages];
  }

  clearPostedMessages(): void {
    this.postedMessages = [];
  }
}

/** Build a minimal WebviewView stub that delegates to a StubWebview */
export function makeStubWebviewView(): { view: { webview: StubWebview; visible: boolean; onDidDispose: (h: () => void) => { dispose(): void } }; webview: StubWebview } {
  const webview = new StubWebview();
  const view = {
    webview,
    visible: true,
    onDidDispose: (_h: () => void) => ({ dispose: () => {} }),
  };
  return { view, webview };
}
