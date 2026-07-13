/**
 * CRM Team Messages Studio — صندوق پیام داخلی آژانس
 */
(function () {
    'use strict';

    const root = document.querySelector('[data-crm-messages]');
    if (!root) return;

    const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const apiThreads = root.dataset.apiThreads;
    const apiUnread = root.dataset.apiUnread;
    const apiMembers = root.dataset.apiMembers;
    const apiNotifications = root.dataset.apiNotifications;
    const canBroadcast = root.dataset.canBroadcast === '1';
    const canManage = root.dataset.canManage === '1';
    const mobileMq = window.matchMedia('(max-width: 960px)');

    const FOLDER_LABELS = { inbox: 'صندوق ورودی', starred: 'ستاره‌دار', archived: 'آرشیو' };
    const KIND_LABELS = { direct: 'خصوصی', broadcast: 'گروهی' };

    let currentFolder = 'inbox';
    let currentThreadId = null;
    let currentThreadMeta = null;
    let threadsCache = [];
    let composeKind = 'direct';
    let pollTimer = null;
    let confirmCallback = null;

    const els = {
        threadList: root.querySelector('[data-msg-thread-list]'),
        detail: root.querySelector('[data-msg-detail]'),
        placeholder: root.querySelector('[data-msg-placeholder]'),
        messages: root.querySelector('[data-msg-messages]'),
        subject: root.querySelector('[data-msg-subject]'),
        participants: root.querySelector('[data-msg-participants]'),
        headerAvatar: root.querySelector('[data-msg-header-avatar]'),
        replyForm: root.querySelector('[data-msg-reply-form]'),
        starBtn: root.querySelector('[data-msg-star]'),
        archiveBtn: root.querySelector('[data-msg-archive]'),
        purgeBtn: root.querySelector('[data-msg-purge-thread]'),
        threadMenuBtn: root.querySelector('[data-msg-thread-menu]'),
        threadMenuPanel: root.querySelector('[data-msg-thread-menu-panel]'),
        search: root.querySelector('[data-msg-search]'),
        folderTitle: root.querySelector('[data-msg-folder-title]'),
        threadCount: root.querySelector('[data-msg-thread-count]'),
        backBtn: root.querySelector('[data-msg-back]'),
        composeModal: document.getElementById('modal-msg-compose'),
        composeForm: document.querySelector('[data-msg-compose-form]'),
        recipientSelect: document.querySelector('[data-msg-recipient-select]'),
        uploadZone: document.querySelector('[data-msg-upload-zone]'),
        fileInput: document.querySelector('[data-msg-file-input]'),
        fileList: document.querySelector('[data-msg-file-list]'),
        composeSubmit: document.querySelector('[data-msg-compose-submit]'),
        composeSubmitLabel: document.querySelector('[data-msg-compose-submit-label]'),
        composeTitle: document.querySelector('[data-msg-compose-title]'),
        composeSub: document.querySelector('[data-msg-compose-sub]'),
        composeBody: document.getElementById('msg-compose-body'),
        notifDrawer: document.getElementById('drawer-msg-notifications'),
        notifList: document.querySelector('[data-msg-notif-list]'),
        notifCount: root.querySelector('[data-msg-notif-count]'),
        folderUnread: root.querySelector('[data-folder-unread="inbox"]'),
        confirmModal: document.getElementById('modal-msg-confirm'),
        confirmTitle: document.querySelector('[data-msg-confirm-title]'),
        confirmText: document.querySelector('[data-msg-confirm-text]'),
    };

    function parseResponse(r) {
        return r.text().then(text => {
            let data = {};
            try { data = text ? JSON.parse(text) : {}; } catch (_) {
                data = { ok: false, error: r.ok ? 'پاسخ سرور نامعتبر بود.' : `خطای سرور (${r.status})` };
            }
            if (!r.ok && data.ok !== false) {
                data.ok = false;
                data.error = data.error || `خطای سرور (${r.status})`;
            }
            return data;
        });
    }

    function fetchJson(url, opts = {}) {
        const headers = Object.assign({ 'X-CSRFToken': csrf }, opts.headers || {});
        if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
        return fetch(url, Object.assign({ credentials: 'same-origin' }, opts, { headers })).then(parseResponse);
    }

    function formatTime(iso) {
        if (!iso) return '';
        try {
            return new Date(iso).toLocaleString('fa-IR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch (_) { return ''; }
    }

    function formatDateLabel(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            const today = new Date();
            const yest = new Date(); yest.setDate(today.getDate() - 1);
            if (d.toDateString() === today.toDateString()) return 'امروز';
            if (d.toDateString() === yest.toDateString()) return 'دیروز';
            return d.toLocaleDateString('fa-IR', { month: 'long', day: 'numeric' });
        } catch (_) { return ''; }
    }

    function initials(name) {
        if (!name) return '؟';
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        return parts.length >= 2 ? `${parts[0][0]}${parts[1][0]}` : parts[0][0];
    }

    function avatarHue(name) {
        if (!name) return 0;
        const s = String(name).trim();
        return s ? [...s].reduce((sum, c) => sum + c.charCodeAt(0), 0) % 6 : 0;
    }

    function escapeHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function formatBadgeCount(n) {
        const count = Number(n) || 0;
        if (count <= 0) return '';
        return count > 99 ? '99+' : String(count);
    }

    function threadLabel(t) { return t.subject || t.participants_label || 'پیام'; }
    function threadAvatarName(t) {
        if (t.kind === 'broadcast') return t.subject || 'گروه';
        return (t.participants_label || t.subject || '؟').split('،')[0].trim();
    }

    function avatarHtml(name, size) {
        const hue = avatarHue(name);
        const cls = size ? `crm-msg-avatar ${size}` : 'crm-msg-avatar';
        return `<span class="${cls} crm-msg-avatar--hue-${hue}" aria-hidden="true">${escapeHtml(initials(name))}</span>`;
    }

    function setHeaderAvatar(t) {
        if (!els.headerAvatar) return;
        const name = threadAvatarName(t);
        els.headerAvatar.textContent = initials(name);
        els.headerAvatar.className = `crm-msg-avatar crm-msg-avatar--xl crm-msg-avatar--hue-${avatarHue(name)}`;
    }

    function updateFolderMeta(count) {
        if (els.folderTitle) els.folderTitle.textContent = FOLDER_LABELS[currentFolder] || 'مکالمات';
        if (els.threadCount) {
            const n = typeof count === 'number' ? count : threadsCache.length;
            els.threadCount.textContent = n ? `${n.toLocaleString('fa-IR')} مکالمه` : 'مکالمه‌ای نیست';
        }
    }

    function setDetailOpen(open) {
        root.classList.toggle('crm-msg-hub--detail-open', open && mobileMq.matches);
    }

    function closeDetail() {
        currentThreadId = null;
        currentThreadMeta = null;
        renderThreads(threadsCache);
        if (els.detail) els.detail.hidden = true;
        if (els.placeholder) els.placeholder.hidden = false;
        setDetailOpen(false);
        closeThreadMenu();
    }

    function renderEmptyState(icon, text, tag) {
        const el = tag || 'li';
        return `<${el} class="crm-msg-state"><span class="crm-msg-state-ring"><i class="fas ${icon}"></i></span><p>${text}</p></${el}>`;
    }

    function renderThreads(threads) {
        const q = (els.search?.value || '').trim().toLowerCase();
        const filtered = q ? threads.filter(t =>
            (t.subject || '').toLowerCase().includes(q) ||
            (t.participants_label || '').toLowerCase().includes(q) ||
            ((t.last_message && t.last_message.body) || '').toLowerCase().includes(q)) : threads;

        updateFolderMeta(filtered.length);

        if (!filtered.length) {
            const text = q ? 'نتیجه‌ای یافت نشد.' :
                currentFolder === 'starred' ? 'مکالمه ستاره‌داری ندارید.' :
                currentFolder === 'archived' ? 'آرشیو خالی است.' : 'صندوق ورودی خالی است.';
            els.threadList.innerHTML = renderEmptyState(q ? 'fa-magnifying-glass' : 'fa-inbox', text);
            return;
        }

        els.threadList.innerHTML = filtered.map(t => {
            const label = threadLabel(t);
            const preview = (t.last_message && t.last_message.body) || 'بدون متن';
            return `
            <li class="crm-msg-thread ${t.unread_count ? 'is-unread' : ''} ${t.id === currentThreadId ? 'is-active' : ''}"
                data-thread-id="${t.id}" role="option">
                ${avatarHtml(threadAvatarName(t))}
                <div class="crm-msg-thread-body">
                    <div class="crm-msg-thread-top">
                        <strong>${escapeHtml(label)}</strong>
                        ${t.kind === 'broadcast' ? '<span class="crm-msg-tag">گروهی</span>' : ''}
                        <time>${formatTime(t.updated_at)}</time>
                    </div>
                    <p class="crm-msg-thread-snippet">${escapeHtml(preview)}</p>
                </div>
                <div class="crm-msg-thread-side">
                    ${t.unread_count ? '<span class="crm-msg-dot" aria-label="خوانده نشده"></span>' : ''}
                    <button type="button" class="crm-msg-thread-del" data-delete-thread="${t.id}" title="حذف مکالمه" aria-label="حذف">
                        <i class="fas fa-trash-can"></i>
                    </button>
                </div>
            </li>`;
        }).join('');

        els.threadList.querySelectorAll('[data-thread-id]').forEach(li => {
            li.addEventListener('click', e => {
                if (e.target.closest('[data-delete-thread]')) return;
                openThread(parseInt(li.dataset.threadId, 10));
            });
        });
        els.threadList.querySelectorAll('[data-delete-thread]').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                confirmDelete('حذف مکالمه', 'این مکالمه از صندوق شما حذف می‌شود.', () => deleteThread(parseInt(btn.dataset.deleteThread, 10)));
            });
        });
    }

    function loadThreads() {
        return fetchJson(`${apiThreads}?folder=${currentFolder}`).then(data => {
            if (!data.ok) return;
            threadsCache = data.threads || [];
            renderThreads(threadsCache);
        });
    }

    function openThread(id) {
        currentThreadId = id;
        renderThreads(threadsCache);
        fetchJson(`${apiThreads}${id}/`).then(data => {
            if (!data.ok) return;
            if (els.placeholder) els.placeholder.hidden = true;
            if (els.detail) els.detail.hidden = false;
            setDetailOpen(true);

            const t = data.thread;
            currentThreadMeta = t;
            if (els.subject) els.subject.textContent = threadLabel(t);
            if (els.participants) els.participants.textContent = t.participants_label || '';
            setHeaderAvatar(t);

            if (els.starBtn) {
                els.starBtn.classList.toggle('is-active', t.is_starred);
                els.starBtn.setAttribute('aria-pressed', t.is_starred ? 'true' : 'false');
                const icon = els.starBtn.querySelector('i');
                if (icon) icon.className = t.is_starred ? 'fas fa-star' : 'far fa-star';
            }
            if (els.purgeBtn) els.purgeBtn.hidden = !(canManage && t.can_purge);

            renderMessages(data.messages || []);
            const idx = threadsCache.findIndex(x => x.id === id);
            if (idx >= 0) threadsCache[idx].unread_count = 0;
            renderThreads(threadsCache);
            refreshUnread();
        });
    }

    function renderMessages(messages) {
        if (!els.messages) return;
        if (!messages.length) {
            els.messages.innerHTML = renderEmptyState('fa-comment-dots', 'هنوز پیامی نیست.', 'div');
            return;
        }
        let lastDate = '';
        const html = messages.map(m => {
            const dateLabel = formatDateLabel(m.created_at);
            let divider = '';
            if (dateLabel && dateLabel !== lastDate) {
                lastDate = dateLabel;
                divider = `<div class="crm-msg-day"><span>${dateLabel}</span></div>`;
            }
            const atts = (m.attachments || []).map(a =>
                `<a class="crm-msg-attach" href="${escapeHtml(a.url)}" target="_blank" rel="noopener"><i class="fas fa-file"></i>${escapeHtml(a.name)}</a>`
            ).join('');
            const delBtn = m.can_delete
                ? `<button type="button" class="crm-msg-bubble-del" data-delete-message="${m.id}" title="حذف پیام" aria-label="حذف"><i class="fas fa-trash-can"></i></button>`
                : '';
            return `${divider}
            <article class="crm-msg-bubble ${m.is_mine ? 'is-mine' : ''}" data-message-id="${m.id}">
                <div class="crm-msg-bubble-meta">
                    <strong>${escapeHtml(m.sender_name)}</strong>
                    <time>${formatTime(m.created_at)}</time>
                    ${delBtn}
                </div>
                <div class="crm-msg-bubble-text">${escapeHtml(m.body).replace(/\n/g, '<br>')}</div>
                ${atts ? `<div class="crm-msg-bubble-files">${atts}</div>` : ''}
            </article>`;
        }).join('');
        els.messages.innerHTML = html;
        els.messages.scrollTop = els.messages.scrollHeight;
        els.messages.querySelectorAll('[data-delete-message]').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                confirmDelete('حذف پیام', 'این پیام برای همیشه حذف می‌شود.', () =>
                    deleteMessage(parseInt(btn.dataset.deleteMessage, 10)));
            });
        });
    }

    function updateTeamNavBadge(n) {
        const link = document.querySelector('[data-nav-team-badge]');
        if (!link) return;
        let badge = link.querySelector('[data-nav-team-messages-badge]');
        const label = formatBadgeCount(n);
        if (!label) { if (badge) badge.hidden = true; return; }
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'ws-nav-badge';
            badge.dataset.navTeamMessagesBadge = '';
            link.appendChild(badge);
        }
        badge.textContent = label;
        badge.hidden = false;
    }

    function refreshUnread() {
        fetchJson(apiUnread).then(data => {
            if (!data.ok) return;
            const n = data.unread_messages || 0;
            if (els.folderUnread) {
                els.folderUnread.textContent = formatBadgeCount(n) || n;
                els.folderUnread.hidden = !n;
            }
            if (els.notifCount) {
                const nn = data.unread_notifications || 0;
                els.notifCount.textContent = formatBadgeCount(nn) || nn;
                els.notifCount.hidden = !nn;
            }
            const tabBadge = document.querySelector('a[href="?tab=messages"] em');
            if (tabBadge) {
                const label = formatBadgeCount(n);
                tabBadge.textContent = label;
                tabBadge.style.display = label ? '' : 'none';
            }
            updateTeamNavBadge(n);
        });
    }

    function patchThread(payload) {
        if (!currentThreadId) return;
        fetchJson(`${apiThreads}${currentThreadId}/`, { method: 'PATCH', body: JSON.stringify(payload) })
            .then(() => loadThreads());
    }

    function deleteMessage(messageId) {
        if (!currentThreadId) return;
        fetchJson(`${apiThreads}${currentThreadId}/items/${messageId}/`, { method: 'DELETE' })
            .then(data => {
                if (!data.ok) { alert(data.error || 'خطا در حذف'); return; }
                if (data.thread_removed) {
                    closeDetail();
                    loadThreads();
                } else {
                    renderMessages(data.messages || []);
                    loadThreads();
                }
                refreshUnread();
            });
    }

    function deleteThread(threadId, purgeAll) {
        fetchJson(`${apiThreads}${threadId}/`, {
            method: 'DELETE',
            body: JSON.stringify({ purge_all: !!purgeAll }),
        }).then(data => {
            if (!data.ok) { alert(data.error || 'خطا در حذف'); return; }
            if (currentThreadId === threadId) closeDetail();
            loadThreads();
            refreshUnread();
        });
    }

    function confirmDelete(title, text, onOk) {
        if (!els.confirmModal) { if (window.confirm(text)) onOk(); return; }
        if (els.confirmTitle) els.confirmTitle.textContent = title;
        if (els.confirmText) els.confirmText.textContent = text;
        confirmCallback = onOk;
        els.confirmModal.hidden = false;
        els.confirmModal.classList.add('is-open');
        document.body.classList.add('ws-modal-open');
    }

    function closeConfirm() {
        if (!els.confirmModal) return;
        els.confirmModal.hidden = true;
        els.confirmModal.classList.remove('is-open');
        document.body.classList.remove('ws-modal-open');
        confirmCallback = null;
    }

    function closeThreadMenu() {
        if (els.threadMenuPanel) els.threadMenuPanel.hidden = true;
        if (els.threadMenuBtn) els.threadMenuBtn.setAttribute('aria-expanded', 'false');
    }

    function loadMembers() {
        return fetchJson(apiMembers).then(data => {
            if (!data.ok || !els.recipientSelect) return;
            els.recipientSelect.innerHTML = '<option value="">انتخاب عضو...</option>' +
                (data.members || []).map(m =>
                    `<option value="${m.id}">${escapeHtml(m.name)} (${escapeHtml(m.role_label)})</option>`).join('');
        });
    }

    function formatFileSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function renderFileList(files) {
        if (!els.fileList || !els.uploadZone) return;
        if (!files?.length) {
            els.fileList.hidden = true;
            els.fileList.innerHTML = '';
            els.uploadZone.classList.remove('has-files');
            return;
        }
        els.fileList.hidden = false;
        els.uploadZone.classList.add('has-files');
        els.fileList.innerHTML = Array.from(files).map(f =>
            `<li><i class="fas fa-file-lines" aria-hidden="true"></i><span>${escapeHtml(f.name)}</span><em>${formatFileSize(f.size)}</em></li>`
        ).join('');
    }

    function initUploadZone() {
        if (!els.uploadZone || !els.fileInput) return;
        els.uploadZone.addEventListener('click', e => { if (!e.target.closest('a')) els.fileInput.click(); });
        els.fileInput.addEventListener('change', () => renderFileList(els.fileInput.files));
        ['dragenter', 'dragover'].forEach(ev => els.uploadZone.addEventListener(ev, e => {
            e.preventDefault(); els.uploadZone.classList.add('is-dragover');
        }));
        ['dragleave', 'drop'].forEach(ev => els.uploadZone.addEventListener(ev, e => {
            e.preventDefault(); els.uploadZone.classList.remove('is-dragover');
        }));
        els.uploadZone.addEventListener('drop', e => {
            if (e.dataTransfer?.files?.length) {
                els.fileInput.files = e.dataTransfer.files;
                renderFileList(e.dataTransfer.files);
            }
        });
    }

    function initComposer() {
        const input = els.replyForm?.querySelector('.crm-msg-composer-field');
        if (!input) return;
        const resize = () => { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 120)}px`; };
        input.addEventListener('input', resize);
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); els.replyForm.requestSubmit(); }
        });
    }

    function openComposeModal() {
        if (!els.composeModal) return;
        if (window.WSModal?.open) window.WSModal.open('modal-msg-compose');
        else { els.composeModal.classList.add('is-open'); document.body.classList.add('ws-modal-open'); }
        loadMembers().then(() => {
            (composeKind === 'direct' ? els.recipientSelect : document.getElementById('msg-compose-body'))?.focus();
        });
    }

    function closeComposeModal() {
        if (!els.composeModal) return;
        if (window.WSModal?.close) window.WSModal.close(els.composeModal);
        else { els.composeModal.classList.remove('is-open'); document.body.classList.remove('ws-modal-open'); }
        els.composeForm?.reset();
        renderFileList(null);
        setComposeKind('direct');
    }

    function setComposeKind(kind) {
        composeKind = kind;
        const isDirect = kind === 'direct';
        if (els.composeModal) {
            els.composeModal.classList.toggle('is-compose-direct', isDirect);
            els.composeModal.classList.toggle('is-compose-broadcast', !isDirect);
        }
        document.querySelectorAll('[data-msg-compose-kind] [data-kind]').forEach(btn => {
            const active = btn.dataset.kind === kind;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        document.querySelectorAll('[data-compose-pane]').forEach(pane => {
            pane.hidden = pane.dataset.composePane !== kind;
        });
        if (els.composeTitle) els.composeTitle.textContent = isDirect ? 'پیام خصوصی' : 'پیام گروهی';
        if (els.composeSub) {
            els.composeSub.textContent = isDirect
                ? 'مکالمه یک‌به‌یک با یک عضو تیم'
                : 'اطلاع‌رسانی به چند نفر یا کل اعضای آژانس';
        }
        if (els.composeSubmitLabel) {
            els.composeSubmitLabel.textContent = isDirect ? 'ارسال خصوصی' : 'ارسال گروهی';
        }
        if (els.composeBody) {
            els.composeBody.placeholder = isDirect
                ? 'پیام خصوصی خود را بنویسید...'
                : 'متن اعلان یا پیام گروهی را بنویسید...';
        }
        if (els.recipientSelect) {
            if (isDirect) els.recipientSelect.setAttribute('required', 'required');
            else els.recipientSelect.removeAttribute('required');
        }
    }

    function openNotifDrawer() {
        if (!els.notifDrawer) return;
        els.notifDrawer.classList.add('is-open');
        document.body.classList.add('crm-drawer-open');
        loadNotifications();
    }

    function closeNotifDrawer() {
        if (!els.notifDrawer) return;
        els.notifDrawer.classList.remove('is-open');
        document.body.classList.remove('crm-drawer-open');
    }

    function loadNotifications() {
        fetchJson(`${apiNotifications}?unread=1`).then(data => {
            if (!data.ok || !els.notifList) return;
            const items = data.notifications || [];
            els.notifList.innerHTML = items.length
                ? items.map(n => `<li class="crm-msg-notif-item ${n.is_read ? '' : 'is-unread'}" data-link="${escapeHtml(n.link)}">
                    <strong>${escapeHtml(n.title)}</strong><p>${escapeHtml(n.body)}</p>
                    <time>${formatTime(n.created_at)}</time></li>`).join('')
                : renderEmptyState('fa-bell-slash', 'اعلان جدیدی نیست');
            els.notifList.querySelectorAll('[data-link]').forEach(li => {
                li.addEventListener('click', () => {
                    const m = (li.dataset.link || '').match(/thread=(\d+)/);
                    if (m) openThread(parseInt(m[1], 10));
                    closeNotifDrawer();
                });
            });
        });
    }

    root.querySelectorAll('[data-folder]').forEach(btn => {
        btn.addEventListener('click', () => {
            currentFolder = btn.dataset.folder;
            root.querySelectorAll('[data-folder]').forEach(b => b.classList.toggle('active', b === btn));
            closeDetail();
            loadThreads();
        });
    });

    root.querySelectorAll('[data-msg-compose]').forEach(b => b.addEventListener('click', openComposeModal));
    document.querySelectorAll('[data-msg-compose-close]').forEach(b => b.addEventListener('click', closeComposeModal));
    root.querySelector('[data-msg-notifications]')?.addEventListener('click', openNotifDrawer);
    document.querySelectorAll('[data-msg-notif-close]').forEach(b => b.addEventListener('click', closeNotifDrawer));
    document.querySelector('[data-msg-notif-read-all]')?.addEventListener('click', () => {
        fetchJson(apiNotifications, { method: 'POST', body: JSON.stringify({ action: 'read_all' }) })
            .then(() => { loadNotifications(); refreshUnread(); });
    });

    els.backBtn?.addEventListener('click', closeDetail);
    mobileMq.addEventListener('change', () => { if (!mobileMq.matches) setDetailOpen(false); });

    document.querySelectorAll('[data-msg-compose-kind] [data-kind]').forEach(btn => {
        btn.addEventListener('click', () => setComposeKind(btn.dataset.kind));
    });

    els.threadMenuBtn?.addEventListener('click', e => {
        e.stopPropagation();
        const open = els.threadMenuPanel?.hidden !== false;
        if (els.threadMenuPanel) els.threadMenuPanel.hidden = !open;
        els.threadMenuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.querySelector('[data-msg-delete-thread]')?.addEventListener('click', () => {
        closeThreadMenu();
        if (!currentThreadId) return;
        confirmDelete('حذف از صندوق', 'مکالمه از لیست شما حذف می‌شود.', () => deleteThread(currentThreadId, false));
    });

    els.purgeBtn?.addEventListener('click', () => {
        closeThreadMenu();
        if (!currentThreadId) return;
        confirmDelete('حذف برای همه', 'کل مکالمه برای تمام اعضا حذف می‌شود. این عمل برگشت‌پذیر نیست.', () =>
            deleteThread(currentThreadId, true));
    });

    document.addEventListener('click', e => {
        if (!e.target.closest('.crm-msg-menu-wrap')) closeThreadMenu();
    });

    document.querySelector('[data-msg-confirm-ok]')?.addEventListener('click', () => {
        const cb = confirmCallback;
        closeConfirm();
        if (cb) cb();
    });
    document.querySelectorAll('[data-msg-confirm-cancel]').forEach(b => b.addEventListener('click', closeConfirm));

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            if (els.confirmModal?.classList.contains('is-open')) closeConfirm();
            else if (els.composeModal?.classList.contains('is-open')) closeComposeModal();
        }
    });

    initUploadZone();
    initComposer();

    els.starBtn?.addEventListener('click', () => {
        const starred = !els.starBtn.classList.contains('is-active');
        patchThread({ is_starred: starred });
        els.starBtn.classList.toggle('is-active', starred);
        els.starBtn.setAttribute('aria-pressed', starred ? 'true' : 'false');
        const icon = els.starBtn.querySelector('i');
        if (icon) icon.className = starred ? 'fas fa-star' : 'far fa-star';
    });

    els.archiveBtn?.addEventListener('click', () => {
        patchThread({ is_archived: true });
        closeDetail();
        loadThreads();
    });

    els.search?.addEventListener('input', () => renderThreads(threadsCache));

    els.replyForm?.addEventListener('submit', e => {
        e.preventDefault();
        if (!currentThreadId) return;
        fetch(`${apiThreads}${currentThreadId}/`, {
            method: 'POST', credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf }, body: new FormData(els.replyForm),
        }).then(parseResponse).then(data => {
            if (data.ok) {
                els.replyForm.reset();
                const input = els.replyForm.querySelector('.crm-msg-composer-field');
                if (input) input.style.height = 'auto';
                openThread(currentThreadId);
                loadThreads();
            } else alert(data.error || 'خطا در ارسال');
        });
    });

    els.composeForm?.addEventListener('submit', e => {
        e.preventDefault();
        if (composeKind === 'broadcast') els.recipientSelect?.removeAttribute('required');
        const fd = new FormData(els.composeForm);
        fd.set('kind', composeKind);
        if (composeKind === 'broadcast') {
            fd.delete('recipient_member_id');
            fd.delete('target_roles');
            document.querySelectorAll('[name=target_roles]:checked').forEach(cb => fd.append('target_roles', cb.value));
        } else fd.delete('target_roles');
        const submitBtn = els.composeSubmit;
        if (submitBtn) submitBtn.disabled = true;
        fetch(apiThreads, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf }, body: fd })
            .then(parseResponse).then(data => {
                if (data.ok) {
                    closeComposeModal();
                    loadThreads().then(() => {
                        const tid = data.thread?.thread?.id;
                        if (tid) openThread(tid);
                    });
                    refreshUnread();
                } else alert(data.error || 'خطا در ارسال');
            }).catch(() => alert('خطا در ارسال پیام'))
            .finally(() => { if (submitBtn) submitBtn.disabled = false; });
    });

    loadThreads().then(refreshUnread);
    const initial = root.dataset.initialThread;
    if (initial) openThread(parseInt(initial, 10));

    pollTimer = setInterval(() => {
        loadThreads();
        refreshUnread();
        if (currentThreadId) openThread(currentThreadId);
    }, 60000);

    window.addEventListener('beforeunload', () => clearInterval(pollTimer));
})();
