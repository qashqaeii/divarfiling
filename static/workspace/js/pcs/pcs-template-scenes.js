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

    const PEARL_GALLERY_CALIBRATION = {
        refW: 940,
        refH: 1672,
        primary: { cx: 452, cy: 526, d: 702 },
        secondary: { cx: 760, cy: 804, d: 310 },
        text: { x0: 108, y0: 1008, x1: 832, y1: 1518, padX: 24, padY: 10, padEndX: 28, padEndY: 18 },
        footer: { x0: 72, y0: 1554, x1: 868, y1: 1628 },
        badge: { cx: 818, cy: 92 },
    };

    const SCULPTURAL_CALIBRATION = {
        refW: 941,
        refH: 1672,
        hero: { x0: 0, y0: 3, x1: 772, y1: 819, focusX: 347, focusY: 420 },
        text: { x0: 520, y0: 798, x1: 939, y1: 1519, padX: 34, padY: 8, padEndX: 30, padEndY: 72 },
        footer: { x0: 52, y0: 1542, x1: 888, y1: 1660 },
        badge: { cx: 718, cy: 52 },
        circles: [
            { cx: 173.05, cy: 1007.84, d: 284, inset: 0.97, z: 1 },
            { cx: 457.77, cy: 1183.04, d: 280, inset: 0.97, z: 2 },
            { cx: 176.53, cy: 1354.73, d: 286, inset: 0.97, z: 3 },
        ],
    };

    const EMERALD_CALIBRATION = {
        refW: 941,
        refH: 1672,
        arch: { x0: 142, y0: 128, x1: 636, y1: 1014, focusX: 390, focusY: 520 },
        strip: { x0: 694, y0: 326, x1: 899, y1: 1014, focusX: 798, focusY: 620 },
        text: { x0: 128, y0: 1060, x1: 916, y1: 1410, padX: 28, padY: 14, padEndX: 32, padEndY: 24 },
        footer: { x0: 48, y0: 1598, x1: 892, y1: 1658 },
        badge: { cx: 848, cy: 72 },
    };

    const OVERLAY_TEMPLATE_IDS = [
        'pearlescent', 'pearlescent_ribbon', 'sculpted_travertine',
        'sculptural', 'emerald_atelier', 'pearl_gallery',
    ];

    function overlayCanvasBackground(templateId) {
        const map = {
            pearlescent: '#e8f4fc',
            pearlescent_ribbon: '#f3ebe0',
            sculpted_travertine: '#e8e0d4',
            sculptural: '#ebe6dc',
            emerald_atelier: '#e8dcc8',
            pearl_gallery: '#0b1220',
        };
        return map[templateId] || '';
    }

    function footerBoxFromCal(cal, px, py) {
        if (!cal?.footer) return null;
        const f = cal.footer;
        return {
            x: px(f.x0),
            y: py(f.y0),
            width: px(f.x1 - f.x0),
            height: py(f.y1 - f.y0),
        };
    }

    function dealBoxFromCal(cal, px, py) {
        if (!cal?.badge) return null;
        const w = 108;
        const h = 44;
        return {
            x: px(cal.badge.cx) - w,
            y: py(cal.badge.cy),
            width: w,
            height: h,
        };
    }

    function scaleCal(cal, w, h) {
        const sx = w / cal.refW;
        const sy = h / cal.refH;
        return {
            px: (x) => Math.round(x * sx),
            py: (y) => Math.round(y * sy),
            pd: (d) => Math.round(d * sx),
        };
    }

    function splitTextColumnBox(textBox) {
        const h = Math.max(80, textBox.height);
        const y0 = textBox.y;
        return {
            headline: {
                x: textBox.x,
                y: y0,
                width: textBox.width,
                height: Math.round(h * 0.38),
            },
            meta: {
                x: textBox.x,
                y: y0 + Math.round(h * 0.36),
                width: textBox.width,
                height: Math.round(h * 0.32),
            },
            price: {
                x: textBox.x,
                y: y0 + Math.round(h * 0.66),
                width: textBox.width,
                height: Math.max(48, Math.round(h * 0.28)),
            },
        };
    }

    function pearlGalleryBoxes(w, h) {
        const cal = PEARL_GALLERY_CALIBRATION;
        const { px, py, pd } = scaleCal(cal, w, h);
        const circle = (c) => ({ cx: px(c.cx), cy: py(c.cy), d: pd(c.d) });
        const t = cal.text;
        const textCol = {
            x: px(t.x0 + (t.padX || 0)),
            y: py(t.y0 + (t.padY || 0)),
            width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
            height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
        };
        return Object.assign(
            splitTextColumnBox(textCol),
            {
                primaryCircle: circle(cal.primary),
                secondaryCircle: circle(cal.secondary),
                footer: footerBoxFromCal(cal, px, py),
                deal: dealBoxFromCal(cal, px, py),
            },
        );
    }

    function sculpturalTemplateBoxes(w, h) {
        const cal = SCULPTURAL_CALIBRATION;
        const { px, py, pd } = scaleCal(cal, w, h);
        const hero = cal.hero;
        const t = cal.text;
        const textCol = {
            x: px(t.x0 + (t.padX || 0)),
            y: py(t.y0 + (t.padY || 0)),
            width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
            height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
        };
        const circles = cal.circles
            .slice()
            .sort((a, b) => (a.z || 0) - (b.z || 0))
            .map((c) => ({
                cx: px(c.cx),
                cy: py(c.cy),
                d: pd(c.d * (c.inset || 0.97)),
            }));
        return Object.assign(splitTextColumnBox(textCol), {
            hero: {
                x: px(hero.x0),
                y: py(hero.y0),
                width: px(hero.x1 - hero.x0),
                height: py(hero.y1 - hero.y0),
                objX: ((hero.focusX - hero.x0) / (hero.x1 - hero.x0)) * 100,
                objY: ((hero.focusY - hero.y0) / (hero.y1 - hero.y0)) * 100,
            },
            circles,
            footer: footerBoxFromCal(cal, px, py),
            deal: dealBoxFromCal(cal, px, py),
        });
    }

    function emeraldTemplateBoxes(w, h) {
        const cal = EMERALD_CALIBRATION;
        const { px, py } = scaleCal(cal, w, h);
        const box = (b) => ({
            x: px(b.x0),
            y: py(b.y0),
            width: px(b.x1 - b.x0),
            height: py(b.y1 - b.y0),
            objX: ((b.focusX - b.x0) / (b.x1 - b.x0)) * 100,
            objY: ((b.focusY - b.y0) / (b.y1 - b.y0)) * 100,
        });
        const t = cal.text;
        const textCol = {
            x: px(t.x0 + (t.padX || 0)),
            y: py(t.y0 + (t.padY || 0)),
            width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
            height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
        };
        return Object.assign(splitTextColumnBox(textCol), {
            arch: box(cal.arch),
            strip: box(cal.strip),
            footer: footerBoxFromCal(cal, px, py),
            deal: dealBoxFromCal(cal, px, py),
        });
    }

    function resolveSecondaryIndex(imgCount, primaryIdx, secondaryIdx) {
        const n = Math.max(0, imgCount || 0);
        if (!n) return 0;
        const hero = Math.max(0, Math.min(n - 1, primaryIdx || 0));
        let strip = Number.isFinite(parseInt(secondaryIdx, 10))
            ? parseInt(secondaryIdx, 10)
            : (n > 1 ? 1 : 0);
        strip = Math.max(0, Math.min(n - 1, strip));
        if (n > 1 && strip === hero) strip = (hero + 1) % n;
        return strip;
    }

    function sculpturalCircleIndices(imgs, heroIndex, count) {
        const n = (imgs || []).length;
        const want = count != null ? count : 3;
        if (!n) return [];
        const hero = Math.max(0, Math.min(n - 1, heroIndex || 0));
        const picked = [];
        for (let i = 0; i < n && picked.length < want; i += 1) {
            if (i !== hero && imgs[i]) picked.push(i);
        }
        for (let i = 0; picked.length < want && i < n; i += 1) {
            if (imgs[i]) picked.push(i);
        }
        while (picked.length < want && n) {
            picked.push(picked[picked.length - 1] ?? hero);
        }
        return picked.slice(0, want);
    }

    function circleSlotToBox(slot) {
        const d = slot.d;
        return {
            x: Math.round(slot.cx - d / 2),
            y: Math.round(slot.cy - d / 2),
            width: d,
            height: d,
            borderRadius: Math.round(d / 2),
        };
    }

    function makeImageLayer(id, name, geom, imageIndex, opts) {
        const o = opts || {};
        return {
            id,
            type: 'image',
            name,
            visible: true,
            locked: false,
            parentId: null,
            x: geom.x,
            y: geom.y,
            width: geom.width,
            height: geom.height,
            rotation: 0,
            opacity: 1,
            imageIndex: imageIndex != null ? imageIndex : 0,
            templateRole: o.templateRole || '',
            style: {
                objectFit: 'cover',
                cropPanX: o.cropPanX != null ? o.cropPanX : 50,
                cropPanY: o.cropPanY != null ? o.cropPanY : 50,
                cropZoom: 1,
                borderRadius: geom.borderRadius || o.borderRadius || 0,
            },
        };
    }

    function posterBrandContact(conf, ctx) {
        const brand = ctx?.brand || {};
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

    function overlayFooterLine(name, phone) {
        if (name && phone) return `${name}  ·  ${phone}`;
        return phone || name || '';
    }

    function pushTemplateImageLayers(conf, ctx, tpl, boxes, layers, order, w, h) {
        const imgs = ctx.images || [];
        const imgCount = imgs.length;
        const primaryIdx = conf?.primary_image_index ?? 0;

        if (tpl === 'pearl_gallery' && boxes.primaryCircle) {
            const secIdx = resolveSecondaryIndex(imgCount, primaryIdx, conf?.secondary_image_index);
            layers.push(makeImageLayer(
                'hero-image',
                'تصویر شاخص',
                circleSlotToBox(boxes.primaryCircle),
                primaryIdx,
                { templateRole: 'hero' },
            ));
            order.push('hero-image');
            layers.push(makeImageLayer(
                'accent-image',
                'تصویر مکمل',
                circleSlotToBox(boxes.secondaryCircle),
                secIdx,
                { templateRole: 'accent' },
            ));
            order.push('accent-image');
            return;
        }

        if (tpl === 'emerald_atelier' && boxes.arch) {
            const secIdx = resolveSecondaryIndex(imgCount, primaryIdx, conf?.secondary_image_index);
            layers.push(makeImageLayer('hero-image', 'تصویر قوس', boxes.arch, primaryIdx, {
                templateRole: 'hero',
                cropPanX: boxes.arch.objX,
                cropPanY: boxes.arch.objY,
            }));
            order.push('hero-image');
            layers.push(makeImageLayer('strip-image', 'نوار تصویر', boxes.strip, secIdx, {
                templateRole: 'accent',
                cropPanX: boxes.strip.objX,
                cropPanY: boxes.strip.objY,
            }));
            order.push('strip-image');
            return;
        }

        if ((tpl === 'pearlescent_ribbon' || tpl === 'sculpted_travertine') && boxes.hero?.width) {
            const hb = boxes.hero;
            layers.push(makeImageLayer('hero-image', 'تصویر شاخص', {
                x: hb.x,
                y: hb.y,
                width: hb.width,
                height: hb.height,
            }, primaryIdx, {
                templateRole: 'hero',
                cropPanX: hb.objX != null ? hb.objX : 50,
                cropPanY: conf?.crop_y ?? 50,
            }));
            order.push('hero-image');
            return;
        }

        if (tpl === 'sculptural' && boxes.hero && boxes.circles) {
            layers.push(makeImageLayer('hero-image', 'تصویر زمینه', {
                x: boxes.hero.x,
                y: boxes.hero.y,
                width: boxes.hero.width,
                height: boxes.hero.height,
            }, primaryIdx, {
                templateRole: 'hero',
                cropPanX: boxes.hero.objX,
                cropPanY: conf?.crop_y ?? 50,
            }));
            order.push('hero-image');
            const circleIdx = sculpturalCircleIndices(imgs, primaryIdx, boxes.circles.length);
            boxes.circles.forEach((slot, i) => {
                const id = `circle-image-${i + 1}`;
                layers.push(makeImageLayer(
                    id,
                    `دایره ${i + 1}`,
                    circleSlotToBox(slot),
                    circleIdx[i] ?? primaryIdx,
                    { templateRole: 'circle' },
                ));
                order.push(id);
            });
            return;
        }

        const heroBox = boxes.hero || {
            x: 0,
            y: 0,
            width: w,
            height: Math.round(h * ((tpl === 'minimal' || tpl === 'modern') ? 0.48 : 0.72)),
        };
        layers.push(makeImageLayer('hero-image', 'تصویر شاخص', heroBox, primaryIdx, {
            templateRole: 'hero',
            cropPanY: conf?.crop_y ?? 50,
            borderRadius: (tpl === 'minimal' || tpl === 'modern') ? 22 : 0,
        }));
        order.push('hero-image');
    }

    function pearlescentRibbonBoxes(w, h) {
        const cal = {
            refW: 941,
            refH: 1672,
            hero: { x0: 206, y0: 126, x1: 885, y1: 970, focusX: 545, focusY: 460 },
            text: { x0: 218, y0: 1010, x1: 908, y1: 1400, padX: 22, padY: 12, padEndX: 28, padEndY: 18 },
            footer: { x0: 212, y0: 1438, x1: 862, y1: 1605 },
            badge: { cx: 818, cy: 172 },
        };
        const { px, py } = scaleCal(cal, w, h);
        const hero = cal.hero;
        const t = cal.text;
        const textCol = {
            x: px(t.x0 + (t.padX || 0)),
            y: py(t.y0 + (t.padY || 0)),
            width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
            height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
        };
        const split = splitTextColumnBox(textCol);
        return Object.assign(split, {
            hero: {
                x: px(hero.x0),
                y: py(hero.y0),
                width: px(hero.x1 - hero.x0),
                height: py(hero.y1 - hero.y0),
                objX: ((hero.focusX - hero.x0) / (hero.x1 - hero.x0)) * 100,
                objY: ((hero.focusY - hero.y0) / (hero.y1 - hero.y0)) * 100,
            },
            footer: {
                x: px(cal.footer.x0),
                y: py(cal.footer.y0),
                width: px(cal.footer.x1 - cal.footer.x0),
                height: py(cal.footer.y1 - cal.footer.y0),
            },
            deal: dealBoxFromCal(cal, px, py),
        });
    }

    function travertineBoxes(w, h) {
        const cal = {
            refW: 940,
            refH: 1672,
            hero: { x0: 112, y0: 175, x1: 826, y1: 1017, focusX: 470, focusY: 520 },
            text: { x0: 168, y0: 1025, x1: 832, y1: 1390, padX: 26, padY: 16, padEndX: 32, padEndY: 20 },
            footer: { x0: 148, y0: 1495, x1: 792, y1: 1625 },
            badge: { cx: 768, cy: 228 },
        };
        const sx = w / cal.refW;
        const sy = h / cal.refH;
        const pxFn = (x) => Math.round(x * sx);
        const pyFn = (y) => Math.round(y * sy);
        const px = pxFn;
        const py = pyFn;
        const t = cal.text;
        return {
            hero: {
                x: px(cal.hero.x0),
                y: py(cal.hero.y0),
                width: px(cal.hero.x1 - cal.hero.x0),
                height: py(cal.hero.y1 - cal.hero.y0),
                objX: ((cal.hero.focusX - cal.hero.x0) / (cal.hero.x1 - cal.hero.x0)) * 100,
                objY: ((cal.hero.focusY - cal.hero.y0) / (cal.hero.y1 - cal.hero.y0)) * 100,
            },
            footer: footerBoxFromCal(cal, pxFn, pyFn),
            deal: dealBoxFromCal(cal, pxFn, pyFn),
            headline: {
                x: px(t.x0 + (t.padX || 0)),
                y: py(t.y0 + (t.padY || 0)),
                width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
                height: Math.round(py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)) * 0.45),
            },
            meta: {
                x: px(t.x0 + (t.padX || 0)),
                y: py(t.y0 + (t.padY || 0) + py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)) * 0.42),
                width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
                height: Math.round(py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)) * 0.28),
            },
            price: {
                x: px(t.x0 + (t.padX || 0)),
                y: py(t.y1 - (t.padEndY || 0) - py((t.y1 - t.y0) * 0.22)),
                width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
                height: Math.round(py((t.y1 - t.y0) * 0.18)),
            },
        };
    }

    function pearlescentBoxes(w, h) {
        const sidePad = Math.round(w * (72 / 1080));
        const photoH = Math.round(0.455 * h);
        const bodyTop = Math.round(0.47 * h);
        const bodyBottom = Math.round(0.875 * h);
        const footerTop = Math.round(0.878 * h);
        const footerBottom = Math.round(0.985 * h);
        const contentW = w - sidePad * 2;
        const bodyH = Math.max(120, bodyBottom - bodyTop);
        return {
            background: { x: 0, y: 0, width: w, height: h },
            hero: { x: 0, y: 0, width: w, height: photoH },
            headline: {
                x: sidePad,
                y: bodyTop + 8,
                width: contentW,
                height: Math.round(bodyH * 0.28),
            },
            location: {
                x: sidePad,
                y: bodyTop + Math.round(bodyH * 0.3),
                width: contentW,
                height: Math.round(bodyH * 0.1),
            },
            meta: {
                x: sidePad,
                y: bodyTop + Math.round(bodyH * 0.4),
                width: contentW,
                height: Math.round(bodyH * 0.36),
            },
            price: {
                x: sidePad,
                y: bodyTop + Math.round(bodyH * 0.76),
                width: contentW,
                height: Math.round(bodyH * 0.22),
            },
            footer: {
                x: Math.max(0, sidePad - 12),
                y: footerTop,
                width: w - Math.max(0, sidePad - 12) * 2,
                height: Math.max(48, footerBottom - footerTop),
            },
            deal: { x: w - sidePad - 118, y: 36, width: 108, height: 44 },
        };
    }

    function headlineInText(headline, fragment) {
        const h = String(headline || '').trim().toLowerCase();
        const f = String(fragment || '').trim().toLowerCase();
        if (!h || !f) return false;
        return h.includes(f) || f.includes(h);
    }

    /** خطوط مشخصات (عنوان : مقدار) هم‌تراز با پوستر legacy قاب استوری */
    function pearlescentMetaLines(ctx, headline) {
        const features = ctx?.features || [];
        const skipKeys = new Set([
            'location_line', 'price', 'deal_mode', 'file_code',
            'area_label', 'rooms_label',
        ]);
        const lines = [];
        features.forEach((f) => {
            if (!f?.key || skipKeys.has(f.key)) return;
            const val = String(f.value || '').trim();
            if (!val || headlineInText(headline, val)) return;
            const label = String(f.label || '').trim();
            lines.push(label ? `${label} : ${val}` : val);
        });
        if (lines.length) return lines.slice(0, 6);
        const p = ctx?.property || {};
        const fallback = [];
        if (p.property_type && !headlineInText(headline, p.property_type)) {
            fallback.push(`نوع ملک : ${p.property_type}`);
        }
        if (p.floor_label && !headlineInText(headline, p.floor_label)) {
            fallback.push(`طبقه : ${p.floor_label}`);
        }
        if (p.build_year_label && !headlineInText(headline, p.build_year_label)) {
            fallback.push(`سال ساخت : ${p.build_year_label}`);
        }
        (p.detail_chips || []).slice(0, 4).forEach((chip) => {
            const t = String(chip || '').trim();
            if (t && !headlineInText(headline, t)) fallback.push(t);
        });
        return fallback.slice(0, 6);
    }

    /** قاب PNG باید زیر متن باشد (مثل legacy: overlay z-index 2، متن z-index 3). */
    function fixTemplateFrameStackOrder(scene) {
        if (!scene?.layerOrder?.length) return scene;
        const frameId = 'template-frame';
        if (!scene.layers.some((l) => l.id === frameId)) return scene;
        const order = scene.layerOrder.filter((id) => id !== frameId);
        let lastImgIdx = -1;
        order.forEach((id, idx) => {
            const layer = scene.layers.find((l) => l.id === id);
            if (layer?.type === 'image') lastImgIdx = idx;
        });
        const insertAt = lastImgIdx >= 0 ? lastImgIdx + 1 : 0;
        order.splice(insertAt, 0, frameId);
        scene.layerOrder = order;
        return scene;
    }

    /** نشان نوع معامله روی ناحیهٔ عکس — بالای قاب. */
    function fixDealBadgeOnTop(scene) {
        if (!scene?.layerOrder?.length) return scene;
        if (!scene.layers.some((l) => l.id === 'deal-1')) return scene;
        const order = scene.layerOrder.filter((id) => id !== 'deal-1');
        order.push('deal-1');
        scene.layerOrder = order;
        return scene;
    }

    function normalizeSceneLayerOrder(scene) {
        fixTemplateFrameStackOrder(scene);
        fixDealBadgeOnTop(scene);
        return scene;
    }

    function storyBoxes(templateId, w, h) {
        if (templateId === 'pearlescent') return pearlescentBoxes(w, h);
        if (templateId === 'pearlescent_ribbon') return pearlescentRibbonBoxes(w, h);
        if (templateId === 'sculpted_travertine') return travertineBoxes(w, h);
        if (templateId === 'pearl_gallery') return pearlGalleryBoxes(w, h);
        if (templateId === 'sculptural') return sculpturalTemplateBoxes(w, h);
        if (templateId === 'emerald_atelier') return emeraldTemplateBoxes(w, h);
        const pad = Math.round(w * 0.055);
        if (templateId === 'minimal' || templateId === 'modern') {
            const headH = Math.round(h * 0.12);
            const footBlock = Math.round(h * 0.28);
            const imgTop = pad + headH + 24;
            const imgH = Math.max(320, h - imgTop - footBlock - pad);
            return {
                background: { x: 0, y: 0, width: w, height: h },
                headline: { x: pad, y: pad + 8, width: w - pad * 2 - 120, height: headH },
                deal: { x: w - pad - 108, y: pad + 12, width: 100, height: 44 },
                hero: { x: pad, y: imgTop, width: w - pad * 2, height: imgH },
                price: { x: pad, y: h - pad - footBlock + 8, width: w - pad * 2, height: 88 },
                meta: { x: pad, y: h - pad - footBlock + 96, width: w - pad * 2, height: 64 },
                brand: { x: pad, y: h - pad - 72, width: w - pad * 2, height: 52 },
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

        const Assets = global.PCSAssets;
        const p = ctx.property || {};
        const headlineText = (conf?.headline || p.headline || '').trim();
        const isPearlescent = tpl === 'pearlescent';
        const isRibbon = tpl === 'pearlescent_ribbon';
        const isTravertine = tpl === 'sculpted_travertine';
        const isPearl = tpl === 'pearl_gallery';
        const isSculptural = tpl === 'sculptural';
        const isEmerald = tpl === 'emerald_atelier';
        const pearlInk = '#f4f1eb';
        const pearlPriceInk = '#e8c9a8';
        const pearlescentInk = '#0a3560';
        const layers = [];
        const order = [];
        let templateFrameLayer = null;

        const overlayBg = overlayCanvasBackground(tpl);
        if (overlayBg) {
            layers.push({
                id: 'bg-fill',
                type: 'shape',
                name: 'پس‌زمینه',
                visible: true,
                locked: true,
                parentId: null,
                x: 0,
                y: 0,
                width: w,
                height: h,
                rotation: 0,
                opacity: 1,
                style: { background: overlayBg },
            });
            order.push('bg-fill');
        } else if (boxes.background && (tpl === 'minimal' || tpl === 'modern' || isPearlescent)) {
            layers.push({
                id: 'bg-fill',
                type: 'shape',
                name: 'پس‌زمینه',
                visible: true,
                locked: true,
                parentId: null,
                x: boxes.background.x,
                y: boxes.background.y,
                width: boxes.background.width,
                height: boxes.background.height,
                rotation: 0,
                opacity: 1,
                style: { background: isPearlescent ? '#e8f4fc' : '#f6f4f0' },
            });
            order.push('bg-fill');
        }

        pushTemplateImageLayers(conf, ctx, tpl, boxes, layers, order, w, h);

        if (ctx.overlayUrl) {
            templateFrameLayer = {
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
                assetRef: Assets ? Assets.templateAssetId(tpl) : tpl,
            };
            layers.push(templateFrameLayer);
            order.push('template-frame');
        }

        if (headlineText) {
            const hl = layerText('headline-1', 'عنوان', boxes.headline, {
                text: headlineText,
                templateRole: 'headline',
                fontSize: Math.round(h * (tpl === 'sculpted_travertine' ? 0.034 : (isPearlescent ? 0.038 : 0.042))),
                fontWeight: conf?.headline_weight || 900,
                fill: isPearl ? pearlInk
                    : (isRibbon ? '#f8fafc' : (isSculptural || isEmerald ? '#f4f1eb' : (isPearlescent ? pearlescentInk
                    : ((tpl === 'minimal' || tpl === 'modern') ? '#1e293b' : (isTravertine ? '#1c1917' : '#ffffff'))))),
            });
            layers.push(hl);
            order.push(hl.id);
        }

        const dealLabel = String(p.deal_mode || p.deal_label || '').trim();
        if (dealLabel && boxes.deal) {
            layers.push(layerText('deal-1', 'نوع معامله', boxes.deal, {
                text: dealLabel,
                bound: true,
                binding: { source: 'property', field: 'deal_mode', mode: 'linked' },
                fontSize: 22,
                fontWeight: 800,
                fill: '#ffffff',
                style: {
                    textPreset: 'capsule',
                    background: '#7c3aed',
                    borderRadius: 999,
                    align: 'center',
                },
            }));
            order.push('deal-1');
        }

        if (isPearlescent && boxes.location) {
            const locVal = String(p.location_line || p.city || '').trim();
            if (locVal) {
                layers.push(layerText('location-1', 'موقعیت', boxes.location, {
                    text: locVal,
                    bound: true,
                    binding: { source: 'property', field: 'location_line', mode: 'linked' },
                    fontSize: 34,
                    fontWeight: 700,
                    fill: pearlescentInk,
                }));
                order.push('location-1');
            }
        }

        const metaParts = [];
        if (isRibbon || isTravertine || isSculptural || isEmerald || isPearl) {
            const loc = String(p.location_line || p.city || '').trim();
            if (loc) metaParts.push(loc);
            if (p.property_type) metaParts.push(p.property_type);
            if (p.area_label) metaParts.push(p.area_label);
            (p.detail_chips || []).slice(0, 6).forEach((chip) => {
                const t = String(chip || '').trim();
                if (t) metaParts.push(t);
            });
        } else if (!isPearlescent) {
            if (p.rooms_label) metaParts.push(p.rooms_label);
            if (p.area_label) metaParts.push(p.area_label);
            if (p.floor_label) metaParts.push(p.floor_label);
            if (!metaParts.length) {
                if (p.location_line) metaParts.push(p.location_line);
                if (p.property_type) metaParts.push(p.property_type);
            }
        }
        const pearlescentMeta = isPearlescent ? pearlescentMetaLines(ctx, headlineText) : [];
        if (isPearlescent && pearlescentMeta.length && boxes.meta) {
            layers.push(layerText('meta-1', 'مشخصات', boxes.meta, {
                text: pearlescentMeta.join('  ·  '),
                templateRole: 'meta',
                fontSize: 28,
                fontWeight: 800,
                fill: pearlescentInk,
                style: { align: 'right', lineHeight: 1.45 },
            }));
            order.push('meta-1');
        } else if (metaParts.length) {
            layers.push(layerText('meta-1', 'مشخصات', boxes.meta, {
                text: metaParts.slice(0, 4).join(' · '),
                templateRole: 'meta',
                fontSize: Math.round(h * 0.019),
                fontWeight: 700,
                fill: (tpl === 'minimal' || tpl === 'modern') ? '#334155'
                    : (isRibbon ? 'rgba(248,250,252,.88)' : (tpl === 'sculpted_travertine' ? 'rgba(28,25,23,.72)' : (isPearl || isSculptural || isEmerald ? 'rgba(244,241,235,.86)' : 'rgba(255,255,255,.9)'))),
            }));
            order.push('meta-1');
        }

        const priceLabel = p.price?.show ? p.price.label : '';
        if (priceLabel && boxes.price) {
            layers.push(layerText('price-1', 'قیمت', boxes.price, {
                text: priceLabel,
                bound: true,
                binding: { source: 'property', field: 'price', mode: 'linked' },
                templateRole: 'price',
                fontSize: Math.round(h * (isPearlescent ? 0.026 : 0.028)),
                fontWeight: conf?.price_weight || 900,
                fill: isPearl ? pearlPriceInk
                    : (isRibbon ? '#fde68a' : (isPearlescent ? pearlescentInk
                    : ((tpl === 'minimal' || tpl === 'modern') ? '#7c3aed' : (isTravertine ? '#92400e' : '#ffffff')))),
            }));
            order.push('price-1');
        }

        const { name: brandName, phone } = posterBrandContact(conf, ctx);
        if (isPearlescent && boxes.footer) {
            const cta = phone ? 'هماهنگی بازدید' : 'مشاوره رایگان';
            const footText = phone && brandName
                ? `${brandName}  ·  ${phone}`
                : (phone ? `${cta}  ·  ${phone}` : (brandName || cta));
            layers.push(layerText('footer-1', 'پاورقی', boxes.footer, {
                text: footText,
                bound: true,
                binding: { source: 'brand', field: 'contact_footer', mode: 'linked' },
                fontSize: 28,
                fontWeight: 800,
                fill: '#ffffff',
                style: { align: 'center' },
            }));
            order.push('footer-1');
        } else if (boxes.footer && (isRibbon || isTravertine || isSculptural || isEmerald || isPearl)) {
            let footFill = '#64748b';
            let footSize = Math.round(h * 0.019);
            if (isRibbon) {
                footFill = '#0f3d42';
                footSize = Math.round(h * 0.023);
            } else if (isSculptural) {
                footFill = 'rgba(255,255,255,.92)';
                footSize = Math.round(h * 0.016);
            } else if (isEmerald) {
                footFill = 'rgba(255,255,255,.92)';
                footSize = Math.round(h * 0.015);
            } else if (isPearl) {
                footFill = '#1e293b';
                footSize = Math.round(h * 0.0155);
            }
            layers.push(layerText('footer-1', 'تماس مشاور', boxes.footer, {
                text: overlayFooterLine(brandName, phone),
                bound: true,
                binding: { source: 'brand', field: 'contact_footer', mode: 'linked' },
                templateRole: 'footer',
                fontSize: footSize,
                fontWeight: 800,
                fill: footFill,
                style: { align: 'right', direction: 'rtl' },
            }));
            order.push('footer-1');
        } else if ((brandName || phone) && boxes.brand) {
            layers.push(layerText('brand-1', 'برند', boxes.brand, {
                text: [brandName, phone].filter(Boolean).join(' · '),
                fontSize: 26,
                fontWeight: 700,
                fill: '#64748b',
            }));
            order.push('brand-1');
        }

        scene.layers = layers;
        scene.layerOrder = order;
        normalizeSceneLayerOrder(scene);
        scene.renderMode = layers.length ? 'layers' : 'legacy';
        scene.templateBuild = layoutRevisionForTemplate(tpl);
        return scene;
    }

    function layoutRevisionForTemplate(templateId) {
        if (OVERLAY_TEMPLATE_IDS.includes(templateId)) return 7;
        return 3;
    }

    function sceneMissingTemplateLayers(scene, templateId) {
        if (!scene?.layers?.length) return true;
        if (OVERLAY_TEMPLATE_IDS.includes(templateId)) {
            if (!scene.layers.some((l) => l.id === 'template-frame')) return true;
            if (!scene.layers.some((l) => l.id === 'bg-fill')) return true;
            if (!scene.layers.some((l) => l.id === 'footer-1')) return true;
        }
        if (templateId === 'pearl_gallery') {
            return !scene.layers.some((l) => l.id === 'accent-image');
        }
        if (templateId === 'emerald_atelier') {
            return !scene.layers.some((l) => l.id === 'strip-image');
        }
        if (templateId === 'sculptural') {
            return !scene.layers.some((l) => l.id === 'circle-image-1');
        }
        return false;
    }

    function mergeMissingTemplateLayers(scene, conf, ctx, baseScene) {
        if (!scene?.layers?.length) {
            return buildInitialScene(conf, ctx, baseScene);
        }
        const tpl = scene.templateId || ctx.templateId;
        const targetBuild = layoutRevisionForTemplate(tpl);
        if ((scene.templateBuild || 0) >= targetBuild && !sceneMissingTemplateLayers(scene, tpl)) {
            return normalizeSceneLayerOrder(scene);
        }
        const fresh = buildInitialScene(conf, ctx, baseScene);
        const have = new Set(scene.layers.map((l) => l.id));
        const order = scene.layerOrder?.length ? scene.layerOrder.slice() : scene.layers.map((l) => l.id);
        const layoutIds = new Set([
            'bg-fill', 'hero-image', 'accent-image', 'strip-image', 'template-frame', 'headline-1', 'deal-1',
            'location-1', 'meta-1', 'price-1', 'footer-1', 'brand-1',
        ]);
        fresh.layers.forEach((layer) => {
            if (layer?.id?.startsWith('circle-image-')) layoutIds.add(layer.id);
        });
        const overlayTpl = ['pearlescent', 'pearlescent_ribbon', 'pearl_gallery', 'sculptural', 'emerald_atelier', 'sculpted_travertine'].includes(tpl);
        fresh.layers.forEach((layer) => {
            const existing = scene.layers.find((l) => l.id === layer.id);
            if (existing && layoutIds.has(layer.id)) {
                existing.x = layer.x;
                existing.y = layer.y;
                existing.width = layer.width;
                existing.height = layer.height;
                if (layer.style) {
                    existing.style = Object.assign(existing.style || {}, layer.style);
                }
                if (layer.type === 'shape' && layer.style) {
                    existing.style = layer.style;
                }
                if (existing.type === 'image' && layer.imageIndex != null && existing.templateRole) {
                    existing.imageIndex = layer.imageIndex;
                }
                if (existing.type === 'image' && existing.templateRole && layer.style) {
                    existing.style = Object.assign(existing.style || {}, {
                        cropPanX: layer.style.cropPanX,
                        cropPanY: layer.style.cropPanY,
                        objectFit: layer.style.objectFit || existing.style?.objectFit,
                    });
                }
                if (overlayTpl && existing.type !== 'bound_text' && layer.text != null && layer.templateRole) {
                    existing.text = layer.text;
                }
            }
            if (layer && !have.has(layer.id)) {
                scene.layers.push(layer);
                const idx = fresh.layerOrder.indexOf(layer.id);
                order.splice(Math.min(idx >= 0 ? idx : order.length, order.length), 0, layer.id);
                have.add(layer.id);
            }
        });
        scene.layerOrder = order;
        scene.templateBuild = targetBuild;
        return normalizeSceneLayerOrder(scene);
    }

    function addFeatureLayer(scene, catalogEntry, docPoint, preset) {
        const SchemaRef = global.PCSSchema;
        const BindingsRef = global.PCSBindings;
        const id = SchemaRef.uid('feat');
        const displayText = BindingsRef?.featureDisplayPlain
            ? BindingsRef.featureDisplayPlain(catalogEntry)
            : (catalogEntry.value || '');
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
            x: Math.max(0, docPoint.x - 200),
            y: Math.max(0, docPoint.y - 24),
            width: 440,
            height: preset === 'price' ? 88 : 56,
            rotation: 0,
            opacity: 1,
            text: displayText,
            binding: { source: 'property', field: catalogEntry.key, mode: 'linked' },
            style,
        };
        scene.layers.push(layer);
        scene.layerOrder.push(id);
        return layer;
    }

    function resolveSceneForPreview(conf, ctx) {
        const SchemaRef = global.PCSSchema;
        if (!SchemaRef) return conf?.scene || null;
        const templateId = ctx.templateId || conf?.templateId || 'pearlescent';
        const formatKey = ctx.formatKey || 'story';
        const formats = ctx.formats || {};
        const base = SchemaRef.emptyScene(templateId, formatKey, formats);
        let scene;
        if (conf?.scene && conf.scene.schemaVersion >= 2) {
            scene = SchemaRef.normalizeScene(conf.scene, templateId, formatKey, formats);
            scene = mergeMissingTemplateLayers(scene, conf, ctx, base);
        } else {
            scene = buildInitialScene(conf, ctx, base);
        }
        return normalizeSceneLayerOrder(scene);
    }

    global.PCSTemplateScenes = {
        buildInitialScene,
        mergeMissingTemplateLayers,
        resolveSceneForPreview,
        addFeatureLayer,
        normalizeSceneLayerOrder,
        storyBoxes,
        overlayCanvasBackground,
    };
}(typeof window !== 'undefined' ? window : globalThis));
