// Quoin Sessions Archive — webview script (nonce-gated, CSP-compliant)
// No inline handlers. Builds DOM via createElement + textContent (never innerHTML with interpolated strings).

(function () {
  'use strict';

  const vscode = acquireVsCodeApi();
  const content = document.getElementById('content');

  // ── Delegated click handler ───────────────────────────────────────────────

  content.addEventListener('click', function (event) {
    const target = event.target;
    if (!target || !(target instanceof Element)) { return; }

    // Walk up to find a row with data attributes
    const sessionRow = target.closest('[data-session-id]');
    if (sessionRow) {
      const sessionId = sessionRow.getAttribute('data-session-id');
      if (sessionId) {
        vscode.postMessage({ cmd: 'reveal', sessionId: sessionId });
      }
      return;
    }

    const archiveRow = target.closest('[data-file-path]');
    if (archiveRow) {
      const filePath = archiveRow.getAttribute('data-file-path');
      if (filePath) {
        vscode.postMessage({ cmd: 'open', filePath: filePath });
      }
    }
  });

  // ── Render ────────────────────────────────────────────────────────────────

  function render(msg) {
    // Clear current content
    while (content.firstChild) {
      content.removeChild(content.firstChild);
    }
    content.className = '';

    const active = Array.isArray(msg.active) ? msg.active : [];
    const archived = Array.isArray(msg.archived) ? msg.archived : [];
    const hasRoot = !!msg.hasRoot;

    if (active.length === 0 && archived.length === 0) {
      content.className = 'placeholder';
      const placeholder = document.createElement('div');
      placeholder.textContent = hasRoot
        ? 'No sessions yet.'
        : 'No quoin project found.';
      content.appendChild(placeholder);
      return;
    }

    // ── Active group ──────────────────────────────────────────────────────

    if (active.length > 0) {
      const groupHeader = document.createElement('div');
      groupHeader.className = 'group-header';
      groupHeader.textContent = 'Active';
      content.appendChild(groupHeader);

      for (const session of active) {
        const row = document.createElement('div');
        row.className = 'session-row';
        row.setAttribute('data-session-id', session.id || '');
        row.title = 'Click to reveal terminal';

        // Status glyph: ● live / ○ relaunchable
        const glyph = document.createElement('span');
        glyph.className = 'glyph';
        glyph.textContent = session.relaunchable ? '○' : '●';

        const label = document.createElement('span');
        label.className = 'session-label';
        label.textContent = session.label || '';

        const badge = document.createElement('span');
        badge.className = 'badge runtime-badge';
        badge.textContent = session.runtime || '';

        row.appendChild(glyph);
        row.appendChild(label);
        row.appendChild(badge);

        if (session.relaunchable) {
          const suffix = document.createElement('span');
          suffix.className = 'relaunchable-suffix';
          suffix.textContent = ' (relaunchable)';
          row.appendChild(suffix);
        }

        content.appendChild(row);
      }
    }

    // ── Archived group ────────────────────────────────────────────────────

    if (archived.length > 0) {
      const groupHeader = document.createElement('div');
      groupHeader.className = 'group-header';
      groupHeader.textContent = 'Archived';
      content.appendChild(groupHeader);

      for (const entry of archived) {
        const row = document.createElement('div');
        row.className = 'archive-row';
        row.setAttribute('data-file-path', entry.filePath || '');
        row.title = 'Click to open file';

        const sourceBadge = document.createElement('span');
        sourceBadge.className = 'badge source-badge';
        sourceBadge.textContent = entry.source || '';

        const label = document.createElement('span');
        label.className = 'archive-label';
        label.textContent = entry.label || '';

        row.appendChild(sourceBadge);
        row.appendChild(label);

        if (entry.date) {
          const dateBadge = document.createElement('span');
          dateBadge.className = 'archive-date';
          dateBadge.textContent = entry.date;
          row.appendChild(dateBadge);
        }

        if (entry.status) {
          const statusSpan = document.createElement('span');
          statusSpan.className = 'archive-status';
          statusSpan.textContent = entry.status;
          row.appendChild(statusSpan);
        }

        content.appendChild(row);
      }
    }
  }

  // ── Message listener ──────────────────────────────────────────────────────

  window.addEventListener('message', function (event) {
    const msg = event.data;
    if (msg && msg.cmd === 'render') {
      render(msg);
    }
  });

}());
