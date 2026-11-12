(function initAccountShell() {
    var shell = document.querySelector('[data-account-shell]');
    if (!shell) return;

    // The mobile chrome lives outside the main shell in base.html.
    var openBtn = document.querySelector('[data-account-sidebar-open]');
    var closeBtn = shell.querySelector('[data-account-sidebar-close]');
    var backdrop = shell.querySelector('[data-account-backdrop]');
    var sidebar = shell.querySelector('#accountSidebar');
    var previousFocus = null;
    var previousOverflow = '';
    var mobileQuery = window.matchMedia('(max-width: 1024px)');

    function setOpen(shouldOpen) {
        var next = Boolean(shouldOpen && mobileQuery.matches);
        var wasOpen = shell.classList.contains('is-sidebar-open');
        if (next === wasOpen) return;

        if (next) {
            previousFocus = document.activeElement;
            previousOverflow = document.body.style.overflow;
        }

        shell.classList.toggle('is-sidebar-open', next);
        if (backdrop) backdrop.hidden = !next;
        if (openBtn) {
            openBtn.setAttribute('aria-expanded', next ? 'true' : 'false');
            openBtn.setAttribute('aria-label', next ? 'بستن منوی بخش‌های حساب' : 'نمایش همه بخش‌های حساب');
        }
        document.body.style.overflow = next ? 'hidden' : previousOverflow;

        if (next && closeBtn) {
            window.requestAnimationFrame(function () { closeBtn.focus(); });
        } else if (!next && previousFocus && typeof previousFocus.focus === 'function') {
            previousFocus.focus();
            previousFocus = null;
        }
    }

    if (openBtn) {
        openBtn.addEventListener('click', function () {
            setOpen(!shell.classList.contains('is-sidebar-open'));
        });
    }
    if (closeBtn) closeBtn.addEventListener('click', function () { setOpen(false); });
    if (backdrop) backdrop.addEventListener('click', function () { setOpen(false); });

    if (sidebar) {
        sidebar.querySelectorAll('a[href]').forEach(function (link) {
            link.addEventListener('click', function () {
                if (mobileQuery.matches) setOpen(false);
            });
        });
    }

    document.addEventListener('keydown', function (event) {
        if (!shell.classList.contains('is-sidebar-open') || !mobileQuery.matches) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            setOpen(false);
            return;
        }
        if (event.key !== 'Tab' || !sidebar) return;
        var focusables = Array.prototype.slice.call(
            sidebar.querySelectorAll('a[href], button:not([disabled])')
        ).filter(function (el) { return el.getClientRects().length > 0; });
        if (!focusables.length) return;
        var first = focusables[0];
        var last = focusables[focusables.length - 1];
        if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
            event.preventDefault();
            first.focus();
        }
    });

    window.addEventListener('resize', function () {
        if (!mobileQuery.matches && shell.classList.contains('is-sidebar-open')) setOpen(false);
    });

    function copyText(text, button) {
        if (!text) return Promise.reject(new Error('empty'));

        function flash(state, label) {
            if (!button) return;
            button.classList.remove('is-success', 'is-error');
            if (state) button.classList.add(state);
            var labelEl = button.querySelector('.mk-acc-affiliate__copy-text');
            if (labelEl && label) labelEl.textContent = label;
            window.setTimeout(function () {
                button.classList.remove('is-success', 'is-error');
                if (labelEl) labelEl.textContent = 'کپی';
            }, 1800);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(function () {
                flash('is-success', 'کپی شد');
                if (typeof showNotification === 'function') showNotification('لینک معرف کپی شد!', 'success');
                else if (typeof showToast === 'function') showToast('لینک معرف کپی شد!', 'success');
            }).catch(function () {
                flash('is-error', 'خطا');
                if (typeof showNotification === 'function') showNotification('خطا در کپی', 'error');
            });
        }

        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            flash('is-success', 'کپی شد');
            if (typeof showNotification === 'function') showNotification('لینک معرف کپی شد!', 'success');
        } catch (err) {
            flash('is-error', 'خطا');
            if (typeof showNotification === 'function') showNotification('خطا در کپی', 'error');
            return Promise.reject(err);
        } finally {
            document.body.removeChild(ta);
        }
        return Promise.resolve();
    }

    shell.querySelectorAll('[data-copy-target]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.getElementById(btn.getAttribute('data-copy-target'));
            if (!input) return;
            copyText(input.value, btn);
        });
    });

    shell.querySelectorAll('[data-copy-text]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            copyText(btn.getAttribute('data-copy-text'), btn);
            if (typeof showNotification === 'function') showNotification('کد معرف کپی شد!', 'success');
        });
    });

    // Center the selected tab without scrolling the page vertically.
    var tabTrack = document.querySelector('[data-account-tab-track]');
    if (tabTrack) {
        var activeTab = tabTrack.querySelector('.mk-account-tab-rail__item.is-active');
        if (activeTab) {
            window.requestAnimationFrame(function () {
                var railRect = tabTrack.getBoundingClientRect();
                var tabRect = activeTab.getBoundingClientRect();
                var delta = (tabRect.left + tabRect.width / 2) -
                    (railRect.left + railRect.width / 2);
                if (Math.abs(delta) > 4) {
                    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                    tabTrack.scrollBy({ left: delta, behavior: reduced ? 'auto' : 'smooth' });
                }
            });
        }
    }
})();
