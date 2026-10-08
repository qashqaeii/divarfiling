(function () {
    'use strict';

    function resizeDashCharts() {
        if (!window.Chart || typeof Chart.getChart !== 'function') return;
        const canvas = document.getElementById('chart-activity');
        if (!canvas) return;
        const inst = Chart.getChart(canvas);
        if (!inst) return;
        try {
            inst.resize();
        } catch (e) { /* ignore */ }
    }

    function initInsightsToggle() {
        const bento = document.getElementById('crmDashBento');
        const btn = document.getElementById('crmDashInsightsToggle');
        if (!bento || !btn) return;

        const setOpen = (open) => {
            bento.classList.toggle('is-insights-open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open) {
                requestAnimationFrame(() => {
                    requestAnimationFrame(resizeDashCharts);
                });
            }
        };

        btn.addEventListener('click', () => {
            setOpen(!bento.classList.contains('is-insights-open'));
        });

        btn.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                setOpen(!bento.classList.contains('is-insights-open'));
            }
        });

        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(resizeDashCharts, 120);
        });

        const mq = window.matchMedia('(max-width: 768px)');
        const sync = () => {
            if (!mq.matches) {
                btn.setAttribute('aria-expanded', 'true');
            } else if (!bento.classList.contains('is-insights-open')) {
                btn.setAttribute('aria-expanded', 'false');
            }
        };
        sync();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', sync);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(sync);
        }
    }

    document.addEventListener('DOMContentLoaded', initInsightsToggle);
})();
