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

  var PA_ALLOWED_HOSTS = ['divarfiling.ir', 'www.divarfiling.ir'];

  function isAllowedPublicLink(url) {
    if (!url) return false;
    url = String(url).trim();
    if (/[\n\r\0<>"]/.test(url)) return false;
    if (url.charAt(0) === '/') {
      return url.indexOf('//') !== 0 && url.split('?')[0].indexOf('..') === -1;
    }
    try {
      var parsed = new URL(url, window.location.origin);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
      if (parsed.username || parsed.password) return false;
      var host = parsed.hostname.toLowerCase();
      if (PA_ALLOWED_HOSTS.indexOf(host) !== -1) return true;
      var pageHost = (window.location.hostname || '').toLowerCase();
      if (pageHost === 'localhost' || pageHost === '127.0.0.1') {
        return host === 'localhost' || host === '127.0.0.1';
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  function renderMarkdownLite(text) {
    var safe = escapeHtml(text || '');
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/_(.+?)_/g, '<em>$1</em>');
    safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      if (!isAllowedPublicLink(url)) return escapeHtml(label);
      var href = escapeHtml(url);
      return '<a href="' + href + '" rel="noopener noreferrer" target="_blank">' + escapeHtml(label) + '</a>';
    });
    return safe;
  }

  var root = document.getElementById('pa-root');
  if (!root) return;
  root.hidden = false;

  var backdrop = document.getElementById('paBackdrop');
  var fab = document.getElementById('paFab');
  var panel = document.getElementById('paPanel');
  var messagesEl = document.getElementById('paMessages');
  var suggestionsEl = document.getElementById('paSuggestions');
  var suggestionsWrap = document.getElementById('paSuggestionsWrap');
  var form = document.getElementById('paForm');
  var input = document.getElementById('paInput');
  var sendBtn = document.getElementById('paSend');
  var closeBtn = document.getElementById('paClose');
  var newChatBtn = document.getElementById('paNewChat');

  var configUrl = root.dataset.configUrl;
  var chatUrl = root.dataset.chatUrl;
  var feedbackUrl = root.dataset.feedbackUrl;
  var resetUrl = root.dataset.resetUrl;

  var configReady = false;
  var welcomeLoaded = false;

  function isMobile() {
    return window.matchMedia('(max-width: 640px)').matches;
  }

  function setOpen(open) {
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      panel.removeAttribute('hidden');
      root.classList.add('is-open');
    } else {
      root.classList.remove('is-open');
      panel.setAttribute('hidden', '');
    }
    if (open) {
      document.body.classList.add('pa-chat-open');
      if (isMobile()) {
        document.body.style.overflow = 'hidden';
      }
      window.setTimeout(function () {
        input.focus();
      }, 280);
    } else {
      document.body.classList.remove('pa-chat-open');
      document.body.style.overflow = '';
    }
    try {
      sessionStorage.setItem('pa_open', open ? '1' : '0');
    } catch (e) {}
  }

  try {
    if (sessionStorage.getItem('pa_open') === '1') {
      setOpen(true);
    }
  } catch (e) {}

  fab.addEventListener('click', function () {
    setOpen(true);
  });
  closeBtn.addEventListener('click', function () {
    setOpen(false);
  });
  backdrop.addEventListener('click', function () {
    setOpen(false);
  });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && root.classList.contains('is-open')) {
      setOpen(false);
    }
  });

  function autoResizeInput() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }

  input.addEventListener('input', autoResizeInput);

  function appendMessage(role, html, sources) {
    var div = document.createElement('div');
    div.className = 'pa-msg pa-msg--' + (role === 'user' ? 'user' : 'bot');
    div.innerHTML = html;
    if (role === 'bot') {
      var meta = document.createElement('div');
      meta.className = 'pa-msg__meta';
      if (sources && sources.length) {
        var src = document.createElement('span');
        src.className = 'pa-msg__sources';
        src.innerHTML = sources
          .map(function (l) {
            if (!isAllowedPublicLink(l.url)) return '';
            return '<a href="' + escapeHtml(l.url) + '">' + escapeHtml(l.label || l.url) + '</a>';
          })
          .filter(Boolean)
          .join(' · ');
        if (src.innerHTML) meta.appendChild(src);
      }
      var actions = document.createElement('span');
      actions.className = 'pa-msg__actions';
      var copy = document.createElement('button');
      copy.type = 'button';
      copy.textContent = 'کپی';
      copy.addEventListener('click', function () {
        navigator.clipboard.writeText(div.innerText || '');
      });
      var up = document.createElement('button');
      up.type = 'button';
      up.textContent = 'مفید';
      up.addEventListener('click', function () {
        postFeedback(true);
      });
      var down = document.createElement('button');
      down.type = 'button';
      down.textContent = 'نامفید';
      down.addEventListener('click', function () {
        postFeedback(false);
      });
      actions.appendChild(copy);
      actions.appendChild(up);
      actions.appendChild(down);
      meta.appendChild(actions);
      div.appendChild(meta);
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
      body: JSON.stringify({ helpful: helpful }),
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
        if (!welcomeLoaded) {
          appendMessage('bot', renderMarkdownLite(data.welcome || ''));
          welcomeLoaded = true;
        }
        suggestionsEl.innerHTML = '';
        (data.suggested_questions || []).forEach(function (q) {
          var chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'pa-chip';
          chip.textContent = q;
          chip.addEventListener('click', function () {
            input.value = q;
            autoResizeInput();
            form.requestSubmit();
          });
          suggestionsEl.appendChild(chip);
        });
      })
      .catch(function () {});
  }

  loadConfig();

  function hideSuggestionsAfterChat() {
    if (suggestionsWrap) {
      suggestionsWrap.style.display = 'none';
    }
  }

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
    hideSuggestionsAfterChat();
    appendMessage('user', escapeHtml(text));
    input.value = '';
    autoResizeInput();
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
        welcomeLoaded = false;
        if (suggestionsWrap) {
          suggestionsWrap.style.display = '';
        }
        loadConfig();
      });
  });
})();
