(function () {
    'use strict';

    var root = document.querySelector('[data-df-home-story]');
    if (!root) return;

    var body = document.querySelector('.mk-home-body');
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var stickyMq = window.matchMedia('(min-width: 992px)');

    root.classList.add('js-ready');
    if (body) body.classList.add('js-story-motion', 'js-ready');

    var scrollFrameQueue = [];
    var scrollFrameScheduled = false;

    function onScroll(cb) {
        scrollFrameQueue.push(cb);
        if (scrollFrameScheduled) return;
        scrollFrameScheduled = true;
        requestAnimationFrame(function () {
            scrollFrameScheduled = false;
            var queue = scrollFrameQueue.slice();
            scrollFrameQueue.length = 0;
            queue.forEach(function (fn) {
                fn();
            });
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
        var pinTrack = scrolly.querySelector('.df-story-file-scroll-track');
        var isPinChapter = !!pinTrack;
        if (!isPinChapter) return;

        var visual = scrolly.querySelector('[data-df-chapter-visual]');
        var steps = pinTrack.querySelectorAll('[data-df-step]');
        if (!steps.length || !visual) return;

        var handoffTargetId = scrolly.getAttribute('data-df-handoff-target') || '';

        var heroImgs = visual ? visual.querySelectorAll('[data-df-hero-img]') : [];
        var satellite = visual ? visual.querySelector('[data-df-hero-layer]') : null;
        var hintEl = scrolly.querySelector('[data-df-file-hint]');
        var textPanels = scrolly.querySelectorAll('[data-df-text-step]');
        var textStack = scrolly.querySelector('[data-df-file-text-stack]');
        var fileExitEl = scrolly.querySelector('[data-df-file-exit]');
        var fileHandoffDone = false;
        var fileLastScrollY = window.scrollY;
        var fileHandoffTimer = null;
        var prevIndex = -1;
        var faStepFmt = typeof Intl !== 'undefined'
            ? new Intl.NumberFormat('fa-IR', { minimumIntegerDigits: 2, useGrouping: false })
            : null;
        var floatAText = scrolly.querySelector('[data-df-float-a-text]');
        var floatBText = scrolly.querySelector('[data-df-float-b-text]');
        var filePin = scrolly.querySelector('.df-story-file-pin');

        function formatFileStepNumber(n) {
            if (faStepFmt) return faStepFmt.format(n);
            return String(n).padStart(2, '0');
        }

        function measureChapterBlockHeight(withCompact) {
            if (!filePin) return 0;
            var bodyEl = filePin.querySelector('.df-story-file-body');
            var footEl = filePin.querySelector('.df-story-file-foot');
            var canvas = filePin.querySelector('.df-story-file-canvas');
            if (!bodyEl || !footEl) return 0;

            filePin.classList.toggle('df-story-file-pin--compact', !!withCompact);
            filePin.classList.add('df-story-file-pin--flow');

            var gapRaw = canvas ? getComputedStyle(canvas).gap : '0';
            var gap = parseFloat(gapRaw) || 24;
            var total = Math.ceil(bodyEl.scrollHeight + footEl.scrollHeight + gap);

            filePin.classList.remove('df-story-file-pin--flow');
            return total;
        }

        function pinContentFitsSticky(pinBudget, withCompact) {
            var need = measureChapterBlockHeight(withCompact);
            return need > 0 && need <= pinBudget - 32;
        }

        function verifyStickyPinFits() {
            if (!filePin || filePin.classList.contains('df-story-file-pin--flow')) return true;
            var bodyEl = filePin.querySelector('.df-story-file-body');
            var footEl = filePin.querySelector('.df-story-file-foot');
            var canvas = filePin.querySelector('.df-story-file-canvas');
            if (!bodyEl || !footEl || !canvas) return true;
            var gapRaw = getComputedStyle(canvas).gap;
            var gap = parseFloat(gapRaw) || 24;
            var need = bodyEl.scrollHeight + footEl.scrollHeight + gap;
            return need <= filePin.clientHeight + 2;
        }

        function getNavOffsetPx() {
            var navEl = document.documentElement;
            var navRaw = getComputedStyle(navEl).getPropertyValue('--h-nav-offset').trim();
            if (!navRaw) {
                navRaw = getComputedStyle(document.documentElement).getPropertyValue('--df-file-nav').trim();
            }
            var navPx = parseFloat(navRaw) || 72;
            if (navRaw.indexOf('rem') !== -1) {
                navPx = parseFloat(navRaw) * parseFloat(getComputedStyle(navEl).fontSize || '16');
            }
            return navPx;
        }

        function getPinHeightPx() {
            var pinRaw = scrolly.style.getPropertyValue('--df-file-pin-h').trim();
            if (!pinRaw) {
                pinRaw = filePin ? filePin.style.getPropertyValue('--df-file-pin-h').trim() : '';
            }
            if (!pinRaw) {
                pinRaw = getComputedStyle(scrolly).getPropertyValue('--df-file-pin-h').trim();
            }
            var pinH = parseFloat(pinRaw);
            if (!pinH || pinH < 240) {
                pinH = filePin && filePin.clientHeight > 240 ? filePin.clientHeight : getPinBudgetPx();
            }
            return pinH;
        }

        function scrollyChapterInView() {
            var r = scrolly.getBoundingClientRect();
            var navPx = getNavOffsetPx();
            return r.bottom > navPx + 48 && r.top < window.innerHeight * 0.94;
        }

        function isPinStuck() {
            if (!filePin || scrolly.classList.contains('df-story-scrolly--pin-flow')) return false;
            var navPx = getNavOffsetPx();
            var top = filePin.getBoundingClientRect().top;
            return top <= navPx + 14 && top >= navPx - 6;
        }

        function pickPinChapterStepIndex() {
            if (!steps.length) return 0;

            var sRect = scrolly.getBoundingClientRect();
            if (sRect.top > window.innerHeight * 0.55) return 0;
            if (sRect.bottom < window.innerHeight * 0.28) return steps.length - 1;

            var pinH = getPinHeightPx();

            if (pinTrack && filePin && isPinStuck()) {
                var trackTop = pinTrack.getBoundingClientRect().top;
                var pinBottom = filePin.getBoundingClientRect().bottom;
                var progress = (pinBottom - trackTop) / pinH;
                var idx = Math.floor(progress - 0.08);
                if (idx < 0) idx = 0;
                if (idx >= steps.length) idx = steps.length - 1;
                return idx;
            }

            var navPx = getNavOffsetPx();
            var pinRect = filePin ? filePin.getBoundingClientRect() : null;
            var anchor = pinRect && pinRect.height > 32
                ? pinRect.top + pinRect.height * 0.42
                : navPx + Math.max(120, (window.innerHeight - navPx) * 0.38);
            var chosen = 0;

            steps.forEach(function (step, i) {
                var r = step.getBoundingClientRect();
                if (r.height < 4) return;
                var trigger = r.top + r.height * 0.42;
                if (trigger <= anchor) chosen = i;
            });
            return chosen;
        }

        function syncScrollTrackHeight() {
            if (!pinTrack || !filePin) return;
            if (scrolly.classList.contains('df-story-scrolly--pin-flow')) {
                pinTrack.style.minHeight = '';
                steps.forEach(function (seg) { seg.style.minHeight = ''; });
                return;
            }
            var pinH = getPinHeightPx();
            steps.forEach(function (seg) {
                seg.style.minHeight = pinH + 'px';
            });
            pinTrack.style.minHeight = (steps.length * pinH) + 'px';
        }

        function getPinBudgetPx() {
            return Math.max(320, window.innerHeight - getNavOffsetPx() - 12);
        }

        function setPinFlowMode(on) {
            if (!filePin) return;
            filePin.classList.toggle('df-story-file-pin--flow', on);
            scrolly.classList.toggle('df-story-scrolly--pin-flow', on);
        }

        var syncLayoutTimer = null;
        function syncFilePinLayout() {
            if (!filePin) return;

            if (!stickyMq.matches) {
                filePin.classList.remove('df-story-file-pin--compact');
                setPinFlowMode(true);
                return;
            }

            setPinFlowMode(false);

            var pinBudget = getPinBudgetPx();
            var pinHStr = pinBudget + 'px';
            scrolly.style.setProperty('--df-file-pin-h', pinHStr);
            filePin.style.setProperty('--df-file-pin-h', pinHStr);

            filePin.classList.remove('df-story-file-pin--compact');
            if (!pinContentFitsSticky(pinBudget, false) && pinContentFitsSticky(pinBudget, true)) {
                filePin.classList.add('df-story-file-pin--compact');
            }

            if (!verifyStickyPinFits()) {
                filePin.classList.add('df-story-file-pin--compact');
            }

            syncScrollTrackHeight();
        }

        function pickFileChapterStepIndex() {
            if (!steps.length) return 0;
            if (scrolly.classList.contains('df-story-scrolly--pin-flow') || !stickyMq.matches) {
                return pickScrollyStepIndex(steps);
            }
            return pickPinChapterStepIndex();
        }

        function syncFilePinLayoutAndRefresh() {
            if (syncLayoutTimer) window.clearTimeout(syncLayoutTimer);
            syncLayoutTimer = window.setTimeout(function () {
                syncLayoutTimer = null;
                syncFilePinLayout();
                if (stickyMq.matches) {
                    apply(pickFileChapterStepIndex());
                }
            }, 50);
        }

        if (heroImgs.length) {
            heroImgs.forEach(function (img) {
                var preload = new Image();
                preload.onload = function () {
                    syncFilePinLayoutAndRefresh();
                };
                preload.src = img.getAttribute('src') || '';
            });
        }

        function scrollToNextChapter() {
            if (!handoffTargetId) return;
            var next = document.getElementById(handoffTargetId);
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
            if (!handoffTargetId || !stickyMq.matches || !fileExitEl || stepIndex !== steps.length - 1) {
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
            var pastLastStep = lastRect && lastRect.bottom < window.innerHeight * 0.36;
            var inExitZone = er.top < window.innerHeight * 0.72;
            if (!pastLastStep && !inExitZone) return;

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
                if ('inert' in panel) {
                    if (on) {
                        panel.removeAttribute('inert');
                    } else {
                        panel.setAttribute('inert', '');
                    }
                }
            });

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
            if (i !== prevIndex && prevIndex >= 0 && !reduced) {
                var pin = scrolly.querySelector('.df-story-file-pin');
                if (pin) pin.classList.add('is-switching');
            }
            applyCore(i);
            if (!reduced) {
                var pinEl = scrolly.querySelector('.df-story-file-pin');
                if (pinEl && pinEl.classList.contains('is-switching')) {
                    window.setTimeout(function () {
                        pinEl.classList.remove('is-switching');
                    }, 420);
                }
            }
        }

        function refresh() {
            if (!scrollyChapterInView()) return;
            var i = pickFileChapterStepIndex();
            apply(i);
            if (stickyMq.matches) {
                maybeFileChapterHandoff(i);
            }
        }

        apply(0);
        {
            syncFilePinLayout();
            syncScrollTrackHeight();
            apply(pickFileChapterStepIndex());
            window.requestAnimationFrame(function () {
                syncFilePinLayout();
                syncScrollTrackHeight();
                apply(pickFileChapterStepIndex());
            });
            window.addEventListener('resize', syncFilePinLayoutAndRefresh);
            if (typeof stickyMq.addEventListener === 'function') {
                stickyMq.addEventListener('change', syncFilePinLayoutAndRefresh);
            } else if (typeof stickyMq.addListener === 'function') {
                stickyMq.addListener(syncFilePinLayoutAndRefresh);
            }
            if (document.fonts && document.fonts.ready) {
                document.fonts.ready.then(function () {
                    syncFilePinLayoutAndRefresh();
                });
            }
            window.addEventListener('load', syncFilePinLayoutAndRefresh, { once: true });
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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initStoryModules);
    } else {
        initStoryModules();
    }

    function initStoryModules() {
        initReveal();
        initPath();
        root.querySelectorAll('[data-df-sticky-chapter]').forEach(bindScrolly);
        initFollow();
        initStudio();
    }
})();
