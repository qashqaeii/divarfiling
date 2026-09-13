(function () {
    'use strict';

    initReveal();
    initPathTabs();
    initVideoTabs();
    initTabIndicators();
    initStickyNav();
    initGalleryFilters();
    initGalleryMore();
    initLightbox();

    function initReveal() {
        var wrap = document.querySelector('.edu-wrap');
        if (!wrap) return;

        var items = wrap.querySelectorAll('.edu-reveal');
        if (!items.length) return;

        var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function activate(el) {
            el.classList.add('is-inview');
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
            threshold: 0.08,
            rootMargin: '0px 0px -5% 0px',
        });

        items.forEach(function (el) {
            if (el.getBoundingClientRect().top < window.innerHeight * 0.92) {
                activate(el);
            } else {
                observer.observe(el);
            }
        });
    }

    function initPathTabs() {
        var tabs = document.querySelectorAll('.edu-path-tab');
        var panels = document.querySelectorAll('.edu-path-panel');
        if (!tabs.length || !panels.length) return;

        var track = document.querySelector('[data-tab-track="path"]');

        function activatePath(pathId) {
            tabs.forEach(function (tab) {
                var isActive = tab.dataset.path === pathId;
                tab.classList.toggle('is-active', isActive);
                tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            panels.forEach(function (panel) {
                var isActive = panel.dataset.pathPanel === pathId;
                panel.classList.toggle('is-active', isActive);
                if (isActive) panel.removeAttribute('hidden');
                else panel.setAttribute('hidden', '');
            });
            moveTabIndicator(track);
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                activatePath(tab.dataset.path);
            });
        });

        moveTabIndicator(track);
        window.addEventListener('resize', function () { moveTabIndicator(track); });
    }

    function initVideoTabs() {
        var tabs = document.querySelectorAll('.edu-vtab');
        var panels = document.querySelectorAll('.edu-vpanel');
        if (!tabs.length || !panels.length) return;

        var track = document.querySelector('[data-tab-track="video"]');

        function activateVideo(id) {
            tabs.forEach(function (tab) {
                var isActive = tab.dataset.vtab === id;
                tab.classList.toggle('is-active', isActive);
                tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
            panels.forEach(function (panel) {
                var isActive = panel.dataset.vpanel === id;
                panel.classList.toggle('is-active', isActive);
                if (isActive) panel.removeAttribute('hidden');
                else panel.setAttribute('hidden', '');
            });
            moveTabIndicator(track);
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                activateVideo(tab.dataset.vtab);
            });
        });

        moveTabIndicator(track);
        window.addEventListener('resize', function () { moveTabIndicator(track); });
    }

    function moveTabIndicator(track) {
        if (!track) return;
        var indicator = track.querySelector('.edu-tab-indicator');
        var active = track.querySelector('.is-active');
        if (!indicator || !active) return;

        indicator.style.width = active.offsetWidth + 'px';
        indicator.style.transform = 'translateX(' + active.offsetLeft + 'px)';
    }

    function initTabIndicators() {
        document.querySelectorAll('[data-tab-track]').forEach(moveTabIndicator);
    }

    function initStickyNav() {
        var nav = document.querySelector('.edu-sticky-nav');
        if (!nav) return;

        var links = nav.querySelectorAll('.edu-sticky-nav__link');
        var sections = [
            { id: 'edu-paths', nav: 'paths' },
            { id: 'edu-videos', nav: 'videos' },
            { id: 'edu-modules', nav: 'modules' },
            { id: 'edu-gallery', nav: 'gallery' },
            { id: 'edu-support', nav: 'gallery' },
        ].filter(function (s) { return document.getElementById(s.id); });

        if (!sections.length || !('IntersectionObserver' in window)) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var match = sections.find(function (s) { return s.id === entry.target.id; });
                if (!match) return;
                links.forEach(function (link) {
                    link.classList.toggle('is-active', link.dataset.eduNav === match.nav);
                });
            });
        }, {
            rootMargin: '-40% 0px -45% 0px',
            threshold: 0,
        });

        sections.forEach(function (s) {
            var el = document.getElementById(s.id);
            if (el) observer.observe(el);
        });

        links.forEach(function (link) {
            link.addEventListener('click', function () {
                links.forEach(function (l) { l.classList.remove('is-active'); });
                link.classList.add('is-active');
            });
        });
    }

    function initGalleryFilters() {
        var filters = document.querySelectorAll('.edu-gallery-filter');
        var cards = document.querySelectorAll('.edu-gallery-card');
        if (!filters.length || !cards.length) return;

        filters.forEach(function (filter) {
            filter.addEventListener('click', function () {
                var cat = filter.dataset.galleryFilter;
                filters.forEach(function (f) {
                    var active = f === filter;
                    f.classList.toggle('is-active', active);
                    f.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                cards.forEach(function (card) {
                    var show = cat === 'all' || card.dataset.galleryCat === cat;
                    card.classList.toggle('is-hidden', !show);
                });
            });
        });
    }

    function initGalleryMore() {
        var btn = document.querySelector('[data-gallery-more]');
        var grid = document.querySelector('[data-gallery-grid]');
        if (!btn || !grid) return;

        btn.addEventListener('click', function () {
            grid.classList.add('is-expanded');
            btn.closest('.edu-gallery-more-wrap').hidden = true;
        });
    }

    function initLightbox() {
        var triggers = Array.prototype.slice.call(document.querySelectorAll('[data-edu-lightbox]'));
        if (!triggers.length) return;

        var items = triggers.map(function (btn) {
            return {
                src: btn.dataset.src || '',
                caption: btn.dataset.caption || btn.getAttribute('aria-label') || '',
            };
        }).filter(function (item) { return item.src; });

        if (!items.length) return;

        var current = 0;
        var lightbox = document.createElement('div');
        lightbox.className = 'edu-lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.innerHTML = [
            '<button type="button" class="edu-lightbox-backdrop" data-edu-lightbox-close aria-label="بستن"></button>',
            '<div class="edu-lightbox-panel">',
            '  <div class="edu-lightbox-toolbar">',
            '    <p class="edu-lightbox-title" id="eduLightboxTitle"></p>',
            '    <div class="edu-lightbox-actions">',
            '      <span class="edu-lightbox-counter" id="eduLightboxCounter"></span>',
            '      <button type="button" class="edu-lightbox-btn" id="eduLightboxPrev" aria-label="قبلی"><i class="fas fa-chevron-right"></i></button>',
            '      <button type="button" class="edu-lightbox-btn" id="eduLightboxNext" aria-label="بعدی"><i class="fas fa-chevron-left"></i></button>',
            '      <button type="button" class="edu-lightbox-btn" id="eduLightboxClose" aria-label="بستن"><i class="fas fa-xmark"></i></button>',
            '    </div>',
            '  </div>',
            '  <div class="edu-lightbox-stage">',
            '    <img class="edu-lightbox-img" id="eduLightboxImg" src="" alt="">',
            '  </div>',
            '</div>',
        ].join('');
        document.body.appendChild(lightbox);

        var imgEl = document.getElementById('eduLightboxImg');
        var titleEl = document.getElementById('eduLightboxTitle');
        var counterEl = document.getElementById('eduLightboxCounter');
        var prevBtn = document.getElementById('eduLightboxPrev');
        var nextBtn = document.getElementById('eduLightboxNext');
        var closeBtn = document.getElementById('eduLightboxClose');
        var backdrop = lightbox.querySelector('[data-edu-lightbox-close]');

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
            document.body.classList.add('edu-lightbox-open');
            closeBtn.focus();
        }

        function close() {
            lightbox.classList.remove('is-open');
            lightbox.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('edu-lightbox-open');
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
})();
