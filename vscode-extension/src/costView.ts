/**
 * CostViewProvider — webview for the quoin.cost view.
 *
 * Security posture (R-05) — byte-identical to sessionsArchive.ts:174-178:
 *   - Per-render random nonce on the single <script> tag
 *   - CSP: default-src 'none'; style-src {cspSource}; script-src 'nonce-{nonce}';
 *           img-src {cspSource}; font-src {cspSource}
 *   - localResourceRoots: [extensionUri/media] — no remote origins
 *   - External stylesheet and script loaded via asWebviewUri (NOT inline)
 *   - Read-only view: no inbound messages handled; any inbound payload silently ignored
 *
 * Data flow:
 *   DataService.getCostView(root) → CostView → postMessage {cmd:'render', view, hasRoot}
 *   Refreshes on dataService.onDidChange (shared instance from extension.ts).
 */
import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import { DataService } from './dataService';

// ── HTML helpers (copied from workflowTree.ts / sessionsArchive.ts) ───────────

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

// ── CostViewProvider ──────────────────────────────────────────────────────────

export class CostViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _lastRoot: string | undefined;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly dataService: DataService,
  ) {}

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

    // Read-only view: type-guard and silently ignore any inbound messages
    webviewView.webview.onDidReceiveMessage((_raw: unknown) => {
      // No inbound messages handled — silently ignore for pattern parity
    });

    // Subscribe to data changes for debounced refresh
    const dsDisposable = this.dataService.onDidChange(() => { void this._refresh(); });

    webviewView.onDidDispose(() => {
      dsDisposable.dispose();
    });

    // Resolve root and start watching
    const root = this.dataService.getProjectRoot(vscode.workspace.workspaceFolders);
    if (root) {
      this._lastRoot = root;
      this.dataService.watch(root);
    }

    void this._refresh();
  }

  private async _refresh(): Promise<void> {
    if (!this._view?.visible) { return; }

    const root = this.dataService.getProjectRoot(vscode.workspace.workspaceFolders);

    if (root !== this._lastRoot) {
      this._lastRoot = root;
      if (root) {
        this.dataService.watch(root);
      }
    }

    let view = null;
    if (root) {
      try {
        view = await this.dataService.getCostView(root);
      } catch {
        view = null;
      }
    }

    void this._view.webview.postMessage({
      cmd: 'render',
      view,
      hasRoot: !!root,
    });
  }

  /**
   * Build the CSP-locked HTML shell.
   * CSP is byte-identical to the shipped sessionsArchive.ts 5-directive string.
   * Public for test assertions (mirrors _buildHtml pattern in sessionsArchive.ts).
   */
  _buildHtml(webview: vscode.Webview): string {
    const nonce = generateNonce();
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'costView.js'),
    );
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'costView.css'),
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
  <title>Quoin Cost</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div id="content" class="placeholder">Loading…</div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}
