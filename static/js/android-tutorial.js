(function () {
    'use strict';

    initImageFallback();
    initReveal();
    initGalleryFilters();

    function initImageFallback() {
        document.querySelectorAll('[data-and-tut-fallback]').forEach(function (img) {
            img.addEventListener('error', function () {
                img.classList.add('is-missing');
                img.removeAttribute('src');
                img.setAttribute('alt', img.getAttribute('alt') || 'تصویر به‌زودی');
            });
        });
    }

    initLightbox();
    initChapterNav();
    initScrollProgress();

    function applyGalleryFilter(cards, cat) {
        cards.forEach(function (card) {
            var show = cat === 'all' || card.dataset.andTutGalleryCat === cat;
            card.classList.toggle('is-hidden', !show);
            if (!show) {
                card.classList.remove('is-visible');
            } else if (card.dataset.andTutRevealed === 'true') {
                card.classList.add('is-visible');
            }
        });
    }

    function initGalleryFilters() {
        var filters = document.querySelectorAll('.and-tut-gallery-pill');
        var cards = document.querySelectorAll('.and-tut-masonry-item');
        if (!filters.length || !cards.length) return;

        filters.forEach(function (filter) {
            filter.addEventListener('click', function () {
                var cat = filter.dataset.andTutGallery;
                filters.forEach(function (f) {
                    var active = f === filter;
                    f.classList.toggle('is-active', active);
                    f.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                applyGalleryFilter(cards, cat);
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
            var item = items[index];
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
        var pills = document.querySelectorAll('.and-tut-dock-item');
        var modules = document.querySelectorAll('.and-tut-chapter');
        var sidebarLinks = document.querySelectorAll('.and-tut-rail-link');
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
        }, { rootMargin: '-35% 0px -52% 0px', threshold: 0 });

        modules.forEach(function (mod) { observer.observe(mod); });
    }

    function initScrollProgress() {
        var bar = document.getElementById('andTutProgressBar');
        var wrap = document.querySelector('.and-tut-curriculum-main');
        if (!bar || !wrap) return;

        function update() {
            var rect = wrap.getBoundingClientRect();
            var total = wrap.scrollHeight - window.innerHeight * 0.5;
            if (total <= 0) return;
            var scrolled = Math.min(Math.max(-rect.top + 120, 0), total);
            bar.style.width = ((scrolled / total) * 100).toFixed(1) + '%';
        }

        window.addEventListener('scroll', update, { passive: true });
        update();
    }

    function initReveal() {
        var nodes = document.querySelectorAll('[data-and-tut-reveal]');
        if (!nodes.length || !('IntersectionObserver' in window)) {
            nodes.forEach(function (n) { n.classList.add('is-visible'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                if (entry.target.classList.contains('is-hidden')) return;
                entry.target.classList.add('is-visible');
                entry.target.dataset.andTutRevealed = 'true';
                observer.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

        nodes.forEach(function (node, i) {
            node.style.transitionDelay = (i % 5) * 60 + 'ms';
            observer.observe(node);
        });
    }
})();
