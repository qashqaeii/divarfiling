/**
 * ابزار دسترسی‌های اطراف — /workspace/tools/
 * نقشه Leaflet + همان engine nearby_pois (Overpass/OSM)
 */
(function (global) {
    'use strict';

    const DEFAULT_CENTER = { lat: 35.6892, lng: 51.3890, zoom: 12 };
    const DEFAULT_RADIUS = 1000;

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input?.value) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function faDigits(value) {
        return String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
    }

    function fmtCoord(n) {
        return Number(n).toFixed(6);
    }

    function createLocationIcon(L) {
        return L.divIcon({
            className: 'ws-nearby-access-pin',
            html: '<span class="ws-nearby-access-pin__dot" aria-hidden="true"></span>',
            iconSize: [32, 32],
            iconAnchor: [16, 32],
        });
    }

    function createPoiIcon(L, marker) {
        const color = marker.color || '#6366f1';
        const icon = marker.icon || 'fa-location-dot';
        return L.divIcon({
            className: 'ws-nearby-access-poi',
            html: `<span class="ws-nearby-access-poi__dot" style="--poi-color:${color}"><i class="fas ${icon}" aria-hidden="true"></i></span>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11],
        });
    }

    function copyPlainText(text) {
        if (!text) return Promise.reject(new Error('متن خالی است'));
        if (navigator.clipboard?.writeText) {
            return navigator.clipboard.writeText(text);
        }
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            return Promise.resolve();
        } finally {
            document.body.removeChild(ta);
        }
    }

    function initNearbyAccessTool(root) {
        if (!root || root.dataset.nearbyBound === '1') return;
        root.dataset.nearbyBound = '1';

        const apiUrl = root.dataset.apiUrl || '';
        const mapEl = document.getElementById('wsNearbyAccessMap');
        const mapShell = root.querySelector('[data-nearby-map-shell]');
        const mapHint = root.querySelector('[data-nearby-map-hint]');
        const mapLoading = root.querySelector('[data-nearby-map-loading]');
        const coordsEl = root.querySelector('[data-nearby-coords]');
        const coordChip = root.querySelector('[data-nearby-coord-chip]');
        const fetchBtn = root.querySelector('[data-nearby-fetch]');
        const fetchSpinner = root.querySelector('[data-nearby-fetch-spinner]');
        const placeholder = root.querySelector('[data-nearby-placeholder]');
        const loading = root.querySelector('[data-nearby-loading]');
        const errorEl = root.querySelector('[data-nearby-error]');
        const body = root.querySelector('[data-nearby-body]');
        const categoriesHost = root.querySelector('[data-nearby-categories]');
        const emptyWrap = root.querySelector('[data-nearby-empty-wrap]');
        const emptyHost = root.querySelector('[data-nearby-empty-cats]');
        const filtersHost = root.querySelector('[data-nearby-filters]');
        const radiusLabelEl = root.querySelector('[data-nearby-radius-label]');
        const statsHost = root.querySelector('[data-nearby-stats]');
        const statCatsEl = root.querySelector('[data-nearby-stat-cats]');
        const statPoisEl = root.querySelector('[data-nearby-stat-pois]');
        const disclaimerEl = root.querySelector('[data-nearby-disclaimer]');
        const copyReportBtn = root.querySelector('[data-nearby-copy-report]');
        const copyCustomerBtn = root.querySelector('[data-nearby-copy-customer]');
        const radiusBtns = root.querySelectorAll('[data-nearby-radius]');
        const stepEls = root.closest('.ws-tbx-panel')?.querySelectorAll('.ws-nearby-access__step');

        let map = null;
        let marker = null;
        let radiusCircle = null;
        let poiLayer = null;
        let clusterGroup = null;
        let lat = null;
        let lng = null;
        let radiusM = parseInt(root.dataset.defaultRadius, 10) || DEFAULT_RADIUS;
        let busy = false;
        let lastPayload = null;
        let activeFilter = 'all';
        let poiMarkers = [];

        function setStepProgress(stage) {
            if (!stepEls?.length) return;
            stepEls.forEach((el, idx) => {
                el.classList.toggle('is-active', idx <= stage);
            });
        }

        function setCoords(newLat, newLng) {
            lat = newLat;
            lng = newLng;
            const has = lat != null && lng != null;
            if (coordsEl) {
                coordsEl.textContent = has
                    ? `${fmtCoord(lat)} , ${fmtCoord(lng)}`
                    : '—';
            }
            if (coordChip) coordChip.classList.toggle('is-set', has);
            if (mapShell) mapShell.classList.toggle('has-location', has);
            if (fetchBtn) fetchBtn.disabled = !has || busy;
            if (has) setStepProgress(1);
            if (has && map && global.L) {
                updateMarkerAndCircle();
            }
        }

        function updateMarkerAndCircle() {
            const L = global.L;
            if (!map || !L || lat == null || lng == null) return;

            if (!marker) {
                marker = L.marker([lat, lng], {
                    draggable: true,
                    icon: createLocationIcon(L),
                    zIndexOffset: 1000,
                    title: 'موقعیت انتخابی',
                }).addTo(map);
                marker.on('dragend', () => {
                    const p = marker.getLatLng();
                    setCoords(p.lat, p.lng);
                    clearResults();
                });
            } else {
                marker.setLatLng([lat, lng]);
            }

            if (radiusCircle) map.removeLayer(radiusCircle);
            radiusCircle = L.circle([lat, lng], {
                radius: radiusM,
                color: '#059669',
                weight: 2,
                fillColor: '#10b981',
                fillOpacity: 0.1,
                interactive: false,
            }).addTo(map);
        }

        function fitToRadius() {
            if (!map || lat == null || lng == null) return;
            const bounds = radiusCircle?.getBounds();
            if (bounds) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
        }

        function initMap() {
            if (!mapEl || !global.L) return;
            const L = global.L;
            map = L.map(mapEl, {
                zoomControl: true,
                attributionControl: true,
                scrollWheelZoom: true,
            }).setView([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng], DEFAULT_CENTER.zoom);

            const tileLayer = global.CartoBasemap
                ? (global.CartoBasemap.createPreferredVoyagerLayer(L, {
                    attribution: '&copy; OSM &copy; CARTO',
                    subdomains: 'abcd',
                    maxZoom: 19,
                }, { retina: true })
                    || global.CartoBasemap.createOsmStandardLayer(L, { maxZoom: 19 }))
                : L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
                    attribution: '&copy; OSM &copy; OSM France',
                    subdomains: 'abc',
                    maxZoom: 19,
                });
            tileLayer.addTo(map);

            map.on('click', (e) => {
                setCoords(e.latlng.lat, e.latlng.lng);
                clearResults();
            });

            setTimeout(() => map.invalidateSize(), 80);
        }

        function ensureMap() {
            if (!mapEl) return;
            if (!global.L) return;
            if (!map) initMap();
            else setTimeout(() => map.invalidateSize(), 60);
        }

        function setRadius(newRadius) {
            radiusM = newRadius;
            radiusBtns.forEach((btn) => {
                btn.classList.toggle('is-active', parseInt(btn.dataset.nearbyRadius, 10) === radiusM);
            });
            if (lat != null && lng != null) {
                setStepProgress(1);
                updateMarkerAndCircle();
                fitToRadius();
            }
        }

        function clearResults() {
            lastPayload = null;
            if (body) body.hidden = true;
            if (placeholder) placeholder.hidden = false;
            if (errorEl) {
                errorEl.hidden = true;
                errorEl.textContent = '';
            }
            if (categoriesHost) categoriesHost.innerHTML = '';
            if (emptyHost) emptyHost.innerHTML = '';
            if (emptyWrap) emptyWrap.hidden = true;
            if (filtersHost) {
                filtersHost.innerHTML = '';
                filtersHost.hidden = true;
            }
            clearPoiMarkers();
        }

        function clearPoiMarkers() {
            poiMarkers = [];
            if (clusterGroup && map) {
                map.removeLayer(clusterGroup);
                clusterGroup = null;
            }
            if (poiLayer && map) {
                map.removeLayer(poiLayer);
                poiLayer = null;
            }
        }

        function setLoading(active) {
            busy = active;
            root.classList.toggle('is-busy', active);
            if (mapLoading) {
                mapLoading.hidden = !active;
                mapLoading.setAttribute('aria-busy', active ? 'true' : 'false');
            }
            if (loading) loading.hidden = !active;
            if (placeholder) placeholder.hidden = active || !!lastPayload;
            if (fetchBtn) {
                fetchBtn.disabled = active || lat == null || lng == null;
                fetchBtn.classList.toggle('is-loading', active);
            }
            if (fetchSpinner) fetchSpinner.hidden = !active;
            if (active && body) body.hidden = true;
            if (active) {
                setStepProgress(2);
            } else if (lastPayload) {
                setStepProgress(2);
            } else if (lat != null) {
                setStepProgress(1);
            } else {
                setStepProgress(0);
            }
        }

        function setError(message) {
            if (!errorEl) return;
            if (!message) {
                errorEl.hidden = true;
                errorEl.textContent = '';
                return;
            }
            errorEl.hidden = false;
            errorEl.textContent = message;
            if (placeholder) placeholder.hidden = true;
            if (body) body.hidden = true;
        }

        async function postNearby(requestBody) {
            const resp = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    Accept: 'application/json',
                },
                body: JSON.stringify(requestBody),
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

        function renderCategoryCard(cat) {
            const card = document.createElement('article');
            card.className = 'ws-nearby-access__cat';
            card.dataset.catKey = cat.key;
            card.style.setProperty('--cat-color', cat.color || '#6366f1');

            const head = document.createElement('div');
            head.className = 'ws-nearby-access__cat-head';
            head.innerHTML = `
                <span class="ws-nearby-access__cat-icon"><i class="fas ${cat.icon || 'fa-location-dot'}" aria-hidden="true"></i></span>
                <span class="ws-nearby-access__cat-title">${cat.label || ''}</span>
                <span class="ws-nearby-access__cat-count">${faDigits(cat.count || 0)}</span>
            `;
            card.appendChild(head);

            const nearest = Array.isArray(cat.nearest) ? cat.nearest : [];
            if (nearest.length) {
                const list = document.createElement('ul');
                list.className = 'ws-nearby-access__nearest';
                nearest.forEach((item, idx) => {
                    const li = document.createElement('li');
                    li.className = 'ws-nearby-access__nearest-item';
                    li.dataset.markerIndex = String(findMarkerIndex(cat.key, item.name, idx));
                    li.innerHTML = `
                        <span class="ws-nearby-access__nearest-name">${item.name || cat.label}</span>
                        <span class="ws-nearby-access__nearest-dist">${item.distance_label || ''}</span>
                    `;
                    li.addEventListener('click', () => focusMarker(li.dataset.markerIndex));
                    list.appendChild(li);
                });
                card.appendChild(list);
            }
            return card;
        }

        function findMarkerIndex(catKey, name, fallbackIdx) {
            const idx = poiMarkers.findIndex((m) => m.key === catKey && m.name === name);
            return idx >= 0 ? idx : fallbackIdx;
        }

        function focusMarker(indexStr) {
            const idx = parseInt(indexStr, 10);
            const entry = poiMarkers[idx];
            if (!entry || !map) return;
            map.setView([entry.lat, entry.lng], Math.max(map.getZoom(), 16), { animate: true });
            entry.layer.openPopup?.();
        }

        function renderFilters(categories) {
            if (!filtersHost) return;
            const withResults = categories.filter((c) => (c.count || 0) > 0);
            if (!withResults.length) {
                filtersHost.hidden = true;
                return;
            }
            filtersHost.innerHTML = '';
            filtersHost.hidden = false;

            const allBtn = document.createElement('button');
            allBtn.type = 'button';
            allBtn.className = 'ws-nearby-access__filter is-active';
            allBtn.textContent = 'همه';
            allBtn.dataset.filter = 'all';
            filtersHost.appendChild(allBtn);

            withResults.forEach((cat) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'ws-nearby-access__filter';
                btn.dataset.filter = cat.key;
                btn.innerHTML = `<i class="fas ${cat.icon || 'fa-circle'}" aria-hidden="true"></i> ${cat.label}`;
                filtersHost.appendChild(btn);
            });

            filtersHost.querySelectorAll('.ws-nearby-access__filter').forEach((btn) => {
                btn.addEventListener('click', () => {
                    activeFilter = btn.dataset.filter || 'all';
                    filtersHost.querySelectorAll('.ws-nearby-access__filter').forEach((b) => {
                        b.classList.toggle('is-active', b === btn);
                    });
                    applyMarkerFilter();
                });
            });
        }

        function applyMarkerFilter() {
            poiMarkers.forEach((entry) => {
                const show = activeFilter === 'all' || entry.key === activeFilter;
                const layer = entry.layer;
                if (!layer) return;
                if (clusterGroup) {
                    if (show && !clusterGroup.hasLayer(layer)) clusterGroup.addLayer(layer);
                    if (!show && clusterGroup.hasLayer(layer)) clusterGroup.removeLayer(layer);
                } else if (poiLayer) {
                    if (show && !poiLayer.hasLayer(layer)) poiLayer.addLayer(layer);
                    if (!show && poiLayer.hasLayer(layer)) poiLayer.removeLayer(layer);
                }
            });
        }

        function renderPoiMarkers(markers) {
            clearPoiMarkers();
            if (!map || !global.L || !Array.isArray(markers) || !markers.length) return;
            const L = global.L;
            const useCluster = global.L.markerClusterGroup;

            if (useCluster) {
                clusterGroup = L.markerClusterGroup({
                    maxClusterRadius: 40,
                    spiderfyOnMaxZoom: true,
                    showCoverageOnHover: false,
                    disableClusteringAtZoom: 17,
                });
            } else {
                poiLayer = L.layerGroup();
            }

            markers.forEach((m, idx) => {
                if (m.lat == null || m.lng == null) return;
                const layer = L.marker([m.lat, m.lng], {
                    icon: createPoiIcon(L, m),
                    title: m.name || m.label || '',
                });
                const popup = `<strong>${m.name || m.label || ''}</strong><br>${m.distance_label || ''}`;
                layer.bindPopup(popup);
                if (clusterGroup) clusterGroup.addLayer(layer);
                else poiLayer.addLayer(layer);
                poiMarkers.push({ ...m, layer, key: m.key });
            });

            if (clusterGroup) clusterGroup.addTo(map);
            else if (poiLayer) poiLayer.addTo(map);
        }

        function renderPayload(data) {
            lastPayload = data;
            const withResults = data.categories_with_results || [];
            const emptyCats = (data.categories || []).filter((c) => !(c.count > 0));

            if (radiusLabelEl) {
                radiusLabelEl.textContent = data.radius_label || '';
            }
            if (disclaimerEl) {
                disclaimerEl.textContent = data.disclaimer ? `(${data.disclaimer})` : '';
            }

            if (statsHost) {
                const hasStats = (data.categories_found || 0) > 0 || (data.total_pois || 0) > 0;
                statsHost.hidden = !hasStats;
                if (statCatsEl) statCatsEl.textContent = faDigits(data.categories_found || 0);
                if (statPoisEl) statPoisEl.textContent = faDigits(data.total_pois || 0);
            }

            if (categoriesHost) {
                categoriesHost.innerHTML = '';
                if (!withResults.length) {
                    categoriesHost.innerHTML = `
                        <div class="ws-nearby-access__no-results">
                            <p>در این محدوده دسترسی ثبت‌شده‌ای پیدا نشد.<br>شعاع جستجو را افزایش دهید.</p>
                        </div>`;
                } else {
                    withResults.forEach((cat) => {
                        categoriesHost.appendChild(renderCategoryCard(cat));
                    });
                }
            }

            if (emptyHost && emptyWrap) {
                emptyHost.innerHTML = '';
                if (emptyCats.length) {
                    emptyWrap.hidden = false;
                    emptyCats.forEach((cat) => {
                        const row = document.createElement('div');
                        row.className = 'ws-nearby-access__empty-row';
                        row.textContent = `${cat.label}: ۰`;
                        emptyHost.appendChild(row);
                    });
                } else {
                    emptyWrap.hidden = true;
                }
            }

            renderFilters(data.categories || []);
            renderPoiMarkers(data.markers || []);
            activeFilter = 'all';

            if (body) body.hidden = false;
            if (placeholder) placeholder.hidden = true;
            if (loading) loading.hidden = true;
            setStepProgress(2);
            fitToRadius();
        }

        async function runFetch() {
            if (!apiUrl || lat == null || lng == null || busy) return;
            setError('');
            clearResults();
            setLoading(true);
            try {
                let { resp, data } = await postNearby({
                    latitude: lat,
                    longitude: lng,
                    radius_m: radiusM,
                });
                if ((!resp.ok || !data.ok) && data.fallback) {
                    const elements = await fetchOverpassFromBrowser(data.fallback);
                    ({ resp, data } = await postNearby({
                        latitude: lat,
                        longitude: lng,
                        radius_m: radiusM,
                        elements,
                    }));
                }
                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'دریافت دسترسی‌های اطراف ناموفق بود.');
                }
                renderPayload(data);
            } catch (err) {
                setError(err.message || 'خطا در دریافت دسترسی‌های اطراف');
            } finally {
                setLoading(false);
            }
        }

        radiusBtns.forEach((btn) => {
            btn.addEventListener('click', () => {
                setRadius(parseInt(btn.dataset.nearbyRadius, 10));
            });
        });

        fetchBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            runFetch();
        });

        copyReportBtn?.addEventListener('click', async () => {
            const text = lastPayload?.report_copy || '';
            try {
                await copyPlainText(text);
                global.showToast?.('گزارش کپی شد.', 'success');
            } catch (_) {
                global.showToast?.('کپی ناموفق بود.', 'error');
            }
        });

        copyCustomerBtn?.addEventListener('click', async () => {
            const text = lastPayload?.customer_copy || '';
            try {
                await copyPlainText(text);
                global.showToast?.('متن معرفی کپی شد.', 'success');
            } catch (_) {
                global.showToast?.('کپی ناموفق بود.', 'error');
            }
        });

        setRadius(radiusM);
        setStepProgress(0);
        if (mapLoading) mapLoading.hidden = true;
        if (loading) loading.hidden = true;
        if (fetchSpinner) fetchSpinner.hidden = true;
        root.classList.remove('is-busy');

        global.wsNearbyAccessOnShow = ensureMap;
    }

    function boot() {
        const root = document.getElementById('wsNearbyAccess');
        if (root) initNearbyAccessTool(root);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
}(window));
