/**
 * Resolve layer binding values — visibility-safe, no stale fallback for linked fields.
 */
(function (global) {
    'use strict';

    function catalogEntry(field, ctx) {
        const catalog = ctx.catalogByKey || {};
        if (field && catalog[field]) return catalog[field];
        return null;
    }

    function featureDisplayPlain(entry) {
        if (!entry) return '';
        const value = String(entry.value != null ? entry.value : '').trim();
        if (!value) return '';
        const label = String(entry.label || '').trim();
        if (!label) return value;
        return `${label} : ${value}`;
    }

    /** یک خط برای لیست «اطلاعات ملک» — همان فرمت متن روی بوم، بدون دو سطر تکراری */
    function featureCatalogPanelLine(entry) {
        if (!entry) return '—';
        const label = String(entry.label || '').trim();
        const value = String(entry.value != null ? entry.value : '').trim();
        if (!value) return label || '—';
        if (!label || label === value) return value;
        return featureDisplayPlain(entry);
    }

    function propertyFieldValue(field, ctx) {
        const p = ctx.property || {};
        if (field === 'location_line') return String(p.location_line || p.city || '');
        if (field === 'area_label') return String(p.area_label || '');
        if (field === 'rooms_label') return String(p.rooms_label || '');
        if (field === 'floor_label') return String(p.floor_label || '');
        if (field === 'build_year_label') return String(p.build_year_label || '');
        if (field === 'price') return p.price?.show ? String(p.price.label || '') : '';
        if (field === 'deal_mode') return String(p.deal_mode || p.deal_label || '');
        if (field === 'property_type') return String(p.property_type || '');
        if (field === 'file_code') return String(p.file_code || '');
        const brand = ctx.brand || {};
        if (field === 'consultant_name') {
            return String(brand.consultant_name || brand.brand_name || '').trim();
        }
        if (field === 'contact_phone') {
            return String(brand.contact_phone || '').trim();
        }
        if (field.startsWith('amenity.')) {
            const idx = parseInt(field.split('.')[1], 10);
            const am = p.amenities || [];
            return am[idx] ? String(am[idx]) : '';
        }
        return '';
    }

    function overlayFooterLine(name, phone) {
        if (name && phone) return `${name}  ·  ${phone}`;
        return phone || name || '';
    }

    /** متن نشان نوع معامله روی پوستر (نه برچسب کاتالوگ «نوع معامله: …»). */
    function posterDealBadgeLabel(dealMode) {
        const mode = String(dealMode || '').trim();
        if (!mode) return '';
        if (mode === 'فروش') return 'آگهی فروش';
        if (mode === 'رهن و اجاره') return 'آگهی رهن و اجاره';
        if (mode === 'اجاره') return 'آگهی اجاره';
        if (mode === 'پیش‌فروش') return 'آگهی پیش‌فروش';
        if (mode.startsWith('آگهی')) return mode;
        return `آگهی ${mode}`;
    }

    function bindingText(layer, ctx) {
        if (!layer) return '';
        const binding = layer.binding;
        if (!binding || binding.mode === 'detached') {
            return String(layer.text || '');
        }
        if (binding.mode === 'override') {
            return String(layer.text || '');
        }
        if (binding.source === 'brand') {
            if (binding.field === 'contact_footer') {
                const { name, phone } = posterBrandContact(ctx?.posterConf || {}, ctx);
                return overlayFooterLine(name, phone);
            }
            return propertyFieldValue(binding.field, ctx);
        }
        if (binding.source !== 'property' || !binding.field) {
            return String(layer.text || '');
        }
        if (binding.field === 'deal_mode' && layer.id === 'deal-1') {
            const raw = String((ctx.property || {}).deal_mode || (ctx.property || {}).deal_label || '').trim();
            return posterDealBadgeLabel(raw);
        }
        const entry = catalogEntry(binding.field, ctx);
        if (entry) {
            const plain = featureDisplayPlain(entry);
            if (plain) return plain;
        }
        return propertyFieldValue(binding.field, ctx);
    }

    function catalogMap(features) {
        const map = {};
        (features || []).forEach((f) => {
            if (f && f.key) map[f.key] = f;
        });
        return map;
    }

    function posterBrandContact(conf, ctx) {
        const brand = ctx.brand || {};
        const vis = brand.visibility || {};
        const name = vis.consultant_name !== false
            ? String(
                conf?.consultant_name || conf?.brand_name
                || brand.consultant_name || brand.brand_name || '',
            ).trim()
            : '';
        const phone = vis.contact_phone !== false
            ? String(conf?.contact_phone || conf?.brand_phone || brand.contact_phone || '').trim()
            : '';
        return { name, phone };
    }

    function syncBrandFooterLayers(scene, ctx) {
        if (!scene?.layers) return scene;
        const conf = ctx?.posterConf || {};
        const { name, phone } = posterBrandContact(conf, ctx);
        const line = overlayFooterLine(name, phone);
        scene.layers.forEach((layer) => {
            if (layer.id !== 'footer-1' && layer.templateRole !== 'footer') return;
            if (layer.binding?.mode === 'override' || layer.binding?.mode === 'detached') return;
            layer.text = line;
        });
        return scene;
    }

    function syncLinkedLayers(scene, ctx) {
        if (!scene?.layers) return scene;
        scene.layers.forEach((layer) => {
            if (layer.binding?.mode !== 'linked') return;
            layer.text = bindingText(layer, ctx);
        });
        syncBrandFooterLayers(scene, ctx);
        return scene;
    }

    global.PCSBindings = {
        bindingText,
        posterDealBadgeLabel,
        featureDisplayPlain,
        featureCatalogPanelLine,
        syncBrandFooterLayers,
        catalogMap,
        syncLinkedLayers,
    };
}(typeof window !== 'undefined' ? window : globalThis));
