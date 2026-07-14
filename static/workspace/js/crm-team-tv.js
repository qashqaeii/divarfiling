/**
 * CRM Agency TV Mode — hardened polling + incremental render.
 */
(function () {
    'use strict';

    var root = document.getElementById('crm-tv-app');
    if (!root) return;

    var cfg = window.crmTeamTV || {};
    var STORAGE_KEY = 'crm-tv-settings-v2';
    var SETTINGS_SCHEMA = 2;

    var state = {
        lastData: null,
        lastPayloadVersion: null,
        pollTimer: null,
        backoffMs: 0,
        inflight: null,
        connection: 'loading'
    };

    function readInitial() {
        var el = document.getElementById('crm-tv-initial');
        if (!el || !el.textContent) return null;
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return null;
        }
    }

    function toFaDigits(str) {
        var map = { '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹' };
        return String(str).replace(/[0-9]/g, function (d) { return map[d] || d; });
    }

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    function loadSettings() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return { schema: SETTINGS_SCHEMA, theme: null, widgets: null };
            var parsed = JSON.parse(raw);
            if (parsed.schema !== SETTINGS_SCHEMA) {
                return { schema: SETTINGS_SCHEMA, theme: parsed.theme || null, widgets: null };
            }
            return parsed;
        } catch (e) {
            return { schema: SETTINGS_SCHEMA, theme: null, widgets: null };
        }
    }

    function saveSettings(patch) {
        var cur = loadSettings();
        var next = Object.assign({}, cur, patch, { schema: SETTINGS_SCHEMA });
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch (e) { /* ignore */ }
    }

    function allowedWidgets(data) {
        return (data && data.allowed_widgets) || [];
    }

    function applyWidgetVisibility(data) {
        var allowed = allowedWidgets(data);
        var settings = loadSettings();
        var selected = settings.widgets;
        if (!selected || !selected.length) selected = allowed.slice();

        selected = selected.filter(function (w) { return allowed.indexOf(w) !== -1; });

        root.querySelectorAll('[data-widget]').forEach(function (panel) {
            var w = panel.getAttribute('data-widget');
            var show = selected.indexOf(w) !== -1 && allowed.indexOf(w) !== -1;
            panel.hidden = !show;
        });

        var form = root.querySelector('[data-tv-widget-form]');
        if (form) {
            form.querySelectorAll('input[name="widget"]').forEach(function (inp) {
                var val = inp.value;
                var isAllowed = allowed.indexOf(val) !== -1;
                inp.disabled = !isAllowed;
                inp.closest('.crm-tv-widget-check').hidden = !isAllowed;
                inp.checked = isAllowed && selected.indexOf(val) !== -1;
            });
        }
    }

    function setConnection(status, message) {
        state.connection = status;
        var sync = root.querySelector('[data-tv-sync]');
        var updated = root.querySelector('[data-tv-updated]');
        if (sync) {
            sync.classList.toggle('is-loading', status === 'loading');
            sync.classList.toggle('is-offline', status === 'offline');
            sync.classList.toggle('is-live', status === 'live');
        }
        if (updated && message) updated.textContent = message;
    }

    function deltaHtml(delta) {
        if (delta == null) return '';
        var cls = delta >= 0 ? 'crm-tv-kpi-delta--up' : 'crm-tv-kpi-delta--down';
        var icon = delta >= 0 ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down';
        return '<span class="crm-tv-kpi-delta ' + cls + '"><i class="fas ' + icon + '"></i> ' +
            toFaDigits(Math.abs(delta)) + '%</span>';
    }

    var KPI_DEFS = {
        manager: [
            ['new_leads_today', 'سرنخ جدید امروز', 'crm-tv-kpi--contacts'],
            ['calls_today', 'تماس امروز', 'crm-tv-kpi--calls'],
            ['visits_today', 'بازدید امروز', 'crm-tv-kpi--visits'],
            ['deals_won_today', 'قرارداد بسته امروز', 'crm-tv-kpi--deals'],
            ['active_deals', 'معامله فعال', 'crm-tv-kpi--active'],
            ['inbox_unassigned', 'سرنخ بدون تخصیص', 'crm-tv-kpi--inbox'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'crm-tv-kpi--overdue'],
            ['commission_month', 'کمیسیون این ماه', 'crm-tv-kpi--commission']
        ],
        secretary: [
            ['new_leads_today', 'سرنخ جدید امروز', 'crm-tv-kpi--contacts'],
            ['calls_today', 'تماس امروز', 'crm-tv-kpi--calls'],
            ['visits_today', 'بازدید امروز', 'crm-tv-kpi--visits'],
            ['deals_won_today', 'قرارداد بسته امروز', 'crm-tv-kpi--deals'],
            ['active_deals', 'معامله فعال', 'crm-tv-kpi--active'],
            ['inbox_unassigned', 'سرنخ بدون تخصیص', 'crm-tv-kpi--inbox'],
            ['overdue_followups', 'پیگیری عقب‌افتاده', 'crm-tv-kpi--overdue'],
            ['stale_leads', 'سرنخ کهنه', 'crm-tv-kpi--inbox']
        ],
        advisor: [
            ['calls_today', 'تماس امروز', 'crm-tv-kpi--calls'],
            ['visits_today', 'بازدید امروز', 'crm-tv-kpi--visits'],
            ['deals_won_today', 'قرارداد بسته', 'crm-tv-kpi--deals'],
            ['active_deals', 'معامله فعال', 'crm-tv-kpi--active'],
            ['my_score', 'امتیاز من', 'crm-tv-kpi--active'],
            ['my_rank', 'رتبه من', 'crm-tv-kpi--contacts']
        ]
    };

    function ensureKpiCards(el, defs) {
        var existing = {};
        el.querySelectorAll('[data-kpi-key]').forEach(function (node) {
            existing[node.getAttribute('data-kpi-key')] = node;
        });
        defs.forEach(function (def, i) {
            var key = def[0];
            if (!existing[key]) {
                var art = document.createElement('article');
                art.className = 'crm-tv-kpi ' + def[2];
                art.setAttribute('data-kpi-key', key);
                art.innerHTML =
                    '<span class="crm-tv-kpi-val" data-kpi-val>۰</span>' +
                    '<span class="crm-tv-kpi-lbl">' + esc(def[1]) + '</span>' +
                    '<span data-kpi-delta></span>';
                if (i === 0) art.classList.add('crm-tv-kpi--animate');
                el.appendChild(art);
            }
        });
        el.querySelectorAll('[data-kpi-key]').forEach(function (node) {
            var key = node.getAttribute('data-kpi-key');
            var found = defs.some(function (d) { return d[0] === key; });
            node.hidden = !found;
        });
    }

    function renderKpis(data) {
        var el = root.querySelector('[data-tv-kpis]');
        if (!el) return;
        var kpis = data.kpis || {};
        var role = data.role || 'advisor';
        var defs = KPI_DEFS[role] || KPI_DEFS.advisor;
        ensureKpiCards(el, defs);

        defs.forEach(function (def) {
            var key = def[0];
            var card = el.querySelector('[data-kpi-key="' + key + '"]');
            if (!card) return;
            var k = kpis[key] || { value: 0, delta: null, status: 'ok' };
            var valEl = card.querySelector('[data-kpi-val]');
            var deltaEl = card.querySelector('[data-kpi-delta]');
            if (valEl && valEl.textContent !== toFaDigits(k.value)) {
                valEl.textContent = toFaDigits(k.value);
            }
            if (deltaEl) {
                var html = deltaHtml(k.delta);
                if (deltaEl.innerHTML !== html) deltaEl.innerHTML = html;
            }
            card.classList.toggle('crm-tv-kpi--warn', k.status === 'warn');
            card.classList.toggle('crm-tv-kpi--danger', k.status === 'danger');
        });

        if (!defs.length) {
            el.innerHTML = '<p class="crm-tv-empty">فعالیتی برای امروز ثبت نشده</p>';
        }
    }

    function renderSpotlight(data) {
        var wrap = root.querySelector('[data-tv-spotlight]');
        var body = root.querySelector('[data-tv-spotlight-body]');
        if (!wrap || !body) return;
        var top = data.top;
        if (!top) {
            wrap.hidden = true;
            return;
        }
        wrap.hidden = false;
        var html =
            '<p class="crm-tv-spotlight-name">' + esc(top.name) + '</p>' +
            '<p class="crm-tv-spotlight-role">' + esc(top.role) + '</p>' +
            '<div class="crm-tv-spotlight-stats">' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.calls) + '</em> تماس</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.visits) + '</em> بازدید</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.deals_closed) + '</em> بسته‌شده</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.score_pct) + '%</em> امتیاز</div>' +
            '</div>';
        if (body.innerHTML !== html) body.innerHTML = html;
    }

    function renderLeaderboard(data) {
        var el = root.querySelector('[data-tv-leaderboard]');
        if (!el) return;
        var rows = data.leaderboard || [];
        if (!rows.length) {
            if (!el.querySelector('.crm-tv-empty')) {
                el.innerHTML = '<li class="crm-tv-empty"><i class="fas fa-users"></i> هنوز عضوی فعالیت ثبت نکرده</li>';
            }
            return;
        }

        var existing = {};
        el.querySelectorAll('[data-lb-rank]').forEach(function (node) {
            existing[node.getAttribute('data-lb-rank')] = node;
        });

        rows.forEach(function (r) {
            var key = String(r.rank);
            var row = existing[key];
            if (!row) {
                row = document.createElement('li');
                row.className = 'crm-tv-lb-row';
                row.setAttribute('data-lb-rank', key);
                row.innerHTML =
                    '<span class="crm-tv-lb-rank"></span>' +
                    '<div><div class="crm-tv-lb-name"></div><div class="crm-tv-lb-role"></div></div>' +
                    '<span class="crm-tv-lb-score"></span>' +
                    '<div class="crm-tv-lb-bar"><i></i></div>';
                el.appendChild(row);
            }
            var prevRank = row.getAttribute('data-prev-rank');
            if (prevRank && prevRank !== key) row.classList.add('crm-tv-lb-row--moved');
            else row.classList.remove('crm-tv-lb-row--moved');
            row.setAttribute('data-prev-rank', key);

            row.classList.toggle('crm-tv-lb-row--top', r.rank === 1);
            row.querySelector('.crm-tv-lb-rank').textContent = toFaDigits(r.rank);
            row.querySelector('.crm-tv-lb-name').textContent = r.name;
            row.querySelector('.crm-tv-lb-role').textContent = r.role;
            row.querySelector('.crm-tv-lb-score').textContent = toFaDigits(r.score);
            row.querySelector('.crm-tv-lb-bar i').style.width = (r.score_pct || 0) + '%';
        });

        el.querySelectorAll('[data-lb-rank]').forEach(function (node) {
            var rank = node.getAttribute('data-lb-rank');
            if (!rows.some(function (r) { return String(r.rank) === rank; })) node.remove();
        });
        var empty = el.querySelector('.crm-tv-empty');
        if (empty) empty.remove();
    }

    function renderGoals(data) {
        var el = root.querySelector('[data-tv-goals]');
        if (!el) return;
        var goals = data.goals || [];
        if (!goals.length) {
            if (!el.querySelector('.crm-tv-empty')) {
                el.innerHTML = '<p class="crm-tv-empty"><i class="fas fa-bullseye"></i> هدفی برای این دوره ثبت نشده</p>';
            }
            return;
        }
        var empty = el.querySelector('.crm-tv-empty');
        if (empty) empty.remove();

        goals.forEach(function (g) {
            var node = el.querySelector('[data-goal-key="' + g.goal_key + '"]');
            if (!node) {
                node = document.createElement('article');
                node.className = 'crm-tv-goal';
                node.setAttribute('data-goal-key', g.goal_key);
                node.innerHTML =
                    '<div class="crm-tv-goal-head"><strong></strong><span class="crm-tv-goal-metric"></span></div>' +
                    '<div class="crm-tv-goal-bar"><i></i></div>' +
                    '<div class="crm-tv-goal-foot"><span data-goal-actual></span><span data-goal-pct></span></div>';
                el.appendChild(node);
            }
            node.querySelector('strong').textContent = g.member_name;
            node.querySelector('.crm-tv-goal-metric').textContent = g.metric_label;
            var bar = node.querySelector('.crm-tv-goal-bar');
            bar.classList.toggle('crm-tv-goal-bar--warn', g.pct >= 40 && g.pct < 80);
            bar.classList.toggle('crm-tv-goal-bar--low', g.pct < 40);
            bar.querySelector('i').style.width = g.pct + '%';
            node.querySelector('[data-goal-actual]').textContent =
                toFaDigits(g.actual) + ' / ' + toFaDigits(g.target);
            node.querySelector('[data-goal-pct]').textContent = toFaDigits(g.pct) + '%';
        });
    }

    function renderAnnouncements(data) {
        var el = root.querySelector('[data-tv-announcements]');
        if (!el) return;
        var items = data.announcements || [];
        if (!items.length) {
            if (!el.querySelector('.crm-tv-empty')) {
                el.innerHTML = '<p class="crm-tv-empty"><i class="fas fa-bullhorn"></i> اطلاعیه فعالی نیست</p>';
            }
            return;
        }
        var empty = el.querySelector('.crm-tv-empty');
        if (empty) empty.remove();

        items.forEach(function (a) {
            var node = el.querySelector('[data-ann-key="' + a.ann_key + '"]');
            if (!node) {
                node = document.createElement('article');
                node.className = 'crm-tv-ann';
                node.setAttribute('data-ann-key', a.ann_key);
                node.innerHTML = '<p class="crm-tv-ann-title"></p><p class="crm-tv-ann-preview"></p>';
                el.appendChild(node);
            }
            var imp = a.importance === 'urgent' ? 'urgent' : (a.importance === 'high' ? 'high' : 'normal');
            node.className = 'crm-tv-ann crm-tv-ann--' + imp;
            node.querySelector('.crm-tv-ann-title').innerHTML =
                (a.is_pinned ? '<i class="fas fa-thumbtack"></i> ' : '') + esc(a.title);
            node.querySelector('.crm-tv-ann-preview').textContent = a.preview || '';
        });
    }

    function renderLeads(data) {
        var el = root.querySelector('[data-tv-leads]');
        if (!el) return;
        var leads = data.leads || {};
        function setStat(key, val, warn) {
            var node = el.querySelector('[data-lead-key="' + key + '"]');
            if (!node) {
                node = document.createElement('div');
                node.className = 'crm-tv-lead-stat';
                node.setAttribute('data-lead-key', key);
                node.innerHTML = '<em></em><span></span>';
                el.appendChild(node);
            }
            node.classList.toggle('crm-tv-lead-stat--warn', !!warn);
            node.querySelector('em').textContent = toFaDigits(val);
        }
        setStat('unassigned', leads.unassigned || 0, (leads.unassigned || 0) > 0);
        setStat('new_today', leads.new_today || 0, false);
        setStat('stale', leads.stale || 0, (leads.stale || 0) > 0);
        var labels = { unassigned: 'بدون تخصیص', new_today: 'جدید امروز', stale: 'بیش از ۴۸ ساعت' };
        Object.keys(labels).forEach(function (k) {
            var node = el.querySelector('[data-lead-key="' + k + '"] span');
            if (node) node.textContent = labels[k];
        });
    }

    function renderDeals(data) {
        var el = root.querySelector('[data-tv-deals]');
        if (!el) return;
        var deals = data.deals || {};

        function renderCol(colKey, items, count, title) {
            var col = el.querySelector('[data-deal-col="' + colKey + '"]');
            if (!col) {
                col = document.createElement('div');
                col.className = 'crm-tv-deal-col';
                col.setAttribute('data-deal-col', colKey);
                col.innerHTML = '<h3></h3><ul class="crm-tv-deal-list"></ul>';
                el.appendChild(col);
            }
            col.querySelector('h3').textContent = title + ' (' + toFaDigits(count) + ')';
            var list = col.querySelector('.crm-tv-deal-list');
            if (!items || !items.length) {
                list.innerHTML = '<li class="crm-tv-deal-empty">موردی نیست</li>';
                return;
            }
            items.forEach(function (d) {
                var key = colKey + '-' + d.slot;
                var li = list.querySelector('[data-deal-key="' + key + '"]');
                if (!li) {
                    li = document.createElement('li');
                    li.className = 'crm-tv-deal-item';
                    li.setAttribute('data-deal-key', key);
                    li.innerHTML = '<strong></strong><span></span>';
                    list.appendChild(li);
                }
                li.querySelector('strong').textContent = d.summary;
                li.querySelector('span').textContent = d.stage + (d.advisor ? ' · ' + d.advisor : '');
            });
        }

        renderCol('active', deals.active, deals.active_count || 0, 'فعال');
        renderCol('closed', deals.closed_today, deals.closed_today_count || 0, 'بسته امروز');
    }

    function renderAlerts(data) {
        var el = root.querySelector('[data-tv-alerts]');
        if (!el) return;
        var alerts = data.alerts || [];
        if (!alerts.length) {
            if (!el.querySelector('.crm-tv-empty')) {
                el.innerHTML = '<p class="crm-tv-empty"><i class="fas fa-circle-check"></i> وضعیت عملیاتی عادی</p>';
            }
            return;
        }
        var empty = el.querySelector('.crm-tv-empty');
        if (empty) empty.remove();
        alerts.forEach(function (a, i) {
            var node = el.querySelector('[data-alert-idx="' + i + '"]');
            if (!node) {
                node = document.createElement('p');
                node.className = 'crm-tv-alert';
                node.setAttribute('data-alert-idx', String(i));
                el.appendChild(node);
            }
            node.className = 'crm-tv-alert crm-tv-alert--' + a.level;
            node.innerHTML = '<i class="fas fa-bell"></i> ' + esc(a.text);
        });
    }

    function renderMeta(data) {
        var dateEl = root.querySelector('[data-tv-date]');
        if (dateEl && data.jalali_date) dateEl.textContent = data.jalali_date;
        var agencyEl = root.querySelector('[data-tv-agency-name]');
        if (agencyEl && data.agency && data.agency.name) agencyEl.textContent = data.agency.name;
    }

    function renderAll(data, force) {
        if (!data || !data.ok) return;
        if (!force && data.payload_version && data.payload_version === state.lastPayloadVersion) {
            renderMeta(data);
            setConnection('live', 'به‌روز · ' + (data.clock || ''));
            return;
        }
        state.lastPayloadVersion = data.payload_version;
        state.lastData = data;
        applyWidgetVisibility(data);
        renderKpis(data);
        renderSpotlight(data);
        renderLeaderboard(data);
        renderGoals(data);
        renderAnnouncements(data);
        renderLeads(data);
        renderDeals(data);
        renderAlerts(data);
        renderMeta(data);
        setConnection('live', 'به‌روز · ' + (data.clock || ''));
    }

    function tickClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, '0');
        var m = String(now.getMinutes()).padStart(2, '0');
        var clockEl = root.querySelector('[data-tv-clock]');
        if (clockEl) clockEl.textContent = toFaDigits(h + ':' + m);
    }

    function schedulePoll(delay) {
        if (state.pollTimer) clearTimeout(state.pollTimer);
        state.pollTimer = setTimeout(function () {
            fetchData().finally(scheduleNextPoll);
        }, delay);
    }

    function scheduleNextPoll() {
        var base = (cfg.pollMs || 45000) + state.backoffMs;
        if (document.hidden) base = Math.max(base, 120000);
        schedulePoll(base);
    }

    function fetchData() {
        if (!cfg.apiUrl) return Promise.resolve();
        if (state.inflight) state.inflight.abort();
        var controller = new AbortController();
        state.inflight = controller;
        var timeout = setTimeout(function () { controller.abort(); }, 10000);

        setConnection('loading', state.lastData ? 'در حال بروزرسانی…' : 'در حال بارگذاری…');

        return fetch(cfg.apiUrl, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
            signal: controller.signal
        })
            .then(function (r) {
                if (!r.ok) throw new Error('http-' + r.status);
                return r.json();
            })
            .then(function (data) {
                clearTimeout(timeout);
                state.inflight = null;
                state.backoffMs = 0;
                renderAll(data, false);
            })
            .catch(function (err) {
                clearTimeout(timeout);
                state.inflight = null;
                if (err && err.name === 'AbortError') return;
                state.backoffMs = Math.min(state.backoffMs ? state.backoffMs * 2 : 5000, 60000);
                if (state.lastData) {
                    setConnection('offline', 'قطع ارتباط — آخرین بروزرسانی ' + (state.lastData.clock || ''));
                } else {
                    setConnection('offline', 'خطا در بارگذاری — تلاش مجدد…');
                }
            });
    }

    function initTheme() {
        var settings = loadSettings();
        if (settings.theme === 'light' || settings.theme === 'dark') {
            document.documentElement.setAttribute('data-theme', settings.theme);
        }
    }

    function toggleTheme() {
        var cur = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = cur === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', next);
        saveSettings({ theme: next });
    }

    function toggleFullscreen() {
        var el = root;
        var hint = root.querySelector('[data-tv-fs-hint]');
        var req = el.requestFullscreen || el.webkitRequestFullscreen;
        if (!req) {
            if (hint) hint.hidden = false;
            return;
        }
        if (!document.fullscreenElement) {
            Promise.resolve(req.call(el)).catch(function () {
                if (hint) hint.hidden = false;
            });
        } else if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }

    function bindControls() {
        var themeBtn = root.querySelector('[data-tv-theme]');
        if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

        var fsBtn = root.querySelector('[data-tv-fullscreen]');
        if (fsBtn) fsBtn.addEventListener('click', toggleFullscreen);

        var widgetsBtn = root.querySelector('[data-tv-widgets]');
        var drawer = root.querySelector('[data-tv-widget-drawer]');
        var closeBtn = root.querySelector('[data-tv-widgets-close]');
        var form = root.querySelector('[data-tv-widget-form]');

        if (widgetsBtn && drawer) widgetsBtn.addEventListener('click', function () { drawer.hidden = false; });
        if (closeBtn && drawer) closeBtn.addEventListener('click', function () { drawer.hidden = true; });
        if (drawer) {
            drawer.addEventListener('click', function (e) {
                if (e.target === drawer) drawer.hidden = true;
            });
        }
        if (form) {
            form.addEventListener('change', function () {
                var selected = [];
                form.querySelectorAll('input[name="widget"]:checked:not(:disabled)').forEach(function (inp) {
                    selected.push(inp.value);
                });
                saveSettings({ widgets: selected });
                if (state.lastData) applyWidgetVisibility(state.lastData);
            });
        }

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) {
                state.backoffMs = 0;
                fetchData();
            }
            scheduleNextPoll();
        });
    }

    function init() {
        initTheme();
        var initial = readInitial();
        if (initial && initial.ok) {
            renderAll(initial, true);
        } else {
            setConnection('loading', 'در حال بارگذاری…');
        }

        tickClock();
        setInterval(tickClock, 1000);
        bindControls();

        fetchData().finally(scheduleNextPoll);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
