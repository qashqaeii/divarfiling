(function () {
    'use strict';

    var page = document.getElementById('maa-page');
    if (!page) return;

    var previewUrl = page.dataset.previewUrl || '';
    var sendUrl = page.dataset.sendUrl || '';
    var automationUrl = page.dataset.automationUrl || '';
    var rules = window.maaAutomationRules || [];

    var sendModal = document.getElementById('maa-send-modal');
    var autoModal = document.getElementById('maa-auto-modal');
    var currentInsight = null;
    var currentRule = null;

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

    function showAutomationDetail(ruleKey) {
        var rule = findRule(ruleKey);
        if (!rule) return;
        currentRule = ruleKey;
        document.getElementById('maa-auto-title').textContent = rule.name || 'خودکارسازی';
        document.getElementById('maa-auto-condition').textContent = rule.condition_label || '—';
        document.getElementById('maa-auto-audience').textContent = rule.audience_label || '—';
        document.getElementById('maa-auto-action').textContent = rule.action_label || '—';
        document.getElementById('maa-auto-template').textContent = rule.template_label || '—';
        document.getElementById('maa-auto-cooldown').textContent = rule.cooldown_label || '—';
        var confirmAuto = document.getElementById('maa-confirm-auto');
        if (confirmAuto) {
            confirmAuto.textContent = rule.is_active ? 'غیرفعال کردن' : 'فعال کردن';
        }
        openModal(autoModal);
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
            toggleAutomation(currentRule, !(rule && rule.is_active));
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
