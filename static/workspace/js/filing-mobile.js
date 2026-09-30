(function () {
    'use strict';

    function initFilingSearchClear() {
        document.querySelectorAll('[data-filing-search-clear]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var form = document.getElementById('dsFilterForm');
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

    function initFilingFilterSheet() {
        var details = document.getElementById('dsFilterDetails');
        if (!details) return;

        var desktop = window.matchMedia('(min-width: 768px)');
        var toggles = document.querySelectorAll('[data-ws-mob-filter-toggle]');

        function closeFilter() {
            details.removeAttribute('open');
            document.body.classList.remove('ws-filing-filter-open');
            toggles.forEach(function (btn) {
                btn.setAttribute('aria-expanded', 'false');
            });
        }

        function openFilter() {
            if (desktop.matches) return;
            details.setAttribute('open', '');
            document.body.classList.add('ws-filing-filter-open');
            toggles.forEach(function (btn) {
                btn.setAttribute('aria-expanded', 'true');
            });
            var closeBtn = details.querySelector('.fl-mob-filter-sheet__close');
            if (closeBtn) closeBtn.focus();
        }

        function syncFilterDetailsDesktop() {
            if (desktop.matches) {
                details.setAttribute('open', '');
                document.body.classList.remove('ws-filing-filter-open');
            } else if (!details.classList.contains('is-active')) {
                closeFilter();
            }
        }

        window.__wsCloseFilingFilter = closeFilter;

        toggles.forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                if (desktop.matches) return;
                e.preventDefault();
                if (details.hasAttribute('open')) closeFilter();
                else openFilter();
            });
        });

        details.querySelectorAll('[data-ws-filter-close]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                if (desktop.matches) return;
                e.preventDefault();
                closeFilter();
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && details.hasAttribute('open') && !desktop.matches) {
                closeFilter();
            }
        });

        if (typeof desktop.addEventListener === 'function') {
            desktop.addEventListener('change', syncFilterDetailsDesktop);
        } else if (typeof desktop.addListener === 'function') {
            desktop.addListener(syncFilterDetailsDesktop);
        }
        syncFilterDetailsDesktop();
    }

    function initFilingFilterChips() {
        document.querySelectorAll('[data-fl-filter-sync]').forEach(function (wrap) {
            var fieldName = wrap.getAttribute('data-fl-filter-sync');
            var form = document.getElementById('dsFilterForm');
            if (!form || !fieldName) return;
            var select = form.querySelector('select[name="' + fieldName + '"]');
            if (!select) return;

            function syncChipActive() {
                var val = select.value || '';
                wrap.querySelectorAll('.fl-mob-filter-chip').forEach(function (chip) {
                    var chipVal = chip.getAttribute('data-value') || '';
                    chip.classList.toggle('is-active', chipVal === val);
                });
            }

            wrap.querySelectorAll('.fl-mob-filter-chip').forEach(function (chip) {
                chip.addEventListener('click', function () {
                    select.value = chip.getAttribute('data-value') || '';
                    syncChipActive();
                });
            });

            select.addEventListener('change', syncChipActive);
            syncChipActive();
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
        initFilingFilterSheet();
        initFilingFilterChips();
        initFilterBackdropDismiss();
    });
})();
