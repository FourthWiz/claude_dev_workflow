/* quoin workflow dashboard — memory browser pane (read-only) */
/* Mirrors app.js ETag/If-None-Match pattern for conditional polling. */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var memState = {
    type: 'lessons',
    items: [],
    selectedId: null,
    etags: {},
    pollInterval: null,
    lastFingerprint: '',
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fetchMemJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url);
    if (memState.etags[url]) {
      xhr.setRequestHeader('If-None-Match', memState.etags[url]);
    }
    xhr.onload = function () {
      if (xhr.status === 304) { cb(null, null); return; }
      if (xhr.status >= 200 && xhr.status < 300) {
        var et = xhr.getResponseHeader('ETag');
        if (et) { memState.etags[url] = et; }
        try { cb(null, JSON.parse(xhr.responseText)); }
        catch (e) { cb(new Error('JSON parse: ' + e.message)); }
      } else {
        cb(new Error('HTTP ' + xhr.status));
      }
    };
    xhr.onerror = function () { cb(new Error('network error')); };
    xhr.send();
  }

  function memTypeUrl(mtype) {
    return '/api/memory/' + encodeURIComponent(mtype);
  }

  function memItemUrl(mtype, itemId) {
    return '/api/memory/' + encodeURIComponent(mtype) + '/' + encodeURIComponent(itemId);
  }

  // ---------------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------------

  function renderTypeButtons(activeType) {
    var btns = document.querySelectorAll('.mem-type-btn');
    btns.forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.mtype === activeType);
    });
  }

  function renderItemList(items) {
    var list = document.getElementById('mem-item-list');
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '<li class="mem-empty">No items.</li>';
      return;
    }
    var html = '';
    items.forEach(function (item) {
      var active = item.id === memState.selectedId ? ' active' : '';
      html += '<li class="mem-item-row' + active + '" data-id="' + escHtml(item.id) + '">';
      html += '<span class="mem-item-title">' + escHtml(item.title) + '</span>';
      if (item.date) {
        html += '<span class="mem-item-date">' + escHtml(item.date) + '</span>';
      }
      html += '</li>';
    });
    list.innerHTML = html;
    list.querySelectorAll('.mem-item-row').forEach(function (row) {
      row.addEventListener('click', function () {
        var id = row.dataset.id;
        if (id) { selectItem(id); }
      });
    });
  }

  function renderItemContent(item) {
    var viewer = document.getElementById('mem-item-viewer');
    if (!viewer) return;
    if (!item) {
      viewer.innerHTML = '<p class="mem-placeholder">Select an item to view.</p>';
      return;
    }
    var html = '<div class="mem-item-header">';
    html += '<strong>' + escHtml(item.title) + '</strong>';
    if (item.date) {
      html += ' <span class="mem-item-date">' + escHtml(item.date) + '</span>';
    }
    html += '</div>';
    html += '<pre class="mem-item-body">' + escHtml(item.body || '') + '</pre>';
    viewer.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  function loadTypeList() {
    var url = memTypeUrl(memState.type);
    fetchMemJSON(url, function (err, data) {
      if (err || data === null) { return; }
      var items = data.items || [];
      // Compute structural fingerprint to skip unnecessary DOM churn on unchanged data
      var fp = memState.type + '|' + JSON.stringify(items.map(function (i) {
        return [i.id, i.title, i.date];
      }));
      if (fp === memState.lastFingerprint) { return; }
      memState.lastFingerprint = fp;
      // Preserve scroll position across re-render
      var listEl = document.getElementById('mem-item-list');
      var savedTop = listEl ? listEl.scrollTop : 0;
      memState.items = items;
      renderItemList(items);
      if (listEl) { listEl.scrollTop = savedTop; }
    });
  }

  function selectItem(itemId) {
    memState.selectedId = itemId;
    document.querySelectorAll('.mem-item-row').forEach(function (r) {
      r.classList.toggle('active', r.dataset.id === itemId);
    });
    var viewer = document.getElementById('mem-item-viewer');
    if (viewer) { viewer.innerHTML = '<p class="mem-placeholder">Loading…</p>'; }
    var url = memItemUrl(memState.type, itemId);
    // Bypass ETag cache for explicit user selection so content is always fresh
    delete memState.etags[url];
    fetchMemJSON(url, function (err, data) {
      if (err) { renderItemContent(null); return; }
      if (data === null) { return; }
      renderItemContent(data);
    });
  }

  function switchType(mtype) {
    if (memState.type === mtype) return;
    memState.type = mtype;
    memState.selectedId = null;
    memState.items = [];
    memState.lastFingerprint = '';
    // Clear ETag so the first fetch after a tab switch always returns full data,
    // not a 304 that would leave the just-cleared list empty.
    delete memState.etags[memTypeUrl(mtype)];
    renderTypeButtons(mtype);
    renderItemList([]);
    renderItemContent(null);
    loadTypeList();
  }

  // ---------------------------------------------------------------------------
  // Polling
  // ---------------------------------------------------------------------------

  function startPolling() {
    if (memState.pollInterval) return;
    memState.pollInterval = setInterval(loadTypeList, 3000);
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    var pane = document.getElementById('memory-pane');
    if (!pane) return;

    pane.querySelectorAll('.mem-type-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchType(btn.dataset.mtype);
      });
    });

    renderTypeButtons(memState.type);
    loadTypeList();
    startPolling();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
