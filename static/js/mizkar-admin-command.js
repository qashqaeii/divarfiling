(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatMoneyShort(value) {
        var n = Number(value) || 0;
        if (n >= 1000000000) {
            return toPersianDigits((n / 1000000000).toFixed(1).replace(/\.0$/, '')) + 'B';
        }
        if (n >= 1000000) {
            return toPersianDigits((n / 1000000).toFixed(1).replace(/\.0$/, '')) + 'M';
        }
        if (n >= 1000) {
            return toPersianDigits((n / 1000).toFixed(0)) + 'K';
        }
        return toPersianDigits(n.toLocaleString('en-US'));
    }

    function formatMoneyFull(value) {
        return toPersianDigits(Number(value || 0).toLocaleString('en-US'));
    }

    function getThemeColors() {
        var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        return {
            text: isDark ? '#94a3b8' : '#64748b',
            grid: isDark ? 'rgba(148, 163, 184, 0.1)' : 'rgba(148, 163, 184, 0.14)',
            tooltipBg: isDark ? 'rgba(15, 23, 42, 0.96)' : 'rgba(255, 255, 255, 0.98)',
            tooltipText: isDark ? '#e2e8f0' : '#0f172a',
            border: isDark ? 'rgba(148, 163, 184, 0.15)' : 'rgba(15, 23, 42, 0.08)',
        };
    }

    function qs(sel, root) {
        return (root || document).querySelector(sel);
    }

    function qsa(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function initCommandQueueNav() {
        qsa('.adm-cmd-queue__row[data-cmd-nav], .adm-overview-actions__row[data-cmd-nav]').forEach(function (link) {
            link.addEventListener('click', function (ev) {
                var href = link.getAttribute('href') || '';
                if (!href || href.charAt(0) === '#') {
                    return;
                }
                if (href.indexOf('/accounts/admin-panel/') === 0 || href.indexOf('http') === 0) {
                    ev.stopPropagation();
                    window.location.assign(href);
                }
            });
        });
    }

    function initOverviewDualChart(cfg) {
        var canvas = document.getElementById('chart-revenue-analytics');
        if (!canvas || typeof Chart === 'undefined' || !cfg.series) return;

        var theme = getThemeColors();
        var rev = cfg.series.revenue || {};
        var ord = cfg.series.orders || {};
        var chartInst = new Chart(canvas, {
            type: 'line',
            data: {
                labels: cfg.labels || [],
                datasets: [
                    {
                        label: rev.label || 'درآمد',
                        data: rev.data || [],
                        borderColor: '#5B4FCF',
                        backgroundColor: 'rgba(91, 79, 207, 0.12)',
                        fill: true,
                        tension: 0.38,
                        borderWidth: 2.5,
                        pointRadius: 0,
                        yAxisID: 'y',
                    },
                    {
                        label: ord.label || 'سفارش',
                        data: ord.data || [],
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.08)',
                        fill: true,
                        tension: 0.38,
                        borderWidth: 2.5,
                        pointRadius: 0,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 920,
                    easing: 'easeOutQuart',
                },
                animations: {
                    x: { duration: 0 },
                    y: {
                        duration: 920,
                        easing: 'easeOutQuart',
                    },
                },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        rtl: true,
                        backgroundColor: theme.tooltipBg,
                        titleColor: theme.tooltipText,
                        bodyColor: theme.tooltipText,
                        borderColor: theme.border,
                        borderWidth: 1,
                        callbacks: {
                            title: function (items) {
                                if (!items.length) return '';
                                return toPersianDigits(items[0].label || '');
                            },
                            label: function (ctx) {
                                var val = ctx.parsed.y;
                                if (ctx.datasetIndex === 0) {
                                    return (rev.label || 'درآمد') + ': ' + formatMoneyFull(val) + ' تومان';
                                }
                                return (ord.label || 'سفارش') + ': ' + toPersianDigits(val);
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            color: theme.text,
                            font: { family: 'Vazirmatn, Tahoma, sans-serif', size: 10 },
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 10,
                            callback: function (v) {
                                return toPersianDigits(this.getLabelForValue(v));
                            },
                        },
                        grid: { color: theme.grid, drawBorder: false },
                        border: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        position: 'left',
                        ticks: {
                            color: theme.text,
                            callback: function (val) {
                                return formatMoneyShort(val);
                            },
                        },
                        grid: { color: theme.grid, drawBorder: false },
                    },
                    y1: {
                        beginAtZero: true,
                        position: 'right',
                        ticks: {
                            color: theme.text,
                            callback: function (val) {
                                return toPersianDigits(val);
                            },
                        },
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });
        window.admCommandChart = chartInst;

        var chartRoot = canvas.closest('.adm-overview-chart--dual');
        if (chartRoot) {
            window.requestAnimationFrame(function () {
                chartRoot.classList.add('is-chart-ready');
            });
        }

        if (chartInst && typeof ResizeObserver !== 'undefined') {
            var wrap = canvas.closest('.adm-overview-chart__canvas');
            if (wrap) {
                var resizeTick = function () {
                    window.requestAnimationFrame(function () {
                        try {
                            chartInst.resize();
                        } catch (e) {
                            /* noop */
                        }
                    });
                };
                new ResizeObserver(resizeTick).observe(wrap);
                resizeTick();
            }
        }
    }

    function initCommandChartToggle() {
        var cfg = window.admCharts && window.admCharts.revenue_analytics;
        if (!cfg || cfg.type !== 'command_trend') return;

        if (qs('.adm-overview-chart--dual')) {
            initOverviewDualChart(cfg);
            return;
        }

        var grainEl = qs('#adm-cmd-chart-grain');
        if (grainEl && cfg.bucketLabelFa) {
            var range = grainEl.textContent.trim();
            grainEl.textContent = range + ' · ' + cfg.bucketLabelFa;
        }

        var chartInst = null;
        var active = cfg.defaultSeries || 'revenue';

        function render(seriesKey) {
            var canvas = document.getElementById('chart-revenue-analytics');
            if (!canvas || typeof Chart === 'undefined') return;
            var series = cfg.series && cfg.series[seriesKey];
            if (!series) return;

            if (chartInst) {
                chartInst.destroy();
            }

            var theme = getThemeColors();
            var axis = series.axis || 'count';

            chartInst = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: cfg.labels || [],
                    datasets: [{
                        label: series.label,
                        data: series.data || [],
                        borderColor: series.borderColor,
                        backgroundColor: series.backgroundColor,
                        fill: true,
                        tension: 0.38,
                        borderWidth: 2.5,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        pointHoverBorderWidth: 2,
                        pointBackgroundColor: series.borderColor,
                        pointBorderColor: '#ffffff',
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 650, easing: 'easeOutQuart' },
                    interaction: { mode: 'index', intersect: false },
                    layout: { padding: { top: 8, right: 6, left: 4, bottom: 4 } },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            rtl: true,
                            backgroundColor: theme.tooltipBg,
                            titleColor: theme.tooltipText,
                            bodyColor: theme.tooltipText,
                            borderColor: theme.border,
                            borderWidth: 1,
                            padding: 12,
                            titleFont: { family: 'Vazirmatn, Tahoma, sans-serif', weight: '700', size: 12 },
                            bodyFont: { family: 'Vazirmatn, Tahoma, sans-serif', size: 11 },
                            displayColors: true,
                            callbacks: {
                                title: function (items) {
                                    if (!items.length) return '';
                                    return toPersianDigits(items[0].label || '');
                                },
                                label: function (ctx) {
                                    var val = ctx.parsed.y;
                                    if (axis === 'money') {
                                        return series.label + ': ' + formatMoneyFull(val) + ' تومان';
                                    }
                                    return series.label + ': ' + toPersianDigits(val);
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: {
                                color: theme.text,
                                font: { family: 'Vazirmatn, Tahoma, sans-serif', size: 10, weight: '500' },
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12,
                                callback: function (v) {
                                    var lbl = this.getLabelForValue(v);
                                    return toPersianDigits(lbl);
                                },
                            },
                            grid: { color: theme.grid, drawBorder: false },
                            border: { display: false },
                        },
                        y: {
                            position: 'left',
                            beginAtZero: true,
                            ticks: {
                                color: theme.text,
                                font: { family: 'Vazirmatn, Tahoma, sans-serif', size: 10, weight: '500' },
                                padding: 8,
                                callback: function (val) {
                                    if (axis === 'money') return formatMoneyShort(val);
                                    return toPersianDigits(val);
                                },
                            },
                            grid: { color: theme.grid, drawBorder: false },
                            border: { display: false },
                        },
                    },
                },
            });
            window.admCommandChart = chartInst;
        }

        qsa('[data-cmd-chart-series]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var key = btn.getAttribute('data-cmd-chart-series');
                if (!key || key === active) return;
                active = key;
                qsa('[data-cmd-chart-series]').forEach(function (b) {
                    var on = b === btn;
                    b.classList.toggle('is-active', on);
                    b.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                var head = qs('.adm-cmd-chart__head h2');
                if (head) {
                    head.textContent = key === 'revenue' ? 'روند درآمد' : 'روند سفارش موفق';
                }
                render(key);
            });
        });

        render(active);

        if (typeof ResizeObserver !== 'undefined') {
            var wrap = document.querySelector('.adm-cmd-chart__canvas');
            if (wrap) {
                var ro = new ResizeObserver(function () {
                    if (chartInst) {
                        try {
                            chartInst.resize();
                        } catch (e) {
                            /* noop */
                        }
                    }
                });
                ro.observe(wrap);
            }
        }
    }

    function initOverviewHealthModal() {
        if (!document.body.classList.contains('adm-overview-active')) return;
        var dataEl = document.getElementById('adm-overview-health-data');
        var modal = document.getElementById('adm-overview-health-modal');
        if (!dataEl || !modal) return;

        var payload;
        try {
            payload = JSON.parse(dataEl.textContent || '{}');
        } catch (e) {
            return;
        }

        var byKey = payload.indicators || {};
        var score = payload.score || null;
        var titleEl = document.getElementById('adm-ov-health-modal-title');
        var badgeEl = document.getElementById('adm-ov-health-modal-badge');
        var reasonEl = document.getElementById('adm-ov-health-modal-reason');
        var factsEl = document.getElementById('adm-ov-health-modal-facts');
        var ruleEl = document.getElementById('adm-ov-health-modal-rule');
        var actionEl = document.getElementById('adm-ov-health-modal-action');
        var linkEl = document.getElementById('adm-ov-health-modal-link');
        var linkTextEl = document.getElementById('adm-ov-health-modal-link-text');
        var lastFocus = null;

        function renderFacts(facts) {
            if (!factsEl) return;
            factsEl.innerHTML = '';
            (facts || []).forEach(function (line) {
                var li = document.createElement('li');
                li.textContent = line;
                factsEl.appendChild(li);
            });
        }

        function openModal(key) {
            var item = key === 'score' ? score : byKey[key];
            if (!item) return;
            lastFocus = document.activeElement;
            if (titleEl) titleEl.textContent = item.label || item.title || '—';
            if (badgeEl) {
                badgeEl.textContent = item.status_label || '—';
                badgeEl.setAttribute('data-status', item.status || 'ok');
            }
            if (reasonEl) reasonEl.textContent = item.reason || '';
            if (ruleEl) ruleEl.textContent = item.rule || '';
            if (actionEl) actionEl.textContent = item.action || '';
            if (linkEl) {
                if (item.href) {
                    linkEl.href = item.href;
                    linkEl.hidden = false;
                    if (linkTextEl) {
                        linkTextEl.textContent = item.link_label || 'رفتن به بخش مربوطه';
                    }
                } else {
                    linkEl.hidden = true;
                    linkEl.removeAttribute('href');
                }
            }
            renderFacts(item.facts);
            modal.hidden = false;
            modal.setAttribute('aria-hidden', 'false');
            document.body.classList.add('adm-ov-health-modal-open');
            var closeBtn = qs('.adm-ov-health-modal__close', modal);
            if (closeBtn) closeBtn.focus();
        }

        function closeModal() {
            modal.hidden = true;
            modal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('adm-ov-health-modal-open');
            if (lastFocus && typeof lastFocus.focus === 'function') {
                lastFocus.focus();
            }
        }

        if (linkEl) {
            linkEl.addEventListener('click', function () {
                if (!modal.hidden) {
                    closeModal();
                }
            });
        }

        qsa('[data-health-key]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                openModal(btn.getAttribute('data-health-key'));
            });
        });

        qsa('[data-ov-health-close]', modal).forEach(function (el) {
            el.addEventListener('click', closeModal);
        });

        document.addEventListener('keydown', function (ev) {
            if (modal.hidden) return;
            if (ev.key === 'Escape') {
                ev.preventDefault();
                closeModal();
            }
        });
    }

    function init() {
        if (!document.body.classList.contains('adm-prime-command')) return;
        initCommandQueueNav();
        initCommandChartToggle();
        initOverviewHealthModal();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
