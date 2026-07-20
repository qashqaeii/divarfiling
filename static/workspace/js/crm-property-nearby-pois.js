(function (global) {
    'use strict';

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input?.value) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function faDigits(value) {
        return String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
    }

    function renderCard(item) {
        const card = document.createElement('article');
        card.className = 'crm-nearby-pois__card' + (item.found ? '' : ' is-empty');
        card.setAttribute('role', 'listitem');
        card.style.setProperty('--card-accent', item.color || 'var(--ws-primary)');

        const top = document.createElement('div');
        top.className = 'crm-nearby-pois__card-top';

        const iconWrap = document.createElement('span');
        iconWrap.className = 'crm-nearby-pois__card-icon';
        iconWrap.innerHTML = `<i class="fas ${item.icon || 'fa-location-dot'}" aria-hidden="true"></i>`;

        const label = document.createElement('span');
        label.className = 'crm-nearby-pois__card-label';
        label.textContent = item.label || '';

        top.appendChild(iconWrap);
        top.appendChild(label);

        card.appendChild(top);

        if (item.found) {
            const dist = document.createElement('div');
            dist.className = 'crm-nearby-pois__card-distance';
            dist.textContent = item.distance_label || '';
            card.appendChild(dist);

            const name = document.createElement('p');
            name.className = 'crm-nearby-pois__card-name';
            name.textContent = item.name || '';
            card.appendChild(name);
        } else {
            const empty = document.createElement('p');
            empty.className = 'crm-nearby-pois__card-empty';
            empty.textContent = item.empty_label || 'یافت نشد';
            card.appendChild(empty);
        }

        return card;
    }

    function initNearbyPoisPanel(root) {
        if (!root) return null;

        const fetchUrl = root.dataset.fetchUrl || '';
        let hasCoords = root.dataset.hasCoords === '1';
        const fetchBtn = root.querySelector('[data-nearby-fetch]');
        const btnLabel = root.querySelector('[data-nearby-btn-label]');
        const panel = root.querySelector('[data-nearby-panel]');
        const placeholder = root.querySelector('[data-nearby-placeholder]');
        const loading = root.querySelector('[data-nearby-loading]');
        const grid = root.querySelector('[data-nearby-grid]');
        const summary = root.querySelector('[data-nearby-summary]');
        const foundCountEl = root.querySelector('[data-nearby-found-count]');
        const radiusEl = root.querySelector('[data-nearby-radius]');
        const updatedEl = root.querySelector('[data-nearby-updated]');
        const errorEl = root.querySelector('[data-nearby-error]');
        const metaEl = root.querySelector('[data-nearby-meta]');

        let hasStored = root.dataset.hasStored === '1';
        let busy = false;

        function setError(message) {
            if (!errorEl) return;
            if (!message) {
                errorEl.hidden = true;
                errorEl.textContent = '';
                return;
            }
            errorEl.hidden = false;
            errorEl.innerHTML = `<i class="fas fa-circle-exclamation" aria-hidden="true"></i><span>${message}</span>`;
        }

        function setLoading(active) {
            busy = active;
            if (loading) loading.hidden = !active;
            if (fetchBtn) {
                fetchBtn.classList.toggle('is-loading', active);
                fetchBtn.disabled = active || !hasCoords;
            }
            if (active && placeholder) placeholder.hidden = true;
        }

        function updateButtonLabel() {
            if (btnLabel) {
                btnLabel.textContent = hasStored ? 'بروزرسانی' : 'نمایش امکانات';
            }
        }

        function renderPayload(data) {
            if (!grid) return;
            grid.innerHTML = '';
            const items = Array.isArray(data?.items) ? data.items : [];
            items.forEach((item) => grid.appendChild(renderCard(item)));

            if (summary) summary.hidden = false;
            if (foundCountEl) {
                const count = data.found_count != null ? data.found_count : items.filter((i) => i.found).length;
                foundCountEl.textContent = `${faDigits(count)} مورد یافت شد`;
            }
            if (radiusEl) {
                const radius = data.radius_m || 3000;
                const label = radius >= 1000
                    ? `شعاع ${faDigits(Math.round(radius / 1000))} کیلومتر`
                    : `شعاع ${faDigits(radius)} متر`;
                radiusEl.textContent = label;
            }
            if (updatedEl && data.fetched_at_label) {
                updatedEl.textContent = `آخرین بروزرسانی: ${data.fetched_at_label}`;
            }
            if (metaEl) {
                metaEl.hidden = false;
                metaEl.textContent = data.cached ? 'از حافظه ذخیره‌شده' : 'تازه دریافت شد';
            }

            if (panel) panel.hidden = false;
            if (placeholder) placeholder.hidden = true;
            hasStored = true;
            root.dataset.hasStored = '1';
            updateButtonLabel();
        }

        async function fetchNearby(refresh) {
            if (!fetchUrl || !hasCoords || busy) return;
            setError('');
            setLoading(true);
            try {
                const resp = await fetch(fetchUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        Accept: 'application/json',
                    },
                    body: JSON.stringify({ refresh: !!refresh }),
                    credentials: 'same-origin',
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'دریافت امکانات اطراف ناموفق بود.');
                }
                renderPayload(data);
                if (typeof global.showToast === 'function') {
                    const msg = data.cached
                        ? 'امکانات ذخیره‌شده نمایش داده شد.'
                        : 'امکانات اطراف با موفقیت دریافت و ذخیره شد.';
                    global.showToast(msg, 'success');
                }
            } catch (err) {
                setError(err.message || 'خطا در دریافت امکانات اطراف');
                if (typeof global.showToast === 'function') {
                    global.showToast(err.message || 'خطا در دریافت امکانات اطراف', 'error');
                }
                if (!hasStored && placeholder) placeholder.hidden = false;
            } finally {
                setLoading(false);
            }
        }

        fetchBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            fetchNearby(hasStored);
        });

        root.addEventListener('crm-property-location-saved', () => {
            hasCoords = true;
            root.dataset.hasCoords = '1';
            hasStored = false;
            root.dataset.hasStored = '0';
            if (fetchBtn) fetchBtn.disabled = false;
            if (panel) panel.hidden = true;
            if (placeholder) placeholder.hidden = false;
            if (grid) grid.innerHTML = '';
            if (summary) summary.hidden = true;
            if (metaEl) metaEl.hidden = true;
            updateButtonLabel();
            setError('');
        });

        const initialEl = document.getElementById('crm-nearby-pois-initial');
        if (initialEl) {
            try {
                const initial = JSON.parse(initialEl.textContent);
                renderPayload(initial);
            } catch (_) {
                /* ignore invalid bootstrap payload */
            }
        }

        updateButtonLabel();

        return { refresh: () => fetchNearby(true) };
    }

    function bootNearbyPois() {
        document.querySelectorAll('[data-nearby-pois-root]').forEach((root) => {
            initNearbyPoisPanel(root);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootNearbyPois);
    } else {
        bootNearbyPois();
    }

    global.initNearbyPoisPanel = initNearbyPoisPanel;
}(window));
