(function () {
    'use strict';

    var PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

    function toPersian(num) {
        return String(num).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatCount(value, suffix) {
        var raw = '+' + value.toLocaleString('en-US') + (suffix || '');
        return toPersian(raw);
    }

    function animateCount(el) {
        var target = parseInt(el.getAttribute('data-ath-count'), 10);
        if (!target || el.dataset.athCounted === '1') return;

        el.dataset.athCounted = '1';
        var suffix = el.getAttribute('data-ath-suffix') || '';
        var duration = 1400;
        var start = performance.now();

        function tick(now) {
            var progress = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            var current = Math.round(target * eased);
            el.textContent = formatCount(current, suffix);
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    }

    function initReveal() {
        var wrap = document.querySelector('.ath-wrap');
        if (!wrap) return;

        var items = wrap.querySelectorAll('.ath-reveal');
        if (!items.length) return;

        var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function activate(el) {
            el.classList.add('is-inview');
            el.querySelectorAll('[data-ath-count]').forEach(animateCount);
        }

        if (prefersReduced || !('IntersectionObserver' in window)) {
            items.forEach(activate);
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    activate(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.12,
            rootMargin: '0px 0px -6% 0px',
        });

        items.forEach(function (el) {
            if (el.getBoundingClientRect().top < window.innerHeight * 0.92) {
                activate(el);
            } else {
                observer.observe(el);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReveal);
    } else {
        initReveal();
    }
})();
