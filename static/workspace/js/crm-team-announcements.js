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
        foot: root.querySelector('[data-ann-foot]'),
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
        statsTotal: root.querySelector('[data-ann-stats-total]'),
        statsUnread: root.querySelector('[data-ann-stats-unread]'),
        statsImportant: root.querySelector('[data-ann-stats-important]'),
        heroBadges: root.querySelector('[data-ann-hero-badges]'),
        chips: root.querySelector('[data-ann-chips]'),
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
        if (typeof crmFormatJalaliDatetime === 'function') {
            try {
                const d = new Date(iso);
                if (!isNaN(d.getTime())) {
                    const pad = n => String(n).padStart(2, '0');
                    const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
                    return crmFormatJalaliDatetime(local);
                }
            } catch (_) { /* fall through */ }
            return crmFormatJalaliDatetime(iso);
        }
        try {
            return new Date(iso).toLocaleString('fa-IR', {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        } catch (_) { return ''; }
    }

    function annNormalizeDigits(s) {
        return String(s || '').replace(/[۰-۹]/g, ch => '۰۱۲۳۴۵۶۷۸۹'.indexOf(ch));
    }

    function annJalaliToGregorian(jy, jm, jd) {
        let gy; let gm; let gd; let days;
        jy = parseInt(jy, 10);
        jm = parseInt(jm, 10);
        jd = parseInt(jd, 10);
        jy += 1595;
        days = -355668 + (365 * jy) + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4)
            + jd + ((jm < 7) ? (jm - 1) * 31 : ((jm - 7) * 30) + 186);
        gy = 400 * Math.floor(days / 146097);
        days %= 146097;
        if (days > 36524) {
            gy += 100 * Math.floor(--days / 36524);
            days %= 36524;
            if (days >= 365) days++;
        }
        gy += 4 * Math.floor(days / 1461);
        days %= 1461;
        if (days > 365) {
            gy += Math.floor((days - 1) / 365);
            days = (days - 1) % 365;
        }
        gd = days + 1;
        const sal_a = [0, 31, ((gy % 4 === 0 && gy % 100 !== 0) || (gy % 400 === 0)) ? 29 : 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        for (gm = 0; gm < 13 && gd > sal_a[gm]; gm++) gd -= sal_a[gm];
        return [gy, gm, gd];
    }

    function annLocalJalaliDatetime(date) {
        const d = date || new Date();
        if (typeof crmGregorianToJalali === 'function' && typeof crmToPersianDigits === 'function') {
            const [jy, jm, jd] = crmGregorianToJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
            const ds = `${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`;
            const ts = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
            return crmToPersianDigits(`${ds} ${ts}`);
        }
        return d.toLocaleString('fa-IR');
    }

    function annIsoToJalaliInput(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            if (isNaN(d.getTime())) return '';
            return annLocalJalaliDatetime(d);
        } catch (_) { return ''; }
    }

    function annParseJalaliInput(value) {
        const s = annNormalizeDigits(value).trim();
        if (!s) return null;
        const m = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?/);
        if (!m) return null;
        const [gy, gm, gd] = annJalaliToGregorian(+m[1], +m[2], +m[3]);
        return new Date(gy, gm - 1, gd, m[4] != null ? +m[4] : 0, m[5] != null ? +m[5] : 0, 0);
    }

    function annInitJalaliPickers() {
        if (typeof initCRMJalaliPickers === 'function' && els.composeModal) {
            initCRMJalaliPickers(els.composeModal);
        }
    }

    function annSyncImportanceCards() {
        const picker = document.querySelector('[data-ann-importance-picker]');
        if (!picker) return;
        picker.querySelectorAll('.crm-ann-importance-card').forEach(card => {
            const input = card.querySelector('input[type=radio]');
            card.classList.toggle('active', !!input?.checked);
        });
    }

    function annApplyPublishPreset(preset) {
        const input = els.composeForm?.querySelector('[data-ann-published]');
        if (!input) return;
        const d = new Date();
        if (preset === 'tomorrow') {
            d.setDate(d.getDate() + 1);
            d.setHours(9, 0, 0, 0);
        } else if (preset === 'nextweek') {
            d.setDate(d.getDate() + 7);
            d.setHours(9, 0, 0, 0);
        }
        input.value = annLocalJalaliDatetime(d);
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function annApplyExpirePreset(preset) {
        const input = els.composeForm?.querySelector('[data-ann-expires]');
        if (!input) return;
        if (preset === 'none') {
            input.value = '';
            return;
        }
        const pubInput = els.composeForm?.querySelector('[data-ann-published]');
        const base = annParseJalaliInput(pubInput?.value) || new Date();
        const d = new Date(base.getTime());
        d.setDate(d.getDate() + (preset === '30d' ? 30 : 7));
        d.setHours(23, 59, 0, 0);
        input.value = annLocalJalaliDatetime(d);
        input.dispatchEvent(new Event('input', { bubbles: true }));
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

    function initials(name) {
        if (!name) return '؟';
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        return parts.length >= 2 ? `${parts[0][0]}${parts[1][0]}` : parts[0][0];
    }

    function importanceIcon(level) {
        const map = {
            low: 'fa-circle',
            normal: 'fa-circle-half-stroke',
            high: 'fa-triangle-exclamation',
            urgent: 'fa-bolt',
        };
        return map[level] || map.normal;
    }

    function updateStats(items, unread) {
        const active = items.filter(a => a.status === 'active');
        const important = active.filter(a => a.importance === 'high' || a.importance === 'urgent');
        if (els.statsTotal) els.statsTotal.textContent = active.length.toLocaleString('fa-IR');
        if (els.statsUnread) els.statsUnread.textContent = (unread || 0).toLocaleString('fa-IR');
        if (els.statsImportant) els.statsImportant.textContent = important.length.toLocaleString('fa-IR');
    }

    function cardTags(a) {
        const parts = [];
        if (a.is_pinned) parts.push('<span class="crm-ann-tag crm-ann-tag--pin"><i class="fas fa-thumbtack"></i> سنجاق</span>');
        if (a.status === 'scheduled') parts.push('<span class="crm-ann-tag crm-ann-tag--scheduled">زمان‌بندی</span>');
        if (a.status === 'expired') parts.push('<span class="crm-ann-tag crm-ann-tag--expired">منقضی</span>');
        if (a.target_roles && a.target_roles.length) {
            parts.push(`<span class="crm-ann-tag crm-ann-tag--audience">${escapeHtml(audienceLabel(a.target_roles))}</span>`);
        }
        return parts.join('');
    }

    function cardBadges(a) {
        const parts = [];
        if (a.is_pinned) parts.push(`<span class="crm-ann-badge crm-ann-badge--pin"><i class="fas fa-thumbtack"></i> سنجاق</span>`);
        parts.push(`<span class="crm-ann-badge ${importanceBadgeClass(a.importance)}">${IMPORTANCE_LABELS[a.importance] || a.importance}</span>`);
        if (a.status === 'scheduled') parts.push('<span class="crm-ann-badge crm-ann-badge--scheduled">زمان‌بندی</span>');
        if (a.status === 'expired') parts.push('<span class="crm-ann-badge crm-ann-badge--expired">منقضی</span>');
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
            const imp = a.importance || 'normal';
            const impClass = imp === 'urgent' ? 'is-urgent' : (imp === 'high' ? 'is-high' : '');
            const author = a.created_by || 'تیم';
            const attach = a.attachment_url
                ? '<span class="crm-ann-card-attach" title="دارای ضمیمه"><i class="fas fa-paperclip"></i></span>'
                : '';
            return `
            <li class="crm-ann-card ${unread ? 'is-unread' : ''} ${impClass} ${a.is_pinned ? 'is-pinned' : ''} ${a.id === currentAnnId ? 'is-active' : ''}"
                data-ann-id="${a.id}" role="option" aria-selected="${a.id === currentAnnId}">
                <span class="crm-ann-card-accent" aria-hidden="true"></span>
                <div class="crm-ann-card-inner">
                    <header class="crm-ann-card-top">
                        <span class="crm-ann-card-imp crm-ann-card-imp--${imp}" title="${IMPORTANCE_LABELS[imp] || imp}">
                            <i class="fas ${importanceIcon(imp)}"></i>
                        </span>
                        <div class="crm-ann-card-tags">${cardTags(a)}</div>
                        <span class="crm-ann-card-unread" ${unread ? '' : 'hidden'} aria-label="خوانده‌نشده"></span>
                    </header>
                    <h4 class="crm-ann-card-title">${escapeHtml(a.title)}</h4>
                    <p class="crm-ann-card-preview">${escapeHtml(a.body_preview || a.body || '')}</p>
                    <footer class="crm-ann-card-foot">
                        <span class="crm-ann-card-author">
                            <span class="crm-ann-card-avatar">${escapeHtml(initials(author))}</span>
                            <span>${escapeHtml(author)}</span>
                        </span>
                        <div class="crm-ann-card-meta">
                            <time datetime="${escapeHtml(a.published_at)}">${formatTime(a.published_at)}</time>
                            ${attach}
                        </div>
                    </footer>
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
        if (els.heroBadges) els.heroBadges.innerHTML = cardBadges(a);
        if (els.chips) {
            const chips = [];
            if (a.created_by) {
                chips.push(`<span class="crm-ann-chip"><i class="fas fa-user-pen"></i>${escapeHtml(a.created_by)}</span>`);
            }
            if (a.published_at) {
                chips.push(`<span class="crm-ann-chip"><i class="fas fa-calendar-check"></i>${formatTime(a.published_at)}</span>`);
            }
            chips.push(`<span class="crm-ann-chip"><i class="fas fa-users"></i>${escapeHtml(audienceLabel(a.target_roles))}</span>`);
            if (!a.is_read && a.status === 'active') {
                chips.push('<span class="crm-ann-chip"><i class="fas fa-circle-dot"></i>خوانده‌نشده</span>');
            }
            els.chips.innerHTML = chips.join('');
        }
        if (els.body) {
            let html = `<div class="crm-ann-prose">${escapeHtml(a.body || '')}</div>`;
            if (a.attachment_url) {
                html += `<a class="crm-ann-attachment" href="${escapeHtml(a.attachment_url)}" target="_blank" rel="noopener">
                    <i class="fas fa-file-arrow-down"></i>
                    <span>
                        <strong>${escapeHtml(a.attachment_name || 'دانلود ضمیمه')}</strong>
                        <small>فایل پیوست اطلاعیه</small>
                    </span>
                </a>`;
            }
            els.body.innerHTML = html;
        }
        if (els.foot) {
            const bits = [];
            if (a.is_pinned) bits.push('<span><i class="fas fa-thumbtack"></i> سنجاق‌شده در بالای تابلو</span>');
            if (a.expires_at) bits.push(`<span><i class="fas fa-hourglass-end"></i> انقضا: ${formatTime(a.expires_at)}</span>`);
            if (a.status === 'scheduled') bits.push('<span><i class="fas fa-clock"></i> منتشر نشده — زمان‌بندی شده</span>');
            if (a.status === 'expired') bits.push('<span><i class="fas fa-ban"></i> منقضی شده</span>');
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
            updateStats(announcementsCache, data.unread || 0);
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
        const pub = els.composeForm.querySelector('[data-ann-published]');
        const exp = els.composeForm.querySelector('[data-ann-expires]');
        if (ann) {
            if (els.composeTitle) els.composeTitle.textContent = 'ویرایش اطلاعیه';
            if (els.composeSub) els.composeSub.textContent = 'تغییر محتوا، زمان‌بندی شمسی یا مخاطبان';
            if (els.composeSubmitLabel) els.composeSubmitLabel.textContent = 'ذخیره تغییرات';
            els.composeForm.title.value = ann.title || '';
            els.composeForm.body.value = ann.body || '';
            const imp = ann.importance || 'normal';
            const impInput = els.composeForm.querySelector(`input[name=importance][value="${imp}"]`);
            if (impInput) impInput.checked = true;
            const pinInput = els.composeForm.querySelector('[data-ann-pin-input]');
            if (pinInput) pinInput.checked = !!ann.is_pinned;
            if (pub) pub.value = annIsoToJalaliInput(ann.published_at);
            if (exp) exp.value = ann.expires_at ? annIsoToJalaliInput(ann.expires_at) : '';
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
            if (els.composeSub) els.composeSub.textContent = 'انتشار حرفه‌ای برای کل تیم یا نقش‌های مشخص';
            if (els.composeSubmitLabel) els.composeSubmitLabel.textContent = 'انتشار اطلاعیه';
            const normalImp = els.composeForm.querySelector('input[name=importance][value=normal]');
            if (normalImp) normalImp.checked = true;
            if (pub) pub.value = annLocalJalaliDatetime(new Date());
            if (exp) exp.value = '';
            if (els.currentFile) els.currentFile.hidden = true;
        }
        annSyncImportanceCards();
        initAudiencePanel();
        els.composeModal.classList.add('is-open');
        document.body.classList.add('ws-modal-open');
        annInitJalaliPickers();
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

    document.querySelector('[data-ann-importance-picker]')?.addEventListener('change', annSyncImportanceCards);

    document.querySelector('[data-ann-publish-presets]')?.addEventListener('click', e => {
        const btn = e.target.closest('[data-preset]');
        if (!btn) return;
        e.preventDefault();
        annApplyPublishPreset(btn.dataset.preset);
    });

    document.querySelector('[data-ann-expire-presets]')?.addEventListener('click', e => {
        const btn = e.target.closest('[data-preset]');
        if (!btn) return;
        e.preventDefault();
        annApplyExpirePreset(btn.dataset.preset);
    });

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
