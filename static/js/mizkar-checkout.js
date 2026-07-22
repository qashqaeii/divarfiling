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

        var repeatPurchaseDiscount = null;
        var currentPrices = { original: 0, final: 0, discounts: [] };

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

        function unitPricesFromSelected(selected) {
            var unitOriginal = parseInt(selected.dataset.originalPrice, 10);
            var unitFinal = parseInt(selected.dataset.finalPrice, 10);
            if (currentPrices.discounts.length > 0) {
                var qty = getQuantity();
                unitFinal = Math.round(currentPrices.final / qty);
            }
            return { unitOriginal: unitOriginal, unitFinal: unitFinal };
        }

        function updateSummary() {
            var selected = getSelectedPlan();
            if (!selected) return;

            syncQuantityField();
            var qty = getQuantity();
            var card = selected.closest('.ck-plan');
            var planName = card.querySelector('.ck-plan-name').textContent.trim();
            var prices = unitPricesFromSelected(selected);
            var originalPrice = prices.unitOriginal * qty;
            var finalPrice = prices.unitFinal * qty;

            if (selected.dataset.hasRepeatDiscount === 'true' && !repeatPurchaseDiscount) {
                var pct = parseInt(selected.dataset.repeatDiscountPercentage, 10);
                var amount = Math.floor(originalPrice * pct / 100);
                repeatPurchaseDiscount = {
                    label: pct + '% تخفیف خرید مجدد',
                    amount: amount,
                    type: 'repeat_purchase'
                };
            } else if (selected.dataset.hasRepeatDiscount !== 'true') {
                repeatPurchaseDiscount = null;
            }

            if (currentPrices.discounts.length > 0) {
                finalPrice = currentPrices.final;
            }

            var allDiscounts = [];
            if (repeatPurchaseDiscount) allDiscounts.push(repeatPurchaseDiscount);
            if (currentPrices.discounts.length > 0) {
                allDiscounts = allDiscounts.concat(currentPrices.discounts);
            }

            var summaryName = planName;
            if (qty > 1) {
                summaryName += ' × ' + qty;
            }
            document.getElementById('summary-plan-name').textContent = summaryName;
            document.getElementById('summary-original-price').textContent =
                formatNumber(originalPrice) + ' تومان';

            var discountContainer = document.getElementById('summary-discount-rows');
            discountContainer.innerHTML = '';
            allDiscounts.forEach(function (d) {
                var row = document.createElement('div');
                row.className = 'ck-order-line is-discount';
                row.innerHTML =
                    '<span>' + d.label + '</span>' +
                    '<span>-' + formatNumber(d.amount) + ' تومان</span>';
                discountContainer.appendChild(row);
            });

            var finalText = formatNumber(finalPrice) + ' تومان';
            document.getElementById('summary-final-price').textContent = finalText;
            var mobileTotal = document.getElementById('mobile-final-price');
            if (mobileTotal) mobileTotal.textContent = finalText;

            currentPrices.original = originalPrice;
            currentPrices.final = finalPrice;

            payBtns.forEach(function (btn) { btn.disabled = false; });
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
            var qty = getQuantity();
            var baseFinal = parseInt(selected.dataset.finalPrice, 10) * qty;

            if (!code) {
                currentPrices.discounts = [];
                currentPrices.final = baseFinal;
                clearDiscountMessage();
                updateSummary();
                return;
            }

            applyBtn.disabled = true;
            applyBtn.textContent = 'بررسی...';

            fetch(applyDiscountUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    discount_code: code,
                    plan_id: selected.value,
                    quantity: qty
                })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                applyBtn.disabled = false;
                applyBtn.textContent = 'اعمال';
                discountInput.value = code;

                if (data.success) {
                    currentPrices.discounts = (data.discount_details || []).filter(function (d) {
                        return d.type === 'discount_code';
                    });
                    currentPrices.final = data.final_price;
                    showDiscountMessage(
                        'کد اعمال شد — ' + formatNumber(data.total_discount) + ' تومان تخفیف',
                        'success'
                    );
                } else {
                    currentPrices.discounts = [];
                    currentPrices.final = baseFinal;
                    showDiscountMessage(data.message || 'کد تخفیف معتبر نیست.', 'error');
                }
                updateSummary();
            })
            .catch(function () {
                applyBtn.disabled = false;
                applyBtn.textContent = 'اعمال';
                showDiscountMessage('خطا در ارتباط. دوباره تلاش کنید.', 'error');
            });
        }

        document.querySelectorAll('input[name="plan"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                document.querySelectorAll('.ck-plan').forEach(function (c) {
                    c.classList.remove('is-selected');
                });
                this.closest('.ck-plan').classList.add('is-selected');

                discountInput.value = '';
                currentPrices.discounts = [];
                repeatPurchaseDiscount = null;
                clearDiscountMessage();
                updateSummary();
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
                discountInput.value = '';
                currentPrices.discounts = [];
                clearDiscountMessage();
                updateSummary();
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
            updateSummary();
        }
    });
})();
