(function () {
    'use strict';

    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '،');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-checkout]');
        if (!root) return;

        var form = document.getElementById('buy-form');
        var applyBtn = document.getElementById('apply-discount-btn');
        var discountInput = document.getElementById('id_discount_code');
        var discountMsg = document.getElementById('discount-message');
        var payBtns = document.querySelectorAll('[data-pay-btn]');
        var qtyInput = document.getElementById('id_quantity');
        var qtyFieldset = document.getElementById('bulk-quantity-fieldset');
        var qtyNote = document.getElementById('bulk-quantity-note');

        var applyDiscountUrl = root.dataset.applyDiscountUrl;
        var csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;

        var pricingState = {
            original: 0,
            final: 0,
            discountDetails: [],
            loading: false,
        };

        var pricingRequestId = 0;

        function getSelectedPlan() {
            return document.querySelector('input[name="plan"]:checked');
        }

        function getQuantity() {
            if (!qtyInput) return 1;
            var selected = getSelectedPlan();
            if (!selected || selected.dataset.allowBulk !== 'true') return 1;
            var min = parseInt(selected.dataset.minQuantity, 10) || 1;
            var max = parseInt(selected.dataset.maxQuantity, 10) || 20;
            var qty = parseInt(qtyInput.value, 10) || 1;
            return Math.max(min, Math.min(max, qty));
        }

        function syncQuantityField() {
            var selected = getSelectedPlan();
            if (!qtyInput || !qtyFieldset) return;

            var allowBulk = selected && selected.dataset.allowBulk === 'true';
            qtyFieldset.hidden = !allowBulk;
            if (!allowBulk) {
                qtyInput.value = '1';
                if (qtyNote) qtyNote.textContent = '';
                return;
            }

            var min = parseInt(selected.dataset.minQuantity, 10) || 1;
            var max = parseInt(selected.dataset.maxQuantity, 10) || 20;
            qtyInput.min = String(min);
            qtyInput.max = String(max);
            var qty = getQuantity();
            qtyInput.value = String(qty);
            if (qtyNote) {
                qtyNote.textContent = 'هر لایسنس شامل ۱ ویندوز + ۱ اندروید — جمعاً ' + qty + ' کلید جداگانه صادر می‌شود.';
            }
        }

        function fallbackPricingFromDataset(selected, qty) {
            var unitList = parseInt(selected.dataset.unitListPrice || selected.dataset.originalPrice, 10) || 0;
            var unitSale = parseInt(selected.dataset.unitSalePrice || selected.dataset.finalPrice, 10) || 0;
            pricingState.original = unitList * qty;
            pricingState.final = unitSale * qty;
            pricingState.discountDetails = [];
        }

        function renderSummary() {
            var selected = getSelectedPlan();
            if (!selected) return;

            syncQuantityField();
            var qty = getQuantity();
            var card = selected.closest('.ck-plan');
            var planName = card.querySelector('.ck-plan-name').textContent.trim();

            var summaryName = planName;
            if (qty > 1) {
                summaryName += ' × ' + qty;
            }
            document.getElementById('summary-plan-name').textContent = summaryName;
            document.getElementById('summary-original-price').textContent =
                formatNumber(pricingState.original) + ' تومان';

            var discountContainer = document.getElementById('summary-discount-rows');
            discountContainer.innerHTML = '';
            pricingState.discountDetails.forEach(function (d) {
                if (!d.amount || d.amount <= 0) return;
                var row = document.createElement('div');
                row.className = 'ck-order-line is-discount';
                row.innerHTML =
                    '<span>' + d.label + '</span>' +
                    '<span>-' + formatNumber(d.amount) + ' تومان</span>';
                discountContainer.appendChild(row);
            });

            var finalText = formatNumber(pricingState.final) + ' تومان';
            document.getElementById('summary-final-price').textContent = finalText;
            var mobileTotal = document.getElementById('mobile-final-price');
            if (mobileTotal) mobileTotal.textContent = finalText;

            payBtns.forEach(function (btn) {
                btn.disabled = pricingState.loading;
            });
        }

        function fetchPlanPricing(options) {
            options = options || {};
            var selected = getSelectedPlan();
            if (!selected || !applyDiscountUrl) return;

            var code = options.discountCode !== undefined
                ? options.discountCode
                : (discountInput ? discountInput.value.trim().toUpperCase() : '');
            var qty = getQuantity();
            var requestId = ++pricingRequestId;

            pricingState.loading = true;
            renderSummary();

            fetch(applyDiscountUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    discount_code: code,
                    plan_id: selected.value,
                    quantity: qty,
                }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (requestId !== pricingRequestId) return;

                    pricingState.loading = false;

                    if (data.success) {
                        pricingState.original = data.original_price;
                        pricingState.final = data.final_price;
                        pricingState.discountDetails = data.discount_details || [];

                        if (options.showDiscountSuccess && code) {
                            showDiscountMessage(
                                'کد اعمال شد — ' + formatNumber(data.total_discount) + ' تومان تخفیف',
                                'success'
                            );
                        }
                    } else {
                        fallbackPricingFromDataset(selected, qty);
                        if (options.showDiscountError) {
                            showDiscountMessage(data.message || 'خطا در محاسبه قیمت.', 'error');
                        }
                    }
                    renderSummary();
                })
                .catch(function () {
                    if (requestId !== pricingRequestId) return;
                    pricingState.loading = false;
                    fallbackPricingFromDataset(selected, qty);
                    if (options.showDiscountError) {
                        showDiscountMessage('خطا در ارتباط. دوباره تلاش کنید.', 'error');
                    }
                    renderSummary();
                });
        }

        function showDiscountMessage(message, type) {
            discountMsg.className = 'ck-promo-msg is-' + type;
            discountMsg.textContent = message;
        }

        function clearDiscountMessage() {
            discountMsg.className = 'ck-promo-msg';
            discountMsg.textContent = '';
        }

        function applyDiscount() {
            var selected = getSelectedPlan();
            if (!selected) {
                showDiscountMessage('ابتدا یک پلن انتخاب کنید.', 'error');
                return;
            }

            var code = discountInput.value.trim().toUpperCase();
            if (!code) {
                clearDiscountMessage();
                fetchPlanPricing({ discountCode: '' });
                return;
            }

            applyBtn.disabled = true;
            applyBtn.textContent = 'بررسی...';
            discountInput.value = code;

            var requestId = ++pricingRequestId;
            var qty = getQuantity();

            fetch(applyDiscountUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    discount_code: code,
                    plan_id: selected.value,
                    quantity: qty,
                }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (requestId !== pricingRequestId) return;
                    applyBtn.disabled = false;
                    applyBtn.textContent = 'اعمال';

                    if (data.success) {
                        pricingState.original = data.original_price;
                        pricingState.final = data.final_price;
                        pricingState.discountDetails = data.discount_details || [];
                        showDiscountMessage(
                            'کد اعمال شد — ' + formatNumber(data.total_discount) + ' تومان تخفیف',
                            'success'
                        );
                    } else {
                        fallbackPricingFromDataset(selected, qty);
                        showDiscountMessage(data.message || 'کد تخفیف معتبر نیست.', 'error');
                    }
                    renderSummary();
                })
                .catch(function () {
                    if (requestId !== pricingRequestId) return;
                    applyBtn.disabled = false;
                    applyBtn.textContent = 'اعمال';
                    fallbackPricingFromDataset(selected, qty);
                    showDiscountMessage('خطا در ارتباط. دوباره تلاش کنید.', 'error');
                    renderSummary();
                });
        }

        document.querySelectorAll('input[name="plan"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                document.querySelectorAll('.ck-plan').forEach(function (c) {
                    c.classList.remove('is-selected');
                });
                this.closest('.ck-plan').classList.add('is-selected');

                if (discountInput) discountInput.value = '';
                clearDiscountMessage();
                fetchPlanPricing({ discountCode: '' });
            });
        });

        document.querySelectorAll('.ck-plan').forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.tagName === 'INPUT') return;
                var radio = card.querySelector('input[type="radio"]');
                if (radio && !radio.checked) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        });

        if (qtyInput) {
            qtyInput.addEventListener('change', function () {
                if (discountInput) discountInput.value = '';
                clearDiscountMessage();
                fetchPlanPricing({ discountCode: '' });
            });
        }

        document.querySelectorAll('[data-qty-step]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!qtyInput) return;
                var step = parseInt(btn.dataset.qtyStep, 10) || 0;
                qtyInput.value = String(getQuantity() + step);
                qtyInput.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });

        if (applyBtn) applyBtn.addEventListener('click', applyDiscount);
        if (discountInput) {
            discountInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    applyDiscount();
                }
            });
        }

        function getSelectedPaymentMethod() {
            return document.querySelector('input[name="payment_method"]:checked');
        }

        function updatePaymentHints() {
            var method = getSelectedPaymentMethod();
            var hint = document.getElementById('pay-btn-hint');
            var foot = document.getElementById('pay-foot-note');
            if (!method) return;

            var isCard = method.value === 'card_transfer';
            if (hint) {
                hint.textContent = isCard
                    ? 'ثبت واریز و ارسال رسید'
                    : 'انتقال به درگاه زیبال';
            }
            if (foot) {
                foot.textContent = isCard
                    ? 'پرداخت کارت به کارت — تایید توسط پشتیبانی'
                    : 'پرداخت از درگاه امن زیبال';
            }
        }

        document.querySelectorAll('input[name="payment_method"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                document.querySelectorAll('.ck-pay-method').forEach(function (el) {
                    el.classList.remove('is-selected');
                });
                var card = this.closest('.ck-pay-method');
                if (card) card.classList.add('is-selected');
                updatePaymentHints();
            });
        });

        document.querySelectorAll('.ck-pay-method').forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.tagName === 'INPUT') return;
                var radio = card.querySelector('input[type="radio"]');
                if (radio && !radio.checked) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        });

        payBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!getSelectedPlan()) {
                    alert('لطفاً یک پلن انتخاب کنید.');
                    return;
                }
                if (qtyInput) {
                    qtyInput.value = String(getQuantity());
                }
                form.requestSubmit();
            });
        });

        updatePaymentHints();

        var initial = getSelectedPlan();
        if (initial) {
            initial.closest('.ck-plan').classList.add('is-selected');
            fetchPlanPricing({ discountCode: '' });
        }

        var loyaltyNotice = document.querySelector('[data-loyalty-notice]');
        var loyaltyKey = 'ck-loyalty-dismissed';
        if (loyaltyNotice) {
            try {
                if (localStorage.getItem(loyaltyKey) === '1') {
                    loyaltyNotice.classList.add('is-dismissed');
                }
            } catch (e) { /* ignore */ }

            document.querySelectorAll('[data-loyalty-dismiss]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    loyaltyNotice.classList.add('is-dismissed');
                    try {
                        localStorage.setItem(loyaltyKey, '1');
                    } catch (e) { /* ignore */ }
                });
            });
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        var successRoot = document.querySelector('[data-pay-success]');
        if (!successRoot) return;

        successRoot.querySelectorAll('[data-copy-target]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var targetId = btn.getAttribute('data-copy-target');
                var el = document.getElementById(targetId);
                if (!el) return;

                var text = el.textContent.trim();
                var label = btn.querySelector('span');
                var icon = btn.querySelector('i');
                var originalLabel = label ? label.textContent : '';
                var originalIconClass = icon ? icon.className : '';

                function onCopied() {
                    btn.classList.add('is-copied');
                    if (label) label.textContent = 'کپی شد';
                    if (icon) icon.className = 'fas fa-check';
                    setTimeout(function () {
                        btn.classList.remove('is-copied');
                        if (label) label.textContent = originalLabel;
                        if (icon) icon.className = originalIconClass;
                    }, 2000);
                }

                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(onCopied).catch(function () {
                        alert('خطا در کپی. لطفاً دستی کپی کنید.');
                    });
                } else {
                    var area = document.createElement('textarea');
                    area.value = text;
                    area.style.position = 'fixed';
                    area.style.opacity = '0';
                    document.body.appendChild(area);
                    area.select();
                    try {
                        document.execCommand('copy');
                        onCopied();
                    } catch (err) {
                        alert('خطا در کپی. لطفاً دستی کپی کنید.');
                    }
                    document.body.removeChild(area);
                }
            });
        });
    });
})();
