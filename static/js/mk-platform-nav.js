/**
 * Mega menu امکانات — fixed panel + backdrop + keyboard
 */
(function () {
    'use strict';

    var btn = document.getElementById('mkFeaturesMenuBtn');
    var panel = document.getElementById('mkFeaturesMegaPanel');
    if (!btn || !panel) return;

    var backdrop = document.getElementById('mkFeaturesMegaBackdrop');
    if (!backdrop) {
        backdrop = document.createElement('button');
        backdrop.type = 'button';
        backdrop.id = 'mkFeaturesMegaBackdrop';
        backdrop.className = 'mk-mega-backdrop';
        backdrop.hidden = true;
        backdrop.setAttribute('aria-label', 'بستن منوی امکانات');
        document.body.appendChild(backdrop);
    }

    /* خارج از flex nav تا عرض محدود نشود */
    if (panel.parentElement !== document.body) {
        document.body.appendChild(panel);
    }

    function positionPanel() {
        var rect = btn.getBoundingClientRect();
        var panelWidth = Math.min(720, window.innerWidth - 24);
        var top = rect.bottom + 8;
        var left = rect.left + rect.width / 2 - panelWidth / 2;

        if (left < 12) left = 12;
        if (left + panelWidth > window.innerWidth - 12) {
            left = window.innerWidth - panelWidth - 12;
        }

        panel.style.width = panelWidth + 'px';
        panel.style.top = top + 'px';
        panel.style.left = left + 'px';
        panel.style.right = 'auto';
    }

    function openPanel() {
        positionPanel();
        panel.hidden = false;
        backdrop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        btn.closest('.mk-nav-item--mega')?.classList.add('is-open');
        document.documentElement.classList.add('mk-mega-open');
    }

    function closePanel() {
        panel.hidden = true;
        backdrop.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        btn.closest('.mk-nav-item--mega')?.classList.remove('is-open');
        document.documentElement.classList.remove('mk-mega-open');
    }

    function togglePanel() {
        if (panel.hidden) openPanel();
        else closePanel();
    }

    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        togglePanel();
    });

    backdrop.addEventListener('click', closePanel);

    document.addEventListener('click', function (e) {
        if (panel.hidden) return;
        if (panel.contains(e.target) || btn.contains(e.target)) return;
        closePanel();
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
            var first = panel.querySelector('a');
            if (first) first.focus();
        }
    });

    window.addEventListener('resize', function () {
        if (!panel.hidden) positionPanel();
    });

    window.addEventListener('scroll', function () {
        if (!panel.hidden) closePanel();
    }, { passive: true });
})();
