/**
 * انتخابگر نقشه مینیمال برای فرم ایجاد/ویرایش فایل شخصی CRM
 * — بازشونده، همگام با latitude / longitude
 */
(function (global) {
    'use strict';

    var LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    var LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    var DEFAULT_CENTER = { lat: 35.6892, lng: 51.3890, zoom: 11 };
    var leafletPromise = null;

    function loadLeaflet() {
        if (global.L && global.L.map) return Promise.resolve(global.L);
        if (leafletPromise) return leafletPromise;

        leafletPromise = new Promise(function (resolve, reject) {
            if (!document.querySelector('link[data-crm-form-map-leaflet]')) {
                var link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = LEAFLET_CSS;
                link.setAttribute('data-crm-form-map-leaflet', '1');
                document.head.appendChild(link);
            }
            if (global.L && global.L.map) {
                resolve(global.L);
                return;
            }
            var existing = document.querySelector('script[data-crm-form-map-leaflet]');
            if (existing) {
                existing.addEventListener('load', function () { resolve(global.L); });
                existing.addEventListener('error', reject);
                return;
            }
            var script = document.createElement('script');
            script.src = LEAFLET_JS;
            script.async = true;
            script.setAttribute('data-crm-form-map-leaflet', '1');
            script.onload = function () { resolve(global.L); };
            script.onerror = reject;
            document.head.appendChild(script);
        });
        return leafletPromise;
    }

    function parseCoord(raw) {
        if (raw == null || raw === '') return null;
        var n = Number(String(raw).replace(',', '.').trim());
        return Number.isFinite(n) ? n : null;
    }

    function fmtCoord(n) {
        return Number(n).toFixed(6);
    }

    function createPinIcon(L) {
        return L.divIcon({
            className: 'crm-form-map-pin',
            html: '<span class="crm-form-map-pin__dot" aria-hidden="true"></span>',
            iconSize: [28, 28],
            iconAnchor: [14, 28],
            popupAnchor: [0, -24],
        });
    }

    function setupFormMap(wrap) {
        if (!wrap || wrap.dataset.crmFormMapBound === '1') return;
        wrap.dataset.crmFormMapBound = '1';

        var form = wrap.closest('form') || document;
        var toggle = wrap.querySelector('[data-crm-form-map-toggle]');
        var panel = wrap.querySelector('[data-crm-form-map-panel]');
        var canvas = wrap.querySelector('[data-crm-form-map-canvas]');
        var coordsEl = wrap.querySelector('[data-crm-form-map-coords]');
        var chipEl = wrap.querySelector('[data-crm-form-map-chip]');
        var summaryEl = wrap.querySelector('[data-crm-form-map-summary]');
        var clearBtn = wrap.querySelector('[data-crm-form-map-clear]');
        var locateBtn = wrap.querySelector('[data-crm-form-map-locate]');
        var latInput = form.querySelector('[name="latitude"]');
        var lngInput = form.querySelector('[name="longitude"]');

        if (!toggle || !panel || !canvas || !latInput || !lngInput) return;

        var map = null;
        var marker = null;
        var tileLayer = null;
        var opening = false;

        function syncUi(lat, lng) {
            var has = lat != null && lng != null;
            if (coordsEl) {
                coordsEl.textContent = has ? (fmtCoord(lat) + ' ، ' + fmtCoord(lng)) : '—';
            }
            if (chipEl) {
                if (has) {
                    chipEl.textContent = fmtCoord(lat) + ' ، ' + fmtCoord(lng);
                    chipEl.hidden = false;
                } else {
                    chipEl.textContent = '';
                    chipEl.hidden = true;
                }
            }
            if (summaryEl) {
                summaryEl.textContent = has
                    ? 'موقعیت روی نقشه ثبت شده'
                    : 'برای ثبت مختصات، نقشه را باز کنید';
            }
            wrap.classList.toggle('has-coords', has);
        }

        function setCoords(lat, lng, opts) {
            opts = opts || {};
            if (lat == null || lng == null) {
                latInput.value = '';
                lngInput.value = '';
                syncUi(null, null);
                if (marker && map) {
                    map.removeLayer(marker);
                    marker = null;
                }
                return;
            }
            latInput.value = fmtCoord(lat);
            lngInput.value = fmtCoord(lng);
            syncUi(lat, lng);
            if (!map) return;
            if (!marker) {
                marker = global.L.marker([lat, lng], {
                    draggable: true,
                    icon: createPinIcon(global.L),
                    keyboard: false,
                    title: 'موقعیت ملک',
                    alt: '',
                }).addTo(map);
                marker.on('dragend', function () {
                    var p = marker.getLatLng();
                    setCoords(p.lat, p.lng);
                });
            } else {
                marker.setLatLng([lat, lng]);
            }
            if (opts.pan !== false) {
                map.setView([lat, lng], Math.max(map.getZoom(), opts.zoom || 15), { animate: true });
            }
        }

        function initMap() {
            var L = global.L;
            var lat = parseCoord(latInput.value);
            var lng = parseCoord(lngInput.value);
            var has = lat != null && lng != null;
            var center = has ? [lat, lng] : [DEFAULT_CENTER.lat, DEFAULT_CENTER.lng];
            var zoom = has ? 15 : DEFAULT_CENTER.zoom;

            map = L.map(canvas, {
                zoomControl: true,
                attributionControl: true,
                scrollWheelZoom: true,
            }).setView(center, zoom);

            tileLayer = global.CartoBasemap?.hasKey()
                ? global.CartoBasemap.createCartoLayer(L, 'voyager', {
                    attribution: '&copy; OSM &copy; CARTO',
                    subdomains: 'abcd',
                    maxZoom: 19,
                }, { retina: true })
                : (global.CartoBasemap
                    ? global.CartoBasemap.createOsmStandardLayer(L, { maxZoom: 19 })
                    : L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
                        attribution: '&copy; OSM &copy; OSM France',
                        subdomains: 'abc',
                        maxZoom: 19,
                    }));
            tileLayer.addTo(map);

            if (has) {
                setCoords(lat, lng, { pan: false });
            }

            map.on('click', function (e) {
                setCoords(e.latlng.lat, e.latlng.lng, { pan: false, zoom: map.getZoom() });
            });

            setTimeout(function () {
                map.invalidateSize();
            }, 80);
        }

        async function openPanel() {
            if (opening) return;
            opening = true;
            panel.hidden = false;
            wrap.classList.add('is-open');
            toggle.setAttribute('aria-expanded', 'true');
            try {
                await loadLeaflet();
                if (!map) initMap();
                else setTimeout(function () { map.invalidateSize(); }, 60);
            } catch (err) {
                console.error(err);
                if (summaryEl) summaryEl.textContent = 'بارگذاری نقشه ناموفق بود';
            } finally {
                opening = false;
            }
        }

        function closePanel() {
            panel.hidden = true;
            wrap.classList.remove('is-open');
            toggle.setAttribute('aria-expanded', 'false');
        }

        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            if (panel.hidden) openPanel();
            else closePanel();
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function (e) {
                e.preventDefault();
                setCoords(null, null);
                if (map) {
                    map.setView([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng], DEFAULT_CENTER.zoom);
                }
            });
        }

        if (locateBtn) {
            locateBtn.addEventListener('click', function (e) {
                e.preventDefault();
                if (!navigator.geolocation) return;
                locateBtn.disabled = true;
                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        setCoords(pos.coords.latitude, pos.coords.longitude, { zoom: 16 });
                        locateBtn.disabled = false;
                    },
                    function () {
                        locateBtn.disabled = false;
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            });
        }

        // همگام‌سازی اولیه UI بدون باز کردن نقشه
        syncUi(parseCoord(latInput.value), parseCoord(lngInput.value));

        // اگر از قبل مختصات دارد، پنل را باز نگه نداریم — فقط خلاصه نشان می‌دهیم
        wrap._crmFormMap = {
            refresh: function () {
                if (map) {
                    setTimeout(function () { map.invalidateSize(); }, 40);
                }
            },
            open: openPanel,
        };
    }

    function initCRMFormMaps(root) {
        var scope = root || document;
        scope.querySelectorAll('[data-crm-form-map]').forEach(setupFormMap);
        // اگر دراور تازه باز شده و پنل باز است، سایز نقشه را تازه کن
        scope.querySelectorAll('[data-crm-form-map].is-open').forEach(function (wrap) {
            if (wrap._crmFormMap && wrap._crmFormMap.refresh) wrap._crmFormMap.refresh();
        });
    }

    global.initCRMFormMaps = initCRMFormMaps;
})(window);
