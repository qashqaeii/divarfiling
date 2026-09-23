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

    function initSmartCommand(root) {
        if (!root || root.dataset.scInitialized === '1') return;
        root.dataset.scInitialized = '1';

        const parseUrl = root.dataset.parseUrl;
        const confirmUrl = root.dataset.confirmUrl;
        const resolveUrl = root.dataset.resolveUrl;
        const allowedIntent = (root.dataset.allowedIntent || '').trim();
        const wrongIntentMessage = (root.dataset.wrongIntentMessage || '').trim();
        const navTodayUrl = root.dataset.navToday || '';
        const navContactsUrl = root.dataset.navContacts || '';
        const navPropertiesUrl = root.dataset.navProperties || '';
        const enableContactResolve = root.dataset.enableContactResolve === '1';

        const input = root.querySelector('[data-sc="input"]');
        const parseBtn = root.querySelector('[data-sc="parse-btn"]');
        const parseLabel = parseBtn?.querySelector('.crm-nl-command__parse-label');
        const preview = root.querySelector('[data-sc="preview"]');
        const ambigStep = root.querySelector('[data-sc="ambig-step"]');
        const readyStep = root.querySelector('[data-sc="ready-step"]');
        const ambigLede = root.querySelector('[data-sc="ambig-lede"]');
        const successEl = root.querySelector('[data-sc="success"]');
        const successMeta = root.querySelector('[data-sc="success-meta"]');
        const successLink = root.querySelector('[data-sc="success-link"]');
        const panelTitleText = readyStep?.querySelector('[data-sc="panel-title-text"]');
        const successTitleText = successEl?.querySelector('[data-sc="success-title-text"]');
        const reminderRows = readyStep?.querySelectorAll('.crm-nl-command__sheet-reminder');
        const contactRows = readyStep?.querySelectorAll('.crm-nl-command__sheet-contact');
        const propertyRows = readyStep?.querySelectorAll('.crm-nl-command__sheet-property');
        const contactNoteRow = readyStep?.querySelector('[data-contact-note-row]');
        const propertyNoteRow = readyStep?.querySelector('[data-property-note-row]');
        const propertyFeaturesRow = readyStep?.querySelector('[data-property-features-row]');
        const propertySaleRow = readyStep?.querySelector('[data-property-sale-row]');
        const propertyDepositRow = readyStep?.querySelector('[data-property-deposit-row]');
        const propertyRentRow = readyStep?.querySelector('[data-property-rent-row]');
        const statusEl = root.querySelector('[data-sc="status"]');
        const confirmBtn = root.querySelector('[data-sc="confirm-btn"]');
        const cancelBtn = root.querySelector('[data-sc="cancel-btn"]');
        const candidatesEl = root.querySelector('[data-sc="candidates"]');
        const continueBtn = root.querySelector('[data-sc="continue-btn"]');
        const noteRow = readyStep?.querySelector('[data-note-row]');
        const aiLabelEl = root.querySelector('[data-sc="ai-label"]');
        const modelInfoBtn = root.querySelector('[data-sc="model-info"]');
        const chipsWrap = root.querySelector('.crm-nl-command__chips');
        const composer = root.querySelector('[data-sc="composer"]');
        const backdrop = root.querySelector('[data-sc="backdrop"]');
        const previewSummary = readyStep?.querySelector('[data-sc="preview-summary"]');
        const previewSummaryLine = readyStep?.querySelector('[data-sc="preview-summary-line"]');
        const previewSummarySub = readyStep?.querySelector('[data-sc="preview-summary-sub"]');
        const aiDefault = root.dataset.aiDefault || '';

        function isWrongIntent(data) {
            if (!allowedIntent || !data || !data.intent) return false;
            if (data.intent === 'unknown') return false;
            return data.intent !== allowedIntent;
        }

        function wrongIntentNav(intent) {
            if (intent === 'create_reminder' && navTodayUrl) {
                return { label: 'رفتن به کارهای امروز', url: navTodayUrl };
            }
            if (intent === 'create_contact' && navContactsUrl) {
                return { label: 'رفتن به مخاطبین', url: navContactsUrl };
            }
            if (intent === 'create_personal_property' && navPropertiesUrl) {
                return { label: 'رفتن به فایل‌های شخصی', url: navPropertiesUrl };
            }
            return null;
        }

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
            root.querySelectorAll('.crm-nl-command__chip').forEach((c) => {
                c.classList.remove('is-active');
            });
            syncInputState();
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
            const isProperty = intent === 'create_personal_property';
            reminderRows?.forEach((row) => {
                row.hidden = isContact || isProperty;
            });
            contactRows?.forEach((row) => {
                row.hidden = !isContact;
            });
            propertyRows?.forEach((row) => {
                row.hidden = !isProperty;
            });
            if (panelTitleText) {
                if (isContact) {
                    panelTitleText.textContent = 'مخاطب آماده ثبت است';
                } else if (isProperty) {
                    panelTitleText.textContent = 'فایل آماده ثبت است';
                } else {
                    panelTitleText.textContent = 'یادآوری آماده است';
                }
            }
            if (successTitleText) {
                if (isContact) {
                    successTitleText.textContent = 'مخاطب ثبت شد';
                } else if (isProperty) {
                    successTitleText.textContent = 'فایل شخصی ثبت شد';
                } else {
                    successTitleText.textContent = 'یادآوری ثبت شد';
                }
            }
            if (successLink) {
                if (isContact) {
                    successLink.textContent = 'مشاهده مخاطب';
                } else if (isProperty) {
                    successLink.textContent = 'مشاهده فایل';
                } else {
                    successLink.textContent = 'مشاهده یادآوری';
                }
            }
        }

        function joinPreviewParts(parts) {
            return parts
                .map((s) => (s || '').trim())
                .filter((s) => s && s !== '—')
                .join(' · ');
        }

        function fillPreviewSummary(p, intent) {
            if (!previewSummary || !previewSummaryLine || !p) return;
            const effective = intent || currentIntent || 'create_reminder';
            let line = '';
            let sub = '';
            if (effective === 'create_personal_property') {
                line = (p.type_deal_display || '').trim();
                sub = joinPreviewParts([
                    p.location_display,
                    p.specs_display,
                    p.sale_price_display,
                    p.deposit_display,
                    p.rent_display,
                ]);
            } else if (effective === 'create_contact') {
                line = (p.name || '').trim();
                sub = joinPreviewParts([
                    p.phone_display,
                    p.customer_type,
                    p.areas_display,
                    p.budget_display,
                ]);
            } else {
                line = (p.due_at_display || p.title || '').trim();
                const titleExtra = (p.title || '').trim();
                sub = joinPreviewParts([
                    p.contact_name,
                    titleExtra && titleExtra !== line ? titleExtra : '',
                ]);
            }
            if (!line) {
                previewSummary.hidden = true;
                return;
            }
            previewSummary.hidden = false;
            previewSummaryLine.textContent = line;
            if (previewSummarySub) {
                previewSummarySub.textContent = sub;
                previewSummarySub.hidden = !sub;
            }
        }

        function fillPropertyPreview(p) {
            if (!readyStep || !p) return;
            const setRow = (selector, val) => {
                const el = readyStep.querySelector('[data-field="' + selector + '"]');
                if (el) el.textContent = val || '—';
            };
            setRow('type_deal_display', (p.type_deal_display || '').trim());
            setRow('location_display', (p.location_display || '').trim());
            setRow('specs_display', (p.specs_display || '').trim());
            const pos = (p.features_positive || []).join(' · ');
            const neg = (p.features_negative || []).join(' · ');
            const feat = [pos, neg].filter(Boolean).join(' · ');
            setRow('features_display', feat);
            if (propertyFeaturesRow) propertyFeaturesRow.hidden = !feat;
            const sale = (p.sale_price_display || '').trim();
            const deposit = (p.deposit_display || '').trim();
            const rent = (p.rent_display || '').trim();
            setRow('sale_price_display', sale);
            setRow('deposit_display', deposit);
            setRow('rent_display', rent);
            if (propertySaleRow) propertySaleRow.hidden = !sale;
            if (propertyDepositRow) propertyDepositRow.hidden = !deposit;
            if (propertyRentRow) propertyRentRow.hidden = !rent;
            propertyRows?.forEach((row) => {
                if (row === propertyFeaturesRow || row === propertySaleRow
                    || row === propertyDepositRow || row === propertyRentRow
                    || row === propertyNoteRow) {
                    return;
                }
                const dd = row.querySelector('dd');
                const t = (dd?.textContent || '').trim();
                row.hidden = !t || t === '—';
            });
            const notesText = (p.notes || '').trim();
            setRow('property_notes', notesText);
            if (propertyNoteRow) propertyNoteRow.hidden = !notesText;
            fillPreviewSummary(p, 'create_personal_property');
        }

        function isIncompleteProperty(data) {
            if (!data || data.intent !== 'create_personal_property' || data.can_confirm) return false;
            const missing = data.missing_fields || [];
            const ambiguous = data.ambiguous_fields || [];
            return missing.length > 0 || ambiguous.length > 0;
        }

        function incompletePropertyFeedback(data) {
            return {
                main: data.hint || 'برای ثبت فایل، حداقل متراژ و نوع معامله را مشخص کنید.',
                hint: data.hint_example || 'مثلاً: آپارتمان ۱۲۰ متری پونک برای فروش، ۱۲ میلیارد.',
            };
        }

        function fillPreview(p, intent) {
            if (!readyStep || !p) return;
            setPreviewMode(intent || currentIntent || 'create_reminder');
            if (intent === 'create_personal_property' || currentIntent === 'create_personal_property') {
                fillPropertyPreview(p);
                return;
            }
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
                fillPreviewSummary(p, 'create_contact');
                return;
            }
            ['contact_name', 'due_at_display', 'title', 'note'].forEach((key) => {
                const el = readyStep.querySelector('[data-field="' + key + '"]');
                if (el) el.textContent = displayValue(p[key]);
            });
            const noteText = (p.note || '').trim();
            if (noteRow) noteRow.hidden = !noteText;
            fillPreviewSummary(p, 'create_reminder');
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
                setStatus(data.message || 'فرمان پشتیبانی نمی‌شود.', 'is-info');
                highlightChips(true);
                return;
            }

            if (isWrongIntent(data)) {
                clearPreview();
                commandId = null;
                const nav = wrongIntentNav(data.intent);
                const opts = { hint: 'می‌توانید در بخش مربوطه دوباره بنویسید.' };
                if (nav) {
                    opts.actionLabel = nav.label;
                    opts.onAction = () => { window.location.href = nav.url; };
                }
                setStatus(wrongIntentMessage || 'این فرمان در این بخش پشتیبانی نمی‌شود.', 'is-info', opts);
                return;
            }

            if (data.intent === 'create_personal_property') {
                commandId = data.command_id;
                if (isIncompleteProperty(data)) {
                    hidePreviewPanel();
                    const fb = incompletePropertyFeedback(data);
                    setStatus(fb.main, 'is-info', {
                        hint: fb.hint,
                        actionLabel: 'ویرایش فرمان',
                        onAction: focusCommand,
                    });
                    return;
                }
                fillPreview(data.preview, 'create_personal_property');
                if (confirmBtn) confirmBtn.disabled = !data.can_confirm;
                showReadyPreview('create_personal_property');
                if (data.can_confirm) {
                    setStatus('');
                } else if (data.hint) {
                    setStatus(data.hint, 'is-warn');
                }
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

            if (enableContactResolve && hasAmbiguousContacts(data)) {
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
            const quotaRem = parseInt(root.dataset.quotaRemaining || '', 10);
            if (!Number.isNaN(quotaRem) && quotaRem <= 0) {
                setStatus('سهمیه بررسی امروز تمام شده است.', 'is-error');
                return;
            }
            const text = (input?.value || '').trim();
            if (!text) {
                setStatus('یک جمله بنویسید.', 'is-error');
                input?.focus();
                return;
            }
            lastParseText = text;
            const mergeIntents = ['create_contact', 'create_personal_property'];
            const resumeIntent = currentIntent;
            const canMerge = allowedIntent && mergeIntents.indexOf(allowedIntent) !== -1
                && resumeIntent === allowedIntent;
            const resumeCommandId = commandId && canMerge ? commandId : null;
            setLoading(true);
            setStatus('');
            clearPreview();
            if (resumeCommandId) {
                commandId = resumeCommandId;
                currentIntent = resumeIntent;
            }
            root.classList.remove('is-success-mode');
            if (successEl) successEl.hidden = true;
            const parseBody = { text, locale: 'fa-IR', timezone: 'Asia/Tehran' };
            if (commandId && allowedIntent && currentIntent === allowedIntent
                && mergeIntents.indexOf(allowedIntent) !== -1) {
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

        function syncInputState() {
            const has = !!(input && (input.value || '').trim());
            root.classList.toggle('is-has-input', has);
        }

        input?.addEventListener('input', () => {
            autoGrowInput();
            syncInputState();
        });
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
                    syncInputState();
                    input.focus();
                }
                root.querySelectorAll('.crm-nl-command__chip').forEach((c) => {
                    c.classList.toggle('is-active', c === chip);
                });
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
                    } else if (data.entity_type === 'property') {
                        const titleEl = readyStep?.querySelector('[data-field="type_deal_display"]');
                        meta = (titleEl?.textContent || '').trim();
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

        const qRem = parseInt(root.dataset.quotaRemaining || '', 10);
        if (!Number.isNaN(qRem) && qRem <= 2) {
            root.classList.add('is-quota-low');
        }
        if (!Number.isNaN(qRem) && qRem <= 0) {
            root.classList.add('is-quota-empty');
            if (parseBtn) parseBtn.disabled = true;
        }

        autoGrowInput();
        syncInputState();
        setAiModel(null);
    }

    function initAll() {
        document.querySelectorAll('[data-crm-smart-command]').forEach(initSmartCommand);
    }

    window.CrmSmartCommand = {
        init: initSmartCommand,
        initAll,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
