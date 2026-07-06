/**
 * Mizkar Notice System — unified dismiss, auto-hide & toast API
 */
(function (global) {
    'use strict';

    var DURATION = 220;
    var AUTO_DISMISS_MS = 5000;

    var ICONS = {
        success: 'check-circle',
        error: 'circle-xmark',
        warning: 'triangle-exclamation',
        info: 'circle-info',
        promo: 'bullhorn',
        update: 'arrow-up-from-bracket',
        discount: 'tag',
        education: 'graduation-cap'
    };

    function getToastStack() {
        return document.getElementById('mkToastStack')
            || document.getElementById('wsToastContainer');
    }

    function isRtl() {
        return document.documentElement.getAttribute('dir') === 'rtl';
    }

    function dismiss(el, callback) {
        if (!el || el.classList.contains('is-leaving')) return;
        el.classList.add('is-leaving');
        setTimeout(function () {
            el.remove();
            if (typeof callback === 'function') callback();
            var parent = el.closest('.mk-notices--banner, .announcements-section, .mk-notices');
            if (parent && parent.querySelectorAll('.mk-notice, .announcement-bar, .banner-card').length === 0) {
                parent.classList.add('is-leaving');
                setTimeout(function () { parent.remove(); }, DURATION);
            }
        }, DURATION);
    }

    function resolveType(type) {
        var t = (type || 'info').toLowerCase();
        if (t.indexOf('success') !== -1) return 'success';
        if (t.indexOf('error') !== -1 || t.indexOf('danger') !== -1) return 'error';
        if (t.indexOf('warn') !== -1) return 'warning';
        if (t.indexOf('promo') !== -1) return 'promo';
        if (t.indexOf('update') !== -1) return 'update';
        if (t.indexOf('discount') !== -1) return 'discount';
        if (t.indexOf('education') !== -1) return 'education';
        return 'info';
    }

    function buildNotice(opts) {
        var type = resolveType(opts.type);
        var icon = opts.icon || ICONS[type] || ICONS.info;
        var dismissible = opts.dismissible !== false;
        var layout = opts.layout || 'toast';

        var el = document.createElement('div');
        el.className = 'mk-notice mk-notice--' + type + ' mk-notice--' + layout;
        el.setAttribute('role', type === 'error' ? 'alert' : 'status');

        var html = '<span class="mk-notice__icon" aria-hidden="true"><i class="fas fa-' + icon + '"></i></span>';
        html += '<div class="mk-notice__body">';
        if (opts.badge) {
            html += '<span class="mk-notice__badge">' + opts.badge + '</span>';
        }
        if (opts.title) {
            html += '<strong class="mk-notice__title">' + opts.title + '</strong>';
        }
        html += '<span class="mk-notice__text">' + (opts.message || '') + '</span>';
        html += '</div>';

        if (opts.actionUrl) {
            html += '<div class="mk-notice__actions">';
            html += '<a class="mk-notice__cta" href="' + opts.actionUrl + '">';
            html += '<span>' + (opts.actionText || 'مشاهده') + '</span>';
            if (layout !== 'toast') {
                html += '<i class="fas fa-arrow-left" aria-hidden="true"></i>';
            }
            html += '</a></div>';
        }

        if (dismissible) {
            html += '<button type="button" class="mk-notice__close" data-mk-notice-close aria-label="بستن">';
            html += '<i class="fas fa-xmark" aria-hidden="true"></i></button>';
        }

        el.innerHTML = html;
        return el;
    }

    function showToast(message, type, options) {
        var opts = typeof options === 'object' && options !== null ? options : {};
        opts.message = message;
        opts.type = type || opts.type || 'info';
        opts.layout = 'toast';
        opts.dismissible = opts.dismissible !== false;

        var stack = getToastStack();
        var el = buildNotice(opts);

        if (stack) {
            stack.appendChild(el);
        } else {
            el.style.position = 'fixed';
            el.style.bottom = 'calc(1rem + env(safe-area-inset-bottom, 0px))';
            el.style.left = '50%';
            el.style.transform = isRtl() ? 'translateX(50%)' : 'translateX(-50%)';
            el.style.zIndex = '10000';
            el.style.width = 'min(calc(100% - 2rem), 420px)';
            document.body.appendChild(el);
        }

        var ms = opts.duration || AUTO_DISMISS_MS;
        if (ms > 0) {
            setTimeout(function () { dismiss(el); }, ms);
        }
        return el;
    }

    function initDismissHandlers() {
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-mk-notice-close], .mk-notice__close, .alert-close, .ws-toast-close');
            if (!btn) return;
            var notice = btn.closest('.mk-notice, .alert, .ws-toast, .announcement-bar, .banner-card');
            if (notice) {
                e.preventDefault();
                dismiss(notice);
            }
        });
    }

    function initAutoDismiss() {
        document.querySelectorAll('[data-auto-dismiss]').forEach(function (el) {
            var ms = parseInt(el.getAttribute('data-auto-dismiss'), 10) || AUTO_DISMISS_MS;
            setTimeout(function () { dismiss(el); }, ms);
        });
    }

    function initLegacyClose() {
        global.closeAnnouncement = function (button) {
            dismiss(button.closest('.announcement-bar, .mk-notice'));
        };
        global.closeBanner = function (button) {
            dismiss(button.closest('.banner-card'));
        };
    }

    function init() {
        initDismissHandlers();
        initAutoDismiss();
        initLegacyClose();
    }

    var MkNotices = {
        dismiss: dismiss,
        show: showToast,
        build: buildNotice,
        icons: ICONS,
        init: init
    };

    global.MkNotices = MkNotices;
    global.showWsToast = showToast;
    global.showNotification = function (message, type) {
        return showToast(message, type, { duration: 3000 });
    };
    global.showToast = function (message, type) {
        return showToast(message, type, { duration: 3000 });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
