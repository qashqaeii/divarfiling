/**
 * Public academy playlist — YouTube-like drawer, scrim, active track scroll
 */
(function () {
    'use strict';

    var mqDesktop = window.matchMedia('(min-width: 1100px)');

    function initDrawer() {
        var page = document.getElementById('acdPlaylistPage');
        var sidebar = document.getElementById('acdPlSidebar') || document.querySelector('.acd-pl-sidebar');
        var scrim = document.querySelector('[data-acd-pl-scrim]');
        var openBtns = document.querySelectorAll('[data-acd-pl-open]');
        var closeBtn = document.querySelector('[data-acd-pl-close]');
        if (!sidebar || !openBtns.length) return;

        function isDesktop() {
            return mqDesktop.matches;
        }

        function setOpen(open) {
            if (isDesktop()) {
                open = false;
            }
            sidebar.classList.toggle('is-open', open);
            document.body.classList.toggle('acd-pl-drawer-open', open);
            openBtns.forEach(function (btn) {
                btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            if (scrim) {
                if (open) {
                    scrim.hidden = false;
                    scrim.setAttribute('aria-hidden', 'false');
                } else {
                    scrim.hidden = true;
                    scrim.setAttribute('aria-hidden', 'true');
                }
            }
            if (open) {
                window.requestAnimationFrame(function () {
                    var active = sidebar.querySelector('.acd-pl-track.is-active');
                    var list = document.getElementById('acdPlList');
                    if (active && list) {
                        var top = active.offsetTop - 56;
                        list.scrollTop = Math.max(0, top);
                    }
                });
            }
        }

        openBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                setOpen(!sidebar.classList.contains('is-open'));
            });
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', function () { setOpen(false); });
        }

        if (scrim) {
            scrim.addEventListener('click', function () { setOpen(false); });
        }

        sidebar.addEventListener('click', function (e) {
            if (e.target.closest('.acd-pl-track-link') && !isDesktop()) {
                setOpen(false);
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
                setOpen(false);
            }
        });

        function onViewportChange() {
            if (isDesktop()) setOpen(false);
        }

        if (typeof mqDesktop.addEventListener === 'function') {
            mqDesktop.addEventListener('change', onViewportChange);
        } else if (typeof mqDesktop.addListener === 'function') {
            mqDesktop.addListener(onViewportChange);
        }

        /* Drag handle / sheet header to dismiss */
        var grab = sidebar.querySelector('[data-acd-pl-grab]');
        var sheetHead = sidebar.querySelector('.acd-pl-sidebar-head');
        var dragTargets = [grab, sheetHead].filter(Boolean);
        if (dragTargets.length) {
            var startY = 0;
            var dragging = false;

            function onStart(e) {
                if (isDesktop() || !sidebar.classList.contains('is-open')) return;
                if (e.target.closest('.acd-pl-sidebar-close')) return;
                dragging = true;
                startY = e.touches[0].clientY;
                sidebar.style.transition = 'none';
            }

            function onMove(e) {
                if (!dragging) return;
                var dy = e.touches[0].clientY - startY;
                if (dy > 0) {
                    sidebar.style.transform = 'translateY(' + dy + 'px)';
                }
            }

            function onEnd(e) {
                if (!dragging) return;
                dragging = false;
                sidebar.style.transition = '';
                var dy = (e.changedTouches[0] && e.changedTouches[0].clientY) - startY;
                sidebar.style.transform = '';
                if (dy > 70) setOpen(false);
            }

            dragTargets.forEach(function (el) {
                el.addEventListener('touchstart', onStart, { passive: true });
                el.addEventListener('touchmove', onMove, { passive: true });
                el.addEventListener('touchend', onEnd);
            });
        }

        if (page) {
            page._acdPlSetOpen = setOpen;
        }
    }

    function scrollActiveTrack() {
        var active = document.querySelector('.acd-pl-track.is-active');
        var body = document.getElementById('acdPlList');
        if (active && body) {
            if (mqDesktop.matches) {
                var top = active.offsetTop - 72;
                body.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
            } else if (document.querySelector('.acd-pl-sidebar.is-open')) {
                try {
                    active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                } catch (e) {
                    active.scrollIntoView(false);
                }
            }
        }

        var railActive = document.querySelector('.acd-pl-rail-item.is-active');
        if (railActive) {
            try {
                railActive.scrollIntoView({
                    inline: 'center',
                    block: 'nearest',
                    behavior: 'smooth',
                });
            } catch (e) {
                railActive.scrollIntoView(false);
            }
        }
    }

    function csrfToken() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function toFaDigits(n) {
        return String(n).replace(/\d/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[parseInt(d, 10)];
        });
    }

    function initViewTracking() {
        var page = document.getElementById('acdPlaylistPage');
        if (!page) return;
        var slug = page.getAttribute('data-video-slug');
        var tpl = page.getAttribute('data-view-url-tpl');
        if (!slug || !tpl) return;

        var playerShell = document.querySelector('[data-acd-pl-player]');
        var video = playerShell ? playerShell.querySelector('video') : null;
        if (!video) return;

        var sent = false;
        video.addEventListener('play', function () {
            if (sent) return;
            sent = true;
            var url = tpl.replace('__SLUG__', slug);
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: '{}',
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data || !data.ok) return;
                    var el = document.querySelector('[data-acd-pl-views-count]');
                    if (el && data.views_count != null) {
                        el.textContent = toFaDigits(data.views_count);
                    }
                })
                .catch(function () {});
        });
    }

    function normalizeFaQuery(raw) {
        return String(raw || '').trim().toLowerCase()
            .replace(/ي/g, 'ی').replace(/ك/g, 'ک');
    }

    function initPlaylistSearch() {
        var dataEl = document.getElementById('acdPlSearchData');
        var input = document.getElementById('acdPlSearch');
        var empty = document.getElementById('acdPlSearchEmpty');
        if (!dataEl || !input) return;

        var bySlug = {};
        try {
            JSON.parse(dataEl.textContent || '[]').forEach(function (item) {
                bySlug[item.slug] = normalizeFaQuery(item.searchText || item.title || '');
            });
        } catch (e) {
            return;
        }

        function trackScore(slug, q) {
            if (!q) return 1;
            var blob = bySlug[slug] || '';
            var s = 0;
            if (blob.indexOf(q) !== -1) s += 100;
            q.split(/\s+/).forEach(function (tok) {
                if (tok.length >= 2 && blob.indexOf(tok) !== -1) s += 12;
            });
            return s;
        }

        function applyFilter() {
            var q = normalizeFaQuery(input.value);
            var anyVisible = false;
            document.querySelectorAll('.acd-pl-track[data-acd-pl-slug]').forEach(function (row) {
                var slug = row.getAttribute('data-acd-pl-slug');
                var show = !q || trackScore(slug, q) > 0;
                row.hidden = !show;
                if (show) anyVisible = true;
            });
            document.querySelectorAll('.acd-pl-chapter').forEach(function (chapter) {
                var tracks = chapter.querySelectorAll('.acd-pl-track[data-acd-pl-slug]');
                var visible = Array.prototype.some.call(tracks, function (t) { return !t.hidden; });
                chapter.hidden = q && !visible;
            });
            if (empty) empty.hidden = !q || anyVisible;
        }

        input.addEventListener('input', applyFilter);
        input.addEventListener('search', applyFilter);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initDrawer();
        initViewTracking();
        initPlaylistSearch();
        window.requestAnimationFrame(scrollActiveTrack);
    });
})();
