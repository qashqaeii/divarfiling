/**
 * Ensures manifest scenes include structural text/image slots (geometry only).
 * Used only by generate_pcs_manifests.mjs — mirrors bound layers from buildInitialScene
 * without embedding fake property values.
 */
export function ensureStructuralLayers(scene, templateId, boxes, h, layerTextHelper) {
    if (!scene?.layers || !boxes) return scene;
    const byId = new Set(scene.layers.map((l) => l.id));
    const order = scene.layerOrder.slice();

    function insertBeforeFrame(id) {
        const fi = order.indexOf('template-frame');
        if (fi >= 0) order.splice(fi, 0, id);
        else order.push(id);
    }

    function addLayer(layer) {
        if (byId.has(layer.id)) return;
        scene.layers.push(layer);
        insertBeforeFrame(layer.id);
        byId.add(layer.id);
    }

    const tpl = templateId;
    const fontKey = ['amethyst_ceramic', 'champagne_origami', 'glacier_prism', 'mediterranean_papercut', 'terracotta_terrace'].includes(tpl)
        ? 'gulzar'
        : 'vazirmatn';

    if (boxes.headline) {
        addLayer(layerTextHelper('headline-1', 'عنوان', boxes.headline, {
            text: '',
            templateRole: 'headline',
            fontSize: Math.round(h * (tpl === 'sculpted_travertine' || tpl.includes('burgundy') ? 0.034 : tpl === 'pearlescent' ? 0.038 : 0.042)),
            fontWeight: 900,
            fontKey,
            fill: '#0a3560',
            style: { align: 'right', lineHeight: 1.2, verticalAlign: 'top' },
        }));
    }

    if (boxes.deal) {
        addLayer(layerTextHelper('deal-1', 'نوع معامله', boxes.deal, {
            text: '',
            bound: true,
            binding: { source: 'property', field: 'deal_mode', mode: 'linked' },
            fontSize: Math.round(h * 0.014),
            fontWeight: 800,
            fill: '#ffffff',
            style: { textPreset: 'capsule', align: 'center' },
        }));
    }

    if (boxes.meta) {
        addLayer(layerTextHelper('meta-1', 'مشخصات', boxes.meta, {
            text: '',
            templateRole: 'meta',
            fontSize: Math.round(h * 0.019),
            fontWeight: 700,
            fontKey,
            fill: '#64748b',
            style: { align: 'right', lineHeight: 1.45, verticalAlign: 'top' },
        }));
    }

    if (boxes.price) {
        addLayer(layerTextHelper('price-1', 'قیمت', boxes.price, {
            text: '',
            bound: true,
            binding: { source: 'property', field: 'price', mode: 'linked' },
            templateRole: 'price',
            fontSize: Math.round(h * 0.028),
            fontWeight: 900,
            fontKey,
            fill: '#64748b',
            style: { align: 'right', lineHeight: 1.15, verticalAlign: 'top' },
        }));
    }

    scene.layerOrder = order;
    return scene;
}

export function extractImageSlotMetadata(scene, boxes, templateId) {
    const slots = [];
    (scene.layers || []).forEach((layer, index) => {
        if (layer.type !== 'image') return;
        const entry = {
            id: layer.id,
            templateRole: layer.templateRole || '',
            imageIndex: layer.imageIndex != null ? layer.imageIndex : 0,
            x: layer.x,
            y: layer.y,
            width: layer.width,
            height: layer.height,
            zIndex: index,
            style: layer.style || {},
        };
        if (layer.style?.borderRadius && layer.style.borderRadius >= layer.width / 2 - 1) {
            entry.mask = { kind: 'circle', borderRadius: layer.style.borderRadius };
        } else if (layer.style?.borderRadius) {
            entry.mask = { kind: 'rounded_rect', borderRadius: layer.style.borderRadius };
        }
        slots.push(entry);
    });

    const calibration = {};
    if (boxes?.primaryCircle) calibration.primaryCircle = boxes.primaryCircle;
    if (boxes?.secondaryCircle) calibration.secondaryCircle = boxes.secondaryCircle;
    if (boxes?.circles) calibration.circles = boxes.circles;
    if (boxes?.arch) calibration.arch = { box: boxes.arch, objX: boxes.arch.objX, objY: boxes.arch.objY };
    if (boxes?.strip) calibration.strip = { box: boxes.strip, objX: boxes.strip.objX, objY: boxes.strip.objY };
    if (boxes?.hero) calibration.hero = boxes.hero;

    return { image_slots: slots, layout_calibration: calibration };
}
