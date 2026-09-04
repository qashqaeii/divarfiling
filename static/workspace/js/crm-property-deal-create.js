(function () {
    'use strict';

    function csrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function debounce(fn, ms) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function initPropertyDealCreate() {
        const form = document.getElementById('crmPropDealCreateForm');
        const root = document.getElementById('crmPropDealFormRoot');
        if (!form || !root) return;

        const searchUrl = root.dataset.searchUrl;
        const duplicateUrl = root.dataset.duplicateUrl;
        const quickUrl = root.dataset.quickCustomerUrl;
        const customerInput = form.querySelector('[name=customer]');
        const forceInput = form.querySelector('[name=force_duplicate]');
        const dealKindSelect = form.querySelector('[name=deal_kind]');
        const titleInput = form.querySelector('[data-prop-deal-title]');
        const searchInput = root.querySelector('[data-prop-deal-search]');
        const resultsEl = root.querySelector('[data-prop-deal-results]');
        const selectedEl = root.querySelector('[data-prop-deal-selected]');
        const searchWrap = root.querySelector('[data-prop-deal-search-wrap]');
        const selectedName = root.querySelector('[data-prop-deal-selected-name]');
        const selectedMeta = root.querySelector('[data-prop-deal-selected-meta]');
        const dupWarn = root.querySelector('[data-prop-deal-dup-warn]');
        const submitBtn = form.querySelector('[data-prop-deal-submit]');
        const submitLabel = form.querySelector('[data-prop-deal-submit-label]');
        const quickPanel = root.querySelector('[data-prop-deal-quick]');
        const quickOpen = root.querySelector('[data-prop-deal-quick-open]');
        const quickClose = root.querySelector('[data-prop-deal-quick-close]');
        const quickSave = root.querySelector('[data-prop-deal-quick-save]');
        const quickName = root.querySelector('[data-prop-deal-quick-name]');
        const quickPhone = root.querySelector('[data-prop-deal-quick-phone]');
        const quickType = root.querySelector('[data-prop-deal-quick-type]');
        const quickErr = root.querySelector('[data-prop-deal-quick-err]');

        let selectedCustomer = null;

        function syncQuickTypeFromDealKind() {
            if (!quickType || !dealKindSelect) return;
            quickType.value = dealKindSelect.value === 'rent' ? 'مستاجر' : 'خریدار';
        }

        function renderResults(items) {
            if (!resultsEl) return;
            if (!items || !items.length) {
                resultsEl.innerHTML = '<div class="crm-prop-deal-customer-result" style="cursor:default;color:#94a3b8">نتیجه‌ای یافت نشد</div>';
                resultsEl.hidden = false;
                return;
            }
            resultsEl.innerHTML = items.map((c) => {
                const related = c.related ? ' is-related' : '';
                const section = c.related ? 'مخاطب مرتبط — ' : '';
                const meta = [c.phone, c.type || c.role].filter(Boolean).join(' · ');
                return `<button type="button" class="crm-prop-deal-customer-result${related}" data-id="${c.id}" data-name="${escapeAttr(c.name)}" data-meta="${escapeAttr(meta)}">
                    <strong>${escapeHtml(section + c.name)}</strong>
                    <em>${escapeHtml(meta)}</em>
                </button>`;
            }).join('');
            resultsEl.hidden = false;
        }

        function escapeHtml(s) {
            return String(s || '').replace(/[&<>"']/g, (ch) => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
            }[ch]));
        }

        function escapeAttr(s) {
            return escapeHtml(s).replace(/"/g, '&quot;');
        }

        function selectCustomer(id, name, meta) {
            selectedCustomer = { id, name, meta };
            if (customerInput) customerInput.value = id;
            if (selectedName) selectedName.textContent = name;
            if (selectedMeta) selectedMeta.textContent = meta || '';
            if (selectedEl) selectedEl.hidden = false;
            if (searchWrap) searchWrap.hidden = true;
            if (resultsEl) resultsEl.hidden = true;
            if (searchInput) searchInput.value = '';
            checkDuplicate(id);
            updateTitlePreview();
        }

        function clearCustomer() {
            selectedCustomer = null;
            if (customerInput) customerInput.value = '';
            if (selectedEl) selectedEl.hidden = true;
            if (searchWrap) searchWrap.hidden = false;
            if (dupWarn) dupWarn.hidden = true;
        }

        function checkDuplicate(customerId) {
            if (!duplicateUrl || !customerId || !dupWarn) return;
            fetch(`${duplicateUrl}?customer_id=${encodeURIComponent(customerId)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then((r) => r.json())
                .then((data) => {
                    if (!data.duplicate) {
                        dupWarn.hidden = true;
                        return;
                    }
                    dupWarn.innerHTML = `برای این مخاطب و این ملک یک معامله فعال وجود دارد: <a href="${data.duplicate.url}">${escapeHtml(data.duplicate.title)}</a> — ${escapeHtml(data.duplicate.stage)}. می‌توانید با این حال معامله جدید بسازید.`;
                    dupWarn.hidden = false;
                })
                .catch(() => {});
        }

        function updateTitlePreview() {
            if (!titleInput || !selectedCustomer) return;
            const base = titleInput.dataset.baseTitle || titleInput.placeholder || titleInput.value;
            if (!titleInput.dataset.userEdited) {
                const kindLabel = dealKindSelect && dealKindSelect.options[dealKindSelect.selectedIndex]
                    ? dealKindSelect.options[dealKindSelect.selectedIndex].text
                    : '';
                const propPart = (base || '').replace(/^(فروش|رهن و اجاره|اجاره)\s+/, '');
                titleInput.value = `${kindLabel} ${propPart}`.trim() + (selectedCustomer.name ? ` به ${selectedCustomer.name}` : '');
            }
        }

        const doSearch = debounce((q) => {
            if (!searchUrl) return;
            fetch(`${searchUrl}?q=${encodeURIComponent(q || '')}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then((r) => r.json())
                .then((data) => renderResults(data.results || []))
                .catch(() => {});
        }, 280);

        if (searchInput) {
            searchInput.addEventListener('focus', () => doSearch(''));
            searchInput.addEventListener('input', () => doSearch(searchInput.value.trim()));
        }

        if (resultsEl) {
            resultsEl.addEventListener('click', (e) => {
                const btn = e.target.closest('[data-id]');
                if (!btn) return;
                selectCustomer(btn.dataset.id, btn.dataset.name, btn.dataset.meta);
            });
        }

        root.querySelector('[data-prop-deal-clear]')?.addEventListener('click', clearCustomer);

        if (dealKindSelect) {
            dealKindSelect.addEventListener('change', () => {
                syncQuickTypeFromDealKind();
                updateTitlePreview();
            });
        }

        if (titleInput) {
            titleInput.dataset.baseTitle = titleInput.value;
            titleInput.addEventListener('input', () => {
                titleInput.dataset.userEdited = '1';
            });
        }

        quickOpen?.addEventListener('click', () => {
            if (quickPanel) quickPanel.hidden = false;
            syncQuickTypeFromDealKind();
        });
        quickClose?.addEventListener('click', () => {
            if (quickPanel) quickPanel.hidden = true;
            if (quickErr) quickErr.hidden = true;
        });

        quickSave?.addEventListener('click', () => {
            if (!quickUrl) return;
            const name = (quickName?.value || '').trim();
            if (!name) {
                if (quickErr) {
                    quickErr.textContent = 'نام مخاطب الزامی است.';
                    quickErr.hidden = false;
                }
                return;
            }
            const body = new FormData();
            body.append('name', name);
            body.append('phone', quickPhone?.value || '');
            body.append('source', 'سایر');
            body.append('deal_kind', dealKindSelect?.value || 'sale');
            if (quickType?.value) {
                body.append('customer_type', quickType.value);
            }
            fetch(quickUrl, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken(),
                },
                body,
            })
                .then((r) => r.json())
                .then((data) => {
                    if (!data.ok) {
                        if (quickErr) {
                            quickErr.textContent = 'ثبت مخاطب انجام نشد.';
                            quickErr.hidden = false;
                        }
                        return;
                    }
                    const c = data.customer;
                    selectCustomer(String(c.id), c.name, [c.phone, c.type].filter(Boolean).join(' · '));
                    if (quickPanel) quickPanel.hidden = true;
                    if (quickName) quickName.value = '';
                    if (quickPhone) quickPhone.value = '';
                })
                .catch(() => {
                    if (quickErr) {
                        quickErr.textContent = 'خطا در ارتباط با سرور.';
                        quickErr.hidden = false;
                    }
                });
        });

        form.addEventListener('submit', (e) => {
            if (!form.dataset.ajax) return;
            e.preventDefault();
            if (!customerInput?.value) {
                alert('لطفاً مخاطب معامله را انتخاب کنید.');
                return;
            }
            if (submitBtn) submitBtn.disabled = true;
            if (submitLabel) submitLabel.textContent = 'در حال ثبت معامله...';

            fetch(form.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: new FormData(form),
            })
                .then(async (r) => {
                    const data = await r.json().catch(() => ({}));
                    if (r.ok && data.ok && data.redirect) {
                        window.location.href = data.redirect;
                        return;
                    }
                    if (r.ok) {
                        window.location.reload();
                        return;
                    }
                    if (data.duplicate && dupWarn) {
                        dupWarn.innerHTML = `برای این مخاطب و این ملک یک معامله فعال وجود دارد. <a href="${data.duplicate.url}">مشاهده معامله موجود</a> — یا با فعال‌کردن «با این حال بساز» ادامه دهید.`;
                        dupWarn.hidden = false;
                        if (forceInput && confirm('معامله فعال مشابه وجود دارد. با این حال معامله جدید ساخته شود؟')) {
                            forceInput.checked = true;
                            form.requestSubmit();
                        }
                    } else {
                        const msg = (data.errors && (data.errors.__all__ || data.errors.customer)) || 'ثبت معامله انجام نشد.';
                        const text = Array.isArray(msg) ? msg.join(' ') : String(msg);
                        alert(text);
                    }
                })
                .catch(() => alert('خطا در ثبت معامله. دوباره تلاش کنید.'))
                .finally(() => {
                    if (submitBtn) submitBtn.disabled = false;
                    if (submitLabel) submitLabel.textContent = 'ثبت معامله';
                });
        });

        syncQuickTypeFromDealKind();
        doSearch('');
    }

    document.addEventListener('DOMContentLoaded', initPropertyDealCreate);
})();
