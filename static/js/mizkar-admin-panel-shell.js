(function () {
    'use strict';

    var MOBILE_SIDEBAR_MQ = '(max-width: 1024px)';

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function qsa(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function initSidebarGroups() {
        qsa('.ecc-nav-group-toggle').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var group = btn.closest('.ecc-nav-group');
                if (!group) return;
                var open = group.classList.toggle('is-open');
                btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        });
    }

    function initMobileSidebar() {
        var sidebar = qs('#ecc-sidebar');
        var backdrop = qs('#ecc-sidebar-backdrop');
        var openBtn = qs('#ecc-sidebar-toggle');
        var closeBtn = qs('#ecc-sidebar-close');
        if (!sidebar) return;

        var mq = window.matchMedia(MOBILE_SIDEBAR_MQ);

        function isMobile() {
            return mq.matches;
        }

        function isOpen() {
            return document.body.classList.contains('ecc-sidebar-open');
        }

        function open() {
            if (!isMobile()) return;
            document.body.classList.add('ecc-sidebar-open');
            sidebar.setAttribute('aria-hidden', 'false');
            if (openBtn) {
                openBtn.setAttribute('aria-expanded', 'true');
                openBtn.setAttribute('aria-label', 'بستن منو');
            }
            if (backdrop) backdrop.setAttribute('aria-hidden', 'false');
            if (closeBtn) {
                window.requestAnimationFrame(function () {
                    if (isOpen()) closeBtn.focus();
                });
            }
        }

        function close(restoreFocus) {
            var wasOpen = isOpen();
            // Never leave focus on a link that becomes hidden in the drawer.
            if (wasOpen && sidebar.contains(document.activeElement) && openBtn) {
                openBtn.focus();
            }
            document.body.classList.remove('ecc-sidebar-open');
            if (openBtn) {
                openBtn.setAttribute('aria-expanded', 'false');
                openBtn.setAttribute('aria-label', 'باز کردن منو');
            }
            if (backdrop) backdrop.setAttribute('aria-hidden', 'true');
            if (isMobile()) {
                sidebar.setAttribute('aria-hidden', 'true');
            } else {
                sidebar.removeAttribute('aria-hidden');
            }
            if (restoreFocus && wasOpen && openBtn) openBtn.focus();
        }

        function syncLayout() {
            if (isMobile()) {
                sidebar.setAttribute('aria-hidden', document.body.classList.contains('ecc-sidebar-open') ? 'false' : 'true');
            } else {
                close(false);
                sidebar.removeAttribute('aria-hidden');
            }
        }

        if (openBtn) openBtn.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', function () { close(true); });
        if (backdrop) backdrop.addEventListener('click', function () { close(true); });

        qsa('.ecc-nav-item', sidebar).forEach(function (item) {
            item.addEventListener('click', function () {
                if (isMobile()) close(false);
            });
        });

        document.addEventListener('keydown', function (event) {
            if (!isMobile() || !isOpen()) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                close(true);
                return;
            }
            if (event.key !== 'Tab') return;
            var focusable = qsa(
                'a[href], button:not([disabled]), input:not([disabled]), [tabindex="0"]',
                sidebar
            ).filter(function (el) {
                return el.getClientRects().length > 0;
            });
            if (!focusable.length) return;
            var first = focusable[0];
            var last = focusable[focusable.length - 1];
            if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
                event.preventDefault();
                first.focus();
            }
        });

        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', syncLayout);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(syncLayout);
        }

        syncLayout();
    }

    function initCompareToggle() {
        var toggle = qs('#ecc-compare-toggle');
        if (!toggle) return;

        toggle.addEventListener('change', function () {
            var url = new URL(window.location.href);
            if (toggle.checked) {
                url.searchParams.set('compare', '1');
            } else {
                url.searchParams.delete('compare');
            }
            window.location.href = url.toString();
        });
    }

    function initRefresh() {
        var btn = qs('#ecc-refresh-btn');
        if (!btn || btn.dataset.shellRefreshBound) return;
        btn.dataset.shellRefreshBound = '1';
        btn.addEventListener('click', function () {
            btn.classList.add('is-loading');
            window.location.reload();
        });
    }

    function initDetailsDeepLinks() {
        // The financial integrity report stays folded until explicitly opened.
        function revealHashTarget() {
            var id = decodeURIComponent(window.location.hash.slice(1));
            if (!id) return;
            var target = document.getElementById(id);
            if (!target) return;
            var details = target.tagName === 'DETAILS' ? target : target.closest('details');
            if (details && !details.open) details.open = true;
        }
        window.addEventListener('hashchange', revealHashTarget);
        revealHashTarget();
    }

    function init() {
        initSidebarGroups();
        initMobileSidebar();
        initCompareToggle();
        initRefresh();
        initDetailsDeepLinks();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
