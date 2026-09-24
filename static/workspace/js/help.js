(function () {
    'use strict';

    initTocNav();
    initImageLightbox();
    initHelpSearch();

    function initHelpSearch() {
        var input = document.getElementById('hlpSearch');
        if (!input) return;

        var clearBtn = document.getElementById('hlpSearchClear');
        var hintEl = document.getElementById('hlpSearchHint');
        var emptyEl = document.getElementById('hlpSearchEmpty');
        var sections = Array.prototype.slice.call(
            document.querySelectorAll('[data-hlp-searchable]')
        );
        var faqItems = Array.prototype.slice.call(
            document.querySelectorAll('[data-hlp-faq]')
        );

        function normalize(text) {
            return (text || '').replace(/\s+/g, ' ').trim().toLowerCase();
        }

        function applyFilter() {
            var q = normalize(input.value);
            if (clearBtn) clearBtn.hidden = !q;

            if (!q) {
                sections.forEach(function (el) {
                    el.classList.remove('hlp-section--filtered-out');
                });
                faqItems.forEach(function (el) {
                    el.classList.remove('hlp-faq-item--hidden');
                });
                if (hintEl) {
                    hintEl.hidden = true;
                    hintEl.textContent = '';
                }
                if (emptyEl) emptyEl.hidden = true;
                return;
            }

            var visibleSections = 0;
            var visibleFaq = 0;

            sections.forEach(function (section) {
                var text = normalize(section.textContent);
                var match = text.indexOf(q) !== -1;
                section.classList.toggle('hlp-section--filtered-out', !match);
                if (match) visibleSections += 1;
            });

            faqItems.forEach(function (item) {
                var text = normalize(item.textContent);
                var match = text.indexOf(q) !== -1;
                item.classList.toggle('hlp-faq-item--hidden', !match);
                if (match) visibleFaq += 1;
            });

            var total = visibleSections + visibleFaq;
            if (hintEl) {
                hintEl.hidden = false;
                hintEl.textContent = total
                    ? total + ' نتیجه برای «' + input.value.trim() + '»'
                    : 'نتیجه‌ای یافت نشد';
            }
            if (emptyEl) emptyEl.hidden = total > 0;
        }

        input.addEventListener('input', applyFilter);
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                input.value = '';
                input.focus();
                applyFilter();
            });
        }
    }

    function initTocNav() {
        var links = document.querySelectorAll('.hlp-toc-link[data-target]');
        if (!links.length) return;

        var sections = [];
        links.forEach(function (link) {
            var id = link.getAttribute('data-target');
            var el = document.getElementById(id);
            if (el) sections.push({ id: id, el: el, link: link });
        });

        function setActive(id) {
            links.forEach(function (link) {
                link.classList.toggle('is-active', link.getAttribute('data-target') === id);
            });
        }

        if ('IntersectionObserver' in window) {
            var visible = new Map();
            var observer = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (entry) {
                        visible.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0);
                    });
                    var best = null;
                    var bestRatio = 0;
                    sections.forEach(function (s) {
                        var ratio = visible.get(s.id) || 0;
                        if (ratio > bestRatio) {
                            bestRatio = ratio;
                            best = s.id;
                        }
                    });
                    if (best) setActive(best);
                },
                { rootMargin: '-10% 0px -55% 0px', threshold: [0, 0.1, 0.25, 0.5] }
            );
            sections.forEach(function (s) { observer.observe(s.el); });
        }

        links.forEach(function (link) {
            link.addEventListener('click', function (e) {
                var id = link.getAttribute('data-target');
                var target = document.getElementById(id);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setActive(id);
                    history.replaceState(null, '', '#' + id);
                }
            });
        });

        var hash = window.location.hash.replace('#', '');
        if (hash) {
            var hashEl = document.getElementById(hash);
            if (hashEl) {
                setTimeout(function () {
                    hashEl.scrollIntoView({ behavior: 'smooth' });
                    setActive(hash);
                }, 100);
            }
        }
    }

    function initImageLightbox() {
        var triggers = Array.prototype.slice.call(
            document.querySelectorAll('.hlp-figure-frame[data-hlp-lightbox]:not(.hlp-figure-frame--missing)')
        );
        if (!triggers.length) return;

        var items = triggers.map(function (frame) {
            var img = frame.querySelector('.hlp-figure-img');
            var figure = frame.closest('.hlp-figure');
            var captionEl = figure ? figure.querySelector('figcaption') : null;
            return {
                src: img ? img.currentSrc || img.src : '',
                alt: img ? img.alt : '',
                caption: captionEl ? captionEl.textContent.trim() : (img ? img.alt : ''),
            };
        }).filter(function (item) { return item.src; });

        if (!items.length) return;

        var current = 0;
        var lightbox = document.createElement('div');
        lightbox.className = 'hlp-lightbox';
        lightbox.setAttribute('role', 'dialog');
        lightbox.setAttribute('aria-modal', 'true');
        lightbox.setAttribute('aria-hidden', 'true');
        lightbox.innerHTML = [
            '<button type="button" class="hlp-lightbox-backdrop" data-hlp-lightbox-close aria-label="بستن"></button>',
            '<div class="hlp-lightbox-panel">',
            '  <div class="hlp-lightbox-toolbar">',
            '    <p class="hlp-lightbox-title" id="hlpLightboxTitle"></p>',
            '    <div class="hlp-lightbox-actions">',
            '      <span class="hlp-lightbox-counter" id="hlpLightboxCounter" aria-hidden="true"></span>',
            '      <button type="button" class="hlp-lightbox-btn" id="hlpLightboxPrev" aria-label="تصویر قبلی"><i class="fas fa-chevron-right"></i></button>',
            '      <button type="button" class="hlp-lightbox-btn" id="hlpLightboxNext" aria-label="تصویر بعدی"><i class="fas fa-chevron-left"></i></button>',
            '      <button type="button" class="hlp-lightbox-btn" id="hlpLightboxClose" aria-label="بستن"><i class="fas fa-xmark"></i></button>',
            '    </div>',
            '  </div>',
            '  <div class="hlp-lightbox-stage">',
            '    <img class="hlp-lightbox-img" id="hlpLightboxImg" src="" alt="">',
            '  </div>',
            '</div>',
        ].join('');
        document.body.appendChild(lightbox);

        var imgEl = document.getElementById('hlpLightboxImg');
        var titleEl = document.getElementById('hlpLightboxTitle');
        var counterEl = document.getElementById('hlpLightboxCounter');
        var prevBtn = document.getElementById('hlpLightboxPrev');
        var nextBtn = document.getElementById('hlpLightboxNext');
        var closeBtn = document.getElementById('hlpLightboxClose');
        var backdrop = lightbox.querySelector('[data-hlp-lightbox-close]');

        function render(index) {
            current = (index + items.length) % items.length;
            var item = items[current];
            imgEl.src = item.src;
            imgEl.alt = item.alt;
            titleEl.textContent = item.caption || item.alt;
            counterEl.textContent = items.length > 1 ? (current + 1) + ' / ' + items.length : '';
            prevBtn.disabled = items.length <= 1;
            nextBtn.disabled = items.length <= 1;
            lightbox.setAttribute('aria-label', item.caption || item.alt || 'بزرگ‌نمایی تصویر');
        }

        function open(index) {
            render(index);
            lightbox.classList.add('is-open');
            lightbox.setAttribute('aria-hidden', 'false');
            document.body.classList.add('hlp-lightbox-open');
            closeBtn.focus();
        }

        function close() {
            lightbox.classList.remove('is-open');
            lightbox.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('hlp-lightbox-open');
            imgEl.removeAttribute('src');
        }

        triggers.forEach(function (frame, index) {
            frame.addEventListener('click', function () { open(index); });
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
