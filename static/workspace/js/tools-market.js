/**
 * ابزارهای بازار فاز ۱ — مبتنی بر فایل انتخابی
 */
(function () {
    'use strict';

    let toolkit = null;
    let datasetId = null;
    let selectedListingId = null;
    let searchTimer = null;

    function getDatasetId() {
        if (datasetId) return datasetId;
        const sel = document.getElementById('wsTbxDataset');
        if (sel?.value) return sel.value;
        return document.getElementById('wsToolbox')?.dataset?.datasetId || null;
    }

    function apiUrl(path) {
        const id = getDatasetId();
        if (!id) return null;
        return `/workspace/tools/api/${id}/${path}`;
    }

    async function fetchToolkit() {
        const url = apiUrl('toolkit/');
        if (!url) {
            toolkit = null;
            renderNoDataset();
            return;
        }
        const opps = document.getElementById('tbxOppsList');
        if (opps) {
            opps.innerHTML = '<div class="ws-mkt-loading"><i class="fas fa-spinner fa-spin"></i> در حال بارگذاری فرصت‌ها...</div>';
        }
        try {
            const res = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!res.ok) throw new Error('fetch failed');
            toolkit = await res.json();
            datasetId = getDatasetId();
            onToolkitLoaded();
        } catch (e) {
            toolkit = null;
            renderToolkitError();
        }
    }

    function getCsrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el?.value) return el.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    async function postEvaluate(body) {
        const url = apiUrl('evaluate/');
        if (!url) return null;
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'خطا');
        return data;
    }

    function parseNumEl(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        let raw;
        if (typeof readFormattedInput === 'function' && el.type !== 'range' && el.type !== 'hidden') {
            raw = readFormattedInput(el);
        } else if (typeof parseFormattedNumber === 'function') {
            raw = parseFormattedNumber(el.value);
        } else {
            raw = el.value.trim().replace(/,/g, '');
        }
        if (raw == null || raw === '') return null;
        const n = parseFloat(String(raw).replace(/,/g, ''));
        return isNaN(n) ? null : n;
    }

    function parseIntEl(id) {
        const n = parseNumEl(id);
        return n == null ? null : Math.round(n);
    }

    function toneClass(tone) {
        return `ws-mkt-tone--${tone || 'neutral'}`;
    }

    function renderEvaluateResult(data) {
        const el = document.getElementById('tbxEvaluateResult');
        if (!el) return;
        const score = data.score;
        const gaugePct = score == null ? 50 : Math.max(5, Math.min(95, 50 + score * 1.5));
        const p25 = data.p25;
        const p75 = data.p75;
        const actual = data.actual;
        let posPct = 50;
        if (p25 && p75 && actual && p75 > p25) {
            posPct = Math.max(4, Math.min(96, ((actual - p25) / (p75 - p25)) * 100));
        }
        el.innerHTML = `
            <div class="ws-mkt-eval-live ${toneClass(data.tone)}">
                <div class="ws-mkt-eval-verdict">
                    <span class="ws-mkt-eval-score">${data.score_fmt || '—'}</span>
                    <strong>${data.verdict}</strong>
                    <em>${data.scope || ''}</em>
                </div>
                <div class="ws-mkt-gauge">
                    <div class="ws-mkt-gauge-track">
                        <div class="ws-mkt-gauge-marker" style="inset-inline-start: ${gaugePct}%"></div>
                    </div>
                    <div class="ws-mkt-gauge-labels">
                        <span>زیر بازار</span><span>میانه</span><span>بالای بازار</span>
                    </div>
                </div>
                ${p25 && p75 ? `
                <div class="ws-mkt-band ws-mkt-band--compact">
                    <div class="ws-mkt-band-labels"><span>${data.p25_fmt}</span><span>باند P25–P75</span><span>${data.p75_fmt}</span></div>
                    <div class="ws-mkt-band-track">
                        <div class="ws-mkt-band-fill"></div>
                        <div class="ws-mkt-band-marker" style="inset-inline-start: ${posPct}%"></div>
                    </div>
                </div>` : ''}
                <div class="ws-tbx-result-grid ws-tbx-result-grid--flex">
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${data.actual_fmt}</span><span class="ws-tbx-result-item-lbl">قیمت آگهی</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${data.expected_fmt}</span><span class="ws-tbx-result-item-lbl">میانه هم‌رده</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${data.pps_actual_fmt || '—'}</span><span class="ws-tbx-result-item-lbl">هر متر</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${data.area_fmt || '—'}</span><span class="ws-tbx-result-item-lbl">متراژ</span></div>
                </div>
                ${data.negotiate_hint_fmt ? `<p class="ws-mkt-negotiate"><i class="fas fa-lightbulb" aria-hidden="true"></i> پیشنهاد مذاکره: <strong>${data.negotiate_hint_fmt}</strong></p>` : ''}
                <div class="ws-tbx-result-actions">
                    ${data.link ? `<a href="${data.link}" target="_blank" rel="noopener" class="ws-mkt-link-btn"><i class="fas fa-external-link-alt"></i> دیوار</a>` : ''}
                    <button type="button" class="ws-tbx-copy-btn" data-copy="${data.copy || ''}"><i class="fas fa-copy"></i> کپی نتیجه</button>
                </div>
            </div>`;
        const copyBtn = el.querySelector('.ws-tbx-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(copyBtn.dataset.copy).then(() => {
                    copyBtn.classList.add('is-copied');
                    copyBtn.innerHTML = '<i class="fas fa-check"></i> کپی شد';
                    setTimeout(() => {
                        copyBtn.classList.remove('is-copied');
                        copyBtn.innerHTML = '<i class="fas fa-copy"></i> کپی نتیجه';
                    }, 2000);
                });
            });
        }
    }

    function renderOpportunities() {
        const list = document.getElementById('tbxOppsList');
        const count = document.getElementById('tbxOppsCount');
        if (!list) return;
        const opps = toolkit?.opportunities || [];
        if (count) count.textContent = opps.length ? `${opps.length} فرصت` : 'فرصتی یافت نشد';
        if (!opps.length) {
            list.innerHTML = '<div class="ws-mkt-empty"><i class="fas fa-gem" aria-hidden="true"></i><p>آگهی زیر بازار در این فایل پیدا نشد</p></div>';
            return;
        }
        list.innerHTML = opps.map((o, i) => `
            <article class="ws-mkt-opp-card" data-listing-id="${o.listing_id}" tabindex="0" role="button">
                <div class="ws-mkt-opp-rank">${i + 1}</div>
                <div class="ws-mkt-opp-score">${o.value_score != null ? `${o.value_score}٪` : '—'}</div>
                <div class="ws-mkt-opp-body">
                    <strong>${o.title || o.token}</strong>
                    <em>${[o.neighborhood, o.area_fmt, o.price_fmt || o.rent_equiv_fmt || o.deposit_fmt].filter(Boolean).join(' · ')}</em>
                    <span class="ws-mkt-opp-reason">${o.reason || ''}</span>
                </div>
                <i class="fas fa-chevron-left ws-mkt-opp-arrow" aria-hidden="true"></i>
            </article>`).join('');
        list.querySelectorAll('.ws-mkt-opp-card').forEach(card => {
            const run = () => openOpportunity(card.dataset.listingId);
            card.addEventListener('click', run);
            card.addEventListener('keydown', e => { if (e.key === 'Enter') run(); });
        });
    }

    function renderNeighborhoodSelect() {
        const names = toolkit?.neighborhood_names || [];
        const opts = names.map(n => `<option value="${n}">${n}</option>`).join('');
        ['tbxNbSelect', 'tbxEvalNb'].forEach(id => {
            const sel = document.getElementById(id);
            if (!sel) return;
            const isEval = id === 'tbxEvalNb';
            sel.innerHTML = (isEval ? '<option value="">کل فایل</option>' : '<option value="">محله را انتخاب کنید</option>') + opts;
        });
        const quick = document.getElementById('tbxNbQuickList');
        if (quick) {
            quick.innerHTML = (toolkit?.neighborhoods || []).slice(0, 8).map(n => `
                <button type="button" class="ws-mkt-nb-chip" data-nb="${n.neighborhood}">
                    <strong>${n.neighborhood}</strong>
                    <span>${n.count} آگهی · ${n.p50_fmt || '—'}</span>
                </button>`).join('');
            quick.querySelectorAll('.ws-mkt-nb-chip').forEach(btn => {
                btn.addEventListener('click', () => {
                    const sel = document.getElementById('tbxNbSelect');
                    if (sel) sel.value = btn.dataset.nb;
                    renderNeighborhoodDetail(btn.dataset.nb);
                });
            });
        }
    }

    function renderNeighborhoodDetail(name) {
        const el = document.getElementById('tbxNeighborhoodResult');
        if (!el) return;
        const nb = (toolkit?.neighborhoods || []).find(n => n.neighborhood === name);
        if (!nb) {
            el.innerHTML = '<div class="ws-tbx-result-empty"><i class="fas fa-map-marker-alt"></i><p>محله‌ای انتخاب نشده</p></div>';
            return;
        }
        const p25 = nb.p25;
        const p75 = nb.p75;
        const p50 = nb.p50;
        const posPct = p25 && p75 && p50 && p75 > p25
            ? Math.max(4, Math.min(96, ((p50 - p25) / (p75 - p25)) * 100))
            : 50;
        el.innerHTML = `
            <div class="ws-mkt-nb-live">
                <div class="ws-mkt-nb-hero">
                    <span class="ws-mkt-nb-name">${nb.neighborhood}</span>
                    <span class="ws-mkt-nb-meta">${nb.count} آگهی · ${nb.metric_label}</span>
                </div>
                <div class="ws-mkt-band">
                    <div class="ws-mkt-band-labels">
                        <span>${nb.p25_fmt}</span><span>P25 – میانه – P75</span><span>${nb.p75_fmt}</span>
                    </div>
                    <div class="ws-mkt-band-track">
                        <div class="ws-mkt-band-fill"></div>
                        <div class="ws-mkt-band-marker ws-mkt-band-marker--median" style="inset-inline-start: ${posPct}%"></div>
                    </div>
                </div>
                <div class="ws-tbx-result-grid ws-tbx-result-grid--flex">
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${nb.p50_fmt}</span><span class="ws-tbx-result-item-lbl">میانه (P50)</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${nb.p25_fmt}</span><span class="ws-tbx-result-item-lbl">P25 (ارزان)</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${nb.p75_fmt}</span><span class="ws-tbx-result-item-lbl">P75 (گران)</span></div>
                    <div class="ws-tbx-result-item"><span class="ws-tbx-result-item-val">${nb.count}</span><span class="ws-tbx-result-item-lbl">تعداد آگهی</span></div>
                </div>
                <div class="ws-tbx-result-actions">
                    <button type="button" class="ws-tbx-copy-btn" data-copy="${nb.neighborhood}: ${nb.p25_fmt} – ${nb.p50_fmt} – ${nb.p75_fmt} (${nb.count} آگهی)">
                        <i class="fas fa-copy"></i> کپی بازه محله
                    </button>
                </div>
            </div>`;
        const copyBtn = el.querySelector('.ws-tbx-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(copyBtn.dataset.copy);
                copyBtn.textContent = 'کپی شد';
            });
        }
    }

    function renderNoDataset() {
        const msg = '<div class="ws-mkt-empty"><i class="fas fa-upload"></i><p>ابتدا یک فایل بازار انتخاب کنید</p></div>';
        const opps = document.getElementById('tbxOppsList');
        if (opps) opps.innerHTML = msg;
    }

    function renderToolkitError() {
        const opps = document.getElementById('tbxOppsList');
        if (opps) opps.innerHTML = '<div class="ws-mkt-empty"><i class="fas fa-exclamation-circle"></i><p>خطا در بارگذاری داده بازار</p></div>';
    }

    function updateEvalModeUI() {
        const isRent = toolkit?.is_rent && !toolkit?.show_price_per_sqm;
        const sale = document.getElementById('tbxEvalSaleFields');
        const rent = document.getElementById('tbxEvalRentFields');
        if (sale) sale.hidden = !!isRent;
        if (rent) rent.hidden = !isRent;
    }

    function onToolkitLoaded() {
        renderOpportunities();
        renderNeighborhoodSelect();
        updateEvalModeUI();
    }

    async function runEvaluate() {
        const container = document.getElementById('tbxEvaluateResult');
        if (!container || !getDatasetId()) return;
        const body = { action: 'evaluate' };
        if (selectedListingId) {
            body.listing_id = selectedListingId;
        } else {
            body.area = parseNumEl('tbxEvalArea');
            body.neighborhood = document.getElementById('tbxEvalNb')?.value || null;
            if (toolkit?.is_rent && !toolkit?.show_price_per_sqm) {
                body.deposit = parseIntEl('tbxEvalDeposit');
                body.rent = parseIntEl('tbxEvalRent');
            } else {
                body.price = parseIntEl('tbxEvalPrice');
            }
        }
        container.innerHTML = '<div class="ws-mkt-loading"><i class="fas fa-spinner fa-spin"></i> در حال ارزیابی...</div>';
        try {
            const data = await postEvaluate(body);
            renderEvaluateResult(data);
        } catch (e) {
            container.innerHTML = `<div class="ws-tbx-result-empty"><i class="fas fa-circle-exclamation"></i><p>${e.message}</p></div>`;
        }
    }

    async function searchListings(q) {
        const box = document.getElementById('tbxEvalSearchResults');
        if (!box) return;
        if (!q || q.length < 2) {
            box.innerHTML = '';
            return;
        }
        try {
            const data = await postEvaluate({ action: 'search', q });
            const items = data.items || [];
            if (!items.length) {
                box.innerHTML = '<p class="ws-mkt-search-empty">نتیجه‌ای یافت نشد</p>';
                return;
            }
            box.innerHTML = items.map(it => `
                <button type="button" class="ws-mkt-search-item" data-id="${it.id}">
                    <strong>${it.title || it.token}</strong>
                    <em>${[it.neighborhood, it.area_fmt, it.price_fmt || it.deposit_fmt].filter(Boolean).join(' · ')}</em>
                </button>`).join('');
            box.querySelectorAll('.ws-mkt-search-item').forEach(btn => {
                btn.addEventListener('click', () => {
                    selectedListingId = parseInt(btn.dataset.id, 10);
                    box.querySelectorAll('.ws-mkt-search-item').forEach(b => b.classList.remove('is-selected'));
                    btn.classList.add('is-selected');
                    runEvaluate();
                });
            });
        } catch (e) {
            box.innerHTML = '';
        }
    }

    function openOpportunity(listingId) {
        const id = parseInt(listingId, 10);
        if (typeof window.wsTbxSwitchTool === 'function') {
            window.wsTbxSwitchTool('evaluate');
        }
        document.querySelector('.ws-mkt-tab[data-eval-tab="file"]')?.click();
        selectedListingId = id;
        const search = document.getElementById('tbxEvalSearch');
        if (search && !search.value.trim()) search.placeholder = 'آگهی انتخاب شد — در حال ارزیابی...';
        runEvaluate();
    }

    function bindEvents() {
        document.addEventListener('wsTbxDatasetChanged', e => {
            datasetId = e.detail?.id || getDatasetId();
            toolkit = null;
            selectedListingId = null;
            fetchToolkit();
        });

        document.getElementById('tbxEvalRun')?.addEventListener('click', () => {
            selectedListingId = null;
            runEvaluate();
        });

        document.querySelectorAll('.ws-mkt-tab[data-eval-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.ws-mkt-tab').forEach(t => t.classList.remove('is-active'));
                tab.classList.add('is-active');
                const key = tab.dataset.evalTab;
                document.getElementById('tbxEvalManual').hidden = key !== 'manual';
                document.getElementById('tbxEvalFile').hidden = key !== 'file';
                selectedListingId = null;
            });
        });

        document.getElementById('tbxEvalSearch')?.addEventListener('input', e => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => searchListings(e.target.value.trim()), 280);
        });

        document.getElementById('tbxNbSelect')?.addEventListener('change', e => {
            renderNeighborhoodDetail(e.target.value);
        });

        ['tbxEvalArea', 'tbxEvalPrice', 'tbxEvalDeposit', 'tbxEvalRent'].forEach(id => {
            document.getElementById(id)?.addEventListener('keydown', e => {
                if (e.key === 'Enter') runEvaluate();
            });
        });
    }

    function init() {
        if (!document.getElementById('wsToolbox')) return;
        bindEvents();
        datasetId = getDatasetId();
        if (datasetId) fetchToolkit();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
