(function () {
    'use strict';

    function initFooterReveal() {
        var footer = document.querySelector('.mk-footer-v2');
        if (!footer) return;

        var items = footer.querySelectorAll('.mk-ft-reveal');
        if (!items.length) return;

        var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReduced || !('IntersectionObserver' in window)) {
            items.forEach(function (el) {
                el.classList.add('is-inview');
            });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-inview');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.12,
            rootMargin: '0px 0px -5% 0px',
        });

        items.forEach(function (el, index) {
            if (!el.style.getPropertyValue('--ft-delay')) {
                el.style.setProperty('--ft-delay', String(index));
            }
            observer.observe(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFooterReveal);
    } else {
        initFooterReveal();
    }
})();
