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
        return (
            '<section class="mk-order-modal__block mk-order-modal__block--flow" aria-labelledby="mkOrderModalTimelineTitle">' +
                '<h3 id="mkOrderModalTimelineTitle" class="mk-order-modal__block-title">روند</h3>' +
                '<ol class="mk-order-modal__timeline mk-order-modal__timeline--rail">' +
                items.map(function (item) {
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
                }).join('') +
                '</ol>' +
            '</section>'
        );
    }

    function renderLicenses(licenses) {
        if (!licenses || !licenses.length) return '';
        return (
            '<section class="mk-order-modal__block mk-order-modal__block--license" aria-label="کلیدهای لایسنس">' +
            '<p class="mk-order-modal__licenses-note">کلید نمایش داده نمی‌شود — فقط کپی.</p>' +
            licenses.map(function (lic) {
                var planLabel = lic.plan ? escapeHtml(lic.plan) : 'کلید لایسنس';
                return (
                    '<div class="mk-order-modal__license">' +
                        '<span class="mk-order-modal__license-label">' + planLabel + '</span>' +
                        '<button type="button" class="mk-ord-modal-act mk-ord-modal-act--inline" data-copy-license-value="' + escapeHtml(lic.key) + '">' +
                            '<i class="fas fa-copy" aria-hidden="true"></i> کپی' +
                        '</button>' +
                    '</div>'
                );
            }).join('') +
            '</section>'
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
            '<section class="mk-order-modal__block mk-order-modal__block--meta" aria-labelledby="mkOrderModalMetaTitle">' +
                '<h3 id="mkOrderModalMetaTitle" class="mk-order-modal__block-title">جزئیات</h3>' +
                '<dl class="mk-order-modal__meta mk-order-modal__meta--dense">' +
                fields.map(function (field) {
                    return (
                        '<div class="mk-order-modal__meta-row">' +
                            '<dt>' + escapeHtml(field.label) + '</dt>' +
                            '<dd>' + escapeHtml(field.value) + '</dd>' +
                        '</div>'
                    );
                }).join('') +
                '</dl>' +
            '</section>'
        );
    }

    function actionButtonClass(kind) {
        if (kind === 'primary' || kind === 'accent') return 'mk-ord-modal-act mk-ord-modal-act--primary';
        return 'mk-ord-modal-act mk-ord-modal-act--soft';
    }

    function renderActions(actions) {
        if (!actions || !actions.length) {
            footEl.innerHTML = '';
            return;
        }
        footEl.innerHTML = actions.map(function (action) {
            if (action.action === 'copy_order_id') {
                return (
                    '<button type="button" class="' + actionButtonClass(action.kind) + '" data-copy-order-id>' +
                        '<i class="fas fa-' + escapeHtml(action.icon) + '" aria-hidden="true"></i> ' +
                        escapeHtml(action.label) +
                    '</button>'
                );
            }
            var iconClass = action.icon_style === 'fab' ? 'fab' : 'fas';
            return (
                '<a href="' + escapeHtml(action.url) + '" class="' + actionButtonClass(action.kind) + '">' +
                    '<i class="' + iconClass + ' fa-' + escapeHtml(action.icon) + '" aria-hidden="true"></i> ' +
                    escapeHtml(action.label) +
                '</a>'
            );
        }).join('');
    }

    function renderSummary(order) {
        var compare = order.original_price
            ? '<p class="mk-order-modal__compare">قیمت اصلی: ' + escapeHtml(order.original_price) + ' تومان</p>'
            : '';
        return (
            '<div class="mk-order-modal__summary">' +
                '<p class="mk-order-modal__summary-label">مبلغ پرداختی</p>' +
                '<div class="mk-order-modal__amount-row">' +
                    '<div class="mk-order-modal__amount">' +
                        escapeHtml(order.amount_display) +
                        '<span class="mk-order-modal__amount-unit">تومان</span>' +
                    '</div>' +
                    '<span class="mk-orders-status ' + toneClass(order.status_tone) + '">' + escapeHtml(order.status_label) + '</span>' +
                '</div>' +
                compare +
            '</div>'
        );
    }

    function renderOrder(order) {
        titleEl.textContent = 'جزئیات سفارش';
        subEl.textContent = '#' + order.id_short + ' · ' + order.product_title;
        var timelineHtml = renderTimeline(order.timeline);
        var fieldsHtml = renderFields(order);
        var licensesHtml = renderLicenses(order.licenses);
        var layoutHtml = '';
        if (timelineHtml || fieldsHtml) {
            layoutHtml =
                '<div class="mk-order-modal__layout">' +
                    (timelineHtml ? '<div class="mk-order-modal__layout-flow">' + timelineHtml + '</div>' : '') +
                    (fieldsHtml ? '<div class="mk-order-modal__layout-meta">' + fieldsHtml + '</div>' : '') +
                '</div>';
        }
        bodyEl.innerHTML =
            renderSummary(order) +
            layoutHtml +
            licensesHtml;

        renderActions(order.actions);
        bodyEl.dataset.orderId = order.id;

        bodyEl.querySelectorAll('[data-copy-license-value]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var key = btn.getAttribute('data-copy-license-value');
                if (!key) return;
                navigator.clipboard.writeText(key).then(function () {
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
        footEl.innerHTML = '<button type="button" class="mk-ord-modal-act mk-ord-modal-act--soft" data-order-modal-close>بستن</button>';
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
