/**
 * Non-style metadata extracted from manifest scenes (image slots, calibration).
 */
export function extractImageSlotMetadata(scene, boxes) {
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
