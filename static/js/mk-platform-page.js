/**
 * Platform page — subtle scroll reveal (respects reduced motion)
 */
(function () {
    'use strict';

    var root = document.querySelector('.plat-page');
    if (!root) return;

    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
        root.querySelectorAll('.plat-reveal').forEach(function (el) {
            el.classList.add('is-visible');
        });
        return;
    }

    var items = root.querySelectorAll('.plat-reveal');
    if (!items.length || !('IntersectionObserver' in window)) {
        items.forEach(function (el) { el.classList.add('is-visible'); });
        return;
    }

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    items.forEach(function (el) { observer.observe(el); });
})();
