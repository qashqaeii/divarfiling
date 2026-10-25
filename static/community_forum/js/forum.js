
(function () {
  'use strict';

  var root = document.getElementById('cfForumApp');
  if (!root) return;

  var csrf = root.dataset.csrf;
  var bootstrapUrl = root.dataset.bootstrapUrl;
  var messagesUrl = root.dataset.apiBase;
  var wsPath = root.dataset.wsPath || '/ws/forum/';
  var EMOJIS = ['👍', '❤️', '👏', '😂', '🙏'];

  var state = {
    messages: new Map(),
    orderedIds: [],
    nextBefore: null,
    replyToId: null,
    myPublicId: null,
    atBottom: true,
    ws: null,
    wsConnected: false,
    wsConnecting: false,
    pollTimer: null,
    heartbeatTimer: null,
    reconnectTimer: null,
    reconnectAttempt: 0,
    lastId: 0,
    lastSyncAt: null,
    sending: false,
    pendingSend: null,
    reportReasons: [],
    ui: { editId: null, deleteId: null, reportId: null, reactionId: null },
    openMenuId: null,
    initialLoaded: false,
  };

  function $(id) { return document.getElementById(id); }

  function hideEl(el) {
    if (!el) return;
    el.hidden = true;
  }

  function showEl(el) {
    if (!el) return;
    el.hidden = false;
  }

  function apiUrl(path) {
    return messagesUrl.replace(/messages\/?$/, '') + String(path).replace(/^\//, '');
  }

  function fetchJson(url, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (opts.method && opts.method !== 'GET') opts.headers['X-CSRFToken'] = csrf;
    if (opts.body && typeof opts.body === 'object') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw data;
        return data;
      });
    });
  }

  function toast(msg, isErr) {
    var el = $('cfToast');
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle('cf-toast--err', !!isErr);
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.hidden = true; }, 3500);
  }

  function draftKey() {
    return state.myPublicId ? 'cf_draft:' + state.myPublicId : 'cf_draft:anon';
  }

  function uuid() {
    return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() :
      'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 3 | 8)).toString(16);
      });
  }

  function isMine(msg) {
    return !!(state.myPublicId && msg.sender_public_id === state.myPublicId);
  }

  function normalizeIncoming(msg) {
    if (!msg) return msg;
    if (!msg.sender_public_id && msg.public_id) msg.sender_public_id = msg.public_id;
    msg.is_mine = isMine(msg);
    return msg;
  }

  function mergeMessage(msg) {
    msg = normalizeIncoming(msg);
    if (!msg || !msg.id) return;
    if (!state.messages.has(msg.id)) {
      state.orderedIds.push(msg.id);
      state.orderedIds.sort(function (a, b) { return a - b; });
    }
    state.messages.set(msg.id, msg);
    if (msg.id > state.lastId) state.lastId = msg.id;
  }

  function isNearBottom() {
    var el = $('cfMessages');
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  function scrollToBottom() {
    var el = $('cfMessages');
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    state.atBottom = true;
    $('cfNewMsgsBtn').hidden = true;
    $('cfScrollEndBtn').hidden = true;
    markRead();
  }

  function markRead() {
    if (!state.lastId) return;
    fetchJson(apiUrl('read/'), { method: 'POST', body: { message_id: state.lastId } }).catch(function () {});
  }

  function formatTime(iso) {
    try {
      return new Date(iso).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) { return ''; }
  }

  function dayKey(iso) {
    try { return new Date(iso).toLocaleDateString('fa-IR'); } catch (e) { return ''; }
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function initials(label) {
    var parts = (label || '?').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2);
    return (parts[0][0] || '') + (parts[parts.length - 1][0] || '');
  }

  function setConnStatus(mode, label) {
    var badge = $('cfConnBadge');
    var dot = $('cfConnDot');
    var lbl = $('cfConnLabel');
    if (!badge || !lbl) return;
    badge.hidden = false;
    badge.classList.remove('cf-conn--live', 'cf-conn--reconnect', 'cf-conn--sync');
    if (mode === 'live') badge.classList.add('cf-conn--live');
    if (mode === 'reconnect') badge.classList.add('cf-conn--reconnect');
    if (mode === 'sync') badge.classList.add('cf-conn--sync');
    lbl.textContent = label;
    if (dot) dot.setAttribute('aria-label', label);
  }

  function hideConnStatus() {
    var badge = $('cfConnBadge');
    if (badge) badge.hidden = true;
  }

  function updateEmptyState() {
    var empty = $('cfEmptyState');
    var loading = $('cfLoadingState');
    if (!empty) return;
    if (!state.initialLoaded) {
      if (loading) loading.hidden = false;
      empty.hidden = true;
      return;
    }
    if (loading) loading.hidden = true;
    empty.hidden = state.orderedIds.length > 0;
  }

  function closeAllMenus() {
    document.querySelectorAll('.cf-msg__menu').forEach(function (m) { m.hidden = true; });
    document.querySelectorAll('.cf-msg__toolbar').forEach(function (t) { t.classList.remove('is-open'); });
    state.openMenuId = null;
  }

  document.addEventListener('click', function (ev) {
    if (!ev.target.closest('.cf-msg__toolbar')) closeAllMenus();
  });

  function menuItems(msg) {
    var items = [
      { act: 'reply', label: 'پاسخ' },
      { act: 'react', label: 'واکنش' },
    ];
    if (msg.is_mine) {
      items.push({ act: 'edit', label: 'ویرایش' });
      items.push({ act: 'del', label: 'حذف', danger: true });
    } else {
      items.push({ act: 'report', label: 'گزارش', danger: true });
    }
    return items;
  }

  function onMenuAction(msg, act) {
    closeAllMenus();
    if (act === 'reply') setReply(msg);
    if (act === 'react') openReaction(msg.id);
    if (act === 'edit') openEdit(msg);
    if (act === 'del') openDelete(msg.id);
    if (act === 'report') openReport(msg.id);
  }

  function buildMessageEl(msg) {
    var wrap = document.createElement('div');
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '') + (msg.is_deleted ? ' cf-msg--deleted' : '');
    wrap.dataset.id = String(msg.id);

    var av;
    if (msg.avatar_url) {
      av = document.createElement('img');
      av.src = msg.avatar_url;
      av.alt = '';
    } else {
      av = document.createElement('div');
      av.textContent = initials(msg.sender_label);
    }
    av.className = 'cf-msg__avatar';

    var stack = document.createElement('div');
    stack.className = 'cf-msg__stack';

    var meta = document.createElement('div');
    meta.className = 'cf-msg__meta';
    meta.innerHTML = '<span class="cf-msg__name">' + escapeHtml(msg.sender_label) + '</span>' +
      '<span class="cf-msg__time">' + formatTime(msg.created_at) +
      (msg.is_edited ? ' <span class="cf-msg__edited">· ویرایش‌شده</span>' : '') + '</span>';

    var bubble = document.createElement('div');
    bubble.className = 'cf-msg__bubble';

    if (msg.reply_to) {
      var rp = document.createElement('div');
      rp.className = 'cf-msg__reply';
      rp.textContent = msg.reply_to.unavailable ? 'پیام در دسترس نیست' :
        ((msg.reply_to.sender_label || '') + ': ' + (msg.reply_to.body_preview || ''));
      bubble.appendChild(rp);
    }

    var body = document.createElement('div');
    body.className = 'cf-msg__body';
    body.setAttribute('dir', 'auto');
    body.textContent = msg.is_deleted ? 'پیام حذف شده' : msg.body;
    bubble.appendChild(body);

    var rx = document.createElement('div');
    rx.className = 'cf-reactions';
    if (msg.reactions && msg.reactions.length) {
      msg.reactions.forEach(function (r) {
        var s = document.createElement('button');
        s.type = 'button';
        s.className = 'cf-reaction';
        s.textContent = r.emoji + ' ' + r.count;
        s.addEventListener('click', function () { openReaction(msg.id); });
        rx.appendChild(s);
      });
    }
    bubble.appendChild(rx);

    stack.appendChild(meta);
    stack.appendChild(bubble);

    if (!msg.is_deleted) {
      var toolbar = document.createElement('div');
      toolbar.className = 'cf-msg__toolbar';
      var menuBtn = document.createElement('button');
      menuBtn.type = 'button';
      menuBtn.className = 'cf-msg__menu-btn';
      menuBtn.setAttribute('aria-label', 'عملیات پیام');
      menuBtn.innerHTML = '<i class="fas fa-ellipsis-v" aria-hidden="true"></i>';
      var menu = document.createElement('div');
      menu.className = 'cf-msg__menu';
      menu.hidden = true;
      menuItems(msg).forEach(function (item) {
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = item.label;
        if (item.danger) b.className = 'cf-menu-danger';
        b.addEventListener('click', function () { onMenuAction(msg, item.act); });
        menu.appendChild(b);
      });
      menuBtn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        var open = state.openMenuId === msg.id;
        closeAllMenus();
        if (!open) {
          menu.hidden = false;
          toolbar.classList.add('is-open');
          state.openMenuId = msg.id;
        }
      });
      toolbar.appendChild(menuBtn);
      toolbar.appendChild(menu);
      bubble.style.position = 'relative';
      toolbar.style.position = 'absolute';
      toolbar.style.top = '4px';
      toolbar.style.insetInlineEnd = '4px';
      bubble.appendChild(toolbar);
    }
    wrap.appendChild(av);
    wrap.appendChild(stack);
    return wrap;
  }

  function patchMessageEl(wrap, msg) {
    msg = normalizeIncoming(msg);
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '') + (msg.is_deleted ? ' cf-msg--deleted' : '');
    var body = wrap.querySelector('.cf-msg__body');
    if (body) body.textContent = msg.is_deleted ? 'پیام حذف شده' : msg.body;
    var meta = wrap.querySelector('.cf-msg__meta');
    if (meta) {
      meta.innerHTML = '<span class="cf-msg__name">' + escapeHtml(msg.sender_label) + '</span>' +
        '<span class="cf-msg__time">' + formatTime(msg.created_at) +
        (msg.is_edited ? ' <span class="cf-msg__edited">· ویرایش‌شده</span>' : '') + '</span>';
    }
    var rx = wrap.querySelector('.cf-reactions');
    if (rx) {
      rx.innerHTML = '';
      (msg.reactions || []).forEach(function (r) {
        var s = document.createElement('button');
        s.type = 'button';
        s.className = 'cf-reaction';
        s.textContent = r.emoji + ' ' + r.count;
        s.addEventListener('click', function () { openReaction(msg.id); });
        rx.appendChild(s);
      });
    }
  }

  function findMessageNode(id) {
    return document.querySelector('.cf-msg[data-id="' + id + '"]');
  }

  function ensureDaySepBefore(msg, insertBeforeNode) {
    var el = $('cfMessages');
    var dk = dayKey(msg.created_at);
    if (!dk) return;
    var prevId = null;
    var idx = state.orderedIds.indexOf(msg.id);
    if (idx > 0) prevId = state.orderedIds[idx - 1];
    var prevMsg = prevId ? state.messages.get(prevId) : null;
    var prevDk = prevMsg ? dayKey(prevMsg.created_at) : '';
    if (prevDk === dk) return;
    var existing = el.querySelector('.cf-day-sep[data-day="' + dk + '"]');
    if (existing) return;
    var sep = document.createElement('div');
    sep.className = 'cf-day-sep';
    sep.dataset.day = dk;
    sep.textContent = dk;
    if (insertBeforeNode) el.insertBefore(sep, insertBeforeNode);
    else el.appendChild(sep);
  }

  function isAppendOnly(msg) {
    if (!state.orderedIds.length) return true;
    return msg.id >= state.orderedIds[state.orderedIds.length - 1];
  }

  function renderAll() {
    var el = $('cfMessages');
    if (!el) return;
    var prevH = el.scrollHeight;
    var prevTop = el.scrollTop;
    var loading = $('cfLoadingState');
    var empty = $('cfEmptyState');
    el.querySelectorAll('.cf-msg, .cf-day-sep').forEach(function (n) { n.remove(); });
    var lastDay = '';
    state.orderedIds.forEach(function (id) {
      var msg = state.messages.get(id);
      if (!msg) return;
      var dk = dayKey(msg.created_at);
      if (dk && dk !== lastDay) {
        lastDay = dk;
        var sep = document.createElement('div');
        sep.className = 'cf-day-sep';
        sep.dataset.day = dk;
        sep.textContent = dk;
        el.appendChild(sep);
      }
      el.appendChild(buildMessageEl(msg));
    });
    if (loading) el.appendChild(loading);
    if (empty) el.appendChild(empty);
    updateEmptyState();
    if (state.atBottom) scrollToBottom();
    else el.scrollTop = prevTop + (el.scrollHeight - prevH);
  }

  function appendMessageDom(msg) {
    var el = $('cfMessages');
    var node = buildMessageEl(msg);
    var loading = $('cfLoadingState');
    var empty = $('cfEmptyState');
    ensureDaySepBefore(msg, loading || empty);
    if (loading && loading.parentNode === el) el.insertBefore(node, loading);
    else if (empty && empty.parentNode === el) el.insertBefore(node, empty);
    else el.appendChild(node);
    updateEmptyState();
  }

  function upsertMessageDom(msg) {
    var existing = findMessageNode(msg.id);
    if (existing) {
      patchMessageEl(existing, msg);
      return;
    }
    if (isAppendOnly(msg)) appendMessageDom(msg);
    else renderAll();
  }

  function upsertFromPayload(msg, scrollIfBottom) {
    mergeMessage(msg);
    var near = isNearBottom();
    upsertMessageDom(msg);
    if (scrollIfBottom && near) scrollToBottom();
    else if (!near && !msg.is_mine) $('cfNewMsgsBtn').hidden = false;
  }

  function loadInitial() {
    return fetchJson(messagesUrl).then(function (data) {
      (data.messages || []).forEach(function (m) { mergeMessage(m); });
      state.nextBefore = data.next_before_id;
      state.initialLoaded = true;
      renderAll();
      scrollToBottom();
    });
  }

  function loadOlder() {
    if (!state.nextBefore) return Promise.resolve();
    var el = $('cfMessages');
    var prevH = el.scrollHeight;
    return fetchJson(messagesUrl + '?before_id=' + state.nextBefore).then(function (data) {
      (data.messages || []).forEach(function (m) { mergeMessage(m); });
      state.nextBefore = data.next_before_id;
      renderAll();
      el.scrollTop = el.scrollHeight - prevH;
    });
  }

  function touchSyncClock() {
    state.lastSyncAt = new Date().toISOString();
  }

  function syncChanges() {
    if (!state.lastId || !state.lastSyncAt) return Promise.resolve();
    setConnStatus('sync', 'همگام‌سازی…');
    var cursor = 0;
    function step() {
      var url = apiUrl(
        'sync/?anchor_id=' + state.lastId
          + '&since=' + encodeURIComponent(state.lastSyncAt)
          + '&cursor=' + cursor,
      );
      return fetchJson(url).then(function (data) {
        (data.messages || []).forEach(function (m) { upsertFromPayload(m, false); });
        if (data.has_more && data.next_cursor) {
          cursor = data.next_cursor;
          return step();
        }
        touchSyncClock();
        if (state.wsConnected) setConnStatus('live', 'متصل');
        else if (state.reconnectTimer || state.wsConnecting) setConnStatus('reconnect', 'در حال اتصال مجدد…');
        else hideConnStatus();
      });
    }
    return step().catch(function () {
      if (state.wsConnected) setConnStatus('live', 'متصل');
    });
  }

  function fetchMissed() {
    return syncChanges().then(function () {
      var after = state.lastId;
      function step() {
        return fetchJson(messagesUrl + '?after_id=' + after).then(function (data) {
          (data.messages || []).forEach(function (m) { upsertFromPayload(m, true); });
          if (data.has_more_after && data.messages && data.messages.length) {
            after = data.messages[data.messages.length - 1].id;
            return step();
          }
          touchSyncClock();
        });
      }
      return step();
    });
  }

  function teardownWs(opts) {
    opts = opts || {};
    state.wsConnected = false;
    if (state.heartbeatTimer) { clearInterval(state.heartbeatTimer); state.heartbeatTimer = null; }
    if (state.ws) {
      try { state.ws.onclose = null; state.ws.close(); } catch (e) {}
      state.ws = null;
    }
    if (!opts.preserveConnecting) state.wsConnecting = false;
  }

  function scheduleReconnect() {
    if (state.reconnectTimer) return;
    var delay = Math.min(30000, 1000 * Math.pow(2, state.reconnectAttempt));
    delay += Math.random() * 500;
    setConnStatus('reconnect', 'در حال اتصال مجدد…');
    state.reconnectTimer = setTimeout(function () {
      state.reconnectTimer = null;
      state.reconnectAttempt += 1;
      connectWs();
    }, delay);
  }

  function startPoll() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(function () {
      if (document.hidden || state.wsConnected) return;
      fetchMissed().catch(function () {});
    }, 10000);
  }

  function stopPoll() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  var wsConnectSeq = 0;

  function connectWs() {
    if (state.wsConnecting || (state.ws && state.ws.readyState <= 1)) return;
    state.wsConnecting = true;
    wsConnectSeq += 1;
    teardownWs({ preserveConnecting: true });
    setConnStatus('reconnect', 'در حال اتصال…');
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + wsPath;
    try { state.ws = new WebSocket(url); } catch (e) {
      state.wsConnecting = false;
      startPoll();
      setConnStatus('reconnect', 'حالت آفلاین — به‌روزرسانی دوره‌ای');
      return;
    }
    state.ws.onopen = function () {
      state.wsConnecting = false;
      state.wsConnected = true;
      state.reconnectAttempt = 0;
      setConnStatus('live', 'متصل');
      stopPoll();
      fetchMissed().catch(function () {});
      state.heartbeatTimer = setInterval(function () {
        if (state.ws && state.ws.readyState === 1) {
          state.ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 25000);
    };
    state.ws.onclose = function () {
      state.wsConnected = false;
      teardownWs();
      startPoll();
      scheduleReconnect();
    };
    state.ws.onmessage = function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.type === 'connected') {
          if (data.sender_public_id) state.myPublicId = data.sender_public_id;
          return;
        }
        if (data.type === 'pong') return;
        var payload = data.payload || {};
        if (data.type === 'message.new' || data.type === 'message.updated') {
          upsertFromPayload(payload.message, true);
        } else if (data.type === 'message.deleted') {
          var m = state.messages.get(payload.id);
          if (m) { m.is_deleted = true; m.body = ''; upsertFromPayload(m, false); }
        } else if (data.type === 'reaction.updated') {
          var msg = state.messages.get(payload.message_id);
          if (msg) {
            msg.reactions = payload.reactions;
            var node = findMessageNode(msg.id);
            if (node) patchMessageEl(node, msg);
            else renderAll();
          }
        }
      } catch (err) {}
    };
  }

  function setReply(msg) {
    state.replyToId = msg.id;
    showEl($('cfReplyPreview'));
    $('cfReplyPreviewText').textContent = (msg.sender_label || '') + ': ' + (msg.body || '').slice(0, 120);
    $('cfComposerInput').focus();
  }

  function clearReply() {
    state.replyToId = null;
    hideEl($('cfReplyPreview'));
    var previewText = $('cfReplyPreviewText');
    if (previewText) previewText.textContent = '';
  }

  function showSendFailed(err) {
    showEl($('cfSendFailed'));
    $('cfSendFailedText').textContent = (err && err.error) || 'ارسال ناموفق بود';
  }

  function hideSendFailed() {
    hideEl($('cfSendFailed'));
  }

  function sendMessage(ev) {
    if (ev) ev.preventDefault();
    if (state.sending) return;
    var text = ($('cfComposerInput').value || '').trim();
    if (!state.pendingSend) {
      if (!text) return;
      state.pendingSend = {
        body: text,
        reply_to_id: state.replyToId,
        client_message_id: uuid(),
      };
    }
    state.sending = true;
    hideSendFailed();
    $('cfSendBtn').disabled = true;
    $('cfSendBtn').classList.add('is-sending');
    var payload = state.pendingSend;
    fetchJson(messagesUrl, { method: 'POST', body: payload })
      .then(function (data) {
        state.pendingSend = null;
        hideSendFailed();
        $('cfComposerInput').value = '';
        growComposer();
        updateChar();
        clearReply();
        upsertFromPayload(data.message, true);
        try { localStorage.removeItem(draftKey()); } catch (e) {}
      })
      .catch(function (err) {
        showSendFailed(err);
      })
      .finally(function () {
        state.sending = false;
        $('cfSendBtn').classList.remove('is-sending');
        updateChar();
      });
  }

  function openEdit(msg) {
    state.ui.editId = msg.id;
    $('cfEditInput').value = msg.body || '';
    $('cfEditDialog').showModal();
  }

  function openDelete(id) {
    state.ui.deleteId = id;
    $('cfDeleteDialog').showModal();
  }

  function openReport(id) {
    state.ui.reportId = id;
    var box = $('cfReportReasons');
    box.innerHTML = '';
    delete box.dataset.selected;
    state.reportReasons.forEach(function (r) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cf-btn cf-btn--ghost cf-report-opt';
      btn.dataset.id = r.id;
      btn.textContent = r.label;
      btn.addEventListener('click', function () {
        box.querySelectorAll('.cf-report-opt').forEach(function (b) { b.classList.remove('is-selected'); });
        btn.classList.add('is-selected');
        box.dataset.selected = r.id;
      });
      box.appendChild(btn);
    });
    $('cfReportDialog').showModal();
  }

  function openReaction(id) {
    state.ui.reactionId = id;
    var pick = $('cfEmojiPick');
    pick.innerHTML = '';
    EMOJIS.forEach(function (em) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'cf-emoji-btn';
      b.textContent = em;
      b.addEventListener('click', function () {
        postReaction(id, em);
        $('cfReactionDialog').close();
      });
      pick.appendChild(b);
    });
    $('cfReactionDialog').showModal();
  }

  function postReaction(mid, emoji) {
    fetchJson(apiUrl('messages/' + mid + '/reactions/'), { method: 'POST', body: { emoji: emoji } })
      .then(function (data) {
        var msg = state.messages.get(mid);
        if (msg) {
          msg.reactions = data.reactions;
          var node = findMessageNode(mid);
          if (node) patchMessageEl(node, msg);
        }
      }).catch(function (err) { toast(err.error || 'خطا', true); });
  }

  function growComposer() {
    var ta = $('cfComposerInput');
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }

  function updateChar() {
    var n = ($('cfComposerInput').value || '').length;
    $('cfCharCount').textContent = String(n);
    $('cfSendBtn').disabled = !n || state.sending;
  }

  function runSearch(page) {
    var q = ($('cfSearchInput').value || '').trim();
    if (q.length < 2) { toast('حداقل ۲ کاراکتر', true); return; }
    fetchJson(apiUrl('search/?q=' + encodeURIComponent(q) + '&page=' + (page || 1)))
      .then(function (data) {
        var box = $('cfSearchResults');
        box.innerHTML = '';
        if (!data.messages.length) {
          box.textContent = 'نتیجه‌ای نیست';
          return;
        }
        data.messages.forEach(function (m) {
          var row = document.createElement('button');
          row.type = 'button';
          row.className = 'cf-search-hit';
          row.textContent = (m.sender_label || '') + ': ' + (m.body || '').slice(0, 80);
          row.addEventListener('click', function () {
            if (!state.messages.has(m.id)) mergeMessage(m);
            renderAll();
            var node = findMessageNode(m.id);
            if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
          });
          box.appendChild(row);
        });
      }).catch(function (err) { toast(err.error || 'خطا', true); });
  }

  function bindDialogClose() {
    document.querySelectorAll('[data-cf-dialog-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var dlg = btn.closest('dialog');
        if (dlg) dlg.close();
      });
    });
    document.querySelectorAll('.cf-dialog').forEach(function (dlg) {
      dlg.addEventListener('cancel', function (ev) {
        ev.preventDefault();
        dlg.close();
      });
      dlg.addEventListener('close', function () {
        document.body.classList.remove('ws-modal-open');
      });
      dlg.addEventListener('click', function (ev) {
        if (ev.target === dlg) dlg.close();
      });
    });
  }

  function openDialog(dlg) {
    if (!dlg) return;
    document.body.classList.add('ws-modal-open');
    dlg.showModal();
  }

  ['cfComposerInput', 'cfEditInput', 'cfReportNote'].forEach(function (id) {
    var el = $(id);
    if (el) el.setAttribute('dir', 'auto');
  });

  $('cfComposer').addEventListener('submit', sendMessage);
  $('cfComposerInput').addEventListener('input', function () {
    updateChar();
    growComposer();
    try { localStorage.setItem(draftKey(), $('cfComposerInput').value); } catch (e) {}
  });
  $('cfComposerInput').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); $('cfComposer').requestSubmit(); }
  });
  $('cfReplyCancel').addEventListener('click', clearReply);
  $('cfNewMsgsBtn').addEventListener('click', scrollToBottom);
  $('cfScrollEndBtn').addEventListener('click', scrollToBottom);
  $('cfMessages').addEventListener('scroll', function () {
    state.atBottom = isNearBottom();
    if (state.atBottom) { $('cfNewMsgsBtn').hidden = true; $('cfScrollEndBtn').hidden = true; markRead(); }
    else $('cfScrollEndBtn').hidden = false;
    if ($('cfMessages').scrollTop < 40) loadOlder();
  });
  $('cfSearchToggle').addEventListener('click', function () {
    var p = $('cfSearchPanel');
    var open = p.hidden;
    p.hidden = !open;
    $('cfSearchToggle').setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) $('cfSearchInput').focus();
  });
  $('cfSearchClose').addEventListener('click', function () {
    $('cfSearchPanel').hidden = true;
    $('cfSearchToggle').setAttribute('aria-expanded', 'false');
  });
  $('cfSearchInput').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') runSearch(1);
  });
  $('cfRulesBtn').addEventListener('click', function () { openDialog($('cfRulesDialog')); });
  $('cfProfileBtn').addEventListener('click', function () { openDialog($('cfProfileDialog')); });
  $('cfProfileClose').addEventListener('click', function () { $('cfProfileDialog').close(); });
  $('cfProfileSave').addEventListener('click', function () {
    fetchJson(apiUrl('profile/'), { method: 'POST', body: { display_name: $('cfDisplayNameInput').value } })
      .then(function () { $('cfProfileDialog').close(); toast('ذخیره شد'); })
      .catch(function (err) {
        $('cfProfileError').hidden = false;
        $('cfProfileError').textContent = err.error || 'خطا';
      });
  });
  $('cfEditCancel').addEventListener('click', function () { $('cfEditDialog').close(); });
  $('cfEditSave').addEventListener('click', function () {
    var id = state.ui.editId;
    fetchJson(apiUrl('messages/' + id + '/'), { method: 'PATCH', body: { body: $('cfEditInput').value } })
      .then(function (data) { $('cfEditDialog').close(); upsertFromPayload(data.message, false); })
      .catch(function (err) { toast(err.error || 'خطا', true); });
  });
  $('cfDeleteCancel').addEventListener('click', function () { $('cfDeleteDialog').close(); });
  $('cfDeleteConfirm').addEventListener('click', function () {
    var id = state.ui.deleteId;
    fetchJson(apiUrl('messages/' + id + '/'), { method: 'DELETE' })
      .then(function () {
        $('cfDeleteDialog').close();
        var m = state.messages.get(id);
        if (m) { m.is_deleted = true; m.body = ''; upsertFromPayload(m, false); }
      }).catch(function (err) { toast(err.error || 'خطا', true); });
  });
  $('cfReportCancel').addEventListener('click', function () { $('cfReportDialog').close(); });
  $('cfReportSubmit').addEventListener('click', function () {
    var reason = $('cfReportReasons').dataset.selected;
    if (!reason) { toast('دلیل را انتخاب کنید', true); return; }
    fetchJson(apiUrl('messages/' + state.ui.reportId + '/report/'), {
      method: 'POST', body: { reason: reason, note: $('cfReportNote').value },
    }).then(function () { $('cfReportDialog').close(); toast('گزارش ثبت شد'); })
      .catch(function (err) { toast(err.error || 'خطا', true); });
  });
  $('cfReactionClear').addEventListener('click', function () {
    postReaction(state.ui.reactionId, null);
    $('cfReactionDialog').close();
  });
  $('cfSendRetry').addEventListener('click', function () { sendMessage(); });
  $('cfSendFailedDismiss').addEventListener('click', function () {
    hideSendFailed();
    state.pendingSend = null;
    state.sending = false;
    $('cfSendBtn').classList.remove('is-sending');
    updateChar();
  });

  bindDialogClose();

  window.addEventListener('pagehide', teardownWs);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && !state.wsConnected) connectWs();
  });

  window.cfForumWsDiag = function () {
    return {
      wsConnecting: state.wsConnecting,
      wsConnected: state.wsConnected,
      readyState: state.ws ? state.ws.readyState : null,
      connectSeq: wsConnectSeq,
    };
  };

  fetchJson(bootstrapUrl).then(function (data) {
    state.myPublicId = data.member && data.member.public_id;
    state.reportReasons = data.report_reasons || [];
    if (data.member && data.member.display_name) {
      $('cfDisplayNameInput').value = data.member.display_name;
    }
    $('cfComposerInput').maxLength = (data.limits && data.limits.max_body) || 2000;
    if (data.pinned_notices && data.pinned_notices.length) {
      $('cfPinned').hidden = false;
      $('cfPinned').textContent = data.pinned_notices.map(function (n) { return n.body; }).join(' — ');
    }
    if (!data.member.welcome_seen) {
      var dlg = $('cfWelcomeDialog');
      openDialog(dlg);
      $('cfWelcomeAck').addEventListener('click', function () {
        dlg.close();
        fetchJson(apiUrl('profile/'), { method: 'POST', body: { welcome_ack: true } });
      }, { once: true });
    }
    touchSyncClock();
    return loadInitial();
  }).then(function () {
    touchSyncClock();
    connectWs();
    try {
      var draft = localStorage.getItem(draftKey());
      if (draft) {
        $('cfComposerInput').value = draft;
        growComposer();
      }
      updateChar();
    } catch (e) {}
  }).catch(function () {
    state.initialLoaded = true;
    updateEmptyState();
    var loading = $('cfLoadingState');
    if (loading) loading.hidden = true;
    toast('بارگذاری گفتگو ناموفق بود', true);
  });
})();
