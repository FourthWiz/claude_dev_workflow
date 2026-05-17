/* Quoin Architecture Diagram — app.js */
(function () {
  'use strict';

  // ── Palette ────────────────────────────────────────────────────────────────
  const NODE_COLOR = {
    skill:               '#D97757',
    script:              '#7AA9C7',
    memory:              '#A8956F',
    hook:                '#B5635B',
    artifact:            '#9C8AAB',
    adapter:             '#5B7C9D',
    group:               '#5B7C9D',
    'dispatch-mechanism':'#3D5A7A',
    _default:            '#888',
  };

  const EDGE_COLOR = {
    'deploys-to':    '#D97757',
    'dispatches-via':'#7C5B8C',
    reads:           '#9CA3AF',
    writes:          '#4B5563',
    triggers:        '#B85C7A',
    references:      '#C8B89E',
    spawns:          '#5B7C9D',
    invokes:         '#6B7280',
    'grouped-in':    '#E8E6E1',
    _default:        '#ccc',
  };

  const NODE_SHAPE = {
    skill:               'ellipse',
    script:              'rectangle',
    memory:              'hexagon',
    hook:                'diamond',
    artifact:            'tag',
    adapter:             'round-rectangle',
    group:               'round-rectangle',
    'dispatch-mechanism':'pentagon',
    _default:            'ellipse',
  };

  function nodeColor(type) { return NODE_COLOR[type] || NODE_COLOR._default; }
  function edgeColor(kind) { return EDGE_COLOR[kind] || EDGE_COLOR._default; }
  function nodeShape(type) { return NODE_SHAPE[type] || NODE_SHAPE._default; }

  // ── Simple markdown renderer (~40 lines) ───────────────────────────────────
  function renderMarkdown(md) {
    if (!md) return '';
    const lines = md.split('\n');
    const out = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];

      // Headings
      if (line.startsWith('## ')) {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<h3>' + escHtml(line.slice(3)) + '</h3>');
        continue;
      }
      if (line.startsWith('# ')) {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push('<h2>' + escHtml(line.slice(2)) + '</h2>');
        continue;
      }

      // List items
      if (line.startsWith('- ') || line.startsWith('* ')) {
        if (!inList) { out.push('<ul>'); inList = true; }
        out.push('<li>' + inlineFormat(line.slice(2)) + '</li>');
        continue;
      }

      if (inList) { out.push('</ul>'); inList = false; }

      // Blank line
      if (line.trim() === '') {
        out.push('');
        continue;
      }

      // Paragraph
      out.push('<p>' + inlineFormat(line) + '</p>');
    }

    if (inList) out.push('</ul>');
    return out.join('\n');
  }

  function inlineFormat(s) {
    s = escHtml(s);
    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Inline code (already html-escaped so backticks are literal)
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    return s;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Build Cytoscape elements ───────────────────────────────────────────────
  const graphData = window.__GRAPH__;

  const elements = [];
  graphData.nodes.forEach(function (n) {
    elements.push({ data: Object.assign({}, n) });
  });
  graphData.edges.forEach(function (e, i) {
    // Cytoscape requires source/target; graph.json uses from/to
    elements.push({ data: Object.assign({}, e, {
      source: e.from,
      target: e.to,
      id: 'edge-' + i,
    }) });
  });

  // ── Cytoscape styles ───────────────────────────────────────────────────────
  const cyStyle = [
    {
      selector: 'node',
      style: {
        'background-color': function (ele) { return nodeColor(ele.data('type')); },
        'shape': function (ele) { return nodeShape(ele.data('type')); },
        'label': 'data(label)',
        'color': '#1F1F1E',
        'font-size': '16px',
        'font-weight': 'bold',
        'font-family': 'ui-sans-serif, -apple-system, "Helvetica Neue", Arial, sans-serif',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-wrap': 'wrap',
        'text-max-width': '140px',
        'width': 150,
        'height': 80,
        'padding': '12px',
        'border-width': 0,
        'transition-property': 'opacity, border-width, border-color',
        'transition-duration': '150ms',
      }
    },
    {
      selector: 'edge',
      style: {
        'line-color': function (ele) { return edgeColor(ele.data('kind')); },
        'target-arrow-color': function (ele) { return edgeColor(ele.data('kind')); },
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'width': 2.5,
        'opacity': 0.8,
        'transition-property': 'opacity',
        'transition-duration': '150ms',
      }
    },
    {
      selector: 'node.faded, edge.faded',
      style: { 'opacity': 0.12 }
    },
    {
      selector: 'node.highlighted',
      style: {
        'opacity': 1,
        'border-width': 3,
        'border-color': '#D97757',
      }
    },
    {
      selector: 'node.search-match',
      style: {
        'opacity': 1,
        'border-width': 3,
        'border-color': '#D97757',
        'background-color': function (ele) { return nodeColor(ele.data('type')); },
      }
    },
    {
      selector: 'node.search-fade',
      style: { 'opacity': 0.15 }
    },
    {
      selector: 'edge.hidden-by-filter, node.hidden-by-filter',
      style: { 'display': 'none' }
    },
  ];

  // ── Layout configs ─────────────────────────────────────────────────────────
  const LAYOUT_COSE = {
    name: 'cose',
    animate: false,
    idealEdgeLength: 220,
    nodeRepulsion: 40000,
    padding: 60,
    randomize: true,
  };

  const LAYOUT_DAGRE = {
    name: 'dagre',
    animate: false,
    rankDir: 'TB',
    nodeSep: 100,
    rankSep: 140,
    padding: 60,
    nodeDimensionsIncludeLabels: true,
  };

  // ── Tooltip ────────────────────────────────────────────────────────────────
  const tooltip = document.createElement('div');
  tooltip.id = 'cy-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  document.body.appendChild(tooltip);

  // ── Init Cytoscape ─────────────────────────────────────────────────────────
  let currentLayout = 'cose';

  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: elements,
    layout: LAYOUT_COSE,
    style: cyStyle,
    wheelSensitivity: 0.3,
  });

  // Export for Playwright / external testing
  window.cy = cy;

  // ── Detail panel ───────────────────────────────────────────────────────────
  const detailPanel  = document.getElementById('detail-panel');
  const detailTitle  = document.getElementById('detail-title');
  const detailMeta   = document.getElementById('detail-meta');
  const detailContent= document.getElementById('detail-content');
  const detailClose  = document.getElementById('detail-close');

  function showDetail(data) {
    detailTitle.textContent = data.label || data.id;

    const metaParts = [];
    if (data.type)        metaParts.push('<span class="meta-badge meta-type">' + escHtml(data.type) + '</span>');
    if (data.layer)       metaParts.push('<span class="meta-badge meta-layer">' + escHtml(data.layer) + '</span>');
    if (data.tier)        metaParts.push('<span class="meta-badge meta-tier">Tier ' + escHtml(data.tier) + '</span>');
    if (data.source_path) metaParts.push('<code class="meta-path">' + escHtml(data.source_path) + '</code>');
    if (data.summary)     metaParts.push('<p class="meta-summary">' + escHtml(data.summary) + '</p>');
    detailMeta.innerHTML = metaParts.join('');

    detailContent.innerHTML = data.details_md ? renderMarkdown(data.details_md) : '';
    detailPanel.removeAttribute('hidden');
  }

  function hideDetail() {
    detailPanel.setAttribute('hidden', '');
  }

  cy.on('tap', 'node', function (evt) {
    showDetail(evt.target.data());
  });

  cy.on('tap', function (evt) {
    if (evt.target === cy) hideDetail();
  });

  detailClose.addEventListener('click', hideDetail);

  // ── Hover neighborhood highlight ───────────────────────────────────────────
  cy.on('mouseover', 'node', function (evt) {
    const node = evt.target;
    const neighborhood = node.closedNeighborhood();

    cy.elements().addClass('faded');
    neighborhood.removeClass('faded').addClass('highlighted');

    // Tooltip
    const pos = evt.renderedPosition || evt.cyRenderedPosition;
    const containerRect = cy.container().getBoundingClientRect();
    tooltip.textContent = node.data('summary') || node.data('label') || node.id();
    tooltip.style.display = 'block';
    tooltip.style.left = (containerRect.left + pos.x + 14) + 'px';
    tooltip.style.top  = (containerRect.top  + pos.y - 8) + 'px';
  });

  cy.on('mouseout', 'node', function () {
    cy.elements().removeClass('faded').removeClass('highlighted');
    tooltip.style.display = 'none';
  });

  cy.on('mousemove', 'node', function (evt) {
    const pos = evt.renderedPosition || evt.cyRenderedPosition;
    const containerRect = cy.container().getBoundingClientRect();
    tooltip.style.left = (containerRect.left + pos.x + 14) + 'px';
    tooltip.style.top  = (containerRect.top  + pos.y - 8) + 'px';
  });

  // ── Filter state ───────────────────────────────────────────────────────────
  let activeLanes     = null; // null = all; Set = enabled
  let activeTiers     = null;
  let searchQuery     = '';

  function getCheckedValues(selector) {
    const boxes = document.querySelectorAll(selector);
    const vals = new Set();
    let allChecked = true;
    boxes.forEach(function (cb) {
      if (cb.checked) vals.add(cb.value);
      else allChecked = false;
    });
    return allChecked ? null : vals;
  }

  function applyFilters() {
    // 1. Lane + tier visibility
    cy.nodes().forEach(function (node) {
      const layer = node.data('layer') || '';
      const tier  = String(node.data('tier') || 'non-tier');

      let hiddenByLane = false;
      let hiddenByTier = false;

      if (activeLanes !== null) {
        hiddenByLane = !activeLanes.has(layer);
      }
      if (activeTiers !== null) {
        // Only apply tier filter to nodes that actually have a tier or are artifacts
        const effectiveTier = node.data('tier') ? String(node.data('tier')) : 'non-tier';
        hiddenByTier = !activeTiers.has(effectiveTier);
      }

      if (hiddenByLane || hiddenByTier) {
        node.addClass('hidden-by-filter');
      } else {
        node.removeClass('hidden-by-filter');
      }
    });

    // Hide edges where either endpoint is hidden
    cy.edges().forEach(function (edge) {
      if (edge.source().hasClass('hidden-by-filter') ||
          edge.target().hasClass('hidden-by-filter')) {
        edge.addClass('hidden-by-filter');
      } else {
        edge.removeClass('hidden-by-filter');
      }
    });

    // 2. Search highlight
    const q = searchQuery.trim().toLowerCase();
    if (q.length === 0) {
      cy.nodes().removeClass('search-match').removeClass('search-fade');
    } else {
      cy.nodes().forEach(function (node) {
        const label   = (node.data('label') || '').toLowerCase();
        const id      = (node.data('id')    || '').toLowerCase();
        const summary = (node.data('summary') || '').toLowerCase();
        const matches = label.includes(q) || id.includes(q) || summary.includes(q);
        if (matches) {
          node.addClass('search-match').removeClass('search-fade');
        } else {
          node.addClass('search-fade').removeClass('search-match');
        }
      });
    }
  }

  // Lane checkboxes
  document.querySelectorAll('.lane-filter').forEach(function (cb) {
    cb.addEventListener('change', function () {
      activeLanes = getCheckedValues('.lane-filter');
      applyFilters();
    });
  });

  // Tier checkboxes
  document.querySelectorAll('.tier-filter').forEach(function (cb) {
    cb.addEventListener('change', function () {
      activeTiers = getCheckedValues('.tier-filter');
      applyFilters();
    });
  });

  // Search
  const searchInput = document.getElementById('search-input');
  searchInput.addEventListener('input', function () {
    searchQuery = searchInput.value;
    applyFilters();
  });

  function clearFilters() {
    // Reset all checkboxes
    document.querySelectorAll('.lane-filter, .tier-filter').forEach(function (cb) {
      cb.checked = true;
    });
    activeLanes = null;
    activeTiers = null;
    searchQuery = '';
    searchInput.value = '';
    applyFilters();
  }

  // ── Layout toggle ──────────────────────────────────────────────────────────
  const layoutBtn = document.getElementById('layout-toggle');

  layoutBtn.addEventListener('click', function () {
    if (currentLayout === 'cose') {
      currentLayout = 'dagre';
      layoutBtn.textContent = 'Switch to Force-directed';
      cy.layout(LAYOUT_DAGRE).run();
    } else {
      currentLayout = 'cose';
      layoutBtn.textContent = 'Switch to Dagre';
      cy.layout(LAYOUT_COSE).run();
    }
  });

  // ── Help overlay ───────────────────────────────────────────────────────────
  const helpOverlay = document.getElementById('help-overlay');
  const helpClose   = document.getElementById('help-close');
  const helpBackdrop= document.getElementById('help-backdrop');

  function showHelp() { helpOverlay.removeAttribute('hidden'); }
  function hideHelp() { helpOverlay.setAttribute('hidden', ''); }

  helpClose.addEventListener('click', hideHelp);
  helpBackdrop.addEventListener('click', hideHelp);

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      // Only Esc applies inside inputs
      if (e.key === 'Escape') {
        e.target.blur();
        clearFilters();
        hideDetail();
        hideHelp();
      }
      return;
    }

    if (e.key === 'Escape') {
      clearFilters();
      hideDetail();
      hideHelp();
    } else if (e.key === 'h' || e.key === '?') {
      if (!helpOverlay.hasAttribute('hidden')) hideHelp();
      else showHelp();
    }
  });

  // ── Mobile hamburger ───────────────────────────────────────────────────────
  const hamburger = document.getElementById('hamburger');
  const sidebar   = document.getElementById('sidebar');

  hamburger.addEventListener('click', function () {
    sidebar.classList.toggle('sidebar-open');
  });

  // ── Resize handler: re-fit graph ───────────────────────────────────────────
  window.addEventListener('resize', function () {
    cy.resize();
    cy.fit(undefined, 40);
  });

})();
