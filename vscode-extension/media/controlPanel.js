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
   * @param {Array<{group: string, skills: string[]}>} groups
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

    for (const { group, skills } of groups) {
      const header = document.createElement('div');
      header.className = 'group-header';
      header.textContent = group;
      skillGroups.appendChild(header);

      const row = document.createElement('div');
      row.className = 'skill-buttons';

      for (const skill of skills) {
        const btn = document.createElement('button');
        btn.className = 'skill-btn';
        btn.dataset.skill = skill;
        btn.textContent = skill;
        btn.disabled = (currentRuntime === 'codex');
        btn.setAttribute('title', '/' + skill);
        row.appendChild(btn);
      }

      skillGroups.appendChild(row);
    }
  }

})();
