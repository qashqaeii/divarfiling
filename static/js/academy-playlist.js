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

    document.addEventListener('DOMContentLoaded', function () {
        initDrawer();
        window.requestAnimationFrame(scrollActiveTrack);
    });
})();
