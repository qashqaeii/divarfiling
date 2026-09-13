(function () {
    'use strict';

    var PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

    function toPersian(num) {
        return String(num).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatCount(value) {
        return toPersian(value.toLocaleString('en-US'));
    }

    function animateCount(el) {
        var target = parseInt(el.getAttribute('data-ath-count'), 10);
        if (!target || el.dataset.athCounted === '1') return;

        el.dataset.athCounted = '1';
        var duration = 1400;
        var start = performance.now();

        function tick(now) {
            var progress = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            var current = Math.round(target * eased);
            el.textContent = formatCount(current);
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
            var counter = el.querySelector('[data-ath-count]');
            if (counter) {
                animateCount(counter);
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

    function initLightbox() {
        var triggers = document.querySelectorAll('[data-ath-lightbox]');
        if (!triggers.length) return;

        var lightbox = document.createElement('div');
        lightbox.className = 'ath-lightbox';
        lightbox.hidden = true;
        lightbox.innerHTML = [
            '<button type="button" class="ath-lightbox-backdrop" data-ath-lightbox-close aria-label="بستن"></button>',
            '<figure class="ath-lightbox-panel">',
            '  <button type="button" class="ath-lightbox-close" data-ath-lightbox-close aria-label="بستن"><i class="fas fa-times"></i></button>',
            '  <img class="ath-lightbox-img" alt="">',
            '  <figcaption class="ath-lightbox-caption"></figcaption>',
            '</figure>',
        ].join('');
        document.body.appendChild(lightbox);

        var img = lightbox.querySelector('.ath-lightbox-img');
        var caption = lightbox.querySelector('.ath-lightbox-caption');

        function open(src, cap) {
            img.src = src;
            img.alt = cap || '';
            caption.textContent = cap || '';
            lightbox.hidden = false;
            document.body.classList.add('ath-lightbox-open');
        }

        function close() {
            lightbox.hidden = true;
            document.body.classList.remove('ath-lightbox-open');
            img.removeAttribute('src');
        }

        triggers.forEach(function (btn) {
            btn.addEventListener('click', function () {
                open(btn.getAttribute('data-src'), btn.getAttribute('data-caption'));
            });
        });

        lightbox.querySelectorAll('[data-ath-lightbox-close]').forEach(function (el) {
            el.addEventListener('click', close);
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !lightbox.hidden) close();
        });
    }

    function init() {
        initReveal();
        initLightbox();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
