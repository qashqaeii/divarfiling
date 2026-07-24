/**
 * SEO landing pages — scroll reveal + image lightbox
 */
(function () {
    'use strict';

    document.documentElement.classList.add('js');

    function markVisible(el) {
        el.classList.add('is-visible');
    }

    function initReveal() {
        var els = document.querySelectorAll(
            '.seo-landing .mk-reveal, .seo-landing .mk-reveal-stagger, ' +
            '.seo-market .mk-reveal, .seo-market .mk-reveal-stagger, ' +
            '.author-page-wrap .mk-reveal, .author-page-wrap .mk-reveal-stagger'
        );
        if (!els.length) return;

        /* Hero / above-fold: show immediately */
        els.forEach(function (el) {
            var rect = el.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.92) {
                markVisible(el);
            }
        });

        if (!('IntersectionObserver' in window)) {
            els.forEach(markVisible);
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    markVisible(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -5% 0px', threshold: 0.05 });

        els.forEach(function (el) {
            if (!el.classList.contains('is-visible')) {
                observer.observe(el);
            }
        });
    }

    function initLightbox() {
        var triggers = document.querySelectorAll('[data-seo-lightbox]');
        if (!triggers.length) return;

        var lightbox = document.createElement('div');
        lightbox.className = 'seo-lightbox';
        lightbox.hidden = true;
        lightbox.innerHTML = [
            '<button type="button" class="seo-lightbox-backdrop" data-seo-lightbox-close aria-label="بستن"></button>',
            '<figure class="seo-lightbox-panel">',
            '  <button type="button" class="seo-lightbox-close" data-seo-lightbox-close aria-label="بستن"><i class="fas fa-times"></i></button>',
            '  <img class="seo-lightbox-img" alt="">',
            '  <figcaption class="seo-lightbox-caption"></figcaption>',
            '</figure>',
        ].join('');
        document.body.appendChild(lightbox);

        var img = lightbox.querySelector('.seo-lightbox-img');
        var caption = lightbox.querySelector('.seo-lightbox-caption');

        function open(src, cap) {
            img.src = src;
            img.alt = cap || '';
            caption.textContent = cap || '';
            lightbox.hidden = false;
            document.body.classList.add('seo-lightbox-open');
        }

        function close() {
            lightbox.hidden = true;
            document.body.classList.remove('seo-lightbox-open');
            img.removeAttribute('src');
        }

        triggers.forEach(function (btn) {
            btn.addEventListener('click', function () {
                open(btn.getAttribute('data-src'), btn.getAttribute('data-caption'));
            });
        });

        lightbox.querySelectorAll('[data-seo-lightbox-close]').forEach(function (el) {
            el.addEventListener('click', close);
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !lightbox.hidden) close();
        });
    }

    function initFaq() {
        var root = document.querySelector('[data-seo-faq]');
        if (!root) return;
        root.querySelectorAll('.seo-faq-item').forEach(function (item) {
            item.addEventListener('toggle', function () {
                if (!item.open) return;
                root.querySelectorAll('.seo-faq-item[open]').forEach(function (other) {
                    if (other !== item) other.open = false;
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initReveal();
            initLightbox();
            initFaq();
        });
    } else {
        initReveal();
        initLightbox();
        initFaq();
    }
})();
