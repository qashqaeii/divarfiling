/**
 * مدیریت کاربران — جدول AJAX + پنل جزئیات
 */
(function () {
    'use strict';

    const root = document.getElementById('ecc-users-mgmt');
    if (!root) return;

    const listUrl = root.getAttribute('data-users-list-url');
    const detailTemplate = root.getAttribute('data-users-detail-url-template') || '';
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

    const drawer = document.getElementById('eccUserDrawer');
    const drawerBody = document.getElementById('eccUserDrawerBody');
    const drawerTitle = document.getElementById('eccUserDrawerTitle');
    const drawerSub = document.getElementById('eccUserDrawerSub');

    const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    let page = 1;
    let totalPages = 1;
    let searchTimer = null;
    let abortList = null;
    let abortDetail = null;
    let listRequestId = 0;
    let detailRequestId = 0;
    let drawerReturnFocus = null;
    let previousBodyOverflow = '';

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
            return (
                '<tr data-user-id="' + u.id + '" tabindex="0">' +
                '<td class="ecc-users-mgmt-user"><strong>' + esc(u.name) + '</strong><small>' + esc(u.phone || u.email || '—') + '</small></td>' +
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

    function miniTable(headers, rowsHtml) {
        if (!rowsHtml) {
            return '<p class="adm-empty" style="margin:0">موردی نیست</p>';
        }
        return (
            '<div class="adm-table-wrap"><table class="adm-table adm-table--pro adm-table--compact"><thead><tr>' +
            headers.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join('') +
            '</tr></thead><tbody>' + rowsHtml + '</tbody></table></div>'
        );
    }

    function renderDetail(u) {
        const usage = u.usage || {};
        const kpis = [
            ['لایسنس', u.has_active_license ? (u.license_access_label || u.license_plan || 'فعال') : (u.has_pending_bot_activation ? 'در انتظار فعال‌سازی' : 'ندارد')],
            ['مجموع پرداخت', money(u.total_spent) + ' تومان'],
            ['دیتاست / آگهی', toFa(usage.datasets || 0) + ' / ' + toFa(usage.listings || 0)],
            ['CRM مخاطب', toFa(usage.crm_contacts || 0)],
            ['معامله باز', toFa(usage.crm_deals_open || 0)],
            ['روز از عضویت', toFa(usage.days_since_join || 0)],
        ].map(function (pair) {
            return '<div class="ecc-ud-kpi"><span>' + esc(pair[0]) + '</span><strong>' + esc(pair[1]) + '</strong></div>';
        }).join('');

        const licenseRows = (u.licenses || []).map(function (l) {
            return '<tr><td>' + esc(l.plan) + '<small style="display:block">' + esc(l.key_masked) + '</small></td>'
                + '<td><span class="ecc-um-flag ' + (l.is_valid ? 'ecc-um-flag--ok' : 'ecc-um-flag--off') + '">'
                + esc(l.status_label) + '</span></td>'
                + '<td>' + toFa(l.slots_used) + '/' + toFa(l.max_activations) + '</td>'
                + '<td>' + esc(l.expires_jalali) + '</td></tr>';
        }).join('');

        const orderRows = (u.orders || []).map(function (o) {
            return '<tr><td>' + esc(o.product) + '<small style="display:block">' + esc(o.plan) + '</small></td>'
                + '<td>' + money(o.amount) + '</td>'
                + '<td>' + esc(o.status_label) + '</td>'
                + '<td>' + esc(o.created_jalali) + '</td></tr>';
        }).join('');

        const actRows = (u.activations || []).map(function (a) {
            return '<tr><td>' + esc(a.platform_label) + '</td><td>' + esc(a.label) + '</td>'
                + '<td>' + (a.is_active ? 'فعال' : 'غیرفعال') + '</td>'
                + '<td>' + esc(a.activated_jalali) + '</td></tr>';
        }).join('');

        const dsRows = (u.datasets || []).map(function (d) {
            return '<tr><td>' + esc(d.name) + '</td><td>' + toFa(d.row_count) + '</td>'
                + '<td>' + esc(d.city) + '</td><td>' + esc(d.created_jalali) + '</td></tr>';
        }).join('');

        const deviceRows = (u.android_devices || []).map(function (d) {
            return '<tr><td>' + esc(d.device_model) + '</td><td>' + esc(d.app_version) + '</td>'
                + '<td>' + esc(d.last_seen_jalali) + '</td></tr>';
        }).join('');

        const crmChips = (u.crm_status_breakdown || []).map(function (s) {
            return '<span class="ecc-ud-chip">' + esc(s.status) + ': ' + toFa(s.count) + '</span>';
        }).join('') || '<span class="ecc-um-flag ecc-um-flag--off">بدون مخاطب</span>';

        const win = u.windows || {};
        const andr = u.android || {};

        drawerTitle.textContent = u.name || 'کاربر';
        drawerSub.textContent = (u.phone || u.email || '')
            + (u.date_joined_jalali ? ' — عضویت ' + u.date_joined_jalali : '');

        drawerBody.innerHTML =
            '<div class="ecc-ud-kpis">' + kpis + '</div>' +
            '<div class="ecc-ud-section"><h3>وضعیت اپ</h3>'
            + '<div class="ecc-users-mgmt-flags" style="margin-bottom:.5rem">'
            + flag(win.downloaded, 'دانلود ویندوز', 'بدون دانلود ویندوز')
            + flag(win.activated, 'فعال‌سازی ویندوز', 'بدون فعال‌سازی ویندوز')
            + flag(win.first_launch, 'اجرای ویندوز', 'بدون اجرای ویندوز')
            + flag(andr.installed, 'اپ اندروید', 'بدون اندروید')
            + '</div></div>' +
            '<div class="ecc-ud-section"><h3>لایسنس‌ها</h3>'
            + miniTable(['پلن', 'وضعیت', 'اسلات', 'انقضا'], licenseRows) + '</div>' +
            '<div class="ecc-ud-section"><h3>سفارش‌ها</h3>'
            + miniTable(['محصول', 'مبلغ', 'وضعیت', 'تاریخ'], orderRows) + '</div>' +
            '<div class="ecc-ud-section"><h3>فعال‌سازی دستگاه</h3>'
            + miniTable(['پلتفرم', 'نام', 'وضعیت', 'تاریخ'], actRows) + '</div>' +
            '<div class="ecc-ud-section"><h3>دستگاه‌های اندروید</h3>'
            + miniTable(['مدل', 'نسخه', 'آخرین بازدید'], deviceRows) + '</div>' +
            '<div class="ecc-ud-section"><h3>دیتاست‌ها</h3>'
            + miniTable(['نام', 'آگهی', 'شهر', 'تاریخ'], dsRows) + '</div>' +
            '<div class="ecc-ud-section"><h3>وضعیت CRM</h3>'
            + '<div class="ecc-ud-chips">' + crmChips + '</div></div>';
    }

    function openDrawer() {
        if (!drawer) return;
        if (drawer.hidden) {
            previousBodyOverflow = document.body.style.overflow;
        }
        drawer.hidden = false;
        drawer.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        const closeBtn = drawer.querySelector('.ecc-user-drawer-close');
        if (closeBtn) closeBtn.focus();
    }

    function closeDrawer() {
        if (!drawer || drawer.hidden) return;
        detailRequestId++;
        if (abortDetail) abortDetail.abort();
        drawer.hidden = true;
        drawer.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = previousBodyOverflow;
        if (bodyEl) {
            bodyEl.querySelectorAll('tr.is-selected').forEach(function (tr) {
                tr.classList.remove('is-selected');
            });
        }
        if (drawerReturnFocus && drawerReturnFocus.isConnected) {
            drawerReturnFocus.focus();
        } else if (searchEl) {
            searchEl.focus();
        }
        drawerReturnFocus = null;
    }

    function loadDetail(userId) {
        if (!drawerBody) return;
        if (!drawer || drawer.hidden) {
            drawerReturnFocus = drawerReturnFocus || document.activeElement;
        }
        openDrawer();
        drawerTitle.textContent = 'جزئیات کاربر';
        drawerSub.textContent = '';
        drawerBody.innerHTML = '<p class="adm-empty">در حال بارگذاری…</p>';

        if (abortDetail) abortDetail.abort();
        const requestId = ++detailRequestId;
        abortDetail = new AbortController();

        fetch(detailUrl(userId), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
            signal: abortDetail.signal,
        })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                if (requestId !== detailRequestId || drawer.hidden) return;
                if (!data.ok || !data.user) throw new Error('invalid');
                renderDetail(data.user);
            })
            .catch(function (err) {
                if (requestId !== detailRequestId || err.name === 'AbortError' || drawer.hidden) return;
                drawerBody.innerHTML = '<p class="adm-empty">دریافت جزئیات انجام نشد. '
                    + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-retry-user-detail="' + esc(userId) + '">'
                    + 'تلاش مجدد</button></p>';
            });
    }

    bodyEl.addEventListener('click', function (e) {
        if (e.target.closest('[data-retry-users-list]')) {
            loadList();
            return;
        }
        if (e.target.closest('[data-reset-users-filter]')) {
            resetFilters();
            return;
        }
        const tr = e.target.closest('tr[data-user-id]');
        if (!tr) return;
        bodyEl.querySelectorAll('tr.is-selected').forEach(function (r) {
            r.classList.remove('is-selected');
        });
        tr.classList.add('is-selected');
        drawerReturnFocus = tr;
        loadDetail(tr.getAttribute('data-user-id'));
    });

    bodyEl.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const tr = e.target.closest('tr[data-user-id]');
        if (!tr) return;
        e.preventDefault();
        tr.click();
    });

    if (drawer) {
        if (drawerBody) {
            drawerBody.addEventListener('click', function (e) {
                const button = e.target.closest('[data-retry-user-detail]');
                if (button) loadDetail(button.getAttribute('data-retry-user-detail'));
            });
        }
        drawer.querySelectorAll('[data-user-drawer-close]').forEach(function (el) {
            el.addEventListener('click', closeDrawer);
        });
        document.addEventListener('keydown', function (e) {
            if (drawer.hidden) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                closeDrawer();
                return;
            }
            if (e.key !== 'Tab') return;
            const focusables = Array.from(drawer.querySelectorAll(
                '.ecc-user-drawer-panel a[href], .ecc-user-drawer-panel button:not([disabled]),'
                + ' .ecc-user-drawer-panel input:not([disabled]),'
                + ' .ecc-user-drawer-panel [tabindex="0"]'
            )).filter(function (el) { return el.getClientRects().length > 0; });
            if (!focusables.length) return;
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }

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
