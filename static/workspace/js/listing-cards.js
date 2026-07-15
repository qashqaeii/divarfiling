/**
 * Card cover gallery — prev/next + swipe for listing cards with multiple images.
 */
(function () {
    'use strict';

    function urlsFromCover(cover) {
        return Array.from(cover.querySelectorAll('.mk-lcard-gallery-urls [data-url]'))
            .map(function (el) { return (el.getAttribute('data-url') || '').trim(); })
            .filter(Boolean);
    }

    function showAt(cover, index) {
        var urls = cover._galleryUrls;
        if (!urls || !urls.length) return;
        var n = urls.length;
        var i = ((index % n) + n) % n;
        cover._galleryIndex = i;
        var img = cover.querySelector('.mk-lcard-cover-img');
        if (img) {
            img.src = urls[i];
        }
        var idxEl = cover.querySelector('[data-gallery-idx]');
        if (idxEl) idxEl.textContent = String(i + 1);
        var totalEl = cover.querySelector('[data-gallery-total]');
        if (totalEl) totalEl.textContent = String(n);
        [urls[(i + 1) % n], urls[(i - 1 + n) % n]].forEach(function (src) {
            if (!src || src === urls[i]) return;
            var preload = new Image();
            preload.referrerPolicy = 'no-referrer';
            preload.src = src;
        });
    }

    function bindCover(cover) {
        if (cover.dataset.galleryReady === '1') return;
        var urls = urlsFromCover(cover);
        if (urls.length < 2) return;
        cover.dataset.galleryReady = '1';
        cover._galleryUrls = urls;
        cover._galleryIndex = 0;
        cover._suppressClick = false;

        var prev = cover.querySelector('.mk-lcard-nav--prev');
        var next = cover.querySelector('.mk-lcard-nav--next');

        function step(delta, e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            showAt(cover, cover._galleryIndex + delta);
        }

        prev && prev.addEventListener('click', function (e) { step(-1, e); });
        next && next.addEventListener('click', function (e) { step(1, e); });

        var startX = 0;
        var startY = 0;
        var tracking = false;

        cover.addEventListener('pointerdown', function (e) {
            if (e.target.closest('.mk-lcard-nav, .mk-lcard-cover-top')) return;
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            tracking = true;
            startX = e.clientX;
            startY = e.clientY;
        });

        cover.addEventListener('pointerup', function (e) {
            if (!tracking) return;
            tracking = false;
            var dx = e.clientX - startX;
            var dy = e.clientY - startY;
            if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy)) return;
            cover._suppressClick = true;
            step(dx < 0 ? 1 : -1, e);
        });

        cover.addEventListener('pointercancel', function () { tracking = false; });

        cover.addEventListener('click', function (e) {
            if (!cover._suppressClick) return;
            cover._suppressClick = false;
            e.preventDefault();
            e.stopPropagation();
        }, true);
    }

    function initListingCardGalleries(root) {
        var scope = root || document;
        scope.querySelectorAll('.mk-lcard-cover--gallery').forEach(bindCover);
    }

    window.initListingCardGalleries = initListingCardGalleries;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initListingCardGalleries();
        });
    } else {
        initListingCardGalleries();
    }
})();
