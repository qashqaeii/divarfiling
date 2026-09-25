(function () {
    'use strict';

    var page = document.getElementById('ecc-ai');
    if (!page) return;

    var jump = page.querySelector('.aic-jump');
    if (jump) {
        var links = jump.querySelectorAll('a[href^="#"]');
        links.forEach(function (link) {
            link.addEventListener('click', function () {
                links.forEach(function (l) { l.classList.remove('is-active'); });
                link.classList.add('is-active');
            });
        });
        if ('IntersectionObserver' in window) {
            var sections = [];
            links.forEach(function (link) {
                var id = link.getAttribute('href');
                if (id && id.length > 1) {
                    var el = document.querySelector(id);
                    if (el) sections.push({ link: link, el: el });
                }
            });
            var obs = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (entry) {
                        if (!entry.isIntersecting) return;
                        sections.forEach(function (s) {
                            if (s.el === entry.target) {
                                links.forEach(function (l) { l.classList.remove('is-active'); });
                                s.link.classList.add('is-active');
                            }
                        });
                    });
                },
                { rootMargin: '-30% 0px -55% 0px', threshold: 0 }
            );
            sections.forEach(function (s) { obs.observe(s.el); });
        }
    }

    page.querySelectorAll('.aic-feature__fill').forEach(function (bar) {
        var w = bar.style.width;
        bar.style.width = '0';
        requestAnimationFrame(function () {
            bar.style.width = w;
        });
    });

})();
