/**
 * Admin Academy panel — tabs, search, analytics charts
 */
(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    var chartInstances = {};
    var chartsReady = false;
    var pendingData = null;

    function toFa(n) {
        return String(n).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatNum(n) {
        return toFa(Number(n || 0).toLocaleString('en-US'));
    }

    function isDark() {
        var html = document.documentElement;
        return html.classList.contains('mk-public') && html.getAttribute('data-theme') !== 'light';
    }

    function chartColors() {
        return {
            teal: isDark() ? 'rgba(20, 184, 166, 0.7)' : 'rgba(13, 148, 136, 0.65)',
            tealBorder: isDark() ? '#14b8a6' : '#0d9488',
            violet: isDark() ? 'rgba(167, 139, 250, 0.75)' : 'rgba(124, 58, 237, 0.7)',
            gold: isDark() ? 'rgba(232, 197, 71, 0.65)' : 'rgba(201, 162, 39, 0.7)',
            grid: isDark() ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)',
            text: isDark() ? '#94a3b8' : '#64748b',
        };
    }

    function parseInitialData() {
        var el = document.getElementById('aa-analytics-data');
        if (!el) return {};
        try {
            return JSON.parse(el.textContent || '{}');
        } catch (e) {
            return {};
        }
    }

    function initNav() {
        var nav = document.getElementById('ab-nav');
        var spacer = document.getElementById('ab-nav-spacer');
        var indicator = document.getElementById('ab-nav-indicator');
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

    function showPanel(id) {
        document.querySelectorAll('.ab-panel').forEach(function (panel) {
            var on = panel.id === id;
            panel.classList.toggle('is-visible', on);
            panel.hidden = !on;
        });
        if (id === 'academy-analytics') {
            requestAnimationFrame(function () {
                ensureCharts(pendingData || parseInitialData());
            });
        }
    }

    function initTabs() {
        document.querySelectorAll('.ab-nav__item[data-tab]').forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                var id = link.getAttribute('data-tab');
                showPanel(id);
                if (history.replaceState) {
                    history.replaceState(null, '', '#' + id);
                }
            });
        });
        var hash = (location.hash || '').replace('#', '');
        if (hash && document.getElementById(hash)) {
            showPanel(hash);
            var navItem = document.querySelector('.ab-nav__item[data-tab="' + hash + '"]');
            if (navItem) {
                document.querySelectorAll('.ab-nav__item').forEach(function (t) { t.classList.remove('is-active'); });
                navItem.classList.add('is-active');
            }
        } else {
            showPanel('academy-overview');
        }
    }

    function initSearch() {
        var input = document.getElementById('ab-post-search');
        var list = document.getElementById('ab-posts-list');
        var empty = document.getElementById('ab-search-empty');
        if (!input || !list) return;
        input.addEventListener('input', function () {
            var q = (input.value || '').trim().toLowerCase();
            var visible = 0;
            list.querySelectorAll('.ab-post-row').forEach(function (row) {
                var hay = (row.getAttribute('data-search') || '').toLowerCase();
                var show = !q || hay.indexOf(q) !== -1;
                row.hidden = !show;
                if (show) visible += 1;
            });
            if (empty) empty.hidden = visible > 0;
        });
    }

    function destroyCharts() {
        Object.keys(chartInstances).forEach(function (k) {
            if (chartInstances[k]) chartInstances[k].destroy();
            delete chartInstances[k];
        });
        chartsReady = false;
    }

    function toggleEmpty(canvasId, emptyId, isEmpty) {
        var canvas = document.getElementById(canvasId);
        var empty = document.getElementById(emptyId);
        if (canvas) canvas.style.display = isEmpty ? 'none' : '';
        if (empty) empty.hidden = !isEmpty;
    }

    function ensureCharts(data) {
        if (typeof Chart === 'undefined') {
            pendingData = data;
            return;
        }
        destroyCharts();
        pendingData = data || {};
        var traffic = (pendingData.traffic || {});
        var daily = traffic.views_daily || {};
        var labels = daily.labels || [];
        var counts = daily.counts || [];
        var prevCounts = daily.prev_counts || [];
        var completions = daily.completions || [];
        var paths = traffic.views_by_path || [];
        var periodTop = traffic.top_videos_period || [];
        var colors = chartColors();
        var hasTraffic = counts.some(function (n) { return n > 0; });

        toggleEmpty('aa-chart-traffic', 'aa-empty-traffic', !hasTraffic);
        var trafficCanvas = document.getElementById('aa-chart-traffic');
        if (trafficCanvas && hasTraffic) {
            chartInstances.traffic = new Chart(trafficCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            type: 'bar',
                            label: 'تکمیل',
                            data: completions,
                            backgroundColor: colors.gold,
                            borderRadius: 4,
                            yAxisID: 'y1',
                            order: 2,
                        },
                        {
                            label: 'بازدید',
                            data: counts,
                            borderColor: colors.tealBorder,
                            backgroundColor: colors.teal,
                            fill: true,
                            tension: 0.35,
                            pointRadius: 0,
                            order: 1,
                        },
                        {
                            label: 'دوره قبل',
                            data: prevCounts,
                            borderColor: colors.violet,
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.35,
                            pointRadius: 0,
                            order: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'bottom', rtl: true, labels: { boxWidth: 10 } },
                        tooltip: { rtl: true, textDirection: 'rtl' },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: {
                                maxTicksLimit: 8,
                                callback: function (v, i) {
                                    var label = labels[i] || '';
                                    return label.slice(5);
                                },
                            },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: colors.grid },
                            ticks: { callback: function (v) { return formatNum(v); } },
                        },
                        y1: {
                            beginAtZero: true,
                            position: 'left',
                            grid: { display: false },
                            ticks: { callback: function (v) { return formatNum(v); } },
                        },
                    },
                },
            });
        }

        toggleEmpty('aa-chart-paths', 'aa-empty-paths', !paths.length);
        var pathCanvas = document.getElementById('aa-chart-paths');
        if (pathCanvas && paths.length) {
            var catColors = [
                colors.tealBorder, '#7c3aed', '#c9a227', '#10b981', '#f59e0b',
                '#f43f5e', '#3b82f6', '#ec4899', '#84cc16', '#64748b',
            ];
            chartInstances.paths = new Chart(pathCanvas, {
                type: 'doughnut',
                data: {
                    labels: paths.map(function (p) { return p.name; }),
                    datasets: [{
                        data: paths.map(function (p) { return p.views; }),
                        backgroundColor: catColors.slice(0, paths.length),
                        borderWidth: 2,
                        borderColor: isDark() ? '#0f172a' : '#fff',
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '58%',
                    plugins: {
                        legend: { position: 'bottom', rtl: true, labels: { boxWidth: 10, padding: 8, font: { size: 10 } } },
                        tooltip: { rtl: true, textDirection: 'rtl' },
                    },
                },
            });
        }

        toggleEmpty('aa-chart-period', 'aa-empty-period', !periodTop.length);
        var periodCanvas = document.getElementById('aa-chart-period');
        if (periodCanvas && periodTop.length) {
            chartInstances.period = new Chart(periodCanvas, {
                type: 'bar',
                data: {
                    labels: periodTop.map(function (p) {
                        return p.title.length > 28 ? p.title.slice(0, 28) + '…' : p.title;
                    }),
                    datasets: [{
                        label: 'بازدید',
                        data: periodTop.map(function (p) { return p.views; }),
                        backgroundColor: colors.violet,
                        borderRadius: 6,
                    }],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { rtl: true, textDirection: 'rtl' } },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: { color: colors.grid },
                            ticks: { callback: function (v) { return formatNum(v); } },
                        },
                        y: { grid: { display: false } },
                    },
                },
            });
        }

        chartsReady = true;
        updatePulse(pendingData);
    }

    function updatePulse(data) {
        var pulse = (data && data.pulse) || {};
        var traffic = (data && data.traffic) || {};
        var map = {
            'aa-pulse-today': pulse.today,
            'aa-pulse-yesterday': pulse.yesterday,
            'aa-pulse-week': pulse.week,
            'aa-pulse-period': traffic.period_total,
        };
        Object.keys(map).forEach(function (id) {
            var el = document.getElementById(id);
            if (el && map[id] != null) el.textContent = formatNum(map[id]);
        });
        var hint = document.getElementById('aa-pulse-period-hint');
        if (hint && traffic.avg_daily != null) {
            hint.textContent = 'میانگین روزانه ' + formatNum(traffic.avg_daily);
        }
    }

    function initRange() {
        var page = document.getElementById('aa-page');
        var range = document.getElementById('aa-analytics-range');
        var loading = document.getElementById('aa-analytics-loading');
        if (!page || !range) return;
        var url = page.getAttribute('data-analytics-url');
        range.querySelectorAll('.ab-range-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var days = btn.getAttribute('data-days');
                range.querySelectorAll('.ab-range-btn').forEach(function (b) { b.classList.remove('is-active'); });
                btn.classList.add('is-active');
                if (loading) loading.hidden = false;
                fetch(url + '?days=' + encodeURIComponent(days), {
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        pendingData = data;
                        ensureCharts(data);
                    })
                    .catch(function () {})
                    .finally(function () {
                        if (loading) loading.hidden = true;
                    });
            });
        });
    }

    function boot() {
        pendingData = parseInitialData();
        initNav();
        initTabs();
        initSearch();
        initRange();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
