/**
 * TV Command Center — incremental render + polling
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

    var state = {
        lastData: null,
        lastPayloadVersion: null,
        pollTimer: null,
        backoffMs: 0,
        inflight: null,
        tickerIdx: 0
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

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
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
        return Math.max(ref * 1.35, top * 0.6, 1);
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
            ['new_leads_today', 'سرنخ جدید', 'ok'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'danger'],
            ['calls_today', 'تماس امروز', 'ok'],
            ['visits_today', 'بازدید امروز', 'ok'],
            ['deals_won_today', 'قرارداد موفق', 'ok'],
            ['commission_month', 'کمیسیون ماه', 'ok']
        ],
        secretary: [
            ['new_leads_today', 'سرنخ جدید', 'ok'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'danger'],
            ['calls_today', 'تماس', 'ok'],
            ['visits_today', 'بازدید', 'ok'],
            ['deals_won_today', 'قرارداد', 'ok'],
            ['inbox_unassigned', 'بدون تخصیص', 'warn']
        ],
        advisor: [
            ['calls_today', 'تماس من', 'ok'],
            ['visits_today', 'بازدید من', 'ok'],
            ['deals_won_today', 'قرارداد', 'ok'],
            ['active_deals', 'فعال', 'ok'],
            ['my_score', 'امتیاز', 'ok'],
            ['my_rank', 'رتبه', 'ok']
        ]
    };

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
                card.innerHTML = '<span class="tv-cmd__kpi-val" data-val>۰</span><span class="tv-cmd__kpi-lbl"></span><span class="tv-cmd__kpi-delta" data-delta></span>';
                row.appendChild(card);
            }
            card.classList.toggle('tv-cmd__kpi--optional', idx === defs.length - 1);
            card.querySelector('.tv-cmd__kpi-lbl').textContent = def[1];
            var k = kpis[key] || { value: 0, delta: null, status: def[2] };
            var valEl = card.querySelector('[data-val]');
            var v = toFa(k.value);
            if (key === 'commission_month' && k.value >= 1000000) {
                v = toFa(Math.round(k.value / 1000000)) + 'M';
            }
            if (valEl.textContent !== v) valEl.textContent = v;
            card.classList.toggle('tv-cmd__kpi--warn', k.status === 'warn');
            card.classList.toggle('tv-cmd__kpi--danger', k.status === 'danger');
            var dEl = card.querySelector('[data-delta]');
            if (k.delta != null) {
                var up = k.delta >= 0;
                dEl.className = 'tv-cmd__kpi-delta tv-cmd__kpi-delta--' + (up ? 'up' : 'down');
                dEl.textContent = (up ? '↑ ' : '↓ ') + toFa(Math.abs(k.delta)) + '% دیروز';
            } else {
                dEl.textContent = '';
                dEl.className = 'tv-cmd__kpi-delta';
            }
        });
    }

    function renderLeaderboard(data) {
        var list = root.querySelector('[data-tv-leaderboard]');
        if (!list) return;
        var rows = (data.leaderboard || []).slice(0, maxLeaderboardRows());
        if (!rows.length) {
            if (!list.querySelector('.tv-cmd__empty')) {
                list.innerHTML = '<li class="tv-cmd__empty">هنوز فعالیتی ثبت نشده</li>';
            }
            return;
        }
        var empty = list.querySelector('.tv-cmd__empty');
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
                    '<div><div class="tv-cmd__board-name"></div><div class="tv-cmd__board-role"></div></div>' +
                    '<span class="tv-cmd__board-score"></span>' +
                    '<div class="tv-cmd__board-bar"><i></i></div>';
                list.appendChild(li);
            }
            li.classList.toggle('tv-cmd__board-row--top', r.rank === 1);
            li.querySelector('.tv-cmd__board-rank').textContent = toFa(r.rank);
            li.querySelector('.tv-cmd__board-name').textContent = r.name;
            li.querySelector('.tv-cmd__board-role').textContent = r.role;
            li.querySelector('.tv-cmd__board-score').textContent = toFa(r.score);
            li.querySelector('.tv-cmd__board-bar i').style.width = (r.score_pct || 0) + '%';
        });
        list.querySelectorAll('[data-rank]').forEach(function (li) {
            var rank = li.getAttribute('data-rank');
            if (!rows.some(function (r) { return String(r.rank) === rank; })) li.remove();
        });
    }

    function polar(cx, cy, r, angle) {
        return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
    }

    function donutPath(cx, cy, rOut, rIn, start, end) {
        var large = end - start > Math.PI ? 1 : 0;
        var p1 = polar(cx, cy, rOut, start);
        var p2 = polar(cx, cy, rOut, end);
        var p3 = polar(cx, cy, rIn, end);
        var p4 = polar(cx, cy, rIn, start);
        return [
            'M', p1[0].toFixed(2), p1[1].toFixed(2),
            'A', rOut, rOut, 0, large, 1, p2[0].toFixed(2), p2[1].toFixed(2),
            'L', p3[0].toFixed(2), p3[1].toFixed(2),
            'A', rIn, rIn, 0, large, 0, p4[0].toFixed(2), p4[1].toFixed(2),
            'Z'
        ].join(' ');
    }

    function renderDonut(doughnut) {
        var svg = root.querySelector('[data-tv-donut]');
        var center = root.querySelector('[data-tv-donut-center]');
        var title = root.querySelector('[data-tv-donut-title]');
        if (!svg) return;
        doughnut = doughnut || { slices: [], center_value: 0, center_label: 'مخاطب', title: 'پرونده مخاطبین' };

        var slices = (doughnut.slices || []).filter(function (sl) { return sl.value > 0; });
        var total = slices.reduce(function (sum, sl) { return sum + sl.value; }, 0);
        var gap = 0.035;
        var cx = 50;
        var cy = 50;
        var rOut = 44;
        var rIn = 28;
        var start = -Math.PI / 2;
        var parts = [
            '<defs>',
            '<filter id="tvDonutShadow" x="-25%" y="-25%" width="150%" height="150%">',
            '<feDropShadow dx="0" dy="1.2" stdDeviation="1.4" flood-color="#000" flood-opacity="0.35"/>',
            '</filter>',
            '</defs>'
        ];

        if (!total) {
            parts.push('<circle cx="50" cy="50" r="36" fill="none" stroke="#334155" stroke-width="14" opacity="0.55"/>');
        } else {
            slices.forEach(function (sl) {
                var sweep = (sl.value / total) * Math.PI * 2;
                var end = start + sweep - gap;
                if (end > start) {
                    parts.push(
                        '<path d="' + donutPath(cx, cy, rOut, rIn, start, end) + '" fill="' + sl.color + '" filter="url(#tvDonutShadow)"/>'
                    );
                }
                start += sweep;
            });
        }
        svg.innerHTML = parts.join('');

        if (center) {
            center.innerHTML =
                '<span class="tv-cmd__chart-donut-val">' + toFa(doughnut.center_value || 0) + '</span>' +
                '<span class="tv-cmd__chart-donut-lbl">' + esc(doughnut.center_label || 'مخاطب') + '</span>';
        }
        if (title) title.textContent = doughnut.title || 'پرونده مخاطبین';
    }

    function renderTrend(chart) {
        var svg = root.querySelector('[data-tv-chart]');
        var daysEl = root.querySelector('[data-tv-chart-days]');
        if (!svg) return;

        var points = chart.points || [];
        var series = chart.series || [
            { key: 'calls', color: '#7c3aed', label: 'تماس' },
            { key: 'visits', color: '#06b6d4', label: 'بازدید' },
            { key: 'leads', color: '#f59e0b', label: 'لید' },
            { key: 'deals', color: '#22c55e', label: 'قرارداد' }
        ];

        if (!points.length) {
            svg.innerHTML = '';
            if (daysEl) daysEl.innerHTML = '';
            return;
        }

        var w = 400;
        var h = 100;
        var padL = 8;
        var padR = 8;
        var padT = 6;
        var padB = 2;
        var chartW = w - padL - padR;
        var chartH = h - padT - padB;
        var allVals = [];
        points.forEach(function (p) {
            series.forEach(function (s) { allVals.push(p[s.key] || 0); });
        });
        var max = softChartMax(allVals);

        function xAt(i) {
            return padL + (i / Math.max(points.length - 1, 1)) * chartW;
        }
        function yAt(v) {
            return padT + chartH - (v / max) * chartH;
        }

        var grid = [0.25, 0.5, 0.75, 1].map(function (frac) {
            var y = padT + chartH * (1 - frac);
            return '<line x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (w - padR) + '" y2="' + y.toFixed(1) + '" class="tv-chart-grid"/>';
        }).join('');

        var areas = series.map(function (s) {
            var top = points.map(function (p, i) {
                return xAt(i).toFixed(1) + ',' + yAt(p[s.key] || 0).toFixed(1);
            }).join(' L');
            var baseline = (padT + chartH).toFixed(1);
            var d = 'M' + xAt(0).toFixed(1) + ',' + baseline + ' L' + top + ' L' + xAt(points.length - 1).toFixed(1) + ',' + baseline + ' Z';
            return '<path d="' + d + '" fill="' + s.color + '" class="tv-chart-area"/>';
        }).join('');

        var lines = series.map(function (s) {
            var coords = points.map(function (p, i) {
                return xAt(i).toFixed(1) + ',' + yAt(p[s.key] || 0).toFixed(1);
            }).join(' ');
            return '<polyline fill="none" stroke="' + s.color + '" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="' + coords + '"/>';
        }).join('');

        var dots = series.map(function (s) {
            return points.map(function (p, i) {
                var v = p[s.key] || 0;
                if (!v) return '';
                return '<circle cx="' + xAt(i).toFixed(1) + '" cy="' + yAt(v).toFixed(1) + '" r="2.6" fill="' + s.color + '" stroke="rgba(15,23,42,0.85)" stroke-width="1"/>';
            }).join('');
        }).join('');

        svg.innerHTML = '<g class="tv-chart-grid-group">' + grid + '</g>' + areas + lines + dots;

        if (daysEl) {
            daysEl.innerHTML = points.map(function (p) {
                return '<span>' + esc(p.label) + '</span>';
            }).join('');
        }
    }

    function renderChartLegend(chart) {
        var legend = root.querySelector('[data-tv-chart-legend]');
        if (!legend) return;

        var doughnut = chart.doughnut || {};
        var slices = doughnut.slices || [];
        var series = chart.series || [];
        var donutHtml = slices.map(function (sl) {
            var val = toFa(sl.value || 0);
            var pct = toFa(sl.pct || 0);
            return (
                '<span class="tv-cmd__legend-item tv-cmd__legend-item--donut" style="--c:' + sl.color + '">' +
                '<em>' + esc(sl.label) + '</em>' +
                '<b>' + val + '</b>' +
                '<i>' + pct + '%</i>' +
                '</span>'
            );
        }).join('');

        var trendHtml = series.map(function (s) {
            var share = s.share_pct != null ? '<i>' + toFa(s.share_pct) + '%</i>' : '';
            return (
                '<span class="tv-cmd__legend-item tv-cmd__legend-item--trend" style="--c:' + s.color + '">' +
                '<em>' + esc(s.label) + '</em>' +
                '<b>' + toFa(s.total || 0) + '</b>' +
                share +
                '</span>'
            );
        }).join('');

        legend.innerHTML =
            '<div class="tv-cmd__legend-block tv-cmd__legend-block--donut">' + donutHtml + '</div>' +
            '<div class="tv-cmd__legend-block tv-cmd__legend-block--trend">' + trendHtml + '</div>';
    }

    function renderChart(data) {
        var chart = data.chart || {};
        renderDonut(chart.doughnut);
        renderTrend(chart);
        renderChartLegend(chart);

        var sub = root.querySelector('[data-tv-chart-subtitle]');
        if (sub) {
            var total = chart.activity_total || 0;
            sub.textContent = total
                ? toFa(total) + ' فعالیت در ۷ روز · توزیع مخاطبین'
                : 'توزیع مخاطبین · روند ۷ روزه';
        }
    }

    function renderGoals(data) {
        var el = root.querySelector('[data-tv-goals]');
        if (!el) return;
        var goals = (data.goals || []).slice(0, 4);
        if (!goals.length) {
            if (!el.querySelector('.tv-cmd__empty')) el.innerHTML = '<p class="tv-cmd__empty">هدفی ثبت نشده</p>';
            return;
        }
        var empty = el.querySelector('.tv-cmd__empty');
        if (empty) empty.remove();

        goals.forEach(function (g) {
            var node = el.querySelector('[data-goal="' + g.goal_key + '"]');
            if (!node) {
                node = document.createElement('div');
                node.className = 'tv-cmd__goal';
                node.setAttribute('data-goal', g.goal_key);
                node.innerHTML =
                    '<div class="tv-cmd__goal-title"></div>' +
                    '<div class="tv-cmd__goal-bar"><i></i></div>' +
                    '<div class="tv-cmd__goal-foot"><span data-act></span><span data-pct></span></div>';
                el.appendChild(node);
            }
            node.querySelector('.tv-cmd__goal-title').textContent = g.title;
            var bar = node.querySelector('.tv-cmd__goal-bar');
            bar.className = 'tv-cmd__goal-bar' + (g.completed ? '' : (g.status === 'warn' ? ' tv-cmd__goal-bar--warn' : (g.status === 'low' ? ' tv-cmd__goal-bar--low' : '')));
            bar.querySelector('i').style.width = g.pct + '%';
            var act = g.completed ? toFa(g.actual) + ' از ' + toFa(g.target) + ' ✓' : toFa(g.actual) + ' از ' + toFa(g.target);
            node.querySelector('[data-act]').textContent = act;
            var foot = g.completed ? 'تکمیل‌شده' : (g.days_left ? toFa(g.days_left) + ' روز مانده' : toFa(g.pct) + '%');
            node.querySelector('[data-pct]').textContent = foot;
        });
    }

    function renderActivity(data) {
        var list = root.querySelector('[data-tv-activity]');
        if (!list) return;
        var items = (data.activity || []).slice(0, 5);
        if (!items.length) {
            if (!list.querySelector('.tv-cmd__empty')) list.innerHTML = '<li class="tv-cmd__empty">رویدادی نیست</li>';
            return;
        }
        var empty = list.querySelector('.tv-cmd__empty');
        if (empty) empty.remove();

        items.forEach(function (a) {
            var li = list.querySelector('[data-act-key="' + a.key + '"]');
            if (!li) {
                li = document.createElement('li');
                li.setAttribute('data-act-key', a.key);
                li.innerHTML = '<span data-txt></span><span data-time></span>';
                list.appendChild(li);
            }
            li.querySelector('[data-txt]').textContent = a.text;
            li.querySelector('[data-time]').textContent = a.time || '';
        });
    }

    function renderSchedule(data) {
        var el = root.querySelector('[data-tv-schedule]');
        if (!el) return;
        var s = data.schedule || {};
        var html =
            '<div class="tv-cmd__sched-grid">' +
            '<div class="tv-cmd__sched-item"><em>' + toFa(s.visits_today || 0) + '</em><span>بازدید</span></div>' +
            '<div class="tv-cmd__sched-item"><em>' + toFa(s.followups_today || 0) + '</em><span>پیگیری</span></div>' +
            '<div class="tv-cmd__sched-item"><em>' + toFa(s.overdue_followups || 0) + '</em><span>معوق</span></div>' +
            '<div class="tv-cmd__sched-item"><em>' + toFa(s.inbox_unassigned || 0) + '</em><span>صندوق</span></div>' +
            '<p class="tv-cmd__sched-hint">' + esc(s.next_hint || '') + '</p></div>';
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

    function renderAll(data, force) {
        if (!data || !data.ok) return;
        if (!force && data.payload_version && data.payload_version === state.lastPayloadVersion) {
            renderMeta(data);
            setStatus('live', 'به‌روز · ' + (data.clock || ''));
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
        setStatus('live', 'به‌روز · ' + (data.clock || ''));
    }

    function tickClock() {
        var now = new Date();
        var t = toFa(String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0'));
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
                setStatus('offline', state.lastData ? 'قطع · ' + (state.lastData.clock || '') : 'خطا در اتصال');
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
        var overlay = root.querySelector('[data-tv-fs-overlay]');
        var dismissed = false;
        try { dismissed = !!sessionStorage.getItem('crm-tv-fs-dismissed'); } catch (e) { /* ignore */ }
        if (overlay && !document.fullscreenElement && !dismissed) overlay.hidden = false;
        window.addEventListener('resize', function () {
            if (state.lastData) {
                renderLeaderboard(state.lastData);
            }
        });
        fetchData().finally(scheduleNext);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
