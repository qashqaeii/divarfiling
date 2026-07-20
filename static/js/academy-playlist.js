/**
 * Public academy playlist — mobile drawer + scroll active track into view
 */
(function () {
    'use strict';

    function initDrawer() {
        var sidebar = document.querySelector('.acd-pl-sidebar');
        var openBtn = document.querySelector('[data-acd-pl-open]');
        var closeBtn = document.querySelector('[data-acd-pl-close]');
        if (!sidebar || !openBtn) return;

        function setOpen(open) {
            sidebar.classList.toggle('is-open', open);
            openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
            document.body.style.overflow = open ? 'hidden' : '';
        }

        openBtn.addEventListener('click', function () {
            setOpen(!sidebar.classList.contains('is-open'));
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', function () { setOpen(false); });
        }

        sidebar.addEventListener('click', function (e) {
            if (e.target.closest('.acd-pl-track-link')) {
                setOpen(false);
            }
        });
    }

    function scrollActiveTrack() {
        var active = document.querySelector('.acd-pl-track.is-active');
        if (!active) return;
        var body = document.getElementById('acdPlList');
        if (!body) return;
        var top = active.offsetTop - body.offsetTop - 24;
        body.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initDrawer();
        scrollActiveTrack();
    });
})();
