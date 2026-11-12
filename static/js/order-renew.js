(function () {
    'use strict';
    var root = document.querySelector('[data-order-renew]');
    if (!root) return;
    var form = document.getElementById('orderRenewForm');
    if (!form) return;
    var quoteUrl = root.getAttribute('data-quote-url');
    var summary = document.getElementById('renewSummary');
    var submitBtn = document.getElementById('renewSubmit');
    var planSelect = document.getElementById('renewPlan');
    var debounceTimer;

    function selectedIds() {
        return Array.prototype.slice
            .call(form.querySelectorAll('.ck-renew-check:checked'))
            .map(function (el) { return parseInt(el.value, 10); })
            .filter(function (n) { return !isNaN(n); });
    }

    function formatMoney(n) {
        try {
            return Number(n).toLocaleString('fa-IR');
        } catch (e) {
            return String(n);
        }
    }

    function syncRowSelectedState() {
        form.querySelectorAll('.ck-renew-row').forEach(function (row) {
            var cb = row.querySelector('.ck-renew-check');
            if (!cb) return;
            row.classList.toggle('is-selected', cb.checked && !cb.disabled);
        });
    }

    function renderQuote(quote) {
        if (!quote || !quote.pricing) return;
        var p = quote.pricing;
        var items = quote.items || [];
        var lines = items.map(function (it) {
            return '<li>کلید ' + it.sequence + ' — انقضای جدید پس از پرداخت ثبت می‌شود</li>';
        }).join('');
        var discountBlock = '';
        if (p.discount_amount && Number(p.discount_amount) > 0) {
            discountBlock =
                '<div class="ck-order-line ck-order-line--discount">' +
                '<span>تخفیف</span>' +
                '<span class="ck-order-val">' + formatMoney(p.discount_amount) + ' تومان</span>' +
                '</div>';
        }
        if (p.original_price && Number(p.original_price) !== Number(p.final_price)) {
            discountBlock =
                '<div class="ck-order-line">' +
                '<span>قیمت پایه</span>' +
                '<span class="ck-order-val">' + formatMoney(p.original_price) + ' تومان</span>' +
                '</div>' + discountBlock;
        }
        summary.innerHTML =
            '<div class="ck-order-lines ck-buy-order-lines">' +
            '<div class="ck-order-line">' +
            '<span>لایسنس انتخاب‌شده</span>' +
            '<span class="ck-order-val">' + quote.quantity + '</span>' +
            '</div>' +
            discountBlock +
            '</div>' +
            '<div class="ck-order-total ck-buy-order-total" role="status">' +
            '<span>قابل پرداخت</span>' +
            '<strong>' + formatMoney(p.final_price) + ' <small>تومان</small></strong>' +
            '</div>' +
            (lines ? '<ul class="ck-renew-summary__items">' + lines + '</ul>' : '');
        submitBtn.disabled = false;
    }

    function refreshQuote() {
        var ids = selectedIds();
        if (!ids.length) {
            summary.innerHTML = '<p class="ck-renew-summary__lead">حداقل یک لایسنس انتخاب کنید.</p>';
            submitBtn.disabled = true;
            return;
        }
        summary.innerHTML = '<p class="ck-renew-summary__lead">در حال محاسبه قیمت…</p>';
        submitBtn.disabled = true;
        fetch(quoteUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (form.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                license_ids: ids,
                plan_id: planSelect ? planSelect.value : null,
            }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.ok) {
                    summary.innerHTML = '<p class="ck-renew-summary__error">' + (data.error || 'خطا در محاسبه') + '</p>';
                    return;
                }
                renderQuote(data.quote);
            })
            .catch(function () {
                summary.innerHTML = '<p class="ck-renew-summary__error">خطا در ارتباط با سرور</p>';
            });
    }

    function scheduleQuote() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(refreshQuote, 280);
    }

    form.querySelectorAll('.ck-renew-check').forEach(function (el) {
        el.addEventListener('change', function () {
            syncRowSelectedState();
            scheduleQuote();
        });
    });
    syncRowSelectedState();
    if (planSelect) planSelect.addEventListener('change', scheduleQuote);

    var selectAll = root.querySelector('[data-renew-select-all]');
    var selectNone = root.querySelector('[data-renew-select-none]');
    if (selectAll) {
        selectAll.addEventListener('click', function () {
            form.querySelectorAll('.ck-renew-check:not(:disabled)').forEach(function (c) { c.checked = true; });
            syncRowSelectedState();
            scheduleQuote();
        });
    }
    if (selectNone) {
        selectNone.addEventListener('click', function () {
            form.querySelectorAll('.ck-renew-check').forEach(function (c) { c.checked = false; });
            syncRowSelectedState();
            scheduleQuote();
        });
    }

    scheduleQuote();
})();
