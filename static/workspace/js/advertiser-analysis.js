/**
 * Advertiser analysis explainability — badge + centered modal + feedback.
 */
(function () {
    'use strict';

    function getCsrfToken() {
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function initAdvertiserAnalysis() {
        var root = document.querySelector('[data-adv-analysis]');
        var overlay = document.querySelector('[data-adv-analysis-overlay]');
        if (!root || !overlay) return;

        var toggle = root.querySelector('[data-adv-analysis-toggle]');
        var panel = overlay.querySelector('[data-adv-analysis-panel]');
        var backdrop = overlay.querySelector('[data-adv-analysis-backdrop]');
        var closeBtn = overlay.querySelector('[data-adv-analysis-close]');
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
            if (!toggle || !overlay) return;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            overlay.hidden = !open;
            overlay.classList.toggle('is-open', open);
            overlay.setAttribute('aria-hidden', open ? 'false' : 'true');
            document.body.classList.toggle('ws-adv-analysis-open', open);
            if (open && panel) {
                panel.focus();
            }
        }

        function closePanel() {
            setOpen(false);
        }

        function openPanel() {
            setOpen(true);
        }

        if (toggle) {
            toggle.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var isOpen = toggle.getAttribute('aria-expanded') === 'true';
                if (isOpen) closePanel();
                else openPanel();
            });
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        if (backdrop) {
            backdrop.addEventListener('click', closePanel);
        }

        if (panel) {
            panel.addEventListener('click', function (e) {
                e.stopPropagation();
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && toggle && toggle.getAttribute('aria-expanded') === 'true') {
                closePanel();
            }
        });

        var feedbackRoot = overlay.querySelector('[data-adv-feedback-root]');
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
                        showMsg('ممنون! بازخورد شما ثبت شد.');
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
