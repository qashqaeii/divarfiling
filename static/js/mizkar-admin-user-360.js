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
            return toFa((n / 1000000).toFixed(abs >= 10000000 ? 0 : 1)) + 'M';
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

    function emptyState(title, hint) {
        return '<div class="adm-u360-empty-state">'
            + '<span class="adm-u360-empty-state__icon" aria-hidden="true"><i class="fas fa-layer-group"></i></span>'
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
        const preview = row.message_preview || '—';
        const detail = row.message_detail || preview;
        const excerpt = preview.length > 52 ? preview.slice(0, 52) + '…' : preview;
        const body = detail.split('\n').map(function (line) { return esc(line); }).join('<br>');
        return '<td data-label="متن پیام"><div class="adm-u360-sms-cell">'
            + '<span class="adm-u360-sms-cell__excerpt">' + esc(excerpt) + '</span>'
            + '<button type="button" class="adm-u360-sms-info" aria-label="نمایش متن پیامک" aria-expanded="false">'
            + '<i class="fas fa-circle-info" aria-hidden="true"></i></button>'
            + '<div class="adm-u360-sms-popover" role="dialog" aria-label="متن پیامک" hidden>'
            + '<p class="adm-u360-sms-popover__title">متن و جزئیات پیامک</p>'
            + '<div class="adm-u360-sms-popover__inner">' + body + '</div>'
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
        mountChart(chartId, {
            type: 'doughnut',
            data: {
                labels: rows.map(function (r) { return toFa(r.label || r.key || '—'); }),
                datasets: [{
                    data: rows.map(function (r) { return r.count; }),
                    backgroundColor: rows.map(function (r, i) { return CHART_PALETTE[i % CHART_PALETTE.length]; }),
                    borderWidth: 0,
                    hoverOffset: 4,
                }],
            },
            options: chartOptions({
                cutout: '70%',
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
        mountChart(chartId, {
            type: 'bar',
            data: {
                labels: rows.map(revenueMonthLabel),
                datasets: [{
                    label: 'درآمد',
                    data: totals,
                    backgroundColor: totals.map(function (v) {
                        if (!v) return 'rgba(148, 163, 184, 0.22)';
                        const alpha = maxVal ? 0.35 + (v / maxVal) * 0.5 : 0.75;
                        return 'rgba(91, 79, 207, ' + alpha.toFixed(2) + ')';
                    }),
                    borderColor: totals.map(function (v) {
                        return v ? 'rgba(91, 79, 207, 0.55)' : 'rgba(148, 163, 184, 0.2)';
                    }),
                    borderWidth: 1,
                    borderRadius: 8,
                    borderSkipped: false,
                    maxBarThickness: 44,
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
                        border: { display: false },
                        grid: { color: 'rgba(148, 163, 184, 0.12)', drawTicks: false },
                        ticks: {
                            maxTicksLimit: 5,
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
                            autoSkip: false,
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
                    + '<span class="adm-u360-finance-legend__label">' + esc(row.label || row.key || '—') + '</span>'
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
        if (!orders.length && !revenue.length) return '';

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
                + '<canvas id="admU360ChartOrders" role="img" aria-label="ترکیب سفارش‌ها"></canvas></div>'
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
                + '<canvas id="admU360ChartRevenue" role="img" aria-label="درآمد پرداخت‌شده"></canvas></div>'
                + '</div>';
        }
        panels += '</div>';

        const stats = '<dl class="adm-u360-finance-stats">'
            + '<div class="adm-u360-finance-stat"><dt>درآمد موفق</dt><dd>' + moneyTomans(pay.total_paid || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>سفارش پرداخت‌شده</dt><dd>' + toFa(pay.paid_orders || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>در انتظار</dt><dd class="'
            + (pay.pending_orders ? 'adm-u360-finance-stat__val--warn' : '')
            + '">' + toFa(pay.pending_orders || 0) + '</dd></div>'
            + '</dl>';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-finance" aria-label="روند مالی">'
            + '<header class="adm-u360-overview-finance__head">'
            + '<h2 class="adm-u360-overview-finance__title">'
            + '<i class="fas fa-chart-line" aria-hidden="true"></i>'
            + '<span>روند مالی</span></h2>'
            + '<p class="adm-u360-overview-finance__lead">خلاصه پرداخت و روند شش‌ماهه</p>'
            + '</header>'
            + '<div class="adm-u360-overview-finance__body">'
            + stats
            + panels
            + '</div></section>';
    }

    function renderOverviewRecentCard(ordersRowsHtml, licensesRowsHtml) {
        const tableClass = ' adm-u360-overview-recent-table';
        const ordersTable = miniTable(
            ['محصول', 'مبلغ', 'وضعیت', 'تاریخ'],
            ordersRowsHtml,
            tableClass.trim()
        );
        const licensesTable = licensesRowsHtml
            ? miniTable(['پلن', 'وضعیت', 'انقضا', 'صدور'], licensesRowsHtml, tableClass.trim())
            : '<div class="adm-u360-overview-recent-table adm-u360-overview-recent-table--empty">'
                + emptyState('لایسنسی ثبت نشده', 'پس از خرید یا فعال‌سازی در این بخش نمایش داده می‌شود.')
                + '</div>';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-recent" aria-label="آخرین سفارش‌ها و لایسنس‌ها">'
            + '<header class="adm-u360-overview-recent__head">'
            + '<h2 class="adm-u360-overview-recent__title">'
            + '<i class="fas fa-clock-rotate-left" aria-hidden="true"></i>'
            + '<span>آخرین تراکنش‌ها</span></h2>'
            + '</header>'
            + '<div class="adm-u360-overview-recent__grid">'
            + '<div class="adm-u360-overview-recent__col">'
            + subTitle('سفارش‌ها', 'fa-receipt')
            + '<div class="adm-u360-overview-recent__panel">' + ordersTable + '</div>'
            + '</div>'
            + '<div class="adm-u360-overview-recent__col">'
            + subTitle('لایسنس‌ها', 'fa-key')
            + '<div class="adm-u360-overview-recent__panel">' + licensesTable + '</div>'
            + '</div>'
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

    function paintPanel(html, tabKey) {
        closeAllSmsPopovers();
        destroyCharts();
        panel.classList.remove('is-loading');
        panel.setAttribute('aria-busy', 'false');
        panel.classList.remove('is-enter');
        const pane = tabKey || activeTab;
        panel.innerHTML = '<div class="adm-u360-tab-stack" data-u360-tab-pane="' + esc(pane) + '">' + html + '</div>';
        void panel.offsetWidth;
        panel.classList.add('is-enter');
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

    function renderOverviewPulseCard(insightsHtml, signalsHtml) {
        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-pulse" aria-label="بینش و وضعیت کلیدی">'
            + '<header class="adm-u360-overview-pulse__head">'
            + '<h2 class="adm-u360-overview-pulse__title">'
            + '<i class="fas fa-compass" aria-hidden="true"></i>'
            + '<span>تمرکز پرونده</span></h2>'
            + '<p class="adm-u360-overview-pulse__lead">بینش‌های اقدام و وضعیت‌های مهم در یک نگاه</p>'
            + '</header>'
            + '<div class="adm-u360-overview-pulse__body">'
            + '<div class="adm-u360-overview-pulse__col adm-u360-overview-pulse__col--insights">'
            + subTitle('بینش و اولویت', 'fa-lightbulb')
            + insightsHtml
            + '</div>'
            + '<div class="adm-u360-overview-pulse__col adm-u360-overview-pulse__col--signals">'
            + subTitle('وضعیت کلیدی', 'fa-bolt')
            + signalsHtml
            + '</div>'
            + '</div></section>';
    }

    function overviewHealthBanner(warnCount, sub, pay) {
        let tone = 'neutral';
        let badge = 'پرونده آماده بررسی';
        let icon = 'fa-user-check';
        if (warnCount) {
            tone = 'warn';
            badge = 'نیاز به پیگیری';
            icon = 'fa-triangle-exclamation';
        } else if (pay.pending_orders) {
            tone = 'info';
            badge = 'سفارش در انتظار';
            icon = 'fa-hourglass-half';
        } else if (sub.has_access) {
            tone = 'ok';
            badge = 'دسترسی فعال';
            icon = 'fa-circle-check';
        }
        const leadText = warnCount
            ? toFa(warnCount) + ' مورد هشدار در بینش‌های موجود؛ برای جزئیات بخش اولویت‌ها را بررسی کنید.'
            : (pay.pending_orders
                ? toFa(pay.pending_orders) + ' سفارش در انتظار بررسی است.'
                : 'نمای کلی بر اساس اطلاعات ثبت‌شده؛ نبود هشدار به معنی تأیید قطعی سلامت حساب نیست.');
        return '<header class="adm-u360-overview-hero adm-u360-overview-hero--' + tone + '">'
            + '<span class="adm-u360-overview-hero__badge">'
            + '<i class="fas ' + icon + '" aria-hidden="true"></i> ' + esc(badge) + '</span>'
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
        const winParts = [];
        if (eng.windows_downloaded) winParts.push('دانلود');
        if (eng.windows_activated) winParts.push('فعال');
        if (eng.windows_launched) winParts.push('اجرا');
        signals.push({
            icon: 'fa-desktop',
            tone: eng.windows_launched ? 'ok' : '',
            title: 'ویندوز',
            value: winParts.length ? winParts.join(' · ') : 'بدون فعالیت ثبت‌شده',
            meta: 'آخرین ورود ' + esc(eng.last_login_jalali || '—'),
            tab: 'devices',
        });
        signals.push({
            icon: 'fa-mobile-screen',
            tone: eng.android_installed ? 'ok' : '',
            title: 'اندروید',
            value: eng.android_installed
                ? toFa(eng.android_devices || 0) + ' دستگاه'
                : 'نصب ثبت نشده',
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
        const insightsHtml = renderInsightsPanel(data.insights || []);
        const insights = data.insights || [];
        const warnCount = insights.filter(function (i) { return i.severity === 'warn'; }).length;

        const orders = (data.recent_orders || []).map(function (o) {
            return '<tr>'
                + td(esc(o.product), 'محصول')
                + td(moneyTomans(o.amount), 'مبلغ')
                + td(esc(o.status_label), 'وضعیت')
                + td(esc(o.created_jalali), 'تاریخ')
                + '</tr>';
        }).join('');

        const licenses = (data.recent_licenses || []).map(function (l) {
            return '<tr>'
                + td(esc(l.plan), 'پلن')
                + td(esc(l.status_label), 'وضعیت')
                + td(esc(l.expires_jalali), 'انقضا')
                + td(esc(l.created_jalali), 'صدور')
                + '</tr>';
        }).join('');

        const charts = data.charts || {};
        const signalsHtml = renderOverviewSignals(h);
        const financeCardHtml = renderOverviewFinanceCard(charts, pay);

        // The overview's primary KPIs use the same server-provided highlights as its detail panels.
        // Do not infer account health from missing telemetry or treat pending orders as revenue.
        const kpis = [
            { label: 'دسترسی اشتراک', value: esc(sub.access_label || (sub.has_access ? 'فعال' : 'بدون دسترسی فعال')), meta: esc(sub.plan || 'وضعیت فعلی'), tab: 'licenses', tone: sub.has_access ? 'ok' : 'neutral' },
            { label: 'درآمد پرداخت‌شده', value: moneyTomans(pay.total_paid || 0), meta: 'فقط سفارش‌های موفق', tab: 'commerce', tone: 'neutral' },
            { label: 'سفارش در انتظار', value: toFa(pay.pending_orders || 0), meta: 'نیازمند بررسی پرداخت', tab: 'commerce', tone: pay.pending_orders ? 'warn' : 'neutral' },
            { label: 'موارد هشدار', value: toFa(warnCount), meta: 'از بینش‌های ثبت‌شده', tab: 'overview', tone: warnCount ? 'warn' : 'ok' },
        ];
        const kpiHtml = '<section class="adm-u360-overview-kpis" aria-label="شاخص‌های اصلی پرونده">'
            + kpis.map(function (k) {
                return '<article class="adm-u360-overview-kpi adm-u360-overview-kpi--' + k.tone + '">'
                    + '<span class="adm-u360-overview-kpi__label">' + k.label + '</span>'
                    + '<strong class="adm-u360-overview-kpi__value">' + k.value + '</strong>'
                    + '<span class="adm-u360-overview-kpi__meta">' + k.meta + '</span>'
                    + (k.tab === 'overview' ? '' : overviewJumpChip('مشاهده', k.tab, 'fa-arrow-left'))
                    + '</article>';
            }).join('') + '</section>';
        const overviewMain = '<div class="adm-u360-overview-main">'
            + kpiHtml
            + renderOverviewPulseCard(insightsHtml, signalsHtml)
            + '</div>';

        let overviewFoot = '<div class="adm-u360-overview-foot">';
        if (financeCardHtml) {
            overviewFoot += financeCardHtml;
        }
        overviewFoot += renderOverviewRecentCard(orders, licenses);
        overviewFoot += '</div>';

        paintPanel(
            '<div class="adm-u360-overview">'
            + overviewHealthBanner(warnCount, sub, pay)
            + tabLayout({
                content: overviewMain + overviewFoot,
            }, 'adm-u360-tab-layout--overview')
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
        return '<div class="adm-u360-account-field' + full + '" role="listitem">'
            + '<span class="adm-u360-account-field__icon" aria-hidden="true"><i class="fas ' + field.icon + '"></i></span>'
            + '<span class="adm-u360-account-field__label">' + esc(field.label) + '</span>'
            + '<div class="adm-u360-account-field__main">'
            + '<span class="adm-u360-account-field__value' + ltr + '">' + field.value + '</span>'
            + meta
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
                    { icon: 'fa-phone', label: 'موبایل', value: esc(id.phone || '—'), ltr: true },
                    { icon: 'fa-envelope', label: 'ایمیل', value: id.email ? esc(id.email) : '—', ltr: true },
                    { icon: 'fa-at', label: 'نام کاربری', value: esc(id.username || '—'), ltr: true },
                    {
                        icon: 'fa-fingerprint',
                        label: 'کد ملی',
                        value: esc(id.national_id || '—') + nationalToolbar,
                        ltr: true,
                    },
                    { icon: 'fa-user-tag', label: 'معرف', value: esc(referral.referred_by || '—') },
                    { icon: 'fa-hashtag', label: 'شناسه کاربر', value: toFa(id.id) },
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
        const revealBtn = document.getElementById('admU360RevealNational');
        if (revealBtn) {
            revealBtn.addEventListener('click', function () {
                loadTab('account', { reveal_sensitive: '1' }, true);
            });
        }
    }

    function shortUuid(id) {
        if (!id) return '—';
        const raw = String(id);
        return '<span class="adm-u360-ltr adm-u360-id" title="' + esc(raw) + '">…' + esc(raw.slice(-8)) + '</span>';
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
        if (!orders.length && !revenue.length && !sum.total_revenue_paid_only) {
            return '';
        }

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
            + '<p class="adm-u360-overview-finance__lead">درآمد، ترکیب سفارش و روند شش‌ماهه</p>'
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
        const meta = pagination && pagination.total
            ? '<p class="adm-u360-commerce-card__meta">' + toFa(pagination.total) + ' سفارش در پرونده</p>'
            : '';
        return commerceCard('سفارش‌ها', 'fa-receipt', meta + table + pager, 'adm-u360-commerce-card--orders');
    }

    function renderCommerceTransactionsCard(transactions) {
        const rows = (transactions || []).map(function (t) {
            return '<tr>'
                + td(shortUuid(t.order_id), 'سفارش')
                + td('<span class="adm-u360-ltr">' + esc(t.gateway_ref || '—') + '</span>', 'مرجع درگاه')
                + td(moneyTomans(t.amount), 'مبلغ')
                + td(orderStatusChip(t.status, t.status), 'وضعیت')
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

    function renderLicenseAccessCard(access, charts) {
        access = access || {};
        charts = charts || {};
        const statusRows = charts.license_status || [];
        const statusTotal = chartRowsSum(statusRows, 'count');

        let chartPanel = '';
        if (statusRows.length) {
            chartPanel = '<div class="adm-u360-license-chart">'
                + '<div class="adm-u360-finance-panel__head">'
                + '<h3 class="adm-u360-finance-panel__title">وضعیت لایسنس‌ها</h3>'
                + '<span class="adm-u360-finance-panel__meta">' + toFa(statusTotal) + ' رکورد</span>'
                + '</div>'
                + '<div class="adm-u360-finance-panel__split adm-u360-license-chart__split">'
                + renderFinanceOrderLegend(statusRows)
                + '<div class="adm-u360-chart-wrap adm-u360-chart-wrap--donut adm-u360-chart-wrap--finance">'
                + '<canvas id="admU360LicenseChartStatus" role="img" aria-label="وضعیت لایسنس‌ها"></canvas>'
                + '</div></div></div>';
        }

        const accessDdClass = access.has_bot_access
            ? ''
            : (access.pending_activation ? ' adm-u360-finance-stat__val--warn' : '');
        const stats = '<dl class="adm-u360-finance-stats adm-u360-finance-stats--license">'
            + '<div class="adm-u360-finance-stat adm-u360-finance-stat--emph"><dt>دسترسی ربات</dt><dd class="'
            + accessDdClass + '">' + esc(access.access_label || '—') + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>پلن فعلی</dt><dd>' + esc(access.plan || '—') + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>انقضا</dt><dd>' + esc(access.expires_jalali || '—') + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>لایسنس در پرونده</dt><dd>' + toFa(access.license_count || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>دستگاه فعال</dt><dd>'
            + toFa(access.activations_active || 0) + ' / ' + toFa(access.activations_total || 0) + '</dd></div>'
            + '<div class="adm-u360-finance-stat"><dt>فعال‌سازی معلق</dt><dd class="'
            + (access.pending_activation ? 'adm-u360-finance-stat__val--warn' : '')
            + '">' + boolChip(!access.pending_activation, 'خیر', 'بله — نیاز به اقدام') + '</dd></div>'
            + '</dl>';

        return '<section class="adm-u360-block adm-u360-block--card adm-u360-overview-finance adm-u360-license-summary" aria-label="دسترسی و اشتراک">'
            + '<header class="adm-u360-overview-finance__head">'
            + '<h2 class="adm-u360-overview-finance__title">'
            + '<i class="fas fa-key" aria-hidden="true"></i>'
            + '<span>دسترسی و اشتراک</span></h2>'
            + '<p class="adm-u360-overview-finance__lead">وضعیت فعلی ربات، ظرفیت و ترکیب لایسنس‌ها</p>'
            + '</header>'
            + '<div class="adm-u360-overview-finance__body adm-u360-license-summary__body">'
            + stats
            + chartPanel
            + '</div></section>';
    }

    function renderLicenseListCard(licenses) {
        const rows = (licenses || []).map(function (l) {
            const slots = '<span class="adm-u360-license-slots">' + toFa(l.slots_used) + ' / ' + toFa(l.max_activations) + '</span>';
            const planCell = '<div class="adm-u360-commerce-product">'
                + '<span class="adm-u360-commerce-product__name">' + esc(l.plan) + '</span>'
                + '<span class="adm-u360-commerce-tag">' + esc(l.relation) + '</span>'
                + '</div>';
            return '<tr>'
                + td(toFa(l.id), 'شناسه')
                + td(planCell, 'پلن')
                + td(licenseStatusChip(l.status, l.status_label, l.entitlement_valid), 'وضعیت')
                + td(slots, 'اسلات')
                + td(esc(l.expires_jalali), 'انقضا')
                + td(esc(l.created_jalali), 'صدور')
                + '</tr>';
        }).join('');
        const body = rows
            ? miniTable(['شناسه', 'پلن', 'وضعیت', 'اسلات', 'انقضا', 'صدور'], rows, 'adm-u360-commerce-table')
            : emptyState('لایسنسی ثبت نشده', 'پس از خرید یا تخصیص، لایسنس‌ها اینجا نمایش داده می‌شوند.');
        const meta = licenses && licenses.length
            ? '<p class="adm-u360-commerce-card__meta">' + toFa(licenses.length) + ' لایسنس (مالک + اختصاصی)</p>'
            : '';
        return commerceCard('لایسنس‌ها', 'fa-key', meta + body, 'adm-u360-license-card--list');
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

    function renderLicenseGrantsCard(grants) {
        const rows = (grants || []).map(function (g) {
            return '<tr>'
                + td('<span class="adm-u360-ltr">' + esc(g.campaign_key || '—') + '</span>', 'کمپین')
                + td(esc(g.status || '—'), 'وضعیت')
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
        const charts = d.charts || {};
        const html = '<div class="adm-u360-licenses">'
            + renderLicenseAccessCard(access, charts)
            + '<div class="adm-u360-commerce__grid adm-u360-licenses__grid">'
            + renderLicenseListCard(d.licenses)
            + '<div class="adm-u360-commerce__stack adm-u360-licenses__stack">'
            + renderLicenseActivationsCard(d.activations)
            + renderLicenseGrantsCard(d.campaign_grants)
            + '</div></div></div>';

        paintPanel(html, 'licenses');
        window.requestAnimationFrame(function () {
            mountOverviewDoughnut('admU360LicenseChartStatus', charts.license_status);
        });
    }

    function renderActivity(d) {
        const toolbar = panelRangeHint();
        const rows = (d.events || []).map(function (ev) {
            const st = ev.success === false ? 'ناموفق' : ev.success === true ? 'موفق' : '—';
            return '<tr>'
                + td(esc(ev.kind_label), 'نوع')
                + td(esc(ev.title) + (ev.detail ? '<small>' + esc(ev.detail) + '</small>' : ''), 'عنوان')
                + td(esc(ev.platform_label || ev.platform), 'پلتفرم')
                + td(st, 'نتیجه')
                + td(esc(ev.at_jalali), 'زمان')
                + '</tr>';
        }).join('');
        const actPts = (d.charts && d.charts.activity_daily) || [];
        const actChart = actPts.length
            ? chartsRow(chartCard('رویدادها در بازه انتخابی', 'admU360ActChart', 'adm-u360-chart-wrap--wide', 'fa-chart-bar'))
            : '';
        paintPanel(tabPanel('فعالیت و رفتار', tabIcon('activity'), {
            metrics: statStrip([
                { label: 'رویداد در این صفحه', value: toFa((d.events || []).length) },
                { label: 'کل (صفحه‌بندی)', value: toFa((d.pagination && d.pagination.total) || (d.events || []).length) },
            ]),
            toolbar: toolbar,
            viz: actChart,
            content: miniTable(['نوع', 'عنوان', 'پلتفرم', 'نتیجه', 'زمان'], rows)
                + renderPager(d.pagination, 'activity'),
        }));
        window.requestAnimationFrame(function () {
            mountBarActivity('admU360ActChart', actPts);
        });
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
        if (tab === 'usage') {
            const feats = data.features || [];
            const usedCount = feats.filter(function (f) { return f.started || (f.count && f.count > 0); }).length;
            const rows = feats.map(function (f) {
                const started = f.started ? 'بله' : (f.note === 'بدون رکورد' ? 'ثبت نشده' : 'خیر');
                return '<tr>'
                    + td(esc(f.name), 'قابلیت')
                    + td(started, 'شروع')
                    + td(toFa(f.count), 'تعداد')
                    + td(esc(f.last_at_jalali || '—'), 'آخرین')
                    + '</tr>';
            }).join('');
            const feat = (data.charts && data.charts.feature_usage) || [];
            const chartPart = feat.length
                ? chartsRow(chartCard('شدت استفاده از امکانات', 'admU360UsageBars', 'adm-u360-chart-wrap--tall', 'fa-chart-bar'))
                : '';
            paintPanel(tabPanel('استفاده از امکانات', tabIcon('usage'), {
                metrics: statStrip([
                    { label: 'قابلیت‌های استفاده‌شده', value: toFa(usedCount) + ' / ' + toFa(feats.length) },
                ]),
                toolbar: panelRangeHint(),
                viz: chartPart,
                content: miniTable(['قابلیت', 'شروع', 'تعداد', 'آخرین'], rows),
            }));
            window.requestAnimationFrame(function () {
                mountHorizontalBars('admU360UsageBars', feat);
            });
            return;
        }
        if (tab === 'devices') {
            const win = data.windows || {};
            const flags = win.flags || {};
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
                metrics: statStrip([
                    { label: 'ویندوز · دانلود', value: flags.downloaded ? 'بله' : 'خیر', tone: flags.downloaded ? 'ok' : '' },
                    { label: 'ویندوز · فعال‌سازی', value: flags.activated ? 'بله' : 'خیر', tone: flags.activated ? 'ok' : '' },
                    { label: 'اندروید', value: androidCount ? toFa(androidCount) + ' دستگاه' : 'ثبت نشده', tone: androidCount ? 'ok' : '' },
                ]),
                toolbar: panelRangeHint(),
                viz: chartPart,
                content: content,
            }));
            window.requestAnimationFrame(function () {
                mountDoughnut('admU360DevPlatform', plat);
            });
            return;
        }
        if (tab === 'support') {
            const perms = bootstrap.permissions || {};
            let toolbar = '';
            if (perms.can_view_internal_tickets) {
                toolbar = '<div class="adm-u360-toolbar"><label class="adm-u360-check">'
                    + '<input type="checkbox" id="admU360SupportInternal" '
                    + (data.include_internal_notes ? 'checked' : '') + '> نمایش یادداشت‌های داخلی</label></div>';
            }
            let content = '';
            let ticketStack = '<div class="adm-u360-ticket-stack">';
            (data.tickets || []).forEach(function (t) {
                ticketStack += '<article class="adm-u360-ticket">'
                    + '<header class="adm-u360-ticket__head"><p class="adm-u360-ticket__title">'
                    + esc(t.ticket_number) + ' — ' + esc(t.subject) + '</p>'
                    + (t.admin_url
                        ? '<a href="' + esc(t.admin_url) + '" class="ecc-btn ecc-btn--ghost ecc-btn--sm" target="_blank" rel="noopener">مدیریت</a>'
                        : '')
                    + '</header><p class="adm-u360-ticket__meta">'
                    + esc(t.status) + ' · ' + esc(t.priority) + ' · ' + esc(t.last_message_jalali) + '</p>';
                (t.recent_messages || []).forEach(function (m) {
                    ticketStack += '<div class="adm-u360-msg"><div class="adm-u360-msg__head"><strong>'
                        + esc(m.author) + '</strong> '
                        + (m.is_internal ? '<span class="ecc-um-flag ecc-um-flag--warn">داخلی</span> ' : '')
                        + '<span>' + esc(m.created_jalali) + '</span></div>'
                        + '<div class="adm-u360-msg__body">' + esc(m.body_preview) + '</div></div>';
                });
                ticketStack += '</article>';
            });
            ticketStack += '</div>';
            if (!(data.tickets || []).length) {
                content += emptyState('تیکتی ثبت نشده', 'هنوز درخواست پشتیبانی از این مشتری در سیستم نیست.');
            } else {
                content += ticketStack;
            }
            content += renderPager(data.pagination, 'support');
            const tStats = (data.charts && data.charts.tickets_by_status) || [];
            const chartPart = tStats.length
                ? chartsRow(chartCard('وضعیت تیکت‌ها', 'admU360SupportStatus', 'adm-u360-chart-wrap--donut', 'fa-chart-pie'))
                : '';
            paintPanel(tabPanel('پشتیبانی و تیکت‌ها', tabIcon('support'), {
                metrics: statStrip([
                    { label: 'تیکت باز', value: toFa((data.stats && data.stats.open) || 0), tone: (data.stats && data.stats.open) ? 'warn' : '' },
                    { label: 'خوانده‌نشده', value: toFa((data.stats && data.stats.staff_unread) || 0) },
                    { label: 'کل تیکت‌ها', value: toFa((data.stats && data.stats.total) || 0) },
                ]),
                toolbar: toolbar + panelRangeHint(),
                viz: chartPart,
                content: content,
            }));
            window.requestAnimationFrame(function () {
                mountDoughnut('admU360SupportStatus', tStats);
            });
            const internalChk = document.getElementById('admU360SupportInternal');
            if (internalChk) {
                internalChk.addEventListener('change', function () {
                    loadTab('support', internalChk.checked ? { internal: '1', page: '1' } : { page: '1' }, true);
                });
            }
            return;
        }
        if (tab === 'workspace') {
            const crm = data.crm || {};
            let content = '';
            const teamNote = data.note_team_data ? lead(esc(data.note_team_data)) : '';
            const contacts = (crm.recent_contacts || []).map(function (c) {
                return '<tr>' + td(esc(c.name), 'نام') + td('<span class="adm-u360-ltr">' + esc(c.phone) + '</span>', 'موبایل')
                    + td(esc(c.status), 'وضعیت') + td(esc(c.created_jalali), 'تاریخ') + '</tr>';
            }).join('');
            if (contacts) content += subSection('آخرین مخاطبین', miniTable(['نام', 'موبایل', 'وضعیت', 'تاریخ'], contacts), 'fa-address-book');
            const rows = (data.datasets || []).map(function (d) {
                return '<tr>' + td(esc(d.name), 'نام') + td(toFa(d.row_count), 'آگهی')
                    + td(esc(d.city), 'شهر') + td(esc(d.created_jalali), 'تاریخ') + '</tr>';
            }).join('');
            content += subSection('دیتاست‌ها', miniTable(['نام', 'آگهی', 'شهر', 'تاریخ'], rows), 'fa-database');
            content += renderPager(data.datasets_pagination, 'workspace');
            const crmChart = (data.charts && data.charts.crm_contacts_status) || [];
            const chartPart = crmChart.length
                ? chartsRow(chartCard('وضعیت مخاطبین', 'admU360CrmStatus', 'adm-u360-chart-wrap--donut', 'fa-chart-pie'))
                : '';
            paintPanel(tabPanel('مخاطبین، فایل‌ها و دیتاست', tabIcon('workspace'), {
                metrics: statStrip([
                    { label: 'مخاطبین', value: toFa(crm.contacts_count || 0) },
                    { label: 'معاملات باز', value: toFa(crm.deals_open || 0) },
                    { label: 'دیتاست‌ها', value: toFa((data.datasets_pagination && data.datasets_pagination.total) || (data.datasets || []).length) },
                ]),
                toolbar: panelRangeHint(),
                lead: teamNote,
                viz: chartPart,
                content: content,
            }));
            window.requestAnimationFrame(function () {
                mountDoughnut('admU360CrmStatus', crmChart);
            });
            return;
        }
        if (tab === 'marketing') {
            let content = '';
            const sms = (data.sms_logs || []).map(function (s) {
                return '<tr>' + td(esc(s.purpose), 'هدف') + smsMessageTd(s)
                    + td(esc(s.status), 'وضعیت') + td(esc(s.created_jalali), 'زمان') + '</tr>';
            }).join('');
            content += subSection('پیامک‌های سیستمی', miniTable(['هدف', 'متن پیام', 'وضعیت', 'زمان'], sms), 'fa-comment-dots');
            const disc = (data.discount_issuances || []).map(function (r) {
                return '<tr>'
                    + td('<span class="adm-u360-ltr">' + esc(r.code) + '</span>', 'کد')
                    + td(esc(r.policy_key), 'سیاست تخفیف')
                    + td(esc(r.source_type), 'منبع')
                    + td(esc(r.issued_jalali), 'زمان') + '</tr>';
            }).join('');
            if (disc) content += subSection('کدهای تخفیف صادرشده', miniTable(['کد', 'سیاست تخفیف', 'منبع', 'زمان'], disc), 'fa-percent');
            const camps = (data.campaigns || []).map(function (r) {
                return '<tr>' + td(esc(r.campaign), 'کمپین') + td(esc(r.status), 'وضعیت')
                    + td(esc(r.created_jalali), 'زمان') + '</tr>';
            }).join('');
            if (camps) content += subSection('کمپین‌ها', miniTable(['کمپین', 'وضعیت', 'زمان'], camps), 'fa-bullhorn');
            const attrs = (data.attributions || []).map(function (r) {
                return '<tr>' + td(esc(r.model), 'مدل') + td(esc(r.status), 'وضعیت')
                    + td(esc(r.created_jalali), 'زمان') + '</tr>';
            }).join('');
            if (attrs) content += subSection('بازگشت مشتری و منبع‌یابی', miniTable(['روش', 'وضعیت', 'زمان'], attrs), 'fa-undo');
            const journey = (data.growth_events || []).map(function (r) {
                return '<tr>' + td(esc(r.event_type), 'رویداد') + td(esc(r.created_jalali), 'زمان') + '</tr>';
            }).join('');
            if (journey) content += subSection('مسیر رشد', miniTable(['رویداد', 'زمان'], journey), 'fa-route');
            paintPanel(tabPanel('ارتباطات و بازاریابی', tabIcon('marketing'), {
                metrics: statStrip([
                    { label: 'انصراف پیامک', value: data.opt_out ? 'بله' : 'خیر', tone: data.opt_out ? 'warn' : 'ok' },
                ]),
                toolbar: panelRangeHint(),
                content: content,
            }));
            return;
        }
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
        if (tab === 'admin_log') {
            const rows = (data.audit_logs || []).map(function (l) {
                return '<tr>' + td(esc(l.action_type), 'عملیات')
                    + td(toFa(l.license_id), 'لایسنس')
                    + td(esc(l.created_jalali), 'زمان') + '</tr>';
            }).join('');
            paintPanel(tabPanel('تاریخچه مدیریتی', tabIcon('admin_log'), {
                toolbar: panelRangeHint(),
                lead: data.note ? lead(esc(data.note)) : '',
                content: miniTable(['عملیات', 'لایسنس', 'زمان'], rows),
            }), 'admin_log');
            return;
        }
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

    loadTab(activeTab);
})();
