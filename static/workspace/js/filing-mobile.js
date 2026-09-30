(function () {
    'use strict';

    function initFilingSearchClear() {
        document.querySelectorAll('[data-filing-search-clear]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var form = document.getElementById('wsFilterForm');
                var inp = form && form.querySelector('input[name="q"]');
                if (!inp || !form) return;
                inp.value = '';
                form.requestSubmit ? form.requestSubmit() : form.submit();
            });
        });
    }

    function initFilingSortSheet() {
        var sheet = document.getElementById('wsMobSortSheet');
        var openBtn = document.getElementById('wsMobSortFocus');
        if (!sheet || !openBtn) return;

        function closeSheet() {
            sheet.hidden = true;
            sheet.classList.remove('is-open');
            sheet.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('ws-filing-sort-open');
            openBtn.setAttribute('aria-expanded', 'false');
        }

        function openSheet() {
            sheet.hidden = false;
            sheet.classList.add('is-open');
            sheet.setAttribute('aria-hidden', 'false');
            document.body.classList.add('ws-filing-sort-open');
            openBtn.setAttribute('aria-expanded', 'true');
            var closeBtn = sheet.querySelector('[data-ws-sort-close].ws-filing-sort-sheet__close');
            if (closeBtn) closeBtn.focus();
        }

        openBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (sheet.classList.contains('is-open')) closeSheet();
            else openSheet();
        });

        sheet.querySelectorAll('[data-ws-sort-close]').forEach(function (el) {
            el.addEventListener('click', closeSheet);
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sheet.classList.contains('is-open')) closeSheet();
        });
    }

    function initFilterBackdropDismiss() {
        document.addEventListener('click', function (e) {
            var shell = document.getElementById('wsFilterShell');
            if (!shell || !shell.classList.contains('fl-dd-filter-open')) return;
            var panel = document.getElementById('wsAdvPanel');
            if (panel && panel.contains(e.target)) return;
            if (e.target.closest('#wsAdvToggleMob, #wsAdvToggle, .ws-mob-search-bar, [data-ds-filter-jump]')) return;
            if (typeof window.__wsCloseFilingFilter === 'function') window.__wsCloseFilingFilter();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initFilingSearchClear();
        initFilingSortSheet();
        initFilterBackdropDismiss();
    });
})();
