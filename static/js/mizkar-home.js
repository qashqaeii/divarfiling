(function () {
    'use strict';

    var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ─── Scroll reveal ─── */
    function initReveal() {
        var els = document.querySelectorAll('.mk-reveal, .mk-reveal-stagger');
        if (!els.length) return;

        if (prefersReduced || !('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('is-visible'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

        els.forEach(function (el) { observer.observe(el); });
    }

    /* ─── Showcase slider ─── */
    function initShowcase() {
        var root = document.querySelector('[data-showcase]');
        if (!root) return;

        var track = root.querySelector('[data-showcase-track]');
        var slides = root.querySelectorAll('[data-showcase-slide]');
        var dotsWrap = root.querySelector('[data-showcase-dots]');
        var prevBtn = root.querySelector('[data-showcase-prev]');
        var nextBtn = root.querySelector('[data-showcase-next]');

        if (!track || !slides.length) return;

        var index = 0;
        var total = slides.length;
        var autoplayTimer = null;
        var isPaused = false;
        var touchStartX = 0;

        slides[0].classList.add('is-active');

        slides.forEach(function (_, i) {
            var dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'mk-showcase-dot' + (i === 0 ? ' is-active' : '');
            dot.setAttribute('aria-label', 'اسلاید ' + (i + 1));
            dot.setAttribute('role', 'tab');
            dot.addEventListener('click', function () { goTo(i); });
            dotsWrap.appendChild(dot);
        });

        var dots = dotsWrap.querySelectorAll('.mk-showcase-dot');

        function goTo(i) {
            index = ((i % total) + total) % total;
            track.style.transform = 'translateX(-' + (index * 100) + '%)';

            slides.forEach(function (s, j) {
                s.classList.toggle('is-active', j === index);
            });
            dots.forEach(function (d, j) {
                d.classList.toggle('is-active', j === index);
            });
        }

        function next() { goTo(index + 1); }
        function prev() { goTo(index - 1); }

        function startAutoplay() {
            if (prefersReduced) return;
            stopAutoplay();
            autoplayTimer = setInterval(function () {
                if (!isPaused) next();
            }, 5500);
        }

        function stopAutoplay() {
            if (autoplayTimer) clearInterval(autoplayTimer);
        }

        if (prevBtn) prevBtn.addEventListener('click', function () { prev(); startAutoplay(); });
        if (nextBtn) nextBtn.addEventListener('click', function () { next(); startAutoplay(); });

        root.addEventListener('mouseenter', function () { isPaused = true; });
        root.addEventListener('mouseleave', function () { isPaused = false; });

        root.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowLeft') { next(); startAutoplay(); }
            if (e.key === 'ArrowRight') { prev(); startAutoplay(); }
        });

        root.addEventListener('touchstart', function (e) {
            touchStartX = e.changedTouches[0].screenX;
        }, { passive: true });

        root.addEventListener('touchend', function (e) {
            var diff = touchStartX - e.changedTouches[0].screenX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) next();
                else prev();
                startAutoplay();
            }
        }, { passive: true });

        /* RTL: track moves positive for next slide */
        track.style.direction = 'ltr';
        slides.forEach(function (s) { s.style.direction = 'rtl'; });

        startAutoplay();
    }

    /* ─── FAQ: single open ─── */
    function initFaq() {
        var faq = document.querySelector('[data-faq]');
        if (!faq) return;

        faq.querySelectorAll('.mk-faq-item').forEach(function (item) {
            item.addEventListener('toggle', function () {
                if (!item.open) return;
                faq.querySelectorAll('.mk-faq-item').forEach(function (other) {
                    if (other !== item) other.open = false;
                });
            });
        });
    }

    /* ─── City marquee pause on hover ─── */
    function initCityMarquee() {
        var marquee = document.querySelector('[data-city-marquee]');
        if (!marquee) return;
        marquee.addEventListener('mouseenter', function () { marquee.classList.add('is-paused'); });
        marquee.addEventListener('mouseleave', function () { marquee.classList.remove('is-paused'); });
    }

    /* ─── CRM mock dashboard animation ─── */
    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[Number(d)];
        });
    }

    function animateCrmCounts(root) {
        root.querySelectorAll('[data-crm-count]').forEach(function (el) {
            var target = parseInt(el.getAttribute('data-crm-count'), 10);
            if (!target || isNaN(target)) return;

            if (prefersReduced) {
                el.textContent = toPersianDigits(target);
                return;
            }

            var start = performance.now();
            var duration = 1100;

            function frame(now) {
                var progress = Math.min((now - start) / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                el.textContent = toPersianDigits(Math.round(target * eased));
                if (progress < 1) requestAnimationFrame(frame);
            }

            requestAnimationFrame(frame);
        });
    }

    function initCrmMock() {
        var mock = document.querySelector('[data-crm-mock]');
        if (!mock) return;

        function activate() {
            if (mock.classList.contains('is-live')) return;
            mock.classList.add('is-live');
            animateCrmCounts(mock);
        }

        var section = mock.closest('.mk-crm-grid');
        if (!section) {
            activate();
            return;
        }

        if (prefersReduced || !('IntersectionObserver' in window)) {
            activate();
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                activate();
                observer.disconnect();
            });
        }, { threshold: 0.2, rootMargin: '0px 0px -60px 0px' });

        observer.observe(section);
    }

    /* ─── Stats counter animation ─── */
    function animateStatCounts() {
        var vals = document.querySelectorAll('.mk-stat-val[data-count]');
        if (!vals.length) return;

        function run(el) {
            var target = parseInt(el.getAttribute('data-count'), 10);
            if (!target || isNaN(target)) return;

            if (prefersReduced) {
                el.textContent = toPersianDigits(target.toLocaleString('en-US'));
                return;
            }

            var start = performance.now();
            var duration = 1400;

            function frame(now) {
                var progress = Math.min((now - start) / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                var current = Math.round(target * eased);
                el.textContent = toPersianDigits(current.toLocaleString('en-US'));
                if (progress < 1) requestAnimationFrame(frame);
            }

            requestAnimationFrame(frame);
        }

        if (!('IntersectionObserver' in window)) {
            vals.forEach(run);
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                run(entry.target);
                observer.unobserve(entry.target);
            });
        }, { threshold: 0.3 });

        vals.forEach(function (el) { observer.observe(el); });
    }

    /* ─── Gallery lightbox ─── */
    function initGalleryLightbox() {
        var triggers = Array.prototype.slice.call(document.querySelectorAll('[data-mk-gallery]'));
        if (!triggers.length) return;

        var items = triggers.map(function (btn) {
            return {
                src: btn.getAttribute('data-src') || '',
                caption: btn.getAttribute('data-caption') || btn.getAttribute('aria-label') || '',
            };
        }).filter(function (item) { return item.src; });

        if (!items.length) return;

        var current = 0;
        var lightbox = document.createElement('div');
        lightbox.className = 'mk-gallery-lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.innerHTML = [
            '<button type="button" class="mk-gallery-lightbox-backdrop" data-mk-gallery-close aria-label="بستن"></button>',
            '<div class="mk-gallery-lightbox-panel">',
            '  <div class="mk-gallery-lightbox-toolbar">',
            '    <p class="mk-gallery-lightbox-title" id="mkGalleryLightboxTitle"></p>',
            '    <div class="mk-gallery-lightbox-actions">',
            '      <span class="mk-gallery-lightbox-counter" id="mkGalleryLightboxCounter"></span>',
            '      <button type="button" class="mk-gallery-lightbox-btn" id="mkGalleryLightboxPrev" aria-label="قبلی"><i class="fas fa-chevron-right"></i></button>',
            '      <button type="button" class="mk-gallery-lightbox-btn" id="mkGalleryLightboxNext" aria-label="بعدی"><i class="fas fa-chevron-left"></i></button>',
            '      <button type="button" class="mk-gallery-lightbox-btn" id="mkGalleryLightboxClose" aria-label="بستن"><i class="fas fa-xmark"></i></button>',
            '    </div>',
            '  </div>',
            '  <div class="mk-gallery-lightbox-stage">',
            '    <img class="mk-gallery-lightbox-img" id="mkGalleryLightboxImg" src="" alt="">',
            '  </div>',
            '</div>',
        ].join('');
        document.body.appendChild(lightbox);

        var imgEl = document.getElementById('mkGalleryLightboxImg');
        var titleEl = document.getElementById('mkGalleryLightboxTitle');
        var counterEl = document.getElementById('mkGalleryLightboxCounter');
        var prevBtn = document.getElementById('mkGalleryLightboxPrev');
        var nextBtn = document.getElementById('mkGalleryLightboxNext');
        var closeBtn = document.getElementById('mkGalleryLightboxClose');
        var backdrop = lightbox.querySelector('[data-mk-gallery-close]');

        function render(index) {
            current = (index + items.length) % items.length;
            var item = items[current];
            imgEl.src = item.src;
            imgEl.alt = item.caption;
            titleEl.textContent = item.caption;
            counterEl.textContent = items.length > 1 ? (current + 1) + ' / ' + items.length : '';
            prevBtn.disabled = items.length <= 1;
            nextBtn.disabled = items.length <= 1;
        }

        function open(index) {
            render(index);
            lightbox.classList.add('is-open');
            lightbox.setAttribute('aria-hidden', 'false');
            document.body.classList.add('mk-gallery-lightbox-open');
            closeBtn.focus();
        }

        function close() {
            lightbox.classList.remove('is-open');
            lightbox.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('mk-gallery-lightbox-open');
            imgEl.removeAttribute('src');
        }

        triggers.forEach(function (btn, index) {
            btn.addEventListener('click', function () { open(index); });
        });

        prevBtn.addEventListener('click', function () { render(current - 1); });
        nextBtn.addEventListener('click', function () { render(current + 1); });
        closeBtn.addEventListener('click', close);
        backdrop.addEventListener('click', close);

        document.addEventListener('keydown', function (e) {
            if (!lightbox.classList.contains('is-open')) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                close();
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                render(current + 1);
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                render(current - 1);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initReveal();
        initShowcase();
        initFaq();
        initCityMarquee();
        initCrmMock();
        animateStatCounts();
        initGalleryLightbox();
    });
})();
