/**
 * Mega menu امکانات — desktop keyboard + click outside
 */
(function () {
    'use strict';

    var btn = document.getElementById('mkFeaturesMenuBtn');
    var panel = document.getElementById('mkFeaturesMegaPanel');
    if (!btn || !panel) return;

    function openPanel() {
        panel.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        btn.closest('.mk-nav-item--mega')?.classList.add('is-open');
    }

    function closePanel() {
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        btn.closest('.mk-nav-item--mega')?.classList.remove('is-open');
    }

    function togglePanel() {
        if (panel.hidden) openPanel();
        else closePanel();
    }

    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        togglePanel();
    });

    document.addEventListener('click', function (e) {
        if (!panel.hidden && !panel.contains(e.target) && e.target !== btn) {
            closePanel();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !panel.hidden) {
            closePanel();
            btn.focus();
        }
    });

    btn.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' && panel.hidden) {
            e.preventDefault();
            openPanel();
            var first = panel.querySelector('a, button');
            if (first) first.focus();
        }
    });
})();
