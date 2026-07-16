/**
 * Mega menu امکانات — fixed panel, hover (desktop), keyboard nav
 * v4: fix page jump (no overflow lock, smart scroll close, hover bridge)
 */
(function () {
    'use strict';

    var btn = document.getElementById('mkFeaturesMenuBtn');
    var panel = document.getElementById('mkFeaturesMegaPanel');
    if (!btn || !panel) return;

    var megaItem = btn.closest('.mk-nav-item--mega');
    var hoverCapable = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    var closeTimer = null;
    var openScrollY = 0;
    var isOpen = false;

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
        var top = rect.bottom + 4;
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
        if (isOpen) return;
        clearTimeout(closeTimer);
        openScrollY = window.scrollY;
        positionPanel();
        panel.hidden = false;
        backdrop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        megaItem?.classList.add('is-open');
        document.documentElement.classList.add('mk-mega-open');
        isOpen = true;
    }

    function closePanel() {
        if (!isOpen) return;
        clearTimeout(closeTimer);
        panel.hidden = true;
        backdrop.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        megaItem?.classList.remove('is-open');
        document.documentElement.classList.remove('mk-mega-open');
        isOpen = false;
    }

    function scheduleClose() {
        clearTimeout(closeTimer);
        closeTimer = setTimeout(closePanel, 220);
    }

    function cancelClose() {
        clearTimeout(closeTimer);
    }

    function togglePanel() {
        if (isOpen) closePanel();
        else openPanel();
    }

    function isMovingToPanel(e) {
        var target = e.relatedTarget;
        return target && (panel.contains(target) || btn.contains(target));
    }

    function isMovingToTrigger(e) {
        var target = e.relatedTarget;
        return target && (megaItem?.contains(target) || btn.contains(target));
    }

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        togglePanel();
    });

    backdrop.addEventListener('click', closePanel);

    document.addEventListener('click', function (e) {
        if (!isOpen) return;
        if (panel.contains(e.target) || btn.contains(e.target)) return;
        closePanel();
    });

    if (hoverCapable && megaItem) {
        megaItem.addEventListener('mouseenter', openPanel);
        megaItem.addEventListener('mouseleave', function (e) {
            if (isMovingToPanel(e)) return;
            scheduleClose();
        });
        panel.addEventListener('mouseenter', cancelClose);
        panel.addEventListener('mouseleave', function (e) {
            if (isMovingToTrigger(e)) return;
            scheduleClose();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && isOpen) {
            closePanel();
            btn.focus();
            return;
        }

        if (!isOpen || !panel.contains(document.activeElement)) return;

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
        if (e.key === 'ArrowDown' && !isOpen) {
            e.preventDefault();
            openPanel();
            var first = focusables()[0];
            if (first) first.focus();
        }
    });

    window.addEventListener('resize', function () {
        if (isOpen) positionPanel();
    });

    /* فقط اسکرول واقعی کاربر — نه layout shift از باز شدن منو */
    window.addEventListener('scroll', function () {
        if (!isOpen) return;
        if (Math.abs(window.scrollY - openScrollY) > 12) {
            closePanel();
        }
    }, { passive: true });
})();
