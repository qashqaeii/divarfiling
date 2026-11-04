(function () {
    'use strict';

    var root = document.querySelector('[data-df-home-story]');
    if (!root) return;

    var body = document.querySelector('.mk-home-body');
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var stickyMq = window.matchMedia('(min-width: 992px) and (min-height: 680px)');

    root.classList.add('js-ready');
    if (body) body.classList.add('js-story-motion', 'js-ready');

    var scrollTick = false;

    function onScroll(cb) {
        if (scrollTick) return;
        scrollTick = true;
        requestAnimationFrame(function () {
            scrollTick = false;
            cb();
        });
    }

    function initReveal() {
        var scope = body || root;
        var nodes = scope.querySelectorAll('[data-df-a]');
        if (!nodes.length) return;

        if (reduced || !('IntersectionObserver' in window)) {
            nodes.forEach(function (n) { n.classList.add('is-in'); });
            return;
        }

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) e.target.classList.add('is-in');
            });
        }, { threshold: 0.08, rootMargin: '0px 0px -4% 0px' });

        nodes.forEach(function (n, i) {
            n.style.setProperty('--df-i', String(i % 5));
            io.observe(n);
        });
    }

    function pickScrollyStepIndex(steps) {
        if (!steps.length) return 0;
        var anchor = window.innerHeight * (stickyMq.matches ? 0.42 : 0.36);
        var chosen = 0;

        steps.forEach(function (step, i) {
            var r = step.getBoundingClientRect();
            var trigger = r.top + r.height * 0.5;
            if (trigger <= anchor) chosen = i;
        });
        return chosen;
    }

    function pickNearestStepIndex(steps) {
        if (!steps.length) return 0;
        var anchor = window.innerHeight * 0.38;
        var best = 0;
        var bestDist = Infinity;

        steps.forEach(function (step, i) {
            var r = step.getBoundingClientRect();
            var mid = r.top + r.height * 0.4;
            var dist = Math.abs(mid - anchor);
            if (dist < bestDist) {
                bestDist = dist;
                best = i;
            }
        });
        return best;
    }

    function bindScrolly(scrolly) {
        var visual = scrolly.querySelector('[data-df-chapter-visual]');
        var steps = scrolly.querySelectorAll('[data-df-step]');
        var rail = scrolly.querySelector('[data-df-rail-fill]');
        if (!visual || !steps.length) return;

        var heroImgs = visual.querySelectorAll('[data-df-hero-img]');
        var satellite = visual.querySelector('[data-df-hero-layer]');
        var hintEl = scrolly.querySelector('[data-df-file-hint]');
        var prevIndex = 0;

        heroImgs.forEach(function (img) {
            var preload = new Image();
            preload.src = img.getAttribute('src') || '';
        });
        if (satellite) {
            var preloadSat = new Image();
            preloadSat.src = satellite.getAttribute('src') || '';
        }

        function apply(i) {
            if (i < 0 || i >= steps.length) i = 0;

            steps.forEach(function (step, idx) {
                step.classList.toggle('is-active', idx === i);
                step.classList.toggle('is-before', idx < i);
                step.classList.toggle('is-after', idx > i);
            });

            var step = steps[i];
            if (!step) return;

            if (i !== prevIndex) {
                visual.setAttribute('data-df-dir', i > prevIndex ? 'fwd' : 'back');
                prevIndex = i;
            }

            var tagSet = step.getAttribute('data-df-tags') || '';
            if (tagSet) visual.setAttribute('data-df-tag-set', tagSet);
            else visual.removeAttribute('data-df-tag-set');

            var heroKey = step.getAttribute('data-df-hero-key') || '';
            visual.setAttribute('data-df-hero-key', heroKey);
            visual.setAttribute('data-df-active-step', String(i));

            heroImgs.forEach(function (img) {
                var on = img.getAttribute('data-df-hero-img') === heroKey;
                img.classList.toggle('is-active', on);
                if (on && img.getAttribute('alt')) {
                    img.removeAttribute('aria-hidden');
                } else if (!on && img.getAttribute('alt')) {
                    img.setAttribute('aria-hidden', 'true');
                }
            });

            if (satellite) {
                satellite.classList.toggle('is-active', heroKey === 'duo');
            }

            visual.classList.toggle('is-linked', step.getAttribute('data-df-connect') === '1');

            if (rail) {
                rail.style.height = (((i + 1) / steps.length) * 100) + '%';
            }

            if (hintEl) {
                hintEl.textContent = step.getAttribute('data-df-hint') || '';
            }
        }

        function refresh() {
            apply(pickScrollyStepIndex(steps));
        }

        apply(0);
        refresh();
        window.addEventListener('scroll', function () { onScroll(refresh); }, { passive: true });
        window.addEventListener('resize', refresh);

        if (typeof stickyMq.addEventListener === 'function') {
            stickyMq.addEventListener('change', refresh);
        } else if (typeof stickyMq.addListener === 'function') {
            stickyMq.addListener(refresh);
        }
    }

    function initPath() {
        var links = root.querySelectorAll('[data-df-path]');
        if (!links.length || !('IntersectionObserver' in window)) return;

        var map = {};
        links.forEach(function (link) {
            var id = link.getAttribute('data-df-path');
            var el = id ? document.getElementById(id) : null;
            if (el) map[id] = link;
        });

        var io = new IntersectionObserver(function (entries) {
            var top = null;
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    if (!top || e.intersectionRatio > top.ratio) {
                        top = { id: e.target.id, ratio: e.intersectionRatio };
                    }
                }
            });
            if (!top) return;
            links.forEach(function (l) {
                l.classList.toggle('is-current', l.getAttribute('data-df-path') === top.id);
            });
        }, { threshold: [0.15, 0.35], rootMargin: '-40% 0px -45% 0px' });

        Object.keys(map).forEach(function (id) {
            io.observe(document.getElementById(id));
        });
    }

    function initFollow() {
        var flow = root.querySelector('[data-df-follow-flow]');
        if (!flow) return;
        var steps = flow.querySelectorAll('[data-df-follow-step]');
        if (!steps.length) return;

        function refresh() {
            if (reduced) {
                steps.forEach(function (s) { s.classList.add('is-lit'); });
                return;
            }
            var i = pickNearestStepIndex(steps);
            steps.forEach(function (s, idx) {
                s.classList.toggle('is-lit', idx === i);
            });
        }

        refresh();
        window.addEventListener('scroll', function () { onScroll(refresh); }, { passive: true });
        window.addEventListener('resize', refresh);
    }

    function initStudio() {
        var cinema = root.querySelector('[data-df-studio]');
        if (!cinema) return;
        if (reduced) {
            cinema.classList.add('is-live');
            return;
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                cinema.classList.toggle('is-live', e.isIntersecting);
            });
        }, { threshold: 0.15 });
        io.observe(cinema);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initReveal();
        initPath();
        root.querySelectorAll('[data-df-sticky-chapter]').forEach(bindScrolly);
        initFollow();
        initStudio();
    });
})();
