(function () {
  'use strict';

  var PANEL_CLOSE_MS = 260;
  var DOCK_POS_KEY = 'pa_dock_pos';
  var DRAG_THRESHOLD = 6;
  var DOCK_MARGIN = 12;
  var ICON_COPY =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M6 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="1.5"/></svg>';
  var ICON_THUMB_UP =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 11v8a1 1 0 0 0 1 1h2.5a1 1 0 0 0 .95-.68L13 14h5.2a2 2 0 0 0 1.94-2.52l-1.2-5A2 2 0 0 0 17.06 5H14a2 2 0 0 0-2 2v1H9a2 2 0 0 0-2 2v1z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  var ICON_THUMB_DOWN =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M17 13V5a1 1 0 0 0-1-1h-2.5a1 1 0 0 0-.95.68L11 10H5.8a2 2 0 0 0-1.94 2.52l1.2 5A2 2 0 0 0 6.94 19H10a2 2 0 0 0 2-2v-1h3a2 2 0 0 0 2-2v-1z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  var ICON_CHIP =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  var ICON_LINK_EXT =
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M10 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4M14 4h6m0 0v6m0-6L10 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_LINK_CART =
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 6h15l-1.5 9h-12L6 6zM9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  var ICON_LINK_WORKSPACE =
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="3" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/></svg>';
  var ICON_LINK_SUPPORT =
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M9.5 9.5a2.5 2.5 0 0 1 4.6 1.2c0 1.5-2.1 1.8-2.1 3.3V15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="17.5" r=".75" fill="currentColor"/></svg>';
  var ICON_LINK_LICENSE =
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 11V7a5 5 0 0 1 10 0v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><rect x="5" y="11" width="14" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/></svg>';
  var ICON_CLOCK =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.5"/><path d="M12 8v4.2l2.6 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_ALERT =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8.5v4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="16.2" r=".85" fill="currentColor"/><path d="M10.3 5.2 4.8 16a1.5 1.5 0 0 0 1.3 2.2h11.8a1.5 1.5 0 0 0 1.3-2.2L13.7 5.2a1.5 1.5 0 0 0-2.6 0z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';

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

  function linkIconFor(label, url) {
    var hay = (String(label) + ' ' + String(url)).toLowerCase();
    if (/خرید|اشتراک|shop|checkout|pricing|plan/.test(hay)) return ICON_LINK_CART;
    if (/میزکار|workspace|mizkar|crm/.test(hay)) return ICON_LINK_WORKSPACE;
    if (/پشتیبانی|support|تماس/.test(hay)) return ICON_LINK_SUPPORT;
    if (/لایسنس|license|فعال/.test(hay)) return ICON_LINK_LICENSE;
    return ICON_LINK_EXT;
  }

  function renderInline(safe) {
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/_(.+?)_/g, '<em>$1</em>');
    safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      if (!isAllowedPublicLink(url)) return escapeHtml(label);
      var href = escapeHtml(url);
      var dirAttr = /^https?:\/\//i.test(url) ? ' dir="ltr"' : '';
      return (
        '<a class="pa-md-link" href="' +
        href +
        '" rel="noopener noreferrer" target="_blank"' +
        dirAttr +
        '>' +
        linkIconFor(label, url) +
        '<span>' +
        escapeHtml(label) +
        '</span></a>'
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
  var minimizeBtn = document.getElementById('paMinimize');
  var newChatBtn = document.getElementById('paNewChat');
  var headStatus = document.getElementById('paHeadStatus');
  var headStatusText = headStatus ? headStatus.querySelector('.pa-head__status-text') : null;
  var jumpBtn = document.getElementById('paJumpEnd');
  var dock = document.getElementById('paDock');
  var headEl = document.getElementById('paHead');

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
  var dockDrag = null;

  function isMobile() {
    return window.matchMedia('(max-width: 640px)').matches;
  }

  function canDockDrag() {
    return !isMobile() && !!dock;
  }

  function resetDockPosition() {
    if (!dock) return;
    dock.classList.remove('is-custom-position');
    dock.style.left = '';
    dock.style.top = '';
    dock.style.right = '';
    dock.style.bottom = '';
  }

  function clampDockXY(x, y) {
    var rect = dock.getBoundingClientRect();
    var w = rect.width || 0;
    var h = rect.height || 0;
    var maxX = Math.max(DOCK_MARGIN, window.innerWidth - w - DOCK_MARGIN);
    var maxY = Math.max(DOCK_MARGIN, window.innerHeight - h - DOCK_MARGIN);
    return {
      x: Math.min(Math.max(DOCK_MARGIN, x), maxX),
      y: Math.min(Math.max(DOCK_MARGIN, y), maxY),
    };
  }

  function setDockXY(x, y, persist) {
    var c = clampDockXY(x, y);
    dock.classList.add('is-custom-position');
    dock.style.left = c.x + 'px';
    dock.style.top = c.y + 'px';
    if (persist) {
      try {
        sessionStorage.setItem(DOCK_POS_KEY, JSON.stringify({ x: c.x, y: c.y }));
      } catch (e) {}
    }
    return c;
  }

  function ensureDockCustomFromAnchor() {
    if (!dock || dock.classList.contains('is-custom-position')) return;
    var rect = dock.getBoundingClientRect();
    dock.classList.add('is-custom-position');
    dock.style.left = rect.left + 'px';
    dock.style.top = rect.top + 'px';
  }

  function loadDockPosition() {
    if (!canDockDrag()) return;
    try {
      var raw = sessionStorage.getItem(DOCK_POS_KEY);
      if (!raw) return;
      var pos = JSON.parse(raw);
      if (typeof pos.x !== 'number' || typeof pos.y !== 'number') return;
      setDockXY(pos.x, pos.y, false);
    } catch (e) {}
  }

  function onDockPointerMove(e) {
    if (!dockDrag || e.pointerId !== dockDrag.pointerId) return;
    var dx = e.clientX - dockDrag.startClientX;
    var dy = e.clientY - dockDrag.startClientY;
    if (!dockDrag.moved) {
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      dockDrag.moved = true;
      ensureDockCustomFromAnchor();
      var rect = dock.getBoundingClientRect();
      dockDrag.offsetX = dockDrag.startClientX - rect.left;
      dockDrag.offsetY = dockDrag.startClientY - rect.top;
    }
    e.preventDefault();
    setDockXY(e.clientX - dockDrag.offsetX, e.clientY - dockDrag.offsetY, false);
  }

  function endDockDrag(e) {
    if (!dockDrag) return;
    if (e && e.pointerId !== undefined && e.pointerId !== dockDrag.pointerId) return;
    var source = dockDrag.source;
    var moved = dockDrag.moved;
    var lastX = parseFloat(dock.style.left);
    var lastY = parseFloat(dock.style.top);
    dockDrag = null;
    root.classList.remove('is-dragging');
    document.removeEventListener('pointermove', onDockPointerMove);
    document.removeEventListener('pointerup', endDockDrag);
    document.removeEventListener('pointercancel', endDockDrag);
    if (moved && !isNaN(lastX) && !isNaN(lastY)) {
      setDockXY(lastX, lastY, true);
    } else if (source === 'fab') {
      setOpen(true);
    }
  }

  function startDockDrag(e, source) {
    if (!canDockDrag()) return;
    if (e.button !== 0) return;
    if (source === 'head') {
      if (e.target.closest('.pa-head__tools, button, a, input, textarea, select, label')) return;
      if (!root.classList.contains('is-open')) return;
    }
    dockDrag = {
      pointerId: e.pointerId,
      source: source,
      startClientX: e.clientX,
      startClientY: e.clientY,
      moved: false,
      offsetX: 0,
      offsetY: 0,
    };
    root.classList.add('is-dragging');
    if (e.currentTarget.setPointerCapture) {
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch (err) {}
    }
    document.addEventListener('pointermove', onDockPointerMove);
    document.addEventListener('pointerup', endDockDrag);
    document.addEventListener('pointercancel', endDockDrag);
  }

  function onDockViewportChange() {
    if (!dock) return;
    if (isMobile()) {
      resetDockPosition();
      return;
    }
    if (dock.classList.contains('is-custom-position')) {
      var x = parseFloat(dock.style.left);
      var y = parseFloat(dock.style.top);
      if (!isNaN(x) && !isNaN(y)) setDockXY(x, y, false);
    }
  }

  function setHeadStatus(text) {
    if (headStatusText) headStatusText.textContent = text;
    else if (headStatus) headStatus.textContent = text;
  }

  function updateSendState() {
    if (!sendBtn) return;
    var empty = !(input.value || '').trim();
    sendBtn.disabled = empty || root.classList.contains('is-sending');
  }

  function setSending(on) {
    if (on) {
      root.classList.add('is-sending');
    } else {
      root.classList.remove('is-sending');
    }
    updateSendState();
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
      if (canDockDrag() && dock.classList.contains('is-custom-position')) {
        requestAnimationFrame(function () {
          var x = parseFloat(dock.style.left);
          var y = parseFloat(dock.style.top);
          if (!isNaN(x) && !isNaN(y)) setDockXY(x, y, false);
        });
      }
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

  if (fab) {
    fab.addEventListener('pointerdown', function (e) {
      startDockDrag(e, 'fab');
    });
    fab.addEventListener('click', function (e) {
      if (canDockDrag()) {
        e.preventDefault();
        return;
      }
      setOpen(true);
    });
  }
  if (headEl) {
    headEl.addEventListener('pointerdown', function (e) {
      startDockDrag(e, 'head');
    });
  }
  loadDockPosition();
  var dockMq = window.matchMedia('(max-width: 640px)');
  if (dockMq.addEventListener) {
    dockMq.addEventListener('change', onDockViewportChange);
  } else if (dockMq.addListener) {
    dockMq.addListener(onDockViewportChange);
  }
  window.addEventListener('resize', onDockViewportChange);
  closeBtn.addEventListener('click', function () {
    setOpen(false);
  });
  if (minimizeBtn) {
    minimizeBtn.addEventListener('click', function () {
      setOpen(false);
    });
  }
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

  input.addEventListener('input', function () {
    autoResizeInput();
    updateSendState();
  });
  updateSendState();
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

  function buildSystemNoticeHtml(variant, title, description) {
    var icon = variant === 'limit' ? ICON_CLOCK : ICON_ALERT;
    return (
      '<div class="pa-system-notice pa-system-notice--' +
      variant +
      '" role="status" aria-live="polite">' +
      '<div class="pa-system-notice__mark">' +
      icon +
      '</div>' +
      '<div class="pa-system-notice__copy">' +
      '<span class="pa-system-notice__title">' +
      escapeHtml(title) +
      '</span>' +
      '<span class="pa-system-notice__desc">' +
      escapeHtml(description) +
      '</span>' +
      '</div></div>'
    );
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
    var isSystem = options.variant === 'error' || options.variant === 'limit';
    var extra = isSystem ? ' pa-msg--system pa-msg--system-' + options.variant : '';
    if (!isSystem && options.variant) {
      extra += ' pa-msg--' + options.variant;
    }
    div.className = 'pa-msg pa-msg--' + (role === 'user' ? 'user' : 'bot') + extra;
    var body = document.createElement('div');
    body.className = 'pa-msg__body';
    body.setAttribute('dir', 'auto');
    if (role === 'user') {
      body.innerHTML = '<p>' + escapeHtml(html) + '</p>';
    } else if (isSystem) {
      var sysTitle =
        options.systemTitle ||
        (options.variant === 'limit' ? 'کمی مکث کنید' : 'مشکلی پیش آمد');
      body.innerHTML = buildSystemNoticeHtml(options.variant, sysTitle, html);
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
      retry.className = isSystem ? 'pa-system-notice__retry' : 'pa-msg__retry';
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
      '<div class="pa-loading-bubble" aria-label="' +
      escapeHtml(label || 'در حال آماده‌سازی پاسخ') +
      '">' +
      '<div class="pa-loading__dots" aria-hidden="true"><span></span><span></span><span></span></div>' +
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
      chip.innerHTML =
        '<span class="pa-chip__icon" aria-hidden="true">' +
        ICON_CHIP +
        '</span><span class="pa-chip__text">' +
        escapeHtml(q) +
        '</span>';
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
            'درخواست‌ها زیاد است. یک یا دو دقیقه بعد همان سؤال را دوباره بپرسید.',
            {
              variant: 'limit',
              retryText: text,
              systemTitle: 'کمی مکث کنید',
            }
          );
          return;
        }
        if (!res.body.ok) {
          appendMessage('bot', res.body.error || 'پاسخی دریافت نشد. دوباره تلاش کنید.', {
            variant: 'error',
            retryText: text,
            systemTitle: 'خطا در پاسخ',
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
        appendMessage('bot', 'اتصال برقرار نشد. اینترنت را بررسی کنید و دوباره بفرستید.', {
          variant: 'error',
          retryText: text,
          systemTitle: 'اتصال قطع شد',
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
        updateSendState();

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
