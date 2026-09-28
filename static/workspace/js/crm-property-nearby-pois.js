(function (global) {
    'use strict';

    const STATUS_PENDING = 'pending';
    const STATUS_READY = 'ready';
    const STATUS_FAILED = 'failed';

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
        title.textContent = group.label || '';
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
        let status = root.dataset.status || '';
        let locationPrecision = root.dataset.locationPrecision || 'none';
        let busy = false;
        let pollTimer = null;
        let pollAttempts = 0;
        const POLL_MAX_ATTEMPTS = 40;

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
            if (active && body) body.hidden = true;
            if (active && stats) stats.hidden = true;
        }

        function updateButtonLabel() {
            if (btnLabel) btnLabel.textContent = hasStored ? 'بروزرسانی' : 'محاسبه';
        }

        function updateHeaderState(data) {
            const nextStatus = data?.status || status;
            const nextPrecision = data?.location_precision || locationPrecision;
            status = nextStatus;
            locationPrecision = nextPrecision;
            root.dataset.status = status;
            root.dataset.locationPrecision = locationPrecision;

            if (headerSub) {
                if (status === STATUS_PENDING) {
                    headerSub.innerHTML = '<span class="crm-nearby-pois__sub-pending">⏳ در حال بررسی موقعیت‌های اطراف ملک…</span>';
                } else if (status === STATUS_FAILED) {
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
                }
            }

            if (approxNote) {
                approxNote.hidden = !(hasStored && locationPrecision === 'approximate');
            }

            if (loading) {
                loading.hidden = status !== STATUS_PENDING;
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
            if (loading) loading.hidden = true;
            hasStored = true;
            root.dataset.hasStored = '1';
            status = data.status || STATUS_READY;
            updateButtonLabel();
            updateHeaderState(data);
            setError('');
            stopPolling();
        }

        function stopPolling() {
            if (pollTimer) {
                window.clearInterval(pollTimer);
                pollTimer = null;
            }
        }

        function showPendingState() {
            status = STATUS_PENDING;
            hasStored = false;
            root.dataset.hasStored = '0';
            root.dataset.status = STATUS_PENDING;
            updateHeaderState({ status: STATUS_PENDING });
            setError('');
            if (body) body.hidden = true;
            if (stats) stats.hidden = true;
            if (placeholder) placeholder.hidden = true;
            if (loading) loading.hidden = false;
            updateButtonLabel();
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

        async function getStatus() {
            const resp = await fetch(fetchUrl, {
                method: 'GET',
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            const data = await resp.json().catch(() => ({}));
            return { resp, data };
        }

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

        async function pollUntilReady() {
            if (!fetchUrl || !hasCoords) return;
            stopPolling();
            pollAttempts = 0;
            pollTimer = window.setInterval(async () => {
                pollAttempts += 1;
                try {
                    const { resp, data } = await getStatus();
                    if (!resp.ok || !data.ok) {
                        if (pollAttempts >= POLL_MAX_ATTEMPTS) {
                            stopPolling();
                            setError('دریافت وضعیت محاسبه ممکن نشد. دکمه «بروزرسانی» را بزنید.');
                            if (loading) loading.hidden = true;
                            if (fetchBtn) fetchBtn.disabled = !hasCoords;
                        }
                        return;
                    }
                    if (data.status === STATUS_READY && Array.isArray(data.items)) {
                        renderPayload(data);
                    } else if (data.status === STATUS_FAILED) {
                        if (data.fallback) {
                            try {
                                const elements = await fetchOverpassFromBrowser(data.fallback);
                                const posted = await postNearby({ refresh: true, elements });
                                if (posted.resp.ok && posted.data.ok && posted.data.status !== STATUS_PENDING) {
                                    renderPayload(posted.data);
                                    return;
                                }
                            } catch (_) {
                                /* fall through to error UI */
                            }
                        }
                        stopPolling();
                        status = STATUS_FAILED;
                        updateHeaderState(data);
                        setError(data.error_message || 'محاسبه دسترسی‌ها انجام نشد.');
                        if (loading) loading.hidden = true;
                        if (fetchBtn) fetchBtn.disabled = !hasCoords;
                    } else if (
                        data.status === STATUS_PENDING
                        && pollAttempts >= POLL_MAX_ATTEMPTS
                    ) {
                        stopPolling();
                        status = STATUS_FAILED;
                        updateHeaderState(data);
                        setError(
                            'محاسبه بیش از حد طول کشید. دکمه «بروزرسانی» را بزنید یا اتصال اینترنت را بررسی کنید.',
                        );
                        if (loading) loading.hidden = true;
                        if (fetchBtn) fetchBtn.disabled = !hasCoords;
                    }
                } catch (_) {
                    /* ignore transient poll errors */
                }
            }, 2500);
        }

        async function fetchNearby(refresh) {
            if (!fetchUrl || !hasCoords || busy) return;
            setError('');
            setLoading(true);
            try {
                let { resp, data } = await postNearby({ refresh: !!refresh });
                if (resp.ok && data.ok && data.status === STATUS_PENDING) {
                    showPendingState();
                    pollUntilReady();
                    return;
                }
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
                if (data.status === STATUS_PENDING) {
                    showPendingState();
                    pollUntilReady();
                    return;
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

        root.addEventListener('crm-property-location-saved', (event) => {
            hasCoords = true;
            root.dataset.hasCoords = '1';
            hasStored = false;
            root.dataset.hasStored = '0';
            if (fetchBtn) fetchBtn.disabled = false;
            if (body) body.hidden = true;
            if (stats) stats.hidden = true;
            if (groupsHost) groupsHost.innerHTML = '';
            if (highlightsHost) {
                highlightsHost.innerHTML = '';
                highlightsHost.hidden = true;
            }
            if (missingHost) missingHost.innerHTML = '';
            if (toggleMissing) toggleMissing.hidden = true;
            updateButtonLabel();
            setError('');
            if (event.detail?.accessibility_status === STATUS_PENDING || !event.detail?.accessibility_status) {
                showPendingState();
                pollUntilReady();
            }
        });

        const initialEl = document.getElementById('crm-nearby-pois-initial');
        if (initialEl) {
            try {
                renderPayload(JSON.parse(initialEl.textContent));
            } catch (_) {
                /* ignore */
            }
        } else if (status === STATUS_PENDING) {
            showPendingState();
            pollUntilReady();
        } else {
            updateHeaderState({ status, location_precision: locationPrecision });
        }

        updateButtonLabel();
        return { refresh: () => fetchNearby(true), pollUntilReady };
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
