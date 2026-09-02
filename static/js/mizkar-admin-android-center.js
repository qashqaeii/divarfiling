(function () {
    'use strict';

    var root = document.querySelector('.aac-page');
    if (!root) return;

    /* Section jump nav — active state on scroll */
    var jumpLinks = root.querySelectorAll('.aac-jump a[href^="#"]');
    var sections = [];
    jumpLinks.forEach(function (link) {
        var id = link.getAttribute('href').slice(1);
        var section = document.getElementById(id);
        if (section) sections.push({ link: link, section: section });
    });

    function updateJumpNav() {
        var scrollY = window.scrollY + 120;
        var current = sections[0];
        sections.forEach(function (item) {
            if (item.section.offsetTop <= scrollY) current = item;
        });
        jumpLinks.forEach(function (l) { l.classList.remove('is-active'); });
        if (current) current.link.classList.add('is-active');
    }

    window.addEventListener('scroll', updateJumpNav, { passive: true });
    updateJumpNav();

    /* Data table tabs */
    root.querySelectorAll('[data-aac-tabs]').forEach(function (wrap) {
        var tabs = wrap.querySelectorAll('.aac-tab');
        var panels = wrap.querySelectorAll('.aac-tab-panel');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                var target = tab.getAttribute('data-tab');
                tabs.forEach(function (t) { t.classList.toggle('is-active', t === tab); });
                panels.forEach(function (p) {
                    p.classList.toggle('is-active', p.getAttribute('data-panel') === target);
                });
            });
        });
    });

    /* Table search */
    root.querySelectorAll('[data-aac-search]').forEach(function (input) {
        var tableId = input.getAttribute('data-aac-search');
        var table = document.getElementById(tableId);
        if (!table) return;
        var rows = table.querySelectorAll('tbody tr');
        input.addEventListener('input', function () {
            var q = (input.value || '').trim().toLowerCase();
            rows.forEach(function (row) {
                var text = row.textContent.toLowerCase();
                row.style.display = !q || text.indexOf(q) !== -1 ? '' : 'none';
            });
        });
    });

    /* SMS select all */
    var master = document.getElementById('aac-sms-select-all');
    if (master) {
        master.addEventListener('change', function () {
            root.querySelectorAll('#aac-sms input[name="selected_phones"]').forEach(function (cb) {
                cb.checked = master.checked;
            });
            updateSmsSelectedCount();
        });
    }

    function updateSmsSelectedCount() {
        var el = document.getElementById('aac-sms-selected-count');
        if (!el) return;
        var count = root.querySelectorAll('#aac-sms input[name="selected_phones"]:checked').length;
        el.textContent = count.toLocaleString('fa-IR');
    }

    root.querySelectorAll('#aac-sms input[name="selected_phones"]').forEach(function (cb) {
        cb.addEventListener('change', updateSmsSelectedCount);
    });
    updateSmsSelectedCount();

    /* Live SMS preview */
    var textarea = document.getElementById('aac-sms-template');
    var preview = document.getElementById('aac-sms-preview-text');
    if (textarea && preview) {
        var sampleVersion = preview.getAttribute('data-sample-version') || '2.0.0';
        var sampleLatest = preview.getAttribute('data-sample-latest') || '';
        var sampleLink = preview.getAttribute('data-sample-link') || '';

        function renderPreview() {
            var tpl = textarea.value || '';
            var text = tpl
                .replace(/\{name_part\}/g, ' علی')
                .replace(/\{version\}/g, sampleVersion)
                .replace(/\{latest_version\}/g, sampleLatest)
                .replace(/\{link\}/g, sampleLink);
            preview.textContent = text || 'پیش‌نمایش پیام…';
        }

        textarea.addEventListener('input', renderPreview);
        renderPreview();
    }

    /* Count-up animation for KPI values */
    root.querySelectorAll('[data-count-up]').forEach(function (el) {
        var target = parseInt(el.getAttribute('data-count-up'), 10);
        if (isNaN(target)) return;
        var start = 0;
        var duration = 600;
        var startTime = null;

        function step(ts) {
            if (!startTime) startTime = ts;
            var p = Math.min((ts - startTime) / duration, 1);
            var val = Math.round(start + (target - start) * p);
            el.textContent = val.toLocaleString('fa-IR');
            if (p < 1) requestAnimationFrame(step);
        }

        requestAnimationFrame(step);
    });
})();
