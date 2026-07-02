/* نقشه جزئیات ملک — میزکار و صفحه عمومی */
(function (global) {
    'use strict';

    const MAP_BASEMAP_STORAGE_KEY = 'ws-map-basemap';

    const MAP_BASEMAPS = {
        voyager: {
            label: 'شهری',
            hint: 'خیابان‌ها و محله‌ها',
            preview: 'voyager',
            create() {
                return L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                });
            },
        },
        standard: {
            label: 'استاندارد',
            hint: 'OpenStreetMap کلاسیک',
            preview: 'standard',
            create() {
                return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; OpenStreetMap',
                    maxZoom: 19,
                    subdomains: 'abc',
                    crossOrigin: true,
                });
            },
        },
        light: {
            label: 'روشن',
            hint: 'مینیمال و تمیز',
            preview: 'light',
            create() {
                return L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                });
            },
        },
        dark: {
            label: 'تاریک',
            hint: 'مناسب شب',
            preview: 'dark',
            create() {
                return L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                });
            },
        },
        satellite: {
            label: 'ماهواره',
            hint: 'تصویر واقعی',
            preview: 'satellite',
            create() {
                return L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                    attribution: '&copy; Esri',
                    maxZoom: 19,
                    crossOrigin: true,
                });
            },
        },
        hybrid: {
            label: 'ترکیبی',
            hint: 'ماهواره + برچسب',
            preview: 'hybrid',
            create() {
                const group = L.layerGroup();
                group.addLayer(L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                    maxZoom: 19,
                    crossOrigin: true,
                }));
                group.addLayer(L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
                    maxZoom: 19,
                    opacity: 0.88,
                    crossOrigin: true,
                }));
                return group;
            },
        },
        topo: {
            label: 'توپوگرافی',
            hint: 'ارتفاع و جغرافیا',
            preview: 'topo',
            create() {
                return L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; OSM &copy; OpenTopoMap',
                    maxZoom: 17,
                    subdomains: 'abc',
                    crossOrigin: true,
                });
            },
        },
    };

    /** @type {Map<string, { cleanup: () => void, map: L.Map }>} */
    const listingMapInstances = new Map();

    function wsEscapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function getDefaultBasemapId() {
        try {
            const stored = localStorage.getItem(MAP_BASEMAP_STORAGE_KEY);
            if (stored && MAP_BASEMAPS[stored]) return stored;
        } catch (e) { /* ignore */ }
        return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'voyager';
    }

    function isListingApproxLocation(options = {}) {
        if (options.accuracyKind === 'exact' || options.location_kind === 'exact') return false;
        if (options.accuracyKind === 'approx' || options.location_kind === 'approx') return true;
        const radius = Number(options.radiusM ?? options.location_radius_m);
        return radius > 0;
    }

    function estimateZoomForRadiusMeters(lat, radiusM, mapWidthPx) {
        const safeLat = Math.max(-85, Math.min(85, lat));
        const width = Math.max(Number(mapWidthPx) || 320, 160);
        const diameter = Math.max(Number(radiusM) * 2.6, 200);
        const metersPerPixel = diameter / width;
        const zoom = Math.log2((156543.03392 * Math.cos((safeLat * Math.PI) / 180)) / metersPerPixel);
        if (!Number.isFinite(zoom)) return 14;
        return Math.min(17, Math.max(11, Math.round(zoom)));
    }

    function boundsForRadiusMeters(lat, lng, radiusM) {
        const latRad = (lat * Math.PI) / 180;
        const deltaLat = radiusM / 111320;
        const deltaLng = radiusM / (111320 * Math.max(Math.abs(Math.cos(latRad)), 0.00001));
        return L.latLngBounds(
            [lat - deltaLat, lng - deltaLng],
            [lat + deltaLat, lng + deltaLng],
        );
    }

    function buildMapMarkerPopup(m) {
        const priceLine = m.price_label || (m.price ? Number(m.price).toLocaleString('fa-IR') : '—');
        const sellerClass = m.is_consultant ? 'consultant' : 'personal';
        const sellerLabel = m.seller_type || (m.is_consultant ? 'مشاور' : 'شخصی');
        const locParts = [m.city, m.neighborhood].filter(Boolean);
        const locLine = locParts.length ? locParts.join(' · ') : '';

        const chips = [];
        if (m.area_label || m.area) chips.push({ icon: 'fa-ruler-combined', value: m.area_label || `${m.area} متر` });
        if (m.rooms) chips.push({ icon: 'fa-door-open', value: `${m.rooms} خواب` });
        if (m.pps_label) chips.push({ icon: 'fa-chart-line', value: m.pps_label });
        if (m.deposit_label) chips.push({ icon: 'fa-hand-holding-usd', value: m.deposit_label.startsWith('ودیعه') ? m.deposit_label : `ودیعه ${m.deposit_label}` });
        if (m.rent_label) chips.push({ icon: 'fa-calendar-alt', value: m.rent_label.startsWith('اجاره') ? m.rent_label : `اجاره ${m.rent_label}` });

        const chipsHtml = chips.length
            ? `<div class="mk-map-popup-chips">${chips.map((c) =>
                `<span class="mk-map-popup-chip"><i class="fas ${c.icon}" aria-hidden="true"></i>${wsEscapeHtml(c.value)}</span>`
            ).join('')}</div>`
            : '';

        const thumbHtml = m.thumb
            ? `<div class="mk-map-popup-media"><img src="${wsEscapeHtml(m.thumb)}" alt="" loading="lazy"></div>`
            : '';

        const locAccIcon = m.location_kind === 'exact' ? 'fa-crosshairs' : 'fa-circle-notch';
        const locAccHtml = m.location_label
            ? `<span class="mk-map-popup-meta-item mk-map-popup-meta-item--loc-${wsEscapeHtml(m.location_kind || 'approx')}"><i class="fas ${locAccIcon}" aria-hidden="true"></i>${wsEscapeHtml(m.location_label)}</span>`
            : '';

        const verdictClass = { under: 'under', fair: 'fair', over: 'over' }[m.market_tier] || '';
        const verdictHtml = m.verdict && verdictClass
            ? `<span class="mk-map-popup-verdict mk-map-popup-verdict--${verdictClass}">${wsEscapeHtml(m.verdict)}</span>`
            : (m.verdict ? `<span class="mk-map-popup-verdict">${wsEscapeHtml(m.verdict)}</span>` : '');

        const metaHtml = (m.published && m.published !== '—') || locLine || m.location_label
            ? `<div class="mk-map-popup-meta">
                ${locAccHtml}
                ${locLine ? `<span class="mk-map-popup-meta-item"><i class="fas fa-map-marker-alt" aria-hidden="true"></i>${wsEscapeHtml(locLine)}</span>` : ''}
                ${m.published && m.published !== '—' ? `<span class="mk-map-popup-meta-item"><i class="far fa-clock" aria-hidden="true"></i>${wsEscapeHtml(m.published)}</span>` : ''}
            </div>`
            : '';

        const platformBtn = m.platform_url
            ? `<a href="${wsEscapeHtml(m.platform_url)}" class="mk-map-popup-btn mk-map-popup-btn--filing"><i class="fas fa-folder-open" aria-hidden="true"></i><span>مشاهده فایل</span></a>`
            : '';
        const divarBtn = m.link
            ? `<a href="${wsEscapeHtml(m.link)}" target="_blank" rel="noopener noreferrer" class="mk-map-popup-btn mk-map-popup-btn--divar"><i class="fas fa-external-link-alt" aria-hidden="true"></i><span>دیوار</span></a>`
            : '';

        return `
            <article class="mk-map-popup mk-map-popup--card mk-map-popup--${sellerClass}">
                ${thumbHtml}
                <div class="mk-map-popup-body">
                    <div class="mk-map-popup-head">
                        <span class="mk-map-popup-badge mk-map-popup-badge--${sellerClass}">${wsEscapeHtml(sellerLabel)}</span>
                        ${m.token ? `<span class="mk-map-popup-token" dir="ltr">#${wsEscapeHtml(m.token)}</span>` : ''}
                    </div>
                    <h3 class="mk-map-popup-title">${wsEscapeHtml(m.title || 'بدون عنوان')}</h3>
                    <div class="mk-map-popup-price-block">
                        <span class="mk-map-popup-price">${wsEscapeHtml(priceLine)}</span>
                        ${verdictHtml}
                    </div>
                    ${chipsHtml}
                    ${metaHtml}
                    ${(platformBtn || divarBtn) ? `<div class="mk-map-popup-actions">${divarBtn}${platformBtn}</div>` : ''}
                </div>
            </article>`;
    }

    function initListingDetailMap(options = {}) {
        const uiPrefix = options.uiPrefix || 'wsLd';
        const mapId = options.mapId || `${uiPrefix}LocationMap`;
        const el = document.getElementById(mapId);
        if (!el || !global.L) return null;

        listingMapInstances.get(mapId)?.cleanup?.();

        const marker = options.marker || {};
        const lat = Number(options.lat ?? marker.lat);
        const lng = Number(options.lng ?? marker.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;

        const locOpts = {
            accuracyKind: marker.location_kind || options.accuracyKind,
            radiusM: marker.location_radius_m || options.radiusM,
            location_kind: marker.location_kind,
            location_radius_m: marker.location_radius_m,
        };
        const isApprox = isListingApproxLocation(locOpts);
        const radiusM = Number(locOpts.radiusM) > 0 ? Number(locOpts.radiusM) : (isApprox ? 500 : 0);

        const map = L.map(el, { zoomControl: false, scrollWheelZoom: true });
        L.control.zoom({ position: 'bottomleft' }).addTo(map);
        L.control.scale({ imperial: false, metric: true, position: 'bottomright' }).addTo(map);

        let currentBasemapId = getDefaultBasemapId();
        let currentBasemapLayer = MAP_BASEMAPS[currentBasemapId].create();
        currentBasemapLayer.addTo(map);

        const basemapMenu = document.getElementById(`${uiPrefix}BasemapMenu`);
        const basemapToggle = document.getElementById(`${uiPrefix}BasemapToggle`);
        const basemapPreview = document.getElementById(`${uiPrefix}BasemapPreview`);
        const basemapLabel = document.getElementById(`${uiPrefix}BasemapLabel`);
        const basemapWrap = document.getElementById(`${uiPrefix}BasemapWrap`);
        const zoomBadge = document.getElementById(`${uiPrefix}MapZoomBadge`);
        const fitBtn = document.getElementById(`${uiPrefix}MapFitBtn`);
        const fullscreenBtn = document.getElementById(`${uiPrefix}MapFullscreenBtn`);
        const stage = document.getElementById(options.stageId || `${uiPrefix}LocationMapStage`);
        const abortController = new AbortController();
        const { signal } = abortController;
        let panelObserver = null;

        function cleanup() {
            abortController.abort();
            panelObserver?.disconnect();
            panelObserver = null;
            try { map.remove(); } catch (e) { /* ignore */ }
            if (global.wsLdDetailMap === map) global.wsLdDetailMap = null;
            listingMapInstances.delete(mapId);
        }

        function updateBasemapUI(activeId) {
            const cfg = MAP_BASEMAPS[activeId];
            basemapMenu?.querySelectorAll('[data-basemap]').forEach((btn) => {
                const on = btn.dataset.basemap === activeId;
                btn.classList.toggle('is-active', on);
                btn.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
            if (basemapPreview && cfg) {
                basemapPreview.className = `ws-ld-basemap-preview mk-map-basemap-preview mk-map-basemap-preview--${cfg.preview}`;
            }
            if (basemapLabel && cfg) basemapLabel.textContent = cfg.label;
            if (basemapToggle && cfg) basemapToggle.title = `نوع نقشه: ${cfg.label}`;
        }

        function setBasemapMenuOpen(open) {
            if (!basemapMenu) return;
            if (open) {
                basemapMenu.removeAttribute('hidden');
                basemapToggle?.setAttribute('aria-expanded', 'true');
                basemapWrap?.classList.add('is-open');
            } else {
                basemapMenu.setAttribute('hidden', '');
                basemapToggle?.setAttribute('aria-expanded', 'false');
                basemapWrap?.classList.remove('is-open');
            }
        }

        function setBasemap(id) {
            const cfg = MAP_BASEMAPS[id];
            if (!cfg || id === currentBasemapId) return;
            map.removeLayer(currentBasemapLayer);
            currentBasemapId = id;
            currentBasemapLayer = cfg.create();
            currentBasemapLayer.addTo(map);
            try { localStorage.setItem(MAP_BASEMAP_STORAGE_KEY, id); } catch (e) { /* ignore */ }
            updateBasemapUI(id);
            setBasemapMenuOpen(false);
        }

        if (basemapMenu) {
            basemapMenu.innerHTML = Object.entries(MAP_BASEMAPS).map(([id, cfg]) => `
                <button type="button" class="ws-ld-basemap-option${id === currentBasemapId ? ' is-active' : ''}"
                    data-basemap="${id}" role="menuitem" aria-pressed="${id === currentBasemapId ? 'true' : 'false'}"
                    title="${wsEscapeHtml(cfg.hint)}">
                    <span class="mk-map-basemap-preview mk-map-basemap-preview--${cfg.preview}" aria-hidden="true"></span>
                    <span class="ws-ld-basemap-option-text">
                        <strong>${wsEscapeHtml(cfg.label)}</strong>
                        <span>${wsEscapeHtml(cfg.hint)}</span>
                    </span>
                </button>
            `).join('');
            basemapMenu.querySelectorAll('[data-basemap]').forEach((btn) => {
                btn.addEventListener('click', () => setBasemap(btn.dataset.basemap), { signal });
            });
        }

        basemapToggle?.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!basemapMenu) return;
            setBasemapMenuOpen(basemapMenu.hasAttribute('hidden'));
        }, { signal });

        document.addEventListener('click', (e) => {
            if (!basemapMenu || basemapMenu.hasAttribute('hidden')) return;
            if (e.target.closest(`#${uiPrefix}BasemapWrap`)) return;
            setBasemapMenuOpen(false);
        }, { signal });

        updateBasemapUI(currentBasemapId);

        let locationLayer;
        if (isApprox && radiusM > 0) {
            locationLayer = L.circle([lat, lng], {
                radius: radiusM,
                color: '#7c3aed',
                fillColor: '#7c3aed',
                fillOpacity: 0.16,
                weight: 2.5,
                opacity: 0.85,
            }).addTo(map);
            L.circleMarker([lat, lng], {
                radius: 6,
                color: '#ffffff',
                weight: 2,
                fillColor: '#7c3aed',
                fillOpacity: 1,
            }).addTo(map);
        } else {
            locationLayer = L.circleMarker([lat, lng], {
                radius: 10,
                color: '#ffffff',
                weight: 2.5,
                fillColor: '#dc2626',
                fillOpacity: 1,
            }).addTo(map);
        }

        const popupMarker = { ...marker, lat, lng };
        const popupOpts = { className: 'mk-map-popup-shell', maxWidth: 300, minWidth: 260 };
        locationLayer.bindPopup(buildMapMarkerPopup(popupMarker), popupOpts);

        function mapHasLayout() {
            return el.clientWidth > 0 && el.clientHeight > 0;
        }

        function fitMapView(animate) {
            const anim = !!animate;
            if (isApprox && radiusM > 0) {
                const bounds = boundsForRadiusMeters(lat, lng, radiusM);
                if (mapHasLayout() && bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [44, 44], maxZoom: 17, animate: anim });
                } else {
                    map.setView([lat, lng], estimateZoomForRadiusMeters(lat, radiusM, el.clientWidth), { animate: anim });
                }
            } else {
                map.setView([lat, lng], options.zoom || 17, { animate: anim });
            }
            if (!Number.isFinite(map.getZoom())) {
                map.setView([lat, lng], options.zoom || 15, { animate: false });
            }
        }

        function updateZoomBadge() {
            if (!zoomBadge) return;
            const z = map.getZoom();
            zoomBadge.textContent = (z != null && !Number.isNaN(z))
                ? `زوم ${z.toLocaleString('fa-IR')}`
                : 'زوم —';
        }

        function maybeOpenPopup() {
            if (!mapHasLayout()) return;
            setTimeout(() => {
                try { locationLayer.openPopup(); } catch (e) { /* ignore */ }
            }, 280);
        }

        fitMapView(false);
        updateZoomBadge();
        map.on('zoomend', updateZoomBadge);

        fitBtn?.addEventListener('click', () => fitMapView(true), { signal });

        fullscreenBtn?.addEventListener('click', async () => {
            const target = stage || el;
            if (!target) return;
            try {
                if (!document.fullscreenElement) {
                    await target.requestFullscreen();
                    fullscreenBtn.querySelector('i')?.classList.replace('fa-expand', 'fa-compress');
                } else {
                    await document.exitFullscreen();
                    fullscreenBtn.querySelector('i')?.classList.replace('fa-compress', 'fa-expand');
                }
            } catch (e) { /* ignore */ }
        }, { signal });

        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement) {
                fullscreenBtn?.querySelector('i')?.classList.replace('fa-compress', 'fa-expand');
            }
            setTimeout(() => {
                map.invalidateSize();
                fitMapView(false);
                updateZoomBadge();
            }, 120);
        }, { signal });

        function refreshMapSize(openPopup) {
            setTimeout(() => {
                map.invalidateSize();
                fitMapView(false);
                updateZoomBadge();
                if (openPopup) maybeOpenPopup();
            }, 120);
        }

        const locationPanel = el.closest('[data-panel="مکان"]');
        if (locationPanel?.hidden) {
            panelObserver = new MutationObserver(() => {
                if (!locationPanel.hidden) {
                    panelObserver?.disconnect();
                    panelObserver = null;
                    refreshMapSize(true);
                }
            });
            panelObserver.observe(locationPanel, { attributes: true, attributeFilter: ['hidden'] });
        } else {
            maybeOpenPopup();
        }

        document.querySelector('.ws-ld-tabs [data-tab="مکان"]')
            ?.addEventListener('click', () => refreshMapSize(true), { signal });
        document.querySelector('[data-ld-map-jump]')
            ?.addEventListener('click', () => setTimeout(() => refreshMapSize(true), 180), { signal });

        refreshMapSize(false);
        listingMapInstances.set(mapId, { cleanup, map });
        global.wsLdDetailMap = map;
        return { map, destroy: cleanup };
    }

    function destroyListingDetailMap(mapId = 'wsLdLocationMap') {
        listingMapInstances.get(mapId)?.cleanup?.();
    }

    global.initListingDetailMap = initListingDetailMap;
    global.destroyListingDetailMap = destroyListingDetailMap;
    global.buildMapMarkerPopup = global.buildMapMarkerPopup || buildMapMarkerPopup;
}(window));
