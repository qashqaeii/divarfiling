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
        var hiddenSubmit = document.getElementById('buy-form-hidden-submit');
        var qtyInput = document.getElementById('id_quantity');
        var qtyFieldset = document.getElementById('bulk-quantity-fieldset');
        var qtyNote = document.getElementById('bulk-quantity-note');

        if (!form) return;

        var applyDiscountUrl = root.dataset.applyDiscountUrl;
        var csrfInput = form.querySelector('[name=csrfmiddlewaretoken]');
        var csrfToken = csrfInput ? csrfInput.value : '';

        var pricingState = {
            original: 0,
            final: 0,
            discountDetails: [],
            loading: false,
        };

        var pricingRequestId = 0;
        var qtyDebounceTimer = null;

        function scheduleQuantityUpdate() {
            if (!qtyInput) return;
            clearTimeout(qtyDebounceTimer);
            qtyDebounceTimer = setTimeout(function () {
                applyQuantityChange(parseInt(qtyInput.value, 10) || 1);
            }, 200);
        }

        function getActivePlanMode() {
            var activeTab = document.querySelector('[data-plan-mode].is-active');
            return activeTab && activeTab.dataset.planMode === 'agency' ? 'agency' : 'personal';
        }

        function getSelectedPlan() {
            var mode = getActivePlanMode();
            var panel = document.querySelector('[data-plan-panel="' + mode + '"]');
            if (panel) {
                var inPanel = panel.querySelector('input[name="plan"]:checked:not(:disabled)');
                if (inPanel) return inPanel;
            }
            return document.querySelector('input[name="plan"]:checked:not(:disabled)');
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
            if (!qtyInput || !qtyFieldset) return 1;

            var allowBulk = selected && selected.dataset.allowBulk === 'true';
            qtyFieldset.hidden = !allowBulk;
            if (!allowBulk) {
                qtyInput.value = '1';
                qtyInput.min = '1';
                qtyInput.max = '1';
                qtyInput.disabled = true;
                if (qtyNote) qtyNote.textContent = '';
                return 1;
            }

            qtyInput.disabled = false;
            var min = parseInt(selected.dataset.minQuantity, 10) || 1;
            var max = parseInt(selected.dataset.maxQuantity, 10) || 20;
            qtyInput.min = String(min);
            qtyInput.max = String(max);
            var qty = parseInt(qtyInput.value, 10) || min;
            qty = Math.max(min, Math.min(max, qty));
            qtyInput.value = String(qty);
            if (qtyNote) {
                qtyNote.textContent = 'برای هر مشاور یک کلید مستقل شامل ویندوز و اندروید صادر می‌شود.';
            }
            return qty;
        }

        function fallbackPricingFromDataset(selected, qty) {
            var unitList = parseInt(selected.dataset.unitListPrice || selected.dataset.originalPrice, 10) || 0;
            var unitSale = parseInt(selected.dataset.unitSalePrice, 10) || 0;
            var unitFinal = parseInt(selected.dataset.finalPrice, 10) || unitSale;
            var hasRepeat = selected.dataset.hasRepeatDiscount === 'true';
            var repeatPct = parseInt(selected.dataset.repeatDiscountPercentage, 10) || 0;

            pricingState.original = unitList * qty;
            if (hasRepeat && repeatPct > 0) {
                var subtotal = unitSale * qty;
                var repeatAmount = Math.floor(subtotal * repeatPct / 100);
                pricingState.final = Math.max(0, subtotal - repeatAmount);
                if (repeatAmount > 0) {
                    pricingState.discountDetails = [{
                        type: 'repeat_purchase',
                        label: repeatPct + '% تخفیف خرید مجدد',
                        amount: repeatAmount,
                    }];
                }
            } else {
                pricingState.final = unitFinal * qty;
                pricingState.discountDetails = [];
            }
        }

        function applyQuantityChange(explicitQty) {
            var selected = getSelectedPlan();
            if (!selected || !qtyInput) return;

            var qty = explicitQty !== undefined ? explicitQty : syncQuantityField();
            if (selected.dataset.allowBulk !== 'true') {
                qty = 1;
            } else {
                var min = parseInt(selected.dataset.minQuantity, 10) || 1;
                var max = parseInt(selected.dataset.maxQuantity, 10) || 20;
                qty = Math.max(min, Math.min(max, qty));
                qtyInput.value = String(qty);
                if (qtyNote) {
                    qtyNote.textContent = 'برای هر مشاور یک کلید مستقل شامل ویندوز و اندروید صادر می‌شود.';
                }
            }

            if (discountInput) discountInput.value = '';
            clearDiscountMessage();
            fallbackPricingFromDataset(selected, qty);
            renderSummary();
            fetchPlanPricing({ discountCode: '', quantity: qty });
        }

        function renderAgencySummary(data) {
            var box = document.getElementById('agency-pricing-summary');
            var liveTotal = document.getElementById('agency-live-total');
            var liveTotalValue = document.getElementById('agency-live-total-value');
            var selected = getSelectedPlan();
            if (!selected || selected.dataset.allowBulk !== 'true') {
                if (box) { box.hidden = true; box.innerHTML = ''; }
                if (liveTotal) liveTotal.hidden = true;
                return;
            }
            var qty = data.quantity || syncQuantityField();
            var slots = data.total_activation_slots || (qty * 2);
            var baseUnit = data.base_unit_price || parseInt(selected.dataset.unitSalePrice, 10) || 0;
            var effUnit = data.effective_unit_price || baseUnit;
            var appliedReason = data.applied_discount_reason || '';
            var finalTotal = data.final_price || pricingState.final || 0;

            if (liveTotal && liveTotalValue) {
                liveTotalValue.textContent = formatNumber(finalTotal) + ' تومان';
                liveTotal.hidden = false;
            }

            if (!box) return;

            var html = '<div class="ck-agency-summary-grid">' +
                item('تعداد مشاور', qty) +
                item('کلید مستقل', qty) +
                item('ظرفیت دستگاه', slots) +
                item('قیمت پایه هر نفر', formatNumber(baseUnit), false) +
                item('قیمت هر نفر', formatNumber(effUnit) + ' تومان', true);
            if (appliedReason) {
                html += '<div class="ck-agency-summary-discount"><span>' + appliedReason + '</span><strong>' +
                    (data.applied_discount_percent || 0) + '٪</strong></div>';
            }
            html += '</div>';
            box.innerHTML = html;
            box.hidden = false;

            function item(label, value, highlight) {
                return '<div class="ck-agency-summary-item' + (highlight ? ' is-highlight' : '') + '">' +
                    '<span>' + label + '</span><strong>' + value + '</strong></div>';
            }
        }

        function setPlanMode(mode) {
            var personalPanel = document.querySelector('[data-plan-panel="personal"]');
            var agencyPanel = document.querySelector('[data-plan-panel="agency"]');
            var liveTotal = document.getElementById('agency-live-total');
            document.querySelectorAll('[data-plan-mode]').forEach(function (btn) {
                var active = btn.dataset.planMode === mode;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            if (personalPanel) personalPanel.hidden = mode !== 'personal';
            if (agencyPanel) agencyPanel.hidden = mode !== 'agency';

            if (mode === 'agency') {
                var firstAgency = agencyPanel && agencyPanel.querySelector('input[name="plan"]:not(:disabled)');
                var checkedAgency = agencyPanel && agencyPanel.querySelector('input[name="plan"]:checked');
                if (firstAgency && !checkedAgency) {
                    firstAgency.checked = true;
                    firstAgency.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (checkedAgency) {
                    syncQuantityField();
                    fetchPlanPricing({ discountCode: '', quantity: syncQuantityField() });
                }
            } else {
                if (liveTotal) liveTotal.hidden = true;
                var agencySummary = document.getElementById('agency-pricing-summary');
                if (agencySummary) {
                    agencySummary.hidden = true;
                    agencySummary.innerHTML = '';
                }
                var checkedPersonal = personalPanel && personalPanel.querySelector('input[name="plan"]:checked');
                var firstPersonal = personalPanel && personalPanel.querySelector('input[name="plan"]:not(:disabled)');
                if (!checkedPersonal && firstPersonal) {
                    firstPersonal.checked = true;
                    firstPersonal.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (checkedPersonal) {
                    syncQuantityField();
                    fetchPlanPricing({ discountCode: '', quantity: 1 });
                }
            }
        }

        document.querySelectorAll('[data-plan-mode]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setPlanMode(btn.dataset.planMode);
            });
        });

        function getPlanDisplayName(selected) {
            if (!selected) return '—';
            var card = selected.closest('.ck-plan, .ck-agency-duration-btn');
            if (!card) return '—';
            var nameEl = card.querySelector('.ck-plan-name');
            if (nameEl) return nameEl.textContent.trim();
            var durationLabel = card.querySelector('.ck-agency-duration-label');
            var agencyTitle = document.querySelector('.ck-agency-title');
            if (durationLabel && agencyTitle) {
                return agencyTitle.textContent.trim() + ' — ' + durationLabel.textContent.trim();
            }
            return agencyTitle ? agencyTitle.textContent.trim() : '—';
        }

        function renderSummary() {
            var selected = getSelectedPlan();
            if (!selected) return;

            var qty = syncQuantityField();
            var planName = getPlanDisplayName(selected);

            var summaryName = planName;
            if (qty > 1) {
                summaryName += ' — ' + qty + ' مشاور';
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

            var liveTotal = document.getElementById('agency-live-total');
            var liveTotalValue = document.getElementById('agency-live-total-value');
            if (liveTotal && liveTotalValue && selected.dataset.allowBulk === 'true') {
                liveTotalValue.textContent = finalText;
                liveTotal.hidden = false;
            }

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
            var qty = options.quantity !== undefined ? options.quantity : syncQuantityField();
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
                        renderAgencySummary(data);

                        if (options.showDiscountSuccess && code) {
                            showDiscountMessage(
                                'کد اعمال شد — ' + formatNumber(data.total_discount) + ' تومان تخفیف',
                                'success'
                            );
                        }
                    } else {
                        fallbackPricingFromDataset(selected, qty);
                        renderAgencySummary({ quantity: qty, final_price: pricingState.final });
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
                    renderAgencySummary({ quantity: qty, final_price: pricingState.final });
                    if (options.showDiscountError) {
                        showDiscountMessage('خطا در ارتباط. دوباره تلاش کنید.', 'error');
                    }
                    renderSummary();
                });
        }

        function showDiscountMessage(message, type) {
            if (!discountMsg) return;
            discountMsg.className = 'ck-promo-msg is-' + type;
            discountMsg.textContent = message;
        }

        function clearDiscountMessage() {
            if (!discountMsg) return;
            discountMsg.className = 'ck-promo-msg';
            discountMsg.textContent = '';
        }

        function submitBuyForm() {
            if (!form) return false;
            if (typeof form.requestSubmit === 'function') {
                try {
                    if (hiddenSubmit) {
                        form.requestSubmit(hiddenSubmit);
                    } else {
                        form.requestSubmit();
                    }
                    return true;
                } catch (err) {
                    /* Safari/WebView قدیمی — fallback */
                }
            }
            if (hiddenSubmit) {
                hiddenSubmit.click();
                return true;
            }
            form.submit();
            return true;
        }

        function handlePayClick(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            var selected = getSelectedPlan();
            if (!selected) {
                alert('لطفاً یک پلن انتخاب کنید.');
                return false;
            }
            syncQuantityField();
            if (!form.checkValidity()) {
                form.reportValidity();
                return false;
            }
            return submitBuyForm();
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
                fetchPlanPricing({ discountCode: '', quantity: syncQuantityField() });
                return;
            }

            applyBtn.disabled = true;
            applyBtn.textContent = 'بررسی...';
            discountInput.value = code;

            var requestId = ++pricingRequestId;
            var qty = syncQuantityField();

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
                        renderAgencySummary(data);
                        showDiscountMessage(
                            'کد اعمال شد — ' + formatNumber(data.total_discount) + ' تومان تخفیف',
                            'success'
                        );
                    } else {
                        fallbackPricingFromDataset(selected, qty);
                        renderAgencySummary({ quantity: qty, final_price: pricingState.final });
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
                document.querySelectorAll('.ck-plan, .ck-agency-duration-btn').forEach(function (c) {
                    c.classList.remove('is-selected');
                });
                var host = this.closest('.ck-plan, .ck-agency-duration-btn');
                if (host) host.classList.add('is-selected');
                if (this.dataset.allowBulk === 'true') {
                    setPlanMode('agency');
                } else {
                    setPlanMode('personal');
                }

                if (discountInput) discountInput.value = '';
                clearDiscountMessage();
                var qty = syncQuantityField();
                fallbackPricingFromDataset(this, qty);
                renderSummary();
                fetchPlanPricing({ discountCode: '', quantity: qty });
            });
        });

        document.querySelectorAll('.ck-plan, .ck-agency-duration-btn').forEach(function (card) {
            card.addEventListener('click', function (e) {
                if (e.target.tagName === 'INPUT') return;
                var radio = card.querySelector('input[type="radio"]');
                if (radio && !radio.disabled && !radio.checked) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        });

        if (qtyInput) {
            qtyInput.addEventListener('input', scheduleQuantityUpdate);
            qtyInput.addEventListener('change', scheduleQuantityUpdate);
        }

        document.querySelectorAll('[data-qty-step]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!qtyInput) return;
                var step = parseInt(btn.dataset.qtyStep, 10) || 0;
                var current = syncQuantityField();
                applyQuantityChange(current + step);
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
            btn.addEventListener('click', handlePayClick);
        });

        form.addEventListener('submit', function (e) {
            var selected = getSelectedPlan();
            if (!selected) {
                e.preventDefault();
                alert('لطفاً یک پلن انتخاب کنید.');
                return;
            }
            syncQuantityField();
            if (!form.checkValidity()) {
                e.preventDefault();
                form.reportValidity();
            }
        });

        updatePaymentHints();

        var initial = getSelectedPlan();
        if (initial) {
            setPlanMode(initial.dataset.allowBulk === 'true' ? 'agency' : 'personal');
            var card = initial.closest('.ck-plan, .ck-agency-duration-btn');
            if (card) card.classList.add('is-selected');
            var initialQty = syncQuantityField();
            fallbackPricingFromDataset(initial, initialQty);
            renderSummary();
            fetchPlanPricing({ discountCode: '', quantity: initialQty });
        } else {
            setPlanMode('personal');
        }

        setTimeout(function () {
            if (pricingState.loading) {
                pricingState.loading = false;
                renderSummary();
            }
        }, 12000);

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

        function markStepDone(stepNum) {
            var step = successRoot.querySelector('.ck-next-step[data-step="' + stepNum + '"]');
            if (step) step.classList.add('is-done');
        }

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
                    var stepNum = btn.getAttribute('data-mark-step');
                    if (stepNum) markStepDone(stepNum);
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

        successRoot.querySelectorAll('[data-mark-step="2"]').forEach(function (el) {
            el.addEventListener('click', function () {
                markStepDone('2');
            });
        });
    });
})();
