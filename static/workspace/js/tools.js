/**
 * ابزارهای هوشمند — جعبه ابزار مشاور
 * محاسبه آنی سمت کلاینت
 */
(function () {
    'use strict';

    const TOOL_KEYS = [
        'mixed', 'deposit', 'compare', 'area', 'discount',
        'commission', 'rent_commission', 'budget', 'pricing',
        'evaluate', 'opportunities', 'neighborhood', 'nearby_access',
    ];

    const TOOL_GROUP_MAP = {
        mixed: 'price', deposit: 'price', area: 'price',
        discount: 'negotiate', commission: 'negotiate', rent_commission: 'negotiate',
        compare: 'client', budget: 'client',
        pricing: 'market', evaluate: 'market', opportunities: 'market', neighborhood: 'market',
        nearby_access: 'location',
    };

    let marketSnapshot = null;
    let marketSnapshots = {};
    let budgetMatchCache = null;

    function loadJsonScript(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        try {
            return JSON.parse(el.textContent || 'null');
        } catch (e) {
            return null;
        }
    }

    function loadMarket() {
        const data = loadJsonScript('wsTbxMarket');
        return data && typeof data === 'object' ? data : null;
    }

    function loadAllMarkets() {
        const data = loadJsonScript('wsTbxMarkets');
        return data && typeof data === 'object' ? data : {};
    }

    function currentToolKey() {
        const active = document.querySelector('.ws-tbx-panel.is-active');
        return active?.dataset.toolPanel || TOOL_KEYS[0];
    }

    function buildToolsUrl(tool) {
        const params = new URLSearchParams();
        if (tool) params.set('tool', tool);
        const ds = document.getElementById('wsTbxDataset')?.value;
        if (ds) params.set('dataset', ds);
        const q = params.toString();
        return q ? '?' + q : window.location.pathname;
    }

    function parseNum(el) {
        if (!el) return null;
        let raw;
        if (typeof readFormattedInput === 'function' && el.type !== 'range' && el.type !== 'hidden') {
            raw = readFormattedInput(el);
        } else {
            raw = el.value;
        }
        if (raw == null || raw === '') return null;
        const s = String(raw).trim().replace(/,/g, '');
        const negative = s.startsWith('-');
        const cleaned = s.replace(/[^\d.]/g, '');
        if (!cleaned) return null;
        const n = parseFloat((negative ? '-' : '') + cleaned);
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

    function formatHumanMoney(n, perSqm) {
        const v = Number(n) || 0;
        if (!v) return '';
        const suffix = perSqm ? ' /متر' : ' تومان';
        if (v >= 1_000_000_000) {
            const b = (v / 1_000_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 1 });
            return `${b} میلیارد${suffix}`;
        }
        if (v >= 1_000_000) {
            const m = (v / 1_000_000).toLocaleString('fa-IR', { maximumFractionDigits: 0 });
            return `${m} میلیون${suffix}`;
        }
        return `${v.toLocaleString('fa-IR')}${suffix}`;
    }

    function pricingConfidenceLabel(sampleCount) {
        const n = Number(sampleCount) || 0;
        if (n >= 30) return { label: 'بالا', tone: 'great' };
        if (n >= 10) return { label: 'متوسط', tone: 'neutral' };
        if (n >= 3) return { label: 'پایین', tone: 'warn' };
        return { label: 'بسیار پایین', tone: 'bad' };
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
        const rateRows = [20, 25, 30].map(rn => ({
            rate: rn,
            fullDep: fullDepositEquiv(d, r, rn),
            active: rn === rate,
        }));
        return {
            hero: { val: formatToman(fullDep), lbl: 'رهن کامل معادل' },
            interpret: `با نرخ ${rate.toLocaleString('fa-IR')}، ${formatToman(d)} ودیعه + ${formatToman(r)} اجاره معادل حدود ${formatHumanMoney(fullDep) || formatToman(fullDep)} رهن کامل است.`,
            items: [
                { val: formatToman(fullRent), lbl: 'اجاره کامل معادل' },
                { val: formatToman(d), lbl: 'ودیعه واردشده' },
                { val: formatToman(r), lbl: 'اجاره واردشده' },
            ],
            rateTable: rateRows,
            copy: `رهن کامل معادل: ${formatToman(fullDep)} (${formatToman(d)} ودیعه + ${formatToman(r)} اجاره، نرخ ${rate})`,
            actions: marketSnapshot?.supports_pricing
                ? [{ type: 'tool', tool: 'pricing', label: 'قیمت‌گذاری هوشمند', icon: 'fa-wand-magic-sparkles' }]
                : [],
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
        const startPct = Math.max(0, pct - 2);
        const startPrice = Math.round(listPrice * (1 - startPct / 100));
        return {
            hero: { val: formatToman(finalPrice), lbl: `پیشنهاد با ${pct}٪ تخفیف` },
            interpret: pct > 0
                ? `با ${pct}٪ تخفیف، ${formatHumanMoney(savings) || formatToman(savings)} از قیمت آگهی کم می‌شود.`
                : 'قیمت آگهی بدون تخفیف.',
            items: [
                { val: formatToman(listPrice), lbl: 'قیمت آگهی' },
                { val: formatToman(savings), lbl: `مبلغ تخفیف (${pct}٪)` },
            ],
            scenarios: [
                { label: 'شروع پیشنهاد', val: formatToman(startPrice) },
                { label: 'هدف مذاکره', val: formatToman(finalPrice) },
                { label: 'قیمت آگهی', val: formatToman(listPrice) },
            ],
            copy: `قیمت آگهی: ${formatToman(listPrice)} | تخفیف ${pct}٪ | پیشنهاد: ${formatToman(finalPrice)}`,
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

    function formatAdjLabel(pct) {
        const v = Math.round(pct * 10) / 10;
        if (v === 0) return 'میانه بازار (۰٪)';
        if (v > 0) return `${v.toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪ بالای بازار`;
        return `${Math.abs(v).toLocaleString('fa-IR', { maximumFractionDigits: 1 })}٪ زیر بازار`;
    }

    function calcPricing(area, adjustmentPct) {
        if (!marketSnapshot || !marketSnapshot.median_pps) return null;
        if (!area || area <= 0) return null;
        const base = marketSnapshot.median_pps;
        const pct = adjustmentPct || 0;
        const adj = 1 + pct / 100;
        const suggestedPps = Math.round(base * adj);
        const total = Math.round(suggestedPps * area);
        const ppsM = ppsToMillion(suggestedPps);
        const p25 = marketSnapshot.pps_p25 || Math.round(base * 0.92);
        const p75 = marketSnapshot.pps_p75 || Math.round(base * 1.08);
        const bandLow = Math.round(p25 * adj * area);
        const bandHigh = Math.round(p75 * adj * area);
        const isRentMetric = marketSnapshot.is_rent && marketSnapshot.pps_metric === 'full_deposit_per_sqm';
        const ppsLabel = isRentMetric ? 'رهن کامل/متر' : 'قیمت هر متر';
        const totalLabel = isRentMetric ? 'رهن کامل پیشنهادی' : 'قیمت پیشنهادی';
        const posPct = bandHigh > bandLow
            ? Math.max(4, Math.min(96, ((total - bandLow) / (bandHigh - bandLow)) * 100))
            : 50;
        const sampleCount = marketSnapshot.row_count || 0;
        const conf = pricingConfidenceLabel(sampleCount);
        return {
            hero: { val: formatToman(total), lbl: totalLabel },
            interpret: `بر اساس ${sampleCount.toLocaleString('fa-IR')} آگهی فایل «${marketSnapshot.dataset_name || ''}» — اطمینان تحلیل: ${conf.label}`,
            items: [
                { val: formatM(ppsM), lbl: ppsLabel },
                { val: formatAdjLabel(pct), lbl: 'تنظیم بازار' },
                { val: formatM(ppsToMillion(p25)), lbl: 'P25 بازار' },
                { val: formatM(ppsToMillion(base)), lbl: 'میانه بازار' },
                { val: formatM(ppsToMillion(p75)), lbl: 'P75 بازار' },
                { val: formatArea(area), lbl: 'متراژ' },
            ],
            band: {
                low: bandLow,
                high: bandHigh,
                lowFmt: formatToman(bandLow),
                highFmt: formatToman(bandHigh),
                posPct,
            },
            confidence: conf,
            copy: `پیشنهاد: ${formatToman(total)} (${formatM(ppsM)}/متر) | باند بازار: ${formatToman(bandLow)} – ${formatToman(bandHigh)} | ${sampleCount} نمونه`,
            actions: [
                { type: 'tool', tool: 'compare', label: 'مقایسه با آگهی دیگر', icon: 'fa-balance-scale' },
                { type: 'tool', tool: 'neighborhood', label: 'بازه قیمت محله', icon: 'fa-map-marker-alt' },
            ],
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
        const cheaperPct = Math.abs(diffPct);
        const winnerLabel = winner === 'b' ? labelB : (winner === 'a' ? labelA : '—');
        return {
            hero: { val: winner === 'tie' ? 'تقریباً برابر' : winnerLabel, lbl: winner === 'tie' ? 'نتیجه مقایسه' : 'انتخاب اقتصادی‌تر' },
            interpret: winner === 'tie'
                ? 'هر دو ملک از نظر قیمت هر متر تقریباً برابرند.'
                : `${winnerLabel} حدود ${cheaperPct.toLocaleString('fa-IR')}٪ ارزان‌تر به ازای هر متر است.`,
            compareTable: {
                headers: ['', labelA, labelB],
                rows: [
                    ['قیمت کل', formatToman(totalA), formatToman(totalB)],
                    ['متراژ', formatArea(areaA), formatArea(areaB)],
                    [metricLbl, formatM(ppsToMillion(perA)), formatM(ppsToMillion(perB))],
                    ['اختلاف', '—', formatPct(diffPct)],
                ],
            },
            items: [
                { val: formatM(ppsToMillion(perA)), lbl: `${labelA} — ${metricLbl}`, winner: winner === 'a' },
                { val: formatM(ppsToMillion(perB)), lbl: `${labelB} — ${metricLbl}`, winner: winner === 'b' },
            ],
            copy: `${verdict} | الف: ${formatM(ppsToMillion(perA))}/متر | ب: ${formatM(ppsToMillion(perB))}/متر`,
            winner,
            actions: marketSnapshot?.dataset_id
                ? [{ type: 'tool', tool: 'evaluate', label: 'ارزیابی با بازار', icon: 'fa-crosshairs' }]
                : [],
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

    function bindResultActions(container, data) {
        container.querySelectorAll('[data-action-tool]').forEach(btn => {
            btn.addEventListener('click', () => switchTool(btn.dataset.actionTool));
        });
        container.querySelectorAll('[data-action-href]').forEach(link => {
            link.addEventListener('click', e => {
                if (link.dataset.actionHref) window.location.href = link.dataset.actionHref;
            });
        });
        bindCopy(container.querySelector('.ws-tbx-copy-btn'));
    }

    function renderResult(container, data) {
        if (!data) return;
        const heroClass = data.verdictClass ? `ws-tbx-result-hero--${data.verdictClass}` : '';
        const itemsHtml = (data.items || []).map(it => `
            <div class="ws-tbx-result-item ${it.winner ? 'is-winner' : ''}">
                <span class="ws-tbx-result-item-val">${it.val}</span>
                <span class="ws-tbx-result-item-lbl">${it.lbl}</span>
            </div>`).join('');
        const bandHtml = data.band ? `
            <div class="ws-mkt-band">
                <div class="ws-mkt-band-labels">
                    <span>${data.band.lowFmt}</span><span>محدوده منطقی بازار</span><span>${data.band.highFmt}</span>
                </div>
                <div class="ws-mkt-band-track">
                    <div class="ws-mkt-band-fill"></div>
                    <div class="ws-mkt-band-marker" style="inset-inline-start: ${data.band.posPct}%"></div>
                </div>
            </div>` : '';
        const rateTableHtml = data.rateTable ? `
            <table class="ws-tbx-rate-table">
                <thead><tr><th>نرخ</th><th>رهن کامل</th></tr></thead>
                <tbody>${data.rateTable.map(row => `
                    <tr class="${row.active ? 'is-active' : ''}">
                        <td>${row.rate.toLocaleString('fa-IR')}</td>
                        <td>${formatHumanMoney(row.fullDep) || formatToman(row.fullDep)}</td>
                    </tr>`).join('')}</tbody>
            </table>` : '';
        const compareTableHtml = data.compareTable ? `
            <table class="ws-tbx-compare-table">
                <thead><tr>${data.compareTable.headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
                <tbody>${data.compareTable.rows.map(row => `
                    <tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
            </table>` : '';
        const scenariosHtml = data.scenarios ? `
            <div class="ws-tbx-scenarios">
                <span class="ws-tbx-scenarios-title">سناریوهای مذاکره</span>
                ${data.scenarios.map(s => `
                    <div class="ws-tbx-scenario-row">
                        <span>${s.label}</span><strong>${s.val}</strong>
                    </div>`).join('')}
            </div>` : '';
        const budgetMatchHtml = data.budgetMatch ? `
            <div class="ws-tbx-budget-match">
                <strong>${data.budgetMatch.count.toLocaleString('fa-IR')} فایل متناسب با بودجه</strong>
                ${data.budgetMatch.filter_url ? `<a href="${data.budgetMatch.filter_url}" class="ws-mkt-link-btn" data-action-href="${data.budgetMatch.filter_url}"><i class="fas fa-folder-open"></i> مشاهده فایل‌های مناسب</a>` : ''}
            </div>` : '';
        const confHtml = data.confidence ? `
            <span class="ws-tbx-confidence ws-tbx-confidence--${data.confidence.tone}">اطمینان تحلیل: ${data.confidence.label}</span>` : '';
        const actionsHtml = (data.actions || []).map(a => {
            if (a.href) {
                return `<a href="${a.href}" class="ws-mkt-link-btn" data-action-href="${a.href}"><i class="fas ${a.icon || 'fa-arrow-left'}"></i> ${a.label}</a>`;
            }
            return `<button type="button" class="ws-mkt-link-btn" data-action-tool="${a.tool}"><i class="fas ${a.icon || 'fa-arrow-left'}"></i> ${a.label}</button>`;
        }).join('');
        container.innerHTML = `
            <div class="ws-tbx-result-live">
                <div class="ws-tbx-result-hero ${heroClass}">
                    <span class="ws-tbx-result-hero-val">${data.hero.val}</span>
                    <span class="ws-tbx-result-hero-lbl">${data.hero.lbl}</span>
                </div>
                ${data.interpret ? `<p class="ws-tbx-result-interpret">${data.interpret}</p>` : ''}
                ${confHtml}
                ${bandHtml}
                ${rateTableHtml}
                ${compareTableHtml}
                ${scenariosHtml}
                ${budgetMatchHtml}
                ${itemsHtml ? `<div class="ws-tbx-result-grid ws-tbx-result-grid--flex">${itemsHtml}</div>` : ''}
                <div class="ws-tbx-result-actions">
                    ${actionsHtml}
                    <button type="button" class="ws-tbx-copy-btn" data-copy="${data.copy || data.hero.val}">
                        <i class="fas fa-copy" aria-hidden="true"></i> کپی نتیجه
                    </button>
                </div>
            </div>`;
        bindResultActions(container, data);
    }

    function renderHero(container, hero, copyText, extraClass, extra) {
        renderResult(container, {
            hero,
            copy: copyText || hero.val,
            verdictClass: extraClass,
            interpret: extra?.interpret || '',
            actions: extra?.actions || [],
        });
    }

    function renderGrid(container, data) {
        renderResult(container, data);
    }

    function renderEmpty(container, icon, text) {
        container.innerHTML = `
            <div class="ws-tbx-result-empty">
                <i class="fas ${icon}" aria-hidden="true"></i>
                <p>${text}</p>
            </div>`;
    }

    function filterNavItems(query) {
        const q = query.trim().toLowerCase();
        document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
            const text = btn.textContent.toLowerCase();
            btn.classList.toggle('is-hidden', q.length > 0 && !text.includes(q));
        });
        document.querySelectorAll('.ws-tbx-nav-group').forEach(group => {
            const visible = group.querySelectorAll('.ws-tbx-nav-item:not(.is-hidden)').length;
            group.classList.toggle('is-empty', q.length > 0 && visible === 0);
        });
    }

    function switchTool(tool) {
        if (!TOOL_KEYS.includes(tool)) tool = TOOL_KEYS[0];
        document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
            const active = btn.dataset.tool === tool;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
            if (active) {
                btn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        });
        document.querySelectorAll('.ws-tbx-panel').forEach(panel => {
            const active = panel.dataset.toolPanel === tool;
            panel.classList.toggle('is-active', active);
            panel.hidden = !active;
        });
        const groupKey = TOOL_GROUP_MAP[tool];
        if (groupKey) openNavGroup(groupKey);
        if (tool === 'nearby_access' && typeof window.wsNearbyAccessOnShow === 'function') {
            window.wsNearbyAccessOnShow();
        }
        try { history.replaceState(null, '', buildToolsUrl(tool)); } catch (e) {}
    }

    function openNavGroup(groupKey) {
        document.querySelectorAll('.ws-tbx-nav-group[data-tool-group]').forEach(group => {
            const isTarget = group.dataset.toolGroup === groupKey;
            group.classList.toggle('is-open', isTarget);
            const toggle = group.querySelector('.ws-tbx-nav-group-toggle');
            const items = group.querySelector('.ws-tbx-nav-group-items');
            if (toggle) toggle.setAttribute('aria-expanded', isTarget ? 'true' : 'false');
            if (items) items.hidden = !isTarget;
        });
    }

    function initNavAccordion() {
        document.querySelectorAll('.ws-tbx-nav-group-toggle').forEach(toggle => {
            toggle.addEventListener('click', () => {
                const group = toggle.closest('.ws-tbx-nav-group');
                const isOpen = group.classList.contains('is-open');
                document.querySelectorAll('.ws-tbx-nav-group[data-tool-group]').forEach(g => {
                    g.classList.remove('is-open');
                    g.querySelector('.ws-tbx-nav-group-toggle')?.setAttribute('aria-expanded', 'false');
                    const items = g.querySelector('.ws-tbx-nav-group-items');
                    if (items) items.hidden = true;
                });
                if (!isOpen) {
                    group.classList.add('is-open');
                    toggle.setAttribute('aria-expanded', 'true');
                    const items = group.querySelector('.ws-tbx-nav-group-items');
                    if (items) items.hidden = false;
                }
            });
        });
    }

    function truncateName(name, max) {
        if (!name) return '';
        return name.length > max ? name.slice(0, max) + '…' : name;
    }

    function updateDatasetUI() {
        const snap = marketSnapshot;
        const meta = document.getElementById('wsTbxDatasetMeta');
        if (meta) {
            if (snap) {
                meta.innerHTML = `
                    <span class="ws-tbx-dataset-chip">${snap.transaction_type || '—'}</span>
                    <span class="ws-tbx-dataset-chip">${snap.row_count} آگهی تحلیل‌شده</span>
                    <span class="ws-tbx-dataset-chip">نرخ ${snap.ratio || 30}:۱</span>`;
            } else {
                meta.innerHTML = '';
            }
        }

        const ctxName = document.getElementById('tbxContextName');
        const ctxMeta = document.getElementById('tbxContextMeta');
        if (ctxName) ctxName.textContent = snap?.dataset_name || '—';
        if (ctxMeta) {
            ctxMeta.textContent = snap
                ? `${snap.transaction_type || '—'} · ${snap.row_count} آگهی`
                : '';
        }

        const analyzeUrl = snap?.analyze_url || '#';
        const analyzeName = truncateName(snap?.dataset_name || '', 28);
        ['tbxAnalyzeLink', 'tbxRailAnalyzeLink'].forEach(id => {
            const link = document.getElementById(id);
            if (link && snap) link.href = analyzeUrl;
        });
        const railName = document.getElementById('tbxRailAnalyzeName');
        if (railName) railName.textContent = analyzeName;

        const banner = document.getElementById('tbxMarketBanner');
        const bannerText = document.getElementById('tbxMarketBannerText');
        if (banner) banner.hidden = !snap?.supports_pricing;
        if (bannerText && snap) {
            bannerText.textContent = `${truncateName(snap.dataset_name, 32)} — ${snap.row_count} آگهی`;
        }

        const emptyMsg = document.getElementById('tbxPricingEmptyMsg');
        if (emptyMsg) {
            if (!snap) {
                emptyMsg.textContent = 'ابتدا یک فایل داده آپلود کنید';
            } else if (!snap.supports_pricing) {
                emptyMsg.textContent = 'فایل انتخابی داده کافی برای قیمت‌گذاری ندارد';
            } else {
                emptyMsg.textContent = 'متراژ را وارد کنید';
            }
        }

        renderBudgetPreset();
    }

    function renderBudgetPreset() {
        const wrap = document.getElementById('tbxBudgetPpsPreset');
        if (!wrap) return;
        wrap.innerHTML = '';
        if (!marketSnapshot?.median_pps) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ws-tbx-inline-preset';
        btn.textContent = marketSnapshot.is_rent ? 'میانه رهن/متر' : 'میانه بازار';
        btn.addEventListener('click', () => {
            const el = document.getElementById('tbxBudgetPps');
            if (el) {
                el.value = Math.round(marketSnapshot.median_pps / 1_000_000 * 10) / 10;
                updateBudget();
            }
        });
        wrap.appendChild(btn);
    }

    function selectDataset(id) {
        marketSnapshot = marketSnapshots[id] || null;
        budgetMatchCache = null;
        updateDatasetUI();
        applyDefaultRates(true);
        updatePricing();
        updateBudget();
        const root = document.getElementById('wsToolbox');
        if (root) root.dataset.datasetId = id;
        document.dispatchEvent(new CustomEvent('wsTbxDatasetChanged', { detail: { id, snapshot: marketSnapshot } }));
        try { history.replaceState(null, '', buildToolsUrl(currentToolKey())); } catch (e) {}
    }

    const STANDARD_RENT_RATE = 30;

    function getDefaultRate() {
        return STANDARD_RENT_RATE;
    }

    function applyDefaultRates(force) {
        const rate = getDefaultRate();
        ['tbxMixRate', 'tbxRate', 'tbxCmpRate'].forEach(id => {
            const el = document.getElementById(id);
            if (el && (force || !el.dataset.userEdited)) el.value = rate;
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
        const interpret = deposit
            ? `${formatHumanMoney(deposit) || formatToman(deposit)} رهن کامل با نرخ ${rate.toLocaleString('fa-IR')}، معادل حدود ${formatHumanMoney(r.value) || formatToman(r.value)} اجاره ماهانه است.`
            : `${formatHumanMoney(rent) || formatToman(rent)} اجاره با نرخ ${rate.toLocaleString('fa-IR')}، معادل حدود ${formatHumanMoney(r.value) || formatToman(r.value)} رهن کامل است.`;
        renderHero(
            container,
            { val: formatToman(r.value), lbl: r.label },
            `${r.label}: ${formatToman(r.value)}`,
            '',
            {
                interpret,
                actions: marketSnapshot?.supports_pricing
                    ? [{ type: 'tool', tool: 'pricing', label: 'قیمت‌گذاری هوشمند', icon: 'fa-wand-magic-sparkles' }]
                    : [],
            },
        );
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

    async function fetchBudgetMatch(budget) {
        const dsId = document.getElementById('wsTbxDataset')?.value;
        if (!dsId || !budget) return null;
        try {
            const res = await fetch(`/workspace/tools/api/${dsId}/evaluate/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
                        || (document.cookie.match(/csrftoken=([^;]+)/) || [])[1],
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ action: 'budget_match', budget, tolerance_pct: 10 }),
            });
            if (!res.ok) return null;
            return await res.json();
        } catch (e) {
            return null;
        }
    }

    async function updateBudget() {
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
        const match = await fetchBudgetMatch(budget);
        if (match && match.count > 0) {
            r.budgetMatch = match;
            r.actions = [
                { href: match.filter_url, label: 'مشاهده فایل‌های مناسب', icon: 'fa-folder-open' },
                { type: 'tool', tool: 'opportunities', label: 'فرصت‌های زیر بازار', icon: 'fa-gem' },
            ];
        }
        renderGrid(container, r);
    }

    function updateAdjSliderUI() {
        const slider = document.getElementById('tbxPricingAdj');
        const out = document.getElementById('tbxPricingAdjOut');
        if (!slider) return;
        const v = parseFloat(slider.value) || 0;
        const min = parseFloat(slider.min) || -20;
        const max = parseFloat(slider.max) || 20;
        const fill = ((v - min) / (max - min)) * 100;
        slider.style.setProperty('--adj-fill', `${fill}%`);
        slider.setAttribute('aria-valuenow', String(v));
        if (out) out.textContent = formatAdjLabel(v);
    }

    function syncPricingPresetsFromSlider() {
        const slider = document.getElementById('tbxPricingAdj');
        if (!slider) return;
        const v = parseFloat(slider.value) || 0;
        document.querySelectorAll('.ws-tbx-preset[data-pricing-adj]').forEach(btn => {
            const match = parseFloat(btn.dataset.pricingAdj) === v;
            btn.classList.toggle('is-active', match);
        });
    }

    function setPricingAdjustment(pct) {
        const slider = document.getElementById('tbxPricingAdj');
        if (slider) slider.value = String(pct);
        updateAdjSliderUI();
        syncPricingPresetsFromSlider();
        updatePricing();
    }

    function updatePricing() {
        const container = document.getElementById('tbxPricingResult');
        if (!container) return;
        if (!marketSnapshot?.supports_pricing) {
            renderEmpty(container, 'fa-wand-magic-sparkles', 'فایل انتخابی داده کافی برای قیمت‌گذاری ندارد');
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
        marketSnapshots = loadAllMarkets();
        applyDefaultRates(false);
        updateDatasetUI();

        const datasetSelect = document.getElementById('wsTbxDataset');
        if (datasetSelect) {
            datasetSelect.addEventListener('change', () => selectDataset(datasetSelect.value));
        }

        ['tbxMixRate', 'tbxRate', 'tbxCmpRate'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', () => { el.dataset.userEdited = '1'; });
        });

        document.querySelectorAll('.ws-tbx-nav-item').forEach(btn => {
            btn.addEventListener('click', () => switchTool(btn.dataset.tool));
        });

        document.querySelectorAll('.ws-tbx-quick-btn[data-quick-tool]').forEach(btn => {
            btn.addEventListener('click', () => switchTool(btn.dataset.quickTool));
        });

        initNavAccordion();
        openNavGroup(TOOL_GROUP_MAP.mixed);

        document.getElementById('tbxDepositSwap')?.addEventListener('click', () => {
            const depEl = document.getElementById('tbxFullDeposit');
            const rentEl = document.getElementById('tbxFullRent');
            if (!depEl || !rentEl) return;
            const dep = depEl.value;
            const rent = rentEl.value;
            if (dep && !rent) {
                rentEl.value = dep;
                depEl.value = '';
            } else if (rent && !dep) {
                depEl.value = rent;
                rentEl.value = '';
            }
            updateDeposit();
        });

        const search = document.getElementById('wsTbxSearch');
        if (search) {
            search.addEventListener('input', () => filterNavItems(search.value));
            search.addEventListener('keydown', e => {
                if (e.key === 'Escape') {
                    search.value = '';
                    filterNavItems('');
                    search.blur();
                }
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
            btn.addEventListener('click', () => setPricingAdjustment(parseFloat(btn.dataset.pricingAdj) || 0));
        });

        const pricingSlider = document.getElementById('tbxPricingAdj');
        if (pricingSlider) {
            pricingSlider.addEventListener('input', () => {
                updateAdjSliderUI();
                syncPricingPresetsFromSlider();
                updatePricing();
            });
            updateAdjSliderUI();
        }

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

        updateAdjSliderUI();

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
            if (e.key === '/' && !e.target.matches('input, textarea, select')) {
                e.preventDefault();
                document.getElementById('wsTbxSearch')?.focus();
                return;
            }
            if (e.target.matches('input, textarea, select')) return;
            const n = parseInt(e.key, 10);
            if (n >= 1 && n <= 9) switchTool(TOOL_KEYS[n - 1]);
        });

        const params = new URLSearchParams(window.location.search);
        const initial = params.get('tool');
        if (initial && TOOL_KEYS.includes(initial)) {
            switchTool(initial);
        } else {
            try { history.replaceState(null, '', buildToolsUrl(currentToolKey())); } catch (e) {}
        }

        updateCompareModeUI();
    }

    window.wsTbxSwitchTool = switchTool;

    document.addEventListener('DOMContentLoaded', initToolbox);
})();
