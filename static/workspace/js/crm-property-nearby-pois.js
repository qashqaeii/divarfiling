(function (global) {
    'use strict';

    const STATUS_READY = 'ready';
    const STATUS_FAILED = 'failed';

    const NEARBY_LOAD_STEPS = [
        { id: 'loc', label: 'خواندن موقعیت ملک', icon: 'fa-map-pin' },
        { id: 'osm', label: 'جستجو در دادهٔ نقشه', icon: 'fa-magnifying-glass-location' },
        { id: 'dist', label: 'محاسبه فاصله و زمان پیاده', icon: 'fa-person-walking' },
        { id: 'group', label: 'دسته‌بندی امکانات و دسترسی‌ها', icon: 'fa-layer-group' },
    ];

    function renderNearbyLoadingMarkup() {
        const steps = NEARBY_LOAD_STEPS.map((step) => (
            `<li class="crm-nearby-pois__load-step" data-nearby-load-step="${step.id}">
                <span class="crm-nearby-pois__load-step-icon"><i class="fas ${step.icon}" aria-hidden="true"></i></span>
                <span class="crm-nearby-pois__load-step-label">${step.label}</span>
                <span class="crm-nearby-pois__load-step-status" aria-hidden="true"></span>
            </li>`
        )).join('');
        return `<div class="crm-nearby-pois__load-panel" role="status" aria-live="polite" aria-busy="true">
            <div class="crm-nearby-pois__load-orb" aria-hidden="true">
                <span class="crm-nearby-pois__load-ring"></span>
                <span class="crm-nearby-pois__load-core"><i class="fas fa-map-location-dot"></i></span>
            </div>
            <p class="crm-nearby-pois__load-title">در حال محاسبه امکانات و دسترسی‌ها</p>
            <p class="crm-nearby-pois__load-sub">جستجو در شعاع اطراف ملک و مرتب‌سازی نتایج…</p>
            <ol class="crm-nearby-pois__load-steps">${steps}</ol>
            <div class="crm-nearby-pois__load-bar" aria-hidden="true"><span class="crm-nearby-pois__load-bar-fill"></span></div>
        </div>`;
    }

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input?.value) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function faDigits(value) {
        return String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
    }

    function renderRow(item, { empty = false } = {}) {
        const row = document.createElement('div');
        row.className = 'crm-nearby-pois__row' + (item.found && !empty ? '' : ' is-empty');
        row.style.setProperty('--row-accent', item.color || 'var(--ws-primary)');

        const icon = document.createElement('span');
        icon.className = 'crm-nearby-pois__row-icon';
        icon.innerHTML = `<i class="fas ${item.icon || 'fa-location-dot'}" aria-hidden="true"></i>`;

        const main = document.createElement('div');
        main.className = 'crm-nearby-pois__row-main';

        const label = document.createElement('span');
        label.className = 'crm-nearby-pois__row-label';
        label.textContent = item.label || '';

        main.appendChild(label);

        if (item.found && item.name) {
            const name = document.createElement('span');
            name.className = 'crm-nearby-pois__row-name';
            name.textContent = item.name;
            main.appendChild(name);
        } else if (!item.found) {
            const name = document.createElement('span');
            name.className = 'crm-nearby-pois__row-name';
            name.textContent = item.empty_label || 'یافت نشد';
            main.appendChild(name);
        }

        const side = document.createElement('div');
        side.className = 'crm-nearby-pois__row-side';

        if (item.found) {
            const dist = document.createElement('span');
            dist.className = 'crm-nearby-pois__row-dist';
            dist.textContent = item.distance_label || '';
            side.appendChild(dist);
            if (item.walk_label) {
                const walk = document.createElement('span');
                walk.className = 'crm-nearby-pois__row-walk';
                walk.textContent = item.walk_label;
                side.appendChild(walk);
            }
        }

        row.appendChild(icon);
        row.appendChild(main);
        row.appendChild(side);
        return row;
    }

    function renderRows(items) {
        const wrap = document.createElement('div');
        wrap.className = 'crm-nearby-pois__rows';
        items.forEach((item) => wrap.appendChild(renderRow(item)));
        return wrap;
    }

    function renderGroup(group) {
        const found = (group.items || []).filter((i) => i.found);
        if (!found.length) return null;

        const section = document.createElement('section');
        section.className = 'crm-nearby-pois__group';
        section.setAttribute('role', 'listitem');

        const title = document.createElement('h3');
        title.className = 'crm-nearby-pois__group-title';
        const titleIcon = document.createElement('span');
        titleIcon.className = 'crm-nearby-pois__group-title-icon';
        titleIcon.setAttribute('aria-hidden', 'true');
        titleIcon.innerHTML = `<i class="fas ${group.icon || 'fa-layer-group'}"></i>`;
        const titleText = document.createElement('span');
        titleText.className = 'crm-nearby-pois__group-title-text';
        titleText.textContent = group.label || '';
        title.appendChild(titleIcon);
        title.appendChild(titleText);
        section.appendChild(title);
        section.appendChild(renderRows(found));
        return section;
    }

    function renderHighlights(items) {
        const wrap = document.createElement('div');
        wrap.className = 'crm-nearby-pois__highlights';
        items.forEach((item) => {
            const pill = document.createElement('span');
            pill.className = 'crm-nearby-pois__pill';
            pill.style.setProperty('--pill-accent', item.color || 'var(--ws-primary)');
            pill.innerHTML = `
                <i class="fas ${item.icon || 'fa-location-dot'}" aria-hidden="true"></i>
                <span>${item.label}</span>
                <span class="crm-nearby-pois__pill-dist">${item.distance_label || ''}</span>
            `;
            wrap.appendChild(pill);
        });
        return wrap;
    }

    function initNearbyPoisPanel(root) {
        if (!root) return null;

        const fetchUrl = root.dataset.fetchUrl || '';
        let hasCoords = root.dataset.hasCoords === '1';
        const fetchBtn = root.querySelector('[data-nearby-fetch]');
        const btnLabel = root.querySelector('[data-nearby-btn-label]');
        const body = root.querySelector('[data-nearby-body]');
        const placeholder = root.querySelector('[data-nearby-placeholder]');
        const loading = root.querySelector('[data-nearby-loading]');
        const stats = root.querySelector('[data-nearby-stats]');
        const highlightsHost = root.querySelector('[data-nearby-highlights]');
        const groupsHost = root.querySelector('[data-nearby-groups]');
        const missingHost = root.querySelector('[data-nearby-missing]');
        const toggleMissing = root.querySelector('[data-nearby-toggle-missing]');
        const missingLabel = root.querySelector('[data-nearby-missing-label]');
        const foundCountEl = root.querySelector('[data-nearby-found-count]');
        const radiusEl = root.querySelector('[data-nearby-radius]');
        const updatedEl = root.querySelector('[data-nearby-updated]');
        const errorEl = root.querySelector('[data-nearby-error]');
        const headerSub = root.querySelector('[data-nearby-header-sub]');
        const approxNote = root.querySelector('[data-nearby-approx-note]');
        const openMapBtn = root.querySelector('[data-open-property-map]');

        let hasStored = root.dataset.hasStored === '1';
        let locationPrecision = root.dataset.locationPrecision || 'none';
        let busy = false;
        let nearbyLoadTimer = null;

        function stopNearbyLoadAnimation() {
            if (nearbyLoadTimer) {
                clearInterval(nearbyLoadTimer);
                nearbyLoadTimer = null;
            }
            root.classList.remove('is-nearby-loading');
            loading?.querySelectorAll('[data-nearby-load-step]').forEach((step) => {
                step.classList.remove('is-active', 'is-done');
            });
        }

        function startNearbyLoadAnimation() {
            stopNearbyLoadAnimation();
            root.classList.add('is-nearby-loading');
            const steps = loading?.querySelectorAll('[data-nearby-load-step]');
            if (!steps?.length) return;
            let index = 0;
            const tick = () => {
                steps.forEach((el, i) => {
                    el.classList.toggle('is-active', i === index);
                    el.classList.toggle('is-done', i < index);
                });
                index = (index + 1) % NEARBY_LOAD_STEPS.length;
            };
            tick();
            nearbyLoadTimer = setInterval(tick, 1300);
        }

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
            if (loading) {
                if (active) {
                    loading.innerHTML = renderNearbyLoadingMarkup();
                    loading.hidden = false;
                    startNearbyLoadAnimation();
                } else {
                    stopNearbyLoadAnimation();
                    loading.hidden = true;
                }
            }
            if (fetchBtn) {
                fetchBtn.classList.toggle('is-loading', active);
                fetchBtn.disabled = active || !hasCoords;
            }
            if (active && placeholder) placeholder.hidden = true;
            if (active && body) body.hidden = true;
            if (active && stats) stats.hidden = true;
        }

        function updateButtonLabel() {
            if (btnLabel) btnLabel.textContent = hasStored ? 'بروزرسانی' : 'محاسبه';
        }

        function updateHeaderState(data) {
            const nextPrecision = data?.location_precision || locationPrecision;
            locationPrecision = nextPrecision;
            root.dataset.locationPrecision = locationPrecision;

            if (headerSub) {
                if (data?.status === STATUS_FAILED) {
                    headerSub.textContent = 'محاسبه دسترسی‌ها انجام نشد';
                } else if (hasStored && data) {
                    const found = data.found_count != null
                        ? data.found_count
                        : (data.items || []).filter((i) => i.found).length;
                    const radius = data.radius_m || 3000;
                    const radiusLabel = radius >= 1000
                        ? `شعاع ${faDigits(Math.round(radius / 1000))} کیلومتر`
                        : `شعاع ${faDigits(radius)} متر`;
                    const updated = data.fetched_at_label ? ` · به‌روزرسانی ${data.fetched_at_label}` : '';
                    headerSub.innerHTML = `<strong>${faDigits(found)} مکان نزدیک</strong> · ${radiusLabel}${updated}`;
                } else if (!hasCoords) {
                    headerSub.textContent = 'برای محاسبه دسترسی‌ها، موقعیت ملک را روی نقشه مشخص کنید';
                } else if (!hasStored) {
                    headerSub.textContent = root.dataset.radiusHint || 'برای دریافت دسترسی‌ها دکمه «محاسبه» را بزنید';
                }
            }

            if (approxNote) {
                approxNote.hidden = !(hasStored && locationPrecision === 'approximate');
            }
        }

        function renderPayload(data) {
            const groups = Array.isArray(data?.groups) ? data.groups : [];
            const highlights = Array.isArray(data?.highlights) ? data.highlights : [];
            const allItems = Array.isArray(data?.items) ? data.items : [];
            const missing = allItems.filter((i) => !i.found);

            if (groupsHost) {
                groupsHost.innerHTML = '';
                groups.forEach((group) => {
                    const el = renderGroup(group);
                    if (el) groupsHost.appendChild(el);
                });
            }

            if (highlightsHost) {
                highlightsHost.innerHTML = '';
                if (highlights.length) {
                    highlightsHost.appendChild(renderHighlights(highlights));
                    highlightsHost.hidden = false;
                } else {
                    highlightsHost.hidden = true;
                }
            }

            if (missingHost) {
                missingHost.innerHTML = '';
                if (missing.length) {
                    missingHost.appendChild(renderRows(missing));
                }
            }

            if (toggleMissing) {
                if (missing.length) {
                    toggleMissing.hidden = false;
                    if (missingLabel) {
                        missingLabel.textContent = `${faDigits(missing.length)} مورد یافت‌نشده`;
                    }
                    toggleMissing.classList.remove('is-open');
                    if (missingHost) missingHost.hidden = true;
                } else {
                    toggleMissing.hidden = true;
                }
            }

            if (stats) stats.hidden = false;
            if (foundCountEl) {
                const found = data.found_count != null
                    ? data.found_count
                    : allItems.filter((i) => i.found).length;
                const total = data.total_count != null ? data.total_count : allItems.length;
                foundCountEl.textContent = `${faDigits(found)} از ${faDigits(total)} مورد`;
            }
            if (radiusEl) {
                const radius = data.radius_m || 3000;
                radiusEl.textContent = radius >= 1000
                    ? `شعاع ${faDigits(Math.round(radius / 1000))} کیلومتر`
                    : `شعاع ${faDigits(radius)} متر`;
            }
            if (updatedEl && data.fetched_at_label) {
                updatedEl.textContent = data.fetched_at_label;
            }

            if (body) body.hidden = false;
            if (placeholder) placeholder.hidden = true;
            if (loading) {
                stopNearbyLoadAnimation();
                loading.hidden = true;
            }
            hasStored = true;
            root.dataset.hasStored = '1';
            root.dataset.status = STATUS_READY;
            updateButtonLabel();
            updateHeaderState(data);
            setError('');
        }

        function resetForNewLocation() {
            hasStored = false;
            root.dataset.hasStored = '0';
            root.dataset.status = '';
            if (body) body.hidden = true;
            if (stats) stats.hidden = true;
            if (placeholder) placeholder.hidden = false;
            if (loading) {
                stopNearbyLoadAnimation();
                loading.hidden = true;
            }
            if (groupsHost) groupsHost.innerHTML = '';
            if (highlightsHost) {
                highlightsHost.innerHTML = '';
                highlightsHost.hidden = true;
            }
            if (missingHost) missingHost.innerHTML = '';
            if (toggleMissing) toggleMissing.hidden = true;
            updateButtonLabel();
            updateHeaderState({});
            setError('');
        }

        toggleMissing?.addEventListener('click', () => {
            if (!missingHost) return;
            const open = missingHost.hidden;
            missingHost.hidden = !open;
            toggleMissing.classList.toggle('is-open', open);
        });

        openMapBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            const mapRoot = document.querySelector('[data-crm-property-map]');
            mapRoot?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });

        async function postNearby(body) {
            const resp = await fetch(fetchUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    Accept: 'application/json',
                },
                body: JSON.stringify(body),
                credentials: 'same-origin',
            });
            const data = await resp.json().catch(() => ({}));
            return { resp, data };
        }

        async function fetchOverpassFromBrowser(fallback) {
            const urls = Array.isArray(fallback?.urls) ? fallback.urls : [];
            const query = fallback?.query || '';
            if (!query || !urls.length) {
                throw new Error('سرویس نقشه در دسترس نیست.');
            }
            let lastMessage = '';
            for (const url of urls) {
                const ctrl = new AbortController();
                const timer = window.setTimeout(() => ctrl.abort(), 40000);
                try {
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        },
                        body: new URLSearchParams({ data: query }),
                        signal: ctrl.signal,
                    });
                    if (!resp.ok) {
                        lastMessage = `HTTP ${resp.status}`;
                        continue;
                    }
                    const payload = await resp.json();
                    if (Array.isArray(payload?.elements)) {
                        return payload.elements;
                    }
                } catch (err) {
                    lastMessage = err?.name === 'AbortError' ? 'timeout' : (err?.message || 'network');
                } finally {
                    window.clearTimeout(timer);
                }
            }
            throw new Error(
                lastMessage
                    ? 'سرویس نقشه از این شبکه در دسترس نیست. اتصال یا VPN را بررسی کنید و دوباره تلاش کنید.'
                    : 'سرویس نقشه در دسترس نیست.',
            );
        }

        async function fetchNearby(refresh) {
            if (!fetchUrl || !hasCoords || busy) return;
            setError('');
            setLoading(true);
            try {
                let { resp, data } = await postNearby({ refresh: !!refresh });
                if ((!resp.ok || !data.ok) && data.fallback) {
                    const elements = await fetchOverpassFromBrowser(data.fallback);
                    ({ resp, data } = await postNearby({
                        refresh: true,
                        elements,
                    }));
                }
                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || data.error_message || 'دریافت امکانات و دسترسی‌ها ناموفق بود.');
                }
                renderPayload(data);
                if (typeof global.showToast === 'function' && !data.cached) {
                    global.showToast('امکانات و دسترسی‌ها ذخیره شد.', 'success');
                }
            } catch (err) {
                setError(err.message || 'خطا در دریافت امکانات و دسترسی‌ها');
                if (typeof global.showToast === 'function') {
                    global.showToast(err.message || 'خطا در دریافت امکانات و دسترسی‌ها', 'error');
                }
                if (!hasStored && placeholder) placeholder.hidden = false;
                updateHeaderState({ status: STATUS_FAILED });
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
            if (fetchBtn) fetchBtn.disabled = false;
            resetForNewLocation();
        });

        const initialEl = document.getElementById('crm-nearby-pois-initial');
        if (initialEl) {
            try {
                renderPayload(JSON.parse(initialEl.textContent));
            } catch (_) {
                /* ignore */
            }
        } else {
            updateHeaderState({});
        }

        updateButtonLabel();
        return { refresh: () => fetchNearby(true) };
    }

    function bootNearbyPois() {
        document.querySelectorAll('[data-nearby-pois-root]').forEach(initNearbyPoisPanel);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootNearbyPois);
    } else {
        bootNearbyPois();
    }

    global.initNearbyPoisPanel = initNearbyPoisPanel;
}(window));
