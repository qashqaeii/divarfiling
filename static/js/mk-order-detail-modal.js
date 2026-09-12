(function () {
    'use strict';

    var modal;
    var bodyEl;
    var footEl;
    var titleEl;
    var subEl;
    var detailUrlTemplate;

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function toneClass(tone) {
        return 'mk-orders-status--' + (tone === 'success' ? 'paid' : tone === 'warning' ? 'pending' : tone === 'info' ? 'pending_verification' : tone === 'danger' ? 'failed' : 'cancelled');
    }

    function renderTimeline(items) {
        if (!items || !items.length) return '';
        return '<ol class="mk-order-modal__timeline">' + items.map(function (item) {
            var classes = ['mk-order-modal__timeline-item'];
            if (item.done) classes.push('is-done');
            if (item.active) classes.push('is-active');
            return (
                '<li class="' + classes.join(' ') + '">' +
                    '<span class="mk-order-modal__timeline-dot" aria-hidden="true"></span>' +
                    '<div>' +
                        '<span class="mk-order-modal__timeline-label">' + escapeHtml(item.label) + '</span>' +
                        (item.at ? '<span class="mk-order-modal__timeline-at">' + escapeHtml(item.at) + '</span>' : '') +
                    '</div>' +
                '</li>'
            );
        }).join('') + '</ol>';
    }

    function renderLicenses(licenses) {
        if (!licenses || !licenses.length) return '';
        return (
            '<div class="mk-order-modal__licenses">' +
            licenses.map(function (lic, idx) {
                return (
                    '<div class="mk-order-modal__license">' +
                        '<code id="mk-order-lic-' + idx + '">' + escapeHtml(lic.key) + '</code>' +
                        '<button type="button" class="mk-acc-icon-btn" data-copy-license="mk-order-lic-' + idx + '" title="کپی کلید">' +
                            '<i class="fas fa-copy" aria-hidden="true"></i>' +
                        '</button>' +
                    '</div>'
                );
            }).join('') +
            '</div>'
        );
    }

    function renderFields(order) {
        var fields = [
            { label: 'محصول', value: order.product_title },
            { label: 'پلن', value: order.plan_name },
            { label: 'روش پرداخت', value: order.payment_method_label },
            { label: 'تاریخ ثبت', value: order.created_at },
        ];
        if (order.paid_at) fields.push({ label: 'تاریخ پرداخت', value: order.paid_at });
        if (order.zibal_track_id) fields.push({ label: 'کد پیگیری', value: order.zibal_track_id });
        if (order.discount_code) fields.push({ label: 'کد تخفیف', value: order.discount_code });
        if (order.discount_amount && order.discount_amount !== '0') {
            fields.push({ label: 'تخفیف', value: order.discount_amount + ' تومان' });
        }
        if (order.transaction && order.transaction.ref_number) {
            fields.push({ label: 'شماره مرجع', value: order.transaction.ref_number });
        }
        if (order.card_transfer) {
            fields.push({ label: 'وضعیت رسید', value: order.card_transfer.status_label });
            if (order.card_transfer.reference_number) {
                fields.push({ label: 'شماره رسید', value: order.card_transfer.reference_number });
            }
        }
        return (
            '<div class="mk-order-modal__grid">' +
            fields.map(function (field) {
                return (
                    '<div class="mk-order-modal__field">' +
                        '<span class="mk-order-modal__field-label">' + escapeHtml(field.label) + '</span>' +
                        '<span class="mk-order-modal__field-value">' + escapeHtml(field.value) + '</span>' +
                    '</div>'
                );
            }).join('') +
            '</div>'
        );
    }

    function renderActions(actions) {
        if (!actions || !actions.length) {
            footEl.innerHTML = '';
            return;
        }
        footEl.innerHTML = actions.map(function (action) {
            if (action.action === 'copy_order_id') {
                return (
                    '<button type="button" class="mk-acc-btn mk-acc-btn--ghost" data-copy-order-id>' +
                        '<i class="fas fa-' + escapeHtml(action.icon) + '" aria-hidden="true"></i> ' +
                        escapeHtml(action.label) +
                    '</button>'
                );
            }
            var iconClass = action.icon_style === 'fab' ? 'fab' : 'fas';
            var btnClass = 'mk-acc-btn';
            if (action.kind === 'primary') btnClass += ' mk-acc-btn--primary';
            else if (action.kind === 'accent') btnClass += ' mk-acc-btn--primary';
            else if (action.kind === 'warning') btnClass += ' mk-acc-btn--ghost';
            else btnClass += ' mk-acc-btn--ghost';
            return (
                '<a href="' + escapeHtml(action.url) + '" class="' + btnClass + '">' +
                    '<i class="' + iconClass + ' fa-' + escapeHtml(action.icon) + '" aria-hidden="true"></i> ' +
                    escapeHtml(action.label) +
                '</a>'
            );
        }).join('');
    }

    function renderOrder(order) {
        titleEl.textContent = 'جزئیات سفارش';
        subEl.textContent = '#' + order.id_short + ' · ' + order.product_title;
        bodyEl.innerHTML =
            '<div class="mk-order-modal__hero">' +
                '<div>' +
                    '<div class="mk-order-modal__amount">' + escapeHtml(order.amount_display) + ' <small>تومان</small></div>' +
                    (order.original_price ? '<div style="font-size:0.64rem;color:var(--acc-text-muted);margin-top:0.15rem;">قیمت اصلی: ' + escapeHtml(order.original_price) + ' تومان</div>' : '') +
                '</div>' +
                '<span class="mk-orders-status ' + toneClass(order.status_tone) + '">' + escapeHtml(order.status_label) + '</span>' +
            '</div>' +
            renderTimeline(order.timeline) +
            renderFields(order) +
            renderLicenses(order.licenses);

        renderActions(order.actions);
        bodyEl.dataset.orderId = order.id;

        bodyEl.querySelectorAll('[data-copy-license]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var target = document.getElementById(btn.getAttribute('data-copy-license'));
                if (!target) return;
                navigator.clipboard.writeText(target.textContent.trim()).then(function () {
                    if (typeof showToast === 'function') showToast('کلید لایسنس کپی شد', 'success');
                });
            });
        });

        var copyOrderBtn = footEl.querySelector('[data-copy-order-id]');
        if (copyOrderBtn) {
            copyOrderBtn.addEventListener('click', function () {
                navigator.clipboard.writeText(order.id).then(function () {
                    if (typeof showToast === 'function') showToast('شماره سفارش کپی شد', 'success');
                });
            });
        }
    }

    function showLoading() {
        titleEl.textContent = 'جزئیات سفارش';
        subEl.textContent = 'در حال بارگذاری اطلاعات پرداخت…';
        bodyEl.innerHTML = '<div class="mk-order-modal__loading"><i class="fas fa-circle-notch" aria-hidden="true"></i>در حال بارگذاری…</div>';
        footEl.innerHTML = '';
    }

    function showError(message) {
        bodyEl.innerHTML = '<div class="mk-order-modal__error"><i class="fas fa-circle-exclamation" aria-hidden="true"></i><p>' + escapeHtml(message) + '</p></div>';
        footEl.innerHTML = '<button type="button" class="mk-acc-btn mk-acc-btn--ghost" data-order-modal-close>بستن</button>';
    }

    function openModal() {
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('mk-order-modal-open');
    }

    function closeModal() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('mk-order-modal-open');
    }

    function fetchAndShow(orderId) {
        if (!detailUrlTemplate) return;
        showLoading();
        openModal();
        var url = detailUrlTemplate.replace('00000000-0000-0000-0000-000000000000', encodeURIComponent(orderId));
        fetch(url, {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) throw new Error(data.error || 'خطا در بارگذاری جزئیات');
                    return data;
                });
            })
            .then(function (data) {
                if (!data.ok || !data.order) throw new Error('پاسخ نامعتبر از سرور');
                renderOrder(data.order);
            })
            .catch(function (err) {
                showError(err.message || 'خطا در بارگذاری جزئیات سفارش');
            });
    }

    function init() {
        modal = qs('#mkOrderDetailModal');
        if (!modal) return;

        bodyEl = qs('#mkOrderDetailBody', modal);
        footEl = qs('#mkOrderDetailFoot', modal);
        titleEl = qs('#mkOrderDetailTitle', modal);
        subEl = qs('#mkOrderDetailSub', modal);
        detailUrlTemplate = modal.getAttribute('data-detail-url');
        if (!detailUrlTemplate) return;

        document.addEventListener('click', function (event) {
            var trigger = event.target.closest('[data-order-detail]');
            if (trigger) {
                event.preventDefault();
                fetchAndShow(trigger.getAttribute('data-order-detail'));
                return;
            }
            if (event.target.closest('[data-order-modal-close]') || event.target.classList.contains('mk-order-modal__overlay')) {
                closeModal();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && modal.classList.contains('is-open')) {
                closeModal();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
