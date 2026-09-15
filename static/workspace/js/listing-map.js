/* نقشه جزئیات ملک — میزکار و صفحه عمومی */
(function (global) {
    'use strict';

    const MAP_BASEMAP_STORAGE_KEY = 'ws-map-basemap';

    function createCartoBasemapLayer(styleId, options, layerOpts) {
        if (global.CartoBasemap?.hasKey()) {
            return global.CartoBasemap.createCartoLayer(L, styleId, options, layerOpts);
        }
        if (global.CartoBasemap) {
            return global.CartoBasemap.createOsmStandardLayer(L, options);
        }
        return global.CartoBasemap?.createOsmStandardLayer(L, options)
            || L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
                attribution: options?.attribution || '&copy; OpenStreetMap &copy; OSM France',
                maxZoom: options?.maxZoom || 19,
                subdomains: 'abc',
                crossOrigin: true,
            });
    }

    const MAP_BASEMAPS = {
        voyager: {
            label: 'شهری',
            hint: 'خیابان‌ها و محله‌ها',
            preview: 'voyager',
            create() {
                return createCartoBasemapLayer('voyager', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                }, { retina: true });
            },
        },
        standard: {
            label: 'استاندارد',
            hint: 'OpenStreetMap کلاسیک',
            preview: 'standard',
            create() {
                return global.CartoBasemap.createOsmStandardLayer(L, {
                    maxZoom: 19,
                    crossOrigin: true,
                });
            },
        },
        light: {
            label: 'روشن',
            hint: 'مینیمال و تمیز',
            preview: 'light',
            create() {
                return createCartoBasemapLayer('light', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                }, { retina: true });
            },
        },
        dark: {
            label: 'تاریک',
            hint: 'مناسب شب',
            preview: 'dark',
            create() {
                return createCartoBasemapLayer('dark', {
                    attribution: '&copy; OSM &copy; CARTO',
                    maxZoom: 20,
                    subdomains: 'abcd',
                    crossOrigin: true,
                }, { retina: true });
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
        let preferred;
        try {
            const stored = localStorage.getItem(MAP_BASEMAP_STORAGE_KEY);
            if (stored && MAP_BASEMAPS[stored]) preferred = stored;
        } catch (e) { /* ignore */ }
        if (!preferred) {
            preferred = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'voyager';
        }
        return global.CartoBasemap?.resolveBasemapId(preferred) || preferred;
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

    function mapSellerKind(m) {
        const sig = String(m.advertiser_signal || '');
        const label = String(m.seller_type || '');
        if (sig === 'disguised_consultant' || m.is_disguised || label === 'مشاور پنهان') return 'disguised';
        if (sig === 'consultant' || m.is_consultant || label === 'مشاور') return 'consultant';
        if (sig === 'genuine_personal' || label === 'مالک واقعی' || label === 'مالک') return 'genuine';
        return 'personal';
    }

    function mapSellerLabel(m) {
        if (m.seller_type) return m.seller_type;
        const kind = mapSellerKind(m);
        if (kind === 'disguised') return 'مشاور پنهان';
        if (kind === 'consultant') return 'مشاور';
        if (kind === 'genuine') return 'مالک واقعی';
        return 'شخصی';
    }

    function buildMapMarkerPopup(m) {
        const priceLine = m.price_label || (m.price ? Number(m.price).toLocaleString('fa-IR') : '—');
        const sellerClass = mapSellerKind(m);
        const sellerLabel = mapSellerLabel(m);
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
        if (options.cartoBasemapKey && global.CartoBasemap) {
            global.CartoBasemap.setKey(options.cartoBasemapKey);
        }
        const uiPrefix = options.uiPrefix || 'wsLd';
        const mapId = options.mapId || `${uiPrefix}LocationMap`;
        const el = document.getElementById(mapId);
        if (!el || !global.L) return null;

        listingMapInstances.get(mapId)?.cleanup?.();

        const marker = options.marker || {};
        function parseCoord(value) {
            if (value == null || value === '') return NaN;
            const n = Number(value);
            return Number.isFinite(n) ? n : NaN;
        }
        const lat = parseCoord(options.lat ?? marker.lat);
        const lng = parseCoord(options.lng ?? marker.lng);
        const editable = !!options.editable;
        if ((!Number.isFinite(lat) || !Number.isFinite(lng)) && !editable) return null;

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
            if (basemapMenu?.classList.contains('is-ported') && basemapMenu._homeParent) {
                try {
                    if (basemapMenu._homeNext && basemapMenu._homeNext.parentNode === basemapMenu._homeParent) {
                        basemapMenu._homeParent.insertBefore(basemapMenu, basemapMenu._homeNext);
                    } else {
                        basemapMenu._homeParent.appendChild(basemapMenu);
                    }
                } catch (e) { /* ignore */ }
                basemapMenu.classList.remove('is-ported');
            }
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

        function positionBasemapMenu() {
            if (!basemapMenu || !basemapToggle || !basemapMenu.classList.contains('is-ported')) return;
            const rect = basemapToggle.getBoundingClientRect();
            const menuWidth = Math.max(basemapMenu.offsetWidth || 210, 210);
            const menuHeight = basemapMenu.scrollHeight || 280;
            const pad = 8;
            const vw = window.innerWidth;
            const vh = window.innerHeight;

            let left = rect.right - menuWidth;
            if (document.documentElement.dir === 'rtl' || getComputedStyle(document.documentElement).direction === 'rtl') {
                left = rect.left;
            }
            left = Math.min(Math.max(pad, left), vw - menuWidth - pad);

            const spaceBelow = vh - rect.bottom - pad;
            const spaceAbove = rect.top - pad;
            let top;
            if (spaceBelow >= Math.min(menuHeight, 200) || spaceBelow >= spaceAbove) {
                top = rect.bottom + 6;
            } else {
                top = Math.max(pad, rect.top - menuHeight - 6);
            }
            if (top + Math.min(menuHeight, vh * 0.7) > vh - pad) {
                top = Math.max(pad, vh - Math.min(menuHeight, vh * 0.7) - pad);
            }

            basemapMenu.style.top = `${Math.round(top)}px`;
            basemapMenu.style.left = `${Math.round(left)}px`;
            basemapMenu.style.right = 'auto';
            basemapMenu.style.bottom = 'auto';
            basemapMenu.style.minWidth = `${Math.max(menuWidth, rect.width)}px`;
        }

        function setBasemapMenuOpen(open) {
            if (!basemapMenu) return;
            if (open) {
                if (!basemapMenu.classList.contains('is-ported')) {
                    basemapMenu._homeParent = basemapMenu.parentElement;
                    basemapMenu._homeNext = basemapMenu.nextSibling;
                    document.body.appendChild(basemapMenu);
                    basemapMenu.classList.add('is-ported');
                }
                basemapMenu.removeAttribute('hidden');
                basemapToggle?.setAttribute('aria-expanded', 'true');
                basemapWrap?.classList.add('is-open');
                positionBasemapMenu();
                const first = basemapMenu.querySelector('[data-basemap]');
                first?.focus?.();
            } else {
                basemapMenu.setAttribute('hidden', '');
                basemapToggle?.setAttribute('aria-expanded', 'false');
                basemapWrap?.classList.remove('is-open');
                if (basemapMenu.classList.contains('is-ported') && basemapMenu._homeParent) {
                    if (basemapMenu._homeNext && basemapMenu._homeNext.parentNode === basemapMenu._homeParent) {
                        basemapMenu._homeParent.insertBefore(basemapMenu, basemapMenu._homeNext);
                    } else {
                        basemapMenu._homeParent.appendChild(basemapMenu);
                    }
                    basemapMenu.classList.remove('is-ported');
                    basemapMenu.style.top = '';
                    basemapMenu.style.left = '';
                    basemapMenu.style.right = '';
                    basemapMenu.style.bottom = '';
                    basemapMenu.style.minWidth = '';
                }
            }
        }

        function setBasemap(id) {
            const cfg = MAP_BASEMAPS[id];
            if (!cfg || id === currentBasemapId) {
                setBasemapMenuOpen(false);
                return;
            }
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
            basemapMenu.addEventListener('keydown', (e) => {
                const options = Array.from(basemapMenu.querySelectorAll('[data-basemap]'));
                const current = document.activeElement;
                const idx = options.indexOf(current);
                if (e.key === 'Escape') {
                    e.preventDefault();
                    setBasemapMenuOpen(false);
                    basemapToggle?.focus();
                    return;
                }
                if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
                    e.preventDefault();
                    options[(idx + 1) % options.length]?.focus();
                } else if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
                    e.preventDefault();
                    options[(idx - 1 + options.length) % options.length]?.focus();
                } else if (e.key === 'Home') {
                    e.preventDefault();
                    options[0]?.focus();
                } else if (e.key === 'End') {
                    e.preventDefault();
                    options[options.length - 1]?.focus();
                }
            }, { signal });
        }

        basemapToggle?.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!basemapMenu) return;
            setBasemapMenuOpen(basemapMenu.hasAttribute('hidden'));
        }, { signal });

        document.addEventListener('click', (e) => {
            if (!basemapMenu || basemapMenu.hasAttribute('hidden')) return;
            if (e.target.closest(`#${uiPrefix}BasemapWrap`) || e.target.closest(`#${uiPrefix}BasemapMenu`)) return;
            setBasemapMenuOpen(false);
        }, { signal });

        window.addEventListener('resize', () => {
            if (basemapMenu && !basemapMenu.hasAttribute('hidden')) positionBasemapMenu();
        }, { signal, passive: true });

        window.addEventListener('scroll', () => {
            if (basemapMenu && !basemapMenu.hasAttribute('hidden')) positionBasemapMenu();
        }, { signal, passive: true, capture: true });

        updateBasemapUI(currentBasemapId);

        const onDraftChange = typeof options.onDraftChange === 'function' ? options.onDraftChange : null;
        const defaultCenter = options.defaultCenter || { lat: 35.6892, lng: 51.3890, zoom: 11 };
        let committedLat = Number.isFinite(lat) ? lat : null;
        let committedLng = Number.isFinite(lng) ? lng : null;
        let draftLat = committedLat;
        let draftLng = committedLng;
        const emptyPlaceMode = editable && (committedLat == null || committedLng == null);

        const pinIcon = L.divIcon({
            className: 'ws-ld-map-pin',
            html: '<span class="ws-ld-map-pin-dot" aria-hidden="true"></span><span class="ws-ld-map-pin-pulse" aria-hidden="true"></span>',
            iconSize: [28, 28],
            iconAnchor: [14, 14],
        });
        const ghostIcon = L.divIcon({
            className: 'ws-ld-map-pin ws-ld-map-pin--ghost',
            html: '<span class="ws-ld-map-pin-dot" aria-hidden="true"></span>',
            iconSize: [22, 22],
            iconAnchor: [11, 11],
        });

        let locationLayer = null;
        let ghostLayer = null;
        let locationCircle = null;

        function clearLocationLayers() {
            if (locationLayer) {
                try { map.removeLayer(locationLayer); } catch (e) { /* ignore */ }
                locationLayer = null;
            }
            if (locationCircle) {
                try { map.removeLayer(locationCircle); } catch (e) { /* ignore */ }
                locationCircle = null;
            }
            if (ghostLayer) {
                try { map.removeLayer(ghostLayer); } catch (e) { /* ignore */ }
                ghostLayer = null;
            }
        }

        function coordsEqual(aLat, aLng, bLat, bLng) {
            if (aLat == null || aLng == null || bLat == null || bLng == null) return false;
            return Math.abs(aLat - bLat) < 1e-8 && Math.abs(aLng - bLng) < 1e-8;
        }

        function updateGhost() {
            if (!editable) return;
            const showGhost = committedLat != null && committedLng != null
                && draftLat != null && draftLng != null
                && !coordsEqual(committedLat, committedLng, draftLat, draftLng);
            if (!showGhost) {
                if (ghostLayer) {
                    try { map.removeLayer(ghostLayer); } catch (e) { /* ignore */ }
                    ghostLayer = null;
                }
                return;
            }
            if (!ghostLayer) {
                ghostLayer = L.marker([committedLat, committedLng], {
                    icon: ghostIcon,
                    interactive: false,
                    keyboard: false,
                }).addTo(map);
            } else {
                ghostLayer.setLatLng([committedLat, committedLng]);
            }
        }

        function bindPopupAt(layer, atLat, atLng) {
            if (!layer || atLat == null || atLng == null) return;
            const popupMarker = { ...marker, lat: atLat, lng: atLng };
            const popupOpts = { className: 'mk-map-popup-shell', maxWidth: 300, minWidth: 260 };
            layer.bindPopup(buildMapMarkerPopup(popupMarker), popupOpts);
        }

        function placeEditableMarker(atLat, atLng, { openPopup = false } = {}) {
            clearLocationLayers();
            locationLayer = L.marker([atLat, atLng], {
                icon: pinIcon,
                draggable: true,
                autoPan: true,
                riseOnHover: true,
            }).addTo(map);
            bindPopupAt(locationLayer, atLat, atLng);
            locationLayer.on('dragstart', () => {
                locationLayer.closePopup();
                el.classList.add('is-dragging-pin');
            });
            locationLayer.on('dragend', () => {
                el.classList.remove('is-dragging-pin');
                const pos = locationLayer.getLatLng();
                setDraft(pos.lat, pos.lng, { fromDrag: true });
            });
            if (openPopup) locationLayer.openPopup();
            updateGhost();
        }

        function placeReadonlyMarker(atLat, atLng) {
            clearLocationLayers();
            if (isApprox && radiusM > 0) {
                // فقط دایره تقریبی — بدون نقطه مرکز تا مختصات دقیق لو نرود
                locationCircle = L.circle([atLat, atLng], {
                    radius: radiusM,
                    color: '#7c3aed',
                    fillColor: '#7c3aed',
                    fillOpacity: 0.16,
                    weight: 2.5,
                    opacity: 0.85,
                }).addTo(map);
                locationLayer = locationCircle;
                bindPopupAt(locationCircle, atLat, atLng);
            } else {
                locationLayer = L.circleMarker([atLat, atLng], {
                    radius: 10,
                    color: '#ffffff',
                    weight: 2.5,
                    fillColor: '#dc2626',
                    fillOpacity: 1,
                }).addTo(map);
                bindPopupAt(locationLayer, atLat, atLng);
            }
        }

        function notifyDraft() {
            const dirty = !coordsEqual(committedLat, committedLng, draftLat, draftLng)
                || (committedLat == null && draftLat != null);
            el.classList.toggle('has-draft-location', dirty);
            el.classList.toggle('has-location', draftLat != null && draftLng != null);
            onDraftChange?.({
                lat: draftLat,
                lng: draftLng,
                committedLat,
                committedLng,
                dirty,
                isNew: committedLat == null || committedLng == null,
            });
        }

        function setDraft(nextLat, nextLng, meta = {}) {
            const nLat = Number(nextLat);
            const nLng = Number(nextLng);
            if (!Number.isFinite(nLat) || !Number.isFinite(nLng)) return;
            draftLat = nLat;
            draftLng = nLng;
            if (editable) {
                if (!locationLayer || !(locationLayer instanceof L.Marker)) {
                    placeEditableMarker(draftLat, draftLng);
                } else {
                    locationLayer.setLatLng([draftLat, draftLng]);
                    bindPopupAt(locationLayer, draftLat, draftLng);
                    updateGhost();
                }
            } else {
                placeReadonlyMarker(draftLat, draftLng);
            }
            if (!meta.skipNotify) notifyDraft();
        }

        function commitDraft() {
            if (draftLat == null || draftLng == null) return null;
            committedLat = draftLat;
            committedLng = draftLng;
            marker.lat = committedLat;
            marker.lng = committedLng;
            updateGhost();
            notifyDraft();
            return { lat: committedLat, lng: committedLng };
        }

        function revertDraft() {
            draftLat = committedLat;
            draftLng = committedLng;
            if (draftLat == null || draftLng == null) {
                clearLocationLayers();
                el.classList.remove('has-location', 'has-draft-location');
                map.setView(
                    [defaultCenter.lat, defaultCenter.lng],
                    defaultCenter.zoom || 11,
                    { animate: true },
                );
                notifyDraft();
                return;
            }
            setDraft(draftLat, draftLng);
            fitMapView(true);
        }

        function getDraft() {
            return draftLat != null && draftLng != null
                ? { lat: draftLat, lng: draftLng }
                : null;
        }

        if (editable && emptyPlaceMode) {
            map.setView(
                [defaultCenter.lat, defaultCenter.lng],
                defaultCenter.zoom || 11,
                { animate: false },
            );
            el.classList.add('is-empty-place');
            const onMapClickEmpty = (e) => {
                el.classList.remove('is-empty-place');
                setDraft(e.latlng.lat, e.latlng.lng);
                map.setView(e.latlng, Math.max(map.getZoom(), 16), { animate: true });
            };
            map.on('click', onMapClickEmpty);
            abortController.signal.addEventListener('abort', () => {
                try { map.off('click', onMapClickEmpty); } catch (e) { /* ignore */ }
            });
        } else if (editable) {
            placeEditableMarker(committedLat, committedLng);
            const onMapClickEdit = (e) => {
                setDraft(e.latlng.lat, e.latlng.lng);
            };
            map.on('click', onMapClickEdit);
            abortController.signal.addEventListener('abort', () => {
                try { map.off('click', onMapClickEdit); } catch (e) { /* ignore */ }
            });
        } else {
            placeReadonlyMarker(committedLat, committedLng);
        }

        function mapHasLayout() {
            return el.clientWidth > 0 && el.clientHeight > 0;
        }

        function fitMapView(animate) {
            const anim = !!animate;
            const viewLat = draftLat != null ? draftLat : committedLat;
            const viewLng = draftLng != null ? draftLng : committedLng;
            if (viewLat == null || viewLng == null) {
                map.setView(
                    [defaultCenter.lat, defaultCenter.lng],
                    defaultCenter.zoom || 11,
                    { animate: anim },
                );
                return;
            }
            if (!editable && isApprox && radiusM > 0) {
                const bounds = boundsForRadiusMeters(viewLat, viewLng, radiusM);
                if (mapHasLayout() && bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [44, 44], maxZoom: 17, animate: anim });
                } else {
                    map.setView([viewLat, viewLng], estimateZoomForRadiusMeters(viewLat, radiusM, el.clientWidth), { animate: anim });
                }
            } else {
                map.setView([viewLat, viewLng], options.zoom || 17, { animate: anim });
            }
            if (!Number.isFinite(map.getZoom())) {
                map.setView([viewLat, viewLng], options.zoom || 15, { animate: false });
            }
        }

        function updateZoomBadge() {
            if (!zoomBadge) return;
            const z = map.getZoom();
            zoomBadge.textContent = (z != null && !Number.isNaN(z))
                ? `زوم ${z.toLocaleString('fa-IR')}`
                : 'زوم —';
        }

        if (!emptyPlaceMode) fitMapView(false);
        updateZoomBadge();
        map.on('zoomend', updateZoomBadge);

        fitBtn?.addEventListener('click', () => fitMapView(true), { signal });

        function refreshMapSize() {
            setTimeout(() => {
                map.invalidateSize();
                if (!emptyPlaceMode || (draftLat != null && draftLng != null)) {
                    fitMapView(false);
                }
                updateZoomBadge();
            }, 120);
        }

        fullscreenBtn?.addEventListener('click', async () => {
            const target = stage || el;
            if (!target) return;
            try {
                if (!document.fullscreenElement) {
                    await target.requestFullscreen();
                    fullscreenBtn.querySelector('i')?.classList.replace('fa-expand', 'fa-compress');
                    refreshMapSize();
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
            refreshMapSize();
        }, { signal });

        const locationPanel = el.closest('[data-panel="مکان"]');
        if (locationPanel?.hidden) {
            panelObserver = new MutationObserver(() => {
                if (!locationPanel.hidden) {
                    panelObserver?.disconnect();
                    panelObserver = null;
                    refreshMapSize();
                }
            });
            panelObserver.observe(locationPanel, { attributes: true, attributeFilter: ['hidden'] });
        }

        document.querySelector('.ws-ld-tabs [data-tab="مکان"]')
            ?.addEventListener('click', () => refreshMapSize(), { signal });
        document.querySelectorAll('[data-ld-map-jump]').forEach((btn) => {
            btn.addEventListener('click', () => setTimeout(refreshMapSize, 180), { signal });
        });
        /* Map finale is visible on load — refresh after layout settles */
        if (el.closest('.crm-prop-map-finale')) {
            requestAnimationFrame(() => setTimeout(refreshMapSize, 80));
        }

        refreshMapSize();
        if (editable) notifyDraft();

        const api = {
            map,
            destroy: cleanup,
            setDraft,
            commitDraft,
            revertDraft,
            getDraft,
            refresh: refreshMapSize,
            hasLocation: () => draftLat != null && draftLng != null,
            isDirty: () => !coordsEqual(committedLat, committedLng, draftLat, draftLng)
                || (committedLat == null && draftLat != null),
        };
        listingMapInstances.set(mapId, { cleanup, map, api });
        global.wsLdDetailMap = map;
        return api;
    }

    function destroyListingDetailMap(mapId = 'wsLdLocationMap') {
        listingMapInstances.get(mapId)?.cleanup?.();
    }

    global.initListingDetailMap = initListingDetailMap;
    global.destroyListingDetailMap = destroyListingDetailMap;
    global.buildMapMarkerPopup = global.buildMapMarkerPopup || buildMapMarkerPopup;
}(window));
