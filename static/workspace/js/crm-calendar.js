/**
 * CRM Calendar — view switch, category filters, day selection, week/list panels, mobile agenda.
 */
(function () {
    'use strict';

    var TYPE_LABELS = {
        followup: 'پیگیری',
        reminder: 'یادآور',
        visit: 'بازدید',
        contract: 'قرارداد',
    };

    var FILTER_LABELS = {
        all: 'همه دسته‌ها',
        followup: 'پیگیری',
        visit: 'بازدید',
        reminder: 'یادآور',
        contract: 'قرارداد',
    };

    var TYPE_CLASS = {
        followup: 'crm-cal-event--followup',
        reminder: 'crm-cal-event--reminder',
        visit: 'crm-cal-event--visit',
        contract: 'crm-cal-event--contract',
    };

    var MOB_EV_CLASS = {
        followup: 'crm-cal-mob-ev--followup',
        reminder: 'crm-cal-mob-ev--reminder',
        visit: 'crm-cal-mob-ev--visit',
        contract: 'crm-cal-mob-ev--contract',
    };

    var PERSIAN_MONTHS = [
        'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
    ];

    var PERSIAN_WEEKDAYS = [
        'شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه',
    ];

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

    function isMobileLayout() {
        return window.matchMedia('(max-width: 768px)').matches;
    }

    function relationLine(ev) {
        if (ev.customer_name) {
            return 'مخاطب: ' + ev.customer_name;
        }
        if (ev.type === 'contract' && ev.short_label) {
            return 'معامله: ' + ev.short_label;
        }
        if (ev.location) {
            return ev.location;
        }
        return '';
    }

    function dayHeaderFromJkey(jkey, events, root) {
        var sample = null;
        for (var i = 0; i < events.length; i++) {
            if (events[i].jkey === jkey) {
                sample = events[i];
                break;
            }
        }
        if (sample) {
            return {
                title: (sample.weekday || '') + ' · ' + (sample.day_label || '') + ' ' + PERSIAN_MONTHS[(sample.jmonth || 1) - 1],
                weekday: sample.weekday || '',
            };
        }

        var cell = root.querySelector('.crm-cal-cell[data-jkey="' + jkey + '"]');
        var dayNum = cell ? cell.querySelector('.crm-cal-day-num') : null;
        var monthTitle = root.querySelector('.crm-cal-toolbar-title strong');
        var weekday = '';
        if (cell) {
            var cellsList = root.querySelectorAll('.crm-cal-cell[data-jkey]');
            var idx = Array.prototype.indexOf.call(cellsList, cell);
            if (idx >= 0) {
                weekday = PERSIAN_WEEKDAYS[idx % 7] || '';
            }
        }
        var dayLabel = dayNum ? dayNum.textContent.trim() : '';
        var monthLabel = monthTitle ? monthTitle.textContent.trim() : '';
        if (dayLabel && monthLabel) {
            return {
                title: (weekday ? weekday + ' · ' : '') + dayLabel + ' ' + monthLabel.split(' ')[0],
                weekday: weekday,
            };
        }

        var parts = jkey.split('-');
        if (parts.length !== 3) {
            return { title: jkey, weekday: '' };
        }
        var jd = parseInt(parts[2], 10);
        var jm = parseInt(parts[1], 10);
        return {
            title: toPersianDigits(jd) + ' ' + PERSIAN_MONTHS[jm - 1],
            weekday: weekday,
        };
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
        var mobAgendaBody = document.getElementById('crmCalMobAgendaBody');
        var mobAgendaTitle = document.getElementById('crmCalMobAgendaTitle');
        var mobAgendaMeta = document.getElementById('crmCalMobAgendaMeta');
        var filterActiveEl = document.getElementById('crmCalFilterActive');
        var filterSheet = document.getElementById('crmCalFilterSheet');
        var filterOpenBtn = document.getElementById('crmCalFilterOpen');

        function setSelectedDay(jkey) {
            if (!jkey) return;
            selectedJkey = jkey;
            cells.forEach(function (cell) {
                var selected = cell.getAttribute('data-jkey') === jkey && !cell.classList.contains('is-out');
                cell.classList.toggle('is-selected', selected);
                cell.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
            renderMobileAgenda(jkey);
        }

        function updateFilterLabel(filter) {
            var label = FILTER_LABELS[filter] || FILTER_LABELS.all;
            if (filterActiveEl) {
                filterActiveEl.textContent = label;
                filterActiveEl.setAttribute('data-filter-label', label);
            }
        }

        function eventsForDay(jkey) {
            return filteredEvents(events).filter(function (ev) {
                return ev.jkey === jkey;
            }).sort(function (a, b) {
                return (a.time || '99:99').localeCompare(b.time || '99:99');
            });
        }

        function openDrawerViaCrm(drawerId) {
            if (!drawerId) return;
            var wired = root.querySelector(
                '.crm-cal-mob-toolbar-add[data-drawer-open="' + drawerId + '"], ' +
                '.crm-cal-mob-cta[data-drawer-open="' + drawerId + '"], ' +
                '.crm-cal-page-head-actions [data-drawer-open="' + drawerId + '"], ' +
                '.fl-header__btn--primary[data-drawer-open="' + drawerId + '"]'
            );
            if (wired) {
                wired.click();
                return;
            }
            var drawer = document.getElementById(drawerId);
            if (!drawer) return;
            drawer.hidden = false;
            drawer.removeAttribute('hidden');
            drawer.classList.add('is-open');
            document.body.classList.add('crm-drawer-open');
        }

        function renderMobileAgenda(jkey) {
            if (!mobAgendaBody || !isMobileLayout()) return;

            var header = dayHeaderFromJkey(jkey, events, root);
            if (mobAgendaTitle) {
                mobAgendaTitle.textContent = header.title;
            }

            var dayEvents = eventsForDay(jkey);
            if (mobAgendaMeta) {
                mobAgendaMeta.textContent = dayEvents.length
                    ? toPersianDigits(dayEvents.length) + ' برنامه'
                    : 'بدون برنامه';
            }

            if (!dayEvents.length) {
                mobAgendaBody.innerHTML =
                    '<div class="crm-cal-mob-agenda-empty">' +
                    '<p>برای این روز برنامه‌ای ثبت نشده</p>' +
                    '<button type="button" class="crm-cal-mob-agenda-empty-cta" data-drawer-open="drawer-reminder">' +
                    '<i class="fas fa-plus" aria-hidden="true"></i> ثبت یادآوری</button></div>';
                var emptyCta = mobAgendaBody.querySelector('.crm-cal-mob-agenda-empty-cta[data-drawer-open]');
                if (emptyCta) {
                    emptyCta.addEventListener('click', function (e) {
                        e.preventDefault();
                        openDrawerViaCrm(emptyCta.getAttribute('data-drawer-open'));
                    });
                }
                return;
            }

            var html = '<ol class="crm-cal-mob-agenda-list">';
            dayEvents.forEach(function (ev) {
                var overdue = jkey < todayJkey && (ev.type === 'reminder' || ev.type === 'followup');
                var rel = relationLine(ev);
                html += '<li>';
                html += '<a href="' + ev.href + '" class="crm-cal-mob-ev ' + (MOB_EV_CLASS[ev.type] || '') + (overdue ? ' is-overdue' : '') + '">';
                html += '<time class="crm-cal-mob-ev-time">' + (ev.time ? toPersianDigits(ev.time) : '—') + '</time>';
                html += '<span class="crm-cal-mob-ev-body">';
                html += '<span class="crm-cal-mob-ev-type">' + (TYPE_LABELS[ev.type] || 'رویداد') + '</span>';
                if (overdue) {
                    html += '<span class="crm-cal-mob-ev-status">عقب‌افتاده</span>';
                }
                html += '<strong class="crm-cal-mob-ev-title">' + (ev.short_label || ev.label) + '</strong>';
                if (rel) {
                    html += '<span class="crm-cal-mob-ev-rel">' + rel + '</span>';
                }
                html += '</span>';
                html += '<i class="fas fa-chevron-left crm-cal-mob-ev-go" aria-hidden="true"></i>';
                html += '</a></li>';
            });
            html += '</ol>';
            mobAgendaBody.innerHTML = html;
        }

        function updateDayIndicators() {
            cells.forEach(function (cell) {
                if (cell.classList.contains('is-out')) return;
                var jkey = cell.getAttribute('data-jkey');
                var dayEvents = eventsForDay(jkey);
                var count = dayEvents.length;
                var countEl = cell.querySelector('.crm-cal-day-count');
                var dotsWrap = cell.querySelector('.crm-cal-dots');

                cell.classList.toggle('has-events', count > 0);

                if (countEl) {
                    if (count > 0) {
                        countEl.textContent = toPersianDigits(count);
                        countEl.hidden = false;
                    } else {
                        countEl.hidden = true;
                    }
                }

                if (dotsWrap) {
                    dotsWrap.innerHTML = '';
                    if (count > 0) {
                        var typesSeen = {};
                        dayEvents.forEach(function (ev) {
                            if (typesSeen[ev.type] || Object.keys(typesSeen).length >= 3) return;
                            typesSeen[ev.type] = true;
                            var dot = document.createElement('i');
                            dot.className = 'crm-cal-dot crm-cal-dot--' + ev.type;
                            dotsWrap.appendChild(dot);
                        });
                    }
                }
            });
            if (selectedJkey) {
                renderMobileAgenda(selectedJkey);
            }
        }

        function applyFilter(filter) {
            activeFilter = filter;
            root.setAttribute('data-cal-filter-active', filter);
            updateFilterLabel(filter);

            filterChips.forEach(function (chip) {
                if (!chip.classList.contains('crm-cal-filter-chip')) return;
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
            updateDayIndicators();
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

        function openFilterSheet() {
            if (!filterSheet) return;
            filterSheet.classList.add('is-open');
            filterSheet.setAttribute('aria-hidden', 'false');
            if (filterOpenBtn) filterOpenBtn.setAttribute('aria-expanded', 'true');
            document.body.classList.add('crm-cal-filter-sheet-open');
        }

        function closeFilterSheet() {
            if (!filterSheet) return;
            filterSheet.classList.remove('is-open');
            filterSheet.setAttribute('aria-hidden', 'true');
            if (filterOpenBtn) filterOpenBtn.setAttribute('aria-expanded', 'false');
            document.body.classList.remove('crm-cal-filter-sheet-open');
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
                if (chip.closest('.crm-cal-mob-filter-sheet')) {
                    closeFilterSheet();
                }
            });
        });

        root.querySelectorAll('[data-cal-goto-today]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyFilter('all');
                setSelectedDay(todayJkey);
                switchView('month');
                var todayCell = root.querySelector('.crm-cal-cell[data-jkey="' + todayJkey + '"]');
                if (todayCell && todayCell.scrollIntoView) {
                    todayCell.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        });

        root.querySelectorAll('[data-cal-goto-overdue]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyFilter('all');
                switchView('list');
                var listPanel = root.querySelector('[data-cal-view-panel="list"]');
                if (listPanel && listPanel.scrollIntoView) {
                    listPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        if (filterOpenBtn) {
            filterOpenBtn.addEventListener('click', function () {
                if (filterSheet && filterSheet.classList.contains('is-open')) {
                    closeFilterSheet();
                } else {
                    openFilterSheet();
                }
            });
        }

        root.querySelectorAll('[data-cal-filter-close]').forEach(function (el) {
            el.addEventListener('click', closeFilterSheet);
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

        window.addEventListener('resize', function () {
            if (selectedJkey) {
                renderMobileAgenda(selectedJkey);
            }
        });

        setSelectedDay(todayJkey);
        applyFilter('all');
        updateDayIndicators();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCalendarApp);
    } else {
        initCalendarApp();
    }
})();
