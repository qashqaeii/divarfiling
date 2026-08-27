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

    function openModal(modal) {
        if (!modal) return;
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
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

    document.querySelectorAll('.maa-btn-send').forEach(function (btn) {
        btn.addEventListener('click', function () {
            currentInsight = btn.dataset.insight || '';
            var title = btn.dataset.title || 'ارسال پیام';
            var count = btn.dataset.count || '—';
            document.getElementById('maa-send-title').textContent = title;
            document.getElementById('maa-send-count').textContent = count;
            document.getElementById('maa-send-message').value = '';
            document.getElementById('maa-recipient-list').innerHTML = '';
            openModal(sendModal);

            loadPreview(currentInsight).then(function (data) {
                if (!data || !data.ok) return;
                if (data.sample_message) {
                    document.getElementById('maa-send-message').value = data.sample_message;
                }
                if (typeof data.count !== 'undefined') {
                    document.getElementById('maa-send-count').textContent = String(data.count);
                }
            });
        });
    });

    var previewBtn = document.getElementById('maa-preview-recipients');
    if (previewBtn) {
        previewBtn.addEventListener('click', function () {
            if (!currentInsight) return;
            loadPreview(currentInsight).then(function (data) {
                var list = document.getElementById('maa-recipient-list');
                if (!list) return;
                if (!data || !data.ok || !data.recipients || !data.recipients.length) {
                    list.textContent = 'گیرنده‌ای برای نمایش نیست.';
                    return;
                }
                list.innerHTML = data.recipients.slice(0, 20).map(function (r) {
                    var name = r.name || r.user_display || 'کاربر';
                    return '<div>• ' + name + '</div>';
                }).join('');
            });
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
