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

    function setLoading(btn, loading) {
        if (!btn) return;
        btn.disabled = loading;
        btn.classList.toggle('ws-ai-loading', loading);
        if (loading) btn.dataset.aiOrigText = btn.innerHTML;
        else if (btn.dataset.aiOrigText) btn.innerHTML = btn.dataset.aiOrigText;
    }

    function renderBadge(data) {
        const provider = data && data.provider;
        if (provider === 'rule_based') {
            return '<span class="ws-ai-badge ws-ai-badge--fallback">حالت پایه</span>';
        }
        if (provider === 'openrouter') {
            return '<span class="ws-ai-badge ws-ai-badge--backup">هوش مصنوعی (پشتیبان)</span>';
        }
        if (data && data.from_cache) {
            return '<span class="ws-ai-badge ws-ai-badge--cache">از کش</span>';
        }
        return '';
    }

    function renderListingSummary(data) {
        const d = data.data || {};
        const highlights = (d.highlights || []).map(h => `<li>${escapeHtml(h)}</li>`).join('');
        let html = renderBadge(data);
        if (d.summary) html += `<p class="ws-ai-summary">${escapeHtml(d.summary)}</p>`;
        if (highlights) html += `<ul class="ws-ai-highlights">${highlights}</ul>`;
        if (d.negotiation_tip) html += `<p class="ws-ai-tip"><strong>مذاکره:</strong> ${escapeHtml(d.negotiation_tip)}</p>`;
        if (d.advertiser_note) html += `<p class="ws-ai-note"><strong>آگهی‌دهنده:</strong> ${escapeHtml(d.advertiser_note)}</p>`;
        return html || `<p>${escapeHtml(d.summary || data.text || '')}</p>`;
    }

    function renderUploadBrief(data) {
        const d = data.data || {};
        let html = renderBadge(data);
        if (d.executive_summary) html += `<p class="ws-ai-summary">${escapeHtml(d.executive_summary)}</p>`;
        const lists = [
            ['فرصت‌ها', d.opportunities],
            ['اقدام پیشنهادی', d.action_items],
        ];
        lists.forEach(([title, items]) => {
            if (items && items.length) {
                html += `<p class="ws-ai-subtitle">${escapeHtml(title)}</p><ul class="ws-ai-highlights">`;
                items.forEach(item => { html += `<li>${escapeHtml(item)}</li>`; });
                html += '</ul>';
            }
        });
        if (d.outliers_note) html += `<p class="ws-ai-note">${escapeHtml(d.outliers_note)}</p>`;
        if (d.duplicates_note) html += `<p class="ws-ai-note">${escapeHtml(d.duplicates_note)}</p>`;
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

    function showResult(container, html) {
        if (!container) return;
        container.innerHTML = html;
        container.hidden = false;
    }

    async function handleListingSummary(btn) {
        const card = btn.closest('[data-ai-card]') || document.getElementById('wsAiListingSummary');
        const result = card ? card.querySelector('.ws-ai-result') : null;
        setLoading(btn, true);
        if (result) result.innerHTML = '<p class="ws-ai-loading-text">در حال تحلیل…</p>';
        if (result) result.hidden = false;
        try {
            const data = await postJson(btn.dataset.aiUrl);
            showResult(result, renderListingSummary(data));
        } catch (e) {
            showResult(result, `<p class="ws-ai-error">${escapeHtml(e.message)}</p>`);
        } finally {
            setLoading(btn, false);
        }
    }

    async function handleUploadBrief(btn) {
        const result = document.getElementById('wsAiUploadBrief') || btn.parentElement.querySelector('.ws-ai-result');
        setLoading(btn, true);
        if (result) {
            result.innerHTML = '<p class="ws-ai-loading-text">در حال تحلیل آپلود…</p>';
            result.hidden = false;
        }
        try {
            const data = await postJson(btn.dataset.aiUrl);
            showResult(result, renderUploadBrief(data));
        } catch (e) {
            showResult(result, `<p class="ws-ai-error">${escapeHtml(e.message)}</p>`);
        } finally {
            setLoading(btn, false);
        }
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
        if (preview) preview.value = 'در حال تولید…';
        try {
            const data = await postJson(compose.dataset.aiUrl, { channel, tone });
            const text = data.text || '';
            if (preview) preview.value = text;
            if (copyBtn) copyBtn.disabled = !text;
            const meta = compose.querySelector('.ws-ai-result');
            if (meta) {
                showResult(meta, renderBadge(data));
            }
        } catch (e) {
            if (preview) preview.value = '';
            alert(e.message || 'خطا');
        } finally {
            setLoading(btn, false);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.ws-ai-trigger[data-ai-url]').forEach(btn => {
            btn.addEventListener('click', () => {
                const feature = btn.dataset.aiFeature;
                if (feature === 'upload_brief') handleUploadBrief(btn);
                else handleListingSummary(btn);
            });
        });

        document.querySelectorAll('.ws-ai-trigger[data-ai-compose]').forEach(btn => {
            btn.addEventListener('click', () => handleCrmCompose(btn));
        });

        const copyBtn = document.getElementById('aiCrmCopy');
        copyBtn?.addEventListener('click', () => {
            const text = document.getElementById('aiCrmPreview')?.value || '';
            if (!text) return;
            if (navigator.clipboard?.writeText) {
                navigator.clipboard.writeText(text);
            }
        });
    });
})();
