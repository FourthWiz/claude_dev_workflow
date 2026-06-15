// Quoin Control Panel — webview script (nonce-gated, CSP-compliant)
// No inline event handlers. All wiring done here with addEventListener.
// Communicates with the extension host via acquireVsCodeApi().postMessage.

(function () {
  'use strict';

  const vscode = acquireVsCodeApi();

  // ── State ──────────────────────────────────────────────────────────────────

  let selectedSkill = null;       // string | null
  let selectedSessionId = null;   // string | null (UUID)
  let currentRuntime = 'claude';  // 'claude' | 'codex'
  let nextSkill = null;           // string | null — next-step highlight from WorkflowTree

  // ── DOM refs ───────────────────────────────────────────────────────────────

  const sessionSelect = document.getElementById('session-select');
  const codexNote    = document.getElementById('codex-note');
  const skillGroups  = document.getElementById('skill-groups');
  const promptArea   = document.getElementById('prompt');
  const runBtn       = document.getElementById('run-btn');

  // ── Session selector ───────────────────────────────────────────────────────

  sessionSelect.addEventListener('change', () => {
    const opt = sessionSelect.options[sessionSelect.selectedIndex];
    selectedSessionId = opt ? opt.value : null;
    // Notify host of the active session change so it can push runtime info
    if (selectedSessionId) {
      vscode.postMessage({ cmd: 'selectSession', sessionId: selectedSessionId });
    }
  });

  // ── Skill button wiring (delegated — buttons are added dynamically) ────────

  skillGroups.addEventListener('click', (e) => {
    const btn = e.target.closest('.skill-btn');
    if (!btn || btn.disabled) return;

    // Toggle selection
    if (btn.dataset.skill === selectedSkill) {
      // Deselect
      selectedSkill = null;
      btn.classList.remove('active');
    } else {
      // Select new
      document.querySelectorAll('.skill-btn.active').forEach(b => b.classList.remove('active'));
      selectedSkill = btn.dataset.skill;
      btn.classList.add('active');
    }
  });

  // ── Run button ─────────────────────────────────────────────────────────────

  runBtn.addEventListener('click', () => {
    const prompt = promptArea.value;
    if (!selectedSessionId) {
      return; // No session selected — button should be disabled but guard anyway
    }
    vscode.postMessage({
      cmd: 'run',
      skill: currentRuntime === 'codex' ? null : selectedSkill,
      prompt,
      sessionId: selectedSessionId,
    });
  });

  // ── Message handler (host → webview) ──────────────────────────────────────

  window.addEventListener('message', (event) => {
    const msg = event.data;
    if (!msg || typeof msg.cmd !== 'string') return;

    switch (msg.cmd) {
      case 'sessions':
        renderSessionList(msg.sessions);
        break;
      case 'session':
        updateSessionRuntime(msg.sessionId, msg.runtime);
        break;
      case 'skills':
        renderSkillGroups(msg.groups);
        break;
      case 'highlight':
        nextSkill = msg.nextSkill;
        applyHighlight();
        break;
    }
  });

  // ── Render helpers ─────────────────────────────────────────────────────────

  /**
   * Render the session <select> options.
   * Each option value is the session UUID (id), not the label.
   *
   * @param {Array<{id: string, label: string, runtime: string}>} sessions
   */
  function renderSessionList(sessions) {
    const prevId = selectedSessionId;
    sessionSelect.innerHTML = '';

    if (!sessions || sessions.length === 0) {
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '(no sessions)';
      placeholder.disabled = true;
      placeholder.selected = true;
      sessionSelect.appendChild(placeholder);
      selectedSessionId = null;
      runBtn.disabled = true;
      return;
    }

    runBtn.disabled = false;
    let restored = false;

    for (const s of sessions) {
      const opt = document.createElement('option');
      opt.value = s.id;          // UUID — matches SessionManager.get(id)
      opt.textContent = s.label; // display name
      sessionSelect.appendChild(opt);
      if (s.id === prevId) {
        opt.selected = true;
        restored = true;
      }
    }

    if (!restored) {
      sessionSelect.selectedIndex = 0;
    }

    // Update state from the currently-selected option
    const sel = sessionSelect.options[sessionSelect.selectedIndex];
    if (sel && sel.value) {
      selectedSessionId = sel.value;
      // Notify host so it can push runtime info
      vscode.postMessage({ cmd: 'selectSession', sessionId: selectedSessionId });
    }
  }

  /**
   * Update skill-button disabled state based on the active session's runtime.
   *
   * @param {string} sessionId
   * @param {'claude'|'codex'} runtime
   */
  function updateSessionRuntime(sessionId, runtime) {
    if (sessionId !== selectedSessionId) return;
    currentRuntime = runtime;
    const isCodex = runtime === 'codex';

    // Show/hide Codex note
    codexNote.classList.toggle('visible', isCodex);

    // Enable/disable skill buttons
    document.querySelectorAll('.skill-btn').forEach(btn => {
      btn.disabled = isCodex;
      if (isCodex) {
        btn.classList.remove('active');
      }
    });

    if (isCodex) {
      selectedSkill = null;
    }
  }

  /**
   * Render grouped skill buttons.
   *
   * Curated groups (Planning, Execution, Lifecycle) render as a header div +
   * skill-buttons row, always expanded.
   *
   * The 'Other' group renders inside a native <details> element (collapsed by
   * default) with a <summary> acting as the toggle header. This is CSP-safe
   * (no inline handlers, no JS toggle logic needed).
   *
   * Each button uses entry.label for display and entry.command for injection
   * (data-skill attribute). The click delegation and applyHighlight logic are
   * unchanged — both work correctly inside <details>.
   *
   * @param {Array<{group: string, entries: Array<{command: string, label: string}>}>} groups
   */
  function renderSkillGroups(groups) {
    skillGroups.innerHTML = '';
    selectedSkill = null; // reset selection on re-render

    if (!groups || groups.length === 0) {
      const msg = document.createElement('div');
      msg.className = 'no-sessions';
      msg.textContent = 'No skills found in ~/.claude/skills/';
      skillGroups.appendChild(msg);
      return;
    }

    for (const { group, entries } of groups) {
      const safeEntries = entries || []; // R-03: defensive against stale-shape message

      if (group === 'Other') {
        // Collapsible Other group using native <details> (CSP-safe, no JS toggle)
        const details = document.createElement('details');
        details.className = 'skill-group-other';
        // No 'open' attribute → collapsed by default

        const summary = document.createElement('summary');
        summary.className = 'group-summary';
        summary.textContent = group;
        details.appendChild(summary);

        const row = document.createElement('div');
        row.className = 'skill-buttons';

        for (const entry of safeEntries) {
          const btn = document.createElement('button');
          btn.className = 'skill-btn';
          btn.dataset.skill = entry.command; // command used for injection + highlight matching
          btn.textContent = entry.label;     // pretty label shown to user
          btn.disabled = (currentRuntime === 'codex');
          btn.setAttribute('title', '/' + entry.command);
          row.appendChild(btn);
        }

        details.appendChild(row);
        skillGroups.appendChild(details);
      } else {
        // Curated group: always-expanded header + button row
        const header = document.createElement('div');
        header.className = 'group-header';
        header.textContent = group;
        skillGroups.appendChild(header);

        const row = document.createElement('div');
        row.className = 'skill-buttons';

        for (const entry of safeEntries) {
          const btn = document.createElement('button');
          btn.className = 'skill-btn';
          btn.dataset.skill = entry.command; // command used for injection + highlight matching
          btn.textContent = entry.label;     // pretty label shown to user
          btn.disabled = (currentRuntime === 'codex');
          btn.setAttribute('title', '/' + entry.command);
          row.appendChild(btn);
        }

        skillGroups.appendChild(row);
      }
    }

    applyHighlight();
  }

  /**
   * Apply the next-step highlight outline to the matching skill button.
   * Removes .next-btn from all buttons, then adds it to the one matching nextSkill.
   */
  function applyHighlight() {
    document.querySelectorAll('.skill-btn.next-btn').forEach(b => b.classList.remove('next-btn'));
    if (!nextSkill) return;
    const btn = skillGroups.querySelector('[data-skill="' + nextSkill + '"]');
    if (btn) {
      btn.classList.add('next-btn');
    }
  }

})();
