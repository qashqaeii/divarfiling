(function () {
    'use strict';

    function formatMoney(value) {
        var num = parseInt(value, 10);
        if (isNaN(num)) return '—';
        try {
            return num.toLocaleString('fa-IR') + ' تومان';
        } catch (e) {
            return num + ' تومان';
        }
    }

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

    function closeAllModals() {
        document.querySelectorAll('.ecc-ct-modal').forEach(closeModal);
    }

    document.addEventListener('click', function (event) {
        if (event.target.closest('[data-close-modal]')) {
            closeAllModals();
            return;
        }

        var approveBtn = event.target.closest('.js-card-approve');
        if (approveBtn) {
            var approveModal = document.getElementById('card-transfer-approve-modal');
            var approveForm = document.getElementById('card-approve-form');
            if (!approveModal || !approveForm) return;
            approveForm.action = approveBtn.getAttribute('data-action-url') || '';
            document.getElementById('card-approve-user').textContent = approveBtn.getAttribute('data-user') || '—';
            document.getElementById('card-approve-plan').textContent = approveBtn.getAttribute('data-plan') || '—';
            document.getElementById('card-approve-amount').textContent = formatMoney(approveBtn.getAttribute('data-amount'));
            document.getElementById('card-approve-quantity').textContent = approveBtn.getAttribute('data-quantity') || '1';
            openModal(approveModal);
            return;
        }

        var rejectBtn = event.target.closest('.js-card-reject');
        if (rejectBtn) {
            var rejectModal = document.getElementById('card-transfer-reject-modal');
            var rejectForm = document.getElementById('card-reject-form');
            if (!rejectModal || !rejectForm) return;
            rejectForm.action = rejectBtn.getAttribute('data-action-url') || '';
            var user = rejectBtn.getAttribute('data-user') || 'کاربر';
            var rejectText = document.getElementById('card-reject-text');
            if (rejectText) {
                rejectText.textContent = 'آیا از رد پرداخت «' + user + '» مطمئن هستید؟';
            }
            openModal(rejectModal);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeAllModals();
        }
    });
})();
