/**
 * Public listing/property share page interactions.
 * Gallery (Swiper), tabs, lightbox with swipe, copy, prose, map, reveal.
 */
(function () {
    'use strict';

    function toFaDigits(n) {
        return String(n).replace(/\d/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[d];
        });
    }

    function initReveal() {
        var nodes = document.querySelectorAll('[data-reveal]');
        if (!nodes.length) return;
        /* Identity sheet is above the fold — animate in immediately */
        var identity = document.querySelector('.ps-identity[data-reveal]');
        if (identity) {
            requestAnimationFrame(function () {
                identity.classList.add('is-in');
            });
        }
        if (!('IntersectionObserver' in window)) {
            nodes.forEach(function (el) { el.classList.add('is-in'); });
            return;
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-in');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -24px 0px' });
        nodes.forEach(function (el) {
            if (el === identity) return;
            io.observe(el);
        });
    }

    function initGallery() {
        var mainEl = document.getElementById('psGalleryMain');
        if (!mainEl || typeof Swiper === 'undefined') return null;

        var thumbsEl = document.getElementById('psGalleryThumbs');
        var countEl = document.getElementById('psGalleryCount');
        var thumbs = null;

        if (thumbsEl) {
            thumbs = new Swiper('#psGalleryThumbs', {
                spaceBetween: 8,
                slidesPerView: 'auto',
                freeMode: true,
                watchSlidesProgress: true,
                rtl: true,
            });
        }

        var slideCount = mainEl.querySelectorAll('.swiper-slide').length;
        var main = new Swiper('#psGalleryMain', {
            loop: slideCount > 1,
            spaceBetween: 0,
            navigation: {
                nextEl: '.ps-gallery-nav--next',
                prevEl: '.ps-gallery-nav--prev',
            },
            thumbs: thumbs ? { swiper: thumbs } : undefined,
            rtl: true,
            on: {
                slideChange: function () {
                    if (!countEl) return;
                    var idx = (this.realIndex || 0) + 1;
                    countEl.textContent = toFaDigits(idx) + ' / ' + toFaDigits(slideCount);
                },
            },
        });

        return { main: main, slideCount: slideCount };
    }

    function collectGalleryUrls() {
        var urls = [];
        document.querySelectorAll('.ps-gallery-slide img[data-full]').forEach(function (img) {
            urls.push(img.getAttribute('data-full'));
        });
        if (!urls.length) {
            document.querySelectorAll('.ps-gallery-slide img').forEach(function (img) {
                urls.push(img.getAttribute('src'));
            });
        }
        return urls;
    }

    function initLightbox(galleryApi) {
        var lb = document.getElementById('psLightbox');
        var lbImg = document.getElementById('psLightboxImg');
        if (!lb || !lbImg) return;

        var urls = collectGalleryUrls();
        var index = 0;
        var countEl = document.getElementById('psLightboxCount');
        var prevBtn = lb.querySelector('.ps-lightbox-nav--prev');
        var nextBtn = lb.querySelector('.ps-lightbox-nav--next');
        var touchStartX = 0;
        var touchDeltaX = 0;

        function updateCount() {
            if (!countEl || !urls.length) return;
            countEl.textContent = toFaDigits(index + 1) + ' / ' + toFaDigits(urls.length);
        }

        function show(i) {
            if (!urls.length) return;
            index = ((i % urls.length) + urls.length) % urls.length;
            lbImg.src = urls[index];
            updateCount();
            lb.hidden = false;
            document.body.style.overflow = 'hidden';
        }

        function close() {
            lb.hidden = true;
            document.body.style.overflow = '';
            lbImg.src = '';
        }

        function next() { show(index + 1); }
        function prev() { show(index - 1); }

        document.querySelectorAll('[data-lightbox-index]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var i = parseInt(btn.getAttribute('data-lightbox-index'), 10) || 0;
                show(i);
            });
        });

        var closeBtn = lb.querySelector('.ps-lightbox-close');
        if (closeBtn) closeBtn.addEventListener('click', close);
        lb.addEventListener('click', function (e) {
            if (e.target === lb) close();
        });

        if (prevBtn) prevBtn.addEventListener('click', function (e) { e.stopPropagation(); prev(); });
        if (nextBtn) nextBtn.addEventListener('click', function (e) { e.stopPropagation(); next(); });

        document.addEventListener('keydown', function (e) {
            if (lb.hidden) return;
            if (e.key === 'Escape') close();
            if (e.key === 'ArrowLeft') next();
            if (e.key === 'ArrowRight') prev();
        });

        lb.addEventListener('touchstart', function (e) {
            if (!e.changedTouches || !e.changedTouches.length) return;
            touchStartX = e.changedTouches[0].screenX;
            touchDeltaX = 0;
        }, { passive: true });

        lb.addEventListener('touchmove', function (e) {
            if (!e.changedTouches || !e.changedTouches.length) return;
            touchDeltaX = e.changedTouches[0].screenX - touchStartX;
        }, { passive: true });

        lb.addEventListener('touchend', function () {
            if (Math.abs(touchDeltaX) < 50) return;
            /* RTL: swipe right (positive) → previous visual / next in LTR sense of gallery */
            if (touchDeltaX > 0) prev();
            else next();
            touchDeltaX = 0;
        });

        return { show: show, close: close };
    }

    function initTabs() {
        var tabs = document.querySelectorAll('.ps-tab');
        if (!tabs.length) return;
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                var name = tab.getAttribute('data-tab');
                tabs.forEach(function (t) {
                    var on = t === tab;
                    t.classList.toggle('is-active', on);
                    t.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                document.querySelectorAll('.ps-panel').forEach(function (p) {
                    p.hidden = p.getAttribute('data-panel') !== name;
                });
            });
        });
    }

    function initProse() {
        document.querySelectorAll('[data-fv-prose-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var wrap = btn.closest('[data-fv-prose]');
                if (!wrap) return;
                var open = btn.getAttribute('aria-expanded') !== 'true';
                var preview = wrap.querySelector('.ps-fv-prose-preview');
                var full = wrap.querySelector('.ps-fv-prose-full');
                if (preview) preview.hidden = open;
                if (full) full.hidden = !open;
                btn.setAttribute('aria-expanded', open ? 'true' : 'false');
                btn.textContent = open ? 'بستن' : 'ادامه متن';
            });
        });
    }

    function initCopy() {
        document.querySelectorAll('[data-copy]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var text = btn.getAttribute('data-copy') || '';
                if (!text) return;
                function done() {
                    btn.classList.add('is-copied');
                    var prev = btn.getAttribute('title') || '';
                    btn.setAttribute('title', 'کپی شد');
                    setTimeout(function () {
                        btn.classList.remove('is-copied');
                        btn.setAttribute('title', prev || 'کپی');
                    }, 1600);
                }
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(done).catch(function () {
                        fallbackCopy(text, done);
                    });
                } else {
                    fallbackCopy(text, done);
                }
            });
        });
    }

    function fallbackCopy(text, done) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            done();
        } catch (e) { /* ignore */ }
        document.body.removeChild(ta);
    }

    function initMap() {
        var markerEl = document.getElementById('listing-map-marker');
        if (!markerEl || typeof initListingDetailMap !== 'function') return;
        try {
            var marker = JSON.parse(markerEl.textContent);
            if (!marker || marker.lat == null || marker.lng == null) return;
            initListingDetailMap({
                marker: marker,
                uiPrefix: 'pubLd',
                mapId: 'pubLocationMap',
                stageId: 'pubLocationMapStage',
                zoom: 17,
            });
        } catch (e) { /* ignore bad marker */ }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initReveal();
        var galleryApi = initGallery();
        initLightbox(galleryApi);
        initTabs();
        initProse();
        initCopy();
        initMap();
    });
})();
