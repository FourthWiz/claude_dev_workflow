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

// ── executeCommand spy (mirrors clipboardSpy pattern) ─────────────────────
// Module-level recorder; tests call executeCommandSpy.reset() at the start of
// each test that checks executeCommand. Do NOT do per-test reassignment of
// commands.executeCommand on the singleton — that risks global-state bleed.

const _executedCommands: Array<{ cmd: string; args: unknown[] }> = [];
export const executeCommandSpy = {
  get calls() { return [..._executedCommands]; },
  reset() { _executedCommands.length = 0; },
};

// ── StatusBar stubs ────────────────────────────────────────────────────────

export enum StatusBarAlignment { Left = 1, Right = 2 }

export class StatusBarItemStub {
  text = '';
  tooltip = '';
  command: string | undefined = undefined;
  show(): void {}
  dispose(): void {}
}

let _lastStatusBarItem: StatusBarItemStub | undefined;
export function _getLastStatusBarItem(): StatusBarItemStub | undefined { return _lastStatusBarItem; }

// ── showQuickPick spy ──────────────────────────────────────────────────────

const _quickPickCalls: Array<unknown[]> = [];
let _quickPickReturn: unknown = undefined;
export const showQuickPickSpy = {
  get calls() { return [..._quickPickCalls]; },
  reset() { _quickPickCalls.length = 0; _quickPickReturn = undefined; },
};
export function _setShowQuickPickReturn(val: unknown): void { _quickPickReturn = val; }

// ── Window + env stubs ─────────────────────────────────────────────────────

export const window = {
  createTerminal: (_opts: unknown) => ({ name: 'stub', show: () => {}, sendText: () => {}, dispose: () => {} }),
  onDidCloseTerminal: (_h: unknown) => ({ dispose: () => {} }),
  showErrorMessage: async (_msg: string, ..._items: string[]) => undefined as string | undefined,
  showInformationMessage: async (_msg: string) => undefined,
  showTextDocument: async (_doc: unknown, _opts?: unknown) => undefined,
  createOutputChannel: (_name: string) => ({ appendLine: () => {}, show: () => {} }),
  registerWebviewViewProvider: (_id: string, _provider: unknown) => ({ dispose: () => {} }),
  createStatusBarItem: (_alignment?: StatusBarAlignment, _priority?: number): StatusBarItemStub => {
    _lastStatusBarItem = new StatusBarItemStub();
    return _lastStatusBarItem;
  },
  showQuickPick: async (items: unknown, _opts?: unknown): Promise<unknown> => {
    _quickPickCalls.push([items, _opts]);
    return _quickPickReturn;
  },
  showWorkspaceFolderPick: async (_opts?: unknown) => undefined,
  showInputBox: async (_opts?: unknown) => undefined,
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
  executeCommand: async (cmd: string, ...args: unknown[]) => {
    _executedCommands.push({ cmd, args });
    return undefined;
  },
  registerCommand: (_cmd: string, _handler: (...args: unknown[]) => unknown) => ({ dispose: () => {} }),
};

export interface WorkspaceFolder {
  uri: { fsPath: string };
  name: string;
  index: number;
}

export class RelativePattern {
  constructor(public readonly base: string, public readonly pattern: string) {}
}

/** Watcher stub with fireable events for debounce tests. */
export function makeWatcherStub(): {
  watcher: {
    onDidCreate: (h: () => void) => { dispose(): void };
    onDidChange: (h: () => void) => { dispose(): void };
    onDidDelete: (h: () => void) => { dispose(): void };
    dispose(): void;
  };
  _emitters: { create: EventEmitter<void>; change: EventEmitter<void>; delete: EventEmitter<void> };
} {
  const _emitters = {
    create: new EventEmitter<void>(),
    change: new EventEmitter<void>(),
    delete: new EventEmitter<void>(),
  };
  const watcher = {
    onDidCreate: _emitters.create.event,
    onDidChange: _emitters.change.event,
    onDidDelete: _emitters.delete.event,
    dispose: () => {
      _emitters.create.dispose();
      _emitters.change.dispose();
      _emitters.delete.dispose();
    },
  };
  return { watcher, _emitters };
}

let _lastWatcherStub: ReturnType<typeof makeWatcherStub> | undefined;

// ── Config store (settable by tests) ─────────────────────────────────────────
// Keys are stored as full dotted paths, e.g. "quoin.pythonPath".
// Tests call _setConfig('quoin.pythonPath', 'python-xyz') to override.
// The getConfiguration stub looks up `${section}.${key}` in this store.
const _configStore = new Map<string, unknown>();
export const _setConfig = (key: string, value: unknown): void => { _configStore.set(key, value); };
export const _clearConfig = (): void => { _configStore.clear(); };

export const workspace = {
  workspaceFolders: undefined as readonly WorkspaceFolder[] | undefined,
  createFileSystemWatcher: (_pattern: RelativePattern) => {
    _lastWatcherStub = makeWatcherStub();
    return _lastWatcherStub.watcher;
  },
  /** Exposed for tests to get the last created watcher's emitters. */
  get _lastWatcherEmitters() {
    return _lastWatcherStub?._emitters;
  },
  openTextDocument: async (_uri: unknown) => ({ uri: _uri }),
  getConfiguration: (section: string) => ({
    get: <T>(key: string, defaultValue?: T): T | undefined => {
      const full = `${section}.${key}`;
      return (_configStore.has(full) ? _configStore.get(full) : defaultValue) as T | undefined;
    },
  }),
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

// ── Shared test helpers (makeMemento / makeContext) ────────────────────────

export function makeMemento(): import('vscode').Memento {
  const store = new Map<string, unknown>();
  return {
    keys: () => [...store.keys()],
    get<T>(key: string, defaultValue?: T): T {
      return (store.has(key) ? store.get(key) : defaultValue) as T;
    },
    update(key: string, value: unknown): Thenable<void> {
      store.set(key, value);
      return Promise.resolve();
    },
  };
}

export function makeContext(): import('vscode').ExtensionContext {
  const gs = makeMemento();
  return {
    globalState: gs,
    subscriptions: [],
    extensionUri: Uri.file('/stub-extension'),
  } as unknown as import('vscode').ExtensionContext;
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
