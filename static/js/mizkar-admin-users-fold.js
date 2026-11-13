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

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-users-fold-accordion]');
        if (root) {
            initAccordion(root);
        }
    });
})();
