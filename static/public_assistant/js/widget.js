(function () {
  'use strict';

  var PANEL_CLOSE_MS = 260;
  var ICON_COPY =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M6 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="1.5"/></svg>';
  var ICON_THUMB_UP =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 11v8a1 1 0 0 0 1 1h2.5a1 1 0 0 0 .95-.68L13 14h5.2a2 2 0 0 0 1.94-2.52l-1.2-5A2 2 0 0 0 17.06 5H14a2 2 0 0 0-2 2v1H9a2 2 0 0 0-2 2v1z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  var ICON_THUMB_DOWN =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M17 13V5a1 1 0 0 0-1-1h-2.5a1 1 0 0 0-.95.68L11 10H5.8a2 2 0 0 0-1.94 2.52l1.2 5A2 2 0 0 0 6.94 19H10a2 2 0 0 0 2-2v-1h3a2 2 0 0 0 2-2v-1z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';

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
  var welcomeEl = document.getElementById('paWelcome');
  var suggestionsEl = document.getElementById('paSuggestions');
  var form = document.getElementById('paForm');
  var input = document.getElementById('paInput');
  var sendBtn = document.getElementById('paSend');
  var closeBtn = document.getElementById('paClose');
  var newChatBtn = document.getElementById('paNewChat');
  var headStatus = document.getElementById('paHeadStatus');
  var jumpBtn = document.getElementById('paJumpEnd');

  var configUrl = root.dataset.configUrl;
  var chatUrl = root.dataset.chatUrl;
  var feedbackUrl = root.dataset.feedbackUrl;
  var resetUrl = root.dataset.resetUrl;

  var configReady = false;
  var hasChat = false;
  var stickToBottom = true;
  var composing = false;
  var panelCloseTimer = null;
  var lastFailedMessage = '';

  function isMobile() {
    return window.matchMedia('(max-width: 640px)').matches;
  }

  function setHeadStatus(text) {
    if (headStatus) headStatus.textContent = text;
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

  function unlockBodyScroll() {
    document.body.classList.remove('pa-chat-open');
    document.body.style.overflow = '';
  }

  function lockBodyScrollIfNeeded() {
    document.body.classList.add('pa-chat-open');
    if (isMobile()) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
  }

  function finalizePanelClose() {
    panel.setAttribute('hidden', '');
    panel.setAttribute('inert', '');
    unlockBodyScroll();
  }

  function setOpen(open) {
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (panelCloseTimer) {
      window.clearTimeout(panelCloseTimer);
      panelCloseTimer = null;
    }

    if (open) {
      panel.removeAttribute('hidden');
      panel.removeAttribute('inert');
      requestAnimationFrame(function () {
        root.classList.add('is-open');
      });
      lockBodyScrollIfNeeded();
      window.setTimeout(function () {
        input.focus();
      }, 280);
    } else {
      root.classList.remove('is-open');
      if (isMobile()) {
        unlockBodyScroll();
      }
      panelCloseTimer = window.setTimeout(finalizePanelClose, PANEL_CLOSE_MS);
      if (!isMobile()) {
        unlockBodyScroll();
      }
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
  input.addEventListener('compositionstart', function () {
    composing = true;
  });
  input.addEventListener('compositionend', function () {
    composing = false;
  });
  input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey && !composing) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });

  function isNearBottom() {
    var threshold = 72;
    return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < threshold;
  }

  function scrollToBottom(smooth) {
    if (typeof messagesEl.scrollTo === 'function') {
      messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    } else {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  function updateJumpButton() {
    if (!jumpBtn) return;
    var show = hasChat && !stickToBottom && !isNearBottom();
    jumpBtn.hidden = !show;
  }

  messagesEl.addEventListener('scroll', function () {
    stickToBottom = isNearBottom();
    updateJumpButton();
  });

  if (jumpBtn) {
    jumpBtn.addEventListener('click', function () {
      stickToBottom = true;
      scrollToBottom(true);
      updateJumpButton();
    });
  }

  function markChatStarted() {
    if (!hasChat) {
      hasChat = true;
      root.classList.add('has-chat');
    }
  }

  function buildSourceChips(sources) {
    if (!sources || !sources.length) return null;
    var wrap = document.createElement('div');
    wrap.className = 'pa-msg__sources';
    var chips = document.createElement('div');
    chips.className = 'pa-msg__source-chips';
    var count = 0;
    sources.forEach(function (l) {
      if (!isAllowedPublicLink(l.url) || count >= 4) return;
      count += 1;
      var a = document.createElement('a');
      a.className = 'pa-source-chip';
      a.href = l.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML =
        '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M10 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4M14 4h6m0 0v6m0-6L10 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        escapeHtml(l.label || l.url);
      chips.appendChild(a);
    });
    if (!chips.children.length) return null;
    wrap.appendChild(chips);
    return wrap;
  }

  function makeActionBtn(label, title, html, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pa-msg__act';
    btn.setAttribute('aria-label', label);
    btn.title = title;
    btn.innerHTML = html;
    btn.addEventListener('click', onClick);
    return btn;
  }

  function appendMessage(role, html, options) {
    options = options || {};
    var div = document.createElement('div');
    var extra = options.variant ? ' pa-msg--' + options.variant : '';
    div.className = 'pa-msg pa-msg--' + (role === 'user' ? 'user' : 'bot') + extra;
    var body = document.createElement('div');
    body.className = 'pa-msg__body';
    body.setAttribute('dir', 'auto');
    if (role === 'user') {
      body.innerHTML = '<p>' + escapeHtml(html) + '</p>';
    } else if (options.variant === 'error' || options.variant === 'limit') {
      body.innerHTML = '<p>' + (options.rawHtml ? html : escapeHtml(html)) + '</p>';
    } else {
      body.innerHTML = html;
    }
    div.appendChild(body);

    var showMeta = role === 'bot' && (!options.variant || options.variant === 'notice');
    if (showMeta) {
      var meta = document.createElement('div');
      meta.className = 'pa-msg__meta';
      var srcEl = buildSourceChips(options.sources);
      if (srcEl) meta.appendChild(srcEl);

      var actions = document.createElement('span');
      actions.className = 'pa-msg__actions';

      var copyBtn = makeActionBtn('کپی پاسخ', 'کپی', ICON_COPY, function () {
        var text = body.innerText || '';
        navigator.clipboard.writeText(text).then(
          function () {
            copyBtn.classList.add('is-copied');
            window.setTimeout(function () {
              copyBtn.classList.remove('is-copied');
            }, 1400);
          },
          function () {}
        );
      });

      var upBtn = makeActionBtn('مفید بود', 'مفید', ICON_THUMB_UP, function () {
        postFeedback(true);
        upBtn.classList.add('is-selected');
        downBtn.classList.remove('is-selected');
      });
      var downBtn = makeActionBtn('مفید نبود', 'نامفید', ICON_THUMB_DOWN, function () {
        postFeedback(false);
        downBtn.classList.add('is-selected');
        upBtn.classList.remove('is-selected');
      });

      actions.appendChild(copyBtn);
      actions.appendChild(upBtn);
      actions.appendChild(downBtn);
      meta.appendChild(actions);
      div.appendChild(meta);
    }

    if (role === 'bot' && options.retryText) {
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

    messagesEl.appendChild(div);
    if (stickToBottom) {
      scrollToBottom(false);
    }
    updateJumpButton();
    return div;
  }

  function showTyping(label) {
    root.classList.add('is-waiting');
    setHeadStatus(label || 'در حال آماده‌سازی پاسخ…');
    var el = document.createElement('div');
    el.className = 'pa-msg pa-msg--bot pa-msg--loading';
    el.id = 'paTyping';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.innerHTML =
      '<div class="pa-loading">' +
      '<span class="pa-loading__avatar" aria-hidden="true">' +
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path fill-rule="evenodd" clip-rule="evenodd" d="M11.2 2.4a.85.85 0 0 1 .84.73l1.05 3.72 3.72 1.05a.85.85 0 0 1 0 1.61l-3.72 1.05-1.05 3.72a.85.85 0 0 1-1.61 0l-1.05-3.72-3.72-1.05a.85.85 0 0 1 0-1.61l3.72-1.05 1.05-3.72a.85.85 0 0 1 .77-.53z" fill="currentColor"/></svg>' +
      '</span>' +
      '<div class="pa-loading__dots" aria-hidden="true"><span></span><span></span><span></span></div>' +
      '<p class="pa-loading__label">' +
      escapeHtml(label || 'در حال آماده‌سازی پاسخ…') +
      '</p>' +
      '</div>';
    messagesEl.appendChild(el);
    if (stickToBottom) scrollToBottom(false);
  }

  function hideTyping() {
    root.classList.remove('is-waiting');
    setHeadStatus('آماده پاسخ‌گویی');
    var t = document.getElementById('paTyping');
    if (!t) return;
    t.classList.add('is-out');
    window.setTimeout(function () {
      if (t.parentNode) t.remove();
    }, 180);
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

  function renderSuggestions(questions) {
    if (!suggestionsEl) return;
    suggestionsEl.innerHTML = '';
    (questions || []).forEach(function (q) {
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
  }

  function loadConfig() {
    return fetch(configUrl, { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        configReady = !!data.ok;
        if (!data.ok) return;
        renderSuggestions(data.suggested_questions || []);
      })
      .catch(function () {});
  }

  loadConfig();

  function sendChat(text) {
    showTyping('در حال آماده‌سازی پاسخ…');
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
        setHeadStatus('در حال دریافت پاسخ…');
        return r.json().then(function (j) {
          return { status: r.status, body: j };
        });
      })
      .then(function (res) {
        hideTyping();
        setSending(false);
        if (res.status === 429) {
          appendMessage(
            'bot',
            'تعداد درخواست‌ها زیاد است. لطفاً یک یا دو دقیقه صبر کنید و دوباره امتحان کنید.',
            { variant: 'limit', retryText: text }
          );
          return;
        }
        if (!res.body.ok) {
          appendMessage('bot', res.body.error || 'خطا در پاسخ‌دهی.', {
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
    if (!text || root.classList.contains('is-sending')) return;
    markChatStarted();
    stickToBottom = true;
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
      .then(function (data) {
        if (!data || !data.ok) return;
        var typing = document.getElementById('paTyping');
        if (typing) typing.remove();
        root.classList.remove('is-waiting', 'is-sending');
        setHeadStatus('آماده پاسخ‌گویی');
        sendBtn.disabled = false;

        Array.prototype.slice.call(messagesEl.querySelectorAll('.pa-msg')).forEach(function (node) {
          node.remove();
        });
        hasChat = false;
        root.classList.remove('has-chat');
        if (welcomeEl && !messagesEl.contains(welcomeEl)) {
          messagesEl.insertBefore(welcomeEl, messagesEl.firstChild);
        }
        stickToBottom = true;
        updateJumpButton();
        loadConfig();
        input.value = '';
        autoResizeInput();
        input.focus();
      });
  });
})();
