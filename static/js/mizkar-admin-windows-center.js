(function () {
    'use strict';

    var root = document.querySelector('.wac-page');
    if (!root) return;

    var jumpLinks = root.querySelectorAll('.wac-jump a[href^="#"]');
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

    root.querySelectorAll('[data-wac-tabs]').forEach(function (wrap) {
        var tabs = wrap.querySelectorAll('.wac-tab');
        var panels = wrap.querySelectorAll('.wac-tab-panel');
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

    root.querySelectorAll('[data-wac-search]').forEach(function (input) {
        var tableId = input.getAttribute('data-wac-search');
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

    root.querySelectorAll('[data-count-up]').forEach(function (el) {
        var target = parseInt(el.getAttribute('data-count-up'), 10);
        if (isNaN(target)) return;
        var duration = 600;
        var startTime = null;

        function step(ts) {
            if (!startTime) startTime = ts;
            var p = Math.min((ts - startTime) / duration, 1);
            var val = Math.round(target * p);
            el.textContent = val.toLocaleString('fa-IR');
            if (p < 1) requestAnimationFrame(step);
        }

        requestAnimationFrame(step);
    });
})();
