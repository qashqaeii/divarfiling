(function () {
    'use strict';

    function initReveal() {
        var els = document.querySelectorAll('.pbp-reveal');
        if (!els.length) return;
        if (!('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('is-inview'); });
            return;
        }
        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-inview');
                obs.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
        els.forEach(function (el) { obs.observe(el); });
    }

    function initStickyNav() {
        var nav = document.querySelector('.pbp-sticky-nav');
        if (!nav) return;
        var links = nav.querySelectorAll('[data-pbp-nav]');
        var sections = [];
        links.forEach(function (link) {
            var id = link.getAttribute('href');
            if (!id || id.charAt(0) !== '#') return;
            var el = document.querySelector(id);
            if (el) sections.push({ nav: link.dataset.pbpNav, el: el, link: link });
        });
        if (!sections.length || !('IntersectionObserver' in window)) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var match = sections.find(function (s) { return s.el === entry.target; });
                if (!match) return;
                links.forEach(function (l) {
                    l.classList.toggle('is-active', l === match.link);
                });
            });
        }, { rootMargin: '-35% 0px -50% 0px', threshold: 0 });

        sections.forEach(function (s) { observer.observe(s.el); });
    }

    function initTabs() {
        document.querySelectorAll('[data-pbp-tabs]').forEach(function (root) {
            var tabs = root.querySelectorAll('[data-pbp-tab]');
            var panels = root.querySelectorAll('[data-pbp-panel]');
            var indicator = root.querySelector('.pbp-tab-indicator');
            if (!tabs.length || !panels.length) return;

            function moveIndicator(active) {
                if (!indicator || !active) return;
                var bar = root.querySelector('.pbp-tabs__bar');
                if (!bar) return;
                indicator.style.width = active.offsetWidth + 'px';
                indicator.style.transform = 'translateX(' + (active.offsetLeft - bar.scrollLeft) + 'px)';
            }

            function activate(id) {
                tabs.forEach(function (tab) {
                    var on = tab.dataset.pbpTab === id;
                    tab.classList.toggle('is-active', on);
                    tab.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                panels.forEach(function (panel) {
                    var on = panel.dataset.pbpPanel === id;
                    panel.classList.toggle('is-active', on);
                    if (on) panel.removeAttribute('hidden');
                    else panel.setAttribute('hidden', '');
                });
                moveIndicator(root.querySelector('[data-pbp-tab].is-active'));
            }

            tabs.forEach(function (tab) {
                tab.addEventListener('click', function () { activate(tab.dataset.pbpTab); });
            });

            moveIndicator(root.querySelector('[data-pbp-tab].is-active'));
            window.addEventListener('resize', function () {
                moveIndicator(root.querySelector('[data-pbp-tab].is-active'));
            });
        });
    }

    function initJourney() {
        var rail = document.querySelector('[data-pbp-journey]');
        if (!rail) return;
        var steps = rail.querySelectorAll('[data-pbp-journey-step]');
        if (!steps.length || !('IntersectionObserver' in window)) return;

        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var idx = parseInt(entry.target.dataset.pbpJourneyStep, 10);
                steps.forEach(function (step, i) {
                    step.classList.toggle('is-active', i <= idx);
                });
                var fill = rail.querySelector('[data-pbp-journey-fill]');
                if (fill && steps.length > 1) {
                    fill.style.width = ((idx / (steps.length - 1)) * 100) + '%';
                }
            });
        }, { rootMargin: '-20% 0px -55% 0px', threshold: 0.2 });

        steps.forEach(function (step) { obs.observe(step); });
    }

    function initFaq() {
        var panel = document.querySelector('[data-pbp-faq]');
        if (!panel) return;
        panel.querySelectorAll('.pbp-faq-item').forEach(function (item) {
            item.addEventListener('toggle', function () {
                if (!item.open) return;
                panel.querySelectorAll('.pbp-faq-item').forEach(function (other) {
                    if (other !== item) other.open = false;
                });
            });
        });
    }

    function initLightbox() {
        var lightbox = document.getElementById('pb-lightbox');
        var lightboxImg = document.getElementById('pb-lightbox-img');
        var lightboxCaption = lightbox ? lightbox.querySelector('.pb-lightbox-caption') : null;
        var openBtns = document.querySelectorAll('[data-pb-lightbox-open]');
        if (!lightbox || !openBtns.length) return;

        if (lightbox.parentElement !== document.body) {
            document.body.appendChild(lightbox);
        }

        var lastFocus = null;

        function resolveSrc(trigger) {
            if (trigger.dataset.pbLightboxSrc) return trigger.dataset.pbLightboxSrc;
            var img = trigger.querySelector('img');
            return img ? (img.currentSrc || img.src) : '';
        }

        function open(trigger) {
            var src = resolveSrc(trigger);
            var caption = trigger.dataset.pbLightboxCaption || '';
            if (src && lightboxImg) {
                lightboxImg.src = src;
                lightboxImg.alt = caption;
            }
            if (lightboxCaption) lightboxCaption.textContent = caption || lightboxImg.alt || '';
            lastFocus = document.activeElement;
            lightbox.hidden = false;
            document.body.style.overflow = 'hidden';
            var closeBtn = lightbox.querySelector('.pb-lightbox-close');
            if (closeBtn) closeBtn.focus();
        }

        function close() {
            lightbox.hidden = true;
            document.body.style.overflow = '';
            if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
        }

        openBtns.forEach(function (btn) {
            btn.addEventListener('click', function () { open(btn); });
        });
        lightbox.querySelectorAll('[data-pb-lightbox-close]').forEach(function (el) {
            el.addEventListener('click', close);
        });
        document.addEventListener('keydown', function (e) {
            if (!lightbox.hidden && e.key === 'Escape') close();
        });
    }

    function updateStickyTop() {
        var header = document.querySelector('.mk-site-header');
        if (!header) return;
        document.documentElement.style.setProperty(
            '--pbp-sticky-top',
            Math.ceil(header.getBoundingClientRect().height) + 'px'
        );
    }

    function initStickyBuyCta() {
        if (!document.body.classList.contains('mk-product-bot-page')) return;

        var bar = document.querySelector('[data-pbp-sticky-cta]');
        var hero = document.querySelector('.pbp-hero');
        var bottomCta = document.querySelector('.pbp-cta');
        var mobileMq = window.matchMedia('(max-width: 767px)');

        if (!bar) return;

        function setVisible(show) {
            bar.classList.toggle('is-visible', show);
            bar.hidden = !show;
        }

        function bindObservers() {
            if (!mobileMq.matches || !('IntersectionObserver' in window)) {
                setVisible(false);
                return;
            }

            var heroVisible = true;
            var ctaVisible = false;

            function update() {
                setVisible(!heroVisible && !ctaVisible);
            }

            var heroObserver = new IntersectionObserver(function (entries) {
                heroVisible = entries.some(function (entry) { return entry.isIntersecting; });
                update();
            }, { threshold: 0.06 });

            var ctaObserver = new IntersectionObserver(function (entries) {
                ctaVisible = entries.some(function (entry) { return entry.isIntersecting; });
                update();
            }, { threshold: 0.15 });

            if (hero) heroObserver.observe(hero);
            if (bottomCta) ctaObserver.observe(bottomCta);
            update();
        }

        if (typeof mobileMq.addEventListener === 'function') {
            mobileMq.addEventListener('change', bindObservers);
        } else if (typeof mobileMq.addListener === 'function') {
            mobileMq.addListener(bindObservers);
        }

        bindObservers();
    }

    document.addEventListener('DOMContentLoaded', function () {
        updateStickyTop();
        window.addEventListener('resize', updateStickyTop, { passive: true });
        initReveal();
        initStickyNav();
        initTabs();
        initJourney();
        initFaq();
        initLightbox();
        initStickyBuyCta();
    });
})();
