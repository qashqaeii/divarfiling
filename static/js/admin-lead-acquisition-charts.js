(function () {
  'use strict';

  var PALETTE = {
    teal: '#0d9488',
    cyan: '#0891b2',
    indigo: '#6366f1',
    violet: '#5b4fcf',
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
    var family = 'Vazirmatn, Tahoma, sans-serif';
    try {
      var root = document.querySelector('.biz-page--leads.leads-v3');
      if (root) {
        var computed = window.getComputedStyle(root).fontFamily;
        if (computed) family = computed;
      }
    } catch (e) { /* noop */ }
    return { family: family, size: 12, weight: '600' };
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
    var range = data.meta.range_label ? data.meta.range_label + ' · ' : '';
    metaEl.textContent =
      range +
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
        '<article class="adm-lac-summary-pill adm-lac-summary-pill--pro">' +
        '<span class="adm-lac-summary-pill__label">' + item.label + '</span>' +
        '<strong class="adm-lac-summary-pill__value">' + item.value + '</strong>' +
        '<small class="adm-lac-summary-pill__sub">' + item.sub + '</small>' +
        '</article>'
      );
    }).join('');
  }

  function stepMetaLine(step, idx) {
    if (idx === 0) return 'نقطه شروع قیف';
    var conv = step.step_conversion;
    if (conv == null || conv === '') return '—';
    if (Number(conv) > 100.5) {
      return 'بیش از مرحله قبل · ' + formatPct(conv, 1);
    }
    if (Number(conv) >= 99.95) {
      return 'تبدیل از قبل · ' + formatPct(conv, 1);
    }
    return 'مانده از قبل · ' + formatPct(conv, 1);
  }

  function renderConversionInsights(rates, summary, funnelSteps) {
    var el = document.getElementById('lac-conversion-insights');
    if (!el) return;
    rates = rates || {};
    summary = summary || {};
    var items = [
      {
        key: 'ctr',
        label: 'کلیک از پیامک',
        value: rates.click_rate,
        foot: summary.accepted ? formatNum(summary.accepted) + ' پیامک پذیرفته' : '—',
        accent: 'cyan',
      },
      {
        key: 'reg',
        label: 'ثبت‌نام از کلیک',
        value: rates.register_rate,
        foot: summary.clicked ? formatNum(summary.clicked) + ' کلیک یکتا' : '—',
        accent: 'violet',
      },
      {
        key: 'paid',
        label: 'خرید از ثبت‌نام',
        value: rates.purchase_rate,
        foot: summary.registered ? formatNum(summary.registered) + ' ثبت‌نام' : '—',
        accent: 'indigo',
      },
      {
        key: 'cvr',
        label: 'CVR کل قیف',
        value: rates.overall_conversion,
        foot: summary.paid != null ? formatNum(summary.paid) + ' خرید نهایی' : '—',
        accent: 'teal',
      },
    ];
    var weakest = null;
    if (funnelSteps && funnelSteps.length > 1) {
      funnelSteps.slice(1).forEach(function (step) {
        var v = Number(step.step_conversion);
        if (Number.isNaN(v) || v <= 0) return;
        if (v > 100) return;
        if (!weakest || v < weakest.rate) {
          weakest = { label: step.label, rate: v };
        }
      });
    }
    var sub = document.getElementById('lac-conversion-sub');
    if (sub) {
      sub.textContent = weakest
        ? 'ضعیف‌ترین پیوند: ' + weakest.label + ' · ' + formatPct(weakest.rate, 1)
        : 'نرخ‌های کلیدی و افت بین مراحل قیف';
    }
    el.innerHTML = items.map(function (item) {
      var pct = item.value != null ? formatPct(item.value, 1) : '—';
      return (
        '<div class="adm-lac-conversion-metric" data-accent="' + item.accent + '">' +
        '<div class="adm-lac-conversion-metric__row">' +
        '<span class="adm-lac-conversion-metric__label">' + item.label + '</span>' +
        '<strong class="adm-lac-conversion-metric__value">' + pct + '</strong>' +
        '</div>' +
        '<span class="adm-lac-conversion-metric__ctx">' + item.foot + '</span>' +
        '</div>'
      );
    }).join('');
  }

  function renderFunnelCascade(steps) {
    var wrap = document.getElementById('lac-funnel-cascade');
    if (!wrap || !steps || !steps.length) return;
    var max = Math.max.apply(null, steps.map(function (s) { return s.value; })) || 1;
    var overflow = steps.some(function (s, i) { return i > 0 && Number(s.share_of_top) > 100.5; });
    var parts = [
      '<header class="adm-lac-cascade-pro__head">',
      '<p class="adm-lac-cascade-pro__title">قیف تجمیعی</p>',
      overflow
        ? '<span class="adm-lac-cascade-pro__note" title="برخی مراحل به‌خاطر هم‌پوشانی ثبت کمپین می‌توانند از «واجد شرایط» بیشتر شوند">هم‌پوشانی ثبت</span>'
        : '',
      '</header>',
      '<div class="adm-lac-cascade-pro__track" role="list" style="--cascade-cols:' + steps.length + '">',
    ];
    steps.forEach(function (step, idx) {
      var width = Math.max(12, Math.round((step.value / max) * 100));
      var meta = stepMetaLine(step, idx);
      var stepOverflow = idx > 0 && Number(step.step_conversion) > 100.5;
      parts.push(
        '<article class="adm-lac-cascade-pro__step' +
        (stepOverflow ? ' is-overflow' : '') +
        '" role="listitem" style="--step-accent:' +
        (step.color || '#5b4fcf') +
        '" title="' +
        (step.label + ' · ' + meta).replace(/"/g, '&quot;') +
        '">' +
        '<div class="adm-lac-cascade-pro__step-top">' +
        '<span class="adm-lac-cascade-pro__step-ix" aria-hidden="true">' +
        persianDigits(String(idx + 1)) +
        '</span>' +
        '<span class="adm-lac-cascade-pro__step-label">' +
        step.label +
        '</span>' +
        '<strong class="adm-lac-cascade-pro__step-value">' +
        formatNum(step.value) +
        '</strong>' +
        '</div>' +
        '<div class="adm-lac-cascade-pro__step-bar" aria-hidden="true">' +
        '<i style="width:' +
        width +
        '%"></i>' +
        '</div>' +
        '<span class="adm-lac-cascade-pro__step-meta">' +
        meta +
        '</span>' +
        '</article>'
      );
    });
    parts.push('</div>');
    wrap.innerHTML = parts.join('');
    wrap.classList.add('is-ready');
  }

  var CAMPAIGN_TABLE_PAGE = 8;
  var campaignTableState = {
    allRows: [],
    totals: null,
    query: '',
    sort: 'newest',
    visibleLimit: CAMPAIGN_TABLE_PAGE,
    bound: false,
  };

  function normalizeSearchQuery(q) {
    return String(q || '')
      .trim()
      .toLowerCase()
      .replace(/^#/, '')
      .replace(/\s+/g, ' ');
  }

  function rowMatchesSearch(row, query) {
    if (!query) return true;
    var idStr = String(row.id || '');
    var haystack = [
      idStr,
      row.name || '',
      row.label || '',
      row.status_display || '',
      row.status || '',
    ]
      .join(' ')
      .toLowerCase();
    if (haystack.indexOf(query) !== -1) return true;
    if (/^\d+$/.test(query) && idStr === query) return true;
    return false;
  }

  function sortCampaignRows(rows, sortKey) {
    var list = rows.slice();
    var cmpName = function (a, b) {
      var an = (a.name || a.label || '').trim();
      var bn = (b.name || b.label || '').trim();
      try {
        return an.localeCompare(bn, 'fa', { sensitivity: 'base', numeric: true });
      } catch (e) {
        return an < bn ? -1 : an > bn ? 1 : 0;
      }
    };
    list.sort(function (a, b) {
      var aid = Number(a.id) || 0;
      var bid = Number(b.id) || 0;
      switch (sortKey) {
        case 'paid': {
          var dp = (Number(b.paid) || 0) - (Number(a.paid) || 0);
          return dp !== 0 ? dp : bid - aid;
        }
        case 'accepted': {
          var da = (Number(b.accepted) || 0) - (Number(a.accepted) || 0);
          return da !== 0 ? da : bid - aid;
        }
        case 'cvr': {
          var dc = (Number(b.overall_cvr) || 0) - (Number(a.overall_cvr) || 0);
          return dc !== 0 ? dc : bid - aid;
        }
        case 'name': {
          var cn = cmpName(a, b);
          return cn !== 0 ? cn : bid - aid;
        }
        case 'newest':
        default: {
          if (a.created_at && b.created_at && a.created_at !== b.created_at) {
            return a.created_at < b.created_at ? 1 : -1;
          }
          return bid - aid;
        }
      }
    });
    return list;
  }

  function buildCampaignRowHtml(row) {
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
  }

  function updateCampaignTableChrome(filteredCount, visibleCount) {
    var countEl = document.getElementById('lac-campaign-table-count');
    if (countEl) {
      if (!filteredCount) {
        countEl.textContent = '';
      } else if (visibleCount >= filteredCount) {
        countEl.textContent =
          persianDigits(String(filteredCount)) + ' کمپین' +
          (campaignTableState.query ? ' (فیلترشده)' : '');
      } else {
        countEl.textContent =
          'نمایش ' + formatNum(visibleCount) + ' از ' + formatNum(filteredCount) + ' کمپین';
      }
    }
    var moreBtn = document.getElementById('lac-campaign-table-more');
    var scrollEl = document.querySelector('.adm-lac-table-scroll--pro');
    var remaining = filteredCount - visibleCount;
    if (moreBtn) {
      if (remaining > 0) {
        moreBtn.hidden = false;
        moreBtn.textContent =
          'نمایش ' + formatNum(Math.min(CAMPAIGN_TABLE_PAGE, remaining)) + ' کمپین دیگر';
      } else {
        moreBtn.hidden = true;
      }
    }
    if (scrollEl) {
      scrollEl.classList.toggle('is-truncated', remaining > 0);
    }
  }

  function refreshCampaignTableView() {
    var body = document.getElementById('lac-campaign-table-body');
    if (!body) return;
    var rows = campaignTableState.allRows || [];
    var query = normalizeSearchQuery(campaignTableState.query);
    var filtered = rows.filter(function (row) {
      return rowMatchesSearch(row, query);
    });
    var sorted = sortCampaignRows(filtered, campaignTableState.sort);
    var slice = sorted.slice(0, campaignTableState.visibleLimit);
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="12" class="adm-lac-table-empty">هنوز کمپینی ثبت نشده</td></tr>';
      updateCampaignTableChrome(0, 0);
      return;
    }
    if (!filtered.length) {
      body.innerHTML =
        '<tr><td colspan="12" class="adm-lac-table-empty">نتیجه‌ای برای جستجو یافت نشد</td></tr>';
      updateCampaignTableChrome(0, 0);
      return;
    }
    body.innerHTML = slice.map(buildCampaignRowHtml).join('');
    updateCampaignTableChrome(filtered.length, slice.length);
  }

  function setCampaignTableData(rows, totals) {
    campaignTableState.allRows = rows || [];
    campaignTableState.totals = totals || null;
    campaignTableState.visibleLimit = CAMPAIGN_TABLE_PAGE;
    renderTableTotals(totals);
    refreshCampaignTableView();
  }

  function setupCampaignTable() {
    if (campaignTableState.bound) return;
    var searchEl = document.getElementById('lac-campaign-table-search');
    var sortEl = document.getElementById('lac-campaign-table-sort');
    var moreBtn = document.getElementById('lac-campaign-table-more');
    if (!searchEl && !sortEl && !moreBtn) return;
    campaignTableState.bound = true;
    if (searchEl) {
      searchEl.addEventListener('input', function () {
        campaignTableState.query = searchEl.value;
        campaignTableState.visibleLimit = CAMPAIGN_TABLE_PAGE;
        refreshCampaignTableView();
      });
    }
    if (sortEl) {
      sortEl.addEventListener('change', function () {
        campaignTableState.sort = sortEl.value || 'newest';
        campaignTableState.visibleLimit = CAMPAIGN_TABLE_PAGE;
        refreshCampaignTableView();
      });
    }
    if (moreBtn) {
      moreBtn.addEventListener('click', function () {
        campaignTableState.visibleLimit += CAMPAIGN_TABLE_PAGE;
        refreshCampaignTableView();
      });
    }
  }

  function renderTableTotals(totals) {
    var row = document.getElementById('lac-campaign-table-totals');
    if (!row) return;
    if (!totals) {
      row.innerHTML = '<td colspan="12" class="adm-lac-table-empty">—</td>';
      return;
    }
    row.innerHTML =
      '<td class="adm-lac-table-name">' +
      '<span class="adm-lac-table-totals-label">' + (totals.label || 'جمع کل') + '</span>' +
      '<small class="adm-lac-table-totals-sub">آمار تجمیع همه کمپین‌های جدول</small>' +
      '</td>' +
      '<td><span class="adm-lac-table-totals-badge">' + formatNum(totals.campaign_count) + ' کمپین</span></td>' +
      '<td><strong>' + formatNum(totals.eligible) + '</strong></td>' +
      '<td><strong>' + formatNum(totals.enrolled) + '</strong></td>' +
      '<td><strong>' + formatNum(totals.accepted) + '</strong></td>' +
      '<td><strong>' + formatNum(totals.clicked) + '</strong></td>' +
      '<td><strong>' + formatNum(totals.registered) + '</strong></td>' +
      '<td><strong class="adm-lac-table-totals-accent">' + formatNum(totals.paid) + '</strong></td>' +
      '<td><strong>' + formatPct(totals.ctr) + '</strong></td>' +
      '<td><strong>' + formatPct(totals.overall_cvr) + '</strong></td>' +
      '<td><strong>' + formatMoney(totals.revenue) + '</strong></td>' +
      '<td><strong>' + formatMoney(totals.sms_cost) + '</strong></td>';
  }

  function renderCampaignTable(rows, totals) {
    setCampaignTableData(rows, totals);
    setupCampaignTable();
  }

  function chartPercentAxisMax(rows, keys, floorMax) {
    var max = 0;
    (rows || []).forEach(function (row) {
      (keys || []).forEach(function (key) {
        var v = Number(row[key]);
        if (!Number.isNaN(v)) max = Math.max(max, v);
      });
    });
    if (max <= 0) return 100;
    var padded = Math.ceil((max + 2) / 5) * 5;
    return Math.min(100, Math.max(floorMax || 15, padded));
  }

  function campaignCvrBarColor(cvr) {
    var v = Number(cvr) || 0;
    if (v >= 8) return 'rgba(91, 79, 207, 0.95)';
    if (v >= 3) return 'rgba(91, 79, 207, 0.78)';
    if (v > 0) return 'rgba(91, 79, 207, 0.52)';
    return 'rgba(148, 163, 184, 0.35)';
  }

  var variantInsightBound = false;

  function escapeHtml(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function variantDecisionTrace(items) {
    var metrics = [
      { key: 'paid', label: 'خرید نهایی' },
      { key: 'registered', label: 'ثبت‌نام' },
      { key: 'clicked', label: 'کلیک' },
    ];
    var trace = [];
    var decided = false;
    metrics.forEach(function (m) {
      var vals = (items || []).map(function (v) {
        return { key: v.key, val: Number(v[m.key]) || 0, name: v.name || '' };
      });
      var max = Math.max.apply(null, vals.map(function (x) { return x.val; }).concat([0]));
      var leaders = vals.filter(function (x) { return x.val === max; });
      var row = {
        label: m.label,
        values: vals,
        tied: leaders.length !== 1,
        leader: leaders.length === 1 ? leaders[0].key : null,
        decisive: false,
      };
      if (!decided && leaders.length === 1) {
        row.decisive = true;
        decided = true;
      }
      trace.push(row);
    });
    return { trace: trace, allTied: !decided };
  }

  function renderVariantInsightModal(variants) {
    var body = document.getElementById('lac-variant-insight-body');
    var sub = document.getElementById('lac-variant-insight-sub');
    var openBtn = document.getElementById('lac-variant-insight-open');
    if (!body) return;
    var items = (variants && variants.items) || [];
    if (items.length < 2) {
      if (openBtn) openBtn.hidden = true;
      body.innerHTML = '<p class="adm-lac-variant-insight__empty">برای مقایسه حداقل دو نسخه فعال لازم است.</p>';
      return;
    }
    if (openBtn) openBtn.hidden = false;
    var winner = variants.winner;
    var analysis = variantDecisionTrace(items);
    var winnerRow = items.filter(function (v) { return v.key === winner; })[0];
    var winnerName = winnerRow ? (winnerRow.name || ('نسخه ' + winner)) : ('نسخه ' + winner);

    if (sub) {
      sub.textContent = winner
        ? 'پیشنهاد فعلی: نسخه ' + winner + ' · ' + winnerName
        : 'مقایسه تجمیعی پایلوت A/B';
    }

    var lead;
    if (!winner) {
      lead = 'هنوز برنده قطعی انتخاب نشده است.';
    } else if (analysis.allTied) {
      lead =
        'نسخه ' + winner + ' به‌صورت پیش‌فرض پیشنهاد شده است؛ در هر سه معیار (خرید، ثبت‌نام، کلیک) برابری دیده می‌شود.';
    } else {
      var decisive = analysis.trace.filter(function (t) { return t.decisive; })[0];
      lead = decisive
        ? 'نسخه ' + winner + ' چون در معیار «' + decisive.label + '» از نسخه دیگر جلوتر است.'
        : 'نسخه ' + winner + ' بر اساس خرید، سپس ثبت‌نام و در نهایت کلیک انتخاب شده است.';
    }

    var stepsHtml = analysis.trace.map(function (step) {
      var status = step.tied
        ? 'مساوی'
        : 'برنده: نسخه ' + step.leader;
      var badge = step.decisive
        ? ' <span class="adm-lac-variant-insight__badge">معیار تعیین‌کننده</span>'
        : '';
      var valsHtml = step.values.map(function (v) {
        var winClass = !step.tied && v.key === step.leader ? ' is-winner' : '';
        return (
          '<li class="adm-lac-variant-insight__metric' + winClass + '">' +
          '<span class="adm-lac-variant-insight__key">' + escapeHtml(v.key) + '</span>' +
          '<strong>' + formatNum(v.val) + '</strong>' +
          '</li>'
        );
      }).join('');
      return (
        '<li class="adm-lac-variant-insight__step">' +
        '<div class="adm-lac-variant-insight__step-head">' +
        '<strong>' + escapeHtml(step.label) + '</strong>' +
        '<span>' + escapeHtml(status) + badge + '</span>' +
        '</div>' +
        '<ul class="adm-lac-variant-insight__metrics">' + valsHtml + '</ul>' +
        '</li>'
      );
    }).join('');

    var tableRows = items.map(function (v) {
      var isWinner = winner && v.key === winner;
      return (
        '<tr class="' + (isWinner ? 'is-winner' : '') + '">' +
        '<td><span class="adm-lac-variant-key">' + escapeHtml(v.key) + '</span></td>' +
        '<td>' + formatNum(v.accepted) + '</td>' +
        '<td>' + formatPct(v.ctr, 1) + '</td>' +
        '<td>' + formatNum(v.registered) + '</td>' +
        '<td>' + formatNum(v.paid) + '</td>' +
        '<td>' + formatPct(v.overall_cvr, 1) + '</td>' +
        '</tr>'
      );
    }).join('');

    body.innerHTML =
      '<div class="adm-lac-variant-insight">' +
      '<p class="adm-lac-variant-insight__lead">' + escapeHtml(lead) + '</p>' +
      '<p class="adm-lac-variant-insight__criteria-line">ترتیب: خرید، ثبت‌نام، کلیک — اولین اختلاف، برنده را مشخص می‌کند.</p>' +
      '<ol class="adm-lac-variant-insight__steps adm-lac-variant-insight__steps--compact">' + stepsHtml + '</ol>' +
      '<div class="adm-lac-variant-insight__table-wrap">' +
      '<table class="adm-lac-variant-insight__table">' +
      '<thead><tr>' +
      '<th scope="col">نسخه</th>' +
      '<th scope="col">ارسال</th>' +
      '<th scope="col">CTR</th>' +
      '<th scope="col">ثبت‌نام</th>' +
      '<th scope="col">خرید</th>' +
      '<th scope="col">CVR</th>' +
      '</tr></thead>' +
      '<tbody>' + tableRows + '</tbody>' +
      '</table></div>' +
      '<p class="adm-lac-variant-insight__note">اعداد تجمیع همه کمپین‌های گزارش‌شده در این نما است.</p>' +
      '</div>';
  }

  function setupVariantInsightModal(variants) {
    renderVariantInsightModal(variants || {});
    if (variantInsightBound) return;
    var modal = document.getElementById('lac-variant-insight-modal');
    var openBtn = document.getElementById('lac-variant-insight-open');
    if (!modal) return;
    variantInsightBound = true;
    var closeModal = function () {
      if (modal.open) modal.close();
    };
    modal.querySelectorAll('[data-lac-variant-insight-close]').forEach(function (btn) {
      btn.addEventListener('click', closeModal);
    });
    modal.addEventListener('cancel', function (e) {
      e.preventDefault();
      closeModal();
    });
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });
    if (openBtn) {
      openBtn.addEventListener('click', function () {
        if (typeof modal.showModal === 'function') modal.showModal();
      });
    }
  }

  function campaignChartTooltipTheme(theme) {
    return {
      enabled: true,
      rtl: true,
      position: 'nearest',
      mode: 'index',
      intersect: false,
      backgroundColor: theme.tooltipBg,
      titleColor: theme.tooltipText,
      bodyColor: theme.tooltipText,
      footerColor: theme.tooltipText,
      borderColor: theme.border,
      borderWidth: 1,
      padding: 14,
      boxPadding: 7,
      titleFont: { weight: '900', size: 12 },
      bodyFont: (function () {
        var f = chartFont();
        f.size = 11;
        return f;
      })(),
      footerFont: { weight: '700', size: 10 },
      titleMarginBottom: 8,
      bodySpacing: 6,
      footerMarginTop: 10,
      usePointStyle: true,
      cornerRadius: 10,
      displayColors: true,
    };
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
    renderConversionInsights(data.rates, data.summary, data.funnel_steps);
    renderCampaignTable(data.campaign_table, data.table_totals);

    var variantSub = document.getElementById('lac-variant-sub');
    if (variantSub && data.variants) {
      variantSub.textContent = data.variants.winner
        ? 'پیشنهاد: نسخه ' + data.variants.winner + ' (بر اساس خرید و ثبت‌نام)'
        : 'پایلوت دو نسخه‌ای';
    }
    setupVariantInsightModal(data.variants);

    destroyChart('lac-chart-conversion');
    destroyChart('lac-chart-campaigns');
    destroyChart('lac-chart-variants');

    var convEl = document.getElementById('lac-chart-conversion');
    if (convEl && data.conversion_series && data.conversion_series.labels.length) {
      var stepRates = data.conversion_series.step_rates || [];
      var stepLabels = data.conversion_series.labels || [];
      var stepColors = (data.funnel_steps || []).slice(1).map(function (s) {
        return s.color || PALETTE.violet;
      });
      while (stepColors.length < stepLabels.length) {
        stepColors.push(PALETTE.violet);
      }
      var maxRate = Math.max.apply(null, stepRates.concat([100]));
      var axisMax = Math.min(Math.max(100, Math.ceil(maxRate / 10) * 10), 160);
      var convWrap = convEl.parentElement;
      if (convWrap) {
        var rowCount = Math.max(stepLabels.length, 1);
        var chartH = Math.min(Math.max(rowCount * 28 + 32, 112), 168);
        convWrap.style.setProperty('--conv-chart-h', chartH + 'px');
      }
      new Chart(convEl, {
        type: 'bar',
        data: {
          labels: stepLabels,
          datasets: [{
            label: 'مانده از مرحله قبل',
            data: stepRates,
            backgroundColor: stepColors.map(function (c) {
              return c.indexOf('rgba') === 0 ? c : c + 'cc';
            }),
            borderColor: stepColors,
            borderWidth: 0,
            borderRadius: 6,
            borderSkipped: false,
            barThickness: 13,
            maxBarThickness: 15,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 0, right: 6, bottom: 0, left: 0 } },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: theme.tooltipBg,
              titleColor: theme.tooltipText,
              bodyColor: theme.tooltipText,
              borderColor: theme.border,
              borderWidth: 1,
              padding: 12,
              titleFont: { weight: '800', size: 12 },
              callbacks: {
                label: function (ctx) {
                  var raw = stepRates[ctx.dataIndex];
                  var line = 'تبدیل: ' + formatPct(raw, 1);
                  if (Number(raw) > 100) {
                    line += ' (بیش از مرحله قبل)';
                  }
                  return line;
                },
                afterLabel: function (ctx) {
                  var steps = data.funnel_steps || [];
                  var idx = ctx.dataIndex + 1;
                  if (!steps[idx]) return '';
                  return 'حجم: ' + formatNum(steps[idx].value);
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              max: axisMax,
              grid: { color: theme.grid, drawBorder: false },
              ticks: {
                color: theme.text,
                maxTicksLimit: 6,
                callback: function (v) { return formatPct(v, 0); },
              },
            },
            y: {
              grid: { display: false },
              ticks: {
                color: theme.textStrong,
                font: chartFont(),
                padding: 2,
                autoSkip: false,
              },
            },
          },
        },
      });
    }

    var campaignsEl = document.getElementById('lac-chart-campaigns');
    var campaignsSub = document.getElementById('lac-campaigns-sub');
    if (campaignsEl && data.campaigns && data.campaigns.length) {
      var sorted = data.campaigns.slice().sort(function (a, b) {
        var dc = (Number(b.overall_cvr) || 0) - (Number(a.overall_cvr) || 0);
        if (dc !== 0) return dc;
        return (Number(b.accepted) || 0) - (Number(a.accepted) || 0);
      });
      var best = sorted[0];
      if (campaignsSub && best) {
        campaignsSub.textContent =
          'برترین CVR: ' + (best.label || '') + ' · ' + formatPct(best.overall_cvr, 1);
      }
      var axisMax = chartPercentAxisMax(sorted, ['overall_cvr', 'ctr'], 18);
      var tooltipBase = campaignChartTooltipTheme(theme);
      new Chart(campaignsEl, {
        type: 'bar',
        data: {
          labels: sorted.map(function (c) {
            return formatNum(c.id) + ' · ' + c.label;
          }),
          datasets: [
            {
              label: 'نرخ خرید (CVR)',
              data: sorted.map(function (c) { return c.overall_cvr; }),
              backgroundColor: sorted.map(function (c) { return campaignCvrBarColor(c.overall_cvr); }),
              hoverBackgroundColor: sorted.map(function () { return 'rgba(91, 79, 207, 1)'; }),
              borderRadius: 8,
              borderSkipped: false,
              maxBarThickness: 16,
              categoryPercentage: 0.72,
              barPercentage: 0.88,
            },
            {
              label: 'نرخ کلیک (CTR)',
              data: sorted.map(function (c) { return c.ctr; }),
              backgroundColor: 'rgba(6, 182, 212, 0.42)',
              hoverBackgroundColor: 'rgba(6, 182, 212, 0.72)',
              borderRadius: 8,
              borderSkipped: false,
              maxBarThickness: 16,
              categoryPercentage: 0.72,
              barPercentage: 0.88,
            },
          ],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 720,
            easing: 'easeOutQuart',
          },
          interaction: {
            mode: 'index',
            axis: 'y',
            intersect: false,
          },
          layout: { padding: { top: 2, right: 6, bottom: 2, left: 2 } },
          plugins: {
            legend: {
              position: 'top',
              align: 'end',
              labels: {
                color: theme.text,
                font: chartFont(),
                usePointStyle: true,
                pointStyle: 'rectRounded',
                boxWidth: 8,
                boxHeight: 8,
                padding: 14,
              },
            },
            tooltip: Object.assign({}, tooltipBase, {
              callbacks: {
                title: function (items) {
                  if (!items.length) return '';
                  var row = sorted[items[0].dataIndex];
                  var title = (row.name || row.label || '').trim();
                  return formatNum(row.id) + ' · ' + (title || 'کمپین');
                },
                label: function (ctx) {
                  var val = ctx.parsed.x;
                  var key = ctx.datasetIndex === 0 ? 'overall_cvr' : 'ctr';
                  var row = sorted[ctx.dataIndex];
                  var line = ctx.dataset.label + ': ' + formatPct(val, 1);
                  if (key === 'overall_cvr' && row.accepted) {
                    line += '  (' + formatNum(row.paid) + ' خرید از ' + formatNum(row.accepted) + ' ارسال)';
                  } else if (key === 'ctr' && row.accepted) {
                    line += '  (' + formatNum(row.clicked) + ' کلیک از ' + formatNum(row.accepted) + ' ارسال)';
                  }
                  return line;
                },
                afterBody: function (items) {
                  if (!items.length) return [];
                  var row = sorted[items[0].dataIndex];
                  return [
                    '────────────────',
                    'قیف: ' + formatNum(row.accepted) + ' ارسال → ' +
                      formatNum(row.clicked) + ' کلیک → ' +
                      formatNum(row.registered) + ' ثبت‌نام → ' +
                      formatNum(row.paid) + ' خرید',
                    row.reg_to_paid != null
                      ? 'ثبت‌نام به خرید: ' + formatPct(row.reg_to_paid, 1)
                      : '',
                  ].filter(Boolean);
                },
                footer: function (items) {
                  if (!items.length) return [];
                  var row = sorted[items[0].dataIndex];
                  var lines = [];
                  if (row.revenue) lines.push('درآمد: ' + formatMoney(row.revenue));
                  if (row.sms_cost) lines.push('هزینه پیامک: ' + formatMoney(row.sms_cost));
                  if (row.roas != null) {
                    lines.push('ROAS ×' + persianDigits(String(row.roas)));
                  }
                  if (row.cac != null) lines.push('CAC: ' + formatMoney(row.cac));
                  return lines;
                },
              },
            }),
          },
          scales: {
            x: {
              beginAtZero: true,
              max: axisMax,
              grid: { color: theme.grid, drawBorder: false },
              border: { display: false },
              ticks: {
                color: theme.text,
                maxTicksLimit: 6,
                callback: function (v) { return formatPct(v, 0); },
              },
            },
            y: {
              grid: { display: false },
              border: { display: false },
              ticks: {
                color: theme.textStrong,
                font: { weight: '750', size: 10 },
                autoSkip: false,
                padding: 6,
              },
            },
          },
        },
      });
    } else if (campaignsSub) {
      campaignsSub.textContent = 'هنوز دادهٔ کافی برای مقایسهٔ کمپین‌ها نیست';
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
    ['lac-chart-conversion', 'lac-chart-campaigns', 'lac-chart-variants'].forEach(function (id) {
      var canvas = document.getElementById(id);
      if (!canvas) return;
      var inst = Chart.getChart(canvas);
      if (inst) inst.resize();
    });
  });
})();
