/**
 * Property Content Studio — document scene schema (v2) + migration from legacy poster config.
 */
(function (global) {
    'use strict';

    const SCENE_SCHEMA_VERSION = 2;
    const LAYER_TYPES = new Set([
        'text', 'bound_text', 'image', 'template_frame', 'logo', 'shape', 'group', 'decor',
    ]);
    const MAX_LAYERS = 48;

    function uid(prefix) {
        return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
    }

    function finiteNum(v, fallback) {
        const n = typeof v === 'number' ? v : parseFloat(v);
        return Number.isFinite(n) ? n : fallback;
    }

    function clamp(n, lo, hi) {
        return Math.min(hi, Math.max(lo, n));
    }

    function canvasForFormat(formatKey, formats) {
        const fmt = (formats && formats[formatKey]) || { width: 1080, height: 1920 };
        return {
            width: fmt.width || fmt.w || 1080,
            height: fmt.height || fmt.h || 1920,
            format: formatKey || 'story',
        };
    }

    const _FORMAT_IDS = new Set(['story', 'post', 'square']);

    function emptyScene(templateId, formatKey, formats) {
        return {
            schemaVersion: SCENE_SCHEMA_VERSION,
            canvas: canvasForFormat(formatKey, formats),
            templateId: templateId || 'luxury',
            renderMode: 'layers',
            layers: [],
            layerOrder: [],
        };
    }

    function normalizeBinding(raw) {
        if (!raw || typeof raw !== 'object') return null;
        const mode = raw.mode === 'override' || raw.mode === 'detached' ? raw.mode : 'linked';
        const source = raw.source === 'property' ? 'property' : 'user';
        const field = String(raw.field || '').slice(0, 64);
        if (source === 'property' && !field) return null;
        return { source, field, mode };
    }

    function normalizeStyle(raw) {
        if (!raw || typeof raw !== 'object') return {};
        const out = {};
        if (raw.fontKey) out.fontKey = String(raw.fontKey).slice(0, 24);
        if (raw.fontSize != null) out.fontSize = clamp(finiteNum(raw.fontSize, 32), 8, 200);
        if (raw.fontWeight != null) out.fontWeight = clamp(finiteNum(raw.fontWeight, 700), 400, 900);
        if (raw.fill) out.fill = String(raw.fill).slice(0, 16);
        if (raw.align) out.align = ['left', 'center', 'right'].includes(raw.align) ? raw.align : 'right';
        if (raw.direction) out.direction = raw.direction === 'ltr' ? 'ltr' : 'rtl';
        if (raw.lineHeight != null) out.lineHeight = clamp(finiteNum(raw.lineHeight, 1.35), 0.8, 3);
        if (raw.background) out.background = String(raw.background).slice(0, 32);
        if (raw.borderRadius != null) out.borderRadius = clamp(finiteNum(raw.borderRadius, 0), 0, 999);
        if (raw.opacity != null) out.opacity = clamp(finiteNum(raw.opacity, 1), 0, 1);
        if (raw.textPreset) out.textPreset = String(raw.textPreset).slice(0, 32);
        if (raw.objectFit) out.objectFit = ['cover', 'contain', 'fill'].includes(raw.objectFit) ? raw.objectFit : 'cover';
        if (raw.cropPanX != null) out.cropPanX = clamp(finiteNum(raw.cropPanX, 50), 0, 100);
        if (raw.cropPanY != null) out.cropPanY = clamp(finiteNum(raw.cropPanY, 50), 0, 100);
        if (raw.cropZoom != null) out.cropZoom = clamp(finiteNum(raw.cropZoom, 1), 0.5, 3);
        return out;
    }

    function normalizeLayer(raw, canvas) {
        if (!raw || typeof raw !== 'object') return null;
        const type = LAYER_TYPES.has(raw.type) ? raw.type : 'text';
        const id = String(raw.id || uid(type)).slice(0, 40);
        const cw = canvas?.width || 1080;
        const ch = canvas?.height || 1920;
        const layer = {
            id,
            type,
            name: String(raw.name || id).slice(0, 80),
            visible: raw.visible !== false,
            locked: !!raw.locked,
            parentId: raw.parentId ? String(raw.parentId).slice(0, 40) : null,
            x: clamp(finiteNum(raw.x, 0), -cw, cw * 2),
            y: clamp(finiteNum(raw.y, 0), -ch, ch * 2),
            width: clamp(finiteNum(raw.width, 200), 1, cw * 2),
            height: clamp(finiteNum(raw.height, 48), 1, ch * 2),
            rotation: clamp(finiteNum(raw.rotation, 0), -360, 360),
            opacity: clamp(finiteNum(raw.opacity, 1), 0, 1),
            binding: normalizeBinding(raw.binding),
            style: normalizeStyle(raw.style),
        };
        if (raw.text != null) layer.text = String(raw.text).slice(0, 2000);
        if (raw.assetRef) layer.assetRef = String(raw.assetRef).slice(0, 64);
        if (raw.imageIndex != null) layer.imageIndex = clamp(finiteNum(raw.imageIndex, 0), 0, 64);
        if (raw.templateRole) layer.templateRole = String(raw.templateRole).slice(0, 32);
        if (raw.hiddenLegacy) layer.hiddenLegacy = !!raw.hiddenLegacy;
        return layer;
    }

    function normalizeScene(raw, templateId, formatKey, formats) {
        const base = emptyScene(templateId, formatKey, formats);
        if (!raw || typeof raw !== 'object') return base;
        const canvas = raw.canvas && typeof raw.canvas === 'object'
            ? {
                width: clamp(finiteNum(raw.canvas.width, base.canvas.width), 320, 4096),
                height: clamp(finiteNum(raw.canvas.height, base.canvas.height), 320, 4096),
                format: _FORMAT_IDS.has(raw.canvas.format) ? raw.canvas.format : base.canvas.format,
            }
            : base.canvas;
        const layersIn = Array.isArray(raw.layers) ? raw.layers.slice(0, MAX_LAYERS) : [];
        const layers = [];
        const ids = new Set();
        layersIn.forEach((item) => {
            const norm = normalizeLayer(item, canvas);
            if (!norm || ids.has(norm.id)) return;
            ids.add(norm.id);
            layers.push(norm);
        });
        let order = Array.isArray(raw.layerOrder) ? raw.layerOrder.map((x) => String(x).slice(0, 40)) : [];
        order = order.filter((id) => ids.has(id));
        layers.forEach((l) => {
            if (!order.includes(l.id)) order.push(l.id);
        });
        return {
            schemaVersion: SCENE_SCHEMA_VERSION,
            canvas,
            templateId: String(raw.templateId || templateId || 'luxury').slice(0, 32),
            renderMode: raw.renderMode === 'legacy' ? 'legacy' : 'layers',
            layers,
            layerOrder: order.slice(0, MAX_LAYERS),
            migratedAt: raw.migratedAt || null,
        };
    }

    function layerById(scene, id) {
        return (scene?.layers || []).find((l) => l.id === id) || null;
    }

    function cloneScene(scene) {
        return JSON.parse(JSON.stringify(scene));
    }

    /**
     * Convert legacy text_layout (% translate on flow blocks) to document pixel layers.
     * legacyMetrics: { headline, meta, price } each { left, top, width, height } in canvas px.
     */
    function textLayoutToLayerBox(layoutEntry, metrics) {
        if (!metrics) return { x: 40, y: 40, width: 400, height: 80 };
        const lx = finiteNum(layoutEntry?.x, 0);
        const ly = finiteNum(layoutEntry?.y, 0);
        const elW = metrics.width || 400;
        const elH = metrics.height || 60;
        const dx = (lx / 100) * elW;
        const dy = (ly / 100) * elH;
        return {
            x: metrics.left + dx,
            y: metrics.top + dy,
            width: elW,
            height: elH,
        };
    }

    function posterConfigToScene(conf, ctx) {
        const templateId = ctx.templateId || 'luxury';
        const formatKey = ctx.formatKey || 'story';
        const formats = ctx.formats || {};
        if (conf?.scene && conf.scene.schemaVersion >= 2) {
            return normalizeScene(conf.scene, templateId, formatKey, formats);
        }
        const scene = emptyScene(templateId, formatKey, formats);
        scene.migratedAt = new Date().toISOString();
        const factory = global.PCSTemplateScenes;
        if (factory && typeof factory.buildInitialScene === 'function') {
            return factory.buildInitialScene(conf, ctx, scene);
        }
        return scene;
    }

    function sceneToPosterPatch(scene) {
        return { scene: normalizeScene(scene, scene?.templateId, scene?.canvas?.format) };
    }

    global.PCSSchema = {
        SCENE_SCHEMA_VERSION,
        LAYER_TYPES,
        MAX_LAYERS,
        uid,
        emptyScene,
        normalizeScene,
        normalizeLayer,
        layerById,
        cloneScene,
        posterConfigToScene,
        sceneToPosterPatch,
        textLayoutToLayerBox,
        canvasForFormat,
    };
}(typeof window !== 'undefined' ? window : globalThis));
