(function () {
    'use strict';

    var FA = '۰۱۲۳۴۵۶۷۸۹';

    function toFaDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return FA[parseInt(d, 10)];
        });
    }

    function formatTomanCompact(amount) {
        var v = Math.round(Number(amount) || 0);
        if (v >= 1000000000) {
            var b = v / 1000000000;
            var bStr = (Math.round(b * 10) / 10) % 1 === 0 ? String(Math.round(b)) : b.toFixed(1).replace(/\.0$/, '');
            return toFaDigits(bStr) + ' میلیارد';
        }
        if (v >= 1000000) {
            return toFaDigits(String(Math.round(v / 1000000))) + ' میلیون';
        }
        if (v >= 1000) {
            return toFaDigits(String(Math.round(v / 1000))) + ' هزار';
        }
        return toFaDigits(String(v));
    }

    function formatDepositLabel(amount) {
        return formatTomanCompact(amount) + ' تومان';
    }

    function formatRentLabel(amount) {
        var v = Math.round(Number(amount) || 0);
        if (v === 0) {
            return 'رایگان';
        }
        return formatTomanCompact(v) + ' تومان';
    }

    function interpolate(cfg, t) {
        var baseD = cfg.base_deposit;
        var baseR = cfg.base_rent;
        var altD = cfg.alt_deposit;
        var altR = cfg.alt_rent;
        if (t <= 0) {
            return { deposit: baseD, rent: baseR };
        }
        if (t >= 1) {
            return { deposit: altD, rent: altR };
        }
        var dep = Math.round(baseD + t * (altD - baseD));
        var rent = Math.round(baseR + t * (altR - baseR));
        dep = Math.max(0, dep);
        rent = Math.max(0, rent);
        var loD = Math.min(baseD, altD);
        var hiD = Math.max(baseD, altD);
        var loR = Math.min(baseR, altR);
        var hiR = Math.max(baseR, altR);
        dep = Math.max(loD, Math.min(hiD, dep));
        rent = Math.max(loR, Math.min(hiR, rent));
        return { deposit: dep, rent: rent };
    }

    function stepToT(cfg, step) {
        var max = cfg.steps || 100;
        if (max <= 0) {
            return 0;
        }
        return Math.max(0, Math.min(1, step / max));
    }

    function ariaValueText(dep, rent) {
        return 'ودیعه ' + formatDepositLabel(dep) + '، اجاره ' + formatRentLabel(rent);
    }

    function initSlider(root) {
        var cfgEl = document.getElementById('ws-rent-convert-slider');
        if (!cfgEl) {
            return;
        }
        var cfg;
        try {
            cfg = JSON.parse(cfgEl.textContent);
        } catch (e) {
            return;
        }
        var range = root.querySelector('[data-rc-range]');
        var depEl = root.querySelector('[data-rc-dep]');
        var rentEl = root.querySelector('[data-rc-rent]');
        var fillEl = root.querySelector('[data-rc-fill]');
        var midNote = root.querySelector('[data-rc-mid-note]');
        var buttons = root.querySelectorAll('[data-rc-step]');
        var maxStep = cfg.steps || 100;

        function syncEndpoints(step) {
            buttons.forEach(function (btn) {
                var target = parseInt(btn.getAttribute('data-rc-step'), 10);
                var active = target === step;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
        }

        function applyStep(step, fromUser) {
            step = Math.max(0, Math.min(maxStep, Math.round(step)));
            if (range && !range.disabled) {
                range.value = String(step);
            }
            var t = stepToT(cfg, step);
            var vals = interpolate(cfg, t);
            if (depEl) {
                depEl.textContent = formatDepositLabel(vals.deposit);
            }
            if (rentEl) {
                rentEl.textContent = formatRentLabel(vals.rent);
            }
            if (range) {
                range.setAttribute('aria-valuetext', ariaValueText(vals.deposit, vals.rent));
            }
            var pct = maxStep > 0 ? (step / maxStep) * 100 : 0;
            root.style.setProperty('--rc-pct', pct + '%');
            if (midNote) {
                var showMid = step > 0 && step < maxStep;
                midNote.hidden = !showMid;
            }
            syncEndpoints(step);
        }

        if (range) {
            range.addEventListener('input', function () {
                applyStep(parseInt(range.value, 10), true);
            });
            range.addEventListener('change', function () {
                applyStep(parseInt(range.value, 10), true);
            });
        }
        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                applyStep(parseInt(btn.getAttribute('data-rc-step'), 10), true);
            });
        });
        applyStep(cfg.default_step || 0, false);
    }

    function initDual(root) {
        var depEl = root.querySelector('[data-rc-dep]');
        var rentEl = root.querySelector('[data-rc-rent]');
        var buttons = root.querySelectorAll('[data-rc-state]');
        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                buttons.forEach(function (b) {
                    b.classList.remove('is-active');
                    b.setAttribute('aria-pressed', 'false');
                });
                btn.classList.add('is-active');
                btn.setAttribute('aria-pressed', 'true');
                if (depEl) {
                    depEl.textContent = btn.getAttribute('data-rc-dep') || '';
                }
                if (rentEl) {
                    rentEl.textContent = btn.getAttribute('data-rc-rent') || '';
                }
            });
        });
    }

    function init() {
        document.querySelectorAll('[data-ws-rent-convert]').forEach(function (root) {
            if (root.classList.contains('ws-ld-rent-convert--dual')) {
                initDual(root);
            } else {
                initSlider(root);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
