/**
 * CARTO raster basemap helpers — API key injected from Django templates (never hard-coded here).
 */
(function (global) {
    'use strict';

    var CARTO_STYLE_PATHS = {
        voyager: 'rastertiles/voyager',
        light: 'light_all',
        dark: 'dark_all',
    };

    var CARTO_BASEMAP_IDS = { voyager: true, light: true, dark: true };

    var cartoBasemapKey = '';

    function setCartoBasemapKey(key) {
        cartoBasemapKey = String(key || '').trim();
    }

    function getCartoBasemapKey() {
        return cartoBasemapKey;
    }

    function hasCartoBasemapKey() {
        return cartoBasemapKey.length > 0;
    }

    function isCartoBasemapId(id) {
        return !!CARTO_BASEMAP_IDS[id];
    }

    function resolveBasemapId(preferredId) {
        if (isCartoBasemapId(preferredId) && !hasCartoBasemapKey()) {
            return 'standard';
        }
        return preferredId;
    }

    function cartoRasterTileUrl(stylePath, options) {
        if (!hasCartoBasemapKey()) return null;
        var retina = options && options.retina;
        var r = retina ? '{r}' : '';
        return 'https://{s}.basemaps.cartocdn.com/' + stylePath + '/{z}/{x}/{y}' + r + '.png?key='
            + encodeURIComponent(cartoBasemapKey);
    }

    // Wikimedia and tile.openstreetmap.org return 403 for third-party sites.
    var STANDARD_BASEMAP_TILE_URL = 'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png';
    var STANDARD_BASEMAP_ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
        + '&copy; <a href="https://openstreetmap.fr/">OpenStreetMap France</a>';

    function createOsmStandardLayer(L, options) {
        var opts = options || {};
        return L.tileLayer(STANDARD_BASEMAP_TILE_URL, {
            attribution: opts.attribution || STANDARD_BASEMAP_ATTRIBUTION,
            maxZoom: opts.maxZoom != null ? opts.maxZoom : 19,
            subdomains: opts.subdomains || 'abc',
            crossOrigin: opts.crossOrigin !== false,
        });
    }

    function createCartoLayer(L, styleId, options, layerOptions) {
        var path = CARTO_STYLE_PATHS[styleId];
        if (!path) return null;
        var url = cartoRasterTileUrl(path, layerOptions);
        if (!url) {
            return createOsmStandardLayer(L, options);
        }
        return L.tileLayer(url, options || {});
    }

    global.CartoBasemap = {
        setKey: setCartoBasemapKey,
        getKey: getCartoBasemapKey,
        hasKey: hasCartoBasemapKey,
        isCartoBasemapId: isCartoBasemapId,
        resolveBasemapId: resolveBasemapId,
        createCartoLayer: createCartoLayer,
        createOsmStandardLayer: createOsmStandardLayer,
    };
}(typeof window !== 'undefined' ? window : this));
