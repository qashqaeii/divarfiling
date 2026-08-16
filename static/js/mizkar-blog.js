(function () {
    'use strict';

    /* ─── Sticky filter bar (list hub) ─── */
    function initBlogFilterBar() {
        var bar = document.querySelector('.mk-blog-filter-bar');
        if (!bar) return;

        function updateStickyTop() {
            var top = 0;
            var header = document.querySelector('.mk-site-header');
            if (header) {
                top = Math.ceil(header.getBoundingClientRect().height);
            }
            document.documentElement.style.setProperty('--mk-blog-sticky-top', top + 'px');
        }

        function updateStuckState() {
            var header = document.querySelector('.mk-site-header');
            var headerBottom = header ? header.getBoundingClientRect().bottom : 0;
            var barTop = bar.getBoundingClientRect().top;
            var stuck = window.scrollY > 8 && barTop <= headerBottom + 2;
            bar.classList.toggle('is-stuck', stuck);
        }

        updateStickyTop();
        window.addEventListener('resize', updateStickyTop, { passive: true });
        window.addEventListener('scroll', updateStuckState, { passive: true });
        updateStuckState();
    }

    /* ─── Infinite scroll (list hub) ─── */
    function initBlogInfiniteScroll() {
        var grid = document.getElementById('mk-blog-grid');
        var sentinel = document.getElementById('mk-blog-load-sentinel');
        if (!grid || !sentinel) return;

        var statusEl = document.getElementById('mk-blog-load-status');
        var loading = false;

        function hasNext() {
            return grid.getAttribute('data-has-next') === '1';
        }

        function getNextPage() {
            var raw = grid.getAttribute('data-next-page');
            return raw ? parseInt(raw, 10) : null;
        }

        function setLoading(on) {
            loading = on;
            if (statusEl) {
                statusEl.hidden = !on;
            }
        }

        function loadMore() {
            var nextPage = getNextPage();
            if (!hasNext() || !nextPage || loading) return;

            setLoading(true);

            var cat = grid.getAttribute('data-cat') || '';
            var params = new URLSearchParams({ partial: '1', page: String(nextPage) });
            if (cat) params.set('cat', cat);

            fetch(window.location.pathname + '?' + params.toString(), {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            })
                .then(function (res) {
                    if (!res.ok) throw new Error('load failed');
                    return res.json();
                })
                .then(function (data) {
                    if (!data.html) return;

                    var wrap = document.createElement('div');
                    wrap.innerHTML = data.html.trim();
                    var cards = wrap.querySelectorAll('.mk-blog-card');

                    cards.forEach(function (card) {
                        card.classList.add('is-visible');
                        grid.appendChild(card);
                    });

                    if (data.has_next && data.next_page) {
                        grid.setAttribute('data-has-next', '1');
                        grid.setAttribute('data-next-page', String(data.next_page));
                    } else {
                        grid.setAttribute('data-has-next', '0');
                        grid.removeAttribute('data-next-page');
                        sentinel.hidden = true;
                    }
                })
                .catch(function () {
                    if (statusEl) {
                        statusEl.textContent = 'بارگذاری ناموفق بود. دوباره اسکرول کنید.';
                        statusEl.hidden = false;
                    }
                })
                .finally(function () {
                    setLoading(false);
                });
        }

        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) loadMore();
                });
            }, { root: null, rootMargin: '320px 0px 320px 0px', threshold: 0 });
            observer.observe(sentinel);
        }
    }

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

    initBlogFilterBar();
    initBlogInfiniteScroll();

    var prose = document.getElementById('blog-content');
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
    var tocList = document.getElementById('blog-toc-list');
    var tocCard = document.getElementById('blog-toc');
    var tocProgress = document.getElementById('blog-toc-progress');
    var progressBar = document.getElementById('blog-read-progress');
    var copyBtns = document.querySelectorAll('#blog-copy-link, #blog-copy-link-footer');
    var tocToggle = document.getElementById('blog-toc-toggle');

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
