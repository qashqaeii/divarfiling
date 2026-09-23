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
        const fillEl = panel.querySelector('[data-ai-quota-fill]');
        const trackEl = panel.querySelector('[data-ai-quota-track]');
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

    function renderResultMeta(data) {
        const badge = renderBadge(data);
        const quota = renderQuotaInline(data.quota);
        if (!badge && !quota) return '';
        return `<div class="ws-ai-result-meta">${badge}${quota}</div>`;
    }

    function setLoading(btn, loading) {
        if (!btn) return;
        btn.disabled = loading;
        btn.classList.toggle('ws-ai-loading', loading);
        if (loading) btn.dataset.aiOrigText = btn.innerHTML;
        else if (btn.dataset.aiOrigText) btn.innerHTML = btn.dataset.aiOrigText;
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

    function renderListingSummary(data) {
        const d = data.data || {};
        const highlights = (d.highlights || []).map(h => `<li>${escapeHtml(h)}</li>`).join('');
        let html = renderResultMeta(data);
        if (d.summary) html += `<p class="ws-ai-summary">${escapeHtml(d.summary)}</p>`;
        if (highlights) html += `<ul class="ws-ai-highlights">${highlights}</ul>`;
        if (d.negotiation_tip) html += `<p class="ws-ai-tip"><strong>مذاکره:</strong> ${escapeHtml(d.negotiation_tip)}</p>`;
        return html || `<p>${escapeHtml(d.summary || data.text || '')}</p>`;
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

    function showResult(container, html) {
        if (!container) return;
        container.innerHTML = html;
        container.hidden = false;
        const card = container.closest('[data-ai-card]');
        if (card) toggleAiEmpty(card, false);
    }

    async function handleListingSummary(btn) {
        const card = btn.closest('[data-ai-card]') || document.getElementById('wsAiListingSummary');
        const result = card ? card.querySelector('.ws-ai-result') : null;
        setLoading(btn, true);
        toggleAiEmpty(card, false);
        if (result) {
            result.innerHTML = '<div class="ws-ai-card__loading"><span class="ws-ai-card__loading-dot"></span><span class="ws-ai-card__loading-dot"></span><span class="ws-ai-card__loading-dot"></span><p>در حال تحلیل هوشمند فایل…</p></div>';
            result.hidden = false;
        }
        try {
            const data = await postJson(btn.dataset.aiUrl);
            showResult(result, renderListingSummary(data));
            if (card && data.quota) updateCardQuota(card, data.quota);
        } catch (e) {
            showResult(result, `<p class="ws-ai-error">${escapeHtml(e.message)}</p>`);
        } finally {
            setLoading(btn, false);
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
