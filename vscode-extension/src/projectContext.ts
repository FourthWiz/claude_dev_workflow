import * as vscode from 'vscode';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { findArtifactsRoot } from './artifactsRoot';
import { FsLike } from './archiveScanner';

const ACTIVE_ROOT_KEY = 'quoin.activeProjectRoot';
const LAST_ROOT_KEY = 'quoin.lastProjectRoot';
const SESSION_PREFIX = 'quoin.sessions::';

type WorkspaceFoldersProvider = () => readonly { uri: { fsPath: string } }[] | undefined;

export interface ProjectContextOptions {
  fsImpl?: Pick<FsLike, 'existsSync'>;
  workspaceFoldersProvider?: WorkspaceFoldersProvider;
}

/**
 * Single source of truth for the active project root within a VS Code window.
 * All views read getActiveRoot() instead of each resolving independently.
 *
 * Precedence (D-01):
 *  1. globalState quoin.activeProjectRoot — if it still resolves to a dir
 *     containing .workflow_artifacts/
 *  2. Walk-up from workspaceFolders[0] via findArtifactsRoot
 *  3. globalState quoin.lastProjectRoot
 *  4. undefined → views render "no quoin project" empty state
 */
export class ProjectContext {
  private readonly _onDidChangeActiveRoot = new vscode.EventEmitter<string | undefined>();
  readonly onDidChangeActiveRoot = this._onDidChangeActiveRoot.event;

  private readonly _fsImpl: Pick<FsLike, 'existsSync'>;
  private readonly _workspaceFolders: WorkspaceFoldersProvider;

  constructor(
    private readonly context: vscode.ExtensionContext,
    opts: ProjectContextOptions = {},
  ) {
    this._fsImpl = opts.fsImpl ?? { existsSync: fs.existsSync };
    this._workspaceFolders = opts.workspaceFoldersProvider ?? (() => vscode.workspace.workspaceFolders);
    context.subscriptions.push(this._onDidChangeActiveRoot);
  }

  getActiveRoot(): string | undefined {
    // 1. Explicit override (persisted by setActiveRoot / switcher)
    const override = this.context.globalState.get<string>(ACTIVE_ROOT_KEY);
    if (override && this._fsImpl.existsSync(path.join(override, '.workflow_artifacts'))) {
      return override;
    }

    // 2. Walk up from workspace folder
    const folders = this._workspaceFolders();
    if (folders && folders.length > 0) {
      const walked = findArtifactsRoot(folders[0].uri.fsPath, this._fsImpl);
      if (walked) { return walked; }
    }

    // 3. Last persisted root
    const last = this.context.globalState.get<string>(LAST_ROOT_KEY);
    if (last && this._fsImpl.existsSync(path.join(last, '.workflow_artifacts'))) {
      return last;
    }

    return undefined;
  }

  async setActiveRoot(root: string): Promise<void> {
    await this.context.globalState.update(ACTIVE_ROOT_KEY, root);
    this._onDidChangeActiveRoot.fire(root);
  }

  /**
   * Enumerate all project roots this extension knows about.
   * Deduplicates and collapses legacy raw-path keys (pre-fix nested-folder
   * sessions stored under the workspace folder, not the artifacts root) so
   * the switcher never shows the same project twice.
   */
  listKnownRoots(): string[] {
    const seen = new Set<string>();
    const add = (r: string | undefined) => {
      if (!r) { return; }
      // Collapse to the artifacts root (if reachable); fall back to r as-is
      const canonical = findArtifactsRoot(r, this._fsImpl) ?? r;
      seen.add(canonical);
    };

    // Workspace folders
    const folders = this._workspaceFolders();
    if (folders) {
      for (const f of folders) { add(f.uri.fsPath); }
    }

    // Persisted switcher choice + last root
    add(this.context.globalState.get<string>(ACTIVE_ROOT_KEY));
    add(this.context.globalState.get<string>(LAST_ROOT_KEY));

    // Session keys in globalState (format: quoin.sessions::<root>)
    for (const key of this.context.globalState.keys()) {
      if (key.startsWith(SESSION_PREFIX)) {
        add(key.slice(SESSION_PREFIX.length));
      }
    }

    return [...seen];
  }
}
