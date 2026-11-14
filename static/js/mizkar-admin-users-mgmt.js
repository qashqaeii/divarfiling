/**
 * مدیریت کاربران — جدول AJAX + اسکرول بی‌نهایت
 */
(function () {
    'use strict';

    const root = document.getElementById('ecc-users-mgmt');
    if (!root) return;

    const listUrl = root.getAttribute('data-users-list-url');
    const detailTemplate = root.getAttribute('data-users-detail-url-template') || '';
    const profileTemplate = root.getAttribute('data-users-profile-url-template') || '';
    const bodyEl = document.getElementById('eccUsersMgmtBody');
    const scrollWrap = root.querySelector('.adm-users-mgmt-table-wrap')
        || root.querySelector('.adm-table-wrap');
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
    const PAGE_SIZE = 40;

    let page = 1;
    let totalCount = 0;
    let loadedCount = 0;
    let hasMore = false;
    let listLoading = false;
    let searchTimer = null;
    let abortList = null;
    let listRequestId = 0;
    let sentinelObserver = null;

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

    function userInitial(name) {
        const s = String(name || '').trim();
        if (!s) return '؟';
        return s.charAt(0);
    }

    function statusChip(tone, text) {
        return '<span class="adm-um-status adm-um-status--' + tone + '">' + esc(text) + '</span>';
    }

    function emptyDash() {
        return '<span class="adm-um-empty" aria-hidden="true">—</span>';
    }

    function metricCell(primaryHtml, secondaryText) {
        if (!primaryHtml) return emptyDash();
        const sub = secondaryText
            ? '<small class="adm-um-meta">' + esc(secondaryText) + '</small>'
            : '';
        return '<div class="adm-um-metric">' + primaryHtml + sub + '</div>';
    }

    function windowsCell(w) {
        const steps = [
            { ok: w.downloaded, label: 'دانلود' },
            { ok: w.activated, label: 'فعال' },
            { ok: w.first_launch, label: 'اجرا' },
        ];
        const dots = steps.map(function (step) {
            const cls = 'adm-um-win-dot' + (step.ok ? ' is-on' : '');
            return '<span class="' + cls + '" title="' + esc(step.label + (step.ok ? ' ✓' : '')) + '"></span>';
        }).join('');
        const done = steps.filter(function (s) { return s.ok; }).length;
        return (
            '<div class="adm-um-win" role="img" aria-label="ویندوز · ' + toFa(done) + ' از ۳">'
            + '<div class="adm-um-win-track">' + dots + '</div>'
            + '<span class="adm-um-win-legend">' + toFa(done) + '/۳</span>'
            + '</div>'
        );
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

    function activeFilterCount() {
        let n = Object.keys(currentFilters()).length;
        if (searchEl && searchEl.value.trim()) {
            n += 1;
        }
        return n;
    }

    function updateFilterActions() {
        if (resetBtn) resetBtn.hidden = !hasFilters();
        const countEl = document.getElementById('eccUsersMgmtFilterCount');
        if (countEl) {
            const n = activeFilterCount();
            countEl.hidden = n <= 0;
            countEl.textContent = n > 0 ? toFa(n) : '';
        }
    }

    function showListStatus(message) {
        if (statusEl) statusEl.textContent = message;
    }

    function updateLoadStatus() {
        if (!totalCount && !loadedCount) {
            return;
        }
        if (loadedCount >= totalCount) {
            showListStatus(
                'نمایش ' + toFa(loadedCount) + ' از ' + toFa(totalCount) + ' کاربر'
                + (hasFilters() ? ' (فیلترشده)' : '')
            );
            return;
        }
        showListStatus(
            'نمایش ' + toFa(loadedCount) + ' از ' + toFa(totalCount) + ' · اسکرول برای ادامه'
        );
    }

    function resetFilters() {
        clearTimeout(searchTimer);
        if (searchEl) searchEl.value = '';
        Object.keys(filterIds).forEach(function (key) {
            const el = document.getElementById(filterIds[key]);
            if (el) el.value = '';
        });
        updateFilterActions();
        loadList();
    }

    function buildListQuery() {
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('page_size', String(PAGE_SIZE));
        params.set('sort', '-date_joined');
        const q = (searchEl && searchEl.value || '').trim();
        if (q) params.set('q', q);
        const filters = currentFilters();
        Object.keys(filters).forEach(function (k) {
            params.set(k, filters[k]);
        });
        return params.toString();
    }

    function buildRowHtml(u) {
        let lic;
        if (u.has_active_license) {
            lic = statusChip('ok', u.license_access_label || u.license_plan || 'فعال');
            if (u.license_expires_jalali) {
                lic += '<small class="adm-um-meta">' + esc(u.license_expires_jalali) + '</small>';
            }
        } else if (u.has_pending_bot_activation) {
            lic = statusChip('warn', 'در انتظار فعال‌سازی');
        } else {
            lic = statusChip('muted', 'بدون لایسنس');
        }
        const paid = metricCell(
            u.paid_orders_count ? '<strong class="adm-um-money">' + money(u.total_spent) + '</strong>' : '',
            u.paid_orders_count ? toFa(u.paid_orders_count) + ' سفارش' : ''
        );
        const android = u.android.installed
            ? statusChip('ok', toFa(u.android.devices_count) + ' دستگاه')
            : emptyDash();
        const ds = metricCell(
            u.datasets_count ? '<strong class="adm-um-count">' + toFa(u.datasets_count) + '</strong>' : '',
            u.datasets_count ? toFa(u.listings_total) + ' آگهی' : ''
        );
        const crm = metricCell(
            u.crm_contacts_count ? '<strong class="adm-um-count">' + toFa(u.crm_contacts_count) + '</strong>' : '',
            u.crm_contacts_count ? toFa(u.crm_deals_count) + ' معامله' : ''
        );
        const href = profileUrl(u.id);
        const initial = esc(userInitial(u.name));
        const userCell = href
            ? '<a class="ecc-users-mgmt-user-link adm-user-360-link adm-user-360-link--profile adm-users-mgmt-user__link" href="' + esc(href) + '">'
              + '<span class="adm-users-mgmt-user__avatar" aria-hidden="true">' + initial + '</span>'
              + '<span class="adm-user-360-link__text"><strong>' + esc(u.name) + '</strong>'
              + '<small class="adm-users-mgmt-user__sub">' + esc(u.phone || u.email || '—') + '</small></span>'
              + '<i class="fas fa-arrow-left adm-user-360-link__goto" aria-hidden="true"></i></a>'
            : '<div class="adm-users-mgmt-user__plain"><span class="adm-users-mgmt-user__avatar" aria-hidden="true">' + initial + '</span>'
              + '<span><strong>' + esc(u.name) + '</strong><small class="adm-users-mgmt-user__sub">' + esc(u.phone || u.email || '—') + '</small></span></div>';
        const rowHref = href ? ' data-u360-href="' + esc(href) + '"' : '';
        const rowLabel = 'پرونده · ' + (u.name || u.phone || u.email || ('کاربر ' + u.id));
        return (
            '<tr data-user-id="' + u.id + '" class="adm-users-row--profile" tabindex="0"'
            + ' aria-label="' + esc(rowLabel) + '"' + rowHref + '>'
            + '<td class="ecc-users-mgmt-user adm-um-col-user">' + userCell + '</td>'
            + '<td class="adm-um-col-license">' + lic + '</td>'
            + '<td class="adm-um-col-paid">' + paid + '</td>'
            + '<td class="adm-um-col-windows">' + windowsCell(u.windows) + '</td>'
            + '<td class="adm-um-col-android">' + android + '</td>'
            + '<td class="adm-um-col-dataset">' + ds + '</td>'
            + '<td class="adm-um-col-crm">' + crm + '</td>'
            + '<td class="adm-um-col-login adm-users-mgmt-table__date">' + esc(u.last_login_jalali) + '</td>'
            + '</tr>'
        );
    }

    function renderEmptyState() {
        const reset = hasFilters()
            ? '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-reset-users-filter>پاک‌کردن فیلترها</button>'
            : '';
        bodyEl.innerHTML = '<tr class="adm-users-mgmt-empty-row"><td colspan="8" class="adm-empty adm-users-mgmt-empty">'
            + '<span class="adm-users-mgmt-empty__text">'
            + (hasFilters() ? 'کاربری با این جستجو یا فیلتر یافت نشد' : 'هنوز کاربری ثبت نشده است')
            + '</span> ' + reset + '</td></tr>';
        disconnectSentinelObserver();
    }

    function removeSentinel() {
        const row = bodyEl.querySelector('tr.adm-users-mgmt-scroll-sentinel');
        if (row) row.remove();
    }

    function setSentinelLoading(isLoading) {
        let row = bodyEl.querySelector('tr.adm-users-mgmt-scroll-sentinel');
        if (!row) {
            bodyEl.insertAdjacentHTML(
                'beforeend',
                '<tr class="adm-users-mgmt-scroll-sentinel" aria-busy="true">'
                + '<td colspan="8" class="adm-users-mgmt-scroll-sentinel__cell"></td></tr>'
            );
            row = bodyEl.querySelector('tr.adm-users-mgmt-scroll-sentinel');
        }
        const cell = row && row.querySelector('td');
        if (cell) {
            cell.textContent = isLoading ? 'در حال بارگذاری…' : '';
            cell.classList.toggle('is-loading', !!isLoading);
        }
        bindSentinelObserver();
    }

    function disconnectSentinelObserver() {
        if (sentinelObserver) {
            sentinelObserver.disconnect();
            sentinelObserver = null;
        }
        removeSentinel();
    }

    function bindSentinelObserver() {
        if (!scrollWrap || !('IntersectionObserver' in window)) {
            return;
        }
        const sentinel = bodyEl.querySelector('tr.adm-users-mgmt-scroll-sentinel');
        if (!sentinel || !hasMore) {
            return;
        }
        if (sentinelObserver) sentinelObserver.disconnect();
        sentinelObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    loadMore();
                }
            });
        }, {
            root: scrollWrap,
            rootMargin: '80px 0px 120px 0px',
            threshold: 0,
        });
        sentinelObserver.observe(sentinel);
    }

    function applyListData(data, append) {
        const results = data.results || [];
        totalCount = Number(data.total) || 0;
        hasMore = !!data.has_next;
        page = data.page || page;

        if (!append) {
            loadedCount = 0;
            if (!results.length) {
                renderEmptyState();
                showListStatus(hasFilters() ? 'نتیجه‌ای یافت نشد' : 'کاربری ثبت نشده است');
                hasMore = false;
                return;
            }
            bodyEl.innerHTML = results.map(buildRowHtml).join('');
            loadedCount = results.length;
        } else {
            removeSentinel();
            if (results.length) {
                bodyEl.insertAdjacentHTML('beforeend', results.map(buildRowHtml).join(''));
                loadedCount += results.length;
            }
        }

        if (hasMore) {
            setSentinelLoading(false);
        } else {
            disconnectSentinelObserver();
        }
        updateLoadStatus();
    }

    function fetchPage(append) {
        if (!listUrl || !bodyEl || listLoading) return;
        if (append && !hasMore) return;

        if (abortList) abortList.abort();
        const requestId = ++listRequestId;
        abortList = new AbortController();
        listLoading = true;
        updateFilterActions();

        if (!append) {
            showListStatus('در حال دریافت کاربران…');
            bodyEl.innerHTML = '<tr><td colspan="8" class="adm-empty">در حال بارگذاری…</td></tr>';
            disconnectSentinelObserver();
        } else {
            setSentinelLoading(true);
        }

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
                applyListData(data, append);
            })
            .catch(function (err) {
                if (requestId !== listRequestId || err.name === 'AbortError') return;
                if (!append) {
                    showListStatus('دریافت فهرست کاربران ناموفق بود؛ دوباره تلاش کنید.');
                    bodyEl.innerHTML = '<tr><td colspan="8" class="adm-empty">'
                        + 'ارتباط با سرور برقرار نشد. '
                        + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-retry-users-list>تلاش مجدد</button>'
                        + '</td></tr>';
                    disconnectSentinelObserver();
                } else {
                    page = Math.max(1, page - 1);
                    setSentinelLoading(false);
                    showListStatus('بارگذاری ادامه فهرست ناموفق بود؛ دوباره اسکرول کنید.');
                }
            })
            .finally(function () {
                if (requestId === listRequestId) {
                    listLoading = false;
                    if (hasMore && bodyEl.querySelector('tr.adm-users-row--profile')) {
                        setSentinelLoading(false);
                    }
                }
            });
    }

    function loadList() {
        page = 1;
        hasMore = false;
        loadedCount = 0;
        fetchPage(false);
    }

    function loadMore() {
        if (!hasMore || listLoading) return;
        page += 1;
        fetchPage(true);
    }

    function onScrollFallback() {
        if (!scrollWrap || !hasMore || listLoading) return;
        if (scrollWrap.scrollTop + scrollWrap.clientHeight >= scrollWrap.scrollHeight - 64) {
            loadMore();
        }
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

    if (resetBtn) resetBtn.addEventListener('click', resetFilters);

    if (searchEl) {
        searchEl.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () {
                loadList();
            }, 320);
        });
    }

    Object.keys(filterIds).forEach(function (key) {
        const el = document.getElementById(filterIds[key]);
        if (!el) return;
        el.addEventListener('change', function () {
            clearTimeout(searchTimer);
            loadList();
        });
    });

    if (scrollWrap) {
        let scrollTick = false;
        scrollWrap.addEventListener('scroll', function () {
            if (scrollTick) return;
            scrollTick = true;
            window.requestAnimationFrame(function () {
                scrollTick = false;
                onScrollFallback();
            });
        }, { passive: true });
    }

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