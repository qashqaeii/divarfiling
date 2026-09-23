(function () {
    'use strict';

    function csrfToken() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(body || {}),
        }).then((r) => r.json().then((data) => ({ ok: r.ok, status: r.status, data })));
    }

    function init() {
        const root = document.getElementById('crmNlCommand');
        if (!root) return;

        const parseUrl = root.dataset.parseUrl;
        const confirmUrl = root.dataset.confirmUrl;
        const resolveUrl = root.dataset.resolveUrl;
        const input = document.getElementById('crmNlCommandInput');
        const parseBtn = document.getElementById('crmNlCommandParseBtn');
        const preview = document.getElementById('crmNlCommandPreview');
        const statusEl = document.getElementById('crmNlCommandStatus');
        const confirmBtn = document.getElementById('crmNlCommandConfirmBtn');
        const cancelBtn = document.getElementById('crmNlCommandCancelBtn');
        const candidatesEl = document.getElementById('crmNlCommandCandidates');

        let commandId = null;

        function setStatus(msg, isError) {
            if (!statusEl) return;
            statusEl.hidden = !msg;
            statusEl.textContent = msg || '';
            statusEl.classList.toggle('is-error', !!isError);
        }

        function fillPreview(p) {
            if (!preview || !p) return;
            preview.querySelector('[data-field="contact_name"]').textContent = p.contact_name || '—';
            preview.querySelector('[data-field="due_at_display"]').textContent = p.due_at_display || '—';
            preview.querySelector('[data-field="title"]').textContent = p.title || '—';
            preview.querySelector('[data-field="note"]').textContent = p.note || '—';
            preview.hidden = false;
        }

        function reset() {
            commandId = null;
            if (preview) preview.hidden = true;
            if (candidatesEl) {
                candidatesEl.hidden = true;
                candidatesEl.innerHTML = '';
            }
            if (confirmBtn) confirmBtn.disabled = true;
            setStatus('');
        }

        function renderCandidates(candidates) {
            if (!candidatesEl || !candidates || !candidates.length) return;
            candidatesEl.innerHTML = '<p class="crm-nl-command__candidates-title">کدام مخاطب؟</p>';
            candidates.forEach((c) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'crm-nl-command__candidate';
                btn.textContent = c.name;
                btn.addEventListener('click', () => {
                    if (!commandId) return;
                    postJson(resolveUrl, { command_id: commandId, contact_id: c.id }).then((res) => {
                        if (!res.data.ok) {
                            setStatus(res.data.error || 'خطا', true);
                            return;
                        }
                        fillPreview(res.data.preview);
                        if (confirmBtn) confirmBtn.disabled = !res.data.can_confirm;
                        candidatesEl.hidden = true;
                    });
                });
                candidatesEl.appendChild(btn);
            });
            candidatesEl.hidden = false;
        }

        parseBtn?.addEventListener('click', () => {
            const text = (input?.value || '').trim();
            if (!text) {
                setStatus('متن فرمان را وارد کنید.', true);
                return;
            }
            parseBtn.disabled = true;
            setStatus('در حال بررسی…');
            postJson(parseUrl, { text, locale: 'fa-IR', timezone: 'Asia/Tehran' })
                .then((res) => {
                    parseBtn.disabled = false;
                    const data = res.data;
                    if (!data.ok) {
                        setStatus(data.error || 'خطا در parse', true);
                        reset();
                        return;
                    }
                    if (data.intent === 'unknown') {
                        setStatus(data.message || 'پشتیبانی نمی‌شود.', true);
                        reset();
                        return;
                    }
                    commandId = data.command_id;
                    fillPreview(data.preview);
                    if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
                    if (data.contact_candidates) renderCandidates(data.contact_candidates);
                    setStatus(data.can_confirm ? 'پیش‌نمایش آماده است.' : 'اطلاعات ناقص یا مبهم است.');
                })
                .catch(() => {
                    parseBtn.disabled = false;
                    setStatus('خطای شبکه.', true);
                });
        });

        confirmBtn?.addEventListener('click', () => {
            if (!commandId) return;
            confirmBtn.disabled = true;
            postJson(confirmUrl, { command_id: commandId }).then((res) => {
                const data = res.data;
                if (!data.ok) {
                    setStatus(data.error || 'ثبت نشد', true);
                    confirmBtn.disabled = false;
                    return;
                }
                setStatus('یادآوری ثبت شد.');
                if (data.url) {
                    window.location.href = data.url;
                }
            });
        });

        cancelBtn?.addEventListener('click', reset);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
