/**
 * Workspace Onboarding Tour — cinematic first-visit guide
 */
(function () {
    'use strict';

    const config = window.wsOnboardingConfig;
    if (!config || !config.steps || !config.steps.length) return;

    const PAD = 10;
    const GAP = 16;
    const CARD_W = 380;

    let current = 0;
    let completed = false;
    let root = null;
    let spotlight = null;
    let card = null;
    let modal = null;
    let prevTarget = null;

    function getCsrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function markComplete() {
        if (completed) return;
        completed = true;
        fetch(config.completeUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
        }).catch(() => {});
    }

    function buildDOM() {
        root = document.createElement('div');
        root.className = 'ws-tour-root';
        root.setAttribute('role', 'dialog');
        root.setAttribute('aria-modal', 'true');
        root.setAttribute('aria-label', 'تور آموزشی میزکار');
        root.innerHTML = `
            <div class="ws-tour-backdrop" data-tour-backdrop></div>
            <div class="ws-tour-spotlight" id="wsTourSpotlight" aria-hidden="true">
                <span class="ws-tour-spotlight-pulse"></span>
            </div>
            <div class="ws-tour-modal" id="wsTourModal" hidden></div>
            <div class="ws-tour-card" id="wsTourCard" hidden>
                <div class="ws-tour-card-accent"></div>
                <div class="ws-tour-card-inner">
                    <div class="ws-tour-card-top">
                        <span class="ws-tour-step-badge" id="wsTourStepBadge"></span>
                        <button type="button" class="ws-tour-skip" id="wsTourSkip">رد کردن</button>
                    </div>
                    <div class="ws-tour-icon-wrap" id="wsTourIcon" aria-hidden="true"></div>
                    <h2 class="ws-tour-title" id="wsTourTitle"></h2>
                    <p class="ws-tour-desc" id="wsTourDesc"></p>
                    <div class="ws-tour-progress" aria-hidden="true"><i id="wsTourProgressBar"></i></div>
                    <div class="ws-tour-dots" id="wsTourDots" aria-hidden="true"></div>
                    <div class="ws-tour-actions">
                        <button type="button" class="ws-tour-btn ws-tour-btn--ghost" id="wsTourPrev" disabled>
                            <i class="fas fa-arrow-right" aria-hidden="true"></i> قبلی
                        </button>
                        <div class="ws-tour-actions-end">
                            <button type="button" class="ws-tour-btn ws-tour-btn--primary" id="wsTourNext">
                                بعدی <i class="fas fa-arrow-left" aria-hidden="true"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(root);
        spotlight = document.getElementById('wsTourSpotlight');
        card = document.getElementById('wsTourCard');
        modal = document.getElementById('wsTourModal');

        document.getElementById('wsTourSkip').addEventListener('click', finish);
        document.getElementById('wsTourPrev').addEventListener('click', prev);
        document.getElementById('wsTourNext').addEventListener('click', next);
        root.querySelector('[data-tour-backdrop]').addEventListener('click', () => {});

        const dotsEl = document.getElementById('wsTourDots');
        config.steps.forEach((_, i) => {
            const dot = document.createElement('span');
            dot.className = 'ws-tour-dot';
            dot.dataset.index = String(i);
            dotsEl.appendChild(dot);
        });

        document.addEventListener('keydown', onKey);
        window.addEventListener('resize', () => goTo(current, false));
    }

    function onKey(e) {
        if (!root || !root.classList.contains('is-active')) return;
        if (e.key === 'Escape') {
            e.preventDefault();
            finish();
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            next();
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            prev();
        }
    }

    function isModalStep(step) {
        return step.type === 'welcome' || step.type === 'finish';
    }

    function clearTarget() {
        if (prevTarget) {
            prevTarget.removeAttribute('data-tour-active');
            if (prevTarget.dataset.tourPosRestored === '1') {
                prevTarget.style.position = '';
                delete prevTarget.dataset.tourPosRestored;
            }
            prevTarget = null;
        }
    }

    function activateTarget(el) {
        const pos = window.getComputedStyle(el).position;
        if (pos === 'static') {
            el.style.position = 'relative';
            el.dataset.tourPosRestored = '1';
        }
        el.setAttribute('data-tour-active', '');
        prevTarget = el;
    }

    function positionSpotlight(el) {
        const rect = el.getBoundingClientRect();
        const top = Math.max(4, rect.top - PAD);
        const left = Math.max(4, rect.left - PAD);
        const width = Math.min(window.innerWidth - left - 4, rect.width + PAD * 2);
        const height = Math.min(window.innerHeight - top - 4, rect.height + PAD * 2);

        spotlight.style.top = `${top}px`;
        spotlight.style.left = `${left}px`;
        spotlight.style.width = `${width}px`;
        spotlight.style.height = `${height}px`;
        spotlight.classList.add('is-visible');
    }

    function positionCard(el, placement) {
        const rect = el.getBoundingClientRect();
        const cardRect = card.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const isMobile = vw <= 768;

        if (isMobile) {
            card.style.top = 'auto';
            card.style.left = '12px';
            card.style.right = '12px';
            card.style.bottom = '16px';
            return;
        }

        let top;
        let left;
        const prefer = placement || 'bottom';

        if (prefer === 'left' && rect.left > CARD_W + GAP + 24) {
            top = rect.top + rect.height / 2 - cardRect.height / 2;
            left = rect.left - CARD_W - GAP;
        } else if (prefer === 'right' && vw - rect.right > CARD_W + GAP + 24) {
            top = rect.top + rect.height / 2 - cardRect.height / 2;
            left = rect.right + GAP;
        } else if (prefer === 'top' && rect.top > cardRect.height + GAP + 24) {
            top = rect.top - cardRect.height - GAP;
            left = rect.left + rect.width / 2 - CARD_W / 2;
        } else {
            top = rect.bottom + GAP;
            left = rect.left + rect.width / 2 - CARD_W / 2;
        }

        top = Math.max(12, Math.min(top, vh - cardRect.height - 12));
        left = Math.max(12, Math.min(left, vw - CARD_W - 12));

        card.style.top = `${top}px`;
        card.style.left = `${left}px`;
        card.style.right = 'auto';
        card.style.bottom = 'auto';
    }

    function renderModal(step) {
        root.classList.add('is-modal-step');
        spotlight.classList.remove('is-visible');
        card.hidden = true;
        card.classList.remove('is-visible');
        modal.hidden = false;

        const isWelcome = step.type === 'welcome';
        const features = isWelcome ? `
            <div class="ws-tour-modal-features">
                <div class="ws-tour-modal-feature"><i class="fas fa-users"></i><span>CRM رایگان</span></div>
                <div class="ws-tour-modal-feature"><i class="fas fa-database"></i><span>فایلینگ دیوار</span></div>
                <div class="ws-tour-modal-feature"><i class="fas fa-chart-line"></i><span>تحلیل بازار</span></div>
            </div>
        ` : '';

        const confetti = !isWelcome ? '<div class="ws-tour-finish-confetti" id="wsTourConfetti"></div>' : '';

        modal.innerHTML = `
            <div class="ws-tour-modal-bg"></div>
            <div class="ws-tour-modal-orbs" aria-hidden="true">
                <span class="ws-tour-orb ws-tour-orb--1"></span>
                <span class="ws-tour-orb ws-tour-orb--2"></span>
                <span class="ws-tour-orb ws-tour-orb--3"></span>
            </div>
            <div class="ws-tour-modal-panel">
                ${confetti}
                <div class="ws-tour-modal-logo">
                    ${isWelcome && config.logoUrl
                        ? `<img src="${config.logoUrl}" alt="" width="44" height="44">`
                        : `<i class="fas ${isWelcome ? 'fa-compass' : 'fa-rocket'}"></i>`}
                </div>
                ${isWelcome ? '<span class="ws-tour-modal-eyebrow"><i class="fas fa-sparkles"></i> تور تعاملی · ۳ دقیقه</span>' : ''}
                <h2 class="ws-tour-modal-title">${step.title}</h2>
                <p class="ws-tour-modal-desc">${step.desc}</p>
                ${features}
                <div class="ws-tour-modal-actions">
                    <button type="button" class="ws-tour-btn ws-tour-btn--primary" id="wsTourModalPrimary">
                        ${isWelcome ? 'شروع تور آموزشی' : 'ورود به میزکار'}
                        <i class="fas fa-arrow-left" aria-hidden="true"></i>
                    </button>
                    ${isWelcome ? '<button type="button" class="ws-tour-btn ws-tour-btn--ghost" id="wsTourModalSkip">فعلاً رد کنم</button>' : ''}
                </div>
            </div>
        `;

        requestAnimationFrame(() => modal.classList.add('is-visible'));

        document.getElementById('wsTourModalPrimary').addEventListener('click', () => {
            if (isWelcome) next();
            else finish();
        });

        const skipBtn = document.getElementById('wsTourModalSkip');
        if (skipBtn) skipBtn.addEventListener('click', finish);

        if (!isWelcome) spawnConfetti();
    }

    function scrollToTarget(target, step) {
        const nav = target.closest('.ws-nav');
        if (step.scrollSidebar && nav) {
            const navRect = nav.getBoundingClientRect();
            const targetRect = target.getBoundingClientRect();
            const offset = targetRect.top - navRect.top - (navRect.height / 2) + (targetRect.height / 2);
            nav.scrollTo({ top: nav.scrollTop + offset, behavior: 'smooth' });
        } else {
            target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        }
    }

    function ensureSidebarOpen(step) {
        if (step.openSidebar && window.innerWidth <= 900) {
            document.getElementById('wsSidebar')?.classList.add('open');
        }
    }

    function repositionForTarget(target, step, delay) {
        setTimeout(() => {
            positionSpotlight(target);
            positionCard(target, step.placement);
            card.classList.add('is-visible');
        }, delay);
    }

    function spawnConfetti() {
        const wrap = document.getElementById('wsTourConfetti');
        if (!wrap) return;
        const colors = ['#7C3AED', '#2563EB', '#10B981', '#F59E0B', '#F43F5E'];
        for (let i = 0; i < 24; i++) {
            const piece = document.createElement('span');
            piece.className = 'ws-tour-confetti-piece';
            piece.style.left = `${10 + Math.random() * 80}%`;
            piece.style.top = `${20 + Math.random() * 30}%`;
            piece.style.background = colors[i % colors.length];
            piece.style.animationDelay = `${Math.random() * 0.4}s`;
            wrap.appendChild(piece);
        }
    }

    function renderTooltip(step, index) {
        root.classList.remove('is-modal-step');
        modal.hidden = true;
        modal.classList.remove('is-visible');
        modal.innerHTML = '';
        card.hidden = false;

        const total = config.steps.length;
        const tourSteps = config.steps.filter(s => !isModalStep(s));
        const tourIndex = tourSteps.indexOf(step);
        const tourTotal = tourSteps.length;

        document.getElementById('wsTourStepBadge').textContent =
            tourIndex >= 0 ? `مرحله ${tourIndex + 1} از ${tourTotal}` : '';
        document.getElementById('wsTourIcon').innerHTML = `<i class="fas ${step.icon || 'fa-circle-info'}"></i>`;
        document.getElementById('wsTourTitle').textContent = step.title;
        document.getElementById('wsTourDesc').textContent = step.desc;
        document.getElementById('wsTourProgressBar').style.width =
            `${((index + 1) / total) * 100}%`;

        document.querySelectorAll('.ws-tour-dot').forEach((dot, i) => {
            dot.classList.toggle('is-active', i === index);
            dot.classList.toggle('is-done', i < index);
        });

        const dotsEl = document.getElementById('wsTourDots');
        if (dotsEl) {
            dotsEl.hidden = total > 18;
        }

        const prevBtn = document.getElementById('wsTourPrev');
        const nextBtn = document.getElementById('wsTourNext');
        prevBtn.disabled = index <= 0;
        const isLast = index >= total - 1;
        nextBtn.innerHTML = isLast
            ? 'پایان <i class="fas fa-check" aria-hidden="true"></i>'
            : 'بعدی <i class="fas fa-arrow-left" aria-hidden="true"></i>';

        if (step.accent) {
            root.style.setProperty('--ws-tour-accent', step.accent);
        } else {
            root.style.removeProperty('--ws-tour-accent');
        }

        clearTarget();
        const target = step.target ? document.querySelector(step.target) : null;

        if (target) {
            ensureSidebarOpen(step);
            activateTarget(target);
            scrollToTarget(target, step);
            const delay = step.openSidebar && window.innerWidth <= 900 ? 320 : (step.scrollSidebar ? 180 : 80);
            repositionForTarget(target, step, delay);
        } else {
            spotlight.classList.remove('is-visible');
            card.classList.add('is-visible');
            card.style.top = '50%';
            card.style.left = '50%';
            card.style.transform = 'translate(-50%, -50%)';
        }
    }

    function goTo(index, animate = true) {
        current = Math.max(0, Math.min(index, config.steps.length - 1));
        const step = config.steps[current];

        if (!animate) {
            card.classList.remove('is-visible');
            modal.classList.remove('is-visible');
        }

        if (isModalStep(step)) {
            clearTarget();
            renderModal(step);
        } else {
            card.style.transform = '';
            renderTooltip(step, current);
        }
    }

    function next() {
        if (current >= config.steps.length - 1) finish();
        else goTo(current + 1);
    }

    function prev() {
        if (current > 0) goTo(current - 1);
    }

    function finish() {
        markComplete();
        root.classList.add('is-closing');
        root.classList.remove('is-active');
        document.body.classList.remove('ws-tour-active');
        clearTarget();
        document.getElementById('wsSidebar')?.classList.remove('open');
        document.removeEventListener('keydown', onKey);
        setTimeout(() => root?.remove(), 500);
    }

    function start() {
        buildDOM();
        document.body.classList.add('ws-tour-active');
        requestAnimationFrame(() => {
            root.classList.add('is-active');
            goTo(0);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(start, 600));
    } else {
        setTimeout(start, 600);
    }
})();
