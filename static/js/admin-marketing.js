(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toFa(n) {
        return String(n).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatNum(n) {
        return toFa(Number(n || 0).toLocaleString('en-US'));
    }

    function formatMoney(n) {
        return formatNum(n) + ' ت';
    }

    /* ─── Tabs ─── */
    function initTabs() {
        var tabs = document.querySelectorAll('.adm-map-tab');
        var sections = [
            'map-overview', 'map-compose', 'map-templates', 'map-automation',
            'map-phonebook', 'map-history', 'map-analytics',
        ];

        function setActive() {
            var hash = (location.hash || '#map-overview').replace('#', '');
            if (sections.indexOf(hash) === -1) hash = 'map-overview';
            tabs.forEach(function (tab) {
                var href = (tab.getAttribute('href') || '').replace('#', '');
                tab.classList.toggle('is-active', href === hash);
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                setTimeout(setActive, 0);
            });
        });
        window.addEventListener('hashchange', setActive);
        setActive();
    }

    /* ─── Campaign Wizard ─── */
    function initWizard() {
        var form = document.getElementById('adm-mkt-send-form');
        if (!form) return;

        var steps = Array.prototype.slice.call(document.querySelectorAll('.adm-map-wizard-step'));
        var panels = Array.prototype.slice.call(
            document.querySelectorAll('#adm-mkt-send-form .adm-map-wizard-panel')
        );
        var btnPrev = document.getElementById('adm-map-wizard-prev');
        var btnNext = document.getElementById('adm-map-wizard-next');
        var current = 0;

        var filterPanel = document.getElementById('adm-map-filter-panel');

        function showStep(idx) {
            current = Math.max(0, Math.min(steps.length - 1, idx));
            steps.forEach(function (step, i) {
                step.classList.toggle('is-active', i === current);
                step.classList.toggle('is-done', i < current);
            });
            panels.forEach(function (panel, i) {
                panel.classList.toggle('is-active', i === current);
            });
            if (filterPanel) filterPanel.hidden = current !== 0;
            if (btnPrev) btnPrev.hidden = current === 0;
            if (btnNext) {
                btnNext.textContent = current === steps.length - 1 ? 'آماده ارسال' : 'مرحله بعد';
                btnNext.hidden = current === steps.length - 1;
            }
            var submitWrap = document.getElementById('adm-map-wizard-submit');
            if (submitWrap) submitWrap.hidden = current !== steps.length - 1;
            updateReview();
        }

        steps.forEach(function (step, i) {
            step.addEventListener('click', function () {
                showStep(i);
            });
        });

        if (btnPrev) {
            btnPrev.addEventListener('click', function () {
                showStep(current - 1);
            });
        }
        if (btnNext) {
            btnNext.addEventListener('click', function () {
                showStep(current + 1);
            });
        }

        /* Audience radio sync with segment select */
        var segmentSelect = document.getElementById('adm-mkt-segment-select');
        var audienceRadios = form.querySelectorAll('.adm-map-audience-opt input[name="wizard_segment"]');
        audienceRadios.forEach(function (radio) {
            radio.addEventListener('change', function () {
                if (!radio.checked || radio.disabled) return;
                if (segmentSelect) {
                    segmentSelect.value = radio.value;
                    var filterForm = document.getElementById('adm-mkt-filter-form');
                    if (filterForm) filterForm.submit();
                }
            });
        });

        showStep(0);
    }

    function updateReview() {
        var form = document.getElementById('adm-mkt-send-form');
        if (!form) return;

        var countEl = document.getElementById('adm-mkt-selected-count');
        var count = countEl ? countEl.textContent : '۰';
        var reviewCount = document.getElementById('adm-map-review-count');
        if (reviewCount) reviewCount.textContent = count;

        var templateEl = document.getElementById('adm-mkt-template');
        var reviewSample = document.getElementById('adm-map-review-sample');
        var liveText = document.getElementById('adm-mkt-live-text');
        if (reviewSample && liveText) {
            reviewSample.textContent = liveText.textContent || '—';
        }

        var mode = (form.querySelector('input[name="discount_mode"]:checked') || {}).value || 'none';
        var reviewDiscount = document.getElementById('adm-map-review-discount');
        if (reviewDiscount) {
            var labels = { none: 'بدون تخفیف', shared: 'کد مشترک', unique: 'کد یکتا' };
            reviewDiscount.textContent = labels[mode] || mode;
        }

        var creditEl = document.getElementById('adm-map-review-credit');
        if (creditEl && window.admMapMeta && window.admMapMeta.smsCredit != null) {
            creditEl.textContent = formatNum(window.admMapMeta.smsCredit);
        }
    }

    /* ─── Live Preview ─── */
    function initPreview() {
        var form = document.getElementById('adm-mkt-send-form');
        if (!form) return;

        var sharedField = form.querySelector('[data-shared-code-field]');
        var discountFields = form.querySelector('[data-discount-fields]');
        var templateEl = document.getElementById('adm-mkt-template');
        var liveText = document.getElementById('adm-mkt-live-text');
        var liveLen = document.getElementById('adm-mkt-live-len');
        var sharedCodeEl = document.getElementById('adm-mkt-shared-code');
        var toggleAll = document.getElementById('adm-mkt-toggle-all');
        var selectNone = document.getElementById('adm-mkt-select-none');
        var selectedCountEl = document.getElementById('adm-mkt-selected-count');
        var confirmCountEl = document.getElementById('adm-mkt-confirm-count');
        var submitBtn = document.getElementById('adm-mkt-submit');
        var searchEl = document.getElementById('adm-mkt-recipient-search');
        var recipientList = document.getElementById('adm-mkt-recipient-list');
        var phoneShell = document.getElementById('adm-map-phone-pro');
        var deviceTabs = document.querySelectorAll('.adm-map-device-tab');

        var sampleFields = {
            phone: document.getElementById('adm-map-sample-phone'),
            name: document.getElementById('adm-map-sample-name'),
            product: document.getElementById('adm-map-sample-product'),
            code: document.getElementById('adm-map-sample-code'),
        };

        deviceTabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                deviceTabs.forEach(function (t) { t.classList.remove('is-active'); });
                tab.classList.add('is-active');
                if (phoneShell) {
                    phoneShell.setAttribute('data-device', tab.getAttribute('data-device') || 'iphone');
                }
            });
        });

        function syncDiscount() {
            var mode = (form.querySelector('input[name="discount_mode"]:checked') || {}).value || 'none';
            if (discountFields) discountFields.hidden = mode === 'none';
            if (sharedField) sharedField.hidden = mode !== 'shared';
            form.querySelectorAll('.adm-mkt-radio-card').forEach(function (card) {
                var input = card.querySelector('input[type="radio"]');
                card.classList.toggle('is-active', input && input.checked);
            });
            updateLivePreview();
            updateReview();
        }

        function selectedCheckboxes() {
            return Array.prototype.slice.call(form.querySelectorAll('input[name="selected_phones"]'));
        }

        function visibleCheckboxes() {
            if (!recipientList) return selectedCheckboxes();
            return selectedCheckboxes().filter(function (b) {
                var row = b.closest('.adm-mkt-recipient');
                return row && row.style.display !== 'none';
            });
        }

        function updateSelectedCount() {
            var boxes = selectedCheckboxes();
            var n = boxes.filter(function (b) { return b.checked; }).length;
            if (selectedCountEl) selectedCountEl.textContent = formatNum(n);
            if (confirmCountEl) confirmCountEl.textContent = formatNum(n);
            if (toggleAll) {
                var visible = visibleCheckboxes();
                var visChecked = visible.filter(function (b) { return b.checked; }).length;
                toggleAll.checked = visible.length > 0 && visChecked === visible.length;
                toggleAll.indeterminate = visChecked > 0 && visChecked < visible.length;
            }
            if (submitBtn) submitBtn.disabled = n === 0;
            updateReview();
        }

        function resolveCode() {
            if (sampleFields.code && sampleFields.code.value.trim()) {
                return sampleFields.code.value.trim().toUpperCase();
            }
            var mode = (form.querySelector('input[name="discount_mode"]:checked') || {}).value || 'none';
            if (mode === 'none') return '—';
            if (mode === 'shared') {
                var code = (sharedCodeEl && sharedCodeEl.value || '').trim().toUpperCase();
                return code || 'RECOVER15';
            }
            return 'MK-XXXXXX';
        }

        function buildContext() {
            var ctx = {
                name: sampleFields.name ? sampleFields.name.value : '',
                name_part: sampleFields.name && sampleFields.name.value ? ' ' + sampleFields.name.value : '',
                product: sampleFields.product ? sampleFields.product.value : 'محصول',
                amount: '',
                link: 'https://divarfiling.ir/',
                code: resolveCode(),
            };
            var el = document.getElementById('adm-mkt-sample-context');
            if (el) {
                try {
                    var base = JSON.parse(el.textContent);
                    Object.keys(base).forEach(function (k) {
                        if (ctx[k] === '' || ctx[k] === 'محصول') {
                            if (base[k]) ctx[k] = base[k];
                        }
                    });
                } catch (e) { /* ignore */ }
            }
            if (sampleFields.name && sampleFields.name.value) {
                ctx.name = sampleFields.name.value;
                ctx.name_part = ' ' + sampleFields.name.value;
            }
            if (sampleFields.product && sampleFields.product.value) {
                ctx.product = sampleFields.product.value;
            }
            ctx.code = resolveCode();
            return ctx;
        }

        function renderTemplate(tpl, ctx) {
            return String(tpl || '').replace(/\{(\w+)\}/g, function (_, key) {
                return ctx[key] != null ? String(ctx[key]) : '';
            });
        }

        function updateLivePreview() {
            if (!templateEl || !liveText) return;
            var ctx = buildContext();
            var text = renderTemplate(templateEl.value, ctx);
            liveText.textContent = text || '—';
            if (liveLen) {
                liveLen.textContent = toFa(text.length) + ' کاراکتر · ' +
                    (text.length <= 70 ? '۱ پیامک' : toFa(Math.ceil(text.length / 67)) + ' پیامک');
            }
            updateReview();
        }

        form.querySelectorAll('input[name="discount_mode"]').forEach(function (el) {
            el.addEventListener('change', syncDiscount);
        });
        if (templateEl) templateEl.addEventListener('input', updateLivePreview);
        if (sharedCodeEl) sharedCodeEl.addEventListener('input', updateLivePreview);

        Object.keys(sampleFields).forEach(function (key) {
            if (sampleFields[key]) {
                sampleFields[key].addEventListener('input', updateLivePreview);
            }
        });

        document.querySelectorAll('.adm-map-var-btn').forEach(function (chip) {
            chip.addEventListener('click', function () {
                if (!templateEl) return;
                var v = chip.getAttribute('data-var') || '';
                var start = templateEl.selectionStart;
                var end = templateEl.selectionEnd;
                var val = templateEl.value;
                templateEl.value = val.slice(0, start) + v + val.slice(end);
                templateEl.focus();
                templateEl.selectionStart = templateEl.selectionEnd = start + v.length;
                updateLivePreview();
            });
        });

        if (searchEl && recipientList) {
            searchEl.addEventListener('input', function () {
                var q = (searchEl.value || '').trim().toLowerCase();
                recipientList.querySelectorAll('.adm-mkt-recipient').forEach(function (row) {
                    var hay = (row.getAttribute('data-search') || '').toLowerCase();
                    row.style.display = !q || hay.indexOf(q) !== -1 ? '' : 'none';
                });
                updateSelectedCount();
            });
        }

        selectedCheckboxes().forEach(function (box) {
            box.addEventListener('change', function () {
                updateSelectedCount();
                updateLivePreview();
            });
        });

        if (toggleAll) {
            toggleAll.addEventListener('change', function () {
                visibleCheckboxes().forEach(function (b) { b.checked = toggleAll.checked; });
                updateSelectedCount();
                updateLivePreview();
            });
        }
        if (selectNone) {
            selectNone.addEventListener('click', function () {
                selectedCheckboxes().forEach(function (b) { b.checked = false; });
                if (toggleAll) toggleAll.checked = false;
                updateSelectedCount();
                updateLivePreview();
            });
        }

        form.addEventListener('submit', function (e) {
            if (selectedCheckboxes().filter(function (b) { return b.checked; }).length === 0) {
                e.preventDefault();
                alert('حداقل یک گیرنده را انتخاب کنید.');
            }
        });

        syncDiscount();
        updateSelectedCount();
        updateLivePreview();
    }

    /* ─── Templates ─── */
    function initTemplates() {
        var templateEl = document.getElementById('adm-mkt-template');
        if (!templateEl) return;

        document.querySelectorAll('.adm-map-template-card').forEach(function (card) {
            card.addEventListener('click', function () {
                var text = card.getAttribute('data-template') || '';
                if (!text) return;
                templateEl.value = text;
                templateEl.dispatchEvent(new Event('input'));
                location.hash = 'map-compose';
                var wizard = document.querySelector('.adm-map-wizard-step[data-step="1"]');
                if (wizard) wizard.click();
            });
        });

        var aiBtn = document.getElementById('adm-map-ai-generate');
        if (aiBtn) {
            aiBtn.addEventListener('click', function () {
                var suggestion = window.admMapMeta && window.admMapMeta.aiTemplate;
                if (suggestion) {
                    templateEl.value = suggestion;
                    templateEl.dispatchEvent(new Event('input'));
                    location.hash = 'map-compose';
                }
            });
        }
    }

    /* ─── Analytics Charts ─── */
    function initCharts() {
        if (typeof Chart === 'undefined' || !window.admMapAnalytics) return;

        var data = window.admMapAnalytics;
        var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        var gridColor = isDark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)';
        var textColor = isDark ? '#94a3b8' : '#64748b';

        function faLabels(labels) {
            return (labels || []).map(function (l) {
                if (!l) return '';
                var parts = l.split('-');
                if (parts.length === 3) return toFa(parts[2]) + '/' + toFa(parts[1]);
                return toFa(l);
            });
        }

        var dailyCanvas = document.getElementById('adm-map-chart-daily');
        if (dailyCanvas) {
            new Chart(dailyCanvas, {
                type: 'bar',
                data: {
                    labels: faLabels(data.daily_labels),
                    datasets: [{
                        label: 'ارسال',
                        data: data.daily_values || [],
                        backgroundColor: 'rgba(124, 58, 237, 0.65)',
                        borderRadius: 6,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: textColor, font: { size: 10 } }, grid: { display: false } },
                        y: { ticks: { color: textColor, callback: function (v) { return toFa(v); } }, grid: { color: gridColor } },
                    },
                },
            });
        }

        var funnelCanvas = document.getElementById('adm-map-chart-funnel');
        if (funnelCanvas) {
            new Chart(funnelCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['تعامل', 'تبدیل', 'سایر'],
                    datasets: [{
                        data: [
                            data.engagement_rate || 0,
                            data.conversion_rate || 0,
                            Math.max(0, 100 - (data.engagement_rate || 0) - (data.conversion_rate || 0)),
                        ],
                        backgroundColor: ['#7c3aed', '#10b981', 'rgba(148, 163, 184, 0.2)'],
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: textColor, font: { size: 11 } } },
                    },
                },
            });
        }

        var revenueCanvas = document.getElementById('adm-map-chart-revenue');
        if (revenueCanvas) {
            new Chart(revenueCanvas, {
                type: 'line',
                data: {
                    labels: ['درآمد'],
                    datasets: [{
                        label: 'تومان',
                        data: [data.revenue || 0],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.15)',
                        fill: true,
                        tension: 0.35,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: false },
                        y: { ticks: { color: textColor, callback: function (v) { return formatNum(v); } }, grid: { color: gridColor } },
                    },
                },
            });
        }
    }

    /* ─── Phonebook ─── */
    function initPhonebook() {
        var meta = window.admMapMeta || {};
        var statusUrl = meta.phonebookStatusUrl;
        var syncUrl = meta.phonebookSyncUrl;
        var refreshBtn = document.getElementById('adm-phonebook-refresh');
        var syncBtn = document.getElementById('adm-phonebook-sync');
        var msgEl = document.getElementById('adm-phonebook-msg');
        var hintEl = document.getElementById('adm-phonebook-hint');
        var elSite = document.getElementById('adm-pb-site-valid');
        var elBook = document.getElementById('adm-pb-book-total');
        var elMissing = document.getElementById('adm-pb-missing');
        var elExtra = document.getElementById('adm-pb-extra');
        var csrf = document.querySelector('#adm-mkt-send-form input[name="csrfmiddlewaretoken"]');

        if (!refreshBtn || !syncBtn || !statusUrl) return;

        function setMsg(text, isError) {
            if (!msgEl) return;
            if (!text) {
                msgEl.hidden = true;
                msgEl.textContent = '';
                return;
            }
            msgEl.hidden = false;
            msgEl.textContent = text;
            msgEl.classList.toggle('adm-mkt-phonebook-msg--error', !!isError);
            msgEl.classList.toggle('adm-mkt-phonebook-msg--ok', !isError);
        }

        function renderStatus(data) {
            if (elSite) elSite.textContent = formatNum(data.site_users_valid);
            if (elBook) elBook.textContent = formatNum(data.phonebook_total);
            if (elMissing) elMissing.textContent = formatNum(data.missing_in_phonebook);
            if (elExtra) elExtra.textContent = formatNum(data.extra_in_phonebook);
            if (!data.ok && data.error) setMsg(data.error, true);
            else setMsg('');
        }

        function setLoading(loading) {
            refreshBtn.disabled = loading;
            syncBtn.disabled = loading;
            if (hintEl) hintEl.style.opacity = loading ? '0.55' : '';
        }

        function loadStatus() {
            setLoading(true);
            return fetch(statusUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
                .then(function (r) { return r.json(); })
                .then(renderStatus)
                .catch(function () { setMsg('بارگذاری وضعیت دفترچه ناموفق بود.', true); })
                .finally(function () { setLoading(false); });
        }

        function syncPhonebook() {
            if (!window.confirm('کاربران سایت در دفترچه تلفن فراز ثبت/به‌روز شوند؟')) return;
            setLoading(true);
            setMsg('در حال همگام‌سازی…', false);
            fetch(syncUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    Accept: 'application/json',
                    'X-CSRFToken': csrf ? csrf.value : '',
                },
            })
                .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
                .then(function (res) {
                    if (!res.ok || !res.body.ok) {
                        setMsg((res.body && res.body.error) || 'همگام‌سازی ناموفق بود.', true);
                        return;
                    }
                    var b = res.body;
                    setMsg(
                        'همگام‌سازی: ' + formatNum(b.synced) + ' کاربر در ' +
                        formatNum(b.batches) + ' دسته.',
                        false
                    );
                    return loadStatus();
                })
                .catch(function () { setMsg('خطا در ارتباط با سرور.', true); })
                .finally(function () { setLoading(false); });
        }

        refreshBtn.addEventListener('click', loadStatus);
        syncBtn.addEventListener('click', syncPhonebook);
        loadStatus();
    }

    /* ─── Segment actions ─── */
    function initSegments() {
        document.querySelectorAll('[data-map-segment]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                var action = el.getAttribute('data-map-action');
                var seg = el.getAttribute('data-map-segment');
                if (action === 'view' || action === 'campaign') {
                    e.preventDefault();
                    location.href = '?segment=' + encodeURIComponent(seg) + '#map-compose';
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTabs();
        initWizard();
        initPreview();
        initTemplates();
        initCharts();
        initPhonebook();
        initSegments();
    });
})();
