(function () {
    'use strict';

    const PARSE_LABEL_IDLE = 'بررسی';
    const PARSE_LABEL_LOADING = 'در حال بررسی…';
    const SUCCESS_RESET_MS = 4500;

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

    function isContactNotFound(data) {
        if (!data || data.intent !== 'create_reminder') return false;
        if (data.can_confirm) return false;
        const msg = (data.message || '').trim();
        return msg.indexOf('پیدا نشد') !== -1;
    }

    function hasAmbiguousContacts(data) {
        return !!(data.contact_candidates && data.contact_candidates.length);
    }

    function init() {
        const root = document.getElementById('crmNlCommand');
        if (!root) return;

        const parseUrl = root.dataset.parseUrl;
        const confirmUrl = root.dataset.confirmUrl;
        const resolveUrl = root.dataset.resolveUrl;
        const input = document.getElementById('crmNlCommandInput');
        const parseBtn = document.getElementById('crmNlCommandParseBtn');
        const parseLabel = parseBtn?.querySelector('.crm-nl-command__parse-label');
        const preview = document.getElementById('crmNlCommandPreview');
        const previewSheet = document.getElementById('crmNlPreviewSheet');
        const previewActions = document.getElementById('crmNlPreviewActions');
        const panelTitleText = preview?.querySelector('[data-panel-title-text]');
        const statusEl = document.getElementById('crmNlCommandStatus');
        const confirmBtn = document.getElementById('crmNlCommandConfirmBtn');
        const cancelBtn = document.getElementById('crmNlCommandCancelBtn');
        const candidatesEl = document.getElementById('crmNlCommandCandidates');
        const continueBtn = document.getElementById('crmNlContinueBtn');
        const noteRow = preview?.querySelector('[data-note-row]');
        const aiLabelEl = root.querySelector('[data-ai-label]');
        const modelInfoBtn = document.getElementById('crmNlModelInfo');
        const chipsWrap = root.querySelector('.crm-nl-command__chips');
        const composer = document.getElementById('crmNlComposer');
        const successEl = document.getElementById('crmNlSuccess');
        const successMeta = document.getElementById('crmNlSuccessMeta');
        const successLink = document.getElementById('crmNlSuccessLink');
        const backdrop = document.getElementById('crmNlSheetBackdrop');
        const aiDefault = root.dataset.aiDefault || '';

        let commandId = null;
        let pendingContactId = null;
        let successTimer = null;
        let lastParseText = '';

        function setAiModel(ai) {
            const label = (ai && ai.model_label) || aiDefault;
            if (aiLabelEl) aiLabelEl.textContent = label;
            if (modelInfoBtn) {
                const cached = ai && ai.cached ? ' (از کش)' : '';
                modelInfoBtn.title = 'مدل: ' + label + cached;
            }
        }

        function autoGrowInput() {
            if (!input) return;
            input.style.height = 'auto';
            const max = 76;
            const next = Math.min(input.scrollHeight, max);
            input.style.height = next + 'px';
        }

        function isMobileSheet() {
            return window.matchMedia('(max-width: 640px)').matches;
        }

        function setSheetOpen(on) {
            const sheet = !!on && isMobileSheet();
            root.classList.toggle('is-sheet-open', sheet);
            if (backdrop) backdrop.hidden = !sheet;
        }

        function setLoading(on) {
            root.classList.toggle('is-loading', !!on);
            if (parseBtn) parseBtn.disabled = !!on;
            if (parseLabel) parseLabel.textContent = on ? PARSE_LABEL_LOADING : PARSE_LABEL_IDLE;
        }

        function clearStatusActions() {
            if (!statusEl) return;
            statusEl.querySelectorAll('.crm-nl-command__feedback-action').forEach((el) => el.remove());
            statusEl.querySelectorAll('.crm-nl-command__feedback-hint').forEach((el) => el.remove());
        }

        function setStatus(msg, tone, options) {
            if (!statusEl) return;
            clearStatusActions();
            const text = (msg || '').trim();
            statusEl.hidden = !text && !(options && options.hint);
            statusEl.classList.remove('is-error', 'is-warn', 'is-success', 'is-info');
            if (tone) statusEl.classList.add(tone);

            const parts = [];
            if (text) {
                const main = document.createElement('span');
                main.className = 'crm-nl-command__feedback-text';
                main.textContent = text;
                parts.push(main);
            }
            statusEl.innerHTML = '';
            parts.forEach((p) => statusEl.appendChild(p));

            if (options && options.hint) {
                const hint = document.createElement('p');
                hint.className = 'crm-nl-command__feedback-hint';
                hint.textContent = options.hint;
                statusEl.appendChild(hint);
            }
            if (options && options.actionLabel && options.onAction) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'crm-nl-command__feedback-action';
                btn.textContent = options.actionLabel;
                btn.addEventListener('click', options.onAction);
                statusEl.appendChild(btn);
            }
        }

        function highlightChips(on) {
            if (chipsWrap) chipsWrap.classList.toggle('is-suggested', !!on);
        }

        function hidePreviewPanel() {
            if (preview) preview.hidden = true;
            setSheetOpen(false);
            preview?.classList.remove('is-ambiguous');
            if (previewSheet) previewSheet.classList.remove('is-hidden');
            if (previewActions) previewActions.hidden = false;
            if (continueBtn) continueBtn.hidden = true;
            if (candidatesEl) {
                candidatesEl.hidden = true;
                candidatesEl.innerHTML = '';
            }
            pendingContactId = null;
        }

        function clearPreview() {
            commandId = null;
            hidePreviewPanel();
            if (confirmBtn) confirmBtn.disabled = true;
        }

        function resetAll() {
            clearPreview();
            setAiModel(null);
            highlightChips(false);
            setStatus('');
            root.classList.remove('is-success-mode');
            if (successEl) successEl.hidden = true;
            if (composer) composer.hidden = false;
            if (input) {
                input.value = '';
                autoGrowInput();
            }
            if (successTimer) {
                window.clearTimeout(successTimer);
                successTimer = null;
            }
        }

        function focusCommand() {
            hidePreviewPanel();
            commandId = null;
            if (confirmBtn) confirmBtn.disabled = true;
            input?.focus();
        }

        function fillPreview(p) {
            if (!preview || !p) return;
            ['contact_name', 'due_at_display', 'title', 'note'].forEach((key) => {
                const el = preview.querySelector('[data-field="' + key + '"]');
                if (el) el.textContent = displayValue(p[key]);
            });
            const noteText = (p.note || '').trim();
            if (noteRow) noteRow.hidden = !noteText;
        }

        function showReadyPreview() {
            if (!preview) return;
            if (panelTitleText) panelTitleText.textContent = 'یادآوری آماده است';
            preview.classList.remove('is-ambiguous');
            if (previewSheet) previewSheet.classList.remove('is-hidden');
            if (previewActions) previewActions.hidden = false;
            if (continueBtn) continueBtn.hidden = true;
            preview.hidden = false;
            setSheetOpen(true);
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
            candidatesEl.innerHTML = '';
            const title = document.createElement('p');
            title.className = 'crm-nl-command__candidates-title';
            title.textContent = 'کدام مخاطب؟';
            candidatesEl.appendChild(title);

            const list = document.createElement('ul');
            list.className = 'crm-nl-command__candidate-list';
            candidates.forEach((c) => {
                const li = document.createElement('li');
                li.className = 'crm-nl-command__candidate-item';
                const radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = 'crmNlContactPick';
                radio.value = String(c.id);
                const label = document.createElement('span');
                label.textContent = c.name;
                li.appendChild(radio);
                li.appendChild(label);
                li.addEventListener('click', () => {
                    radio.checked = true;
                    pendingContactId = c.id;
                    list.querySelectorAll('.crm-nl-command__candidate-item').forEach((el) => {
                        el.classList.toggle('is-selected', el === li);
                    });
                    if (continueBtn) continueBtn.disabled = false;
                });
                list.appendChild(li);
            });
            candidatesEl.appendChild(list);
            candidatesEl.hidden = false;
            pendingContactId = null;
            if (continueBtn) {
                continueBtn.hidden = false;
                continueBtn.disabled = true;
            }
        }

        function showAmbiguousPanel(data) {
            if (!preview) return;
            commandId = data.command_id;
            if (panelTitleText) panelTitleText.textContent = 'کدام مخاطب؟';
            preview.classList.add('is-ambiguous');
            if (previewSheet) previewSheet.classList.add('is-hidden');
            if (previewActions) previewActions.hidden = true;
            if (confirmBtn) confirmBtn.disabled = true;
            fillPreview(data.preview);
            renderCandidates(data.contact_candidates);
            preview.hidden = false;
            setSheetOpen(true);
            setStatus('');
        }

        function runResolveContact() {
            if (!commandId || !pendingContactId) return;
            if (continueBtn) continueBtn.disabled = true;
            setStatus('در حال انتخاب مخاطب…', 'is-info');
            postJson(resolveUrl, { command_id: commandId, contact_id: pendingContactId })
                .then((res) => {
                    if (!res.data.ok) {
                        setStatus(res.data.error || 'خطا در انتخاب مخاطب', 'is-error');
                        if (continueBtn) continueBtn.disabled = false;
                        return;
                    }
                    fillPreview(res.data.preview);
                    if (confirmBtn) confirmBtn.disabled = !res.data.can_confirm;
                    if (candidatesEl) {
                        candidatesEl.hidden = true;
                        candidatesEl.innerHTML = '';
                    }
                    showReadyPreview();
                    if (res.data.can_confirm) {
                        setStatus('');
                    } else {
                        setStatus(res.data.hint || res.data.message || 'اطلاعات هنوز ناقص است.', 'is-warn');
                    }
                })
                .catch(() => {
                    setStatus('خطا در انتخاب مخاطب.', 'is-error');
                    if (continueBtn) continueBtn.disabled = false;
                });
        }

        function handleHttpError(res) {
            const data = res.data || {};
            const code = data.code || '';
            if (res.status === 429 || code === 'quota_exceeded' || code === 'feature_limit' || code === 'daily_limit') {
                setStatus(data.error || 'سهمیه امروز شما تمام شده است.', 'is-warn');
                return;
            }
            if (code === 'parse_failed') {
                setStatus(data.error || 'فرمان قابل تشخیص نبود. دوباره ساده‌تر بنویسید.', 'is-error');
                return;
            }
            if (res.status === 503 || code === 'provider_unavailable') {
                setStatus(data.error || 'سرویس هوشمند موقتاً در دسترس نیست.', 'is-error', {
                    actionLabel: 'تلاش دوباره',
                    onAction: () => {
                        if (lastParseText) {
                            if (input) input.value = lastParseText;
                            autoGrowInput();
                        }
                        runParse();
                    },
                });
                return;
            }
            if (res.status >= 500) {
                setStatus('سرویس هوشمند موقتاً در دسترس نیست.', 'is-error', {
                    actionLabel: 'تلاش دوباره',
                    onAction: runParse,
                });
                return;
            }
            setStatus(data.error || 'خطا در بررسی فرمان.', 'is-error');
        }

        function handleParseSuccess(data) {
            if (data.ai) setAiModel(data.ai);

            if (data.intent === 'unknown') {
                clearPreview();
                if (data.examples) applyExamplePhrases(data.examples);
                setStatus(data.message || 'فعلاً فرمان هوشمند فقط برای ثبت یادآوری فعال است.', 'is-info', {
                    hint: 'مثلاً بنویس: فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم',
                });
                highlightChips(true);
                return;
            }

            if (!data.command_id || !data.preview) {
                setStatus(data.hint || data.message || 'پاسخ سرور ناقص بود.', 'is-warn');
                clearPreview();
                return;
            }

            commandId = data.command_id;
            highlightChips(false);

            if (isContactNotFound(data)) {
                hidePreviewPanel();
                commandId = data.command_id;
                setStatus(data.message, 'is-warn', {
                    actionLabel: 'ویرایش فرمان',
                    onAction: focusCommand,
                });
                return;
            }

            if (hasAmbiguousContacts(data)) {
                showAmbiguousPanel(data);
                return;
            }

            fillPreview(data.preview);
            if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
            showReadyPreview();

            if (data.can_confirm) {
                setStatus('');
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
            lastParseText = text;
            setLoading(true);
            setStatus('');
            clearPreview();
            root.classList.remove('is-success-mode');
            if (successEl) successEl.hidden = true;
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
                    setStatus('سرویس هوشمند موقتاً در دسترس نیست.', 'is-error', {
                        actionLabel: 'تلاش دوباره',
                        onAction: runParse,
                    });
                })
                .finally(() => {
                    setLoading(false);
                });
        }

        parseBtn?.addEventListener('click', runParse);

        input?.addEventListener('input', autoGrowInput);
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
                    autoGrowInput();
                    input.focus();
                }
                highlightChips(false);
            });
        });

        continueBtn?.addEventListener('click', runResolveContact);

        backdrop?.addEventListener('click', () => {
            if (preview && !preview.hidden) {
                hidePreviewPanel();
                commandId = null;
                if (confirmBtn) confirmBtn.disabled = true;
            }
        });

        confirmBtn?.addEventListener('click', () => {
            if (!commandId) return;
            confirmBtn.disabled = true;
            setStatus('در حال ثبت…', 'is-info');
            postJson(confirmUrl, { command_id: commandId })
                .then((res) => {
                    const data = res.data;
                    if (!res.ok || !data.ok) {
                        setStatus(data.error || 'ثبت نشد', 'is-error');
                        confirmBtn.disabled = false;
                        return;
                    }
                    const dueEl = preview?.querySelector('[data-field="due_at_display"]');
                    const titleEl = preview?.querySelector('[data-field="title"]');
                    const meta = [dueEl?.textContent, titleEl?.textContent]
                        .map((s) => (s || '').trim())
                        .filter((s) => s && s !== '—')
                        .join(' — ');
                    if (successMeta) successMeta.textContent = meta || '';
                    if (successLink && data.url) {
                        successLink.href = data.url;
                        successLink.hidden = false;
                    } else if (successLink) {
                        successLink.hidden = true;
                    }
                    hidePreviewPanel();
                    setStatus('');
                    root.classList.add('is-success-mode');
                    if (successEl) successEl.hidden = false;
                    setSheetOpen(false);
                    if (successTimer) window.clearTimeout(successTimer);
                    successTimer = window.setTimeout(() => {
                        resetAll();
                    }, SUCCESS_RESET_MS);
                    if (data.url) {
                        window.setTimeout(() => {
                            window.location.href = data.url;
                        }, 1200);
                    }
                })
                .catch(() => {
                    setStatus('خطا در ثبت.', 'is-error');
                    confirmBtn.disabled = false;
                });
        });

        cancelBtn?.addEventListener('click', resetAll);

        autoGrowInput();
        setAiModel(null);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
