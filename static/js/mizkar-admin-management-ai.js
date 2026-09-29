/**
 * Management AI — manual on-demand only. GET loads stored analysis; POST generates.
 */
(function () {
    'use strict';

    var TYPE_LABELS = {
        fact: 'واقعیت',
        interpretation: 'تحلیل',
        hypothesis: 'فرضیه',
    };

    var STATUS_UI = {
        good: { label: 'مطلوب', pill: 'is-good' },
        watch: { label: 'رصد', pill: 'is-watch' },
        warning: { label: 'هشدار', pill: 'is-warning' },
        critical: { label: 'نیازمند توجه', pill: 'is-critical' },
    };

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function currentQuerySuffix(panel) {
        var params = new URLSearchParams(window.location.search);
        var days = params.get('days') || 'all';
        var compare = params.get('compare') === '1' ? '&compare=1' : '';
        return '?days=' + encodeURIComponent(days) + compare;
    }

    function setPanelState(panel, state) {
        panel.setAttribute('data-mgmt-ai-state', state);
        panel.setAttribute('aria-busy', state === 'loading' || state === 'generating' ? 'true' : 'false');
        var skeleton = panel.querySelector('[data-mgmt-ai-skeleton]');
        if (skeleton) skeleton.hidden = state !== 'loading' && state !== 'generating';
    }

    function setLoading(panel, loading) {
        var gen = panel.querySelector('[data-mgmt-ai-generate]');
        var regen = panel.querySelector('[data-mgmt-ai-regenerate]');
        var genLabel = panel.querySelector('[data-mgmt-ai-generate-label]');
        var regenLabel = panel.querySelector('[data-mgmt-ai-regenerate-label]');
        if (loading) {
            setPanelState(panel, 'generating');
        }
        [gen, regen].forEach(function (btn) {
            if (!btn) return;
            btn.disabled = loading;
            btn.classList.toggle('is-loading', loading);
        });
        if (genLabel) {
            genLabel.textContent = loading && gen && !gen.hidden
                ? 'در حال تحلیل…'
                : (gen && gen.getAttribute('data-default-label')) || 'دریافت تحلیل AI';
        }
        if (regenLabel) {
            regenLabel.textContent = loading && regen && !regen.hidden
                ? 'در حال تحلیل…'
                : (regen && regen.getAttribute('data-default-label')) || 'تحلیل مجدد';
        }
        if (!loading) {
            var body = panel.querySelector('[data-mgmt-ai-body]');
            var empty = panel.querySelector('[data-mgmt-ai-empty]');
            if (body && !body.hidden) setPanelState(panel, 'ready');
            else if (empty && !empty.hidden) setPanelState(panel, 'empty');
            else setPanelState(panel, 'idle');
        }
    }

    function applyStatusPill(panel, analysisStatus) {
        var pill = panel.querySelector('[data-mgmt-ai-status-pill]');
        var pillText = panel.querySelector('[data-mgmt-ai-status-pill-text]');
        if (!pill || !pillText) return;
        var cfg = STATUS_UI[analysisStatus] || STATUS_UI.watch;
        pill.hidden = false;
        pill.className = 'ecc-mgmt-ai-status-pill ' + cfg.pill;
        pillText.textContent = cfg.label;
    }

    function clearBlocks(panel) {
        var insights = panel.querySelector('[data-mgmt-ai-insights]');
        var actions = panel.querySelector('[data-mgmt-ai-actions]');
        var risks = panel.querySelector('[data-mgmt-ai-risks]');
        if (insights) insights.innerHTML = '';
        if (actions) actions.innerHTML = '';
        if (risks) risks.innerHTML = '';
    }

    function renderInsightCard(item) {
        var card = document.createElement('article');
        card.className = 'ecc-mgmt-ai-insight';
        card.setAttribute('role', 'listitem');
        var type = (item.type || 'interpretation').toLowerCase();
        card.setAttribute('data-insight-type', type);

        var head = document.createElement('div');
        head.className = 'ecc-mgmt-ai-insight-head';
        var badge = document.createElement('span');
        badge.className = 'ecc-mgmt-ai-insight-type';
        badge.textContent = TYPE_LABELS[type] || type;
        head.appendChild(badge);
        if (item.title) {
            var title = document.createElement('strong');
            title.className = 'ecc-mgmt-ai-insight-title';
            title.textContent = item.title;
            head.appendChild(title);
        }
        card.appendChild(head);

        if (item.description) {
            var desc = document.createElement('p');
            desc.className = 'ecc-mgmt-ai-insight-desc';
            desc.textContent = item.description;
            card.appendChild(desc);
        }
        return card;
    }

    function renderActionChip(item) {
        var chip = document.createElement('article');
        chip.className = 'ecc-mgmt-ai-action-chip';
        chip.setAttribute('role', 'listitem');
        var pri = (item.priority || 'medium').toLowerCase();
        chip.setAttribute('data-priority', pri);
        var title = document.createElement('strong');
        title.textContent = item.title || 'اقدام';
        chip.appendChild(title);
        if (item.description) {
            var p = document.createElement('span');
            p.textContent = item.description;
            chip.appendChild(p);
        }
        return chip;
    }

    function renderRiskRow(item) {
        var row = document.createElement('article');
        row.className = 'ecc-mgmt-ai-risk';
        row.setAttribute('role', 'listitem');
        row.setAttribute('data-severity', (item.severity || 'medium').toLowerCase());
        var title = document.createElement('strong');
        title.textContent = item.title || 'ریسک';
        row.appendChild(title);
        if (item.description) {
            var p = document.createElement('p');
            p.textContent = item.description;
            row.appendChild(p);
        }
        return row;
    }

    function renderAnalysis(panel, payload) {
        var body = panel.querySelector('[data-mgmt-ai-body]');
        var empty = panel.querySelector('[data-mgmt-ai-empty]');
        var summaryEl = panel.querySelector('[data-mgmt-ai-summary]');
        var listEl = panel.querySelector('[data-mgmt-ai-insights]');
        var insightsBlock = panel.querySelector('[data-mgmt-ai-insights-block]');
        var actionsEl = panel.querySelector('[data-mgmt-ai-actions]');
        var actionsBlock = panel.querySelector('[data-mgmt-ai-actions-block]');
        var risksEl = panel.querySelector('[data-mgmt-ai-risks]');
        var risksBlock = panel.querySelector('[data-mgmt-ai-risks-block]');
        var metaEl = panel.querySelector('[data-mgmt-ai-meta]');
        var metaWrap = panel.querySelector('[data-mgmt-ai-meta-wrap]');
        var providerEl = panel.querySelector('[data-mgmt-ai-provider]');
        var staleEl = panel.querySelector('[data-mgmt-ai-stale]');
        var statusText = panel.querySelector('[data-mgmt-ai-status-text]');
        var genBtn = panel.querySelector('[data-mgmt-ai-generate]');
        var regenBtn = panel.querySelector('[data-mgmt-ai-regenerate]');
        var errEl = panel.querySelector('[data-mgmt-ai-error]');
        var pill = panel.querySelector('[data-mgmt-ai-status-pill]');

        errEl.hidden = true;
        var status = payload.status;

        if (status === 'disabled') {
            panel.hidden = true;
            return;
        }

        if (status === 'not_generated') {
            body.hidden = true;
            empty.hidden = false;
            if (pill) pill.hidden = true;
            statusText.textContent = 'آمادهٔ دریافت اولین تحلیل برای بازهٔ انتخاب‌شده';
            genBtn.hidden = false;
            regenBtn.hidden = true;
            staleEl.hidden = true;
            setPanelState(panel, 'empty');
            return;
        }

        if (status !== 'available' || !payload.analysis) {
            empty.hidden = true;
            body.hidden = true;
            statusText.textContent = 'وضعیت تحلیل نامشخص است.';
            setPanelState(panel, 'idle');
            return;
        }

        var analysis = payload.analysis;
        empty.hidden = true;
        body.hidden = false;
        genBtn.hidden = true;
        regenBtn.hidden = false;
        staleEl.hidden = !payload.is_stale;

        applyStatusPill(panel, analysis.status);
        statusText.textContent = 'تحلیل ذخیره‌شده برای همین بازه — در صورت تغییر KPI، هشدار «منقضی» نمایش داده می‌شود.';

        summaryEl.textContent = analysis.summary || '';

        clearBlocks(panel);
        var insights = (analysis.insights || []).slice(0, 5);
        insights.forEach(function (item) {
            listEl.appendChild(renderInsightCard(item));
        });
        insightsBlock.hidden = insights.length === 0;

        var actions = (analysis.actions || []).slice(0, 5);
        actions.forEach(function (item) {
            actionsEl.appendChild(renderActionChip(item));
        });
        actionsBlock.hidden = actions.length === 0;

        var risks = (analysis.risks || []).slice(0, 3);
        risks.forEach(function (item) {
            risksEl.appendChild(renderRiskRow(item));
        });
        risksBlock.hidden = risks.length === 0;

        if (payload.generated_at && metaEl) {
            metaEl.textContent = 'آخرین تحلیل: ' + new Date(payload.generated_at).toLocaleString('fa-IR');
        }
        if (providerEl) {
            var prov = payload.provider || '';
            var model = payload.model || '';
            providerEl.textContent = prov ? ('مدل: ' + (model || prov)) : '';
        }
        if (metaWrap) metaWrap.hidden = !payload.generated_at;

        setPanelState(panel, 'ready');
    }

    function fetchLatest(panel) {
        setPanelState(panel, 'loading');
        var baseGet = panel.getAttribute('data-mgmt-ai-get-url').split('?')[0];
        var url = baseGet + currentQuerySuffix(panel);
        return fetch(url, {
            method: 'GET',
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        }).then(function (r) { return r.json(); });
    }

    function postGenerate(panel, force) {
        var basePost = panel.getAttribute('data-mgmt-ai-post-url');
        var suffix = currentQuerySuffix(panel);
        var body = new URLSearchParams();
        body.set('csrfmiddlewaretoken', getCookie('csrftoken'));
        if (force) body.set('force', '1');
        if (suffix.indexOf('compare=1') !== -1) body.set('compare', '1');
        var daysMatch = suffix.match(/days=([^&]+)/);
        if (daysMatch) body.set('days', daysMatch[1]);

        return fetch(basePost + suffix, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                Accept: 'application/json',
            },
            body: body.toString(),
        }).then(function (r) { return r.json().then(function (j) { return { status: r.status, json: j }; }); });
    }

    function showError(panel, message) {
        var errEl = panel.querySelector('[data-mgmt-ai-error]');
        errEl.hidden = false;
        errEl.textContent = message;
        setPanelState(panel, 'error');
    }

    function bindPanel(panel) {
        fetchLatest(panel).then(function (payload) {
            renderAnalysis(panel, payload);
        }).catch(function () {
            var statusText = panel.querySelector('[data-mgmt-ai-status-text]');
            if (statusText) statusText.textContent = 'بارگذاری وضعیت تحلیل ممکن نبود.';
            setPanelState(panel, 'error');
        });

        panel.querySelector('[data-mgmt-ai-generate]')?.addEventListener('click', function () {
            setLoading(panel, true);
            postGenerate(panel, false).then(function (res) {
                setLoading(panel, false);
                if (!res.json.ok) {
                    showError(panel, res.json.detail || res.json.error || 'تحلیل هوشمند در حال حاضر در دسترس نیست.');
                    return;
                }
                renderAnalysis(panel, {
                    status: 'available',
                    analysis: res.json.analysis,
                    generated_at: res.json.generated_at || new Date().toISOString(),
                    provider: res.json.provider,
                    model: res.json.model,
                    is_stale: false,
                });
            }).catch(function () {
                setLoading(panel, false);
                showError(panel, 'تحلیل هوشمند در حال حاضر در دسترس نیست.');
            });
        });

        panel.querySelector('[data-mgmt-ai-regenerate]')?.addEventListener('click', function () {
            setLoading(panel, true);
            postGenerate(panel, true).then(function (res) {
                setLoading(panel, false);
                if (!res.json.ok) {
                    var msg = res.json.detail || res.json.error || 'تحلیل هوشمند در حال حاضر در دسترس نیست.';
                    if (res.status === 429) msg = 'لطفاً حدود یک دقیقه صبر کنید و دوباره تلاش کنید.';
                    showError(panel, msg);
                    return;
                }
                renderAnalysis(panel, {
                    status: 'available',
                    analysis: res.json.analysis,
                    generated_at: res.json.generated_at || new Date().toISOString(),
                    provider: res.json.provider,
                    model: res.json.model,
                    is_stale: false,
                });
            }).catch(function () {
                setLoading(panel, false);
                showError(panel, 'تحلیل هوشمند در حال حاضر در دسترس نیست.');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-mgmt-ai-panel]').forEach(bindPanel);
    });
})();
