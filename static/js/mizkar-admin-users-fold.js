(function () {
    'use strict';

    var DESKTOP_MQ = window.matchMedia('(min-width: 900px)');

    function setPanelOpen(panel, open) {
        var body = panel.querySelector('[data-users-fold-body]');
        var trigger = panel.querySelector('[data-users-fold-trigger]');
        if (!body || !trigger) {
            return;
        }
        panel.classList.toggle('is-open', open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (DESKTOP_MQ.matches) {
            body.hidden = !open;
        } else {
            body.hidden = false;
        }
    }

    function applyDesktopDefaults(root) {
        root.querySelectorAll('[data-users-fold-panel]').forEach(function (panel) {
            var defaultOpen = panel.getAttribute('data-fold-open') === '1';
            setPanelOpen(panel, defaultOpen);
        });
    }

    function expandAll(root) {
        root.querySelectorAll('[data-users-fold-panel]').forEach(function (panel) {
            setPanelOpen(panel, true);
        });
    }

    function initAccordion(root) {
        root.classList.add('is-accordion-ready');

        root.querySelectorAll('[data-users-fold-trigger]').forEach(function (trigger) {
            trigger.addEventListener('click', function () {
                if (!DESKTOP_MQ.matches) {
                    return;
                }
                var panel = trigger.closest('[data-users-fold-panel]');
                if (!panel) {
                    return;
                }
                setPanelOpen(panel, !panel.classList.contains('is-open'));
            });
        });

        function syncLayout() {
            if (DESKTOP_MQ.matches) {
                applyDesktopDefaults(root);
            } else {
                expandAll(root);
            }
        }

        syncLayout();

        if (typeof DESKTOP_MQ.addEventListener === 'function') {
            DESKTOP_MQ.addEventListener('change', syncLayout);
        } else if (typeof DESKTOP_MQ.addListener === 'function') {
            DESKTOP_MQ.addListener(syncLayout);
        }
    }

    function profileHrefForRow(row) {
        var fromData = row.getAttribute('data-u360-href');
        if (fromData) {
            return fromData;
        }
        var link = row.querySelector('a.adm-user-360-link, a.ecc-users-mgmt-user-link');
        return link && link.href ? link.href : '';
    }

    function navigateProfileRow(row) {
        var href = profileHrefForRow(row);
        if (href) {
            window.location.href = href;
        }
    }

    function initProfileRowNav(root) {
        root.addEventListener('click', function (event) {
            if (event.target.closest('a, button, input, select, label')) {
                return;
            }
            var row = event.target.closest('tr.adm-users-row--profile[data-user-id]');
            if (!row) {
                return;
            }
            navigateProfileRow(row);
        });

        root.addEventListener('keydown', function (event) {
            if (event.key !== 'Enter' && event.key !== ' ') {
                return;
            }
            var row = event.target.closest('tr.adm-users-row--profile[data-user-id]');
            if (!row || !row.hasAttribute('tabindex')) {
                return;
            }
            if (event.target.closest('a, button, input, select, label')) {
                return;
            }
            event.preventDefault();
            navigateProfileRow(row);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var page = document.querySelector('.adm-users-page');
        if (!page) {
            return;
        }
        var accordion = page.querySelector('[data-users-fold-accordion]');
        if (accordion) {
            initAccordion(accordion);
            initProfileRowNav(accordion);
        } else {
            initProfileRowNav(page);
        }
    });
})();
