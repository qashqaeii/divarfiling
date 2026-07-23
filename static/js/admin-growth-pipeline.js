/* Growth Pipeline charts */
(function () {
  const el = document.getElementById('gp-charts-data');
  if (!el || typeof Chart === 'undefined') return;

  let data;
  try {
    data = JSON.parse(el.textContent || '{}');
  } catch (e) {
    return;
  }

  const teal = '#0d9488';
  const cyan = '#0891b2';
  const amber = '#d97706';
  const rose = '#e11d48';
  const violet = '#7c3aed';
  const slate = '#64748b';
  const palette = [teal, cyan, amber, violet, rose, '#2563eb', '#059669', '#ca8a04', '#db2777', '#4f46e5', slate];

  const common = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: { boxWidth: 10, font: { family: 'inherit', size: 11 } },
      },
      tooltip: {
        rtl: true,
        titleFont: { family: 'inherit' },
        bodyFont: { family: 'inherit' },
      },
    },
  };

  function mk(ctxId, conf) {
    const canvas = document.getElementById(ctxId);
    if (!canvas) return null;
    return new Chart(canvas.getContext('2d'), conf);
  }

  // Funnel as horizontal bar (descending visual via order)
  const funnel = data.funnel || {};
  mk('gp-chart-funnel', {
    type: 'bar',
    data: {
      labels: funnel.labels || [],
      datasets: [{
        label: 'تعداد',
        data: funnel.values || [],
        backgroundColor: [
          'rgba(13,148,136,.85)',
          'rgba(8,145,178,.8)',
          'rgba(37,99,235,.75)',
          'rgba(124,58,237,.7)',
          'rgba(217,119,6,.75)',
          'rgba(225,29,72,.7)',
          'rgba(5,150,105,.8)',
        ],
        borderRadius: 8,
        maxBarThickness: 28,
      }],
    },
    options: {
      ...common,
      indexAxis: 'y',
      plugins: { ...common.plugins, legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: 'rgba(148,163,184,.15)' }, ticks: { precision: 0 } },
        y: { grid: { display: false } },
      },
    },
  });

  const dist = data.distribution || {};
  mk('gp-chart-distribution', {
    type: 'doughnut',
    data: {
      labels: dist.labels || [],
      datasets: [{
        data: dist.values || [],
        backgroundColor: palette,
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 6,
      }],
    },
    options: {
      ...common,
      cutout: '62%',
      onClick: function (_evt, elements) {
        if (!elements.length) return;
        const idx = elements[0].index;
        const key = (dist.keys || [])[idx];
        if (key) window.location.search = '?stage=' + encodeURIComponent(key);
      },
    },
  });

  const trend = data.trend || {};
  const gradientFill = function (chart) {
    const ctx = chart.ctx;
    const area = chart.chartArea;
    if (!area) return 'rgba(13,148,136,.25)';
    const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
    g.addColorStop(0, 'rgba(13,148,136,.35)');
    g.addColorStop(1, 'rgba(13,148,136,.02)');
    return g;
  };

  mk('gp-chart-trend', {
    type: 'line',
    data: {
      labels: trend.labels || [],
      datasets: [{
        label: 'رویداد مسیر',
        data: trend.values || [],
        borderColor: teal,
        backgroundColor: function (ctx) {
          return gradientFill(ctx.chart);
        },
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
      }],
    },
    options: {
      ...common,
      plugins: { ...common.plugins, legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(148,163,184,.15)' } },
      },
    },
  });

  const events = data.events || {};
  mk('gp-chart-events', {
    type: 'bar',
    data: {
      labels: events.labels || [],
      datasets: [{
        label: 'تعداد',
        data: events.values || [],
        backgroundColor: cyan,
        borderRadius: 8,
        maxBarThickness: 34,
      }],
    },
    options: {
      ...common,
      plugins: { ...common.plugins, legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 0 } },
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: 'rgba(148,163,184,.15)' } },
      },
    },
  });

  const sources = data.sources || {};
  mk('gp-chart-sources', {
    type: 'polarArea',
    data: {
      labels: sources.labels || [],
      datasets: [{
        data: sources.values || [],
        backgroundColor: [
          'rgba(13,148,136,.7)',
          'rgba(8,145,178,.65)',
          'rgba(124,58,237,.6)',
        ],
      }],
    },
    options: {
      ...common,
      scales: {
        r: { ticks: { backdropColor: 'transparent', precision: 0 } },
      },
    },
  });

  // Guide modal
  const modal = document.getElementById('gp-guide-modal');
  const openBtn = document.getElementById('gp-guide-open');
  const closeBtns = document.querySelectorAll('[data-gp-guide-close]');
  function openGuide() {
    if (!modal) return;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function closeGuide() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = '';
  }
  if (openBtn) openBtn.addEventListener('click', openGuide);
  closeBtns.forEach(function (b) { b.addEventListener('click', closeGuide); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeGuide();
  });
})();
