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
        var popup = wrap.querySelector('[data-h-flow-popup]');
        var popupCard = wrap.querySelector('[data-h-flow-popup-card]');
        var popupStep = wrap.querySelector('[data-h-flow-popup-step]');
        var popupTitle = wrap.querySelector('[data-h-flow-popup-title]');
        var popupText = wrap.querySelector('[data-h-flow-popup-text]');
        var popupIcon = wrap.querySelector('[data-h-flow-popup-icon]');
        var popupClose = wrap.querySelector('[data-h-flow-popup-close]');
        var mobileDetail = wrap.querySelector('[data-h-flow-mobile-detail]');
        var mobileStep = wrap.querySelector('[data-h-flow-mobile-step]');
        var mobileTitle = wrap.querySelector('[data-h-flow-mobile-title]');
        var mobileText = wrap.querySelector('[data-h-flow-mobile-text]');
        var openIndex = -1;
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

        function closePopup() {
            if (!popup) return;
            openIndex = -1;
            popup.classList.remove('is-open');
            popup.setAttribute('hidden', '');
            nodes.forEach(function (node) {
                node.classList.remove('is-popup-open');
                var btn = node.querySelector('.h-flow__node-btn');
                if (btn) {
                    btn.setAttribute('aria-expanded', 'false');
                }
            });
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

        function positionPopup(node) {
            if (!popup || !node) return;
            var centerX = node.offsetLeft + node.offsetWidth / 2;
            var topY = node.offsetTop;
            popup.style.left = centerX + 'px';
            popup.style.top = topY + 'px';
        }

        function showPopup(index, btn) {
            if (!desktopMq.matches || !popup || !btn) return;

            if (openIndex === index && popup.classList.contains('is-open')) {
                closePopup();
                return;
            }

            var node = nodes[index];
            var accent = node.getAttribute('data-accent') || 'violet';

            if (popupStep) {
                popupStep.textContent = 'مرحله ' + btn.getAttribute('data-flow-step');
            }
            if (popupTitle) {
                popupTitle.textContent = btn.getAttribute('data-flow-title') || '';
            }
            if (popupText) {
                popupText.textContent = btn.getAttribute('data-flow-detail') || '';
            }
            if (popupIcon) {
                popupIcon.innerHTML = '<i class="fas ' + btn.getAttribute('data-flow-icon') + '" aria-hidden="true"></i>';
            }
            if (popupCard) {
                popupCard.setAttribute('data-accent', accent);
            }

            nodes.forEach(function (node, i) {
                node.classList.toggle('is-popup-open', i === index);
                var nodeBtn = node.querySelector('.h-flow__node-btn');
                if (nodeBtn) {
                    nodeBtn.setAttribute('aria-expanded', i === index ? 'true' : 'false');
                }
            });

            positionPopup(node);
            popup.removeAttribute('hidden');
            requestAnimationFrame(function () {
                popup.classList.add('is-open');
            });
            openIndex = index;
        }

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var index = parseInt(btn.getAttribute('data-h-flow-btn'), 10);
                setActive(index);
                if (desktopMq.matches) {
                    hideMobileDetail();
                    showPopup(index, btn);
                } else {
                    closePopup();
                    showMobileDetail(index, btn);
                }
            });
        });

        if (popupClose) {
            popupClose.addEventListener('click', closePopup);
        }

        document.addEventListener('click', function (event) {
            if (!popup || !popup.classList.contains('is-open')) return;
            if (event.target.closest('[data-h-flow-popup]')) return;
            if (event.target.closest('[data-h-flow-btn]')) return;
            closePopup();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closePopup();
            }
        });

        function onFlowModeChange() {
            if (!desktopMq.matches) {
                closePopup();
            } else {
                hideMobileDetail();
            }
        }

        if (typeof desktopMq.addEventListener === 'function') {
            desktopMq.addEventListener('change', onFlowModeChange);
        } else if (typeof desktopMq.addListener === 'function') {
            desktopMq.addListener(onFlowModeChange);
        }

        window.addEventListener('resize', function () {
            if (openIndex >= 0 && desktopMq.matches) {
                positionPopup(nodes[openIndex]);
            }
        }, { passive: true });

        setActive(0);

        if (!desktopMq.matches && buttons.length) {
            showMobileDetail(0, buttons[0]);
        }

        if (prefersReduced || !('IntersectionObserver' in window) || desktopMq.matches) {
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var idx = parseInt(entry.target.getAttribute('data-h-flow-step'), 10);
                    setActive(idx);
                    var activeBtn = buttons[idx];
                    if (activeBtn) {
                        showMobileDetail(idx, activeBtn);
                    }
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
        initStoryMobileReveal();
        initClimaxReveal();
        initCompare();
        initFlow();
        initPillars();
    });
})();
