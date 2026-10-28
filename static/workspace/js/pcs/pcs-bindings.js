/**
 * Resolve layer binding values from property + brand (respect visibility).
 */
(function (global) {
    'use strict';

    function bindingText(layer, ctx) {
        if (!layer) return '';
        const binding = layer.binding;
        if (!binding || binding.mode === 'detached') {
            return String(layer.text || '');
        }
        if (binding.mode === 'override') {
            return String(layer.text || '');
        }
        if (binding.source !== 'property' || !binding.field) {
            return String(layer.text || '');
        }
        const catalog = ctx.catalogByKey || {};
        const entry = catalog[binding.field];
        if (entry && entry.value != null) return String(entry.value);
        const p = ctx.property || {};
        const field = binding.field;
        if (field === 'location_line') return String(p.location_line || p.city || '');
        if (field === 'area_label') return String(p.area_label || '');
        if (field === 'rooms_label') return String(p.rooms_label || '');
        if (field === 'floor_label') return String(p.floor_label || '');
        if (field === 'build_year_label') return String(p.build_year_label || '');
        if (field === 'price') return p.price?.show ? String(p.price.label || '') : '';
        if (field === 'deal_mode') return String(p.deal_mode || '');
        if (field === 'property_type') return String(p.property_type || '');
        if (field === 'file_code') return String(p.file_code || '');
        if (field.startsWith('amenity.')) {
            const idx = parseInt(field.split('.')[1], 10);
            const am = p.amenities || [];
            return am[idx] ? String(am[idx]) : '';
        }
        return String(layer.text || '');
    }

    function catalogMap(features) {
        const map = {};
        (features || []).forEach((f) => {
            if (f && f.key) map[f.key] = f;
        });
        return map;
    }

    function syncLinkedLayers(scene, ctx) {
        if (!scene?.layers) return scene;
        scene.layers.forEach((layer) => {
            if (layer.binding?.mode !== 'linked') return;
            const val = bindingText(layer, ctx);
            if (val !== layer.text) layer.text = val;
        });
        return scene;
    }

    global.PCSBindings = {
        bindingText,
        catalogMap,
        syncLinkedLayers,
    };
}(typeof window !== 'undefined' ? window : globalThis));
