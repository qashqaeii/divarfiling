(function () {
    'use strict';

    var MOBILE_SIDEBAR_MQ = '(max-width: 1024px)';

    var SECTION_NAV_MAP = {
        'ecc-command': 'command',
        'ecc-glance': 'command',
        'ecc-charts': 'growth',
        'ecc-growth': 'growth',
        'ecc-summary': 'users',
        'ecc-today': 'command'
    };

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

        function open() {
            if (!isMobile()) return;
            document.body.classList.add('ecc-sidebar-open');
            sidebar.setAttribute('aria-hidden', 'false');
            if (openBtn) openBtn.setAttribute('aria-expanded', 'true');
            if (backdrop) backdrop.setAttribute('aria-hidden', 'false');
            if (closeBtn) {
                window.requestAnimationFrame(function () {
                    closeBtn.focus();
                });
            }
        }

        function close() {
            document.body.classList.remove('ecc-sidebar-open');
            if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
            if (backdrop) backdrop.setAttribute('aria-hidden', 'true');
            if (isMobile()) {
                sidebar.setAttribute('aria-hidden', 'true');
            } else {
                sidebar.removeAttribute('aria-hidden');
            }
        }

        function syncLayout() {
            if (isMobile()) {
                sidebar.setAttribute('aria-hidden', document.body.classList.contains('ecc-sidebar-open') ? 'false' : 'true');
            } else {
                close();
                sidebar.removeAttribute('aria-hidden');
            }
        }

        if (openBtn) openBtn.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (backdrop) backdrop.addEventListener('click', close);

        qsa('.ecc-nav-item', sidebar).forEach(function (item) {
            item.addEventListener('click', function () {
                if (isMobile()) close();
            });
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && document.body.classList.contains('ecc-sidebar-open')) {
                close();
                if (openBtn) openBtn.focus();
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

    function setActiveNav(navId) {
        if (!navId) return;
        qsa('.ecc-nav-item[data-nav-id]').forEach(function (item) {
            item.classList.toggle('is-active', item.getAttribute('data-nav-id') === navId);
        });
    }

    function hashFromHref(href) {
        if (!href) return '';
        var hashIndex = href.indexOf('#');
        return hashIndex >= 0 ? href.slice(hashIndex) : '';
    }

    function initDashboardNavigation() {
        var sections = qsa('.ecc-main .ecc-section[id]').map(function (el) { return el.id; });
        if (!sections.length) return;

        qsa('.ecc-nav-item[data-nav-id]').forEach(function (item) {
            item.addEventListener('click', function () {
                var hash = hashFromHref(item.getAttribute('href'));
                var sectionId = hash.replace('#', '');
                var navId = SECTION_NAV_MAP[sectionId] || item.getAttribute('data-nav-id');
                if (navId) setActiveNav(navId);
            });
        });

        function onScroll() {
            var current = sections[0];
            sections.forEach(function (id) {
                var el = document.getElementById(id);
                if (el && el.getBoundingClientRect().top <= 140) {
                    current = id;
                }
            });
            var navId = SECTION_NAV_MAP[current] || 'command';
            setActiveNav(navId);
        }

        window.addEventListener('scroll', onScroll, { passive: true });

        var initialHash = window.location.hash.replace('#', '');
        if (initialHash && SECTION_NAV_MAP[initialHash]) {
            setActiveNav(SECTION_NAV_MAP[initialHash]);
        } else if (qs('.ecc-nav-item[data-nav-id="command"]')) {
            setActiveNav('command');
        }

        onScroll();
    }

    function init() {
        initSidebarGroups();
        initMobileSidebar();
        initCompareToggle();
        initRefresh();
        initDashboardNavigation();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
