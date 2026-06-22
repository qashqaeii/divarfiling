/**
 * ابزارهای هوشمند — جعبه ابزار مشاور
 * محاسبه آنی سمت کلاینت
 */
(function () {
    'use strict';

    const TOOL_KEYS = [
        'mixed', 'deposit', 'compare', 'area', 'discount',
        'commission', 'rent_commission', 'budget', 'pricing',
    ];

    let marketSnapshot = null;

    function loadMarket() {
        const el = document.getElementById('wsTbxMarket');
        if (!el) return null;
        try {
            const data = JSON.parse(el.textContent || 'null');
            return data && typeof data === 'object' ? data : null;
        } catch (e) {
            return null;
        }
    }

    function parseNum(el) {
        if (!el) return null;
        const raw = typeof readFormattedInput === 'function'
            ? readFormattedInput(el)
            : el.value.replace(/[^\d.]/g, '');
        if (!raw && raw !== 0) return null;
        const n = parseFloat(raw);
        return isNaN(n) ? null : n;
    }

    function parseIntNum(el) {
        const n = parseNum(el);
        return n == null ? null : Math.round(n);
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

    function formatPct(n) {
        if (n == null || isNaN(n)) return '—';
        const sign = n > 0 ? '+' : '';
        return sign + Number(n).toLocaleString('fa-IR', { maximumFractionDigits: 1 }) + '٪';
    }

    function ppsToMillion(pps) {
        return pps / 1_000_000;
    }

    function millionToPps(m) {
        return m * 1_000_000;
    }

    function fullDepositEquiv(deposit, rent, rate) {
        const d = deposit || 0;
        const r = rent || 0;
        if (d === 0 && r === 0) return null;
        return Math.round(d + r * rate);
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

    function calcMixed(deposit, rent, rate) {
        if (!rate) return null;
        const d = deposit || 0;
        const r = rent || 0;
        if (d === 0 && r === 0) return null;
        const fullDep = fullDepositEquiv(d, r, rate);
        const fullRent = Math.round(fullDep / rate);
        return {
            hero: { val: formatToman(fullDep), lbl: 'رهن کامل معادل' },
            items: [
                { val: formatToman(fullRent), lbl: 'اجاره کامل معادل' },
                { val: formatToman(d), lbl: 'ودیعه واردشده' },
                { val: formatToman(r), lbl: 'اجاره واردشده' },
            ],
            copy: `رهن کامل: ${formatToman(fullDep)} | اجاره کامل: ${formatToman(fullRent)}`,
        };
    }

    function calcArea(pps, area, total) {
        if (pps && area) {
            const ppsRaw = millionToPps(pps);
            return {
                hero: { val: formatToman(Math.round(ppsRaw * area)), lbl: 'قیمت کل' },
                items: [
                    { val: formatM(pps), lbl: 'قیمت هر متر' },
                    { val: formatArea(area), lbl: 'متراژ' },
                ],
                copy: formatToman(Math.round(ppsRaw * area)),
            };
        }
        if (total && area && area > 0) {
            const p = Math.round(total / area / 1_000_000 * 10) / 10;
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
            const ppsRaw = millionToPps(pps);
            const a = Math.round((total / ppsRaw) * 10) / 10;
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

    function calcDiscount(listPrice, discountPct) {
        if (!listPrice) return null;
        const pct = Math.max(0, Math.min(discountPct || 0, 100));
        const savings = Math.round(listPrice * pct / 100);
        const finalPrice = listPrice - savings;
        return {
            hero: { val: formatToman(finalPrice), lbl: 'قیمت پس از تخفیف' },
            items: [
                { val: formatToman(listPrice), lbl: 'قیمت آگهی' },
                { val: formatToman(savings), lbl: `تخفیف (${pct}٪)` },
            ],
            copy: `قیمت نهایی: ${formatToman(finalPrice)} (تخفیف ${pct}٪ = ${formatToman(savings)})`,
        };
    }

    function calcRentCommission(rent, tenantShare, landlordShare) {
        if (!rent) return null;
        const tenant = Math.round(rent * tenantShare / 100);
        const landlord = Math.round(rent * landlordShare / 100);
        const total = tenant + landlord;
        return {
            hero: { val: formatToman(total), lbl: 'جمع کمیسیون اجاره' },
            items: [
                { val: formatToman(tenant), lbl: `مستأجر (${tenantShare}٪)` },
                { val: formatToman(landlord), lbl: `مالک (${landlordShare}٪)` },
            ],
            copy: `کمیسیون اجاره: ${formatToman(total)} | مستأجر: ${formatToman(tenant)} | مالک: ${formatToman(landlord)}`,
        };
    }

    function calcBudget(budget, ppsM, area) {
        if (!budget) return null;
        const hasPps = ppsM != null && ppsM > 0;
        const hasArea = area != null && area > 0;
        if (hasPps && hasArea) {
            const total = Math.round(millionToPps(ppsM) * area);
            const ok = total <= budget;
            return {
                hero: { val: ok ? 'بودجه کافی است' : formatToman(total - budget) + ' کمبود', lbl: ok ? 'وضعیت خرید' : 'کمبود بودجه' },
                items: [
                    { val: formatToman(total), lbl: 'قیمت ملک' },
                    { val: formatToman(budget), lbl: 'بودجه مشتری' },
                    { val: ok ? formatToman(budget - total) : '—', lbl: ok ? 'باقیمانده' : '—' },
                ],
                copy: ok
                    ? `بودجه کافی — قیمت ${formatToman(total)} از ${formatToman(budget)}`
                    : `کمبود ${formatToman(total - budget)} — قیمت ${formatToman(total)}`,
                verdictClass: ok ? 'is-ok' : 'is-warn',
            };
        }
        if (hasPps) {
            const maxArea = Math.round((budget / millionToPps(ppsM)) * 10) / 10;
            return {
                hero: { val: formatArea(maxArea), lbl: 'حداکثر متراژ قابل خرید' },
                items: [
                    { val: formatToman(budget), lbl: 'بودجه' },
                    { val: formatM(ppsM), lbl: 'قیمت هر متر' },
                ],
                copy: `با بودجه ${formatToman(budget)} و ${formatM(ppsM)}/متر → حداکثر ${formatArea(maxArea)}`,
            };
        }
        if (hasArea) {
            const reqPps = Math.round(budget / area / 1_000_000 * 10) / 10;
            return {
                hero: { val: formatM(reqPps), lbl: 'قیمت متر مجاز' },
                items: [
                    { val: formatToman(budget), lbl: 'بودجه' },
                    { val: formatArea(area), lbl: 'متراژ' },
                ],
                copy: `برای ${formatArea(area)} با بودجه ${formatToman(budget)} → ${formatM(reqPps)}/متر`,
            };
        }
        return null;
    }

    function calcPricing(area, adjustmentPct) {
        if (!marketSnapshot || !marketSnapshot.median_pps) return null;
        if (!area || area <= 0) return null;
        const base = marketSnapshot.median_pps;
        const adj = 1 + (adjustmentPct || 0) / 100;
        const suggestedPps = Math.round(base * adj);
        const total = Math.round(suggestedPps * area);
        const ppsM = ppsToMillion(suggestedPps);
        const baseM = ppsToMillion(base);
        return {
            hero: { val: formatToman(total), lbl: 'قیمت پیشنهادی' },
            items: [
                { val: formatM(ppsM), lbl: 'قیمت هر متر' },
                { val: formatArea(area), lbl: 'متراژ' },
                { val: formatM(baseM), lbl: 'میانه بازار' },
            ],
            copy: `پیشنهاد: ${formatToman(total)} (${formatM(ppsM)}/متر × ${formatArea(area)})`,
        };
    }

    function calcCompare(isRent, rate) {
        const labelA = document.getElementById('tbxCmpALabel')?.value.trim() || 'آگهی الف';
        const labelB = document.getElementById('tbxCmpBLabel')?.value.trim() || 'آگهی ب';
        const areaA = parseNum(document.getElementById('tbxCmpAArea'));
        const areaB = parseNum(document.getElementById('tbxCmpBArea'));
        if (!areaA || !areaB) return null;

        let perA, perB, totalA, totalB;
        if (isRent) {
            const depA = parseIntNum(document.getElementById('tbxCmpADeposit')) || 0;
            const rentA = parseIntNum(document.getElementById('tbxCmpARent')) || 0;
            const depB = parseIntNum(document.getElementById('tbxCmpBDeposit')) || 0;
            const rentB = parseIntNum(document.getElementById('tbxCmpBRent')) || 0;
            totalA = fullDepositEquiv(depA, rentA, rate);
            totalB = fullDepositEquiv(depB, rentB, rate);
            if (!totalA || !totalB) return null;
            perA = Math.round(totalA / areaA);
            perB = Math.round(totalB / areaB);
        } else {
            totalA = parseIntNum(document.getElementById('tbxCmpAPrice'));
            totalB = parseIntNum(document.getElementById('tbxCmpBPrice'));
            if (!totalA || !totalB) return null;
            perA = Math.round(totalA / areaA);
            perB = Math.round(totalB / areaB);
        }

        const diffPct = Math.round((perB - perA) / perA * 1000) / 10;
        let winner, verdict;
        if (diffPct < -1) {
            winner = 'b';
            verdict = `${labelB} ارزان‌تر است`;
        } else if (diffPct > 1) {
            winner = 'a';
            verdict = `${labelA} ارزان‌تر است`;
        } else {
            winner = 'tie';
            verdict = 'تقریباً برابر';
        }

        const metricLbl = isRent ? 'رهن کامل/متر' : 'قیمت/متر';
        return {
            hero: { val: verdict, lbl: 'نتیجه مقایسه' },
            items: [
                { val: formatM(ppsToMillion(perA)), lbl: `${labelA} — ${metricLbl}`, winner: winner === 'a' },
                { val: formatM(ppsToMillion(perB)), lbl: `${labelB} — ${metricLbl}`, winner: winner === 'b' },
                { val: formatPct(diffPct), lbl: 'اختلاف (ب نسبت به الف)' },
                { val: formatToman(totalA), lbl: `${labelA} — کل` },
                { val: formatToman(totalB), lbl: `${labelB} — کل` },
            ],
            copy: `${verdict} | الف: ${formatM(ppsToMillion(perA))}/متر | ب: ${formatM(ppsToMillion(perB))}/متر`,
            winner,
        };
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

    function renderHero(container, hero, copyText, extraClass) {
        container.innerHTML = `
            <div class="ws-tbx-result-live">
                <div class="ws-tbx-result-hero ${extraClass || ''}">
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
            <div class="ws-tbx-result-item ${it.winner ? 'is-winner' : ''}">
                <span class="ws-tbx-result-item-val">${it.val}</span>
                <span class="ws-tbx-result-item-lbl">${it.lbl}</span>
            </div>`).join('');
        const heroClass = data.verdictClass ? `ws-tbx-result-hero--${data.verdictClass}` : '';
        container.innerHTML = `
            <div class="ws-tbx-result-live">
                <div class="ws-tbx-result-hero ${heroClass}">
                    <span class="ws-tbx-result-hero-val">${data.hero.val}</span>
                    <span class="ws-tbx-result-hero-lbl">${data.hero.lbl}</span>
                </div>
                ${itemsHtml ? `<div class="ws-tbx-result-grid ws-tbx-result-grid--flex">${itemsHtml}</div>` : ''}
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

    function switchTool(tool) {
        if (!TOOL_KEYS.includes(tool)) tool = TOOL_KEYS[0];
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

    function getDefaultRate() {
        return marketSnapshot?.ratio || 30;
    }

    function applyDefaultRates() {
        const rate = getDefaultRate();
        ['tbxMixRate', 'tbxRate', 'tbxCmpRate'].forEach(id => {
            const el = document.getElementById(id);
            if (el && !el.dataset.userEdited) el.value = rate;
        });
    }

    function updateMixed() {
        const container = document.getElementById('tbxMixedResult');
        if (!container) return;
        const deposit = parseIntNum(document.getElementById('tbxMixDeposit'));
        const rent = parseIntNum(document.getElementById('tbxMixRent'));
        const rate = parseNum(document.getElementById('tbxMixRate')) || getDefaultRate();
        if (!deposit && !rent) {
            renderEmpty(container, 'fa-layer-group', 'ودیعه یا اجاره را وارد کنید');
            return;
        }
        const r = calcMixed(deposit, rent, rate);
        if (!r) {
            renderEmpty(container, 'fa-circle-exclamation', 'مقادیر نامعتبر');
            return;
        }
        renderGrid(container, r);
    }

    function updateDeposit() {
        const container = document.getElementById('tbxDepositResult');
        if (!container) return;
        const deposit = parseIntNum(document.getElementById('tbxFullDeposit'));
        const rent = parseIntNum(document.getElementById('tbxFullRent'));
        const rate = parseNum(document.getElementById('tbxRate')) || getDefaultRate();
        if (deposit && rent) {
            renderEmpty(container, 'fa-circle-exclamation', 'فقط یکی از ودیعه یا اجاره را وارد کنید');
            return;
        }
        const r = calcDeposit(deposit, rent, rate);
        if (!r) {
            renderEmpty(container, 'fa-calculator', 'مقدار را وارد کنید');
            return;
        }
        renderHero(container, { val: formatToman(r.value), lbl: r.label }, formatToman(r.value));
    }

    function getCompareMode() {
        const active = document.querySelector('.ws-tbx-mode-btn.is-active[data-compare-mode]');
        return active?.dataset.compareMode === 'rent';
    }

    function updateCompareModeUI() {
        const isRent = getCompareMode();
        document.querySelectorAll('.ws-tbx-cmp-sale').forEach(el => { el.hidden = isRent; });
        document.querySelectorAll('.ws-tbx-cmp-rent').forEach(el => { el.hidden = !isRent; });
        const rateWrap = document.querySelector('.ws-tbx-cmp-rate-wrap');
        if (rateWrap) rateWrap.hidden = !isRent;
    }

    function updateCompare() {
        const container = document.getElementById('tbxCompareResult');
        if (!container) return;
        const isRent = getCompareMode();
        const rate = parseNum(document.getElementById('tbxCmpRate')) || getDefaultRate();
        const r = calcCompare(isRent, rate);
        if (!r) {
            renderEmpty(container, 'fa-balance-scale', 'اطلاعات هر دو آگهی را کامل کنید');
            return;
        }
        renderGrid(container, r);
    }

    function updateArea() {
        const container = document.getElementById('tbxAreaResult');
        if (!container) return;
        const pps = parseNum(document.getElementById('tbxPps'));
        const area = parseNum(document.getElementById('tbxArea'));
        const total = parseIntNum(document.getElementById('tbxTotal'));
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

    function updateDiscount() {
        const container = document.getElementById('tbxDiscountResult');
        if (!container) return;
        const price = parseIntNum(document.getElementById('tbxListPrice'));
        const pct = parseNum(document.getElementById('tbxDiscountPct')) ?? 0;
        if (!price) {
            renderEmpty(container, 'fa-tags', 'قیمت آگهی را وارد کنید');
            return;
        }
        renderGrid(container, calcDiscount(price, pct));
    }

    function updateCommission() {
        const container = document.getElementById('tbxCommissionResult');
        if (!container) return;
        const price = parseIntNum(document.getElementById('tbxPrice'));
        const buyerPct = parseNum(document.getElementById('tbxBuyerPct')) ?? 1;
        const sellerPct = parseNum(document.getElementById('tbxSellerPct')) ?? 1;
        if (!price) {
            renderEmpty(container, 'fa-percent', 'قیمت معامله را وارد کنید');
            return;
        }
        renderGrid(container, calcCommission(price, buyerPct, sellerPct));
    }

    function updateRentCommission() {
        const container = document.getElementById('tbxRentCommissionResult');
        if (!container) return;
        const rent = parseIntNum(document.getElementById('tbxRentCommRent'));
        const tenant = parseNum(document.getElementById('tbxTenantShare')) ?? 50;
        const landlord = parseNum(document.getElementById('tbxLandlordShare')) ?? 50;
        if (!rent) {
            renderEmpty(container, 'fa-key', 'اجاره ماهانه را وارد کنید');
            return;
        }
        renderGrid(container, calcRentCommission(rent, tenant, landlord));
    }

    function updateBudget() {
        const container = document.getElementById('tbxBudgetResult');
        if (!container) return;
        const budget = parseIntNum(document.getElementById('tbxBudget'));
        const pps = parseNum(document.getElementById('tbxBudgetPps'));
        const area = parseNum(document.getElementById('tbxBudgetArea'));
        if (!budget) {
            renderEmpty(container, 'fa-wallet', 'بودجه مشتری را وارد کنید');
            return;
        }
        if (!pps && !area) {
            renderEmpty(container, 'fa-wallet', 'قیمت متر یا متراژ را هم وارد کنید');
            return;
        }
        const r = calcBudget(budget, pps, area);
        if (!r) {
            renderEmpty(container, 'fa-circle-exclamation', 'ورودی نامعتبر');
            return;
        }
        renderGrid(container, r);
    }

    function updatePricing() {
        const container = document.getElementById('tbxPricingResult');
        if (!container) return;
        if (!marketSnapshot?.median_pps) {
            renderEmpty(container, 'fa-upload', 'فایل داده آپلود کنید تا قیمت‌گذاری هوشمند فعال شود');
            return;
        }
        const area = parseNum(document.getElementById('tbxPricingArea'));
        const adj = parseNum(document.getElementById('tbxPricingAdj')) ?? 0;
        if (!area) {
            renderEmpty(container, 'fa-wand-magic-sparkles', 'متراژ ملک را وارد کنید');
            return;
        }
        renderGrid(container, calcPricing(area, adj));
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

        marketSnapshot = loadMarket();
        applyDefaultRates();

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
                if (rateEl) rateEl.value = btn.dataset.rate;
                updateDeposit();
            });
        });

        document.querySelectorAll('.ws-tbx-preset[data-mix-rate]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-preset[data-mix-rate]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                const el = document.getElementById('tbxMixRate');
                if (el) el.value = btn.dataset.mixRate;
                updateMixed();
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

        document.querySelectorAll('.ws-tbx-preset[data-discount]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-preset[data-discount]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                const el = document.getElementById('tbxDiscountPct');
                if (el) el.value = btn.dataset.discount;
                updateDiscount();
            });
        });

        document.querySelectorAll('.ws-tbx-preset[data-rent-comm]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-preset[data-rent-comm]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                const [t, l] = btn.dataset.rentComm.split(',');
                const tenantEl = document.getElementById('tbxTenantShare');
                const landlordEl = document.getElementById('tbxLandlordShare');
                if (tenantEl) tenantEl.value = t;
                if (landlordEl) landlordEl.value = l;
                updateRentCommission();
            });
        });

        document.querySelectorAll('.ws-tbx-preset[data-pricing-adj]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-preset[data-pricing-adj]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                const el = document.getElementById('tbxPricingAdj');
                if (el) el.value = btn.dataset.pricingAdj;
                updatePricing();
            });
        });

        document.querySelectorAll('.ws-tbx-mode-btn[data-compare-mode]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ws-tbx-mode-btn[data-compare-mode]').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                updateCompareModeUI();
                updateCompare();
            });
        });

        document.querySelectorAll('[data-budget-pps]').forEach(btn => {
            btn.addEventListener('click', () => {
                const pps = parseFloat(btn.dataset.budgetPps);
                const el = document.getElementById('tbxBudgetPps');
                if (el && pps) {
                    el.value = Math.round(pps / 1_000_000 * 10) / 10;
                    updateBudget();
                }
            });
        });

        bindCalcInputs(['tbxMixDeposit', 'tbxMixRent', 'tbxMixRate'], updateMixed);
        bindCalcInputs(['tbxFullDeposit', 'tbxFullRent', 'tbxRate'], updateDeposit);
        bindCalcInputs([
            'tbxCmpAPrice', 'tbxCmpBPrice', 'tbxCmpADeposit', 'tbxCmpARent',
            'tbxCmpBDeposit', 'tbxCmpBRent', 'tbxCmpAArea', 'tbxCmpBArea', 'tbxCmpRate',
        ], updateCompare);
        document.getElementById('tbxCmpALabel')?.addEventListener('input', updateCompare);
        document.getElementById('tbxCmpBLabel')?.addEventListener('input', updateCompare);
        bindCalcInputs(['tbxPps', 'tbxArea', 'tbxTotal'], updateArea);
        bindCalcInputs(['tbxListPrice', 'tbxDiscountPct'], updateDiscount);
        bindCalcInputs(['tbxPrice', 'tbxBuyerPct', 'tbxSellerPct'], updateCommission);
        bindCalcInputs(['tbxRentCommRent', 'tbxTenantShare', 'tbxLandlordShare'], updateRentCommission);
        bindCalcInputs(['tbxBudget', 'tbxBudgetPps', 'tbxBudgetArea'], updateBudget);
        bindCalcInputs(['tbxPricingArea'], updatePricing);

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
            if (n >= 1 && n <= TOOL_KEYS.length) switchTool(TOOL_KEYS[n - 1]);
        });

        const params = new URLSearchParams(window.location.search);
        const initial = params.get('tool');
        if (initial && TOOL_KEYS.includes(initial)) {
            switchTool(initial);
        }

        updateCompareModeUI();
    }

    document.addEventListener('DOMContentLoaded', initToolbox);
})();
