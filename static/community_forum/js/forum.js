
(function () {
  'use strict';

  var root = document.getElementById('cfForumApp');
  if (!root) return;

  var csrf = root.dataset.csrf;
  var bootstrapUrl = root.dataset.bootstrapUrl;
  var messagesUrl = root.dataset.apiBase;
  var wsPath = root.dataset.wsPath || '/ws/forum/';
  var EMOJIS = (window.CFForumEmoji && window.CFForumEmoji.REACTION_EMOJIS) ||
    ['👍', '❤️', '👏', '😂', '🙏'];
  var maxBodyLen = 2000;
  var reactionPopover = null;

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
    canModerate: false,
    pinnedMessage: null,
    ui: { editId: null, deleteId: null, reportId: null, reactionId: null, activeMsgId: null },
    initialLoaded: false,
    viewPending: new Set(),
    viewRecorded: new Set(),
    viewObserver: null,
    viewFlushTimer: null,
    welcomeSeen: false,
    welcomeAckInFlight: false,
  };

  var overlay = { hideTimer: null, stripOpen: false };
  var DEFAULT_DBL_REACTION = '❤️';

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

  function welcomeAckStorageKey() {
    return state.myPublicId ? 'cf_welcome_ack:' + state.myPublicId : 'cf_welcome_ack:anon';
  }

  function hasLocalWelcomeAck() {
    try {
      return localStorage.getItem(welcomeAckStorageKey()) === '1';
    } catch (e) {
      return false;
    }
  }

  function setLocalWelcomeAck() {
    try {
      localStorage.setItem(welcomeAckStorageKey(), '1');
    } catch (e) {}
  }

  function ackWelcomeSeen() {
    if (state.welcomeSeen || state.welcomeAckInFlight) return;
    state.welcomeAckInFlight = true;
    state.welcomeSeen = true;
    setLocalWelcomeAck();
    fetchJson(apiUrl('profile/'), { method: 'POST', body: { welcome_ack: true } })
      .catch(function () {})
      .finally(function () {
        state.welcomeAckInFlight = false;
      });
  }

  function initForumComposerVoice() {
    var root = $('cfComposerVoiceRoot');
    var input = $('cfComposerInput');
    var micBtn = $('cfComposerVoiceBtn');
    if (!root || !input || !micBtn || root.dataset.crmFieldVoiceReady === '1') {
      return !!root && root.dataset.crmFieldVoiceReady === '1';
    }
    var Voice = window.CrmSmartCommandVoice;
    if (!Voice || typeof Voice.createVoiceInputAdapter !== 'function') {
      return false;
    }
    var statusEl = root.querySelector('[data-crm-field-voice-status]');
    if (typeof Voice.isSpeechRecognitionSupported === 'function' && !Voice.isSpeechRecognitionSupported()) {
      micBtn.classList.add('is-unsupported');
      micBtn.setAttribute('aria-disabled', 'true');
      micBtn.title = 'ورود صوتی در این مرورگر پشتیبانی نمی‌شود';
    }
    Voice.createVoiceInputAdapter(root, {
      input: input,
      micBtn: micBtn,
      voiceStatusEl: statusEl,
      micAriaStart: 'دستیار صوتی',
      micAriaStop: 'توقف دستیار صوتی',
      micTooltip: 'دستیار صوتی',
      silenceTimeoutMs: 3500,
      getInputValue: function () {
        return input.value || '';
      },
      setInputValue: function (text) {
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      },
      getSelectionRange: function () {
        return { start: input.selectionStart, end: input.selectionEnd };
      },
      setSelectionRange: function (start, end) {
        try {
          input.setSelectionRange(start, end);
        } catch (e) {}
      },
      isInputDisabled: function () {
        return !!input.disabled;
      },
    });
    if (statusEl && typeof MutationObserver !== 'undefined') {
      var lastToast = '';
      var obs = new MutationObserver(function () {
        if (statusEl.hidden || !statusEl.classList.contains('is-error')) return;
        var msg = (statusEl.textContent || '').trim();
        if (!msg || msg === lastToast) return;
        lastToast = msg;
        toast(msg, true);
      });
      obs.observe(statusEl, {
        attributes: true,
        attributeFilter: ['hidden', 'class'],
        childList: true,
        characterData: true,
        subtree: true,
      });
    }
    root.dataset.crmFieldVoiceReady = '1';
    return true;
  }

  function scheduleForumComposerVoice() {
    if (initForumComposerVoice()) return;
    var attempts = 0;
    (function retry() {
      attempts += 1;
      if (initForumComposerVoice() || attempts >= 40) return;
      setTimeout(retry, 75);
    })();
    document.addEventListener('DOMContentLoaded', initForumComposerVoice);
    window.addEventListener('load', initForumComposerVoice);
  }

  function maybeShowWelcomeDialog(member) {
    var seen = !!(member && member.welcome_seen) || hasLocalWelcomeAck();
    if (seen) {
      state.welcomeSeen = true;
      return;
    }
    var dlg = $('cfWelcomeDialog');
    if (!dlg) return;
    var onClose = function () {
      ackWelcomeSeen();
    };
    dlg.addEventListener('close', onClose);
    var ackBtn = $('cfWelcomeAck');
    if (ackBtn) {
      ackBtn.addEventListener('click', function () {
        dlg.close();
      }, { once: true });
    }
    openDialog(dlg);
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
    if (msg.view_count == null) msg.view_count = 0;
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

  function formatViewCount(n) {
    var num = Number(n) || 0;
    if (num < 1) return '';
    try {
      return num.toLocaleString('fa-IR');
    } catch (e) {
      return String(num);
    }
  }

  function updateBubbleFoot(bubble, msg) {
    if (!bubble || !msg || msg.is_deleted) return;
    var foot = bubble.querySelector('.cf-msg__bubble-foot');
    if (!foot) {
      foot = document.createElement('div');
      foot.className = 'cf-msg__bubble-foot';
      bubble.appendChild(foot);
    }
    var vc = msg.view_count || 0;
    var html = '';
    if (vc > 0) {
      html += '<span class="cf-msg__views" title="تعداد بازدید">' +
        '<i class="fas fa-eye" aria-hidden="true"></i>' +
        '<span class="cf-msg__views-num">' + formatViewCount(vc) + '</span></span>';
    }
    html += '<span class="cf-msg__time-inline">' + formatTime(msg.created_at) +
      (msg.is_edited ? ' <span class="cf-msg__edited">· ویرایش‌شده</span>' : '') + '</span>';
    foot.innerHTML = html;
  }

  function applyViewCounts(map) {
    if (!map) return;
    Object.keys(map).forEach(function (key) {
      var id = Number(key);
      var m = state.messages.get(id);
      if (!m) return;
      m.view_count = map[key];
      var node = findMessageNode(id);
      if (!node) return;
      var bubble = node.querySelector('.cf-msg__bubble');
      updateBubbleFoot(bubble, m);
    });
  }

  function queueMessageView(mid) {
    if (!mid || state.viewRecorded.has(mid) || state.viewPending.has(mid)) return;
    var m = state.messages.get(mid);
    if (!m || m.is_deleted) return;
    state.viewPending.add(mid);
    clearTimeout(state.viewFlushTimer);
    state.viewFlushTimer = setTimeout(flushMessageViews, 420);
  }

  function flushMessageViews() {
    var ids = [];
    state.viewPending.forEach(function (id) {
      if (ids.length < 40) ids.push(id);
    });
    if (!ids.length) return;
    ids.forEach(function (id) { state.viewPending.delete(id); });
    fetchJson(apiUrl('views/'), { method: 'POST', body: { message_ids: ids } })
      .then(function (data) {
        ids.forEach(function (id) { state.viewRecorded.add(id); });
        applyViewCounts(data.views || {});
      })
      .catch(function () {
        ids.forEach(function (id) { state.viewPending.add(id); });
      });
  }

  function rescanViewObservers() {
    if (!state.viewObserver) return;
    state.viewObserver.disconnect();
    var list = $('cfMessages');
    if (!list) return;
    list.querySelectorAll('.cf-msg:not(.cf-msg--deleted)').forEach(function (row) {
      state.viewObserver.observe(row);
    });
  }

  function initViewObservers() {
    var list = $('cfMessages');
    if (!list || !window.IntersectionObserver) return;
    if (state.viewObserver) state.viewObserver.disconnect();
    state.viewObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (ent) {
        if (!ent.isIntersecting || ent.intersectionRatio < 0.42) return;
        var row = ent.target;
        if (!row || !row.dataset.id) return;
        queueMessageView(Number(row.dataset.id));
      });
    }, { root: list, threshold: [0.42, 0.65, 0.9] });
    rescanViewObservers();
  }

  function dayKey(iso) {
    try { return new Date(iso).toLocaleDateString('fa-IR'); } catch (e) { return ''; }
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function isNoticeMessage(msg) {
    if (!msg || msg.is_mine) return false;
    var l = (msg.sender_label || '').toLowerCase();
    return l.indexOf('مدیریت') >= 0 || l.indexOf('فایلینگ دیوار') >= 0 || l.indexOf('پشتیبانی') >= 0;
  }

  function shouldGroupWith(prev, msg) {
    if (!prev || prev.is_deleted || msg.is_deleted || isNoticeMessage(msg) || isNoticeMessage(prev)) return false;
    if (prev.sender_public_id !== msg.sender_public_id) return false;
    if (dayKey(prev.created_at) !== dayKey(msg.created_at)) return false;
    try {
      return (new Date(msg.created_at) - new Date(prev.created_at)) < 300000;
    } catch (e) { return false; }
  }

  function setMessageBody(el, text, useRich) {
    if (!el) return;
    el.textContent = '';
    var s = text || '';
    if (!s) return;
    if (!useRich || s.indexOf('**') < 0) {
      el.textContent = s;
      return;
    }
    var re = /\*\*([^*]+)\*\*/g;
    var last = 0;
    var m;
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) el.appendChild(document.createTextNode(s.slice(last, m.index)));
      var strong = document.createElement('strong');
      strong.textContent = m[1];
      el.appendChild(strong);
      last = m.index + m[0].length;
    }
    if (last < s.length) el.appendChild(document.createTextNode(s.slice(last)));
  }

  function isMobileUi() {
    return window.matchMedia('(max-width: 768px)').matches;
  }

  function isDesktopUi() {
    return !isMobileUi() && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  }

  function msgById(id) {
    return state.messages.get(Number(id));
  }

  function fillReactions(rx, msg) {
    if (!rx) return;
    rx.innerHTML = '';
    (msg.reactions || []).forEach(function (r) {
      var s = document.createElement('button');
      s.type = 'button';
      s.className = 'cf-reaction';
      if (msg.my_reaction === r.emoji) s.classList.add('cf-reaction--mine');
      s.dataset.mid = String(msg.id);
      s.dataset.emoji = r.emoji;
      s.textContent = r.emoji + ' ' + r.count;
      rx.appendChild(s);
    });
  }

  function optimisticReaction(msg, emoji) {
    var mine = msg.my_reaction || '';
    var list = (msg.reactions || []).map(function (r) { return { emoji: r.emoji, count: r.count }; });
    function dec(e) {
      list = list.map(function (r) {
        if (r.emoji !== e) return r;
        var c = r.count - 1;
        return c > 0 ? { emoji: r.emoji, count: c } : null;
      }).filter(Boolean);
    }
    function inc(e) {
      var f = list.filter(function (r) { return r.emoji === e; })[0];
      if (f) f.count += 1;
      else list.push({ emoji: e, count: 1 });
    }
    if (!emoji) {
      if (mine) dec(mine);
      msg.my_reaction = '';
    } else {
      if (mine && mine !== emoji) dec(mine);
      if (mine === emoji) {
        dec(emoji);
        msg.my_reaction = '';
      } else {
        inc(emoji);
        msg.my_reaction = emoji;
      }
    }
    msg.reactions = list;
  }

  function scrollToMessageId(id, highlight) {
    if (!id) return;
    if (!state.messages.has(id)) {
      return fetchJson(messagesUrl + '?before_id=' + (id + 1)).then(function (data) {
        (data.messages || []).forEach(function (m) { mergeMessage(m); });
        renderAll();
        focusMessageNode(id, highlight);
      }).catch(function () { toast('پیام پیدا نشد', true); });
    }
    focusMessageNode(id, highlight);
    return Promise.resolve();
  }

  function focusMessageNode(id, highlight) {
    var node = findMessageNode(id);
    if (!node) { toast('پیام در این بخش از گفتگو نیست', true); return; }
    node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (highlight) {
      node.classList.add('cf-msg--flash');
      setTimeout(function () { node.classList.remove('cf-msg--flash'); }, 2200);
    }
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

  function overlayRoot(id) {
    return $(id);
  }

  function isOverlayEl(el) {
    return !!(el && el.closest && el.closest('#cfQuickBar, #cfReactStrip, #cfMoreMenu'));
  }

  function overlayHovered() {
    return ['cfQuickBar', 'cfReactStrip', 'cfMoreMenu'].some(function (id) {
      var el = overlayRoot(id);
      return el && !el.hidden && el.matches(':hover');
    });
  }

  function scheduleOverlayHide() {
    clearTimeout(overlay.hideTimer);
    overlay.hideTimer = setTimeout(function () {
      if (overlayHovered()) return;
      closeOverlays();
    }, 320);
  }

  function closeOverlays() {
    clearTimeout(overlay.hideTimer);
    overlay.stripOpen = false;
    state.ui.activeMsgId = null;
    ['cfQuickBar', 'cfReactStrip', 'cfMoreMenu'].forEach(function (id) {
      var el = overlayRoot(id);
      if (el) {
        el.classList.remove('is-visible');
        el.hidden = true;
      }
    });
  }

  function bindOverlayHover(el) {
    if (!el || el._cfHoverBound) return;
    el._cfHoverBound = true;
    el.addEventListener('mouseenter', function () { clearTimeout(overlay.hideTimer); });
    el.addEventListener('mouseleave', function () { scheduleOverlayHide(); });
  }

  function secondaryMenuItems(msg) {
    var items = [];
    if (state.canModerate && !msg.is_deleted) {
      items.push({
        act: msg.is_pinned ? 'unpin' : 'pin',
        label: msg.is_pinned ? 'برداشتن سنجاق' : 'سنجاق پیام',
        icon: 'fa-thumbtack',
      });
    }
    if (msg.is_mine) {
      items.push({ act: 'edit', label: 'ویرایش', icon: 'fa-pen' });
      items.push({ act: 'del', label: 'حذف', danger: true, icon: 'fa-trash' });
    } else {
      items.push({ act: 'report', label: 'گزارش', danger: true, icon: 'fa-flag' });
    }
    return items;
  }

  function a11yMenuItems(msg) {
    return [
      { act: 'reply', label: 'پاسخ', icon: 'fa-reply' },
      { act: 'react', label: 'واکنش', icon: 'fa-smile' },
      { act: 'copy', label: 'کپی متن', icon: 'fa-copy' },
    ];
  }

  function onMenuAction(msg, act) {
    closeOverlays();
    if (act === 'reply') setReply(msg);
    if (act === 'react') openReactionPicker(msg.id);
    if (act === 'edit') openEdit(msg);
    if (act === 'del') openDelete(msg.id);
    if (act === 'report') openReport(msg.id);
    if (act === 'copy') copyMessageText(msg);
    if (act === 'pin') togglePin(msg.id, true);
    if (act === 'unpin') togglePin(msg.id, false);
  }

  function pinnedPreview(body) {
    var t = (body || '').replace(/\s+/g, ' ').trim();
    if (t.length > 72) return t.slice(0, 72) + '…';
    return t;
  }

  function applyPinnedMessage(pinnedMsg) {
    state.pinnedMessage = pinnedMsg || null;
    state.messages.forEach(function (m) {
      if (m.is_pinned) m.is_pinned = false;
    });
    if (pinnedMsg) {
      mergeMessage(pinnedMsg);
      var stored = state.messages.get(pinnedMsg.id);
      if (stored) stored.is_pinned = true;
    }
    renderPinnedBar();
    state.orderedIds.forEach(function (id) {
      var node = findMessageNode(id);
      var m = state.messages.get(id);
      if (node && m) node.classList.toggle('cf-msg--pinned', !!m.is_pinned);
    });
  }

  function renderPinnedBar() {
    var root = $('cfPinnedMsg');
    if (!root) return;
    var pm = state.pinnedMessage;
    if (!pm || pm.is_deleted) {
      root.hidden = true;
      var unpin = $('cfPinnedMsgUnpin');
      if (unpin) unpin.hidden = true;
      return;
    }
    root.hidden = false;
    var who = $('cfPinnedMsgWho');
    var prev = $('cfPinnedMsgPreview');
    if (who) who.textContent = pm.sender_label || '';
    if (prev) prev.textContent = pinnedPreview(pm.body);
    var unpinBtn = $('cfPinnedMsgUnpin');
    if (unpinBtn) unpinBtn.hidden = !state.canModerate;
  }

  function scrollToMessage(id, flash) {
    var node = findMessageNode(id);
    if (!node) return;
    node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (flash) {
      node.classList.add('cf-msg--flash');
      setTimeout(function () { node.classList.remove('cf-msg--flash'); }, 1200);
    }
  }

  function togglePin(id, pin) {
    return fetchJson(apiUrl('messages/' + id + '/pin/'), { method: 'POST', body: { pin: pin } })
      .then(function (data) {
        applyPinnedMessage(data.pinned_message);
        toast(pin ? 'پیام سنجاق شد' : 'سنجاق برداشته شد');
      })
      .catch(function (err) { toast(err.error || 'خطا', true); });
  }

  function appendAvatar(wrap, msg) {
    var shell = document.createElement('div');
    shell.className = 'cf-msg__avatar-wrap';
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
    if (msg.sender_is_moderator) {
      var crown = document.createElement('span');
      crown.className = 'cf-msg__crown';
      crown.setAttribute('aria-hidden', 'true');
      crown.innerHTML = '<i class="fas fa-crown"></i>';
      shell.appendChild(crown);
    }
    shell.appendChild(av);
    wrap.appendChild(shell);
  }

  function copyMessageText(msg) {
    var text = msg.is_deleted ? '' : (msg.body || '');
    if (!text) { toast('متنی برای کپی نیست', true); return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast('متن کپی شد'); })
        .catch(function () { toast('کپی ناموفق بود', true); });
      return;
    }
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      toast('متن کپی شد');
    } catch (e) {
      toast('کپی ناموفق بود', true);
    }
  }

  function buildMessageEl(msg, opts) {
    opts = opts || {};
    var wrap = document.createElement('div');
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '') + (msg.is_deleted ? ' cf-msg--deleted' : '');
    if (opts.grouped) wrap.classList.add('cf-msg--grouped');
    if (isNoticeMessage(msg)) wrap.classList.add('cf-msg--notice');
    if (msg.is_pinned) wrap.classList.add('cf-msg--pinned');
    if (msg.sender_is_moderator) wrap.classList.add('cf-msg--moderator');
    wrap.dataset.id = String(msg.id);
    if (!msg.is_deleted) wrap.tabIndex = 0;

    var stack = document.createElement('div');
    stack.className = 'cf-msg__stack';

    var meta = document.createElement('div');
    meta.className = 'cf-msg__meta';
    meta.innerHTML = '<span class="cf-msg__name">' + escapeHtml(msg.sender_label) + '</span>';
    if (!msg.is_deleted) {
      var actBtn = document.createElement('button');
      actBtn.type = 'button';
      actBtn.className = 'cf-msg__act';
      actBtn.setAttribute('aria-label', 'عملیات پیام');
      actBtn.innerHTML = '<i class="fas fa-ellipsis-v" aria-hidden="true"></i>';
      meta.appendChild(actBtn);
    }

    var swipeWrap = document.createElement('div');
    swipeWrap.className = 'cf-msg__swipe';
    var swipeHint = document.createElement('div');
    swipeHint.className = 'cf-msg__swipe-hint';
    swipeHint.innerHTML = '<i class="fas fa-reply" aria-hidden="true"></i>';
    swipeWrap.appendChild(swipeHint);

    var bubble = document.createElement('div');
    bubble.className = 'cf-msg__bubble';

    if (msg.reply_to) {
      var rp = document.createElement('button');
      rp.type = 'button';
      rp.className = 'cf-msg__reply';
      rp.textContent = msg.reply_to.unavailable ? 'پیام در دسترس نیست' :
        ((msg.reply_to.sender_label || '') + ': ' + (msg.reply_to.body_preview || ''));
      if (!msg.reply_to.unavailable && msg.reply_to.id) {
        rp.dataset.replyTo = String(msg.reply_to.id);
      } else {
        rp.disabled = true;
      }
      bubble.appendChild(rp);
    }

    var body = document.createElement('div');
    body.className = 'cf-msg__body';
    body.setAttribute('dir', 'auto');
    if (msg.is_deleted) body.textContent = 'پیام حذف شده';
    else setMessageBody(body, msg.body, isNoticeMessage(msg));
    bubble.appendChild(body);

    var rx = document.createElement('div');
    rx.className = 'cf-reactions';
    fillReactions(rx, msg);
    bubble.appendChild(rx);
    updateBubbleFoot(bubble, msg);

    swipeWrap.appendChild(bubble);
    stack.appendChild(meta);
    stack.appendChild(swipeWrap);
    appendAvatar(wrap, msg);
    wrap.appendChild(stack);
    return wrap;
  }

  function patchMessageEl(wrap, msg) {
    msg = normalizeIncoming(msg);
    wrap.className = 'cf-msg' + (msg.is_mine ? ' cf-msg--mine' : '') +
      (msg.is_deleted ? ' cf-msg--deleted' : '') +
      (msg.is_pinned ? ' cf-msg--pinned' : '') +
      (msg.sender_is_moderator ? ' cf-msg--moderator' : '');
    var body = wrap.querySelector('.cf-msg__body');
    if (body) {
      if (msg.is_deleted) body.textContent = 'پیام حذف شده';
      else setMessageBody(body, msg.body, isNoticeMessage(msg));
    }
    var meta = wrap.querySelector('.cf-msg__meta');
    if (meta) {
      var act = meta.querySelector('.cf-msg__act');
      meta.innerHTML = '<span class="cf-msg__name">' + escapeHtml(msg.sender_label) + '</span>';
      if (!msg.is_deleted && act) meta.appendChild(act);
    }
    fillReactions(wrap.querySelector('.cf-reactions'), msg);
    updateBubbleFoot(wrap.querySelector('.cf-msg__bubble'), msg);
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
    var prevMsg = null;
    state.orderedIds.forEach(function (id) {
      var msg = state.messages.get(id);
      if (!msg) return;
      var dk = dayKey(msg.created_at);
      if (dk && dk !== lastDay) {
        lastDay = dk;
        prevMsg = null;
        var sep = document.createElement('div');
        sep.className = 'cf-day-sep';
        sep.dataset.day = dk;
        sep.textContent = dk;
        el.appendChild(sep);
      }
      el.appendChild(buildMessageEl(msg, { grouped: shouldGroupWith(prevMsg, msg) }));
      if (!msg.is_deleted) prevMsg = msg;
    });
    if (loading) el.appendChild(loading);
    if (empty) el.appendChild(empty);
    updateEmptyState();
    if (state.atBottom) scrollToBottom();
    else el.scrollTop = prevTop + (el.scrollHeight - prevH);
    rescanViewObservers();
  }

  function appendMessageDom(msg) {
    var el = $('cfMessages');
    var prevId = state.orderedIds[state.orderedIds.indexOf(msg.id) - 1];
    var prevMsg = prevId ? state.messages.get(prevId) : null;
    var node = buildMessageEl(msg, { grouped: shouldGroupWith(prevMsg, msg) });
    var loading = $('cfLoadingState');
    var empty = $('cfEmptyState');
    ensureDaySepBefore(msg, loading || empty);
    if (loading && loading.parentNode === el) el.insertBefore(node, loading);
    else if (empty && empty.parentNode === el) el.insertBefore(node, empty);
    else el.appendChild(node);
    updateEmptyState();
    if (state.viewObserver) state.viewObserver.observe(node);
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
          if (m) {
            m.is_deleted = true;
            m.body = '';
            if (state.pinnedMessage && state.pinnedMessage.id === m.id) applyPinnedMessage(null);
            upsertFromPayload(m, false);
          }
        } else if (data.type === 'message.pinned') {
          applyPinnedMessage(payload.pinned_message || null);
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
    if (!msg || msg.is_deleted) return;
    closeOverlays();
    state.replyToId = msg.id;
    showEl($('cfReplyPreview'));
    $('cfReplyPreviewText').textContent = (msg.sender_label || '') + ': ' + (msg.body || '').slice(0, 120);
    var input = $('cfComposerInput');
    if (input) {
      input.focus();
      try { input.setSelectionRange(input.value.length, input.value.length); } catch (e) {}
    }
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

  function openReactionPicker(id) {
    state.ui.reactionId = id;
    closeOverlays();
    var pick = $('cfEmojiPick');
    if (!pick) return;
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
    openDialog($('cfReactionDialog'));
  }

  function postReaction(mid, emoji) {
    var msg = state.messages.get(mid);
    if (!msg || msg.is_deleted) return;
    if (emoji && EMOJIS.indexOf(emoji) < 0) return;
    var snapshot = {
      reactions: (msg.reactions || []).map(function (r) { return { emoji: r.emoji, count: r.count }; }),
      my_reaction: msg.my_reaction || '',
    };
    var nextEmoji = emoji;
    if (emoji && msg.my_reaction === emoji) nextEmoji = null;
    optimisticReaction(msg, nextEmoji);
    var node = findMessageNode(mid);
    if (node) patchMessageEl(node, msg);
    return fetchJson(apiUrl('messages/' + mid + '/reactions/'), { method: 'POST', body: { emoji: nextEmoji } })
      .then(function (data) {
        msg.reactions = data.reactions;
        msg.my_reaction = nextEmoji || '';
        if (node) patchMessageEl(node, msg);
      })
      .catch(function (err) {
        msg.reactions = snapshot.reactions;
        msg.my_reaction = snapshot.my_reaction;
        if (node) patchMessageEl(node, msg);
        toast(err.error || 'خطا', true);
      });
  }

  function anchorBubble(msgEl) {
    return msgEl ? msgEl.querySelector('.cf-msg__bubble') : null;
  }

  function placeFloating(el, anchorRect, offsetY, gapPx) {
    if (!el || !anchorRect) return;
    el.hidden = false;
    el.style.visibility = 'hidden';
    el.classList.add('is-visible');
    var w = el.offsetWidth;
    var h = el.offsetHeight;
    var gap = gapPx != null ? gapPx : 4;
    var top = anchorRect.top - h - gap + (offsetY || 0);
    if (top < 8) top = anchorRect.bottom + gap;
    var left = anchorRect.left + (anchorRect.width / 2) - (w / 2);
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - h - 8));
    el.style.top = top + 'px';
    el.style.left = left + 'px';
    el.style.visibility = '';
  }

  function showQuickBar(msgEl) {
    if (!isDesktopUi() || !msgEl || msgEl.classList.contains('cf-msg--deleted')) return;
    var bar = $('cfQuickBar');
    if (!bar) return;
    var bubble = anchorBubble(msgEl);
    if (!bubble) return;
    var mid = Number(msgEl.dataset.id);
    if (state.ui.activeMsgId === mid && bar.classList.contains('is-visible') && !overlay.stripOpen) {
      clearTimeout(overlay.hideTimer);
      return;
    }
    closeOverlays();
    state.ui.activeMsgId = mid;
    placeFloating(bar, bubble.getBoundingClientRect(), 0, 2);
    bar.classList.add('is-visible');
    bar.hidden = false;
  }

  function placeStripOnQuickBar(strip, bar) {
    if (!strip || !bar) return;
    strip.hidden = false;
    strip.style.visibility = 'hidden';
    strip.classList.add('is-visible');
    var barRect = bar.getBoundingClientRect();
    var w = strip.offsetWidth;
    var h = strip.offsetHeight;
    var gap = 2;
    var top = barRect.top - h - gap;
    var left = barRect.left + (barRect.width / 2) - (w / 2);
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    if (top < 8) top = barRect.bottom + gap;
    strip.style.top = top + 'px';
    strip.style.left = left + 'px';
    strip.style.visibility = '';
  }

  function showReactStrip(msgEl) {
    var strip = $('cfReactStrip');
    var bar = $('cfQuickBar');
    if (!strip || !bar || !msgEl) return;
    var mid = Number(msgEl.dataset.id);
    var msg = msgById(mid);
    if (!msg) return;
    clearTimeout(overlay.hideTimer);
    state.ui.activeMsgId = mid;
    if (!bar.classList.contains('is-visible')) {
      showQuickBar(msgEl);
    }
    strip.innerHTML = '';
    EMOJIS.forEach(function (em) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'cf-react-strip__btn';
      b.textContent = em;
      b.setAttribute('role', 'option');
      if (msg.my_reaction === em) b.classList.add('is-mine');
      b.addEventListener('click', function () {
        postReaction(mid, em);
        closeOverlays();
      });
      strip.appendChild(b);
    });
    var more = document.createElement('button');
    more.type = 'button';
    more.className = 'cf-react-strip__more';
    more.textContent = '+';
    more.setAttribute('aria-label', 'واکنش‌های بیشتر');
    more.addEventListener('click', function () {
      openReactionPicker(mid);
    });
    strip.appendChild(more);
    overlay.stripOpen = true;
    placeStripOnQuickBar(strip, bar);
  }

  function showMoreMenu(msgEl) {
    var menu = $('cfMoreMenu');
    if (!menu || !msgEl) return;
    var msg = msgById(Number(msgEl.dataset.id));
    if (!msg) return;
    menu.innerHTML = '';
    secondaryMenuItems(msg).forEach(function (item) {
      menu.appendChild(menuButton(item, msg));
    });
    var sep = document.createElement('div');
    sep.className = 'cf-more-menu__sep';
    sep.setAttribute('role', 'separator');
    menu.appendChild(sep);
    a11yMenuItems(msg).forEach(function (item) {
      menu.appendChild(menuButton(item, msg));
    });
    placeFloating(menu, anchorBubble(msgEl).getBoundingClientRect());
    menu.hidden = false;
    menu.classList.add('is-visible');
  }

  function menuButton(item, msg) {
    var b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('role', 'menuitem');
    if (item.danger) b.className = 'cf-menu-danger';
    b.innerHTML = '<i class="fas ' + item.icon + '" aria-hidden="true"></i><span>' + item.label + '</span>';
    b.addEventListener('click', function () { onMenuAction(msg, item.act); });
    return b;
  }

  function openMobileSheet(mid) {
    var msg = msgById(mid);
    if (!msg) return;
    closeOverlays();
    var list = $('cfMsgSheetList');
    var dlg = $('cfMsgSheet');
    if (!list || !dlg) return;
    list.innerHTML = '';
    var quick = [
      { act: 'reply', label: 'پاسخ', icon: 'fa-reply' },
      { act: 'react', label: 'واکنش', icon: 'fa-smile' },
      { act: 'copy', label: 'کپی متن', icon: 'fa-copy' },
    ].concat(secondaryMenuItems(msg));
    quick.forEach(function (item) {
      var b = document.createElement('button');
      b.type = 'button';
      if (item.danger) b.className = 'cf-menu-danger';
      b.innerHTML = '<i class="fas ' + item.icon + '" aria-hidden="true"></i><span>' + item.label + '</span>';
      b.addEventListener('click', function () {
        dlg.close();
        onMenuAction(msg, item.act);
      });
      list.appendChild(b);
    });
    openDialog(dlg);
  }

  function initMessageInteractions() {
    var list = $('cfMessages');
    if (!list) return;

    list.addEventListener('click', function (ev) {
      var reactBtn = ev.target.closest('.cf-reaction');
      if (reactBtn) {
        ev.preventDefault();
        var mid = Number(reactBtn.dataset.mid);
        var emoji = reactBtn.dataset.emoji;
        var m = msgById(mid);
        if (m) postReaction(mid, m.my_reaction === emoji ? null : emoji);
        return;
      }
      var replyLink = ev.target.closest('.cf-msg__reply[data-reply-to]');
      if (replyLink) {
        ev.preventDefault();
        scrollToMessageId(Number(replyLink.dataset.replyTo), true);
        return;
      }
      var act = ev.target.closest('.cf-msg__act');
      if (act) {
        ev.stopPropagation();
        var row = act.closest('.cf-msg');
        if (row) openMobileSheet(Number(row.dataset.id));
        return;
      }
      if (!ev.target.closest('#cfQuickBar, #cfReactStrip, #cfMoreMenu')) {
        if (!ev.target.closest('.cf-msg__bubble, .cf-msg__meta')) closeOverlays();
      }
    });

    list.addEventListener('dblclick', function (ev) {
      if (!isDesktopUi()) return;
      if (ev.target.closest('button, a, .cf-reaction')) return;
      var sel = window.getSelection && window.getSelection();
      if (sel && sel.toString().trim()) return;
      var bubble = ev.target.closest('.cf-msg__bubble');
      if (!bubble) return;
      var row = bubble.closest('.cf-msg');
      if (!row || row.classList.contains('cf-msg--deleted')) return;
      var mid = Number(row.dataset.id);
      var m = msgById(mid);
      if (!m) return;
      postReaction(mid, m.my_reaction === DEFAULT_DBL_REACTION ? null : DEFAULT_DBL_REACTION);
    });

    list.addEventListener('keydown', function (ev) {
      var row = ev.target.closest('.cf-msg');
      if (!row) return;
      var m = msgById(Number(row.dataset.id));
      if (!m) return;
      if (ev.key === 'r' || ev.key === 'R') {
        if (ev.ctrlKey || ev.metaKey) return;
        ev.preventDefault();
        setReply(m);
      }
      if (ev.key === 'c' && (ev.ctrlKey || ev.metaKey)) return;
    });

    list.addEventListener('mouseover', function (ev) {
      if (!isDesktopUi()) return;
      var row = ev.target.closest('.cf-msg');
      if (!row || row.classList.contains('cf-msg--deleted')) return;
      if (ev.target.closest('#cfQuickBar, #cfReactStrip, #cfMoreMenu')) return;
      if (row.contains(ev.relatedTarget)) return;
      clearTimeout(overlay.hideTimer);
      showQuickBar(row);
    });

    initViewObservers();

    list.addEventListener('mouseout', function (ev) {
      if (!isDesktopUi()) return;
      var row = ev.target.closest('.cf-msg');
      if (!row) return;
      var related = ev.relatedTarget;
      if (related && (row.contains(related) || isOverlayEl(related))) return;
      scheduleOverlayHide();
    });

    var bar = $('cfQuickBar');
    var strip = $('cfReactStrip');
    var more = $('cfMoreMenu');
    [bar, strip, more].forEach(bindOverlayHover);

    if (bar) {
      bar.addEventListener('click', function (ev) {
        var btn = ev.target.closest('.cf-qb');
        if (!btn) return;
        var mid = state.ui.activeMsgId;
        var m = msgById(mid);
        var row = findMessageNode(mid);
        if (!m || !row) return;
        var act = btn.dataset.act;
        if (act === 'reply') setReply(m);
        if (act === 'copy') copyMessageText(m);
        if (act === 'react') {
          ev.preventDefault();
          showReactStrip(row);
        }
        if (act === 'more') showMoreMenu(row);
      });
    }

    list.addEventListener('scroll', function () { closeOverlays(); }, { passive: true });
    window.addEventListener('resize', closeOverlays);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closeOverlays();
    });

    var swipeState = null;
    var SWIPE_THRESH = 52;

    list.addEventListener('pointerdown', function (ev) {
      if (!isMobileUi() || ev.pointerType === 'mouse') return;
      var bubble = ev.target.closest('.cf-msg__bubble');
      if (!bubble || ev.target.closest('button, a, .cf-reaction')) return;
      var wrap = bubble.closest('.cf-msg__swipe');
      var row = bubble.closest('.cf-msg');
      if (!wrap || !row || row.classList.contains('cf-msg--deleted')) return;
      swipeState = {
        id: Number(row.dataset.id),
        wrap: wrap,
        bubble: bubble,
        startX: ev.clientX,
        active: true,
        pointerId: ev.pointerId,
      };
      try { bubble.setPointerCapture(ev.pointerId); } catch (e) {}
    });

    list.addEventListener('pointermove', function (ev) {
      if (!swipeState || !swipeState.active || ev.pointerId !== swipeState.pointerId) return;
      var dx = ev.clientX - swipeState.startX;
      var dir = dx > 0 ? 1 : -1;
      var mag = Math.min(Math.abs(dx), 72);
      var tx = dir * mag;
      swipeState.bubble.style.transform = 'translateX(' + tx + 'px)';
      swipeState.wrap.classList.toggle('is-dragging', true);
      swipeState.wrap.classList.toggle('is-threshold', mag >= SWIPE_THRESH);
    });

    list.addEventListener('pointerup', function (ev) {
      if (!swipeState || ev.pointerId !== swipeState.pointerId) return;
      var dx = ev.clientX - swipeState.startX;
      var m = msgById(swipeState.id);
      if (Math.abs(dx) >= SWIPE_THRESH && m) setReply(m);
      swipeState.bubble.style.transform = '';
      swipeState.wrap.classList.remove('is-dragging', 'is-threshold');
      try { swipeState.bubble.releasePointerCapture(ev.pointerId); } catch (e) {}
      swipeState = null;
    });

    list.addEventListener('pointercancel', function (ev) {
      if (!swipeState || ev.pointerId !== swipeState.pointerId) return;
      swipeState.bubble.style.transform = '';
      swipeState.wrap.classList.remove('is-dragging', 'is-threshold');
      swipeState = null;
    });

    var longPress = null;
    list.addEventListener('pointerdown', function (ev) {
      if (!isMobileUi()) return;
      var row = ev.target.closest('.cf-msg');
      if (!row || row.classList.contains('cf-msg--deleted')) return;
      if (ev.target.closest('.cf-msg__act, button, a')) return;
      clearTimeout(longPress);
      longPress = setTimeout(function () {
        openMobileSheet(Number(row.dataset.id));
      }, 480);
    });
    ['pointerup', 'pointermove', 'pointercancel'].forEach(function (evt) {
      list.addEventListener(evt, function () { clearTimeout(longPress); });
    });
  }

  function growComposer() {
    var ta = $('cfComposerInput');
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
  }

  function updateChar() {
    var n = ($('cfComposerInput').value || '').length;
    $('cfCharCount').textContent = String(n);
    var wrap = $('cfCharCountWrap');
    if (wrap) {
      wrap.hidden = !(n > maxBodyLen * 0.82 || n >= maxBodyLen - 80);
    }
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
            mergeMessage(m);
            if (!findMessageNode(m.id)) renderAll();
            scrollToMessageId(m.id, true);
            $('cfSearchPanel').hidden = true;
            $('cfSearchToggle').setAttribute('aria-expanded', 'false');
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

  scheduleForumComposerVoice();

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
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    var search = $('cfSearchPanel');
    if (search && !search.hidden) {
      search.hidden = true;
      $('cfSearchToggle').setAttribute('aria-expanded', 'false');
      $('cfSearchToggle').focus();
    }
  });
  var pinnedRoot = $('cfPinned');
  if ($('cfPinnedToggle') && pinnedRoot) {
    $('cfPinnedToggle').addEventListener('click', function () {
      var collapsed = pinnedRoot.classList.toggle('cf-pinned--collapsed');
      this.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });
  }
  if (window.CFForumEmoji && $('cfEmojiToggle') && $('cfEmojiPopover')) {
    window.CFForumEmoji.createPicker({
      toggle: $('cfEmojiToggle'),
      popover: $('cfEmojiPopover'),
      textarea: $('cfComposerInput'),
      onPick: function () { updateChar(); growComposer(); },
    });
  }
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
        if (m) {
          m.is_deleted = true;
          m.body = '';
          if (state.pinnedMessage && state.pinnedMessage.id === id) applyPinnedMessage(null);
          upsertFromPayload(m, false);
        }
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

  var pinnedHit = $('cfPinnedMsgHit');
  if (pinnedHit) {
    pinnedHit.addEventListener('click', function () {
      if (state.pinnedMessage && state.pinnedMessage.id) {
        scrollToMessage(state.pinnedMessage.id, true);
      }
    });
  }
  var pinnedUnpin = $('cfPinnedMsgUnpin');
  if (pinnedUnpin) {
    pinnedUnpin.addEventListener('click', function () {
      if (state.pinnedMessage && state.pinnedMessage.id) togglePin(state.pinnedMessage.id, false);
    });
  }

  initMessageInteractions();
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
    state.canModerate = !!data.can_moderate;
    state.reportReasons = data.report_reasons || [];
    if (data.member && data.member.display_name) {
      $('cfDisplayNameInput').value = data.member.display_name;
    }
    maxBodyLen = (data.limits && data.limits.max_body) || 2000;
    $('cfComposerInput').maxLength = maxBodyLen;
    if (data.pinned_notices && data.pinned_notices.length) {
      $('cfPinned').hidden = false;
      var bodyEl = $('cfPinnedBody');
      if (bodyEl) {
        bodyEl.textContent = data.pinned_notices.map(function (n) { return n.body; }).join('\n');
      }
    }
    if (data.pinned_message) applyPinnedMessage(normalizeIncoming(data.pinned_message));
    else renderPinnedBar();
    maybeShowWelcomeDialog(data.member);
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
