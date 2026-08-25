/**
 * تأیید هویت دو مرحله‌ای (رمز + OTP) پیش از خروجی داده‌های حساس — میزکار وب
 */
(function () {
    'use strict';

    const STEP_PASSWORD = 'password';
    const STEP_OTP = 'otp';

    const state = {
        step: STEP_PASSWORD,
        passwordChallenge: null,
        resendIn: 0,
        resendTimer: null,
        pending: null,
        busy: false,
    };

    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input?.value) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function getApiUrl(name) {
        return '/workspace/api/export-security/' + name + '/';
    }

    function qs(id) {
        return document.getElementById(id);
    }

    function setError(msg) {
        const el = qs('exportSecurityError');
        if (!el) return;
        if (msg) {
            el.textContent = msg;
            el.hidden = false;
        } else {
            el.textContent = '';
            el.hidden = true;
        }
    }

    function setBusy(busy) {
        state.busy = busy;
        const pwBtn = qs('exportSecurityPasswordBtn');
        const otpBtn = qs('exportSecurityOtpBtn');
        if (pwBtn) pwBtn.disabled = busy;
        if (otpBtn) otpBtn.disabled = busy;
        const pwInput = qs('exportSecurityPassword');
        const otpInput = qs('exportSecurityOtp');
        if (pwInput) pwInput.disabled = busy;
        if (otpInput) otpInput.disabled = busy;
    }

    function showStep(step) {
        state.step = step;
        qs('exportSecurityStepPassword')?.toggleAttribute('hidden', step !== STEP_PASSWORD);
        qs('exportSecurityStepOtp')?.toggleAttribute('hidden', step !== STEP_OTP);
        qs('exportSecurityStepPasswordIndicator')?.classList.toggle('is-active', step === STEP_PASSWORD);
        qs('exportSecurityStepOtpIndicator')?.classList.toggle('is-active', step === STEP_OTP);
        qs('exportSecurityStepPasswordIndicator')?.classList.toggle('is-done', step === STEP_OTP);
        setError('');
        if (step === STEP_PASSWORD) {
            setTimeout(() => qs('exportSecurityPassword')?.focus(), 120);
        } else {
            setTimeout(() => qs('exportSecurityOtp')?.focus(), 120);
        }
    }

    function resetModal() {
        if (state.resendTimer) {
            clearInterval(state.resendTimer);
            state.resendTimer = null;
        }
        state.passwordChallenge = null;
        state.resendIn = 0;
        const pw = qs('exportSecurityPassword');
        const otp = qs('exportSecurityOtp');
        if (pw) pw.value = '';
        if (otp) otp.value = '';
        const resendBtn = qs('exportSecurityResendBtn');
        if (resendBtn) {
            resendBtn.disabled = true;
            resendBtn.textContent = 'ارسال مجدد کد';
        }
        showStep(STEP_PASSWORD);
    }

    function updateResendLabel() {
        const btn = qs('exportSecurityResendBtn');
        if (!btn) return;
        if (state.resendIn > 0) {
            btn.disabled = true;
            btn.textContent = `ارسال مجدد (${state.resendIn} ثانیه)`;
        } else {
            btn.disabled = state.busy;
            btn.textContent = 'ارسال مجدد کد';
        }
    }

    function startResendTimer(seconds) {
        state.resendIn = Math.max(0, parseInt(seconds, 10) || 0);
        updateResendLabel();
        if (state.resendTimer) clearInterval(state.resendTimer);
        if (state.resendIn <= 0) return;
        state.resendTimer = setInterval(() => {
            state.resendIn -= 1;
            updateResendLabel();
            if (state.resendIn <= 0 && state.resendTimer) {
                clearInterval(state.resendTimer);
                state.resendTimer = null;
            }
        }, 1000);
    }

    async function postJson(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(body || {}),
        });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }
        if (!res.ok || data.ok === false) {
            const err = new Error(data.error || 'خطا در تأیید هویت');
            err.code = data.code;
            err.retryAfter = data.retry_after;
            throw err;
        }
        return data.data || data;
    }

    async function submitPassword() {
        const password = (qs('exportSecurityPassword')?.value || '').trim();
        if (!password) {
            setError('رمز عبور حساب خود را وارد کنید.');
            return;
        }
        setBusy(true);
        setError('');
        try {
            const data = await postJson(getApiUrl('verify-password'), { password });
            state.passwordChallenge = data.password_challenge;
            const phoneEl = qs('exportSecurityPhoneDisplay');
            if (phoneEl) phoneEl.textContent = data.phone_display || 'شماره شما';
            startResendTimer(data.resend_in || 60);
            showStep(STEP_OTP);
        } catch (err) {
            setError(err.message || 'رمز عبور نادرست است.');
        } finally {
            setBusy(false);
        }
    }

    async function submitOtp() {
        const code = (qs('exportSecurityOtp')?.value || '').trim();
        if (!code) {
            setError('کد پیامک را وارد کنید.');
            return;
        }
        if (!state.passwordChallenge) {
            setError('نشست منقضی شده. دوباره رمز عبور را وارد کنید.');
            showStep(STEP_PASSWORD);
            return;
        }
        setBusy(true);
        setError('');
        try {
            await postJson(getApiUrl('verify-otp'), {
                password_challenge: state.passwordChallenge,
                code,
            });
            if (typeof WSModal !== 'undefined') WSModal.close('modal-export-security');
            await runPendingExport();
        } catch (err) {
            setError(err.message || 'کد تأیید نادرست است.');
        } finally {
            setBusy(false);
        }
    }

    async function resendOtp() {
        if (state.resendIn > 0 || !state.passwordChallenge) return;
        setBusy(true);
        setError('');
        try {
            const data = await postJson(getApiUrl('resend-otp'), {
                password_challenge: state.passwordChallenge,
            });
            state.passwordChallenge = data.password_challenge || state.passwordChallenge;
            startResendTimer(data.resend_in || 60);
        } catch (err) {
            setError(err.message || 'ارسال مجدد انجام نشد.');
        } finally {
            setBusy(false);
        }
    }

    async function runPendingExport() {
        const pending = state.pending;
        state.pending = null;
        if (!pending?.url) return;

        if (pending.type === 'fetch-json') {
            const btn = pending.button;
            if (btn) btn.disabled = true;
            const label = btn?.querySelector('span');
            const prev = label?.textContent;
            if (label) label.textContent = 'در حال آماده‌سازی…';
            try {
                const res = await fetch(pending.url, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.error || 'خروجی گرفته نشد.');
                }
                const data = await res.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = pending.filename || `crm-export-${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
                URL.revokeObjectURL(a.href);
            } catch (err) {
                window.alert(err.message || 'خروجی گرفته نشد.');
            } finally {
                if (btn) btn.disabled = false;
                if (label && prev) label.textContent = prev;
            }
            return;
        }

        if (pending.type === 'fetch-blob') {
            try {
                const res = await fetch(pending.url, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!res.ok) throw new Error('دانلود ناموفق');
                const blob = await res.blob();
                const disposition = res.headers.get('Content-Disposition') || '';
                const match = disposition.match(/filename="([^"]+)"/);
                const filename = match?.[1] || pending.filename || 'export';
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                a.click();
                URL.revokeObjectURL(a.href);
            } catch (_) {
                window.location.href = pending.url;
            }
            return;
        }

        window.location.href = pending.url;
    }

    function openModal(pending) {
        state.pending = pending;
        resetModal();
        const labelEl = qs('exportSecurityContext');
        if (labelEl) {
            labelEl.textContent = pending?.label
                ? `برای خروجی «${pending.label}» ابتدا هویت خود را تأیید کنید.`
                : 'برای خروجی داده‌های حساس، رمز عبور و کد پیامک ورود لازم است.';
        }
        if (typeof WSModal !== 'undefined') {
            WSModal.open('modal-export-security');
        }
    }

    function requestExport(url, options) {
        openModal({
            url,
            type: options?.type || 'navigate',
            filename: options?.filename,
            label: options?.label,
            button: options?.button || null,
        });
    }

    function bindEvents() {
        qs('exportSecurityPasswordBtn')?.addEventListener('click', submitPassword);
        qs('exportSecurityOtpBtn')?.addEventListener('click', submitOtp);
        qs('exportSecurityResendBtn')?.addEventListener('click', resendOtp);
        qs('exportSecurityPassword')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitPassword();
            }
        });
        qs('exportSecurityOtp')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitOtp();
            }
        });
        qs('exportSecurityTogglePassword')?.addEventListener('click', () => {
            const input = qs('exportSecurityPassword');
            const icon = qs('exportSecurityTogglePasswordIcon');
            if (!input) return;
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            if (icon) {
                icon.classList.toggle('fa-eye', show);
                icon.classList.toggle('fa-eye-slash', !show);
            }
        });

        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('.js-secure-export');
            if (!trigger) return;
            e.preventDefault();
            const url = trigger.dataset.exportUrl || trigger.getAttribute('href');
            if (!url || url === '#') return;
            requestExport(url, {
                type: trigger.dataset.exportType || 'navigate',
                label: trigger.dataset.exportLabel || trigger.title || '',
                filename: trigger.dataset.exportFilename || '',
            });
        });
    }

    window.ExportSecurity = {
        requestExport,
        openModal,
        runPendingExport,
    };

    document.addEventListener('DOMContentLoaded', bindEvents);
})();
