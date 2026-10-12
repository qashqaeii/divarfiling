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
        var sheet = document.getElementById('wsFilingHubFilterSheet');
        var form = document.getElementById('dsFilterForm');
        if (!sheet || !form) return;

        var desktop = window.matchMedia('(min-width: 769px)');

        function closeFilterSheet() {
            sheet.classList.remove('is-open');
            if (!desktop.matches) {
                sheet.hidden = true;
                sheet.setAttribute('aria-hidden', 'true');
            }
            document.body.classList.remove('ws-filing-filter-open');
            var toggle = document.querySelector('[data-ws-mob-filter-toggle]');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }

        function openFilterSheet() {
            if (desktop.matches) return;
            sheet.hidden = false;
            sheet.classList.add('is-open');
            sheet.setAttribute('aria-hidden', 'false');
            document.body.classList.add('ws-filing-filter-open');
            var toggle = document.querySelector('[data-ws-mob-filter-toggle]');
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
            var closeBtn = sheet.querySelector('[data-ws-filing-hub-filter-close].ws-mob-sheet-close');
            if (closeBtn) closeBtn.focus();
        }

        window.__wsCloseFilingFilter = closeFilterSheet;

        function syncFilterDesktop() {
            if (desktop.matches) {
                sheet.hidden = true;
                sheet.setAttribute('aria-hidden', 'true');
                sheet.classList.remove('is-open');
                document.body.classList.remove('ws-filing-filter-open');
                var toggle = document.querySelector('[data-ws-mob-filter-toggle]');
                if (toggle) toggle.setAttribute('aria-expanded', 'false');
            } else {
                sheet.classList.remove('is-open');
                sheet.hidden = true;
                sheet.setAttribute('aria-hidden', 'true');
                document.body.classList.remove('ws-filing-filter-open');
                var toggleMob = document.querySelector('[data-ws-mob-filter-toggle]');
                if (toggleMob) toggleMob.setAttribute('aria-expanded', 'false');
            }
        }

        syncFilterDesktop();
        if (typeof desktop.addEventListener === 'function') {
            desktop.addEventListener('change', syncFilterDesktop);
        } else if (typeof desktop.addListener === 'function') {
            desktop.addListener(syncFilterDesktop);
        }

        document.querySelectorAll('[data-ws-mob-filter-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                if (desktop.matches) return;
                if (sheet.classList.contains('is-open')) closeFilterSheet();
                else openFilterSheet();
            });
        });

        sheet.querySelectorAll('[data-ws-filing-hub-filter-close]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                if (desktop.matches) return;
                e.preventDefault();
                closeFilterSheet();
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sheet.classList.contains('is-open') && !desktop.matches) {
                closeFilterSheet();
            }
        });

        form.addEventListener('submit', function () {
            if (!desktop.matches) closeFilterSheet();
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

    function initDatasetDetailStatsSheet() {
        var sheet = document.getElementById('wsFilingDdStatsSheet');
        if (!sheet) return;

        function closeSheet() {
            sheet.hidden = true;
            sheet.classList.remove('is-open');
            sheet.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('ws-filing-dd-stats-open');
        }

        function openSheet() {
            sheet.hidden = false;
            sheet.classList.add('is-open');
            sheet.setAttribute('aria-hidden', 'false');
            document.body.classList.add('ws-filing-dd-stats-open');
            var closeBtn = sheet.querySelector('[data-ws-dd-stats-close].ws-filing-sort-sheet__close');
            if (closeBtn) closeBtn.focus();
        }

        document.querySelectorAll('[data-ds-stats-open]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelectorAll('.fl-dd-mob-more[open]').forEach(function (m) {
                    m.removeAttribute('open');
                });
                if (sheet.classList.contains('is-open')) closeSheet();
                else openSheet();
            });
        });

        sheet.querySelectorAll('[data-ws-dd-stats-close]').forEach(function (el) {
            el.addEventListener('click', closeSheet);
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sheet.classList.contains('is-open')) closeSheet();
        });
    }

    function initDatasetRenameFromHub() {
        var modal = document.getElementById('modal-rename');
        var form = document.getElementById('wsDatasetRenameForm');
        if (!modal || !form) return;

        var urlTemplate = form.getAttribute('data-rename-url-template') || '';
        var nameInput = document.getElementById('wsDatasetRenameName');
        var nextInput = document.getElementById('wsDatasetRenameNext');
        var placeholder = '00000000-0000-0000-0000-000000000000';

        function openRenameModal(datasetId, datasetName) {
            if (!datasetId || !urlTemplate) return;
            form.action = urlTemplate.replace(placeholder, datasetId);
            if (nameInput) {
                nameInput.value = datasetName || '';
            }
            if (nextInput) {
                nextInput.value = window.location.pathname + window.location.search;
            }
            document.querySelectorAll('.fl-row-menu[open], .mk-ds-card-menu[open], .fl-gcard__menu[open]').forEach(function (m) {
                m.removeAttribute('open');
            });
            if (typeof window.WSModal !== 'undefined') {
                window.WSModal.open('modal-rename');
            } else {
                modal.classList.add('is-open');
                document.body.classList.add('ws-modal-open');
            }
            if (nameInput) {
                setTimeout(function () {
                    nameInput.focus();
                    nameInput.select();
                }, 120);
            }
        }

        document.querySelectorAll('[data-ds-rename-open]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                openRenameModal(btn.getAttribute('data-dataset-id'), btn.getAttribute('data-dataset-name'));
            });
        });
    }

    function initDatasetCardMenus() {
        document.querySelectorAll('.mk-ds-card-check').forEach(function (label) {
            label.addEventListener('click', function (e) {
                e.stopPropagation();
            });
            var input = label.querySelector('input[type="checkbox"]');
            if (input) {
                input.addEventListener('click', function (e) {
                    e.stopPropagation();
                });
            }
        });

        document.querySelectorAll('.mk-ds-card-menu').forEach(function (menu) {
            var summary = menu.querySelector('summary');
            if (summary) {
                summary.addEventListener('click', function (e) {
                    e.stopPropagation();
                });
            }

            menu.addEventListener('toggle', function () {
                if (!menu.open) return;
                document.querySelectorAll('.mk-ds-card-menu[open]').forEach(function (other) {
                    if (other !== menu) other.removeAttribute('open');
                });
            });
        });

        document.addEventListener('click', function (e) {
            if (e.target.closest('.mk-ds-card-menu')) return;
            document.querySelectorAll('.mk-ds-card-menu[open]').forEach(function (menu) {
                menu.removeAttribute('open');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initFilingSearchClear();
        initFilingSortSheet();
        initFilterBackdropDismiss();
        initDatasetFilterSheet();
        initDatasetDetailStatsSheet();
        initDatasetRenameFromHub();
        initDatasetCardMenus();
    });
})();
