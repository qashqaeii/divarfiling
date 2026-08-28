(function () {
    'use strict';

    var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var desktopMq = window.matchMedia('(min-width: 992px)');

    function initStoryScroll() {
        var root = document.querySelector('[data-h-story]');
        if (!root) return;

        var rail = root.querySelector('[data-h-story-rail]');
        var scenes = root.querySelectorAll('[data-h-scene]');
        var sentinels = root.querySelectorAll('[data-h-sentinel]');
        var progressBtns = root.querySelectorAll('[data-h-progress]');
        var barFill = root.querySelector('[data-h-story-bar]');
        var total = scenes.length;

        if (!total) return;

        function setScene(index) {
            var i = Math.max(0, Math.min(index, total - 1));
            scenes.forEach(function (scene, idx) {
                var active = idx === i;
                scene.classList.toggle('is-active', active);
                scene.setAttribute('aria-hidden', active ? 'false' : 'true');
            });
            progressBtns.forEach(function (btn, idx) {
                var active = idx === i;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-current', active ? 'step' : 'false');
            });
            if (barFill) {
                barFill.style.width = (((i + 1) / total) * 100) + '%';
            }
        }

        progressBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var idx = parseInt(btn.getAttribute('data-h-progress'), 10);
                setScene(idx);
                var target = sentinels[idx];
                if (target && desktopMq.matches) {
                    target.scrollIntoView({ behavior: prefersReduced ? 'auto' : 'smooth', block: 'center' });
                }
            });
        });

        if (prefersReduced || !('IntersectionObserver' in window)) {
            setScene(0);
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    setScene(parseInt(entry.target.getAttribute('data-h-sentinel'), 10));
                }
            });
        }, { threshold: 0.55, rootMargin: '-10% 0px -10% 0px' });

        function bindSentinels() {
            sentinels.forEach(function (s) { observer.observe(s); });
        }

        function unbindSentinels() {
            observer.disconnect();
        }

        function onModeChange() {
            if (desktopMq.matches && sentinels.length) {
                bindSentinels();
            } else {
                unbindSentinels();
                setScene(0);
            }
        }

        if (typeof desktopMq.addEventListener === 'function') {
            desktopMq.addEventListener('change', onModeChange);
        } else if (typeof desktopMq.addListener === 'function') {
            desktopMq.addListener(onModeChange);
        }

        onModeChange();
    }

    function initClimaxReveal() {
        var product = document.querySelector('.h-climax__product');
        if (!product) return;

        if (prefersReduced || !('IntersectionObserver' in window)) {
            product.classList.add('is-visible');
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.25 });

        observer.observe(product);
    }

    function initCompare() {
        var root = document.querySelector('[data-h-compare]');
        if (!root) return;

        var tabs = root.querySelectorAll('[data-h-compare-tab]');
        var panels = root.querySelectorAll('[data-h-compare-panel]');
        var slider = root.querySelector('[data-h-compare-slider]');

        function show(mode) {
            tabs.forEach(function (tab) {
                var active = tab.getAttribute('data-h-compare-tab') === mode;
                tab.classList.toggle('is-active', active);
                tab.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            panels.forEach(function (panel) {
                var showPanel = panel.getAttribute('data-h-compare-panel') === mode;
                panel.hidden = !showPanel;
                panel.classList.toggle('is-visible', showPanel);
            });
            var thumb = root.querySelector('[data-h-compare-thumb]');
            if (thumb) {
                thumb.style.insetInlineEnd = mode === 'after' ? '0.25rem' : 'calc(50% + 0px)';
            }
            if (slider) {
                slider.value = mode === 'after' ? '100' : '0';
            }
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                show(tab.getAttribute('data-h-compare-tab'));
            });
        });

        if (slider) {
            slider.addEventListener('input', function () {
                show(parseInt(slider.value, 10) > 50 ? 'after' : 'before');
            });
        }

        show('after');
    }

    function initFlow() {
        var wrap = document.querySelector('[data-h-flow-wrap]');
        if (!wrap) return;

        var track = wrap.querySelector('[data-h-flow-track]');
        var steps = wrap.querySelectorAll('[data-h-flow-step]');
        var progress = wrap.querySelector('[data-h-flow-progress]');
        if (!track || !steps.length) return;

        function setActive(index) {
            steps.forEach(function (step, i) {
                step.classList.toggle('is-active', i === index);
            });
            if (progress) {
                progress.style.width = (((index + 1) / steps.length) * 100) + '%';
            }
        }

        if (prefersReduced || !('IntersectionObserver' in window)) {
            setActive(0);
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    setActive(parseInt(entry.target.getAttribute('data-h-flow-step'), 10));
                }
            });
        }, { threshold: 0.6, root: track, rootMargin: '0px -20% 0px -20%' });

        steps.forEach(function (step) { observer.observe(step); });

        track.addEventListener('scroll', function () {
            if (!desktopMq.matches) {
                var center = track.scrollLeft + track.clientWidth / 2;
                var closest = 0;
                var minDist = Infinity;
                steps.forEach(function (step, i) {
                    var stepCenter = step.offsetLeft + step.offsetWidth / 2;
                    var dist = Math.abs(center - stepCenter);
                    if (dist < minDist) {
                        minDist = dist;
                        closest = i;
                    }
                });
                setActive(closest);
            }
        }, { passive: true });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initStoryScroll();
        initClimaxReveal();
        initCompare();
        initFlow();
    });
})();
