/**
 * Public listing/property share page interactions.
 * Gallery (Swiper), tabs/accordion, lightbox, copy, prose, map, reveal.
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

    function bindGalleryImage(img) {
        var slide = img.closest('.ps-gallery-slide');
        if (!slide) return;

        function markLoaded() {
            slide.classList.add('is-loaded');
            if (img.naturalWidth && img.naturalHeight && img.naturalHeight > img.naturalWidth * 1.15) {
                slide.classList.add('is-portrait');
            }
        }

        function markError() {
            slide.classList.add('is-error');
            slide.classList.remove('is-loaded');
            img.removeAttribute('data-full');
            img.alt = 'بارگذاری تصویر ممکن نشد';
        }

        if (img.complete && img.naturalWidth > 0) {
            markLoaded();
        } else if (img.complete && img.naturalWidth === 0) {
            markError();
        } else {
            img.addEventListener('load', markLoaded, { once: true });
            img.addEventListener('error', markError, { once: true });
        }
    }

    function initGalleryImages() {
        document.querySelectorAll('.ps-gallery-img').forEach(bindGalleryImage);
    }

    function initGallery() {
        var mainEl = document.getElementById('psGalleryMain');
        if (!mainEl || typeof Swiper === 'undefined') return null;

        initGalleryImages();

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

        if (countEl && slideCount) {
            countEl.textContent = toFaDigits(1) + ' / ' + toFaDigits(slideCount);
        }

        return { main: main, slideCount: slideCount };
    }

    function collectGalleryUrls() {
        var urls = [];
        document.querySelectorAll('.ps-gallery-slide:not(.is-error) img[data-full]').forEach(function (img) {
            urls.push(img.getAttribute('data-full'));
        });
        if (!urls.length) {
            document.querySelectorAll('.ps-gallery-slide:not(.is-error) img').forEach(function (img) {
                var src = img.getAttribute('src');
                if (src) urls.push(src);
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
            urls = collectGalleryUrls();
            if (!urls.length) return;
            index = ((i % urls.length) + urls.length) % urls.length;
            lbImg.src = urls[index];
            lbImg.alt = 'تصویر ' + toFaDigits(index + 1);
            updateCount();
            lb.hidden = false;
            document.body.style.overflow = 'hidden';
            var closeBtn = lb.querySelector('.ps-lightbox-close');
            if (closeBtn) closeBtn.focus();
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
                if (btn.classList.contains('is-error')) return;
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
            if (touchDeltaX > 0) prev();
            else next();
            touchDeltaX = 0;
        });

        return { show: show, close: close };
    }

    function activateTab(tabs, panels, name) {
        tabs.forEach(function (t) {
            var on = t.getAttribute('data-tab') === name;
            t.classList.toggle('is-active', on);
            t.setAttribute('aria-selected', on ? 'true' : 'false');
            t.setAttribute('tabindex', on ? '0' : '-1');
        });
        panels.forEach(function (p) {
            p.hidden = p.getAttribute('data-panel') !== name;
        });
    }

    function initTabs() {
        var root = document.querySelector('[data-ps-details]');
        if (!root) return;
        var tabs = Array.prototype.slice.call(root.querySelectorAll('.ps-tab'));
        var panels = Array.prototype.slice.call(root.querySelectorAll('.ps-panel'));
        if (!tabs.length) return;

        tabs.forEach(function (tab, idx) {
            tab.addEventListener('click', function () {
                activateTab(tabs, panels, tab.getAttribute('data-tab'));
            });
            tab.addEventListener('keydown', function (e) {
                var nextIdx = idx;
                if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') nextIdx = (idx + 1) % tabs.length;
                else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') nextIdx = (idx - 1 + tabs.length) % tabs.length;
                else if (e.key === 'Home') nextIdx = 0;
                else if (e.key === 'End') nextIdx = tabs.length - 1;
                else return;
                e.preventDefault();
                tabs[nextIdx].focus();
                activateTab(tabs, panels, tabs[nextIdx].getAttribute('data-tab'));
            });
        });
    }

    function initAccordion() {
        var accordion = document.querySelector('[data-ps-accordion]');
        if (!accordion) return;
        var items = Array.prototype.slice.call(accordion.querySelectorAll('.ps-acc-item'));
        items.forEach(function (item) {
            item.addEventListener('toggle', function () {
                if (!item.open) return;
                items.forEach(function (other) {
                    if (other !== item) other.open = false;
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

            var start = function () {
                initListingDetailMap({
                    marker: marker,
                    uiPrefix: 'pubLd',
                    mapId: 'pubLocationMap',
                    stageId: 'pubLocationMapStage',
                    zoom: 17,
                });
            };

            if ('IntersectionObserver' in window) {
                var mapEl = document.getElementById('pubLocationMap');
                if (mapEl) {
                    var io = new IntersectionObserver(function (entries) {
                        if (entries.some(function (e) { return e.isIntersecting; })) {
                            io.disconnect();
                            start();
                        }
                    }, { rootMargin: '200px' });
                    io.observe(mapEl);
                    return;
                }
            }
            start();
        } catch (e) { /* ignore bad marker */ }
    }

    function initDockPadding() {
        var dock = document.querySelector('.ps-dock');
        var page = document.querySelector('.ps-page');
        if (dock && page) page.classList.add('has-dock');
    }

    document.addEventListener('DOMContentLoaded', function () {
        initReveal();
        var galleryApi = initGallery();
        initLightbox(galleryApi);
        initTabs();
        initAccordion();
        initProse();
        initCopy();
        initMap();
        initDockPadding();
    });
})();
