/**
 * CRM Team Messages Pro — صندوق پیام داخلی آژانس
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
    const mobileMq = window.matchMedia('(max-width: 960px)');

    const FOLDER_LABELS = {
        inbox: 'صندوق ورودی',
        starred: 'ستاره‌دار',
        archived: 'آرشیو',
    };

    const KIND_LABELS = {
        direct: 'خصوصی',
        broadcast: 'گروهی',
    };

    let currentFolder = 'inbox';
    let currentThreadId = null;
    let threadsCache = [];
    let composeKind = 'direct';
    let pollTimer = null;

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
        composeSubmit: document.querySelector('.crm-msg-compose-submit'),
        notifDrawer: document.getElementById('drawer-msg-notifications'),
        notifList: document.querySelector('[data-msg-notif-list]'),
        notifCount: root.querySelector('[data-msg-notif-count]'),
        folderUnread: root.querySelector('[data-folder-unread="inbox"]'),
    };

    function parseResponse(r) {
        return r.text().then(text => {
            let data = {};
            try {
                data = text ? JSON.parse(text) : {};
            } catch (_) {
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
        if (opts.body && !(opts.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }
        return fetch(url, Object.assign({ credentials: 'same-origin' }, opts, { headers }))
            .then(parseResponse);
    }

    function formatTime(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleString('fa-IR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch (_) {
            return '';
        }
    }

    function initials(name) {
        if (!name) return '؟';
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`;
        return parts[0][0];
    }

    function avatarHue(name) {
        if (!name) return 0;
        const stripped = String(name).trim();
        if (!stripped) return 0;
        return [...stripped].reduce((sum, c) => sum + c.charCodeAt(0), 0) % 6;
    }

    function threadLabel(t) {
        return t.subject || t.participants_label || 'پیام';
    }

    function threadAvatarName(t) {
        if (t.kind === 'broadcast') return t.subject || 'گروه';
        return (t.participants_label || t.subject || '؟').split('،')[0].trim();
    }

    function avatarHtml(name, sizeClass) {
        const hue = avatarHue(name);
        const cls = sizeClass ? `crm-msg-avatar ${sizeClass}` : 'crm-msg-avatar';
        return `<span class="${cls} crm-msg-avatar--hue-${hue}" aria-hidden="true">${escapeHtml(initials(name))}</span>`;
    }

    function setHeaderAvatar(t) {
        if (!els.headerAvatar) return;
        const name = threadAvatarName(t);
        const hue = avatarHue(name);
        els.headerAvatar.textContent = initials(name);
        els.headerAvatar.className = `crm-msg-avatar crm-msg-avatar--lg crm-msg-avatar--hue-${hue}`;
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
        renderThreads(threadsCache);
        if (els.detail) els.detail.hidden = true;
        if (els.placeholder) els.placeholder.hidden = false;
        setDetailOpen(false);
    }

    function renderEmptyState(icon, text, tag) {
        const el = tag || 'li';
        return `<${el} class="crm-msg-state">
            <span class="crm-msg-state-icon"><i class="fas ${icon}"></i></span>
            <p>${text}</p>
        </${el}>`;
    }

    function renderThreads(threads) {
        const q = (els.search?.value || '').trim().toLowerCase();
        const filtered = q
            ? threads.filter(t =>
                (t.subject || '').toLowerCase().includes(q) ||
                (t.participants_label || '').toLowerCase().includes(q) ||
                ((t.last_message && t.last_message.body) || '').toLowerCase().includes(q))
            : threads;

        updateFolderMeta(filtered.length);

        if (!filtered.length) {
            const emptyText = q
                ? 'نتیجه‌ای برای جستجوی شما یافت نشد.'
                : currentFolder === 'starred'
                    ? 'هنوز مکالمه‌ای ستاره‌دار نکرده‌اید.'
                    : currentFolder === 'archived'
                        ? 'آرشیو خالی است.'
                        : 'صندوق ورودی خالی است — اولین پیام را بفرستید.';
            els.threadList.innerHTML = renderEmptyState(q ? 'fa-magnifying-glass' : 'fa-inbox', emptyText);
            return;
        }

        els.threadList.innerHTML = filtered.map(t => {
            const label = threadLabel(t);
            const avatarName = threadAvatarName(t);
            const kind = t.kind || 'direct';
            const preview = (t.last_message && t.last_message.body) || 'بدون متن';
            return `
            <li class="crm-msg-thread-item ${t.unread_count ? 'unread' : ''} ${t.id === currentThreadId ? 'active' : ''}"
                data-thread-id="${t.id}" role="option" aria-selected="${t.id === currentThreadId}">
                ${avatarHtml(avatarName)}
                <div class="crm-msg-thread-body">
                    <div class="crm-msg-thread-item-head">
                        <strong>${escapeHtml(label)}</strong>
                        ${kind === 'broadcast' ? `<span class="crm-msg-thread-kind" data-kind="broadcast">${KIND_LABELS.broadcast}</span>` : ''}
                        <time datetime="${escapeHtml(t.updated_at)}">${formatTime(t.updated_at)}</time>
                    </div>
                    <div class="crm-msg-thread-preview">${escapeHtml(preview)}</div>
                </div>
                <span class="crm-msg-unread-dot" aria-hidden="true"></span>
            </li>`;
        }).join('');

        els.threadList.querySelectorAll('[data-thread-id]').forEach(li => {
            li.addEventListener('click', () => openThread(parseInt(li.dataset.threadId, 10)));
        });
    }

    function escapeHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function loadThreads() {
        return fetchJson(`${apiThreads}?folder=${currentFolder}`)
            .then(data => {
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
            if (els.subject) els.subject.textContent = threadLabel(t);
            if (els.participants) els.participants.textContent = t.participants_label || '';
            setHeaderAvatar(t);

            if (els.starBtn) {
                els.starBtn.classList.toggle('active', t.is_starred);
                els.starBtn.setAttribute('aria-pressed', t.is_starred ? 'true' : 'false');
                const icon = els.starBtn.querySelector('i');
                if (icon) icon.className = t.is_starred ? 'fas fa-star' : 'far fa-star';
            }

            if (els.messages) {
                els.messages.innerHTML = (data.messages || []).length
                    ? (data.messages || []).map(renderBubble).join('')
                    : renderEmptyState('fa-comment-dots', 'هنوز پیامی در این مکالمه نیست.', 'div');
                els.messages.scrollTop = els.messages.scrollHeight;
            }

            const idx = threadsCache.findIndex(x => x.id === id);
            if (idx >= 0) threadsCache[idx].unread_count = 0;
            renderThreads(threadsCache);
            refreshUnread();
        });
    }

    function renderBubble(m) {
        const atts = (m.attachments || []).map(a =>
            `<a class="crm-msg-attach-link" href="${escapeHtml(a.url)}" target="_blank" rel="noopener">
                <i class="fas fa-file"></i>${escapeHtml(a.name)}
            </a>`
        ).join('');
        return `<article class="crm-msg-bubble ${m.is_mine ? 'mine' : ''}">
            <div class="crm-msg-bubble-head">
                <strong>${escapeHtml(m.sender_name)}</strong>
                <time datetime="${escapeHtml(m.created_at)}">${formatTime(m.created_at)}</time>
            </div>
            <div class="crm-msg-bubble-body">${escapeHtml(m.body).replace(/\n/g, '<br>')}</div>
            ${atts ? `<div class="crm-msg-attachments">${atts}</div>` : ''}
        </article>`;
    }

    function formatBadgeCount(n) {
        const count = Number(n) || 0;
        if (count <= 0) return '';
        return count > 99 ? '99+' : String(count);
    }

    function updateTeamNavBadge(n) {
        const link = document.querySelector('[data-nav-team-badge]');
        if (!link) return;
        let badge = link.querySelector('[data-nav-team-messages-badge]');
        const label = formatBadgeCount(n);
        if (!label) {
            if (badge) badge.hidden = true;
            return;
        }
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
        fetchJson(`${apiThreads}${currentThreadId}/`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        }).then(() => loadThreads());
    }

    function loadMembers() {
        return fetchJson(apiMembers).then(data => {
            if (!data.ok || !els.recipientSelect) return;
            const opts = (data.members || []).map(m =>
                `<option value="${m.id}">${escapeHtml(m.name)} (${escapeHtml(m.role_label)})</option>`
            ).join('');
            els.recipientSelect.innerHTML = '<option value="">انتخاب عضو...</option>' + opts;
        });
    }

    function formatFileSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function renderFileList(files) {
        if (!els.fileList || !els.uploadZone) return;
        if (!files || !files.length) {
            els.fileList.hidden = true;
            els.fileList.innerHTML = '';
            els.uploadZone.classList.remove('has-files');
            return;
        }
        els.fileList.hidden = false;
        els.uploadZone.classList.add('has-files');
        els.fileList.innerHTML = Array.from(files).map(f => `
            <li class="crm-msg-file-item">
                <i class="fas fa-file-lines" aria-hidden="true"></i>
                <span>${escapeHtml(f.name)}</span>
                <em>${formatFileSize(f.size)}</em>
            </li>
        `).join('');
    }

    function initUploadZone() {
        if (!els.uploadZone || !els.fileInput) return;
        els.uploadZone.addEventListener('click', e => {
            if (e.target.closest('a')) return;
            els.fileInput.click();
        });
        els.fileInput.addEventListener('change', () => renderFileList(els.fileInput.files));
        ['dragenter', 'dragover'].forEach(ev => {
            els.uploadZone.addEventListener(ev, e => {
                e.preventDefault();
                els.uploadZone.classList.add('is-dragover');
            });
        });
        ['dragleave', 'drop'].forEach(ev => {
            els.uploadZone.addEventListener(ev, e => {
                e.preventDefault();
                els.uploadZone.classList.remove('is-dragover');
            });
        });
        els.uploadZone.addEventListener('drop', e => {
            const files = e.dataTransfer?.files;
            if (!files?.length) return;
            els.fileInput.files = files;
            renderFileList(files);
        });
    }

    function initComposer() {
        const input = els.replyForm?.querySelector('.crm-msg-composer-input');
        if (!input) return;
        const resize = () => {
            input.style.height = 'auto';
            input.style.height = `${Math.min(input.scrollHeight, 112)}px`;
        };
        input.addEventListener('input', resize);
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                els.replyForm.requestSubmit();
            }
        });
    }

    function openComposeModal() {
        if (!els.composeModal) return;
        if (window.WSModal && typeof window.WSModal.open === 'function') {
            window.WSModal.open('modal-msg-compose');
        } else {
            els.composeModal.classList.add('is-open');
            document.body.classList.add('ws-modal-open');
        }
        loadMembers().then(() => {
            const focus = composeKind === 'direct' ? els.recipientSelect : document.getElementById('msg-compose-body');
            focus?.focus();
        });
    }

    function closeComposeModal() {
        if (!els.composeModal) return;
        if (window.WSModal && typeof window.WSModal.close === 'function') {
            window.WSModal.close(els.composeModal);
        } else {
            els.composeModal.classList.remove('is-open');
            document.body.classList.remove('ws-modal-open');
        }
        els.composeForm?.reset();
        renderFileList(null);
        setComposeKind('direct');
    }

    function showCompose() {
        openComposeModal();
    }

    function hideCompose() {
        closeComposeModal();
    }

    function setComposeKind(kind) {
        composeKind = kind;
        document.querySelectorAll('[data-msg-compose-kind] [data-kind]').forEach(btn => {
            const active = btn.dataset.kind === kind;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        const showRecipient = kind === 'direct';
        const recipientField = document.querySelector('[data-field-recipient]');
        const subjectField = document.querySelector('[data-field-subject]');
        const rolesField = document.querySelector('[data-field-roles]');
        if (recipientField) recipientField.hidden = !showRecipient;
        if (subjectField) subjectField.hidden = showRecipient;
        if (rolesField) rolesField.hidden = showRecipient;
        if (els.recipientSelect) {
            if (showRecipient) els.recipientSelect.setAttribute('required', 'required');
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
                ? items.map(n => `<li class="crm-msg-notif-item ${n.is_read ? '' : 'unread'}" data-link="${escapeHtml(n.link)}">
                    <strong>${escapeHtml(n.title)}</strong>
                    <p>${escapeHtml(n.body)}</p>
                    <time datetime="${escapeHtml(n.created_at)}">${formatTime(n.created_at)}</time>
                </li>`).join('')
                : renderEmptyState('fa-bell-slash', 'اعلان جدیدی نیست');
            els.notifList.querySelectorAll('[data-link]').forEach(li => {
                li.addEventListener('click', () => {
                    const link = li.dataset.link || '';
                    if (link.includes('thread=')) {
                        const m = link.match(/thread=(\d+)/);
                        if (m) openThread(parseInt(m[1], 10));
                    }
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

    root.querySelectorAll('[data-msg-compose]').forEach(btn => btn.addEventListener('click', showCompose));
    document.querySelectorAll('[data-msg-compose-close]').forEach(b => b.addEventListener('click', hideCompose));
    root.querySelector('[data-msg-notifications]')?.addEventListener('click', openNotifDrawer);
    document.querySelectorAll('[data-msg-notif-close]').forEach(b => b.addEventListener('click', closeNotifDrawer));
    document.querySelector('[data-msg-notif-read-all]')?.addEventListener('click', () => {
        fetchJson(apiNotifications, { method: 'POST', body: JSON.stringify({ action: 'read_all' }) })
            .then(() => { loadNotifications(); refreshUnread(); });
    });

    els.backBtn?.addEventListener('click', closeDetail);

    mobileMq.addEventListener('change', () => {
        if (!mobileMq.matches) setDetailOpen(false);
    });

    document.querySelectorAll('[data-msg-compose-kind] [data-kind]').forEach(btn => {
        btn.addEventListener('click', () => setComposeKind(btn.dataset.kind));
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && els.composeModal?.classList.contains('is-open')) {
            hideCompose();
        }
    });

    initUploadZone();
    initComposer();

    els.starBtn?.addEventListener('click', () => {
        const starred = !els.starBtn.classList.contains('active');
        patchThread({ is_starred: starred });
        els.starBtn.classList.toggle('active', starred);
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
        const fd = new FormData(els.replyForm);
        fetch(`${apiThreads}${currentThreadId}/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf },
            body: fd,
        }).then(parseResponse).then(data => {
            if (data.ok) {
                els.replyForm.reset();
                const input = els.replyForm.querySelector('.crm-msg-composer-input');
                if (input) input.style.height = 'auto';
                openThread(currentThreadId);
                loadThreads();
            } else {
                alert(data.error || 'خطا در ارسال');
            }
        });
    });

    els.composeForm?.addEventListener('submit', e => {
        e.preventDefault();
        if (composeKind === 'broadcast') {
            els.recipientSelect?.removeAttribute('required');
        }
        const fd = new FormData(els.composeForm);
        fd.set('kind', composeKind);
        if (composeKind === 'broadcast') {
            fd.delete('recipient_member_id');
            fd.delete('target_roles');
            document.querySelectorAll('[name=target_roles]:checked').forEach(cb => {
                fd.append('target_roles', cb.value);
            });
        } else {
            fd.delete('target_roles');
        }
        const submitBtn = els.composeSubmit;
        if (submitBtn) submitBtn.disabled = true;
        fetch(apiThreads, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf },
            body: fd,
        }).then(parseResponse).then(data => {
            if (data.ok) {
                hideCompose();
                loadThreads().then(() => {
                    const threadId = data.thread?.thread?.id;
                    if (threadId) {
                        openThread(threadId);
                    } else {
                        alert('پیام ارسال شد اما نمایش مکالمه ممکن نشد. لیست را به‌روز کنید.');
                    }
                });
                refreshUnread();
            } else {
                alert(data.error || 'خطا در ارسال');
            }
        }).catch(() => {
            alert('خطا در ارسال پیام');
        }).finally(() => {
            if (submitBtn) submitBtn.disabled = false;
        });
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
