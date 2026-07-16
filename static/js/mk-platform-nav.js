/**
 * Mega menu امکانات — fixed panel, hover (desktop), keyboard nav
 * v5: fix hover flicker (backdrop was covering nav, stealing mouse events)
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
    var openMode = null; /* 'hover' | 'click' */

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

    function isInHoverZone(target) {
        if (!target) return false;
        return megaItem?.contains(target) || panel.contains(target) || btn.contains(target);
    }

    function positionPanel() {
        var rect = btn.getBoundingClientRect();
        var panelWidth = Math.min(760, window.innerWidth - 24);
        var top = rect.bottom - 2;
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

    function syncOpenClasses() {
        var root = document.documentElement;
        root.classList.toggle('mk-mega-open', isOpen);
        root.classList.toggle('mk-mega-hover', isOpen && openMode === 'hover');
    }

    function openPanel(mode) {
        clearTimeout(closeTimer);
        var nextMode = mode || 'click';

        if (isOpen) {
            if (openMode === 'click' && nextMode === 'hover') return;
            openMode = nextMode;
            positionPanel();
            syncOpenClasses();
            backdrop.hidden = openMode !== 'click';
            return;
        }

        openMode = nextMode;
        openScrollY = window.scrollY;
        positionPanel();
        panel.hidden = false;
        backdrop.hidden = openMode !== 'click';
        btn.setAttribute('aria-expanded', 'true');
        megaItem?.classList.add('is-open');
        syncOpenClasses();
        isOpen = true;
    }

    function closePanel() {
        if (!isOpen) return;
        clearTimeout(closeTimer);
        panel.hidden = true;
        backdrop.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        megaItem?.classList.remove('is-open');
        document.documentElement.classList.remove('mk-mega-open', 'mk-mega-hover');
        isOpen = false;
        openMode = null;
    }

    function scheduleClose() {
        clearTimeout(closeTimer);
        closeTimer = setTimeout(closePanel, 280);
    }

    function cancelClose() {
        clearTimeout(closeTimer);
    }

    function togglePanel() {
        if (isOpen && openMode === 'click') closePanel();
        else openPanel('click');
    }

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        togglePanel();
    });

    backdrop.addEventListener('click', closePanel);

    document.addEventListener('click', function (e) {
        if (!isOpen) return;
        if (isInHoverZone(e.target)) return;
        closePanel();
    });

    if (hoverCapable && megaItem) {
        megaItem.addEventListener('mouseenter', function () {
            openPanel('hover');
        });

        megaItem.addEventListener('mouseleave', function (e) {
            if (openMode !== 'hover') return;
            if (isInHoverZone(e.relatedTarget)) return;
            scheduleClose();
        });

        panel.addEventListener('mouseenter', function () {
            if (openMode === 'hover') cancelClose();
        });

        panel.addEventListener('mouseleave', function (e) {
            if (openMode !== 'hover') return;
            if (isInHoverZone(e.relatedTarget)) return;
            scheduleClose();
        });

        /* fallback: اگر relatedTarget null شد (backdrop قبلی)، موقعیت موس را چک کن */
        document.addEventListener('mousemove', function (e) {
            if (!isOpen || openMode !== 'hover') return;
            var hit = document.elementFromPoint(e.clientX, e.clientY);
            if (isInHoverZone(hit)) cancelClose();
        }, { passive: true });
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
            openPanel('click');
            var first = focusables()[0];
            if (first) first.focus();
        }
    });

    window.addEventListener('resize', function () {
        if (isOpen) positionPanel();
    });

    window.addEventListener('scroll', function () {
        if (!isOpen) return;
        if (Math.abs(window.scrollY - openScrollY) > 12) {
            closePanel();
        }
    }, { passive: true });
})();
