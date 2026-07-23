(function () {
  'use strict';

  var PALETTE = {
    teal: '#0d9488',
    cyan: '#0891b2',
    indigo: '#6366f1',
    rose: '#e11d48',
    slate: '#64748b',
  };

  function persianDigits(n) {
    return String(n).replace(/\d/g, function (d) {
      return '۰۱۲۳۴۵۶۷۸۹'[d];
    });
  }

  function formatNum(n) {
    if (n == null || n === '') return '—';
    var num = Number(n);
    if (Number.isNaN(num)) return String(n);
    return persianDigits(num.toLocaleString('en-US'));
  }

  function formatPct(n, digits) {
    if (n == null || n === '') return '—';
    var num = Number(n);
    if (Number.isNaN(num)) return '—';
    return persianDigits(num.toFixed(digits == null ? 1 : digits)) + '٪';
  }

  function formatMoney(n) {
    if (n == null || !n) return '—';
    return formatNum(n) + ' ریال';
  }

  function readChartData() {
    var el = document.getElementById('lac-charts-data');
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || el.innerHTML || '{}');
    } catch (e) {
      return null;
    }
  }

  function themeColors() {
    var isDark = document.documentElement.getAttribute('data-theme') !== 'light'
      && document.body.classList.contains('mk-public');
    return {
      text: isDark ? '#94a3b8' : '#64748b',
      textStrong: isDark ? '#e2e8f0' : '#0f172a',
      grid: isDark ? 'rgba(148,163,184,0.1)' : 'rgba(148,163,184,0.18)',
      tooltipBg: isDark ? 'rgba(15,23,42,0.96)' : 'rgba(255,255,255,0.98)',
      tooltipText: isDark ? '#f1f5f9' : '#0f172a',
      border: isDark ? 'rgba(148,163,184,0.22)' : 'rgba(148,163,184,0.28)',
      surface: isDark ? 'rgba(15,23,42,0.55)' : 'rgba(255,255,255,0.9)',
    };
  }

  function chartFont() {
    return { family: 'inherit', size: 11, weight: '600' };
  }

  function destroyChart(id) {
    if (!window.Chart) return;
    var canvas = document.getElementById(id);
    if (!canvas) return;
    var existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
  }

  function renderMeta(data) {
    var metaEl = document.getElementById('lac-analytics-meta');
    if (!metaEl || !data.meta) return;
    metaEl.textContent =
      formatNum(data.meta.reported_campaigns) + ' کمپین گزارش‌شده · ' +
      formatNum(data.meta.campaign_count) + ' کمپین در لیست';
  }

  function renderSummary(summary) {
    var strip = document.getElementById('lac-summary-strip');
    if (!strip || !summary) return;
    var items = [
      { label: 'ارسال پذیرفته', value: formatNum(summary.accepted), sub: 'پیامک موفق' },
      { label: 'کلیک', value: formatNum(summary.clicked), sub: 'CTR ' + formatPct(summary.ctr) },
      { label: 'ثبت‌نام', value: formatNum(summary.registered), sub: formatPct(summary.click_to_reg) + ' از کلیک' },
      { label: 'خرید', value: formatNum(summary.paid), sub: 'CVR ' + formatPct(summary.overall_cvr) },
      { label: 'درآمد', value: formatMoney(summary.revenue), sub: summary.roas ? 'ROAS ×' + persianDigits(summary.roas) : '—' },
      { label: 'هزینه SMS', value: formatMoney(summary.sms_cost), sub: summary.cac ? 'CAC ' + formatMoney(summary.cac) : '—' },
    ];
    strip.innerHTML = items.map(function (item) {
      return (
        '<article class="adm-lac-summary-pill">' +
        '<span class="adm-lac-summary-pill__label">' + item.label + '</span>' +
        '<strong class="adm-lac-summary-pill__value">' + item.value + '</strong>' +
        '<small class="adm-lac-summary-pill__sub">' + item.sub + '</small>' +
        '</article>'
      );
    }).join('');
  }

  function renderFunnelCascade(steps) {
    var wrap = document.getElementById('lac-funnel-cascade');
    if (!wrap || !steps || !steps.length) return;
    var max = Math.max.apply(null, steps.map(function (s) { return s.value; })) || 1;
    wrap.innerHTML = steps.map(function (step, idx) {
      var width = Math.max(18, Math.round((step.value / max) * 100));
      var drop = idx > 0 && step.drop_from_prev > 0
        ? '<span class="adm-lac-cascade__drop">↓ ' + formatPct(step.drop_from_prev, 1) + '</span>'
        : '';
      return (
        '<div class="adm-lac-cascade__row" style="--step-color:' + step.color + '">' +
        '<div class="adm-lac-cascade__label">' +
        '<span>' + step.label + '</span>' + drop +
        '</div>' +
        '<div class="adm-lac-cascade__bar">' +
        '<div class="adm-lac-cascade__fill" style="width:' + width + '%"></div>' +
        '</div>' +
        '<div class="adm-lac-cascade__nums">' +
        '<strong>' + formatNum(step.value) + '</strong>' +
        '<small>' + formatPct(step.share_of_top) + ' از کل</small>' +
        '</div>' +
        '</div>'
      );
    }).join('');
  }

  function renderCampaignTable(rows) {
    var body = document.getElementById('lac-campaign-table-body');
    if (!body) return;
    if (!rows || !rows.length) {
      body.innerHTML = '<tr><td colspan="12" class="adm-lac-table-empty">هنوز کمپینی ثبت نشده</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (row) {
      var pilot = row.is_pilot ? ' <span class="adm-lac-table-tag">پایلوت</span>' : '';
      return (
        '<tr>' +
        '<td class="adm-lac-table-name" title="' + (row.name || '') + '">' +
        '<a href="/accounts/admin-panel/marketing/lead-campaigns/' + row.id + '/">' +
        formatNum(row.id) + ' · ' + row.label + '</a>' + pilot +
        '</td>' +
        '<td><span class="adm-lac-table-status adm-lac-table-status--' + row.status + '">' +
        (row.status_display || row.status) + '</span></td>' +
        '<td>' + formatNum(row.eligible) + '</td>' +
        '<td>' + formatNum(row.enrolled) + '</td>' +
        '<td>' + formatNum(row.accepted) + '</td>' +
        '<td>' + formatNum(row.clicked) + '</td>' +
        '<td>' + formatNum(row.registered) + '</td>' +
        '<td><strong>' + formatNum(row.paid) + '</strong></td>' +
        '<td>' + formatPct(row.ctr) + '</td>' +
        '<td>' + formatPct(row.overall_cvr) + '</td>' +
        '<td>' + formatMoney(row.revenue) + '</td>' +
        '<td>' + formatMoney(row.sms_cost) + '</td>' +
        '</tr>'
      );
    }).join('');
  }

  function tooltipCallbacks(theme, summary) {
    return {
      backgroundColor: theme.tooltipBg,
      titleColor: theme.tooltipText,
      bodyColor: theme.tooltipText,
      borderColor: theme.border,
      borderWidth: 1,
      padding: 12,
      titleFont: { weight: '800', size: 12 },
      bodyFont: chartFont(),
      callbacks: {
        label: function (ctx) {
          var label = ctx.dataset.label || '';
          var val = ctx.parsed.y != null ? ctx.parsed.y : ctx.parsed.x;
          if (typeof val === 'object' && val != null) val = val.y != null ? val.y : val.x;
          return label + ': ' + formatNum(val);
        },
      },
    };
  }

  function initCharts(data) {
    if (!window.Chart || !data) return;

    var theme = themeColors();
    Chart.defaults.font.family = 'inherit';
    Chart.defaults.color = theme.text;

    renderMeta(data);
    renderSummary(data.summary);
    renderFunnelCascade(data.funnel_steps);
    renderCampaignTable(data.campaign_table);

    var statusSub = document.getElementById('lac-status-sub');
    if (statusSub && data.status) {
      statusSub.textContent = formatNum(data.status.total) + ' کمپین · ' +
        formatNum(data.status.values.length) + ' وضعیت فعال';
    }

    var variantSub = document.getElementById('lac-variant-sub');
    if (variantSub && data.variants) {
      variantSub.textContent = data.variants.winner
        ? 'پیشنهاد: نسخه ' + data.variants.winner + ' (بر اساس خرید و ثبت‌نام)'
        : 'پایلوت دو نسخه‌ای';
    }

    destroyChart('lac-chart-conversion');
    destroyChart('lac-chart-status');
    destroyChart('lac-chart-campaigns');
    destroyChart('lac-chart-variants');

    var convEl = document.getElementById('lac-chart-conversion');
    if (convEl && data.conversion_series) {
      new Chart(convEl, {
        type: 'line',
        data: {
          labels: data.conversion_series.labels,
          datasets: [{
            label: 'تبدیل مرحله‌ای',
            data: data.conversion_series.step_rates,
            borderColor: PALETTE.teal,
            backgroundColor: 'rgba(13,148,136,0.08)',
            borderWidth: 2.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: '#fff',
            pointBorderColor: PALETTE.teal,
            pointBorderWidth: 2,
            tension: 0.35,
            fill: true,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: tooltipCallbacks(theme),
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: theme.text, font: { weight: '700', size: 10 } },
            },
            y: {
              beginAtZero: true,
              max: 100,
              grid: { color: theme.grid },
              ticks: {
                color: theme.text,
                callback: function (v) { return formatPct(v, 0); },
              },
            },
          },
        },
      });
    }

    var statusEl = document.getElementById('lac-chart-status');
    var donutCenter = document.getElementById('lac-donut-center');
    if (statusEl && data.status && data.status.values && data.status.values.length) {
      if (donutCenter) {
        donutCenter.innerHTML =
          '<strong>' + formatNum(data.status.total) + '</strong>' +
          '<small>کمپین</small>';
      }
      new Chart(statusEl, {
        type: 'doughnut',
        data: {
          labels: data.status.labels,
          datasets: [{
            data: data.status.values,
            backgroundColor: data.status.colors || [],
            borderWidth: 0,
            hoverOffset: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: theme.text,
                boxWidth: 10,
                boxHeight: 10,
                padding: 12,
                font: chartFont(),
              },
            },
            tooltip: tooltipCallbacks(theme),
          },
        },
      });
    } else if (donutCenter) {
      donutCenter.innerHTML = '<strong>۰</strong><small>کمپین</small>';
    }

    var campaignsEl = document.getElementById('lac-chart-campaigns');
    if (campaignsEl && data.campaigns && data.campaigns.length) {
      var sorted = data.campaigns.slice().sort(function (a, b) {
        return (b.overall_cvr || 0) - (a.overall_cvr || 0);
      });
      new Chart(campaignsEl, {
        type: 'bar',
        data: {
          labels: sorted.map(function (c) { return c.label; }),
          datasets: [
            {
              label: 'CVR کل',
              data: sorted.map(function (c) { return c.overall_cvr; }),
              backgroundColor: 'rgba(13,148,136,0.88)',
              borderRadius: 6,
              barThickness: 14,
            },
            {
              label: 'CTR',
              data: sorted.map(function (c) { return c.ctr; }),
              backgroundColor: 'rgba(8,145,178,0.55)',
              borderRadius: 6,
              barThickness: 14,
            },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: { color: theme.text, font: chartFont(), boxWidth: 10 },
            },
            tooltip: {
              backgroundColor: theme.tooltipBg,
              titleColor: theme.tooltipText,
              bodyColor: theme.tooltipText,
              borderColor: theme.border,
              borderWidth: 1,
              padding: 12,
              callbacks: {
                afterBody: function (items) {
                  if (!items.length) return [];
                  var idx = items[0].dataIndex;
                  var row = sorted[idx];
                  return [
                    'ارسال: ' + formatNum(row.accepted),
                    'کلیک: ' + formatNum(row.clicked),
                    'ثبت‌نام: ' + formatNum(row.registered),
                    'خرید: ' + formatNum(row.paid),
                  ];
                },
                label: function (ctx) {
                  return ctx.dataset.label + ': ' + formatPct(ctx.parsed.x);
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              max: 100,
              grid: { color: theme.grid },
              ticks: {
                color: theme.text,
                callback: function (v) { return formatPct(v, 0); },
              },
            },
            y: {
              grid: { display: false },
              ticks: { color: theme.textStrong, font: { weight: '700', size: 10 } },
            },
          },
        },
      });
    }

    var variantsEl = document.getElementById('lac-chart-variants');
    var variantItems = (data.variants && data.variants.items) || [];
    if (variantsEl && variantItems.length) {
      new Chart(variantsEl, {
        type: 'radar',
        data: {
          labels: ['ارسال', 'کلیک', 'ثبت‌نام', 'خرید', 'CVR'],
          datasets: variantItems.map(function (v, idx) {
            var isWinner = data.variants.winner === v.key;
            var color = idx === 0 ? PALETTE.teal : PALETTE.indigo;
            var maxAccepted = Math.max.apply(null, variantItems.map(function (x) { return x.accepted; })) || 1;
            var maxPaid = Math.max.apply(null, variantItems.map(function (x) { return x.paid; })) || 1;
            return {
              label: 'نسخه ' + v.key + (isWinner ? ' ★' : ''),
              data: [
                Math.round((v.accepted / maxAccepted) * 100),
                v.ctr,
                v.click_to_reg,
                maxPaid ? Math.round((v.paid / maxPaid) * 100) : 0,
                v.overall_cvr,
              ],
              borderColor: color,
              backgroundColor: color + '22',
              borderWidth: isWinner ? 2.5 : 1.5,
              pointRadius: isWinner ? 4 : 3,
              pointBackgroundColor: color,
            };
          }),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { color: theme.text, font: chartFont(), boxWidth: 10 },
            },
            tooltip: {
              backgroundColor: theme.tooltipBg,
              titleColor: theme.tooltipText,
              bodyColor: theme.tooltipText,
              borderColor: theme.border,
              borderWidth: 1,
              callbacks: {
                label: function (ctx) {
                  var v = variantItems[ctx.datasetIndex];
                  if (!v) return ctx.formattedValue;
                  var map = [
                    'ارسال: ' + formatNum(v.accepted),
                    'CTR: ' + formatPct(v.ctr),
                    'ثبت‌نام/کلیک: ' + formatPct(v.click_to_reg),
                    'خرید: ' + formatNum(v.paid),
                    'CVR: ' + formatPct(v.overall_cvr),
                  ];
                  return map[ctx.dataIndex] || ctx.formattedValue;
                },
              },
            },
          },
          scales: {
            r: {
              beginAtZero: true,
              max: 100,
              ticks: {
                display: false,
                stepSize: 25,
              },
              grid: { color: theme.grid },
              angleLines: { color: theme.grid },
              pointLabels: {
                color: theme.textStrong,
                font: { weight: '800', size: 10 },
              },
            },
          },
        },
      });
    }
  }

  function boot() {
    var data = readChartData();
    if (!data) return;
    if (window.Chart) {
      initCharts(data);
      return;
    }
    var tries = 0;
    var timer = setInterval(function () {
      tries += 1;
      if (window.Chart) {
        clearInterval(timer);
        initCharts(data);
      } else if (tries > 40) {
        clearInterval(timer);
      }
    }, 100);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.addEventListener('resize', function () {
    if (!window.Chart) return;
    ['lac-chart-conversion', 'lac-chart-status', 'lac-chart-campaigns', 'lac-chart-variants'].forEach(function (id) {
      var canvas = document.getElementById(id);
      if (!canvas) return;
      var inst = Chart.getChart(canvas);
      if (inst) inst.resize();
    });
  });
})();
