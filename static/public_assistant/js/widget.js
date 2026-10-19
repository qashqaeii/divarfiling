(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
  }

  function getCsrf() {
    return getCookie('csrftoken');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderMarkdownLite(text) {
    var safe = escapeHtml(text || '');
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/_(.+?)_/g, '<em>$1</em>');
    safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      if (!/^https?:\/\//i.test(url) && !url.startsWith('/')) return label;
      return '<a href="' + escapeHtml(url) + '" rel="noopener noreferrer" target="_blank">' + label + '</a>';
    });
    return safe;
  }

  var root = document.getElementById('pa-root');
  if (!root) return;
  root.hidden = false;

  var fab = document.getElementById('paFab');
  var panel = document.getElementById('paPanel');
  var messagesEl = document.getElementById('paMessages');
  var suggestionsEl = document.getElementById('paSuggestions');
  var form = document.getElementById('paForm');
  var input = document.getElementById('paInput');
  var sendBtn = document.getElementById('paSend');
  var closeBtn = document.getElementById('paClose');
  var newChatBtn = document.getElementById('paNewChat');

  var configUrl = root.dataset.configUrl;
  var chatUrl = root.dataset.chatUrl;
  var feedbackUrl = root.dataset.feedbackUrl;
  var resetUrl = root.dataset.resetUrl;

  var openState = false;
  var configReady = false;

  try {
    openState = sessionStorage.getItem('pa_open') === '1';
  } catch (e) {}

  function setOpen(open) {
    openState = open;
    panel.hidden = !open;
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    try {
      sessionStorage.setItem('pa_open', open ? '1' : '0');
    } catch (e) {}
    if (open) input.focus();
  }

  if (openState) setOpen(true);

  fab.addEventListener('click', function () {
    setOpen(panel.hidden);
  });
  closeBtn.addEventListener('click', function () {
    setOpen(false);
  });

  function appendMessage(role, html, sources) {
    var div = document.createElement('div');
    div.className = 'pa-msg pa-msg--' + (role === 'user' ? 'user' : 'bot');
    div.innerHTML = html;
    if (sources && sources.length) {
      var src = document.createElement('div');
      src.className = 'pa-msg__sources';
      src.innerHTML = 'منابع: ' + sources
        .map(function (l) {
          return '<a href="' + escapeHtml(l.url) + '">' + escapeHtml(l.label || l.url) + '</a>';
        })
        .join(' · ');
      div.appendChild(src);
    }
    if (role === 'bot') {
      var actions = document.createElement('div');
      actions.className = 'pa-msg__actions';
      var copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'pa-btn pa-btn--ghost';
      copy.textContent = 'کپی';
      copy.addEventListener('click', function () {
        navigator.clipboard.writeText(div.innerText || '');
      });
      var up = document.createElement('button');
      up.type = 'button';
      up.className = 'pa-btn pa-btn--ghost';
      up.textContent = 'مفید';
      up.addEventListener('click', function () {
        postFeedback(true);
      });
      var down = document.createElement('button');
      down.type = 'button';
      down.className = 'pa-btn pa-btn--ghost';
      down.textContent = 'نامفید';
      down.addEventListener('click', function () {
        postFeedback(false);
      });
      actions.appendChild(copy);
      actions.appendChild(up);
      actions.appendChild(down);
      div.appendChild(actions);
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function showTyping() {
    var el = document.createElement('div');
    el.className = 'pa-msg pa-msg--bot';
    el.id = 'paTyping';
    el.innerHTML = '<div class="pa-typing"><span></span><span></span><span></span></div>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    var t = document.getElementById('paTyping');
    if (t) t.remove();
  }

  function postFeedback(helpful) {
    fetch(feedbackUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
      },
      body: JSON.stringify({ helpful: helpful, session_id: sessionId }),
    }).catch(function () {});
  }

  function ensureCsrfCookie() {
    if (getCsrf()) {
      return Promise.resolve();
    }
    return fetch(configUrl, { credentials: 'same-origin' }).then(function () {});
  }

  function loadConfig() {
    return fetch(configUrl, { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        configReady = true;
        if (!data.ok) return;
        appendMessage('bot', renderMarkdownLite(data.welcome || ''));
        suggestionsEl.innerHTML = '';
        (data.suggested_questions || []).forEach(function (q) {
          var chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'pa-chip';
          chip.textContent = q;
          chip.addEventListener('click', function () {
            input.value = q;
            form.requestSubmit();
          });
          suggestionsEl.appendChild(chip);
        });
      })
      .catch(function () {});
  }

  loadConfig();

  function sendChat(text) {
    showTyping();
    fetch(chatUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
      },
      body: JSON.stringify({ message: text }),
    })
      .then(function (r) {
        return r.json().then(function (j) {
          return { status: r.status, body: j };
        });
      })
      .then(function (res) {
        hideTyping();
        sendBtn.disabled = false;
        if (!res.body.ok) {
          appendMessage('bot', escapeHtml(res.body.error || 'خطا در پاسخ‌دهی.'));
          return;
        }
        appendMessage('bot', renderMarkdownLite(res.body.answer || ''), res.body.sources || []);
      })
      .catch(function () {
        hideTyping();
        sendBtn.disabled = false;
        appendMessage('bot', 'اتصال برقرار نشد. دوباره تلاش کنید.');
      });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = (input.value || '').trim();
    if (!text) return;
    appendMessage('user', escapeHtml(text));
    input.value = '';
    sendBtn.disabled = true;
    var run = configReady ? ensureCsrfCookie() : loadConfig().then(ensureCsrfCookie);
    run
      .then(function () {
        sendChat(text);
      })
      .catch(function () {
        sendBtn.disabled = false;
        appendMessage('bot', 'خطا در آماده‌سازی امن گفتگو. صفحه را یک‌بار رفرش کنید.');
      });
  });

  newChatBtn.addEventListener('click', function () {
    fetch(resetUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
      },
      body: '{}',
    })
      .then(function (r) {
        return r.json();
      })
      .then(function () {
        messagesEl.innerHTML = '';
        loadConfig();
      });
  });
})();
