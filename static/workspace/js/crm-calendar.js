/**
 * CRM Calendar — view switch, category filters, day selection, week/list panels.
 */
(function () {
    'use strict';

    var TYPE_LABELS = {
        followup: 'پیگیری',
        reminder: 'یادآور',
        visit: 'بازدید',
        contract: 'قرارداد',
    };

    var TYPE_CLASS = {
        followup: 'crm-cal-event--followup',
        reminder: 'crm-cal-event--reminder',
        visit: 'crm-cal-event--visit',
        contract: 'crm-cal-event--contract',
    };

    function toPersianDigits(str) {
        var map = {'0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'};
        return String(str).replace(/[0-9]/g, function (d) { return map[d] || d; });
    }

    function parseEvents(root) {
        var el = document.getElementById('crmCalEventsData');
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || '[]');
        } catch (e) {
            return [];
        }
    }

    function initCalendarApp() {
        var root = document.getElementById('crmCalendarApp');
        if (!root) return;

        var events = parseEvents(root);
        var todayJkey = root.getAttribute('data-today-jkey') || '';
        var activeFilter = 'all';
        var activeView = 'month';
        var selectedJkey = todayJkey;
        var weekRendered = false;
        var listRendered = false;

        var cells = root.querySelectorAll('.crm-cal-cell[data-jkey]');
        var filterChips = root.querySelectorAll('[data-cal-filter]');
        var viewBtns = root.querySelectorAll('[data-cal-view]');
        var viewPanels = root.querySelectorAll('[data-cal-view-panel]');
        var weekGrid = document.getElementById('crmCalWeekGrid');
        var listEl = document.getElementById('crmCalList');

        function setSelectedDay(jkey) {
            if (!jkey) return;
            selectedJkey = jkey;
            cells.forEach(function (cell) {
                cell.classList.toggle('is-selected', cell.getAttribute('data-jkey') === jkey);
            });
        }

        function applyFilter(filter) {
            activeFilter = filter;
            root.setAttribute('data-cal-filter-active', filter);

            filterChips.forEach(function (chip) {
                chip.classList.toggle('is-active', chip.getAttribute('data-cal-filter') === filter);
            });

            root.querySelectorAll('[data-event-type]').forEach(function (el) {
                var type = el.getAttribute('data-event-type');
                var hidden = filter !== 'all' && type !== filter;
                el.classList.toggle('is-filter-hidden', hidden);
            });

            root.querySelectorAll('.crm-cal-list-item[data-event-type]').forEach(function (el) {
                var type = el.getAttribute('data-event-type');
                el.classList.toggle('is-filter-hidden', filter !== 'all' && type !== filter);
            });

            updateMoreCounts();
            if (activeView === 'week') renderWeekView(true);
            if (activeView === 'list') renderListView(true);
        }

        function filteredEvents(list) {
            if (activeFilter === 'all') return list;
            return list.filter(function (ev) { return ev.type === activeFilter; });
        }

        function updateMoreCounts() {
            cells.forEach(function (cell) {
                var jkey = cell.getAttribute('data-jkey');
                if (!jkey || cell.classList.contains('is-out')) return;
                var visible = cell.querySelectorAll('.crm-cal-event:not(.is-filter-hidden)');
                var moreEl = cell.querySelector('.crm-cal-event-more');
                if (!moreEl) return;
                var total = cell.querySelectorAll('.crm-cal-event').length;
                var hiddenCount = total - visible.length;
                var baseMore = parseInt(moreEl.getAttribute('data-more-count') || '0', 10);
                var extra = Math.max(0, hiddenCount);
                var showCount = baseMore + extra;
                if (showCount > 0 && (activeFilter === 'all' || visible.length > 0)) {
                    moreEl.textContent = '+' + toPersianDigits(showCount) + ' مورد دیگر';
                    moreEl.style.display = '';
                } else if (visible.length <= 2 && baseMore === 0) {
                    moreEl.style.display = 'none';
                }
            });
        }

        function switchView(view) {
            activeView = view;
            viewBtns.forEach(function (btn) {
                var isActive = btn.getAttribute('data-cal-view') === view;
                btn.classList.toggle('is-active', isActive);
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            viewPanels.forEach(function (panel) {
                var match = panel.getAttribute('data-cal-view-panel') === view;
                panel.classList.toggle('is-active', match);
                panel.hidden = !match;
            });
            if (view === 'week' && !weekRendered) renderWeekView(false);
            if (view === 'list' && !listRendered) renderListView(false);
        }

        function groupByJkey(list) {
            var map = {};
            list.forEach(function (ev) {
                if (!map[ev.jkey]) map[ev.jkey] = [];
                map[ev.jkey].push(ev);
            });
            return map;
        }

        function renderWeekView(refresh) {
            if (!weekGrid) return;
            if (weekRendered && !refresh) return;
            weekRendered = true;

            var targetJkey = selectedJkey || todayJkey;
            var weekKeys = [];
            var startIdx = -1;
            var allKeys = [];

            cells.forEach(function (cell) {
                if (!cell.classList.contains('is-out')) {
                    allKeys.push(cell.getAttribute('data-jkey'));
                }
            });

            allKeys.forEach(function (key, idx) {
                if (key === targetJkey) startIdx = idx;
            });
            if (startIdx < 0) startIdx = 0;

            var weekStart = startIdx - (startIdx % 7);
            weekKeys = allKeys.slice(weekStart, weekStart + 7);

            var grouped = groupByJkey(filteredEvents(events));
            var html = '';

            weekKeys.forEach(function (jkey) {
                var dayEvents = grouped[jkey] || [];
                var sample = dayEvents[0] || {};
                var isToday = jkey === todayJkey;
                html += '<div class="crm-cal-week-day">';
                html += '<div class="crm-cal-week-day-head' + (isToday ? ' is-today' : '') + '">';
                html += '<span>' + (sample.weekday || '') + '</span>';
                html += '<span>' + (sample.day_label || '') + '</span>';
                html += '</div><div class="crm-cal-week-day-body">';
                if (!dayEvents.length) {
                    html += '<span class="crm-cal-view-empty" style="padding:0.75rem;font-size:0.72rem;">بدون رویداد</span>';
                } else {
                    dayEvents.forEach(function (ev) {
                        html += '<a href="' + ev.href + '" class="crm-cal-event ' + (TYPE_CLASS[ev.type] || '') + '" data-event-type="' + ev.type + '">';
                        html += '<span class="crm-cal-event-dot"></span>';
                        html += '<span class="crm-cal-event-text">' + (ev.short_label || ev.label) + '</span></a>';
                    });
                }
                html += '</div></div>';
            });

            weekGrid.innerHTML = html || '<div class="crm-cal-view-empty"><i class="fas fa-calendar-xmark"></i><p>رویدادی برای این هفته نیست</p></div>';
        }

        function renderListView(refresh) {
            if (!listEl) return;
            if (listRendered && !refresh) return;
            listRendered = true;

            var list = filteredEvents(events).slice().sort(function (a, b) {
                return (a.jkey + (a.time || '')).localeCompare(b.jkey + (b.time || ''));
            });

            if (!list.length) {
                listEl.innerHTML = '<div class="crm-cal-view-empty"><i class="fas fa-calendar-check"></i><p>رویدادی در این ماه ثبت نشده</p></div>';
                return;
            }

            var grouped = {};
            list.forEach(function (ev) {
                var head = ev.day_label + ' ' + (ev.weekday || '');
                if (!grouped[head]) grouped[head] = [];
                grouped[head].push(ev);
            });

            var html = '';
            Object.keys(grouped).forEach(function (head) {
                html += '<div class="crm-cal-list-group">';
                html += '<div class="crm-cal-list-group-head">' + head + '</div>';
                grouped[head].forEach(function (ev) {
                    html += '<a href="' + ev.href + '" class="crm-cal-list-item" data-event-type="' + ev.type + '">';
                    html += '<span class="crm-cal-list-item-badge ' + (TYPE_CLASS[ev.type] || '') + '">' + (TYPE_LABELS[ev.type] || '') + '</span>';
                    html += '<span class="crm-cal-list-item-body"><strong>' + (ev.short_label || ev.label) + '</strong>';
                    if (ev.customer_name) html += '<span>' + ev.customer_name + '</span>';
                    html += '</span>';
                    if (ev.time) html += '<time>' + toPersianDigits(ev.time) + '</time>';
                    html += '</a>';
                });
                html += '</div>';
            });
            listEl.innerHTML = html;
        }

        cells.forEach(function (cell) {
            cell.addEventListener('click', function (e) {
                if (cell.classList.contains('is-out')) return;
                if (e.target.closest('a.crm-cal-event')) return;
                setSelectedDay(cell.getAttribute('data-jkey'));
            });
            cell.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (!cell.classList.contains('is-out')) {
                        setSelectedDay(cell.getAttribute('data-jkey'));
                    }
                }
            });
        });

        filterChips.forEach(function (chip) {
            chip.addEventListener('click', function () {
                applyFilter(chip.getAttribute('data-cal-filter') || 'all');
            });
        });

        viewBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                switchView(btn.getAttribute('data-cal-view') || 'month');
            });
        });

        root.querySelectorAll('[data-cal-menu-toggle]').forEach(function (toggle) {
            toggle.addEventListener('click', function (e) {
                e.stopPropagation();
                var menu = toggle.closest('.crm-cal-task-menu');
                if (!menu) return;
                var panel = menu.querySelector('.crm-cal-task-menu-panel');
                var open = menu.classList.contains('is-open');
                root.querySelectorAll('.crm-cal-task-menu.is-open').forEach(function (m) {
                    m.classList.remove('is-open');
                    var p = m.querySelector('.crm-cal-task-menu-panel');
                    if (p) p.hidden = true;
                    var b = m.querySelector('[data-cal-menu-toggle]');
                    if (b) b.setAttribute('aria-expanded', 'false');
                });
                if (!open) {
                    menu.classList.add('is-open');
                    if (panel) panel.hidden = false;
                    toggle.setAttribute('aria-expanded', 'true');
                }
            });
        });

        document.addEventListener('click', function () {
            root.querySelectorAll('.crm-cal-task-menu.is-open').forEach(function (menu) {
                menu.classList.remove('is-open');
                var panel = menu.querySelector('.crm-cal-task-menu-panel');
                if (panel) panel.hidden = true;
                var toggle = menu.querySelector('[data-cal-menu-toggle]');
                if (toggle) toggle.setAttribute('aria-expanded', 'false');
            });
        });

        setSelectedDay(todayJkey);
        applyFilter('all');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCalendarApp);
    } else {
        initCalendarApp();
    }
})();
