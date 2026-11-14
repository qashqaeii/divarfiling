(function () {
    'use strict';

    function openModal(modal) {
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value || '—';
    }

    function setLink(id, href) {
        var el = document.getElementById(id);
        if (!el) return;
        if (href) {
            el.href = href;
            el.hidden = false;
        } else {
            el.hidden = true;
        }
    }

    document.addEventListener('click', function (event) {
        if (event.target.closest('[data-close-modal]')) {
            var modal = document.getElementById('sales-failed-detail-modal');
            closeModal(modal);
            return;
        }

        var btn = event.target.closest('.js-sales-failed-detail');
        if (!btn) return;

        var modal = document.getElementById('sales-failed-detail-modal');
        if (!modal) return;

        setText('sales-failed-modal-reason', btn.getAttribute('data-reason'));
        setText('sales-failed-modal-order', btn.getAttribute('data-order-label'));
        setText('sales-failed-modal-user', btn.getAttribute('data-user-label'));
        setText('sales-failed-modal-product', btn.getAttribute('data-product'));
        setText('sales-failed-modal-amount', btn.getAttribute('data-amount'));
        setText('sales-failed-modal-method', btn.getAttribute('data-method'));
        setText('sales-failed-modal-when', btn.getAttribute('data-when'));
        setText('sales-failed-modal-tx', btn.getAttribute('data-tx-status'));
        setText('sales-failed-modal-track', btn.getAttribute('data-track'));
        setText('sales-failed-modal-source', btn.getAttribute('data-source'));

        var categoryEl = document.getElementById('sales-failed-modal-category');
        if (categoryEl) {
            categoryEl.textContent = btn.getAttribute('data-category') || '—';
            var catKey = btn.getAttribute('data-category-key') || 'unknown';
            categoryEl.setAttribute('data-category', catKey);
        }

        var code = btn.getAttribute('data-gateway-code');
        var codeRow = document.getElementById('sales-failed-modal-code-row');
        if (codeRow) {
            if (code) {
                codeRow.hidden = false;
                setText('sales-failed-modal-code', code);
            } else {
                codeRow.hidden = true;
            }
        }

        setLink('sales-failed-modal-u360', btn.getAttribute('data-u360'));
        setLink('sales-failed-modal-admin', btn.getAttribute('data-admin-order'));

        openModal(modal);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeModal(document.getElementById('sales-failed-detail-modal'));
        }
    });
})();