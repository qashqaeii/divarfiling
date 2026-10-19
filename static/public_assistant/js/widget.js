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

  function stripInternalCitations(text) {
    return String(text || '')
      .replace(/\s*\[\d+\]/g, '')
      .replace(/^منابع:\s*$/gm, '')
      .trim();
  }

  function renderInline(safe) {
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/_(.+?)_/g, '<em>$1</em>');
    safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      if (!isAllowedPublicLink(url)) return escapeHtml(label);
      var href = escapeHtml(url);
      var dirAttr = /^https?:\/\//i.test(url) ? ' dir="ltr"' : '';
      return (
        '<a href="' +
        href +
        '" rel="noopener noreferrer" target="_blank"' +
        dirAttr +
        '>' +
        escapeHtml(label) +
        '</a>'
      );
    });
    return safe;
  }

  function renderBlock(block) {
    var lines = block.split(/\n/).map(function (l) {
      return l.trim();
    }).filter(Boolean);
    if (!lines.length) return '';
    var html = [];
    var inList = false;
    var listType = null;

    function closeList() {
      if (inList) {
        html.push(listType === 'ol' ? '</ol>' : '</ul>');
        inList = false;
        listType = null;
      }
    }

    lines.forEach(function (trimmed) {
      if (/^###\s+/.test(trimmed)) {
        closeList();
        html.push('<h3 class="pa-md-h3">' + renderInline(escapeHtml(trimmed.replace(/^###\s+/, ''))) + '</h3>');
        return;
      }
      if (/^##\s+/.test(trimmed)) {
        closeList();
        html.push('<h3 class="pa-md-h3">' + renderInline(escapeHtml(trimmed.replace(/^##\s+/, ''))) + '</h3>');
        return;
      }
      if (/^>\s+/.test(trimmed) || /^نکته:/.test(trimmed)) {
        closeList();
        var tip = trimmed.replace(/^>\s+/, '').replace(/^نکته:\s*/, 'نکته: ');
        html.push('<blockquote class="pa-md-tip">' + renderInline(escapeHtml(tip)) + '</blockquote>');
        return;
      }
      var ul = /^[-*•]\s+(.+)$/.exec(trimmed);
      if (ul) {
        if (!inList || listType !== 'ul') {
          closeList();
          html.push('<ul>');
          inList = true;
          listType = 'ul';
        }
        html.push('<li>' + renderInline(escapeHtml(ul[1])) + '</li>');
        return;
      }
      var ol = /^\d+[.)]\s+(.+)$/.exec(trimmed);
      if (ol) {
        if (!inList || listType !== 'ol') {
          closeList();
          html.push('<ol>');
          inList = true;
          listType = 'ol';
        }
        html.push('<li>' + renderInline(escapeHtml(ol[1])) + '</li>');
        return;
      }
      closeList();
      html.push('<p>' + renderInline(escapeHtml(trimmed)) + '</p>');
    });
    closeList();
    return html.join('');
  }

  function renderMarkdownLite(text) {
    var raw = stripInternalCitations(text || '');
    var blocks = raw.split(/\n\s*\n/);
    if (blocks.length === 1 && blocks[0].indexOf('\n') === -1) {
      return renderBlock(blocks[0]);
    }
    return blocks
      .map(function (b) {
        return renderBlock(b);
      })
      .filter(Boolean)
      .join('');
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
  var lastFailedMessage = '';

  function isMobile() {
    return window.matchMedia('(max-width: 640px)').matches;
  }

  function setSending(on) {
    if (on) {
      root.classList.add('is-sending');
      sendBtn.disabled = true;
    } else {
      root.classList.remove('is-sending');
      sendBtn.disabled = false;
    }
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
  input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });

  function buildSourceChips(sources) {
    if (!sources || !sources.length) return null;
    var wrap = document.createElement('div');
    wrap.className = 'pa-msg__sources';
    var label = document.createElement('p');
    label.className = 'pa-msg__sources-label';
    label.textContent = 'راهنماهای مرتبط';
    wrap.appendChild(label);
    var chips = document.createElement('div');
    chips.className = 'pa-msg__source-chips';
    sources.forEach(function (l) {
      if (!isAllowedPublicLink(l.url)) return;
      var a = document.createElement('a');
      a.className = 'pa-source-chip';
      a.href = l.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML =
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M10 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4M14 4h6m0 0v6m0-6L10 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        escapeHtml(l.label || l.url);
      chips.appendChild(a);
    });
    if (!chips.children.length) return null;
    wrap.appendChild(chips);
    return wrap;
  }

  function appendMessage(role, html, options) {
    options = options || {};
    var div = document.createElement('div');
    var extra = options.variant ? ' pa-msg--' + options.variant : '';
    if (options.welcome) extra += ' pa-msg--welcome';
    div.className = 'pa-msg pa-msg--' + (role === 'user' ? 'user' : 'bot') + extra;
    var body = document.createElement('div');
    body.className = 'pa-msg__body';
    body.setAttribute('dir', 'auto');
    body.innerHTML = role === 'user' ? '<p>' + escapeHtml(html) + '</p>' : html;
    div.appendChild(body);

    if (role === 'bot') {
      var meta = document.createElement('div');
      meta.className = 'pa-msg__meta';
      var srcEl = buildSourceChips(options.sources);
      if (srcEl) meta.appendChild(srcEl);

      var actions = document.createElement('span');
      actions.className = 'pa-msg__actions';
      var copy = document.createElement('button');
      copy.type = 'button';
      copy.textContent = 'کپی';
      copy.setAttribute('aria-label', 'کپی پاسخ');
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

      if (options.retryText) {
        var retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'pa-msg__retry';
        retry.textContent = 'تلاش دوباره';
        retry.addEventListener('click', function () {
          input.value = options.retryText;
          autoResizeInput();
          form.requestSubmit();
        });
        body.appendChild(retry);
      }
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function showTyping() {
    root.classList.add('is-waiting');
    var el = document.createElement('div');
    el.className = 'pa-msg pa-msg--bot pa-msg--loading';
    el.id = 'paTyping';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-label', 'در حال تولید پاسخ');
    el.innerHTML =
      '<div class="pa-loading">' +
      '<div class="pa-loading__dots" aria-hidden="true"><span></span><span></span><span></span></div>' +
      '<div class="pa-loading__bars" aria-hidden="true"><span></span><span></span><span></span></div>' +
      '<p class="pa-loading__label">در حال نوشتن پاسخ…</p>' +
      '</div>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    root.classList.remove('is-waiting');
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
          appendMessage('bot', renderMarkdownLite(data.welcome || ''), { welcome: true });
          welcomeLoaded = true;
        }
        suggestionsEl.innerHTML = '';
        (data.suggested_questions || []).forEach(function (q) {
          var chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'pa-chip';
          chip.setAttribute('role', 'listitem');
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
        setSending(false);
        if (res.status === 429) {
          appendMessage('bot', escapeHtml('تعداد درخواست‌ها زیاد است. لطفاً یک یا دو دقیقه صبر کنید و دوباره امتحان کنید.'), {
            variant: 'limit',
            retryText: text,
          });
          return;
        }
        if (!res.body.ok) {
          appendMessage('bot', escapeHtml(res.body.error || 'خطا در پاسخ‌دهی.'), {
            variant: 'error',
            retryText: text,
          });
          return;
        }
        var variant = res.body.low_confidence ? 'notice' : '';
        appendMessage('bot', renderMarkdownLite(res.body.answer || ''), {
          sources: res.body.sources || [],
          variant: variant,
        });
        lastFailedMessage = '';
      })
      .catch(function () {
        hideTyping();
        setSending(false);
        lastFailedMessage = text;
        appendMessage('bot', 'اتصال برقرار نشد. اتصال اینترنت را بررسی کنید.', {
          variant: 'error',
          retryText: text,
        });
      });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = (input.value || '').trim();
    if (!text) return;
    hideSuggestionsAfterChat();
    appendMessage('user', text);
    input.value = '';
    autoResizeInput();
    setSending(true);
    var run = configReady ? ensureCsrfCookie() : loadConfig().then(ensureCsrfCookie);
    run
      .then(function () {
        sendChat(text);
      })
      .catch(function () {
        setSending(false);
        appendMessage('bot', 'خطا در آماده‌سازی امن گفتگو. صفحه را یک‌بار رفرش کنید.', { variant: 'error' });
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
