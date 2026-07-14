/**
 * Live Command Center — TV Dashboard (Blueprint rebuild)
 */
(function () {
    'use strict';

    var root = document.getElementById('crm-tv-app');
    if (!root) return;

    var cfg = window.crmTeamTV || {};
    var STORAGE_KEY = 'crm-tv-settings-v4';
    var SETTINGS_SCHEMA = 4;
    var OPTIONAL = ['chart', 'goals', 'activity', 'schedule', 'announcements', 'alerts'];
    var ALWAYS = ['kpis', 'leaderboard'];

    var CHART_THEME = {
        text: '#94a3b8',
        textBright: '#f8fafc',
        grid: 'rgba(148, 163, 184, 0.08)',
        tooltipBg: 'rgba(15, 23, 42, 0.96)',
        tooltipBorder: 'rgba(124, 58, 237, 0.35)',
        tooltipText: '#f8fafc'
    };

    var state = {
        lastData: null,
        lastPayloadVersion: null,
        pollTimer: null,
        backoffMs: 0,
        inflight: null,
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

    function formatAnnTime(iso) {
        if (!iso) return '';
        try {
            var d = new Date(iso);
            return toFa(
                String(d.getHours()).padStart(2, '0') + ':' +
                String(d.getMinutes()).padStart(2, '0')
            );
        } catch (e) {
            return '';
        }
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
        g.addColorStop(0, hexToRgba(color, 0.3));
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
                inp.closest('.lcc-check').hidden = !ok;
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
        var live = root.querySelector('[data-tv-live-label]');
        if (live) {
            live.textContent = mode === 'offline' ? 'آفلاین' : (mode === 'loading' ? 'بروزرسانی' : 'آنلاین');
        }
        var el = root.querySelector('[data-tv-updated]');
        if (el && text) {
            el.textContent = mode === 'live' ? 'به‌روز' : text;
        }
    }

    var KPI_COLORS = {
        new_leads_today: '#7c3aed',
        calls_today: '#38bdf8',
        visits_today: '#f59e0b',
        followups_today: '#22c55e',
        active_deals: '#06b6d4',
        deals_won_today: '#22c55e',
        commission_month: '#fbbf24',
        overdue_followups: '#ef4444',
        inbox_unassigned: '#f59e0b',
        my_score: '#7c3aed',
        my_rank: '#fbbf24'
    };

    var KPI_DEFS = {
        manager: [
            ['new_leads_today', 'سرنخ جدید امروز', 'ok', 'fa-user-plus'],
            ['calls_today', 'تماس‌های امروز', 'ok', 'fa-phone'],
            ['followups_today', 'پیگیری‌های امروز', 'ok', 'fa-phone-volume'],
            ['visits_today', 'بازدیدهای امروز', 'ok', 'fa-door-open'],
            ['active_deals', 'معاملات فعال', 'ok', 'fa-briefcase'],
            ['commission_month', 'کمیسیون این ماه', 'gold', 'fa-coins']
        ],
        secretary: [
            ['new_leads_today', 'سرنخ جدید امروز', 'ok', 'fa-user-plus'],
            ['calls_today', 'تماس‌های امروز', 'ok', 'fa-phone'],
            ['followups_today', 'پیگیری‌های امروز', 'ok', 'fa-phone-volume'],
            ['visits_today', 'بازدیدهای امروز', 'ok', 'fa-door-open'],
            ['deals_won_today', 'قرارداد موفق', 'ok', 'fa-handshake'],
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

    function resolveKpiEntry(data, key, fallbackStatus) {
        var kpis = data.kpis || {};
        if (kpis[key]) return kpis[key];
        if (key === 'followups_today') {
            var v = (data.schedule && data.schedule.followups_today) || 0;
            return { value: v, delta: null, status: fallbackStatus || 'ok' };
        }
        return { value: 0, delta: null, status: fallbackStatus || 'ok' };
    }

    function formatKpiValue(key, value) {
        if (key === 'commission_month') {
            if (value >= 1000000) return toFa(Math.round(value / 1000000 * 10) / 10);
            return toFa(value);
        }
        return toFa(value);
    }

    function kpiHasUnit(key) {
        return key === 'commission_month';
    }

    function renderKpis(data) {
        var row = root.querySelector('[data-tv-kpis]');
        if (!row) return;
        var defs = KPI_DEFS[data.role] || KPI_DEFS.advisor;

        defs.forEach(function (def) {
            var key = def[0];
            var card = row.querySelector('[data-kpi="' + key + '"]');
            if (!card) {
                card = document.createElement('article');
                card.className = 'lcc-kpi';
                card.setAttribute('data-kpi', key);
                card.innerHTML =
                    '<span class="lcc-kpi__icon"><i class="fas"></i></span>' +
                    '<span class="lcc-kpi__label"></span>' +
                    '<span class="lcc-kpi__value" data-val data-animate-key="kpi-' + key + '">۰</span>' +
                    '<span class="lcc-kpi__delta" data-delta></span>';
                row.appendChild(card);
            }
            card.style.setProperty('--kc', KPI_COLORS[key] || '#7c3aed');
            card.querySelector('.lcc-kpi__label').textContent = def[1];
            var icon = card.querySelector('.lcc-kpi__icon i');
            if (icon) icon.className = 'fas ' + (def[3] || 'fa-chart-simple');

            var k = resolveKpiEntry(data, key, def[2]);
            var valEl = card.querySelector('[data-val]');
            var num = Number(k.value) || 0;
            var unitEl = card.querySelector('.lcc-kpi__unit');
            if (unitEl) unitEl.remove();
            animateCount(valEl, num, function (v) {
                if (kpiHasUnit(key) && v >= 1000000) {
                    return formatKpiValue(key, v) + 'M';
                }
                return formatKpiValue(key, v);
            });
            if (kpiHasUnit(key) && num >= 1000000) {
                valEl.insertAdjacentHTML('beforeend', '<span class="lcc-kpi__unit">تومان</span>');
            }

            card.classList.toggle('lcc-kpi--warn', k.status === 'warn');
            card.classList.toggle('lcc-kpi--danger', k.status === 'danger');

            var dEl = card.querySelector('[data-delta]');
            if (k.delta != null) {
                var up = k.delta >= 0;
                dEl.className = 'lcc-kpi__delta lcc-kpi__delta--' + (up ? 'up' : 'down');
                dEl.innerHTML = (up ? '▲ ' : '▼ ') + toFa(Math.abs(k.delta)) + '% نسبت به دیروز';
            } else {
                dEl.textContent = '';
                dEl.className = 'lcc-kpi__delta';
            }
        });
    }

    function rankBadgeClass(rank) {
        if (rank === 1) return 'lcc-lb__rank--gold';
        if (rank === 2) return 'lcc-lb__rank--silver';
        if (rank === 3) return 'lcc-lb__rank--bronze';
        return '';
    }

    function rankDisplay(rank) {
        if (rank === 1) return '🥇';
        if (rank === 2) return '🥈';
        if (rank === 3) return '🥉';
        return toFa(rank);
    }

    function renderLeaderboard(data) {
        var list = root.querySelector('[data-tv-leaderboard]');
        if (!list) return;
        var rows = (data.leaderboard || []).slice(0, maxLeaderboardRows());
        if (!rows.length) {
            if (!list.querySelector('.lcc-empty--inline')) {
                list.innerHTML =
                    '<li class="lcc-empty lcc-empty--inline">' +
                    '<i class="fas fa-ranking-star"></i><p>هنوز فعالیتی ثبت نشده</p></li>';
            }
            return;
        }
        var empty = list.querySelector('.lcc-empty--inline');
        if (empty) empty.remove();

        rows.forEach(function (r) {
            var key = String(r.rank);
            var li = list.querySelector('[data-rank="' + key + '"]');
            if (!li) {
                li = document.createElement('li');
                li.className = 'lcc-lb__row';
                li.setAttribute('data-rank', key);
                li.innerHTML =
                    '<span class="lcc-lb__rank"></span>' +
                    '<span class="lcc-lb__avatar"></span>' +
                    '<div class="lcc-lb__body">' +
                    '<div class="lcc-lb__name"></div>' +
                    '<div class="lcc-lb__role"></div>' +
                    '<div class="lcc-lb__bar"><span></span></div>' +
                    '</div>' +
                    '<span class="lcc-lb__score" data-animate-key="score-' + key + '"></span>';
                list.appendChild(li);
            }

            li.className = 'lcc-lb__row' + (r.rank === 1 ? ' lcc-lb__row--top' : '');

            var rankEl = li.querySelector('.lcc-lb__rank');
            rankEl.textContent = rankDisplay(r.rank);
            rankEl.className = 'lcc-lb__rank ' + rankBadgeClass(r.rank);

            li.querySelector('.lcc-lb__avatar').textContent = initials(r.name);
            li.querySelector('.lcc-lb__name').textContent = r.name;
            li.querySelector('.lcc-lb__role').textContent = r.role;

            li.querySelector('.lcc-lb__bar span').style.width = (r.score_pct || 0) + '%';
            animateCount(li.querySelector('.lcc-lb__score'), Number(r.score) || 0);
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
            var size = Math.min(area.width, area.height);
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = CHART_THEME.tooltipText;
            ctx.font = '800 ' + Math.round(size * 0.22) + 'px Vazirmatn, sans-serif';
            ctx.fillText(toFa(meta.value || 0), cx, cy - 5);
            ctx.fillStyle = CHART_THEME.text;
            ctx.font = '600 ' + Math.round(size * 0.11) + 'px Vazirmatn, sans-serif';
            ctx.fillText(meta.label || 'مخاطب', cx, cy + Math.round(size * 0.14));
            ctx.restore();
        }
    };

    function renderDonutChart(doughnut) {
        var canvas = root.querySelector('[data-tv-donut]');
        var emptyEl = root.querySelector('[data-tv-donut-empty]');
        var title = root.querySelector('[data-tv-donut-title]');
        if (!canvas || !window.Chart) return;

        doughnut = doughnut || { slices: [], center_value: 0, center_label: 'مخاطب', heading: 'توزیع مخاطبین' };
        var slices = (doughnut.slices || []).filter(function (sl) {
            return sl.value > 0 && sl.label !== 'بدون مخاطب';
        });
        var total = slices.reduce(function (sum, sl) { return sum + sl.value; }, 0);
        var isEmpty = !total;

        if (title) title.textContent = doughnut.heading || doughnut.title || 'توزیع مخاطبین';
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
                cutout: '70%',
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
                '<button type="button" class="lcc-chip' + (hidden ? ' is-off' : '') + '" ' +
                'data-series-idx="' + idx + '" data-series-key="' + esc(s.key) + '" ' +
                'style="--cc:' + s.color + '" aria-pressed="' + (!hidden) + '">' +
                '<i></i><span>' + esc(s.label) + '</span>' +
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

    function renderTrendKpis(chart) {
        var el = root.querySelector('[data-tv-trend-kpis]');
        if (!el) return;
        var summary = chart.summary || [];
        if (!summary.length) {
            el.innerHTML = '';
            return;
        }

        el.innerHTML = summary.map(function (s) {
            return (
                '<div class="lcc-sum" style="--sc:' + s.color + '">' +
                '<span class="lcc-sum__lbl">' + esc(s.label) + '</span>' +
                '<span class="lcc-sum__val">' + toFa(s.total || 0) + '</span>' +
                '</div>'
            );
        }).join('');
    }

    function renderTrendChart(chart) {
        var canvas = root.querySelector('[data-tv-chart]');
        var emptyEl = root.querySelector('[data-tv-chart-empty]');
        if (!canvas || !window.Chart) return;

        var points = chart.points || [];
        var series = chart.series || [
            { key: 'calls', color: '#38bdf8', label: 'تماس' },
            { key: 'visits', color: '#f59e0b', label: 'بازدید' },
            { key: 'followups', color: '#22c55e', label: 'پیگیری' },
            { key: 'leads', color: '#7c3aed', label: 'لید' }
        ];
        var activityTotal = chart.activity_total || 0;
        var allVals = [];
        points.forEach(function (p) {
            series.forEach(function (s) { allVals.push(p[s.key] || 0); });
        });
        var suggestedMax = Math.ceil(softChartMax(allVals));
        var isEmpty = !activityTotal || !points.length;

        bindTrendLegend(series);
        renderTrendKpis(chart);

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
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: s.color,
                pointBorderColor: '#0b0f1a',
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
                        grid: { color: CHART_THEME.grid, drawTicks: false },
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
                '<div class="lcc-empty lcc-empty--inline">' +
                '<i class="fas fa-users"></i><p>مخاطبی ثبت نشده</p></div>';
            return;
        }

        legend.innerHTML = slices.map(function (sl) {
            return (
                '<div class="lcc-leg" style="--c:' + sl.color + '">' +
                '<span class="lcc-leg__dot"></span>' +
                '<span class="lcc-leg__lbl">' + esc(sl.label) + '</span>' +
                '<span class="lcc-leg__val"><small>(' + toFa(sl.pct || 0) + '%)</small>' + toFa(sl.value || 0) + '</span>' +
                '</div>'
            );
        }).join('');
    }

    function renderChart(data) {
        var chart = data.chart || {};
        renderTrendChart(chart);
        renderDonutChart(chart.doughnut);
        renderChartLegend(chart);
    }

    function goalStatusClass(g) {
        if (g.completed) return ' lcc-goal__bar--done';
        if (g.status === 'warn') return ' lcc-goal__bar--warn';
        if (g.status === 'low') return ' lcc-goal__bar--low';
        return '';
    }

    function renderGoals(data) {
        var el = root.querySelector('[data-tv-goals]');
        if (!el) return;
        var goals = (data.goals || []).slice(0, 3);
        if (!goals.length) {
            if (!el.querySelector('.lcc-empty--inline')) {
                el.innerHTML =
                    '<div class="lcc-empty lcc-empty--inline">' +
                    '<i class="fas fa-bullseye"></i><p>هدفی ثبت نشده</p></div>';
            }
            return;
        }
        var empty = el.querySelector('.lcc-empty--inline');
        if (empty) empty.remove();

        var minDays = null;
        goals.forEach(function (g) {
            if (!g.completed && g.days_left != null) {
                minDays = minDays == null ? g.days_left : Math.min(minDays, g.days_left);
            }
            var node = el.querySelector('[data-goal="' + g.goal_key + '"]');
            if (!node) {
                node = document.createElement('div');
                node.className = 'lcc-goal';
                node.setAttribute('data-goal', g.goal_key);
                node.innerHTML =
                    '<div class="lcc-goal__top">' +
                    '<span class="lcc-goal__title"></span>' +
                    '<span class="lcc-goal__nums"><span data-act></span><b data-pct></b></span>' +
                    '</div>' +
                    '<div class="lcc-goal__bar"><span></span></div>';
                el.appendChild(node);
            }
            node.classList.toggle('lcc-goal--done', !!g.completed);
            node.querySelector('.lcc-goal__title').textContent = g.title;
            var bar = node.querySelector('.lcc-goal__bar');
            bar.className = 'lcc-goal__bar' + goalStatusClass(g);
            bar.querySelector('span').style.width = g.pct + '%';
            node.querySelector('[data-act]').textContent = toFa(g.actual) + ' / ' + toFa(g.target);
            node.querySelector('[data-pct]').textContent = toFa(g.pct) + '%';
        });

        var foot = el.querySelector('[data-tv-goals-foot]');
        if (minDays != null) {
            if (!foot) {
                foot = document.createElement('p');
                foot.className = 'lcc-goals__foot';
                foot.setAttribute('data-tv-goals-foot', '');
                el.appendChild(foot);
            }
            foot.textContent = toFa(minDays) + ' روز تا پایان ماه';
            foot.hidden = false;
        } else if (foot) {
            foot.hidden = true;
        }
    }

    function activityTone(key) {
        if (!key) return 'sys';
        if (key.indexOf('visit') === 0) return 'visit';
        if (key.indexOf('deal') === 0) return 'deal';
        if (key.indexOf('audit') === 0) return 'lead';
        return 'sys';
    }

    function activityIcon(key) {
        if (key.indexOf('visit') === 0) return 'fa-door-open';
        if (key.indexOf('deal') === 0) return 'fa-handshake';
        if (key.indexOf('audit') === 0) return 'fa-user-plus';
        return 'fa-bolt';
    }

    function renderActivity(data) {
        var list = root.querySelector('[data-tv-activity]');
        if (!list) return;
        var items = (data.activity || []).slice(0, 6);
        if (!items.length) {
            if (!list.querySelector('.lcc-empty--inline')) {
                list.innerHTML =
                    '<li class="lcc-empty lcc-empty--inline">' +
                    '<i class="fas fa-bolt"></i><p>رویدادی نیست</p></li>';
            }
            return;
        }
        var empty = list.querySelector('.lcc-empty--inline');
        if (empty) empty.remove();

        items.forEach(function (a) {
            var li = list.querySelector('[data-act-key="' + a.key + '"]');
            var tone = activityTone(a.key);
            if (!li) {
                li = document.createElement('li');
                li.className = 'lcc-feed__item';
                li.setAttribute('data-act-key', a.key);
                li.innerHTML =
                    '<span class="lcc-feed__text" data-txt></span>' +
                    '<span class="lcc-feed__time" data-time></span>' +
                    '<span class="lcc-feed__ico"><i class="fas"></i></span>';
                list.appendChild(li);
            }
            var ico = li.querySelector('.lcc-feed__ico');
            ico.className = 'lcc-feed__ico lcc-feed__ico--' + tone;
            ico.querySelector('i').className = 'fas ' + activityIcon(a.key);
            li.querySelector('[data-txt]').textContent = a.text;
            li.querySelector('[data-time]').textContent = relativeTimeFromClock(a.time) || a.time || '';
        });

        list.querySelectorAll('[data-act-key]').forEach(function (li) {
            var k = li.getAttribute('data-act-key');
            if (!items.some(function (a) { return a.key === k; })) li.remove();
        });
    }

    function scheduleStatusClass(status) {
        return 'lcc-today__status lcc-today__status--' + (status || 'pending');
    }

    function renderSchedule(data) {
        var el = root.querySelector('[data-tv-schedule]');
        if (!el) return;
        var s = data.schedule || {};
        var items = s.items || [];

        if (!items.length) {
            var hint = s.next_hint || '';
            if (hint) {
                el.innerHTML =
                    '<div class="lcc-today">' +
                    '<div class="lcc-today__row">' +
                    '<span class="lcc-today__time">--:--</span>' +
                    '<span class="lcc-today__title">' + esc(hint) + '</span>' +
                    '<span class="lcc-today__status lcc-today__status--pending"></span>' +
                    '</div></div>';
            } else {
                el.innerHTML =
                    '<div class="lcc-empty lcc-empty--inline">' +
                    '<i class="fas fa-calendar-day"></i><p>برنامه‌ای برای امروز ثبت نشده</p></div>';
            }
            return;
        }

        var html = '<div class="lcc-today">';
        items.forEach(function (item) {
            html +=
                '<div class="lcc-today__row" data-sched="' + esc(item.key) + '">' +
                '<span class="lcc-today__time">' + esc(item.time || '--:--') + '</span>' +
                '<span class="lcc-today__title">' + esc(item.summary || '') + '</span>' +
                '<span class="' + scheduleStatusClass(item.status) + '"></span>' +
                '</div>';
        });
        html += '</div>';
        if (el.innerHTML !== html) el.innerHTML = html;
    }

    function renderAnnouncements(data) {
        var el = root.querySelector('[data-tv-announcements]');
        if (!el) return;
        var items = (data.announcements || []).slice(0, 4);
        if (!items.length) {
            el.innerHTML =
                '<div class="lcc-empty lcc-empty--inline">' +
                '<i class="fas fa-bullhorn"></i><p>اعلانی ثبت نشده</p></div>';
            return;
        }

        el.innerHTML = items.map(function (a) {
            var cls = 'lcc-ann__item';
            var badge = '';
            if (a.importance === 'urgent') {
                cls += ' lcc-ann__item--urgent';
                badge = '<span class="lcc-ann__badge">مهم</span>';
            } else if (a.importance === 'high') {
                cls += ' lcc-ann__item--high';
                badge = '<span class="lcc-ann__badge lcc-ann__badge--high">اولویت بالا</span>';
            }
            var pin = a.is_pinned ? '<i class="fas fa-thumbtack" style="opacity:0.6;font-size:0.65em"></i> ' : '';
            return (
                '<article class="' + cls + '" data-ann="' + esc(a.ann_key) + '">' +
                '<div class="lcc-ann__head">' + badge +
                '<span class="lcc-ann__time">' + esc(formatAnnTime(a.published_at)) + '</span></div>' +
                '<div class="lcc-ann__title">' + pin + esc(a.title) + '</div>' +
                (a.preview ? '<div class="lcc-ann__preview">' + esc(a.preview) + '</div>' : '') +
                '</article>'
            );
        }).join('');
    }

    function renderAlerts(data) {
        var strip = root.querySelector('[data-tv-alerts-strip]');
        if (!strip) return;
        var alerts = data.alerts || [];
        if (!alerts.length) { strip.hidden = true; strip.innerHTML = ''; return; }
        strip.hidden = false;
        strip.innerHTML = alerts.map(function (a) {
            return '<span class="lcc-alert lcc-alert--' + esc(a.level) + '">' + esc(a.text) + '</span>';
        }).join('');
    }

    function renderTicker(data) {
        var track = root.querySelector('[data-tv-ticker-track]');
        if (!track) return;
        var items = data.announcements || [];
        var deals = data.recent_deals || {};
        var extras = [];
        if (deals.closed_today_count) {
            extras.push('امروز ' + toFa(deals.closed_today_count) + ' قرارداد بسته شد');
        }
        if (!items.length && !extras.length) {
            track.className = 'lcc-ticker__track lcc-ticker__track--static';
            track.textContent = 'اطلاعیه فعالی نیست';
            return;
        }
        var parts = items.map(function (a) {
            var pin = a.is_pinned ? '📌 ' : '';
            var imp = a.importance === 'urgent' ? '⚠ ' : (a.importance === 'high' ? '● ' : '');
            return pin + imp + a.title + (a.preview ? ' — ' + a.preview : '');
        }).concat(extras);
        var text = '🏆  ' + parts.join('    •    ');
        track.className = 'lcc-ticker__track' + (parts.length < 2 ? ' lcc-ticker__track--static' : '');
        if (parts.length >= 2) text = text + '    •    ' + text;
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
                img.setAttribute('data-tv-agency-logo', '');
                img.width = 44;
                img.height = 44;
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
        renderAnnouncements(data);
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

        var theme = root.querySelector('[data-tv-theme]');
        if (theme) theme.addEventListener('click', function () {
            root.classList.toggle('lcc--bright');
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
            root.classList.remove('lcc--fs-hide');
            clearTimeout(hideTimer);
            if (document.fullscreenElement) {
                hideTimer = setTimeout(function () { root.classList.add('lcc--fs-hide'); }, 4000);
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'F11') {
                e.preventDefault();
                toggleFullscreen();
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
