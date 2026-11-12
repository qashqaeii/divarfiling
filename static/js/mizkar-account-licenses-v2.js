/* Account Center · licensing enhancements — no changes to license API mutations.
   Progressive enhancement for local search, status filters and private key display. */
(function initPremiumAccountLicenses() {
    'use strict';
    var root = document.querySelector('[data-license-mgmt].lic-premium');
    if (!root) return;

    var toolbar = root.querySelector('[data-lic-toolbar]');
    var search = root.querySelector('[data-lic-search]');
    var filters = Array.prototype.slice.call(root.querySelectorAll('[data-lic-filter]'));
    var tiles = Array.prototype.slice.call(root.querySelectorAll('.lic-grid > .lic-tile'));
    var resultLabel = root.querySelector('[data-lic-result-count]');
    var filteredEmpty = root.querySelector('[data-lic-filter-empty]');
    var clearFilters = root.querySelector('[data-lic-clear-filters]');
    var selectedFilter = 'all';

    function normalize(value) {
        return String(value || '').normalize('NFKC').toLocaleLowerCase()
            .replace(/ي/g, 'ی').replace(/ك/g, 'ک')
            .replace(/\s+/g, ' ').trim();
    }

    function matchStatus(tile, mode) {
        var tone = tile.getAttribute('data-lic-tone') || '';
        if (mode === 'expired') return tone === 'expired';
        if (mode === 'active') return tone !== 'expired' && tone !== 'inactive';
        if (mode === 'available') {
            return tile.getAttribute('data-alloc-state') === 'available' && tone !== 'expired';
        }
        if (mode === 'attention') return tone === 'warning' || tone === 'critical';
        return true;
    }

    function paintFilterState() {
        filters.forEach(function (button) {
            var active = button.getAttribute('data-lic-filter') === selectedFilter;
            button.setAttribute('aria-pressed', active ? 'true' : 'false');
            button.classList.toggle('is-active', active);
        });
    }

    function applyFilters() {
        var term = search ? normalize(search.value) : '';
        var shown = 0;
        tiles.forEach(function (tile) {
            var identity = tile.querySelector('.lic-tile-names');
            var key = tile.querySelector('.lic-tile-key-code');
            var searchText = normalize((identity ? identity.textContent : '') + ' ' + (key ? key.textContent : ''));
            var visible = matchStatus(tile, selectedFilter) && (!term || searchText.indexOf(term) !== -1);
            tile.hidden = !visible;
            if (visible) shown++;
        });
        if (resultLabel) {
            resultLabel.textContent = shown + ' لایسنس از ' + tiles.length + ' مورد نمایش داده می‌شود';
        }
        if (filteredEmpty) filteredEmpty.hidden = shown !== 0;
    }

    function clearAllFilters() {
        if (search) search.value = '';
        selectedFilter = 'all';
        paintFilterState();
        applyFilters();
        if (search) search.focus();
    }

    if (toolbar && search && filters.length && tiles.length) {
        // Without JS, all license cards stay visible and filtering controls stay hidden.
        toolbar.hidden = false;
        if (resultLabel) resultLabel.hidden = false;
        search.addEventListener('input', applyFilters);
        filters.forEach(function (button) {
            button.addEventListener('click', function () {
                selectedFilter = button.getAttribute('data-lic-filter') || 'all';
                paintFilterState();
                applyFilters();
            });
        });
        if (clearFilters) clearFilters.addEventListener('click', clearAllFilters);
        applyFilters();
    }

    // Mask on load only. A user without JS still sees their key and can copy it.
    root.querySelectorAll('[data-lic-toggle-key]').forEach(function (toggle) {
        var controlledId = toggle.getAttribute('aria-controls');
        var key = controlledId && document.getElementById(controlledId);
        if (!key) return;
        key.classList.add('is-masked');
        toggle.setAttribute('aria-pressed', 'false');
        toggle.addEventListener('click', function () {
            var isShowing = key.classList.toggle('is-masked') === false;
            toggle.setAttribute('aria-pressed', isShowing ? 'true' : 'false');
            toggle.setAttribute('aria-label', isShowing ? 'پنهان کردن کلید لایسنس' : 'نمایش کلید لایسنس');
            toggle.setAttribute('title', isShowing ? 'پنهان کردن کلید' : 'نمایش کلید');
            var icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye', !isShowing);
                icon.classList.toggle('fa-eye-slash', isShowing);
            }
        });
    });

    // Existing dashboard expiration ticker changes data-lic-tone on expiry;
    // keep the small status badge and any active local filter in sync.
    function syncLiveTone(tile) {
        var badge = tile.querySelector('[data-lic-status]');
        if (!badge) return;
        var tone = tile.getAttribute('data-lic-tone') || '';
        Array.prototype.slice.call(badge.classList).forEach(function (name) {
            if (name.indexOf('lic-premium__tile-status--') === 0) badge.classList.remove(name);
        });
        badge.classList.add('lic-premium__tile-status--' + tone);
        var dot = badge.querySelector('.lic-premium__status-dot');
        var state = tone === 'expired' ? 'منقضی' :
            tone === 'inactive' ? 'غیرفعال' :
            tone === 'unlimited' ? 'نامحدود' :
            tone === 'warning' || tone === 'critical' ? 'نزدیک انقضا' : 'معتبر';
        badge.textContent = '';
        if (dot) badge.appendChild(dot);
        badge.appendChild(document.createTextNode(state));
        if (toolbar && !toolbar.hidden) applyFilters();
    }

    if (typeof MutationObserver !== 'undefined') {
        tiles.forEach(function (tile) {
            var observer = new MutationObserver(function (records) {
                if (records.some(function (r) { return r.attributeName === 'data-lic-tone'; })) syncLiveTone(tile);
            });
            observer.observe(tile, { attributes: true, attributeFilter: ['data-lic-tone'] });
        });
    }

    // Clipboard is not available in all mobile WebViews or insecure origins.
    // Keep the inline copyLicenseKey API used by the original template.
    function fallbackCopy(value) {
        var area = document.createElement('textarea');
        area.value = value;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.inset = '-1000px auto auto -1000px';
        document.body.appendChild(area);
        var prior = document.activeElement;
        area.focus();
        area.select();
        var successful = false;
        try { successful = document.execCommand('copy'); }
        finally {
            area.remove();
            if (prior && typeof prior.focus === 'function') prior.focus({ preventScroll: true });
        }
        return successful;
    }
    function notice(message, kind) {
        if (typeof showToast === 'function') showToast(message, kind);
        else if (typeof showNotification === 'function') showNotification(message, kind);
    }
    window.copyLicenseKey = async function (elementId) {
        var key = document.getElementById(elementId);
        if (!key) return;
        var value = (key.textContent || '').trim();
        if (!value) return;
        var successful = false;
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function' && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(value);
                successful = true;
            } catch (error) { /* Fall through to selection based copy. */ }
        }
        if (!successful) {
            try { successful = fallbackCopy(value); }
            catch (error) { successful = false; }
        }
        notice(successful ? 'کلید لایسنس کپی شد' : 'کپی کلید انجام نشد؛ لطفاً دوباره تلاش کنید', successful ? 'success' : 'error');
    };
})();
