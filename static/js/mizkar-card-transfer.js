(function () {
    'use strict';

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'absolute';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        return Promise.resolve();
    }

    function normalizeCopyValue(el) {
        return (el.textContent || '').replace(/\s+/g, '').trim();
    }

    function initJalaliDatepicker() {
        if (typeof jalaliDatepicker === 'undefined') return;
        jalaliDatepicker.startWatch({
            minDate: 'attr',
            maxDate: 'attr',
            zIndex: 20050,
            separatorChars: { date: '/', between: ' ', time: ':' },
            persianDigits: true,
            autoHide: true,
            hideAfterChange: true,
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-card-pay]');
        if (!root) return;

        initJalaliDatepicker();

        root.querySelectorAll('[data-copy-target]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var target = document.getElementById(btn.getAttribute('data-copy-target'));
                if (!target) return;

                copyText(normalizeCopyValue(target)).then(function () {
                    btn.classList.add('is-copied');
                    var icon = btn.querySelector('i');
                    if (icon) {
                        icon.className = 'fas fa-check';
                    }
                    setTimeout(function () {
                        btn.classList.remove('is-copied');
                        if (icon) {
                            icon.className = 'fas fa-copy';
                        }
                    }, 1800);
                });
            });
        });

        root.querySelectorAll('.ctp-upload input[type="file"]').forEach(function (input) {
            var wrap = input.closest('.ctp-upload');
            var nameEl = wrap && wrap.querySelector('[data-upload-name]');
            if (!wrap || !nameEl) return;

            input.addEventListener('change', function () {
                if (input.files && input.files.length) {
                    nameEl.textContent = input.files[0].name;
                    wrap.classList.add('has-file');
                } else {
                    nameEl.textContent = '';
                    wrap.classList.remove('has-file');
                }
            });
        });
    });
})();
