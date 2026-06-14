import * as vscode from 'vscode';
import { randomBytes } from 'node:crypto';
import { SessionManager } from './sessionManager';
import { CommandRunner } from './commandRunner';
import { enumerateSkills, groupSkills } from './skillCatalog';

// ── Message types (webview ↔ host) ────────────────────────────────────────────

/** Sent by the webview when the user clicks Run. */
interface RunMessage {
  cmd: 'run';
  skill: string | null;
  prompt: string;
  sessionId: string;  // UUID (session.id), NOT the display label
}

/** Sent by the webview when the user changes the session selector. */
interface SelectSessionMessage {
  cmd: 'selectSession';
  sessionId: string;
}

type WebviewMessage = RunMessage | SelectSessionMessage;

function isRunMessage(msg: unknown): msg is RunMessage {
  if (!msg || typeof msg !== 'object') return false;
  const m = msg as Record<string, unknown>;
  return (
    m['cmd'] === 'run' &&
    (m['skill'] === null || typeof m['skill'] === 'string') &&
    typeof m['prompt'] === 'string' &&
    typeof m['sessionId'] === 'string'
  );
}

function isSelectSessionMessage(msg: unknown): msg is SelectSessionMessage {
  if (!msg || typeof msg !== 'object') return false;
  const m = msg as Record<string, unknown>;
  return m['cmd'] === 'selectSession' && typeof m['sessionId'] === 'string';
}

// ── HTML helpers ──────────────────────────────────────────────────────────────

/**
 * Escape a string for safe injection into HTML double-quoted attribute values or text nodes.
 * Single quotes don't need escaping inside double-quoted attributes, so we only escape
 * &, <, >, and " to keep CSP directives like default-src 'none' readable in the attribute.
 */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Generate a cryptographically-random nonce for the CSP script-src. */
function generateNonce(): string {
  return randomBytes(24).toString('base64');
}

// ── ControlPanelViewProvider ──────────────────────────────────────────────────

/**
 * WebviewViewProvider for the Quoin Control Panel view (quoin.controlPanel).
 *
 * Security posture (R-05):
 *   - Per-render random nonce on the single <script> tag
 *   - CSP: default-src 'none'; script-src 'nonce-{nonce}'; style-src {cspSource};
 *           img-src {cspSource}; font-src {cspSource}
 *   - localResourceRoots: [extensionUri/media] — no remote origins
 *   - External stylesheet loaded via asWebviewUri (NOT inline <style>)
 *   - All skill names HTML-escaped before injection
 *   - All inbound postMessage payloads type-checked before dispatch
 *
 * Codex guard (R-09):
 *   - Webview disables skill buttons when runtime === 'codex'
 *   - Host FORCES skill=null for Codex sessions regardless of webview payload
 */
export class ControlPanelViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly sessionManager: SessionManager,
    private readonly commandRunner: CommandRunner
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, 'media')],
    };

    webviewView.webview.html = this._buildHtml(webviewView.webview);

    // Listen for webview → host messages
    webviewView.webview.onDidReceiveMessage((raw: unknown) => {
      this._handleMessage(raw, webviewView.webview);
    });

    // Push initial data to the webview once it's ready
    this._postSessionList(webviewView.webview);
    this._postSkillGroups(webviewView.webview);

    // Re-push session list whenever sessions change
    const listener = this.sessionManager.onDidChange(() => {
      if (this._view?.visible) {
        this._postSessionList(this._view.webview);
      }
    });
    webviewView.onDidDispose(() => listener.dispose());
  }

  // ── Message handling ───────────────────────────────────────────────────────

  private _handleMessage(raw: unknown, webview: vscode.Webview): void {
    if (isRunMessage(raw)) {
      this._handleRun(raw, webview);
    } else if (isSelectSessionMessage(raw)) {
      this._handleSelectSession(raw, webview);
    }
    // Unknown commands are silently ignored (strict type-check above)
  }

  private _handleRun(msg: RunMessage, webview: vscode.Webview): void {
    const session = this.sessionManager.get(msg.sessionId);
    if (!session) {
      void vscode.window.showInformationMessage('Quoin: Unknown or closed session');
      return;
    }

    // T-04 Codex guard — FORCE skill=null for Codex sessions (never trust the webview)
    const skill = session.runtime === 'codex' ? null : msg.skill;

    this.commandRunner.run(session, skill, msg.prompt);

    // Push updated runtime state so webview stays in sync
    void webview.postMessage({
      cmd: 'session',
      sessionId: session.id,
      runtime: session.runtime,
    });
  }

  private _handleSelectSession(msg: SelectSessionMessage, webview: vscode.Webview): void {
    const session = this.sessionManager.get(msg.sessionId);
    if (!session) return;

    void webview.postMessage({
      cmd: 'session',
      sessionId: session.id,
      runtime: session.runtime,
    });
  }

  // ── Data push helpers ──────────────────────────────────────────────────────

  private _postSessionList(webview: vscode.Webview): void {
    const sessions = this.sessionManager.getAll().map(s => ({
      id: s.id,
      label: s.label,
      runtime: s.runtime,
    }));
    void webview.postMessage({ cmd: 'sessions', sessions });

    // Push runtime for the first session (best-effort)
    if (sessions.length > 0) {
      void webview.postMessage({
        cmd: 'session',
        sessionId: sessions[0].id,
        runtime: sessions[0].runtime,
      });
    }
  }

  private _postSkillGroups(webview: vscode.Webview): void {
    const names = enumerateSkills();
    const groups = groupSkills(names);
    void webview.postMessage({ cmd: 'skills', groups });
  }

  // ── HTML builder ───────────────────────────────────────────────────────────

  _buildHtml(webview: vscode.Webview): string {
    const nonce = generateNonce();
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'controlPanel.js')
    );
    const styleUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, 'media', 'controlPanel.css')
    );
    const csp = webview.cspSource;

    // CSP: no unsafe-inline, no remote origins, nonce-gated script, external stylesheet
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
  <title>Quoin Control Panel</title>
  <link rel="stylesheet" href="${styleUri}">
</head>
<body>
  <div class="session-row">
    <label for="session-select">Session</label>
    <select id="session-select">
      <option value="" disabled selected>(no sessions)</option>
    </select>
  </div>

  <div id="codex-note" class="codex-note">
    Codex: raw prompt only (no /skill)
  </div>

  <div id="skill-groups" class="skill-groups"></div>

  <div class="prompt-row">
    <label for="prompt">Prompt</label>
    <textarea id="prompt" rows="3" placeholder="Enter prompt…"></textarea>
  </div>

  <div class="run-row">
    <button id="run-btn">Run</button>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}
