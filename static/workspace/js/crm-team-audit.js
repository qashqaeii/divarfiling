/**
 * CRM Team Audit — client-side filter & search
 */
(function () {
    'use strict';

    const root = document.querySelector('[data-crm-audit]');
    if (!root) return;

    const filters = root.querySelectorAll('[data-audit-filter]');
    const searchInput = root.querySelector('[data-audit-search]');
    const events = root.querySelectorAll('[data-audit-event]');
    const days = root.querySelectorAll('[data-audit-day]');
    const timeline = root.querySelector('[data-audit-timeline]');
    const filterEmpty = root.querySelector('[data-audit-filter-empty]');
    const visibleCount = root.querySelector('[data-audit-visible-count]');
    const resetBtn = root.querySelector('[data-audit-reset]');

    let currentFilter = 'all';

    function normalize(text) {
        return String(text || '').trim().toLowerCase();
    }

    function applyFilters() {
        const q = normalize(searchInput?.value);
        let visible = 0;

        events.forEach((el) => {
            const cat = el.dataset.category || '';
            const search = el.dataset.search || '';
            const catOk = currentFilter === 'all' || cat === currentFilter;
            const searchOk = !q || search.includes(q);
            const show = catOk && searchOk;
            el.hidden = !show;
            if (show) visible += 1;
        });

        days.forEach((day) => {
            const anyVisible = Array.from(day.querySelectorAll('[data-audit-event]')).some((el) => !el.hidden);
            day.hidden = !anyVisible;
        });

        if (timeline) timeline.hidden = visible === 0;
        if (filterEmpty) filterEmpty.hidden = visible !== 0;
        if (visibleCount) {
            visibleCount.textContent = visible
                ? `${visible.toLocaleString('fa-IR')} رویداد نمایش داده می‌شود`
                : '';
        }
    }

    filters.forEach((btn) => {
        btn.addEventListener('click', () => {
            currentFilter = btn.dataset.auditFilter || 'all';
            filters.forEach((b) => {
                const active = b === btn;
                b.classList.toggle('active', active);
                b.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            applyFilters();
        });
    });

    if (searchInput) {
        let timer;
        searchInput.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(applyFilters, 120);
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            currentFilter = 'all';
            filters.forEach((b) => {
                const active = (b.dataset.auditFilter || '') === 'all';
                b.classList.toggle('active', active);
                b.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            if (searchInput) searchInput.value = '';
            applyFilters();
        });
    }

    applyFilters();
})();
