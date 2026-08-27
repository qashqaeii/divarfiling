(function () {
    'use strict';

    var SECTION_NAV_MAP = {
        'ecc-command': 'command',
        'ecc-glance': 'command',
        'ecc-growth': 'growth',
        'ecc-revenue': 'sales',
        'ecc-sales': 'sales',
        'ecc-recovery': 'recovery',
        'ecc-marketing': 'marketing',
        'ecc-plan-conversion': 'plan_conversion',
        'ecc-users': 'users',
        'ecc-licensing': 'licenses',
        'ecc-crm': 'crm',
        'ecc-operations': 'operations',
        'ecc-support': 'support',
        'ecc-blog': 'blog',
        'ecc-academy': 'academy',
        'ecc-activity': 'activity',
        'ecc-windows': 'windows',
        'ecc-affiliates': 'affiliates',
        'ecc-exports': 'exports'
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

        function open() {
            document.body.classList.add('ecc-sidebar-open');
            if (backdrop) backdrop.hidden = false;
        }

        function close() {
            document.body.classList.remove('ecc-sidebar-open');
            if (backdrop) backdrop.hidden = true;
        }

        if (openBtn) openBtn.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);
        if (backdrop) backdrop.addEventListener('click', close);

        qsa('.ecc-nav-item', sidebar).forEach(function (item) {
            item.addEventListener('click', function () {
                if (window.matchMedia('(max-width: 960px)').matches) {
                    close();
                }
            });
        });
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
