/**
 * CRM Team Messages — صندوق پیام داخلی آژانس
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
        replyForm: root.querySelector('[data-msg-reply-form]'),
        starBtn: root.querySelector('[data-msg-star]'),
        archiveBtn: root.querySelector('[data-msg-archive]'),
        search: root.querySelector('[data-msg-search]'),
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

    function fetchJson(url, opts = {}) {
        const headers = Object.assign({ 'X-CSRFToken': csrf }, opts.headers || {});
        if (opts.body && !(opts.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }
        return fetch(url, Object.assign({ credentials: 'same-origin' }, opts, { headers }))
            .then(r => r.json());
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

    function renderThreads(threads) {
        const q = (els.search?.value || '').trim().toLowerCase();
        const filtered = q
            ? threads.filter(t => (t.subject || '').toLowerCase().includes(q) || (t.participants_label || '').toLowerCase().includes(q))
            : threads;
        if (!filtered.length) {
            els.threadList.innerHTML = '<li class="crm-msg-thread-empty">پیامی یافت نشد</li>';
            return;
        }
        els.threadList.innerHTML = filtered.map(t => `
            <li class="crm-msg-thread-item ${t.unread_count ? 'unread' : ''} ${t.id === currentThreadId ? 'active' : ''}"
                data-thread-id="${t.id}" role="option">
                <div class="crm-msg-thread-item-head">
                    <strong>${escapeHtml(t.subject || t.participants_label)}</strong>
                    <time>${formatTime(t.updated_at)}</time>
                </div>
                <div class="crm-msg-thread-preview">${escapeHtml((t.last_message && t.last_message.body) || '')}</div>
            </li>
        `).join('');
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
            els.placeholder.hidden = true;
            els.detail.hidden = false;
            const t = data.thread;
            els.subject.textContent = t.subject || t.participants_label;
            els.participants.textContent = t.participants_label;
            els.starBtn.classList.toggle('active', t.is_starred);
            els.starBtn.querySelector('i').className = t.is_starred ? 'fas fa-star' : 'far fa-star';
            els.messages.innerHTML = (data.messages || []).map(renderBubble).join('');
            els.messages.scrollTop = els.messages.scrollHeight;
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
                <time>${formatTime(m.created_at)}</time>
            </div>
            <div>${escapeHtml(m.body).replace(/\n/g, '<br>')}</div>
            ${atts ? `<div class="crm-msg-attachments">${atts}</div>` : ''}
        </article>`;
    }

    function refreshUnread() {
        fetchJson(apiUnread).then(data => {
            if (!data.ok) return;
            const n = data.unread_messages || 0;
            if (els.folderUnread) {
                els.folderUnread.textContent = n;
                els.folderUnread.hidden = !n;
            }
            if (els.notifCount) {
                const nn = data.unread_notifications || 0;
                els.notifCount.textContent = nn;
                els.notifCount.hidden = !nn;
            }
            const tabBadge = document.querySelector('a[href="?tab=messages"] em');
            if (tabBadge) {
                tabBadge.textContent = n;
                tabBadge.style.display = n ? '' : 'none';
            }
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
                    <time>${formatTime(n.created_at)}</time>
                </li>`).join('')
                : '<li class="crm-msg-thread-empty">اعلان جدیدی نیست</li>';
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
            currentThreadId = null;
            els.detail.hidden = true;
            els.placeholder.hidden = false;
            loadThreads();
        });
    });

    root.querySelector('[data-msg-compose]')?.addEventListener('click', showCompose);
    document.querySelectorAll('[data-msg-compose-close]').forEach(b => b.addEventListener('click', hideCompose));
    root.querySelector('[data-msg-notifications]')?.addEventListener('click', openNotifDrawer);
    document.querySelectorAll('[data-msg-notif-close]').forEach(b => b.addEventListener('click', closeNotifDrawer));
    document.querySelector('[data-msg-notif-read-all]')?.addEventListener('click', () => {
        fetchJson(apiNotifications, { method: 'POST', body: JSON.stringify({ action: 'read_all' }) })
            .then(() => { loadNotifications(); refreshUnread(); });
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

    els.starBtn?.addEventListener('click', () => {
        const starred = !els.starBtn.classList.contains('active');
        patchThread({ is_starred: starred });
        els.starBtn.classList.toggle('active', starred);
        els.starBtn.querySelector('i').className = starred ? 'fas fa-star' : 'far fa-star';
    });

    els.archiveBtn?.addEventListener('click', () => {
        patchThread({ is_archived: true });
        currentThreadId = null;
        els.detail.hidden = true;
        els.placeholder.hidden = false;
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
        }).then(r => r.json()).then(data => {
            if (data.ok) {
                els.replyForm.reset();
                openThread(currentThreadId);
                loadThreads();
            } else {
                alert(data.error || 'خطا در ارسال');
            }
        });
    });

    els.composeForm?.addEventListener('submit', e => {
        e.preventDefault();
        const fd = new FormData(els.composeForm);
        fd.append('kind', composeKind);
        if (composeKind === 'broadcast') {
            fd.delete('recipient_member_id');
            document.querySelectorAll('[name=target_roles]:checked').forEach(cb => {
                fd.append('target_roles', cb.value);
            });
        }
        const submitBtn = els.composeSubmit;
        if (submitBtn) submitBtn.disabled = true;
        fetch(apiThreads, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf },
            body: fd,
        }).then(r => r.json()).then(data => {
            if (data.ok) {
                hideCompose();
                loadThreads().then(() => {
                    if (data.thread && data.thread.thread) openThread(data.thread.thread.id);
                });
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
