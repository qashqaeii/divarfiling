/**
 * Market analysis landing — sticky mobile CTA
 */
(function () {
    'use strict';

    function initStickyCta() {
        var root = document.querySelector('[data-ma-root]');
        var bar = document.querySelector('[data-ma-sticky]');
        if (!root || !bar) return;

        var hero = root.querySelector('.ma-hero');
        var finalCta = root.querySelector('.ma-cta-band--final');
        var page = document.querySelector('.seo-market-page');

        function sync() {
            if (window.matchMedia('(min-width: 768px)').matches) {
                bar.hidden = true;
                bar.classList.remove('is-visible');
                if (page) page.classList.remove('has-ma-sticky');
                return;
            }

            bar.hidden = false;
            var pastHero = true;
            if (hero) {
                var hr = hero.getBoundingClientRect();
                pastHero = hr.bottom < 80;
            }
            var nearFinal = false;
            if (finalCta) {
                var fr = finalCta.getBoundingClientRect();
                nearFinal = fr.top < window.innerHeight - 24;
            }

            var show = pastHero && !nearFinal;
            bar.classList.toggle('is-visible', show);
            if (page) page.classList.toggle('has-ma-sticky', show);
        }

        var ticking = false;
        function onScroll() {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(function () {
                sync();
                ticking = false;
            });
        }

        sync();
        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', sync, { passive: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStickyCta);
    } else {
        initStickyCta();
    }
})();
