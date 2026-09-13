(function () {
    'use strict';

    var PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

    function toPersian(num) {
        return String(num).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatCount(value, el) {
        var prefix = el.getAttribute('data-abt-prefix') || '';
        var suffix = el.getAttribute('data-abt-suffix') || '';
        var raw = prefix + value + suffix;
        if (el.getAttribute('data-abt-persian') !== '0') {
            return toPersian(raw);
        }
        return raw;
    }

    function animateCount(el) {
        var target = parseInt(el.getAttribute('data-abt-count'), 10);
        if (!target || el.dataset.abtCounted === '1') return;

        var strong = el.querySelector('strong');
        if (!strong) return;

        el.dataset.abtCounted = '1';
        var duration = 1400;
        var start = performance.now();

        function tick(now) {
            var progress = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            var current = Math.round(target * eased);
            strong.textContent = formatCount(current, el);
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    }

    function initReveal() {
        var wrap = document.querySelector('.abt-wrap');
        if (!wrap) return;

        var items = wrap.querySelectorAll('.abt-reveal');
        if (!items.length) return;

        var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function activate(el) {
            el.classList.add('is-inview');
            if (el.hasAttribute('data-abt-count')) {
                animateCount(el);
            }
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
            threshold: 0.15,
            rootMargin: '0px 0px -6% 0px',
        });

        items.forEach(function (el) {
            observer.observe(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReveal);
    } else {
        initReveal();
    }
})();
