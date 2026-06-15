import * as vscode from 'vscode';
import * as path from 'node:path';
import { randomBytes } from 'node:crypto';
import { DataService } from './dataService';
import { ProjectContext } from './projectContext';
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

// UX NOTE (vscode-ext-ux-bugs): combining Control Panel + Workflow into one
// tabbed webview was evaluated and deferred (plan D-05). The main coupling to
// untangle is the controlPanel.postHighlight cross-call. Escalate to /architect
// if the merge is wanted — it changes provider topology and extension.ts wiring.
export class WorkflowTreeViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly dataService: DataService,
    private readonly projectContext: ProjectContext,
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

    // Subscribe to data changes and active-root changes
    const dsDisposable = this.dataService.onDidChange(() => { void this._refresh(); });
    const pcDisposable = this.projectContext.onDidChangeActiveRoot(() => { void this._refresh(); });
    // Re-render when the view becomes visible (guard lives inside _refresh)
    const visDisposable = webviewView.onDidChangeVisibility(() => { void this._refresh(); });

    webviewView.onDidDispose(() => {
      dsDisposable.dispose();
      pcDisposable.dispose();
      visDisposable.dispose();
    });

    void this._refresh();
  }

  private async _refresh(): Promise<void> {
    if (!this._view?.visible) { return; }
    const webview = this._view.webview;

    const root = this.projectContext.getActiveRoot();

    if (!root) {
      void webview.postMessage({ cmd: 'render', status: 'no-task', message: 'No quoin project found in workspace.' });
      this.controlPanel.postHighlight(null);
      return;
    }

    // Get active task name
    const task = await this.dataService.getActiveTask(root);
    if (!task) {
      void webview.postMessage({ cmd: 'render', status: 'no-task', message: 'No active task found.', project: path.basename(root) });
      this.controlPanel.postHighlight(null);
      return;
    }

    // Get workflow nodes
    const result = await this.dataService.getWorkflowNodes(task, root);

    void webview.postMessage({
      cmd: 'render',
      status: result.status,
      nodes: result.nodes,
      task: result.task ?? task,
      stage: result.stage,
      message: result.message,
      project: path.basename(root),
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
