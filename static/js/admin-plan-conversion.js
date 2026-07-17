(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toFa(n) {
        return String(n).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function isDark() {
        var html = document.documentElement;
        return html.classList.contains('mk-public') && html.getAttribute('data-theme') !== 'light';
    }

    function palette() {
        return {
            violet: isDark() ? 'rgba(124, 58, 237, 0.75)' : 'rgba(124, 58, 237, 0.65)',
            emerald: isDark() ? 'rgba(16, 185, 129, 0.75)' : 'rgba(16, 185, 129, 0.65)',
            blue: isDark() ? 'rgba(59, 130, 246, 0.75)' : 'rgba(59, 130, 246, 0.65)',
            amber: isDark() ? 'rgba(245, 158, 11, 0.75)' : 'rgba(245, 158, 11, 0.65)',
            grid: isDark() ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)',
            text: isDark() ? '#94a3b8' : '#64748b',
        };
    }

    function getData() {
        return window.admPlanConversion || {};
    }

    function baseOptions() {
        var c = palette();
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: c.text, font: { family: 'inherit' } },
                },
            },
            scales: {
                x: {
                    ticks: { color: c.text, maxRotation: 45 },
                    grid: { color: c.grid },
                },
                y: {
                    ticks: { color: c.text },
                    grid: { color: c.grid },
                },
            },
        };
    }

    function initNav() {
        var nav = document.getElementById('apc-nav');
        var spacer = document.getElementById('apc-nav-spacer');
        var indicator = document.getElementById('apc-nav-indicator');
        var items = nav ? nav.querySelectorAll('.ab-nav__item') : [];
        if (!nav || !indicator) return;

        var anchorTop = 0;

        function headerH() {
            var header = document.querySelector('.mk-site-header');
            return header ? header.getBoundingClientRect().height : 56;
        }

        function syncIndicator(active) {
            if (!active) return;
            indicator.style.width = active.offsetWidth + 'px';
            indicator.style.left = active.offsetLeft + 'px';
        }

        function measure() {
            nav.classList.remove('is-pinned');
            if (spacer) {
                spacer.classList.remove('is-active');
                spacer.style.height = '';
            }
            anchorTop = nav.getBoundingClientRect().top + window.scrollY;
            document.documentElement.style.setProperty('--ab-nav-h', nav.offsetHeight + 'px');
            syncIndicator(nav.querySelector('.ab-nav__item.is-active'));
        }

        function onScroll() {
            var hh = headerH();
            document.documentElement.style.setProperty('--ab-nav-top', hh + 'px');
            var pin = window.scrollY + hh >= anchorTop - 1;
            nav.classList.toggle('is-pinned', pin);
            if (spacer) {
                spacer.classList.toggle('is-active', pin);
                if (pin) spacer.style.height = nav.offsetHeight + 'px';
            }
        }

        items.forEach(function (item) {
            item.addEventListener('click', function () {
                setTimeout(function () {
                    items.forEach(function (t) { t.classList.remove('is-active'); });
                    item.classList.add('is-active');
                    syncIndicator(item);
                }, 0);
            });
        });

        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', function () { measure(); onScroll(); });
        measure();
        onScroll();
    }

    function initPanels() {
        var panels = document.querySelectorAll('.ab-panel');
        var navItems = document.querySelectorAll('#apc-nav .ab-nav__item');
        if (!panels.length) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var id = entry.target.id;
                navItems.forEach(function (item) {
                    item.classList.toggle('is-active', item.getAttribute('href') === '#' + id);
                });
                var indicator = document.getElementById('apc-nav-indicator');
                var active = document.querySelector('#apc-nav .ab-nav__item.is-active');
                if (indicator && active) {
                    indicator.style.width = active.offsetWidth + 'px';
                    indicator.style.left = active.offsetLeft + 'px';
                }
            });
        }, { rootMargin: '-20% 0px -60% 0px', threshold: 0.05 });

        panels.forEach(function (panel) { observer.observe(panel); });
    }

    function initCountUp() {
        document.querySelectorAll('[data-count]').forEach(function (el) {
            var target = parseInt(el.getAttribute('data-count'), 10) || 0;
            if (target <= 0) return;
            el.textContent = toFa(target.toLocaleString('en-US'));
        });
    }

    function initCharts() {
        if (typeof Chart === 'undefined') return;
        var data = getData();
        var c = palette();
        var opts = baseOptions();

        var funnelEl = document.getElementById('apc-chart-funnel');
        if (funnelEl && data.funnel_daily) {
            var fd = data.funnel_daily;
            new Chart(funnelEl, {
                type: 'line',
                data: {
                    labels: fd.purchase_labels.length ? fd.purchase_labels : fd.pricing_labels,
                    datasets: [
                        {
                            label: 'بازدید قیمت',
                            data: fd.pricing_counts,
                            borderColor: c.violet,
                            backgroundColor: c.violet.replace('0.75', '0.15').replace('0.65', '0.15'),
                            tension: 0.35,
                            fill: true,
                        },
                        {
                            label: 'شروع خرید',
                            data: fd.checkout_counts,
                            borderColor: c.amber,
                            backgroundColor: 'transparent',
                            tension: 0.35,
                        },
                        {
                            label: 'پرداخت موفق',
                            data: fd.purchase_counts,
                            borderColor: c.emerald,
                            backgroundColor: 'transparent',
                            tension: 0.35,
                        },
                    ],
                },
                options: opts,
            });
        }

        var shareEl = document.getElementById('apc-chart-share');
        if (shareEl && data.plan_share) {
            new Chart(shareEl, {
                type: 'doughnut',
                data: {
                    labels: data.plan_share.labels,
                    datasets: [{
                        data: data.plan_share.values,
                        backgroundColor: data.plan_share.colors,
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: c.text } },
                        tooltip: {
                            callbacks: {
                                label: function (ctx) {
                                    return toFa(ctx.label) + ': ' + toFa(ctx.parsed) + '٪';
                                },
                            },
                        },
                    },
                },
            });
        }

        var convEl = document.getElementById('apc-chart-conversion');
        if (convEl && data.plan_conversion) {
            var pc = data.plan_conversion;
            new Chart(convEl, {
                type: 'bar',
                data: {
                    labels: pc.labels,
                    datasets: [
                        {
                            label: 'تبدیل قیف (٪)',
                            data: pc.funnel_rates,
                            backgroundColor: c.violet,
                            borderRadius: 8,
                        },
                        {
                            label: 'تبدیل Checkout (٪)',
                            data: pc.checkout_rates,
                            backgroundColor: c.emerald,
                            borderRadius: 8,
                        },
                    ],
                },
                options: opts,
            });
        }

        var weeklyEl = document.getElementById('apc-chart-weekly');
        if (weeklyEl && data.weekly_purchases) {
            var wp = data.weekly_purchases;
            new Chart(weeklyEl, {
                type: 'bar',
                data: {
                    labels: wp.labels,
                    datasets: [
                        { label: 'کل خرید', data: wp.total, backgroundColor: c.violet, borderRadius: 6 },
                        { label: '۱روزه', data: wp.daily, backgroundColor: c.emerald, borderRadius: 6 },
                        { label: '۱ماهه', data: wp.monthly, backgroundColor: c.blue, borderRadius: 6 },
                    ],
                },
                options: opts,
            });
        }

        var cohortEl = document.getElementById('apc-chart-cohort');
        if (cohortEl && data.cohort) {
            var ch = data.cohort;
            new Chart(cohortEl, {
                type: 'line',
                data: {
                    labels: ch.labels,
                    datasets: [
                        {
                            label: 'تکرار ۷روز (٪)',
                            data: ch.repeat_7d_rate,
                            borderColor: c.amber,
                            tension: 0.35,
                        },
                        {
                            label: 'تکرار ۳۰روز (٪)',
                            data: ch.repeat_30d_rate,
                            borderColor: c.blue,
                            tension: 0.35,
                        },
                        {
                            label: 'ارتقا ماهانه ۷روز (٪)',
                            data: ch.upgrade_rate,
                            borderColor: c.emerald,
                            tension: 0.35,
                        },
                    ],
                },
                options: opts,
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initNav();
        initPanels();
        initCountUp();
        initCharts();
    });
})();
