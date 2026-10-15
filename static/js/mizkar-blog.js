(function () {
    'use strict';

    function moveFilterIndicator(track) {
        if (!track) return;
        var indicator = track.querySelector('.mk-blog-filter-indicator');
        var active = track.querySelector('.mk-blog-filter-pill.is-active');
        if (!indicator || !active) return;

        indicator.style.width = active.offsetWidth + 'px';
        indicator.style.transform = 'translateX(' + active.offsetLeft + 'px)';
    }

    function initFilterIndicator() {
        var track = document.querySelector('[data-filter-track]');
        if (!track) return;

        moveFilterIndicator(track);
        window.addEventListener('resize', function () { moveFilterIndicator(track); });

        var activePill = track.querySelector('.mk-blog-filter-pill.is-active');
        if (activePill && typeof activePill.scrollIntoView === 'function') {
            activePill.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'auto' });
        }
    }

    /* ─── Sticky filter bar (list hub) ─── */
    function initBlogFilterBar() {
        var bar = document.querySelector('.mk-blog-filter-bar');
        if (!bar) return;

        var placeholder = document.createElement('div');
        placeholder.className = 'mk-blog-filter-bar-placeholder';
        placeholder.setAttribute('aria-hidden', 'true');
        bar.parentNode.insertBefore(placeholder, bar);

        var anchorTop = 0;
        var header = document.querySelector('.mk-site-header');

        function updateStickyTop() {
            var top = 0;
            if (header) {
                top = Math.ceil(header.getBoundingClientRect().height);
            }
            document.documentElement.style.setProperty('--mk-blog-sticky-top', top + 'px');
            return top;
        }

        function measureAnchor() {
            if (!bar.classList.contains('is-fixed')) {
                anchorTop = bar.getBoundingClientRect().top + window.scrollY;
            }
        }

        function syncPlaceholder() {
            placeholder.style.height = bar.offsetHeight + 'px';
        }

        function setFixed(on) {
            bar.classList.toggle('is-fixed', on);
            bar.classList.toggle('is-stuck', on);
            placeholder.classList.toggle('is-active', on);
            if (on) {
                syncPlaceholder();
            }
        }

        function updateBarState() {
            var stickyTop = updateStickyTop();
            var shouldFix = window.scrollY + stickyTop >= anchorTop - 1;

            if (shouldFix !== bar.classList.contains('is-fixed')) {
                setFixed(shouldFix);
            }

            if (!shouldFix) {
                measureAnchor();
            }
        }

        function onLayoutChange() {
            var wasFixed = bar.classList.contains('is-fixed');
            if (wasFixed) {
                setFixed(false);
            }
            measureAnchor();
            syncPlaceholder();
            updateStickyTop();
            if (wasFixed) {
                updateBarState();
            }
        }

        measureAnchor();
        syncPlaceholder();
        updateStickyTop();
        updateBarState();

        window.addEventListener('resize', onLayoutChange, { passive: true });
        window.addEventListener('scroll', updateBarState, { passive: true });

        if (typeof ResizeObserver !== 'undefined') {
            var ro = new ResizeObserver(onLayoutChange);
            if (header) ro.observe(header);
            ro.observe(bar);
        }
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
                        grid.appendChild(card);
                        bindReveal(card);
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
    var revealObs = null;

    function bindReveal(el) {
        if (!el || el.classList.contains('is-visible')) return;
        if (!revealObs) {
            if ('IntersectionObserver' in window) {
                revealObs = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('is-visible');
                            revealObs.unobserve(entry.target);
                        }
                    });
                }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });
            }
        }
        if (revealObs) {
            revealObs.observe(el);
        } else {
            el.classList.add('is-visible');
        }
    }

    document.querySelectorAll('.mk-blog-reveal').forEach(bindReveal);

    function initBlogHubMob() {
        var hero = document.querySelector('[data-blg-hero-mob]');
        if (hero) {
            requestAnimationFrame(function () {
                hero.classList.add('is-entered');
            });
        }

        var scrollWrap = document.querySelector('[data-blg-filter-scroll]');
        if (!scrollWrap) return;
        var nav = scrollWrap.querySelector('.mk-blog-filter-nav');
        if (!nav) return;

        function scrollMetrics() {
            var max = Math.max(0, nav.scrollWidth - nav.clientWidth);
            var pos = Math.abs(nav.scrollLeft);
            if (max <= 2) {
                scrollWrap.classList.remove('has-start-fade', 'has-end-fade');
                return;
            }
            scrollWrap.classList.toggle('has-start-fade', pos > 6);
            scrollWrap.classList.toggle('has-end-fade', pos < max - 6);
        }

        nav.addEventListener('scroll', scrollMetrics, { passive: true });
        window.addEventListener('resize', scrollMetrics, { passive: true });
        scrollMetrics();
    }

    initBlogFilterBar();
    initFilterIndicator();
    initBlogInfiniteScroll();
    initBlogHubMob();

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
    var tocBackdrop = document.getElementById('blog-toc-backdrop');

    function setTocOpen(open) {
        if (!tocCard || !tocToggle) return;
        tocCard.classList.toggle('is-mobile-open', open);
        tocToggle.classList.toggle('is-active', open);
        tocToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.body.classList.toggle('mk-blog-toc-open', open);
        if (tocBackdrop) {
            tocBackdrop.classList.toggle('is-visible', open);
            tocBackdrop.hidden = !open;
            tocBackdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
        }
    }

    if (tocList && tocCard) {
        var headings = prose.querySelectorAll('h2, h3');
        if (!headings.length) {
            tocCard.classList.add('is-empty');
            if (tocToggle) tocToggle.hidden = true;
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
            setTocOpen(!tocCard.classList.contains('is-mobile-open'));
        });
        if (tocBackdrop) {
            tocBackdrop.addEventListener('click', function () {
                setTocOpen(false);
            });
        }
        document.addEventListener('click', function (e) {
            if (!tocCard.classList.contains('is-mobile-open')) return;
            if (tocCard.contains(e.target) || tocToggle.contains(e.target)) return;
            if (tocBackdrop && tocBackdrop.contains(e.target)) return;
            setTocOpen(false);
        });
        if (tocList) {
            tocList.addEventListener('click', function (e) {
                if (e.target.closest('a') && window.matchMedia('(max-width: 1024px)').matches) {
                    setTocOpen(false);
                }
            });
        }
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
