/**
 * ابزارهای هوشمند — جعبه ابزار مشاور
 * محاسبه آنی سمت کلاینت
 */
(function () {
    'use strict';

    const TOOL_KEYS = ['deposit', 'area', 'commission'];

    function parseNum(el) {
        if (!el) return null;
        const raw = typeof readFormattedInput === 'function'
            ? readFormattedInput(el)
            : el.value.replace(/[^\d.]/g, '');
        if (!raw && raw !== 0) return null;
        const n = parseFloat(raw);
        return isNaN(n) ? null : n;
    }

    function formatToman(n) {
        if (n == null || isNaN(n)) return '—';
        const s = typeof formatWithSeparators === 'function'
            ? formatWithSeparators(Math.round(n))
            : Math.round(n).toLocaleString('fa-IR');
        return s + ' تومان';
    }

    function formatM(n) {
        if (n == null || isNaN(n)) return '—';
        return Number(n).toLocaleString('fa-IR', { maximumFractionDigits: 1 }) + ' M';
    }

    function formatArea(n) {
        if (n == null || isNaN(n)) return '—';
        return Number(n).toLocaleString('fa-IR', { maximumFractionDigits: 0 }) + ' متر';
    }

    function calcDeposit(deposit, rent, rate) {
        if (!rate) return null;
        if (deposit) {
            return { type: 'rent', value: Math.round(deposit / rate), label: 'اجاره ماهانه معادل' };
        }
        if (rent) {
            return { type: 'deposit', value: Math.round(rent * rate), label: 'ودیعه کامل معادل' };
        }
        return null;
    }

    function calcArea(pps, area, total) {
        if (pps && area) {
            return {
                hero: { val: formatToman(Math.round(pps * area)), lbl: 'قیمت کل' },
                items: [
                    { val: formatM(pps), lbl: 'قیمت هر متر' },
                    { val: formatArea(area), lbl: 'متراژ' },
                ],
                copy: formatToman(Math.round(pps * area)),
            };
        }
        if (total && area && area > 0) {
            const p = Math.round(total / area);
            return {
                hero: { val: formatM(p), lbl: 'قیمت هر متر' },
                items: [
                    { val: formatToman(total), lbl: 'قیمت کل' },
                    { val: formatArea(area), lbl: 'متراژ' },
                ],
                copy: formatM(p) + ' — ' + formatToman(total),
            };
        }
        if (total && pps && pps > 0) {
            const a = Math.round((total / pps) * 10) / 10;
            return {
                hero: { val: formatArea(a), lbl: 'متراژ' },
                items: [
                    { val: formatToman(total), lbl: 'قیمت کل' },
                    { val: formatM(pps), lbl: 'قیمت هر متر' },
                ],
                copy: formatArea(a) + ' — ' + formatToman(total),
            };
        }
        return null;
    }

    function calcCommission(price, buyerPct, sellerPct) {
        if (!price) return null;
        const buyer = Math.round(price * buyerPct / 100);
        const seller = Math.round(price * sellerPct / 100);
        const total = buyer + seller;
        return {
            hero: { val: formatToman(total), lbl: 'جمع کل کمیسیون' },
            items: [
                { val: formatToman(buyer), lbl: `خریدار (${buyerPct}٪)` },
                { val: formatToman(seller), lbl: `فروشنده (${sellerPct}٪)` },
            ],
            copy: `کمیسیون کل: ${formatToman(total)} | خریدار: ${formatToman(buyer)} | فروشنده: ${formatToman(seller)}`,
        };
    }

    function renderHero(container, hero, copyText) {
        container.innerHTML = `
            <div class="ws-tbx-result-live">
                <div class="ws-tbx-result-hero">
                    <span class="ws-tbx-result-hero-val">${hero.val}</span>
                    <span class="ws-tbx-result-hero-lbl">${hero.lbl}</span>
                </div>
                <div class="ws-tbx-result-actions">
                    <button type="button" class="ws-tbx-copy-btn" data-copy="${copyText || hero.val}">
                        <i class="fas fa-copy" aria-hidden="true"></i> کپی نتیجه
                    </button>
                </div>
            </div>`;
        bindCopy(container.querySelector('.ws-tbx-copy-btn'));
    }

    function renderGrid(container, data) {
        const itemsHtml = (data.items || []).map(it => `
            <div class="ws-tbx-result-item">
                <span class="ws-tbx-result-item-val">${it.val}</span>
                <span class="ws-tbx-result-item-lbl">${it.lbl}</span>
            </div>`).join('');
        container.innerHTML = `
            <div class="ws-tbx-result-live">
                <div class="ws-tbx-result-hero">
                    <span class="ws-tbx-result-hero-val">${data.hero.val}</span>
                    <span class="ws-tbx-result-hero-lbl">${data.hero.lbl}</span>
                </div>
                ${itemsHtml ? `<div class="ws-tbx-result-grid">${itemsHtml}</div>` : ''}
                <div class="ws-tbx-result-actions">
                    <button type="button" class="ws-tbx-copy-btn" data-copy="${data.copy}">
                        <i class="fas fa-copy" aria-hidden="true"></i> کپی نتیجه
                    </button>
                </div>
            </div>`;
        bindCopy(container.querySelector('.ws-tbx-copy-btn'));
    }

    function renderEmpty(container, icon, text) {
        container.innerHTML = `
            <div class="ws-tbx-result-empty">
                <i class="fas ${icon}" aria-hidden="true"></i>
                <p>${text}</p>
            </div>`;
    }

    function bindCopy(btn) {
        if (!btn) return;
        btn.addEventListener('click', () => {
            const text = btn.dataset.copy;
            navigator.clipboard.writeText(text).then(() => {
                btn.classList.add('is-copied');
                const orig = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i> کپی شد';
                setTimeout(() => {
                    btn.classList.remove('is-copied');
                    btn.innerHTML = orig;
                }, 2000);
            });
        });
    }

    function switchTool(tool) {
        if (!TOOL_KEYS.includes(tool)) tool = 'deposit';
        document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
            const active = btn.dataset.tool === tool;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        document.querySelectorAll('.ws-tbx-panel').forEach(panel => {
            const active = panel.dataset.toolPanel === tool;
            panel.classList.toggle('is-active', active);
            panel.hidden = !active;
        });
        try { history.replaceState(null, '', '?tool=' + tool); } catch (e) {}
    }

    function updateDeposit() {
        const container = document.getElementById('tbxDepositResult');
        if (!container) return;
        const deposit = parseNum(document.getElementById('tbxFullDeposit'));
        const rent = parseNum(document.getElementById('tbxFullRent'));
        const rate = parseNum(document.getElementById('tbxRate')) || 30;
        if (deposit && rent) {
            renderEmpty(container, 'fa-circle-exclamation', 'فقط یکی از ودیعه یا اجاره را وارد کنید');
            return;
        }
        const r = calcDeposit(deposit, rent, rate);
        if (!r) {
            renderEmpty(container, 'fa-calculator', 'مقدار را وارد کنید — نتیجه بلافاصله نمایش داده می‌شود');
            return;
        }
        const val = formatToman(r.value);
        renderHero(container, { val, lbl: r.label }, val);
    }

    function updateArea() {
        const container = document.getElementById('tbxAreaResult');
        if (!container) return;
        const pps = parseNum(document.getElementById('tbxPps'));
        const area = parseNum(document.getElementById('tbxArea'));
        const total = parseNum(document.getElementById('tbxTotal'));
        const filled = [pps, area, total].filter(v => v != null).length;
        if (filled < 2) {
            renderEmpty(container, 'fa-ruler-combined', 'حداقل دو فیلد را پر کنید');
            return;
        }
        const r = calcArea(pps, area, total);
        if (!r) {
            renderEmpty(container, 'fa-circle-exclamation', 'ترکیب ورودی نامعتبر است');
            return;
        }
        renderGrid(container, r);
    }

    function updateCommission() {
        const container = document.getElementById('tbxCommissionResult');
        if (!container) return;
        const price = parseNum(document.getElementById('tbxPrice'));
        const buyerPct = parseNum(document.getElementById('tbxBuyerPct')) ?? 1;
        const sellerPct = parseNum(document.getElementById('tbxSellerPct')) ?? 1;
        if (!price) {
            renderEmpty(container, 'fa-percent', 'قیمت معامله را وارد کنید');
            return;
        }
        const r = calcCommission(price, buyerPct, sellerPct);
        renderGrid(container, r);
    }

    function bindCalcInputs(ids, updater) {
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', updater);
            if (typeof bindFormattedNumericInput === 'function') {
                bindFormattedNumericInput(el, { onChange: updater });
            }
        });
    }

    function initToolbox() {
        const root = document.getElementById('wsToolbox');
        if (!root) return;

        document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
            btn.addEventListener('click', () => switchTool(btn.dataset.tool));
        });

        const search = document.getElementById('wsTbxSearch');
        if (search) {
            search.addEventListener('input', () => {
                const q = search.value.trim().toLowerCase();
                document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
                    const text = btn.textContent.toLowerCase();
                    btn.classList.toggle('is-hidden', q.length > 0 && !text.includes(q));
                });
            });
        }

        document.querySelectorAll('.ws-tbx-preset[data-rate]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-preset[data-rate]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                const rateEl = document.getElementById('tbxRate');
                if (rateEl) {
                    rateEl.value = btn.dataset.rate;
                    if (typeof bindFormattedNumericInput !== 'function') updateDeposit();
                }
                updateDeposit();
            });
        });

        document.querySelectorAll('.ws-tbx-preset[data-commission]').forEach(btn => {
            btn.addEventListener('click', () => {
                const [b, s] = btn.dataset.commission.split(',');
                const buyerEl = document.getElementById('tbxBuyerPct');
                const sellerEl = document.getElementById('tbxSellerPct');
                if (buyerEl) buyerEl.value = b;
                if (sellerEl) sellerEl.value = s;
                updateCommission();
            });
        });

        bindCalcInputs(['tbxFullDeposit', 'tbxFullRent', 'tbxRate'], updateDeposit);
        bindCalcInputs(['tbxPps', 'tbxArea', 'tbxTotal'], updateArea);
        bindCalcInputs(['tbxPrice', 'tbxBuyerPct', 'tbxSellerPct'], updateCommission);

        const depEl = document.getElementById('tbxFullDeposit');
        const rentEl = document.getElementById('tbxFullRent');
        if (depEl && rentEl) {
            depEl.addEventListener('input', () => { if (depEl.value.trim()) rentEl.value = ''; });
            rentEl.addEventListener('input', () => { if (rentEl.value.trim()) depEl.value = ''; });
        }

        if (typeof initFormattedNumericInputs === 'function') {
            initFormattedNumericInputs(root);
        }

        document.addEventListener('keydown', e => {
            if (e.target.matches('input, textarea, select')) return;
            const n = parseInt(e.key, 10);
            if (n >= 1 && n <= 3) switchTool(TOOL_KEYS[n - 1]);
        });

        const params = new URLSearchParams(window.location.search);
        const initial = params.get('tool');
        if (initial && TOOL_KEYS.includes(initial)) {
            switchTool(initial);
        }
    }

    document.addEventListener('DOMContentLoaded', initToolbox);
})();
