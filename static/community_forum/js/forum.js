(function () {
  'use strict';

  var root = document.getElementById('cfForumApp');
  if (!root) return;

  var csrf = root.dataset.csrf;
  var bootstrapUrl = root.dataset.bootstrapUrl;
  var messagesUrl = root.dataset.apiBase;
  var wsPath = root.dataset.wsPath || '/ws/forum/';

  var state = {
    messages: new Map(),
    orderedIds: [],
    nextBefore: null,
    replyToId: null,
    maxBody: 2000,
    memberPublicId: null,
    atBottom: true,
    ws: null,
    pollTimer: null,
    lastId: 0,
    sending: false,
  };

  var el = {
    messages: document.getElementById('cfMessages'),
    composer: document.getElementById('cfComposer'),
    input: document.getElementById('cfComposerInput'),
    sendBtn: document.getElementById('cfSendBtn'),
    newBtn: document.getElementById('cfNewMsgsBtn'),
    scrollEnd: document.getElementById('cfScrollEndBtn'),
    conn: document.getElementById('cfConnStatus'),
    replyPreview: document.getElementById('cfReplyPreview'),
    replyText: document.getElementById('cfReplyPreviewText'),
    replyCancel: document.getElementById('cfReplyCancel'),
    charCount: document.getElementById('cfCharCount'),
    pinned: document.getElementById('cfPinned'),
  };

  function apiUrl(path) {
    if (path.indexOf('http') === 0) return path;
    return messagesUrl.replace(/messages\/?$/, '') + path.replace(/^\//, '');
  }

  function fetchJson(url, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (opts.method && opts.method !== 'GET') {
      opts.headers['X-CSRFToken'] = csrf;
    }
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
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

  function escapeText(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  function formatTime(iso) {
    try {
      var d = new Date(iso);
      return d.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  }

  function dayKey(iso) {
    try {
      return new Date(iso).toLocaleDateString('fa-IR');
    } catch (e) {
      return '';
    }
  }

  function mergeMessage(msg) {
    if (!msg || !msg.id) return;
    if (!state.messages.has(msg.id)) {
      state.orderedIds.push(msg.id);
      state.orderedIds.sort(function (a, b) { return a - b; });
    }
    state.messages.set(msg.id, msg);
    if (msg.id > state.lastId) state.lastId = msg.id;
  }

  function isNearBottom() {
    if (!el.messages) return true;
    var t = el.messages.scrollHeight - el.messages.scrollTop - el.messages.clientHeight;
    return t < 80;
  }

  function scrollToBottom() {
    if (!el.messages) return;
    el.messages.scrollTop = el.messages.scrollHeight;
    state.atBottom = true;
    el.newBtn.hidden = true;
    el.scrollEnd.hidden = true;
    markRead();
  }

  function markRead() {
    if (!state.lastId) return;
    fetchJson(apiUrl('read/'), { method: 'POST', body: { message_id: state.lastId } }).catch(function () {});
  }

  function renderMessage(msg) {
    var wrap = document.createElement('div');
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '');
    wrap.dataset.id = String(msg.id);

    var av = document.createElement(msg.avatar_url ? 'img' : 'div');
    av.className = 'cf-msg__avatar';
    if (msg.avatar_url) {
      av.src = msg.avatar_url;
      av.alt = '';
    }

    var bubble = document.createElement('div');
    bubble.className = 'cf-msg__bubble';

    var meta = document.createElement('div');
    meta.className = 'cf-msg__meta';
    meta.innerHTML = '<span class="cf-msg__name">' + escapeText(msg.sender_label) + '</span><span>' + formatTime(msg.created_at) + (msg.is_edited ? ' · ویرایش‌شده' : '') + '</span>';

    bubble.appendChild(meta);

    if (msg.reply_to) {
      var rp = document.createElement('div');
      rp.className = 'cf-msg__reply';
      if (msg.reply_to.unavailable) {
        rp.textContent = 'پیام در دسترس نیست';
      } else {
        rp.textContent = (msg.reply_to.sender_label || '') + ': ' + (msg.reply_to.body_preview || '');
      }
      bubble.appendChild(rp);
    }

    var body = document.createElement('div');
    body.className = 'cf-msg__body';
    if (msg.is_deleted) {
      body.textContent = 'پیام حذف شده';
    } else {
      body.textContent = msg.body;
    }
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
      actions.addEventListener('click', function (ev) {
        var btn = ev.target.closest('button');
        if (!btn) return;
        var act = btn.dataset.act;
        if (act === 'reply') setReply(msg);
        if (act === 'react') promptReaction(msg.id);
        if (act === 'edit') promptEdit(msg);
        if (act === 'del') deleteMsg(msg.id);
        if (act === 'report') promptReport(msg.id);
      });
      bubble.appendChild(actions);
    }

    wrap.appendChild(av);
    wrap.appendChild(bubble);
    return wrap;
  }

  function renderAll() {
    if (!el.messages) return;
    var prevH = el.messages.scrollHeight;
    var prevTop = el.messages.scrollTop;
    var lastDay = '';
    el.messages.innerHTML = '';
    state.orderedIds.forEach(function (id) {
      var msg = state.messages.get(id);
      if (!msg) return;
      var dk = dayKey(msg.created_at);
      if (dk && dk !== lastDay) {
        lastDay = dk;
        var sep = document.createElement('div');
        sep.className = 'cf-day-sep';
        sep.textContent = dk;
        el.messages.appendChild(sep);
      }
      el.messages.appendChild(renderMessage(msg));
    });
    if (state.atBottom) {
      scrollToBottom();
    } else {
      el.messages.scrollTop = prevTop + (el.messages.scrollHeight - prevH);
    }
  }

  function upsertFromPayload(msg, scrollIfBottom) {
    mergeMessage(msg);
    var near = isNearBottom();
    renderAll();
    if (scrollIfBottom && near) scrollToBottom();
    else if (!near && !msg.is_mine) el.newBtn.hidden = false;
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
    var prevH = el.messages.scrollHeight;
    return fetchJson(messagesUrl + '?before_id=' + state.nextBefore).then(function (data) {
      (data.messages || []).forEach(function (m) { mergeMessage(m); });
      state.nextBefore = data.next_before_id;
      renderAll();
      el.messages.scrollTop = el.messages.scrollHeight - prevH;
    });
  }

  function setReply(msg) {
    state.replyToId = msg.id;
    el.replyPreview.hidden = false;
    el.replyText.textContent = (msg.sender_label || '') + ': ' + (msg.body || '').slice(0, 80);
    el.input.focus();
  }

  function clearReply() {
    state.replyToId = null;
    el.replyPreview.hidden = true;
  }

  function connectWs() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + wsPath;
    try {
      state.ws = new WebSocket(url);
    } catch (e) {
      startPoll();
      return;
    }
    state.ws.onopen = function () {
      el.conn.hidden = true;
      stopPoll();
    };
    state.ws.onclose = function () {
      el.conn.hidden = false;
      el.conn.textContent = 'در حال اتصال مجدد…';
      startPoll();
      setTimeout(connectWs, 2000 + Math.random() * 2000);
    };
    state.ws.onmessage = function (ev) {
      try {
        var data = JSON.parse(ev.data);
        if (data.type === 'connected' || data.type === 'pong') return;
        var payload = data.payload || {};
        if (data.type === 'message.new' || data.type === 'message.updated') {
          upsertFromPayload(payload.message, true);
        }
        if (data.type === 'message.deleted') {
          var m = state.messages.get(payload.id);
          if (m) {
            m.is_deleted = true;
            m.body = '';
            upsertFromPayload(m, false);
          }
        }
        if (data.type === 'reaction.updated') {
          var msg = state.messages.get(payload.message_id);
          if (msg) {
            msg.reactions = payload.reactions;
            renderAll();
          }
        }
      } catch (err) { /* ignore */ }
    };
    setInterval(function () {
      if (state.ws && state.ws.readyState === 1) {
        state.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 25000);
  }

  function startPoll() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(function () {
      if (document.hidden) return;
      fetchJson(messagesUrl + '?after_id=' + state.lastId).then(function (data) {
        (data.messages || []).forEach(function (m) {
          upsertFromPayload(m, true);
        });
      }).catch(function () {});
    }, 8000);
  }

  function stopPoll() {
    if (state.pollTimer) clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function sendMessage(ev) {
    ev.preventDefault();
    if (state.sending) return;
    var text = (el.input.value || '').trim();
    if (!text) return;
    state.sending = true;
    el.sendBtn.disabled = true;
    var clientId = uuid();
    fetchJson(messagesUrl, {
      method: 'POST',
      body: {
        body: text,
        reply_to_id: state.replyToId,
        client_message_id: clientId,
      },
    }).then(function (data) {
      el.input.value = '';
      updateChar();
      clearReply();
      upsertFromPayload(data.message, true);
      try { localStorage.removeItem('cf_draft'); } catch (e) {}
    }).catch(function (err) {
      alert((err && err.error) || 'ارسال ناموفق بود');
    }).finally(function () {
      state.sending = false;
      el.sendBtn.disabled = !(el.input.value || '').trim();
    });
  }

  function promptReaction(mid) {
    var emoji = window.prompt('واکنش: 👍 ❤️ 👏 😂 🙏', '👍');
    if (!emoji) return;
    fetchJson(apiUrl('messages/' + mid + '/reactions/'), { method: 'POST', body: { emoji: emoji.trim() } })
      .then(function (data) {
        var msg = state.messages.get(mid);
        if (msg) {
          msg.reactions = data.reactions;
          renderAll();
        }
      }).catch(function (err) { alert(err.error || 'خطا'); });
  }

  function promptEdit(msg) {
    var t = window.prompt('ویرایش پیام', msg.body);
    if (t === null) return;
    fetchJson(apiUrl('messages/' + msg.id + '/'), { method: 'PATCH', body: { body: t } })
      .then(function (data) { upsertFromPayload(data.message, false); })
      .catch(function (err) { alert(err.error || 'خطا'); });
  }

  function deleteMsg(id) {
    if (!window.confirm('پیام حذف شود؟')) return;
    fetchJson(apiUrl('messages/' + id + '/'), { method: 'DELETE' })
      .then(function () {
        var m = state.messages.get(id);
        if (m) { m.is_deleted = true; m.body = ''; upsertFromPayload(m, false); }
      });
  }

  function promptReport(mid) {
    var reason = window.prompt('دلیل: spam, inappropriate, pii, fraud, other', 'spam');
    if (!reason) return;
    fetchJson(apiUrl('messages/' + mid + '/report/'), { method: 'POST', body: { reason: reason } })
      .then(function () { alert('گزارش ثبت شد'); })
      .catch(function (err) { alert(err.error || 'خطا'); });
  }

  function updateChar() {
    var n = (el.input.value || '').length;
    el.charCount.textContent = String(n);
    el.sendBtn.disabled = !n || state.sending;
  }

  el.composer.addEventListener('submit', sendMessage);
  el.input.addEventListener('input', function () {
    updateChar();
    try { localStorage.setItem('cf_draft', el.input.value); } catch (e) {}
    el.input.style.height = 'auto';
    el.input.style.height = Math.min(el.input.scrollHeight, 140) + 'px';
  });
  el.input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      el.composer.requestSubmit();
    }
  });
  el.replyCancel.addEventListener('click', clearReply);
  el.newBtn.addEventListener('click', scrollToBottom);
  el.scrollEnd.addEventListener('click', scrollToBottom);
  el.messages.addEventListener('scroll', function () {
    state.atBottom = isNearBottom();
    if (state.atBottom) {
      el.newBtn.hidden = true;
      el.scrollEnd.hidden = true;
      markRead();
    } else {
      el.scrollEnd.hidden = false;
    }
    if (el.messages.scrollTop < 40) loadOlder();
  });

  document.getElementById('cfRulesBtn').addEventListener('click', function () {
    document.getElementById('cfRulesDialog').showModal();
  });
  document.getElementById('cfProfileBtn').addEventListener('click', function () {
    document.getElementById('cfProfileDialog').showModal();
  });
  document.getElementById('cfProfileClose').addEventListener('click', function () {
    document.getElementById('cfProfileDialog').close();
  });
  document.getElementById('cfProfileSave').addEventListener('click', function () {
    var name = document.getElementById('cfDisplayNameInput').value;
    fetchJson(apiUrl('profile/'), { method: 'POST', body: { display_name: name } })
      .then(function () { document.getElementById('cfProfileDialog').close(); })
      .catch(function (err) {
        var er = document.getElementById('cfProfileError');
        er.hidden = false;
        er.textContent = err.error || 'خطا';
      });
  });

  fetchJson(bootstrapUrl).then(function (data) {
    state.maxBody = (data.limits && data.limits.max_body) || 2000;
    state.memberPublicId = data.member && data.member.public_id;
    el.input.maxLength = state.maxBody;
    if (data.pinned_notices && data.pinned_notices.length) {
      el.pinned.hidden = false;
      el.pinned.textContent = data.pinned_notices.map(function (n) { return n.body; }).join(' — ');
    }
    if (!data.member.welcome_seen) {
      var dlg = document.getElementById('cfWelcomeDialog');
      dlg.showModal();
      dlg.addEventListener('close', function () {
        fetchJson(apiUrl('profile/'), { method: 'POST', body: { welcome_ack: true } });
      });
    }
    return loadInitial();
  }).then(function () {
    connectWs();
    try {
      var draft = localStorage.getItem('cf_draft');
      if (draft) el.input.value = draft;
      updateChar();
    } catch (e) {}
  }).catch(function () {
    if (el.messages) el.messages.innerHTML = '<p class="cf-status">بارگذاری گفتگو ناموفق بود.</p>';
  });
})();
