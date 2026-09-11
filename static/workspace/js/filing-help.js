(function () {
    var modal = document.getElementById('modal-filing-help');
    if (!modal) return;

    var tabs = modal.querySelectorAll('[data-fl-help-tab]');
    var panes = modal.querySelectorAll('[data-fl-help-pane]');

    function activateTab(id) {
        tabs.forEach(function (btn) {
            var on = btn.getAttribute('data-fl-help-tab') === id;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        panes.forEach(function (pane) {
            var on = pane.getAttribute('data-fl-help-pane') === id;
            pane.classList.toggle('is-active', on);
            if (on) {
                pane.removeAttribute('hidden');
            } else {
                pane.setAttribute('hidden', '');
            }
        });
        var body = modal.querySelector('.fl-help-modal__body');
        if (body) body.scrollTop = 0;
    }

    tabs.forEach(function (btn) {
        btn.setAttribute('role', 'tab');
        btn.setAttribute('type', 'button');
        btn.addEventListener('click', function () {
            activateTab(btn.getAttribute('data-fl-help-tab'));
        });
    });

    modal.querySelectorAll('[data-modal-open="modal-filing-help"]').forEach(function (trigger) {
        trigger.addEventListener('click', function () {
            activateTab('start');
        });
    });

    modal.addEventListener('click', function (e) {
        if (e.target.closest('[data-modal-close]') && typeof WSModal !== 'undefined') {
            setTimeout(function () { activateTab('start'); }, 280);
        }
    });
})();
