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

    function displayValue(val) {
        const t = (val || '').trim();
        return t || '—';
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
        const noteRow = preview?.querySelector('[data-note-row]');

        let commandId = null;

        function setLoading(on) {
            root.classList.toggle('is-loading', !!on);
            if (parseBtn) parseBtn.disabled = !!on;
        }

        function setStatus(msg, tone) {
            if (!statusEl) return;
            statusEl.hidden = !msg;
            statusEl.textContent = msg || '';
            statusEl.classList.remove('is-error', 'is-warn', 'is-success');
            if (tone) statusEl.classList.add(tone);
        }

        function fillPreview(p) {
            if (!preview || !p) return;
            const contact = preview.querySelector('[data-field="contact_name"]');
            const due = preview.querySelector('[data-field="due_at_display"]');
            const title = preview.querySelector('[data-field="title"]');
            const note = preview.querySelector('[data-field="note"]');
            if (contact) contact.textContent = displayValue(p.contact_name);
            if (due) due.textContent = displayValue(p.due_at_display);
            if (title) title.textContent = displayValue(p.title);
            const noteText = (p.note || '').trim();
            if (note) note.textContent = displayValue(noteText);
            if (noteRow) noteRow.hidden = !noteText;
            preview.hidden = false;
        }

        function reset() {
            commandId = null;
            setLoading(false);
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
            candidatesEl.innerHTML = '<p class="crm-nl-command__candidates-title">کدام مخاطب مدنظر شماست؟</p>';
            candidates.forEach((c) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'crm-nl-command__candidate';
                btn.textContent = c.name;
                btn.addEventListener('click', () => {
                    if (!commandId) return;
                    candidatesEl.querySelectorAll('.crm-nl-command__candidate').forEach((el) => {
                        el.classList.remove('is-selected');
                    });
                    btn.classList.add('is-selected');
                    postJson(resolveUrl, { command_id: commandId, contact_id: c.id }).then((res) => {
                        if (!res.data.ok) {
                            setStatus(res.data.error || 'خطا در انتخاب مخاطب', 'is-error');
                            return;
                        }
                        fillPreview(res.data.preview);
                        if (confirmBtn) confirmBtn.disabled = !res.data.can_confirm;
                        setStatus(res.data.can_confirm ? 'مخاطب انتخاب شد. آماده ثبت.' : 'هنوز اطلاعات ناقص است.', res.data.can_confirm ? 'is-success' : 'is-warn');
                    });
                });
                candidatesEl.appendChild(btn);
            });
            candidatesEl.hidden = false;
        }

        function runParse() {
            const text = (input?.value || '').trim();
            if (!text) {
                setStatus('متن فرمان را وارد کنید.', 'is-error');
                input?.focus();
                return;
            }
            setLoading(true);
            setStatus('در حال تحلیل فرمان…');
            postJson(parseUrl, { text, locale: 'fa-IR', timezone: 'Asia/Tehran' })
                .then((res) => {
                    setLoading(false);
                    const data = res.data;
                    if (!data.ok) {
                        setStatus(data.error || 'خطا در بررسی فرمان', 'is-error');
                        reset();
                        return;
                    }
                    if (data.intent === 'unknown') {
                        setStatus(data.message || 'این نوع فرمان هنوز پشتیبانی نمی‌شود.', 'is-warn');
                        reset();
                        return;
                    }
                    commandId = data.command_id;
                    fillPreview(data.preview);
                    if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
                    if (data.contact_candidates) renderCandidates(data.contact_candidates);
                    if (data.message && !data.can_confirm) {
                        setStatus(data.message, 'is-warn');
                    } else if (data.can_confirm) {
                        setStatus('پیش‌نمایش آماده است. در صورت نیاز ویرایش کنید یا تأیید بزنید.', 'is-success');
                    } else {
                        setStatus('برای ثبت، ابتدا مخاطب یا زمان را مشخص کنید.', 'is-warn');
                    }
                })
                .catch(() => {
                    setLoading(false);
                    setStatus('خطای ارتباط با سرور. دوباره تلاش کنید.', 'is-error');
                });
        }

        parseBtn?.addEventListener('click', runParse);

        input?.addEventListener('keydown', (ev) => {
            if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
                ev.preventDefault();
                runParse();
            }
        });

        root.querySelectorAll('[data-nl-sample]').forEach((chip) => {
            chip.addEventListener('click', () => {
                const sample = chip.getAttribute('data-nl-sample') || '';
                if (input) {
                    input.value = sample;
                    input.focus();
                }
            });
        });

        confirmBtn?.addEventListener('click', () => {
            if (!commandId) return;
            confirmBtn.disabled = true;
            setStatus('در حال ثبت یادآوری…');
            postJson(confirmUrl, { command_id: commandId }).then((res) => {
                const data = res.data;
                if (!data.ok) {
                    setStatus(data.error || 'ثبت انجام نشد', 'is-error');
                    confirmBtn.disabled = false;
                    return;
                }
                setStatus('یادآوری با موفقیت ثبت شد.', 'is-success');
                if (data.url) {
                    window.setTimeout(() => {
                        window.location.href = data.url;
                    }, 450);
                }
            });
        });

        cancelBtn?.addEventListener('click', reset);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
