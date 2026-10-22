/**
 * صفحات ورود و ثبت‌نام — نمایش رمز، قدرت رمز، تعامل فرم
 */
(function () {
    'use strict';

    function togglePassword(btn) {
        const wrap = btn.closest('.auth-input-wrap');
        if (!wrap) return;
        const input = wrap.querySelector('input');
        const icon = btn.querySelector('i');
        if (!input || !icon) return;

        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        icon.classList.toggle('fa-eye', !show);
        icon.classList.toggle('fa-eye-slash', show);
        btn.setAttribute('aria-label', show ? 'مخفی کردن رمز' : 'نمایش رمز');
        btn.setAttribute('aria-pressed', show ? 'true' : 'false');
    }

    function scorePassword(value) {
        let score = 0;
        if (!value) return 0;
        if (value.length >= 8) score += 1;
        if (value.length >= 12) score += 1;
        if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
        if (/\d/.test(value)) score += 1;
        if (/[^A-Za-z0-9]/.test(value)) score += 1;
        return Math.min(score, 4);
    }

    function initPasswordStrength() {
        const input = document.querySelector('[data-password-strength]');
        const bar = document.querySelector('[data-strength-bar]');
        const label = document.querySelector('[data-strength-label]');
        if (!input || !bar) return;

        const labels = ['', 'ضعیف', 'متوسط', 'خوب', 'عالی'];
        const colors = ['', '#ef4444', '#f59e0b', '#3b82f6', '#22c55e'];

        input.addEventListener('input', () => {
            const score = scorePassword(input.value);
            const pct = score * 25;
            bar.style.width = `${pct}%`;
            bar.style.background = colors[score] || 'transparent';
            if (label) {
                label.textContent = input.value ? (labels[score] || '') : '';
                label.style.color = colors[score] || '';
            }
        });
    }

    function initOtpSendWaitingHint(form) {
        let hint = form.querySelector('[data-auth-otp-send-hint]');
        if (!hint) {
            hint = document.createElement('p');
            hint.className = 'auth-hint auth-hint-spam';
            hint.setAttribute('data-auth-otp-send-hint', '');
            hint.setAttribute('role', 'status');
            hint.textContent =
                'در حال ارسال پیامک… اگر کد تا چند لحظه نرسید، پوشهٔ هرزنامه (Spam) پیامک را هم بررسی کنید.';
            const btn = form.querySelector('.auth-submit-btn');
            if (btn && btn.parentNode) {
                btn.parentNode.insertBefore(hint, btn.nextSibling);
            }
        }
        hint.hidden = false;
    }

    function initSubmitState() {
        document.querySelectorAll('.auth-form').forEach(form => {
            form.addEventListener('submit', () => {
                const btn = form.querySelector('.auth-submit-btn');
                if (!btn || btn.disabled) return;
                btn.disabled = true;
                btn.classList.add('is-loading');
                const span = btn.querySelector('span');
                if (span) span.dataset.prev = span.textContent;
                const isOtpSend = form.hasAttribute('data-auth-otp-send');
                if (span) {
                    span.textContent = isOtpSend ? 'در حال ارسال کد…' : 'لطفاً صبر کنید…';
                }
                if (isOtpSend) {
                    initOtpSendWaitingHint(form);
                }
            });
        });
    }

    function toPersianDigits(n) {
        return String(n).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
    }

    function initOtpResend() {
        document.querySelectorAll('[data-otp-resend]').forEach(btn => {
            const seconds = parseInt(
                btn.getAttribute('data-seconds') || btn.closest('form')?.getAttribute('data-otp-resend-seconds') || '60',
                10
            );
            if (!seconds || seconds < 1) return;
            let left = seconds;
            const label = btn.textContent;
            btn.disabled = true;
            const tick = () => {
                if (left <= 0) {
                    btn.disabled = false;
                    btn.textContent = label;
                    return;
                }
                btn.textContent = `ارسال مجدد (${toPersianDigits(left)} ثانیه)`;
                left -= 1;
                window.setTimeout(tick, 1000);
            };
            tick();
        });
    }

    function initOtpInput() {
        const input = document.querySelector('.auth-otp-input');
        if (!input) return;
        input.addEventListener('input', () => {
            input.value = input.value.replace(/[^\d۰-۹٠-٩]/g, '').slice(0, 8);
        });
    }

    function init() {
        document.querySelectorAll('[data-password-toggle]').forEach(btn => {
            btn.addEventListener('click', () => togglePassword(btn));
        });
        initPasswordStrength();
        initSubmitState();
        initOtpResend();
        initOtpInput();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
