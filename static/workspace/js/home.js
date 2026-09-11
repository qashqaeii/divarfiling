(function () {
    'use strict';

    function greetingMeta(h) {
        if (h >= 5 && h < 12) {
            return { text: 'صبح بخیر', icon: 'fa-sun', tone: 'morning' };
        }
        if (h >= 12 && h < 17) {
            return { text: 'ظهر بخیر', icon: 'fa-sun', tone: 'noon' };
        }
        if (h >= 17 && h < 21) {
            return { text: 'عصر بخیر', icon: 'fa-cloud-sun', tone: 'evening' };
        }
        return { text: 'شب بخیر', icon: 'fa-moon', tone: 'night' };
    }

    function initGreeting() {
        const textEl = document.getElementById('wsHomeGreeting');
        const iconEl = document.getElementById('wsHomeGreetingIcon');
        const meta = greetingMeta(new Date().getHours());
        if (textEl) textEl.textContent = meta.text;
        if (iconEl) {
            iconEl.className = `wsh-hero__greeting-icon fas ${meta.icon} is-${meta.tone}`;
        }
    }

    function initHomeCharts() {
        if (typeof window.initCharts === 'function' && window.wsCharts && window.Chart) {
            initCharts(window.wsCharts);
        }
    }

    function resizeHomeCharts() {
        if (!window.Chart || typeof Chart.getChart !== 'function') return;
        ['chart-activity', 'chart-status'].forEach((id) => {
            const canvas = document.getElementById(id);
            if (!canvas) return;
            const inst = Chart.getChart(canvas);
            if (inst) {
                try { inst.resize(); } catch (e) { /* ignore */ }
            }
        });
    }

    function initGlobalSearch() {
        const input = document.getElementById('crmSearchInput');
        const results = document.getElementById('crmSearchResults');
        if (!input || !results) return;

        let timer = null;
        const searchUrl = input.dataset.url || '/workspace/crm/search/';

        input.addEventListener('input', () => {
            clearTimeout(timer);
            const q = input.value.trim();
            if (q.length < 2) { results.hidden = true; return; }
            timer = setTimeout(async () => {
                try {
                    const res = await fetch(`${searchUrl}?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    renderResults(data);
                } catch (e) { /* ignore */ }
            }, 250);
        });

        function renderResults(data) {
            const parts = [];
            if (data.contacts?.length) {
                parts.push('<div class="crm-search-group"><div class="crm-search-group-title">مخاطبین</div>');
                data.contacts.forEach((c) => {
                    parts.push(`<a href="${c.url}" class="crm-search-item"><span>${c.name}</span><span class="crm-search-item-meta">${c.type} · ${c.phone || ''}</span></a>`);
                });
                parts.push('</div>');
            }
            if (data.properties?.length) {
                parts.push('<div class="crm-search-group"><div class="crm-search-group-title">املاک</div>');
                data.properties.forEach((p) => {
                    parts.push(`<a href="${p.url}" class="crm-search-item"><span>${p.title}</span><span class="crm-search-item-meta">${p.deal_mode} · ${p.city || ''}</span></a>`);
                });
                parts.push('</div>');
            }
            if (!parts.length) {
                results.innerHTML = '<div class="crm-empty-text" style="padding:1rem">نتیجه‌ای یافت نشد</div>';
            } else {
                results.innerHTML = parts.join('');
            }
            results.hidden = false;
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#crmGlobalSearch')) results.hidden = true;
        });
    }

    function isoDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    function initReminderTabs() {
        const root = document.getElementById('wshReminders');
        const list = document.getElementById('wshRemindersList');
        if (!root || !list) return;

        const tabs = root.querySelectorAll('[data-wsh-reminder-tab]');
        const items = list.querySelectorAll('.wsh-reminders__item[data-wsh-reminder-date], .wsh-reminders__item[data-wsh-reminder-scope]');
        const emptyAll = document.getElementById('wshRemindersEmpty');
        const emptyTab = document.getElementById('wshRemindersTabEmpty');
        if (!tabs.length) return;

        const today = isoDate(new Date());
        const tomorrow = isoDate(new Date(Date.now() + 86400000));
        const weekEnd = isoDate(new Date(Date.now() + 7 * 86400000));

        function matchesTab(item, tab) {
            const scope = item.getAttribute('data-wsh-reminder-scope') || '';
            const date = item.getAttribute('data-wsh-reminder-date') || '';
            if (tab === 'all') return true;
            if (tab === 'today') {
                return scope.includes('today') || date === today;
            }
            if (tab === 'tomorrow') {
                return date === tomorrow;
            }
            if (tab === 'week') {
                if (scope.includes('today')) return true;
                if (!date) return false;
                return date >= today && date <= weekEnd;
            }
            return true;
        }

        function applyTab(tab) {
            let visible = 0;
            items.forEach((item) => {
                const show = matchesTab(item, tab);
                item.hidden = !show;
                if (show) visible += 1;
            });
            if (emptyAll) emptyAll.hidden = items.length > 0;
            if (emptyTab) emptyTab.hidden = visible > 0 || items.length === 0;
            tabs.forEach((btn) => {
                const active = btn.dataset.wshReminderTab === tab;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-selected', active ? 'true' : 'false');
            });
        }

        tabs.forEach((btn) => {
            btn.addEventListener('click', () => applyTab(btn.dataset.wshReminderTab || 'all'));
        });

        applyTab('all');
    }

    function looksLikeIranMobile(value) {
        const digits = String(value || '').replace(/\D/g, '');
        return /^09\d{9}$/.test(digits) || /^9\d{9}$/.test(digits) || /^989\d{9}$/.test(digits);
    }

    function guardHomeFilesSearchInput(input) {
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('autocorrect', 'off');
        input.setAttribute('spellcheck', 'false');
        input.setAttribute('data-lpignore', 'true');
        input.setAttribute('data-1p-ignore', 'true');
        input.setAttribute('data-form-type', 'other');
        if (!input.name) input.name = 'mk_home_files_filter';
        input.setAttribute('readonly', 'readonly');
        input.addEventListener('focus', () => input.removeAttribute('readonly'), { once: true });
    }

    function clearPhoneAutofill(input) {
        const value = input.value.trim();
        if (!value || !looksLikeIranMobile(value)) return false;
        input.value = '';
        return true;
    }

    function initFileSearch() {
        const search = document.getElementById('homeFilesSearch');
        const table = document.getElementById('homeFilesTable');
        const empty = document.getElementById('homeFilesEmpty');
        const filterTx = document.getElementById('homeFilesFilterTx');
        const filterLoc = document.getElementById('homeFilesFilterLoc');
        const filterFmt = document.getElementById('homeFilesFilterFmt');
        if (!search || !table) return;

        guardHomeFilesSearchInput(search);
        const rows = table.querySelectorAll('tbody tr');
        const wrap = table.closest('.mk-table-wrap');

        const applyFilter = () => {
            const q = search.value.trim().toLowerCase();
            const tx = filterTx ? filterTx.value : '';
            const loc = filterLoc ? filterLoc.value.trim().toLowerCase() : '';
            const fmt = filterFmt ? filterFmt.value.trim().toLowerCase() : '';
            let visible = 0;
            rows.forEach((row) => {
                const matchSearch = !q || (row.dataset.search || '').toLowerCase().includes(q);
                const matchTx = !tx || (row.dataset.tx || '') === tx;
                const matchLoc = !loc || (row.dataset.loc || '').includes(loc);
                const matchFmt = !fmt || (row.dataset.fmt || '') === fmt;
                const match = matchSearch && matchTx && matchLoc && matchFmt;
                row.hidden = !match;
                if (match) visible += 1;
            });
            const noResults = visible === 0 && rows.length > 0;
            if (empty) empty.hidden = !noResults;
            if (wrap) wrap.hidden = noResults;
        };

        const sweepAutofill = () => {
            if (clearPhoneAutofill(search)) applyFilter();
        };

        search.addEventListener('input', applyFilter);
        [filterTx, filterLoc, filterFmt].forEach((el) => {
            if (el) el.addEventListener('change', applyFilter);
        });
        sweepAutofill();
        requestAnimationFrame(() => requestAnimationFrame(sweepAutofill));
        window.setTimeout(sweepAutofill, 120);
        window.setTimeout(sweepAutofill, 500);
        applyFilter();
    }

    function initReveal() {
        const root = document.querySelector('.wsh-dashboard');
        if (!root) return;
        requestAnimationFrame(() => root.classList.add('is-ready'));
    }

    function initResizeWatch() {
        let t = null;
        window.addEventListener('resize', () => {
            clearTimeout(t);
            t = setTimeout(resizeHomeCharts, 120);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initGreeting();
        initGlobalSearch();
        initReminderTabs();
        initFileSearch();
        initHomeCharts();
        initResizeWatch();
        initReveal();
    });
})();
