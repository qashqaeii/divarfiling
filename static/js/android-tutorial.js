(function () {
    'use strict';

    initImageFallback();
    initGalleryFilters();
    initLightbox();
    initChapterNav();
    initScrollProgress();

    function initImageFallback() {
        document.querySelectorAll('[data-and-tut-fallback]').forEach(function (img) {
            img.addEventListener('error', function () {
                img.classList.add('is-missing');
                img.removeAttribute('src');
                img.setAttribute('alt', img.getAttribute('alt') || 'تصویر به‌زودی');
            });
        });
    }

    function initGalleryFilters() {
        var filters = document.querySelectorAll('.and-tut-gallery-filter');
        var cards = document.querySelectorAll('.and-tut-gallery-card');
        if (!filters.length || !cards.length) return;

        filters.forEach(function (filter) {
            filter.addEventListener('click', function () {
                var cat = filter.dataset.andTutGallery;
                filters.forEach(function (f) {
                    var active = f === filter;
                    f.classList.toggle('is-active', active);
                    f.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                cards.forEach(function (card) {
                    var show = cat === 'all' || card.dataset.andTutGalleryCat === cat;
                    card.classList.toggle('is-hidden', !show);
                });
            });
        });
    }

    function initLightbox() {
        var triggers = Array.prototype.slice.call(document.querySelectorAll('[data-and-tut-lightbox]'));
        if (!triggers.length) return;

        var items = triggers.map(function (btn) {
            return {
                src: btn.dataset.src || '',
                caption: btn.dataset.caption || '',
            };
        }).filter(function (item) { return item.src; });

        if (!items.length) return;

        var current = 0;
        var lightbox = document.createElement('div');
        lightbox.className = 'and-tut-lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.innerHTML = [
            '<button type="button" class="and-tut-lightbox-backdrop" data-and-tut-lb-close aria-label="بستن"></button>',
            '<div class="and-tut-lightbox-panel">',
            '  <button type="button" class="and-tut-lightbox-close" data-and-tut-lb-close aria-label="بستن"><i class="fas fa-times"></i></button>',
            '  <img src="" alt="" id="andTutLbImg">',
            '  <p class="and-tut-lightbox-title" id="andTutLbTitle"></p>',
            '</div>',
        ].join('');
        document.body.appendChild(lightbox);

        var imgEl = lightbox.querySelector('#andTutLbImg');
        var titleEl = lightbox.querySelector('#andTutLbTitle');

        function openAt(index) {
            current = index;
            var item = items[current];
            imgEl.src = item.src;
            imgEl.alt = item.caption;
            titleEl.textContent = item.caption;
            lightbox.classList.add('is-open');
            lightbox.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
        }

        function close() {
            lightbox.classList.remove('is-open');
            lightbox.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
            imgEl.removeAttribute('src');
        }

        triggers.forEach(function (btn, index) {
            btn.addEventListener('click', function () { openAt(index); });
        });

        lightbox.querySelectorAll('[data-and-tut-lb-close]').forEach(function (el) {
            el.addEventListener('click', close);
        });

        document.addEventListener('keydown', function (e) {
            if (!lightbox.classList.contains('is-open')) return;
            if (e.key === 'Escape') close();
        });
    }

    function initChapterNav() {
        var pills = document.querySelectorAll('.and-tut-chapter-pill');
        var modules = document.querySelectorAll('.and-tut-module');
        var sidebarLinks = document.querySelectorAll('.and-tut-sidebar-link');
        if (!modules.length) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var id = entry.target.id.replace('chapter-', '');
                pills.forEach(function (pill) {
                    pill.classList.toggle('is-active', pill.dataset.andTutChapter === id);
                });
                sidebarLinks.forEach(function (link) {
                    link.classList.toggle('is-active', link.dataset.andTutSidebar === id);
                });
            });
        }, { rootMargin: '-40% 0px -50% 0px', threshold: 0 });

        modules.forEach(function (mod) { observer.observe(mod); });
    }

    function initScrollProgress() {
        var bar = document.getElementById('andTutProgressBar');
        var wrap = document.querySelector('.and-tut-curriculum-main');
        if (!bar || !wrap) return;

        function update() {
            var rect = wrap.getBoundingClientRect();
            var total = wrap.scrollHeight - window.innerHeight;
            if (total <= 0) return;
            var scrolled = Math.min(Math.max(-rect.top, 0), total);
            bar.style.width = ((scrolled / total) * 100).toFixed(1) + '%';
        }

        window.addEventListener('scroll', update, { passive: true });
        update();
    }
})();
