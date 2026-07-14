/**
 * CRM Agency TV Mode — fullscreen dashboard with light polling.
 */
(function () {
    'use strict';

    var root = document.getElementById('crm-tv-app');
    if (!root) return;

    var cfg = window.crmTeamTV || {};
    var STORAGE_WIDGETS = 'crm-tv-widgets';
    var STORAGE_THEME = 'crm-tv-theme';

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

    function deltaHtml(delta) {
        if (delta == null) return '';
        var cls = delta >= 0 ? 'crm-tv-kpi-delta--up' : 'crm-tv-kpi-delta--down';
        var icon = delta >= 0 ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down';
        return '<span class="crm-tv-kpi-delta ' + cls + '"><i class="fas ' + icon + '"></i> ' +
            toFaDigits(Math.abs(delta)) + '%</span>';
    }

    function getWidgets() {
        try {
            var raw = localStorage.getItem(STORAGE_WIDGETS);
            if (raw) return JSON.parse(raw);
        } catch (e) { /* ignore */ }
        return null;
    }

    function saveWidgets(list) {
        try {
            localStorage.setItem(STORAGE_WIDGETS, JSON.stringify(list));
        } catch (e) { /* ignore */ }
    }

    function applyWidgets(list) {
        if (!list || !list.length) return;
        root.querySelectorAll('[data-widget]').forEach(function (panel) {
            var w = panel.getAttribute('data-widget');
            panel.hidden = list.indexOf(w) === -1;
        });
        var form = root.querySelector('[data-tv-widget-form]');
        if (form) {
            form.querySelectorAll('input[name="widget"]').forEach(function (inp) {
                inp.checked = list.indexOf(inp.value) !== -1;
            });
        }
    }

    function renderKpis(data) {
        var el = root.querySelector('[data-tv-kpis]');
        if (!el) return;
        var kpis = data.kpis || {};
        var team = data.team_view;

        if (team) {
            var items = [
                { key: 'calls', lbl: 'تماس امروز', cls: 'crm-tv-kpi--calls' },
                { key: 'visits', lbl: 'بازدید امروز', cls: 'crm-tv-kpi--visits' },
                { key: 'new_contacts', lbl: 'مخاطب جدید', cls: 'crm-tv-kpi--contacts' },
                { key: 'deals_closed', lbl: 'معامله بسته', cls: 'crm-tv-kpi--deals' },
                { key: 'active_deals', lbl: 'معامله فعال', cls: 'crm-tv-kpi--active' },
                { key: 'inbox_unassigned', lbl: 'سرنخ بدون تخصیص', cls: 'crm-tv-kpi--inbox' },
                { key: 'overdue_followups', lbl: 'پیگیری معوق', cls: 'crm-tv-kpi--overdue' },
                { key: 'commission_today', lbl: 'کمیسیون امروز', cls: 'crm-tv-kpi--commission' }
            ];
            el.innerHTML = items.map(function (item, i) {
                var k = kpis[item.key] || { value: 0, delta: null };
                return '<article class="crm-tv-kpi ' + item.cls + '" style="animation-delay:' + (i * 0.05) + 's">' +
                    '<span class="crm-tv-kpi-val">' + toFaDigits(k.value) + '</span>' +
                    '<span class="crm-tv-kpi-lbl">' + item.lbl + '</span>' +
                    deltaHtml(k.delta) + '</article>';
            }).join('');
        } else {
            el.innerHTML =
                '<article class="crm-tv-kpi crm-tv-kpi--calls"><span class="crm-tv-kpi-val">' +
                toFaDigits(kpis.calls && kpis.calls.value || 0) + '</span><span class="crm-tv-kpi-lbl">تماس امروز</span></article>' +
                '<article class="crm-tv-kpi crm-tv-kpi--visits"><span class="crm-tv-kpi-val">' +
                toFaDigits(kpis.visits && kpis.visits.value || 0) + '</span><span class="crm-tv-kpi-lbl">بازدید امروز</span></article>' +
                '<article class="crm-tv-kpi crm-tv-kpi--deals"><span class="crm-tv-kpi-val">' +
                toFaDigits(kpis.deals_closed && kpis.deals_closed.value || 0) + '</span><span class="crm-tv-kpi-lbl">معامله بسته</span></article>' +
                '<article class="crm-tv-kpi crm-tv-kpi--active"><span class="crm-tv-kpi-val">' +
                toFaDigits(kpis.active_deals && kpis.active_deals.value || 0) + '</span><span class="crm-tv-kpi-lbl">معامله فعال</span></article>';
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
        body.innerHTML =
            '<p class="crm-tv-spotlight-name">' + esc(top.name) + '</p>' +
            '<p class="crm-tv-spotlight-role">' + esc(top.role) + '</p>' +
            '<div class="crm-tv-spotlight-stats">' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.calls) + '</em> تماس</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.visits) + '</em> بازدید</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.deals_closed) + '</em> بسته‌شده</div>' +
            '<div class="crm-tv-spotlight-stat"><em>' + toFaDigits(top.score_pct) + '%</em> امتیاز</div>' +
            '</div>';
    }

    function renderLeaderboard(data) {
        var el = root.querySelector('[data-tv-leaderboard]');
        if (!el) return;
        var rows = data.leaderboard || [];
        if (!rows.length) {
            el.innerHTML = '<li class="crm-tv-empty">داده‌ای برای رتبه‌بندی نیست</li>';
            return;
        }
        el.innerHTML = rows.map(function (r) {
            var topCls = r.rank === 1 ? ' crm-tv-lb-row--top' : '';
            return '<li class="crm-tv-lb-row' + topCls + '">' +
                '<span class="crm-tv-lb-rank">' + toFaDigits(r.rank) + '</span>' +
                '<div><div class="crm-tv-lb-name">' + esc(r.name) + '</div>' +
                '<div class="crm-tv-lb-role">' + esc(r.role) + '</div></div>' +
                '<span class="crm-tv-lb-score">' + toFaDigits(r.score) + '</span>' +
                '<div class="crm-tv-lb-bar"><i style="width:' + (r.score_pct || 0) + '%"></i></div>' +
                '</li>';
        }).join('');
    }

    function renderGoals(data) {
        var el = root.querySelector('[data-tv-goals]');
        if (!el) return;
        var goals = data.goals || [];
        if (!goals.length) {
            el.innerHTML = '<p class="crm-tv-empty">هدفی برای این دوره ثبت نشده</p>';
            return;
        }
        el.innerHTML = goals.map(function (g) {
            var barCls = g.pct >= 80 ? '' : (g.pct >= 40 ? ' crm-tv-goal-bar--warn' : ' crm-tv-goal-bar--low');
            return '<article class="crm-tv-goal">' +
                '<div class="crm-tv-goal-head"><strong>' + esc(g.member_name) + '</strong>' +
                '<span class="crm-tv-goal-metric">' + esc(g.metric_label) + '</span></div>' +
                '<div class="crm-tv-goal-bar' + barCls + '"><i style="width:' + g.pct + '%"></i></div>' +
                '<div class="crm-tv-goal-foot"><span>' + toFaDigits(g.actual) + ' / ' + toFaDigits(g.target) + '</span>' +
                '<span>' + toFaDigits(g.pct) + '%</span></div></article>';
        }).join('');
    }

    function renderAnnouncements(data) {
        var el = root.querySelector('[data-tv-announcements]');
        if (!el) return;
        var items = data.announcements || [];
        if (!items.length) {
            el.innerHTML = '<p class="crm-tv-empty">اطلاعیه‌ای نیست</p>';
            return;
        }
        el.innerHTML = items.map(function (a, i) {
            var imp = a.importance === 'urgent' ? 'urgent' : (a.importance === 'high' ? 'high' : 'normal');
            var pin = a.is_pinned ? '<i class="fas fa-thumbtack"></i>' : '';
            return '<article class="crm-tv-ann crm-tv-ann--' + imp + '" style="animation-delay:' + (i * 0.08) + 's">' +
                '<p class="crm-tv-ann-title">' + pin + esc(a.title) + '</p>' +
                '<p class="crm-tv-ann-preview">' + esc(a.body_preview) + '</p></article>';
        }).join('');
    }

    function renderLeads(data) {
        var el = root.querySelector('[data-tv-leads]');
        if (!el) return;
        var leads = data.leads || {};
        el.innerHTML =
            '<div class="crm-tv-lead-stat crm-tv-lead-stat--warn"><em>' + toFaDigits(leads.unassigned || 0) + '</em><span>بدون تخصیص</span></div>' +
            '<div class="crm-tv-lead-stat"><em>' + toFaDigits(leads.new_today || 0) + '</em><span>جدید امروز</span></div>' +
            '<div class="crm-tv-lead-stat"><em>' + toFaDigits(leads.stale || 0) + '</em><span>بیش از ۴۸ ساعت</span></div>';
    }

    function renderDeals(data) {
        var el = root.querySelector('[data-tv-deals]');
        if (!el) return;
        var deals = data.deals || {};
        function listItems(items, empty) {
            if (!items || !items.length) return '<p class="crm-tv-deal-empty">' + empty + '</p>';
            return '<ul class="crm-tv-deal-list">' + items.map(function (d) {
                return '<li class="crm-tv-deal-item"><strong>' + esc(d.title) + '</strong>' +
                    '<span>' + esc(d.stage) + (d.advisor ? ' · ' + esc(d.advisor) : '') + '</span></li>';
            }).join('') + '</ul>';
        }
        el.innerHTML =
            '<div class="crm-tv-deal-col"><h3>فعال (' + toFaDigits(deals.active_count || 0) + ')</h3>' +
            listItems(deals.active, 'معامله فعالی نیست') + '</div>' +
            '<div class="crm-tv-deal-col"><h3>بسته امروز (' + toFaDigits(deals.closed_today_count || 0) + ')</h3>' +
            listItems(deals.closed_today, 'امروز معامله‌ای بسته نشده') + '</div>';
    }

    function renderAlerts(data) {
        var el = root.querySelector('[data-tv-alerts]');
        if (!el) return;
        var alerts = data.alerts || [];
        if (!alerts.length) {
            el.innerHTML = '<p class="crm-tv-empty"><i class="fas fa-circle-check"></i> وضعیت عادی</p>';
            return;
        }
        el.innerHTML = alerts.map(function (a) {
            return '<p class="crm-tv-alert crm-tv-alert--' + esc(a.level) + '"><i class="fas fa-bell"></i> ' + esc(a.text) + '</p>';
        }).join('');
    }

    function renderAll(data) {
        if (!data || !data.ok) return;
        renderKpis(data);
        renderSpotlight(data);
        renderLeaderboard(data);
        renderGoals(data);
        renderAnnouncements(data);
        renderLeads(data);
        renderDeals(data);
        renderAlerts(data);

        var dateEl = root.querySelector('[data-tv-date]');
        if (dateEl && data.jalali_date) dateEl.textContent = data.jalali_date;

        var updated = root.querySelector('[data-tv-updated]');
        if (updated) {
            var t = data.clock || '';
            updated.textContent = 'به‌روز · ' + t;
        }
    }

    function tickClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, '0');
        var m = String(now.getMinutes()).padStart(2, '0');
        var clockEl = root.querySelector('[data-tv-clock]');
        if (clockEl) clockEl.textContent = toFaDigits(h + ':' + m);
    }

    function fetchData() {
        if (!cfg.apiUrl) return Promise.resolve();
        var sync = root.querySelector('[data-tv-sync]');
        if (sync) sync.classList.add('is-loading');
        return fetch(cfg.apiUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                renderAll(data);
                if (sync) sync.classList.remove('is-loading');
            })
            .catch(function () {
                if (sync) sync.classList.remove('is-loading');
            });
    }

    function initTheme() {
        var saved = null;
        try { saved = localStorage.getItem(STORAGE_THEME); } catch (e) { /* ignore */ }
        if (saved === 'light' || saved === 'dark') {
            document.documentElement.setAttribute('data-theme', saved);
        }
    }

    function toggleTheme() {
        var cur = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = cur === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', next);
        try { localStorage.setItem(STORAGE_THEME, next); } catch (e) { /* ignore */ }
    }

    function toggleFullscreen() {
        var el = root;
        if (!document.fullscreenElement) {
            if (el.requestFullscreen) el.requestFullscreen();
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

        if (widgetsBtn && drawer) {
            widgetsBtn.addEventListener('click', function () { drawer.hidden = false; });
        }
        if (closeBtn && drawer) {
            closeBtn.addEventListener('click', function () { drawer.hidden = true; });
        }
        if (drawer) {
            drawer.addEventListener('click', function (e) {
                if (e.target === drawer) drawer.hidden = true;
            });
        }
        if (form) {
            form.addEventListener('change', function () {
                var selected = [];
                form.querySelectorAll('input[name="widget"]:checked').forEach(function (inp) {
                    selected.push(inp.value);
                });
                saveWidgets(selected);
                applyWidgets(selected);
            });
        }
    }

    function init() {
        initTheme();
        var widgets = getWidgets();
        if (widgets) applyWidgets(widgets);

        var initial = readInitial();
        if (initial) renderAll(initial);

        tickClock();
        setInterval(tickClock, 1000);

        bindControls();

        var pollMs = cfg.pollMs || 45000;
        setInterval(fetchData, pollMs);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
