(function initAccountShell() {
    var shell = document.querySelector('[data-account-shell]');
    if (!shell) return;

    var openBtn = shell.querySelector('[data-account-sidebar-open]');
    var closeBtn = shell.querySelector('[data-account-sidebar-close]');
    var backdrop = shell.querySelector('[data-account-backdrop]');

    function setOpen(isOpen) {
        shell.classList.toggle('is-sidebar-open', isOpen);
        if (backdrop) backdrop.hidden = !isOpen;
        document.body.style.overflow = isOpen ? 'hidden' : '';
    }

    if (openBtn) {
        openBtn.addEventListener('click', function () { setOpen(true); });
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', function () { setOpen(false); });
    }
    if (backdrop) {
        backdrop.addEventListener('click', function () { setOpen(false); });
    }

    shell.querySelectorAll('.mk-account-sidebar__link').forEach(function (link) {
        link.addEventListener('click', function () {
            if (window.matchMedia('(max-width: 960px)').matches) {
                setOpen(false);
            }
        });
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
})();
