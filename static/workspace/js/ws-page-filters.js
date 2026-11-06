/**
 * Divar Filing — premium filter dropdowns (ws-filters)
 * Progressive enhancement for .ws-filters__select (native select kept for form submit).
 */
(function () {
    'use strict';

    const OPEN_CLASS = 'is-open';
    const ROOT_SEL = '.ws-filters';
    const SELECT_SEL = '.ws-filters__select:not(.crm-contacts-mob-select):not(.crm-files-mob-select):not(.crm-deals-mob-select):not([data-ws-dd-ready])';

    function closeAll(except) {
        document.querySelectorAll('.ws-filters-dd.' + OPEN_CLASS).forEach((dd) => {
            if (except && dd === except) return;
            setOpen(dd, false);
        });
    }

    function setOpen(dd, open) {
        const trigger = dd.querySelector('.ws-filters-dd__trigger');
        const menu = dd.querySelector('.ws-filters-dd__menu');
        if (!trigger || !menu) return;
        dd.classList.toggle(OPEN_CLASS, open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        menu.hidden = !open;
        if (open) {
            positionMenu(dd, menu, trigger);
            const active = menu.querySelector('[aria-selected="true"]') || menu.querySelector('[role="option"]');
            active?.focus({ preventScroll: true });
        }
    }

    function positionMenu(dd, menu, trigger) {
        menu.style.top = '';
        menu.style.bottom = '';
        menu.style.maxHeight = '';
        const rect = trigger.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom - 12;
        const spaceAbove = rect.top - 12;
        const preferDown = spaceBelow >= 220 || spaceBelow >= spaceAbove;
        if (preferDown) {
            menu.style.top = 'calc(100% + 6px)';
            menu.style.bottom = 'auto';
            menu.style.maxHeight = Math.max(160, Math.min(320, spaceBelow)) + 'px';
        } else {
            menu.style.bottom = 'calc(100% + 6px)';
            menu.style.top = 'auto';
            menu.style.maxHeight = Math.max(160, Math.min(320, spaceAbove)) + 'px';
        }
    }

    function syncTrigger(dd) {
        const select = dd.querySelector('select');
        const label = dd.querySelector('.ws-filters-dd__label');
        if (!select || !label) return;
        const opt = select.options[select.selectedIndex];
        label.textContent = (opt && opt.textContent) ? opt.textContent.trim() : '';
        dd.classList.toggle('is-active', Boolean(select.value));
        select.classList.toggle('is-active', Boolean(select.value));
        dd.querySelectorAll('.ws-filters-dd__option').forEach((btn) => {
            const on = btn.getAttribute('data-value') === select.value;
            btn.classList.toggle('is-selected', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
        });
    }

    function buildDropdown(select) {
        if (select.dataset.wsDdReady === '1') return;
        select.dataset.wsDdReady = '1';

        const wrap = document.createElement('div');
        wrap.className = 'ws-filters-dd';
        if (select.classList.contains('is-active') || select.value) wrap.classList.add('is-active');

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'ws-filters-dd__trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        const aria = select.getAttribute('aria-label') || 'فیلتر';
        trigger.setAttribute('aria-label', aria);

        const label = document.createElement('span');
        label.className = 'ws-filters-dd__label';
        const chevron = document.createElement('i');
        chevron.className = 'fas fa-chevron-down ws-filters-dd__chevron';
        chevron.setAttribute('aria-hidden', 'true');
        trigger.append(label, chevron);

        const menu = document.createElement('div');
        menu.className = 'ws-filters-dd__menu';
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-label', aria);
        menu.hidden = true;

        Array.from(select.options).forEach((opt, idx) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ws-filters-dd__option';
            btn.setAttribute('role', 'option');
            btn.setAttribute('data-value', opt.value);
            btn.tabIndex = -1;
            if (idx === 0 && !opt.value) btn.classList.add('is-placeholder');

            const text = document.createElement('span');
            text.className = 'ws-filters-dd__option-text';
            text.textContent = opt.textContent.trim();

            const check = document.createElement('i');
            check.className = 'fas fa-check ws-filters-dd__check';
            check.setAttribute('aria-hidden', 'true');

            btn.append(text, check);
            menu.appendChild(btn);
        });

        select.classList.add('ws-filters__select--enhanced');
        select.setAttribute('tabindex', '-1');
        select.setAttribute('aria-hidden', 'true');
        select.parentNode.insertBefore(wrap, select);
        wrap.append(select, trigger, menu);
        syncTrigger(wrap);

        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (select.disabled) return;
            const willOpen = !wrap.classList.contains(OPEN_CLASS);
            closeAll(wrap);
            setOpen(wrap, willOpen);
        });

        menu.addEventListener('click', (e) => {
            const optBtn = e.target.closest('.ws-filters-dd__option');
            if (!optBtn || !menu.contains(optBtn)) return;
            e.preventDefault();
            e.stopPropagation();
            const value = optBtn.getAttribute('data-value') || '';
            if (select.value !== value) {
                select.value = value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                setOpen(wrap, false);
            }
            syncTrigger(wrap);
            setOpen(wrap, false);
            trigger.focus({ preventScroll: true });
        });

        select.addEventListener('change', () => syncTrigger(wrap));
    }

    function onKeydown(e) {
        const openDd = document.querySelector('.ws-filters-dd.' + OPEN_CLASS);
        if (!openDd) return;
        const menu = openDd.querySelector('.ws-filters-dd__menu');
        const options = Array.from(menu?.querySelectorAll('.ws-filters-dd__option') || []);
        if (!options.length) return;

        if (e.key === 'Escape') {
            e.preventDefault();
            setOpen(openDd, false);
            openDd.querySelector('.ws-filters-dd__trigger')?.focus({ preventScroll: true });
            return;
        }

        const current = document.activeElement?.closest?.('.ws-filters-dd__option');
        let idx = options.indexOf(current);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            idx = Math.min(options.length - 1, Math.max(0, idx) + 1);
            options[idx].focus({ preventScroll: true });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            idx = Math.max(0, (idx < 0 ? options.length : idx) - 1);
            options[idx].focus({ preventScroll: true });
        } else if (e.key === 'Home') {
            e.preventDefault();
            options[0].focus({ preventScroll: true });
        } else if (e.key === 'End') {
            e.preventDefault();
            options[options.length - 1].focus({ preventScroll: true });
        } else if (e.key === 'Enter' || e.key === ' ') {
            if (current) {
                e.preventDefault();
                current.click();
            }
        }
    }

    function initSearchClear(root) {
        const scope = root || document;
        scope.querySelectorAll('.ws-filters__search').forEach((search) => {
            const input = search.querySelector('input[type="search"], input[type="text"]');
            const clearBtn = search.querySelector('.ws-filters__search-clear');
            if (!input || !clearBtn || clearBtn.dataset.wsClearBound === '1' || clearBtn.dataset.bound === '1') return;
            clearBtn.dataset.wsClearBound = '1';
            clearBtn.dataset.bound = '1';
            const sync = () => {
                clearBtn.hidden = !String(input.value || '').trim();
            };
            input.addEventListener('input', sync);
            clearBtn.addEventListener('click', () => {
                input.value = '';
                sync();
                input.focus({ preventScroll: true });
                const form = input.closest('form');
                if (form) {
                    if (form.requestSubmit) form.requestSubmit();
                    else form.submit();
                }
            });
            sync();
        });
    }

    function init(root) {
        const scope = root || document;
        scope.querySelectorAll(ROOT_SEL).forEach((form) => {
            form.querySelectorAll(SELECT_SEL).forEach(buildDropdown);
        });
        initSearchClear(scope);
    }

    function bindGlobals() {
        if (document.documentElement.dataset.wsFiltersDdBound === '1') return;
        document.documentElement.dataset.wsFiltersDdBound = '1';

        document.addEventListener('click', (e) => {
            if (e.target.closest('.ws-filters-dd')) return;
            closeAll();
        });
        document.addEventListener('keydown', onKeydown);
        window.addEventListener('resize', () => closeAll(), { passive: true });
        // Close only on page/container scroll — never while scrolling inside an open menu
        document.addEventListener('scroll', (e) => {
            const t = e.target;
            if (t && t.nodeType === 1 && t.closest && t.closest('.ws-filters-dd__menu')) return;
            closeAll();
        }, { passive: true, capture: true });
        // Wheel inside menu must not bubble-close via parent scrollers
        document.addEventListener('wheel', (e) => {
            const menu = e.target.closest && e.target.closest('.ws-filters-dd__menu');
            if (!menu) return;
            const canScroll = menu.scrollHeight > menu.clientHeight + 1;
            if (!canScroll) return;
            const atTop = menu.scrollTop <= 0;
            const atBottom = menu.scrollTop + menu.clientHeight >= menu.scrollHeight - 1;
            if ((e.deltaY < 0 && atTop) || (e.deltaY > 0 && atBottom)) {
                e.preventDefault();
            }
            e.stopPropagation();
        }, { passive: false, capture: true });
    }

    window.initWsFiltersDropdowns = init;

    function boot() {
        bindGlobals();
        init(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
