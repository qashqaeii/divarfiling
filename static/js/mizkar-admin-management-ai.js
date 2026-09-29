/**
 * Management AI — manual on-demand only. GET loads stored analysis; POST generates.
 */
(function () {
    'use strict';

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

    function setLoading(panel, loading) {
        var gen = panel.querySelector('[data-mgmt-ai-generate]');
        var regen = panel.querySelector('[data-mgmt-ai-regenerate]');
        [gen, regen].forEach(function (btn) {
            if (!btn) return;
            btn.disabled = loading;
            if (btn === gen && loading) {
                btn.textContent = 'در حال تحلیل…';
            } else if (btn === gen && !loading) {
                btn.textContent = 'دریافت تحلیل AI';
            }
            if (btn === regen && loading) {
                btn.textContent = 'در حال تحلیل…';
            } else if (btn === regen && !loading) {
                btn.textContent = 'تحلیل مجدد';
            }
        });
    }

    function renderAnalysis(panel, payload) {
        var body = panel.querySelector('[data-mgmt-ai-body]');
        var summaryEl = panel.querySelector('[data-mgmt-ai-summary]');
        var listEl = panel.querySelector('[data-mgmt-ai-insights]');
        var metaEl = panel.querySelector('[data-mgmt-ai-meta]');
        var staleEl = panel.querySelector('[data-mgmt-ai-stale]');
        var statusText = panel.querySelector('[data-mgmt-ai-status-text]');
        var genBtn = panel.querySelector('[data-mgmt-ai-generate]');
        var regenBtn = panel.querySelector('[data-mgmt-ai-regenerate]');
        var errEl = panel.querySelector('[data-mgmt-ai-error]');

        errEl.hidden = true;
        var status = payload.status;

        if (status === 'disabled') {
            panel.hidden = true;
            return;
        }

        if (status === 'not_generated') {
            body.hidden = true;
            statusText.textContent = 'هنوز تحلیلی برای این بازه ایجاد نشده است.';
            genBtn.hidden = false;
            regenBtn.hidden = true;
            staleEl.hidden = true;
            return;
        }

        if (status !== 'available' || !payload.analysis) {
            statusText.textContent = 'وضعیت تحلیل نامشخص است.';
            return;
        }

        var analysis = payload.analysis;
        body.hidden = false;
        genBtn.hidden = true;
        regenBtn.hidden = false;
        staleEl.hidden = !payload.is_stale;

        summaryEl.textContent = analysis.summary || '';
        statusText.textContent = analysis.status === 'critical'
            ? 'وضعیت: نیازمند توجه'
            : (analysis.status === 'warning' ? 'وضعیت: هشدار' : 'وضعیت: قابل بررسی');

        listEl.innerHTML = '';
        (analysis.insights || []).slice(0, 5).forEach(function (item) {
            var li = document.createElement('li');
            li.textContent = (item.title ? item.title + ' — ' : '') + (item.description || '');
            listEl.appendChild(li);
        });

        if (payload.generated_at) {
            metaEl.textContent = 'آخرین تحلیل: ' + new Date(payload.generated_at).toLocaleString('fa-IR');
        }
    }

    function fetchLatest(panel) {
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

    function bindPanel(panel) {
        fetchLatest(panel).then(function (payload) {
            renderAnalysis(panel, payload);
        }).catch(function () {
            var statusText = panel.querySelector('[data-mgmt-ai-status-text]');
            if (statusText) statusText.textContent = 'بارگذاری وضعیت تحلیل ممکن نبود.';
        });

        panel.querySelector('[data-mgmt-ai-generate]')?.addEventListener('click', function () {
            setLoading(panel, true);
            postGenerate(panel, false).then(function (res) {
                setLoading(panel, false);
                var errEl = panel.querySelector('[data-mgmt-ai-error]');
                if (!res.json.ok) {
                    errEl.hidden = false;
                    errEl.textContent = res.json.detail || 'تحلیل هوشمند در حال حاضر در دسترس نیست.';
                    return;
                }
                renderAnalysis(panel, {
                    status: 'available',
                    analysis: res.json.analysis,
                    generated_at: res.json.generated_at || new Date().toISOString(),
                    is_stale: false,
                });
            }).catch(function () {
                setLoading(panel, false);
                var errEl = panel.querySelector('[data-mgmt-ai-error]');
                errEl.hidden = false;
                errEl.textContent = 'تحلیل هوشمند در حال حاضر در دسترس نیست.';
            });
        });

        panel.querySelector('[data-mgmt-ai-regenerate]')?.addEventListener('click', function () {
            setLoading(panel, true);
            postGenerate(panel, true).then(function (res) {
                setLoading(panel, false);
                var errEl = panel.querySelector('[data-mgmt-ai-error]');
                if (!res.json.ok) {
                    errEl.hidden = false;
                    errEl.textContent = res.json.detail || 'تحلیل هوشمند در حال حاضر در دسترس نیست.';
                    return;
                }
                renderAnalysis(panel, {
                    status: 'available',
                    analysis: res.json.analysis,
                    generated_at: res.json.generated_at || new Date().toISOString(),
                    is_stale: false,
                });
            }).catch(function () {
                setLoading(panel, false);
                var errEl = panel.querySelector('[data-mgmt-ai-error]');
                errEl.hidden = false;
                errEl.textContent = 'تحلیل هوشمند در حال حاضر در دسترس نیست.';
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-mgmt-ai-panel]').forEach(bindPanel);
    });
})();
