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

    function isDark() {
        var html = document.documentElement;
        return html.classList.contains('mk-public') && html.getAttribute('data-theme') !== 'light';
    }

    function chartColors() {
        return {
            teal: isDark() ? 'rgba(20, 184, 166, 0.7)' : 'rgba(13, 148, 136, 0.65)',
            tealBorder: isDark() ? '#14b8a6' : '#0d9488',
            gold: isDark() ? 'rgba(232, 197, 71, 0.65)' : 'rgba(201, 162, 39, 0.7)',
            grid: isDark() ? 'rgba(148, 163, 184, 0.08)' : 'rgba(148, 163, 184, 0.15)',
            text: isDark() ? '#94a3b8' : '#64748b',
        };
    }

    /* ─── Sticky nav + sliding indicator ─── */
    function initNav() {
        var nav = document.getElementById('ab-nav');
        var spacer = document.getElementById('ab-nav-spacer');
        var indicator = document.getElementById('ab-nav-indicator');
        var items = nav ? nav.querySelectorAll('.ab-nav__item') : [];
        if (!nav || !indicator) return;

        var anchorTop = 0;

        function headerH() {
            var header = document.querySelector('.mk-site-header');
            if (header) return header.getBoundingClientRect().height;
            return 56;
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
            var h = nav.offsetHeight;
            document.documentElement.style.setProperty('--ab-nav-h', h + 'px');
            var active = nav.querySelector('.ab-nav__item.is-active');
            syncIndicator(active);
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
        window.addEventListener('resize', function () {
            measure();
            onScroll();
        });

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(measure).observe(nav);
        }

        measure();
        onScroll();
    }

    /* ─── Section panels ─── */
    function initPanels() {
        var sections = ['blog-overview', 'blog-posts', 'blog-analytics', 'blog-import'];
        var els = sections.map(function (id) { return document.getElementById(id); });
        var navItems = document.querySelectorAll('.ab-nav__item');

        function show(hash) {
            if (sections.indexOf(hash) === -1) hash = 'blog-overview';
            els.forEach(function (el) {
                if (!el) return;
                if (el.id === hash) {
                    el.hidden = false;
                    el.classList.add('is-visible');
                } else {
                    el.hidden = true;
                    el.classList.remove('is-visible');
                }
            });
            navItems.forEach(function (tab) {
                var href = (tab.getAttribute('href') || '').replace('#', '');
                tab.classList.toggle('is-active', href === hash);
            });
        }

        navItems.forEach(function (tab) {
            tab.addEventListener('click', function () {
                setTimeout(function () {
                    show((location.hash || '#blog-overview').replace('#', ''));
                }, 0);
            });
        });

        window.addEventListener('hashchange', function () {
            show((location.hash || '#blog-overview').replace('#', ''));
        });

        var initial = (location.hash || '#blog-overview').replace('#', '');
        if (location.search && initial === 'blog-overview') {
            initial = 'blog-posts';
            history.replaceState(null, '', '#blog-posts');
        }
        show(initial);
    }

    /* ─── KPI count-up ─── */
    function initCounters() {
        var els = document.querySelectorAll('.ab-kpi__val[data-count]');
        els.forEach(function (el) {
            var target = parseInt(el.getAttribute('data-count'), 10) || 0;
            if (target <= 0) return;
            var start = 0;
            var duration = 800;
            var t0 = performance.now();
            function tick(now) {
                var p = Math.min(1, (now - t0) / duration);
                var eased = 1 - Math.pow(1 - p, 3);
                el.textContent = formatNum(Math.round(start + (target - start) * eased));
                if (p < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }

    /* ─── Post search ─── */
    function initSearch() {
        var input = document.getElementById('ab-post-search');
        var rows = document.querySelectorAll('.ab-post-row');
        var empty = document.getElementById('ab-search-empty');
        if (!input || !rows.length) return;

        input.addEventListener('input', function () {
            var q = input.value.trim().toLowerCase();
            var visible = 0;
            rows.forEach(function (row) {
                var text = (row.getAttribute('data-search') || '').toLowerCase();
                var match = !q || text.indexOf(q) !== -1;
                row.classList.toggle('is-hidden', !match);
                if (match) visible++;
            });
            if (empty) empty.hidden = visible > 0 || !q;
        });
    }

    /* ─── Charts ─── */
    function initCharts() {
        if (typeof Chart === 'undefined') return;
        var colors = chartColors();
        var data = getAnalytics();
        var publish = data.published_daily || { labels: [], counts: [] };
        var topViews = data.top_views || [];

        Chart.defaults.font.family = 'inherit';
        Chart.defaults.color = colors.text;

        var pubCanvas = document.getElementById('adm-blog-chart-publish');
        if (pubCanvas) {
            var grad = pubCanvas.getContext('2d').createLinearGradient(0, 0, 0, 280);
            grad.addColorStop(0, colors.teal);
            grad.addColorStop(1, 'rgba(13, 148, 136, 0.05)');

            new Chart(pubCanvas, {
                type: 'bar',
                data: {
                    labels: publish.labels,
                    datasets: [{
                        label: 'انتشار',
                        data: publish.counts,
                        backgroundColor: grad,
                        borderColor: colors.tealBorder,
                        borderWidth: 1,
                        borderRadius: 8,
                        borderSkipped: false,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            grid: { color: colors.grid },
                        },
                    },
                },
            });
        }

        var viewsCanvas = document.getElementById('adm-blog-chart-views');
        if (viewsCanvas && topViews.length) {
            new Chart(viewsCanvas, {
                type: 'bar',
                data: {
                    labels: topViews.map(function (p) {
                        return p.title.length > 24 ? p.title.slice(0, 24) + '…' : p.title;
                    }),
                    datasets: [{
                        label: 'بازدید',
                        data: topViews.map(function (p) { return p.views_count; }),
                        backgroundColor: colors.gold,
                        borderRadius: 6,
                    }],
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, grid: { color: colors.grid } },
                        y: { grid: { display: false } },
                    },
                },
            });
        }
    }

    /* ─── JSON editor ─── */
    function updateEditorMeta() {
        var editor = document.getElementById('adm-blog-json-input');
        var meta = document.getElementById('ab-editor-meta');
        var dropzone = document.getElementById('ab-dropzone');
        if (!editor) return;
        var lines = editor.value ? editor.value.split('\n').length : 0;
        if (meta) meta.textContent = formatNum(lines) + ' خط';
        if (dropzone) dropzone.classList.toggle('is-empty', !editor.value.trim());
    }

    function initEditor() {
        var editor = document.getElementById('adm-blog-json-input');
        var dropzone = document.getElementById('ab-dropzone');
        var fileInput = document.getElementById('adm-blog-json-file');
        if (!editor) return;

        editor.addEventListener('input', updateEditorMeta);
        updateEditorMeta();

        if (dropzone) {
            ['dragenter', 'dragover'].forEach(function (ev) {
                dropzone.addEventListener(ev, function (e) {
                    e.preventDefault();
                    dropzone.classList.add('is-dragover');
                });
            });
            ['dragleave', 'drop'].forEach(function (ev) {
                dropzone.addEventListener(ev, function (e) {
                    e.preventDefault();
                    dropzone.classList.remove('is-dragover');
                });
            });
            dropzone.addEventListener('drop', function (e) {
                var file = e.dataTransfer && e.dataTransfer.files[0];
                if (file) loadFile(file);
            });
        }

        function loadFile(file) {
            var reader = new FileReader();
            reader.onload = function () {
                try {
                    editor.value = JSON.stringify(JSON.parse(reader.result), null, 2);
                } catch (err) {
                    editor.value = reader.result;
                }
                updateEditorMeta();
            };
            reader.readAsText(file, 'UTF-8');
        }

        if (fileInput) {
            fileInput.addEventListener('change', function () {
                var file = fileInput.files && fileInput.files[0];
                if (file) loadFile(file);
            });
        }

        var loadSample = document.getElementById('ab-load-sample');
        if (loadSample) {
            loadSample.addEventListener('click', function () {
                var url = getMeta().sampleUrl;
                if (!url) return;
                fetch(url).then(function (r) { return r.text(); }).then(function (text) {
                    try {
                        editor.value = JSON.stringify(JSON.parse(text), null, 2);
                    } catch (e) {
                        editor.value = text;
                    }
                    updateEditorMeta();
                });
            });
        }
    }

    function parseEditorJson() {
        var raw = document.getElementById('adm-blog-json-input');
        if (!raw || !raw.value.trim()) throw new Error('JSON خالی است.');
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
        box.className = 'ab-result is-' + type;
        box.innerHTML = html;
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function postJson(url, payload) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getMeta().csrfToken || '',
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
            (data.errors || []).forEach(function (e) { errHtml += '<li>' + e + '</li>'; });
            showResult('error', errHtml + '</ul>');
            return;
        }
        var a = data.article || {};
        var actionMap = { update: 'به‌روزرسانی', skip: 'رد (موجود)', create: 'ایجاد جدید' };
        var html = '<strong>✓ JSON معتبر است</strong>';
        html += '<p>عملیات: <b>' + (actionMap[data.action] || data.action) + '</b></p>';
        html += '<p><strong>' + (a.title || '—') + '</strong></p>';
        html += '<p>Slug: <code dir="ltr">' + (a.slug_base || '') + '</code></p>';
        html += '<p>' + (a.category || '—') + ' · ' + formatNum(a.tag_count) + ' برچسب</p>';
        if (data.warnings && data.warnings.length) {
            html += '<ul>';
            data.warnings.forEach(function (w) { html += '<li>' + w + '</li>'; });
            html += '</ul>';
        }
        showResult(data.warnings && data.warnings.length ? 'warn' : 'ok', html);
    }

    function initImport() {
        var btnValidate = document.getElementById('adm-blog-btn-validate');
        var btnImport = document.getElementById('adm-blog-btn-import');
        var meta = getMeta();

        if (btnValidate) {
            btnValidate.addEventListener('click', function () {
                try {
                    postJson(meta.previewUrl, applyOptions(parseEditorJson()))
                        .then(function (res) { renderPreview(res.data); })
                        .catch(function () { showResult('error', '<strong>خطای شبکه</strong>'); });
                } catch (e) {
                    showResult('error', '<strong>JSON نامعتبر</strong><p>' + e.message + '</p>');
                }
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
                btnImport.innerHTML = '<i class="fas fa-spinner fa-spin"></i> در حال درون‌ریزی…';
                postJson(meta.importUrl, payload).then(function (res) {
                    btnImport.disabled = false;
                    btnImport.innerHTML = '<i class="fas fa-rocket"></i> درون‌ریزی مقاله';
                    if (!res.ok || !res.data.ok) {
                        var errHtml = '<strong>درون‌ریزی ناموفق</strong><ul>';
                        ((res.data && res.data.errors) || ['خطای ناشناخته']).forEach(function (e) {
                            errHtml += '<li>' + e + '</li>';
                        });
                        showResult('error', errHtml + '</ul>');
                        return;
                    }
                    var p = res.data.post || {};
                    var html = '<strong>✓ ' + (res.data.action_label || 'انجام شد') + '</strong>';
                    html += '<p>' + (p.title || '') + '</p>';
                    if (p.is_published && p.url) {
                        html += '<p><a href="' + p.url + '" target="_blank" rel="noopener">مشاهده مقاله منتشرشده →</a></p>';
                    } else {
                        html += '<p><strong>پیش‌نویس است</strong> — URL عمومی 404 می‌دهد تا publish کنید.</p>';
                        html += '<p>۱) تیک «انتشار فوری» را بزنید و با force_update دوباره import کنید<br>';
                        html += '۲) یا در <a href="' + (p.admin_edit_url || '/admin/blog/post/') + '" target="_blank" rel="noopener">Django Admin</a> گزینه «منتشر شده» را فعال کنید.</p>';
                        if (p.url) {
                            html += '<p style="font-size:0.78rem;color:var(--mk-text-muted)">پیش‌نمایش staff (بعد از login): <a href="' + p.url + '" target="_blank" rel="noopener">' + p.url + '</a></p>';
                        }
                    }
                    showResult(p.is_published ? 'ok' : 'warn', html);
                }).catch(function () {
                    btnImport.disabled = false;
                    btnImport.innerHTML = '<i class="fas fa-rocket"></i> درون‌ریزی مقاله';
                    showResult('error', '<strong>خطای شبکه</strong>');
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        initNav();
        initPanels();
        initCounters();
        initSearch();
        initCharts();
        initEditor();
        initImport();
    });
})();
