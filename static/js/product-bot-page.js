(function () {
    'use strict';

    function initReveal() {
        var els = document.querySelectorAll('.pbp-reveal');
        if (!els.length) return;

        if (!('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('is-inview'); });
            return;
        }

        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-inview');
                obs.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });

        els.forEach(function (el) { obs.observe(el); });
    }

    function initStickyNav() {
        var nav = document.querySelector('.pbp-sticky-nav');
        if (!nav) return;

        var links = nav.querySelectorAll('.pbp-sticky-nav__link[data-pbp-nav]');
        var sections = [];
        links.forEach(function (link) {
            var id = link.getAttribute('href');
            if (!id || id.charAt(0) !== '#') return;
            var el = document.querySelector(id);
            if (el) sections.push({ id: id.slice(1), nav: link.dataset.pbpNav, el: el });
        });

        if (!sections.length || !('IntersectionObserver' in window)) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var match = sections.find(function (s) { return s.el === entry.target; });
                if (!match) return;
                links.forEach(function (link) {
                    link.classList.toggle('is-active', link.dataset.pbpNav === match.nav);
                });
            });
        }, {
            rootMargin: '-38% 0px -48% 0px',
            threshold: 0,
        });

        sections.forEach(function (s) { observer.observe(s.el); });

        links.forEach(function (link) {
            link.addEventListener('click', function () {
                links.forEach(function (l) { l.classList.remove('is-active'); });
                link.classList.add('is-active');
            });
        });
    }

    function updateStickyTop() {
        var header = document.querySelector('.mk-site-header');
        if (!header) return;
        var top = Math.ceil(header.getBoundingClientRect().height);
        document.documentElement.style.setProperty('--pbp-sticky-top', top + 'px');
    }

    document.addEventListener('DOMContentLoaded', function () {
        updateStickyTop();
        window.addEventListener('resize', updateStickyTop, { passive: true });
        initReveal();
        initStickyNav();
    });
})();
