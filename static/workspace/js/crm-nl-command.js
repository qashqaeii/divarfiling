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

    function isIncompleteReminder(data) {
        if (!data || data.intent !== 'create_reminder' || data.can_confirm) return false;
        if (isContactNotFound(data) || hasAmbiguousContacts(data)) return false;
        const missing = data.missing_fields || [];
        const ambiguous = data.ambiguous_fields || [];
        if (missing.length > 0) return true;
        return ambiguous.indexOf('due_at') !== -1;
    }

    function incompleteReminderFeedback(data) {
        const missing = data.missing_fields || [];
        const ambiguous = data.ambiguous_fields || [];
        const example = 'مثلاً: فردا ساعت ۱۰ به احمدی زنگ بزنم.';
        if (ambiguous.indexOf('due_at') !== -1) {
            return {
                main: data.hint || data.message || 'زمان یادآوری در گذشته است یا نامعتبر است.',
                hint: example,
            };
        }
        if (missing.indexOf('date_text') !== -1 || missing.indexOf('time_text') !== -1) {
            return {
                main: data.hint || data.message || 'زمان یادآوری را مشخص کنید.',
                hint: example,
            };
        }
        if (data.hint && data.hint.indexOf('کامل') !== -1) {
            return { main: 'چی رو یادت بندازم؟', hint: example };
        }
        if (data.hint || data.message) {
            return { main: data.hint || data.message, hint: example };
        }
        return { main: 'چی رو یادت بندازم؟', hint: example };
    }

    function faCount(n) {
        return Number(n).toLocaleString('fa-IR');
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
        const ambigStep = document.getElementById('crmNlAmbigStep');
        const readyStep = document.getElementById('crmNlReadyStep');
        const ambigLede = document.getElementById('crmNlAmbigLede');
        const previewSheet = document.getElementById('crmNlPreviewSheet');
        const previewActions = document.getElementById('crmNlPreviewActions');
        const successEl = document.getElementById('crmNlSuccess');
        const successMeta = document.getElementById('crmNlSuccessMeta');
        const successLink = document.getElementById('crmNlSuccessLink');
        const panelTitleText = readyStep?.querySelector('[data-panel-title-text]');
        const successTitleText = successEl?.querySelector('[data-success-title-text]');
        const reminderRows = readyStep?.querySelectorAll('.crm-nl-command__sheet-reminder');
        const contactRows = readyStep?.querySelectorAll('.crm-nl-command__sheet-contact');
        const contactNoteRow = readyStep?.querySelector('[data-contact-note-row]');
        const statusEl = document.getElementById('crmNlCommandStatus');
        const confirmBtn = document.getElementById('crmNlCommandConfirmBtn');
        const cancelBtn = document.getElementById('crmNlCommandCancelBtn');
        const candidatesEl = document.getElementById('crmNlCommandCandidates');
        const continueBtn = document.getElementById('crmNlContinueBtn');
        const noteRow = readyStep?.querySelector('[data-note-row]');
        const aiLabelEl = root.querySelector('[data-ai-label]');
        const modelInfoBtn = document.getElementById('crmNlModelInfo');
        const chipsWrap = root.querySelector('.crm-nl-command__chips');
        const composer = document.getElementById('crmNlComposer');
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
            if (ambigStep) ambigStep.hidden = true;
            if (readyStep) readyStep.hidden = true;
            if (continueBtn) continueBtn.disabled = true;
            if (candidatesEl) candidatesEl.innerHTML = '';
            if (ambigLede) ambigLede.textContent = '';
            pendingContactId = null;
        }

        function clearPreview() {
            commandId = null;
            currentIntent = null;
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

        let currentIntent = null;

        function setPreviewMode(intent) {
            currentIntent = intent;
            const isContact = intent === 'create_contact';
            reminderRows?.forEach((row) => {
                row.hidden = isContact;
            });
            contactRows?.forEach((row) => {
                row.hidden = !isContact;
            });
            if (panelTitleText) {
                panelTitleText.textContent = isContact ? 'مخاطب آماده ثبت است' : 'یادآوری آماده است';
            }
            if (successTitleText) {
                successTitleText.textContent = isContact ? 'مخاطب ثبت شد' : 'یادآوری ثبت شد';
            }
            if (successLink) {
                successLink.textContent = isContact ? 'مشاهده مخاطب' : 'مشاهده یادآوری';
            }
        }

        function fillPreview(p, intent) {
            if (!readyStep || !p) return;
            setPreviewMode(intent || currentIntent || 'create_reminder');
            if (intent === 'create_contact' || currentIntent === 'create_contact') {
                const contactFields = [
                    'name', 'phone_display', 'customer_type', 'areas_display',
                    'area_range_display', 'budget_display', 'rooms_display', 'notes',
                ];
                contactFields.forEach((key) => {
                    const el = readyStep.querySelector('[data-field="' + key + '"]');
                    if (!el) return;
                    const val = (p[key] || '').trim();
                    const row = el.closest('.crm-nl-command__sheet-contact');
                    if (row && !row.hasAttribute('data-contact-note-row')) {
                        row.hidden = !val;
                    }
                    el.textContent = val || '—';
                });
                const notesText = (p.notes || '').trim();
                if (contactNoteRow) contactNoteRow.hidden = !notesText;
                return;
            }
            ['contact_name', 'due_at_display', 'title', 'note'].forEach((key) => {
                const el = readyStep.querySelector('[data-field="' + key + '"]');
                if (el) el.textContent = displayValue(p[key]);
            });
            const noteText = (p.note || '').trim();
            if (noteRow) noteRow.hidden = !noteText;
        }

        function isDuplicateContact(data) {
            return !!(data && data.duplicate_contact && data.existing_contact);
        }

        function isIncompleteContact(data) {
            if (!data || data.intent !== 'create_contact' || data.can_confirm) return false;
            if (isDuplicateContact(data)) return false;
            const missing = data.missing_fields || [];
            const ambiguous = data.ambiguous_fields || [];
            return missing.length > 0 || ambiguous.length > 0;
        }

        function incompleteContactFeedback(data) {
            const name = (data.preview && data.preview.name) || '';
            if ((data.missing_fields || []).indexOf('phone') !== -1 && name) {
                return { main: 'شماره تماس ' + name + ' را وارد کنید.', hint: 'مثلاً: ۰۹۱۲۱۲۳۴۵۶۷' };
            }
            return {
                main: data.hint || data.message || 'اطلاعات مخاطب کامل نیست.',
                hint: 'می‌توانید همان فرمان را با جزئیات بیشتر دوباره بنویسید.',
            };
        }

        function showReadyPreview(intent) {
            if (!preview) return;
            if (ambigStep) ambigStep.hidden = true;
            if (readyStep) readyStep.hidden = false;
            setPreviewMode(intent || currentIntent);
            if (candidatesEl) candidatesEl.innerHTML = '';
            if (continueBtn) continueBtn.disabled = true;
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

        function selectCandidateCard(card) {
            if (!candidatesEl || !card) return;
            pendingContactId = parseInt(card.dataset.contactId, 10);
            candidatesEl.querySelectorAll('.crm-nl-command__candidate-card').forEach((el) => {
                const on = el === card;
                el.classList.toggle('is-selected', on);
                el.setAttribute('aria-checked', on ? 'true' : 'false');
            });
            if (continueBtn) continueBtn.disabled = !pendingContactId;
        }

        function renderCandidates(candidates, searchName) {
            if (!candidatesEl || !candidates || !candidates.length) return;
            candidatesEl.innerHTML = '';
            const name = (searchName || '').trim() || 'موردنظر';
            if (ambigLede) {
                ambigLede.textContent =
                    faCount(candidates.length) + ' مخاطب با نام «' + name + '» پیدا شد.';
            }
            candidates.forEach((c) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'crm-nl-command__candidate-card';
                btn.setAttribute('role', 'radio');
                btn.setAttribute('aria-checked', 'false');
                btn.dataset.contactId = String(c.id);

                const mark = document.createElement('span');
                mark.className = 'crm-nl-command__candidate-mark';
                mark.setAttribute('aria-hidden', 'true');

                const body = document.createElement('span');
                body.className = 'crm-nl-command__candidate-body';

                const nameEl = document.createElement('span');
                nameEl.className = 'crm-nl-command__candidate-name';
                nameEl.textContent = c.name;

                const meta = document.createElement('span');
                meta.className = 'crm-nl-command__candidate-meta';
                meta.textContent = 'مخاطب CRM';

                body.appendChild(nameEl);
                body.appendChild(meta);
                btn.appendChild(mark);
                btn.appendChild(body);
                btn.addEventListener('click', () => selectCandidateCard(btn));
                candidatesEl.appendChild(btn);
            });
            pendingContactId = null;
            if (continueBtn) continueBtn.disabled = true;
        }

        function showAmbiguousPanel(data) {
            if (!preview) return;
            commandId = data.command_id;
            if (readyStep) readyStep.hidden = true;
            if (ambigStep) ambigStep.hidden = false;
            if (confirmBtn) confirmBtn.disabled = true;
            fillPreview(data.preview, 'create_reminder');
            const searchName = (data.preview && data.preview.contact_name) || '';
            renderCandidates(data.contact_candidates, searchName);
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
                    fillPreview(res.data.preview, 'create_reminder');
                    if (confirmBtn) confirmBtn.disabled = !res.data.can_confirm;
                    showReadyPreview('create_reminder');
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
                setStatus(data.message || 'فرمان پشتیبانی نمی‌شود.', 'is-info', {
                    hint: 'مثلاً: فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم یا حسینی رو ذخیره کن',
                });
                highlightChips(true);
                return;
            }

            if (data.intent === 'create_contact') {
                commandId = data.command_id;
                if (isDuplicateContact(data)) {
                    commandId = null;
                    hidePreviewPanel();
                    const ex = data.existing_contact;
                    setStatus(data.message || 'این شماره قبلاً ثبت شده است.', 'is-warn', {
                        actionLabel: 'مشاهده مخاطب',
                        onAction: () => {
                            if (ex && ex.url) window.location.href = ex.url;
                        },
                    });
                    return;
                }
                if (isIncompleteContact(data)) {
                    hidePreviewPanel();
                    const fb = incompleteContactFeedback(data);
                    setStatus(fb.main, 'is-info', {
                        hint: fb.hint,
                        actionLabel: 'ویرایش فرمان',
                        onAction: focusCommand,
                    });
                    return;
                }
                fillPreview(data.preview, 'create_contact');
                if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
                showReadyPreview('create_contact');
                if (data.warning) {
                    setStatus(data.warning, 'is-warn');
                } else if (data.can_confirm) {
                    setStatus('');
                } else if (data.hint) {
                    setStatus(data.hint, 'is-warn');
                }
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

            if (isIncompleteReminder(data)) {
                hidePreviewPanel();
                commandId = null;
                const fb = incompleteReminderFeedback(data);
                setStatus(fb.main, 'is-info', {
                    hint: fb.hint,
                    actionLabel: 'ویرایش فرمان',
                    onAction: focusCommand,
                });
                return;
            }

            fillPreview(data.preview, 'create_reminder');
            if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
            showReadyPreview('create_reminder');

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
            const resumeCommandId = commandId && currentIntent === 'create_contact' ? commandId : null;
            setLoading(true);
            setStatus('');
            clearPreview();
            if (resumeCommandId) {
                commandId = resumeCommandId;
                currentIntent = 'create_contact';
            }
            root.classList.remove('is-success-mode');
            if (successEl) successEl.hidden = true;
            const parseBody = { text, locale: 'fa-IR', timezone: 'Asia/Tehran' };
            if (commandId && currentIntent === 'create_contact') {
                parseBody.command_id = commandId;
            }
            postJson(parseUrl, parseBody)
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
                    let meta = '';
                    if (data.entity_type === 'contact') {
                        const nameEl = readyStep?.querySelector('[data-field="name"]');
                        meta = (nameEl?.textContent || '').trim();
                        if (meta === '—') meta = '';
                    } else {
                        const dueEl = readyStep?.querySelector('[data-field="due_at_display"]');
                        const titleEl = readyStep?.querySelector('[data-field="title"]');
                        meta = [dueEl?.textContent, titleEl?.textContent]
                            .map((s) => (s || '').trim())
                            .filter((s) => s && s !== '—')
                            .join(' — ');
                    }
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
