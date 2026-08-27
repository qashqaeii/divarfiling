(function () {
    'use strict';

    const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatMoney(value) {
        return toPersianDigits(Number(value || 0).toLocaleString('en-US'));
    }

    function formatMoneyShort(value) {
        const n = Number(value) || 0;
        if (n >= 1_000_000_000) {
            return toPersianDigits((n / 1_000_000_000).toFixed(1).replace(/\.0$/, '')) + 'B';
        }
        if (n >= 1_000_000) {
            return toPersianDigits((n / 1_000_000).toFixed(1).replace(/\.0$/, '')) + 'M';
        }
        if (n >= 1_000) {
            return toPersianDigits((n / 1_000).toFixed(0)) + 'K';
        }
        return toPersianDigits(n.toLocaleString('en-US'));
    }

    function getThemeColors() {
        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        return {
            text: isDark ? '#94a3b8' : '#64748b',
            grid: isDark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)',
            tooltipBg: isDark ? 'rgba(15, 23, 42, 0.96)' : 'rgba(255, 255, 255, 0.98)',
            tooltipText: isDark ? '#e2e8f0' : '#1e293b',
            border: isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(148, 163, 184, 0.16)',
        };
    }

    function baseOptions(chartConfig) {
        const theme = getThemeColors();
        const axis = chartConfig.axis || 'count';

        const tickCallback = function (val) {
            if (axis === 'money') return formatMoneyShort(val);
            return toPersianDigits(val);
        };

        const opts = {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 700, easing: 'easeOutQuart' },
            interaction: { mode: 'index', intersect: false },
            layout: {
                padding: chartConfig.type === 'doughnut' ? { top: 4, bottom: 2, left: 4, right: 4 } : { top: 0, bottom: 0 },
            },
            plugins: {
                legend: {
                    display: chartConfig.type !== 'sparkline',
                    position: chartConfig.legendPosition || 'bottom',
                    rtl: true,
                    labels: {
                        color: theme.text,
                        font: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif', size: 11 },
                        padding: 14,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    rtl: true,
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipText,
                    bodyColor: theme.tooltipText,
                    borderColor: theme.border,
                    borderWidth: 1,
                    padding: 10,
                    titleFont: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif', weight: '700' },
                    bodyFont: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif' },
                    callbacks: {
                        label: function (ctx) {
                            const val = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
                            const label = ctx.dataset.label || '';
                            if (axis === 'money' || ctx.dataset.yAxisID === 'y') {
                                if (chartConfig.type === 'combo' && ctx.dataset.yAxisID === 'y1') {
                                    return label + ': ' + toPersianDigits(val);
                                }
                                if (label.includes('درآمد') || label.includes('AOV') || label.includes('میانگین')) {
                                    return label + ': ' + formatMoney(val) + ' تومان';
                                }
                            }
                            return label + ': ' + toPersianDigits(val);
                        },
                    },
                },
            },
        };

        if (chartConfig.type === 'sparkline') {
            opts.plugins.legend.display = false;
            opts.plugins.tooltip.enabled = false;
            opts.scales = {
                x: { display: false },
                y: { display: false },
            };
            return opts;
        }

        if (chartConfig.type === 'combo') {
            opts.scales = {
                x: {
                    ticks: { color: theme.text, font: { size: 10 }, maxRotation: 0 },
                    grid: { color: theme.grid },
                },
                y: {
                    type: 'linear',
                    position: 'right',
                    ticks: { color: theme.text, font: { size: 10 }, callback: tickCallback },
                    grid: { color: theme.grid },
                    beginAtZero: true,
                },
                y1: {
                    type: 'linear',
                    position: 'left',
                    ticks: { color: theme.text, font: { size: 10 }, callback: function (v) { return toPersianDigits(v); } },
                    grid: { drawOnChartArea: false },
                    beginAtZero: true,
                },
            };
            return opts;
        }

        if (chartConfig.type === 'doughnut') {
            opts.cutout = '58%';
            opts.plugins.legend.labels.boxWidth = 10;
            opts.plugins.legend.labels.font = { family: 'Vazirmatn, Vazir, Tahoma, sans-serif', size: 10 };
            opts.plugins.legend.labels.padding = 10;
            return opts;
        }

        if (chartConfig.chartKind === 'plan_sales') {
            opts.plugins.legend.display = false;
            opts.layout.padding = { left: 4, right: 16, top: 6, bottom: 6 };
            opts.indexAxis = 'y';
            opts.interaction = { mode: 'nearest', axis: 'y', intersect: true };
            opts.scales = {
                x: {
                    grid: { color: theme.grid },
                    border: { display: false },
                    ticks: {
                        color: theme.text,
                        font: { size: 11 },
                        callback: tickCallback,
                        maxTicksLimit: 6,
                    },
                    beginAtZero: true,
                },
                y: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: {
                        color: theme.text,
                        font: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif', size: 12, weight: '600' },
                        autoSkip: false,
                        padding: 8,
                        callback: function (val) {
                            return this.getLabelForValue(val);
                        },
                    },
                },
            };
            opts.plugins.tooltip.callbacks = {
                title: function (items) {
                    if (!items.length) return '';
                    const idx = items[0].dataIndex;
                    return (chartConfig.fullLabels && chartConfig.fullLabels[idx]) || items[0].label;
                },
                label: function (ctx) {
                    return [];
                },
                afterBody: function (items) {
                    if (!items.length) return [];
                    const item = items[0];
                    const idx = item.dataIndex;
                    const totals = chartConfig.planTotals
                        || (chartConfig.datasets && chartConfig.datasets[0] && chartConfig.datasets[0].data);
                    let revenue = 0;
                    if (totals && totals[idx] != null) {
                        revenue = Number(totals[idx]) || 0;
                    } else if (item.raw != null) {
                        revenue = Number(item.raw) || 0;
                    } else if (item.parsed) {
                        revenue = Number(item.parsed.x != null ? item.parsed.x : item.parsed.y) || 0;
                    }
                    const count = Number(
                        chartConfig.orderCounts && chartConfig.orderCounts[idx] != null
                            ? chartConfig.orderCounts[idx] : 0
                    );
                    const price = Number(
                        chartConfig.planPrices && chartConfig.planPrices[idx] != null
                            ? chartConfig.planPrices[idx] : 0
                    );
                    return [
                        'درآمد: ' + formatMoney(revenue) + ' تومان',
                        'تعداد سفارش: ' + toPersianDigits(count),
                        'قیمت پلن: ' + formatMoney(price) + ' تومان',
                    ];
                },
            };
            return opts;
        }

        if (chartConfig.type !== 'doughnut') {
            opts.scales = {
                x: {
                    ticks: { color: theme.text, font: { size: 10 }, maxRotation: 0 },
                    grid: { color: theme.grid },
                },
                y: {
                    ticks: { color: theme.text, font: { size: 10 }, callback: tickCallback },
                    grid: { color: theme.grid },
                    beginAtZero: true,
                },
            };

            if (chartConfig.horizontal) {
                opts.indexAxis = 'y';
                opts.scales.x.ticks.callback = tickCallback;
                opts.scales.y.ticks.callback = function (val) {
                    const label = this.getLabelForValue(val);
                    return label.length > 22 ? label.slice(0, 22) + '…' : label;
                };
            }
        }

        return opts;
    }

    function renderChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !config || typeof Chart === 'undefined') return null;

        const chartType = config.type === 'combo' ? 'bar' : (config.type === 'sparkline' ? 'line' : config.type);

        return new Chart(canvas, {
            type: chartType,
            data: {
                labels: config.labels || [],
                datasets: (config.datasets || []).map(function (ds) {
                    const copy = Object.assign({}, ds);
                    if (config.type === 'sparkline') {
                        copy.pointRadius = 0;
                        copy.borderWidth = 1.5;
                        copy.tension = 0.4;
                    }
                    if (config.chartKind === 'plan_sales') {
                        copy.borderRadius = 8;
                    }
                    return copy;
                }),
            },
            options: baseOptions(config),
        });
    }

    const chartInstances = [];

    function resizeCharts() {
        chartInstances.forEach(function (chart) {
            try {
                chart.resize();
            } catch (e) {
                /* noop */
            }
        });
    }

    function observeChartContainers() {
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(function () {
            window.requestAnimationFrame(resizeCharts);
        });
        document.querySelectorAll('.ecc-section .ecc-chart-wrap').forEach(function (el) {
            observer.observe(el);
        });
    }

    function initCharts() {
        const charts = window.admCharts;
        if (!charts) return;

        const mapping = [
            ['chart-revenue-analytics', charts.revenue_analytics],
            ['chart-user-analytics', charts.user_analytics],
            ['chart-user-retention', charts.user_retention],
            ['chart-sales-trend', charts.sales_trend],
            ['chart-crm-growth', charts.crm_growth],
            ['chart-operations', charts.operations_gauge],
            ['chart-revenue', charts.revenue_trend],
            ['chart-signups', charts.user_signups],
            ['chart-users-active', charts.users_active_trend],
            ['chart-licenses-activity', charts.licenses_activity],
            ['chart-renewal-revenue', charts.renewal_revenue_trend],
            ['chart-ops-sms-trend', charts.sms_usage_trend],
            ['chart-ops-datasets-trend', charts.dataset_activity_trend],
            ['chart-order-status', charts.order_status],
            ['chart-license-status', charts.license_status],
            ['chart-payment', charts.payment_methods],
            ['chart-plans', charts.plan_sales],
            ['chart-product', charts.product_revenue],
        ];

        mapping.forEach(function (item) {
            const cfg = item[1];
            if (!cfg) return;
            const inst = renderChart(item[0], cfg);
            if (inst) chartInstances.push(inst);
        });

        window.requestAnimationFrame(resizeCharts);
        setTimeout(resizeCharts, 120);
        setTimeout(resizeCharts, 450);
        observeChartContainers();

        document.querySelectorAll('[data-sparkline]').forEach(function (el) {
            const raw = el.getAttribute('data-sparkline');
            if (!raw) return;
            let values;
            try { values = JSON.parse(raw); } catch (e) { return; }
            const canvas = el.querySelector('canvas');
            if (!canvas) return;
            const accent = el.closest('[data-accent]');
            const colorMap = {
                emerald: 'rgba(16, 185, 129, 0.9)',
                violet: 'rgba(124, 58, 237, 0.9)',
                blue: 'rgba(59, 130, 246, 0.9)',
                amber: 'rgba(245, 158, 11, 0.9)',
                cyan: 'rgba(6, 182, 212, 0.9)',
                indigo: 'rgba(99, 102, 241, 0.9)',
                rose: 'rgba(244, 63, 94, 0.9)',
            };
            const accentKey = accent ? accent.getAttribute('data-accent') : 'violet';
            const borderColor = colorMap[accentKey] || colorMap.violet;
            const inst = renderChart(canvas.id, {
                type: 'sparkline',
                labels: values.map(function (_, i) { return String(i); }),
                datasets: [{
                    data: values,
                    borderColor: borderColor,
                    backgroundColor: borderColor.replace('0.9', '0.12'),
                    fill: true,
                }],
                axis: 'count',
            });
            if (inst) chartInstances.push(inst);
        });
    }

    function refreshThemeOnCharts() {
        const theme = getThemeColors();
        chartInstances.forEach(function (chart) {
            if (chart.options.plugins.legend && chart.options.plugins.legend.labels) {
                chart.options.plugins.legend.labels.color = theme.text;
            }
            if (chart.options.plugins.tooltip) {
                chart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
                chart.options.plugins.tooltip.titleColor = theme.tooltipText;
                chart.options.plugins.tooltip.bodyColor = theme.tooltipText;
                chart.options.plugins.tooltip.borderColor = theme.border;
            }
            if (chart.options.scales) {
                ['x', 'y', 'y1'].forEach(function (axis) {
                    if (chart.options.scales[axis]) {
                        if (chart.options.scales[axis].ticks) {
                            chart.options.scales[axis].ticks.color = theme.text;
                        }
                        if (chart.options.scales[axis].grid) {
                            chart.options.scales[axis].grid.color = theme.grid;
                        }
                    }
                });
            }
            chart.update('none');
        });
    }

    function animateCountUp() {
        document.querySelectorAll('[data-count-up]').forEach(function (el) {
            const target = parseFloat(el.getAttribute('data-count-up') || '0');
            const format = el.getAttribute('data-format') || 'count';
            const duration = 900;
            const start = performance.now();

            function frame(now) {
                const t = Math.min(1, (now - start) / duration);
                const eased = 1 - Math.pow(1 - t, 3);
                const current = Math.round(target * eased);
                if (format === 'money') {
                    el.textContent = formatMoney(current);
                } else if (format === 'percent') {
                    el.textContent = toPersianDigits((target * eased).toFixed(1)) + '٪';
                } else {
                    el.textContent = formatMoney(current);
                }
                if (t < 1) requestAnimationFrame(frame);
            }

            requestAnimationFrame(frame);
        });
    }

    function initClock() {
        const clockEl = document.getElementById('ecc-live-clock');
        const dateEl = document.getElementById('ecc-live-date');
        if (!clockEl) return;

        function tick() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            clockEl.textContent = toPersianDigits(h + ':' + m + ':' + s);
            if (dateEl) {
                dateEl.textContent = now.toLocaleDateString('fa-IR', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                });
            }
        }

        tick();
        setInterval(tick, 1000);
    }

    function initNavigation() {
        if (document.querySelector('.ecc-sidebar--grouped')) return;
        const navItems = document.querySelectorAll('.ecc-nav-item');
        const sections = Array.from(document.querySelectorAll('.ecc-section[id]')).map(function (el) {
            return el.id;
        });

        function setActive(hash) {
            const id = (hash || '#ecc-command').replace('#', '');
            navItems.forEach(function (item) {
                const href = item.getAttribute('href') || '';
                item.classList.toggle('is-active', href === '#' + id);
            });
        }

        navItems.forEach(function (item) {
            item.addEventListener('click', function () {
                setActive(item.getAttribute('href'));
            });
        });

        function onScroll() {
            let current = sections[0];
            sections.forEach(function (id) {
                const el = document.getElementById(id);
                if (el && el.getBoundingClientRect().top <= 130) {
                    current = id;
                }
            });
            setActive('#' + current);
        }

        window.addEventListener('scroll', onScroll, { passive: true });
        setActive(window.location.hash || '#ecc-command');
    }

    function initFeedFilters() {
        const filters = document.querySelectorAll('.ecc-feed-filter');
        const items = document.querySelectorAll('.ecc-feed-item');
        if (!filters.length) return;

        filters.forEach(function (btn) {
            btn.addEventListener('click', function () {
                const type = btn.getAttribute('data-filter') || 'all';
                filters.forEach(function (b) { b.classList.toggle('is-active', b === btn); });
                items.forEach(function (item) {
                    const itemType = item.getAttribute('data-type');
                    item.hidden = type !== 'all' && itemType !== type;
                });
            });
        });
    }

    function initTableTools() {
        document.querySelectorAll('[data-ecc-table]').forEach(function (wrap) {
            const table = wrap.querySelector('table');
            const search = wrap.querySelector('.ecc-table-search');
            if (!table || !search) return;

            search.addEventListener('input', function () {
                const q = search.value.trim().toLowerCase();
                table.querySelectorAll('tbody tr').forEach(function (row) {
                    if (row.classList.contains('adm-tbl-row--more') && row.hidden) return;
                    const text = row.textContent.toLowerCase();
                    row.style.display = !q || text.includes(q) ? '' : 'none';
                });
            });

            table.querySelectorAll('th[data-sort]').forEach(function (th) {
                th.style.cursor = 'pointer';
                th.addEventListener('click', function () {
                    const idx = Array.from(th.parentNode.children).indexOf(th);
                    const tbody = table.querySelector('tbody');
                    const rows = Array.from(tbody.querySelectorAll('tr:not(.adm-empty)'));
                    const asc = th.getAttribute('data-sort-dir') !== 'asc';
                    th.parentNode.querySelectorAll('th').forEach(function (h) {
                        h.removeAttribute('data-sort-dir');
                    });
                    th.setAttribute('data-sort-dir', asc ? 'asc' : 'desc');
                    rows.sort(function (a, b) {
                        const av = (a.children[idx] && a.children[idx].textContent.trim()) || '';
                        const bv = (b.children[idx] && b.children[idx].textContent.trim()) || '';
                        const an = parseFloat(av.replace(/[^\d.-]/g, ''));
                        const bn = parseFloat(bv.replace(/[^\d.-]/g, ''));
                        if (!isNaN(an) && !isNaN(bn)) {
                            return asc ? an - bn : bn - an;
                        }
                        return asc ? av.localeCompare(bv, 'fa') : bv.localeCompare(av, 'fa');
                    });
                    rows.forEach(function (r) { tbody.appendChild(r); });
                });
            });
        });
    }

    function initCollapsibleTables() {
        document.querySelectorAll('.adm-tbl-box').forEach(function (box) {
            const toggle = box.querySelector('.adm-tbl-toggle');
            if (!toggle) return;

            const moreRows = box.querySelectorAll('.adm-tbl-row--more');
            const moreLabel = toggle.querySelector('.adm-tbl-toggle-more');
            const lessLabel = toggle.querySelector('.adm-tbl-toggle-less');

            toggle.addEventListener('click', function () {
                const expanded = toggle.getAttribute('aria-expanded') === 'true';
                moreRows.forEach(function (row) {
                    row.hidden = expanded;
                });
                toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
                box.classList.toggle('is-expanded', !expanded);
                if (moreLabel) moreLabel.hidden = !expanded;
                if (lessLabel) lessLabel.hidden = expanded;
            });
        });
    }

    function initRefresh() {
        const btn = document.getElementById('ecc-refresh-btn');
        if (!btn || btn.dataset.shellRefreshBound) return;
        btn.addEventListener('click', function () {
            btn.classList.add('is-loading');
            window.location.reload();
        });
    }

    function init() {
        initCharts();
        animateCountUp();
        initClock();
        initNavigation();
        initFeedFilters();
        initTableTools();
        initCollapsibleTables();
        initRefresh();

        window.addEventListener('resize', function () {
            window.requestAnimationFrame(resizeCharts);
        }, { passive: true });

        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setTimeout(refreshThemeOnCharts, 60);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
