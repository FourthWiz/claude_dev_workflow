// Quoin Sessions Archive — webview script (nonce-gated, CSP-compliant)
// No inline handlers. Builds DOM via createElement + textContent (never innerHTML with interpolated strings).

(function () {
  'use strict';

  const vscode = acquireVsCodeApi();
  const content = document.getElementById('content');

  // ── State ─────────────────────────────────────────────────────────────────

  const PAGE_SIZE = 25;
  let _allArchived = [];
  let _filterText = '';
  let _pageIndex = 0;

  // ── Delegated click handler ───────────────────────────────────────────────

  content.addEventListener('click', function (event) {
    const target = event.target;
    if (!target || !(target instanceof Element)) { return; }

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

  // ── Archive filter + pagination ───────────────────────────────────────────

  function filteredArchived() {
    if (!_filterText) { return _allArchived; }
    const q = _filterText.toLowerCase();
    return _allArchived.filter(function (e) {
      return (e.label || '').toLowerCase().includes(q) ||
             (e.task || '').toLowerCase().includes(q) ||
             (e.date || '').toLowerCase().includes(q);
    });
  }

  function buildArchivedSection() {
    const details = document.createElement('details');

    const summary = document.createElement('summary');
    summary.className = 'group-header';
    summary.textContent = 'Archived';
    details.appendChild(summary);

    // Filter input
    const filterWrap = document.createElement('div');
    filterWrap.className = 'archive-filter-wrap';
    const filterInput = document.createElement('input');
    filterInput.type = 'text';
    filterInput.className = 'archive-filter';
    filterInput.placeholder = 'Filter archived…';
    filterInput.value = _filterText;
    filterWrap.appendChild(filterInput);
    details.appendChild(filterWrap);

    const rows = filteredArchived();
    const totalRows = rows.length;
    const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
    if (_pageIndex >= totalPages) { _pageIndex = 0; }
    const start = _pageIndex * PAGE_SIZE;
    const pageRows = rows.slice(start, start + PAGE_SIZE);

    for (const entry of pageRows) {
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

      details.appendChild(row);
    }

    // Pagination bar
    if (totalRows > PAGE_SIZE) {
      const pager = document.createElement('div');
      pager.className = 'archive-pager';

      const prevBtn = document.createElement('button');
      prevBtn.className = 'pager-btn';
      prevBtn.textContent = '‹ Prev';
      prevBtn.disabled = _pageIndex === 0;

      const nextBtn = document.createElement('button');
      nextBtn.className = 'pager-btn';
      nextBtn.textContent = 'Next ›';
      nextBtn.disabled = _pageIndex >= totalPages - 1;

      const info = document.createElement('span');
      info.className = 'pager-info';
      info.textContent = (start + 1) + '–' + Math.min(start + PAGE_SIZE, totalRows) + ' of ' + totalRows;

      pager.appendChild(prevBtn);
      pager.appendChild(info);
      pager.appendChild(nextBtn);
      details.appendChild(pager);

      prevBtn.addEventListener('click', function () {
        if (_pageIndex > 0) {
          _pageIndex--;
          rebuildArchivedSection();
        }
      });

      nextBtn.addEventListener('click', function () {
        if (_pageIndex < totalPages - 1) {
          _pageIndex++;
          rebuildArchivedSection();
        }
      });
    }

    // Wire filter input (no inline handler — addEventListener in script)
    filterInput.addEventListener('input', function () {
      _filterText = filterInput.value;
      _pageIndex = 0;
      rebuildArchivedSection();
    });

    return details;
  }

  function rebuildArchivedSection() {
    const existing = content.querySelector('details.archived-details');
    if (!existing) { return; }
    const fresh = buildArchivedSection();
    fresh.className = 'archived-details';
    fresh.open = existing.open;
    content.replaceChild(fresh, existing);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function render(msg) {
    // Reset client-side state on every render (D-05)
    _filterText = '';
    _pageIndex = 0;

    while (content.firstChild) {
      content.removeChild(content.firstChild);
    }
    content.className = '';

    const active = Array.isArray(msg.active) ? msg.active : [];
    _allArchived = Array.isArray(msg.archived) ? msg.archived : [];
    const hasRoot = !!msg.hasRoot;

    if (active.length === 0 && _allArchived.length === 0) {
      content.className = 'placeholder';
      const placeholder = document.createElement('div');
      placeholder.textContent = hasRoot
        ? 'No sessions yet.'
        : 'No quoin project found.';
      content.appendChild(placeholder);
      return;
    }

    // ── Active group (open by default) ──────────────────────────────────────

    if (active.length > 0) {
      const activeDetails = document.createElement('details');
      activeDetails.open = true;
      activeDetails.className = 'active-details';

      const activeSummary = document.createElement('summary');
      activeSummary.className = 'group-header';
      activeSummary.textContent = 'Active';
      activeDetails.appendChild(activeSummary);

      for (const session of active) {
        const row = document.createElement('div');
        row.className = 'session-row';
        row.setAttribute('data-session-id', session.id || '');
        row.title = 'Click to reveal terminal';

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

        activeDetails.appendChild(row);
      }

      content.appendChild(activeDetails);
    }

    // ── Archived group (collapsed by default) ──────────────────────────────

    if (_allArchived.length > 0) {
      const archivedDetails = buildArchivedSection();
      archivedDetails.className = 'archived-details';
      // archived collapsed by default (no .open = true)
      content.appendChild(archivedDetails);
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
