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

    function initDatasetFilterSheet() {
        var details = document.getElementById('dsFilterDetails');
        var form = document.getElementById('dsFilterForm');
        if (!details || !form) return;

        var desktop = window.matchMedia('(min-width: 768px)');

        function closeFilterSheet() {
            details.removeAttribute('open');
            details.classList.remove('is-open');
            document.body.classList.remove('ws-filing-filter-open');
            var toggle = document.querySelector('[data-ws-mob-filter-toggle]');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }

        function openFilterSheet() {
            if (desktop.matches) return;
            details.setAttribute('open', '');
            details.classList.add('is-open');
            document.body.classList.add('ws-filing-filter-open');
            var toggle = document.querySelector('[data-ws-mob-filter-toggle]');
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
            var closeBtn = details.querySelector('.fl-mob-filter-sheet__close');
            if (closeBtn) closeBtn.focus();
        }

        window.__wsCloseFilingFilter = closeFilterSheet;

        function syncFilterDetailsDesktop() {
            if (desktop.matches) {
                details.setAttribute('open', '');
                document.body.classList.remove('ws-filing-filter-open');
            } else if (!details.classList.contains('is-open')) {
                details.removeAttribute('open');
            }
        }

        syncFilterDetailsDesktop();
        if (typeof desktop.addEventListener === 'function') {
            desktop.addEventListener('change', syncFilterDetailsDesktop);
        } else if (typeof desktop.addListener === 'function') {
            desktop.addListener(syncFilterDetailsDesktop);
        }

        document.querySelectorAll('[data-ws-mob-filter-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                if (desktop.matches) return;
                if (details.hasAttribute('open')) closeFilterSheet();
                else openFilterSheet();
            });
        });

        details.querySelectorAll('[data-ws-filter-close]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                if (desktop.matches) return;
                e.preventDefault();
                closeFilterSheet();
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && details.hasAttribute('open') && !desktop.matches) {
                closeFilterSheet();
            }
        });

        document.querySelectorAll('[data-fl-filter-sync]').forEach(function (group) {
            var fieldName = group.getAttribute('data-fl-filter-sync');
            var select = form.querySelector('select[name="' + fieldName + '"]');
            if (!select) return;

            group.querySelectorAll('.fl-mob-filter-chip').forEach(function (chip) {
                chip.addEventListener('click', function () {
                    var value = chip.getAttribute('data-value') || '';
                    select.value = value;
                    group.querySelectorAll('.fl-mob-filter-chip').forEach(function (c) {
                        c.classList.toggle('is-active', c === chip);
                    });
                });
            });

            select.addEventListener('change', function () {
                var val = select.value;
                group.querySelectorAll('.fl-mob-filter-chip').forEach(function (chip) {
                    chip.classList.toggle('is-active', (chip.getAttribute('data-value') || '') === val);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initFilingSearchClear();
        initFilingSortSheet();
        initFilterBackdropDismiss();
        initDatasetFilterSheet();
    });
})();
