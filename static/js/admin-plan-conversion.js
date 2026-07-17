(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    var chartRegistry = {};

    function toFa(n) {
        return String(n).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatNum(n) {
        var num = Number(n || 0);
        if (!isFinite(num)) return toFa('0');
        return toFa(Math.round(num).toLocaleString('en-US'));
    }

    function formatPct(n) {
        var num = Number(n || 0);
        var fixed = Number.isInteger(num) ? String(num) : num.toFixed(2).replace(/\.?0+$/, '');
        return toFa(fixed) + '٪';
    }

    function formatMoney(n) {
        return formatNum(n) + ' ت';
    }

    function isDark() {
        var html = document.documentElement;
        return html.classList.contains('mk-public') && html.getAttribute('data-theme') !== 'light';
    }

    function palette() {
        return {
            violet: isDark() ? '#a78bfa' : '#7c3aed',
            violetSoft: isDark() ? 'rgba(167, 139, 250, 0.2)' : 'rgba(124, 58, 237, 0.14)',
            emerald: isDark() ? '#34d399' : '#10b981',
            emeraldSoft: isDark() ? 'rgba(52, 211, 153, 0.18)' : 'rgba(16, 185, 129, 0.12)',
            blue: isDark() ? '#60a5fa' : '#3b82f6',
            amber: isDark() ? '#fbbf24' : '#f59e0b',
            rose: isDark() ? '#fb7185' : '#f43f5e',
            grid: isDark() ? 'rgba(148, 163, 184, 0.07)' : 'rgba(148, 163, 184, 0.14)',
            text: isDark() ? '#94a3b8' : '#64748b',
            tooltipBg: isDark() ? 'rgba(15, 23, 42, 0.94)' : 'rgba(255, 255, 255, 0.97)',
            tooltipTitle: isDark() ? '#f1f5f9' : '#0f172a',
        };
    }

    function getData() {
        return window.admPlanConversion || {};
    }

    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    function animateValue(el, target, duration, suffix) {
        if (!el) return;
        target = Number(target) || 0;
        if (target <= 0) {
            el.textContent = toFa('0') + (suffix || '');
            return;
        }
        var start = performance.now();
        suffix = suffix || '';
        function frame(now) {
            var p = Math.min((now - start) / duration, 1);
            var val = Math.round(easeOutCubic(p) * target);
            el.textContent = formatNum(val) + suffix;
            if (p < 1) requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
    }

    function injectGaugeGradient() {
        var svg = document.querySelector('.apc-gauge__svg');
        if (!svg || svg.querySelector('#apcGaugeGrad')) return;
        var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = '<linearGradient id="apcGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">' +
            '<stop offset="0%" stop-color="#7c3aed"/>' +
            '<stop offset="100%" stop-color="#14b8a6"/>' +
            '</linearGradient>';
        svg.insertBefore(defs, svg.firstChild);
    }

    function initGauge() {
        var fill = document.querySelector('.apc-gauge__fill');
        var valEl = document.querySelector('.apc-gauge__val');
        if (!fill) return;
        var rate = parseFloat(fill.getAttribute('data-rate') || '0');
        var circumference = 326.7;
        var offset = circumference - (circumference * Math.min(Math.max(rate, 0), 100) / 100);
        requestAnimationFrame(function () {
            fill.style.strokeDashoffset = String(offset);
        });
        if (valEl) {
            valEl.textContent = formatPct(rate);
        }
    }

    function initFunnelBars() {
        document.querySelectorAll('.apc-funnel-stage__bar[data-width]').forEach(function (bar) {
            var w = parseFloat(bar.getAttribute('data-width') || '0');
            bar.style.width = '0';
            requestAnimationFrame(function () {
                setTimeout(function () {
                    bar.style.width = Math.min(Math.max(w, 0), 100) + '%';
                }, 100);
            });
        });
        document.querySelectorAll('.apc-plan-card__bar span').forEach(function (bar) {
            var inline = bar.getAttribute('style') || '';
            var match = inline.match(/width:\s*([\d.]+)/);
            var w = match ? parseFloat(match[1]) : 0;
            bar.style.width = '0';
            requestAnimationFrame(function () {
                setTimeout(function () {
                    bar.style.width = w + '%';
                }, 180);
            });
        });
    }

    function initCountUp() {
        document.querySelectorAll('[data-count]').forEach(function (el) {
            var target = parseInt(el.getAttribute('data-count'), 10) || 0;
            animateValue(el, target, 900);
        });
    }

    function initReveal() {
        var sections = document.querySelectorAll('[data-reveal]');
        if (!sections.length || !('IntersectionObserver' in window)) {
            sections.forEach(function (s) { s.classList.add('is-revealed'); });
            return;
        }
        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-revealed');
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
        sections.forEach(function (s) { obs.observe(s); });
    }

    function initNav() {
        var nav = document.getElementById('apc-nav');
        var spacer = document.getElementById('apc-nav-spacer');
        var indicator = document.getElementById('apc-nav-indicator');
        var items = nav ? nav.querySelectorAll('.ab-nav__item') : [];
        if (!nav || !indicator) return;

        var anchorTop = 0;

        function headerH() {
            var header = document.querySelector('.mk-site-header');
            return header ? header.getBoundingClientRect().height : 56;
        }

        function syncIndicator(active) {
            if (!active) return;
            indicator.style.width = active.offsetWidth + 'px';
            indicator.style.left = active.offsetLeft + 'px';
        }

        function measure() {
            nav.classList.remove('is-pinned');
            if (spacer) {
                spacer.classList.remove('is-active');
                spacer.style.height = '';
            }
            anchorTop = nav.getBoundingClientRect().top + window.scrollY;
            document.documentElement.style.setProperty('--ab-nav-h', nav.offsetHeight + 'px');
            syncIndicator(nav.querySelector('.ab-nav__item.is-active'));
        }

        function onScroll() {
            var hh = headerH();
            document.documentElement.style.setProperty('--ab-nav-top', hh + 'px');
            var pin = window.scrollY + hh >= anchorTop - 1;
            nav.classList.toggle('is-pinned', pin);
            if (spacer) {
                spacer.classList.toggle('is-active', pin);
                if (pin) spacer.style.height = nav.offsetHeight + 'px';
            }
        }

        items.forEach(function (item) {
            item.addEventListener('click', function () {
                setTimeout(function () {
                    items.forEach(function (t) { t.classList.remove('is-active'); });
                    item.classList.add('is-active');
                    syncIndicator(item);
                }, 0);
            });
        });

        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', function () { measure(); onScroll(); });
        measure();
        onScroll();
    }

    function initScrollSpy() {
        var sections = document.querySelectorAll('.apc-section');
        var navItems = document.querySelectorAll('#apc-nav .ab-nav__item');
        if (!sections.length) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var id = entry.target.id;
                navItems.forEach(function (item) {
                    item.classList.toggle('is-active', item.getAttribute('href') === '#' + id);
                });
                var indicator = document.getElementById('apc-nav-indicator');
                var active = document.querySelector('#apc-nav .ab-nav__item.is-active');
                if (indicator && active) {
                    indicator.style.width = active.offsetWidth + 'px';
                    indicator.style.left = active.offsetLeft + 'px';
                }
            });
        }, { rootMargin: '-25% 0px -55% 0px', threshold: 0.05 });

        sections.forEach(function (s) { observer.observe(s); });
    }

    function chartDefaults(extraY) {
        var c = palette();
        var scales = {
            x: {
                ticks: { color: c.text, maxRotation: 45, minRotation: 0, font: { size: 10, weight: '600' }, autoSkip: true, maxTicksLimit: 14 },
                grid: { display: false },
                border: { display: false },
            },
            y: {
                ticks: {
                    color: c.text,
                    font: { size: 10 },
                    callback: function (v) { return toFa(v); },
                },
                grid: { color: c.grid, drawBorder: false },
                border: { display: false },
                beginAtZero: true,
            },
        };
        if (extraY) {
            scales.y1 = extraY;
        }
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    labels: {
                        color: c.text,
                        font: { family: 'inherit', size: 11, weight: '600' },
                        boxWidth: 10,
                        boxHeight: 10,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 16,
                    },
                },
                tooltip: {
                    backgroundColor: c.tooltipBg,
                    titleColor: c.tooltipTitle,
                    bodyColor: c.text,
                    borderColor: isDark() ? 'rgba(148,163,184,0.18)' : 'rgba(148,163,184,0.28)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 12,
                    rtl: true,
                    textDirection: 'rtl',
                    displayColors: true,
                    boxPadding: 4,
                },
            },
            scales: scales,
        };
    }

    function destroyChart(key) {
        if (chartRegistry[key]) {
            chartRegistry[key].destroy();
            delete chartRegistry[key];
        }
    }

    function setDonutCenter(mode) {
        var data = getData().plan_share || {};
        var totalEl = document.getElementById('apc-donut-total');
        var labelEl = document.getElementById('apc-donut-label');
        if (!totalEl || !labelEl) return;
        if (mode === 'orders') {
            var sumOrders = (data.purchases || []).reduce(function (a, b) { return a + Number(b || 0); }, 0);
            totalEl.textContent = formatNum(sumOrders);
            labelEl.textContent = 'کل خرید';
        } else {
            var sumRev = (data.revenue || []).reduce(function (a, b) { return a + Number(b || 0); }, 0);
            totalEl.textContent = formatNum(sumRev);
            labelEl.textContent = 'کل درآمد (ت)';
        }
    }

    function buildFunnelChart(mode) {
        destroyChart('funnel');
        var el = document.getElementById('apc-chart-funnel');
        var data = getData();
        if (!el || !data.funnel_daily || typeof Chart === 'undefined') return;

        var fd = data.funnel_daily;
        var c = palette();
        var opts = chartDefaults();
        var labels = fd.labels || fd.purchase_labels || [];
        var fullLabels = fd.labels_full || labels;

        opts.plugins.tooltip.callbacks = {
            title: function (items) {
                var i = items[0] && items[0].dataIndex;
                return fullLabels[i] || labels[i] || '';
            },
            label: function (ctx) {
                return ' ' + ctx.dataset.label + ': ' + formatNum(ctx.parsed.y);
            },
        };

        var datasets = [
            {
                key: 'pricing',
                label: 'بازدید قیمت',
                data: fd.pricing_counts || [],
                borderColor: c.violet,
                backgroundColor: c.violetSoft,
                fill: true,
                tension: 0.38,
                pointRadius: 0,
                pointHoverRadius: 5,
                borderWidth: 2.5,
            },
            {
                key: 'checkout',
                label: 'شروع Checkout',
                data: fd.checkout_counts || [],
                borderColor: c.amber,
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.38,
                pointRadius: 0,
                pointHoverRadius: 5,
                borderWidth: 2,
                borderDash: [5, 4],
            },
            {
                key: 'paid',
                label: 'پرداخت موفق',
                data: fd.purchase_counts || [],
                borderColor: c.emerald,
                backgroundColor: c.emeraldSoft,
                fill: mode === 'paid',
                tension: 0.38,
                pointRadius: 0,
                pointHoverRadius: 5,
                borderWidth: 2.5,
            },
        ];

        if (mode && mode !== 'all') {
            datasets = datasets.filter(function (d) { return d.key === mode; });
            if (datasets[0]) datasets[0].fill = true;
        }

        chartRegistry.funnel = new Chart(el, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: opts,
        });
    }

    function buildShareChart(mode) {
        destroyChart('share');
        var el = document.getElementById('apc-chart-share');
        var data = getData().plan_share;
        if (!el || !data || typeof Chart === 'undefined') return;

        var c = palette();
        var values = mode === 'orders' ? (data.order_share || data.values) : data.values;
        var absolute = mode === 'orders' ? data.purchases : data.revenue;

        setDonutCenter(mode === 'orders' ? 'orders' : 'revenue');

        chartRegistry.share = new Chart(el, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: values,
                    backgroundColor: data.colors,
                    borderWidth: 0,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: c.text, font: { size: 11, weight: '600' }, padding: 14, usePointStyle: true },
                    },
                    tooltip: {
                        backgroundColor: c.tooltipBg,
                        titleColor: c.tooltipTitle,
                        bodyColor: c.text,
                        borderWidth: 1,
                        borderColor: isDark() ? 'rgba(148,163,184,0.18)' : 'rgba(148,163,184,0.28)',
                        cornerRadius: 12,
                        rtl: true,
                        textDirection: 'rtl',
                        callbacks: {
                            label: function (ctx) {
                                var abs = absolute && absolute[ctx.dataIndex] != null ? absolute[ctx.dataIndex] : null;
                                var line = ' ' + toFa(ctx.label) + ': ' + formatPct(ctx.parsed);
                                if (abs != null) {
                                    line += mode === 'orders'
                                        ? ' (' + formatNum(abs) + ' خرید)'
                                        : ' (' + formatMoney(abs) + ')';
                                }
                                return line;
                            },
                        },
                    },
                },
            },
        });
    }

    function buildConversionChart() {
        destroyChart('conversion');
        var el = document.getElementById('apc-chart-conversion');
        var pc = getData().plan_conversion;
        if (!el || !pc || typeof Chart === 'undefined') return;
        var c = palette();
        var opts = chartDefaults();
        opts.plugins.tooltip.callbacks = {
            label: function (ctx) {
                return ' ' + ctx.dataset.label + ': ' + formatPct(ctx.parsed.y);
            },
        };
        opts.scales.y.ticks.callback = function (v) { return toFa(v) + '٪'; };

        chartRegistry.conversion = new Chart(el, {
            type: 'bar',
            data: {
                labels: pc.labels,
                datasets: [
                    {
                        label: 'تبدیل قیف',
                        data: pc.funnel_rates,
                        backgroundColor: c.violet,
                        borderRadius: 10,
                        borderSkipped: false,
                        maxBarThickness: 28,
                    },
                    {
                        label: 'تبدیل Checkout',
                        data: pc.checkout_rates,
                        backgroundColor: c.emerald,
                        borderRadius: 10,
                        borderSkipped: false,
                        maxBarThickness: 28,
                    },
                ],
            },
            options: opts,
        });
    }

    function buildWeeklyChart() {
        destroyChart('weekly');
        var el = document.getElementById('apc-chart-weekly');
        var wp = getData().weekly_purchases;
        if (!el || !wp || typeof Chart === 'undefined') return;
        var c = palette();
        var opts = chartDefaults({
            type: 'linear',
            position: 'left',
            ticks: {
                color: c.text,
                font: { size: 10 },
                callback: function (v) { return formatNum(v); },
            },
            grid: { drawOnChartArea: false },
            border: { display: false },
            beginAtZero: true,
            title: {
                display: true,
                text: 'درآمد (تومان)',
                color: c.text,
                font: { size: 10, weight: '600' },
            },
        });
        opts.scales.y.position = 'right';
        opts.scales.y.title = {
            display: true,
            text: 'تعداد خرید',
            color: c.text,
            font: { size: 10, weight: '600' },
        };
        opts.plugins.tooltip.callbacks = {
            title: function (items) {
                var i = items[0] && items[0].dataIndex;
                return (wp.labels_short && wp.labels_short[i]) || (wp.labels && wp.labels[i]) || '';
            },
            label: function (ctx) {
                if (ctx.dataset.yAxisID === 'y1') {
                    return ' ' + ctx.dataset.label + ': ' + formatMoney(ctx.parsed.y);
                }
                return ' ' + ctx.dataset.label + ': ' + formatNum(ctx.parsed.y);
            },
        };

        chartRegistry.weekly = new Chart(el, {
            type: 'bar',
            data: {
                labels: wp.labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'کل خرید',
                        data: wp.total,
                        backgroundColor: c.violet,
                        borderRadius: 6,
                        borderSkipped: false,
                        yAxisID: 'y',
                        order: 2,
                    },
                    {
                        type: 'bar',
                        label: '۱روزه',
                        data: wp.daily,
                        backgroundColor: c.emerald,
                        borderRadius: 6,
                        borderSkipped: false,
                        yAxisID: 'y',
                        order: 2,
                    },
                    {
                        type: 'bar',
                        label: '۱ماهه',
                        data: wp.monthly,
                        backgroundColor: c.blue,
                        borderRadius: 6,
                        borderSkipped: false,
                        yAxisID: 'y',
                        order: 2,
                    },
                    {
                        type: 'line',
                        label: 'درآمد',
                        data: wp.revenue,
                        borderColor: c.amber,
                        backgroundColor: 'transparent',
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        borderWidth: 2.5,
                        yAxisID: 'y1',
                        order: 1,
                    },
                ],
            },
            options: opts,
        });
    }

    function buildCohortChart() {
        destroyChart('cohort');
        var el = document.getElementById('apc-chart-cohort');
        var ch = getData().cohort;
        if (!el || !ch || typeof Chart === 'undefined') return;
        var c = palette();
        var opts = chartDefaults();
        opts.scales.y.ticks.callback = function (v) { return toFa(v) + '٪'; };
        opts.plugins.tooltip.callbacks = {
            title: function (items) {
                var i = items[0] && items[0].dataIndex;
                return (ch.labels_jalali && ch.labels_jalali[i]) || (ch.labels && ch.labels[i]) || '';
            },
            label: function (ctx) {
                return ' ' + ctx.dataset.label + ': ' + formatPct(ctx.parsed.y);
            },
            afterBody: function (items) {
                var i = items[0] && items[0].dataIndex;
                if (i == null || !ch.users) return [];
                return [' کاربران کوهورت: ' + formatNum(ch.users[i])];
            },
        };

        chartRegistry.cohort = new Chart(el, {
            type: 'line',
            data: {
                labels: ch.labels,
                datasets: [
                    {
                        label: 'تکرار ۷روز',
                        data: ch.repeat_7d_rate,
                        borderColor: c.amber,
                        backgroundColor: 'transparent',
                        tension: 0.35,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2,
                    },
                    {
                        label: 'تکرار ۳۰روز',
                        data: ch.repeat_30d_rate,
                        borderColor: c.blue,
                        backgroundColor: 'transparent',
                        tension: 0.35,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2,
                    },
                    {
                        label: 'ارتقا به ماهانه',
                        data: ch.upgrade_rate,
                        borderColor: c.emerald,
                        backgroundColor: c.emeraldSoft,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2.5,
                    },
                ],
            },
            options: opts,
        });
    }

    function initCharts() {
        if (typeof Chart === 'undefined') return;
        Chart.defaults.font.family = 'inherit';
        buildFunnelChart('all');
        buildShareChart('revenue');
        buildConversionChart();
        buildWeeklyChart();
        buildCohortChart();
    }

    function initToggles() {
        document.querySelectorAll('[data-chart-toggle]').forEach(function (group) {
            var kind = group.getAttribute('data-chart-toggle');
            group.querySelectorAll('.apc-toggle').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    group.querySelectorAll('.apc-toggle').forEach(function (b) { b.classList.remove('is-active'); });
                    btn.classList.add('is-active');
                    var mode = btn.getAttribute('data-mode');
                    if (kind === 'funnel') buildFunnelChart(mode);
                    if (kind === 'share') buildShareChart(mode);
                });
            });
        });
    }

    function initThemeObserver() {
        var observer = new MutationObserver(function () {
            initCharts();
        });
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme', 'class'],
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        injectGaugeGradient();
        initGauge();
        initNav();
        initScrollSpy();
        initReveal();
        initCountUp();
        initFunnelBars();
        initCharts();
        initToggles();
        initThemeObserver();
    });
})();
