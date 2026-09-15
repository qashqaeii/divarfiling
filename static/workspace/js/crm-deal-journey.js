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

    function initDealTabs() {
        var root = document.querySelector('.dj-deal');
        if (!root || root.dataset.djTabsBound === '1') return;
        var nav = root.querySelector('[data-dj-tabs]');
        var panels = root.querySelectorAll('[data-dj-panel]');
        if (!nav || !panels.length) return;
        root.dataset.djTabsBound = '1';

        var validTabs = ['overview', 'activity', 'finance', 'documents', 'contracts', 'history'];
        var defaultTab = root.dataset.defaultTab || 'overview';

        function normalizeTab(tab) {
            return validTabs.indexOf(tab) >= 0 ? tab : defaultTab;
        }

        function tabFromUrl() {
            try {
                var params = new URLSearchParams(window.location.search);
                return normalizeTab(params.get('tab') || defaultTab);
            } catch (e) {
                return defaultTab;
            }
        }

        function buildUrl(tab) {
            var url = new URL(window.location.href);
            if (!tab || tab === 'overview') url.searchParams.delete('tab');
            else url.searchParams.set('tab', tab);
            return url.pathname + url.search + url.hash;
        }

        function activateTab(tab, updateHistory) {
            tab = normalizeTab(tab);
            nav.querySelectorAll('[data-dj-tab]').forEach(function (link) {
                var active = link.dataset.djTab === tab;
                link.classList.toggle('is-active', active);
                link.setAttribute('aria-selected', active ? 'true' : 'false');
            });
            panels.forEach(function (panel) {
                var active = panel.dataset.djPanel === tab;
                panel.hidden = !active;
                panel.classList.toggle('is-active', active);
            });
            if (updateHistory) {
                var nextUrl = buildUrl(tab);
                if (nextUrl !== window.location.pathname + window.location.search + window.location.hash) {
                    history.pushState({ djTab: tab }, '', nextUrl);
                }
            }
        }

        nav.addEventListener('click', function (e) {
            var link = e.target.closest('[data-dj-tab]');
            if (!link || !nav.contains(link)) return;
            e.preventDefault();
            activateTab(link.dataset.djTab, true);
        });

        root.addEventListener('click', function (e) {
            var link = e.target.closest('[data-dj-tab-link]');
            if (!link || !root.contains(link)) return;
            e.preventDefault();
            activateTab(link.dataset.djTabLink, true);
            var workspace = root.querySelector('.dj-workspace');
            if (workspace && typeof workspace.scrollIntoView === 'function') {
                workspace.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });

        window.addEventListener('popstate', function () {
            activateTab(tabFromUrl(), false);
        });

        activateTab(tabFromUrl(), false);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initDealMoreMenu();
        initStageTransition();
        initDealTabs();
    });
})();
