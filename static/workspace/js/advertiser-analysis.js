/**
 * Advertiser analysis explainability — listing detail badge popover + feedback.
 */
(function () {
    'use strict';

    function getCsrfToken() {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function initAdvertiserAnalysis() {
        var root = document.querySelector('[data-adv-analysis]');
        if (!root) return;

        var toggle = root.querySelector('[data-adv-analysis-toggle]');
        var panel = root.querySelector('[data-adv-analysis-panel]');
        var closeBtn = root.querySelector('[data-adv-analysis-close]');
        var dataEl = document.getElementById('ws-adv-analysis-data');
        var config = {};
        if (dataEl) {
            try {
                config = JSON.parse(dataEl.textContent || '{}');
            } catch (e) {
                config = {};
            }
        }

        function setOpen(open) {
            if (!toggle || !panel) return;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            panel.hidden = !open;
        }

        function closePanel() {
            setOpen(false);
        }

        function openPanel() {
            setOpen(true);
        }

        if (toggle) {
            toggle.addEventListener('click', function (e) {
                e.stopPropagation();
                var isOpen = toggle.getAttribute('aria-expanded') === 'true';
                if (isOpen) closePanel();
                else openPanel();
            });
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        document.addEventListener('click', function (e) {
            if (!root.contains(e.target)) closePanel();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closePanel();
        });

        var feedbackRoot = root.querySelector('[data-adv-feedback-root]');
        if (!feedbackRoot || !config.feedback_url) return;

        var msgEl = feedbackRoot.querySelector('[data-adv-feedback-msg]');
        var correctionBox = feedbackRoot.querySelector('[data-adv-correction]');
        var correctionSubmit = feedbackRoot.querySelector('[data-adv-correction-submit]');
        var feedbackBtns = feedbackRoot.querySelectorAll('[data-adv-feedback]');

        function showMsg(text, isError) {
            if (!msgEl) return;
            msgEl.hidden = false;
            msgEl.textContent = text;
            msgEl.style.color = isError ? '#dc2626' : '#16a34a';
        }

        function setActiveFeedback(value) {
            feedbackBtns.forEach(function (btn) {
                btn.classList.toggle('is-active', btn.getAttribute('data-adv-feedback') === value);
            });
        }

        function submitFeedback(payload) {
            return fetch(config.feedback_url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            }).then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) throw new Error(data.error || 'خطا در ثبت بازخورد');
                    return data;
                });
            });
        }

        feedbackBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var value = btn.getAttribute('data-adv-feedback');
                if (value === 'incorrect') {
                    if (correctionBox) {
                        correctionBox.hidden = false;
                        correctionBox.classList.remove('is-hidden');
                    }
                    setActiveFeedback('incorrect');
                    return;
                }
                submitFeedback({ feedback: 'correct' })
                    .then(function () {
                        setActiveFeedback('correct');
                        if (correctionBox) {
                            correctionBox.hidden = true;
                            correctionBox.classList.add('is-hidden');
                        }
                        showMsg('ممنون! بازخورد شما ثبت شد.');
                    })
                    .catch(function (err) {
                        showMsg(err.message || 'خطا در ثبت', true);
                    });
            });
        });

        if (correctionSubmit) {
            correctionSubmit.addEventListener('click', function () {
                var selected = feedbackRoot.querySelector('input[name="adv_correction"]:checked');
                if (!selected) {
                    showMsg('لطفاً یک گزینه را انتخاب کنید.', true);
                    return;
                }
                submitFeedback({
                    feedback: 'incorrect',
                    user_correction: selected.value,
                })
                    .then(function () {
                        setActiveFeedback('incorrect');
                        showMsg('ممنون! بازخورد شما برای بهبود سیستم ثبت شد.');
                    })
                    .catch(function (err) {
                        showMsg(err.message || 'خطا در ثبت', true);
                    });
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAdvertiserAnalysis);
    } else {
        initAdvertiserAnalysis();
    }
})();
