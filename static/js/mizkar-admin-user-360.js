/**
 * پرونده ۳۶۰ مشتری — تب‌ها، رندر پریمیوم، RTL
 */
(function () {
    'use strict';

    const root = document.getElementById('adm-u360-root');
    if (!root) return;

    const panel = document.getElementById('admU360Panel');
    const tabsNav = document.getElementById('admU360Tabs');
    const tabsWrap = document.getElementById('admU360TabsWrap');
    const kpisEl = document.getElementById('admU360Kpis');
    const kpisWrap = document.getElementById('admU360KpisWrap');
    const userId = root.getAttribute('data-user-id');
    let activeTab = root.getAttribute('data-active-tab') || 'overview';
    let bootstrap = {};
    try {
        const el = document.getElementById('adm-u360-bootstrap');
        bootstrap = el ? JSON.parse(el.textContent || '{}') : {};
    } catch (e) {
        bootstrap = {};
    }

    const PERSIAN = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  const CHART_PALETTE = [
        'rgba(91, 79, 207, 0.78)',
        'rgba(16, 185, 129, 0.72)',
        'rgba(245, 158, 11, 0.72)',
        'rgba(56, 189, 248, 0.7)',
        'rgba(244, 63, 94, 0.68)',
        'rgba(148, 163, 184, 0.75)',
    ];
    const tabCache = {};
    const chartInstances = {};
    const tabQueryState = {};
    let activeRequest = null;
    let requestVersion = 0;
    const U360_BUILD = 58;
    let supportDeskSelectedId = null;
    let adminLogScrollState = { pagination: null, loaded: 0, loading: false };
    let adminLogScrollObserver = null;
    let adminLogScrollEl = null;
    let bustUsageTabCache = false;
    if (sessionStorage.getItem('adm_u360_build') !== String(U360_BUILD)) {
        sessionStorage.setItem('adm_u360_build', String(U360_BUILD));
        bustUsageTabCache = true;
    }

    function panelRangeDaysParam() {
        return new URLSearchParams(window.location.search).get('days') || 'all';
    }

    function mergePanelRangeQuery(query) {
        const q = Object.assign({}, query || {});
        const days = panelRangeDaysParam();
        if (days && !q.days) {
            q.days = days;
        }
        return q;
    }

    if (bootstrap.overview_embedded) {
        tabCache['overview' + JSON.stringify(mergePanelRangeQuery({}))] = bootstrap.overview_embedded;
    }

    function toFa(v) {
        return String(v == null ? '' : v).replace(/\d/g, function (d) {
            return PERSIAN[parseInt(d, 10)];
        });
    }

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function money(n) {
        return toFa(Number(n || 0).toLocaleString('en-US'));
    }

    function moneyTomans(n) {
        return '<span class="adm-u360-amount">' + money(n) + '</span> <span class="adm-u360-kpi__unit">تومان</span>';
    }

    function formatAxisTomans(value) {
        const n = Number(value) || 0;
        if (n === 0) return toFa(0);
        const abs = Math.abs(n);
        if (abs >= 1000000000) {
            return toFa((n / 1000000000).toFixed(abs >= 10000000000 ? 0 : 1)) + 'B';
        }
        if (abs >= 1000000) {
            const m = n / 1000000;
            if (m < 10) {
                const fixed = m.toFixed(2).replace(/\.?0+$/, '');
                return toFa(fixed) + 'M';
            }
            return toFa((m).toFixed(abs >= 10000000 ? 0 : 1)) + 'M';
        }
        if (abs >= 1000) {
            return toFa(Math.round(n / 1000)) + 'K';
        }
        return toFa(n);
    }

    function tabUrl(tab, query) {
        let url = '/accounts/admin-panel/users/' + userId + '/' + tab + '.json';
        if (query) {
            if (typeof query === 'string') url += (query.startsWith('?') ? query : '?' + query);
            else url += '?' + new URLSearchParams(query).toString();
        }
        return url;
    }

    function csrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el && el.value) return el.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function supportTicketDetailUrl(ticketId, query) {
        let url = '/accounts/admin-panel/users/' + userId + '/support/tickets/' + ticketId + '.json';
        if (query) {
            url += '?' + new URLSearchParams(query).toString();
        }
        return url;
    }

    function licenseActionUrl(licenseId) {
        return '/accounts/admin-panel/users/' + userId + '/licenses/' + licenseId + '/action/';
    }

    function bustLicensesTabCache() {
        Object.keys(tabCache).forEach(function (key) {
            if (key.indexOf('licenses') === 0) delete tabCache[key];
        });
    }

    function supportTicketActionUrl(ticketId) {
        return '/accounts/admin-panel/users/' + userId + '/support/tickets/' + ticketId + '/action/';
    }

    function setTabInUrl(tab) {
        const u = new URL(window.location.href);
        u.searchParams.set('tab', tab);
        window.history.replaceState({}, '', u.toString());
    }

    function tabIcon(tabKey) {
        const tabs = bootstrap.tabs || [];
        for (let i = 0; i < tabs.length; i++) {
            if (tabs[i].key === tabKey) {
                return tabs[i].icon || 'fa-circle';
            }
        }
        return 'fa-circle';
    }

    function sectionHeading(title, icon) {
        const ic = icon || 'fa-layer-group';
        return '<h2 class="adm-u360-section-title">'
            + '<span class="adm-u360-section-title__icon" aria-hidden="true"><i class="fas ' + ic + '"></i></span>'
            + '<span class="adm-u360-section-title__text">' + esc(title) + '</span></h2>';
    }

    function block(title, inner, icon, modClass) {
        const mod = modClass ? ' ' + modClass : '';
        return '<section class="adm-u360-block' + mod + '">' + sectionHeading(title, icon)
            + '<div class="adm-u360-block__body">' + inner + '</div></section>';
    }

    function subTitle(title, icon) {
        const ic = icon
            ? '<span class="adm-u360-subtitle__icon" aria-hidden="true"><i class="fas ' + icon + '"></i></span>'
            : '';
        return '<h3 class="adm-u360-subtitle">' + ic + '<span class="adm-u360-subtitle__text">' + esc(title) + '</span></h3>';
    }

    function subSection(title, inner, icon) {
        return '<div class="adm-u360-subsection adm-u360-data-card">'
            + subTitle(title, icon)
            + '<div class="adm-u360-data-card__body">' + inner + '</div></div>';
    }

    /** چینش یکپارچه تب: شاخص → ابزار → نمودار → داده */
    function tabLayout(zones, layoutClass) {
        zones = zones || {};
        const layoutMod = layoutClass ? ' ' + layoutClass : '';
        let html = '<div class="adm-u360-tab-layout' + layoutMod + '">';
        const band = [];
        if (zones.metrics) {
            band.push('<div class="adm-u360-tab-layout__metrics">' + zones.metrics + '</div>');
        }
        if (zones.toolbar) {
            band.push(zones.toolbar);
        }
        if (zones.lead) {
            band.push(zones.lead);
        }
        if (band.length) {
            html += '<div class="adm-u360-tab-layout__band">' + band.join('') + '</div>';
        }
        if (zones.viz) {
            html += '<div class="adm-u360-tab-layout__viz">' + zones.viz + '</div>';
        }
        if (zones.content) {
            html += '<div class="adm-u360-tab-layout__content">' + zones.content + '</div>';
        }
        html += '</div>';
        return html;
    }

    function tabPanel(title, icon, zones) {
        return block(title, tabLayout(zones), icon);
    }

    function lead(html) {
        return '<p class="adm-u360-lead">' + html + '</p>';
    }

    function emptyState(title, hint, icon) {
        const ic = icon || 'fa-layer-group';
        return '<div class="adm-u360-empty-state">'
            + '<span class="adm-u360-empty-state__icon" aria-hidden="true"><i class="fas ' + ic + '"></i></span>'
            + '<p class="adm-u360-empty-state__title">' + esc(title || 'موردی نیست') + '</p>'
            + (hint ? '<p class="adm-u360-empty-state__hint">' + esc(hint) + '</p>' : '')
            + '</div>';
    }

    function statStrip(cells, extraClass) {
        if (!cells || !cells.length) return '';
        const stripClass = 'adm-u360-stat-strip' + (extraClass ? ' ' + extraClass : '');
        return '<div class="' + stripClass + '" role="list">'
            + cells.filter(function (c) { return c && c.label && c.value !== undefined && c.value !== null; }).map(function (c, i) {
                const tone = c.tone ? ' adm-u360-stat--' + c.tone : '';
                const primary = c.primary ? ' adm-u360-stat--primary' : '';
                const keyMod = c.key ? ' adm-u360-stat--key-' + c.key : '';
                const tag = c.tab ? 'button' : 'div';
                const btnAttrs = c.tab
                    ? ' type="button" data-u360-tab-jump="' + esc(c.tab) + '"'
                    : '';
                const aria = c.tab
                    ? ' aria-label="' + esc(c.label) + ' — رفتن به بخش مرتبط"'
                    : '';
                const glyph = c.icon
                    ? '<span class="adm-u360-stat__glyph" aria-hidden="true"><i class="fas ' + c.icon + '"></i></span>'
                    : '';
                const goto = c.tab
                    ? '<i class="fas fa-chevron-left adm-u360-stat__goto" aria-hidden="true"></i>'
                    : '';
                return '<' + tag + ' class="adm-u360-stat' + tone + primary + keyMod + '"' + btnAttrs
                    + ' role="listitem" style="--u360-stat-i:' + i + '"' + aria + '>'
                    + glyph
                    + '<span class="adm-u360-stat__stack">'
                    + '<span class="adm-u360-stat__label">' + esc(c.label) + '</span>'
                    + '<span class="adm-u360-stat__body">'
                    + '<span class="adm-u360-stat__value">' + c.value + '</span>'
                    + goto
                    + '</span></span>'
                    + '</' + tag + '>';
            }).join('')
            + '</div>';
    }

    function panelRangeHint() {
        const days = panelRangeDaysParam();
        const range = days === 'all' ? 'کل دوره' : toFa(days) + ' روز';
        return '<div class="adm-u360-toolbar adm-u360-toolbar--hint">'
            + '<p class="adm-u360-toolbar__note"><i class="fas fa-sliders" aria-hidden="true"></i>'
            + ' بازه انتخابی · <strong>' + range + '</strong> · برخی اطلاعات هویتی و وضعیت‌های جاری مستقل از بازه‌اند.</p></div>';
    }

    function miniTable(headers, rowsHtml, extraClass) {
        if (!rowsHtml) {
            return emptyState('موردی برای نمایش نیست', 'با تغییر بازه یا فیلترها دوباره بررسی کنید.');
        }
        const cls = extraClass ? ' ' + extraClass : '';
        return (
            '<div class="adm-u360-table-wrap adm-u360-data-table' + cls + '"><table class="adm-table adm-table--pro adm-table--compact"><thead><tr>'
            + headers.map(function (h) { return '<th scope="col">' + esc(h) + '</th>'; }).join('')
            + '</tr></thead><tbody>' + rowsHtml + '</tbody></table></div>'
        );
    }

    function td(content, label) {
        return '<td data-label="' + esc(label) + '">' + content + '</td>';
    }

    function smsMessageTd(row) {
        const messageText = (row.message_body || '').trim();
        const preview = row.message_preview || '—';
        const excerptSrc = messageText || preview;
        const excerpt = excerptSrc.length > 52 ? excerptSrc.slice(0, 52) + '…' : excerptSrc;
        const detail = row.message_detail || '';
        let inner = '';
        if (messageText) {
            inner += '<div class="adm-u360-sms-popover__block">'
                + '<p class="adm-u360-sms-popover__label">متن پیام</p>'
                + '<div class="adm-u360-sms-popover__body">' + esc(messageText).replace(/\n/g, '<br>') + '</div>'
                + '</div>';
        }
        if (detail) {
            const meta = detail.split('\n').map(function (line) { return esc(line); }).join('<br>');
            if (meta) {
                inner += '<div class="adm-u360-sms-popover__block adm-u360-sms-popover__block--meta">'
                    + '<p class="adm-u360-sms-popover__label">جزئیات فنی</p>'
                    + '<div class="adm-u360-sms-popover__meta">' + meta + '</div>'
                    + '</div>';
            }
        }
        if (!inner) {
            inner = '<div class="adm-u360-sms-popover__inner">' + esc(preview) + '</div>';
        }
        return '<td data-label="متن پیام"><div class="adm-u360-sms-cell">'
            + '<span class="adm-u360-sms-cell__excerpt">' + esc(excerpt) + '</span>'
            + '<button type="button" class="adm-u360-sms-info" aria-label="نمایش متن پیامک" aria-expanded="false">'
            + '<i class="fas fa-circle-info" aria-hidden="true"></i></button>'
            + '<div class="adm-u360-sms-popover" role="dialog" aria-label="متن پیامک" hidden>'
            + '<p class="adm-u360-sms-popover__title">متن و جزئیات پیامک</p>'
            + inner
            + '</div></div></td>';
    }

    const SMS_SHEET_MQ = window.matchMedia('(max-width: 899px)');
    let smsBackdropEl = null;

    function ensureSmsBackdrop() {
        if (smsBackdropEl) {
            return smsBackdropEl;
        }
        smsBackdropEl = document.createElement('button');
        smsBackdropEl.type = 'button';
        smsBackdropEl.className = 'adm-u360-sms-backdrop';
        smsBackdropEl.id = 'admU360SmsBackdrop';
        smsBackdropEl.setAttribute('aria-label', 'بستن جزئیات پیامک');
        smsBackdropEl.hidden = true;
        smsBackdropEl.addEventListener('click', closeAllSmsPopovers);
        document.body.appendChild(smsBackdropEl);
        return smsBackdropEl;
    }

    function restoreSmsPopoverHome(pop) {
        if (!pop || !pop._u360SmsHome || !pop._u360SmsHome.parent) {
            return;
        }
        const home = pop._u360SmsHome;
        if (home.next && home.next.parentNode === home.parent) {
            home.parent.insertBefore(pop, home.next);
        } else {
            home.parent.appendChild(pop);
        }
    }

    function closeAllSmsPopovers() {
        document.querySelectorAll('.adm-u360-sms-popover').forEach(function (el) {
            el.hidden = true;
            el.classList.remove('adm-u360-sms-popover--sheet');
            restoreSmsPopoverHome(el);
        });
        panel.querySelectorAll('.adm-u360-sms-info').forEach(function (btn) {
            btn.setAttribute('aria-expanded', 'false');
        });
        if (smsBackdropEl) {
            smsBackdropEl.hidden = true;
        }
        document.body.classList.remove('adm-u360-sms-sheet-open');
        panel.classList.remove('is-sms-popover-open');
    }

    function openSmsPopover(btn, pop) {
        const useSheet = SMS_SHEET_MQ.matches;
        if (useSheet) {
            if (!pop._u360SmsHome) {
                pop._u360SmsHome = { parent: pop.parentElement, next: pop.nextSibling };
            }
            document.body.appendChild(pop);
            pop.classList.add('adm-u360-sms-popover--sheet');
            ensureSmsBackdrop().hidden = false;
            document.body.classList.add('adm-u360-sms-sheet-open');
        } else {
            pop.classList.remove('adm-u360-sms-popover--sheet');
        }
        pop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        panel.classList.add('is-sms-popover-open');
    }

    function renderPager(pagination, tab) {
        if (!pagination || pagination.total_pages <= 1) return '';
        return '<div class="adm-u360-pager">'
            + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-u360-page="' + tab + '" data-page="'
            + (pagination.page - 1) + '" ' + (pagination.has_prev ? '' : 'disabled') + '>قبلی</button>'
            + '<span class="adm-u360-pager__info">' + toFa(pagination.page) + ' / ' + toFa(pagination.total_pages) + '</span>'
            + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-u360-page="' + tab + '" data-page="'
            + (pagination.page + 1) + '" ' + (pagination.has_next ? '' : 'disabled') + '>بعدی</button></div>';
    }

    function destroyCharts() {
        Object.keys(chartInstances).forEach(function (id) {
            try {
                chartInstances[id].destroy();
            } catch (e) {
                /* noop */
            }
            delete chartInstances[id];
        });
    }

    function chartOptions(extra) {
        const base = {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 4, right: 6, bottom: 4, left: 6 } },
            plugins: {
                legend: {
                    display: false,
                    rtl: true,
                    labels: {
                        font: { family: 'inherit', size: 10 },
                        boxWidth: 10,
                        padding: 10,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    rtl: true,
                    titleFont: { family: 'inherit' },
                    bodyFont: { family: 'inherit' },
                },
            },
            scales: {},
        };
        const opts = Object.assign(base, extra || {});
        if (opts.scales) {
            Object.keys(opts.scales).forEach(function (axis) {
                if (opts.scales[axis] && opts.scales[axis].ticks) {
                    opts.scales[axis].ticks.maxRotation = 0;
                    opts.scales[axis].ticks.autoSkip = true;
                    opts.scales[axis].ticks.autoSkipPadding = 6;
                }
            });
        }
        return opts;
    }

    function mountChart(id, config) {
        if (typeof Chart === 'undefined') return;
        const canvas = document.getElementById(id);
        if (!canvas) return;
        if (chartInstances[id]) {
            chartInstances[id].destroy();
            delete chartInstances[id];
        }
        chartInstances[id] = new Chart(canvas, config);
        window.requestAnimationFrame(function () {
            if (chartInstances[id]) {
                try {
                    chartInstances[id].resize();
                } catch (e) {
                    /* noop */
                }
            }
        });
    }

    function chartCard(title, canvasId, variant, icon) {
        const v = variant || '';
        return '<section class="adm-u360-chart-card">' + subTitle(title, icon || 'fa-chart-bar')
            + '<div class="adm-u360-chart-wrap ' + v + '"><canvas id="' + canvasId
            + '" role="img" aria-label="' + esc(title) + '"></canvas></div></section>';
    }

    function chartsRow(inner) {
        if (!inner) return '';
        return '<div class="adm-u360-charts-row">' + inner + '</div>';
    }

    function mountBarActivity(chartId, points) {
        if (!points || !points.length) return;
        mountChart(chartId, {
            type: 'bar',
            data: {
                labels: points.map(function (p) { return toFa((p.date || '').slice(5)); }),
                datasets: [{
                    label: 'رویداد',
                    data: points.map(function (p) { return p.count; }),
                    backgroundColor: 'rgba(91, 79, 207, 0.52)',
                    borderRadius: 6,
                    maxBarThickness: 28,
                }],
            },
            options: chartOptions({
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0, font: { family: 'inherit' } } },
                    x: { ticks: { font: { family: 'inherit', size: 10 } } },
                },
            }),
        });
    }

    function mountDoughnut(chartId, rows, valueKey) {
        if (!rows || !rows.length) return;
        const key = valueKey || 'count';
        mountChart(chartId, {
            type: 'doughnut',
            data: {
                labels: rows.map(function (r) { return toFa(r.label || r.key || '—'); }),
                datasets: [{
                    data: rows.map(function (r) { return r[key]; }),
                    backgroundColor: rows.map(function (r, i) { return CHART_PALETTE[i % CHART_PALETTE.length]; }),
                    borderWidth: 0,
                    hoverOffset: 6,
                }],
            },
            options: chartOptions({
                cutout: '62%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: { font: { size: 9 }, boxWidth: 8, padding: 8 },
                    },
                },
            }),
        });
    }

    function mountLineRevenue(chartId, rows) {
        if (!rows || !rows.length) return;
        mountChart(chartId, {
            type: 'line',
            data: {
                labels: rows.map(function (r) { return toFa((r.month || '').slice(2)); }),
                datasets: [{
                    label: 'تومان',
                    data: rows.map(function (r) { return r.total; }),
                    borderColor: 'rgba(91, 79, 207, 0.9)',
                    backgroundColor: 'rgba(91, 79, 207, 0.12)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                }],
            },
            options: chartOptions({
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            font: { family: 'inherit' },
                            callback: function (v) { return toFa(v); },
                        },
                    },
                    x: { ticks: { font: { family: 'inherit', size: 10 } } },
                },
            }),
        });
    }

    function mountOverviewDoughnut(chartId, rows) {
        if (!rows || !rows.length) return;
        const multi = rows.length > 1;
        mountChart(chartId, {
            type: 'doughnut',
            data: {
                labels: rows.map(function (r) { return toFa(orderStatusDisplayLabel(r)); }),
                datasets: [{
                    data: rows.map(function (r) { return r.count; }),
                    backgroundColor: rows.map(function (r, i) { return CHART_PALETTE[i % CHART_PALETTE.length]; }),
                    borderWidth: 0,
                    hoverOffset: multi ? 5 : 2,
                    spacing: multi ? 2 : 0,
                }],
            },
            options: chartOptions({
                cutout: multi ? '68%' : '72%',
                animation: { animateRotate: true, duration: 480 },
                plugins: { legend: { display: false }, tooltip: { bodyFont: { size: 11 }, titleFont: { size: 11 } } },
            }),
        });
    }

    function revenueMonthLabel(row) {
        if (row && row.label) return row.label;
        return toFa((row.month || '').slice(2));
    }

    function mountOverviewRevenueChart(chartId, rows) {
        if (!rows || !rows.length) return;
        const totals = rows.map(function (r) { return Number(r.total) || 0; });
        const maxVal = Math.max.apply(null, totals.concat([0]));
        const ySuggestedMax = maxVal > 0
            ? Math.ceil((maxVal * 1.12) / 100000) * 100000
            : undefined;
        mountChart(chartId, {
            type: 'bar',
            data: {
                labels: rows.map(revenueMonthLabel),
                datasets: [{
                    label: 'درآمد',
                    data: totals,
                    backgroundColor: totals.map(function (v) {
                        if (!v) return 'rgba(148, 163, 184, 0.18)';
                        const alpha = maxVal ? 0.42 + (v / maxVal) * 0.45 : 0.78;
                        return 'rgba(91, 79, 207, ' + alpha.toFixed(2) + ')';
                    }),
                    borderColor: totals.map(function (v) {
                        return v ? 'rgba(91, 79, 207, 0.45)' : 'rgba(148, 163, 184, 0.28)';
                    }),
                    borderWidth: 1,
                    borderRadius: 6,
                    borderSkipped: false,
                    maxBarThickness: 36,
                    categoryPercentage: 0.72,
                    barPercentage: 0.85,
                }],
            },
            options: chartOptions({
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        rtl: true,
                        callbacks: {
                            title: function (items) {
                                const item = items && items[0];
                                return item ? item.label : '';
                            },
                            label: function (ctx) {
                                const row = rows[ctx.dataIndex] || {};
                                const lines = [money(Number(ctx.parsed.y) || 0) + ' تومان'];
                                if (row.orders) {
                                    lines.push(toFa(row.orders) + ' سفارش پرداخت‌شده');
                                }
                                return lines;
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: ySuggestedMax,
                        grace: maxVal ? '4%' : undefined,
                        border: { display: false },
                        grid: { color: 'rgba(148, 163, 184, 0.12)', drawTicks: false },
                        ticks: {
                            maxTicksLimit: 4,
                            padding: 8,
                            font: { family: 'inherit', size: 10 },
                            callback: function (v) { return formatAxisTomans(v); },
                        },
                    },
                    x: {
                        border: { display: false },
                        grid: { display: false },
                        ticks: {
                            font: { family: 'inherit', size: 9 },
                            padding: 6,
                            maxRotation: 0,
                            autoSkip: rows.length > 6,
                        },
                    },
                },
            }),
        });
    }

    function chartRowsSum(rows, key) {
        key = key || 'count';
        return (rows || []).reduce(function (sum, row) { return sum + (Number(row[key]) || 0); }, 0);
    }

    const ORDER_STATUS_FA = {
        pending: 'در انتظار',
        pending_verification: 'در انتظار تایید',
        paid: 'پرداخت‌شده',
        granted: 'هدیه / اعطایی',
        failed: 'ناموفق',
        cancelled: 'لغو',
    };

    const TRANSACTION_STATUS_FA = {
        paid: 'پرداخت شده',
        success: 'پرداخت شده',
        pending: 'در انتظار پرداخت',
        failed: 'ناموفق',
        cancelled: 'لغو شده',
    };

    function transactionStatusDisplayLabel(t) {
        if (t && t.status_label) return t.status_label;
        const key = String((t && t.status) || '').trim().toLowerCase();
        return TRANSACTION_STATUS_FA[key] || ORDER_STATUS_FA[key] || (t && t.status) || '—';
    }

    function orderStatusDisplayLabel(row) {
        if (!row) return '—';
        if (row.label && row.label !== row.key) return row.label;
        const key = row.key || row.label || '';
        return ORDER_STATUS_FA[key] || row.label || key || '—';
    }

    function renderFinanceOrderLegend(rows) {
        if (!rows || !rows.length) return '';
        const total = chartRowsSum(rows, 'count');
        return '<ul class="adm-u360-finance-legend" role="list">'
            + rows.map(function (row, i) {
                const count = Number(row.count) || 0;
                const pct = total ? Math.round((count / total) * 100) : 0;
                const color = CHART_PALETTE[i % CHART_PALETTE.length];
                return '<li class="adm-u360-finance-legend__item" role="listitem">'
                    + '<span class="adm-u360-finance-legend__dot" style="background:' + color + '" aria-hidden="true"></span>'
                    + '<span class="adm-u360-finance-legend__label">' + esc(orderStatusDisplayLabel(row)) + '</span>'
                    + '<span class="adm-u360-finance-legend__count">' + toFa(count) + '</span>'
                    + '<span class="adm-u360-finance-legend__pct">' + toFa(pct) + '٪</span>'
                    + '</li>';
            }).join('')
            + '</ul>';
    }

    function renderOverviewFinanceCard(charts, pay) {
        charts = charts || {};
        pay = pay || {};
        const orders = charts.orders_by_status || [];
        const revenue = charts.revenue_monthly || [];
        const hasChartData = orders.length || revenue.length;

        const orderTotal = chartRowsSum(orders, 'count');
        const revenueSum = chartRowsSum(revenue, 'total');
        const lastMonth = revenue.length ? revenue[revenue.length - 1] : null;

        let panels = '';
        if (!hasChartData) {
            panels += '<div class="adm-u360-finance-panel adm-u360-finance-panel--empty">'
                + emptyState(
                    'جریان مالی برای این بازه ثبت نشده',
                    'با تغییر بازه زمانی یا پس از اولین پرداخت موفق، نمودار و جمع‌ها اینجا نمایش داده می‌شوند.'
                )
                + '</div>';
        }
        if (hasChartData) {
            panels += '<div class="adm-u360-finance-panels">';
        }
        if (orders.length) {
            panels += '<div class="adm-u360-finance-panel adm-u360-finance-panel--mix">'
                + '<div class="adm-u360-finance-panel__head">'
                + '<h3 class="adm-u360-finance-panel__title">ترکیب سفارش‌ها</h3>'
                + '<span class="adm-u360-finance-panel__meta">' + toFa(orderTotal) + ' سفارش</span>'
                + '</div>'
                + '<div class="adm-u360-finance-panel__split">'
                + renderFinanceOrderLegend(orders)
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--donut adm-u360-chart-wrap--finance">'
                + '<canvas id="admU360ChartOrders" role="img" aria-label="ترکیب سفارش‌ها"></canvas></div>'
                + '</div></div>';
        }
        if (revenue.length) {
            panels += '<div class="adm-u360-finance-panel adm-u360-finance-panel--revenue">'
                + '<div class="adm-u360-finance-panel__head">'
                + '<h3 class="adm-u360-finance-panel__title">درآمد پرداخت‌شده</h3>'
                + '<span class="adm-u360-finance-panel__meta">ماه‌های دارای داده در گزارش</span>'
                + '</div>'
                + '<p class="adm-u360-finance-panel__summary">'
                + '<span>جمع دوره <strong>' + moneyTomans(revenueSum) + '</strong></span>'
                + (lastMonth
                    ? '<span class="adm-u360-finance-panel__summary-sep" aria-hidden="true">·</span>'
                        + '<span>آخرین ماه <strong>' + moneyTomans(lastMonth.total) + '</strong></span>'
                    : '')
                + '</p>'
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--wide adm-u360-chart-wrap--finance">'
                + '<canvas id="admU360ChartRevenue" role="img" aria-label="درآمد پرداخت‌شده"></canvas></div>'
                + '</div>';
        }
        if (hasChartData) {
        panels += '</div>';
        }

        const stats = '<dl class="adm-u360-finance-stats">'
            + '<div class="adm-u360-finance-stat"><dt>درآمد پرداخت‌شده</dt><dd>' + moneyTomans(pay.total_paid || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>سفارش پرداخت‌شده</dt><dd>' + toFa(pay.paid_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>در انتظار</dt><dd class="'
            + (pay.pending_orders ? 'adm-u360-finance-stat__val--warn' : '')
            + '">' + toFa(pay.pending_orders || 0) + '</dd></div>'
            + '</dl>';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-finance" aria-label="روند مالی">'
            + '<header class="adm-u360-overview-finance__head">'
            + '<h2 class="adm-u360-overview-finance__title"><span>روند مالی</span></h2>'
            + '</header>'
            + '<div class="adm-u360-overview-finance__body">'
            + stats
            + panels
            + '</div></section>';
    }

    function recentCountBadge(count) {
        if (!count) {
            return '';
        }
        return '<span class="adm-u360-overview-recent__count" title="تعداد در پیش‌نمایش">'
            + toFa(count) + '</span>';
    }

    function renderRecentOrderItem(o) {
        const date = o.paid_jalali && o.paid_jalali !== '—' ? o.paid_jalali : o.created_jalali;
        const planMeta = o.plan && o.plan !== '—'
            ? '<span class="adm-u360-recent-item__plan">' + esc(o.plan) + '</span>'
            : '';
        return '<li class="adm-u360-recent-item adm-u360-recent-item--compact" role="listitem">'
            + '<div class="adm-u360-recent-item__body">'
            + '<div class="adm-u360-recent-item__row">'
            + '<span class="adm-u360-recent-item__title">' + esc(o.product || '—') + '</span>'
            + '<span class="adm-u360-recent-item__amount">' + moneyTomans(o.amount) + '</span>'
            + '</div>'
            + '<div class="adm-u360-recent-item__meta">'
            + (planMeta ? planMeta + '<span class="adm-u360-recent-item__sep" aria-hidden="true">·</span>' : '')
            + orderStatusChip(o.status, o.status_label)
            + '<time class="adm-u360-recent-item__date">' + esc(date || '—') + '</time>'
            + '</div>'
            + '</div></li>';
    }

    function renderRecentLicenseItem(l) {
        const entitled = !!(l.is_valid || l.entitlement_valid);
        return '<li class="adm-u360-recent-item adm-u360-recent-item--license adm-u360-recent-item--compact" role="listitem">'
            + '<div class="adm-u360-recent-item__body">'
            + '<div class="adm-u360-recent-item__row">'
            + '<span class="adm-u360-recent-item__title">' + esc(l.plan || '—') + '</span>'
            + licenseStatusChip(l.status, l.status_label, entitled)
            + '</div>'
            + '<div class="adm-u360-recent-item__meta adm-u360-recent-item__meta--detail">'
            + '<span>انقضا <strong>' + esc(l.expires_jalali || '—') + '</strong></span>'
            + '<span class="adm-u360-recent-item__sep" aria-hidden="true">·</span>'
            + '<span>صدور ' + esc(l.created_jalali || '—') + '</span>'
            + '</div>'
            + '</div></li>';
    }

    function renderRecentList(items, renderItem, emptyIcon, emptyTitle, emptyHint) {
        if (!items || !items.length) {
            return '<div class="adm-u360-recent-list adm-u360-recent-list--empty" role="status">'
                + emptyState(emptyTitle, emptyHint, emptyIcon)
                + '</div>';
        }
        return '<ul class="adm-u360-recent-list" role="list">'
            + items.map(renderItem).join('')
            + '</ul>';
    }

    function renderOverviewRecentCol(title, icon, tab, items, renderItem, emptyIcon, emptyTitle, emptyHint) {
        const list = items || [];
        return '<div class="adm-u360-overview-recent__col">'
            + '<header class="adm-u360-overview-recent__col-head">'
            + subTitle(title, icon)
            + recentCountBadge(list.length)
            + overviewJumpChip('همه', tab, 'fa-arrow-left')
            + '</header>'
            + '<div class="adm-u360-overview-recent__panel">'
            + renderRecentList(list, renderItem, emptyIcon, emptyTitle, emptyHint)
            + '</div></div>';
    }

    function renderOverviewRecentCard(recentOrders, recentLicenses) {
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-recent adm-u360-overview-recent--stack" aria-label="آخرین سفارش‌ها و لایسنس‌ها">'
            + '<header class="adm-u360-overview-recent__head">'
            + '<h2 class="adm-u360-overview-recent__title">'
            + '<i class="fas fa-clock-rotate-left" aria-hidden="true"></i>'
            + '<span>آخرین تراکنش‌ها</span></h2>'
            + '</header>'
            + '<div class="adm-u360-overview-recent__grid">'
            + renderOverviewRecentCol(
                'سفارش‌ها',
                'fa-receipt',
                'commerce',
                recentOrders,
                renderRecentOrderItem,
                'fa-receipt',
                'موردی برای نمایش نیست',
                'با تغییر بازه یا پس از ثبت سفارش، اینجا به‌روز می‌شود.'
            )
            + renderOverviewRecentCol(
                'لایسنس‌ها',
                'fa-key',
                'licenses',
                recentLicenses,
                renderRecentLicenseItem,
                'fa-key',
                'لایسنسی ثبت نشده',
                'پس از خرید یا فعال‌سازی در این بخش نمایش داده می‌شود.'
            )
            + '</div></section>';
    }

    function mountHorizontalBars(chartId, rows) {
        if (!rows || !rows.length) return;
        mountChart(chartId, {
            type: 'bar',
            data: {
                labels: rows.map(function (r) { return r.label; }),
                datasets: [{
                    label: 'تعداد',
                    data: rows.map(function (r) { return r.count; }),
                    backgroundColor: 'rgba(56, 189, 248, 0.55)',
                    borderRadius: 6,
                    maxBarThickness: 22,
                }],
            },
            options: chartOptions({
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0, font: { family: 'inherit' }, callback: function (v) { return toFa(v); } },
                    },
                    y: { ticks: { font: { family: 'inherit', size: 10 } } },
                },
            }),
        });
    }

    function usageChartUnit(label) {
        const keys = Object.keys(USAGE_COUNT_UNIT);
        for (let i = 0; i < keys.length; i++) {
            const key = keys[i];
            if (USAGE_FEATURE_LABELS[key] === label) {
                return USAGE_COUNT_UNIT[key];
            }
        }
        if (label.indexOf('آگهی') >= 0) return 'آگهی';
        if (label.indexOf('فایل') >= 0) return 'فایل';
        return 'بار';
    }

    function renderUsageRankChart(rows) {
        if (!rows || !rows.length) {
            return '<p class="adm-u360-usage-chart__empty">هنوز فعالیتی برای مقایسه ثبت نشده است.</p>';
        }
        const max = Math.max.apply(null, rows.map(function (r) { return Number(r.count) || 0; })) || 1;
        return '<ul class="adm-u360-usage-rank" role="list">'
            + rows.map(function (r, i) {
                const count = Number(r.count) || 0;
                const pct = Math.max(8, Math.round((count / max) * 100));
                const unit = usageChartUnit(r.label);
                return '<li class="adm-u360-usage-rank__row" role="listitem" style="--u360-rank-i:' + i + '">'
                    + '<span class="adm-u360-usage-rank__label">' + esc(r.label) + '</span>'
                    + '<div class="adm-u360-usage-rank__track" aria-hidden="true">'
                    + '<span class="adm-u360-usage-rank__fill" style="width:' + pct + '%"></span>'
                    + '</div>'
                    + '<span class="adm-u360-usage-rank__val">'
                    + '<strong>' + toFa(count) + '</strong> '
                    + '<span class="adm-u360-usage-rank__unit">' + esc(unit) + '</span>'
                    + '</span></li>';
            }).join('')
            + '</ul>';
    }

    function paintPanel(html, tabKey) {
        closeAllSmsPopovers();
        destroyCharts();
        panel.classList.remove('is-loading');
        panel.setAttribute('aria-busy', 'false');
        panel.classList.remove('is-enter');
        const pane = tabKey || activeTab;
        panel.setAttribute('data-u360-active-tab', pane);
        panel.innerHTML = '<div class="adm-u360-tab-stack" data-u360-tab-pane="' + esc(pane) + '">' + html + '</div>';
        void panel.offsetWidth;
        panel.classList.add('is-enter');
        if (pane === 'licenses') {
            initU360JalaliPickers(panel);
        }
    }

    function initU360JalaliPickers(root) {
        if (typeof jalaliDatepicker === 'undefined') return;
        if (window.__admU360JdpBound) return;
        window.__admU360JdpBound = true;
        jalaliDatepicker.startWatch({
            minDate: 'attr',
            maxDate: 'attr',
            zIndex: 25080,
            separatorChars: { date: '/', between: ' ', time: ':' },
            persianDigits: true,
            autoHide: true,
            time: true,
            hasSecond: false,
            hideAfterChange: false,
        });
    }

    function splitLicenseExpiryJalali(jalali) {
        const raw = String(jalali || '').trim();
        if (!raw || raw === 'نامحدود') {
            return { unlimited: true, date: '', time: '', inputValue: '' };
        }
        const parts = raw.split(/\s+/);
        const date = parts[0] || raw;
        const time = parts[1] || '';
        return {
            unlimited: false,
            date: date,
            time: time,
            inputValue: time ? (date + ' ' + time) : date,
        };
    }

    function licenseExpiryRemainHint(lic) {
        if (lic.days_until_expiry === null || lic.days_until_expiry === undefined) return '';
        const d = Number(lic.days_until_expiry);
        if (Number.isNaN(d)) return '';
        if (d < 0) {
            return '<span class="adm-u360-lic-expiry-hint is-late">' + toFa(Math.abs(d)) + ' روز گذشته</span>';
        }
        if (d === 0) {
            return '<span class="adm-u360-lic-expiry-hint is-soon">امروز</span>';
        }
        return '<span class="adm-u360-lic-expiry-hint">' + toFa(d) + ' روز مانده</span>';
    }

    function showLoading() {
        destroyCharts();
        panel.classList.add('is-loading');
        panel.setAttribute('aria-busy', 'true');
        panel.classList.remove('is-enter');
        panel.innerHTML = '<div class="adm-u360-skeleton adm-u360-skeleton--rich" aria-hidden="true">'
            + '<span class="adm-u360-skeleton__line adm-u360-skeleton__line--sm"></span>'
            + '<span class="adm-u360-skeleton__line"></span>'
            + '<span class="adm-u360-skeleton__line adm-u360-skeleton__line--md"></span>'
            + '<span class="adm-u360-skeleton__block"></span></div>'
            + '<p class="adm-v2-sr-only">در حال بارگذاری</p>';
    }

    function tabsScrollMetrics() {
        if (!tabsNav) return { scrollable: false, atStart: true, atEnd: true };
        const max = Math.max(0, tabsNav.scrollWidth - tabsNav.clientWidth);
        if (max <= 2) {
            return { scrollable: false, atStart: true, atEnd: true };
        }
        const sl = Math.abs(tabsNav.scrollLeft);
        return {
            scrollable: true,
            atStart: sl <= 4,
            atEnd: sl >= max - 4,
        };
    }

    function syncTabsScrollUI() {
        if (!tabsWrap || !tabsNav) return;
        const m = tabsScrollMetrics();
        tabsWrap.classList.toggle('is-scrollable', m.scrollable);
        tabsWrap.classList.toggle('is-at-start', m.atStart);
        tabsWrap.classList.toggle('is-at-end', m.atEnd);
    }

    function scrollMetrics(el) {
        if (!el) return { scrollable: false, atStart: true, atEnd: true };
        const max = Math.max(0, el.scrollWidth - el.clientWidth);
        if (max <= 2) {
            return { scrollable: false, atStart: true, atEnd: true };
        }
        const sl = Math.abs(el.scrollLeft);
        return {
            scrollable: true,
            atStart: sl <= 4,
            atEnd: sl >= max - 4,
        };
    }

    function syncKpisScrollUI() {
        if (!kpisWrap || !kpisEl) return;
        const m = scrollMetrics(kpisEl);
        kpisWrap.classList.toggle('is-scrollable', m.scrollable);
        kpisWrap.classList.toggle('is-at-start', m.atStart);
        kpisWrap.classList.toggle('is-at-end', m.atEnd);
    }

    function scrollActiveTabIntoView() {
        if (!tabsNav) return;
        const active = tabsNav.querySelector('.adm-u360-tab.is-active');
        if (active && active.scrollIntoView) {
            active.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
        }
        window.requestAnimationFrame(syncTabsScrollUI);
    }

    function insightSeverityMeta(severity) {
        if (severity === 'warn') {
            return { cls: 'adm-u360-insight--warn', badge: 'نیازمند اقدام', icon: 'fa-triangle-exclamation' };
        }
        if (severity === 'ok') {
            return { cls: 'adm-u360-insight--ok', badge: 'وضعیت مطلوب', icon: 'fa-circle-check' };
        }
        return { cls: 'adm-u360-insight--info', badge: 'توجه', icon: 'fa-circle-info' };
    }

    function renderInsightsPanel(items) {
        const list = (items || []).slice().sort(function (a, b) {
            const order = { warn: 0, info: 1, ok: 2 };
            return (Object.prototype.hasOwnProperty.call(order, a.severity) ? order[a.severity] : 9)
                - (Object.prototype.hasOwnProperty.call(order, b.severity) ? order[b.severity] : 9);
        });
        if (!list.length) {
            return '<div class="adm-u360-insights adm-u360-insights--empty">'
                + '<p class="adm-u360-insights-empty__title">مورد نیازمند اقدام شناسایی نشد</p>'
                + '<p class="adm-u360-insights-empty__lead">بر اساس داده‌های فعلی، هشدار یا پیگیری فوری ثبت نشده است.</p>'
                + '</div>';
        }
        const counts = { warn: 0, info: 0, ok: 0 };
        list.forEach(function (item) {
            const key = item.severity === 'warn' || item.severity === 'ok' ? item.severity : 'info';
            counts[key] += 1;
        });
        let summary = '<div class="adm-u360-insights-summary">';
        if (counts.warn) {
            summary += '<span class="adm-u360-insights-pill adm-u360-insights-pill--warn">'
                + toFa(counts.warn) + ' نیازمند اقدام</span>';
        }
        if (counts.info) {
            summary += '<span class="adm-u360-insights-pill adm-u360-insights-pill--info">'
                + toFa(counts.info) + ' توجه</span>';
        }
        if (counts.ok) {
            summary += '<span class="adm-u360-insights-pill adm-u360-insights-pill--ok">'
                + toFa(counts.ok) + ' مطلوب</span>';
        }
        summary += '</div>';
        const cards = list.map(function (item) {
            const meta = insightSeverityMeta(item.severity);
            return '<article class="adm-u360-insight ' + meta.cls + '">'
                + '<header class="adm-u360-insight__head">'
                + '<span class="adm-u360-insight__badge"><i class="fas ' + meta.icon + '" aria-hidden="true"></i>'
                + esc(meta.badge) + '</span></header>'
                + '<h3 class="adm-u360-insight__title">' + esc(item.title) + '</h3>'
                + '<p class="adm-u360-insight__detail">' + esc(item.detail) + '</p>'
                + (item.suggested_action
                    ? '<footer class="adm-u360-insight__foot"><span class="adm-u360-insight__action-label">پیشنهاد</span>'
                        + '<p class="adm-u360-insight__action">' + esc(item.suggested_action) + '</p></footer>'
                    : '')
                + '</article>';
        }).join('');
        return '<div class="adm-u360-insights">' + summary + '<div class="adm-u360-insights__list">' + cards + '</div></div>';
    }

    function overviewJumpChip(label, tab, icon) {
        const ic = icon ? '<i class="fas ' + icon + '" aria-hidden="true"></i>' : '';
        return '<button type="button" class="adm-u360-jump-chip" data-u360-tab-jump="' + esc(tab) + '">'
            + ic + '<span>' + esc(label) + '</span></button>';
    }

    function renderPrimaryKpisSection() {
        const primary = bootstrap.primary_kpis || [];
        const fallbackKeys = {
            revenue: true,
            paid_count: true,
            pending: true,
            tickets: true,
            datasets: true,
            crm: true,
            deals: true,
            devices: true,
        };
        const kpis = primary.length
            ? primary
            : (bootstrap.kpis || []).filter(function (k) { return fallbackKeys[k.key]; });
        const cells = kpis.map(function (k) {
            let value = '';
            if (k.key === 'revenue') {
                value = moneyTomans(k.value);
            } else if (k.value_text) {
                value = esc(toFa(k.value_text));
            } else {
                value = toFa(k.value);
            }
            let tone = '';
            if ((k.key === 'tickets' || k.key === 'pending') && Number(k.value) > 0) {
                tone = 'warn';
            }
            return {
                key: k.key,
                label: k.label,
                value: value,
                icon: k.icon,
                tab: k.anchor,
                tone: tone,
            };
        });
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-metrics" aria-labelledby="admU360KpisTitle">'
            + '<header class="adm-u360-kpis-head">'
            + '<h2 class="adm-u360-kpis-head__title" id="admU360KpisTitle">شاخص‌های کلیدی</h2>'
            + '<span class="adm-u360-kpis-head__hint">برای جزئیات، روی هر شاخص بزنید</span>'
            + '</header>'
            + statStrip(cells, 'adm-u360-stat-strip--hero adm-u360-stat-strip--grid-kpi')
            + '</section>';
    }

    function renderOverviewInsightsAside(items) {
        const list = (items || []).slice().sort(function (a, b) {
            const order = { warn: 0, info: 1, ok: 2 };
            return (Object.prototype.hasOwnProperty.call(order, a.severity) ? order[a.severity] : 9)
                - (Object.prototype.hasOwnProperty.call(order, b.severity) ? order[b.severity] : 9);
        });
        if (!list.length) {
            return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-insights" aria-label="بینش و اولویت">'
                + '<h2 class="adm-u360-overview-insights__title">بینش و اولویت</h2>'
                + '<div class="adm-u360-insights adm-u360-insights--empty adm-u360-insights--panel">'
                + '<p class="adm-u360-insights-empty__title">مورد نیازمند اقدام شناسایی نشد</p>'
                + '<p class="adm-u360-insights-empty__lead">بر اساس داده‌های فعلی، هشدار یا پیگیری فوری ثبت نشده است.</p>'
                + '</div></section>';
        }
        const cards = list.map(function (item) {
            const meta = insightSeverityMeta(item.severity);
            return '<article class="adm-u360-insight adm-u360-insight--compact ' + meta.cls + '">'
                + '<span class="adm-u360-insight__badge"><i class="fas ' + meta.icon + '" aria-hidden="true"></i>'
                + esc(meta.badge) + '</span>'
                + '<h3 class="adm-u360-insight__title">' + esc(item.title) + '</h3>'
                + '<p class="adm-u360-insight__detail">' + esc(item.detail) + '</p>'
                + (item.suggested_action
                    ? '<p class="adm-u360-insight__action">' + esc(item.suggested_action) + '</p>'
                    : '')
                + '</article>';
        }).join('');
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-insights" aria-label="بینش و اولویت">'
            + '<h2 class="adm-u360-overview-insights__title">بینش و اولویت</h2>'
            + '<div class="adm-u360-insights adm-u360-insights--panel"><div class="adm-u360-insights__list">'
            + cards
            + '</div></div></section>';
    }

    function formatWindowsEngagement(flags) {
        const f = flags || {};
        const steps = [];
        if (f.windows_downloaded || f.downloaded) steps.push('نصب‌کننده دریافت شده');
        if (f.windows_activated || f.activated) steps.push('لایسنس فعال شده');
        if (f.windows_launched || f.first_launch) steps.push('برنامه اجرا شده');
        if (!steps.length) return 'هنوز اثری از نصب یا اجرا ثبت نشده';
        return steps.join(' · ');
    }

    function formatAndroidEngagement(eng) {
        const installed = eng && (eng.android_installed || eng.installed);
        const count = Number((eng && (eng.android_devices != null ? eng.android_devices : eng.devices_count)) || 0);
        if (installed && count > 0) return toFa(count) + ' دستگاه متصل';
        if (installed) return 'نصب ثبت شده';
        return 'اپ نصب یا ورود ثبت نشده';
    }

    function renderDeviceCheckRow(label, on, detail) {
        return '<li class="adm-u360-devices-check' + (on ? ' adm-u360-devices-check--on' : '') + '" role="listitem">'
            + '<span class="adm-u360-devices-check__label">' + esc(label) + '</span>'
            + '<span class="adm-u360-devices-check__value">' + esc(detail) + '</span>'
            + '</li>';
    }

    function supportStatusMod(key) {
        const k = String(key || '').toLowerCase();
        if (k === 'closed') return 'closed';
        if (k === 'waiting_user') return 'waiting';
        if (k === 'answered') return 'answered';
        if (k === 'in_review') return 'review';
        if (k === 'open') return 'open';
        return 'default';
    }

    function supportPriorityMod(key) {
        const k = String(key || '').toLowerCase();
        if (k === 'high' || k === 'urgent') return 'high';
        if (k === 'low') return 'low';
        return 'normal';
    }

    function renderSupportMessage(m) {
        const mods = [];
        if (m.is_internal) mods.push('internal');
        const isStaff = !!m.is_staff;
        mods.push(isStaff ? 'staff' : 'customer');
        const modClass = mods.map(function (x) { return 'adm-u360-support-msg--' + x; }).join(' ');
        const text = (m.body || m.body_preview || '').trim();
        let attachments = '';
        if (m.attachments && m.attachments.length) {
            attachments = '<ul class="adm-u360-support-msg__files" role="list">'
                + m.attachments.map(function (a) {
                    return '<li role="listitem"><a href="' + esc(a.url) + '" target="_blank" rel="noopener">'
                        + '<i class="fas fa-paperclip" aria-hidden="true"></i> '
                        + esc(a.filename) + '</a></li>';
                }).join('') + '</ul>';
        }
        let roleLabel;
        let roleIcon;
        if (m.is_internal) {
            roleLabel = 'یادداشت داخلی';
            roleIcon = 'fa-lock';
        } else if (isStaff) {
            roleLabel = 'پاسخ پشتیبانی';
            roleIcon = 'fa-headset';
        } else {
            roleLabel = 'پیام مشتری';
            roleIcon = 'fa-user';
        }
        return '<article class="adm-u360-support-msg ' + modClass + '" role="listitem">'
            + '<div class="adm-u360-support-msg__bubble">'
            + '<p class="adm-u360-support-msg__role">'
            + '<i class="fas ' + roleIcon + '" aria-hidden="true"></i>'
            + '<span>' + esc(roleLabel) + '</span></p>'
            + '<header class="adm-u360-support-msg__meta">'
            + '<span class="adm-u360-support-msg__author">' + esc(m.author) + '</span>'
            + '<time class="adm-u360-support-msg__time">' + esc(m.created_jalali) + '</time>'
            + '</header>'
            + '<p class="adm-u360-support-msg__text">' + esc(text) + '</p>'
            + attachments
            + '</div></article>';
    }

    function renderSupportSelect(name, options, selected, attrs) {
        const opts = (options || []).map(function (o) {
            const sel = o.key === selected ? ' selected' : '';
            return '<option value="' + esc(o.key) + '"' + sel + '>' + esc(o.label) + '</option>';
        }).join('');
        return '<select class="adm-u360-support-select" name="' + esc(name) + '" ' + (attrs || '') + '>'
            + opts + '</select>';
    }

    function renderSupportListItem(t, selectedId) {
        const stMod = supportStatusMod(t.status_key);
        const selected = Number(t.ticket_id) === Number(selectedId);
        const preview = ((t.recent_messages || [])[0] || {}).body_preview || '';
        const previewShort = preview.length > 88 ? preview.slice(0, 88) + '…' : preview;
        return '<button type="button" class="adm-u360-support-list__item'
            + (selected ? ' is-active' : '')
            + (t.staff_unread ? ' is-unread' : '')
            + '" data-u360-support-ticket="' + esc(t.ticket_id) + '"'
            + ' aria-current="' + (selected ? 'true' : 'false') + '">'
            + '<span class="adm-u360-support-list__top">'
            + '<span class="adm-u360-support-list__id">' + esc(t.ticket_number) + '</span>'
            + '<span class="adm-u360-support-tag adm-u360-support-tag--' + stMod + '">' + esc(t.status) + '</span>'
            + '</span>'
            + '<span class="adm-u360-support-list__subject">' + esc(t.subject) + '</span>'
            + (previewShort
                ? '<span class="adm-u360-support-list__preview">' + esc(previewShort) + '</span>'
                : '')
            + '<span class="adm-u360-support-list__foot">'
            + '<span>' + esc(t.last_message_jalali || '—') + '</span>'
            + '<span>' + toFa(t.messages_count || 0) + ' پیام</span>'
            + '</span>'
            + '</button>';
    }

    function renderSupportWorkspacePlaceholder(canManage) {
        return '<div class="adm-u360-support-workspace__placeholder">'
            + '<i class="fas fa-headset" aria-hidden="true"></i>'
            + '<p class="adm-u360-support-workspace__title">یک تیکت را انتخاب کنید</p>'
            + '<p class="adm-u360-support-workspace__hint">'
            + (canManage
                ? 'مکالمه کامل، پاسخ، تغییر وضعیت و بستن تیکت را همین‌جا انجام دهید.'
                : 'برای مشاهده مکالمه کامل یک تیکت از فهرست انتخاب کنید.')
            + '</p></div>';
    }

    function renderSupportWorkspaceDetail(ticket, canManage) {
        const stMod = supportStatusMod(ticket.status_key);
        const form = ticket.form_options || {};
        const messages = (ticket.messages || []).map(renderSupportMessage).join('');
        const desc = (ticket.description || '').trim();
        let controls = '';
        if (canManage) {
            controls = '<div class="adm-u360-support-workspace__controls" role="toolbar" aria-label="کنترل تیکت">'
                + '<div class="adm-u360-support-workspace__ctrl">'
                + '<label>وضعیت</label>'
                + renderSupportSelect('status', form.status, ticket.status_key, 'data-u360-support-field="status"')
            + '</div>'
                + '<div class="adm-u360-support-workspace__ctrl">'
                + '<label>اولویت</label>'
                + renderSupportSelect('priority', form.priority, ticket.priority_key, 'data-u360-support-field="priority"')
            + '</div>'
                + '<div class="adm-u360-support-workspace__ctrl-actions">'
                + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-u360-support-save-meta>ذخیره</button>'
                + (ticket.is_closed
                    ? '<button type="button" class="ecc-btn ecc-btn--primary ecc-btn--sm" data-u360-support-reopen>باز کردن</button>'
                    : '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" data-u360-support-close>بستن</button>')
                + '</div></div>';
        }
        let compose = '';
        if (canManage) {
            const afterStatus = renderSupportSelect(
                'after_status',
                form.status,
                ticket.is_closed ? 'open' : 'answered',
                'data-u360-support-after-status'
            );
            compose = '<footer class="adm-u360-support-compose">'
                + '<label class="adm-u360-support-compose__label" for="admU360SupportBody">پاسخ یا یادداشت</label>'
                + '<textarea id="admU360SupportBody" class="adm-u360-support-compose__input" rows="4" '
                + 'placeholder="متن پاسخ را بنویسید؛ برای کاربر ارسال می‌شود مگر یادداشت داخلی باشد."></textarea>'
                + '<div class="adm-u360-support-compose__row">'
                + '<label class="adm-u360-support-compose__check adm-u360-check">'
                + '<input type="checkbox" data-u360-support-internal> <span>یادداشت داخلی (مشتری نمی‌بیند)</span></label>'
                + '<label class="adm-u360-support-compose__status">پس از ارسال · ' + afterStatus + '</label>'
                + '</div>'
                + '<div class="adm-u360-support-compose__actions">'
                + '<span class="adm-u360-support-compose__feedback" data-u360-support-feedback hidden></span>'
                + '<button type="button" class="ecc-btn ecc-btn--primary ecc-btn--sm" data-u360-support-send>'
                + '<i class="fas fa-paper-plane" aria-hidden="true"></i> ارسال</button>'
                + '</div></footer>';
        }
        return '<article class="adm-u360-support-workspace__panel adm-u360-support-case--' + stMod + '">'
            + '<header class="adm-u360-support-workspace__head">'
            + '<div><span class="adm-u360-support-case__id">' + esc(ticket.ticket_number) + '</span>'
            + '<h3 class="adm-u360-support-case__subject">' + esc(ticket.subject) + '</h3>'
            + '<p class="adm-u360-support-workspace__meta">'
            + esc(ticket.category || '—') + ' · ایجاد ' + esc(ticket.created_jalali || '—')
            + (ticket.assigned_to && ticket.assigned_to !== '—' ? ' · مسئول ' + esc(ticket.assigned_to) : '')
            + '</p></div>'
            + (ticket.staff_unread ? '<span class="adm-u360-support-workspace__unread">جدید</span>' : '')
            + '</header>'
            + controls
            + (desc
                ? '<div class="adm-u360-support-workspace__desc"><p class="adm-u360-support-workspace__desc-label">شرح اولیه</p>'
                    + '<p>' + esc(desc) + '</p></div>'
                : '')
            + '<div class="adm-u360-support-thread adm-u360-support-thread--full" role="list" aria-label="مکالمه تیکت">'
            + (messages || '<p class="adm-u360-support-thread__empty">هنوز پیامی ثبت نشده.</p>')
            + '</div>'
            + compose
            + '</article>';
    }

    function renderSupportStatusStrip(rows) {
        if (!rows || !rows.length) return '';
        const segments = rows.map(function (r) {
            const mod = supportStatusMod(r.key);
            const weight = Math.max(Number(r.count) || 0, 0.35);
            return '<div class="adm-u360-support-seg adm-u360-support-seg--' + mod + '" '
                + 'style="flex-grow:' + weight + '" '
                + 'title="' + esc(r.label || r.key) + ' · ' + toFa(r.count) + '"></div>';
        }).join('');
        const legend = rows.map(function (r) {
            const mod = supportStatusMod(r.key);
            return '<span class="adm-u360-support-strip__chip adm-u360-support-strip__chip--' + mod + '">'
                + '<span class="adm-u360-support-legend__dot" aria-hidden="true"></span>'
                + esc(r.label || r.key) + ' · ' + toFa(r.count)
                + '</span>';
        }).join('');
        return '<div class="adm-u360-support-strip" role="img" aria-label="توزیع وضعیت">'
            + '<div class="adm-u360-support-viz__bar">' + segments + '</div>'
            + '<div class="adm-u360-support-strip__legend">' + legend + '</div></div>';
    }

    function renderSupportTopBar(data, canManage, tStats, includeInternal) {
        const stats = data.stats || {};
        const openN = Number(stats.open) || 0;
        const unreadN = Number(stats.staff_unread) || 0;
        const totalN = Number(stats.total) || 0;
        const perms = bootstrap.permissions || {};
        let tools = '';
        if (perms.can_view_internal_tickets) {
            tools = '<label class="adm-u360-support-top__toggle adm-u360-check">'
                + '<input type="checkbox" id="admU360SupportInternal" '
                + (includeInternal ? 'checked' : '') + '>'
                + '<span>یادداشت داخلی</span></label>';
        }
        return '<header class="adm-u360-support-top" aria-label="خلاصه پشتیبانی">'
            + '<div class="adm-u360-support-top__row">'
            + '<div class="adm-u360-support-top__brand">'
            + '<h2 class="adm-u360-support-top__title">'
            + '<i class="fas fa-headset" aria-hidden="true"></i><span>پشتیبانی مشتری</span></h2>'
            + (canManage ? '<span class="adm-u360-support-top__mode">مدیریت</span>' : '')
            + '</div>'
            + '<div class="adm-u360-support-top__kpis" role="list">'
            + '<span class="adm-u360-support-kpi' + (openN ? ' adm-u360-support-kpi--warn' : '') + '" role="listitem">'
            + '<span class="adm-u360-support-kpi__label">باز</span>'
            + '<span class="adm-u360-support-kpi__val">' + toFa(openN) + '</span></span>'
            + '<span class="adm-u360-support-kpi' + (unreadN ? ' adm-u360-support-kpi--accent' : '') + '" role="listitem">'
            + '<span class="adm-u360-support-kpi__label">خوانده‌نشده</span>'
            + '<span class="adm-u360-support-kpi__val">' + toFa(unreadN) + '</span></span>'
            + '<span class="adm-u360-support-kpi" role="listitem">'
            + '<span class="adm-u360-support-kpi__label">کل تیکت</span>'
            + '<span class="adm-u360-support-kpi__val">' + toFa(totalN) + '</span></span>'
            + '</div>'
            + '<div class="adm-u360-support-top__tools">' + tools + '</div>'
            + '</div>'
            + (totalN && tStats.length ? renderSupportStatusStrip(tStats) : '')
            + '</header>';
    }

    function supportInternalQuery() {
        const st = tabQueryState.support || {};
        return st.internal === '1' ? { internal: '1' } : {};
    }

    function supportWorkspaceEl() {
        return document.getElementById('admU360SupportWorkspace');
    }

    function setSupportWorkspaceLoading(on) {
        const ws = supportWorkspaceEl();
        if (!ws) return;
        ws.classList.toggle('is-loading', !!on);
    }

    function paintSupportWorkspace(html) {
        const ws = supportWorkspaceEl();
        if (ws) ws.innerHTML = html;
    }

    function loadSupportTicketDetail(ticketId, opts) {
        opts = opts || {};
        const canManage = !!(bootstrap.permissions || {}).can_manage_support_tickets
            || !!opts.canManage;
        if (!ticketId) {
            paintSupportWorkspace(renderSupportWorkspacePlaceholder(canManage));
            return Promise.resolve();
        }
        supportDeskSelectedId = ticketId;
        const query = supportInternalQuery();
        setSupportWorkspaceLoading(true);
        return fetch(supportTicketDetailUrl(ticketId, query), {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (payload) {
                if (!payload.ok) throw new Error('bad');
                paintSupportWorkspace(renderSupportWorkspaceDetail(payload.ticket, canManage));
                const thread = supportWorkspaceEl() && supportWorkspaceEl().querySelector('.adm-u360-support-thread--full');
                if (thread) thread.scrollTop = thread.scrollHeight;
                panel.querySelectorAll('[data-u360-support-ticket]').forEach(function (btn) {
                    const on = btn.getAttribute('data-u360-support-ticket') === String(ticketId);
                    btn.classList.toggle('is-active', on);
                    btn.setAttribute('aria-current', on ? 'true' : 'false');
                });
            })
            .catch(function () {
                paintSupportWorkspace('<p class="adm-u360-empty">بارگذاری تیکت ناموفق بود.</p>');
            })
            .finally(function () {
                setSupportWorkspaceLoading(false);
            });
    }

    function postSupportTicketAction(ticketId, body) {
        return fetch(supportTicketActionUrl(ticketId), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(Object.assign({ internal: (tabQueryState.support || {}).internal === '1' ? '1' : '' }, body)),
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok || !data.ok) {
                    throw new Error((data && data.error) || 'خطا در عملیات');
                }
                return data;
            });
        });
    }

    function renderSupport(data) {
        const perms = bootstrap.permissions || {};
        const canManage = !!(perms.can_manage_support_tickets || data.can_manage_tickets);
        const tStats = (data.charts && data.charts.tickets_by_status) || [];
        const stats = data.stats || {};
        const tickets = data.tickets || [];
        const st = tabQueryState.support || {};
        const preferId = st.ticket || supportDeskSelectedId;
        let selectedId = preferId;
        if (!selectedId && tickets.length) {
            const unread = tickets.find(function (t) { return t.staff_unread; });
            selectedId = (unread || tickets[0]).ticket_id;
        }

        const top = renderSupportTopBar(data, canManage, tStats, data.include_internal_notes);

        const listHtml = tickets.length
            ? tickets.map(function (t) { return renderSupportListItem(t, selectedId); }).join('')
            : '';
        const pager = tickets.length ? renderPager(data.pagination, 'support') : '';

        let stage;
        if (!tickets.length) {
            stage = '<section class="adm-u360-support-stage adm-u360-support-stage--empty">'
                + emptyState('تیکتی ثبت نشده', 'هنوز درخواست پشتیبانی از این مشتری در سیستم نیست.', 'fa-headset')
                + '</section>';
        } else {
            stage = '<section class="adm-u360-support-stage" aria-label="میزکار تیکت">'
                + '<div class="adm-u360-support-desk__grid">'
                + '<aside class="adm-u360-support-list" aria-label="فهرست تیکت‌ها">'
                + '<header class="adm-u360-support-list__head">'
                + '<h3 class="adm-u360-support-list__title">تیکت‌ها</h3>'
                + '<span class="adm-u360-support-list__count">' + toFa(stats.total || tickets.length) + '</span>'
                + '</header>'
                + '<div class="adm-u360-support-list__scroll" role="list">' + listHtml + '</div>'
                + (pager ? '<footer class="adm-u360-support-list__foot">' + pager + '</footer>' : '')
                + '</aside>'
                + '<main class="adm-u360-support-workspace" id="admU360SupportWorkspace" aria-live="polite">'
                + renderSupportWorkspacePlaceholder(canManage)
                + '</main></div></section>';
        }

        paintPanel('<div class="adm-u360-support adm-u360-support--pro">'
            + top
            + stage
            + '</div>', 'support');

        const internalChk = document.getElementById('admU360SupportInternal');
        if (internalChk) {
            internalChk.addEventListener('change', function () {
                loadTab('support', internalChk.checked ? { internal: '1', page: '1', ticket: supportDeskSelectedId || '' } : { page: '1', ticket: supportDeskSelectedId || '' }, true);
            });
        }
        if (selectedId) {
            loadSupportTicketDetail(selectedId, { canManage: canManage });
        }
    }

    function renderWorkspaceTopBar(stats, note) {
        const s = stats || {};
        const openDeals = Number(s.deals_open) || 0;
        const contacts = Number(s.contacts) || 0;
        return '<header class="adm-u360-ws-top" aria-label="خلاصه فضای کار">'
            + '<div class="adm-u360-ws-top__row">'
            + '<div class="adm-u360-ws-top__brand">'
            + '<h2 class="adm-u360-ws-top__title">'
            + '<i class="fas fa-layer-group" aria-hidden="true"></i><span>مخاطبین و فایل‌ها</span></h2>'
            + (note ? '<p class="adm-u360-ws-top__note">' + esc(note) + '</p>' : '')
            + '</div>'
            + '<div class="adm-u360-ws-top__kpis" role="list">'
            + '<span class="adm-u360-ws-kpi adm-u360-ws-kpi--accent" role="listitem">'
            + '<span class="adm-u360-ws-kpi__label">مخاطبین CRM</span>'
            + '<span class="adm-u360-ws-kpi__val">' + toFa(contacts) + '</span></span>'
            + '<span class="adm-u360-ws-kpi' + (openDeals ? ' adm-u360-ws-kpi--warn' : '') + '" role="listitem">'
            + '<span class="adm-u360-ws-kpi__label">معامله باز</span>'
            + '<span class="adm-u360-ws-kpi__val">' + toFa(openDeals) + '</span></span>'
            + '<span class="adm-u360-ws-kpi" role="listitem">'
            + '<span class="adm-u360-ws-kpi__label">کل معاملات</span>'
            + '<span class="adm-u360-ws-kpi__val">' + toFa(s.deals_total || 0) + '</span></span>'
            + '<span class="adm-u360-ws-kpi" role="listitem">'
            + '<span class="adm-u360-ws-kpi__label">دیتاست فعال</span>'
            + '<span class="adm-u360-ws-kpi__val">' + toFa(s.datasets_total || 0) + '</span></span>'
            + '<span class="adm-u360-ws-kpi" role="listitem">'
            + '<span class="adm-u360-ws-kpi__label">آگهی در بانک</span>'
            + '<span class="adm-u360-ws-kpi__val">' + toFa(s.listings_in_files || 0) + '</span></span>'
            + '</div></div></header>';
    }

    function renderWorkspaceContactRow(c) {
        return '<li class="adm-u360-ws-contact" role="listitem">'
            + '<div class="adm-u360-ws-contact__body">'
            + '<p class="adm-u360-ws-contact__name">' + esc(c.name || '—') + '</p>'
            + '<p class="adm-u360-ws-contact__sub">'
            + '<span class="adm-u360-ws-pill">' + esc(c.status || '—') + '</span>'
            + (c.type ? '<span class="adm-u360-ws-pill adm-u360-ws-pill--muted">' + esc(c.type) + '</span>' : '')
            + '</p>'
            + '</div>'
            + '<div class="adm-u360-ws-contact__side">'
            + '<span class="adm-u360-ws-contact__phone adm-u360-ltr">' + esc(c.phone || '—') + '</span>'
            + '<time class="adm-u360-ws-contact__time">' + esc(c.created_jalali || '') + '</time>'
            + '</div></li>';
    }

    function renderWorkspaceDatasetRow(d) {
        const rows = Number(d.row_count) || 0;
        return '<li class="adm-u360-ws-dataset" role="listitem">'
            + '<div class="adm-u360-ws-dataset__body">'
            + '<p class="adm-u360-ws-dataset__name">' + esc(d.name || '—') + '</p>'
            + '<p class="adm-u360-ws-dataset__meta">'
            + '<span>' + esc(d.city || '—') + '</span>'
            + '<span>·</span>'
            + '<time>' + esc(d.created_jalali || '') + '</time>'
            + '</p></div>'
            + '<div class="adm-u360-ws-dataset__count" title="تعداد آگهی در فایل">'
            + '<strong>' + toFa(rows) + '</strong>'
            + '<span>آگهی</span></div></li>';
    }

    function marketingJourneyIcon(eventKey) {
        const k = String(eventKey || '').toLowerCase();
        if (k.indexOf('expir') >= 0 || k.indexOf('license') >= 0) return 'fa-hourglass-half';
        if (k.indexOf('paid') >= 0 || k.indexOf('checkout') >= 0 || k.indexOf('payment') >= 0) return 'fa-credit-card';
        if (k.indexOf('signup') >= 0 || k.indexOf('register') >= 0) return 'fa-user-plus';
        if (k.indexOf('sms') >= 0 || k.indexOf('campaign') >= 0) return 'fa-comment-dots';
        return 'fa-bolt';
    }

    function renderMarketingJourneyItem(item) {
        const icon = marketingJourneyIcon(item.event_key);
        const count = Number(item.count) || 1;
        return '<li class="adm-u360-mkt-journey__item" role="listitem">'
            + '<span class="adm-u360-mkt-journey__dot" aria-hidden="true">'
            + '<i class="fas ' + icon + '"></i></span>'
            + '<div class="adm-u360-mkt-journey__body">'
            + '<p class="adm-u360-mkt-journey__title">' + esc(item.event_type) + '</p>'
            + '<p class="adm-u360-mkt-journey__meta">'
            + '<span class="adm-u360-mkt-journey__meta-label">آخرین ثبت</span>'
            + '<time>' + esc(item.last_jalali) + '</time>'
            + (count > 1
                ? '<span class="adm-u360-mkt-journey__count" title="تعداد دفعاتی که این رویداد در لاگ مسیر رشد ثبت شده">'
                    + toFa(count) + ' بار در لاگ'
                    + '</span>'
                : '')
            + '</p></div></li>';
    }

    function renderMarketingCompactRows(headers, rowHtml, emptyTitle) {
        if (!rowHtml) {
            return '<p class="adm-u360-mkt-mini__empty">' + esc(emptyTitle || 'موردی نیست') + '</p>';
        }
        return '<div class="adm-u360-table-wrap adm-u360-data-table adm-u360-mkt-mini-table">'
            + '<table class="adm-table adm-table--pro adm-table--compact"><thead><tr>'
            + headers.map(function (h) { return '<th scope="col">' + esc(h) + '</th>'; }).join('')
            + '</tr></thead><tbody>' + rowHtml + '</tbody></table></div>';
    }

    function renderMarketingTopBar(stats, optOut) {
        const s = stats || {};
        return '<header class="adm-u360-mkt-top" aria-label="خلاصه بازاریابی">'
            + '<div class="adm-u360-mkt-top__row">'
            + '<div class="adm-u360-mkt-top__brand">'
            + '<h2 class="adm-u360-mkt-top__title">'
            + '<i class="fas fa-bullhorn" aria-hidden="true"></i><span>ارتباطات و بازاریابی</span></h2>'
            + '<span class="adm-u360-mkt-top__opt' + (optOut ? ' adm-u360-mkt-top__opt--warn' : ' adm-u360-mkt-top__opt--ok') + '">'
            + (optOut ? 'انصراف از پیامک' : 'دریافت پیامک فعال') + '</span>'
            + '</div>'
            + '<div class="adm-u360-mkt-top__kpis" role="list">'
            + '<span class="adm-u360-mkt-kpi" role="listitem"><span class="adm-u360-mkt-kpi__l">پیامک</span>'
            + '<span class="adm-u360-mkt-kpi__v">' + toFa(s.sms_count || 0) + '</span></span>'
            + '<span class="adm-u360-mkt-kpi" role="listitem"><span class="adm-u360-mkt-kpi__l">کمپین</span>'
            + '<span class="adm-u360-mkt-kpi__v">' + toFa(s.campaign_count || 0) + '</span></span>'
            + '<span class="adm-u360-mkt-kpi" role="listitem"><span class="adm-u360-mkt-kpi__l">رویداد رشد</span>'
            + '<span class="adm-u360-mkt-kpi__v">' + toFa(s.journey_type_count || 0) + '</span></span>'
            + '<span class="adm-u360-mkt-kpi" role="listitem"><span class="adm-u360-mkt-kpi__l">تخفیف</span>'
            + '<span class="adm-u360-mkt-kpi__v">' + toFa(s.discount_count || 0) + '</span></span>'
            + '</div></div></header>';
    }

    function renderMarketing(data) {
        const stats = data.stats || {};
        const journeySummary = data.growth_journey_summary || [];
        const sms = (data.sms_logs || []).map(function (s) {
            return '<tr>' + td(esc(s.purpose), 'هدف') + smsMessageTd(s)
                + td(esc(s.status), 'وضعیت') + td(esc(s.created_jalali), 'زمان') + '</tr>';
        }).join('');

        const journeyBody = journeySummary.length
            ? '<ol class="adm-u360-mkt-journey" role="list">' + journeySummary.map(renderMarketingJourneyItem).join('') + '</ol>'
            : emptyState('رویداد رشدی نیست', 'مسیر رشد این کاربر هنوز رویدادی ندارد.', 'fa-route');

        const camps = (data.campaigns || []).map(function (r) {
            return '<tr>' + td(esc(r.campaign), 'کمپین') + td(esc(r.status), 'وضعیت')
                + td(esc(r.created_jalali), 'زمان') + '</tr>';
        }).join('');
        const disc = (data.discount_issuances || []).map(function (r) {
            return '<tr>'
                + td('<span class="adm-u360-ltr">' + esc(r.code) + '</span>', 'کد')
                + td(esc(r.policy_key), 'سیاست')
                + td(esc(r.issued_jalali), 'زمان') + '</tr>';
        }).join('');
        const attrs = (data.attributions || []).map(function (r) {
            return '<tr>' + td(esc(r.model), 'مدل') + td(esc(r.status), 'وضعیت')
                + td(esc(r.created_jalali), 'زمان') + '</tr>';
        }).join('');

        const stage = '<div class="adm-u360-mkt-stage adm-u360-mkt-stage--stack">'
            + '<section class="adm-u360-mkt-panel adm-u360-mkt-panel--sms" aria-label="پیامک‌های سیستمی">'
            + '<header class="adm-u360-mkt-panel__head"><h3 class="adm-u360-mkt-panel__title">پیامک‌های سیستمی</h3>'
            + '<span class="adm-u360-mkt-panel__count">' + toFa(stats.sms_count || 0) + '</span></header>'
            + '<div class="adm-u360-mkt-panel__body">'
            + (sms ? renderMarketingCompactRows(['هدف', 'متن', 'وضعیت', 'زمان'], sms) : emptyState('پیامکی نیست', 'لاگ پیامک برای این شماره ثبت نشده.', 'fa-comment-dots'))
            + '</div></section>'
            + '<section class="adm-u360-mkt-panel adm-u360-mkt-panel--journey" aria-label="مسیر رشد">'
            + '<header class="adm-u360-mkt-panel__head"><h3 class="adm-u360-mkt-panel__title">مسیر رشد</h3>'
            + '<span class="adm-u360-mkt-panel__count">' + toFa(journeySummary.length) + '</span></header>'
            + '<div class="adm-u360-mkt-panel__body">' + journeyBody + '</div>'
            + '</section></div>';

        const foot = '<div class="adm-u360-mkt-foot adm-u360-mkt-foot--stack">'
            + '<section class="adm-u360-mkt-mini" aria-label="کمپین‌ها">'
            + '<h3 class="adm-u360-mkt-mini__title">کمپین‌ها</h3>'
            + renderMarketingCompactRows(['کمپین', 'وضعیت', 'زمان'], camps, 'کمپینی ثبت نشده')
            + '</section>'
            + '<section class="adm-u360-mkt-mini" aria-label="تخفیف‌ها">'
            + '<h3 class="adm-u360-mkt-mini__title">کدهای تخفیف</h3>'
            + renderMarketingCompactRows(['کد', 'سیاست', 'زمان'], disc, 'تخفیفی صادر نشده')
            + '</section>'
            + '<section class="adm-u360-mkt-mini" aria-label="بازگشت مشتری">'
            + '<h3 class="adm-u360-mkt-mini__title">بازگشت / منبع‌یابی</h3>'
            + renderMarketingCompactRows(['مدل', 'وضعیت', 'زمان'], attrs, 'رکوردی نیست')
            + '</section></div>';

        paintPanel('<div class="adm-u360-marketing adm-u360-marketing--pro adm-u360-marketing--stack">'
            + renderMarketingTopBar(stats, data.opt_out)
            + stage
            + foot
            + '</div>', 'marketing');
    }

    function adminLogActionTone(actionKey) {
        const k = String(actionKey || '');
        if (k === 'suspicious') return 'danger';
        if (k === 'revoke' || k === 'deactivation') return 'warn';
        if (k === 'validation') return 'info';
        if (k === 'activation' || k === 'transfer') return 'ok';
        return 'neutral';
    }

    function adminLogActionIcon(actionKey) {
        const k = String(actionKey || '');
        if (k === 'validation') return 'fa-shield-halved';
        if (k === 'activation') return 'fa-bolt';
        if (k === 'deactivation') return 'fa-power-off';
        if (k === 'revoke') return 'fa-ban';
        if (k === 'transfer') return 'fa-right-left';
        if (k === 'suspicious') return 'fa-triangle-exclamation';
        return 'fa-fingerprint';
    }

    function renderAdminLogDetailLines(lines) {
        if (!lines || !lines.length) return '';
        return '<dl class="adm-u360-alog-kv">'
            + lines.map(function (row) {
                return '<div class="adm-u360-alog-kv__row">'
                    + '<dt>' + esc(row.key) + '</dt>'
                    + '<dd>' + esc(row.value) + '</dd></div>';
            }).join('')
            + '</dl>';
    }

    function renderAdminLogRow(log) {
        const tone = adminLogActionTone(log.action_key);
        const icon = adminLogActionIcon(log.action_key);
        const metaBits = [];
        if (log.license_id) metaBits.push('لایسنس #' + toFa(log.license_id));
        if (log.license_plan) metaBits.push(esc(log.license_plan));
        if (log.license_status) metaBits.push(esc(log.license_status));
        const metaLine = metaBits.join('<span class="adm-u360-alog-row__sep" aria-hidden="true">·</span>');
        const ip = log.ip && log.ip !== '—'
            ? '<span class="adm-u360-alog-row__ip adm-u360-ltr" dir="ltr">' + esc(log.ip) + '</span>'
            : '';
        const metaHtml = [metaLine, ip].filter(Boolean).join('<span class="adm-u360-alog-row__sep" aria-hidden="true">·</span>');
        const details = (log.detail_lines || []).length
            ? '<details class="adm-u360-alog-row__more">'
                + '<summary>جزئیات فنی</summary>'
                + renderAdminLogDetailLines(log.detail_lines)
                + (log.user_agent_short && log.user_agent_short !== '—'
                    ? '<p class="adm-u360-alog-row__ua" title="' + esc(log.user_agent_short) + '">'
                        + '<span>User-Agent</span> '
                        + '<code class="adm-u360-ltr" dir="ltr">' + esc(log.user_agent_short) + '</code></p>'
                    : '')
                + '</details>'
            : '';
        return '<li class="adm-u360-alog-row adm-u360-alog-row--' + tone + '" role="listitem">'
            + '<span class="adm-u360-alog-row__rail" aria-hidden="true"><i class="fas ' + icon + '"></i></span>'
            + '<div class="adm-u360-alog-row__body">'
            + '<div class="adm-u360-alog-row__head">'
            + '<span class="adm-u360-alog-row__badge">' + esc(log.action_type) + '</span>'
            + '<time class="adm-u360-alog-row__time" datetime="' + esc(log.created_at || '') + '">'
            + esc(log.created_jalali) + '</time>'
            + '</div>'
            + '<p class="adm-u360-alog-row__summary">' + esc(log.detail_summary || '—') + '</p>'
            + (metaHtml ? '<p class="adm-u360-alog-row__meta">' + metaHtml + '</p>' : '')
            + details
            + '</div></li>';
    }

    function teardownAdminLogInfiniteScroll() {
        if (adminLogScrollObserver) {
            adminLogScrollObserver.disconnect();
            adminLogScrollObserver = null;
        }
        if (adminLogScrollEl) {
            adminLogScrollEl.removeEventListener('scroll', onAdminLogFeedScroll);
            adminLogScrollEl = null;
        }
    }

    function updateAdminLogFeedCount() {
        const countEl = panel.querySelector('.adm-u360-alog-feed__count');
        const pag = adminLogScrollState.pagination;
        if (!countEl || !pag) return;
        countEl.textContent = toFa(adminLogScrollState.loaded) + ' / ' + toFa(pag.total || adminLogScrollState.loaded);
    }

    function setAdminLogFeedLoader(on) {
        const loader = panel.querySelector('.adm-u360-alog-feed__loader');
        if (loader) loader.hidden = !on;
    }

    function updateAdminLogFeedEnd() {
        const endEl = panel.querySelector('.adm-u360-alog-feed__end');
        const pag = adminLogScrollState.pagination;
        if (!endEl || !pag) return;
        if (!pag.has_next) {
            endEl.hidden = false;
            endEl.textContent = 'پایان — ' + toFa(pag.total || adminLogScrollState.loaded) + ' رویداد';
        } else {
            endEl.hidden = true;
        }
    }

    function onAdminLogFeedScroll() {
        const el = adminLogScrollEl;
        const pag = adminLogScrollState.pagination;
        if (!el || !pag || !pag.has_next || adminLogScrollState.loading) return;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 96) {
            loadMoreAdminLogs();
        }
    }

    function loadMoreAdminLogs() {
        const pag = adminLogScrollState.pagination;
        if (!pag || !pag.has_next || adminLogScrollState.loading || activeTab !== 'admin_log') return;
        adminLogScrollState.loading = true;
        setAdminLogFeedLoader(true);
        const query = mergePanelRangeQuery(Object.assign({}, tabQueryState.admin_log || {}, {
            page: pag.page + 1,
        }));
        fetch(tabUrl('admin_log', query), {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (payload) {
                if (!payload.ok || activeTab !== 'admin_log') return;
                const chunk = payload.data || {};
                adminLogScrollState.pagination = chunk.pagination;
                const list = panel.querySelector('.adm-u360-alog-rows');
                const rows = chunk.audit_logs || [];
                if (list && rows.length) {
                    list.insertAdjacentHTML('beforeend', rows.map(renderAdminLogRow).join(''));
                    adminLogScrollState.loaded += rows.length;
                }
                updateAdminLogFeedCount();
                updateAdminLogFeedEnd();
            })
            .catch(function () {
                const endEl = panel.querySelector('.adm-u360-alog-feed__end');
                if (endEl) {
                    endEl.hidden = false;
                    endEl.classList.add('is-error');
                    endEl.textContent = 'بارگذاری بیشتر ناموفق بود — دوباره اسکرول کنید';
                }
            })
            .finally(function () {
                adminLogScrollState.loading = false;
                setAdminLogFeedLoader(false);
                window.requestAnimationFrame(maybeFillAdminLogFeed);
            });
    }

    function maybeFillAdminLogFeed() {
        const el = adminLogScrollEl;
        const pag = adminLogScrollState.pagination;
        if (!el || !pag || !pag.has_next || adminLogScrollState.loading) return;
        if (el.scrollHeight <= el.clientHeight + 8) {
            loadMoreAdminLogs();
        }
    }

    function setupAdminLogInfiniteScroll() {
        teardownAdminLogInfiniteScroll();
        const scrollRoot = panel.querySelector('[data-u360-alog-scroll]');
        const sentinel = panel.querySelector('.adm-u360-alog-feed__sentinel');
        if (!scrollRoot) return;
        adminLogScrollEl = scrollRoot;
        adminLogScrollEl.addEventListener('scroll', onAdminLogFeedScroll, { passive: true });
        if (sentinel && typeof IntersectionObserver !== 'undefined') {
            adminLogScrollObserver = new IntersectionObserver(function (entries) {
                if (entries[0] && entries[0].isIntersecting) loadMoreAdminLogs();
            }, { root: scrollRoot, rootMargin: '120px 0px', threshold: 0 });
            adminLogScrollObserver.observe(sentinel);
        }
        maybeFillAdminLogFeed();
    }

    function renderAdminLog(data) {
        teardownAdminLogInfiniteScroll();
        if (data.empty) {
            adminLogScrollState = { pagination: null, loaded: 0, loading: false };
            paintPanel(emptyState('لاگ مدیریتی نیست', data.message || 'لایسنس مرتبط با این کاربر ثبت نشده.', 'fa-history'), 'admin_log');
            return;
        }
        adminLogScrollState.pagination = data.pagination || null;
        adminLogScrollState.loaded = (data.audit_logs || []).length;
        adminLogScrollState.loading = false;
        const stats = data.stats || {};
        const selected = tabQueryState.admin_log || {};
        const days = panelRangeDaysParam();
        const rangeLabel = days === 'all' ? 'کل دوره' : toFa(days) + ' روز';
        const filters = (data.filters && data.filters.actions) || [];
        const currentKind = selected.kind || '';
        const filterOptions = [{ value: '', label: 'همه عملیات' }].concat(
            filters.map(function (a) { return { value: a.key, label: a.label }; })
        );
        const filterSelect = '<label class="adm-u360-alog-filter">'
            + '<span class="adm-u360-alog-filter__label">نوع عملیات</span>'
            + '<select class="adm-u360-alog-filter__select" data-u360-alog-filter="kind" aria-label="نوع عملیات">'
            + filterOptions.map(function (o) {
                return '<option value="' + esc(o.value) + '"' + (currentKind === o.value ? ' selected' : '') + '>'
                    + esc(o.label) + '</option>';
            }).join('') + '</select></label>'
            + '<button type="button" class="adm-u360-alog-filters__reset" data-u360-alog-reset>پاک‌سازی فیلتر</button>';

        const top = '<header class="adm-u360-alog-top" aria-label="خلاصه لاگ مدیریتی">'
            + '<div class="adm-u360-alog-top__row">'
            + '<div class="adm-u360-alog-top__brand">'
            + '<h2 class="adm-u360-alog-top__title">'
            + '<i class="fas fa-history" aria-hidden="true"></i><span>تاریخچه مدیریتی</span></h2>'
            + '<span class="adm-u360-alog-top__range">بازه · ' + esc(rangeLabel) + '</span>'
            + '</div>'
            + '<div class="adm-u360-alog-top__kpis" role="list">'
            + '<span class="adm-u360-alog-kpi" role="listitem"><span class="adm-u360-alog-kpi__l">کل رویداد</span>'
            + '<span class="adm-u360-alog-kpi__v">' + toFa(stats.total || 0) + '</span></span>'
            + '<span class="adm-u360-alog-kpi" role="listitem"><span class="adm-u360-alog-kpi__l">لایسنس</span>'
            + '<span class="adm-u360-alog-kpi__v">' + toFa(stats.license_count || 0) + '</span></span>'
            + '<span class="adm-u360-alog-kpi adm-u360-alog-kpi--info" role="listitem">'
            + '<span class="adm-u360-alog-kpi__l">اعتبارسنجی</span>'
            + '<span class="adm-u360-alog-kpi__v">' + toFa(stats.validation_count || 0) + '</span></span>'
            + '<span class="adm-u360-alog-kpi' + ((stats.suspicious_count || 0) ? ' adm-u360-alog-kpi--warn' : '') + '" role="listitem">'
            + '<span class="adm-u360-alog-kpi__l">مشکوک</span>'
            + '<span class="adm-u360-alog-kpi__v">' + toFa(stats.suspicious_count || 0) + '</span></span>'
            + '</div></div>'
            + (data.note ? '<p class="adm-u360-alog-top__note">' + esc(data.note) + '</p>' : '')
            + '<p class="adm-u360-alog-top__last">آخرین رویداد · <time>' + esc(stats.last_jalali || '—') + '</time></p>'
            + '</header>';

        const actionChart = (data.charts && data.charts.actions) || [];
        const dailyChart = (data.charts && data.charts.daily) || [];
        const viz = (actionChart.length || dailyChart.length)
            ? '<section class="adm-u360-alog-viz" aria-label="نمودارهای لاگ">'
            + (actionChart.length
                ? '<div class="adm-u360-alog-viz__card adm-u360-alog-viz__card--donut">'
                + '<h3 class="adm-u360-alog-viz__title">توزیع عملیات</h3>'
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--donut">'
                + '<canvas id="admU360AlogActions" role="img" aria-label="توزیع نوع عملیات"></canvas>'
                + '</div></div>'
                : '')
            + (dailyChart.length
                ? '<div class="adm-u360-alog-viz__card adm-u360-alog-viz__card--bar">'
                + '<h3 class="adm-u360-alog-viz__title">روند روزانه</h3>'
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--wide adm-u360-chart-wrap--alog">'
                + '<canvas id="admU360AlogDaily" role="img" aria-label="روند روزانه لاگ"></canvas>'
                + '</div></div>'
                : '')
            + '</section>'
            : '';

        const filtersBar = '<section class="adm-u360-alog-filters-bar" aria-label="فیلتر لاگ">'
            + '<div class="adm-u360-alog-filters">' + filterSelect + '</div></section>';

        const total = (data.pagination && data.pagination.total) || stats.total || adminLogScrollState.loaded;
        const logs = (data.audit_logs || []).map(renderAdminLogRow).join('');
        const feedBody = logs
            ? '<div class="adm-u360-alog-feed__scroll" data-u360-alog-scroll tabindex="0" aria-label="فهرست رویدادها — با اسکرول بارگذاری می‌شود">'
                + '<ul class="adm-u360-alog-rows" role="list">' + logs + '</ul>'
                + '<div class="adm-u360-alog-feed__sentinel" aria-hidden="true"></div>'
                + '<p class="adm-u360-alog-feed__loader" hidden>در حال بارگذاری رویدادهای بیشتر…</p>'
                + '<p class="adm-u360-alog-feed__end" hidden></p>'
                + '</div>'
            : '<div class="adm-u360-alog-feed__empty">'
                + emptyState('رویدادی با این فیلتر نیست', 'بازه یا نوع عملیات را تغییر دهید.', 'fa-filter')
                + '</div>';
        const feed = '<section class="adm-u360-alog-feed" aria-label="فهرست لاگ‌ها">'
            + '<header class="adm-u360-alog-feed__head">'
            + '<h3 class="adm-u360-alog-feed__title">رویدادهای امنیتی</h3>'
            + '<span class="adm-u360-alog-feed__count" title="نمایش‌داده‌شده از کل">'
            + toFa(adminLogScrollState.loaded) + ' / ' + toFa(total) + '</span>'
            + '</header>'
            + '<div class="adm-u360-alog-feed__body">' + feedBody + '</div>'
            + '</section>';

        paintPanel('<div class="adm-u360-alog adm-u360-alog--pro">'
            + top + filtersBar + viz + feed + '</div>', 'admin_log');

        window.requestAnimationFrame(function () {
            setupAdminLogInfiniteScroll();
            updateAdminLogFeedCount();
            updateAdminLogFeedEnd();
            if (actionChart.length) mountDoughnut('admU360AlogActions', actionChart);
            if (dailyChart.length) {
                mountBarActivity('admU360AlogDaily', dailyChart.map(function (p) {
                    return { date: p.label || p.date, count: p.count };
                }));
            }
        });
    }

    function renderWorkspace(data) {
        const crm = data.crm || {};
        const stats = data.stats || {};
        const chartRows = (data.charts && data.charts.crm_contacts_status) || [];
        const contacts = (crm.recent_contacts || []).slice(0, 12);
        const datasets = data.datasets || [];
        const pager = datasets.length ? renderPager(data.datasets_pagination, 'workspace') : '';

        const crmRank = chartRows.length
            ? '<section class="adm-u360-ws-panel adm-u360-ws-panel--chart" aria-label="وضعیت مخاطبین">'
                + '<header class="adm-u360-ws-panel__head">'
                + '<h3 class="adm-u360-ws-panel__title">پراکندگی وضعیت مخاطبین</h3>'
                + '</header>'
                + '<div class="adm-u360-ws-panel__body">' + renderUsageRankChart(chartRows) + '</div>'
                + '</section>'
            : '';

        const contactBody = contacts.length
            ? '<ul class="adm-u360-ws-contacts" role="list">' + contacts.map(renderWorkspaceContactRow).join('') + '</ul>'
            : emptyState('مخاطبی ثبت نشده', 'این کاربر هنوز مخاطب CRM نساخته است.', 'fa-address-book');

        const datasetBody = datasets.length
            ? '<ul class="adm-u360-ws-datasets" role="list">' + datasets.map(renderWorkspaceDatasetRow).join('') + '</ul>'
            : emptyState('دیتاست فعالی نیست', 'فایل/بانک آگهی برای این حساب ثبت نشده است.', 'fa-database');

        const stage = '<div class="adm-u360-ws-stage">'
            + crmRank
            + '<div class="adm-u360-ws-columns">'
            + '<section class="adm-u360-ws-panel" aria-label="آخرین مخاطبین">'
            + '<header class="adm-u360-ws-panel__head">'
            + '<h3 class="adm-u360-ws-panel__title">آخرین مخاطبین</h3>'
            + '<span class="adm-u360-ws-panel__count">' + toFa(contacts.length) + '</span>'
            + '</header>'
            + '<div class="adm-u360-ws-panel__body">' + contactBody + '</div>'
            + '</section>'
            + '<section class="adm-u360-ws-panel" aria-label="دیتاست‌ها">'
            + '<header class="adm-u360-ws-panel__head">'
            + '<h3 class="adm-u360-ws-panel__title">دیتاست‌ها</h3>'
            + '<span class="adm-u360-ws-panel__count">' + toFa(stats.datasets_total || datasets.length) + '</span>'
            + '</header>'
            + '<div class="adm-u360-ws-panel__body">' + datasetBody
            + (pager ? '<footer class="adm-u360-ws-panel__foot">' + pager + '</footer>' : '')
            + '</div></section>'
            + '</div></div>';

        paintPanel('<div class="adm-u360-workspace adm-u360-workspace--pro">'
            + renderWorkspaceTopBar(stats, data.note_team_data)
            + stage
            + '</div>', 'workspace');
    }

    function renderDevicesPlatformSummary(flags, androidDevices) {
        const f = flags || {};
        const androidCount = (androidDevices || []).length;
        const winList = '<ul class="adm-u360-devices-checklist" role="list">'
            + renderDeviceCheckRow(
                'دریافت نصب‌کننده',
                !!f.downloaded,
                f.downloaded ? 'در سیستم ثبت شده' : 'در لاگ دانلود نیست'
            )
            + renderDeviceCheckRow(
                'فعال‌سازی روی ویندوز',
                !!f.activated,
                f.activated ? 'حداقل یک‌بار انجام شده' : 'هنوز ثبت نشده'
            )
            + renderDeviceCheckRow(
                'اجرای برنامه',
                !!f.first_launch,
                f.first_launch ? 'حداقل یک‌بار اجرا شده' : 'هنوز ثبت نشده'
            )
            + '</ul>';
        const andList = '<ul class="adm-u360-devices-checklist" role="list">'
            + renderDeviceCheckRow(
                'دستگاه‌های متصل',
                androidCount > 0,
                androidCount > 0
                    ? toFa(androidCount) + ' دستگاه'
                    : 'اپ نصب یا ورود ثبت نشده'
            )
            + '</ul>';
        return '<section class="adm-u360-devices-summary" aria-label="خلاصه نرم‌افزارها">'
            + '<header class="adm-u360-devices-summary__head">'
            + '<h2 class="adm-u360-devices-summary__title">نرم‌افزارهای مشتری</h2>'
            + '<p class="adm-u360-devices-summary__lead">بر اساس لاگ دانلود، فعال‌سازی لایسنس و ثبت دستگاه در سیستم.</p>'
            + '</header>'
            + '<div class="adm-u360-devices-platform">'
            + '<h3 class="adm-u360-devices-platform__title"><i class="fas fa-desktop" aria-hidden="true"></i>'
            + '<span>ویندوز</span></h3>'
            + winList
            + '</div>'
            + '<div class="adm-u360-devices-platform">'
            + '<h3 class="adm-u360-devices-platform__title"><i class="fas fa-mobile-screen" aria-hidden="true"></i>'
            + '<span>اندروید</span></h3>'
            + andList
            + '</div></section>';
    }

    function renderOverviewKeyStatusRow(h, sub, pay, warnCount) {
        const eng = h.engagement || {};
        const winValue = formatWindowsEngagement(eng);
        const androidValue = formatAndroidEngagement(eng);
        const accessTone = sub.has_access ? 'ok' : (pay.pending_orders ? 'warn' : '');
        const accessValue = sub.has_access
            ? esc(sub.access_label || 'فعال') + (sub.plan ? ' · ' + esc(sub.plan) : '')
            : esc(sub.access_label || 'بدون دسترسی فعال');
        const cols = [
            {
                icon: 'fa-circle-check',
                title: 'دسترسی',
                value: accessValue,
                meta: 'انقضا ' + esc(sub.expires_jalali || '—'),
                tab: 'licenses',
                tone: accessTone,
            },
            {
                icon: 'fa-desktop',
                title: 'ویندوز',
                value: winValue,
                meta: 'آخرین ورود ' + esc(eng.last_login_jalali || '—'),
                tab: 'devices',
                tone: eng.windows_launched ? 'ok' : '',
            },
            {
                icon: 'fa-mobile-screen',
                title: 'اندروید',
                value: androidValue,
                meta: eng.days_since_login != null
                    ? toFa(eng.days_since_login) + ' روز از آخرین ورود'
                    : '—',
                tab: 'devices',
                tone: eng.android_installed ? 'ok' : '',
            },
        ];
        const leadText = warnCount
            ? toFa(warnCount) + ' مورد هشدار در بینش‌های موجود؛ برای جزئیات بخش اولویت‌ها را بررسی کنید.'
            : (pay.pending_orders
                ? toFa(pay.pending_orders) + ' سفارش در انتظار بررسی است.'
                : 'نمای کلی بر اساس اطلاعات ثبت‌شده؛ نبود هشدار به معنی تأیید قطعی سلامت حساب نیست.');
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-keystatus" aria-label="وضعیت کلیدی">'
            + '<header class="adm-u360-overview-keystatus__head">'
            + '<h2 class="adm-u360-overview-keystatus__title">وضعیت کلیدی</h2>'
            + '</header>'
            + '<div class="adm-u360-keystatus-grid" role="list">'
            + cols.map(function (c) {
                const tone = c.tone ? ' adm-u360-keystatus-col--' + c.tone : '';
                return '<article class="adm-u360-keystatus-col' + tone + '" role="listitem">'
                    + '<span class="adm-u360-keystatus-col__icon" aria-hidden="true"><i class="fas ' + c.icon + '"></i></span>'
                    + '<span class="adm-u360-keystatus-col__title">' + esc(c.title) + '</span>'
                    + '<strong class="adm-u360-keystatus-col__value">' + c.value + '</strong>'
                    + '<span class="adm-u360-keystatus-col__meta">' + c.meta + '</span>'
                    + overviewJumpChip('مشاهده', c.tab, 'fa-arrow-left')
                    + '</article>';
            }).join('')
            + '</div>'
            + '<p class="adm-u360-overview-keystatus__note">' + esc(leadText) + '</p>'
            + '</section>';
    }

    function overviewHealthBanner(warnCount, sub, pay) {
        let tone = 'neutral';
        let badge = 'پرونده آماده بررسی';
        if (warnCount) {
            tone = 'warn';
            badge = 'نیاز به پیگیری';
        } else if (pay.pending_orders) {
            tone = 'info';
            badge = 'سفارش در انتظار';
        } else if (sub.has_access) {
            tone = 'ok';
            badge = 'دسترسی فعال';
        }
        const leadText = warnCount
            ? toFa(warnCount) + ' مورد هشدار در بینش‌های موجود؛ برای جزئیات بخش اولویت‌ها را بررسی کنید.'
            : (pay.pending_orders
                ? toFa(pay.pending_orders) + ' سفارش در انتظار بررسی است.'
                : 'نمای کلی بر اساس اطلاعات ثبت‌شده؛ نبود هشدار به معنی تأیید قطعی سلامت حساب نیست.');
        return '<header class="adm-u360-overview-hero adm-u360-overview-hero--' + tone + '">'
            + '<div class="adm-u360-overview-hero__status">'
            + '<span class="adm-u360-overview-hero__dot" aria-hidden="true"></span>'
            + '<span class="adm-u360-overview-hero__badge">' + esc(badge) + '</span>'
            + '</div>'
            + '<p class="adm-u360-overview-hero__lead">' + esc(leadText) + '</p>'
            + '</header>';
    }

    function renderOverviewSignals(h) {
        const pay = h.payments || {};
        const sub = h.subscription || {};
        const eng = h.engagement || {};
        const signals = [];
        if (h.last_order_product) {
            signals.push({
                icon: 'fa-receipt',
                tone: 'ok',
                title: 'آخرین خرید موفق',
                value: esc(h.last_order_product),
                meta: esc(h.last_paid_jalali || '—'),
                tab: 'commerce',
            });
        }
        if (h.last_ticket_subject) {
            signals.push({
                icon: 'fa-headset',
                tone: h.tickets_open ? 'warn' : '',
                title: 'آخرین تیکت',
                value: esc(h.last_ticket_subject),
                meta: esc(h.last_ticket_at_jalali || '—'),
                tab: 'support',
            });
        }
        if (sub.plan) {
            signals.push({
                icon: 'fa-key',
                tone: sub.has_access ? 'ok' : (sub.pending_activation ? 'warn' : ''),
                title: 'اشتراک',
                value: esc(sub.access_label || '—') + (sub.plan ? ' · ' + esc(sub.plan) : ''),
                meta: 'انقضا ' + esc(sub.expires_jalali || '—'),
                tab: 'licenses',
            });
        }
        signals.push({
            icon: 'fa-desktop',
            tone: eng.windows_launched ? 'ok' : '',
            title: 'ویندوز',
            value: formatWindowsEngagement(eng),
            meta: 'آخرین ورود ' + esc(eng.last_login_jalali || '—'),
            tab: 'devices',
        });
        signals.push({
            icon: 'fa-mobile-screen',
            tone: eng.android_installed ? 'ok' : '',
            title: 'اندروید',
            value: formatAndroidEngagement(eng),
            meta: eng.days_since_login != null
                ? toFa(eng.days_since_login) + ' روز از آخرین ورود'
                : '—',
            tab: 'devices',
        });
        if (pay.pending_orders) {
            signals.push({
                icon: 'fa-hourglass-half',
                tone: 'warn',
                title: 'سفارش معلق',
                value: toFa(pay.pending_orders) + ' مورد',
                meta: 'پیگیری در تب خریدها',
                tab: 'commerce',
            });
        }
        return '<div class="adm-u360-signals" role="list">'
            + signals.map(function (s) {
                const tone = s.tone ? ' adm-u360-signal--' + s.tone : '';
                return '<article class="adm-u360-signal' + tone + '" role="listitem">'
                    + '<span class="adm-u360-signal__icon" aria-hidden="true"><i class="fas ' + s.icon + '"></i></span>'
                    + '<div class="adm-u360-signal__body">'
                    + '<span class="adm-u360-signal__title">' + esc(s.title) + '</span>'
                    + '<strong class="adm-u360-signal__value">' + s.value + '</strong>'
                    + '<span class="adm-u360-signal__meta">' + s.meta + '</span>'
                    + '</div>'
                    + overviewJumpChip('جزئیات', s.tab, 'fa-arrow-left')
                    + '</article>';
            }).join('')
            + '</div>';
    }

    function renderOverview(data) {
        const h = data.highlights || {};
        const pay = h.payments || {};
        const sub = h.subscription || {};
        const insights = data.insights || [];
        const warnCount = insights.filter(function (i) { return i.severity === 'warn'; }).length;

        const recentOrders = (data.recent_orders || []).slice(0, 5);
        const recentLicenses = (data.recent_licenses || []).slice(0, 5);

        const charts = data.charts || {};
        const splitRow = '<div class="adm-u360-overview-split">'
            + '<div class="adm-u360-overview-split__metrics">' + renderPrimaryKpisSection() + '</div>'
            + '<div class="adm-u360-overview-split__insights">' + renderOverviewInsightsAside(insights) + '</div>'
            + '</div>';
        const keyStatusHtml = renderOverviewKeyStatusRow(h, sub, pay, warnCount);
        const overviewFoot = '<div class="adm-u360-overview-foot adm-u360-overview-foot--split">'
            + renderOverviewFinanceCard(charts, pay)
            + renderOverviewRecentCard(recentOrders, recentLicenses)
            + '</div>';

        paintPanel(
            '<div class="adm-u360-overview adm-u360-overview--mock">'
            + splitRow
            + keyStatusHtml
            + overviewFoot
            + '</div>',
            'overview'
        );

        window.requestAnimationFrame(function () {
            mountOverviewDoughnut('admU360ChartOrders', charts.orders_by_status);
            mountOverviewRevenueChart('admU360ChartRevenue', charts.revenue_monthly);
        });
    }

    function accountFlag(ok, okText, noText) {
        if (ok) {
            return '<span class="adm-u360-account-flag adm-u360-account-flag--ok">' + esc(okText) + '</span>';
        }
        return '<span class="adm-u360-account-flag">' + esc(noText) + '</span>';
    }

    function accountFieldRow(field) {
        const ltr = field.ltr ? ' adm-u360-ltr' : '';
        const full = field.full ? ' adm-u360-account-field--full' : '';
        const meta = field.meta
            ? '<span class="adm-u360-account-field__meta">' + field.meta + '</span>'
            : '';
        // Copy only explicitly whitelisted, non-sensitive account values.
        const copy = field.copyValue
            ? '<button type="button" class="adm-u360-account-copy" data-u360-account-copy="' + encodeURIComponent(String(field.copyValue)) + '" aria-label="کپی ' + esc(field.label) + '"><i class="fas fa-copy" aria-hidden="true"></i><span>کپی</span></button>'
            : '';
        return '<div class="adm-u360-account-field' + full + '" role="listitem">'
            + '<span class="adm-u360-account-field__icon" aria-hidden="true"><i class="fas ' + field.icon + '"></i></span>'
            + '<span class="adm-u360-account-field__label">' + esc(field.label) + '</span>'
            + '<div class="adm-u360-account-field__main">'
            + '<span class="adm-u360-account-field__value' + ltr + '">' + field.value + '</span>'
            + meta + copy
            + '</div></div>';
    }

    function renderAccountGroup(group) {
        return '<section class="adm-u360-account-group adm-u360-block adm-u360-block--card adm-u360-account-group--card">'
            + '<h3 class="adm-u360-account-group__title">'
            + '<i class="fas ' + group.icon + '" aria-hidden="true"></i>'
            + '<span>' + esc(group.title) + '</span></h3>'
            + '<div class="adm-u360-account-fields" role="list">'
            + group.fields.map(accountFieldRow).join('')
            + '</div></section>';
    }

    function renderAccountProfile(d, sens, perms) {
        const id = d.identity || {};
        const profile = d.profile || {};
        const referral = d.referral || {};
        const fullName = ((id.first_name || '') + ' ' + (id.last_name || '')).trim();

        let nationalToolbar = '';
        if (perms.can_reveal_national_id && sens.national_id_masked && sens.national_id_present) {
            nationalToolbar = ' <button type="button" class="adm-u360-account-reveal" id="admU360RevealNational">نمایش کامل</button>';
        }

        const phoneMeta = id.phone_verified && id.phone_verified_at_jalali
            ? esc('تأیید در ' + id.phone_verified_at_jalali)
            : (id.phone_verified ? '' : esc('هنوز تأیید نشده'));

        const smsMeta = id.marketing_sms_opt_out && id.marketing_sms_opt_out_at_jalali
            ? esc('ثبت در ' + id.marketing_sms_opt_out_at_jalali)
            : '';

        const statusFields = [
            {
                icon: 'fa-user-check',
                label: 'وضعیت حساب',
                value: accountFlag(id.is_active, 'فعال', 'غیرفعال'),
            },
            {
                icon: 'fa-mobile-screen-button',
                label: 'تأیید موبایل',
                value: accountFlag(id.phone_verified, 'تأیید‌شده', 'تأیید نشده'),
                meta: phoneMeta,
            },
            {
                icon: 'fa-calendar-plus',
                label: 'تاریخ عضویت',
                value: esc(id.date_joined_jalali || '—'),
            },
            {
                icon: 'fa-right-to-bracket',
                label: 'آخرین ورود',
                value: esc(id.last_login_jalali || '—'),
            },
            {
                icon: 'fa-comment-sms',
                label: 'پیامک تبلیغاتی',
                value: accountFlag(!id.marketing_sms_opt_out, 'دریافت مجاز', 'عدم دریافت'),
                meta: smsMeta,
            },
        ];
        if (id.is_staff) {
            statusFields.push({
                icon: 'fa-user-gear',
                label: 'دسترسی کارمند',
                value: '<span class="adm-u360-account-flag adm-u360-account-flag--accent">فعال</span>',
            });
        }
        if (id.is_affiliate) {
            statusFields.push({
                icon: 'fa-handshake',
                label: 'همکاری در فروش',
                value: accountFlag(true, 'فعال', 'غیرفعال'),
            });
        }

        const groups = [
            {
                title: 'هویت و تماس',
                icon: 'fa-address-card',
                fields: [
                    { icon: 'fa-user', label: 'نام و نام خانوادگی', value: esc(fullName || '—') },
                    { icon: 'fa-phone', label: 'موبایل', value: esc(id.phone || '—'), ltr: true, copyValue: id.phone },
                    { icon: 'fa-envelope', label: 'ایمیل', value: id.email ? esc(id.email) : '—', ltr: true, copyValue: id.email },
                    { icon: 'fa-at', label: 'نام کاربری', value: esc(id.username || '—'), ltr: true, copyValue: id.username },
                    {
                        icon: 'fa-fingerprint',
                        label: 'کد ملی',
                        value: esc(id.national_id || '—') + nationalToolbar,
                        ltr: true,
                    },
                    { icon: 'fa-user-tag', label: 'معرف', value: esc(referral.referred_by || '—') },
                    { icon: 'fa-hashtag', label: 'شناسه کاربر', value: toFa(id.id), copyValue: id.id == null ? '' : String(id.id) },
                ],
            },
            {
                title: 'وضعیت حساب',
                icon: 'fa-shield-halved',
                fields: statusFields,
            },
            {
                title: 'پروفایل تکمیلی',
                icon: 'fa-location-dot',
                fields: [
                    { icon: 'fa-city', label: 'شهر', value: esc(profile.city || '—') },
                    {
                        icon: 'fa-mailbox',
                        label: 'کد پستی',
                        value: profile.postal_code
                            ? '<span class="adm-u360-ltr">' + esc(profile.postal_code) + '</span>'
                            : '—',
                        copyValue: profile.postal_code,
                    },
                    {
                        icon: 'fa-map-location-dot',
                        label: 'آدرس',
                        value: esc(profile.address || '—'),
                        full: true,
                    },
                    {
                        icon: 'fa-image',
                        label: 'آواتار',
                        value: accountFlag(profile.has_avatar, 'دارد', 'ندارد'),
                    },
                    {
                        icon: 'fa-align-right',
                        label: 'درباره من',
                        value: profile.bio ? esc(profile.bio) : '—',
                        full: true,
                    },
                ],
            },
        ];

        return '<section class="adm-u360-account-profile" aria-label="حساب کاربری">'
            + '<div class="adm-u360-account-profile__stack">'
            + groups.map(renderAccountGroup).join('')
            + '</div></section>';
    }

    function renderAccount(d) {
        const sens = d.sensitive || {};
        const perms = bootstrap.permissions || {};
        paintPanel(
            '<div class="adm-u360-account">' + renderAccountProfile(d, sens, perms) + '</div>',
            'account'
        );
        const copyButtons = panel.querySelectorAll('[data-u360-account-copy]');
        copyButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                if (!navigator.clipboard || !navigator.clipboard.writeText) return;
                const value = decodeURIComponent(button.getAttribute('data-u360-account-copy') || '');
                navigator.clipboard.writeText(value).then(function () {
                    const label = button.querySelector('span');
                    if (label) label.textContent = 'کپی شد';
                    button.setAttribute('aria-label', 'کپی شد');
                }).catch(function () {});
            });
        });
        const revealBtn = document.getElementById('admU360RevealNational');
        if (revealBtn) {
            revealBtn.addEventListener('click', function () {
                loadTab('account', { reveal_sensitive: '1' }, true);
            });
        }
    }

    function shortUuid(id) {
        if (!id) return '—';
        const raw = String(id).trim();
        const compact = raw.length > 18
            ? raw.slice(0, 8) + '…' + raw.slice(-8)
            : raw;
        return '<span class="adm-u360-ltr adm-u360-id" dir="ltr" title="' + esc(raw) + '">'
            + esc(compact) + '</span>';
    }

    function renderLicenseOrderLine(lic) {
        const o = lic.order;
        const oid = (o && o.id) || lic.order_id;
        if (!oid) return '';
        const bits = ['<div class="adm-u360-lic-manage__order adm-u360-lic-manage__order--lite">'
            + '<span class="adm-u360-lic-manage__order-label">سفارش</span>'];
        bits.push(shortUuid(oid));
        if (o && o.sequence) {
            bits.push('<span class="adm-u360-lic-manage__order-seq">کلید ' + toFa(o.sequence) + '</span>');
        }
        if (o && o.product) {
            bits.push('<span class="adm-u360-lic-manage__order-product">' + esc(o.product) + '</span>');
        }
        if (o && o.status) {
            bits.push(orderStatusChip(o.status, o.status_label));
        }
        if (o && o.paid_jalali) {
            bits.push('<time class="adm-u360-lic-manage__order-time">پرداخت ' + esc(o.paid_jalali) + '</time>');
        } else if (o && o.created_jalali) {
            bits.push('<time class="adm-u360-lic-manage__order-time">' + esc(o.created_jalali) + '</time>');
        }
        bits.push('<button type="button" class="adm-u360-jump-chip adm-u360-jump-chip--quiet" data-u360-tab-jump="commerce">'
            + 'مالی</button>');
        bits.push('</div>');
        return bits.join('');
    }

    function licenseStatItem(label, value, extraClass) {
        const val = value || '—';
        return '<li class="adm-u360-lic-manage__stat' + (extraClass ? ' ' + extraClass : '') + '">'
            + '<span class="adm-u360-lic-manage__stat-k">' + esc(label) + '</span>'
            + '<span class="adm-u360-lic-manage__stat-v adm-u360-ltr" dir="ltr">' + esc(val) + '</span>'
            + '</li>';
    }

    function renderLicenseMetaStrip(lic) {
        return '<ul class="adm-u360-lic-manage__stats" role="list">'
            + licenseStatItem('اسلات', toFa(lic.slots_used || 0) + '/' + toFa(lic.max_activations || 0))
            + licenseStatItem('صدور', lic.created_jalali || '—')
            + licenseStatItem('نقش', lic.relation || '—')
            + '</ul>';
    }

    function orderStatusChip(status, label) {
        const tones = {
            paid: 'ok',
            granted: 'accent',
            pending: 'warn',
            pending_verification: 'warn',
            failed: 'danger',
            cancelled: 'muted',
        };
        const mod = tones[status] || 'muted';
        return '<span class="adm-u360-order-chip adm-u360-order-chip--' + mod + '">' + esc(label || status || '—') + '</span>';
    }

    function licenseStatusChip(status, label, entitled) {
        const tones = {
            active: 'ok',
            expired: 'danger',
            suspended: 'warn',
            revoked: 'danger',
            pending: 'warn',
        };
        let mod = tones[status] || 'muted';
        if (entitled) {
            mod = 'ok';
        }
        return '<span class="adm-u360-order-chip adm-u360-order-chip--' + mod + '">' + esc(label || status || '—') + '</span>';
    }

    function boolChip(ok, okText, noText) {
        return '<span class="adm-u360-order-chip adm-u360-order-chip--' + (ok ? 'ok' : 'muted') + '">'
            + esc(ok ? okText : noText) + '</span>';
    }

    function commerceCard(title, icon, body, mod) {
        const extra = mod ? ' ' + mod : '';
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-commerce-card' + extra + '">'
            + subTitle(title, icon)
            + '<div class="adm-u360-commerce-card__body">' + body + '</div></section>';
    }

    function renderCommerceFinanceCard(sum, charts) {
        charts = charts || {};
        sum = sum || {};
        const orders = charts.orders_by_status || [];
        const revenue = charts.revenue_monthly || [];
        

        const orderTotal = chartRowsSum(orders, 'count');
        const revenueSum = chartRowsSum(revenue, 'total');
        const lastMonth = revenue.length ? revenue[revenue.length - 1] : null;

        let panels = '<div class="adm-u360-finance-panels">';
        if (orders.length) {
            panels += '<div class="adm-u360-finance-panel adm-u360-finance-panel--mix">'
                + '<div class="adm-u360-finance-panel__head">'
                + '<h3 class="adm-u360-finance-panel__title">ترکیب سفارش‌ها</h3>'
                + '<span class="adm-u360-finance-panel__meta">' + toFa(orderTotal) + ' سفارش</span>'
                + '</div>'
                + '<div class="adm-u360-finance-panel__split">'
                + renderFinanceOrderLegend(orders)
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--donut adm-u360-chart-wrap--finance">'
                + '<canvas id="admU360CommerceChartOrders" role="img" aria-label="ترکیب سفارش‌ها"></canvas></div>'
                + '</div></div>';
        }
        if (revenue.length) {
            panels += '<div class="adm-u360-finance-panel adm-u360-finance-panel--revenue">'
                + '<div class="adm-u360-finance-panel__head">'
                + '<h3 class="adm-u360-finance-panel__title">درآمد پرداخت‌شده</h3>'
                + '<span class="adm-u360-finance-panel__meta">۶ ماه اخیر</span>'
                + '</div>'
                + '<p class="adm-u360-finance-panel__summary">'
                + '<span>جمع دوره <strong>' + moneyTomans(revenueSum) + '</strong></span>'
                + (lastMonth
                    ? '<span class="adm-u360-finance-panel__summary-sep" aria-hidden="true">·</span>'
                        + '<span>آخرین ماه <strong>' + moneyTomans(lastMonth.total) + '</strong></span>'
                    : '')
                + '</p>'
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--wide adm-u360-chart-wrap--finance">'
                + '<canvas id="admU360CommerceChartRevenue" role="img" aria-label="درآمد پرداخت‌شده"></canvas></div>'
                + '</div>';
        }
        panels += '</div>';

        const stats = '<dl class="adm-u360-finance-stats adm-u360-finance-stats--commerce">'
            + '<div class="adm-u360-finance-stat adm-u360-finance-stat--emph"><dt>درآمد پرداخت‌شده</dt><dd>'
            + moneyTomans(sum.total_revenue_paid_only || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>سفارش پرداخت‌شده</dt><dd>' + toFa(sum.paid_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>در انتظار</dt><dd class="'
            + (sum.pending_orders ? 'adm-u360-finance-stat__val--warn' : '')
            + '">' + toFa(sum.pending_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>هدیه / اعطایی</dt><dd>' + toFa(sum.granted_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>ناموفق / لغو</dt><dd class="'
            + (sum.failed_orders ? 'adm-u360-finance-stat__val--warn' : '')
            + '">' + toFa(sum.failed_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>کل سفارش‌ها</dt><dd>' + toFa(sum.total_orders || 0) + '</dd></div>'
            + '</dl>';

        const note = sum.note
            ? '<p class="adm-u360-commerce-note"><i class="fas fa-circle-info" aria-hidden="true"></i> ' + esc(sum.note) + '</p>'
            : '';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-finance adm-u360-commerce-summary" aria-label="خلاصه مالی">'
            + '<header class="adm-u360-overview-finance__head">'
            + '<h2 class="adm-u360-overview-finance__title">'
            + '<i class="fas fa-chart-line" aria-hidden="true"></i>'
            + '<span>خلاصه مالی</span></h2>'
            + '<p class="adm-u360-overview-finance__lead">فقط پرداخت‌های موفق در درآمد محاسبه شده‌اند؛ هدیه و سفارش در انتظار جدا هستند.</p>'
            + '</header>'
            + '<div class="adm-u360-overview-finance__body">'
            + stats
            + panels
            + note
            + '</div></section>';
    }

    function renderCommerceOrdersCard(orders, pagination) {
        const rows = (orders || []).map(function (o) {
            let productHtml = '<div class="adm-u360-commerce-product">'
                + '<span class="adm-u360-commerce-product__name">' + esc(o.product) + '</span>'
                + '<span class="adm-u360-commerce-product__plan">' + esc(o.plan) + '</span>';
            if (o.is_renewal) {
                productHtml += '<span class="adm-u360-commerce-tag">تمدید</span>';
            }
            if (o.discount_code) {
                productHtml += '<span class="adm-u360-commerce-tag adm-u360-commerce-tag--code adm-u360-ltr">'
                    + esc(o.discount_code) + '</span>';
            }
            productHtml += '</div>';
            let amountHtml = '<span class="adm-u360-commerce-amount">' + moneyTomans(o.amount) + '</span>';
            if (o.discount_amount) {
                amountHtml += '<small class="adm-u360-cell-sub">تخفیف ' + moneyTomans(o.discount_amount) + '</small>';
            }
            let fulfillHtml = esc(o.fulfillment_status);
            if (o.fulfillment_error) {
                fulfillHtml += '<small class="adm-u360-cell-sub adm-u360-cell-sub--warn" title="' + esc(o.fulfillment_error) + '">'
                    + esc(o.fulfillment_error.slice(0, 42)) + (o.fulfillment_error.length > 42 ? '…' : '')
                    + '</small>';
            }
            return '<tr>'
                + td(shortUuid(o.id), 'شناسه')
                + td(productHtml, 'محصول')
                + td(amountHtml, 'مبلغ')
                + td(esc(o.payment_method || '—'), 'روش پرداخت')
                + td(orderStatusChip(o.status, o.status_label), 'وضعیت')
                + td(fulfillHtml, 'تکمیل')
                + td(esc(o.paid_jalali || '—'), 'پرداخت')
                + td(esc(o.created_jalali), 'ثبت')
                + '</tr>';
        }).join('');

        const table = miniTable(
            ['شناسه', 'محصول', 'مبلغ', 'روش', 'وضعیت', 'تکمیل', 'پرداخت', 'ثبت'],
            rows,
            'adm-u360-commerce-table'
        );
        const pager = renderPager(pagination, 'commerce');
        const meta = '<p class="adm-u360-commerce-card__meta">'
            + toFa((pagination && pagination.total) || 0) + ' سفارش در پرونده؛ مبالغ به تومان</p>';
        return commerceCard('سفارش‌ها', 'fa-receipt', meta + table + pager, 'adm-u360-commerce-card--orders');
    }

    function renderCommerceTransactionsCard(transactions) {
        const rows = (transactions || []).map(function (t) {
            return '<tr>'
                + td(shortUuid(t.order_id), 'سفارش')
                + td('<span class="adm-u360-ltr">' + esc(t.gateway_ref || '—') + '</span>', 'مرجع درگاه')
                + td(moneyTomans(t.amount), 'مبلغ')
                + td(orderStatusChip(t.status, transactionStatusDisplayLabel(t)), 'وضعیت')
                + td(esc(t.created_jalali), 'زمان')
                + '</tr>';
        }).join('');
        const body = rows
            ? miniTable(['سفارش', 'مرجع', 'مبلغ', 'وضعیت', 'زمان'], rows, 'adm-u360-commerce-table adm-u360-commerce-table--compact')
            : emptyState('تراکنش درگاهی ثبت نشده', 'پس از پرداخت آنلاین اینجا نمایش داده می‌شود.');
        return commerceCard('تراکنش‌های درگاه', 'fa-credit-card', body, 'adm-u360-commerce-card--txn');
    }

    function renderCommerceCardTransfersCard(cardTransfers) {
        const rows = (cardTransfers || []).map(function (c) {
            return '<tr>'
                + td(shortUuid(c.order_id), 'سفارش')
                + td(orderStatusChip(c.status, c.status_label), 'وضعیت')
                + td(esc(c.submitted_jalali), 'ثبت')
                + td(esc(c.reviewed_jalali || '—'), 'بررسی')
                + '</tr>';
        }).join('');
        const body = rows
            ? miniTable(['سفارش', 'وضعیت', 'ثبت', 'بررسی'], rows, 'adm-u360-commerce-table adm-u360-commerce-table--compact')
            : emptyState('رسید کارت‌به‌کارت ندارد', 'درخواست‌های کارت‌به‌کارت این کاربر اینجا لیست می‌شود.');
        return commerceCard('کارت‌به‌کارت', 'fa-building-columns', body, 'adm-u360-commerce-card--cardpay');
    }

    function renderCommerce(d) {
        const sum = d.summary || {};
        const charts = d.charts || {};
        const summaryHtml = renderCommerceFinanceCard(sum, charts);
        const html = '<div class="adm-u360-commerce">'
            + (summaryHtml || '')
            + '<div class="adm-u360-commerce__grid">'
            + renderCommerceOrdersCard(d.orders, d.pagination)
            + '<div class="adm-u360-commerce__stack">'
            + renderCommerceTransactionsCard(d.transactions)
            + renderCommerceCardTransfersCard(d.card_transfers)
            + '</div></div></div>';

        paintPanel(html, 'commerce');
        window.requestAnimationFrame(function () {
            mountOverviewDoughnut('admU360CommerceChartOrders', charts.orders_by_status);
            mountOverviewRevenueChart('admU360CommerceChartRevenue', charts.revenue_monthly);
        });
    }

    function licenseKvRow(label, valueHtml, mod) {
        const modClass = mod ? ' adm-u360-license-kv__row--' + mod : '';
        return '<div class="adm-u360-license-kv__row' + modClass + '">'
            + '<dt>' + esc(label) + '</dt><dd>' + valueHtml + '</dd></div>';
    }

    function renderLicenseAccessChip(access) {
        const label = esc(access.access_label || '—');
        if (access.has_bot_access) {
            return '<span class="adm-u360-order-chip adm-u360-order-chip--ok">' + label + '</span>';
        }
        if (access.pending_activation) {
            return '<span class="adm-u360-order-chip adm-u360-order-chip--warn">' + label + '</span>';
        }
        return '<span class="adm-u360-order-chip adm-u360-order-chip--muted">' + label + '</span>';
    }

    function renderLicenseAccessCard(access) {
        access = access || {};
        const pending = !!access.pending_activation;
        const kv = '<dl class="adm-u360-license-kv">'
            + licenseKvRow('دسترسی ربات', renderLicenseAccessChip(access), 'primary')
            + licenseKvRow('پلن', esc(access.plan || '—'))
            + licenseKvRow('انقضا', esc(access.expires_jalali || '—'))
            + licenseKvRow('لایسنس', toFa(access.license_count || 0))
            + licenseKvRow('دستگاه فعال', toFa(access.activations_active || 0) + ' / ' + toFa(access.activations_total || 0))
            + licenseKvRow('فعال‌سازی معلق', boolChip(!pending, 'خیر', 'بله'))
            + '</dl>';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-license-summary adm-u360-license-summary--minimal" aria-label="دسترسی و اشتراک">'
            + '<header class="adm-u360-license-summary__head">'
            + '<h2 class="adm-u360-license-summary__title"><span>دسترسی و اشتراک</span></h2>'
            + '</header>'
            + kv
            + '</section>';
    }

    function renderLicenseListItem(l) {
        const relation = l.relation
            ? '<span class="adm-u360-license-row__tag">' + esc(l.relation) + '</span>'
            : '';
        return '<li class="adm-u360-license-row' + (l.entitlement_valid ? ' adm-u360-license-row--valid' : '') + '" role="listitem">'
            + '<div class="adm-u360-license-row__main">'
            + '<span class="adm-u360-license-row__plan">' + esc(l.plan || '—') + '</span>'
            + relation
            + licenseStatusChip(l.status, l.status_label, l.entitlement_valid)
            + '</div>'
            + '<div class="adm-u360-license-row__meta">'
            + '<span class="adm-u360-license-row__id">#' + toFa(l.id) + '</span>'
            + '<span class="adm-u360-license-row__sep" aria-hidden="true">·</span>'
            + '<span>' + toFa(l.slots_used) + '/' + toFa(l.max_activations) + ' اسلات</span>'
            + '<span class="adm-u360-license-row__sep" aria-hidden="true">·</span>'
            + '<span>انقضا ' + esc(l.expires_jalali || '—') + '</span>'
            + '<span class="adm-u360-license-row__sep" aria-hidden="true">·</span>'
            + '<span>صدور ' + esc(l.created_jalali || '—') + '</span>'
            + '</div></li>';
    }

    function renderLicenseRowsList(items) {
        if (!items || !items.length) {
            return '';
        }
        return '<ul class="adm-u360-license-rows" role="list">'
            + items.map(renderLicenseListItem).join('')
            + '</ul>';
    }

    function renderLicenseListCard(licenses) {
        const all = licenses || [];
        const current = all.filter(function (l) { return l.entitlement_valid === true; });
        const history = all.filter(function (l) { return l.entitlement_valid !== true; });
        let body = '';

        if (!all.length) {
            body = '<div class="adm-u360-license-list__empty">'
                + emptyState('لایسنسی ثبت نشده', 'پس از خرید یا اختصاص، رکورد اینجا نمایش داده می‌شود.', 'fa-key')
                + '</div>';
        } else {
            if (current.length) {
                body += renderLicenseRowsList(current);
            } else {
                body += '<div class="adm-u360-license-list__empty adm-u360-license-list__empty--inline">'
                    + emptyState('دسترسی معتبر فعلی ندارد', 'خلاصه بالای صفحه وضعیت دسترسی را نشان می‌دهد.', 'fa-circle-info')
                    + '</div>';
            }
            if (history.length) {
                body += '<div class="adm-u360-license-list__hist" role="separator">'
                    + '<span class="adm-u360-license-list__hist-label">سوابق</span>'
                    + '<span class="adm-u360-license-list__hist-count">' + toFa(history.length) + '</span>'
                    + '</div>'
                    + renderLicenseRowsList(history);
            }
        }

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-license-list adm-u360-license-card--list" aria-label="لایسنس‌ها و سوابق">'
            + '<header class="adm-u360-license-list__head">'
            + '<h2 class="adm-u360-license-list__title"><span>لایسنس‌ها</span></h2>'
            + (all.length
                ? '<span class="adm-u360-license-list__count" title="تعداد رکورد">' + toFa(all.length) + '</span>'
                : '')
            + '</header>'
            + '<div class="adm-u360-license-list__body">' + body + '</div>'
            + '</section>';
    }

    function renderLicenseActivationsCard(activations) {
        const rows = (activations || []).map(function (act) {
            const device = '<div class="adm-u360-commerce-product">'
                + '<span class="adm-u360-commerce-product__name">' + esc(act.label || '—') + '</span>'
                + '<span class="adm-u360-commerce-product__plan">' + esc(act.plan) + '</span>'
                + (act.fingerprint_masked
                    ? '<span class="adm-u360-cell-sub adm-u360-ltr">' + esc(act.fingerprint_masked) + '</span>'
                    : '')
                + '</div>';
            return '<tr>'
                + td('<span class="adm-u360-commerce-tag">' + esc(act.platform) + '</span>', 'پلتفرم')
                + td(device, 'دستگاه')
                + td(boolChip(act.is_active, 'فعال', 'غیرفعال'), 'وضعیت')
                + td(esc(act.activated_jalali), 'تاریخ')
                + '</tr>';
        }).join('');
        const body = rows
            ? miniTable(['پلتفرم', 'دستگاه', 'وضعیت', 'تاریخ'], rows, 'adm-u360-commerce-table adm-u360-commerce-table--compact')
            : emptyState('فعال‌سازی ثبت نشده', 'اولین ورود به ربات یا نصب اپ، اینجا ظاهر می‌شود.');
        return commerceCard('فعال‌سازی‌ها', 'fa-plug', body, 'adm-u360-license-card--activations');
    }

    const CAMPAIGN_GRANT_STATUS_FA = {
        granted: 'فعال‌شده',
        failed: 'خطا',
        skipped: 'رد شده',
    };

    const CAMPAIGN_KEY_FA = {
        signup_welcome_7d_v1: 'هدیه خوش‌آمدگویی (۷ روز)',
        weekly_professional_gift_v1: 'هدیه آزمایشی حرفه‌ای',
    };

    function campaignGrantStatusChip(status, label) {
        const text = label || CAMPAIGN_GRANT_STATUS_FA[status] || status || '—';
        const tones = { granted: 'ok', failed: 'danger', skipped: 'muted' };
        const mod = tones[status] || 'muted';
        return '<span class="adm-u360-order-chip adm-u360-order-chip--' + mod + '">' + esc(text) + '</span>';
    }

    function campaignGrantLabel(g) {
        if (g.campaign_label) return g.campaign_label;
        const key = (g.campaign_key || '').trim();
        if (CAMPAIGN_KEY_FA[key]) return CAMPAIGN_KEY_FA[key];
        if (key.indexOf('signup_welcome') === 0) return 'هدیه خوش‌آمدگویی ثبت‌نام';
        if (key.indexOf('weekly_professional_gift') === 0) return 'هدیه آزمایشی حرفه‌ای';
        return key || '—';
    }

    function postLicenseAction(licenseId, body) {
        return fetch(licenseActionUrl(licenseId), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(body || {}),
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok || !data.ok) {
                    throw new Error((data && data.error) || 'خطا در عملیات لایسنس');
                }
                return data;
            });
        });
    }

    function setLicenseCardFeedback(licenseId, message, isError) {
        const card = panel.querySelector('[data-u360-lic-card="' + licenseId + '"]');
        if (!card) return;
        const fb = card.querySelector('.adm-u360-lic-manage__feedback');
        if (!fb) return;
        fb.textContent = message || '';
        fb.classList.toggle('is-error', !!isError);
        fb.classList.toggle('is-ok', !!message && !isError);
    }

    function renderLicenseSlotMeter(lic) {
        const used = Number(lic.slots_used) || 0;
        const max = Math.max(1, Number(lic.max_activations) || 1);
        const active = Number(lic.slots_active) || 0;
        const pct = Math.min(100, Math.round((used / max) * 100));
        return '<div class="adm-u360-lic-meter adm-u360-lic-meter--inline" role="img" aria-label="ظرفیت اسلات">'
            + '<div class="adm-u360-lic-meter__track">'
            + '<span class="adm-u360-lic-meter__fill" style="width:' + pct + '%"></span>'
            + '</div>'
            + '<span class="adm-u360-lic-meter__label">'
            + toFa(used) + '/' + toFa(max) + ' · ' + toFa(active) + ' فعال'
            + '</span></div>';
    }

    function renderLicenseStatusActions(lic, statusOptions) {
        const groupName = 'u360-lic-status-' + lic.id;
        return '<div class="adm-u360-lic-panel adm-u360-lic-panel--status adm-u360-lic-panel--toolbar">'
            + '<span class="adm-u360-lic-panel__toolbar-label">وضعیت</span>'
            + '<div class="adm-u360-lic-radios" role="radiogroup" aria-label="وضعیت لایسنس"'
            + ' data-current-status="' + esc(lic.status || '') + '">'
            + (statusOptions || []).map(function (opt) {
                const on = lic.status === opt.key;
                return '<label class="adm-u360-lic-radio adm-u360-lic-radio--' + esc(opt.key) + '">'
                    + '<input type="radio" class="adm-u360-lic-radio__input"'
                    + ' name="' + esc(groupName) + '" value="' + esc(opt.key) + '"'
                    + (on ? ' checked' : '')
                    + ' data-u360-lic="' + esc(lic.id) + '"'
                    + ' data-u360-lic-field="status"'
                    + ' data-u360-lic-action="set_status">'
                    + '<span class="adm-u360-lic-radio__ui" aria-hidden="true"></span>'
                    + '<span class="adm-u360-lic-radio__text">' + esc(opt.label) + '</span>'
                    + '</label>';
            }).join('')
            + '</div></div>';
    }

    function submitLicenseAction(licenseId, body, busyEls) {
        const busy = busyEls || [];
        busy.forEach(function (el) {
            if (el) el.disabled = true;
        });
        setLicenseCardFeedback(licenseId, 'در حال اعمال…', false);
        return postLicenseAction(licenseId, body)
            .then(function () {
                bustLicensesTabCache();
                loadTab('licenses', tabQueryState.licenses || {}, true);
            })
            .catch(function (err) {
                setLicenseCardFeedback(licenseId, err.message || 'خطا', true);
                throw err;
            })
            .finally(function () {
                busy.forEach(function (el) {
                    if (el) el.disabled = false;
                });
            });
    }

    function renderLicenseExpiryActions(lic) {
        const exp = splitLicenseExpiryJalali(lic.expires_jalali);
        const dateVal = exp.unlimited ? '' : exp.date;
        const timeKeep = exp.time || '23:59';
        const placeholder = exp.unlimited ? 'بدون انقضا — تاریخ را انتخاب کنید' : 'تقویم شمسی';
        return '<div class="adm-u360-lic-panel adm-u360-lic-panel--expiry adm-u360-lic-panel--expiry-cal adm-u360-lic-panel--toolbar">'
            + '<span class="adm-u360-lic-panel__toolbar-label">انقضا</span>'
            + '<div class="adm-u360-lic-expiry-cal" aria-label="تقویم انقضا">'
            + '<input type="text" class="adm-u360-lic-expiry-input adm-u360-lic-expiry-input--cal adm-u360-ltr"'
            + ' dir="ltr" autocomplete="off" inputmode="none" readonly'
            + ' data-jdp data-jdp-only-date'
            + ' data-u360-lic-expiry="' + esc(lic.id) + '"'
            + ' data-initial-value="' + esc(dateVal) + '"'
            + ' data-expiry-time="' + esc(timeKeep) + '"'
            + ' value="' + esc(dateVal) + '"'
            + ' placeholder="' + esc(placeholder) + '"'
            + ' aria-label="تاریخ انقضای شمسی">'
            + '<button type="button" class="adm-u360-lic-expiry-clear" title="بدون انقضا"'
            + ' data-u360-lic="' + esc(lic.id) + '" data-u360-lic-action="adjust_expiry" data-mode="clear"'
            + ' aria-label="حذف تاریخ انقضا">×</button>'
            + '</div></div>';
    }

    function composeExpiryJalaliForSave(raw, timeKeep) {
        const val = String(raw || '').trim();
        if (!val) return '';
        if (/\s+\d{1,2}:\d{2}/.test(val)) return val;
        const t = String(timeKeep || '23:59').trim() || '23:59';
        return val + ' ' + t;
    }

    function renderLicenseSlotsManage(lic, canManage) {
        const acts = lic.activations || [];
        const slotsHtml = acts.length
            ? '<ul class="adm-u360-lic-slots" role="list">'
                + acts.map(function (act) {
                    const platIcon = (act.platform || '').indexOf('اندروید') >= 0 ? 'fa-mobile-screen' : 'fa-desktop';
                    return '<li class="adm-u360-lic-slot' + (act.is_active ? ' is-live' : '') + '" role="listitem">'
                        + '<span class="adm-u360-lic-slot__icon" aria-hidden="true"><i class="fas ' + platIcon + '"></i></span>'
                        + '<div class="adm-u360-lic-slot__main">'
                        + '<div class="adm-u360-lic-slot__title-row">'
                        + '<span class="adm-u360-lic-slot__label">' + esc(act.label || 'دستگاه') + '</span>'
                        + '<span class="adm-u360-lic-slot__state' + (act.is_active ? ' is-on' : '') + '">'
                        + (act.is_active ? 'متصل' : 'قطع') + '</span></div>'
                        + '<span class="adm-u360-lic-slot__meta">'
                        + esc(act.platform) + ' · ' + esc(act.activated_jalali || '—')
                        + (act.fingerprint_masked
                            ? ' · <span class="adm-u360-ltr" dir="ltr">' + esc(act.fingerprint_masked) + '</span>'
                            : '')
                        + '</span></div>'
                        + (canManage
                            ? '<div class="adm-u360-lic-slot__actions">'
                            + '<button type="button" class="adm-u360-lic-slot__act" data-u360-lic="' + esc(lic.id)
                            + '" data-u360-lic-action="set_activation_active" data-activation-id="' + esc(act.id)
                            + '" data-active="' + (act.is_active ? '0' : '1') + '">'
                            + (act.is_active ? 'قطع' : 'فعال') + '</button>'
                            + '<button type="button" class="adm-u360-lic-slot__act adm-u360-lic-slot__act--danger" data-u360-lic="'
                            + esc(lic.id) + '" data-u360-lic-action="remove_activation" data-activation-id="' + esc(act.id)
                            + '">حذف</button></div>'
                            : '')
                        + '</li>';
                }).join('')
                + '</ul>'
            : '<p class="adm-u360-lic-manage__empty-slots">هنوز دستگاهی به این لایسنس وصل نشده.</p>';

        const maxField = canManage
            ? '<div class="adm-u360-lic-max adm-u360-lic-max--inline">'
                + '<input type="number" min="1" max="50" class="adm-u360-lic-manage__max-input" data-u360-lic-max="'
                + esc(lic.id) + '" value="' + esc(lic.max_activations || 1) + '" aria-label="حداکثر اسلات" title="سقف اسلات">'
                + '<button type="button" class="adm-u360-lic-expiry-save adm-u360-lic-expiry-save--ghost" data-u360-lic="'
                + esc(lic.id) + '" data-u360-lic-action="set_max_activations">سقف</button>'
                + '</div>'
            : '';

        return '<div class="adm-u360-lic-panel adm-u360-lic-panel--slots adm-u360-lic-panel--slots-compact">'
            + '<div class="adm-u360-lic-slots-bar">'
            + '<span class="adm-u360-lic-panel__toolbar-label">اسلات</span>'
            + renderLicenseSlotMeter(lic)
            + maxField
            + '</div>'
            + slotsHtml
            + '</div>';
    }

    function renderLicenseManageCard(lic, statusOptions, canManage) {
        const cardMod = lic.entitlement_valid ? ' is-valid' : '';
        const assignLine = lic.assigned_to && lic.assigned_to !== '—'
            ? '<p class="adm-u360-lic-manage__assign">'
                + 'تخصیص · <strong>' + esc(lic.assigned_to) + '</strong>'
                + (canManage && lic.assigned_user_id
                    ? ' · <button type="button" class="adm-u360-lic-inline-act" data-u360-lic="'
                        + esc(lic.id) + '" data-u360-lic-action="revoke_assignment">لغو</button>'
                    : '')
                + '</p>'
            : '';

        const head = '<header class="adm-u360-lic-manage__summary">'
            + '<div class="adm-u360-lic-manage__title-row">'
            + '<h3 class="adm-u360-lic-manage__plan">' + esc(lic.plan || '—') + '</h3>'
            + '<div class="adm-u360-lic-manage__title-aside">'
            + '<span class="adm-u360-lic-manage__id">#' + toFa(lic.id) + '</span>'
            + licenseStatusChip(lic.status, lic.status_label, lic.entitlement_valid)
            + '</div></div>'
            + renderLicenseMetaStrip(lic)
            + assignLine
            + renderLicenseOrderLine(lic)
            + '</header>';

        const tools = canManage
            ? '<div class="adm-u360-lic-manage__tools adm-u360-lic-manage__tools--compact">'
                + '<div class="adm-u360-lic-manage__controls">'
                + renderLicenseStatusActions(lic, statusOptions)
                + renderLicenseExpiryActions(lic)
                + '</div>'
                + renderLicenseSlotsManage(lic, canManage)
                + '</div>'
                + '<p class="adm-u360-lic-manage__feedback" role="status" aria-live="polite"></p>'
            : '<p class="adm-u360-lic-manage__readonly adm-u360-lic-manage__readonly--inset">'
                + 'ویرایش لایسنس فقط برای مدیران دارای مجوز تغییر لایسنس فعال است.</p>';

        return '<section class="adm-u360-lic-manage adm-u360-lic-manage--card adm-u360-lic-manage--pro adm-u360-lic-manage--compact'
            + cardMod + '" data-u360-lic-card="' + esc(lic.id) + '" aria-label="لایسنس ' + esc(lic.id) + '">'
            + head + tools + '</section>';
    }

    function renderLicenseGrantsCard(grants) {
        const rows = (grants || []).map(function (g) {
            const keyHint = g.campaign_key && g.campaign_label && g.campaign_key !== g.campaign_label
                ? ' <span class="adm-u360-ltr adm-u360-grant-key" title="شناسه فنی">· ' + esc(g.campaign_key) + '</span>'
                : '';
            return '<tr>'
                + td(esc(campaignGrantLabel(g)) + keyHint, 'کمپین')
                + td(campaignGrantStatusChip(g.status, g.status_label), 'وضعیت')
                + td(g.license_id ? toFa(g.license_id) : '—', 'لایسنس')
                + td(esc(g.created_jalali), 'تاریخ')
                + '</tr>';
        }).join('');
        const body = rows
            ? miniTable(['کمپین', 'وضعیت', 'لایسنس', 'تاریخ'], rows, 'adm-u360-commerce-table adm-u360-commerce-table--compact')
            : emptyState('اعطای کمپین ندارد', 'لایسنس‌های هدیه یا کمپین در این بخش لیست می‌شوند.');
        return commerceCard('اعطای کمپین', 'fa-gift', body, 'adm-u360-license-card--grants');
    }

    function renderLicenses(d) {
        const access = d.access_summary || {};
        const perms = bootstrap.permissions || {};
        const canManage = !!(d.can_manage_licenses || perms.can_manage_user_licenses);
        const licenses = d.licenses || [];
        const statusOptions = (d.form_options && d.form_options.status) || [];
        const sorted = licenses.slice().sort(function (a, b) {
            if (!!a.entitlement_valid !== !!b.entitlement_valid) {
                return a.entitlement_valid ? -1 : 1;
            }
            return (b.id || 0) - (a.id || 0);
        });

        let manageBlock = '';
        if (sorted.length) {
            manageBlock = '<section class="adm-u360-lic-deck" aria-label="مدیریت لایسنس‌ها">'
                + '<header class="adm-u360-lic-deck__head">'
                + '<h2 class="adm-u360-lic-deck__title"><i class="fas fa-sliders-h" aria-hidden="true"></i>'
                + '<span>مدیریت لایسنس</span></h2>'
                + (canManage
                    ? '<span class="adm-u360-lic-deck__mode adm-u360-lic-deck__mode--ok">اقدامات فعال</span>'
                    : '<span class="adm-u360-lic-deck__mode">فقط مشاهده</span>')
                + '</header>'
                + '<div class="adm-u360-lic-deck__stack">'
                + sorted.map(function (lic) {
                    return renderLicenseManageCard(lic, statusOptions, canManage);
                }).join('')
                + '</div></section>';
        } else {
            manageBlock = '<div class="adm-u360-license-list__empty">'
                + emptyState('لایسنسی ثبت نشده', 'پس از خرید یا اختصاص، رکورد اینجا نمایش داده می‌شود.', 'fa-key')
                + '</div>';
        }

        const html = '<div class="adm-u360-licenses adm-u360-licenses--pro">'
            + renderLicenseAccessCard(access)
            + manageBlock
            + renderLicenseGrantsCard(d.campaign_grants)
            + '</div>';

        paintPanel(html, 'licenses');
    }

    function activitySuccessChip(success) {
        if (success === true) {
            return '<span class="adm-u360-order-chip adm-u360-order-chip--ok">موفق</span>';
        }
        if (success === false) {
            return '<span class="adm-u360-order-chip adm-u360-order-chip--danger">ناموفق</span>';
        }
        return '<span class="adm-u360-order-chip adm-u360-order-chip--muted">—</span>';
    }

    const ACTIVITY_KIND_BADGE = {
        signup: 'ثبت‌نام',
        login_marker: 'ورود',
        order: 'خرید',
        download: 'دانلود',
        app_event: 'اپ',
        android_device: 'اندروید',
        extraction: 'استخراج',
        dataset: 'دیتاست',
        crm_contact: 'مخاطب',
        crm_deal: 'معامله',
        ticket: 'پشتیبانی',
    };

    function activityOutcomeText(success) {
        if (success === true) {
            return 'موفق';
        }
        if (success === false) {
            return 'ناموفق';
        }
        return '';
    }

    function activityDetailLine(detail) {
        if (!detail) {
            return '';
        }
        const raw = String(detail).trim();
        if (!raw) {
            return '';
        }
        const short = raw.length > 220 ? raw.slice(0, 217) + '…' : raw;
        return '<p class="adm-u360-activity-row__detail" title="' + esc(raw) + '">' + esc(short) + '</p>';
    }

    function renderActivityEventRow(ev) {
        const badge = ACTIVITY_KIND_BADGE[ev.kind] || ev.kind_label || 'رویداد';
        const title = ev.title || '—';
        const outcome = activityOutcomeText(ev.success);
        const metaBits = [];
        if (ev.at_jalali) {
            metaBits.push('<time class="adm-u360-activity-row__time" datetime="' + esc(ev.at || '') + '">'
                + esc(ev.at_jalali) + '</time>');
        }
        if (outcome) {
            metaBits.push('<span class="adm-u360-activity-row__outcome adm-u360-activity-row__outcome--'
                + (ev.success === false ? 'fail' : 'ok') + '">' + esc(outcome) + '</span>');
        }
        const detailHtml = activityDetailLine(ev.detail);

        return '<li class="adm-u360-activity-row" role="listitem">'
            + '<div class="adm-u360-activity-row__body">'
            + '<div class="adm-u360-activity-row__head">'
            + '<span class="adm-u360-activity-row__badge">' + esc(badge) + '</span>'
            + '<h3 class="adm-u360-activity-row__title">' + esc(title) + '</h3>'
            + '</div>'
            + '<div class="adm-u360-activity-row__meta">' + metaBits.join('<span class="adm-u360-activity-row__sep" aria-hidden="true">·</span>') + '</div>'
            + (detailHtml || '')
            + '</div></li>';
    }

    function renderActivity(d) {
        const selected = tabQueryState.activity || {};
        const filters = d.filters || {};
        function filterSelect(name, label, options) {
            const current = selected[name] || '';
            return '<label class="adm-u360-activity-filter">'
                + '<span class="adm-u360-activity-filter__label">' + esc(label) + '</span>'
                + '<select class="adm-u360-activity-filter__select" data-u360-activity-filter="' + name + '" aria-label="' + esc(label) + '">'
                + options.map(function (o) {
                    return '<option value="' + esc(o.value) + '"' + (current === o.value ? ' selected' : '') + '>'
                        + esc(o.label) + '</option>';
                }).join('') + '</select></label>';
        }
        const kindOptions = [{ value: '', label: 'همه' }].concat(
            (filters.kinds || []).map(function (k) { return { value: k.key, label: k.label }; })
        );
        const platformLabels = { web: 'وب', shop: 'فروشگاه', windows: 'ویندوز', android: 'اندروید',
            workspace: 'فضای کار', crm: 'مخاطبین', support: 'پشتیبانی' };
        const platformOptions = [{ value: '', label: 'همه' }].concat(
            (filters.platforms || []).map(function (p) {
                return { value: p, label: platformLabels[p] || p };
            })
        );
        const filterControls = '<div class="adm-u360-activity-filters" role="group" aria-label="فیلتر فعالیت">'
            + filterSelect('kind', 'نوع', kindOptions)
            + filterSelect('platform', 'پلتفرم', platformOptions)
            + filterSelect('success', 'نتیجه', [
                { value: '', label: 'همه' }, { value: 'ok', label: 'موفق' },
                { value: 'fail', label: 'ناموفق' },
            ])
            + filterSelect('sort', 'ترتیب', [
                { value: '-at', label: 'جدیدترین' }, { value: 'at', label: 'قدیمی‌ترین' },
            ])
            + '<button type="button" class="adm-u360-activity-filters__reset" data-u360-activity-reset">پاک‌سازی</button>'
            + '</div>';

        const days = panelRangeDaysParam();
        const rangeLabel = days === 'all' ? 'کل دوره' : toFa(days) + ' روز';
        const pageCount = (d.events || []).length;
        const total = d.pagination ? d.pagination.total : pageCount;

        const summary = '<section class="adm-u360-block adm-u360-block--card adm-u360-activity-summary" aria-label="خلاصه فعالیت">'
            + '<header class="adm-u360-activity-summary__head">'
            + '<h2 class="adm-u360-activity-summary__title"><span>فعالیت و رفتار</span></h2>'
            + '<span class="adm-u360-activity-summary__range">بازه · ' + esc(rangeLabel) + '</span>'
            + '</header>'
            + '<dl class="adm-u360-activity-metrics">'
            + '<div class="adm-u360-activity-metric"><dt>این صفحه</dt><dd>' + toFa(pageCount) + '</dd></div>'
            + '<div class="adm-u360-activity-metric"><dt>کل رویداد</dt><dd>' + toFa(total) + '</dd></div>'
            + '</dl></section>';

        const filtersCard = '<section class="adm-u360-activity-filters-bar" aria-label="فیلتر رویدادها">'
            + filterControls
            + '</section>';

        const actPts = (d.charts && d.charts.activity_daily) || [];
        let chartSection = '';
        if (actPts.length) {
            chartSection = '<section class="adm-u360-block adm-u360-block--card adm-u360-activity-chart" aria-label="روند روزانه">'
                + '<header class="adm-u360-activity-chart__head">'
                + '<h2 class="adm-u360-activity-chart__title"><span>روند روزانه</span></h2>'
                + '<span class="adm-u360-activity-chart__meta">بدون اعمال فیلتر جدول</span>'
                + '</header>'
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--wide adm-u360-chart-wrap--activity">'
                + '<canvas id="admU360ActChart" role="img" aria-label="روند روزانه رویدادها"></canvas>'
                + '</div></section>';
        }

        const events = (d.events || []).map(renderActivityEventRow).join('');
        const feedBody = events
            ? '<ul class="adm-u360-activity-rows" role="list">' + events + '</ul>'
            : '<div class="adm-u360-activity-feed__empty">'
                + emptyState('رویدادی با این فیلترها نیست', 'فیلترها یا بازه زمانی را تغییر دهید.', 'fa-filter')
                + '</div>';
        const feed = '<section class="adm-u360-block adm-u360-block--card adm-u360-activity-feed adm-u360-activity-feed--minimal" aria-label="فهرست رویدادها">'
            + '<header class="adm-u360-activity-feed__head">'
            + '<h2 class="adm-u360-activity-feed__title"><span>رویدادها</span></h2>'
            + (pageCount ? '<span class="adm-u360-activity-feed__count">' + toFa(pageCount) + '</span>' : '')
            + '</header>'
            + '<div class="adm-u360-activity-feed__body">' + feedBody + '</div>'
            + renderPager(d.pagination, 'activity')
            + '</section>';

        paintPanel('<div class="adm-u360-activity adm-u360-activity--minimal">'
            + summary
            + filtersCard
            + chartSection
            + feed
            + '</div>');

        window.requestAnimationFrame(function () {
            mountBarActivity('admU360ActChart', actPts);
        });
    }

    const USAGE_FEATURE_LABELS = {
        'ربات ویندوز': 'نرم‌افزار ویندوز',
        'اپ اندروید': 'اپلیکیشن اندروید',
        'استخراج آگهی': 'استخراج از دیوار',
        'دیتاست‌ها': 'دیتاست‌ها',
        'شمارش آگهی‌ها': 'آگهی در بانک فایل',
        'آگهی در بانک فایل': 'آگهی در بانک فایل',
        'مخاطبین': 'مخاطبین CRM',
        'معاملات': 'معاملات CRM',
        'یادآورها': 'یادآورها',
        'فعالیت لیستینگ دیوار': 'کار روی آگهی‌های فایل',
        'کار روی آگهی فایل': 'کار روی آگهی‌های فایل',
        'همگام‌سازی موبایل': 'همگام‌سازی موبایل',
    };

    const USAGE_COUNT_UNIT = {
        'کار روی آگهی فایل': 'آگهی',
        'فعالیت لیستینگ دیوار': 'آگهی',
        'شمارش آگهی‌ها': 'آگهی',
        'آگهی در بانک فایل': 'آگهی',
        'دیتاست‌ها': 'فایل',
        'مخاطبین': 'مخاطب',
        'معاملات': 'معامله',
        'یادآورها': 'یادآور',
    };

    function usageFeatureTitle(f) {
        const key = (f && f.name) || '';
        return USAGE_FEATURE_LABELS[key] || key || '—';
    }

    function usageFeatureUsed(f) {
        return !!(f && (f.started || (f.count && f.count > 0)));
    }

    function usageStatusLabel(f) {
        let text = 'استفاده نشده';
        let tone = 'idle';
        if (usageFeatureUsed(f)) {
            text = 'در حال استفاده';
            tone = 'on';
        } else if (f && f.note === 'بدون رکورد') {
            text = 'بدون گزارش سیستم';
            tone = 'unknown';
        }
        return '<span class="adm-u360-usage-row__status adm-u360-usage-row__status--' + tone + '">'
            + esc(text) + '</span>';
    }

    function usageFeatureDetail(f) {
        const count = Number(f && f.count) || 0;
        const unit = USAGE_COUNT_UNIT[(f && f.name) || ''] || 'بار';
        if (count > 0) {
            return toFa(count) + ' ' + unit;
        }
        if (f && f.started) {
            return 'حداقل یک‌بار باز شده';
        }
        if (f && f.note === 'بدون رکورد') {
            return 'شمارش دقیق در دسترس نیست';
        }
        return 'هنوز استفاده نشده';
    }

    function renderUsageFeatureRow(f) {
        const used = usageFeatureUsed(f);
        const last = (f.last_at_jalali || '').trim();
        const lastBit = last && last !== '—'
            ? '<span class="adm-u360-usage-row__sep" aria-hidden="true">·</span>'
                + '<span>آخرین بار ' + esc(last) + '</span>'
            : '';
        const noteBit = (f.note || '').trim()
            ? '<span class="adm-u360-usage-row__sep" aria-hidden="true">·</span>'
                + '<span class="adm-u360-usage-row__note">' + esc(f.note) + '</span>'
            : '';
        return '<li class="adm-u360-usage-row' + (used ? ' adm-u360-usage-row--on' : '') + '" role="listitem">'
            + '<div class="adm-u360-usage-row__head">'
            + '<h3 class="adm-u360-usage-row__title">' + esc(usageFeatureTitle(f)) + '</h3>'
            + usageStatusLabel(f)
            + '</div>'
            + '<div class="adm-u360-usage-row__meta">'
            + '<span>' + esc(usageFeatureDetail(f)) + '</span>'
            + lastBit
            + noteBit
            + '</div></li>';
    }

    function renderUsage(d) {
        const feats = d.features || [];
        const usedCount = feats.filter(usageFeatureUsed).length;
        const days = panelRangeDaysParam();
        const rangeLabel = days === 'all' ? 'کل دوره' : toFa(days) + ' روز';
        const chartRows = (d.charts && d.charts.feature_usage) || [];

        const summary = '<section class="adm-u360-block adm-u360-block--card adm-u360-usage-summary" aria-label="خلاصه استفاده">'
            + '<header class="adm-u360-usage-summary__head">'
            + '<h2 class="adm-u360-usage-summary__title"><span>چقدر از محصول استفاده شده؟</span></h2>'
            + '<span class="adm-u360-usage-summary__range">بازه · ' + esc(rangeLabel) + '</span>'
            + '</header>'
            + '<dl class="adm-u360-usage-metrics">'
            + '<div class="adm-u360-usage-metric">'
            + '<dt>بخش‌های استفاده‌شده</dt><dd>' + toFa(usedCount) + ' <span class="adm-u360-usage-metric__of">از '
            + toFa(feats.length) + ' بخش</span></dd></div>'
            + '<div class="adm-u360-usage-metric">'
            + '<dt>سهم استفاده</dt><dd>' + toFa(feats.length ? Math.round((usedCount / feats.length) * 100) : 0)
            + '<span class="adm-u360-usage-metric__pct">٪</span></dd></div>'
            + '</dl>'
            + '<p class="adm-u360-usage-summary__hint">بر پایهٔ رکوردهای همین حساب؛ برای بعضی بخش‌ها ممکن است عدد دقیق ثبت نشده باشد.</p>'
            + '</section>';

        const chartSection = '<section class="adm-u360-block adm-u360-block--card adm-u360-usage-chart" aria-label="مقایسه فعالیت بخش‌ها">'
            + '<header class="adm-u360-usage-chart__head">'
            + '<h2 class="adm-u360-usage-chart__title"><span>کجا بیشتر فعال بوده؟</span></h2>'
            + '<p class="adm-u360-usage-chart__lead">'
            + 'مرتب‌سازی بر اساس تعداد رویداد و کار ثبت‌شده؛ '
            + '<strong>حجم آگهی در بانک فایل</strong> اینجا نمایش داده نمی‌شود.'
            + '</p>'
            + '</header>'
            + '<div class="adm-u360-usage-chart__body">'
            + renderUsageRankChart(chartRows)
            + '</div></section>';

        const listBody = feats.length
            ? '<ul class="adm-u360-usage-rows" role="list">' + feats.map(renderUsageFeatureRow).join('') + '</ul>'
            : '<div class="adm-u360-usage-feed__empty">'
                + emptyState('قابلیتی تعریف نشده', 'دادهٔ استفاده برای این کاربر موجود نیست.', 'fa-layer-group')
                + '</div>';

        const feed = '<section class="adm-u360-block adm-u360-block--card adm-u360-usage-feed" aria-label="فهرست بخش‌های محصول">'
            + '<header class="adm-u360-usage-feed__head">'
            + '<h2 class="adm-u360-usage-feed__title"><span>همهٔ بخش‌ها</span></h2>'
            + '<span class="adm-u360-usage-feed__count">' + toFa(feats.length) + '</span>'
            + '</header>'
            + '<div class="adm-u360-usage-feed__body">' + listBody + '</div>'
            + '</section>';

        paintPanel('<div class="adm-u360-usage adm-u360-usage--minimal">'
            + summary
            + chartSection
            + feed
            + '</div>', 'usage');

    }

    function renderTabData(tab, data) {
        if (!data) {
            paintPanel('<p class="adm-u360-empty">داده‌ای برنگشت.</p>');
            return;
        }
        if (tab === 'overview') return renderOverview(data);
        if (tab === 'account') return renderAccount(data);
        if (tab === 'commerce') return renderCommerce(data);
        if (tab === 'licenses') return renderLicenses(data);
        if (tab === 'activity') return renderActivity(data);
        if (tab === 'usage') return renderUsage(data);
        if (tab === 'devices') {
            const win = data.windows || {};
            const flags = win.flags || ((win.downloaded !== undefined || win.activated !== undefined)
                ? win
                : {});
            const androidCount = (data.android_devices || []).length;
            let content = '';
            const dl = (win.downloads || []).map(function (d) {
                return '<tr>' + td(esc(d.created_jalali), 'زمان') + td(esc(d.plan), 'پلن')
                    + td('<span class="adm-u360-ltr">' + esc(d.ip) + '</span>', 'آدرس IP') + '</tr>';
            }).join('');
            if (dl) content += subSection('دانلود ویندوز', miniTable(['زمان', 'پلن', 'آدرس IP'], dl), 'fa-download');
            const ev = (win.app_events || []).map(function (e) {
                return '<tr>' + td(esc(e.event_label), 'رویداد') + td(esc(e.app_version), 'نسخه')
                    + td(esc(e.created_jalali), 'زمان') + '</tr>';
            }).join('');
            if (ev) content += subSection('رویداد اپ', miniTable(['رویداد', 'نسخه', 'زمان'], ev), 'fa-bolt');
            const dev = (data.android_devices || []).map(function (d) {
                return '<tr>' + td(esc(d.device_model), 'مدل') + td(esc(d.app_version), 'نسخه')
                    + td(esc(d.last_seen_jalali), 'آخرین ارتباط') + '</tr>';
            }).join('');
            content += subSection('دستگاه‌های اندروید', miniTable(['مدل', 'نسخه', 'آخرین ارتباط'], dev), 'fa-mobile-alt');
            const plat = (data.charts && data.charts.platform_activations) || [];
            const chartPart = plat.length
                ? chartsRow(chartCard('فعال‌سازی‌ها به تفکیک پلتفرم', 'admU360DevPlatform', 'adm-u360-chart-wrap--donut', 'fa-chart-pie'))
                : '';
            paintPanel(tabPanel('دستگاه‌ها و نرم‌افزارها', tabIcon('devices'), {
                metrics: renderDevicesPlatformSummary(flags, data.android_devices),
                toolbar: panelRangeHint(),
                viz: chartPart,
                content: content,
            }));
            window.requestAnimationFrame(function () {
                mountDoughnut('admU360DevPlatform', plat);
            });
            return;
        }
        if (tab === 'support') return renderSupport(data);
        if (tab === 'workspace') return renderWorkspace(data);
        if (tab === 'marketing') return renderMarketing(data);
        if (tab === 'agency') {
            if (data.empty) {
                paintPanel(emptyState(data.message || 'عضویت آژانسی ندارد', 'این کاربر در هیچ فضای آژانسی ثبت نشده است.'), 'agency');
                return;
            }
            let content = '';
            const rows = (data.memberships || []).map(function (m) {
                return '<tr>' + td(esc(m.agency_name), 'آژانس') + td(esc(m.role), 'نقش')
                    + td(m.is_active ? 'فعال' : 'غیرفعال', 'وضعیت')
                    + td(esc(m.joined_jalali), 'تاریخ') + '</tr>';
            }).join('');
            content += subSection('عضویت در آژانس', miniTable(['آژانس', 'نقش', 'وضعیت', 'تاریخ'], rows), 'fa-users');
            const subs = (data.owner_subscriptions || []).map(function (s) {
                return '<tr>' + td(esc(s.agency_name), 'آژانس') + td(esc(s.plan), 'پلن')
                    + td(esc(s.status), 'وضعیت') + td(esc(s.expires_jalali), 'انقضا') + '</tr>';
            }).join('');
            if (subs) content += subSection('اشتراک‌های مالکیت', miniTable(['آژانس', 'پلن', 'وضعیت', 'انقضا'], subs), 'fa-star');
            paintPanel(tabPanel('فضای آژانس', tabIcon('agency'), {
                metrics: statStrip([
                    { label: 'عضویت‌ها', value: toFa((data.memberships || []).length) },
                    { label: 'اشتراک مالکیت', value: toFa((data.owner_subscriptions || []).length) },
                ]),
                toolbar: panelRangeHint(),
                content: content,
            }));
            return;
        }
        if (tab === 'admin_log') return renderAdminLog(data);
        paintPanel(emptyState('این تب هنوز آماده نیست'), tab);
    }

    function loadTab(tab, query, skipCache) {
        // Keep each tab's pagination and support filters when navigating.
        const saved = tabQueryState[tab] || {};
        query = mergePanelRangeQuery(Object.assign({}, saved, query || {}));
        tabQueryState[tab] = Object.assign({}, query);
        activeTab = tab;
        setTabInUrl(tab);
        tabsNav.querySelectorAll('.adm-u360-tab').forEach(function (btn) {
            const on = btn.getAttribute('data-u360-tab') === tab;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        scrollActiveTabIntoView();

        // An earlier response must never overwrite the currently selected tab.
        const version = ++requestVersion;
        if (activeRequest) activeRequest.abort();
        activeRequest = null;
        if (tab === 'usage' && bustUsageTabCache) {
            skipCache = true;
            bustUsageTabCache = false;
        }
        const cacheKey = tab + JSON.stringify(query);
        if (!skipCache && tabCache[cacheKey]) {
            renderTabData(tab, tabCache[cacheKey]);
            return;
        }
        showLoading();
        const controller = new AbortController();
        activeRequest = controller;
        fetch(tabUrl(tab, query), {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
            signal: controller.signal,
        })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (payload) {
                if (version !== requestVersion) return;
                if (!payload.ok) throw new Error('bad');
                tabCache[cacheKey] = payload.data;
                renderTabData(tab, payload.data);
            })
            .catch(function (error) {
                if (version !== requestVersion || error.name === 'AbortError') return;
                paintPanel('<p class="adm-u360-empty">بارگذاری ناموفق بود. '
                    + '<button type="button" class="ecc-btn ecc-btn--ghost ecc-btn--sm" id="admU360Retry">تلاش مجدد</button></p>');
                const retry = document.getElementById('admU360Retry');
                if (retry) retry.addEventListener('click', function () {
                    delete tabCache[cacheKey];
                    loadTab(tab, query, true);
                });
            })
            .finally(function () {
                if (version === requestVersion) activeRequest = null;
            });
    }

    panel.addEventListener('change', function (e) {
        const statusRadio = e.target.closest('[data-u360-lic-field="status"]');
        if (statusRadio && activeTab === 'licenses' && statusRadio.type === 'radio' && statusRadio.checked) {
            const licenseId = statusRadio.getAttribute('data-u360-lic');
            const nextStatus = statusRadio.value || '';
            const group = statusRadio.closest('.adm-u360-lic-radios');
            const current = group ? group.getAttribute('data-current-status') : '';
            if (!licenseId || !nextStatus || nextStatus === current) return;
            const radios = panel.querySelectorAll(
                '[data-u360-lic-field="status"][data-u360-lic="' + licenseId + '"]'
            );
            const busy = Array.prototype.slice.call(radios);
            submitLicenseAction(licenseId, { action: 'set_status', status: nextStatus }, busy)
                .catch(function () {
                    if (group && current) {
                        radios.forEach(function (r) {
                            r.checked = r.value === current;
                        });
                    }
                });
            return;
        }
        const expiryInput = e.target.closest('[data-u360-lic-expiry]');
        if (expiryInput && activeTab === 'licenses') {
            const licenseId = expiryInput.getAttribute('data-u360-lic-expiry');
            const nextDate = String(expiryInput.value || '').trim();
            const initial = String(expiryInput.getAttribute('data-initial-value') || '').trim();
            if (!licenseId || !nextDate || nextDate === initial) return;
            const jalali = composeExpiryJalaliForSave(
                nextDate,
                expiryInput.getAttribute('data-expiry-time')
            );
            expiryInput.disabled = true;
            submitLicenseAction(licenseId, {
                action: 'adjust_expiry',
                mode: 'set_datetime',
                expires_jalali: jalali,
            }, [expiryInput])
                .catch(function () {
                    expiryInput.value = initial;
                });
            return;
        }
        const alogFilter = e.target.closest('[data-u360-alog-filter]');
        if (alogFilter && activeTab === 'admin_log') {
            const name = alogFilter.getAttribute('data-u360-alog-filter');
            if (name === 'kind') {
                const query = Object.assign({}, tabQueryState.admin_log || {}, { page: 1 });
                query.kind = alogFilter.value;
                loadTab('admin_log', query, true);
            }
            return;
        }
        const filter = e.target.closest('[data-u360-activity-filter]');
        if (!filter || activeTab !== 'activity') return;
        const name = filter.getAttribute('data-u360-activity-filter');
        if (!['kind', 'platform', 'success', 'sort'].includes(name)) return;
        const query = Object.assign({}, tabQueryState.activity || {}, { page: 1 });
        query[name] = filter.value;
        loadTab('activity', query, true);
    });

    panel.addEventListener('click', function (e) {
        const licBtn = e.target.closest('[data-u360-lic-action]');
        if (licBtn && activeTab === 'licenses') {
            const licenseId = licBtn.getAttribute('data-u360-lic');
            const action = licBtn.getAttribute('data-u360-lic-action');
            if (!licenseId || !action) return;
            const body = { action: action };
            if (action === 'set_status') {
                return;
            } else if (action === 'adjust_expiry') {
                body.action = 'adjust_expiry';
                const mode = licBtn.getAttribute('data-mode');
                if (mode === 'clear') {
                    body.mode = 'clear';
                } else {
                    body.days = parseInt(licBtn.getAttribute('data-days') || '0', 10);
                }
            } else if (action === 'set_max_activations') {
                body.action = 'set_max_activations';
                const maxInput = panel.querySelector('[data-u360-lic-max="' + licenseId + '"]');
                body.max_activations = maxInput ? parseInt(maxInput.value || '0', 10) : 0;
            } else if (action === 'set_activation_active') {
                body.action = 'set_activation_active';
                body.activation_id = licBtn.getAttribute('data-activation-id');
                body.is_active = licBtn.getAttribute('data-active') === '1';
            } else if (action === 'remove_activation') {
                if (!window.confirm('اسلات حذف شود؟ این عمل قابل بازگشت از UI نیست.')) return;
                body.action = 'remove_activation';
                body.activation_id = licBtn.getAttribute('data-activation-id');
            } else if (action === 'revoke_assignment') {
                if (!window.confirm('تخصیص عضو لغو شود؟')) return;
                body.action = 'revoke_assignment';
            } else {
                return;
            }
            submitLicenseAction(licenseId, body, [licBtn]);
            return;
        }
        if (e.target.closest('[data-u360-alog-reset]')) {
            const query = Object.assign({}, tabQueryState.admin_log || {}, { page: 1, kind: '' });
            loadTab('admin_log', query, true);
            return;
        }
        if (!e.target.closest('[data-u360-activity-reset]')) return;
        const query = Object.assign({}, tabQueryState.activity || {}, {
            page: 1, kind: '', platform: '', success: '', sort: '-at',
        });
        loadTab('activity', query, true);
    });

    panel.addEventListener('click', function (e) {
        const pageBtn = e.target.closest('[data-u360-page]');
        if (!pageBtn || pageBtn.disabled) return;
        const tab = pageBtn.getAttribute('data-u360-page');
        const page = pageBtn.getAttribute('data-page');
        loadTab(tab, { page: page }, true);
    });

    if (tabsNav) {
        tabsNav.addEventListener('click', function (e) {
            const btn = e.target.closest('[data-u360-tab]');
            if (!btn) return;
            loadTab(btn.getAttribute('data-u360-tab'));
        });
        tabsNav.addEventListener('scroll', syncTabsScrollUI, { passive: true });
    }

    if (typeof ResizeObserver !== 'undefined' && tabsNav) {
        const tabsRo = new ResizeObserver(function () {
            syncTabsScrollUI();
        });
        tabsRo.observe(tabsNav);
    } else {
        window.addEventListener('resize', syncTabsScrollUI);
    }
    syncTabsScrollUI();

    if (kpisEl) {
        kpisEl.addEventListener('scroll', syncKpisScrollUI, { passive: true });
    }
    if (typeof ResizeObserver !== 'undefined' && kpisEl) {
        const kpisRo = new ResizeObserver(syncKpisScrollUI);
        kpisRo.observe(kpisEl);
    } else {
        window.addEventListener('resize', syncKpisScrollUI);
    }
    syncKpisScrollUI();

    root.querySelectorAll('[data-u360-anchor]').forEach(function (kpi) {
        kpi.addEventListener('click', function () {
            const anchor = kpi.getAttribute('data-u360-anchor');
            if (anchor) loadTab(anchor);
        });
    });

    const copyBtn = document.getElementById('admU360CopyPhone');
    if (copyBtn) {
        copyBtn.addEventListener('click', function () {
            const phone = copyBtn.getAttribute('data-phone') || '';
            if (!phone || !navigator.clipboard) return;
            navigator.clipboard.writeText(phone).then(function () {
                copyBtn.classList.add('is-done');
                setTimeout(function () { copyBtn.classList.remove('is-done'); }, 1400);
            }).catch(function () {});
        });
    }

    panel.addEventListener('click', function (e) {
        const jump = e.target.closest('[data-u360-tab-jump]');
        if (jump) {
            loadTab(jump.getAttribute('data-u360-tab-jump'));
            return;
        }
        const btn = e.target.closest('.adm-u360-sms-info');
        if (!btn) {
            if (!e.target.closest('.adm-u360-sms-popover')) {
                closeAllSmsPopovers();
            }
            return;
        }
        e.stopPropagation();
        const cell = btn.closest('.adm-u360-sms-cell');
        const pop = cell && cell.querySelector('.adm-u360-sms-popover');
        if (!pop) return;
        const willOpen = pop.hidden;
        closeAllSmsPopovers();
        if (willOpen) {
            openSmsPopover(btn, pop);
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllSmsPopovers();
    });

    panel.addEventListener('click', function (e) {
        const pick = e.target.closest('[data-u360-support-ticket]');
        if (!pick) return;
        const id = pick.getAttribute('data-u360-support-ticket');
        tabQueryState.support = Object.assign({}, tabQueryState.support || {}, { ticket: id });
        loadSupportTicketDetail(id);
    });

    panel.addEventListener('click', function (e) {
        if (activeTab !== 'support') return;
        const canManage = !!(bootstrap.permissions || {}).can_manage_support_tickets;
        if (!canManage) return;
        const ws = supportWorkspaceEl();
        if (!ws || !supportDeskSelectedId) return;

        function showFeedback(msg, ok) {
            const el = ws.querySelector('[data-u360-support-feedback]');
            if (!el) return;
            el.hidden = false;
            el.textContent = msg;
            el.classList.toggle('is-error', !ok);
            el.classList.toggle('is-ok', !!ok);
        }

        if (e.target.closest('[data-u360-support-send]')) {
            const ta = ws.querySelector('#admU360SupportBody');
            const body = (ta && ta.value || '').trim();
            const isInternal = !!(ws.querySelector('[data-u360-support-internal]') && ws.querySelector('[data-u360-support-internal]').checked);
            const statusSel = ws.querySelector('[data-u360-support-after-status]');
            const status = statusSel ? statusSel.value : '';
            if (!body) {
                showFeedback('متن پیام را بنویسید.', false);
                return;
            }
            const btn = e.target.closest('[data-u360-support-send]');
            btn.disabled = true;
            postSupportTicketAction(supportDeskSelectedId, {
                action: 'reply',
                body: body,
                is_internal: isInternal,
                status: isInternal ? '' : status,
            }).then(function (data) {
                if (ta) ta.value = '';
                paintSupportWorkspace(renderSupportWorkspaceDetail(data.ticket, true));
                showFeedback(isInternal ? 'یادداشت ذخیره شد.' : 'پاسخ برای مشتری ارسال شد.', true);
                delete tabCache['support' + JSON.stringify(tabQueryState.support || {})];
            }).catch(function (err) {
                showFeedback(err.message || 'ارسال ناموفق بود.', false);
            }).finally(function () {
                btn.disabled = false;
            });
            return;
        }

        if (e.target.closest('[data-u360-support-close]')) {
            postSupportTicketAction(supportDeskSelectedId, { action: 'close' })
                .then(function (data) {
                    paintSupportWorkspace(renderSupportWorkspaceDetail(data.ticket, true));
                    showFeedback('تیکت بسته شد.', true);
                })
                .catch(function (err) { showFeedback(err.message, false); });
            return;
        }

        if (e.target.closest('[data-u360-support-reopen]')) {
            postSupportTicketAction(supportDeskSelectedId, { action: 'reopen' })
                .then(function (data) {
                    paintSupportWorkspace(renderSupportWorkspaceDetail(data.ticket, true));
                    showFeedback('تیکت باز شد.', true);
                })
                .catch(function (err) { showFeedback(err.message, false); });
            return;
        }

        if (e.target.closest('[data-u360-support-save-meta]')) {
            const statusEl = ws.querySelector('[data-u360-support-field="status"]');
            const priEl = ws.querySelector('[data-u360-support-field="priority"]');
            postSupportTicketAction(supportDeskSelectedId, {
                action: 'update_meta',
                status: statusEl ? statusEl.value : '',
                priority: priEl ? priEl.value : '',
            }).then(function (data) {
                paintSupportWorkspace(renderSupportWorkspaceDetail(data.ticket, true));
                showFeedback('وضعیت ذخیره شد.', true);
            }).catch(function (err) { showFeedback(err.message, false); });
        }
    });

    (function initSupportFromQuery() {
        const params = new URLSearchParams(window.location.search);
        const ticket = (params.get('ticket') || '').trim();
        if (!ticket) return;
        tabQueryState.support = Object.assign({}, tabQueryState.support || {}, {
            ticket: ticket,
            page: tabQueryState.support && tabQueryState.support.page ? tabQueryState.support.page : '1',
        });
        supportDeskSelectedId = ticket;
    })();

    loadTab(activeTab);
})();
