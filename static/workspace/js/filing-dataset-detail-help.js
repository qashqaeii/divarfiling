(function () {
    var modal = document.getElementById('modal-dataset-detail-help');
    if (!modal) return;

    var tabs = modal.querySelectorAll('[data-fl-help-tab]');
    var panes = modal.querySelectorAll('[data-fl-help-pane]');
    var body = document.getElementById('flDdHelpScrollBody');
    var progress = document.getElementById('flDdHelpScrollProgress');
    var nav = modal.querySelector('.fl-help-modal__nav');
    var indicator = modal.querySelector('.fl-help-modal__nav-indicator');

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

    function activateTab(id) {
        var activeBtn = null;
        tabs.forEach(function (btn) {
            var on = btn.getAttribute('data-fl-help-tab') === id;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
            if (on) activeBtn = btn;
        });
        panes.forEach(function (pane) {
            var on = pane.getAttribute('data-fl-help-pane') === id;
            pane.classList.toggle('is-active', on);
            if (on) pane.removeAttribute('hidden');
            else pane.setAttribute('hidden', '');
        });
        if (body) body.scrollTop = 0;
        updateScrollProgress();
        requestAnimationFrame(function () { moveIndicator(activeBtn); });
    }

    tabs.forEach(function (btn) {
        btn.addEventListener('click', function () {
            activateTab(btn.getAttribute('data-fl-help-tab'));
        });
    });

    modal.querySelectorAll('[data-modal-open="modal-dataset-detail-help"]').forEach(function (trigger) {
        trigger.addEventListener('click', function () {
            activateTab('browse');
        });
    });

    if (body) body.addEventListener('scroll', updateScrollProgress, { passive: true });
    window.addEventListener('resize', function () {
        moveIndicator(modal.querySelector('.fl-help-modal__nav-btn.is-active'));
    });
    modal.addEventListener('click', function (e) {
        if (e.target.closest('[data-modal-close]')) {
            setTimeout(function () { activateTab('browse'); }, 280);
        }
    });

    if (typeof WSModal !== 'undefined') {
        var origOpen = WSModal.open.bind(WSModal);
        WSModal.open = function (id) {
            origOpen(id);
            if (id === 'modal-dataset-detail-help') {
                requestAnimationFrame(function () {
                    moveIndicator(modal.querySelector('.fl-help-modal__nav-btn.is-active'));
                    updateScrollProgress();
                });
            }
        };
    }

    requestAnimationFrame(function () {
        moveIndicator(modal.querySelector('.fl-help-modal__nav-btn.is-active'));
        updateScrollProgress();
    });
})();
