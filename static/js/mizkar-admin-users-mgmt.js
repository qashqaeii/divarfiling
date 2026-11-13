/**
 * مدیریت کاربران — جدول AJAX + پنل جزئیات
 */
(function () {
    'use strict';

    const root = document.getElementById('ecc-users-mgmt');
    if (!root) return;

    const listUrl = root.getAttribute('data-users-list-url');
    const detailTemplate = root.getAttribute('data-users-detail-url-template') || '';
    const profileTemplate = root.getAttribute('data-users-profile-url-template') || '';
    const bodyEl = document.getElementById('eccUsersMgmtBody');
    const pagerEl = document.getElementById('eccUsersMgmtPager');
    const pageInfoEl = document.getElementById('eccUsersMgmtPageInfo');
    const prevBtn = document.getElementById('eccUsersMgmtPrev');
    const nextBtn = document.getElementById('eccUsersMgmtNext');
    const searchEl = document.getElementById('eccUsersMgmtSearch');
    const resetBtn = document.getElementById('eccUsersMgmtReset');
    const statusEl = document.getElementById('eccUsersMgmtStatus');
    const filterIds = {
        license: 'eccUsersMgmtLicense',
        windows: 'eccUsersMgmtWindows',
        android: 'eccUsersMgmtAndroid',
        datasets: 'eccUsersMgmtDatasets',
        crm: 'eccUsersMgmtCrm',
        paid: 'eccUsersMgmtPaid',
    };

    const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    let page = 1;
    let totalPages = 1;
    let searchTimer = null;
    let abortList = null;
    let listRequestId = 0;

    function toFa(value) {
        return String(value == null ? '' : value).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function money(value) {
        const n = Number(value) || 0;
        return toFa(n.toLocaleString('en-US'));
    }

    function esc(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function flag(ok, labelOk, labelOff) {
        if (ok) {
            return '<span class="ecc-um-flag ecc-um-flag--ok">' + esc(labelOk) + '</span>';
        }
        return '<span class="ecc-um-flag ecc-um-flag--off">' + esc(labelOff) + '</span>';
    }

    function windowsCell(w) {
        const parts = [];
        parts.push(flag(w.downloaded, 'دانلود', 'دانلود'));
        parts.push(flag(w.activated, 'فعال', 'فعال'));
        parts.push(flag(w.first_launch, 'اجرا', 'اجرا'));
        return '<div class="ecc-users-mgmt-flags">' + parts.join('') + '</div>';
    }

    function detailUrl(userId) {
        return detailTemplate.replace(/\/0\.json$/, '/' + userId + '.json');
    }

    function profileUrl(userId) {
        if (!profileTemplate) return '';
        const base = profileTemplate.replace(/\/0\/?$/, '/' + userId + '/');
        const ret = encodeURIComponent(window.location.pathname + window.location.search + '#ecc-users');
        return base + (base.indexOf('?') >= 0 ? '&' : '?') + 'return=' + ret;
    }

    function currentFilters() {
        const f = {};
        Object.keys(filterIds).forEach(function (key) {
            const el = document.getElementById(filterIds[key]);
            if (el && el.value) f[key] = el.value;
        });
        return f;
    }

    function hasFilters() {
        return !!((searchEl && searchEl.value.trim()) || Object.keys(currentFilters()).length);
    }

    function updateFilterActions() {
        if (resetBtn) resetBtn.hidden = !hasFilters();
    }

    function showListStatus(message) {
        if (statusEl) statusEl.textContent = message;
    }

    function resetFilters() {
        clearTimeout(searchTimer);
        if (searchEl) searchEl.value = '';
        Object.keys(filterIds).forEach(function (key) {
            const el = document.getElementById(filterIds[key]);
            if (el) el.value = '';
        });
        page = 1;
        updateFilterActions();
        loadList();
    }

    function buildListQuery() {
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('page_size', '25');
        params.set('sort', '-date_joined');
        const q = (searchEl && searchEl.value || '').trim();
        if (q) params.set('q', q);
        const filters = currentFilters();
        Object.keys(filters).forEach(function (k) {
            params.set(k, filters[k]);
        });
        return params.toString();
    }

    function renderRows(results) {
        if (!results.length) {
            const reset = hasFilters()
                ? '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-reset-users-filter>پاک‌کردن فیلترها</button>'
                : '';
            bodyEl.innerHTML = '<tr><td colspan="8" class="adm-empty"> '
                + (hasFilters() ? 'کاربری با این جستجو یا فیلتر یافت نشد' : 'هنوز کاربری ثبت نشده است')
                + ' ' + reset + '</td></tr>';
            return;
        }
        bodyEl.innerHTML = results.map(function (u) {
            const lic = u.has_active_license
                ? '<span class="ecc-um-flag ecc-um-flag--ok">' + esc(u.license_access_label || u.license_plan || 'فعال') + '</span>'
                  + '<small style="display:block;margin-top:.15rem;color:var(--ecc-text-muted);font-size:.65rem">'
                  + esc(u.license_expires_jalali) + '</small>'
                : (u.has_pending_bot_activation
                    ? '<span class="ecc-um-flag ecc-um-flag--warn">در انتظار فعال‌سازی</span>'
                    : '<span class="ecc-um-flag ecc-um-flag--warn">بدون لایسنس</span>');
            const paid = u.paid_orders_count
                ? '<strong>' + money(u.total_spent) + '</strong><small style="display:block;color:var(--ecc-text-muted)">'
                  + toFa(u.paid_orders_count) + ' سفارش</small>'
                : '<span class="ecc-um-flag ecc-um-flag--off">—</span>';
            const android = u.android.installed
                ? '<span class="ecc-um-flag ecc-um-flag--ok">' + toFa(u.android.devices_count) + ' دستگاه</span>'
                : '<span class="ecc-um-flag ecc-um-flag--off">—</span>';
            const ds = u.datasets_count
                ? '<strong>' + toFa(u.datasets_count) + '</strong><small style="display:block;color:var(--ecc-text-muted)">'
                  + toFa(u.listings_total) + ' آگهی</small>'
                : '<span class="ecc-um-flag ecc-um-flag--off">—</span>';
            const crm = u.crm_contacts_count
                ? '<strong>' + toFa(u.crm_contacts_count) + '</strong><small style="display:block;color:var(--ecc-text-muted)">'
                  + toFa(u.crm_deals_count) + ' معامله</small>'
                : '<span class="ecc-um-flag ecc-um-flag--off">—</span>';
            const href = profileUrl(u.id);
            const userCell = href
                ? '<a class="ecc-users-mgmt-user-link adm-user-360-link adm-user-360-link--profile" href="' + esc(href) + '">'
                  + '<span class="adm-user-360-link__text"><strong>' + esc(u.name) + '</strong>'
                  + '<small>' + esc(u.phone || u.email || '—') + '</small></span>'
                  + '<i class="fas fa-arrow-left adm-user-360-link__goto" aria-hidden="true"></i></a>'
                : '<strong>' + esc(u.name) + '</strong><small>' + esc(u.phone || u.email || '—') + '</small>';
            const rowHref = href ? ' data-u360-href="' + esc(href) + '"' : '';
            return (
                '<tr data-user-id="' + u.id + '" class="adm-users-row--profile"' + rowHref + '>' +
                '<td class="ecc-users-mgmt-user">' + userCell + '</td>' +
                '<td>' + lic + '</td>' +
                '<td>' + paid + '</td>' +
                '<td>' + windowsCell(u.windows) + '</td>' +
                '<td>' + android + '</td>' +
                '<td>' + ds + '</td>' +
                '<td>' + crm + '</td>' +
                '<td>' + esc(u.last_login_jalali) + '</td>' +
                '</tr>'
            );
        }).join('');
    }

    function updatePager(data) {
        totalPages = data.total_pages || 1;
        page = data.page || 1;
        pagerEl.hidden = totalPages <= 1;
        pageInfoEl.textContent = toFa(page) + ' / ' + toFa(totalPages)
            + ' — ' + toFa(data.total) + ' کاربر';
        prevBtn.disabled = !data.has_prev;
        nextBtn.disabled = !data.has_next;
    }

    function loadList() {
        if (!listUrl || !bodyEl) return;
        if (abortList) abortList.abort();
        const requestId = ++listRequestId;
        abortList = new AbortController();
        updateFilterActions();
        showListStatus('در حال دریافت کاربران…');
        if (pagerEl) pagerEl.hidden = true;
        bodyEl.innerHTML = '<tr><td colspan="8" class="adm-empty">در حال بارگذاری…</td></tr>';

        fetch(listUrl + '?' + buildListQuery(), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
            signal: abortList.signal,
        })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                if (requestId !== listRequestId) return;
                if (!data || data.ok !== true || !Array.isArray(data.results)) {
                    throw new Error('Invalid response');
                }
                updatePager(data);
                renderRows(data.results);
                showListStatus(
                    data.total
                        ? toFa(data.total) + ' کاربر در نتایج ' + (hasFilters() ? 'فیلترشده' : 'فهرست')
                        : 'نتیجه‌ای یافت نشد'
                );
            })
            .catch(function (err) {
                if (requestId !== listRequestId || err.name === 'AbortError') return;
                if (pagerEl) pagerEl.hidden = true;
                showListStatus('دریافت فهرست کاربران ناموفق بود؛ دوباره تلاش کنید.');
                bodyEl.innerHTML = '<tr><td colspan="8" class="adm-empty">'
                    + 'ارتباط با سرور برقرار نشد. '
                    + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-retry-users-list>تلاش مجدد</button>'
                    + '</td></tr>';
            });
    }

    bodyEl.addEventListener('click', function (e) {
        if (e.target.closest('[data-retry-users-list]')) {
            loadList();
            return;
        }
        if (e.target.closest('[data-reset-users-filter]')) {
            resetFilters();
        }
        if (e.target.closest('a')) {
            return;
        }
        const tr = e.target.closest('tr[data-user-id]');
        if (!tr) return;
        const href = profileUrl(tr.getAttribute('data-user-id'));
        if (href) {
            window.location.href = href;
        }
    });

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            if (page > 1) {
                page -= 1;
                loadList();
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            if (page < totalPages) {
                page += 1;
                loadList();
            }
        });
    }

    if (resetBtn) resetBtn.addEventListener('click', resetFilters);

    if (searchEl) {
        searchEl.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () {
                page = 1;
                loadList();
            }, 320);
        });
    }

    Object.keys(filterIds).forEach(function (key) {
        const el = document.getElementById(filterIds[key]);
        if (!el) return;
        el.addEventListener('change', function () {
            clearTimeout(searchTimer);
            page = 1;
            loadList();
        });
    });

    // Lazy-load when section enters viewport (or immediately if already visible / hash)
    function shouldLoadNow() {
        if (location.hash === '#ecc-users' || location.hash === '#ecc-users-mgmt') return true;
        const section = document.getElementById('ecc-users');
        if (!section || !('IntersectionObserver' in window)) return true;
        const rect = section.getBoundingClientRect();
        return rect.top < window.innerHeight && rect.bottom > 0;
    }

    let loadedOnce = false;
    function ensureLoaded() {
        if (loadedOnce) return;
        loadedOnce = true;
        loadList();
    }

    if (shouldLoadNow()) {
        ensureLoaded();
    } else if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    ensureLoaded();
                    io.disconnect();
                }
            });
        }, { rootMargin: '120px' });
        io.observe(root);
    } else {
        ensureLoaded();
    }

    window.addEventListener('hashchange', function () {
        if (location.hash === '#ecc-users' || location.hash === '#ecc-users-mgmt') ensureLoaded();
    });
})();
