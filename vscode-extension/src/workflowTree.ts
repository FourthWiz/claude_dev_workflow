import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import { DataService } from './dataService';
import { SessionManager } from './sessionManager';
import { getNextSkill } from './workflowMapping';

/** Minimal interface for the control panel — satisfied by ControlPanelViewProvider after T-06. */
interface HighlightTarget {
  postHighlight(nextSkill: string | null): void;
}

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

export class WorkflowTreeViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _projectRoot: string | undefined;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly dataService: DataService,
    private readonly sessionManager: SessionManager,
    private readonly controlPanel: HighlightTarget,
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

    // Subscribe to data + session changes
    const dsDisposable = this.dataService.onDidChange(() => { void this._refresh(); });
    const smDisposable = this.sessionManager.onDidChange(() => { void this._refresh(); });

    webviewView.onDidDispose(() => {
      dsDisposable.dispose();
      smDisposable.dispose();
    });

    void this._refresh();
  }

  private async _refresh(): Promise<void> {
    if (!this._view?.visible) { return; }
    const webview = this._view.webview;

    // Resolve project root: prefer active session's root, then workspace walk-up
    let newRoot: string | undefined;
    const sessions = this.sessionManager.getAll();
    if (sessions.length > 0 && sessions[0].projectRoot) {
      newRoot = sessions[0].projectRoot;
    }
    if (!newRoot) {
      newRoot = this.dataService.getProjectRoot(vscode.workspace.workspaceFolders);
    }

    if (newRoot !== this._projectRoot) {
      this._projectRoot = newRoot;
      if (newRoot) {
        this.dataService.watch(newRoot);
      }
    }

    if (!newRoot) {
      void webview.postMessage({ cmd: 'render', status: 'no-task', message: 'No quoin project found in workspace.' });
      this.controlPanel.postHighlight(null);
      return;
    }

    // Get active task name
    const task = await this.dataService.getActiveTask(newRoot);
    if (!task) {
      void webview.postMessage({ cmd: 'render', status: 'no-task', message: 'No active task found.' });
      this.controlPanel.postHighlight(null);
      return;
    }

    // Get workflow nodes
    const result = await this.dataService.getWorkflowNodes(task, newRoot);

    void webview.postMessage({
      cmd: 'render',
      status: result.status,
      nodes: result.nodes,
      task: result.task ?? task,
      stage: result.stage,
      message: result.message,
    });

    // Compute next skill from active node
    const activeNode = result.nodes?.find((n) => n.state === 'active')?.node ?? null;
    this.controlPanel.postHighlight(getNextSkill(activeNode));
  }

  private _buildHtml(webview: vscode.Webview): string {
    const nonce = generateNonce();
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'workflowTree.js'),
    );
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'workflowTree.css'),
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
  <title>Quoin Workflow</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div id="content" class="placeholder">Loading…</div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}
