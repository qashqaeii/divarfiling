(function () {
    'use strict';

    var page = document.getElementById('maa-page');
    if (!page) return;

    var previewUrl = page.dataset.previewUrl || '';
    var sendUrl = page.dataset.sendUrl || '';
    var automationUrl = page.dataset.automationUrl || '';
    var automationDetailUrl = page.dataset.automationDetailUrl || '';
    var automationPreviewUrl = page.dataset.automationPreviewUrl || '';
    var automationRunUrl = page.dataset.automationRunUrl || '';
    var automationSettingsUrl = page.dataset.automationSettingsUrl || '';
    var automationMessagePreviewUrl = page.dataset.automationMessagePreviewUrl || '';
    var automationTestSendUrl = page.dataset.automationTestSendUrl || '';
    var rules = window.maaAutomationRules || [];

    var sendModal = document.getElementById('maa-send-modal');
    var autoModal = document.getElementById('maa-auto-modal');
    var currentInsight = null;
    var currentRule = null;
    var currentRuleDetail = null;

    function csrfToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function openModal(modal) {
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('maa-modal-open');
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        if (!document.querySelector('.maa-modal:not([hidden])')) {
            document.body.classList.remove('maa-modal-open');
        }
    }

    document.querySelectorAll('[data-close-modal]').forEach(function (el) {
        el.addEventListener('click', function () {
            closeModal(el.closest('.maa-modal'));
        });
    });

    function findRule(key) {
        return rules.find(function (r) { return r.key === key; }) || null;
    }

    function loadPreview(insightKey) {
        if (!previewUrl || !insightKey) return Promise.resolve(null);
        return fetch(previewUrl + '?insight=' + encodeURIComponent(insightKey), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        }).then(function (r) { return r.json(); });
    }

    function loadAutomationDetail(ruleKey) {
        if (!automationDetailUrl || !ruleKey) return Promise.resolve(null);
        return fetch(automationDetailUrl + '?rule_key=' + encodeURIComponent(ruleKey), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        }).then(function (r) { return r.json(); });
    }

    function loadAutomationPreview(ruleKey) {
        if (!automationPreviewUrl || !ruleKey) return Promise.resolve(null);
        return fetch(automationPreviewUrl + '?rule_key=' + encodeURIComponent(ruleKey), {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' }
        }).then(function (r) { return r.json(); });
    }

    function renderRecipientList(listEl, data) {
        if (!listEl) return;
        listEl.classList.remove('is-loading');

        if (!data || !data.ok) {
            listEl.innerHTML = '<p class="maa-recipient-empty">' + escapeHtml(data && data.error ? data.error : 'خطا در بارگذاری گیرندگان.') + '</p>';
            return;
        }

        if (data.preview_note && (!data.recipients || !data.recipients.length)) {
            listEl.innerHTML = '<p class="maa-recipient-empty">' + escapeHtml(data.preview_note) + '</p>';
            return;
        }

        if (!data.recipients || !data.recipients.length) {
            listEl.innerHTML = '<p class="maa-recipient-empty">گیرنده‌ای برای نمایش نیست.</p>';
            return;
        }

        var rows = data.recipients.slice(0, 30).map(function (r) {
            var display = r.display || r.name || r.user_display || r.masked_phone || 'کاربر';
            var detail = r.detail || r.product || '';
            var meta = r.masked_phone && display !== r.masked_phone ? r.masked_phone : '';
            var metaHtml = meta ? '<span class="maa-recipient-meta">' + escapeHtml(meta) + '</span>' : '';
            var detailHtml = detail ? '<span class="maa-recipient-detail">' + escapeHtml(detail) + '</span>' : '';
            return (
                '<div class="maa-recipient-row">' +
                    '<span class="maa-recipient-name">' + escapeHtml(display) + '</span>' +
                    detailHtml +
                    metaHtml +
                '</div>'
            );
        }).join('');

        var more = '';
        if (data.count > 30) {
            more = '<p class="maa-recipient-more">+' + escapeHtml(String(data.count - 30)) + ' نفر دیگر</p>';
        }

        listEl.innerHTML = rows + more;
    }

    function renderAutomationAudience(listEl, audience) {
        if (!listEl) return;
        listEl.classList.remove('is-loading');

        if (!audience || !audience.recipients || !audience.recipients.length) {
            listEl.innerHTML = '<p class="maa-recipient-empty">در حال حاضر مخاطبی واجد شرایط نیست.</p>';
            return;
        }

        var rows = audience.recipients.slice(0, 50).map(function (r) {
            var display = r.display || r.name || r.masked_phone || 'کاربر';
            var detail = r.detail || '';
            var statusClass = r.status === 'ready' ? 'is-ready' : 'is-skip';
            var statusLabel = r.status_label || (r.status === 'ready' ? 'آماده ارسال' : 'Skip');
            var detailHtml = detail ? '<span class="maa-recipient-detail">' + escapeHtml(detail) + '</span>' : '';
            return (
                '<div class="maa-recipient-row maa-recipient-row--status ' + statusClass + '">' +
                    '<div class="maa-recipient-main">' +
                        '<span class="maa-recipient-name">' + escapeHtml(display) + '</span>' +
                        detailHtml +
                    '</div>' +
                    '<span class="maa-recipient-status">' + escapeHtml(statusLabel) + '</span>' +
                '</div>'
            );
        }).join('');

        var more = '';
        if (audience.count > 50) {
            more = '<p class="maa-recipient-more">+' + escapeHtml(String(audience.count - 50)) + ' نفر دیگر</p>';
        }

        listEl.innerHTML = rows + more;
    }

    function showRecipientLoading(listEl) {
        if (!listEl) return;
        listEl.classList.add('is-loading');
        listEl.innerHTML = '<p class="maa-recipient-empty">در حال بارگذاری گیرندگان…</p>';
    }

    function refreshSendPreview() {
        var list = document.getElementById('maa-recipient-list');
        if (!currentInsight) return Promise.resolve(null);
        showRecipientLoading(list);
        return loadPreview(currentInsight).then(function (data) {
            if (!data || !data.ok) {
                renderRecipientList(list, data);
                return data;
            }
            if (data.sample_message) {
                document.getElementById('maa-send-message').value = data.sample_message;
            }
            if (typeof data.count !== 'undefined') {
                document.getElementById('maa-send-count').textContent = String(data.count);
            }
            renderRecipientList(list, data);
            return data;
        });
    }

    document.querySelectorAll('.maa-btn-send').forEach(function (btn) {
        btn.addEventListener('click', function () {
            currentInsight = btn.dataset.insight || '';
            var title = btn.dataset.title || 'ارسال پیام';
            var count = btn.dataset.count || '—';
            document.getElementById('maa-send-title').textContent = title;
            document.getElementById('maa-send-count').textContent = count;
            document.getElementById('maa-send-message').value = '';
            showRecipientLoading(document.getElementById('maa-recipient-list'));
            openModal(sendModal);
            refreshSendPreview();
        });
    });

    var previewBtn = document.getElementById('maa-preview-recipients');
    if (previewBtn) {
        previewBtn.addEventListener('click', function () {
            refreshSendPreview();
        });
    }

    var confirmSend = document.getElementById('maa-confirm-send');
    if (confirmSend) {
        confirmSend.addEventListener('click', function () {
            if (!currentInsight || !sendUrl) return;
            confirmSend.disabled = true;
            fetch(sendUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(),
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    insight_key: currentInsight,
                    message_template: document.getElementById('maa-send-message').value,
                    confirm_send: '1'
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.ok) {
                        alert('پیام با موفقیت ارسال شد.');
                        closeModal(sendModal);
                        window.location.reload();
                    } else {
                        alert(data.error || 'ارسال ناموفق بود.');
                    }
                })
                .catch(function () { alert('خطا در ارسال.'); })
                .finally(function () { confirmSend.disabled = false; });
        });
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value || '—';
    }

    function setInputValue(id, value) {
        var el = document.getElementById(id);
        if (!el) return;
        if (value === null || typeof value === 'undefined' || value === '') {
            el.value = '';
        } else {
            el.value = String(value);
        }
    }

    function hideSettingsForm() {
        var form = document.getElementById('maa-auto-settings-form');
        var view = document.getElementById('maa-auto-settings-view');
        var toggle = document.getElementById('maa-auto-toggle-settings');
        if (form) form.hidden = true;
        if (view) view.hidden = false;
        if (toggle) toggle.textContent = 'ویرایش';
    }

    function showSettingsForm() {
        var form = document.getElementById('maa-auto-settings-form');
        var view = document.getElementById('maa-auto-settings-view');
        var toggle = document.getElementById('maa-auto-toggle-settings');
        if (form) form.hidden = false;
        if (view) view.hidden = true;
        if (toggle) toggle.textContent = 'بستن';
    }

    function populateSettingsForm(rule) {
        setInputValue('maa-setting-cadence', rule.cadence || 'daily');
        setInputValue('maa-setting-cooldown', rule.cooldown_days);
        setInputValue('maa-setting-max-recipients', rule.max_recipients_per_run);
        setInputValue('maa-setting-quiet-start', rule.allowed_hours_start);
        setInputValue('maa-setting-quiet-end', rule.allowed_hours_end);
    }

    function renderAutomationDetail(data) {
        var loading = document.getElementById('maa-auto-loading');
        var content = document.getElementById('maa-auto-content');
        if (!data || !data.ok) {
            if (loading) loading.textContent = (data && data.error) || 'خطا در بارگذاری.';
            if (content) content.hidden = true;
            return;
        }

        currentRuleDetail = data;
        var rule = data.rule || {};
        var stats = data.stats_30d || {};
        var audience = data.audience || {};

        if (loading) loading.hidden = true;
        if (content) content.hidden = false;

        setText('maa-auto-title', rule.name);
        var badge = document.getElementById('maa-auto-status-badge');
        if (badge) {
            badge.textContent = data.status_label || '—';
            badge.className = 'maa-auto-status-badge is-' + (data.status_tone || 'inactive');
        }

        setText('maa-auto-cadence-view', rule.cadence_label);
        setText('maa-auto-cooldown-view', (rule.cooldown_days || 0) + ' روز');
        setText('maa-auto-max-view', String(rule.max_recipients_per_run || '—'));
        setText('maa-auto-quiet-view', rule.quiet_hours_label);
        populateSettingsForm(rule);
        hideSettingsForm();

        setText('maa-auto-last-run', rule.last_run_label);
        setText('maa-auto-next-run', rule.next_run_label);
        setText('maa-auto-condition', rule.condition_label);
        setText('maa-auto-audience', rule.audience_label);

        var msgSection = document.getElementById('maa-auto-message-section');
        var msgInput = document.getElementById('maa-auto-message-input');
        var msgPreview = document.getElementById('maa-auto-message-preview');
        var templateBadge = document.getElementById('maa-auto-template-badge');
        if (rule.editable) {
            if (msgSection) msgSection.hidden = false;
            if (msgInput) msgInput.value = rule.message_template || '';
            if (msgPreview) {
                msgPreview.hidden = true;
                msgPreview.textContent = '';
            }
            if (templateBadge) {
                templateBadge.textContent = rule.is_custom_template ? 'سفارشی' : 'پیش‌فرض';
                templateBadge.className = 'maa-auto-template-badge' + (rule.is_custom_template ? ' is-custom' : '');
            }
        } else if (msgSection) {
            msgSection.hidden = true;
        }

        setText('maa-stat-matched', stats.matched || 0);
        setText('maa-stat-sent', stats.sent || 0);
        setText('maa-stat-skipped', stats.skipped || 0);
        setText('maa-stat-converted', stats.converted || 0);

        var countEl = document.getElementById('maa-auto-audience-count');
        if (countEl) {
            var ready = audience.ready_count || 0;
            var total = audience.count || 0;
            countEl.textContent = total + ' نفر · ' + ready + ' آماده ارسال';
        }

        renderAutomationAudience(document.getElementById('maa-auto-audience-list'), audience);

        var recentSection = document.getElementById('maa-auto-recent-section');
        var recentEl = document.getElementById('maa-auto-recent');
        var executions = data.recent_executions || [];
        if (recentSection && recentEl) {
            if (executions.length) {
                recentSection.hidden = false;
                recentEl.innerHTML = executions.map(function (ex) {
                    var dry = ex.dry_run ? ' · Dry Run' : '';
                    return (
                        '<div class="maa-auto-recent-row">' +
                            '<time>' + escapeHtml(ex.started_label) + '</time>' +
                            '<span>Match ' + escapeHtml(String(ex.matched_count)) +
                            ' · موفق ' + escapeHtml(String(ex.success_count)) +
                            ' · Skip ' + escapeHtml(String(ex.skipped_count)) +
                            dry + '</span>' +
                        '</div>'
                    );
                }).join('');
            } else {
                recentSection.hidden = true;
            }
        }

        var confirmAuto = document.getElementById('maa-confirm-auto');
        if (confirmAuto) {
            confirmAuto.textContent = rule.is_active ? 'توقف' : 'فعال کردن';
        }

        var runNow = document.getElementById('maa-auto-run-now');
        if (runNow) {
            runNow.disabled = !rule.is_active || rule.is_paused;
        }
    }

    function showAutomationDetailLoading() {
        var loading = document.getElementById('maa-auto-loading');
        var content = document.getElementById('maa-auto-content');
        if (loading) {
            loading.hidden = false;
            loading.textContent = 'در حال بارگذاری جزئیات…';
        }
        if (content) content.hidden = true;
        showRecipientLoading(document.getElementById('maa-auto-audience-list'));
    }

    function showAutomationDetail(ruleKey) {
        var rule = findRule(ruleKey);
        if (!rule && !ruleKey) return;
        currentRule = ruleKey;
        showAutomationDetailLoading();
        openModal(autoModal);

        if (rule) {
            setText('maa-auto-title', rule.name || 'خودکارسازی');
        }

        loadAutomationDetail(ruleKey).then(function (data) {
            renderAutomationDetail(data);
        }).catch(function () {
            renderAutomationDetail({ ok: false, error: 'خطا در بارگذاری جزئیات.' });
        });
    }

    document.querySelectorAll('.maa-btn-automate, .maa-btn-automate-detail').forEach(function (btn) {
        btn.addEventListener('click', function () {
            showAutomationDetail(btn.dataset.rule || '');
        });
    });

    document.querySelectorAll('.maa-btn-toggle-auto').forEach(function (btn) {
        btn.addEventListener('click', function () {
            toggleAutomation(btn.dataset.rule, btn.dataset.active === '1');
        });
    });

    var confirmAuto = document.getElementById('maa-confirm-auto');
    if (confirmAuto) {
        confirmAuto.addEventListener('click', function () {
            if (!currentRule) return;
            var rule = findRule(currentRule);
            var detailRule = currentRuleDetail && currentRuleDetail.rule;
            var isActive = (detailRule && detailRule.is_active) || (rule && rule.is_active);
            toggleAutomation(currentRule, !isActive);
        });
    }

    var refreshAudienceBtn = document.getElementById('maa-auto-refresh-audience');
    if (refreshAudienceBtn) {
        refreshAudienceBtn.addEventListener('click', function () {
            if (!currentRule) return;
            showRecipientLoading(document.getElementById('maa-auto-audience-list'));
            loadAutomationPreview(currentRule).then(function (data) {
                if (data && data.ok && currentRuleDetail) {
                    currentRuleDetail.audience = {
                        count: data.count,
                        ready_count: data.ready_count,
                        skip_count: data.skip_count,
                        recipients: data.recipients
                    };
                    if (data.sample_message) {
                        currentRuleDetail.sample_message = data.sample_message;
                        var msgPreview = document.getElementById('maa-auto-message-preview');
                        if (msgPreview) {
                            msgPreview.textContent = data.sample_message;
                            msgPreview.hidden = false;
                        }
                    }
                    renderAutomationDetail(currentRuleDetail);
                } else {
                    renderAutomationAudience(
                        document.getElementById('maa-auto-audience-list'),
                        null
                    );
                }
            });
        });
    }

    function runAutomation(dryRun) {
        if (!currentRule || !automationRunUrl) return;
        var label = dryRun ? 'اجرای آزمایشی (Dry Run)' : 'اجرای واقعی';
        if (!window.confirm(label + ' برای این Rule انجام شود؟')) return;

        var btn = dryRun
            ? document.getElementById('maa-auto-dry-run')
            : document.getElementById('maa-auto-run-now');
        if (btn) btn.disabled = true;

        fetch(automationRunUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                rule_key: currentRule,
                dry_run: dryRun,
                force: true,
                confirm_run: '1'
            })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    alert(
                        (dryRun ? 'Dry Run' : 'اجرا') + ' انجام شد.\n' +
                        'Match: ' + data.matched + '\n' +
                        'موفق: ' + data.success + '\n' +
                        'Skip: ' + data.skipped +
                        (data.failed ? '\nخطا: ' + data.failed : '')
                    );
                    showAutomationDetail(currentRule);
                } else {
                    alert(data.error || 'اجرا ناموفق بود.');
                }
            })
            .catch(function () { alert('خطا در اجرا.'); })
            .finally(function () {
                if (btn) btn.disabled = false;
            });
    }

    var dryRunBtn = document.getElementById('maa-auto-dry-run');
    if (dryRunBtn) {
        dryRunBtn.addEventListener('click', function () { runAutomation(true); });
    }

    var runNowBtn = document.getElementById('maa-auto-run-now');
    if (runNowBtn) {
        runNowBtn.addEventListener('click', function () { runAutomation(false); });
    }

    var toggleSettingsBtn = document.getElementById('maa-auto-toggle-settings');
    if (toggleSettingsBtn) {
        toggleSettingsBtn.addEventListener('click', function () {
            var form = document.getElementById('maa-auto-settings-form');
            if (form && form.hidden) {
                showSettingsForm();
            } else {
                hideSettingsForm();
            }
        });
    }

    var cancelSettingsBtn = document.getElementById('maa-auto-cancel-settings');
    if (cancelSettingsBtn) {
        cancelSettingsBtn.addEventListener('click', function () {
            if (currentRuleDetail && currentRuleDetail.rule) {
                populateSettingsForm(currentRuleDetail.rule);
            }
            hideSettingsForm();
        });
    }

    function saveAutomationSettings(payload, onSuccess) {
        if (!automationSettingsUrl || !currentRule) return;
        fetch(automationSettingsUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
                'Accept': 'application/json'
            },
            body: JSON.stringify(Object.assign({ rule_key: currentRule, confirm_save: '1' }, payload))
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    if (onSuccess) onSuccess(data);
                    showAutomationDetail(currentRule);
                } else {
                    alert(data.error || 'ذخیره ناموفق بود.');
                }
            })
            .catch(function () { alert('خطا در ذخیره.'); });
    }

    var saveSettingsBtn = document.getElementById('maa-auto-save-settings');
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', function () {
            var startVal = document.getElementById('maa-setting-quiet-start').value;
            var endVal = document.getElementById('maa-setting-quiet-end').value;
            saveAutomationSettings({
                cadence: document.getElementById('maa-setting-cadence').value,
                cooldown_days: parseInt(document.getElementById('maa-setting-cooldown').value, 10),
                max_recipients_per_run: parseInt(document.getElementById('maa-setting-max-recipients').value, 10),
                quiet_hours_end: startVal === '' ? null : parseInt(startVal, 10),
                quiet_hours_start: endVal === '' ? null : parseInt(endVal, 10)
            });
        });
    }

    var previewMessageBtn = document.getElementById('maa-auto-preview-message');
    if (previewMessageBtn) {
        previewMessageBtn.addEventListener('click', function () {
            if (!automationMessagePreviewUrl || !currentRule) return;
            var template = document.getElementById('maa-auto-message-input').value || '';
            var url = automationMessagePreviewUrl +
                '?rule_key=' + encodeURIComponent(currentRule) +
                '&message_template=' + encodeURIComponent(template);
            fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var msgPreview = document.getElementById('maa-auto-message-preview');
                    if (!data.ok) {
                        alert(data.error || 'Preview ناموفق بود.');
                        return;
                    }
                    if (msgPreview) {
                        msgPreview.textContent = data.sample_message || '';
                        msgPreview.hidden = false;
                    }
                })
                .catch(function () { alert('خطا در Preview.'); });
        });
    }

    var saveMessageBtn = document.getElementById('maa-auto-save-message');
    if (saveMessageBtn) {
        saveMessageBtn.addEventListener('click', function () {
            var template = document.getElementById('maa-auto-message-input').value || '';
            saveAutomationSettings({ message_template: template });
        });
    }

    var resetMessageBtn = document.getElementById('maa-auto-reset-message');
    if (resetMessageBtn) {
        resetMessageBtn.addEventListener('click', function () {
            if (!window.confirm('متن پیام به پیش‌فرض سیستم بازگردانده شود؟')) return;
            saveAutomationSettings({ reset_template: true }, function () {
                var msgPreview = document.getElementById('maa-auto-message-preview');
                if (msgPreview) {
                    msgPreview.hidden = true;
                    msgPreview.textContent = '';
                }
            });
        });
    }

    var testSendBtn = document.getElementById('maa-auto-test-send');
    if (testSendBtn) {
        testSendBtn.addEventListener('click', function () {
            if (!automationTestSendUrl || !currentRule) return;
            if (!window.confirm('پیام آزمایشی به شماره staff ارسال شود؟')) return;
            testSendBtn.disabled = true;
            fetch(automationTestSendUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(),
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    rule_key: currentRule,
                    message_template: document.getElementById('maa-auto-message-input').value || '',
                    confirm_send: '1'
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.ok) {
                        alert('پیام آزمایشی ارسال شد' + (data.phone_masked ? ' (' + data.phone_masked + ')' : '') + '.');
                    } else {
                        alert(data.error || 'ارسال ناموفق بود.');
                    }
                })
                .catch(function () { alert('خطا در ارسال آزمایشی.'); })
                .finally(function () { testSendBtn.disabled = false; });
        });
    }

    function toggleAutomation(ruleKey, active) {
        if (!automationUrl || !ruleKey) return;
        fetch(automationUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
                'Accept': 'application/json'
            },
            body: JSON.stringify({ rule_key: ruleKey, active: !!active })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    window.location.reload();
                } else {
                    alert(data.error || 'عملیات ناموفق بود.');
                }
            })
            .catch(function () { alert('خطا در ذخیره تنظیمات.'); });
    }
})();
