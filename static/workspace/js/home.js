(function () {
    'use strict';

    function greetingForHour(h) {
        if (h >= 5 && h < 12) return 'صبح بخیر';
        if (h >= 12 && h < 17) return 'ظهر بخیر';
        if (h >= 17 && h < 21) return 'عصر بخیر';
        return 'شب بخیر';
    }

    function initGreeting() {
        const el = document.getElementById('wsHomeGreeting');
        if (!el) return;
        el.textContent = greetingForHour(new Date().getHours());
    }

    function resizeHomeCharts() {
        if (!window.Chart || typeof Chart.getChart !== 'function') return;
        ['chart-activity', 'chart-status'].forEach((id) => {
            const canvas = document.getElementById(id);
            if (!canvas) return;
            const inst = Chart.getChart(canvas);
            if (inst) {
                try {
                    inst.resize();
                } catch (e) { /* ignore */ }
            }
        });
    }

    function initInsightsToggle() {
        const root = document.getElementById('wsHomeInsights');
        const btn = document.getElementById('wsHomeInsightsToggle');
        if (!root || !btn) return;

        const setExpanded = (expanded) => {
            root.classList.toggle('is-collapsed-mobile', !expanded);
            btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            if (expanded) {
                requestAnimationFrame(() => {
                    requestAnimationFrame(resizeHomeCharts);
                });
            }
        };

        btn.addEventListener('click', () => {
            const collapsed = root.classList.contains('is-collapsed-mobile');
            setExpanded(collapsed);
        });

        // Desktop always shows body via CSS; keep aria in sync on resize
        const mq = window.matchMedia('(max-width: 768px)');
        const syncForViewport = () => {
            if (!mq.matches) {
                btn.setAttribute('aria-expanded', 'true');
            } else if (root.classList.contains('is-collapsed-mobile')) {
                btn.setAttribute('aria-expanded', 'false');
            }
        };
        syncForViewport();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', syncForViewport);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(syncForViewport);
        }
    }

    function initFileSearch() {
        const search = document.getElementById('homeFilesSearch');
        const table = document.getElementById('homeFilesTable');
        const empty = document.getElementById('homeFilesEmpty');
        if (!search || !table) return;
        const rows = table.querySelectorAll('tbody tr');
        const wrap = table.closest('.mk-table-wrap');

        const applyFilter = () => {
            const q = search.value.trim().toLowerCase();
            let visible = 0;
            rows.forEach((row) => {
                const match = !q || (row.dataset.search || '').toLowerCase().includes(q);
                row.hidden = !match;
                if (match) visible += 1;
            });
            if (empty) empty.hidden = !(q && visible === 0);
            if (wrap) wrap.hidden = !!(q && visible === 0);
        };

        search.addEventListener('input', applyFilter);
    }

    function initReveal() {
        const root = document.querySelector('.ws-home');
        if (!root) return;
        requestAnimationFrame(() => root.classList.add('is-ready'));
    }

    document.addEventListener('DOMContentLoaded', () => {
        initGreeting();
        initFileSearch();
        initInsightsToggle();
        initReveal();
    });
})();
