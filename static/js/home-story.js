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
                var pct = (((i + 1) / total) * 100) + '%';
                if (barFill.classList.contains('h-story__timeline-fill')) {
                    barFill.style.height = pct;
                } else {
                    barFill.style.width = pct;
                }
            }
            var activeScene = scenes[i];
            if (activeScene && rail) {
                var accent = activeScene.getAttribute('data-accent') || 'violet';
                rail.style.setProperty('--h-story-active-accent', 'var(--h-story-accent-' + accent + ', #7c3aed)');
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

        setScene(0);

        if (prefersReduced || !('IntersectionObserver' in window)) {
            return;
        }

        var visibleScenes = new Map();

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                var idx = parseInt(entry.target.getAttribute('data-h-sentinel'), 10);
                if (entry.isIntersecting) {
                    visibleScenes.set(idx, entry.intersectionRatio);
                } else {
                    visibleScenes.delete(idx);
                }
            });

            if (!visibleScenes.size) return;

            var bestIdx = 0;
            var bestRatio = -1;
            visibleScenes.forEach(function (ratio, idx) {
                if (ratio > bestRatio) {
                    bestRatio = ratio;
                    bestIdx = idx;
                }
            });

            setScene(bestIdx);
        }, {
            threshold: [0, 0.15, 0.35, 0.55, 0.75, 1],
            rootMargin: '-14% 0px -14% 0px',
        });

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

    function initStoryMobileReveal() {
        var cards = document.querySelectorAll('.h-story__mobile-card');
        if (!cards.length) return;

        if (prefersReduced || !('IntersectionObserver' in window)) {
            cards.forEach(function (card) {
                card.classList.add('is-inview');
            });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-inview');
                }
            });
        }, { threshold: 0.2, rootMargin: '-6% 0px -8% 0px' });

        cards.forEach(function (card) {
            observer.observe(card);
        });
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
        var spotlight = wrap.querySelector('[data-h-flow-spotlight]');
        var spotlightStep = wrap.querySelector('[data-h-flow-spotlight-step]');
        var spotlightTitle = wrap.querySelector('[data-h-flow-spotlight-title]');
        var spotlightText = wrap.querySelector('[data-h-flow-spotlight-text]');
        var spotlightIcon = wrap.querySelector('[data-h-flow-spotlight-icon]');
        var mobileDetail = wrap.querySelector('[data-h-flow-mobile-detail]');
        var mobileStep = wrap.querySelector('[data-h-flow-mobile-step]');
        var mobileTitle = wrap.querySelector('[data-h-flow-mobile-title]');
        var mobileText = wrap.querySelector('[data-h-flow-mobile-text]');
        if (!track || !nodes.length) return;

        function progressPct(index) {
            return nodes.length <= 1 ? 100 : (index / (nodes.length - 1)) * 100;
        }

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
                progress.style.width = progressPct(index) + '%';
            }
        }

        function fillDetail(btn, index) {
            if (!btn) return;
            var node = nodes[index];
            var accent = (node && node.getAttribute('data-accent')) || 'violet';
            var stepLabel = 'مرحله ' + (btn.getAttribute('data-flow-step') || '');
            var title = btn.getAttribute('data-flow-title') || '';
            var detail = btn.getAttribute('data-flow-detail') || '';
            var iconClass = btn.getAttribute('data-flow-icon') || '';

            if (spotlight) {
                spotlight.setAttribute('data-accent', accent);
            }
            if (spotlightStep) {
                spotlightStep.textContent = stepLabel;
            }
            if (spotlightTitle) {
                spotlightTitle.textContent = title;
            }
            if (spotlightText) {
                spotlightText.textContent = detail;
            }
            if (spotlightIcon) {
                spotlightIcon.innerHTML = '<i class="fas ' + iconClass + '" aria-hidden="true"></i>';
            }
        }

        function showMobileDetail(index, btn) {
            if (!mobileDetail || !btn || desktopMq.matches) return;

            if (mobileStep) {
                mobileStep.textContent = 'مرحله ' + (btn.getAttribute('data-flow-step') || '');
            }
            if (mobileTitle) {
                mobileTitle.textContent = btn.getAttribute('data-flow-title') || '';
            }
            if (mobileText) {
                mobileText.textContent = btn.getAttribute('data-flow-detail') || '';
            }

            mobileDetail.removeAttribute('hidden');
            requestAnimationFrame(function () {
                mobileDetail.classList.add('is-visible');
            });
        }

        function hideMobileDetail() {
            if (!mobileDetail) return;
            mobileDetail.classList.remove('is-visible');
            mobileDetail.setAttribute('hidden', '');
        }

        function selectStep(index) {
            var btn = buttons[index];
            if (!btn) return;
            setActive(index);
            fillDetail(btn, index);
            if (desktopMq.matches) {
                hideMobileDetail();
            } else {
                showMobileDetail(index, btn);
            }
        }

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var index = parseInt(btn.getAttribute('data-h-flow-btn'), 10);
                selectStep(index);
            });
        });

        function onFlowModeChange() {
            if (desktopMq.matches) {
                hideMobileDetail();
                var activeBtn = buttons[0];
                nodes.forEach(function (node, i) {
                    if (node.classList.contains('is-active')) {
                        activeBtn = buttons[i];
                    }
                });
                if (activeBtn) {
                    var idx = parseInt(activeBtn.getAttribute('data-h-flow-btn'), 10);
                    fillDetail(activeBtn, idx);
                }
            } else if (buttons.length) {
                var activeIndex = 0;
                nodes.forEach(function (node, i) {
                    if (node.classList.contains('is-active')) {
                        activeIndex = i;
                    }
                });
                showMobileDetail(activeIndex, buttons[activeIndex]);
            }
        }

        if (typeof desktopMq.addEventListener === 'function') {
            desktopMq.addEventListener('change', onFlowModeChange);
        } else if (typeof desktopMq.addListener === 'function') {
            desktopMq.addListener(onFlowModeChange);
        }

        selectStep(0);

        if (prefersReduced || !('IntersectionObserver' in window) || desktopMq.matches) {
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var idx = parseInt(entry.target.getAttribute('data-h-flow-step'), 10);
                    selectStep(idx);
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

    function initIntelligence() {
        var voice = document.querySelector('[data-h-intel-voice]');
        if (!voice) return;

        var tabs = voice.querySelectorAll('[data-h-intel-voice-tab]');
        var demos = voice.querySelectorAll('[data-h-intel-voice-demo]');
        if (!tabs.length || !demos.length) return;

        function show(index) {
            tabs.forEach(function (tab, i) {
                var active = i === index;
                tab.classList.toggle('is-active', active);
                tab.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            demos.forEach(function (demo, i) {
                var active = i === index;
                demo.classList.toggle('is-active', active);
                if (active) {
                    demo.removeAttribute('hidden');
                } else {
                    demo.setAttribute('hidden', '');
                }
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                show(parseInt(tab.getAttribute('data-h-intel-voice-tab'), 10));
            });
            tab.addEventListener('keydown', function (e) {
                if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
                e.preventDefault();
                var idx = parseInt(tab.getAttribute('data-h-intel-voice-tab'), 10);
                if (e.key === 'ArrowLeft') show((idx + 1) % tabs.length);
                else show((idx - 1 + tabs.length) % tabs.length);
            });
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
        initStoryMobileReveal();
        initCompare();
        initFlow();
        initIntelligence();
        initPillars();
    });
})();
