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

    function initSubmitState() {
        document.querySelectorAll('.auth-form').forEach(form => {
            form.addEventListener('submit', () => {
                const btn = form.querySelector('.auth-submit-btn');
                if (!btn || btn.disabled) return;
                btn.disabled = true;
                btn.classList.add('is-loading');
                const span = btn.querySelector('span');
                if (span) span.dataset.prev = span.textContent;
                if (span) span.textContent = 'لطفاً صبر کنید…';
            });
        });
    }

    function init() {
        document.querySelectorAll('[data-password-toggle]').forEach(btn => {
            btn.addEventListener('click', () => togglePassword(btn));
        });
        initPasswordStrength();
        initSubmitState();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
