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

        /* Drag handle to dismiss */
        var grab = sidebar.querySelector('[data-acd-pl-grab]');
        if (grab) {
            var startY = 0;
            var dragging = false;

            grab.addEventListener('touchstart', function (e) {
                if (isDesktop() || !sidebar.classList.contains('is-open')) return;
                dragging = true;
                startY = e.touches[0].clientY;
            }, { passive: true });

            grab.addEventListener('touchmove', function (e) {
                if (!dragging) return;
                var dy = e.touches[0].clientY - startY;
                if (dy > 0) {
                    sidebar.style.transform = 'translateY(' + dy + 'px)';
                }
            }, { passive: true });

            grab.addEventListener('touchend', function (e) {
                if (!dragging) return;
                dragging = false;
                var dy = (e.changedTouches[0] && e.changedTouches[0].clientY) - startY;
                sidebar.style.transform = '';
                if (dy > 80) setOpen(false);
            });
        }

        if (page) {
            page._acdPlSetOpen = setOpen;
        }
    }

    function scrollActiveTrack() {
        var active = document.querySelector('.acd-pl-track.is-active');
        if (!active) return;

        var body = document.getElementById('acdPlList');
        if (body && mqDesktop.matches) {
            var top = active.offsetTop - 72;
            body.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        }

        var railActive = document.querySelector('.acd-pl-rail-item.is-active');
        var rail = document.querySelector('.acd-pl-rail-scroller');
        if (railActive && rail) {
            var left = railActive.offsetLeft - 16;
            rail.scrollTo({ left: Math.max(0, left), behavior: 'smooth' });
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

    document.addEventListener('DOMContentLoaded', function () {
        initDrawer();
        initViewTracking();
        window.requestAnimationFrame(scrollActiveTrack);
    });
})();
