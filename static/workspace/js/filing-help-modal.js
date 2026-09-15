(function () {
    function initFilingHelpModal(modal) {
        if (!modal || modal.dataset.flHelpInit === '1') return;
        modal.dataset.flHelpInit = '1';

        var tabs = modal.querySelectorAll('[data-fl-help-tab]');
        var panes = modal.querySelectorAll('[data-fl-help-pane]');
        var body = modal.querySelector('.fl-help-modal__body');
        var progress = modal.querySelector('.fl-help-modal__scroll-progress');
        var nav = modal.querySelector('.fl-help-modal__nav');
        var indicator = modal.querySelector('.fl-help-modal__nav-indicator');
        var defaultTab = modal.getAttribute('data-fl-help-default') || 'start';

        function moveIndicator(activeBtn) {
            if (!nav || !indicator || !activeBtn) return;
            if (window.matchMedia('(max-width: 768px)').matches) return;
            var rtl = window.getComputedStyle(nav).direction === 'rtl';
            var offset = rtl
                ? nav.clientWidth - activeBtn.offsetLeft - activeBtn.offsetWidth
                : activeBtn.offsetLeft;
            indicator.style.width = activeBtn.offsetWidth + 'px';
            indicator.style.insetInlineStart = offset + 'px';
            indicator.style.transform = 'none';
        }

        function updateScrollProgress() {
            if (!body || !progress) return;
            var max = body.scrollHeight - body.clientHeight;
            var ratio = max > 0 ? body.scrollTop / max : 0;
            progress.style.transform = 'scaleX(' + Math.min(1, Math.max(0, ratio)) + ')';
        }

        function replayPaneMotion(pane) {
            if (!pane) return;
            pane.classList.remove('is-active');
            void pane.offsetWidth;
            pane.classList.add('is-active');
        }

        function activateTab(id) {
            var activeBtn = null;
            var activePane = null;
            tabs.forEach(function (btn) {
                var on = btn.getAttribute('data-fl-help-tab') === id;
                btn.classList.toggle('is-active', on);
                btn.setAttribute('aria-selected', on ? 'true' : 'false');
                if (on) activeBtn = btn;
            });
            panes.forEach(function (pane) {
                var on = pane.getAttribute('data-fl-help-pane') === id;
                pane.classList.toggle('is-active', on);
                if (on) {
                    activePane = pane;
                    pane.removeAttribute('hidden');
                    replayPaneMotion(pane);
                } else {
                    pane.setAttribute('hidden', '');
                }
            });
            if (body) body.scrollTop = 0;
            updateScrollProgress();
            requestAnimationFrame(function () { moveIndicator(activeBtn); });
        }

        function switchTab(id) {
            modal.classList.add('is-switching');
            activateTab(id);
            window.setTimeout(function () {
                modal.classList.remove('is-switching');
            }, 360);
        }

        tabs.forEach(function (btn, index) {
            btn.addEventListener('click', function () {
                switchTab(btn.getAttribute('data-fl-help-tab'));
            });
            btn.addEventListener('keydown', function (e) {
                if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
                e.preventDefault();
                var dir = e.key === 'ArrowRight' ? 1 : -1;
                var rtl = nav && window.getComputedStyle(nav).direction === 'rtl';
                if (rtl) dir *= -1;
                var next = (index + dir + tabs.length) % tabs.length;
                tabs[next].focus();
                switchTab(tabs[next].getAttribute('data-fl-help-tab'));
            });
        });

        if (body) body.addEventListener('scroll', updateScrollProgress, { passive: true });

        modal._flHelpActivate = activateTab;
        modal._flHelpMoveIndicator = function () {
            moveIndicator(modal.querySelector('.fl-help-modal__nav-btn.is-active'));
        };

        modal.addEventListener('click', function (e) {
            if (e.target.closest('[data-modal-close]')) {
                setTimeout(function () { activateTab(defaultTab); }, 280);
            }
        });

        activateTab(defaultTab);
    }

    document.querySelectorAll('.fl-help-modal').forEach(initFilingHelpModal);

    document.querySelectorAll('[data-modal-open]').forEach(function (trigger) {
        var targetId = trigger.getAttribute('data-modal-open');
        if (!targetId) return;
        var target = document.getElementById(targetId);
        if (!target || !target.classList.contains('fl-help-modal')) return;
        trigger.addEventListener('click', function () {
            var defaultTab = target.getAttribute('data-fl-help-default') || 'start';
            if (target._flHelpActivate) target._flHelpActivate(defaultTab);
        });
    });

    window.addEventListener('resize', function () {
        document.querySelectorAll('.fl-help-modal').forEach(function (modal) {
            if (modal._flHelpMoveIndicator) modal._flHelpMoveIndicator();
        });
    });

    if (typeof WSModal !== 'undefined' && !window._flHelpModalPatched) {
        window._flHelpModalPatched = true;
        var origOpen = WSModal.open.bind(WSModal);
        WSModal.open = function (id) {
            origOpen(id);
            var modal = document.getElementById(id);
            if (modal && modal.classList.contains('fl-help-modal') && modal._flHelpMoveIndicator) {
                requestAnimationFrame(function () {
                    modal._flHelpMoveIndicator();
                    var body = modal.querySelector('.fl-help-modal__body');
                    var progress = modal.querySelector('.fl-help-modal__scroll-progress');
                    if (body && progress) {
                        progress.style.transform = 'scaleX(0)';
                    }
                });
            }
        };
    }
})();
