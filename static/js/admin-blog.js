(function () {
    'use strict';

    var PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

    function toFa(n) {
        return String(n).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[parseInt(d, 10)];
        });
    }

    function formatNum(n) {
        return toFa(Number(n || 0).toLocaleString('en-US'));
    }

    function getMeta() {
        return window.admBlogMeta || {};
    }

    function getAnalytics() {
        return window.admBlogAnalytics || {};
    }

    /* ─── Pinned tabs below site header ─── */
    function initPinnedTabs() {
        var tabsBar = document.getElementById('adm-map-tabs');
        var spacer = document.getElementById('adm-map-tabs-spacer');
        var page = document.querySelector('.adm-map-page');
        if (!tabsBar || !spacer || !page) return;

        var anchorTop = 0;

        function siteHeaderHeight() {
            var header = document.querySelector('.mk-site-header');
            if (header) return header.getBoundingClientRect().height;
            var root = getComputedStyle(document.documentElement);
            var h = parseFloat(root.getPropertyValue('--mk-site-header-h'));
            return Number.isFinite(h) && h > 0 ? h : 56;
        }

        function syncTabsHeight() {
            var h = tabsBar.offsetHeight;
            page.style.setProperty('--adm-map-tabs-h', h + 'px');
            if (tabsBar.classList.contains('is-pinned')) {
                spacer.style.height = h + 'px';
            }
        }

        function measureAnchor() {
            tabsBar.classList.remove('is-pinned');
            spacer.classList.remove('is-active');
            spacer.style.height = '';
            anchorTop = tabsBar.getBoundingClientRect().top + window.scrollY;
            syncTabsHeight();
        }

        function updatePin() {
            var headerH = siteHeaderHeight();
            page.style.setProperty('--adm-map-tabs-top', headerH + 'px');
            var shouldPin = window.scrollY + headerH >= anchorTop - 1;

            if (shouldPin) {
                if (!tabsBar.classList.contains('is-pinned')) {
                    tabsBar.classList.add('is-pinned');
                    spacer.classList.add('is-active');
                }
                syncTabsHeight();
            } else {
                tabsBar.classList.remove('is-pinned');
                spacer.classList.remove('is-active');
                spacer.style.height = '';
            }
        }

        window.addEventListener('scroll', updatePin, { passive: true });
        window.addEventListener('resize', function () {
            measureAnchor();
            updatePin();
        });

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(function () {
                syncTabsHeight();
            }).observe(tabsBar);
        }

        measureAnchor();
        updatePin();
    }

    /* ─── Section tabs ─── */
    function initBlogTabs() {
        var tabs = document.querySelectorAll('.adm-blog-page .adm-map-tab');
        var sections = ['blog-overview', 'blog-posts', 'blog-analytics', 'blog-import'];
        var sectionEls = sections.map(function (id) {
            return document.getElementById(id);
        });

        function showSection(hash) {
            if (sections.indexOf(hash) === -1) hash = 'blog-overview';
            sectionEls.forEach(function (el) {
                if (!el) return;
                el.hidden = el.id !== hash;
            });
            tabs.forEach(function (tab) {
                var href = (tab.getAttribute('href') || '').replace('#', '');
                tab.classList.toggle('is-active', href === hash);
            });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                setTimeout(function () {
                    showSection((location.hash || '#blog-overview').replace('#', ''));
                }, 0);
            });
        });
        window.addEventListener('hashchange', function () {
            showSection((location.hash || '#blog-overview').replace('#', ''));
        });

        var initial = (location.hash || '#blog-overview').replace('#', '');
        if (location.search && initial === 'blog-overview') {
            initial = 'blog-posts';
            history.replaceState(null, '', '#blog-posts');
        }
        showSection(initial);
    }

    /* ─── Charts ─── */
    function initBlogCharts() {
        if (typeof Chart === 'undefined') return;
        var data = getAnalytics();
        var publish = data.published_daily || { labels: [], counts: [] };
        var topViews = data.top_views || [];

        var publishCanvas = document.getElementById('adm-blog-chart-publish');
        if (publishCanvas) {
            new Chart(publishCanvas, {
                type: 'bar',
                data: {
                    labels: publish.labels,
                    datasets: [{
                        label: 'انتشار',
                        data: publish.counts,
                        backgroundColor: 'rgba(13, 148, 136, 0.55)',
                        borderRadius: 6,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                },
            });
        }

        var viewsCanvas = document.getElementById('adm-blog-chart-views');
        if (viewsCanvas && topViews.length) {
            var labels = topViews.map(function (p) {
                return p.title.length > 28 ? p.title.slice(0, 28) + '…' : p.title;
            });
            new Chart(viewsCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'بازدید',
                        data: topViews.map(function (p) { return p.views_count; }),
                        backgroundColor: 'rgba(124, 58, 237, 0.5)',
                        borderRadius: 6,
                    }],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true },
                    },
                },
            });
        }
    }

    /* ─── JSON Import ─── */
    function parseEditorJson() {
        var raw = document.getElementById('adm-blog-json-input');
        if (!raw || !raw.value.trim()) {
            throw new Error('JSON خالی است.');
        }
        return JSON.parse(raw.value);
    }

    function applyOptions(payload) {
        var publish = document.getElementById('adm-blog-opt-publish');
        var force = document.getElementById('adm-blog-opt-force');
        payload.options = payload.options || {};
        if (publish && publish.checked) payload.options.publish = true;
        if (force && force.checked) payload.options.force_update = true;
        return payload;
    }

    function showResult(type, html) {
        var box = document.getElementById('adm-blog-import-result');
        if (!box) return;
        box.hidden = false;
        box.className = 'adm-blog-import-result is-' + type;
        box.innerHTML = html;
    }

    function postJson(url, payload) {
        var meta = getMeta();
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': meta.csrfToken || '',
            },
            body: JSON.stringify(payload),
            credentials: 'same-origin',
        }).then(function (resp) {
            return resp.json().then(function (data) {
                return { ok: resp.ok, data: data };
            });
        });
    }

    function renderPreview(data) {
        if (!data.ok) {
            var errHtml = '<strong>خطا در اعتبارسنجی</strong><ul>';
            (data.errors || []).forEach(function (e) {
                errHtml += '<li>' + e + '</li>';
            });
            errHtml += '</ul>';
            showResult('error', errHtml);
            return;
        }

        var a = data.article || {};
        var html = '<strong>JSON معتبر است</strong>';
        html += '<p>عملیات: <b>' + (data.action === 'update' ? 'به‌روزرسانی' : data.action === 'skip' ? 'رد (موجود)' : 'ایجاد جدید') + '</b></p>';
        html += '<p>عنوان: ' + (a.title || '—') + '</p>';
        html += '<p>Slug: <code dir="ltr">' + (a.slug_base || '') + '</code></p>';
        html += '<p>دسته: ' + (a.category || '—') + ' — ' + formatNum(a.tag_count) + ' برچسب</p>';

        if (data.warnings && data.warnings.length) {
            html += '<ul>';
            data.warnings.forEach(function (w) {
                html += '<li>' + w + '</li>';
            });
            html += '</ul>';
        }
        showResult(data.warnings && data.warnings.length ? 'warn' : 'ok', html);
    }

    function initImport() {
        var fileInput = document.getElementById('adm-blog-json-file');
        var editor = document.getElementById('adm-blog-json-input');
        var btnValidate = document.getElementById('adm-blog-btn-validate');
        var btnImport = document.getElementById('adm-blog-btn-import');
        var meta = getMeta();

        if (fileInput && editor) {
            fileInput.addEventListener('change', function () {
                var file = fileInput.files && fileInput.files[0];
                if (!file) return;
                var reader = new FileReader();
                reader.onload = function () {
                    editor.value = reader.result;
                    try {
                        var parsed = JSON.parse(reader.result);
                        editor.value = JSON.stringify(parsed, null, 2);
                    } catch (e) { /* keep raw */ }
                };
                reader.readAsText(file, 'UTF-8');
            });
        }

        if (btnValidate) {
            btnValidate.addEventListener('click', function () {
                var payload;
                try {
                    payload = applyOptions(parseEditorJson());
                } catch (e) {
                    showResult('error', '<strong>JSON نامعتبر</strong><p>' + e.message + '</p>');
                    return;
                }
                postJson(meta.previewUrl, payload).then(function (res) {
                    renderPreview(res.data);
                }).catch(function () {
                    showResult('error', '<strong>خطای شبکه</strong>');
                });
            });
        }

        if (btnImport) {
            btnImport.addEventListener('click', function () {
                var payload;
                try {
                    payload = applyOptions(parseEditorJson());
                } catch (e) {
                    showResult('error', '<strong>JSON نامعتبر</strong><p>' + e.message + '</p>');
                    return;
                }
                btnImport.disabled = true;
                postJson(meta.importUrl, payload).then(function (res) {
                    btnImport.disabled = false;
                    if (!res.ok || !res.data.ok) {
                        var errHtml = '<strong>درون‌ریزی ناموفق</strong><ul>';
                        ((res.data && res.data.errors) || ['خطای ناشناخته']).forEach(function (e) {
                            errHtml += '<li>' + e + '</li>';
                        });
                        errHtml += '</ul>';
                        showResult('error', errHtml);
                        return;
                    }
                    var p = res.data.post || {};
                    var html = '<strong>✓ ' + (res.data.action_label || 'انجام شد') + '</strong>';
                    html += '<p>' + (p.title || '') + '</p>';
                    if (p.url) {
                        html += '<p><a href="' + p.url + '" target="_blank" rel="noopener">مشاهده مقاله →</a></p>';
                    }
                    if (res.data.action === 'created' || res.data.action === 'updated') {
                        html += '<p style="margin-top:0.5rem;font-size:0.78rem;color:var(--mk-text-muted)">صفحه را رفرش کنید تا لیست به‌روز شود.</p>';
                    }
                    showResult('ok', html);
                }).catch(function () {
                    btnImport.disabled = false;
                    showResult('error', '<strong>خطای شبکه</strong>');
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initPinnedTabs();
        initBlogTabs();
        initBlogCharts();
        initImport();
    });
})();
