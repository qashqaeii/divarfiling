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
        const aiLabelEl = document.querySelector('[data-ai-label]');
        const samplesWrap = root.querySelector('.crm-nl-command__samples');
        const aiDefault = root.dataset.aiDefault || '';

        let commandId = null;

        function setAiModel(ai) {
            if (!aiLabelEl) return;
            const label = (ai && ai.model_label) || aiDefault;
            aiLabelEl.textContent = label;
            if (ai && ai.cached) {
                aiLabelEl.setAttribute('title', 'نتیجه از کش');
            } else {
                aiLabelEl.removeAttribute('title');
            }
        }

        function setLoading(on) {
            root.classList.toggle('is-loading', !!on);
            if (parseBtn) parseBtn.disabled = !!on;
            if (input) input.disabled = !!on;
        }

        function setStatus(msg, tone) {
            if (!statusEl) return;
            const text = (msg || '').trim();
            statusEl.hidden = !text;
            statusEl.textContent = text;
            statusEl.classList.remove('is-error', 'is-warn', 'is-success');
            if (tone) statusEl.classList.add(tone);
        }

        function highlightSamples(on) {
            if (samplesWrap) samplesWrap.classList.toggle('is-suggested', !!on);
        }

        function clearPreview() {
            commandId = null;
            if (preview) preview.hidden = true;
            if (candidatesEl) {
                candidatesEl.hidden = true;
                candidatesEl.innerHTML = '';
            }
            if (confirmBtn) confirmBtn.disabled = true;
        }

        function resetAll() {
            clearPreview();
            setAiModel(null);
            highlightSamples(false);
            setStatus('');
        }

        function fillPreview(p) {
            if (!preview || !p) return;
            ['contact_name', 'due_at_display', 'title', 'note'].forEach((key) => {
                const el = preview.querySelector('[data-field="' + key + '"]');
                if (el) el.textContent = displayValue(p[key]);
            });
            const noteText = (p.note || '').trim();
            if (noteRow) noteRow.hidden = !noteText;
            preview.hidden = false;
            highlightSamples(false);
        }

        function applyExamplePhrases(examples) {
            if (!examples || !examples.length) return;
            const buttons = root.querySelectorAll('[data-nl-sample]');
            examples.forEach((phrase, idx) => {
                if (buttons[idx]) {
                    buttons[idx].setAttribute('data-nl-sample', phrase);
                }
            });
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
                        setStatus(
                            res.data.can_confirm ? 'مخاطب انتخاب شد.' : (res.data.hint || 'اطلاعات هنوز ناقص است.'),
                            res.data.can_confirm ? 'is-success' : 'is-warn',
                        );
                    });
                });
                candidatesEl.appendChild(btn);
            });
            candidatesEl.hidden = false;
        }

        function handleHttpError(res) {
            const data = res.data || {};
            const code = data.code || '';
            if (res.status === 429 || code === 'quota_exceeded' || code === 'feature_limit' || code === 'daily_limit') {
                setStatus(data.error || 'سقف روزانه فرمان هوشمند تمام شده است.', 'is-warn');
                return;
            }
            if (code === 'parse_failed') {
                setStatus(data.error || 'فرمان قابل تشخیص نبود. دوباره ساده‌تر بنویسید.', 'is-error');
                return;
            }
            if (res.status === 503 || code === 'provider_unavailable') {
                setStatus(
                    data.error || 'سرویس هوشمند موقتاً در دسترس نیست. دوباره تلاش کنید.',
                    'is-error',
                );
                return;
            }
            if (res.status >= 500) {
                setStatus('سرویس هوشمند موقتاً در دسترس نیست. دوباره تلاش کنید.', 'is-error');
                return;
            }
            setStatus(data.error || 'خطا در بررسی فرمان.', 'is-error');
        }

        function handleParseSuccess(data) {
            if (data.ai) setAiModel(data.ai);

            if (data.intent === 'unknown') {
                clearPreview();
                if (data.examples) applyExamplePhrases(data.examples);
                setStatus(data.message || 'فعلاً فرمان هوشمند فقط برای ثبت یادآوری فعال است.', 'is-warn');
                highlightSamples(true);
                return;
            }

            if (!data.command_id || !data.preview) {
                setStatus(data.hint || data.message || 'پاسخ سرور ناقص بود.', 'is-warn');
                clearPreview();
                return;
            }

            commandId = data.command_id;
            fillPreview(data.preview);
            if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
            if (data.contact_candidates && data.contact_candidates.length) {
                renderCandidates(data.contact_candidates);
            }

            if (data.can_confirm) {
                setStatus('پیش‌نمایش آماده است.', 'is-success');
            } else if (data.message) {
                setStatus(data.message, 'is-warn');
            } else if (data.hint) {
                setStatus(data.hint, 'is-warn');
            } else {
                setStatus('برای ثبت، زمان یا مخاطب را مشخص کنید.', 'is-warn');
            }
        }

        function runParse() {
            const text = (input?.value || '').trim();
            if (!text) {
                setStatus('یک جمله بنویسید.', 'is-error');
                input?.focus();
                return;
            }
            setLoading(true);
            setStatus('در حال تحلیل…');
            clearPreview();
            postJson(parseUrl, { text, locale: 'fa-IR', timezone: 'Asia/Tehran' })
                .then((res) => {
                    if (!res.ok || !res.data.ok) {
                        clearPreview();
                        handleHttpError(res);
                        return;
                    }
                    handleParseSuccess(res.data);
                })
                .catch(() => {
                    clearPreview();
                    setStatus('سرویس هوشمند موقتاً در دسترس نیست. دوباره تلاش کنید.', 'is-error');
                })
                .finally(() => {
                    setLoading(false);
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
                highlightSamples(false);
            });
        });

        confirmBtn?.addEventListener('click', () => {
            if (!commandId) return;
            confirmBtn.disabled = true;
            setStatus('در حال ثبت…');
            postJson(confirmUrl, { command_id: commandId })
                .then((res) => {
                    const data = res.data;
                    if (!res.ok || !data.ok) {
                        setStatus(data.error || 'ثبت نشد', 'is-error');
                        confirmBtn.disabled = false;
                        return;
                    }
                    setStatus('ثبت شد.', 'is-success');
                    if (data.url) {
                        window.setTimeout(() => {
                            window.location.href = data.url;
                        }, 400);
                    }
                })
                .catch(() => {
                    setStatus('خطا در ثبت.', 'is-error');
                    confirmBtn.disabled = false;
                });
        });

        cancelBtn?.addEventListener('click', resetAll);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
