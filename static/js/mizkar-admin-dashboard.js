(function () {
    'use strict';

    const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatMoneyShort(value) {
        const n = Number(value) || 0;
        if (n >= 1_000_000_000) {
            return toPersianDigits((n / 1_000_000_000).toFixed(1).replace(/\.0$/, '')) + 'B';
        }
        if (n >= 1_000_000) {
            return toPersianDigits((n / 1_000_000).toFixed(1).replace(/\.0$/, '')) + 'M';
        }
        if (n >= 1_000) {
            return toPersianDigits((n / 1_000).toFixed(0)) + 'K';
        }
        return toPersianDigits(n.toLocaleString('en-US'));
    }

    function formatJalaliLabel(isoDate) {
        if (!isoDate) return '';
        try {
            const parts = isoDate.split('-');
            if (parts.length === 3) {
                return toPersianDigits(parts[1] + '/' + parts[2]);
            }
        } catch (e) { /* ignore */ }
        return isoDate;
    }

    function getThemeColors() {
        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        return {
            text: isDark ? '#94a3b8' : '#64748b',
            grid: isDark ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)',
            tooltipBg: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.98)',
            tooltipText: isDark ? '#e2e8f0' : '#1e293b',
        };
    }

    function baseOptions(chartConfig) {
        const theme = getThemeColors();
        const axis = chartConfig.axis || 'count';

        const tickCallback = function (val) {
            if (axis === 'money') return formatMoneyShort(val);
            return toPersianDigits(val);
        };

        const opts = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: chartConfig.type === 'doughnut',
                    position: 'bottom',
                    rtl: true,
                    labels: {
                        color: theme.text,
                        font: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif', size: 11 },
                        padding: 12,
                    },
                },
                tooltip: {
                    rtl: true,
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipText,
                    bodyColor: theme.tooltipText,
                    titleFont: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif' },
                    bodyFont: { family: 'Vazirmatn, Vazir, Tahoma, sans-serif' },
                    callbacks: {
                        label: function (ctx) {
                            const val = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
                            const label = ctx.dataset.label || '';
                            if (axis === 'money') {
                                return label + ': ' + toPersianDigits(Number(val).toLocaleString('en-US')) + ' تومان';
                            }
                            return label + ': ' + toPersianDigits(val);
                        },
                    },
                },
            },
        };

        if (chartConfig.type !== 'doughnut') {
            opts.scales = {
                x: {
                    ticks: {
                        color: theme.text,
                        font: { size: 10 },
                        maxRotation: 0,
                        callback: function (val, idx) {
                            const label = this.getLabelForValue(val);
                            return formatJalaliLabel(label);
                        },
                    },
                    grid: { color: theme.grid },
                },
                y: {
                    ticks: {
                        color: theme.text,
                        font: { size: 10 },
                        callback: tickCallback,
                    },
                    grid: { color: theme.grid },
                    beginAtZero: true,
                },
            };

            if (chartConfig.horizontal) {
                opts.indexAxis = 'y';
                opts.scales.x.ticks.callback = tickCallback;
                opts.scales.y.ticks.callback = function (val) {
                    const label = this.getLabelForValue(val);
                    return label.length > 22 ? label.slice(0, 22) + '…' : label;
                };
            }
        }

        return opts;
    }

    function renderChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !config || typeof Chart === 'undefined') return null;

        return new Chart(canvas, {
            type: config.type,
            data: {
                labels: config.labels,
                datasets: config.datasets,
            },
            options: baseOptions(config),
        });
    }

    function initAdminDashboard() {
        const charts = window.admCharts;
        if (!charts) return;

        const instances = [];

        const mapping = [
            ['chart-revenue', charts.revenue_trend],
            ['chart-signups', charts.user_signups],
            ['chart-order-status', charts.order_status],
            ['chart-license-status', charts.license_status],
            ['chart-plans', charts.plan_sales],
            ['chart-payment', charts.payment_methods],
        ];

        mapping.forEach(function (item) {
            const inst = renderChart(item[0], item[1]);
            if (inst) instances.push(inst);
        });

        document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setTimeout(function () {
                    instances.forEach(function (chart) {
                        const theme = getThemeColors();
                        if (chart.options.plugins.legend) {
                            chart.options.plugins.legend.labels.color = theme.text;
                        }
                        if (chart.options.plugins.tooltip) {
                            chart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
                            chart.options.plugins.tooltip.titleColor = theme.tooltipText;
                            chart.options.plugins.tooltip.bodyColor = theme.tooltipText;
                        }
                        if (chart.options.scales) {
                            ['x', 'y'].forEach(function (axis) {
                                if (chart.options.scales[axis]) {
                                    chart.options.scales[axis].ticks.color = theme.text;
                                    chart.options.scales[axis].grid.color = theme.grid;
                                }
                            });
                        }
                        chart.update('none');
                    });
                }, 50);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAdminDashboard);
    } else {
        initAdminDashboard();
    }

    function initTabs() {
        const tabs = document.querySelectorAll('.adm-tab');
        const sections = ['adm-overview', 'adm-reports', 'adm-exports'];

        function setActiveTab(hash) {
            const id = (hash || '#adm-overview').replace('#', '');
            tabs.forEach(function (tab) {
                const href = tab.getAttribute('href') || '';
                tab.classList.toggle('is-active', href === '#' + id);
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                setActiveTab(tab.getAttribute('href'));
            });
        });

        function onScroll() {
            let current = sections[0];
            sections.forEach(function (id) {
                const el = document.getElementById(id);
                if (el && el.getBoundingClientRect().top <= 120) {
                    current = id;
                }
            });
            setActiveTab('#' + current);
        }

        window.addEventListener('scroll', onScroll, { passive: true });
        setActiveTab(window.location.hash || '#adm-overview');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTabs);
    } else {
        initTabs();
    }
})();
