(function () {
  'use strict';

  function persianDigits(n) {
    return String(n).replace(/\d/g, function (d) {
      return '۰۱۲۳۴۵۶۷۸۹'[d];
    });
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
    var root = document.documentElement;
    var isDark = document.documentElement.getAttribute('data-theme') !== 'light'
      && document.body.classList.contains('mk-public');
    return {
      text: isDark ? '#94a3b8' : '#64748b',
      grid: isDark ? 'rgba(148,163,184,0.12)' : 'rgba(148,163,184,0.22)',
      tooltipBg: isDark ? '#0f172a' : '#fff',
      tooltipText: isDark ? '#e2e8f0' : '#0f172a',
      border: isDark ? 'rgba(148,163,184,0.25)' : 'rgba(148,163,184,0.35)',
    };
  }

  function baseOptions(theme) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: theme.text,
            font: { weight: '700', size: 11 },
            padding: 14,
          },
        },
        tooltip: {
          backgroundColor: theme.tooltipBg,
          titleColor: theme.tooltipText,
          bodyColor: theme.tooltipText,
          borderColor: theme.border,
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function (ctx) {
              var label = ctx.dataset.label || ctx.label || '';
              var val = ctx.parsed.y != null ? ctx.parsed.y : ctx.parsed;
              if (typeof val === 'object' && val != null) val = val.x != null ? val.x : val.y;
              return label + ': ' + persianDigits(val);
            },
          },
        },
      },
    };
  }

  function renderRateStrip(rates) {
    var strip = document.getElementById('lac-rate-strip');
    if (!strip || !rates) return;
    var items = [
      { label: 'کلیک / ارسال', value: rates.click_rate, color: '#0891b2' },
      { label: 'ثبت‌نام / کلیک', value: rates.register_rate, color: '#6366f1' },
      { label: 'خرید / ثبت‌نام', value: rates.purchase_rate, color: '#e11d48' },
      { label: 'تبدیل کل', value: rates.overall_conversion, color: '#0d9488' },
    ];
    strip.innerHTML = items.map(function (item) {
      return (
        '<span class="adm-lac-rate-chip" style="--rate-color:' + item.color + '">' +
        '<small>' + item.label + '</small>' +
        '<strong>' + persianDigits(item.value) + '٪</strong>' +
        '</span>'
      );
    }).join('');
  }

  function renderFunnelVisual(funnel) {
    var wrap = document.getElementById('lac-funnel-visual');
    if (!wrap || !funnel || !funnel.values || !funnel.values.length) return;
    var max = Math.max.apply(null, funnel.values) || 1;
    wrap.innerHTML = funnel.labels.map(function (label, idx) {
      var val = funnel.values[idx] || 0;
      var pct = Math.max(4, Math.round((val / max) * 100));
      var color = (funnel.colors && funnel.colors[idx]) || '#0d9488';
      return (
        '<div class="adm-lac-funnel-step">' +
        '<div class="adm-lac-funnel-step__meta">' +
        '<span>' + label + '</span>' +
        '<strong>' + persianDigits(val) + '</strong>' +
        '</div>' +
        '<div class="adm-lac-funnel-step__track">' +
        '<div class="adm-lac-funnel-step__fill" style="width:' + pct + '%;background:' + color + '"></div>' +
        '</div>' +
        '</div>'
      );
    }).join('');
  }

  function destroyChart(id) {
    if (!window.Chart) return;
    var canvas = document.getElementById(id);
    if (!canvas) return;
    var existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
  }

  function initCharts(data) {
    if (!window.Chart || !data) return;

    var theme = themeColors();
    Chart.defaults.font.family = 'inherit';
    Chart.defaults.color = theme.text;

    renderRateStrip(data.rates);
    renderFunnelVisual(data.funnel);

    destroyChart('lac-chart-funnel');
    destroyChart('lac-chart-status');
    destroyChart('lac-chart-campaigns');
    destroyChart('lac-chart-variants');

    var funnelEl = document.getElementById('lac-chart-funnel');
    if (funnelEl && data.funnel) {
      new Chart(funnelEl, {
        type: 'bar',
        data: {
          labels: data.funnel.labels,
          datasets: [{
            label: 'تعداد',
            data: data.funnel.values,
            backgroundColor: (data.funnel.colors || []).map(function (c) { return c + 'cc'; }),
            borderColor: data.funnel.colors || [],
            borderWidth: 1.5,
            borderRadius: 8,
            borderSkipped: false,
          }],
        },
        options: Object.assign({}, baseOptions(theme), {
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: theme.grid },
              ticks: { color: theme.text },
            },
            y: {
              grid: { display: false },
              ticks: { color: theme.text, font: { weight: '700' } },
            },
          },
          plugins: Object.assign({}, baseOptions(theme).plugins, {
            legend: { display: false },
          }),
        }),
      });
    }

    var statusEl = document.getElementById('lac-chart-status');
    if (statusEl && data.status && data.status.values && data.status.values.length) {
      var statusColors = ['#0d9488', '#0891b2', '#6366f1', '#d97706', '#64748b', '#94a3b8'];
      new Chart(statusEl, {
        type: 'doughnut',
        data: {
          labels: data.status.labels,
          datasets: [{
            data: data.status.values,
            backgroundColor: statusColors.slice(0, data.status.values.length),
            borderWidth: 2,
            borderColor: theme.tooltipBg,
            hoverOffset: 6,
          }],
        },
        options: Object.assign({}, baseOptions(theme), {
          cutout: '62%',
          plugins: Object.assign({}, baseOptions(theme).plugins, {
            legend: { position: 'bottom' },
          }),
        }),
      });
    }

    var campaignsEl = document.getElementById('lac-chart-campaigns');
    if (campaignsEl && data.campaigns && data.campaigns.length) {
      var labels = data.campaigns.map(function (c) { return c.label; });
      new Chart(campaignsEl, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'ارسال',
              data: data.campaigns.map(function (c) { return c.accepted; }),
              backgroundColor: 'rgba(13,148,136,0.85)',
              borderRadius: 4,
            },
            {
              label: 'کلیک',
              data: data.campaigns.map(function (c) { return c.clicked; }),
              backgroundColor: 'rgba(8,145,178,0.85)',
              borderRadius: 4,
            },
            {
              label: 'ثبت‌نام',
              data: data.campaigns.map(function (c) { return c.registered; }),
              backgroundColor: 'rgba(99,102,241,0.85)',
              borderRadius: 4,
            },
            {
              label: 'خرید',
              data: data.campaigns.map(function (c) { return c.paid; }),
              backgroundColor: 'rgba(225,29,72,0.85)',
              borderRadius: 4,
            },
          ],
        },
        options: Object.assign({}, baseOptions(theme), {
          scales: {
            x: {
              stacked: false,
              grid: { display: false },
              ticks: { color: theme.text, maxRotation: 45, minRotation: 0, font: { size: 10 } },
            },
            y: {
              beginAtZero: true,
              grid: { color: theme.grid },
              ticks: { color: theme.text },
            },
          },
        }),
      });
    }

    var variantsEl = document.getElementById('lac-chart-variants');
    if (variantsEl && data.variants && data.variants.labels && data.variants.labels.length) {
      new Chart(variantsEl, {
        type: 'bar',
        data: {
          labels: data.variants.labels.map(function (k) { return 'نسخه ' + k; }),
          datasets: [
            {
              label: 'ارسال',
              data: data.variants.accepted,
              backgroundColor: 'rgba(13,148,136,0.85)',
              borderRadius: 6,
            },
            {
              label: 'کلیک',
              data: data.variants.clicked,
              backgroundColor: 'rgba(8,145,178,0.85)',
              borderRadius: 6,
            },
            {
              label: 'ثبت‌نام',
              data: data.variants.registered,
              backgroundColor: 'rgba(99,102,241,0.85)',
              borderRadius: 6,
            },
            {
              label: 'خرید',
              data: data.variants.paid,
              backgroundColor: 'rgba(225,29,72,0.85)',
              borderRadius: 6,
            },
          ],
        },
        options: Object.assign({}, baseOptions(theme), {
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: theme.text, font: { weight: '800' } },
            },
            y: {
              beginAtZero: true,
              grid: { color: theme.grid },
              ticks: { color: theme.text },
            },
          },
        }),
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
    ['lac-chart-funnel', 'lac-chart-status', 'lac-chart-campaigns', 'lac-chart-variants'].forEach(function (id) {
      var canvas = document.getElementById(id);
      if (!canvas) return;
      var inst = Chart.getChart(canvas);
      if (inst) inst.resize();
    });
  });
})();
