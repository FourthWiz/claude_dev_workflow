// Quoin Workflow Tree — webview script (nonce-gated, CSP-compliant, read-only)

(function () {
  'use strict';

  const GLYPHS = { done: '●', active: '►', future: '○' };

  const content = document.getElementById('content');

  function render(msg) {
    if (msg.status !== 'ok' || !Array.isArray(msg.nodes)) {
      const label = msg.message || (msg.status === 'no-task' ? 'No active task.' : 'Workflow unavailable.');
      content.className = 'placeholder';
      content.textContent = label;
      return;
    }

    const task = msg.task || '';
    const stage = msg.stage ? ` · stage ${msg.stage}` : '';
    const header = document.createElement('div');
    header.className = 'task-header';
    header.textContent = task + stage;

    const list = document.createElement('ul');
    list.className = 'node-list';

    for (const node of msg.nodes) {
      const li = document.createElement('li');
      li.className = 'node-row ' + node.state;

      const glyph = document.createElement('span');
      glyph.className = 'glyph ' + node.state;
      glyph.textContent = GLYPHS[node.state] || '○';

      const label = document.createElement('span');
      label.className = 'node-name';
      label.textContent = node.node.replace(/_/g, '_​'); // allow break after underscore

      li.appendChild(glyph);
      li.appendChild(label);

      if (node.critic_rounds) {
        const adorn = document.createElement('span');
        adorn.className = 'adorn';
        adorn.textContent = ' ×' + node.critic_rounds + ' critic';
        li.appendChild(adorn);
      }
      if (node.review_rounds) {
        const adorn = document.createElement('span');
        adorn.className = 'adorn';
        adorn.textContent = ' ×' + node.review_rounds + ' review';
        li.appendChild(adorn);
      }

      list.appendChild(li);
    }

    content.className = '';
    content.innerHTML = '';
    content.appendChild(header);
    content.appendChild(list);
  }

  window.addEventListener('message', function (event) {
    const msg = event.data;
    if (msg && msg.cmd === 'render') {
      render(msg);
    }
  });
}());
