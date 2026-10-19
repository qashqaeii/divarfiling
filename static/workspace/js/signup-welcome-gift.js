/**
 * پنجره هدیه خوش‌آمدگویی ۷روزه — قبل از تور میزکار
 */
(function (global) {
    'use strict';

    const cfg = global.wsSignupWelcomeConfig;
    if (!cfg || !cfg.ackUrl) {
        return;
    }

    const CONFETTI_COLORS = ['#7c3aed', '#a78bfa', '#fbbf24', '#34d399', '#f472b6'];

    function getCsrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function toPersianDigits(value) {
        const map = '۰۱۲۳۴۵۶۷۸۹';
        return String(value).replace(/\d/g, (d) => map[d] || d);
    }

    function prefersReducedMotion() {
        return global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function spawnConfetti(container) {
        if (prefersReducedMotion() || !container) return;
        const count = global.innerWidth <= 480 ? 24 : 40;
        for (let i = 0; i < count; i += 1) {
            const piece = document.createElement('i');
            piece.style.left = `${Math.random() * 100}%`;
            piece.style.background = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
            piece.style.animationDelay = `${Math.random() * 0.6}s`;
            piece.style.setProperty('--swg-dx', `${(Math.random() - 0.5) * 120}px`);
            container.appendChild(piece);
        }
    }

    function buildModal() {
        const days = cfg.giftDays || 7;
        const daysFa = toPersianDigits(days);
        const root = document.createElement('div');
        root.className = 'ws-signup-welcome';
        root.setAttribute('role', 'dialog');
        root.setAttribute('aria-modal', 'true');
        root.setAttribute('aria-labelledby', 'wsSignupWelcomeTitle');
        root.innerHTML = `
            <div class="ws-signup-welcome__backdrop" data-swg-backdrop></div>
            <div class="ws-signup-welcome__confetti" aria-hidden="true"></div>
            <div class="ws-signup-welcome__card">
                <div class="ws-signup-welcome__gift" aria-hidden="true">
                    <div class="ws-signup-welcome__gift-lid"></div>
                    <div class="ws-signup-welcome__gift-box"></div>
                    <div class="ws-signup-welcome__gift-ribbon"></div>
                </div>
                <p class="ws-signup-welcome__eyebrow">
                    <i class="fas fa-gift" aria-hidden="true"></i>
                    هدیه ویژه کاربران جدید
                </p>
                <h2 class="ws-signup-welcome__title" id="wsSignupWelcomeTitle">
                    تبریک! یه هدیه ویژه داری!
                </h2>
                <div class="ws-signup-welcome__badge">
                    <strong>${daysFa} روز رایگان</strong>
                    <span>لایسنس شما فعال شد</span>
                </div>
                <p class="ws-signup-welcome__desc">
                    به مناسبت عضویتت در فایلینگ دیوار، اشتراک حرفه‌ای ${daysFa} روزه بهت هدیه دادیم.
                    ${daysFa} روز فرصت داری امکانات حرفه‌ای رو تجربه کنی — بدون پرداخت و بدون کد تخفیف.
                </p>
                <button type="button" class="ws-signup-welcome__cta" id="wsSignupWelcomeCta">
                    بزن بریم، میزکارمو نشون بده!
                </button>
                <p class="ws-signup-welcome__fine">هدیه همین الان فعال شده است.</p>
            </div>
        `;
        document.body.appendChild(root);
        spawnConfetti(root.querySelector('.ws-signup-welcome__confetti'));
        requestAnimationFrame(() => root.classList.add('is-active'));
        return root;
    }

    function acknowledge(startTour) {
        const body = new URLSearchParams();
        if (startTour) {
            body.set('start_tour', '1');
        }
        return fetch(cfg.ackUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            credentials: 'same-origin',
            body: body.toString(),
        });
    }

    function closeModal(root) {
        root.classList.remove('is-active');
        setTimeout(() => {
            if (root.parentNode) {
                root.parentNode.removeChild(root);
            }
        }, 400);
    }

    function startTourIfNeeded() {
        if (!cfg.startTourAfter || !global.wsOnboardingConfig || !global.wsWorkspaceTour) {
            return;
        }
        global.wsOnboardingConfig.autoStart = true;
        global.wsWorkspaceTour.start(global.wsOnboardingConfig);
    }

    function boot() {
        const root = buildModal();
        const cta = root.querySelector('#wsSignupWelcomeCta');
        const backdrop = root.querySelector('[data-swg-backdrop]');

        function onContinue() {
            cta.disabled = true;
            acknowledge(cfg.startTourAfter)
                .catch(() => {})
                .finally(() => {
                    closeModal(root);
                    startTourIfNeeded();
                });
        }

        cta.addEventListener('click', onContinue);
        backdrop.addEventListener('click', (e) => {
            e.preventDefault();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})(window);
