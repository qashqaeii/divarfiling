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
        var isFileChapter = scrolly.getAttribute('data-df-scrolly-chapter') === 'file';
        var visual = scrolly.querySelector('[data-df-chapter-visual]');
        var steps = isFileChapter
            ? scrolly.querySelectorAll('.df-story-file-scroll-track [data-df-step]')
            : scrolly.querySelectorAll('[data-df-step]');
        var rail = scrolly.querySelector('[data-df-rail-fill]');
        if (!steps.length) return;
        if (!isFileChapter && !visual) return;
        if (isFileChapter && !visual) return;

        var heroImgs = visual ? visual.querySelectorAll('[data-df-hero-img]') : [];
        var satellite = visual ? visual.querySelector('[data-df-hero-layer]') : null;
        var hintEl = scrolly.querySelector('[data-df-file-hint]');
        var textPanels = scrolly.querySelectorAll('[data-df-text-step]');
        var textStack = scrolly.querySelector('[data-df-file-text-stack]');
        var fileExitEl = isFileChapter ? scrolly.querySelector('[data-df-file-exit]') : null;
        var fileHandoffDone = false;
        var fileLastScrollY = window.scrollY;
        var fileHandoffTimer = null;
        var prevIndex = -1;
        var faStepFmt = typeof Intl !== 'undefined'
            ? new Intl.NumberFormat('fa-IR', { minimumIntegerDigits: 2, useGrouping: false })
            : null;
        var floatAText = scrolly.querySelector('[data-df-float-a-text]');
        var floatBText = scrolly.querySelector('[data-df-float-b-text]');
        var filePin = isFileChapter ? scrolly.querySelector('.df-story-file-pin') : null;

        function formatFileStepNumber(n) {
            if (faStepFmt) return faStepFmt.format(n);
            return String(n).padStart(2, '0');
        }

        function measureFileTextStack() {
            if (!isFileChapter || !textStack) return;
            if (!stickyMq.matches) return;
            textStack.classList.add('is-measuring');
            var maxH = 0;
            textPanels.forEach(function (panel) {
                maxH = Math.max(maxH, panel.offsetHeight);
            });
            textStack.classList.remove('is-measuring');
            if (maxH > 0) {
                textStack.style.setProperty('--df-file-stack-h', Math.ceil(maxH) + 'px');
            }
        }

        function syncFilePinLayout() {
            if (!isFileChapter || !filePin) return;
            measureFileTextStack();
            var compact = window.innerHeight < 920 || window.matchMedia('(max-height: 900px)').matches;
            filePin.classList.toggle('df-story-file-pin--compact', compact && stickyMq.matches);
            if (!stickyMq.matches) {
                filePin.classList.add('df-story-file-pin--flow');
                return;
            }
            filePin.classList.remove('df-story-file-pin--flow');
            if (window.innerHeight <= 680) {
                filePin.classList.add('df-story-file-pin--flow');
            }
        }

        if (heroImgs.length) {
            heroImgs.forEach(function (img) {
                var preload = new Image();
                preload.src = img.getAttribute('src') || '';
            });
        }

        function scrollToNextChapter() {
            var next = document.getElementById('df-story-ch-match');
            if (!next) return;
            var navEl = document.documentElement;
            var navRaw = getComputedStyle(navEl).getPropertyValue('--h-nav-offset').trim();
            var navPx = parseFloat(navRaw) || 72;
            if (navRaw.indexOf('rem') !== -1) {
                navPx = parseFloat(navRaw) * parseFloat(getComputedStyle(navEl).fontSize || '16');
            }
            var y = next.getBoundingClientRect().top + window.pageYOffset - navPx - 10;
            window.scrollTo({ top: Math.max(0, y), behavior: reduced ? 'auto' : 'smooth' });
        }

        function maybeFileChapterHandoff(stepIndex) {
            if (!isFileChapter || !stickyMq.matches || !fileExitEl || stepIndex !== steps.length - 1) {
                if (stepIndex < steps.length - 1) fileHandoffDone = false;
                return;
            }
            if (fileHandoffDone) return;

            var scrollingDown = window.scrollY >= fileLastScrollY - 2;
            fileLastScrollY = window.scrollY;
            if (!scrollingDown) return;

            var er = fileExitEl.getBoundingClientRect();
            var lastStep = steps[steps.length - 1];
            var lastRect = lastStep ? lastStep.getBoundingClientRect() : null;
            var pastStepFour = lastRect && lastRect.bottom < window.innerHeight * 0.36;
            var inExitZone = er.top < window.innerHeight * 0.72;
            if (!pastStepFour && !inExitZone) return;

            fileHandoffDone = true;
            scrollToNextChapter();
            if (fileHandoffTimer) window.clearTimeout(fileHandoffTimer);
            fileHandoffTimer = window.setTimeout(function () {
                fileHandoffDone = false;
            }, 1400);
        }

        function applyCore(i) {
            if (i < 0 || i >= steps.length) i = 0;

            steps.forEach(function (step, idx) {
                step.classList.toggle('is-active', idx === i);
            });

            var step = steps[i];
            if (!step) return;

            if (visual) {
                if (i !== prevIndex) {
                    visual.setAttribute('data-df-dir', i > prevIndex ? 'fwd' : 'back');
                }

                var tagSet = step.getAttribute('data-df-tags') || '';
                if (tagSet) visual.setAttribute('data-df-tag-set', tagSet);
                else visual.removeAttribute('data-df-tag-set');

                var heroKey = step.getAttribute('data-df-hero-key') || '';
                visual.setAttribute('data-df-hero-key', heroKey);
                visual.setAttribute('data-df-active-step', String(i));

                heroImgs.forEach(function (img) {
                    var onImg = img.getAttribute('data-df-hero-img') === heroKey;
                    img.classList.toggle('is-active', onImg);
                    img.classList.remove('is-leaving', 'is-entering');
                    if (img.getAttribute('alt')) {
                        img.setAttribute('aria-hidden', onImg ? 'false' : 'true');
                    }
                });

                if (satellite) {
                    satellite.classList.toggle('is-active', heroKey === 'binder');
                }

                visual.classList.toggle('is-linked', step.getAttribute('data-df-connect') === '1');
            }

            textPanels.forEach(function (panel, idx) {
                var on = idx === i;
                panel.classList.toggle('is-active', on);
                panel.classList.remove('is-leaving', 'is-entering');
                panel.setAttribute('aria-hidden', on ? 'false' : 'true');
            });

            if (rail) {
                rail.style.height = (((i + 1) / steps.length) * 100) + '%';
            }

            if (hintEl) {
                hintEl.textContent = step.getAttribute('data-df-hint') || '';
                hintEl.classList.remove('is-leaving', 'is-entering');
            }

            if (textStack) {
                textStack.setAttribute('data-df-step-index', String(i));
            }

            scrolly.querySelectorAll('[data-df-file-progress], [data-df-file-timeline]').forEach(function (el) {
                el.setAttribute('data-df-active', String(i));
            });

            scrolly.querySelectorAll('[data-df-file-counter]').forEach(function (el) {
                el.textContent = formatFileStepNumber(i + 1);
            });
            scrolly.querySelectorAll('[data-df-file-total]').forEach(function (el) {
                el.textContent = formatFileStepNumber(steps.length);
            });

            if (floatAText) {
                floatAText.textContent = step.getAttribute('data-df-float-a') || '';
            }
            if (floatBText) {
                floatBText.textContent = step.getAttribute('data-df-float-b') || '';
            }

            prevIndex = i;
        }

        function apply(i) {
            if (i < 0 || i >= steps.length) i = 0;
            if (isFileChapter && i !== prevIndex && prevIndex >= 0 && !reduced) {
                var pin = scrolly.querySelector('.df-story-file-pin');
                if (pin) pin.classList.add('is-switching');
            }
            applyCore(i);
            if (isFileChapter && !reduced) {
                var pinEl = scrolly.querySelector('.df-story-file-pin');
                if (pinEl && pinEl.classList.contains('is-switching')) {
                    window.setTimeout(function () {
                        pinEl.classList.remove('is-switching');
                    }, 420);
                }
            }
        }

        function refresh() {
            if (isFileChapter && !stickyMq.matches) return;
            var i = pickScrollyStepIndex(steps);
            apply(i);
            if (isFileChapter) maybeFileChapterHandoff(i);
        }

        apply(0);
        if (isFileChapter) {
            syncFilePinLayout();
            window.requestAnimationFrame(function () {
                syncFilePinLayout();
            });
            window.addEventListener('resize', syncFilePinLayout);
            if (typeof stickyMq.addEventListener === 'function') {
                stickyMq.addEventListener('change', syncFilePinLayout);
            } else if (typeof stickyMq.addListener === 'function') {
                stickyMq.addListener(syncFilePinLayout);
            }
        }
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
