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

    function initFileSearch() {
        const search = document.getElementById('homeFilesSearch');
        const table = document.getElementById('homeFilesTable');
        if (!search || !table) return;
        const rows = table.querySelectorAll('tbody tr');
        search.addEventListener('input', () => {
            const q = search.value.trim().toLowerCase();
            rows.forEach((row) => {
                row.hidden = q && !(row.dataset.search || '').toLowerCase().includes(q);
            });
        });
    }

    function initReveal() {
        const root = document.querySelector('.ws-home');
        if (!root) return;
        requestAnimationFrame(() => root.classList.add('is-ready'));
    }

    document.addEventListener('DOMContentLoaded', () => {
        initGreeting();
        initFileSearch();
        initReveal();
    });
})();
