/**
 * SessionsArchiveViewProvider — webview for the quoin.sessionsArchive view.
 *
 * Security posture (R-05):
 *   - Per-render random nonce on the single <script> tag
 *   - CSP: default-src 'none'; script-src 'nonce-{nonce}'; style-src {cspSource};
 *           img-src {cspSource}; font-src {cspSource}
 *   - localResourceRoots: [extensionUri/media] — no remote origins
 *   - External stylesheet and script loaded via asWebviewUri (NOT inline)
 *   - All inbound postMessage payloads type-checked before dispatch (mirror controlPanel.ts)
 *
 * Data flow:
 *   SessionManager.getAll() → active sessions (live or relaunchable)
 *   scanArchive(root, fsImpl) → archived sessions from disk
 *   merged → postMessage {cmd:'render', active, archived, hasRoot}
 *   click active row → postMessage {cmd:'reveal', sessionId} → quoin.revealSession
 *   click archived row → postMessage {cmd:'open', filePath} → quoin.openArchivedSession
 */
import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import * as fs from 'node:fs';
import { SessionManager } from './sessionManager';
import { DataService } from './dataService';
import { scanArchive, FsLike } from './archiveScanner';

// ── Message type-guards (inbound from webview) ────────────────────────────────

interface RevealMessage {
  cmd: 'reveal';
  sessionId: string;
}

interface OpenMessage {
  cmd: 'open';
  filePath: string;
}

function isRevealMessage(msg: unknown): msg is RevealMessage {
  if (!msg || typeof msg !== 'object') { return false; }
  const m = msg as Record<string, unknown>;
  return m['cmd'] === 'reveal' && typeof m['sessionId'] === 'string' && !!m['sessionId'];
}

function isOpenMessage(msg: unknown): msg is OpenMessage {
  if (!msg || typeof msg !== 'object') { return false; }
  const m = msg as Record<string, unknown>;
  return m['cmd'] === 'open' && typeof m['filePath'] === 'string' && !!m['filePath'];
}

// ── HTML helpers (copied from workflowTree.ts) ────────────────────────────────

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function generateNonce(): string {
  return randomBytes(24).toString('base64');
}

// ── Default fs implementation ─────────────────────────────────────────────────

const defaultFs: FsLike = {
  existsSync: fs.existsSync,
  readdirSync: (p: string) => fs.readdirSync(p) as string[],
  readFileSync: (p: string, enc: 'utf8') => fs.readFileSync(p, enc),
};

// ── SessionsArchiveViewProvider ───────────────────────────────────────────────

export class SessionsArchiveViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _lastRoot: string | undefined;
  private readonly _fs: FsLike;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly sessionManager: SessionManager,
    private readonly dataService: DataService,
    fsImpl?: FsLike,
  ) {
    this._fs = fsImpl ?? defaultFs;
  }

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, 'media')],
    };

    webviewView.webview.html = this._buildHtml(webviewView.webview);

    // Validate and dispatch inbound messages from the webview
    webviewView.webview.onDidReceiveMessage((raw: unknown) => {
      if (isRevealMessage(raw)) {
        void vscode.commands.executeCommand('quoin.revealSession', raw.sessionId);
      } else if (isOpenMessage(raw)) {
        void vscode.commands.executeCommand('quoin.openArchivedSession', raw.filePath);
      }
      // Any other shape is silently ignored
    });

    // Subscribe to data + session changes
    const dsDisposable = this.dataService.onDidChange(() => { void this._refresh(); });
    const smDisposable = this.sessionManager.onDidChange(() => { void this._refresh(); });

    webviewView.onDidDispose(() => {
      dsDisposable.dispose();
      smDisposable.dispose();
    });

    // Resolve root and start watching
    const root = this.dataService.getProjectRoot(vscode.workspace.workspaceFolders);
    if (root) {
      this._lastRoot = root;
      this.dataService.watch(root);
    }

    void this._refresh();
  }

  private _refresh(): void {
    if (!this._view?.visible) { return; }

    // Map active sessions host-side; compute relaunchable glyph decision here
    const active = this.sessionManager.getAll().map((s) => ({
      id: s.id,
      label: s.label,
      runtime: s.runtime,
      relaunchable: s.relaunchable || !s.terminal,
      projectRoot: s.projectRoot,
    }));

    // Resolve project root: prefer active session root, else workspace walk-up
    const root = active[0]?.projectRoot ?? this.dataService.getProjectRoot(vscode.workspace.workspaceFolders);

    if (root !== this._lastRoot) {
      this._lastRoot = root;
      if (root) {
        this.dataService.watch(root);
      }
    }

    const archived = root ? scanArchive(root, this._fs) : [];

    void this._view.webview.postMessage({
      cmd: 'render',
      active,
      archived,
      hasRoot: !!root,
    });
  }

  _buildHtml(webview: vscode.Webview): string {
    const nonce = generateNonce();
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'sessionsArchive.js'),
    );
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'sessionsArchive.css'),
    );
    const csp = webview.cspSource;

    const contentSecurityPolicy = [
      `default-src 'none'`,
      `style-src ${csp}`,
      `script-src 'nonce-${nonce}'`,
      `img-src ${csp}`,
      `font-src ${csp}`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="${escapeHtml(contentSecurityPolicy)}">
  <title>Quoin Sessions Archive</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div id="content" class="placeholder">Loading…</div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}
