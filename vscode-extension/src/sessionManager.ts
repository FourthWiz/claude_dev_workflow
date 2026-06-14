import * as vscode from 'vscode';
import { randomUUID } from 'node:crypto';
import { QuoinSession, PersistedSession, Runtime } from './types';

const GLOBAL_STATE_PREFIX = 'quoin.sessions::';

type TerminalFactory = (opts: vscode.TerminalOptions) => vscode.Terminal;

export class SessionManager {
  private registry = new Map<string, QuoinSession>();
  private _onDidChange = new vscode.EventEmitter<void>();
  readonly onDidChange = this._onDidChange.event;
  private runtimeCounters = new Map<string, number>();

  constructor(
    private readonly context: vscode.ExtensionContext,
    terminalCloseEvent: vscode.Event<vscode.Terminal>
  ) {
    context.subscriptions.push(
      terminalCloseEvent(this.onTerminalClose, this)
    );
  }

  /** Pure function: maps persisted entries to in-memory sessions with no live terminal */
  static rehydrate(persisted: PersistedSession[]): QuoinSession[] {
    return persisted.map((p) => ({ ...p, terminal: undefined, relaunchable: true }));
  }

  loadPersisted(projectRoot: string): void {
    const key = GLOBAL_STATE_PREFIX + projectRoot;
    const persisted = this.context.globalState.get<PersistedSession[]>(key, []);
    const sessions = SessionManager.rehydrate(persisted);
    for (const s of sessions) {
      this.registry.set(s.id, s);
    }
  }

  async savePersisted(projectRoot: string): Promise<void> {
    const key = GLOBAL_STATE_PREFIX + projectRoot;
    const toSave: PersistedSession[] = [];
    for (const s of this.registry.values()) {
      if (s.projectRoot === projectRoot) {
        const { terminal: _t, ...rest } = s;
        toSave.push(rest);
      }
    }
    await this.context.globalState.update(key, toSave);
  }

  create(
    runtime: Runtime,
    projectRoot: string,
    terminalFactory: TerminalFactory = vscode.window.createTerminal
  ): QuoinSession {
    const counterKey = `${runtime}:${projectRoot}`;
    const n = (this.runtimeCounters.get(counterKey) ?? 0) + 1;
    this.runtimeCounters.set(counterKey, n);
    const label = `${runtime}-${n}`;

    const session: QuoinSession = {
      id: randomUUID(),
      label,
      runtime,
      projectRoot,
      createdAt: Date.now(),
      relaunchable: false,
    };

    // Synchronous handle — createTerminal returns immediately
    session.terminal = terminalFactory({ name: label, cwd: projectRoot });
    session.terminal.sendText(runtime, true);
    session.terminal.show();

    this.registry.set(session.id, session);
    void this.savePersisted(projectRoot);
    this._onDidChange.fire();
    return session;
  }

  get(id: string): QuoinSession | undefined {
    return this.registry.get(id);
  }

  getAll(): QuoinSession[] {
    return [...this.registry.values()];
  }

  /**
   * Relaunch an existing session in-place, reusing its UUID so the webview
   * selection stays accurate after the terminal closes and is relaunched.
   */
  relaunch(
    id: string,
    terminalFactory: TerminalFactory = vscode.window.createTerminal
  ): QuoinSession | undefined {
    const session = this.registry.get(id);
    if (!session) return undefined;

    session.terminal = terminalFactory({ name: session.label, cwd: session.projectRoot });
    session.terminal.sendText(session.runtime, true);
    session.terminal.show();
    session.relaunchable = false;
    session.createdAt = Date.now();

    void this.savePersisted(session.projectRoot);
    this._onDidChange.fire();
    return session;
  }

  private onTerminalClose(terminal: vscode.Terminal): void {
    for (const session of this.registry.values()) {
      if (session.terminal === terminal) {
        // Exit-too-fast heuristic: show PATH hint if terminal died within 3s of creation
        if (Date.now() - session.createdAt < 3000) {
          vscode.window.showInformationMessage(
            `Quoin: '${session.runtime}' exited immediately — is it on your PATH?`
          );
        }
        session.terminal = undefined;
        session.relaunchable = true;
        void this.savePersisted(session.projectRoot);
        this._onDidChange.fire();
        break;
      }
    }
  }

  dispose(): void {
    this._onDidChange.dispose();
  }
}
