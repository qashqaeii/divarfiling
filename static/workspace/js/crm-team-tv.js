/**
 * TV Command Center — incremental render + polling + Chart.js visualizations
 */
(function () {
    'use strict';

    var root = document.getElementById('crm-tv-app');
    if (!root) return;

    var cfg = window.crmTeamTV || {};
    var STORAGE_KEY = 'crm-tv-settings-v3';
    var SETTINGS_SCHEMA = 3;
    var OPTIONAL = ['chart', 'goals', 'activity', 'schedule', 'alerts'];
    var ALWAYS = ['kpis', 'leaderboard'];

    var CHART_THEME = {
        text: '#8b93a8',
        textBright: '#e8eaf0',
        grid: 'rgba(255, 255, 255, 0.05)',
        tooltipBg: 'rgba(18, 18, 32, 0.96)',
        tooltipBorder: 'rgba(124, 58, 237, 0.3)',
        tooltipText: '#f0f0f5'
    };

    var state = {
        lastData: null,
        lastPayloadVersion: null,
        pollTimer: null,
        backoffMs: 0,
        inflight: null,
        tickerIdx: 0,
        trendChart: null,
        donutChart: null,
        donutCenter: { value: 0, label: 'مخاطب' },
        seriesHidden: {},
        numCache: {}
    };

    function readInitial() {
        var el = document.getElementById('crm-tv-initial');
        if (!el || !el.textContent) return null;
        try { return JSON.parse(el.textContent); } catch (e) { return null; }
    }

    function toFa(n) {
        var m = { '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹' };
        return String(n).replace(/[0-9]/g, function (d) { return m[d] || d; });
    }

    function toAsciiDigits(s) {
        return String(s).replace(/[۰-۹]/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'.indexOf(d); });
    }

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    function hexToRgba(hex, alpha) {
        var n = parseInt(String(hex).replace('#', ''), 16);
        if (isNaN(n)) return 'rgba(124, 58, 237, ' + alpha + ')';
        return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
    }

    function initials(name) {
        var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '؟';
        if (parts.length === 1) return parts[0].charAt(0);
        return parts[0].charAt(0) + parts[parts.length - 1].charAt(0);
    }

    function relativeTimeFromClock(timeStr) {
        if (!timeStr) return '';
        var parts = toAsciiDigits(timeStr).split(':');
        if (parts.length < 2) return timeStr;
        var h = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10);
        if (isNaN(h) || isNaN(m)) return timeStr;
        var now = new Date();
        var then = new Date(now);
        then.setHours(h, m, 0, 0);
        var diffMs = now - then;
        if (diffMs < 0) diffMs += 86400000;
        var mins = Math.floor(diffMs / 60000);
        if (mins < 1) return 'همین الان';
        if (mins < 60) return toFa(mins) + ' دقیقه پیش';
        var hrs = Math.floor(mins / 60);
        if (hrs < 24) return toFa(hrs) + ' ساعت پیش';
        return timeStr;
    }

    function animateCount(el, target, formatter, duration) {
        if (!el) return;
        var key = el.getAttribute('data-animate-key') || '';
        var prev = state.numCache[key];
        if (prev === target && el.getAttribute('data-num') === String(target)) return;
        state.numCache[key] = target;

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            el.textContent = formatter ? formatter(target) : toFa(target);
            el.setAttribute('data-num', String(target));
            return;
        }

        var start = parseInt(el.getAttribute('data-num') || '0', 10);
        if (isNaN(start)) start = 0;
        if (start === target) {
            el.textContent = formatter ? formatter(target) : toFa(target);
            el.setAttribute('data-num', String(target));
            return;
        }

        var startTime = null;
        var dur = duration || 650;
        function step(ts) {
            if (!startTime) startTime = ts;
            var p = Math.min((ts - startTime) / dur, 1);
            var eased = 1 - Math.pow(1 - p, 3);
            var val = Math.round(start + (target - start) * eased);
            el.textContent = formatter ? formatter(val) : toFa(val);
            if (p < 1) requestAnimationFrame(step);
            else el.setAttribute('data-num', String(target));
        }
        requestAnimationFrame(step);
    }

    function isCompactViewport() {
        return window.innerWidth <= 1450 || window.innerHeight <= 820;
    }

    function maxLeaderboardRows() {
        return isCompactViewport() ? 4 : 5;
    }

    function softChartMax(values) {
        var filtered = values.filter(function (v) { return v > 0; }).sort(function (a, b) { return a - b; });
        if (!filtered.length) return 1;
        var top = filtered[filtered.length - 1];
        var ref = filtered[Math.max(0, Math.floor(filtered.length * 0.7))];
        return Math.max(ref * 1.35, top * 0.72, 1);
    }

    function lineAreaGradient(chart, color) {
        var ctx = chart.ctx;
        var area = chart.chartArea;
        if (!area) return hexToRgba(color, 0.12);
        var g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
        g.addColorStop(0, hexToRgba(color, 0.28));
        g.addColorStop(0.55, hexToRgba(color, 0.08));
        g.addColorStop(1, hexToRgba(color, 0));
        return g;
    }

    function enterFullscreen() {
        var doc = document.documentElement;
        var req = doc.requestFullscreen || doc.webkitRequestFullscreen || doc.msRequestFullscreen;
        if (!req) return Promise.reject(new Error('unsupported'));
        try {
            return Promise.resolve(req.call(doc, { navigationUI: 'hide' }));
        } catch (e) {
            return Promise.resolve(req.call(doc));
        }
    }

    function exitFullscreen() {
        var exit = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
        if (exit && document.fullscreenElement) return Promise.resolve(exit.call(document));
        return Promise.resolve();
    }

    function showFsHint() {
        var hint = root.querySelector('[data-tv-fs-hint]');
        if (hint) hint.hidden = false;
    }

    function hideFsOverlay() {
        var overlay = root.querySelector('[data-tv-fs-overlay]');
        if (overlay) overlay.hidden = true;
        try { sessionStorage.setItem('crm-tv-fs-dismissed', '1'); } catch (e) { /* ignore */ }
    }

    function loadSettings() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return { schema: SETTINGS_SCHEMA, widgets: null };
            var p = JSON.parse(raw);
            if (p.schema !== SETTINGS_SCHEMA) return { schema: SETTINGS_SCHEMA, widgets: null };
            return p;
        } catch (e) { return { schema: SETTINGS_SCHEMA, widgets: null }; }
    }

    function saveSettings(patch) {
        var cur = loadSettings();
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.assign({}, cur, patch, { schema: SETTINGS_SCHEMA })));
        } catch (e) { /* ignore */ }
    }

    function applyWidgets(data) {
        var allowed = (data && data.allowed_widgets) || [];
        var sel = loadSettings().widgets;
        if (!sel || !sel.length) sel = OPTIONAL.filter(function (w) { return allowed.indexOf(w) !== -1; });
        sel = sel.filter(function (w) { return allowed.indexOf(w) !== -1; });

        root.querySelectorAll('[data-widget]').forEach(function (el) {
            var w = el.getAttribute('data-widget');
            if (ALWAYS.indexOf(w) !== -1) { el.hidden = false; return; }
            el.hidden = sel.indexOf(w) === -1;
        });

        var form = root.querySelector('[data-tv-widget-form]');
        if (form) {
            form.querySelectorAll('input[name="widget"]').forEach(function (inp) {
                var ok = allowed.indexOf(inp.value) !== -1;
                inp.disabled = !ok;
                inp.closest('.tv-cmd__check').hidden = !ok;
                inp.checked = ok && sel.indexOf(inp.value) !== -1;
            });
        }
    }

    function setStatus(mode, text) {
        var sync = root.querySelector('[data-tv-sync]');
        if (sync) {
            sync.classList.toggle('is-loading', mode === 'loading');
            sync.classList.toggle('is-offline', mode === 'offline');
        }
        var el = root.querySelector('[data-tv-updated]');
        if (el && text) el.textContent = text;
    }

    var KPI_DEFS = {
        manager: [
            ['new_leads_today', 'سرنخ جدید', 'ok', 'fa-user-plus'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'danger', 'fa-clock'],
            ['calls_today', 'تماس امروز', 'ok', 'fa-phone'],
            ['visits_today', 'بازدید امروز', 'ok', 'fa-door-open'],
            ['deals_won_today', 'قرارداد موفق', 'ok', 'fa-handshake'],
            ['commission_month', 'کمیسیون ماه', 'ok', 'fa-coins']
        ],
        secretary: [
            ['new_leads_today', 'سرنخ جدید', 'ok', 'fa-user-plus'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'danger', 'fa-clock'],
            ['calls_today', 'تماس', 'ok', 'fa-phone'],
            ['visits_today', 'بازدید', 'ok', 'fa-door-open'],
            ['deals_won_today', 'قرارداد', 'ok', 'fa-handshake'],
            ['inbox_unassigned', 'بدون تخصیص', 'warn', 'fa-inbox']
        ],
        advisor: [
            ['calls_today', 'تماس من', 'ok', 'fa-phone'],
            ['visits_today', 'بازدید من', 'ok', 'fa-door-open'],
            ['deals_won_today', 'قرارداد', 'ok', 'fa-handshake'],
            ['active_deals', 'فعال', 'ok', 'fa-briefcase'],
            ['my_score', 'امتیاز', 'ok', 'fa-star'],
            ['my_rank', 'رتبه', 'ok', 'fa-ranking-star']
        ]
    };

    function formatKpiValue(key, value) {
        if (key === 'commission_month' && value >= 1000000) {
            return toFa(Math.round(value / 1000000)) + 'M';
        }
        return toFa(value);
    }

    function renderKpis(data) {
        var row = root.querySelector('[data-tv-kpis]');
        if (!row) return;
        var defs = KPI_DEFS[data.role] || KPI_DEFS.advisor;
        var kpis = data.kpis || {};

        defs.forEach(function (def, idx) {
            var key = def[0];
            var card = row.querySelector('[data-kpi="' + key + '"]');
            if (!card) {
                card = document.createElement('article');
                card.className = 'tv-cmd__kpi';
                card.setAttribute('data-kpi', key);
                card.innerHTML =
                    '<span class="tv-cmd__kpi-icon"><i class="fas"></i></span>' +
                    '<span class="tv-cmd__kpi-val" data-val data-animate-key="kpi-' + key + '">۰</span>' +
                    '<span class="tv-cmd__kpi-lbl"></span>' +
                    '<span class="tv-cmd__kpi-delta" data-delta></span>';
                row.appendChild(card);
            }
            card.classList.toggle('tv-cmd__kpi--optional', idx === defs.length - 1);
            card.querySelector('.tv-cmd__kpi-lbl').textContent = def[1];
            var icon = card.querySelector('.tv-cmd__kpi-icon i');
            if (icon) icon.className = 'fas ' + (def[3] || 'fa-chart-simple');

            var k = kpis[key] || { value: 0, delta: null, status: def[2] };
            var valEl = card.querySelector('[data-val]');
            animateCount(valEl, Number(k.value) || 0, function (v) { return formatKpiValue(key, v); });

            card.classList.toggle('tv-cmd__kpi--warn', k.status === 'warn');
            card.classList.toggle('tv-cmd__kpi--danger', k.status === 'danger');
            card.classList.toggle('tv-cmd__kpi--gold', key === 'commission_month');

            var dEl = card.querySelector('[data-delta]');
            if (k.delta != null) {
                var up = k.delta >= 0;
                dEl.className = 'tv-cmd__kpi-delta tv-cmd__kpi-delta--' + (up ? 'up' : 'down');
                dEl.innerHTML = '<i class="fas fa-' + (up ? 'arrow-trend-up' : 'arrow-trend-down') + '"></i> ' +
                    toFa(Math.abs(k.delta)) + '% دیروز';
            } else {
                dEl.textContent = '';
                dEl.className = 'tv-cmd__kpi-delta';
            }
        });
    }

    function rankBadgeClass(rank) {
        if (rank === 1) return 'tv-cmd__board-rank--gold';
        if (rank === 2) return 'tv-cmd__board-rank--silver';
        if (rank === 3) return 'tv-cmd__board-rank--bronze';
        return '';
    }

    function renderLeaderboard(data) {
        var list = root.querySelector('[data-tv-leaderboard]');
        if (!list) return;
        var rows = (data.leaderboard || []).slice(0, maxLeaderboardRows());
        if (!rows.length) {
            if (!list.querySelector('.tv-cmd__empty-state--inline')) {
                list.innerHTML =
                    '<li class="tv-cmd__empty-state tv-cmd__empty-state--inline">' +
                    '<i class="fas fa-ranking-star"></i><p>هنوز فعالیتی ثبت نشده</p></li>';
            }
            return;
        }
        var empty = list.querySelector('.tv-cmd__empty-state--inline');
        if (empty) empty.remove();

        rows.forEach(function (r) {
            var key = String(r.rank);
            var li = list.querySelector('[data-rank="' + key + '"]');
            if (!li) {
                li = document.createElement('li');
                li.className = 'tv-cmd__board-row';
                li.setAttribute('data-rank', key);
                li.innerHTML =
                    '<span class="tv-cmd__board-rank"></span>' +
                    '<span class="tv-cmd__board-avatar"></span>' +
                    '<div class="tv-cmd__board-info">' +
                    '<div class="tv-cmd__board-name"></div>' +
                    '<div class="tv-cmd__board-role"></div>' +
                    '<div class="tv-cmd__board-bar"><i></i></div>' +
                    '</div>' +
                    '<span class="tv-cmd__board-score" data-animate-key="score-' + key + '"></span>';
                list.appendChild(li);
            }

            li.classList.toggle('tv-cmd__board-row--top', r.rank === 1);
            li.classList.toggle('tv-cmd__board-row--second', r.rank === 2);
            li.classList.toggle('tv-cmd__board-row--third', r.rank === 3);

            var rankEl = li.querySelector('.tv-cmd__board-rank');
            rankEl.textContent = toFa(r.rank);
            rankEl.className = 'tv-cmd__board-rank ' + rankBadgeClass(r.rank);

            li.querySelector('.tv-cmd__board-avatar').textContent = initials(r.name);
            li.querySelector('.tv-cmd__board-name').textContent = r.name;
            li.querySelector('.tv-cmd__board-role').textContent = r.role;

            var barInner = li.querySelector('.tv-cmd__board-bar i');
            var pct = r.score_pct || 0;
            barInner.style.width = pct + '%';

            var scoreEl = li.querySelector('.tv-cmd__board-score');
            animateCount(scoreEl, Number(r.score) || 0);
        });

        list.querySelectorAll('[data-rank]').forEach(function (li) {
            var rank = li.getAttribute('data-rank');
            if (!rows.some(function (r) { return String(r.rank) === rank; })) li.remove();
        });
    }

    var donutCenterPlugin = {
        id: 'tvDonutCenter',
        afterDraw: function (chart) {
            if (chart.config.type !== 'doughnut') return;
            var meta = state.donutCenter || {};
            var area = chart.chartArea;
            if (!area) return;
            var cx = (area.left + area.right) / 2;
            var cy = (area.top + area.bottom) / 2;
            var ctx = chart.ctx;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = CHART_THEME.tooltipText;
            ctx.font = '800 ' + Math.round(Math.min(area.width, area.height) * 0.22) + 'px Vazirmatn, sans-serif';
            ctx.fillText(toFa(meta.value || 0), cx, cy - 6);
            ctx.fillStyle = CHART_THEME.text;
            ctx.font = '600 ' + Math.round(Math.min(area.width, area.height) * 0.11) + 'px Vazirmatn, sans-serif';
            ctx.fillText(meta.label || 'مخاطب', cx, cy + Math.round(Math.min(area.width, area.height) * 0.14));
            ctx.restore();
        }
    };

    function renderDonutChart(doughnut) {
        var canvas = root.querySelector('[data-tv-donut]');
        var emptyEl = root.querySelector('[data-tv-donut-empty]');
        var title = root.querySelector('[data-tv-donut-title]');
        if (!canvas || !window.Chart) return;

        doughnut = doughnut || { slices: [], center_value: 0, center_label: 'مخاطب', heading: 'پرونده مخاطبین' };
        var slices = (doughnut.slices || []).filter(function (sl) {
            return sl.value > 0 && sl.label !== 'بدون مخاطب';
        });
        var total = slices.reduce(function (sum, sl) { return sum + sl.value; }, 0);
        var isEmpty = !total;

        if (title) title.textContent = doughnut.heading || doughnut.title || 'پرونده مخاطبین';
        state.donutCenter = {
            value: doughnut.center_value || total || 0,
            label: doughnut.center_label || 'مخاطب'
        };

        canvas.hidden = isEmpty;
        if (emptyEl) emptyEl.hidden = !isEmpty;
        if (isEmpty) {
            if (state.donutChart) {
                state.donutChart.destroy();
                state.donutChart = null;
            }
            return;
        }

        var labels = slices.map(function (sl) { return sl.label; });
        var values = slices.map(function (sl) { return sl.value; });
        var colors = slices.map(function (sl) { return sl.color; });
        var borderColors = colors.map(function (c) { return hexToRgba(c, 0.35); });

        if (state.donutChart) {
            state.donutChart.data.labels = labels;
            state.donutChart.data.datasets[0].data = values;
            state.donutChart.data.datasets[0].backgroundColor = colors;
            state.donutChart.data.datasets[0].borderColor = borderColors;
            state.donutChart.update('none');
            return;
        }

        state.donutChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderColor: borderColors,
                    borderWidth: 2,
                    borderRadius: slices.length === 1 ? 6 : 4,
                    spacing: slices.length === 1 ? 0 : 2,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                animation: { animateRotate: true, duration: 700, easing: 'easeOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: CHART_THEME.tooltipBg,
                        titleColor: CHART_THEME.tooltipText,
                        bodyColor: CHART_THEME.tooltipText,
                        borderColor: CHART_THEME.tooltipBorder,
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 10,
                        rtl: true,
                        textDirection: 'rtl',
                        callbacks: {
                            label: function (ctx) {
                                var pct = total ? Math.round(ctx.parsed / total * 100) : 0;
                                return ctx.label + ': ' + toFa(ctx.parsed) + ' (' + toFa(pct) + '%)';
                            }
                        }
                    }
                }
            },
            plugins: [donutCenterPlugin]
        });
    }

    function bindTrendLegend(series) {
        var pillsEl = root.querySelector('[data-tv-trend-legend]');
        if (!pillsEl) return;

        pillsEl.innerHTML = series.map(function (s, idx) {
            var hidden = state.seriesHidden[s.key];
            return (
                '<button type="button" class="tv-cmd__chip' + (hidden ? ' is-off' : '') + '" ' +
                'data-series-idx="' + idx + '" data-series-key="' + esc(s.key) + '" ' +
                'style="--chip-color:' + s.color + '" aria-pressed="' + (!hidden) + '">' +
                '<i></i><span>' + esc(s.label) + '</span>' +
                '<b>' + toFa(s.total || 0) + '</b>' +
                '</button>'
            );
        }).join('');
    }

    function initTrendLegendDelegation() {
        var pillsEl = root.querySelector('[data-tv-trend-legend]');
        if (!pillsEl || pillsEl._tvDelegated) return;
        pillsEl._tvDelegated = true;
        pillsEl.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-series-idx]');
            if (!btn || !state.trendChart) return;
            var idx = parseInt(btn.getAttribute('data-series-idx'), 10);
            var meta = state.trendChart.getDatasetMeta(idx);
            meta.hidden = !meta.hidden;
            state.seriesHidden[btn.getAttribute('data-series-key')] = meta.hidden;
            btn.classList.toggle('is-off', meta.hidden);
            btn.setAttribute('aria-pressed', String(!meta.hidden));
            state.trendChart.update('none');
        });
    }

    function renderTrendKpis(series, activityTotal) {
        var el = root.querySelector('[data-tv-trend-kpis]');
        if (!el) return;
        if (!series.length || !activityTotal) {
            el.innerHTML = '';
            return;
        }

        el.innerHTML = series.map(function (s) {
            var pct = s.share_pct || 0;
            return (
                '<div class="tv-cmd__summary-card" style="--sc-color:' + s.color + '">' +
                '<div class="tv-cmd__summary-card-head">' +
                '<span><i></i>' + esc(s.label) + '</span>' +
                '<strong>' + toFa(s.total || 0) + '</strong>' +
                '</div>' +
                '<div class="tv-cmd__summary-card-bar"><i style="width:' + pct + '%"></i></div>' +
                '<div class="tv-cmd__summary-card-foot">' +
                toFa(pct) + '% از کل' +
                '</div></div>'
            );
        }).join('');
    }

    function renderTrendChart(chart) {
        var canvas = root.querySelector('[data-tv-chart]');
        var emptyEl = root.querySelector('[data-tv-chart-empty]');
        if (!canvas || !window.Chart) return;

        var points = chart.points || [];
        var series = chart.series || [
            { key: 'calls', color: '#7c3aed', label: 'تماس' },
            { key: 'visits', color: '#06b6d4', label: 'بازدید' },
            { key: 'leads', color: '#f59e0b', label: 'لید' },
            { key: 'deals', color: '#22c55e', label: 'قرارداد' }
        ];
        var activityTotal = chart.activity_total || 0;
        var allVals = [];
        points.forEach(function (p) {
            series.forEach(function (s) { allVals.push(p[s.key] || 0); });
        });
        var suggestedMax = Math.ceil(softChartMax(allVals));
        var isEmpty = !activityTotal || !points.length;

        bindTrendLegend(series);
        renderTrendKpis(series, activityTotal);

        canvas.hidden = isEmpty;
        if (emptyEl) emptyEl.hidden = !isEmpty;
        if (isEmpty) {
            if (state.trendChart) {
                state.trendChart.destroy();
                state.trendChart = null;
            }
            return;
        }

        var labels = points.map(function (p) { return p.label; });
        var datasets = series.map(function (s, idx) {
            return {
                label: s.label,
                data: points.map(function (p) { return p[s.key] || 0; }),
                borderColor: s.color,
                backgroundColor: function (ctx) { return lineAreaGradient(ctx.chart, s.color); },
                borderWidth: 2.5,
                pointRadius: 3.5,
                pointHoverRadius: 6,
                pointBackgroundColor: s.color,
                pointBorderColor: '#090912',
                pointBorderWidth: 2,
                tension: 0.42,
                fill: true,
                hidden: !!state.seriesHidden[s.key]
            };
        });

        if (state.trendChart) {
            state.trendChart.data.labels = labels;
            state.trendChart.data.datasets.forEach(function (ds, i) {
                ds.data = datasets[i].data;
                ds.hidden = datasets[i].hidden;
            });
            state.trendChart.options.scales.y.suggestedMax = suggestedMax;
            state.trendChart.update('none');
            return;
        }

        state.trendChart = new Chart(canvas, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                animation: { duration: 750, easing: 'easeOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: CHART_THEME.tooltipBg,
                        titleColor: CHART_THEME.tooltipText,
                        bodyColor: CHART_THEME.textBright,
                        borderColor: CHART_THEME.tooltipBorder,
                        borderWidth: 1,
                        padding: 14,
                        cornerRadius: 12,
                        rtl: true,
                        textDirection: 'rtl',
                        titleFont: { family: 'Vazirmatn', size: 12, weight: '700' },
                        bodyFont: { family: 'Vazirmatn', size: 11 },
                        boxPadding: 6,
                        usePointStyle: true,
                        callbacks: {
                            label: function (ctx) {
                                return ctx.dataset.label + ': ' + toFa(ctx.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: CHART_THEME.text,
                            font: { family: 'Vazirmatn', size: 10, weight: '600' },
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 7
                        },
                        border: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        suggestedMax: suggestedMax,
                        grid: {
                            color: CHART_THEME.grid,
                            drawTicks: false
                        },
                        ticks: {
                            color: CHART_THEME.text,
                            stepSize: Math.max(1, Math.ceil(suggestedMax / 4)),
                            font: { family: 'Vazirmatn', size: 10 },
                            padding: 8,
                            callback: function (v) { return toFa(v); }
                        },
                        border: { display: false }
                    }
                }
            }
        });
    }

    function renderChartLegend(chart) {
        var legend = root.querySelector('[data-tv-chart-legend]');
        if (!legend) return;

        var doughnut = chart.doughnut || {};
        var slices = (doughnut.slices || []).filter(function (sl) {
            return sl.value > 0 && sl.label !== 'بدون مخاطب';
        });
        if (!slices.length) {
            legend.innerHTML =
                '<div class="tv-cmd__empty-state tv-cmd__empty-state--inline">' +
                '<i class="fas fa-users"></i><p>مخاطبی ثبت نشده</p></div>';
            return;
        }

        legend.innerHTML = slices.map(function (sl) {
            return (
                '<div class="tv-cmd__audience-item" style="--c:' + sl.color + '">' +
                '<span class="tv-cmd__audience-dot"></span>' +
                '<div class="tv-cmd__audience-body">' +
                '<em>' + esc(sl.label) + '</em>' +
                '<span class="tv-cmd__audience-meta">' +
                '<b>' + toFa(sl.value || 0) + '</b>' +
                '<i>(' + toFa(sl.pct || 0) + '%)</i>' +
                '</span></div>' +
                '<div class="tv-cmd__audience-bar"><span style="width:' + (sl.pct || 0) + '%"></span></div>' +
                '</div>'
            );
        }).join('');
    }

    function renderChart(data) {
        var chart = data.chart || {};
        renderTrendChart(chart);
        renderDonutChart(chart.doughnut);
        renderChartLegend(chart);

        var sub = root.querySelector('[data-tv-chart-subtitle]');
        if (sub) {
            var total = chart.activity_total || 0;
            sub.textContent = total
                ? toFa(total) + ' فعالیت در ۷ روز · توزیع مخاطبین'
                : 'توزیع مخاطبین · روند ۷ روزه';
        }
    }

    function goalStatusClass(g) {
        if (g.completed) return ' tv-cmd__goal-bar--done';
        if (g.status === 'warn') return ' tv-cmd__goal-bar--warn';
        if (g.status === 'low') return ' tv-cmd__goal-bar--low';
        return '';
    }

    function renderGoals(data) {
        var el = root.querySelector('[data-tv-goals]');
        if (!el) return;
        var goals = (data.goals || []).slice(0, 4);
        if (!goals.length) {
            if (!el.querySelector('.tv-cmd__empty-state--inline')) {
                el.innerHTML =
                    '<div class="tv-cmd__empty-state tv-cmd__empty-state--inline">' +
                    '<i class="fas fa-bullseye"></i><p>هدفی ثبت نشده</p></div>';
            }
            return;
        }
        var empty = el.querySelector('.tv-cmd__empty-state--inline');
        if (empty) empty.remove();

        var minDays = null;
        goals.forEach(function (g) {
            if (!g.completed && g.days_left != null) {
                minDays = minDays == null ? g.days_left : Math.min(minDays, g.days_left);
            }
            var node = el.querySelector('[data-goal="' + g.goal_key + '"]');
            if (!node) {
                node = document.createElement('div');
                node.className = 'tv-cmd__goal';
                node.setAttribute('data-goal', g.goal_key);
                node.innerHTML =
                    '<div class="tv-cmd__goal-head">' +
                    '<span class="tv-cmd__goal-title"></span>' +
                    '<span class="tv-cmd__goal-metrics"><b data-pct></b><span data-act></span></span>' +
                    '</div>' +
                    '<div class="tv-cmd__goal-bar"><i></i></div>';
                el.appendChild(node);
            }
            node.classList.toggle('tv-cmd__goal--done', !!g.completed);
            node.querySelector('.tv-cmd__goal-title').textContent = g.title;
            var bar = node.querySelector('.tv-cmd__goal-bar');
            bar.className = 'tv-cmd__goal-bar' + goalStatusClass(g);
            bar.querySelector('i').style.width = g.pct + '%';
            node.querySelector('[data-act]').textContent = toFa(g.actual) + ' / ' + toFa(g.target);
            node.querySelector('[data-pct]').textContent = toFa(g.pct) + '%';
        });

        var foot = el.querySelector('[data-tv-goals-foot]');
        if (minDays != null) {
            if (!foot) {
                foot = document.createElement('p');
                foot.className = 'tv-cmd__goals-foot';
                foot.setAttribute('data-tv-goals-foot', '');
                el.appendChild(foot);
            }
            foot.innerHTML = '<i class="fas fa-hourglass-half"></i> ' + toFa(minDays) + ' روز تا پایان ماه';
            foot.hidden = false;
        } else if (foot) {
            foot.hidden = true;
        }
    }

    function activityIcon(key) {
        if (!key) return 'fa-bolt';
        if (key.indexOf('audit') === 0) return 'fa-user-plus';
        if (key.indexOf('visit') === 0) return 'fa-door-open';
        if (key.indexOf('deal') === 0) return 'fa-handshake';
        return 'fa-circle-dot';
    }

    function renderActivity(data) {
        var list = root.querySelector('[data-tv-activity]');
        if (!list) return;
        var items = (data.activity || []).slice(0, 5);
        if (!items.length) {
            if (!list.querySelector('.tv-cmd__empty-state--inline')) {
                list.innerHTML =
                    '<li class="tv-cmd__empty-state tv-cmd__empty-state--inline">' +
                    '<i class="fas fa-bolt"></i><p>رویدادی نیست</p></li>';
            }
            return;
        }
        var empty = list.querySelector('.tv-cmd__empty-state--inline');
        if (empty) empty.remove();

        items.forEach(function (a) {
            var li = list.querySelector('[data-act-key="' + a.key + '"]');
            if (!li) {
                li = document.createElement('li');
                li.className = 'tv-cmd__feed-item';
                li.setAttribute('data-act-key', a.key);
                li.innerHTML =
                    '<span class="tv-cmd__feed-icon"><i class="fas"></i></span>' +
                    '<div class="tv-cmd__feed-body">' +
                    '<span class="tv-cmd__feed-text" data-txt></span>' +
                    '<span class="tv-cmd__feed-time" data-time></span>' +
                    '</div>';
                list.appendChild(li);
            }
            li.querySelector('.tv-cmd__feed-icon i').className = 'fas ' + activityIcon(a.key);
            li.querySelector('[data-txt]').textContent = a.text;
            li.querySelector('[data-time]').textContent = relativeTimeFromClock(a.time) || a.time || '';
        });

        list.querySelectorAll('[data-act-key]').forEach(function (li) {
            var k = li.getAttribute('data-act-key');
            if (!items.some(function (a) { return a.key === k; })) li.remove();
        });
    }

    function renderSchedule(data) {
        var el = root.querySelector('[data-tv-schedule]');
        if (!el) return;
        var s = data.schedule || {};
        var rows = [
            { key: 'visits', icon: 'fa-door-open', val: s.visits_today || 0, label: 'بازدید امروز', tone: 'ok' },
            { key: 'followups', icon: 'fa-phone-volume', val: s.followups_today || 0, label: 'پیگیری امروز', tone: 'info' },
            { key: 'overdue', icon: 'fa-clock', val: s.overdue_followups || 0, label: 'پیگیری معوق', tone: s.overdue_followups ? 'warn' : 'muted' },
            { key: 'inbox', icon: 'fa-inbox', val: s.inbox_unassigned || 0, label: 'صندوق ورودی', tone: s.inbox_unassigned ? 'warn' : 'muted' }
        ];
        var hasAny = rows.some(function (r) { return r.val > 0; });
        var hint = s.next_hint || '';

        if (!hasAny && !hint) {
            el.innerHTML =
                '<div class="tv-cmd__empty-state tv-cmd__empty-state--inline">' +
                '<i class="fas fa-calendar-day"></i><p>برنامه‌ای برای امروز ثبت نشده</p></div>';
            return;
        }

        var html = '<div class="tv-cmd__sched-list">';
        rows.forEach(function (r) {
            html +=
                '<div class="tv-cmd__sched-row tv-cmd__sched-row--' + r.tone + '" data-sched="' + r.key + '">' +
                '<span class="tv-cmd__sched-icon"><i class="fas ' + r.icon + '"></i></span>' +
                '<div class="tv-cmd__sched-body">' +
                '<span class="tv-cmd__sched-label">' + r.label + '</span>' +
                '<span class="tv-cmd__sched-val">' + toFa(r.val) + '</span>' +
                '</div>' +
                '<span class="tv-cmd__sched-dot' + (r.val > 0 ? ' is-active' : '') + '"></span>' +
                '</div>';
        });
        if (hint) {
            html += '<p class="tv-cmd__sched-hint"><i class="fas fa-circle-info"></i> ' + esc(hint) + '</p>';
        }
        html += '</div>';
        if (el.innerHTML !== html) el.innerHTML = html;
    }

    function renderAlerts(data) {
        var strip = root.querySelector('[data-tv-alerts-strip]');
        if (!strip) return;
        var alerts = data.alerts || [];
        if (!alerts.length) { strip.hidden = true; strip.innerHTML = ''; return; }
        strip.hidden = false;
        strip.innerHTML = alerts.map(function (a) {
            return '<span class="tv-cmd__alert-pill tv-cmd__alert-pill--' + esc(a.level) + '">' + esc(a.text) + '</span>';
        }).join('');
    }

    function renderTicker(data) {
        var track = root.querySelector('[data-tv-ticker-track]');
        if (!track) return;
        var items = data.announcements || [];
        if (!items.length) {
            track.className = 'tv-cmd__ticker-track tv-cmd__ticker-track--static';
            track.textContent = 'اطلاعیه فعالی نیست';
            return;
        }
        var parts = items.map(function (a) {
            var pin = a.is_pinned ? '📌 ' : '';
            var imp = a.importance === 'urgent' ? '⚠ ' : (a.importance === 'high' ? '● ' : '');
            return pin + imp + a.title + (a.preview ? ' — ' + a.preview : '');
        });
        var text = parts.join('    ·    ');
        track.className = 'tv-cmd__ticker-track' + (parts.length < 2 ? ' tv-cmd__ticker-track--static' : '');
        if (parts.length >= 2) text = text + '    ·    ' + text;
        track.textContent = text;
    }

    function renderMeta(data) {
        var d = root.querySelector('[data-tv-date]');
        if (d && data.jalali_date) d.textContent = data.jalali_date;
        var n = root.querySelector('[data-tv-agency-name]');
        if (n && data.agency) n.textContent = data.agency.name;
        var logoWrap = root.querySelector('[data-tv-logo]');
        if (logoWrap && data.agency && data.agency.logo_url) {
            var logoUrl = data.agency.logo_url;
            var img = logoWrap.querySelector('[data-tv-agency-logo]');
            if (!img) {
                img = document.createElement('img');
                img.className = 'tv-cmd__logo tv-cmd__logo--img';
                img.setAttribute('data-tv-agency-logo', '');
                img.width = 48;
                img.height = 48;
                img.alt = data.agency.name || '';
                logoWrap.innerHTML = '';
                logoWrap.appendChild(img);
            }
            if (img.src !== logoUrl) img.src = logoUrl;
        }
    }

    function resizeCharts() {
        if (state.trendChart) state.trendChart.resize();
        if (state.donutChart) state.donutChart.resize();
    }

    function renderAll(data, force) {
        if (!data || !data.ok) return;
        if (!force && data.payload_version && data.payload_version === state.lastPayloadVersion) {
            renderMeta(data);
            setStatus('live', 'به‌روز');
            return;
        }
        state.lastPayloadVersion = data.payload_version;
        state.lastData = data;
        applyWidgets(data);
        renderKpis(data);
        renderLeaderboard(data);
        renderChart(data);
        renderGoals(data);
        renderActivity(data);
        renderSchedule(data);
        renderAlerts(data);
        renderTicker(data);
        renderMeta(data);
        setStatus('live', 'به‌روز');
    }

    function tickClock() {
        var now = new Date();
        var t = toFa(
            String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0') + ':' +
            String(now.getSeconds()).padStart(2, '0')
        );
        var c = root.querySelector('[data-tv-clock]');
        if (c) c.textContent = t;
    }

    function schedulePoll(delay) {
        if (state.pollTimer) clearTimeout(state.pollTimer);
        state.pollTimer = setTimeout(function () {
            fetchData().finally(scheduleNext);
        }, delay);
    }

    function scheduleNext() {
        var base = (cfg.pollMs || 45000) + state.backoffMs;
        if (document.hidden) base = Math.max(base, 120000);
        schedulePoll(base);
    }

    function fetchData() {
        if (!cfg.apiUrl) return Promise.resolve();
        if (state.inflight) state.inflight.abort();
        var ctrl = new AbortController();
        state.inflight = ctrl;
        var timer = setTimeout(function () { ctrl.abort(); }, 10000);
        setStatus('loading', state.lastData ? 'بروزرسانی…' : 'بارگذاری…');
        root.classList.add('is-refreshing');

        return fetch(cfg.apiUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: ctrl.signal })
            .then(function (r) { if (!r.ok) throw new Error('http'); return r.json(); })
            .then(function (data) {
                clearTimeout(timer);
                state.inflight = null;
                state.backoffMs = 0;
                renderAll(data, false);
            })
            .catch(function (err) {
                clearTimeout(timer);
                state.inflight = null;
                if (err && err.name === 'AbortError') return;
                state.backoffMs = Math.min(state.backoffMs ? state.backoffMs * 2 : 5000, 60000);
                setStatus('offline', state.lastData ? 'قطع' : 'خطا در اتصال');
            })
            .finally(function () {
                root.classList.remove('is-refreshing');
            });
    }

    function toggleFullscreen() {
        if (document.fullscreenElement) {
            exitFullscreen();
            return;
        }
        enterFullscreen().then(hideFsOverlay).catch(showFsHint);
    }

    function bindControls() {
        var fs = root.querySelector('[data-tv-fullscreen]');
        if (fs) fs.addEventListener('click', toggleFullscreen);

        var fsStart = root.querySelector('[data-tv-fs-start]');
        if (fsStart) fsStart.addEventListener('click', toggleFullscreen);

        var fsOverlay = root.querySelector('[data-tv-fs-overlay]');
        if (fsOverlay) {
            fsOverlay.addEventListener('click', function (e) {
                if (e.target === fsOverlay) hideFsOverlay();
            });
        }

        document.addEventListener('fullscreenchange', function () {
            var icon = fs && fs.querySelector('i');
            if (icon) {
                icon.className = document.fullscreenElement ? 'fas fa-compress' : 'fas fa-expand';
            }
            if (document.fullscreenElement) hideFsOverlay();
            resizeCharts();
        });

        var drawer = root.querySelector('[data-tv-widget-drawer]');
        root.querySelector('[data-tv-widgets]')?.addEventListener('click', function () { if (drawer) drawer.hidden = false; });
        root.querySelector('[data-tv-widgets-close]')?.addEventListener('click', function () { if (drawer) drawer.hidden = true; });
        drawer?.addEventListener('click', function (e) { if (e.target === drawer) drawer.hidden = true; });

        var form = root.querySelector('[data-tv-widget-form]');
        if (form) form.addEventListener('change', function () {
            var sel = [];
            form.querySelectorAll('input:checked:not(:disabled)').forEach(function (i) { sel.push(i.value); });
            saveSettings({ widgets: sel });
            if (state.lastData) applyWidgets(state.lastData);
        });

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) { state.backoffMs = 0; fetchData(); }
            scheduleNext();
        });

        var hideTimer;
        root.addEventListener('mousemove', function () {
            root.classList.remove('tv-cmd--fs-hide-chrome');
            clearTimeout(hideTimer);
            if (document.fullscreenElement) {
                hideTimer = setTimeout(function () { root.classList.add('tv-cmd--fs-hide-chrome'); }, 4000);
            }
        });
    }

    function init() {
        var initial = readInitial();
        if (initial && initial.ok) renderAll(initial, true);
        else setStatus('loading', 'بارگذاری…');
        tickClock();
        setInterval(tickClock, 1000);
        bindControls();
        initTrendLegendDelegation();
        var overlay = root.querySelector('[data-tv-fs-overlay]');
        var dismissed = false;
        try { dismissed = !!sessionStorage.getItem('crm-tv-fs-dismissed'); } catch (e) { /* ignore */ }
        if (overlay && !document.fullscreenElement && !dismissed) overlay.hidden = false;

        var resizeTimer;
        window.addEventListener('resize', function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (state.lastData) renderLeaderboard(state.lastData);
                resizeCharts();
            }, 120);
        });

        fetchData().finally(scheduleNext);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
