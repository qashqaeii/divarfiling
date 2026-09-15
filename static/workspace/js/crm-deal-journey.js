/**
 * Deal Journey — header menu + stage rail (uses CRMStageTransition)
 */
(function () {
    'use strict';

    function initDealMoreMenu() {
        var btn = document.getElementById('djDealMoreBtn');
        var menu = document.getElementById('djDealMoreMenu');
        if (!btn || !menu) return;
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var open = menu.hasAttribute('hidden');
            if (open) {
                menu.removeAttribute('hidden');
                btn.setAttribute('aria-expanded', 'true');
            } else {
                menu.setAttribute('hidden', '');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
        document.addEventListener('click', function () {
            menu.setAttribute('hidden', '');
            btn.setAttribute('aria-expanded', 'false');
        });
        menu.querySelectorAll('[data-drawer-open]').forEach(function (el) {
            el.addEventListener('click', function () {
                menu.setAttribute('hidden', '');
                btn.setAttribute('aria-expanded', 'false');
            });
        });
    }

    function initStageTransition() {
        var root = document.querySelector('.dj-deal');
        if (!root || !window.CRMStageTransition) return;

        var stageUrl = root.dataset.stageUrl;
        var stages = [];
        try {
            var stagesEl = document.getElementById('crmDealStagesListData');
            if (stagesEl) stages = JSON.parse(stagesEl.textContent).map(function (d) { return d.name || d; });
        } catch (e) {}
        if (!stages.length) {
            root.querySelectorAll('.dj-stage-rail__btn').forEach(function (b) {
                if (b.dataset.stage) stages.push(b.dataset.stage);
            });
        }

        window.CRMStageTransition.init({
            lostStage: root.dataset.lostStage || 'از دست رفته',
            wonStage: 'بسته‌شده',
            contractStage: 'قرارداد',
            stages: stages,
        });

        var currentStep = root.querySelector('.dj-stage-rail__step.is-current');
        if (currentStep && typeof currentStep.scrollIntoView === 'function') {
            currentStep.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }

        root.querySelectorAll('[data-stage-transition]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var to = btn.dataset.stage;
                var current = root.querySelector('.dj-stage-rail__step.is-current .dj-stage-rail__btn');
                var from = current ? current.dataset.stage : '';
                if (!to || to === from) return;

                var meta = {
                    customer: root.dataset.customer || '',
                    property: root.dataset.property || '',
                    valueLabel: root.dataset.valueLabel || '',
                    contractCount: parseInt(root.dataset.contractCount || '0', 10) || 0,
                    hasFinalized: root.dataset.hasFinalized === '1',
                    createContractUrl: root.dataset.createContractUrl || '',
                };

                window.CRMStageTransition.requestTransition({
                    fromStage: from,
                    toStage: to,
                    stageUrl: stageUrl,
                    meta: meta,
                }).then(function () {
                    window.location.reload();
                }).catch(function (err) {
                    if (err && err.message === 'cancelled') return;
                    window.CRMStageTransition.showToast(err.message || 'انتقال انجام نشد.', true);
                });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initDealMoreMenu();
        initStageTransition();
    });
})();
