/**
 * فایلینگ دیوار — UI هوش مصنوعی (فاز صفر)
 */
(function () {
    'use strict';

    function csrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function toPersianDigits(value) {
        return String(value ?? '').replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
    }

    function quotaStateClass(quota) {
        if (!quota || quota.is_unlimited) return 'ws-ai-quota--unlimited';
        if ((quota.feature_remaining ?? 0) <= 0) return 'ws-ai-quota--depleted';
        if ((quota.feature_remaining ?? 0) <= 2) return 'ws-ai-quota--low';
        return '';
    }

    function updateCardQuota(card, quota) {
        if (!card || !quota || quota.is_unlimited) return;
        const panel = card.querySelector('[data-ai-quota-panel]');
        if (!panel) return;

        panel.classList.remove('ws-ai-quota--low', 'ws-ai-quota--depleted', 'ws-ai-quota--unlimited');
        const extra = quotaStateClass(quota);
        if (extra) panel.classList.add(extra);

        const usedEl = panel.querySelector('[data-ai-quota-used]');
        const limitEl = panel.querySelector('[data-ai-quota-limit]');
        const remainingPill = panel.querySelector('[data-ai-quota-remaining-pill]');
        const fillEl = card.querySelector('[data-ai-quota-fill]');
        const trackEl = card.querySelector('[data-ai-quota-track]');
        const dailyRemainingEl = panel.querySelector('[data-ai-daily-remaining]');
        const dailyLimitEl = panel.querySelector('[data-ai-daily-limit]');

        const used = quota.feature_used ?? 0;
        const limit = quota.feature_limit ?? 0;
        const remaining = quota.feature_remaining ?? 0;
        const percent = limit ? Math.min(100, Math.round(used * 100 / limit)) : 0;

        if (usedEl) usedEl.textContent = toPersianDigits(used);
        if (limitEl) limitEl.textContent = toPersianDigits(limit);
        if (remainingPill) remainingPill.textContent = `${toPersianDigits(remaining)} باقی‌مانده`;
        if (fillEl) fillEl.style.width = `${percent}%`;
        if (trackEl) {
            trackEl.setAttribute('aria-valuenow', String(used));
            trackEl.setAttribute('aria-valuemax', String(limit));
        }
        if (dailyRemainingEl) dailyRemainingEl.textContent = toPersianDigits(quota.daily_remaining ?? 0);
        if (dailyLimitEl) dailyLimitEl.textContent = toPersianDigits(quota.daily_limit ?? 0);
    }

    function renderQuotaInline(quota) {
        if (!quota) return '';
        if (quota.is_unlimited) {
            return '<span class="ws-ai-quota-inline ws-ai-quota-inline--unlimited"><i class="fas fa-infinity" aria-hidden="true"></i> ظرفیت نامحدود</span>';
        }
        const used = quota.feature_used ?? 0;
        const limit = quota.feature_limit ?? 0;
        const remaining = quota.feature_remaining ?? 0;
        return `<span class="ws-ai-quota-inline" title="ظرفیت روزانه خلاصه هوشمند">
            <i class="fas fa-gauge-high" aria-hidden="true"></i>
            ${toPersianDigits(used)} از ${toPersianDigits(limit)} درخواست
            · ${toPersianDigits(remaining)} باقی‌مانده
        </span>`;
    }

    const LISTING_PREFS_STORAGE_KEY = 'ws_ai_listing_summary_prefs_v1';

    function renderPreferenceBadges(prefs) {
        if (!prefs) return '';
        const tone = prefs.tone_label || prefs.tone || '';
        const style = prefs.style_label || prefs.style || '';
        let html = '';
        if (tone) {
            html += `<span class="ws-ai-pref-badge" title="لحن تولید"><i class="fas fa-microphone-lines" aria-hidden="true"></i> ${escapeHtml(tone)}</span>`;
        }
        if (style) {
            html += `<span class="ws-ai-pref-badge ws-ai-pref-badge--style" title="سبک تولید"><i class="fas fa-palette" aria-hidden="true"></i> ${escapeHtml(style)}</span>`;
        }
        return html;
    }

    function renderResultMeta(data) {
        const badge = renderBadge(data);
        const quota = renderQuotaInline(data.quota);
        const prefs = renderPreferenceBadges(data.preferences);
        if (!badge && !quota && !prefs) return '';
        return `<div class="ws-ai-result-meta">${badge}${prefs}${quota}</div>`;
    }

    function readListingSummaryPrefs(card) {
        const panel = card?.querySelector('[data-ai-summary-prefs]');
        const toneInput = panel?.querySelector('[data-ai-tone-input]:checked');
        const styleInput = panel?.querySelector('[data-ai-style-input]:checked');
        return {
            tone: toneInput?.value || 'مشاورانه',
            style: styleInput?.value || 'کارتی',
        };
    }

    function updateListingPrefHints(card) {
        const panel = card?.querySelector('[data-ai-summary-prefs]');
        if (!panel) return;
        const toneInput = panel.querySelector('[data-ai-tone-input]:checked');
        const styleInput = panel.querySelector('[data-ai-style-input]:checked');
        const toneHint = panel.querySelector('[data-ai-tone-hint]');
        const styleHint = panel.querySelector('[data-ai-style-hint]');
        if (toneHint && toneInput) {
            toneHint.textContent = toneInput.closest('label')?.querySelector('.ws-ai-pro__seg-btn, .ws-ai-summary-prefs__opt-pill')?.getAttribute('title') || '';
        }
        if (styleHint && styleInput) {
            styleHint.textContent = styleInput.closest('label')?.querySelector('.ws-ai-pro__seg-btn, .ws-ai-summary-prefs__opt-pill')?.getAttribute('title') || '';
        }
    }

    function persistListingSummaryPrefs(card) {
        const prefs = readListingSummaryPrefs(card);
        try {
            localStorage.setItem(LISTING_PREFS_STORAGE_KEY, JSON.stringify(prefs));
        } catch (_e) { /* ignore */ }
    }

    function restoreListingSummaryPrefs(card) {
        const panel = card?.querySelector('[data-ai-summary-prefs]');
        if (!panel) return;
        let saved = null;
        try {
            saved = JSON.parse(localStorage.getItem(LISTING_PREFS_STORAGE_KEY) || 'null');
        } catch (_e) {
            saved = null;
        }
        if (!saved || typeof saved !== 'object') return;
        const tone = saved.tone;
        const style = saved.style;
        const escAttr = (value) => {
            if (window.CSS && typeof window.CSS.escape === 'function') {
                return window.CSS.escape(String(value));
            }
            return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        };
        if (tone) {
            const input = panel.querySelector(`[data-ai-tone-input][value="${escAttr(tone)}"]`);
            if (input) input.checked = true;
        }
        if (style) {
            const input = panel.querySelector(`[data-ai-style-input][value="${escAttr(style)}"]`);
            if (input) input.checked = true;
        }
        updateListingPrefHints(card);
    }

    function initListingSummaryPrefs() {
        document.querySelectorAll('#wsAiListingSummary[data-ai-card]').forEach((card) => {
            restoreListingSummaryPrefs(card);
            updateListingPrefHints(card);
            card.querySelectorAll('[data-ai-tone-input], [data-ai-style-input]').forEach((input) => {
                input.addEventListener('change', () => {
                    updateListingPrefHints(card);
                    persistListingSummaryPrefs(card);
                });
            });
        });
    }

    const LISTING_SUMMARY_LOAD_STEPS = [
        { id: 'market', label: 'تحلیل بازار و قیمت', icon: 'fa-chart-line' },
        { id: 'features', label: 'امکانات و ویژگی‌های ملک', icon: 'fa-building' },
        { id: 'negotiation', label: 'پیشنهاد مذاکره', icon: 'fa-handshake' },
    ];

    const HIGHLIGHT_ICONS = [
        'fa-circle-check',
        'fa-bolt',
        'fa-gem',
        'fa-location-dot',
        'fa-chart-simple',
        'fa-house-chimney',
        'fa-star',
        'fa-shield-halved',
    ];

    function pickHighlightIcon(text) {
        const t = String(text || '');
        if (/قیمت|معامله|رهن|اجاره|ودیعه|میلیارد|تومان|متری/i.test(t)) return 'fa-coins';
        if (/متراژ|خواب|اتاق|طبقه|ساخت|سال/i.test(t)) return 'fa-ruler-combined';
        if (/محله|منطقه|موقعیت|دسترسی|شهر/i.test(t)) return 'fa-location-dot';
        if (/بازار|میانه|زیر|بالا|متعارف/i.test(t)) return 'fa-chart-line';
        if (/پارکینگ|انباری|آسانسور|امکانات|بالکن/i.test(t)) return 'fa-sparkles';
        return 'fa-circle-check';
    }

    function formatSummaryHtml(summary) {
        const clean = String(summary || '').trim();
        if (!clean) return '';
        const parts = clean
            .split(/(?<=[.!?؟۔])\s+/)
            .map((s) => s.trim())
            .filter(Boolean);
        if (parts.length <= 1) {
            return `<p class="ws-ai-summary-pro__lead-text">${escapeHtml(clean)}</p>`;
        }
        return `<div class="ws-ai-summary-pro__lead-text ws-ai-summary-pro__lead-text--stacked">${parts
            .map((p) => `<p class="ws-ai-summary-pro__sentence">${escapeHtml(p)}</p>`)
            .join('')}</div>`;
    }

    let listingSummaryLoadTimer = null;

    function setLoading(btn, loading, { listing = false } = {}) {
        if (!btn) return;
        btn.disabled = loading;
        btn.classList.toggle('ws-ai-loading', loading);
        btn.classList.toggle('is-loading', loading && listing);
        const label = btn.querySelector('.ws-ai-card__cta-label');
        if (loading) {
            if (!btn.dataset.aiOrigText) btn.dataset.aiOrigText = btn.innerHTML;
            if (label) {
                if (!btn.dataset.aiOrigLabel) btn.dataset.aiOrigLabel = label.textContent;
                label.textContent = listing ? 'در حال تولید…' : (btn.dataset.aiOrigLabel || label.textContent);
            }
        } else {
            if (btn.dataset.aiOrigText) {
                btn.innerHTML = btn.dataset.aiOrigText;
                delete btn.dataset.aiOrigText;
            }
            if (label && btn.dataset.aiOrigLabel) {
                label.textContent = btn.dataset.aiOrigLabel;
                delete btn.dataset.aiOrigLabel;
            }
            btn.classList.remove('is-loading');
        }
    }

    function renderBadge(data) {
        if (!data) return '';
        const modelLabel = (data.model_label || '').trim();
        if (modelLabel) {
            const isSystem = modelLabel === 'مدل داخلی سیستم'
                || modelLabel === 'منطق سیستم'
                || data.provider === 'rule_based'
                || data.source === 'fallback';
            const cls = isSystem ? 'ws-ai-badge--fallback' : 'ws-ai-badge--model';
            return `<span class="ws-ai-badge ${cls}" title="مدل تولید">${escapeHtml(modelLabel)}</span>`;
        }
        const provider = data.provider;

        if (provider === 'rule_based') {
            return '<span class="ws-ai-badge ws-ai-badge--fallback">مدل داخلی سیستم</span>';
        }
        if (provider === 'openrouter' || provider === 'arvan') {
            return '<span class="ws-ai-badge ws-ai-badge--backup">هوش مصنوعی (پشتیبان)</span>';
        }
        if (provider === 'gemini' && data.is_fallback) {
            return '<span class="ws-ai-badge ws-ai-badge--lite">هوش مصنوعی (مدل جایگزین)</span>';
        }
        if (data.from_cache || provider === 'cache') {
            return '<span class="ws-ai-badge ws-ai-badge--cache">از کش</span>';
        }
        if (data.model) {
            return `<span class="ws-ai-badge ws-ai-badge--model">${escapeHtml(data.model)}</span>`;
        }
        return '';
    }

    function renderListingSummaryLoading() {
        const steps = LISTING_SUMMARY_LOAD_STEPS.map((step) => (
            `<li class="ws-ai-load-step" data-ai-load-step="${step.id}">
                <span class="ws-ai-load-step__icon"><i class="fas ${step.icon}" aria-hidden="true"></i></span>
                <span class="ws-ai-load-step__label">${escapeHtml(step.label)}</span>
                <span class="ws-ai-load-step__status" aria-hidden="true"></span>
            </li>`
        )).join('');
        return `<div class="ws-ai-summary-loading" role="status" aria-live="polite" aria-busy="true">
            <div class="ws-ai-summary-loading__orb" aria-hidden="true">
                <span class="ws-ai-summary-loading__ring"></span>
                <span class="ws-ai-summary-loading__core"><i class="fas fa-wand-magic-sparkles"></i></span>
            </div>
            <p class="ws-ai-summary-loading__title">در حال ساخت خلاصه هوشمند</p>
            <p class="ws-ai-summary-loading__sub">داده‌های فایل، امکانات و موقعیت در حال ترکیب است…</p>
            <ol class="ws-ai-load-steps">${steps}</ol>
            <div class="ws-ai-summary-loading__bar" aria-hidden="true"><span class="ws-ai-summary-loading__bar-fill"></span></div>
        </div>`;
    }

    function stopListingSummaryLoadAnimation(card) {
        if (listingSummaryLoadTimer) {
            clearInterval(listingSummaryLoadTimer);
            listingSummaryLoadTimer = null;
        }
        card?.classList.remove('is-ai-loading');
        card?.querySelectorAll('[data-ai-load-step]').forEach((step) => {
            step.classList.remove('is-active', 'is-done');
        });
    }

    function startListingSummaryLoadAnimation(card) {
        if (!card) return;
        stopListingSummaryLoadAnimation(card);
        card.classList.add('is-ai-loading');
        const steps = card.querySelectorAll('[data-ai-load-step]');
        let index = 0;

        const tick = () => {
            steps.forEach((el, i) => {
                el.classList.toggle('is-active', i === index);
                el.classList.toggle('is-done', i < index);
            });
            index = (index + 1) % LISTING_SUMMARY_LOAD_STEPS.length;
        };

        tick();
        listingSummaryLoadTimer = setInterval(tick, 1400);
    }

    function summaryPlainText(d) {
        const parts = [];
        const summary = (d.summary || '').trim();
        if (summary) parts.push(summary);
        (d.highlights || []).forEach((h) => {
            const line = String(h || '').trim();
            if (line) parts.push(`• ${line}`);
        });
        const tip = (d.negotiation_tip || '').trim();
        if (tip) parts.push(`نکته مذاکره: ${tip}`);
        return parts.join('\n\n');
    }

    function bindListingSummaryActions(container, data) {
        if (!container) return;
        const copyBtn = container.querySelector('[data-ai-copy-summary]');
        if (!copyBtn) return;
        const d = data.data || {};
        const text = summaryPlainText(d) || String(data.text || '').trim();
        copyBtn.addEventListener('click', () => {
            if (!text) return;
            const done = () => {
                copyBtn.classList.add('is-copied');
                const span = copyBtn.querySelector('span');
                if (span) {
                    const orig = span.textContent;
                    span.textContent = 'کپی شد';
                    setTimeout(() => {
                        span.textContent = orig;
                        copyBtn.classList.remove('is-copied');
                    }, 1800);
                }
            };
            if (navigator.clipboard?.writeText) {
                navigator.clipboard.writeText(text).then(done).catch(() => {});
            }
        });
    }

    function renderListingSummary(data) {
        const d = data.data || {};
        const summary = (d.summary || data.text || '').trim();
        const highlights = (d.highlights || []).filter((h) => String(h || '').trim());
        const negotiation = (d.negotiation_tip || '').trim();
        const meta = renderResultMeta(data);
        const canCopy = !!(summary || highlights.length || negotiation);

        let html = '<div class="ws-ai-summary-pro ws-ai-summary-pro--enter">';
        if (meta || canCopy) {
            html += '<div class="ws-ai-summary-pro__toolbar">';
            html += meta || '<div></div>';
            if (canCopy) {
                html += `<div class="ws-ai-summary-pro__actions">
                    <button type="button" class="ws-ai-summary-pro__copy" data-ai-copy-summary>
                        <i class="fas fa-copy" aria-hidden="true"></i><span>کپی متن</span>
                    </button>
                </div>`;
            }
            html += '</div>';
        }

        if (summary) {
            html += `<article class="ws-ai-summary-pro__lead">
                <header class="ws-ai-summary-pro__lead-head">
                    <span class="ws-ai-summary-pro__lead-icon" aria-hidden="true"><i class="fas fa-file-lines"></i></span>
                    <h4>خلاصه اجرایی</h4>
                </header>
                ${formatSummaryHtml(summary)}
            </article>`;
        }

        if (highlights.length) {
            html += '<section class="ws-ai-summary-pro__grid" aria-label="نکات برجسته">';
            html += '<h4 class="ws-ai-summary-pro__section-title"><i class="fas fa-star" aria-hidden="true"></i> نکات برجسته</h4>';
            html += '<ul class="ws-ai-summary-pro__highlights">';
            highlights.forEach((h, i) => {
                const icon = pickHighlightIcon(h) || HIGHLIGHT_ICONS[i % HIGHLIGHT_ICONS.length];
                html += `<li class="ws-ai-summary-pro__highlight">
                    <span class="ws-ai-summary-pro__highlight-ico" aria-hidden="true"><i class="fas ${icon}"></i></span>
                    <span>${escapeHtml(h)}</span>
                </li>`;
            });
            html += '</ul></section>';
        }

        if (negotiation) {
            html += `<aside class="ws-ai-summary-pro__negotiate">
                <div class="ws-ai-summary-pro__negotiate-icon" aria-hidden="true"><i class="fas fa-handshake"></i></div>
                <div>
                    <strong>نکته مذاکره</strong>
                    <p>${escapeHtml(negotiation)}</p>
                </div>
            </aside>`;
        }

        html += '</div>';
        if (!summary && !highlights.length && !negotiation) {
            return `<p class="ws-ai-summary">${escapeHtml(data.text || '')}</p>`;
        }
        return html;
    }

    async function postJson(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: body ? JSON.stringify(body) : '{}',
            credentials: 'same-origin',
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
            const err = new Error(data.error || 'خطا در سرویس AI');
            err.code = data.code;
            throw err;
        }
        return data;
    }

    function toggleAiEmpty(card, show) {
        if (!card) return;
        const empty = card.querySelector('[data-ai-empty]');
        if (empty) empty.hidden = !show;
    }

    function showResult(container, html, { card, data } = {}) {
        if (!container) return;
        container.innerHTML = html;
        container.hidden = false;
        const rootCard = card || container.closest('[data-ai-card]');
        if (rootCard) toggleAiEmpty(rootCard, false);
        if (data) bindListingSummaryActions(container, data);
    }

    async function handleListingSummary(btn) {
        const card = btn.closest('[data-ai-card]') || document.getElementById('wsAiListingSummary');
        const result = card ? card.querySelector('[data-ai-result], .ws-ai-result') : null;
        setLoading(btn, true, { listing: true });
        toggleAiEmpty(card, false);
        if (result) {
            result.innerHTML = renderListingSummaryLoading();
            result.hidden = false;
        }
        startListingSummaryLoadAnimation(card);
        try {
            const prefs = readListingSummaryPrefs(card);
            persistListingSummaryPrefs(card);
            const data = await postJson(btn.dataset.aiUrl, prefs);
            stopListingSummaryLoadAnimation(card);
            if (data.skipped) {
                const hint = data.message || 'برای تولید خلاصه هوشمند، اطلاعات بیشتری از ملک ثبت کنید.';
                showResult(result, `<div class="ws-ai-summary-pro ws-ai-summary-pro--enter">
                    <div class="ws-ai-summary-pro__skipped">
                        <i class="fas fa-circle-info" aria-hidden="true"></i>
                        <span>${escapeHtml(hint)}</span>
                    </div>
                </div>`, { card });
                if (card && data.quota) updateCardQuota(card, data.quota);
                return;
            }
            showResult(result, renderListingSummary(data), { card, data });
            if (card && data.quota) updateCardQuota(card, data.quota);
        } catch (e) {
            stopListingSummaryLoadAnimation(card);
            showResult(result, `<div class="ws-ai-summary-pro ws-ai-summary-pro--enter">
                <div class="ws-ai-summary-pro__error">
                    <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
                    <span>${escapeHtml(e.message)}</span>
                </div>
            </div>`, { card });
        } finally {
            setLoading(btn, false, { listing: true });
        }
    }

    function syncCrmPreviewState(preview) {
        if (!preview) return;
        const box = preview.closest('[data-ai-preview-box]');
        const empty = box?.querySelector('[data-ai-preview-empty]');
        const hasContent = !!(preview.value || '').trim();
        if (box) box.classList.toggle('has-content', hasContent);
        if (empty) empty.hidden = hasContent;
        syncCrmWhatsAppButton(preview);
    }

    function normalizeWaPhone(phone) {
        let digits = String(phone || '').replace(/\D/g, '');
        if (!digits) return '';
        if (digits.startsWith('00')) {
            digits = digits.slice(2);
        } else if (digits.startsWith('0')) {
            digits = digits.slice(1);
        }
        if (digits.startsWith('98')) {
            return digits;
        }
        return `98${digits}`;
    }

    function buildWhatsAppUrl(phone, text) {
        const cc = normalizeWaPhone(phone);
        const body = (text || '').trim();
        if (!cc || !body || body.startsWith('در حال ساخت')) return '';
        return `https://wa.me/${cc}?text=${encodeURIComponent(body)}`;
    }

    function syncCrmWhatsAppButton(preview) {
        const waBtn = document.getElementById('aiCrmWhatsApp');
        if (!waBtn || !preview) return;
        const phone = preview.closest('.ws-ai-crm-compose')?.dataset.waPhone || '';
        const url = buildWhatsAppUrl(phone, preview.value);
        waBtn.href = url || '#';
        waBtn.setAttribute('aria-disabled', url ? 'false' : 'true');
        waBtn.classList.toggle('is-disabled', !url);
    }

    async function handleCrmCompose(btn) {
        const panel = btn.closest('.crm-drawer-panel');
        const compose = panel ? panel.querySelector('.ws-ai-crm-compose') : null;
        if (!compose) return;
        const channel = panel.querySelector('#aiCrmChannel')?.value || 'واتساپ';
        const tone = panel.querySelector('#aiCrmTone')?.value || 'رسمی';
        const preview = panel.querySelector('#aiCrmPreview');
        const copyBtn = panel.querySelector('#aiCrmCopy');
        setLoading(btn, true);
        if (preview) {
            preview.value = 'در حال ساخت پیام هوشمند…';
            syncCrmPreviewState(preview);
        }
        try {
            const data = await postJson(compose.dataset.aiUrl, { channel, tone });
            const text = data.text || '';
            if (preview) {
                preview.value = text;
                syncCrmPreviewState(preview);
            }
            if (copyBtn) copyBtn.disabled = !text;
            const meta = compose.querySelector('.ws-ai-result');
            if (meta) {
                showResult(meta, renderBadge(data));
            }
        } catch (e) {
            if (preview) {
                preview.value = '';
                syncCrmPreviewState(preview);
            }
            alert(e.message || 'خطا');
        } finally {
            setLoading(btn, false);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initListingSummaryPrefs();
        document.querySelectorAll('.ws-ai-trigger[data-ai-url]').forEach(btn => {
            btn.addEventListener('click', () => handleListingSummary(btn));
        });

        document.querySelectorAll('.ws-ai-trigger[data-ai-compose]').forEach(btn => {
            btn.addEventListener('click', () => handleCrmCompose(btn));
        });

        const copyBtn = document.getElementById('aiCrmCopy');
        copyBtn?.addEventListener('click', () => {
            const text = document.getElementById('aiCrmPreview')?.value || '';
            if (!text || text.startsWith('در حال ساخت')) return;
            if (navigator.clipboard?.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    const label = copyBtn.querySelector('span');
                    if (!label) return;
                    const orig = label.textContent;
                    label.textContent = 'کپی شد';
                    setTimeout(() => { label.textContent = orig; }, 1600);
                });
            }
        });

        document.querySelectorAll('#aiCrmPreview').forEach(preview => {
            syncCrmPreviewState(preview);
        });

        document.getElementById('aiCrmWhatsApp')?.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            if (btn.getAttribute('aria-disabled') === 'true') {
                e.preventDefault();
            }
        });
    });
})();
