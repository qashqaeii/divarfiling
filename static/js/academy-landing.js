/**
 * Academy landing — reveal + hero stagger
 */
(function () {
    'use strict';

    function reveal() {
        var nodes = document.querySelectorAll('[data-aal-reveal]');
        if (!nodes.length) return;

        if (!('IntersectionObserver' in window)) {
            nodes.forEach(function (el) { el.classList.add('is-in'); });
            return;
        }

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-in');
                io.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });

        nodes.forEach(function (el, i) {
            if (!el.style.getPropertyValue('--aal-i')) {
                el.style.setProperty('--aal-i', String(Math.min(i % 6, 5)));
            }
            io.observe(el);
        });

        // Hero items appear immediately for first paint composition
        var hero = document.querySelector('.aal-hero');
        if (hero) {
            hero.querySelectorAll('[data-aal-reveal]').forEach(function (el, i) {
                el.style.setProperty('--aal-i', String(i));
                requestAnimationFrame(function () {
                    el.classList.add('is-in');
                });
            });
        }
    }

    function faqExclusive() {
        var root = document.querySelector('.aal-faq-list');
        if (!root) return;
        root.addEventListener('toggle', function (e) {
            var t = e.target;
            if (!t || t.tagName !== 'DETAILS' || !t.open) return;
            root.querySelectorAll('details[open]').forEach(function (d) {
                if (d !== t) d.open = false;
            });
        }, true);
    }

    function boot() {
        reveal();
        faqExclusive();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
