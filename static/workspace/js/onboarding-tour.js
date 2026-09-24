/**
 * Workspace Tour — shared cinematic guide (میزکار، فایلینگ، …)
 */
(function (global) {
    'use strict';

    function createWorkspaceTour(userConfig) {
    const config = userConfig;
    if (!config || !config.steps || !config.steps.length) {
        return { start() {}, destroy() {} };
    }

    const PAD = 10;
    const PAD_MOBILE = 6;
    const GAP = 16;
    const CARD_W = 380;
    const MOBILE_BP = 768;
    const TABLET_BP = 900;

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
        if (completed || !config.completeUrl) return;
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

    function isMobileView() {
        return window.innerWidth <= MOBILE_BP;
    }

    function getMobileBottomInset() {
        let inset = 12;
        const bottomNav = document.getElementById('wsBottomNav');
        if (bottomNav && window.innerWidth <= TABLET_BP) {
            const style = window.getComputedStyle(bottomNav);
            if (style.display !== 'none' && style.visibility !== 'hidden') {
                inset += bottomNav.getBoundingClientRect().height;
            }
        }
        const fab = document.querySelector('.mk-filing-fab:not([hidden])');
        if (fab && isMobileView()) {
            inset = Math.max(inset, 72);
        }
        return inset;
    }

    function buildDOM() {
        root = document.createElement('div');
        root.className = 'ws-tour-root';
        if (config.variant) {
            root.classList.add(`ws-tour-root--${config.variant}`);
        }
        root.setAttribute('role', 'dialog');
        root.setAttribute('aria-modal', 'true');
        root.setAttribute('aria-label', config.ariaLabel || 'تور آموزشی');
        root.innerHTML = `
            <div class="ws-tour-backdrop" data-tour-backdrop></div>
            <div class="ws-tour-spotlight" id="wsTourSpotlight" aria-hidden="true">
                <span class="ws-tour-spotlight-pulse"></span>
                <span class="ws-tour-spotlight-corners" aria-hidden="true"></span>
            </div>
            <div class="ws-tour-modal" id="wsTourModal" hidden></div>
            <div class="ws-tour-card" id="wsTourCard" hidden>
                <div class="ws-tour-sheet-handle" aria-hidden="true"><span></span></div>
                <div class="ws-tour-card-accent"></div>
                <div class="ws-tour-card-inner">
                    <div class="ws-tour-card-top">
                        <span class="ws-tour-step-badge" id="wsTourStepBadge"></span>
                        <button type="button" class="ws-tour-skip" id="wsTourSkip">رد کردن</button>
                    </div>
                    <div class="ws-tour-icon-wrap" id="wsTourIcon" aria-hidden="true"></div>
                    <p class="ws-tour-section" id="wsTourSection" hidden></p>
                    <h2 class="ws-tour-title" id="wsTourTitle"></h2>
                    <p class="ws-tour-desc" id="wsTourDesc"></p>
                    <p class="ws-tour-tip" id="wsTourTip" hidden></p>
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

    function isStepVisible(step) {
        if (step.onlyMobile && window.innerWidth > 900) return false;
        if (!step.target) return true;
        const el = document.querySelector(step.target);
        if (!el) return !step.skipIfMissing;
        if (step.onlyMobile) {
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
        }
        return true;
    }

    function resolveStepIndex(index, direction) {
        let i = index;
        const delta = direction >= 0 ? 1 : -1;
        while (i >= 0 && i < config.steps.length) {
            const step = config.steps[i];
            if (isModalStep(step) || isStepVisible(step)) return i;
            i += delta;
        }
        return direction >= 0 ? config.steps.length - 1 : 0;
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
        const pad = isMobileView() ? PAD_MOBILE : PAD;
        const rect = el.getBoundingClientRect();
        const top = Math.max(4, rect.top - pad);
        const left = Math.max(4, rect.left - pad);
        const width = Math.min(window.innerWidth - left - 4, rect.width + pad * 2);
        const height = Math.min(window.innerHeight - top - 4, rect.height + pad * 2);

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
        const cardH = cardRect.height || 320;

        if (isMobileView()) {
            const bottomInset = getMobileBottomInset();
            const targetMid = rect.top + rect.height / 2;
            const placeAboveTarget = targetMid > vh * 0.52 && rect.top > cardH + 24;

            card.classList.toggle('is-mobile-sheet', !placeAboveTarget);
            card.classList.toggle('is-mobile-float', placeAboveTarget);

            card.style.left = '10px';
            card.style.right = '10px';
            card.style.width = 'auto';

            if (placeAboveTarget) {
                let top = Math.max(12, rect.top - cardH - GAP);
                top = Math.min(top, vh - cardH - bottomInset - 8);
                card.style.top = `${top}px`;
                card.style.bottom = 'auto';
            } else {
                card.style.top = 'auto';
                card.style.bottom = `calc(${bottomInset}px + env(safe-area-inset-bottom, 0px))`;
            }
            return;
        }

        card.classList.remove('is-mobile-sheet', 'is-mobile-float');

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

    function renderWelcomeFeaturesHtml() {
        const defaults = [
            { icon: 'fa-users', label: 'CRM رایگان' },
            { icon: 'fa-database', label: 'فایلینگ دیوار' },
            { icon: 'fa-file-signature', label: 'قرارداد و مالی' },
            { icon: 'fa-microphone-lines', label: 'دستیار هوشمند' },
        ];
        const items = (config.welcomeFeatures && config.welcomeFeatures.length)
            ? config.welcomeFeatures
            : defaults;
        const cells = items.map((f) =>
            `<div class="ws-tour-modal-feature"><i class="fas ${f.icon}" aria-hidden="true"></i><span>${f.label}</span></div>`
        ).join('');
        return `<div class="ws-tour-modal-features">${cells}</div>`;
    }

    function renderModal(step) {
        root.classList.add('is-modal-step');
        root.classList.remove('is-tooltip-step');
        spotlight.classList.remove('is-visible');
        card.hidden = true;
        card.classList.remove('is-visible');
        modal.hidden = false;

        const isWelcome = step.type === 'welcome';
        const features = isWelcome ? renderWelcomeFeaturesHtml() : '';
        const eyebrowText = isWelcome
            ? (config.welcomeEyebrow || '<i class="fas fa-sparkles"></i> تور تعاملی · حدود ۵ دقیقه')
            : '';
        const finishCta = config.finishButtonText || 'ورود به میزکار';
        const welcomeCta = config.welcomeButtonText || 'شروع تور آموزشی';

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
                        : `<i class="fas ${isWelcome ? (config.welcomeIcon || 'fa-compass') : (config.finishIcon || 'fa-rocket')}"></i>`}
                </div>
                ${isWelcome ? `<span class="ws-tour-modal-eyebrow">${eyebrowText}</span>` : ''}
                <h2 class="ws-tour-modal-title">${step.title}</h2>
                <p class="ws-tour-modal-desc">${step.desc}</p>
                ${features}
                <div class="ws-tour-modal-actions">
                    <button type="button" class="ws-tour-btn ws-tour-btn--primary" id="wsTourModalPrimary">
                        ${isWelcome ? welcomeCta : finishCta}
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
        } else if (isMobileView()) {
            const vh = window.innerHeight;
            const rect = target.getBoundingClientRect();
            const block = rect.top > vh * 0.55 ? 'end' : (rect.top < vh * 0.25 ? 'start' : 'center');
            target.scrollIntoView({ behavior: 'smooth', block, inline: 'nearest' });
        } else {
            target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        }
    }

    function ensureNavMoreOpen(step) {
        if (!step.openNavMore) return;
        const more = document.querySelector('[data-tour="nav-more"]');
        if (more && more.tagName === 'DETAILS') more.open = true;
    }

    function ensureSidebarForStep(step) {
        const sidebar = document.getElementById('wsSidebar');
        if (!sidebar) return;
        if (step.closeSidebar) {
            sidebar.classList.remove('open');
        } else if (step.openSidebar && window.innerWidth <= 900) {
            sidebar.classList.add('open');
        }
    }

    function repositionForTarget(target, step, delay) {
        setTimeout(() => {
            root.classList.add('is-tooltip-step');
            root.classList.remove('is-modal-step');
            positionSpotlight(target);
            positionCard(target, step.placement);
            card.classList.remove('is-visible');
            requestAnimationFrame(() => {
                card.classList.add('is-visible');
            });
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
        const sectionEl = document.getElementById('wsTourSection');
        if (step.section) {
            sectionEl.textContent = step.section;
            sectionEl.hidden = false;
        } else {
            sectionEl.textContent = '';
            sectionEl.hidden = true;
        }

        document.getElementById('wsTourTitle').textContent = step.title;
        document.getElementById('wsTourDesc').textContent = step.desc;

        const tipEl = document.getElementById('wsTourTip');
        if (step.tip) {
            tipEl.replaceChildren();
            const tipIcon = document.createElement('i');
            tipIcon.className = 'fas fa-lightbulb';
            tipIcon.setAttribute('aria-hidden', 'true');
            const tipText = document.createElement('span');
            tipText.textContent = step.tip;
            tipEl.append(tipIcon, tipText);
            tipEl.hidden = false;
        } else {
            tipEl.replaceChildren();
            tipEl.hidden = true;
        }

        const progressPct = ((index + 1) / total) * 100;
        document.getElementById('wsTourProgressBar').style.width = `${progressPct}%`;
        root.style.setProperty('--ws-tour-progress', `${progressPct}%`);

        document.querySelectorAll('.ws-tour-dot').forEach((dot, i) => {
            dot.classList.toggle('is-active', i === index);
            dot.classList.toggle('is-done', i < index);
        });

        const dotsEl = document.getElementById('wsTourDots');
        if (dotsEl) {
            dotsEl.hidden = total > 22;
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

        if (step.target && !target && step.skipIfMissing) {
            next();
            return;
        }

        if (target) {
            ensureNavMoreOpen(step);
            ensureSidebarForStep(step);
            activateTarget(target);
            scrollToTarget(target, step);
            const delay = step.openSidebar && window.innerWidth <= 900 ? 320 : (step.openNavMore ? 220 : (step.scrollSidebar ? 180 : 80));
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
        const clamped = Math.max(0, Math.min(index, config.steps.length - 1));
        const direction = index >= current ? 1 : -1;
        current = resolveStepIndex(clamped, direction);
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
        if (current >= config.steps.length - 1) {
            finish();
            return;
        }
        let nextIndex = current + 1;
        while (nextIndex < config.steps.length && !isModalStep(config.steps[nextIndex]) && !isStepVisible(config.steps[nextIndex])) {
            nextIndex += 1;
        }
        if (nextIndex >= config.steps.length) finish();
        else goTo(nextIndex);
    }

    function prev() {
        if (current <= 0) return;
        let prevIndex = current - 1;
        while (prevIndex > 0 && !isModalStep(config.steps[prevIndex]) && !isStepVisible(config.steps[prevIndex])) {
            prevIndex -= 1;
        }
        goTo(prevIndex);
    }

    function finish() {
        if (config.completeUrl) markComplete();
        if (!root) return;
        root.classList.add('is-closing');
        root.classList.remove('is-active');
        document.body.classList.remove('ws-tour-active');
        clearTarget();
        document.getElementById('wsSidebar')?.classList.remove('open');
        document.removeEventListener('keydown', onKey);
        const completeUrl = config.completeUrl;
        setTimeout(function () {
            root?.remove();
            root = null;
            if (!completeUrl) return;
            fetch(completeUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data && data.redirect_url) {
                        global.location.href = data.redirect_url;
                    }
                })
                .catch(function () {});
        }, 500);
    }

    function start() {
        if (root) return;
        completed = false;
        current = 0;
        buildDOM();
        document.body.classList.add('ws-tour-active');
        requestAnimationFrame(() => {
            root.classList.add('is-active');
            goTo(0);
        });
    }

    return { start, destroy: finish };
    }

    global.wsWorkspaceTour = {
        start(cfg) {
            if (this._instance) {
                try { this._instance.destroy(); } catch (e) { /* ignore */ }
            }
            this._instance = createWorkspaceTour(cfg);
            this._instance.start();
        },
    };

    function bootConfiguredTour() {
        if (!global.wsOnboardingConfig) return;
        if (global.wsOnboardingConfig.autoStart === false) return;
        const delay = global.wsOnboardingConfig.startDelay ?? 600;
        const run = () => global.wsWorkspaceTour.start(global.wsOnboardingConfig);
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => setTimeout(run, delay));
        } else {
            setTimeout(run, delay);
        }
    }

    bootConfiguredTour();
})(window);
