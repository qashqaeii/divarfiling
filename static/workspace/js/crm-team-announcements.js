/**
 * CRM Team Announcements — تابلو اطلاعیه‌های آژانس
 */
(function () {
    'use strict';

    const root = document.querySelector('[data-crm-announcements]');
    if (!root) return;

    const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const apiList = root.dataset.apiList.replace(/\/?$/, '/');
    const canManage = root.dataset.canManage === '1';
    const mobileMq = window.matchMedia('(max-width: 960px)');

    const FILTER_LABELS = {
        all: 'همه اطلاعیه‌ها',
        unread: 'خوانده‌نشده',
        important: 'مهم و فوری',
        manage: 'مدیریت اطلاعیه‌ها',
    };

    const IMPORTANCE_LABELS = {
        low: 'عادی',
        normal: 'متوسط',
        high: 'مهم',
        urgent: 'فوری',
    };

    const ROLE_LABELS = {
        owner: 'مالک',
        manager: 'مدیر',
        advisor: 'مشاور',
        secretary: 'منشی',
    };

    let currentFilter = 'all';
    let currentAnnId = null;
    let announcementsCache = [];
    let editingId = null;
    let pollTimer = null;
    let confirmCallback = null;

    const els = {
        list: root.querySelector('[data-ann-list]'),
        detail: root.querySelector('[data-ann-detail]'),
        placeholder: root.querySelector('[data-ann-placeholder]'),
        body: root.querySelector('[data-ann-body]'),
        title: root.querySelector('[data-ann-title]'),
        meta: root.querySelector('[data-ann-meta]'),
        foot: root.querySelector('[data-ann-foot]'),
        headerImportance: root.querySelector('[data-ann-header-importance]'),
        filterTitle: root.querySelector('[data-ann-filter-title]'),
        count: root.querySelector('[data-ann-count]'),
        search: root.querySelector('[data-ann-search]'),
        unreadBadge: root.querySelector('[data-ann-unread-badge]'),
        backBtn: root.querySelector('[data-ann-back]'),
        editBtn: root.querySelector('[data-ann-edit]'),
        deleteBtn: root.querySelector('[data-ann-delete]'),
        composeModal: document.getElementById('modal-ann-compose'),
        composeForm: document.querySelector('[data-ann-compose-form]'),
        composeTitle: document.querySelector('[data-ann-compose-title]'),
        composeSub: document.querySelector('[data-ann-compose-sub]'),
        composeSubmitLabel: document.querySelector('[data-ann-compose-submit-label]'),
        audienceScope: document.querySelector('[data-ann-audience-scope]'),
        audienceGrid: document.querySelector('[data-ann-audience-grid]'),
        uploadZone: document.querySelector('[data-ann-upload-zone]'),
        fileInput: document.querySelector('[data-ann-file-input]'),
        currentFile: document.querySelector('[data-ann-current-file]'),
        confirmModal: document.getElementById('modal-ann-confirm'),
        confirmTitle: document.querySelector('[data-ann-confirm-title]'),
        confirmText: document.querySelector('[data-ann-confirm-text]'),
    };

    function apiDetail(id) {
        return `${apiList}${id}/`;
    }

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

    function escapeHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function formatBadgeCount(n) {
        const count = Number(n) || 0;
        if (count <= 0) return '';
        return count > 99 ? '99+' : String(count);
    }

    function formatTime(iso) {
        if (!iso) return '';
        try {
            return new Date(iso).toLocaleString('fa-IR', {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        } catch (_) { return ''; }
    }

    function toDatetimeLocal(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            const pad = n => String(n).padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        } catch (_) { return ''; }
    }

    function nowDatetimeLocal() {
        return toDatetimeLocal(new Date().toISOString());
    }

    function importanceBadgeClass(level) {
        return `crm-ann-badge crm-ann-badge--${level || 'normal'}`;
    }

    function audienceLabel(roles) {
        if (!roles || !roles.length) return 'همه اعضا';
        return roles.map(r => ROLE_LABELS[r] || r).join('، ');
    }

    function setDetailOpen(open) {
        root.classList.toggle('crm-ann-hub--detail-open', open && mobileMq.matches);
    }

    function closeDetail() {
        currentAnnId = null;
        renderList(announcementsCache);
        if (els.detail) els.detail.hidden = true;
        if (els.placeholder) els.placeholder.hidden = false;
        setDetailOpen(false);
    }

    function updateUnreadBadges(n) {
        const label = formatBadgeCount(n);
        if (els.unreadBadge) {
            if (label) {
                els.unreadBadge.textContent = label;
                els.unreadBadge.hidden = false;
            } else {
                els.unreadBadge.hidden = true;
            }
        }
        if (window.crmTeamHubUnread) {
            window.crmTeamHubUnread.setAnnouncements(n);
        }
    }

    function buildListUrl() {
        const params = new URLSearchParams();
        if (currentFilter === 'unread') params.set('unread', '1');
        if (currentFilter === 'important') params.set('important', '1');
        if (currentFilter === 'manage') params.set('manage', '1');
        const q = params.toString();
        return q ? `${apiList}?${q}` : apiList;
    }

    function renderEmptyState(icon, text) {
        return `<li class="crm-ann-state"><span class="crm-ann-state-ring"><i class="fas ${icon}"></i></span><p>${text}</p></li>`;
    }

    function cardBadges(a) {
        const parts = [];
        if (a.is_pinned) parts.push('<span class="crm-ann-badge crm-ann-badge--pin"><i class="fas fa-thumbtack"></i></span>');
        if (a.status === 'scheduled') parts.push('<span class="crm-ann-badge crm-ann-badge--scheduled">زمان‌بندی</span>');
        if (a.status === 'expired') parts.push('<span class="crm-ann-badge crm-ann-badge--expired">منقضی</span>');
        parts.push(`<span class="${importanceBadgeClass(a.importance)}">${IMPORTANCE_LABELS[a.importance] || a.importance}</span>`);
        return parts.join('');
    }

    function renderList(items) {
        const q = (els.search?.value || '').trim().toLowerCase();
        const filtered = q ? items.filter(a => (a.title || '').toLowerCase().includes(q) ||
            (a.body_preview || a.body || '').toLowerCase().includes(q)) : items;

        if (els.filterTitle) els.filterTitle.textContent = FILTER_LABELS[currentFilter] || 'اطلاعیه‌ها';
        if (els.count) {
            els.count.textContent = filtered.length
                ? `${filtered.length.toLocaleString('fa-IR')} اطلاعیه`
                : 'اطلاعیه‌ای نیست';
        }

        if (!filtered.length) {
            const text = q ? 'نتیجه‌ای یافت نشد.' :
                currentFilter === 'unread' ? 'همه اطلاعیه‌ها خوانده شده‌اند.' :
                currentFilter === 'important' ? 'اطلاعیه مهم فعالی نیست.' :
                currentFilter === 'manage' ? 'اطلاعیه‌ای ثبت نشده است.' : 'تابلو اطلاعیه خالی است.';
            els.list.innerHTML = renderEmptyState(q ? 'fa-magnifying-glass' : 'fa-bullhorn', text);
            return;
        }

        els.list.innerHTML = filtered.map(a => {
            const unread = !a.is_read && a.status === 'active';
            const impClass = a.importance === 'urgent' ? 'is-urgent' : (a.importance === 'high' ? 'is-high' : '');
            return `
            <li class="crm-ann-card ${unread ? 'is-unread' : ''} ${impClass} ${a.id === currentAnnId ? 'is-active' : ''}"
                data-ann-id="${a.id}" role="option" aria-selected="${a.id === currentAnnId}">
                <div class="crm-ann-card-head">
                    <h4 class="crm-ann-card-title">${escapeHtml(a.title)}</h4>
                    <div class="crm-ann-card-badges">${cardBadges(a)}</div>
                </div>
                <p class="crm-ann-card-preview">${escapeHtml(a.body_preview || a.body || '')}</p>
                <div class="crm-ann-card-foot">
                    <span>${escapeHtml(a.created_by || 'تیم')}</span>
                    <time datetime="${escapeHtml(a.published_at)}">${formatTime(a.published_at)}</time>
                </div>
            </li>`;
        }).join('');

        els.list.querySelectorAll('[data-ann-id]').forEach(el => {
            el.addEventListener('click', () => openAnnouncement(Number(el.dataset.annId)));
        });
    }

    function renderDetail(a) {
        if (!a) return;
        if (els.title) els.title.textContent = a.title || '—';
        if (els.meta) {
            const parts = [a.created_by, formatTime(a.published_at)].filter(Boolean);
            if (a.target_roles && a.target_roles.length) parts.push(audienceLabel(a.target_roles));
            els.meta.textContent = parts.join(' · ');
        }
        if (els.headerImportance) {
            els.headerImportance.className = `crm-ann-importance-badge ${importanceBadgeClass(a.importance)}`;
            els.headerImportance.textContent = IMPORTANCE_LABELS[a.importance] || a.importance;
        }
        if (els.body) {
            let html = escapeHtml(a.body || '');
            if (a.attachment_url) {
                html += `<a class="crm-ann-attachment" href="${escapeHtml(a.attachment_url)}" target="_blank" rel="noopener">
                    <i class="fas fa-paperclip"></i>
                    <span>${escapeHtml(a.attachment_name || 'دانلود ضمیمه')}</span>
                </a>`;
            }
            els.body.innerHTML = html;
        }
        if (els.foot) {
            const bits = [];
            if (a.is_pinned) bits.push('<span><i class="fas fa-thumbtack"></i> سنجاق‌شده</span>');
            if (a.expires_at) bits.push(`<span>انقضا: ${formatTime(a.expires_at)}</span>`);
            if (a.status === 'scheduled') bits.push('<span>منتشر نشده — زمان‌بندی شده</span>');
            if (a.status === 'expired') bits.push('<span>منقضی شده</span>');
            if (bits.length) {
                els.foot.innerHTML = bits.join('');
                els.foot.hidden = false;
            } else {
                els.foot.hidden = true;
            }
        }
    }

    function openAnnouncement(id) {
        currentAnnId = id;
        renderList(announcementsCache);
        if (els.detail) els.detail.hidden = false;
        if (els.placeholder) els.placeholder.hidden = true;
        setDetailOpen(true);

        fetchJson(apiDetail(id)).then(data => {
            if (!data.ok || !data.announcement) {
                alert(data.error || 'خطا در بارگذاری اطلاعیه');
                return;
            }
            const a = data.announcement;
            const idx = announcementsCache.findIndex(x => x.id === id);
            if (idx >= 0) announcementsCache[idx] = Object.assign({}, announcementsCache[idx], a);
            renderDetail(a);
            if (!a.is_read && a.status === 'active') {
                fetchJson(apiDetail(id), {
                    method: 'PATCH',
                    body: JSON.stringify({ action: 'read' }),
                }).then(res => {
                    if (res.ok) {
                        if (idx >= 0) announcementsCache[idx].is_read = true;
                        renderList(announcementsCache);
                        refreshUnread();
                    }
                });
            }
        });
    }

    function loadAnnouncements() {
        return fetchJson(buildListUrl()).then(data => {
            if (!data.ok) {
                els.list.innerHTML = renderEmptyState('fa-triangle-exclamation', data.error || 'خطا در بارگذاری');
                return;
            }
            announcementsCache = data.announcements || [];
            renderList(announcementsCache);
            updateUnreadBadges(data.unread || 0);
            const initialId = root.dataset.initialId;
            if (initialId && !currentAnnId) {
                root.dataset.initialId = '';
                openAnnouncement(Number(initialId));
            }
        });
    }

    function refreshUnread() {
        fetchJson(apiList).then(data => {
            if (data.ok) updateUnreadBadges(data.unread || 0);
        });
    }

    function initAudiencePanel() {
        if (!els.audienceGrid || !els.audienceScope) return;
        const sync = () => {
            const checked = [...els.audienceGrid.querySelectorAll('input:checked')];
            if (!checked.length) {
                els.audienceScope.textContent = 'همه اعضا';
                els.audienceScope.classList.add('is-all');
                els.audienceScope.classList.remove('is-partial');
            } else {
                els.audienceScope.textContent = checked.map(i => ROLE_LABELS[i.value] || i.value).join('، ');
                els.audienceScope.classList.remove('is-all');
                els.audienceScope.classList.add('is-partial');
            }
        };
        els.audienceGrid.querySelectorAll('input').forEach(i => i.addEventListener('change', sync));
        sync();
    }

    function initUploadZone() {
        if (!els.uploadZone || !els.fileInput) return;
        els.uploadZone.addEventListener('click', () => els.fileInput.click());
        els.uploadZone.addEventListener('dragover', e => { e.preventDefault(); els.uploadZone.classList.add('is-drag'); });
        els.uploadZone.addEventListener('dragleave', () => els.uploadZone.classList.remove('is-drag'));
        els.uploadZone.addEventListener('drop', e => {
            e.preventDefault();
            els.uploadZone.classList.remove('is-drag');
            if (e.dataTransfer.files.length) els.fileInput.files = e.dataTransfer.files;
        });
        els.fileInput.addEventListener('change', () => {
            if (els.currentFile && els.fileInput.files[0]) {
                els.currentFile.textContent = `فایل انتخاب‌شده: ${els.fileInput.files[0].name}`;
                els.currentFile.hidden = false;
            }
        });
    }

    function openComposeModal(ann) {
        if (!els.composeModal || !els.composeForm) return;
        editingId = ann ? ann.id : null;
        els.composeForm.reset();
        if (els.audienceGrid) {
            els.audienceGrid.querySelectorAll('input').forEach(i => { i.checked = false; });
        }
        if (ann) {
            if (els.composeTitle) els.composeTitle.textContent = 'ویرایش اطلاعیه';
            if (els.composeSub) els.composeSub.textContent = 'تغییر محتوا، مخاطبان یا زمان انتشار';
            if (els.composeSubmitLabel) els.composeSubmitLabel.textContent = 'ذخیره تغییرات';
            els.composeForm.title.value = ann.title || '';
            els.composeForm.body.value = ann.body || '';
            els.composeForm.importance.value = ann.importance || 'normal';
            const pinInput = els.composeForm.querySelector('[data-ann-pin-input]');
            if (pinInput) pinInput.checked = !!ann.is_pinned;
            const pub = els.composeForm.querySelector('[data-ann-published]');
            const exp = els.composeForm.querySelector('[data-ann-expires]');
            if (pub) pub.value = toDatetimeLocal(ann.published_at);
            if (exp) exp.value = toDatetimeLocal(ann.expires_at);
            (ann.target_roles || []).forEach(role => {
                const cb = els.audienceGrid?.querySelector(`input[value="${role}"]`);
                if (cb) cb.checked = true;
            });
            if (els.currentFile && ann.attachment_name) {
                els.currentFile.textContent = `ضمیمه فعلی: ${ann.attachment_name}`;
                els.currentFile.hidden = false;
            } else if (els.currentFile) {
                els.currentFile.hidden = true;
            }
        } else {
            if (els.composeTitle) els.composeTitle.textContent = 'اطلاعیه جدید';
            if (els.composeSub) els.composeSub.textContent = 'انتشار برای همه یا نقش‌های مشخص';
            if (els.composeSubmitLabel) els.composeSubmitLabel.textContent = 'انتشار اطلاعیه';
            const pub = els.composeForm.querySelector('[data-ann-published]');
            if (pub) pub.value = nowDatetimeLocal();
            if (els.currentFile) els.currentFile.hidden = true;
        }
        initAudiencePanel();
        els.composeModal.classList.add('is-open');
        document.body.classList.add('ws-modal-open');
    }

    function closeComposeModal() {
        if (!els.composeModal) return;
        els.composeModal.classList.remove('is-open');
        document.body.classList.remove('ws-modal-open');
        editingId = null;
    }

    function confirmAction(title, text, cb) {
        confirmCallback = cb;
        if (els.confirmTitle) els.confirmTitle.textContent = title;
        if (els.confirmText) els.confirmText.textContent = text;
        if (els.confirmModal) {
            els.confirmModal.classList.add('is-open');
            document.body.classList.add('ws-modal-open');
        }
    }

    function closeConfirm() {
        confirmCallback = null;
        if (els.confirmModal) els.confirmModal.classList.remove('is-open');
        if (!els.composeModal?.classList.contains('is-open')) {
            document.body.classList.remove('ws-modal-open');
        }
    }

    function submitCompose(e) {
        e.preventDefault();
        if (!els.composeForm) return;
        const fd = new FormData(els.composeForm);
        if (!fd.get('is_pinned')) fd.delete('is_pinned');
        const submitBtn = document.querySelector('[data-ann-compose-submit]');
        if (submitBtn) submitBtn.disabled = true;

        const url = editingId ? apiDetail(editingId) : apiList;
        const method = editingId ? 'PATCH' : 'POST';

        fetch(url, { method, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf }, body: fd })
            .then(parseResponse)
            .then(data => {
                if (!data.ok) {
                    alert(data.error || 'خطا در ذخیره اطلاعیه');
                    return;
                }
                closeComposeModal();
                loadAnnouncements().then(() => {
                    const id = editingId || data.id;
                    if (id) openAnnouncement(Number(id));
                });
            })
            .finally(() => { if (submitBtn) submitBtn.disabled = false; });
    }

    function deleteCurrent() {
        if (!currentAnnId) return;
        confirmAction('حذف اطلاعیه', 'این اطلاعیه برای همه اعضا حذف می‌شود. ادامه می‌دهید؟', () => {
            fetchJson(apiDetail(currentAnnId), { method: 'DELETE' }).then(data => {
                if (!data.ok) { alert(data.error || 'خطا در حذف'); return; }
                closeDetail();
                loadAnnouncements();
            });
        });
    }

    root.querySelectorAll('[data-ann-compose]').forEach(btn => {
        btn.addEventListener('click', () => openComposeModal(null));
    });

    root.querySelectorAll('[data-ann-filter]').forEach(btn => {
        btn.addEventListener('click', () => {
            root.querySelectorAll('[data-ann-filter]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter || 'all';
            closeDetail();
            loadAnnouncements();
        });
    });

    els.backBtn?.addEventListener('click', closeDetail);
    mobileMq.addEventListener('change', () => { if (!mobileMq.matches) setDetailOpen(false); });
    els.search?.addEventListener('input', () => renderList(announcementsCache));
    els.composeForm?.addEventListener('submit', submitCompose);
    els.editBtn?.addEventListener('click', () => {
        const ann = announcementsCache.find(a => a.id === currentAnnId);
        if (ann) {
            fetchJson(apiDetail(currentAnnId)).then(data => {
                if (data.ok && data.announcement) openComposeModal(data.announcement);
            });
        }
    });
    els.deleteBtn?.addEventListener('click', deleteCurrent);

    document.querySelectorAll('[data-ann-compose-close]').forEach(b => b.addEventListener('click', closeComposeModal));
    document.querySelector('[data-ann-confirm-ok]')?.addEventListener('click', () => {
        const cb = confirmCallback;
        closeConfirm();
        if (cb) cb();
    });
    document.querySelectorAll('[data-ann-confirm-cancel]').forEach(b => b.addEventListener('click', closeConfirm));

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            if (els.confirmModal?.classList.contains('is-open')) closeConfirm();
            else if (els.composeModal?.classList.contains('is-open')) closeComposeModal();
        }
    });

    initUploadZone();
    initAudiencePanel();
    loadAnnouncements();

    pollTimer = setInterval(() => {
        loadAnnouncements();
        if (currentAnnId) openAnnouncement(currentAnnId);
    }, 60000);

    window.addEventListener('beforeunload', () => clearInterval(pollTimer));
})();
