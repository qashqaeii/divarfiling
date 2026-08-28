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

        var pairs = root.querySelectorAll('[data-h-compare-pair]');
        if (!pairs.length) return;

        if (prefersReduced || !('IntersectionObserver' in window)) {
            pairs.forEach(function (pair) {
                pair.classList.add('is-visible');
            });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.35, rootMargin: '0px 0px -8% 0px' });

        pairs.forEach(function (pair, index) {
            pair.style.transitionDelay = (index * 0.08) + 's';
            observer.observe(pair);
        });
    }

    function initFlow() {
        var wrap = document.querySelector('[data-h-flow-wrap]');
        if (!wrap) return;

        var track = wrap.querySelector('[data-h-flow-track]');
        var nodes = wrap.querySelectorAll('.h-flow__node[data-h-flow-step]');
        var progress = wrap.querySelector('[data-h-flow-progress]');
        var buttons = wrap.querySelectorAll('[data-h-flow-btn]');
        if (!track || !nodes.length) return;

        function setActive(index) {
            nodes.forEach(function (node, i) {
                var active = i === index;
                node.classList.toggle('is-active', active);
                var btn = node.querySelector('.h-flow__node-btn');
                if (btn) {
                    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
                }
            });
            if (progress) {
                var pct = nodes.length <= 1 ? 100 : (index / (nodes.length - 1)) * 100;
                progress.style.width = pct + '%';
            }
        }

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var index = parseInt(btn.getAttribute('data-h-flow-btn'), 10);
                setActive(index);
                if (!desktopMq.matches && track.scrollTo) {
                    var node = nodes[index];
                    if (node) {
                        var offset = node.offsetLeft - (track.clientWidth - node.offsetWidth) / 2;
                        track.scrollTo({
                            left: offset,
                            behavior: prefersReduced ? 'auto' : 'smooth',
                        });
                    }
                }
            });
        });

        setActive(0);

        if (prefersReduced || !('IntersectionObserver' in window) || desktopMq.matches) {
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    setActive(parseInt(entry.target.getAttribute('data-h-flow-step'), 10));
                }
            });
        }, {
            threshold: 0.55,
            rootMargin: '-8% 0px -38% 0px',
        });

        nodes.forEach(function (node) {
            observer.observe(node);
        });
    }

    function initPillars() {
        var root = document.querySelector('[data-h-pillars]');
        if (!root) return;

        var tabs = root.querySelectorAll('[data-h-pillar-tab]');
        var panels = root.querySelectorAll('[data-h-pillar-panel]');
        if (!tabs.length || !panels.length) return;

        function show(index) {
            tabs.forEach(function (tab, i) {
                var active = i === index;
                tab.classList.toggle('is-active', active);
                tab.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            panels.forEach(function (panel, i) {
                var active = i === index;
                panel.classList.toggle('is-active', active);
                if (active) {
                    panel.removeAttribute('hidden');
                } else {
                    panel.setAttribute('hidden', '');
                }
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                show(parseInt(tab.getAttribute('data-h-pillar-tab'), 10));
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initStoryScroll();
        initClimaxReveal();
        initCompare();
        initFlow();
        initPillars();
    });
})();
