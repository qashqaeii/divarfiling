/**
 * Mega menu امکانات — fixed panel, hover (desktop), keyboard nav
 */
(function () {
    'use strict';

    var btn = document.getElementById('mkFeaturesMenuBtn');
    var panel = document.getElementById('mkFeaturesMegaPanel');
    if (!btn || !panel) return;

    var megaItem = btn.closest('.mk-nav-item--mega');
    var hoverCapable = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    var closeTimer = null;

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

    if (panel.parentElement !== document.body) {
        document.body.appendChild(panel);
    }

    function focusables() {
        return Array.prototype.slice.call(
            panel.querySelectorAll('a[href], button:not([disabled])')
        );
    }

    function positionPanel() {
        var rect = btn.getBoundingClientRect();
        var panelWidth = Math.min(760, window.innerWidth - 24);
        var top = rect.bottom + 10;
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
        clearTimeout(closeTimer);
        positionPanel();
        panel.hidden = false;
        backdrop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        megaItem?.classList.add('is-open');
        document.documentElement.classList.add('mk-mega-open');
    }

    function closePanel() {
        panel.hidden = true;
        backdrop.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        megaItem?.classList.remove('is-open');
        document.documentElement.classList.remove('mk-mega-open');
    }

    function scheduleClose() {
        clearTimeout(closeTimer);
        closeTimer = setTimeout(closePanel, 180);
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

    if (hoverCapable && megaItem) {
        megaItem.addEventListener('mouseenter', openPanel);
        megaItem.addEventListener('mouseleave', scheduleClose);
        panel.addEventListener('mouseenter', function () { clearTimeout(closeTimer); });
        panel.addEventListener('mouseleave', scheduleClose);
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !panel.hidden) {
            closePanel();
            btn.focus();
            return;
        }

        if (panel.hidden || !panel.contains(document.activeElement)) return;

        var links = focusables();
        var idx = links.indexOf(document.activeElement);

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            var next = links[idx + 1] || links[0];
            if (next) next.focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            var prev = links[idx - 1] || links[links.length - 1];
            if (prev) prev.focus();
        } else if (e.key === 'Home') {
            e.preventDefault();
            if (links[0]) links[0].focus();
        } else if (e.key === 'End') {
            e.preventDefault();
            if (links.length) links[links.length - 1].focus();
        }
    });

    btn.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' && panel.hidden) {
            e.preventDefault();
            openPanel();
            var first = focusables()[0];
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
