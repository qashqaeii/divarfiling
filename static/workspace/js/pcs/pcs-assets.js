/**
 * Stable template asset ids → resolved static URLs (avoid truncating URLs in assetRef).
 */
(function (global) {
    'use strict';

    const TEMPLATE_ASSET_PREFIX = 'tpl:';

    function templateAssetId(templateId) {
        return `${TEMPLATE_ASSET_PREFIX}${templateId}`;
    }

    function resolveAssetRef(ref, overlayByTemplate) {
        const raw = String(ref || '').trim();
        if (!raw) return '';
        if (raw.startsWith(TEMPLATE_ASSET_PREFIX)) {
            const tid = raw.slice(TEMPLATE_ASSET_PREFIX.length);
            return overlayByTemplate?.[tid] || '';
        }
        if (/^https?:\/\//i.test(raw) || raw.startsWith('/')) return raw;
        return overlayByTemplate?.[raw] || raw;
    }

    global.PCSAssets = {
        TEMPLATE_ASSET_PREFIX,
        templateAssetId,
        resolveAssetRef,
    };
}(typeof window !== 'undefined' ? window : globalThis));
