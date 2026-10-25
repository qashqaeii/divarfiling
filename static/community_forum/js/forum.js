
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
    wsConnecting: false,
    pollTimer: null,
    heartbeatTimer: null,
    reconnectTimer: null,
    reconnectAttempt: 0,
    lastId: 0,
    lastSyncAt: null,
    sending: false,
    reportReasons: [],
    ui: { editId: null, deleteId: null, reportId: null, reactionId: null },
  };

  function $(id) { return document.getElementById(id); }

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

  function renderMessage(msg) {
    var wrap = document.createElement('div');
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '');
    wrap.dataset.id = String(msg.id);
    var av = document.createElement(msg.avatar_url ? 'img' : 'div');
    av.className = 'cf-msg__avatar';
    if (msg.avatar_url) { av.src = msg.avatar_url; av.alt = ''; }
    var bubble = document.createElement('div');
    bubble.className = 'cf-msg__bubble';
    var meta = document.createElement('div');
    meta.className = 'cf-msg__meta';
    meta.innerHTML = '<span class="cf-msg__name">' + escapeHtml(msg.sender_label) + '</span><span>' +
      formatTime(msg.created_at) + (msg.is_edited ? ' · ویرایش‌شده' : '') + '</span>';
    bubble.appendChild(meta);
    if (msg.reply_to) {
      var rp = document.createElement('div');
      rp.className = 'cf-msg__reply';
      rp.textContent = msg.reply_to.unavailable ? 'پیام در دسترس نیست' :
        ((msg.reply_to.sender_label || '') + ': ' + (msg.reply_to.body_preview || ''));
      bubble.appendChild(rp);
    }
    var body = document.createElement('div');
    body.className = 'cf-msg__body';
    body.textContent = msg.is_deleted ? 'پیام حذف شده' : msg.body;
    bubble.appendChild(body);
    if (msg.reactions && msg.reactions.length) {
      var rx = document.createElement('div');
      rx.className = 'cf-reactions';
      msg.reactions.forEach(function (r) {
        var s = document.createElement('span');
        s.className = 'cf-reaction';
        s.textContent = r.emoji + ' ' + r.count;
        rx.appendChild(s);
      });
      bubble.appendChild(rx);
    }
    if (!msg.is_deleted) {
      var actions = document.createElement('div');
      actions.className = 'cf-msg__actions';
      actions.innerHTML = '<button type="button" data-act="reply">پاسخ</button><button type="button" data-act="react">واکنش</button>';
      if (msg.is_mine) {
        actions.innerHTML += '<button type="button" data-act="edit">ویرایش</button><button type="button" data-act="del">حذف</button>';
      } else {
        actions.innerHTML += '<button type="button" data-act="report">گزارش</button>';
      }
      actions.addEventListener('click', onAction(msg));
      bubble.appendChild(actions);
    }
    wrap.appendChild(av);
    wrap.appendChild(bubble);
    return wrap;
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function renderAll() {
    var el = $('cfMessages');
    if (!el) return;
    var prevH = el.scrollHeight, prevTop = el.scrollTop, lastDay = '';
    el.innerHTML = '';
    state.orderedIds.forEach(function (id) {
      var msg = state.messages.get(id);
      if (!msg) return;
      var dk = dayKey(msg.created_at);
      if (dk && dk !== lastDay) {
        lastDay = dk;
        var sep = document.createElement('div');
        sep.className = 'cf-day-sep';
        sep.textContent = dk;
        el.appendChild(sep);
      }
      el.appendChild(renderMessage(msg));
    });
    if (state.atBottom) scrollToBottom();
    else el.scrollTop = prevTop + (el.scrollHeight - prevH);
  }

  function upsertFromPayload(msg, scrollIfBottom) {
    mergeMessage(msg);
    var near = isNearBottom();
    renderAll();
    if (scrollIfBottom && near) scrollToBottom();
    else if (!near && !msg.is_mine) $('cfNewMsgsBtn').hidden = false;
  }

  function onAction(msg) {
    return function (ev) {
      var act = ev.target.closest('button') && ev.target.closest('button').dataset.act;
      if (act === 'reply') setReply(msg);
      if (act === 'react') openReaction(msg.id);
      if (act === 'edit') openEdit(msg);
      if (act === 'del') openDelete(msg.id);
      if (act === 'report') openReport(msg.id);
    };
  }

  function loadInitial() {
    return fetchJson(messagesUrl).then(function (data) {
      (data.messages || []).forEach(function (m) { mergeMessage(m); });
      state.nextBefore = data.next_before_id;
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
    var url = apiUrl(
      'sync/?anchor_id=' + state.lastId + '&since=' + encodeURIComponent(state.lastSyncAt),
    );
    return fetchJson(url).then(function (data) {
      (data.messages || []).forEach(function (m) { upsertFromPayload(m, false); });
      touchSyncClock();
    }).catch(function () {});
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

  function teardownWs() {
    if (state.heartbeatTimer) { clearInterval(state.heartbeatTimer); state.heartbeatTimer = null; }
    if (state.ws) {
      try { state.ws.onclose = null; state.ws.close(); } catch (e) {}
      state.ws = null;
    }
    state.wsConnecting = false;
  }

  function scheduleReconnect() {
    if (state.reconnectTimer) return;
    var delay = Math.min(30000, 1000 * Math.pow(2, state.reconnectAttempt));
    delay += Math.random() * 500;
    $('cfConnStatus').hidden = false;
    $('cfConnStatus').textContent = 'در حال اتصال مجدد…';
    state.reconnectTimer = setTimeout(function () {
      state.reconnectTimer = null;
      state.reconnectAttempt += 1;
      connectWs();
    }, delay);
  }

  function startPoll() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(function () {
      if (document.hidden || (state.ws && state.ws.readyState === 1)) return;
      fetchMissed().catch(function () {});
    }, 10000);
  }

  function stopPoll() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  function connectWs() {
    if (state.wsConnecting || (state.ws && state.ws.readyState <= 1)) return;
    state.wsConnecting = true;
    teardownWs();
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + wsPath;
    try { state.ws = new WebSocket(url); } catch (e) {
      state.wsConnecting = false;
      startPoll();
      return;
    }
    state.ws.onopen = function () {
      state.wsConnecting = false;
      state.reconnectAttempt = 0;
      $('cfConnStatus').hidden = true;
      stopPoll();
      fetchMissed().catch(function () {});
      state.heartbeatTimer = setInterval(function () {
        if (state.ws && state.ws.readyState === 1) {
          state.ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 25000);
    };
    state.ws.onclose = function () {
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
          if (msg) { msg.reactions = payload.reactions; renderAll(); }
        }
      } catch (err) {}
    };
  }

  function setReply(msg) {
    state.replyToId = msg.id;
    $('cfReplyPreview').hidden = false;
    $('cfReplyPreviewText').textContent = (msg.sender_label || '') + ': ' + (msg.body || '').slice(0, 80);
    $('cfComposerInput').focus();
  }

  function clearReply() {
    state.replyToId = null;
    $('cfReplyPreview').hidden = true;
  }

  function sendMessage(ev) {
    ev.preventDefault();
    if (state.sending) return;
    var text = ($('cfComposerInput').value || '').trim();
    if (!text) return;
    state.sending = true;
    $('cfSendBtn').disabled = true;
    fetchJson(messagesUrl, {
      method: 'POST',
      body: { body: text, reply_to_id: state.replyToId, client_message_id: uuid() },
    }).then(function (data) {
      $('cfComposerInput').value = '';
      updateChar();
      clearReply();
      upsertFromPayload(data.message, true);
      try { localStorage.removeItem(draftKey()); } catch (e) {}
      toast('پیام ارسال شد');
    }).catch(function (err) {
      toast((err && err.error) || 'ارسال ناموفق بود', true);
    }).finally(function () {
      state.sending = false;
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
        if (msg) { msg.reactions = data.reactions; renderAll(); }
      }).catch(function (err) { toast(err.error || 'خطا', true); });
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
            var node = document.querySelector('.cf-msg[data-id="' + m.id + '"]');
            if (node) node.scrollIntoView({ behavior: 'smooth', block: 'center' });
          });
          box.appendChild(row);
        });
      }).catch(function (err) { toast(err.error || 'خطا', true); });
  }

  $('cfComposer').addEventListener('submit', sendMessage);
  $('cfComposerInput').addEventListener('input', function () {
    updateChar();
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
    p.hidden = !p.hidden;
  });
  $('cfSearchInput').addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') runSearch(1);
  });
  $('cfRulesBtn').addEventListener('click', function () { $('cfRulesDialog').showModal(); });
  $('cfProfileBtn').addEventListener('click', function () { $('cfProfileDialog').showModal(); });
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

  window.addEventListener('pagehide', teardownWs);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && (!state.ws || state.ws.readyState !== 1)) connectWs();
  });

  fetchJson(bootstrapUrl).then(function (data) {
    state.myPublicId = data.member && data.member.public_id;
    state.reportReasons = data.report_reasons || [];
    $('cfComposerInput').maxLength = (data.limits && data.limits.max_body) || 2000;
    if (data.pinned_notices && data.pinned_notices.length) {
      $('cfPinned').hidden = false;
      $('cfPinned').textContent = data.pinned_notices.map(function (n) { return n.body; }).join(' — ');
    }
    if (!data.member.welcome_seen) {
      var dlg = $('cfWelcomeDialog');
      dlg.showModal();
      dlg.addEventListener('close', function () {
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
      if (draft) $('cfComposerInput').value = draft;
      updateChar();
    } catch (e) {}
  }).catch(function () {
    $('cfMessages').innerHTML = '<p class="cf-status">بارگذاری گفتگو ناموفق بود.</p>';
  });
})();
