/**
 * Initial scene layers per template + migration from legacy poster config.
 */
(function (global) {
    'use strict';

    const Schema = global.PCSSchema;

    function layerText(id, name, box, opts) {
        return {
            id,
            type: opts?.bound ? 'bound_text' : 'text',
            name,
            visible: true,
            locked: false,
            parentId: null,
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            rotation: 0,
            opacity: 1,
            text: opts?.text || '',
            binding: opts?.binding || null,
            templateRole: opts?.templateRole || '',
            style: Object.assign({
                fontKey: 'vazirmatn',
                fontSize: opts?.fontSize || 32,
                fontWeight: opts?.fontWeight || 700,
                fill: opts?.fill || '#ffffff',
                align: 'right',
                direction: 'rtl',
            }, opts?.style || {}),
        };
    }

    function storyBoxes(templateId, w, h) {
        const pad = Math.round(w * 0.055);
        if (templateId === 'minimal' || templateId === 'modern') {
            return {
                headline: { x: pad, y: pad + 8, width: w - pad * 2 - 120, height: Math.round(h * 0.12) },
                price: { x: pad, y: h - pad - 220, width: w - pad * 2, height: 72 },
                meta: { x: pad, y: h - pad - 140, width: w - pad * 2, height: 56 },
            };
        }
        return {
            headline: { x: pad, y: h - pad - 420, width: w - pad * 2, height: Math.round(h * 0.14) },
            price: { x: pad, y: h - pad - 200, width: w - pad * 2, height: 80 },
            meta: { x: pad, y: h - pad - 110, width: w - pad * 2, height: 56 },
        };
    }

    function applyLegacyTextLayout(conf, boxes, w, h) {
        const tl = conf?.text_layout || {};
        ['headline', 'meta', 'price'].forEach((role) => {
            const entry = tl[role];
            const metrics = boxes[role];
            if (!entry || !metrics) return;
            const box = Schema.textLayoutToLayerBox(entry, metrics);
            boxes[role] = box;
        });
    }

    function buildInitialScene(conf, ctx, baseScene) {
        const scene = Schema.normalizeScene(baseScene, ctx.templateId, ctx.formatKey, ctx.formats);
        const w = scene.canvas.width;
        const h = scene.canvas.height;
        const tpl = scene.templateId;
        const boxes = storyBoxes(tpl, w, h);
        if (conf?.text_layout) applyLegacyTextLayout(conf, boxes, w, h);

        const p = ctx.property || {};
        const headlineText = (conf?.headline || p.headline || '').trim();
        const layers = [];
        const order = [];

        layers.push({
            id: 'hero-image',
            type: 'image',
            name: 'تصویر شاخص',
            visible: true,
            locked: false,
            parentId: null,
            x: 0,
            y: 0,
            width: w,
            height: Math.round(h * (tpl === 'minimal' ? 0.55 : 0.72)),
            rotation: 0,
            opacity: 1,
            imageIndex: conf?.primary_image_index || 0,
            style: {
                objectFit: 'cover',
                cropPanY: conf?.crop_y ?? 50,
                cropPanX: 50,
                cropZoom: 1,
            },
        });
        order.push('hero-image');

        if (ctx.overlayUrl) {
            layers.push({
                id: 'template-frame',
                type: 'template_frame',
                name: 'قاب قالب',
                visible: true,
                locked: true,
                parentId: null,
                x: 0,
                y: 0,
                width: w,
                height: h,
                rotation: 0,
                opacity: 1,
                assetRef: ctx.overlayUrl,
            });
            order.push('template-frame');
        }

        if (headlineText) {
            const hl = layerText('headline-1', 'عنوان', boxes.headline, {
                text: headlineText,
                templateRole: 'headline',
                fontSize: Math.round(h * 0.042),
                fontWeight: conf?.headline_weight || 900,
                fill: tpl === 'minimal' ? '#1e293b' : '#ffffff',
            });
            layers.push(hl);
            order.push(hl.id);
        }

        const metaParts = [];
        if (p.location_line) metaParts.push(p.location_line);
        if (p.property_type) metaParts.push(p.property_type);
        if (p.area_label) metaParts.push(p.area_label);
        if (metaParts.length) {
            layers.push(layerText('meta-1', 'مشخصات', boxes.meta, {
                text: metaParts.slice(0, 3).join(' · '),
                templateRole: 'meta',
                fontSize: Math.round(h * 0.018),
                fontWeight: 600,
                fill: tpl === 'minimal' ? '#475569' : 'rgba(255,255,255,.9)',
            }));
            order.push('meta-1');
        }

        const priceLabel = p.price?.show ? p.price.label : '';
        if (priceLabel) {
            layers.push(layerText('price-1', 'قیمت', boxes.price, {
                text: priceLabel,
                bound: true,
                binding: { source: 'property', field: 'price', mode: 'linked' },
                templateRole: 'price',
                fontSize: Math.round(h * 0.028),
                fontWeight: conf?.price_weight || 900,
                fill: tpl === 'minimal' ? '#7c3aed' : '#ffffff',
            }));
            order.push('price-1');
        }

        scene.layers = layers;
        scene.layerOrder = order;
        scene.renderMode = ctx.overlayUrl ? 'layers' : 'legacy';
        return scene;
    }

    function addFeatureLayer(scene, catalogEntry, docPoint, preset) {
        const SchemaRef = global.PCSSchema;
        const id = SchemaRef.uid('feat');
        const w = scene.canvas.width;
        const style = {
            fontKey: 'vazirmatn',
            fontSize: preset === 'badge' ? 26 : 32,
            fontWeight: preset === 'price' ? 900 : 700,
            fill: '#ffffff',
            align: 'right',
            direction: 'rtl',
            textPreset: preset || 'plain',
        };
        if (preset === 'capsule') {
            style.background = 'rgba(15,23,42,.72)';
            style.borderRadius = 999;
        }
        const layer = {
            id,
            type: 'bound_text',
            name: catalogEntry.label || catalogEntry.key,
            visible: true,
            locked: false,
            parentId: null,
            x: Math.max(0, docPoint.x - 160),
            y: Math.max(0, docPoint.y - 24),
            width: 320,
            height: preset === 'price' ? 88 : 56,
            rotation: 0,
            opacity: 1,
            text: catalogEntry.value || '',
            binding: { source: 'property', field: catalogEntry.key, mode: 'linked' },
            style,
        };
        scene.layers.push(layer);
        scene.layerOrder.push(id);
        return layer;
    }

    global.PCSTemplateScenes = {
        buildInitialScene,
        addFeatureLayer,
        storyBoxes,
    };
}(typeof window !== 'undefined' ? window : globalThis));
