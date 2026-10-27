/**
 * استودیوی هوشمند ملک — پوستر HTML/CSS + html2canvas برای خروجی
 */
(function () {
    'use strict';

    const cfg = window.PCS_CONFIG || {};
    if (!cfg.propertyId) return;

    const FORMATS = {
        story: { w: 1080, h: 1920, cls: '' },
        post: { w: 1080, h: 1350, cls: 'pcs-canvas--post' },
        square: { w: 1080, h: 1080, cls: 'pcs-canvas--square' },
    };
    const TEMPLATES = ['luxury', 'minimal', 'gallery', 'bold'];
    const TEMPLATE_META = {
        luxury: { label: 'لوکس', icon: 'fa-gem' },
        minimal: { label: 'مینیمال', icon: 'fa-feather' },
        gallery: { label: 'چندتصویری', icon: 'fa-images' },
        bold: { label: 'تبلیغاتی', icon: 'fa-bolt' },
    };
    const FORMAT_META = {
        story: { label: 'استوری', sub: '1080×1920', icon: 'fa-mobile-screen' },
        post: { label: 'پست', sub: '1080×1350', icon: 'fa-image' },
        square: { label: 'مربع', sub: '1080×1080', icon: 'fa-square' },
    };
    const PCS_FONT_STACK = "'Vazirmatn', Tahoma, 'Segoe UI', sans-serif";
    const PCS_FONTS = {
        vazirmatn: { label: 'وزیرمتن', family: "'Vazirmatn', Tahoma, sans-serif", load: '400 32px Vazirmatn' },
        estedad: { label: 'استعداد', family: "'Estedad', Vazirmatn, sans-serif", load: '700 32px Estedad' },
        lalezar: { label: 'لاله‌زار', family: "'Lalezar', Vazirmatn, sans-serif", load: '400 32px Lalezar' },
        markazi: { label: 'مرکزی', family: "'Markazi Text', Vazirmatn, serif", load: '700 32px \"Markazi Text\"' },
        gulzar: { label: 'گلزار', family: "'Gulzar', Vazirmatn, serif", load: '400 32px Gulzar' },
    };

    function posterFieldDefaults(imgs) {
        const count = (imgs || []).length;
        const pipDefault = count > 1 ? 1 : 0;
        return {
            headline: '',
            primary_image_index: 0,
            image_order: (imgs || []).map((_, i) => i),
            crop_y: 50,
            img_brightness: 100,
            img_blur: 0,
            img_opacity: 100,
            font_key: 'vazirmatn',
            headline_scale: 100,
            price_scale: 100,
            pip_enabled: false,
            pip_image_index: pipDefault,
            pip_corner: 'br',
            pip_size: 'm',
            pip_shape: 'rounded',
            pip_crop_y: 50,
            pip_border: 'light',
            pip_tilt: -4,
            hero_vignette: 0,
            hero_warmth: 'neutral',
        };
    }

    const COMPOSITION_PRESETS = {
        pip_classic: {
            pip_enabled: true, pip_corner: 'br', pip_size: 'm', pip_shape: 'rounded',
            pip_border: 'light', pip_tilt: -5, hero_vignette: 22, hero_warmth: 'neutral',
        },
        magazine: {
            pip_enabled: true, pip_corner: 'bl', pip_size: 'l', pip_shape: 'card',
            pip_border: 'brand', pip_tilt: 6, hero_vignette: 35, hero_warmth: 'warm',
        },
        cinematic: {
            pip_enabled: false, hero_vignette: 58, hero_warmth: 'cool', img_brightness: 90, img_blur: 0,
        },
        clean: {
            pip_enabled: false, hero_vignette: 0, hero_warmth: 'neutral', img_brightness: 100, pip_tilt: 0,
        },
    };

    function normalizePosterConfig(raw, imgs) {
        const base = posterFieldDefaults(imgs);
        if (!raw || typeof raw !== 'object') return base;
        const merged = { ...base, ...raw, image_order: (raw.image_order && raw.image_order.length) ? raw.image_order.slice() : base.image_order };
        const pIdx = parseInt(merged.primary_image_index, 10);
        merged.primary_image_index = Number.isFinite(pIdx) ? pIdx : 0;
        const crop = parseInt(merged.crop_y, 10);
        merged.crop_y = Number.isFinite(crop) ? Math.min(100, Math.max(0, crop)) : 50;
        merged.pip_enabled = !!merged.pip_enabled;
        const pipIdx = parseInt(merged.pip_image_index, 10);
        merged.pip_image_index = Number.isFinite(pipIdx) ? pipIdx : 0;
        const pipCrop = parseInt(merged.pip_crop_y, 10);
        merged.pip_crop_y = Number.isFinite(pipCrop) ? Math.min(100, Math.max(0, pipCrop)) : 50;
        const tilt = parseInt(merged.pip_tilt, 10);
        merged.pip_tilt = Number.isFinite(tilt) ? Math.min(12, Math.max(-12, tilt)) : 0;
        const vig = parseInt(merged.hero_vignette, 10);
        merged.hero_vignette = Number.isFinite(vig) ? Math.min(80, Math.max(0, vig)) : 0;
        const warmth = merged.hero_warmth;
        merged.hero_warmth = warmth === 'cool' || warmth === 'warm' ? warmth : 'neutral';
        const pipCorner = merged.pip_corner;
        merged.pip_corner = ['br', 'bl', 'tr', 'tl'].includes(pipCorner) ? pipCorner : 'br';
        const pipSize = merged.pip_size;
        merged.pip_size = pipSize === 's' || pipSize === 'l' ? pipSize : 'm';
        const pipShape = merged.pip_shape;
        merged.pip_shape = pipShape === 'circle' || pipShape === 'card' ? pipShape : 'rounded';
        const pipBorder = merged.pip_border;
        merged.pip_border = pipBorder === 'brand' || pipBorder === 'gold' ? pipBorder : 'light';
        return merged;
    }

    function editorControlsEl() {
        return $('#pcsEditorControls');
    }

    function pcsFontFamily(conf) {
        const key = conf?.font_key || 'vazirmatn';
        return (PCS_FONTS[key] || PCS_FONTS.vazirmatn).family;
    }

    function posterFontSize(conf, px, role) {
        const scale = role === 'price' ? (conf.price_scale ?? 100) : (conf.headline_scale ?? 100);
        return Math.max(10, Math.round(px * scale / 100));
    }

    function pcsTextStyle(extra, conf) {
        return `font-family:${pcsFontFamily(conf)};direction:rtl;unicode-bidi:plaintext;text-rendering:optimizeLegibility;${extra || ''}`;
    }

    let fontsReady = false;

    async function ensurePersianFonts() {
        if (fontsReady) return;
        if (!document.fonts || !document.fonts.load) return;
        try {
            const loads = [
                '400 16px Vazirmatn', '700 48px Vazirmatn',
                ...Object.values(PCS_FONTS).map((f) => f.load),
            ];
            await Promise.all(loads.map((spec) => document.fonts.load(spec)));
            await document.fonts.ready;
            fontsReady = true;
        } catch (_) { /* ignore */ }
    }

    function applyFontToSubtree(root) {
        if (!root) return;
        const canvas = root.classList?.contains('pcs-canvas') ? root : root.querySelector?.('.pcs-canvas');
        const key = canvas?.dataset?.fontKey || 'vazirmatn';
        const family = pcsFontFamily({ font_key: key });
        root.style.fontFamily = family;
        root.style.direction = 'rtl';
        const targets = canvas ? [canvas, ...canvas.querySelectorAll('*')] : [root, ...root.querySelectorAll('*')];
        targets.forEach((node) => {
            if (node.style) node.style.fontFamily = family;
        });
    }

    function createExportHost(html, formatKey) {
        const fmt = FORMATS[formatKey] || FORMATS.story;
        const host = document.createElement('div');
        host.className = 'pcs-export-host';
        host.style.cssText = `position:fixed;left:0;top:0;width:${fmt.w}px;height:${fmt.h}px;overflow:hidden;opacity:0;pointer-events:none;z-index:-1;`;
        host.innerHTML = html;
        document.body.appendChild(host);
        applyFontToSubtree(host.querySelector('.pcs-canvas'));
        armImagesForExport(host);
        return host;
    }
    const VIS_KEYS = [
        ['price', 'قیمت'], ['neighborhood', 'محله'], ['area', 'متراژ'], ['bedrooms', 'خواب'],
        ['floor', 'طبقه'], ['amenities', 'امکانات'], ['consultant_name', 'نام مشاور'],
        ['contact_phone', 'شماره تماس'], ['file_code', 'کد فایل'],
    ];
    const VIS_ICONS = {
        price: 'fa-tag',
        neighborhood: 'fa-location-dot',
        area: 'fa-ruler-combined',
        bedrooms: 'fa-bed',
        floor: 'fa-layer-group',
        amenities: 'fa-star',
        consultant_name: 'fa-user-tie',
        contact_phone: 'fa-phone',
        file_code: 'fa-barcode',
    };

    const state = {
        session: null,
        draft: null,
        format: 'story',
        editorTemplate: null,
        saveTimer: null,
        libsLoaded: false,
        brandFieldsBound: false,
        visTogglesBound: false,
        previewTemplate: null,
        editorBuffer: null,
        editorSnapshot: null,
        editorDirty: false,
    };

    const $ = (sel, root) => (root || document).querySelector(sel);
    const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

    function csrf() {
        if (cfg.csrf) return cfg.csrf;
        const inp = document.querySelector('[name=csrfmiddlewaretoken]');
        if (inp?.value) return inp.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function toast(msg) {
        if (window.wsToast) window.wsToast(msg);
        else if (msg) console.log(msg);
    }

    function visibleData() {
        const p = { ...(state.session?.property || {}) };
        const vis = state.draft?.brand_override?.visibility || state.session?.brand_effective?.visibility || {};
        if (!vis.price) p.price = { show: false, label: '' };
        if (!vis.neighborhood) p.location_line = p.city || '';
        if (!vis.area) p.area_label = '';
        if (!vis.bedrooms) p.rooms_label = '';
        if (!vis.amenities) p.amenities = [];
        if (!vis.file_code) p.file_code = '';
        return { property: p, brand: mergeBrand(), vis };
    }

    function mergeBrand() {
        const base = state.session?.brand_effective || state.session?.brand || {};
        const ov = state.draft?.brand_override || {};
        const out = JSON.parse(JSON.stringify(base));
        ['brand_name', 'consultant_name', 'contact_phone', 'instagram', 'logo_url'].forEach((k) => {
            if (ov[k]) out[k] = ov[k];
        });
        if (ov.colors) out.colors = { ...out.colors, ...ov.colors };
        if (ov.visibility) out.visibility = { ...out.visibility, ...ov.visibility };
        return out;
    }

    function posterConfigFromDraft(tpl) {
        const posters = state.draft?.posters || {};
        return normalizePosterConfig(posters[tpl], propertyImageList());
    }

    function posterConfig(tpl) {
        if (state.editorBuffer && state.editorTemplate === tpl) return state.editorBuffer;
        return posterConfigFromDraft(tpl);
    }

    function buildGalleryImageOrder(imgs, slots) {
        const used = new Set();
        const order = [];
        slots.forEach((i) => {
            const idx = parseInt(i, 10);
            if (Number.isFinite(idx) && idx >= 0 && idx < imgs.length && !used.has(idx)) {
                order.push(idx);
                used.add(idx);
            }
        });
        imgs.forEach((_, i) => {
            if (!used.has(i)) order.push(i);
        });
        return order.length ? order : imgs.map((_, i) => i);
    }

    function syncEditorDirtyFlag() {
        if (!state.editorBuffer) {
            state.editorDirty = false;
            return;
        }
        state.editorDirty = state.editorSnapshot !== JSON.stringify(state.editorBuffer);
        const bar = $('#pcsEditor');
        bar?.classList.toggle('pcs-editor--dirty', state.editorDirty);
    }

    function initEditorBuffer(tpl) {
        const imgs = propertyImageList();
        state.editorBuffer = { ...normalizePosterConfig(posterConfigFromDraft(tpl), imgs) };
        state.editorSnapshot = JSON.stringify(state.editorBuffer);
        state.editorDirty = false;
        $('#pcsEditor')?.classList.remove('pcs-editor--dirty');
    }

    function propertyImageList() {
        const p = state.session?.property || {};
        const list = [...(p.images || [])].filter(Boolean);
        const cover = p.cover_image || '';
        if (cover && !list.includes(cover)) list.unshift(cover);
        if (!list.length && cover) list.push(cover);
        return list;
    }

    function orderedImages(tpl) {
        const imgs = propertyImageList();
        const conf = posterConfig(tpl || 'luxury');
        const order = (conf.image_order && conf.image_order.length) ? conf.image_order : imgs.map((_, i) => i);
        return order.filter((i) => i >= 0 && i < imgs.length).map((i) => imgs[i]);
    }

    function defaultPropertyHeadline() {
        const p = state.session?.property || {};
        return String(p.headline || p.title || '').trim();
    }

    function editorImageOrderForGallery(imgs, conf) {
        const base = imgs.map((_, i) => i);
        const raw = (conf.image_order && conf.image_order.length) ? conf.image_order.slice(0, 3) : base.slice(0, 3);
        while (raw.length < 3) {
            const next = base.find((i) => !raw.includes(i));
            raw.push(next != null ? next : 0);
        }
        return raw.slice(0, 3);
    }

    function editorGallerySlotGrid(imgs, galleryOrder) {
        if (!imgs.length) return '';
        return [0, 1, 2].map((slot) => `
            <div class="pcs-editor__gallery-slot">
                <span class="pcs-editor__gallery-slot-label">اسلاید ${slot + 1}</span>
                <input type="hidden" data-pcs-gallery-slot="${slot}" value="${galleryOrder[slot]}">
                <div class="pcs-editor__img-grid pcs-editor__img-grid--compact" role="radiogroup" aria-label="تصویر اسلاید ${slot + 1}">
                    ${imgs.map((url, i) => `
                    <button type="button" class="pcs-editor__img-tile${galleryOrder[slot] === i ? ' is-selected' : ''}"
                        data-pcs-gallery-slot-pick="${slot}" data-pcs-img-idx="${i}" aria-pressed="${galleryOrder[slot] === i}">
                        <img src="${esc(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
                        <span class="pcs-editor__img-tile-num">${i + 1}</span>
                    </button>`).join('')}
                </div>
            </div>`).join('');
    }

    function renderEditorFormatBar(tpl) {
        const bar = $('#pcsEditFormatBar');
        if (!bar) return;
        bar.innerHTML = '';
        Object.entries(FORMAT_META).forEach(([key, meta]) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'pcs-editor__format-btn' + (state.format === key ? ' is-active' : '');
            b.innerHTML = `<i class="fas ${meta.icon}" aria-hidden="true"></i><span>${esc(meta.label)}</span><small>${esc(meta.sub)}</small>`;
            b.addEventListener('click', () => {
                state.format = key;
                if (state.draft) state.draft.format = key;
                renderEditorFormatBar(tpl);
                const fmtMeta = FORMAT_META[key];
                const fmtPill = $('#pcsEditorFormatPill');
                if (fmtPill && fmtMeta) {
                    fmtPill.innerHTML = `<i class="fas ${fmtMeta.icon}" aria-hidden="true"></i> ${esc(fmtMeta.label)} · ${esc(fmtMeta.sub)}`;
                }
                refreshEditorPreview(tpl);
            });
            bar.appendChild(b);
        });
    }

    function editorThumbGrid(imgs, selectedIndex, field) {
        if (!imgs.length) {
            return `<p class="pcs-editor__empty">تصویری برای این فایل ثبت نشده است.</p>`;
        }
        const gridAttr = field === 'primary' ? ' data-pcs-primary-grid' : field === 'pip' ? ' data-pcs-pip-grid' : '';
        return `<div class="pcs-editor__img-grid" role="radiogroup" aria-label="انتخاب تصویر"${gridAttr}>
            ${imgs.map((url, i) => `
            <button type="button" class="pcs-editor__img-tile${i === selectedIndex ? ' is-selected' : ''}"
                data-pcs-img-idx="${i}" aria-pressed="${i === selectedIndex}">
                <img src="${esc(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
                <span class="pcs-editor__img-tile-num">${i + 1}</span>
            </button>`).join('')}
        </div>`;
    }

    function setEditorMobPane(pane) {
        const root = $('#pcsEditor');
        if (!root) return;
        const mob = isMobileViewport();
        root.querySelectorAll('.pcs-editor__mob-tab').forEach((el) => {
            const on = el.getAttribute('data-pcs-editor-pane') === pane;
            el.classList.toggle('is-active', on);
            el.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        root.querySelectorAll('.pcs-editor__preview-pane, .pcs-editor__settings-pane').forEach((el) => {
            if (!mob) {
                el.classList.add('is-active');
                return;
            }
            el.classList.toggle('is-active', el.getAttribute('data-pcs-editor-pane') === pane);
        });
        if (pane === 'preview' || !mob) {
            const prev = $('#pcsEditorPreview');
            if (prev) whenImagesReady(prev, () => scalePreviewCanvas(prev, state.format, mob ? 0.92 : 1));
        }
    }

    function posterImg(url, style, conf) {
        if (!url) return '';
        const c = conf || {};
        const parts = [];
        if (c.img_brightness != null && c.img_brightness !== 100) parts.push(`brightness(${c.img_brightness}%)`);
        if (c.img_blur > 0) parts.push(`blur(${c.img_blur}px)`);
        const op = (c.img_opacity ?? 100) / 100;
        const fx = parts.length ? `filter:${parts.join(' ')};` : '';
        const opx = op < 0.999 ? `opacity:${op};` : '';
        return `<img src="${esc(url)}" alt="" decoding="async" referrerpolicy="no-referrer" style="${style}${fx}${opx}">`;
    }

    function primaryImageUrl(conf) {
        const list = propertyImageList();
        if (!list.length) return '';
        const idx = Math.min(list.length - 1, Math.max(0, conf.primary_image_index || 0));
        return list[idx] || list[0];
    }

    function moveInOrder(order, pos, dir) {
        const next = order.slice();
        const to = pos + dir;
        if (to < 0 || to >= next.length) return next;
        const t = next[pos];
        next[pos] = next[to];
        next[to] = t;
        return next;
    }

    function editorImageOrderPanel(imgs, order) {
        const ord = (order && order.length) ? order.filter((i) => i >= 0 && i < imgs.length) : imgs.map((_, i) => i);
        imgs.forEach((_, i) => { if (!ord.includes(i)) ord.push(i); });
        return `<div class="pcs-editor__order-list" id="pcsEditImageOrder">
            ${ord.map((imgIdx, pos) => `
            <div class="pcs-editor__order-row">
                <span class="pcs-editor__order-rank">${pos + 1}</span>
                <img src="${esc(imgs[imgIdx])}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
                <span class="pcs-editor__order-label">تصویر ${imgIdx + 1}</span>
                <div class="pcs-editor__order-actions">
                    <button type="button" class="pcs-editor__order-btn" data-pcs-order-up="${pos}" aria-label="بالا" ${pos === 0 ? 'disabled' : ''}><i class="fas fa-chevron-up"></i></button>
                    <button type="button" class="pcs-editor__order-btn" data-pcs-order-down="${pos}" aria-label="پایین" ${pos >= ord.length - 1 ? 'disabled' : ''}><i class="fas fa-chevron-down"></i></button>
                </div>
            </div>`).join('')}
        </div>`;
    }

    function bindEditorOrderEvents(tpl, root) {
        if (!root) return;
        root.querySelectorAll('[data-pcs-order-up], [data-pcs-order-down]').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (!state.editorBuffer) return;
                const pos = parseInt(btn.getAttribute('data-pcs-order-up') ?? btn.getAttribute('data-pcs-order-down'), 10);
                const dir = btn.hasAttribute('data-pcs-order-up') ? -1 : 1;
                state.editorBuffer.image_order = moveInOrder(state.editorBuffer.image_order, pos, dir);
                rerenderEditorImageOrder(tpl);
                refreshEditorPreview(tpl);
            });
        });
    }

    function rerenderEditorImageOrder(tpl) {
        const host = $('#pcsEditImageOrder');
        const imgs = propertyImageList();
        if (!host || !state.editorBuffer) return;
        host.outerHTML = editorImageOrderPanel(imgs, state.editorBuffer.image_order);
        bindEditorOrderEvents(tpl, $('#pcsEditImageOrder')?.parentElement || $('#pcsEditorControls'));
    }

    function armImagesForExport(root) {
        if (!root) return;
        root.querySelectorAll('img').forEach((img) => {
            img.crossOrigin = 'anonymous';
            img.referrerPolicy = 'no-referrer';
        });
    }

    function esc(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    }

    function brandLogoBlock(b, size) {
        const px = size || 88;
        if (!b.logo_url) return '';
        return `<div style="position:absolute;top:40px;right:40px;z-index:3;padding:10px;border-radius:16px;background:rgba(255,255,255,.92);box-shadow:0 8px 24px rgba(0,0,0,.15);">
            <img src="${esc(b.logo_url)}" alt="" decoding="async" referrerpolicy="no-referrer" style="width:${px}px;height:${px}px;object-fit:contain;display:block;">
        </div>`;
    }

    const PCS_SVG_PATHS = {
        tag: '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7" cy="7" r="1.5" fill="currentColor"/>',
        location: '<path d="M12 21s7-4.5 7-11a7 7 0 1 0-14 0c0 6.5 7 11 7 11z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="2.5" fill="currentColor"/>',
        area: '<rect x="3" y="8" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 8V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v3" fill="none" stroke="currentColor" stroke-width="2"/>',
        bed: '<path d="M3 14V8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6M3 14v4M21 14v4M3 14h18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
        building: '<path d="M4 21V9l8-5 8 5v12M9 21v-6h6v6" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
        phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.78.62 2.63a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.45-1.14a2 2 0 0 1 2.11-.45c.85.29 1.73.5 2.63.62A2 2 0 0 1 22 16.92z" fill="none" stroke="currentColor" stroke-width="2"/>',
        user: '<circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M4 21v-1a6 6 0 0 1 12 0v1" fill="none" stroke="currentColor" stroke-width="2"/>',
        star: '<path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7-6.3-4.6L5.7 21 8 14 2 9.4h7.6z" fill="currentColor"/>',
        check: '<path d="M20 6L9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
        parking: '<rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 16V8h4.5a3 3 0 0 1 0 6H9" fill="none" stroke="currentColor" stroke-width="2"/>',
        elevator: '<rect x="5" y="3" width="14" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v10M9 10l3-3 3 3M9 14l3 3 3-3" fill="none" stroke="currentColor" stroke-width="2"/>',
        storage: '<path d="M4 8h16v12H4zM4 8l2-4h12l2 4M10 12v4M14 12v4" fill="none" stroke="currentColor" stroke-width="2"/>',
        images: '<rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8.5" cy="10.5" r="1.5" fill="currentColor"/><path d="M21 17l-5-5-4 4-2-2-5 5" fill="none" stroke="currentColor" stroke-width="2"/>',
        bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/>',
        gem: '<path d="M12 2l8 6-8 14L4 8l8-6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    };

    function pcsSvg(type, px, color) {
        const body = PCS_SVG_PATHS[type] || PCS_SVG_PATHS.check;
        const n = px || 24;
        return `<span aria-hidden="true" style="display:inline-flex;align-items:center;justify-content:center;width:${n}px;height:${n}px;color:${color || 'currentColor'};flex-shrink:0;line-height:0;"><svg viewBox="0 0 24 24" width="${n}" height="${n}" xmlns="http://www.w3.org/2000/svg">${body}</svg></span>`;
    }

    function amenityIconKey(label) {
        const s = String(label || '');
        if (/پارکینگ/i.test(s)) return 'parking';
        if (/آسانسور/i.test(s)) return 'elevator';
        if (/انبار/i.test(s)) return 'storage';
        if (/بالکن|تراس/i.test(s)) return 'star';
        return 'check';
    }

    function chipIconFor(text) {
        const s = String(text || '');
        if (/متر/i.test(s)) return 'area';
        if (/خواب|اتاق|سوئیت/i.test(s)) return 'bed';
        if (/آپارتمان|ویلا|مغازه|زمین|ملک|تجاری/i.test(s)) return 'building';
        if (/پارکینگ/i.test(s)) return 'parking';
        if (/آسانسور/i.test(s)) return 'elevator';
        return 'star';
    }

    function amenityRows(items, color, darkText) {
        const list = (items || []).slice(0, 4);
        if (!list.length) return '';
        const textColor = darkText ? '#334155' : '#fff';
        const iconBg = darkText ? color : 'rgba(255,255,255,.22)';
        const iconFg = darkText ? '#fff' : '#fff';
        return list.map((t) => `
            <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">
                <span style="width:36px;height:36px;border-radius:11px;background:linear-gradient(145deg,${darkText ? color : iconBg},${primaryRgba(color, darkText ? 0.72 : 0.35)});display:inline-flex;align-items:center;justify-content:center;box-shadow:0 6px 16px ${primaryRgba(color, 0.32)};">
                    ${pcsSvg(amenityIconKey(t), 20, iconFg)}
                </span>
                <span style="${pcsTextStyle(`font-size:24px;color:${textColor};font-weight:600;`)}">${esc(t)}</span>
            </div>`).join('');
    }

    function primaryRgba(hex, alpha) {
        const h = String(hex || '#7c3aed').replace('#', '');
        if (h.length !== 6) return `rgba(124,58,237,${alpha})`;
        const r = parseInt(h.slice(0, 2), 16);
        const g = parseInt(h.slice(2, 4), 16);
        const b = parseInt(h.slice(4, 6), 16);
        return `rgba(${r},${g},${b},${alpha})`;
    }

    function colorLuminance(hex) {
        const h = String(hex || '#000').replace('#', '');
        if (h.length !== 6) return 0;
        const ch = [0, 2, 4].map((i) => {
            const v = parseInt(h.slice(i, i + 2), 16) / 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
    }

    function normalizeBrandColor(hex) {
        const c = String(hex || '#7c3aed').trim();
        if (!/^#[0-9a-fA-F]{6}$/.test(c)) return '#7c3aed';
        const lum = colorLuminance(c);
        if (lum > 0.88) return '#7c3aed';
        if (lum < 0.06) return '#6366f1';
        return c;
    }

    function textOnColor(bgHex, light = '#ffffff', dark = '#0f172a') {
        return colorLuminance(bgHex) > 0.55 ? dark : light;
    }

    function inkAccentOnWhite(hex) {
        const c = normalizeBrandColor(hex);
        return colorLuminance(c) > 0.62 ? '#5b21b6' : c;
    }

    function specChipRow(items, primaryColor, variant) {
        const list = (items || []).filter(Boolean).slice(0, 4);
        if (!list.length) return '';
        const dark = variant === 'dark';
        return `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:16px;">
            ${list.map((t) => `
            <span style="${pcsTextStyle(`display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:999px;font-size:21px;font-weight:700;${
                dark
                    ? `color:#fff;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.24);box-shadow:0 4px 14px rgba(0,0,0,.2);`
                    : `color:${primaryColor};background:${primaryRgba(primaryColor, 0.1)};border:1px solid ${primaryRgba(primaryColor, 0.22)};`
            }`)}">${pcsSvg(chipIconFor(t), 18, dark ? '#f8fafc' : primaryColor)}<span>${esc(t)}</span></span>`).join('')}
        </div>`;
    }

    function posterShineOverlay() {
        return `<div style="position:absolute;inset:0;pointer-events:none;z-index:4;background:linear-gradient(125deg, rgba(255,255,255,.22) 0%, transparent 38%, transparent 62%, rgba(255,255,255,.12) 100%);opacity:.55;"></div>`;
    }

    function posterGrainOverlay() {
        return `<div style="position:absolute;inset:0;pointer-events:none;z-index:5;opacity:.07;background-image:radial-gradient(circle at 20% 30%,#fff 0.5px,transparent 0.6px),radial-gradient(circle at 80% 70%,#fff 0.5px,transparent 0.6px);background-size:4px 4px,5px 5px;"></div>`;
    }

    function posterBokehDots(primaryColor) {
        return `<div style="position:absolute;width:280px;height:280px;border-radius:50%;top:12%;left:-8%;background:radial-gradient(circle,${primaryRgba(primaryColor, 0.28)} 0%,transparent 68%);pointer-events:none;z-index:2;"></div>
            <div style="position:absolute;width:200px;height:200px;border-radius:50%;bottom:28%;right:-6%;background:radial-gradient(circle,rgba(212,175,55,.22) 0%,transparent 70%);pointer-events:none;z-index:2;"></div>`;
    }

    function dealBadgeHtml(dealLabel, primaryColor, variant) {
        const dark = variant === 'dark';
        const bg = dark
            ? `linear-gradient(135deg,rgba(0,0,0,.72),rgba(0,0,0,.4))`
            : `linear-gradient(135deg,#fff,#f8fafc)`;
        const border = dark ? 'rgba(255,255,255,.28)' : primaryRgba(primaryColor, 0.2);
        const text = dark ? '#fff' : inkAccentOnWhite(primaryColor);
        const icon = dark ? '#f5e6a8' : primaryColor;
        return `<div style="display:inline-flex;align-items:center;gap:10px;padding:11px 22px;border-radius:999px;background:${bg};border:1px solid ${border};box-shadow:0 10px 28px rgba(0,0,0,.28);${pcsTextStyle(`font-size:22px;color:${text};font-weight:800;`)}">
            ${pcsSvg('tag', 20, icon)}<span>${esc(dealLabel)}</span>
        </div>`;
    }

    function statTilesHtml(p, locLine, color, variant) {
        const tiles = [];
        if (p.area_label) tiles.push({ icon: 'area', label: p.area_label });
        if (p.rooms_label) tiles.push({ icon: 'bed', label: p.rooms_label });
        if (locLine) tiles.push({ icon: 'location', label: locLine });
        if (!tiles.length) return '';
        const dark = variant === 'dark';
        const max = dark ? 3 : 3;
        return `<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;">
            ${tiles.slice(0, max).map((t) => `
            <div style="display:flex;align-items:center;gap:9px;padding:11px 15px;border-radius:14px;${
                dark
                    ? 'background:rgba(15,23,42,.45);border:1px solid rgba(255,255,255,.16);box-shadow:0 8px 24px rgba(0,0,0,.25);'
                    : `background:#fff;border:1px solid ${primaryRgba(color, 0.14)};box-shadow:0 10px 24px ${primaryRgba(color, 0.1)};`
            }">
                ${pcsSvg(t.icon, 21, dark ? '#e2e8f0' : color)}
                <span style="${pcsTextStyle(`font-size:20px;font-weight:700;color:${dark ? '#f1f5f9' : '#334155'};max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;`)}">${esc(t.label)}</span>
            </div>`).join('')}
        </div>`;
    }

    function priceHighlightHtml(price, color, variant, conf) {
        if (!price) return '';
        const dark = variant === 'dark';
        const c = conf || {};
        const px = posterFontSize(c, dark ? 40 : 46, 'price');
        if (dark) {
            return `<div style="margin-top:20px;display:inline-flex;align-items:center;gap:14px;padding:16px 28px;border-radius:18px;background:linear-gradient(135deg,${primaryRgba(color, 0.42)},rgba(0,0,0,.5));border:1px solid ${primaryRgba(color, 0.55)};box-shadow:0 14px 36px rgba(0,0,0,.45);">
                ${pcsSvg('tag', 26, '#f5e6a8')}
                <span style="${pcsTextStyle(`font-size:${px}px;font-weight:800;color:#fff;`, c)}">${esc(price)}</span>
            </div>`;
        }
        return `<div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:12px;">
            ${pcsSvg('tag', 28, color)}
            <span style="${pcsTextStyle(`font-size:${px}px;font-weight:800;color:${color};`, c)}">${esc(price)}</span>
        </div>`;
    }

    function editorFontPicker(selected) {
        return `<div class="pcs-editor__font-grid" role="radiogroup" aria-label="فونت پوستر">
            ${Object.entries(PCS_FONTS).map(([key, meta]) => `
            <button type="button" class="pcs-editor__font-btn${key === selected ? ' is-active' : ''}" data-pcs-font-key="${key}" style="font-family:${meta.family};" aria-pressed="${key === selected}">
                ${esc(meta.label)}
            </button>`).join('')}
        </div>`;
    }

    function brandFooterHtml(brandName, phone, variant) {
        if (!brandName) return '';
        const dark = variant === 'dark';
        const text = dark ? '#f8fafc' : '#475569';
        const phoneBg = dark ? 'rgba(255,255,255,.1)' : primaryRgba('#7c3aed', 0.08);
        return `<div style="display:flex;justify-content:space-between;align-items:center;gap:16px;width:100%;${pcsTextStyle(`font-size:24px;color:${text};font-weight:600;`)}">
            <span style="display:inline-flex;align-items:center;gap:10px;">${pcsSvg('user', 22, dark ? '#cbd5e1' : '#64748b')}<span>${esc(brandName)}</span></span>
            ${phone ? `<span dir="ltr" style="unicode-bidi:isolate;display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:12px;background:${phoneBg};border:1px solid ${dark ? 'rgba(255,255,255,.12)' : '#e2e8f0'};">${pcsSvg('phone', 18, dark ? '#e2e8f0' : '#64748b')}<span>${esc(phone)}</span></span>` : ''}
        </div>`;
    }

    function galleryPosterImgStyle(cropY) {
        const y = cropY ?? 50;
        return `width:100%;height:100%;object-fit:cover;object-position:center ${y}%;`;
    }

    function pipImageUrl(conf, list) {
        const imgs = list || propertyImageList();
        if (!imgs.length) return '';
        let idx = parseInt(conf.pip_image_index, 10);
        if (!Number.isFinite(idx)) idx = imgs.length > 1 ? 1 : 0;
        if (imgs.length > 1 && idx === conf.primary_image_index) {
            idx = (conf.primary_image_index + 1) % imgs.length;
        }
        idx = Math.min(imgs.length - 1, Math.max(0, idx));
        return imgs[idx] || imgs[0];
    }

    function posterHeroWarmth(conf) {
        const w = conf.hero_warmth || 'neutral';
        if (w === 'cool') {
            return '<div style="position:absolute;inset:0;z-index:3;pointer-events:none;background:rgba(56,189,248,.14);mix-blend-mode:soft-light;"></div>';
        }
        if (w === 'warm') {
            return '<div style="position:absolute;inset:0;z-index:3;pointer-events:none;background:rgba(251,146,60,.16);mix-blend-mode:soft-light;"></div>';
        }
        return '';
    }

    function posterHeroVignetteExtra(conf) {
        const v = conf.hero_vignette ?? 0;
        if (v <= 0) return '';
        const o = Math.min(0.82, (v / 100) * 0.78);
        return `<div style="position:absolute;inset:0;pointer-events:none;z-index:4;background:radial-gradient(ellipse 82% 72% at 50% 42%,transparent 30%,rgba(0,0,0,${o}) 100%);"></div>`;
    }

    function posterPipInset(conf, primaryColor, accentInk) {
        if (!conf.pip_enabled) return '';
        const url = pipImageUrl(conf);
        if (!url) return '';
        const sizePct = { s: 20, m: 28, l: 36 }[conf.pip_size] || 28;
        const corners = {
            br: 'bottom:26px;right:26px;',
            bl: 'bottom:26px;left:26px;',
            tr: 'top:26px;right:26px;',
            tl: 'top:26px;left:26px;',
        };
        const pos = corners[conf.pip_corner] || corners.br;
        const shape = conf.pip_shape || 'rounded';
        const radius = shape === 'circle' ? '50%' : shape === 'card' ? '10px' : '16px';
        const aspect = shape === 'circle' ? '1/1' : '5/4';
        const crop = conf.pip_crop_y ?? 50;
        const border = conf.pip_border === 'gold'
            ? '3px solid rgba(212,175,55,.9)'
            : conf.pip_border === 'brand'
                ? `3px solid ${accentInk || primaryColor}`
                : '3px solid rgba(255,255,255,.95)';
        const tilt = conf.pip_tilt ?? 0;
        const pad = shape === 'card' ? 'padding:8px 8px 22px 8px;background:#fff;' : '';
        const innerRadius = shape === 'card' ? '6px' : radius;
        return `<div style="position:absolute;${pos}z-index:9;width:${sizePct}%;max-width:320px;aspect-ratio:${aspect};transform:rotate(${tilt}deg);filter:drop-shadow(0 22px 40px rgba(0,0,0,.42));">
            <div style="width:100%;height:100%;border-radius:${radius};overflow:hidden;border:${border};${pad}box-sizing:border-box;">
                <div style="width:100%;height:100%;border-radius:${innerRadius};overflow:hidden;background:#0f172a;">
                    ${posterImg(url, `width:100%;height:100%;object-fit:cover;object-position:center ${crop}%;`, conf)}
                </div>
            </div>
            <div style="position:absolute;inset:4px;border-radius:${radius};pointer-events:none;box-shadow:inset 0 0 0 1px rgba(255,255,255,.2);"></div>
        </div>`;
    }

    function editorOptionChips(attr, options, activeValue) {
        return `<div class="pcs-editor__chip-row" role="group">${options.map(([val, label]) => `
            <button type="button" class="pcs-editor__chip${val === activeValue ? ' is-active' : ''}" data-${attr}="${val}">${esc(label)}</button>`).join('')}
        </div>`;
    }

    function editorCompositionPresets() {
        const items = [
            ['pip_classic', 'عکس در عکس'],
            ['magazine', 'مجله‌ای'],
            ['cinematic', 'سینمایی'],
            ['clean', 'خالص'],
        ];
        return `<div class="pcs-editor__composition-row" role="group" aria-label="پیش‌تنظیم ترکیب">
            ${items.map(([key, label]) => `<button type="button" class="pcs-editor__composition-btn" data-pcs-composition="${key}">${esc(label)}</button>`).join('')}
        </div>`;
    }

    function editorPipSection(imgs, conf) {
        if (imgs.length < 2) {
            return `<section class="pcs-editor__section pcs-editor__section--muted">
                <h4 class="pcs-editor__section-title"><i class="fas fa-clone" aria-hidden="true"></i> عکس در عکس</h4>
                <p class="pcs-editor__section-hint">حداقل دو تصویر برای فایل لازم است تا تصویر کوچک روی تصویر اصلی قرار بگیرد.</p>
            </section>`;
        }
        const pipIdx = conf.pip_image_index ?? 1;
        const pipOn = !!conf.pip_enabled;
        return `<section class="pcs-editor__section">
            <h4 class="pcs-editor__section-title"><i class="fas fa-clone" aria-hidden="true"></i> عکس در عکس</h4>
            <p class="pcs-editor__section-hint">یک تصویر دوم به‌صورت شناور روی تصویر اصلی — مناسب نمایش اتاق دوم یا نما</p>
            <label class="pcs-editor__toggle">
                <input type="checkbox" data-pcs-pip-enabled${pipOn ? ' checked' : ''}>
                <span class="pcs-editor__toggle-track" aria-hidden="true"></span>
                <span class="pcs-editor__toggle-label">فعال‌سازی عکس در عکس</span>
            </label>
            <div class="pcs-editor__pip-panel${pipOn ? ' is-open' : ''}" data-pcs-pip-panel>
                <input type="hidden" id="pcsEditPipImage" value="${pipIdx}">
                <p class="pcs-editor__mini-label">تصویر کوچک</p>
                ${editorThumbGrid(imgs, pipIdx, 'pip')}
                <p class="pcs-editor__mini-label">جایگاه</p>
                ${editorOptionChips('pcs-pip-corner', [['br', 'پایین راست'], ['bl', 'پایین چپ'], ['tr', 'بالا راست'], ['tl', 'بالا چپ']], conf.pip_corner || 'br')}
                <p class="pcs-editor__mini-label">اندازه و شکل</p>
                ${editorOptionChips('pcs-pip-size', [['s', 'کوچک'], ['m', 'متوسط'], ['l', 'بزرگ']], conf.pip_size || 'm')}
                ${editorOptionChips('pcs-pip-shape', [['rounded', 'گرد'], ['circle', 'دایره'], ['card', 'پولاروید']], conf.pip_shape || 'rounded')}
                <p class="pcs-editor__mini-label">حاشیه</p>
                ${editorOptionChips('pcs-pip-border', [['light', 'سفید'], ['brand', 'برند'], ['gold', 'طلایی']], conf.pip_border || 'light')}
                <label class="pcs-editor__range-label">قاب تصویر کوچک <span data-pcs-range-val="pip_crop">${conf.pip_crop_y ?? 50}%</span></label>
                <input type="range" class="pcs-editor__range" data-pcs-edit-range="pip_crop" min="0" max="100" value="${conf.pip_crop_y ?? 50}">
                <label class="pcs-editor__range-label">چرخش جزئی <span data-pcs-range-val="pip_tilt">${conf.pip_tilt ?? 0}°</span></label>
                <input type="range" class="pcs-editor__range" data-pcs-edit-range="pip_tilt" min="-10" max="10" value="${conf.pip_tilt ?? 0}">
            </div>
        </section>`;
    }

    function editorHeroMoodSection(conf) {
        return `<section class="pcs-editor__section">
            <h4 class="pcs-editor__section-title"><i class="fas fa-camera-retro" aria-hidden="true"></i> جو تصویر اصلی</h4>
            <p class="pcs-editor__section-hint">لنز، گرما و عمق — روی تصویر بزرگ (نه متن پوستر)</p>
            <p class="pcs-editor__mini-label">دمای رنگ</p>
            ${editorOptionChips('pcs-hero-warmth', [['neutral', 'خنثی'], ['warm', 'گرم'], ['cool', 'سرد']], conf.hero_warmth || 'neutral')}
            <label class="pcs-editor__range-label">سایه لنز (وینیت) <span data-pcs-range-val="hero_vignette">${conf.hero_vignette ?? 0}%</span></label>
            <input type="range" class="pcs-editor__range" data-pcs-edit-range="hero_vignette" min="0" max="80" value="${conf.hero_vignette ?? 0}">
        </section>`;
    }

    function syncCompositionFormFromBuffer(conf) {
        const controls = editorControlsEl();
        if (!controls || !conf) return;
        const pipCheck = controls.querySelector('[data-pcs-pip-enabled]');
        if (pipCheck) pipCheck.checked = !!conf.pip_enabled;
        const pipPanel = controls.querySelector('[data-pcs-pip-panel]');
        pipPanel?.classList.toggle('is-open', !!conf.pip_enabled);
        const pipHidden = controls.querySelector('#pcsEditPipImage');
        if (pipHidden) pipHidden.value = String(conf.pip_image_index ?? 1);
        controls.querySelectorAll('[data-pcs-pip-corner]').forEach((b) => {
            b.classList.toggle('is-active', b.getAttribute('data-pcs-pip-corner') === (conf.pip_corner || 'br'));
        });
        controls.querySelectorAll('[data-pcs-pip-size]').forEach((b) => {
            b.classList.toggle('is-active', b.getAttribute('data-pcs-pip-size') === (conf.pip_size || 'm'));
        });
        controls.querySelectorAll('[data-pcs-pip-shape]').forEach((b) => {
            b.classList.toggle('is-active', b.getAttribute('data-pcs-pip-shape') === (conf.pip_shape || 'rounded'));
        });
        controls.querySelectorAll('[data-pcs-pip-border]').forEach((b) => {
            b.classList.toggle('is-active', b.getAttribute('data-pcs-pip-border') === (conf.pip_border || 'light'));
        });
        controls.querySelectorAll('[data-pcs-hero-warmth]').forEach((b) => {
            b.classList.toggle('is-active', b.getAttribute('data-pcs-hero-warmth') === (conf.hero_warmth || 'neutral'));
        });
        const setRange = (key, val) => {
            const inp = controls.querySelector(`[data-pcs-edit-range="${key}"]`);
            if (inp && val != null) inp.value = String(val);
        };
        setRange('hero_vignette', conf.hero_vignette ?? 0);
        setRange('pip_crop', conf.pip_crop_y ?? 50);
        setRange('pip_tilt', conf.pip_tilt ?? 0);
        setRange('brightness', conf.img_brightness ?? 100);
        setRange('blur', conf.img_blur ?? 0);
        const pipIdx = conf.pip_image_index ?? 1;
        controls.querySelectorAll('[data-pcs-pip-grid] .pcs-editor__img-tile').forEach((tile) => {
            const i = parseInt(tile.getAttribute('data-pcs-img-idx') || '0', 10);
            const on = i === pipIdx;
            tile.classList.toggle('is-selected', on);
            tile.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    function applyCompositionPreset(key) {
        const preset = COMPOSITION_PRESETS[key];
        if (!preset || !state.editorBuffer) return;
        Object.assign(state.editorBuffer, preset);
        if (state.editorBuffer.pip_enabled && propertyImageList().length > 1) {
            const p = state.editorBuffer.primary_image_index || 0;
            state.editorBuffer.pip_image_index = (p + 1) % propertyImageList().length;
        }
        syncCompositionFormFromBuffer(state.editorBuffer);
        refreshEditorPreview(state.editorTemplate);
    }

    function buildCanvasHtml(templateId, formatKey, confOverride) {
        const fmt = FORMATS[formatKey] || FORMATS.story;
        const { property: p, brand: b } = visibleData();
        const conf = confOverride
            ? normalizePosterConfig(confOverride, propertyImageList())
            : posterConfig(templateId);
        const imgs = orderedImages(templateId);
        const primary = primaryImageUrl(conf);
        const cropY = conf.crop_y ?? 50;
        const headline = (conf.headline || p.headline || p.title || '').trim();
        const price = p.price?.show ? p.price.label : '';
        const primaryColor = normalizeBrandColor(b.colors?.primary || '#7c3aed');
        const accentInk = inkAccentOnWhite(primaryColor);
        const badgeInk = textOnColor(primaryColor);
        const brandName = b.visibility?.consultant_name !== false ? (b.consultant_name || b.brand_name || '') : '';
        const phone = b.visibility?.contact_phone !== false ? (b.contact_phone || '') : '';
        const chips = [];
        if (p.property_type) chips.push(p.property_type);
        if (p.area_label) chips.push(p.area_label);
        (p.amenities || []).slice(0, 3).forEach((c) => chips.push(c));

        const dealLabel = p.deal_mode === 'فروش' ? 'فروش' : (p.deal_mode || 'آگهی');
        const locLine = p.location_line || p.city || '';
        const specItems = chips.length ? chips : [p.property_type, p.area_label, p.rooms_label].filter(Boolean);
        let inner = '';
        if (templateId === 'luxury') {
            inner = `
                <div style="position:absolute;inset:0;background:#030305;overflow:hidden;">
                    <div style="position:absolute;inset:-8% 0 22% 0;overflow:hidden;">
                        ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;transform:scale(1.1);`, conf) : '<div style="width:100%;height:100%;background:linear-gradient(160deg,#1e293b,#0f172a);"></div>'}
                        <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.6) 0%,transparent 26%,transparent 46%,rgba(0,0,0,.9) 100%);"></div>
                        <div style="position:absolute;inset:0;background:radial-gradient(ellipse 90% 70% at 50% 32%, transparent 32%, rgba(0,0,0,.55) 100%);"></div>
                        <div style="position:absolute;inset:0;background:radial-gradient(circle at 88% 10%, ${primaryRgba(primaryColor, 0.5)} 0%, transparent 42%);opacity:.9;"></div>
                        ${posterHeroWarmth(conf)}
                        ${posterHeroVignetteExtra(conf)}
                        ${posterPipInset(conf, primaryColor, accentInk)}
                    </div>
                    ${posterBokehDots(primaryColor)}
                    ${posterShineOverlay()}
                    ${posterGrainOverlay()}
                    ${brandLogoBlock(b, 76)}
                    <div style="position:absolute;inset:26px;border:1px solid rgba(255,255,255,.22);border-radius:14px;pointer-events:none;z-index:3;"></div>
                    <div style="position:absolute;inset:34px;border:1px solid rgba(212,175,55,.32);border-radius:10px;pointer-events:none;z-index:3;"></div>
                    <div style="position:absolute;top:48px;left:48px;z-index:6;display:flex;align-items:center;gap:12px;">
                        ${dealBadgeHtml(dealLabel, primaryColor, 'dark')}
                        <span style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:999px;background:rgba(212,175,55,.18);border:1px solid rgba(212,175,55,.35);">${pcsSvg('gem', 18, '#f5e6a8')}</span>
                    </div>
                    <div style="position:absolute;left:48px;right:48px;bottom:140px;z-index:6;">
                        <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
                            ${pcsSvg('building', 26, '#f5e6a8')}
                            <div style="width:64px;height:4px;border-radius:4px;background:linear-gradient(90deg,#d4af37,#f5e6a8,#d4af37);"></div>
                            <div style="width:7px;height:7px;border-radius:50%;background:${primaryColor};box-shadow:0 0 14px ${primaryRgba(primaryColor, 0.85)};"></div>
                        </div>
                        <div style="${pcsTextStyle(`font-size:${posterFontSize(conf, 54, 'headline')}px;font-weight:800;line-height:1.12;margin-bottom:12px;color:#fff;text-shadow:0 6px 32px rgba(0,0,0,.6);`, conf)}">${esc(headline)}</div>
                        ${statTilesHtml(p, locLine, primaryColor, 'dark')}
                        ${specChipRow(specItems, primaryColor, 'dark')}
                        ${priceHighlightHtml(price, primaryColor, 'dark', conf)}
                    </div>
                    ${brandName ? `<div style="position:absolute;bottom:0;left:0;right:0;z-index:6;padding:24px 48px 40px;background:linear-gradient(180deg,transparent,rgba(0,0,0,.94));">${brandFooterHtml(brandName, phone, 'dark')}</div>` : ''}
                </div>`;
        } else if (templateId === 'minimal') {
            const imgH = fmt.h > 1500 ? '46%' : '42%';
            inner = `
                <div style="height:100%;position:relative;overflow:hidden;background:linear-gradient(145deg,#f8fafc 0%,#eef2f7 42%,${primaryRgba(primaryColor, 0.14)} 100%);box-sizing:border-box;padding:40px;">
                    <div style="position:absolute;width:400px;height:400px;border-radius:50%;top:-110px;left:-70px;background:${primaryRgba(primaryColor, 0.16)};"></div>
                    <div style="position:absolute;width:260px;height:260px;border-radius:50%;bottom:70px;right:-50px;background:${primaryRgba(primaryColor, 0.11)};"></div>
                    <div style="position:relative;z-index:1;height:100%;background:#fff;border-radius:28px;overflow:hidden;box-shadow:0 32px 80px rgba(15,23,42,.12),0 0 0 1px rgba(15,23,42,.05);display:flex;flex-direction:column;">
                        <div style="position:relative;height:${imgH};overflow:hidden;">
                            ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : `<div style="width:100%;height:100%;background:linear-gradient(135deg,#e2e8f0,#cbd5e1);"></div>`}
                            <div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 50%,rgba(15,23,42,.28) 100%);"></div>
                            ${posterHeroWarmth(conf)}
                            ${posterHeroVignetteExtra(conf)}
                            ${posterPipInset(conf, primaryColor, accentInk)}
                            ${posterShineOverlay()}
                            <div style="position:absolute;top:24px;right:24px;z-index:2;">${dealBadgeHtml(dealLabel, accentInk, 'light')}</div>
                            ${locLine ? `<div style="position:absolute;bottom:20px;right:24px;left:24px;z-index:2;display:inline-flex;align-items:center;gap:10px;padding:10px 16px;border-radius:12px;background:rgba(255,255,255,.92);border:1px solid #e2e8f0;box-shadow:0 8px 22px rgba(15,23,42,.12);">
                                ${pcsSvg('location', 20, accentInk)}
                                <span style="${pcsTextStyle(`font-size:22px;font-weight:600;color:#334155;`)}">${esc(locLine)}</span>
                            </div>` : ''}
                        </div>
                        <div style="padding:36px 40px 40px;flex:1;display:flex;flex-direction:column;border-top:4px solid ${accentInk};background:linear-gradient(180deg,#fff 0%,#f8fafc 100%);">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                                ${pcsSvg(chipIconFor(p.property_type || 'ملک'), 22, accentInk)}
                                <span style="${pcsTextStyle('font-size:20px;font-weight:700;color:#64748b;')}">${esc(p.property_type || 'ملک')}</span>
                            </div>
                            <div style="${pcsTextStyle(`font-size:${posterFontSize(conf, 42, 'headline')}px;font-weight:800;color:#0f172a;line-height:1.2;margin-bottom:8px;`, conf)}">${esc(headline)}</div>
                            ${priceHighlightHtml(price, accentInk, 'light', conf)}
                            ${statTilesHtml(p, '', accentInk, 'light')}
                            ${specChipRow(specItems, accentInk, 'light')}
                            ${amenityRows((p.amenities || []).slice(0, 3), accentInk, true)}
                            ${brandName ? `<div style="margin-top:auto;padding-top:20px;border-top:1px dashed #e2e8f0;">${brandFooterHtml(brandName, phone, 'light')}</div>` : ''}
                        </div>
                    </div>
                </div>`;
        } else if (templateId === 'gallery') {
            const g0 = imgs[0] || '';
            const g1 = imgs[1] || g0;
            const g2 = imgs[2] || g1;
            const cellOverlay = `<div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 50%,rgba(0,0,0,.55) 100%);pointer-events:none;"></div>`;
            const imgCount = imgs.filter(Boolean).length;
            const grid = imgs.length >= 3
                ? `<div style="position:relative;height:56%;padding:14px;background:linear-gradient(180deg,#0f172a,#1e293b);box-sizing:border-box;">
                    <div style="display:grid;grid-template-columns:1.2fr .8fr;grid-template-rows:1fr 1fr;height:100%;gap:12px;">
                        <div style="position:relative;grid-row:span 2;border-radius:16px;overflow:hidden;box-shadow:0 16px 40px rgba(0,0,0,.35);">
                            ${posterImg(g0, galleryPosterImgStyle(cropY), conf)}
                            ${posterHeroWarmth(conf)}
                            ${posterHeroVignetteExtra(conf)}
                            ${posterPipInset(conf, primaryColor, accentInk)}
                            ${cellOverlay}
                        </div>
                        <div style="position:relative;border-radius:14px;overflow:hidden;box-shadow:0 10px 28px rgba(0,0,0,.25);">${posterImg(g1, galleryPosterImgStyle(cropY), conf)}${cellOverlay}</div>
                        <div style="position:relative;border-radius:14px;overflow:hidden;box-shadow:0 10px 28px rgba(0,0,0,.25);">${posterImg(g2, galleryPosterImgStyle(cropY), conf)}${cellOverlay}</div>
                    </div>
                    <div style="position:absolute;top:24px;right:24px;z-index:3;display:flex;flex-direction:column;align-items:flex-end;gap:10px;">
                        ${dealBadgeHtml(dealLabel, primaryColor, 'dark')}
                        <span style="display:inline-flex;align-items:center;gap:8px;padding:9px 16px;border-radius:999px;background:rgba(15,23,42,.72);border:1px solid rgba(255,255,255,.2);${pcsTextStyle('font-size:18px;color:#e2e8f0;font-weight:700;')}">${pcsSvg('images', 18, '#38bdf8')}<span>${imgCount} تصویر</span></span>
                    </div>
                   </div>`
                : `<div style="position:relative;height:52%;overflow:hidden;">
                    ${g0 ? posterImg(g0, galleryPosterImgStyle(cropY), conf) : '<div style="height:100%;background:#334155"></div>'}
                    <div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent,rgba(0,0,0,.5));"></div>
                   </div>`;
            inner = `
                <div style="background:linear-gradient(180deg,#fff 0%,#f8fafc 100%);height:100%;display:flex;flex-direction:column;position:relative;">
                    ${grid}
                    <div style="flex:1;padding:32px 40px 40px;display:flex;flex-direction:column;justify-content:space-between;">
                        <div>
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
                                ${pcsSvg('images', 24, accentInk)}
                                <div style="width:56px;height:4px;border-radius:4px;background:linear-gradient(90deg,${accentInk},${primaryRgba(accentInk, 0.35)});"></div>
                            </div>
                            <div style="${pcsTextStyle(`font-size:${posterFontSize(conf, 40, 'headline')}px;font-weight:800;color:#0f172a;line-height:1.18;margin-bottom:8px;`, conf)}">${esc(headline)}</div>
                            ${locLine ? `<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">${pcsSvg('location', 22, '#64748b')}<span style="${pcsTextStyle('font-size:25px;color:#475569;')}">${esc(locLine)}</span></div>` : ''}
                            ${statTilesHtml(p, '', accentInk, 'light')}
                            ${specChipRow(specItems, accentInk, 'light')}
                        </div>
                        <div style="padding-top:18px;margin-top:14px;border-top:2px solid #e8edf3;">
                            ${priceHighlightHtml(price, accentInk, 'light', conf)}
                            ${brandName ? `<div style="margin-top:14px;">${brandFooterHtml(brandName, phone, 'light')}</div>` : ''}
                        </div>
                    </div>
                </div>`;
        } else {
            const topFeature = chips[0] || p.property_type || '';
            const boldHeroH = Math.round(fmt.h * 0.48);
            inner = `
                <div style="height:100%;position:relative;overflow:hidden;background:#05070d;">
                    <div style="position:absolute;width:160%;height:62%;top:-12%;left:-30%;background:linear-gradient(135deg,${primaryColor},${primaryRgba(primaryColor, 0.55)});transform:rotate(-10deg);opacity:.94;"></div>
                    <div style="position:absolute;width:90%;height:40%;bottom:-5%;right:-20%;background:linear-gradient(45deg,${primaryRgba(primaryColor, 0.38)},transparent);transform:rotate(8deg);"></div>
                    <div style="position:absolute;inset:0;background:radial-gradient(circle at 20% 80%,rgba(255,255,255,.08),transparent 45%);pointer-events:none;z-index:1;"></div>
                    <div style="position:relative;z-index:2;margin:32px 32px 0;border-radius:22px;overflow:hidden;box-shadow:0 28px 64px rgba(0,0,0,.5);border:3px solid rgba(255,255,255,.18);">
                        ${primary ? posterImg(primary, `width:100%;height:${boldHeroH}px;object-fit:cover;object-position:center ${cropY}%;display:block;`, conf) : `<div style="height:${boldHeroH}px;background:#1e293b"></div>`}
                        <div style="position:absolute;top:0;left:0;right:0;height:${boldHeroH}px;pointer-events:none;background:linear-gradient(180deg,rgba(0,0,0,.4),transparent 42%);"></div>
                        ${posterHeroWarmth(conf)}
                        ${posterHeroVignetteExtra(conf)}
                        ${posterPipInset(conf, primaryColor, accentInk)}
                        <div style="position:absolute;top:22px;right:22px;z-index:2;">${dealBadgeHtml(dealLabel, primaryColor, 'dark')}</div>
                        ${topFeature ? `<div style="position:absolute;bottom:22px;right:22px;z-index:2;display:inline-flex;align-items:center;gap:10px;padding:12px 20px;border-radius:14px;background:#fff;box-shadow:0 10px 28px rgba(0,0,0,.28);${pcsTextStyle(`font-size:22px;font-weight:800;color:${accentInk};`)}">${pcsSvg(chipIconFor(topFeature), 22, accentInk)}<span>${esc(topFeature)}</span></div>` : ''}
                    </div>
                    <div style="position:relative;z-index:3;padding:36px 44px 48px;margin-top:-44px;">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">${pcsSvg('bolt', 28, '#fbbf24')}<span style="${pcsTextStyle('font-size:22px;font-weight:700;color:#e2e8f0;')}">پیشنهاد ویژه</span></div>
                        <div style="${pcsTextStyle(`font-size:${posterFontSize(conf, 52, 'headline')}px;font-weight:800;line-height:1.08;color:#f8fafc;margin-bottom:10px;text-shadow:0 8px 28px rgba(0,0,0,.55);`, conf)}">${esc(headline)}</div>
                        ${locLine ? `<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">${pcsSvg('location', 24, '#cbd5e1')}<span style="${pcsTextStyle('font-size:26px;color:#e2e8f0;')}">${esc(locLine)}</span></div>` : ''}
                        ${statTilesHtml(p, '', primaryColor, 'dark')}
                        ${specChipRow(specItems, primaryColor, 'dark')}
                        <div style="margin-top:16px;display:inline-flex;align-items:stretch;">
                            ${price ? `<div style="display:inline-flex;align-items:center;gap:14px;padding:16px 32px;border-radius:18px;background:#fff;border:2px solid ${primaryRgba(accentInk, 0.22)};box-shadow:0 14px 40px rgba(0,0,0,.3);">${pcsSvg('tag', 30, accentInk)}<span style="${pcsTextStyle(`font-size:48px;font-weight:900;color:${accentInk};`)}">${esc(price)}</span></div>` : ''}
                        </div>
                        ${brandName ? `<div style="margin-top:24px;padding-top:20px;border-top:1px solid rgba(255,255,255,.18);">${brandFooterHtml(brandName, phone, 'dark')}</div>` : ''}
                    </div>
                </div>`;
        }

        return `<div class="pcs-canvas ${fmt.cls}" data-pcs-canvas data-template="${templateId}" data-font-key="${esc(conf.font_key || 'vazirmatn')}" style="width:${fmt.w}px;height:${fmt.h}px;--pcs-scale:1;${pcsTextStyle('', conf)}">${inner}</div>`;
    }

    function isMobileViewport() {
        return window.matchMedia('(max-width: 768px)').matches;
    }

    function syncViewportMode() {
        $('#pcsModal')?.classList.toggle('pcs-modal--mob', isMobileViewport());
    }

    function lightboxPreviewBounds(wrap) {
        const panel = wrap?.closest?.('.pcs-lightbox__panel');
        if (!panel) return null;
        const headH = panel.querySelector('.pcs-lightbox__head')?.offsetHeight || 52;
        const footH = panel.querySelector('.pcs-lightbox__foot')?.offsetHeight || 48;
        const maxPanelH = Math.min(window.innerHeight * 0.92, 880);
        const width = Math.max(220, panel.clientWidth - 36);
        const height = Math.max(200, maxPanelH - headH - footH - 20);
        return { width, height };
    }

    function editorPreviewBounds(wrap) {
        const stage = wrap?.closest?.('.pcs-editor__preview-stage');
        if (!stage) return null;
        const tagH = stage.querySelector('.pcs-editor__preview-tag')?.offsetHeight || 24;
        const pad = 28;
        return {
            width: Math.max(180, stage.clientWidth - pad),
            height: Math.max(220, stage.clientHeight - tagH - pad),
        };
    }

    function previewMaxHeight(formatKey, wrap) {
        if (wrap?.id === 'pcsEditorPreview') {
            const b = editorPreviewBounds(wrap);
            return b ? b.height : Math.min(window.innerHeight * 0.55, 520);
        }
        if (wrap?.id === 'pcsLightboxPreview' || wrap?.classList?.contains('pcs-lightbox__preview')) {
            const b = lightboxPreviewBounds(wrap);
            return b ? b.height : Math.min(window.innerHeight * 0.68, 640);
        }
        if (wrap?.classList?.contains('pcs-story-slide__frame')) {
            return isMobileViewport() ? 132 : 148;
        }
        if (wrap?.closest?.('.pcs-poster-card')) {
            const mob = isMobileViewport();
            if (formatKey === 'post') return mob ? 200 : 168;
            if (formatKey === 'square') return mob ? 180 : 148;
            return mob ? 228 : 196;
        }
        return null;
    }

    const previewScaleAttempts = new WeakMap();

    function scalePreviewCanvas(wrap, formatKey, maxScale) {
        const canvas = $('.pcs-canvas', wrap);
        if (!canvas) return;
        const fmt = FORMATS[formatKey] || FORMATS.story;
        const isLightbox = wrap.id === 'pcsLightboxPreview' || wrap.classList.contains('pcs-lightbox__preview');
        const isEditorPreview = wrap.id === 'pcsEditorPreview';
        let containerW = wrap.clientWidth || wrap.getBoundingClientRect().width || 0;
        if (isLightbox) {
            const b = lightboxPreviewBounds(wrap);
            if (b) containerW = b.width;
        }
        if (isEditorPreview) {
            const b = editorPreviewBounds(wrap);
            if (b) containerW = b.width;
        }
        if (containerW < 8) {
            const tries = (previewScaleAttempts.get(wrap) || 0) + 1;
            previewScaleAttempts.set(wrap, tries);
            if (tries < 48) {
                requestAnimationFrame(() => scalePreviewCanvas(wrap, formatKey, maxScale));
                return;
            }
            containerW = wrap.parentElement?.clientWidth || 280;
        } else {
            previewScaleAttempts.delete(wrap);
        }
        const maxH = previewMaxHeight(formatKey, wrap);
        let scale = containerW / fmt.w;
        if (maxH) scale = Math.min(scale, maxH / fmt.h);
        if (maxScale != null && !isLightbox && !isEditorPreview) scale = Math.min(scale, maxScale);
        scale = Math.max(0.08, scale);
        const visualW = Math.round(fmt.w * scale);
        const visualH = Math.round(fmt.h * scale);

        wrap.style.overflow = isLightbox ? 'auto' : 'hidden';
        wrap.style.width = '100%';
        wrap.style.display = 'flex';
        wrap.style.justifyContent = 'center';
        wrap.style.alignItems = isLightbox ? 'center' : 'flex-start';
        wrap.style.height = isLightbox ? 'auto' : `${visualH}px`;
        wrap.style.minHeight = isLightbox ? '0' : '0';
        wrap.style.maxHeight = isLightbox && maxH ? `${maxH}px` : 'none';
        if (isLightbox) {
            wrap.style.padding = '1rem 0.85rem 1.1rem';
            wrap.style.boxSizing = 'border-box';
        }

        let scaler = $('.pcs-preview-scaler', wrap);
        if (!scaler) {
            scaler = document.createElement('div');
            scaler.className = 'pcs-preview-scaler';
            wrap.appendChild(scaler);
        }
        if (canvas.parentNode !== scaler) scaler.appendChild(canvas);

        scaler.style.width = `${visualW}px`;
        scaler.style.height = `${visualH}px`;
        scaler.style.overflow = 'hidden';
        scaler.style.position = 'relative';
        scaler.style.flexShrink = '0';

        canvas.style.width = `${fmt.w}px`;
        canvas.style.height = `${fmt.h}px`;
        canvas.style.transform = `scale(${scale})`;
        canvas.style.transformOrigin = 'top left';
        canvas.style.position = 'absolute';
        canvas.style.left = '0';
        canvas.style.top = '0';
        canvas.style.margin = '0';
        wrap.classList.add('is-ready');
    }

    function whenImagesReady(wrap, cb) {
        const imgs = wrap ? wrap.querySelectorAll('img') : [];
        if (!imgs.length) {
            cb();
            return;
        }
        let pending = 0;
        imgs.forEach((img) => {
            if (img.complete) return;
            pending += 1;
            const finish = () => {
                pending -= 1;
                if (pending <= 0) cb();
            };
            img.addEventListener('load', finish, { once: true });
            img.addEventListener('error', finish, { once: true });
        });
        if (pending === 0) cb();
    }

    function bindPosterCarousel() {
        const grid = $('#pcsPosterGrid');
        const dots = $('#pcsPosterDots');
        if (!grid || !dots || !isMobileViewport()) {
            if (dots) dots.innerHTML = '';
            return;
        }
        const cards = $$('.pcs-poster-card', grid);
        dots.innerHTML = cards.map((_, i) => `<span class="pcs-poster-dot${i === 0 ? ' is-active' : ''}" data-pcs-dot="${i}"></span>`).join('');
        const syncDot = () => {
            if (!cards.length) return;
            const mid = grid.scrollLeft + grid.clientWidth / 2;
            let active = 0;
            cards.forEach((card, i) => {
                const left = card.offsetLeft;
                const right = left + card.offsetWidth;
                if (mid >= left && mid < right) active = i;
            });
            dots.querySelectorAll('.pcs-poster-dot').forEach((d, i) => {
                d.classList.toggle('is-active', i === active);
            });
        };
        if (!grid.dataset.pcsCarouselBound) {
            grid.dataset.pcsCarouselBound = '1';
            grid.addEventListener('scroll', () => requestAnimationFrame(syncDot), { passive: true });
        }
        syncDot();
    }

    async function ensureLibs() {
        if (state.libsLoaded) return;
        const load = (src) => new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.crossOrigin = 'anonymous';
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
        if (typeof html2canvas !== 'function') {
            await load('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js');
        }
        if (typeof JSZip === 'undefined') {
            await load('https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js');
        }
        state.libsLoaded = true;
    }

    async function rasterizeCanvas(canvas, formatKey) {
        await ensureLibs();
        await ensurePersianFonts();
        armImagesForExport(canvas);
        const fmt = FORMATS[formatKey] || FORMATS.story;
        return html2canvas(canvas, {
            useCORS: true,
            allowTaint: false,
            scale: 1,
            width: fmt.w,
            height: fmt.h,
            backgroundColor: '#ffffff',
            logging: false,
            onclone: (_doc, cloned) => {
                applyFontToSubtree(cloned);
            },
        });
    }

    async function exportCanvasElement(canvas, filename, formatKey) {
        const shot = await rasterizeCanvas(canvas, formatKey || state.format);
        const link = document.createElement('a');
        link.download = filename;
        link.href = shot.toDataURL('image/png');
        link.click();
    }

    function renderPosters() {
        const grid = $('#pcsPosterGrid');
        if (!grid) return;
        grid.innerHTML = '';
        TEMPLATES.forEach((tpl) => {
            const meta = TEMPLATE_META[tpl] || { label: tpl, icon: 'fa-image' };
            const card = document.createElement('article');
            card.className = `pcs-poster-card pcs-poster-card--${tpl}`;
            const head = document.createElement('div');
            head.className = 'pcs-poster-card__head';
            head.innerHTML = `<span class="pcs-poster-card__badge"><i class="fas ${meta.icon}" aria-hidden="true"></i> ${esc(meta.label)}</span>`;
            const preview = document.createElement('div');
            preview.className = 'pcs-poster-card__preview' + (state.format === 'post' ? ' is-post' : state.format === 'square' ? ' is-square' : '');
            preview.innerHTML = buildCanvasHtml(tpl, state.format);
            const foot = document.createElement('div');
            foot.className = 'pcs-poster-card__foot';
            foot.innerHTML = `
                <button type="button" class="pcs-btn pcs-btn--ghost" data-pcs-dl="${tpl}" aria-label="دانلود پوستر ${esc(meta.label)}">
                    <i class="fas fa-download" aria-hidden="true"></i><span class="pcs-btn__label">دانلود</span>
                </button>
                <button type="button" class="pcs-btn pcs-btn--ghost" data-pcs-edit="${tpl}" aria-label="ویرایش پوستر ${esc(meta.label)}">
                    <i class="fas fa-pen" aria-hidden="true"></i><span class="pcs-btn__label">ویرایش</span>
                </button>
                <button type="button" class="pcs-btn pcs-btn--soft pcs-btn--preview" data-pcs-preview="${tpl}" aria-label="پیش‌نمایش پوستر ${esc(meta.label)}">
                    <i class="fas fa-expand" aria-hidden="true"></i><span class="pcs-btn__label">پیش‌نمایش</span>
                </button>`;
            card.append(head, preview, foot);
            grid.appendChild(card);
        });
        const scaleAll = () => {
            grid.querySelectorAll('.pcs-poster-card__preview').forEach((el) => {
                whenImagesReady(el, () => scalePreviewCanvas(el, state.format));
            });
            bindPosterCarousel();
        };
        requestAnimationFrame(() => requestAnimationFrame(scaleAll));
    }

    function openPreview(tpl) {
        const meta = TEMPLATE_META[tpl] || { label: tpl };
        const box = $('#pcsLightboxPreview');
        const lb = $('#pcsLightbox');
        const title = $('#pcsLightboxTitle');
        const sub = $('#pcsLightboxSub');
        if (!box || !lb) return;
        state.previewTemplate = tpl;
        if (title) title.textContent = meta.label;
        const fmtMeta = FORMAT_META[state.format];
        if (sub) sub.textContent = fmtMeta ? `${fmtMeta.label} · ${fmtMeta.sub}` : '';
        box.innerHTML = buildCanvasHtml(tpl, state.format);
        box.classList.remove('is-ready');
        box.style.height = '';
        box.style.maxHeight = '';
        lb.removeAttribute('hidden');
        document.body.classList.add('pcs-lightbox-open');
        const fit = () => whenImagesReady(box, () => scalePreviewCanvas(box, state.format));
        requestAnimationFrame(() => requestAnimationFrame(fit));
    }

    function closePreview() {
        $('#pcsLightbox')?.setAttribute('hidden', '');
        document.body.classList.remove('pcs-lightbox-open');
        const box = $('#pcsLightboxPreview');
        if (box) box.innerHTML = '';
    }

    async function downloadPoster(tpl) {
        const host = createExportHost(buildCanvasHtml(tpl, state.format), state.format);
        const canvas = host.querySelector('.pcs-canvas');
        try {
            await exportCanvasElement(canvas, `property-${cfg.propertyId}-${tpl}-${state.format}.png`, state.format);
            toast('دانلود شروع شد');
        } catch (e) {
            toast('خطا در تولید تصویر');
        }
        host.remove();
    }

    function renderFormatBar() {
        const bar = $('#pcsFormatBar');
        if (!bar) return;
        bar.innerHTML = '';
        Object.entries(FORMAT_META).forEach(([key, meta]) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'pcs-format-btn' + (state.format === key ? ' is-active' : '');
            b.innerHTML = `<i class="fas ${meta.icon}" aria-hidden="true"></i><span class="pcs-format-btn__label">${meta.label}</span><span class="pcs-format-btn__sub">${meta.sub}</span>`;
            b.addEventListener('click', () => {
                state.format = key;
                if (state.draft) state.draft.format = key;
                scheduleSave();
                renderFormatBar();
                renderPosters();
                renderStoryboard();
                if (state.editorTemplate && !$('#pcsEditor')?.hasAttribute('hidden')) {
                    renderEditorFormatBar(state.editorTemplate);
                    refreshEditorPreview(state.editorTemplate);
                }
            });
            bar.appendChild(b);
        });
    }

    function renderStoryboard() {
        const track = $('#pcsStoryTrack');
        if (!track || !state.draft?.storyboard?.slides) return;
        track.innerHTML = '';
        const order = state.draft.storyboard.order || [];
        order.forEach((id) => {
            const slide = (state.draft.storyboard.slides || []).find((s) => s.id === id);
            if (!slide) return;
            const el = document.createElement('div');
            el.className = 'pcs-story-slide';
            const frame = document.createElement('div');
            frame.className = 'pcs-story-slide__frame';
            const tpl = slide.type === 'cover' ? 'luxury' : slide.type === 'gallery_price' ? 'gallery' : 'minimal';
            frame.innerHTML = buildCanvasHtml(tpl, 'story');
            el.appendChild(frame);
            track.appendChild(el);
        });
        requestAnimationFrame(() => {
            track.querySelectorAll('.pcs-story-slide__frame').forEach((frame) => {
                scalePreviewCanvas(frame, 'story');
            });
        });
    }

    function renderQuality() {
        const list = $('#pcsQualityList');
        const q = state.session?.quality;
        if (!list || !q) return;
        list.innerHTML = (q.items || []).map((item) => {
            const cls = item.status === 'ok' ? 'is-ok' : 'is-warn';
            const icon = item.status === 'ok' ? 'fa-check-circle' : 'fa-triangle-exclamation';
            return `<li class="${cls}"><i class="fas ${icon}"></i><span>${esc(item.label)}</span></li>`;
        }).join('');
    }

    function renderVisibilityToggles() {
        const wrap = $('#pcsVisibilityToggles');
        const vis = mergeBrand().visibility || {};
        if (!wrap) return;
        wrap.innerHTML = VIS_KEYS.map(([key, label]) => {
            const icon = VIS_ICONS[key] || 'fa-circle';
            return `
            <label class="pcs-switch">
                <input type="checkbox" data-vis-key="${key}" ${vis[key] !== false ? 'checked' : ''}>
                <span class="pcs-switch__track" aria-hidden="true"></span>
                <span class="pcs-switch__label"><i class="fas ${icon}" aria-hidden="true"></i><span>${label}</span></span>
            </label>`;
        }).join('');
        if (state.visTogglesBound) return;
        state.visTogglesBound = true;
        document.addEventListener('change', (e) => {
            const inp = e.target;
            if (!inp?.dataset?.visKey || !inp.closest('#pcsVisibilityToggles')) return;
            const baseVis = mergeBrand().visibility || {};
            state.draft.brand_override = state.draft.brand_override || {};
            state.draft.brand_override.visibility = state.draft.brand_override.visibility || { ...baseVis };
            state.draft.brand_override.visibility[inp.dataset.visKey] = inp.checked;
            scheduleSave();
            ensureSettingsSheetDom();
            requestAnimationFrame(() => {
                ensureSettingsSheetDom();
                if ($('#pcsSettingsSheet')?.hasAttribute('hidden')) {
                    renderPosters();
                    renderStoryboard();
                }
            });
        });
    }

    function ensureSettingsSheetDom() {
        const sheet = $('#pcsSettingsSheet');
        if (!sheet || sheet.hasAttribute('hidden')) return;
        const body = $('#pcsSettingsSheetBody');
        const inner = $('#pcsSidebarInner');
        const sidebar = $('#pcsSidebar');
        if (inner && body && inner.parentElement !== body) body.appendChild(inner);
        if (sidebar) settingsSheetState.sidebar = sidebar;
    }

    function syncColorSwatch(color) {
        const sw = $('#pcsColorSwatch');
        if (sw && color) sw.style.background = color;
    }

    function bindBrandFields() {
        const b = mergeBrand();
        const set = (id, val) => { const el = $(id); if (el) el.value = val || ''; };
        set('#pcsBrandName', b.brand_name);
        set('#pcsConsultantName', b.consultant_name);
        set('#pcsContactPhone', b.contact_phone);
        set('#pcsInstagram', b.instagram);
        const primary = normalizeBrandColor(b.colors?.primary || '#7c3aed');
        set('#pcsPrimaryColor', primary);
        syncColorSwatch(primary);
        if (state.brandFieldsBound) return;
        state.brandFieldsBound = true;
        document.addEventListener('input', (e) => {
            const el = e.target;
            if (!el || !el.closest || !el.closest('#pcsSidebarInner')) return;
            const map = {
                pcsBrandName: 'brand_name',
                pcsConsultantName: 'consultant_name',
                pcsContactPhone: 'contact_phone',
                pcsInstagram: 'instagram',
            };
            const key = map[el.id];
            if (!key && el.id !== 'pcsPrimaryColor') return;
            state.draft.brand_override = state.draft.brand_override || {};
            if (key) state.draft.brand_override[key] = el.value;
            if (el.id === 'pcsPrimaryColor') {
                const norm = normalizeBrandColor(el.value);
                if (norm !== el.value) el.value = norm;
                state.draft.brand_override.colors = { ...(state.draft.brand_override.colors || {}), primary: norm };
                syncColorSwatch(norm);
            }
            scheduleSave();
            renderPosters();
            renderStoryboard();
        });
    }

    function renderHeader() {
        const p = state.session?.property;
        if (!p) return;
        $('#pcsHeaderProperty')?.removeAttribute('hidden');
        $('#pcsHeaderTitle').textContent = p.title || p.headline || '';
        $('#pcsHeaderLocation').textContent = p.location_line || '';
        $('#pcsHeaderPrice').textContent = p.price?.show ? p.price.label : '';
        const thumb = $('#pcsHeaderThumb');
        if (thumb) thumb.innerHTML = p.cover_image ? `<img src="${esc(p.cover_image)}" alt="">` : '';
        const chips = $('#pcsHeaderChips');
        if (chips) {
            chips.innerHTML = [p.property_type, p.area_label].filter(Boolean).map((c) => `<span class="pcs-chip">${esc(c)}</span>`).join('');
        }
    }

    function renderAiStrip() {
        const strip = $('#pcsAiStrip');
        if (!strip) return;
        const titles = (state.draft?.ai?.divar?.titles || []).slice(0, 2);
        const cap = (state.draft?.ai?.social?.captions || [])[0];
        strip.innerHTML = `
            <div class="pcs-ai-mini">
                <div class="pcs-ai-mini__head"><i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i><h4>عنوان‌های دیوار (AI)</h4></div>
                ${titles.length ? titles.map((t) => `<div class="pcs-ai-mini__line">${esc(t.text)}</div>`).join('') : '<p class="pcs-ai-mini__empty">هنوز تولید نشده — از تب آگهی دیوار تولید کنید</p>'}
            </div>
            <div class="pcs-ai-mini">
                <div class="pcs-ai-mini__head"><i class="fas fa-comment-dots" aria-hidden="true"></i><h4>کپشن شبکه‌ها (AI)</h4></div>
                <p class="pcs-ai-mini__line">${cap ? esc(cap.text) : '<span class="pcs-ai-mini__empty">—</span>'}</p>
            </div>`;
    }

    function setFieldValue(id, value) {
        const el = $(id);
        if (el) el.value = value ?? '';
    }

    function syncFormFromDraft() {
        setFieldValue('#pcsDivarBody', state.draft?.ai?.divar?.body || '');
        const tags = (state.draft?.ai?.social?.hashtags || []).join(' ');
        setFieldValue('#pcsHashtags', tags);
        setFieldValue(
            '#pcsWhatsappText',
            state.draft?.ai?.social?.whatsapp_full || state.draft?.ai?.social?.whatsapp_short || '',
        );
        setFieldValue('#pcsTelegramText', state.draft?.ai?.social?.telegram || '');
        renderDivarTitles();
        renderSocialCaptions();
    }

    function renderDivarTitles() {
        const wrap = $('#pcsDivarTitles');
        if (!wrap) return;
        const titles = state.draft?.ai?.divar?.titles || [];
        wrap.innerHTML = titles.map((t, i) => `
            <div class="pcs-ai-card">
                <div class="pcs-ai-card__head"><strong>${esc(t.style)}</strong>
                <div><button type="button" class="pcs-link-btn" data-copy-title="${i}">کپی</button>
                <button type="button" class="pcs-link-btn" data-use-title="${i}">انتخاب</button></div></div>
                <textarea data-title-idx="${i}">${esc(t.text)}</textarea>
            </div>`).join('');
        wrap.querySelectorAll('[data-copy-title]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const i = btn.getAttribute('data-copy-title');
                const ta = wrap.querySelector(`[data-title-idx="${i}"]`);
                navigator.clipboard.writeText(ta?.value || '');
                toast('کپی شد');
            });
        });
        wrap.querySelectorAll('[data-use-title]').forEach((btn) => {
            btn.addEventListener('click', () => {
                state.draft.ai.divar.selected_title_index = parseInt(btn.getAttribute('data-use-title'), 10);
                scheduleSave();
                toast('عنوان انتخاب شد');
            });
        });
        wrap.querySelectorAll('textarea[data-title-idx]').forEach((ta) => {
            ta.addEventListener('input', () => {
                const i = parseInt(ta.dataset.titleIdx, 10);
                if (state.draft.ai.divar.titles[i]) state.draft.ai.divar.titles[i].text = ta.value;
                scheduleSave();
                renderAiStrip();
            });
        });
    }

    function renderSocialCaptions() {
        const wrap = $('#pcsSocialCaptions');
        if (!wrap) return;
        const caps = state.draft?.ai?.social?.captions || [];
        wrap.innerHTML = caps.map((c, i) => `
            <div class="pcs-ai-card"><div class="pcs-ai-card__head"><strong>${esc(c.style)}</strong>
            <button type="button" class="pcs-link-btn" data-copy-cap="${i}">کپی</button></div>
            <textarea data-cap-idx="${i}">${esc(c.text)}</textarea></div>`).join('');
        wrap.querySelectorAll('[data-copy-cap]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const ta = wrap.querySelector(`[data-cap-idx="${btn.getAttribute('data-copy-cap')}"]`);
                navigator.clipboard.writeText(ta?.value || '');
                toast('کپی شد');
            });
        });
    }

    function scheduleSave() {
        clearTimeout(state.saveTimer);
        state.saveTimer = setTimeout(saveDraft, 800);
    }

    async function saveBrandDefaults() {
        const btn = document.querySelector('.pcs-save-brand:not(:disabled)') || $('.pcs-save-brand');
        if (!cfg.brandUrl) {
            toast('آدرس ذخیره برند در دسترس نیست');
            return;
        }
        const token = csrf();
        if (!token) {
            toast('خطای امنیتی: CSRF موجود نیست. صفحه را رفرش کنید.');
            return;
        }
        const payload = {
            brand_name: $('#pcsBrandName')?.value,
            consultant_name: $('#pcsConsultantName')?.value,
            contact_phone: $('#pcsContactPhone')?.value,
            instagram: $('#pcsInstagram')?.value,
            colors: { primary: normalizeBrandColor($('#pcsPrimaryColor')?.value || '#7c3aed') },
            visibility: { ...(mergeBrand().visibility || {}) },
        };
        if (btn) btn.disabled = true;
        try {
            const res = await fetch(cfg.brandUrl, {
                method: 'PUT',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': token,
                    Accept: 'application/json',
                },
                body: JSON.stringify(payload),
            });
            let data = {};
            try {
                data = await res.json();
            } catch (_) { /* ignore */ }
            if (!res.ok || data.ok === false) {
                toast(data.error || 'ذخیره تنظیمات برند ناموفق بود');
                return;
            }
            if (data.brand) {
                state.session = state.session || {};
                state.session.brand_effective = data.brand;
                state.session.brand = data.brand;
            }
            if (state.draft) {
                state.draft.brand_override = {};
                await saveDraft();
            }
            bindBrandFields();
            renderVisibilityToggles();
            ensureSettingsSheetDom();
            renderPosters();
            renderStoryboard();
            toast('تنظیمات برند در پروفایل ذخیره شد');
            closeSettingsSheet();
        } catch (_) {
            toast('خطا در ارتباط با سرور');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async function saveDraft() {
        if (!state.draft) return;
        $('#pcsDivarBody') && (state.draft.ai.divar.body = $('#pcsDivarBody').value);
        const hashTags = ($('#pcsHashtags')?.value || '').split(/\s+/).filter(Boolean);
        state.draft.ai.social.hashtags = hashTags;
        state.draft.ai.social.whatsapp_full = $('#pcsWhatsappText')?.value || '';
        state.draft.ai.social.telegram = $('#pcsTelegramText')?.value || '';
        await fetch(cfg.draftUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify({ draft: state.draft }),
        });
    }

    async function loadSession() {
        const loading = $('#pcsLoading');
        loading?.removeAttribute('hidden');
        try {
            const res = await fetch(cfg.sessionUrl, { headers: { Accept: 'application/json' } });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            state.session = data;
            state.draft = data.draft || {};
            state.draft.ai = state.draft.ai || { divar: { titles: [], body: '', selected_title_index: 0 }, social: { captions: [], hashtags: [] } };
            state.draft.ai.divar = state.draft.ai.divar || { titles: [], body: '', selected_title_index: 0 };
            state.draft.ai.social = state.draft.ai.social || { captions: [], hashtags: [] };
            state.format = state.draft.format || 'story';
            await ensurePersianFonts();
            renderHeader();
            renderFormatBar();
            renderPosters();
            renderStoryboard();
            bindPosterCarousel();
            renderQuality();
            renderVisibilityToggles();
            bindBrandFields();
            syncFormFromDraft();
            renderAiStrip();
            renderSharePanel();
            setTab(state.draft.active_tab || 'posters');
            requestAnimationFrame(() => rescaleAllPreviews());
        } finally {
            loading?.setAttribute('hidden', '');
        }
    }

    function rescaleAllPreviews() {
        $$('.pcs-poster-card__preview').forEach((wrap) => scalePreviewCanvas(wrap, state.format));
        $$('.pcs-story-slide__frame').forEach((wrap) => scalePreviewCanvas(wrap, 'story'));
    }

    function renderSharePanel() {
        const grid = $('#pcsShareGrid');
        if (!grid) return;
        const url = state.session?.property?.public_share_url || '';
        grid.innerHTML = `
            <div class="pcs-share-card">
                <p class="pcs-share-card__label">لینک عمومی فایل</p>
                <input type="text" class="pcs-input" id="pcsShareUrlField" readonly dir="ltr" value="${esc(url)}">
                <button type="button" class="pcs-btn pcs-btn--soft pcs-btn--block" id="pcsShareTabCopy">کپی لینک</button>
            </div>
            <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--block" id="pcsShareTabDivar">رفتن به تب آگهی دیوار</button>`;
        $('#pcsShareTabCopy')?.addEventListener('click', () => {
            if (!url) { toast('لینک عمومی موجود نیست'); return; }
            navigator.clipboard.writeText(url);
            toast('لینک کپی شد');
        });
        $('#pcsShareTabDivar')?.addEventListener('click', () => setTab('divar'));
    }

    function setTab(tab) {
        $$('.pcs-tab').forEach((t) => {
            const on = t.dataset.pcsTab === tab;
            t.classList.toggle('is-active', on);
            t.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        const activeTab = $(`.pcs-tab[data-pcs-tab="${tab}"]`);
        if (activeTab && isMobileViewport()) {
            activeTab.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
        }
        $$('.pcs-panel').forEach((p) => {
            const on = p.dataset.pcsPanel === tab;
            p.classList.toggle('is-active', on);
            if (on) p.removeAttribute('hidden');
            else p.setAttribute('hidden', '');
        });
        if (state.draft) {
            state.draft.active_tab = tab;
            scheduleSave();
        }
        syncFooterForTab(tab);
    }

    function syncFooterForTab(tab) {
        const footer = $('#pcsFooter');
        const dl = $('#pcsDownloadAll');
        if (!footer) return;
        const mob = isMobileViewport();
        const showDl = tab === 'posters';
        const showQuick = tab === 'posters' || tab === 'share';
        if (dl) dl.hidden = !showDl;
        footer.hidden = mob && !showQuick && !showDl;
        footer.classList.toggle('pcs-footer--minimal', mob && tab !== 'posters');
    }

    function mountToBody(el) {
        if (el && el.parentElement !== document.body) document.body.appendChild(el);
    }

    function closeMobileMore() {
        const more = document.getElementById('wsCrmPdMobMore');
        if (!more || !more.classList.contains('is-open')) return;
        more.classList.remove('is-open');
        more.setAttribute('hidden', '');
        more.setAttribute('aria-hidden', 'true');
    }

    const scrollLock = { y: 0, active: false };

    function lockPageScroll() {
        if (scrollLock.active) return;
        scrollLock.y = window.scrollY || document.documentElement.scrollTop || 0;
        scrollLock.active = true;
        document.documentElement.classList.add('pcs-modal-open');
        document.body.classList.add('pcs-modal-open', 'ws-modal-open');
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollLock.y}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        document.body.style.overflow = 'hidden';
    }

    function unlockPageScroll() {
        if (!scrollLock.active) return;
        scrollLock.active = false;
        document.documentElement.classList.remove('pcs-modal-open');
        document.body.classList.remove('pcs-modal-open', 'ws-modal-open');
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        window.scrollTo(0, scrollLock.y);
    }

    function pcsScrollOverflow(node) {
        if (!node || node.nodeType !== 1) return { y: false, x: false };
        const style = window.getComputedStyle(node);
        const oy = style.overflowY;
        const ox = style.overflowX;
        const oyScroll = oy === 'auto' || oy === 'scroll' || oy === 'overlay';
        const oxScroll = ox === 'auto' || ox === 'scroll' || ox === 'overlay';
        const canY = oyScroll && node.scrollHeight > node.clientHeight + 1;
        const canX = oxScroll && node.scrollWidth > node.clientWidth + 1;
        return { y: canY, x: canX };
    }

    function findPcsScrollableAncestor(el, root) {
        let node = el;
        while (node && node !== root && node !== document.documentElement) {
            const { y, x } = pcsScrollOverflow(node);
            if (y || x) return node;
            node = node.parentElement;
        }
        return null;
    }

    function pcsOverlayRootFor(target) {
        const modal = $('#pcsModal');
        const sheet = $('#pcsSettingsSheet');
        if (sheet && !sheet.hasAttribute('hidden') && sheet.contains(target)) return sheet;
        if (modal && !modal.hasAttribute('hidden') && modal.contains(target)) return modal;
        return null;
    }

    function onPcsTouchMove(e) {
        const modal = $('#pcsModal');
        const sheet = $('#pcsSettingsSheet');
        const modalOpen = modal && !modal.hasAttribute('hidden');
        const sheetOpen = sheet && !sheet.hasAttribute('hidden');
        if (!modalOpen && !sheetOpen) return;

        const root = pcsOverlayRootFor(e.target);
        if (!root) {
            e.preventDefault();
            return;
        }
        if (findPcsScrollableAncestor(e.target, root)) return;
        e.preventDefault();
    }

    function openModal() {
        const modal = $('#pcsModal');
        if (!modal) return;
        mountToBody(modal);
        mountToBody($('#pcsSettingsSheet'));
        closeMobileMore();
        resetStudioShellState();
        lockPageScroll();
        modal.removeAttribute('hidden');
        syncViewportMode();
        loadSession().catch(() => toast('بارگذاری استودیو ناموفق بود'));
    }

    function closeModal() {
        closePreview();
        closeSettingsSheet();
        if (!$('#pcsEditor')?.hasAttribute('hidden')) {
            closeEditor();
            if (!$('#pcsEditor')?.hasAttribute('hidden')) return;
        }
        resetStudioShellState();
        $('#pcsModal')?.setAttribute('hidden', '');
        unlockPageScroll();
        saveDraft();
    }

    const settingsSheetState = { sidebar: null, footParent: null };

    function openSettingsSheet() {
        const inner = $('#pcsSidebarInner');
        const body = $('#pcsSettingsSheetBody');
        const sheet = $('#pcsSettingsSheet');
        const sidebar = $('#pcsSidebar');
        if (!inner || !body || !sheet || !sidebar) return;
        mountToBody(sheet);
        settingsSheetState.sidebar = sidebar;
        body.appendChild(inner);
        document.body.classList.add('pcs-settings-open');
        sheet.removeAttribute('hidden');
        ensureSettingsSheetDom();
    }

    function closeSettingsSheet() {
        const inner = $('#pcsSidebarInner');
        const sheet = $('#pcsSettingsSheet');
        const sidebar = settingsSheetState.sidebar || $('#pcsSidebar');
        const foot = $('#pcsSidebarFoot');
        if (inner && sidebar) {
            if (foot && foot.parentElement === sidebar) sidebar.insertBefore(inner, foot);
            else sidebar.prepend(inner);
        }
        document.body.classList.remove('pcs-settings-open');
        sheet?.setAttribute('hidden', '');
        if (!$('#pcsSettingsSheet')?.hasAttribute('hidden')) return;
        requestAnimationFrame(() => {
            renderPosters();
            renderStoryboard();
        });
    }

    function readEditorForm(tpl) {
        const controls = editorControlsEl();
        const imgs = propertyImageList();
        const prev = state.editorBuffer || posterConfigFromDraft(tpl);
        const cropVal = parseInt(controls?.querySelector('#pcsEditCrop')?.value || String(prev.crop_y ?? 50), 10);
        const primary = parseInt(controls?.querySelector('#pcsEditImage')?.value || String(prev.primary_image_index || 0), 10);
        let imageOrder = prev.image_order && prev.image_order.length ? prev.image_order.slice() : imgs.map((_, i) => i);
        if (tpl === 'gallery') {
            const slots = [0, 1, 2].map((slot) => {
                const inp = controls?.querySelector(`[data-pcs-gallery-slot="${slot}"]`);
                const fallback = editorImageOrderForGallery(imgs, prev)[slot];
                const v = parseInt(inp?.value || String(fallback), 10);
                return Number.isFinite(v) ? v : slot;
            });
            imageOrder = buildGalleryImageOrder(imgs, slots);
        }
        const fontBtn = controls?.querySelector('.pcs-editor__font-btn.is-active');
        return {
            headline: (controls?.querySelector('#pcsEditHeadline')?.value || '').trim(),
            crop_y: Math.min(100, Math.max(0, cropVal)),
            primary_image_index: imgs.length ? Math.min(imgs.length - 1, Math.max(0, primary)) : 0,
            image_order: imageOrder,
            img_brightness: parseInt(controls?.querySelector('[data-pcs-edit-range="brightness"]')?.value || String(prev.img_brightness ?? 100), 10),
            img_blur: parseInt(controls?.querySelector('[data-pcs-edit-range="blur"]')?.value || String(prev.img_blur ?? 0), 10),
            img_opacity: parseInt(controls?.querySelector('[data-pcs-edit-range="opacity"]')?.value || String(prev.img_opacity ?? 100), 10),
            headline_scale: parseInt(controls?.querySelector('[data-pcs-edit-range="headline_scale"]')?.value || String(prev.headline_scale ?? 100), 10),
            price_scale: parseInt(controls?.querySelector('[data-pcs-edit-range="price_scale"]')?.value || String(prev.price_scale ?? 100), 10),
            font_key: fontBtn?.getAttribute('data-pcs-font-key') || prev.font_key || 'vazirmatn',
            pip_enabled: !!controls?.querySelector('[data-pcs-pip-enabled]')?.checked,
            pip_image_index: imgs.length
                ? Math.min(imgs.length - 1, Math.max(0, parseInt(controls?.querySelector('#pcsEditPipImage')?.value || String(prev.pip_image_index ?? 1), 10)))
                : 0,
            pip_corner: controls?.querySelector('[data-pcs-pip-corner].is-active')?.getAttribute('data-pcs-pip-corner') || prev.pip_corner || 'br',
            pip_size: controls?.querySelector('[data-pcs-pip-size].is-active')?.getAttribute('data-pcs-pip-size') || prev.pip_size || 'm',
            pip_shape: controls?.querySelector('[data-pcs-pip-shape].is-active')?.getAttribute('data-pcs-pip-shape') || prev.pip_shape || 'rounded',
            pip_border: controls?.querySelector('[data-pcs-pip-border].is-active')?.getAttribute('data-pcs-pip-border') || prev.pip_border || 'light',
            pip_crop_y: parseInt(controls?.querySelector('[data-pcs-edit-range="pip_crop"]')?.value || String(prev.pip_crop_y ?? 50), 10),
            pip_tilt: parseInt(controls?.querySelector('[data-pcs-edit-range="pip_tilt"]')?.value || String(prev.pip_tilt ?? 0), 10),
            hero_vignette: parseInt(controls?.querySelector('[data-pcs-edit-range="hero_vignette"]')?.value || String(prev.hero_vignette ?? 0), 10),
            hero_warmth: controls?.querySelector('[data-pcs-hero-warmth].is-active')?.getAttribute('data-pcs-hero-warmth') || prev.hero_warmth || 'neutral',
        };
    }

    function updateEditorBufferFromForm(tpl) {
        if (!state.editorBuffer) return;
        Object.assign(state.editorBuffer, readEditorForm(tpl));
        syncEditorDirtyFlag();
    }

    function commitEditorToDraft(tpl) {
        if (!state.draft || !tpl) return;
        updateEditorBufferFromForm(tpl);
        state.draft.posters = state.draft.posters || {};
        state.draft.posters[tpl] = { ...state.editorBuffer };
    }

    function clearEditorSession() {
        state.editorBuffer = null;
        state.editorTemplate = null;
        state.editorSnapshot = null;
        state.editorDirty = false;
        $('#pcsEditor')?.classList.remove('pcs-editor--dirty');
    }

    function resetEditorPreviewWrap(wrap) {
        if (!wrap) return;
        wrap.classList.remove('is-ready');
        wrap.style.height = '';
        wrap.style.minHeight = '';
        wrap.style.maxHeight = '';
        wrap.style.overflow = '';
        wrap.style.display = '';
        wrap.style.justifyContent = '';
        wrap.style.alignItems = '';
    }

    function updateEditorLiveMeta(conf, tpl) {
        const meta = $('#pcsEditorLiveMeta');
        if (!meta || !conf) return;
        const imgs = propertyImageList();
        if (tpl === 'gallery') {
            const ord = editorImageOrderForGallery(imgs, conf);
            const pip = conf.pip_enabled ? ' · عکس در عکس' : '';
            meta.textContent = `گالری: ${ord.map((i) => i + 1).join(' · ')} · قاب ${conf.crop_y}%${pip}`;
            return;
        }
        const pipPart = conf.pip_enabled ? ` · عکس در عکس ${(conf.pip_image_index ?? 0) + 1}` : '';
        meta.textContent = imgs.length
            ? `تصویر ${(conf.primary_image_index || 0) + 1} · قاب ${conf.crop_y}%${pipPart}`
            : '';
    }

    function refreshEditorPreview(tpl) {
        const activeTpl = tpl || state.editorTemplate;
        if (!activeTpl) return;
        updateEditorBufferFromForm(activeTpl);
        const conf = state.editorBuffer ? { ...state.editorBuffer } : null;
        const prev = $('#pcsEditorPreview');
        if (!prev || !conf) return;
        resetEditorPreviewWrap(prev);
        prev.innerHTML = buildCanvasHtml(activeTpl, state.format, conf);
        updateEditorLiveMeta(conf, activeTpl);
        whenImagesReady(prev, () => scalePreviewCanvas(prev, state.format));
        const controls = editorControlsEl();
        const cropLbl = controls?.querySelector('#pcsEditCropValue');
        if (cropLbl) cropLbl.textContent = `${conf.crop_y}%`;
        const headCount = controls?.querySelector('#pcsEditHeadlineCount');
        if (headCount) headCount.textContent = `${(controls.querySelector('#pcsEditHeadline')?.value || '').length} کاراکتر`;
        syncCropPresetActive(conf.crop_y);
        controls?.querySelectorAll('[data-pcs-edit-range]').forEach((inp) => {
            const key = inp.getAttribute('data-pcs-edit-range');
            const lbl = controls.querySelector(`[data-pcs-range-val="${key}"]`);
            if (!lbl) return;
            if (key === 'blur') lbl.textContent = `${conf.img_blur}px`;
            else if (key === 'pip_tilt') lbl.textContent = `${conf.pip_tilt}°`;
            else if (key === 'pip_crop') lbl.textContent = `${conf.pip_crop_y}%`;
            else if (key === 'hero_vignette') lbl.textContent = `${conf.hero_vignette}%`;
            else if (key === 'brightness' || key === 'opacity' || key === 'headline_scale' || key === 'price_scale') {
                lbl.textContent = `${conf[key === 'headline_scale' ? 'headline_scale' : key === 'price_scale' ? 'price_scale' : key === 'brightness' ? 'img_brightness' : 'img_opacity']}%`;
            }
        });
    }

    function resetStudioShellState() {
        const modal = $('#pcsModal');
        modal?.classList.remove('pcs-modal--editor');
        $('#pcsEditor')?.setAttribute('hidden', '');
        clearEditorSession();
        const body = modal ? $('.pcs-body', modal) : null;
        if (body) body.scrollTop = 0;
    }

    function restoreStudioAfterEditor() {
        resetStudioShellState();
        requestAnimationFrame(() => {
            rescaleAllPreviews();
            const body = $('.pcs-body', $('#pcsModal'));
            if (body) body.scrollTop = 0;
        });
    }

    function closeEditor(force) {
        if (!force && state.editorDirty) {
            const ok = window.confirm('تغییرات ذخیره نشده‌اند. بدون ذخیره ببندیم؟');
            if (!ok) return;
        }
        restoreStudioAfterEditor();
    }

    function bindEditorControlEvents(tpl, controls) {
        bindEditorOrderEvents(tpl, controls);
    }

    function bindEditorSettingsDelegation() {
        const pane = document.querySelector('.pcs-editor__settings-pane');
        if (!pane || pane.dataset.pcsEditorDelegated) return;
        pane.dataset.pcsEditorDelegated = '1';

        pane.addEventListener('input', (e) => {
            if (!state.editorTemplate) return;
            const t = e.target;
            if (!t.closest('#pcsEditorControls')) return;
            if (t.matches('#pcsEditHeadline, #pcsEditCrop, [data-pcs-edit-range]')) {
                refreshEditorPreview(state.editorTemplate);
            }
        });

        pane.addEventListener('change', (e) => {
            if (!state.editorTemplate) return;
            if (e.target.matches('[data-pcs-pip-enabled]')) {
                const controls = editorControlsEl();
                controls?.querySelector('[data-pcs-pip-panel]')?.classList.toggle('is-open', e.target.checked);
                refreshEditorPreview(state.editorTemplate);
            }
        });

        pane.addEventListener('click', (e) => {
            const tpl = state.editorTemplate;
            if (!tpl) return;
            const controls = editorControlsEl();
            if (!controls?.contains(e.target)) return;

            if (e.target.closest('#pcsEditHeadlineFromFile')) {
                const inp = controls.querySelector('#pcsEditHeadline');
                if (inp) inp.value = defaultPropertyHeadline();
                refreshEditorPreview(tpl);
                return;
            }
            if (e.target.closest('#pcsEditHeadlineClear')) {
                const inp = controls.querySelector('#pcsEditHeadline');
                if (inp) inp.value = '';
                refreshEditorPreview(tpl);
                return;
            }

            const cropBtn = e.target.closest('[data-pcs-crop-preset]');
            if (cropBtn) {
                const v = cropBtn.getAttribute('data-pcs-crop-preset');
                const crop = controls.querySelector('#pcsEditCrop');
                if (crop) crop.value = v;
                controls.querySelectorAll('[data-pcs-crop-preset]').forEach((b) => {
                    b.classList.toggle('is-active', b === cropBtn);
                });
                refreshEditorPreview(tpl);
                return;
            }

            const primaryTile = e.target.closest('.pcs-editor__img-tile[data-pcs-img-idx]');
            if (primaryTile?.closest('[data-pcs-primary-grid]')) {
                const idx = parseInt(primaryTile.getAttribute('data-pcs-img-idx') || '0', 10);
                const hidden = controls.querySelector('#pcsEditImage');
                if (hidden) hidden.value = String(idx);
                controls.querySelectorAll('[data-pcs-primary-grid] .pcs-editor__img-tile').forEach((tile) => {
                    const on = tile === primaryTile;
                    tile.classList.toggle('is-selected', on);
                    tile.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }

            const galleryTile = e.target.closest('[data-pcs-gallery-slot-pick]');
            if (galleryTile) {
                const slot = galleryTile.getAttribute('data-pcs-gallery-slot-pick');
                const idx = parseInt(galleryTile.getAttribute('data-pcs-img-idx') || '0', 10);
                const hidden = controls.querySelector(`[data-pcs-gallery-slot="${slot}"]`);
                if (hidden) hidden.value = String(idx);
                controls.querySelectorAll(`[data-pcs-gallery-slot-pick="${slot}"]`).forEach((tile) => {
                    const on = tile === galleryTile;
                    tile.classList.toggle('is-selected', on);
                    tile.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }

            const fontBtn = e.target.closest('[data-pcs-font-key]');
            if (fontBtn) {
                controls.querySelectorAll('[data-pcs-font-key]').forEach((b) => {
                    const on = b === fontBtn;
                    b.classList.toggle('is-active', on);
                    b.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }

            const pipTile = e.target.closest('.pcs-editor__img-tile[data-pcs-img-idx]');
            if (pipTile?.closest('[data-pcs-pip-grid]')) {
                const idx = parseInt(pipTile.getAttribute('data-pcs-img-idx') || '0', 10);
                const hidden = controls.querySelector('#pcsEditPipImage');
                if (hidden) hidden.value = String(idx);
                controls.querySelectorAll('[data-pcs-pip-grid] .pcs-editor__img-tile').forEach((tile) => {
                    const on = tile === pipTile;
                    tile.classList.toggle('is-selected', on);
                    tile.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }

            const chip = e.target.closest('[data-pcs-pip-corner], [data-pcs-pip-size], [data-pcs-pip-shape], [data-pcs-pip-border], [data-pcs-hero-warmth]');
            if (chip) {
                const group = chip.closest('.pcs-editor__chip-row');
                group?.querySelectorAll('.pcs-editor__chip').forEach((b) => {
                    b.classList.toggle('is-active', b === chip);
                });
                refreshEditorPreview(tpl);
                return;
            }

            const comp = e.target.closest('[data-pcs-composition]');
            if (comp) {
                applyCompositionPreset(comp.getAttribute('data-pcs-composition'));
            }
        });
    }

    function openEditor(tpl) {
        if (!state.draft) {
            toast('استودیو هنوز بارگذاری نشده است');
            return;
        }
        state.editorTemplate = tpl;
        initEditorBuffer(tpl);
        const meta = TEMPLATE_META[tpl] || { label: tpl, icon: 'fa-image' };
        const fmtMeta = FORMAT_META[state.format] || FORMAT_META.story;
        const conf = state.editorBuffer;
        const imgs = propertyImageList();
        const galleryOrder = editorImageOrderForGallery(imgs, conf);

        const badge = $('#pcsEditorTplBadge');
        if (badge) badge.innerHTML = `<i class="fas ${meta.icon}" aria-hidden="true"></i> ${esc(meta.label)}`;
        const fmtPill = $('#pcsEditorFormatPill');
        if (fmtPill) {
            fmtPill.hidden = false;
            fmtPill.innerHTML = `<i class="fas ${fmtMeta.icon}" aria-hidden="true"></i> ${esc(fmtMeta.label)} · ${esc(fmtMeta.sub)}`;
        }
        const dlBtn = $('#pcsEditorDownload');
        if (dlBtn) dlBtn.hidden = false;

        const controls = $('#pcsEditorControls');
        if (controls) {
            const headlineVal = conf.headline || defaultPropertyHeadline();
            const galleryBlock = tpl === 'gallery' && imgs.length
                ? `<section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-images" aria-hidden="true"></i> تصاویر گالری</h4>
                    <p class="pcs-editor__section-hint">برای هر بخش چیدمان یک تصویر انتخاب کنید — پیش‌نمایش بلافاصله به‌روز می‌شود</p>
                    <div class="pcs-editor__gallery-slots">${editorGallerySlotGrid(imgs, galleryOrder)}</div>
                </section>`
                : '';

            controls.innerHTML = `
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-expand" aria-hidden="true"></i> فرمت خروجی</h4>
                    <p class="pcs-editor__section-hint">پیش‌نمایش با همان ابعاد دانلود به‌روز می‌شود</p>
                    <div class="pcs-editor__format-bar" id="pcsEditFormatBar"></div>
                </section>
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-pen-fancy" aria-hidden="true"></i> عنوان تبلیغاتی</h4>
                    <p class="pcs-editor__section-hint">متن اصلی روی پوستر — کوتاه و جذاب باشد</p>
                    <div class="pcs-editor__headline-row">
                        <input type="text" id="pcsEditHeadline" class="pcs-input" maxlength="120"
                            placeholder="مثلاً آپارتمان نوساز با نور عالی" value="${esc(headlineVal)}">
                        <button type="button" class="pcs-btn pcs-btn--soft pcs-btn--sm" id="pcsEditHeadlineFromFile">
                            <i class="fas fa-file-lines" aria-hidden="true"></i> از فایل
                        </button>
                        <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--sm" id="pcsEditHeadlineClear" title="خالی = عنوان پیش‌فرض فایل">
                            <i class="fas fa-eraser" aria-hidden="true"></i>
                        </button>
                    </div>
                    <span class="pcs-editor__meta" id="pcsEditHeadlineCount">${headlineVal.length} کاراکتر</span>
                </section>
                ${tpl !== 'gallery' ? `<section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-image" aria-hidden="true"></i> تصویر شاخص</h4>
                    <p class="pcs-editor__section-hint">تصویر بزرگ یا پس‌زمینه پوستر — بلافاصله در پیش‌نمایش زنده اعمال می‌شود</p>
                    <input type="hidden" id="pcsEditImage" value="${conf.primary_image_index || 0}">
                    ${editorThumbGrid(imgs, conf.primary_image_index || 0, 'primary')}
                </section>` : ''}
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-crop-simple" aria-hidden="true"></i> قاب‌بندی تصویر</h4>
                    <p class="pcs-editor__section-hint">کدام بخش تصویر در کادر دیده شود${tpl === 'gallery' ? ' (روی همه تصاویر گالری)' : ''}</p>
                    <div class="pcs-editor__crop-presets" role="group" aria-label="پیش‌تنظیم قاب">
                        <button type="button" class="pcs-editor__crop-preset" data-pcs-crop-preset="18">بالا</button>
                        <button type="button" class="pcs-editor__crop-preset is-active" data-pcs-crop-preset="50">وسط</button>
                        <button type="button" class="pcs-editor__crop-preset" data-pcs-crop-preset="82">پایین</button>
                    </div>
                    <div class="pcs-editor__range-row">
                        <input type="range" id="pcsEditCrop" min="0" max="100" value="${conf.crop_y ?? 50}" aria-label="موقعیت عمودی تصویر">
                        <span class="pcs-editor__range-value" id="pcsEditCropValue">${conf.crop_y ?? 50}%</span>
                    </div>
                </section>
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i> ترکیب حرفه‌ای</h4>
                    <p class="pcs-editor__section-hint">یک کلیک — استایل آماده برای استوری و پست</p>
                    ${editorCompositionPresets()}
                </section>
                ${editorPipSection(imgs, conf)}
                ${editorHeroMoodSection(conf)}
                ${imgs.length > 1 ? `<section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-sort" aria-hidden="true"></i> ترتیب تصاویر فایل</h4>
                    <p class="pcs-editor__section-hint">برای جابه‌جایی در گالری و چیدمان، تصاویر را بالا یا پایین ببرید</p>
                    ${editorImageOrderPanel(imgs, conf.image_order)}
                </section>` : ''}
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-adjust" aria-hidden="true"></i> افکت تصویر شاخص</h4>
                    <label class="pcs-editor__range-label">روشنایی <span data-pcs-range-val="brightness">${conf.img_brightness ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="brightness" min="40" max="160" value="${conf.img_brightness ?? 100}">
                    <label class="pcs-editor__range-label">تاری <span data-pcs-range-val="blur">${conf.img_blur ?? 0}px</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="blur" min="0" max="12" value="${conf.img_blur ?? 0}">
                    <label class="pcs-editor__range-label">شفافیت <span data-pcs-range-val="opacity">${conf.img_opacity ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="opacity" min="35" max="100" value="${conf.img_opacity ?? 100}">
                </section>
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-font" aria-hidden="true"></i> تایپوگرافی</h4>
                    <p class="pcs-editor__section-hint">۵ فونت فارسی — روی عنوان و قیمت اعمال می‌شود</p>
                    ${editorFontPicker(conf.font_key || 'vazirmatn')}
                    <label class="pcs-editor__range-label">اندازه عنوان <span data-pcs-range-val="headline_scale">${conf.headline_scale ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="headline_scale" min="70" max="140" value="${conf.headline_scale ?? 100}">
                    <label class="pcs-editor__range-label">اندازه قیمت <span data-pcs-range-val="price_scale">${conf.price_scale ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="price_scale" min="70" max="140" value="${conf.price_scale ?? 100}">
                </section>
                ${galleryBlock}
                <div class="pcs-editor__tip">
                    <i class="fas fa-lightbulb" aria-hidden="true"></i>
                    <span>برای دیدن جزئیات بیشتر، در موبایل بین پیش‌نمایش و تنظیمات جابه‌جا شوید.</span>
                </div>`;

            bindEditorControlEvents(tpl, controls);
            renderEditorFormatBar(tpl);
            syncCropPresetActive(conf.crop_y ?? 50);
        }

        $('#pcsEditor')?.removeAttribute('hidden');
        $('#pcsModal')?.classList.add('pcs-modal--editor');
        setEditorMobPane('preview');
        refreshEditorPreview(tpl);
    }

    function syncCropPresetActive(val) {
        const controls = $('#pcsEditorControls');
        if (!controls) return;
        const presets = ['18', '50', '82'];
        controls.querySelectorAll('[data-pcs-crop-preset]').forEach((b) => {
            const p = parseInt(b.getAttribute('data-pcs-crop-preset') || '50', 10);
            b.classList.toggle('is-active', Math.abs(val - p) <= 8);
        });
    }

    async function aiPost(action, body) {
        const res = await fetch(`${cfg.aiBaseUrl}${action}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body || {}),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'خطا');
        return data;
    }

    function bindEvents() {
        bindEditorSettingsDelegation();
        document.addEventListener('click', (e) => {
            const trigger = e.target.closest('[data-pcs-open]');
            if (!trigger) return;
            e.preventDefault();
            e.stopPropagation();
            openModal();
        }, true);
        $$('[data-pcs-close]').forEach((el) => el.addEventListener('click', closeModal));
        $$('[data-pcs-lightbox-close]').forEach((el) => el.addEventListener('click', closePreview));
        $('#pcsLightboxDownload')?.addEventListener('click', () => {
            const tpl = state.previewTemplate;
            if (tpl) downloadPoster(tpl);
        });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (!$('#pcsEditor')?.hasAttribute('hidden')) {
                closeEditor();
                return;
            }
            if (!$('#pcsLightbox')?.hasAttribute('hidden')) {
                closePreview();
                return;
            }
            if (!$('#pcsModal')?.hasAttribute('hidden')) closeModal();
        });
        $$('.pcs-tab').forEach((t) => t.addEventListener('click', () => setTab(t.dataset.pcsTab)));
        $('#pcsGenDivarTitles')?.addEventListener('click', async () => {
            try {
                const data = await aiPost('divar-titles');
                state.draft.ai.divar.titles = data.data?.titles || [];
                scheduleSave();
                renderDivarTitles();
                renderAiStrip();
            } catch (e) { toast(e.message || 'خطای AI'); }
        });
        $('#pcsGenDivarBody')?.addEventListener('click', async () => {
            try {
                const style = $('#pcsDivarBodyStyle')?.value || 'formal';
                const data = await aiPost('divar-body', { style });
                state.draft.ai.divar.body = data.data?.body || '';
                $('#pcsDivarBody').value = state.draft.ai.divar.body;
                scheduleSave();
            } catch (e) { toast(e.message || 'خطای AI'); }
        });
        $('#pcsGenSocial')?.addEventListener('click', async () => {
            try {
                const data = await aiPost('social');
                const d = data.data || {};
                state.draft.ai.social.captions = d.captions || [];
                state.draft.ai.social.hashtags = d.hashtags || [];
                state.draft.ai.social.whatsapp_short = d.whatsapp_short || '';
                state.draft.ai.social.whatsapp_full = d.whatsapp_full || '';
                state.draft.ai.social.telegram = d.telegram || '';
                state.draft.ai.social.ctas = d.ctas || [];
                syncFormFromDraft();
                scheduleSave();
                renderAiStrip();
            } catch (e) { toast(e.message || 'خطای AI'); }
        });
        $('#pcsCopyDivarBundle')?.addEventListener('click', () => {
            const idx = state.draft?.ai?.divar?.selected_title_index || 0;
            const title = state.draft?.ai?.divar?.titles?.[idx]?.text || '';
            const body = $('#pcsDivarBody')?.value || '';
            navigator.clipboard.writeText(`${title}\n\n${body}`.trim());
            toast('عنوان و متن کپی شد');
        });
        $('#pcsCopyShareLink')?.addEventListener('click', () => {
            const url = state.session?.property?.public_share_url || '';
            if (!url) { toast('لینک عمومی موجود نیست'); return; }
            navigator.clipboard.writeText(url);
            toast('لینک کپی شد');
        });
        $('#pcsShareWhatsapp')?.addEventListener('click', () => {
            const text = $('#pcsWhatsappText')?.value || state.session?.property?.title || '';
            const url = state.session?.property?.public_share_url || '';
            const msg = encodeURIComponent(`${text}\n${url}`.trim());
            window.open(`https://wa.me/?text=${msg}`, '_blank', 'noopener');
        });
        $('#pcsShareTelegram')?.addEventListener('click', () => {
            const text = $('#pcsTelegramText')?.value || '';
            const url = state.session?.property?.public_share_url || '';
            const msg = encodeURIComponent(`${text}\n${url}`.trim());
            window.open(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${msg}`, '_blank', 'noopener');
        });
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.pcs-save-brand')) return;
            e.preventDefault();
            saveBrandDefaults();
        });
        $('#pcsPosterGrid')?.addEventListener('click', (e) => {
            const dl = e.target.closest('[data-pcs-dl]');
            const ed = e.target.closest('[data-pcs-edit]');
            const pr = e.target.closest('[data-pcs-preview]');
            if (dl) downloadPoster(dl.getAttribute('data-pcs-dl'));
            if (ed) openEditor(ed.getAttribute('data-pcs-edit'));
            if (pr) openPreview(pr.getAttribute('data-pcs-preview'));
        });
        $('#pcsDownloadAll')?.addEventListener('click', async () => {
            try {
                await ensureLibs();
                await ensurePersianFonts();
                const zip = new JSZip();
                for (const tpl of TEMPLATES) {
                    const host = createExportHost(buildCanvasHtml(tpl, state.format), state.format);
                    const canvas = host.querySelector('.pcs-canvas');
                    try {
                        const shot = await rasterizeCanvas(canvas, state.format);
                        const blob = await new Promise((r) => shot.toBlob(r, 'image/png'));
                        zip.file(`${tpl}-${state.format}.png`, blob);
                    } catch (_) { /* skip */ }
                    host.remove();
                }
                const out = await zip.generateAsync({ type: 'blob' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(out);
                a.download = `property-${cfg.propertyId}-posters.zip`;
                a.click();
                toast('فایل ZIP آماده شد');
            } catch (_) {
                toast('خطا در ساخت ZIP');
            }
        });
        $('#pcsStoryDownloadAll')?.addEventListener('click', async () => {
            try {
                await ensureLibs();
                await ensurePersianFonts();
                const zip = new JSZip();
                const order = state.draft?.storyboard?.order || [];
                let idx = 0;
                for (const id of order) {
                    const slide = (state.draft?.storyboard?.slides || []).find((s) => s.id === id);
                    if (!slide) continue;
                    const tpl = slide.type === 'cover' ? 'luxury' : slide.type === 'gallery_price' ? 'gallery' : 'minimal';
                    const host = createExportHost(buildCanvasHtml(tpl, 'story'), 'story');
                    const canvas = host.querySelector('.pcs-canvas');
                    try {
                        const shot = await rasterizeCanvas(canvas, 'story');
                        const blob = await new Promise((r) => shot.toBlob(r, 'image/png'));
                        zip.file(`story-${String(++idx).padStart(2, '0')}-${tpl}.png`, blob);
                    } catch (_) { /* skip */ }
                    host.remove();
                }
                if (!idx) { toast('اسلایدی برای دانلود نیست'); return; }
                const out = await zip.generateAsync({ type: 'blob' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(out);
                a.download = `property-${cfg.propertyId}-storyboard.zip`;
                a.click();
                toast('استوری‌برد دانلود شد');
            } catch (_) {
                toast('خطا در دانلود استوری‌برد');
            }
        });
        $('#pcsOpenSettings')?.addEventListener('click', openSettingsSheet);
        $('#pcsOpenSettingsHead')?.addEventListener('click', openSettingsSheet);
        $('#pcsFooterSettings')?.addEventListener('click', openSettingsSheet);
        $$('[data-pcs-settings-close]').forEach((el) => el.addEventListener('click', closeSettingsSheet));
        $('#pcsEditorClose')?.addEventListener('click', closeEditor);
        $('#pcsEditorBack')?.addEventListener('click', closeEditor);
        $('#pcsEditorCancel')?.addEventListener('click', closeEditor);
        $('#pcsEditorSave')?.addEventListener('click', () => {
            const tpl = state.editorTemplate;
            if (!tpl || !state.draft) return;
            commitEditorToDraft(tpl);
            scheduleSave();
            renderPosters();
            closeEditor(true);
            toast('تغییرات پوستر ذخیره شد');
        });
        $('#pcsEditorDownload')?.addEventListener('click', async () => {
            const tpl = state.editorTemplate;
            if (!tpl) return;
            updateEditorBufferFromForm(tpl);
            await downloadPoster(tpl);
        });
        $('#pcsEditorReset')?.addEventListener('click', () => {
            const tpl = state.editorTemplate;
            if (!tpl || !state.draft) return;
            if (!window.confirm('تنظیمات این قالب به حالت پیش‌فرض برگردد؟')) return;
            if (state.draft.posters) delete state.draft.posters[tpl];
            scheduleSave();
            openEditor(tpl);
            toast('به پیش‌فرض برگشت');
        });
        $('#pcsEditorMobTabs')?.addEventListener('click', (e) => {
            const tab = e.target.closest('[data-pcs-editor-pane]');
            if (!tab) return;
            setEditorMobPane(tab.getAttribute('data-pcs-editor-pane'));
        });
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                if ($('#pcsModal')?.hasAttribute('hidden')) return;
                syncViewportMode();
                rescaleAllPreviews();
                syncFooterForTab(state.draft?.active_tab || 'posters');
                const lbBox = $('#pcsLightboxPreview');
                if (lbBox && !$('#pcsLightbox')?.hasAttribute('hidden')) {
                    scalePreviewCanvas(lbBox, state.format);
                }
                if (!$('#pcsEditor')?.hasAttribute('hidden') && state.editorTemplate) {
                    const activeTab = $('#pcsEditorMobTabs')?.querySelector('.pcs-editor__mob-tab.is-active');
                    setEditorMobPane(activeTab?.getAttribute('data-pcs-editor-pane') || 'preview');
                    refreshEditorPreview(state.editorTemplate);
                }
            }, 120);
        });
    }

    window.openPropertyContentStudio = openModal;

    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        document.addEventListener('touchmove', onPcsTouchMove, { passive: false });
    });
})();
