(function () {
    'use strict';

    var prose = document.getElementById('blog-content');
    var tocList = document.getElementById('blog-toc-list');
    var tocCard = document.getElementById('blog-toc');
    var tocProgress = document.getElementById('blog-toc-progress');
    var progressBar = document.getElementById('blog-read-progress');
    var copyBtns = document.querySelectorAll('#blog-copy-link, #blog-copy-link-footer');
    var tocToggle = document.getElementById('blog-toc-toggle');

    /* ─── Scroll reveal (list page) ─── */
    var revealEls = document.querySelectorAll('.mk-blog-reveal');
    if (revealEls.length && 'IntersectionObserver' in window) {
        var revealObs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    revealObs.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
        revealEls.forEach(function (el) { revealObs.observe(el); });
    } else {
        revealEls.forEach(function (el) { el.classList.add('is-visible'); });
    }

    if (!prose) return;

    /* ─── FAQ accordion ─── */
    (function buildFaq() {
        var h2s = prose.querySelectorAll('h2');
        h2s.forEach(function (h2) {
            var text = (h2.textContent || '').trim();
            if (text.indexOf('سوالات متداول') === -1 && text.indexOf('FAQ') === -1) return;

            var faqWrap = document.createElement('div');
            faqWrap.className = 'mk-blog-faq';
            h2.parentNode.insertBefore(faqWrap, h2.nextSibling);

            var block = [];
            var sib = faqWrap.nextSibling;
            while (sib) {
                if (sib.nodeType === 1 && sib.tagName === 'H2') break;
                block.push(sib);
                sib = sib.nextSibling;
            }

            block.forEach(function (node) {
                if (node.nodeType !== 1 || node.tagName !== 'H3') return;

                var answerParts = [];
                var next = node.nextSibling;
                while (next && !(next.nodeType === 1 && /^H[23]$/.test(next.tagName))) {
                    answerParts.push(next);
                    next = next.nextSibling;
                }

                var details = document.createElement('details');
                details.className = 'mk-blog-faq-item';
                var summary = document.createElement('summary');
                summary.textContent = node.textContent.trim();
                details.appendChild(summary);

                var answer = document.createElement('div');
                answer.className = 'mk-blog-faq-answer';
                answerParts.forEach(function (part) { answer.appendChild(part); });
                details.appendChild(answer);

                faqWrap.appendChild(details);
                node.remove();
            });
        });
    })();

    /* ─── فهرست مطالب ─── */
    if (tocList && tocCard) {
        var headings = prose.querySelectorAll('h2, h3');
        if (!headings.length) {
            tocCard.classList.add('is-empty');
        } else {
            headings.forEach(function (heading, index) {
                if (!heading.id) {
                    heading.id = 'blog-section-' + (index + 1);
                }
                var li = document.createElement('li');
                if (heading.tagName === 'H3') {
                    li.className = 'is-h3';
                }
                var link = document.createElement('a');
                link.href = '#' + heading.id;
                link.textContent = heading.textContent.trim();
                li.appendChild(link);
                tocList.appendChild(li);
            });

            var tocLinks = tocList.querySelectorAll('a');
            if ('IntersectionObserver' in window && tocLinks.length) {
                var observer = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (!entry.isIntersecting) return;
                        var id = entry.target.getAttribute('id');
                        tocLinks.forEach(function (a) {
                            a.classList.toggle('is-active', a.getAttribute('href') === '#' + id);
                        });
                    });
                }, { rootMargin: '-18% 0px -62% 0px', threshold: 0 });

                headings.forEach(function (h) { observer.observe(h); });
            }
        }
    }

    /* ─── Mobile TOC toggle ─── */
    if (tocToggle && tocCard) {
        tocToggle.addEventListener('click', function () {
            var open = tocCard.classList.toggle('is-mobile-open');
            tocToggle.classList.toggle('is-active', open);
            tocToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('click', function (e) {
            if (!tocCard.classList.contains('is-mobile-open')) return;
            if (tocCard.contains(e.target) || tocToggle.contains(e.target)) return;
            tocCard.classList.remove('is-mobile-open');
            tocToggle.classList.remove('is-active');
            tocToggle.setAttribute('aria-expanded', 'false');
        });
    }

    /* ─── نوار پیشرفت مطالعه ─── */
    function updateProgress() {
        var rect = prose.getBoundingClientRect();
        var start = window.scrollY + rect.top - 80;
        var height = prose.offsetHeight;
        var scrolled = window.scrollY - start;
        var pct = Math.min(100, Math.max(0, (scrolled / height) * 100));

        if (progressBar) {
            progressBar.style.width = pct + '%';
        }
        if (tocProgress) {
            tocProgress.textContent = Math.round(pct) + '٪';
        }
    }

    if (progressBar || tocProgress) {
        var ticking = false;
        window.addEventListener('scroll', function () {
            if (!ticking) {
                window.requestAnimationFrame(function () {
                    updateProgress();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
        updateProgress();
    }

    /* ─── کپی لینک ─── */
    function bindCopy(btn) {
        if (!btn) return;
        btn.addEventListener('click', function () {
            var url = window.location.href;
            var done = function () {
                btn.classList.add('is-copied');
                var label = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> کپی شد';
                setTimeout(function () {
                    btn.classList.remove('is-copied');
                    btn.innerHTML = label;
                }, 2000);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(done).catch(function () {
                    window.prompt('لینک مقاله:', url);
                });
            } else {
                window.prompt('لینک مقاله:', url);
            }
        });
    }

    copyBtns.forEach(bindCopy);
})();
