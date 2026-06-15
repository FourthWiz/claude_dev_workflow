// Quoin Cost — webview script (nonce-gated, CSP-compliant)
// No inline handlers. Builds DOM via createElement + textContent (never innerHTML with interpolated strings).
// Read-only view: no messages are posted back to the host.

(function () {
  'use strict';

  // acquireVsCodeApi is available in the webview context (nonce-gated by host)
  // eslint-disable-next-line no-undef
  const vscode = acquireVsCodeApi();
  void vscode; // kept for potential future outbound messages; no messages sent in v1

  const content = document.getElementById('content');

  // ── DOM helpers ───────────────────────────────────────────────────────────────

  function el(tag, className) {
    const e = document.createElement(tag);
    if (className) { e.className = className; }
    return e;
  }

  function text(tag, className, txt) {
    const e = el(tag, className);
    e.textContent = txt;
    return e;
  }

  function formatUsd(usd) {
    if (usd === null || usd === undefined) { return null; }
    return '$' + usd.toFixed(2);
  }

  function badge(label, className) {
    const b = el('span', 'badge ' + (className || ''));
    b.textContent = label;
    return b;
  }

  function groupHeader(title) {
    return text('div', 'group-header', title);
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  function render(msg) {
    // Clear current content
    while (content.firstChild) {
      content.removeChild(content.firstChild);
    }
    content.className = '';

    const view = msg && msg.view;
    const hasRoot = !!msg.hasRoot;

    if (!hasRoot) {
      content.className = 'placeholder';
      const ph = el('div');
      ph.textContent = 'No quoin project found.';
      content.appendChild(ph);
      return;
    }

    if (!view) {
      content.className = 'placeholder';
      const ph = el('div');
      ph.textContent = 'Scripts not found — install quoin to enable cost tracking.';
      content.appendChild(ph);
      return;
    }

    const live = view.live;
    const tasks = Array.isArray(view.tasks) ? view.tasks : [];

    // ── Scope note (D-05) ──────────────────────────────────────────────────────

    if (view.scopeNote) {
      const noteRow = el('div', 'scope-note');
      noteRow.textContent = view.scopeNote;
      content.appendChild(noteRow);
    }

    // ── Today's spend (this project) ──────────────────────────────────────────

    content.appendChild(groupHeader("Today's spend (this project)"));

    const todayRow = el('div', 'cost-row');
    if (live !== null && live !== undefined) {
      const usdFormatted = formatUsd(live.today_usd);
      const todayVal = text('span', 'cost-value', usdFormatted);
      todayRow.appendChild(todayVal);
      if (live.stale) {
        todayRow.appendChild(badge('stale', 'badge-stale'));
      }
    } else {
      todayRow.appendChild(text('span', 'cost-unavailable', 'unavailable'));
    }
    content.appendChild(todayRow);

    // ── Per task — today (this project) ──────────────────────────────────────

    const todayTasks = tasks.filter(function (t) { return t.today_usd !== null && t.today_usd !== undefined; });

    if (todayTasks.length > 0) {
      content.appendChild(groupHeader('Per task — today (this project)'));

      for (const task of todayTasks) {
        const row = el('div', 'task-row');

        const nameSpan = text('span', 'task-name', task.task);
        row.appendChild(nameSpan);

        const usdFormatted = formatUsd(task.today_usd);
        const valSpan = text('span', 'cost-value', usdFormatted !== null ? usdFormatted : '—');
        row.appendChild(valSpan);

        if (task.state === 'partial') {
          row.appendChild(badge('partial', 'badge-partial'));
        }

        content.appendChild(row);
      }
    }

    // Incomplete list note (D-05/MAJ-3 fixture d):
    // Show when by_task_partial OR today_usd>0 with empty by_task
    const hasEmptyByTask = live && live.today_usd > 0 && Object.keys(live.by_task).length === 0;
    if ((live && live.by_task_partial) || hasEmptyByTask) {
      const note = el('div', 'incomplete-note');
      note.textContent = 'Per-task list may be incomplete — some project sessions could not be resolved.';
      content.appendChild(note);
    }

    // ── Per task — finalized total ────────────────────────────────────────────

    const finalizedTasks = tasks.filter(function (t) { return t.finalized_usd !== null && t.finalized_usd !== undefined; });
    const unavailableTasks = tasks.filter(function (t) { return t.state === 'unavailable' && (t.finalized_usd === null || t.finalized_usd === undefined); });

    if (finalizedTasks.length > 0 || unavailableTasks.length > 0) {
      content.appendChild(groupHeader('Per task — finalized total'));

      for (const task of finalizedTasks) {
        const row = el('div', 'task-row');

        row.appendChild(text('span', 'task-name', task.task));

        const usdFormatted = formatUsd(task.finalized_usd);
        row.appendChild(text('span', 'cost-value', usdFormatted !== null ? usdFormatted : '—'));

        if (task.state === 'partial') {
          row.appendChild(badge('partial — some sessions unresolved', 'badge-partial'));
        }

        content.appendChild(row);
      }

      for (const task of unavailableTasks) {
        const row = el('div', 'task-row');
        row.appendChild(text('span', 'task-name', task.task));
        row.appendChild(text('span', 'cost-unavailable', 'unavailable'));
        content.appendChild(row);
      }
    }

    // ── Finalized grand total ─────────────────────────────────────────────────

    const grandTotal = view.finalizedGrandTotal;
    const grandState = view.finalizedGrandTotalState;

    if (grandTotal !== null && grandTotal !== undefined) {
      content.appendChild(groupHeader('Finalized grand total'));

      const grandRow = el('div', 'cost-row grand-total-row');
      const gtFormatted = formatUsd(grandTotal);
      grandRow.appendChild(text('span', 'cost-value cost-total', gtFormatted !== null ? gtFormatted : '—'));

      if (grandState === 'partial') {
        grandRow.appendChild(badge('partial', 'badge-partial'));
      } else if (grandState === 'unavailable') {
        grandRow.appendChild(badge('some tasks unavailable', 'badge-unavailable'));
      }

      content.appendChild(grandRow);
    }

    // ── Exclusions note (R-06) ────────────────────────────────────────────────

    const exclusionsNote = el('div', 'exclusions-note');
    exclusionsNote.textContent = 'Note: Codex USD and per-phase charts not included in v1.';
    content.appendChild(exclusionsNote);
  }

  // ── Message listener ───────────────────────────────────────────────────────

  window.addEventListener('message', function (event) {
    const msg = event.data;
    if (msg && msg.cmd === 'render') {
      render(msg);
    }
  });

}());
