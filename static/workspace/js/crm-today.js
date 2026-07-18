(function () {
    'use strict';

    function initTelHandlers() {
        document.querySelectorAll('.crm-today-pro [data-tel]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const tel = btn.getAttribute('data-tel');
                if (tel) window.location.href = 'tel:' + tel;
            });
        });
    }

    function setPanel(root, board, tabs, name) {
        if (!board) return;
        board.setAttribute('data-active-panel', name);
        board.querySelectorAll('.crm-queue-col').forEach((col) => {
            const isActive = col.id === 'panel-' + name;
            col.classList.toggle('is-panel-active', isActive);
            if (isActive) {
                col.removeAttribute('hidden');
            } else {
                col.setAttribute('hidden', '');
            }
        });
        tabs.forEach((tab) => {
            const active = tab.getAttribute('data-today-tab') === name;
            tab.classList.toggle('is-active', active);
            tab.setAttribute('aria-selected', active ? 'true' : 'false');
        });
    }

    function initTabs() {
        const root = document.getElementById('crmTodayPro');
        if (!root) return;
        const board = root.querySelector('.crm-today-board');
        const tabs = Array.from(root.querySelectorAll('[data-today-tab]'));
        if (!board || !tabs.length) return;

        const mq = window.matchMedia('(max-width: 900px)');

        const syncDesktop = () => {
            if (!mq.matches) {
                board.querySelectorAll('.crm-queue-col').forEach((col) => {
                    col.classList.add('is-panel-active');
                    col.removeAttribute('hidden');
                });
            } else {
                const current = board.getAttribute('data-active-panel') || 'overdue';
                setPanel(root, board, tabs, current);
            }
        };

        tabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                const name = tab.getAttribute('data-today-tab');
                if (name) setPanel(root, board, tabs, name);
            });
        });

        root.querySelectorAll('[data-today-jump]').forEach((link) => {
            link.addEventListener('click', (e) => {
                const name = link.getAttribute('data-today-jump');
                if (!name) return;
                if (mq.matches) {
                    e.preventDefault();
                    setPanel(root, board, tabs, name);
                    const panel = document.getElementById('panel-' + name);
                    if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        syncDesktop();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', syncDesktop);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(syncDesktop);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        initTelHandlers();
        initTabs();
    });
})();
