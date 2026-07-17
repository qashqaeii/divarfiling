/**
 * Platform page — motion system (reveal, flow, stagger, subtle parallax)
 * Progressive enhancement: content visible before JS runs.
 */
(function () {
    'use strict';

    var root = document.querySelector('.plat-page');
    if (!root) return;

    var html = document.documentElement;
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var vh = window.innerHeight || document.documentElement.clientHeight || 800;

    var STAGGER_SEL = [
        '.fhub-pillars', '.fhub-lifecycle', '.fhub-audience', '.fhub-explore', '.fhub-related',
        '.fhub-kpis', '.fhub-signals', '.fhub-mistakes', '.fhub-reasons',
        '.rem-concepts', '.rem-gallery', '.rem-use-grid', '.rem-limits', '.rem-states',
        '.shub-choose', '.shub-map', '.shub-path', '.fhub-tools',
        '.sol-reasons', '.sol-mistakes', '.sol-framework', '.sol-personas', '.sol-kpis',
        '.sol-signals', '.sol-tools', '.sol-related-grid', '.mk-mega-grid'
    ].join(',');

    var FLOW_SEL = [
        '.rem-timeline', '.sol-timeline', '.fhub-lifecycle', '.rem-workflow',
        '.sol-framework', '.shub-choose', '.rem-workflow'
    ].join(',');

    function markVisible(el) {
        el.classList.add('is-visible');
    }

    function inViewport(el, ratio) {
        var rect = el.getBoundingClientRect();
        return rect.top < vh * (ratio || 0.92) && rect.bottom > 0;
    }

    function applyStagger() {
        root.querySelectorAll(STAGGER_SEL).forEach(function (group) {
            var items = group.querySelectorAll(':scope > li, :scope > .plat-reveal');
            items.forEach(function (el, i) {
                el.style.setProperty('--plat-stagger', Math.min(i * 50, 200) + 'ms');
            });
        });
    }

    function initFlows() {
        root.querySelectorAll(FLOW_SEL).forEach(function (flow) {
            flow.classList.add('plat-flow');
            if (reduced || inViewport(flow, 0.88)) {
                flow.classList.add('is-flow-visible');
            }
        });
    }

    function initReveals() {
        var reveals = root.querySelectorAll('.plat-reveal');
        var shots = root.querySelectorAll('.plat-shot-story');

        if (reduced) {
            reveals.forEach(markVisible);
            shots.forEach(markVisible);
            html.classList.add('plat-motion-ready');
            return;
        }

        reveals.forEach(function (el) {
            if (inViewport(el, 0.94)) markVisible(el);
        });

        shots.forEach(function (el) {
            if (inViewport(el, 0.94)) markVisible(el);
        });

        html.classList.add('plat-motion-ready');

        if (!('IntersectionObserver' in window)) {
            reveals.forEach(markVisible);
            shots.forEach(markVisible);
            root.querySelectorAll('.plat-flow').forEach(function (f) {
                f.classList.add('is-flow-visible');
            });
            return;
        }

        var revealObs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    markVisible(entry.target);
                    revealObs.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });

        reveals.forEach(function (el) {
            if (!el.classList.contains('is-visible')) revealObs.observe(el);
        });

        shots.forEach(function (el) {
            if (!el.classList.contains('is-visible')) revealObs.observe(el);
        });

        var flowObs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-flow-visible');
                    flowObs.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 });

        root.querySelectorAll('.plat-flow:not(.is-flow-visible)').forEach(function (flow) {
            flowObs.observe(flow);
        });
    }

    function initParallax() {
        if (reduced) return;
        if (!window.matchMedia('(min-width: 1024px)').matches) return;

        var shots = root.querySelectorAll('.plat-shot-story--hero .plat-shot-story__frame');
        if (!shots.length) return;

        var ticking = false;
        window.addEventListener('scroll', function () {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(function () {
                var viewH = window.innerHeight;
                shots.forEach(function (frame) {
                    var shot = frame.closest('.plat-shot-story');
                    if (!shot) return;
                    var rect = shot.getBoundingClientRect();
                    if (rect.bottom < 0 || rect.top > viewH) return;
                    var offset = Math.max(-8, Math.min(8, (rect.top - viewH * 0.32) * 0.012));
                    frame.style.transform = 'translate3d(0,' + offset + 'px,0)';
                });
                ticking = false;
            });
        }, { passive: true });
    }

    function initStickyCta() {
        var sticky = document.getElementById('platStickyCta');
        if (!sticky) return;

        var mobile = window.matchMedia('(max-width: 767px)');
        var heroCta = root.querySelector(
            '.plat-crm-hero__cta, .rem-hero__cta, .sol-hero__cta, .fhub-hero__cta, .shub-hero__cta, [class*="-hero__cta"]'
        );

        function setVisible(on) {
            if (on) {
                sticky.hidden = false;
                // next frame so CSS transition runs
                requestAnimationFrame(function () {
                    sticky.classList.add('is-visible');
                });
            } else {
                sticky.classList.remove('is-visible');
                window.setTimeout(function () {
                    if (!sticky.classList.contains('is-visible')) {
                        sticky.hidden = true;
                    }
                }, 280);
            }
        }

        function sync() {
            if (!mobile.matches) {
                setVisible(false);
                return;
            }
            if (!heroCta) {
                setVisible(true);
                return;
            }
            var rect = heroCta.getBoundingClientRect();
            setVisible(rect.bottom < 8);
        }

        sync();
        window.addEventListener('scroll', sync, { passive: true });
        window.addEventListener('resize', sync, { passive: true });
        if (typeof mobile.addEventListener === 'function') {
            mobile.addEventListener('change', sync);
        } else if (typeof mobile.addListener === 'function') {
            mobile.addListener(sync);
        }
    }

    applyStagger();
    initFlows();
    initReveals();
    initParallax();
    initStickyCta();
})();
