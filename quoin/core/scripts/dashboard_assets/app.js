/* quoin workflow dashboard — vanilla JS SPA, no CDN, no build step */
/* SSE decision: polling-only (T-05 spike skipped per D-10 fallback).
   No EventSource reference; setInterval drives live refresh (~3s). */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var state = {
    includeFinalized: false,
    selectedTask: null,
    pollInterval: null,
    tasks: [],
    activeTask: null,
  };

  // ---------------------------------------------------------------------------
  // API helpers
  // ---------------------------------------------------------------------------

  function tasksUrl(includeFinalized) {
    return '/api/tasks?include_finalized=' + (includeFinalized ? 'true' : 'false');
  }

  function taskDetailUrl(name) {
    return '/api/tasks/' + encodeURIComponent(name);
  }

  function fetchJSON(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url);
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          cb(null, JSON.parse(xhr.responseText));
        } catch (e) {
          cb(new Error('JSON parse error: ' + e.message));
        }
      } else {
        cb(new Error('HTTP ' + xhr.status));
      }
    };
    xhr.onerror = function () { cb(new Error('network error')); };
    xhr.send();
  }

  // ---------------------------------------------------------------------------
  // Cost badge rendering (T-08, D-14)
  // ---------------------------------------------------------------------------

  function badgeText(cost) {
    if (!cost || cost.mode === 'counts') {
      var sessions = cost && cost.total_sessions ? cost.total_sessions : '?';
      return sessions + ' sessions, cost unavailable';
    }
    if (cost.mode === 'usd' && cost.usd != null) {
      return '$' + cost.usd.toFixed(2);
    }
    if (cost.mode === 'tokens' && cost.tokens != null) {
      var m = (cost.tokens / 1e6).toFixed(2);
      return m + 'M tokens';
    }
    return '—';
  }

  function badgeClass(cost) {
    if (!cost || cost.mode === 'counts') return 'cost-badge cost-badge-counts';
    if (cost.mode === 'usd') return 'cost-badge cost-badge-usd';
    if (cost.mode === 'tokens') return 'cost-badge cost-badge-tokens';
    return 'cost-badge cost-badge-counts';
  }

  // ---------------------------------------------------------------------------
  // Phase chip
  // ---------------------------------------------------------------------------

  var PHASE_CSS = {
    discover:  'phase-discover',
    architect: 'phase-architect',
    plan:      'phase-plan',
    implement: 'phase-implement',
    review:    'phase-review',
    done:      'phase-done',
  };

  function phaseChip(phaseLabel, isCurrent) {
    var cssKey = (phaseLabel || '').toLowerCase().replace(/[^a-z]/g, '');
    var cls = PHASE_CSS[cssKey] || 'phase-default';
    var currentCls = isCurrent ? ' current' : '';
    return '<span class="phase-graph-chip ' + cls + currentCls + '">' +
      escHtml(phaseLabel || '—') + '</span>';
  }

  // ---------------------------------------------------------------------------
  // HTML escape
  // ---------------------------------------------------------------------------

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ---------------------------------------------------------------------------
  // Date formatting
  // ---------------------------------------------------------------------------

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString();
    } catch (e) {
      return iso;
    }
  }

  // ---------------------------------------------------------------------------
  // Task table rendering (T-08)
  // ---------------------------------------------------------------------------

  function renderTaskTable(data) {
    state.tasks = data.tasks || [];
    state.activeTask = data.active_task || null;

    var container = document.getElementById('task-table');
    if (!container) return;

    if (!state.tasks.length) {
      container.innerHTML = '<p class="loading">No tasks found under .workflow_artifacts/</p>';
      return;
    }

    var rows = '';
    for (var i = 0; i < state.tasks.length; i++) {
      var t = state.tasks[i];
      var isActive = t.name === state.activeTask;
      var isFinalized = t.finalized || false;
      var rowCls = 'task-row' +
        (isActive ? ' active-row' : '') +
        (isFinalized ? ' finalized-row' : '') +
        (t.name === state.selectedTask ? ' selected-row' : '');

      // Stage display: "n/total" for multi-stage, blank for single
      var stageText = '';
      if (t.stage_info && t.stage_info.total > 1) {
        stageText = '<span class="task-stage">stage ' +
          t.stage_info.current + '/' + t.stage_info.total + '</span>';
      }

      // Phase label
      var phaseLabel = t.phase_label || t.phase || '—';
      var phaseCssKey = (phaseLabel).toLowerCase().replace(/[^a-z]/g, '');
      var phaseCls = PHASE_CSS[phaseCssKey] || 'phase-default';
      var chipHtml = '<span class="phase-chip ' + phaseCls + '">' +
        escHtml(phaseLabel) + '</span>';

      // Cost badge
      var badgeHtml = '<span class="' + badgeClass(t.cost) + '">' +
        escHtml(badgeText(t.cost)) + '</span>';

      // Last activity
      var lastAct = fmtDate(t.last_activity);

      rows += '<tr class="' + rowCls + '" data-name="' + escHtml(t.name) + '">' +
        '<td><div class="task-name">' + escHtml(t.name) + '</div>' + stageText + '</td>' +
        '<td>' + chipHtml + '</td>' +
        '<td>' + badgeHtml + '</td>' +
        '<td class="date-label">' + escHtml(lastAct) + '</td>' +
        '</tr>';
    }

    container.innerHTML =
      '<table class="task-table">' +
      '<thead><tr>' +
      '<th>Task</th><th>Phase</th><th>Cost</th><th>Last activity</th>' +
      '</tr></thead>' +
      '<tbody>' + rows + '</tbody>' +
      '</table>';

    // Attach click handlers
    var trs = container.querySelectorAll('tr.task-row');
    for (var j = 0; j < trs.length; j++) {
      trs[j].addEventListener('click', onTaskRowClick);
    }
  }

  function onTaskRowClick(e) {
    var tr = e.currentTarget;
    var name = tr.getAttribute('data-name');
    if (!name) return;
    state.selectedTask = name;
    // Re-render table to update selected highlight
    refreshTaskList();
    loadTaskDetail(name);
  }

  // ---------------------------------------------------------------------------
  // Detail pane rendering (T-09)
  // ---------------------------------------------------------------------------

  function renderDetailPane(detail) {
    var pane = document.getElementById('detail-pane');
    if (!pane) return;

    var html = '<div class="detail-title">' + escHtml(detail.name || '—') + '</div>';

    // Meta line
    var meta = [];
    if (detail.phase_label) meta.push('Phase: ' + escHtml(detail.phase_label));
    if (detail.linear) meta.push('Linear: ' + escHtml(detail.linear));
    html += '<div class="detail-meta">' + meta.join(' · ') + '</div>';

    // Phase graph (pipeline phases with active one marked)
    html += '<div class="detail-section"><h3>Pipeline</h3><div class="phase-graph">';
    var allPhases = ['discover', 'architect', 'plan', 'implement', 'review', 'done'];
    var currentPhase = (detail.phase_label || '').toLowerCase();
    for (var pi = 0; pi < allPhases.length; pi++) {
      var ph = allPhases[pi];
      var isCurrent = ph === currentPhase || (
        ph === 'implement' && (currentPhase === 'in-progress' || currentPhase === 'in_progress')
      );
      html += '<div class="phase-graph-item">' +
        '<div class="phase-graph-chip ' + (PHASE_CSS[ph] || 'phase-default') +
        (isCurrent ? ' current' : '') + '">' + ph + '</div></div>';
      if (pi < allPhases.length - 1) {
        html += '<span class="phase-graph-arrow">›</span>';
      }
    }
    html += '</div></div>';

    // Cost breakdown by_phase (D-14: must branch on cost.mode)
    var cost = detail.cost;
    if (cost && cost.by_phase && Object.keys(cost.by_phase).length > 0) {
      html += '<div class="detail-section"><h3>Cost by phase</h3>';
      html += '<table class="by-phase-table"><thead><tr><th>Phase</th><th>Cost</th></tr></thead><tbody>';
      var byPhase = cost.by_phase;
      var phases = Object.keys(byPhase).sort();
      for (var bpi = 0; bpi < phases.length; bpi++) {
        var bph = phases[bpi];
        var val = byPhase[bph];
        var cellText;
        if (cost.mode === 'counts') {
          // val is plain int (flat shape, counts mode)
          cellText = (typeof val === 'number' ? val : '?') + ' sessions';
        } else if (cost.mode === 'usd') {
          // val is {"usd": float} (nested shape)
          var usdVal = (val && val.usd != null) ? val.usd.toFixed(2) : '?';
          cellText = '$' + usdVal;
        } else if (cost.mode === 'tokens') {
          // val is {"tokens": int} (nested shape)
          var tokVal = (val && val.tokens != null) ? (val.tokens / 1e6).toFixed(2) : '?';
          cellText = tokVal + 'M tokens';
        } else {
          cellText = JSON.stringify(val);
        }
        html += '<tr><td>' + escHtml(bph) + '</td><td>' + escHtml(cellText) + '</td></tr>';
      }
      html += '</tbody></table></div>';
    }

    // Stages list
    if (detail.stages && detail.stages.length > 0) {
      html += '<div class="detail-section"><h3>Stages</h3><ul class="stage-list">';
      for (var si = 0; si < detail.stages.length; si++) {
        var st = detail.stages[si];
        var stPhaseLabel = st.phase_label || st.phase || '—';
        var stPhaseCls = PHASE_CSS[(stPhaseLabel).toLowerCase()] || 'phase-default';
        html += '<li><span>Stage ' + escHtml(String(st.stage || si + 1)) + '</span>' +
          '<span class="phase-chip ' + stPhaseCls + '">' + escHtml(stPhaseLabel) + '</span></li>';
      }
      html += '</ul></div>';
    }

    // Ledger rows (session metadata)
    var rows = detail.ledger_rows || [];
    if (rows.length > 0) {
      html += '<div class="detail-section"><h3>Sessions (' + rows.length + ')</h3>';
      html += '<table class="by-phase-table"><thead><tr><th>Date</th><th>Phase</th><th>Model/effort</th><th>Note</th></tr></thead><tbody>';
      var maxRows = Math.min(rows.length, 20);
      for (var ri = 0; ri < maxRows; ri++) {
        var row = rows[ri];
        // Note: the key is model_or_effort, NOT model
        html += '<tr>' +
          '<td>' + escHtml(row.date || '—') + '</td>' +
          '<td>' + escHtml(row.phase || '—') + '</td>' +
          '<td>' + escHtml(row.model_or_effort || '—') + '</td>' +
          '<td>' + escHtml(row.note || '') + '</td>' +
          '</tr>';
      }
      if (rows.length > 20) {
        html += '<tr><td colspan="4" style="color:#888;font-style:italic">… and ' +
          (rows.length - 20) + ' more</td></tr>';
      }
      html += '</tbody></table></div>';
    }

    // Dates
    html += '<div class="detail-section"><h3>Activity</h3>';
    html += '<table class="by-phase-table"><tbody>';
    html += '<tr><td class="date-label">First activity</td><td class="date-value">' +
      escHtml(fmtDate(detail.first_activity)) + '</td></tr>';
    html += '<tr><td class="date-label">Last activity</td><td class="date-value">' +
      escHtml(fmtDate(detail.last_activity)) + '</td></tr>';
    html += '</tbody></table></div>';

    pane.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // Data loading + polling (T-09: polling unconditional, D-10)
  // ---------------------------------------------------------------------------

  function refreshTaskList() {
    fetchJSON(tasksUrl(state.includeFinalized), function (err, data) {
      if (err) {
        console.warn('dashboard: task list fetch error:', err.message);
        return;
      }
      renderTaskTable(data);
    });
  }

  function loadTaskDetail(name) {
    var pane = document.getElementById('detail-pane');
    if (pane) pane.innerHTML = '<p class="loading">Loading…</p>';

    fetchJSON(taskDetailUrl(name), function (err, data) {
      if (err) {
        if (pane) pane.innerHTML = '<p class="error-msg">Error loading task: ' +
          escHtml(err.message) + '</p>';
        return;
      }
      renderDetailPane(data);
    });
  }

  function startPolling() {
    if (state.pollInterval) clearInterval(state.pollInterval);
    state.pollInterval = setInterval(function () {
      refreshTaskList();
      if (state.selectedTask) {
        loadTaskDetail(state.selectedTask);
      }
    }, 3000);
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    // Wire up finalized toggle
    var toggle = document.getElementById('show-finalized');
    if (toggle) {
      toggle.addEventListener('change', function () {
        state.includeFinalized = toggle.checked;
        refreshTaskList();
      });
    }

    // Initial load
    refreshTaskList();

    // Start polling (~3s, unconditional — polling-only per D-10)
    startPolling();
  }

  // Run after DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
