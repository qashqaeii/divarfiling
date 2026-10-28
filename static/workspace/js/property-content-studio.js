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
    const CORE_POSTER_TEMPLATES = ['luxury', 'minimal', 'gallery', 'bold'];
    const OVERLAY_POSTER_TEMPLATES = ['pearlescent', 'sculptural', 'emerald_atelier', 'pearl_gallery'];
    const TEMPLATES = [...CORE_POSTER_TEMPLATES, ...OVERLAY_POSTER_TEMPLATES];
    const TEMPLATE_META = {
        luxury: { label: 'لوکس', icon: 'fa-gem' },
        minimal: { label: 'مدرن', icon: 'fa-building' },
        gallery: { label: 'کلاژ', icon: 'fa-shapes' },
        bold: { label: 'کمپین', icon: 'fa-bolt' },
        pearlescent: { label: 'قاب استوری', icon: 'fa-layer-group' },
        sculptural: { label: 'قاب عاج', icon: 'fa-palette' },
        emerald_atelier: { label: 'قاب زمرد', icon: 'fa-building-columns' },
        pearl_gallery: { label: 'گالری مروارید', icon: 'fa-gem' },
    };
    const FORMAT_META = {
        story: { label: 'استوری', sub: '1080×1920', icon: 'fa-mobile-screen' },
        post: { label: 'پست', sub: '1080×1350', icon: 'fa-image' },
        square: { label: 'مربع', sub: '1080×1080', icon: 'fa-square' },
    };
    /** خروجی دانلود — WebP برای حجم کمتر (fallback به PNG در مرورگرهای قدیمی) */
    const PCS_EXPORT_IMAGE_TYPE = 'image/webp';
    const PCS_EXPORT_IMAGE_QUALITY = 0.86;
    const PCS_EXPORT_EXT = 'webp';
    const PCS_FONT_STACK = "'Vazirmatn', Tahoma, 'Segoe UI', sans-serif";
    const PCS_FONTS = {
        vazirmatn: { label: 'وزیرمتن', family: "'Vazirmatn', Tahoma, sans-serif", load: '400 32px Vazirmatn' },
        estedad: { label: 'استعداد', family: "'Estedad', Vazirmatn, sans-serif", load: '700 32px Estedad' },
        lalezar: { label: 'لاله‌زار', family: "'Lalezar', Vazirmatn, sans-serif", load: '400 32px Lalezar' },
        markazi: { label: 'مرکزی', family: "'Markazi Text', Vazirmatn, serif", load: '700 32px \"Markazi Text\"' },
        gulzar: { label: 'گلزار', family: "'Gulzar', Vazirmatn, serif", load: '400 32px Gulzar' },
        parastoo: { label: 'پرستو', family: "'Parastoo', Vazirmatn, sans-serif", load: '700 32px Parastoo' },
    };

    function posterFieldDefaults(imgs) {
        const count = (imgs || []).length;
        const pipDefault = count > 1 ? 1 : 0;
        return {
            headline: '',
            primary_image_index: 0,
            secondary_image_index: 1,
            image_order: (imgs || []).map((_, i) => i),
            crop_y: 50,
            img_brightness: 100,
            img_blur: 0,
            img_opacity: 100,
            font_key: 'vazirmatn',
            headline_scale: 100,
            price_scale: 100,
            headline_weight: 900,
            price_weight: 900,
            headline_italic: false,
            headline_underline: false,
            price_italic: false,
            price_underline: false,
            headline_color: '',
            price_color: '',
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
            pip_border: 'gold', pip_tilt: -7, hero_vignette: 16, hero_warmth: 'neutral',
        },
        magazine: {
            pip_enabled: true, pip_corner: 'bl', pip_size: 'l', pip_shape: 'card',
            pip_border: 'brand', pip_tilt: 5, hero_vignette: 48, hero_warmth: 'warm',
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
        const secRaw = parseInt(merged.secondary_image_index, 10);
        const imgCount = (imgs || []).length;
        merged.secondary_image_index = Number.isFinite(secRaw) ? secRaw : (imgCount > 1 ? 1 : 0);
        if (imgCount > 0) {
            merged.primary_image_index = Math.min(imgCount - 1, Math.max(0, merged.primary_image_index));
            merged.secondary_image_index = Math.min(imgCount - 1, Math.max(0, merged.secondary_image_index));
            if (imgCount > 1 && merged.secondary_image_index === merged.primary_image_index) {
                merged.secondary_image_index = (merged.primary_image_index + 1) % imgCount;
            }
        }
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
        merged.headline_weight = normalizePosterTextWeight(merged.headline_weight, 900);
        merged.price_weight = normalizePosterTextWeight(merged.price_weight, 900);
        merged.headline_italic = !!merged.headline_italic;
        merged.headline_underline = !!merged.headline_underline;
        merged.price_italic = !!merged.price_italic;
        merged.price_underline = !!merged.price_underline;
        merged.headline_color = normalizePosterHexColor(merged.headline_color);
        merged.price_color = normalizePosterHexColor(merged.price_color);
        merged.brand_primary = normalizePosterHexColor(merged.brand_primary);
        merged.text_layout = normalizeTextLayout(merged.text_layout);
        consolidateTextLayoutTypography(merged);
        return merged;
    }

    const PCS_TEXT_LAYOUT_ROLES = ['headline', 'meta', 'price'];

    function defaultTextLayoutEntry() {
        return { x: 0, y: 0, s: 100 };
    }

    function normalizeTextLayout(raw) {
        const out = {};
        PCS_TEXT_LAYOUT_ROLES.forEach((role) => {
            const src = raw && typeof raw === 'object' ? raw[role] : null;
            if (!src || typeof src !== 'object') {
                out[role] = defaultTextLayoutEntry();
                return;
            }
            const x = parseFloat(src.x);
            const y = parseFloat(src.y);
            const s = parseFloat(src.s != null ? src.s : src.scale);
            out[role] = {
                x: Number.isFinite(x) ? Math.min(55, Math.max(-55, x)) : 0,
                y: Number.isFinite(y) ? Math.min(55, Math.max(-55, y)) : 0,
                s: Number.isFinite(s) ? Math.min(180, Math.max(50, s)) : 100,
            };
        });
        return out;
    }

    /** عنوان/قیمت: اندازه پایدار در headline_scale/price_scale؛ s فقط transform موقت (مشخصات در s). */
    function consolidateTextLayoutTypography(conf) {
        if (!conf) return;
        conf.text_layout = normalizeTextLayout(conf.text_layout);
        ['headline', 'price'].forEach((role) => {
            const entry = conf.text_layout[role];
            if (!entry || entry.s === 100) return;
            const v = Math.round(entry.s);
            if (role === 'headline') conf.headline_scale = v;
            else conf.price_scale = v;
            entry.s = 100;
        });
    }

    function posterTextLayoutStyle(conf, role) {
        const layout = normalizeTextLayout(conf?.text_layout)[role] || defaultTextLayoutEntry();
        const parts = [];
        if (layout.x || layout.y) {
            parts.push(`translate(${layout.x}%, ${layout.y}%)`);
        }
        if (layout.s !== 100) {
            parts.push(`scale(${layout.s / 100})`);
        }
        if (!parts.length) return '';
        return `transform:${parts.join(' ')};transform-origin:top right;`;
    }

    function wrapPosterTextRole(role, html, conf) {
        if (!html) return '';
        const layoutCss = posterTextLayoutStyle(conf, role);
        return `<div class="pcs-poster-text" data-pcs-text-role="${role}" style="position:relative;width:100%;max-width:100%;${layoutCss}">${html}</div>`;
    }

    function wrapPosterHeadlineRole(html, conf) {
        return wrapPosterTextRole('headline', html, conf);
    }

    function wrapPosterMetaRole(html, conf) {
        return wrapPosterTextRole('meta', html, conf);
    }

    function wrapPosterPriceRole(html, conf) {
        return wrapPosterTextRole('price', html, conf);
    }

    function posterSpecsLineWrapped(facts, color, variant, opts, conf) {
        const inner = posterSpecsLineHtml(facts, color, variant, opts);
        return wrapPosterMetaRole(inner, conf);
    }

    function posterPriceEditorialWrapped(price, conf, layout, color, onDark, opts) {
        if (!price) return '';
        return wrapPosterPriceRole(posterPriceEditorial(price, conf, layout, color, onDark, opts), conf);
    }

    function normalizePosterTextWeight(value, fallback) {
        const n = parseInt(value, 10);
        if (!Number.isFinite(n)) return fallback ?? 900;
        if (n >= 850) return 900;
        if (n >= 650) return 700;
        if (n >= 550) return 600;
        return 500;
    }

    function normalizePosterHexColor(value) {
        const c = String(value || '').trim();
        return /^#[0-9a-fA-F]{6}$/.test(c) ? c.toLowerCase() : '';
    }

    function posterTextEmphasis(conf, role, defaultColor) {
        const isPrice = role === 'price';
        const weight = normalizePosterTextWeight(isPrice ? conf?.price_weight : conf?.headline_weight, 900);
        const italic = !!(isPrice ? conf?.price_italic : conf?.headline_italic);
        const underline = !!(isPrice ? conf?.price_underline : conf?.headline_underline);
        const custom = normalizePosterHexColor(isPrice ? conf?.price_color : conf?.headline_color);
        let css = `font-weight:${weight};`;
        if (italic) css += 'font-style:italic;';
        if (underline) css += 'text-decoration:underline;';
        if (custom) css += `color:${custom};`;
        else if (defaultColor) css += `color:${defaultColor};`;
        return css;
    }

    function editorControlsEl() {
        return $('#pcsEditorControls');
    }

    function resolveTemplateMeta(tpl) {
        const fromPage = cfg.templateMeta?.[tpl];
        if (fromPage && fromPage.label) {
            return {
                label: fromPage.label,
                icon: fromPage.icon || TEMPLATE_META[tpl]?.icon || 'fa-image',
            };
        }
        return TEMPLATE_META[tpl] || { label: tpl, icon: 'fa-image' };
    }

    function setEditorTplBadge(meta) {
        const badge = $('#pcsEditorTplBadge');
        if (!badge || !meta) return;
        badge.replaceChildren();
        const icon = document.createElement('i');
        icon.className = `fas ${meta.icon || 'fa-image'}`;
        icon.setAttribute('aria-hidden', 'true');
        badge.appendChild(icon);
        badge.appendChild(document.createTextNode(` ${meta.label}`));
    }

    function pcsFontFamily(conf) {
        const key = conf?.font_key || 'vazirmatn';
        return (PCS_FONTS[key] || PCS_FONTS.vazirmatn).family;
    }

    function posterFontSize(conf, px, role) {
        const scale = role === 'price' ? (conf.price_scale ?? 100) : (conf.headline_scale ?? 100);
        return Math.max(10, Math.round(px * scale / 100));
    }

    let _pcsMeasureCanvas;

    function pcsMeasureCtx(conf, weight) {
        if (typeof document === 'undefined') return null;
        if (!_pcsMeasureCanvas) {
            _pcsMeasureCanvas = document.createElement('canvas');
        }
        const ctx = _pcsMeasureCanvas.getContext('2d');
        if (!ctx) return null;
        const w = weight || 900;
        ctx.font = `${w} 32px ${pcsFontFamily(conf)}`;
        return ctx;
    }

    function pcsMeasureTextWidth(text, fontSizePx, conf, weight) {
        const ctx = pcsMeasureCtx(conf, weight);
        if (!ctx) {
            const len = String(text || '').length;
            return len * fontSizePx * 0.52;
        }
        ctx.font = `${weight || 900} ${fontSizePx}px ${pcsFontFamily(conf)}`;
        return ctx.measureText(String(text || '')).width;
    }

    function posterWrapHeadlineLines(headline, fontSizePx, maxWidthPx, conf, weight) {
        const w = weight || 900;
        const raw = String(headline || 'ملک').trim();
        const words = raw.split(/\s+/).filter(Boolean);
        if (!words.length) return [raw || 'ملک'];
        const lines = [];
        let line = '';
        words.forEach((word) => {
            const candidate = line ? `${line} ${word}` : word;
            if (pcsMeasureTextWidth(candidate, fontSizePx, conf, w) <= maxWidthPx) {
                line = candidate;
                return;
            }
            if (line) lines.push(line);
            line = word;
            if (pcsMeasureTextWidth(line, fontSizePx, conf, w) > maxWidthPx && line.length > 1) {
                lines.push(line);
                line = '';
            }
        });
        if (line) lines.push(line);
        return lines.length ? lines : [raw];
    }

    function posterHeadlineFit(conf, basePx, headline, maxWidthPx, maxLines) {
        const cap = Math.max(1, maxLines || 3);
        const hw = normalizePosterTextWeight(conf?.headline_weight, 900);
        let px = basePx;
        const floor = Math.max(28, Math.round(basePx * 0.58));
        while (px >= floor) {
            const fitted = posterFontSize(conf, px, 'headline');
            const lines = posterWrapHeadlineLines(headline, fitted, maxWidthPx, conf, hw);
            if (lines.length <= cap) {
                const widest = lines.reduce((m, ln) => Math.max(m, pcsMeasureTextWidth(ln, fitted, conf, hw)), 0);
                if (widest <= maxWidthPx * 1.02) return { px: fitted, lines };
            }
            px -= 2;
        }
        const fitted = posterFontSize(conf, floor, 'headline');
        return { px: fitted, lines: posterWrapHeadlineLines(headline, fitted, maxWidthPx, conf, hw).slice(0, cap) };
    }

    function posterHeadlineBlockHeight(linePx, lineCount, lineHeight) {
        const lh = lineHeight || 1.12;
        return Math.round(linePx * lh * Math.max(1, lineCount));
    }

    function posterHeadlineSize(conf, basePx, headline, layoutOpts) {
        const o = layoutOpts || {};
        const maxW = o.maxWidth || 920;
        const maxLines = o.maxLines || 3;
        return posterHeadlineFit(conf, basePx, headline, maxW, maxLines).px;
    }

    function posterPriceFit(conf, layout, price, maxWidthPx) {
        let px = posterFontSize(conf, layout.priceLg, 'price');
        const floor = Math.max(32, Math.round(layout.priceLg * 0.62));
        const text = String(price || '');
        const weight = normalizePosterTextWeight(conf?.price_weight, 900);
        while (px > floor && pcsMeasureTextWidth(text, px, conf, weight) > maxWidthPx) {
            px -= 2;
        }
        return px;
    }

    function posterPriceWeight(conf) {
        return normalizePosterTextWeight(conf?.price_weight, 900);
    }

    function posterPriceValueHtml(price, px, priceEmph, maxWidthPx, conf) {
        const text = String(price || '');
        const weight = posterPriceWeight(conf);
        const maxW = maxWidthPx || 900;
        let lines = [text];
        if (pcsMeasureTextWidth(text, px, conf, weight) > maxW * 1.02) {
            lines = posterWrapHeadlineLines(text, px, maxW, conf, weight);
            if (lines.length > 2) {
                lines = posterWrapHeadlineLines(text, Math.max(28, px - 4), maxW, conf, weight).slice(0, 2);
            }
        }
        const lineStyle = `font-size:${px}px;line-height:1.18;${priceEmph}`;
        if (lines.length <= 1) {
            return `<div class="pcs-poster-price-value" style="${pcsTextStyle(lineStyle)}">${esc(text)}</div>`;
        }
        return `<div class="pcs-poster-price-value pcs-poster-price-value--wrap">${lines.map((ln) => `<div style="${pcsTextStyle(lineStyle)}">${esc(ln)}</div>`).join('')}</div>`;
    }

    function sanitizePosterTextForExport(root) {
        const canvas = root?.classList?.contains('pcs-canvas') ? root : root?.querySelector?.('.pcs-canvas');
        if (!canvas) return;
        canvas.style.unicodeBidi = 'isolate';
        canvas.style.direction = 'rtl';
        canvas.style.textRendering = 'auto';
        canvas.querySelectorAll('*').forEach((el) => {
            if (!el.style) return;
            const tag = el.tagName;
            if (tag === 'IMG' || tag === 'SVG') return;
            if (el.getAttribute('dir') === 'ltr') {
                el.style.unicodeBidi = 'isolate';
                return;
            }
            el.style.unicodeBidi = 'inherit';
            el.style.textRendering = 'auto';
            const ls = el.style.letterSpacing;
            if (ls && (ls.startsWith('-') || parseFloat(ls) < 0)) {
                el.style.letterSpacing = '0';
            }
            if (el.style.textDecorationThickness || el.style.textUnderlineOffset) {
                el.style.textDecorationThickness = '';
                el.style.textUnderlineOffset = '';
            }
        });
        canvas.querySelectorAll('.pcs-poster-price-value').forEach((el) => {
            el.style.display = 'block';
            el.style.width = '100%';
            el.style.maxWidth = '100%';
            if (!el.classList.contains('pcs-poster-price-value--wrap')) {
                el.style.whiteSpace = 'nowrap';
            }
        });
    }

    function formatDimsHtml(formatKey) {
        const f = FORMATS[formatKey] || FORMATS.story;
        return `<span dir="ltr" class="pcs-ltr-dims" lang="en">${f.w}&nbsp;×&nbsp;${f.h}</span>`;
    }

    function isPosterNumericToken(word) {
        const w = String(word || '').trim();
        if (!w) return true;
        if (/^[\d۰-۹]+([.,٫][\d۰-۹]+)?$/.test(w)) return true;
        if (/^متر[،,]?$/.test(w)) return true;
        return false;
    }

    function modernHeadlineIsSpecStyle(headline) {
        const h = String(headline || '');
        if (/متر|متری|خواب|اتاق|سوئیت/i.test(h)) return true;
        if (/[\d۰-۹]/.test(h) && /[،,]/.test(h)) return true;
        return false;
    }

    function pickHeadlineFocusIndex(words) {
        if (!words || words.length < 2) return 0;
        const stop = new Set(['و', 'در', 'با', 'از', 'به', 'برای', 'تا', 'که']);
        let best = -1;
        let bestScore = -1;
        words.forEach((w, i) => {
            if (!w || stop.has(w) || isPosterNumericToken(w)) return;
            const score = w.length * 2 + (i > 0 ? 1 : 0);
            if (score > bestScore) {
                bestScore = score;
                best = i;
            }
        });
        if (best < 0) return Math.min(1, words.length - 1);
        return best;
    }

    let _pcsActivePosterConf = null;

    function withPosterRenderConf(conf, fn) {
        const prev = _pcsActivePosterConf;
        _pcsActivePosterConf = conf;
        try {
            return fn();
        } finally {
            _pcsActivePosterConf = prev;
        }
    }

    function pcsTextStyle(extra, conf) {
        const c = conf != null ? conf : _pcsActivePosterConf;
        return `font-family:${pcsFontFamily(c)};${extra || ''}`;
    }

    function syncCanvasTypography(root) {
        applyFontToSubtree(root);
        sanitizePosterTextForExport(root);
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
        saveSeq: 0,
        draftDirtyRev: 0,
        saveInflight: false,
        savePending: false,
        saveStatus: 'idle',
        sessionToken: 0,
        exportInflight: false,
        aiInflight: false,
        libsLoaded: false,
        brandFieldsBound: false,
        visTogglesBound: false,
        previewTemplate: null,
        editorBuffer: null,
        editorSnapshot: null,
        editorDirty: false,
        editorGallerySlot: 0,
        editorEmeraldSlot: 0,
        editorStorySlideId: null,
        editorPreviewView: { zoom: 1, panX: 0, panY: 0 },
        editorPreviewViewBound: false,
        editorTextRole: null,
        editorTextDrag: null,
        editorPosterHeadlineSuggestions: null,
    };

    const PCS_POSTER_HEADLINE_MAX = 44;

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

    function visibilityMap() {
        const base = state.session?.brand_effective?.visibility || state.session?.brand?.visibility || {};
        const ov = state.draft?.brand_override?.visibility || {};
        return { ...base, ...ov };
    }

    function visibleData() {
        const p = { ...(state.session?.property || {}) };
        const vis = visibilityMap();
        if (vis.price === false) p.price = { show: false, label: '', deal_mode: p.deal_mode || '' };
        if (vis.neighborhood === false) {
            p.neighborhood = '';
            p.location_line = p.city || '';
        }
        if (vis.area === false) p.area_label = '';
        if (vis.bedrooms === false) p.rooms_label = '';
        if (vis.floor === false) {
            p.floor = null;
            p.floor_label = '';
            p.build_year_label = '';
        }
        if (vis.amenities === false) {
            p.amenities = [];
            p.detail_chips = [];
        }
        if (vis.file_code === false) p.file_code = '';
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

    function storySlideCatalogRef(slideId) {
        return cfg.storySlides?.[slideId] || {};
    }

    /** کلیدهایی که برای «قدیمی» (لوکس در فرمت استوری) همیشه از هویت اسلاید کاور اعمال می‌شوند */
    const STORY_POSTER_IDENTITY_KEYS = [
        'font_key', 'headline_scale', 'price_scale', 'img_brightness', 'img_blur', 'img_opacity',
    ];

    function usesLuxuryStoryIdentity(tpl, formatKey) {
        const fmt = formatKey || state.format;
        return fmt === 'story' && tpl === 'luxury' && !!storySlideCatalogRef('cover').poster;
    }

    function posterDisplayLabel(tpl, formatKey) {
        if (usesLuxuryStoryIdentity(tpl, formatKey)) {
            return storySlideCatalogRef('cover').label || 'لوکس';
        }
        return resolveTemplateMeta(tpl).label;
    }

    function applyStoryPosterIdentityKeys(conf, identityPoster) {
        if (!identityPoster || !conf) return conf;
        const out = { ...conf };
        STORY_POSTER_IDENTITY_KEYS.forEach((k) => {
            if (identityPoster[k] !== undefined) out[k] = identityPoster[k];
        });
        return out;
    }

    function ensureStoryboardSlideIdentities() {
        if (!state.draft?.storyboard?.slides) return;
        state.draft.storyboard.slides.forEach((slide) => {
            const ref = storySlideCatalogRef(slide.id);
            if (!ref || typeof ref !== 'object') return;
            if (ref.template_id) slide.template_id = ref.template_id;
            if (ref.label) slide.label = ref.label;
            slide.poster = { ...(ref.poster || {}), ...(slide.poster || {}) };
        });
    }

    function ensureStoryboardSlidesStructure() {
        if (!state.draft?.storyboard) return false;
        const snapshot = JSON.stringify(state.draft.storyboard);
        const imgs = propertyImageList();
        const p = state.session?.property || {};
        let slides = [...(state.draft.storyboard.slides || [])];
        let order = [...(state.draft.storyboard.order || slides.map((s) => s.id))];
        const hasExtra = slides.some((s) => s.id === 'extra_photos');
        const hasEmerald = slides.some((s) => s.id === 'emerald_showcase');
        const hasPearl = slides.some((s) => s.id === 'pearl_showcase');
        const ref = storySlideCatalogRef('extra_photos');
        const emeraldRef = storySlideCatalogRef('emerald_showcase');
        const pearlRef = storySlideCatalogRef('pearl_showcase');

        if (imgs.length >= 2 && !hasEmerald && emeraldRef) {
            const archIdx = 0;
            const stripIdx = imgs.length > 1 ? 1 : 0;
            const emerald = {
                id: 'emerald_showcase',
                type: 'dual_photos',
                title: String(p.title || p.headline || '').trim(),
                subtitle: String(p.location_line || p.city || '').trim(),
                image_index: archIdx,
                image_indices: [stripIdx],
            };
            if (emeraldRef.template_id) emerald.template_id = emeraldRef.template_id;
            if (emeraldRef.label) emerald.label = emeraldRef.label;
            if (emeraldRef.poster) emerald.poster = { ...emeraldRef.poster };
            const insertBefore = order.indexOf('extra_photos');
            const anchor = insertBefore >= 0 ? insertBefore : order.indexOf('contact');
            if (anchor >= 0) {
                order.splice(anchor, 0, 'emerald_showcase');
            } else {
                order.push('emerald_showcase');
            }
            slides.push(emerald);
        } else if (imgs.length < 2 && hasEmerald) {
            slides = slides.filter((s) => s.id !== 'emerald_showcase');
            order = order.filter((id) => id !== 'emerald_showcase');
        }

        if (imgs.length >= 2 && !hasPearl && pearlRef) {
            const pearl = {
                id: 'pearl_showcase',
                type: 'dual_photos',
                title: String(p.title || p.headline || '').trim(),
                subtitle: String(p.location_line || p.city || '').trim(),
                image_index: 0,
                image_indices: [imgs.length > 1 ? 1 : 0],
            };
            if (pearlRef.template_id) pearl.template_id = pearlRef.template_id;
            if (pearlRef.label) pearl.label = pearlRef.label;
            if (pearlRef.poster) pearl.poster = { ...pearlRef.poster };
            const insertBefore = order.indexOf('extra_photos');
            const anchor = insertBefore >= 0 ? insertBefore : order.indexOf('contact');
            if (anchor >= 0) {
                order.splice(anchor, 0, 'pearl_showcase');
            } else {
                order.push('pearl_showcase');
            }
            slides.push(pearl);
        } else if (imgs.length < 2 && hasPearl) {
            slides = slides.filter((s) => s.id !== 'pearl_showcase');
            order = order.filter((id) => id !== 'pearl_showcase');
        }

        if (imgs.length > 3 && !hasExtra && ref) {
            const extra = {
                id: 'extra_photos',
                type: 'photo_showcase',
                title: String(p.title || p.headline || '').trim(),
                subtitle: String(p.location_line || p.city || '').trim(),
                image_index: Math.min(3, imgs.length - 1),
                image_indices: sculpturalCircleIndices(imgs, Math.min(3, imgs.length - 1), 3),
            };
            if (ref.template_id) extra.template_id = ref.template_id;
            if (ref.label) extra.label = ref.label;
            if (ref.poster) extra.poster = { ...ref.poster };
            const contactIdx = order.indexOf('contact');
            if (contactIdx >= 0) {
                order.splice(contactIdx, 0, 'extra_photos');
            } else {
                order.push('extra_photos');
            }
            slides.push(extra);
        } else if (imgs.length <= 3 && hasExtra) {
            slides = slides.filter((s) => s.id !== 'extra_photos');
            order = order.filter((id) => id !== 'extra_photos');
        }

        state.draft.storyboard.slides = slides;
        const freshOrder = ['cover', 'specs', 'gallery_price'];
        if (imgs.length >= 2) {
            freshOrder.push('emerald_showcase', 'pearl_showcase');
        }
        if (imgs.length > 3) freshOrder.push('extra_photos');
        freshOrder.push('contact');
        const valid = new Set(slides.map((s) => s.id));
        state.draft.storyboard.order = freshOrder.filter((id) => valid.has(id));
        ensureStoryboardSlideIdentities();
        return JSON.stringify(state.draft.storyboard) !== snapshot;
    }

    function posterConfigFromDraft(tpl) {
        const imgs = propertyImageList();
        const posters = state.draft?.posters || {};
        const raw = posters[tpl];
        if (usesLuxuryStoryIdentity(tpl, state.format)) {
            const identity = storySlideCatalogRef('cover').poster || {};
            const base = { ...posterFieldDefaults(imgs), ...identity };
            if (raw == null) {
                return normalizePosterConfig(base, imgs);
            }
            const merged = normalizePosterConfig({ ...base, ...raw }, imgs);
            return normalizePosterConfig(applyStoryPosterIdentityKeys(merged, identity), imgs);
        }
        if (raw == null) return normalizePosterConfig(null, imgs);
        return normalizePosterConfig(raw, imgs);
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
        const dirtyFlag = $('#pcsEditorDirtyFlag');
        if (dirtyFlag) {
            if (state.editorDirty) dirtyFlag.removeAttribute('hidden');
            else dirtyFlag.setAttribute('hidden', '');
        }
    }

    function initEditorBuffer(tpl) {
        const imgs = propertyImageList();
        state.editorBuffer = { ...normalizePosterConfig(posterConfigFromDraft(tpl), imgs) };
        consolidateTextLayoutTypography(state.editorBuffer);
        state.editorSnapshot = JSON.stringify(state.editorBuffer);
        state.editorDirty = false;
        $('#pcsEditor')?.classList.remove('pcs-editor--dirty');
        $('#pcsEditorDirtyFlag')?.setAttribute('hidden', '');
    }

    function propertyImageList() {
        const p = state.session?.property || {};
        const list = [...(p.images || [])].filter(Boolean);
        const cover = p.cover_image || '';
        if (cover && !list.includes(cover)) list.unshift(cover);
        if (!list.length && cover) list.push(cover);
        return list;
    }

    function posterGridTemplates() {
        const imgs = propertyImageList();
        const list = [...CORE_POSTER_TEMPLATES, 'pearlescent'];
        if (imgs.length >= 2) list.push('emerald_atelier', 'pearl_gallery');
        if (imgs.length > 3) list.push('sculptural');
        return list;
    }

    function posterTemplatesForSession() {
        return posterGridTemplates();
    }

    function orderedImages(tpl, confOverride) {
        const imgs = propertyImageList();
        const conf = confOverride
            ? normalizePosterConfig(confOverride, imgs)
            : posterConfig(tpl || 'luxury');
        const order = (conf.image_order && conf.image_order.length) ? conf.image_order : imgs.map((_, i) => i);
        return order.filter((i) => i >= 0 && i < imgs.length).map((i) => imgs[i]);
    }

    function defaultPropertyHeadline() {
        const { property: p, vis } = visibleData();
        const customTitle = String(p.title || '').trim();
        const parts = [];
        if (vis.area !== false && p.area_label) parts.push(p.area_label);
        if (vis.bedrooms !== false && p.rooms_label) parts.push(p.rooms_label);
        if (parts.length) return parts.join('، ');
        return customTitle || p.property_type || 'ملک';
    }

    function visibleHeadline(conf) {
        const custom = (conf?.headline || '').trim();
        if (custom) return custom;
        return defaultPropertyHeadline();
    }

    function slideImageAt(index) {
        const imgs = propertyImageList();
        if (!imgs.length) return '';
        const i = parseInt(index, 10);
        if (!Number.isFinite(i) || i < 0 || i >= imgs.length) return imgs[0];
        return imgs[i];
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

    const GALLERY_LAYOUT_SLOTS = [
        { title: 'تصویر اصلی', sub: 'سلول بزرگ' },
        { title: 'بالا چپ', sub: 'گرید' },
        { title: 'پایین چپ', sub: 'گرید' },
    ];

    function editorAssetFilmstrip(imgs, selectedIdx, pickAttrName) {
        if (!imgs.length) {
            return '<p class="pcs-editor__empty">تصویری برای این فایل ثبت نشده است.</p>';
        }
        const attr = pickAttrName || 'data-pcs-asset-pick';
        return `<div class="pcs-editor__filmstrip" role="listbox" aria-label="کتابخانه تصاویر">
            ${imgs.map((url, i) => `
            <button type="button" class="pcs-editor__film-thumb${selectedIdx === i ? ' is-selected' : ''}"
                ${attr}="${i}" data-pcs-img-idx="${i}" aria-pressed="${selectedIdx === i}">
                <img src="${esc(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">
                <span class="pcs-editor__film-thumb-num">${i + 1}</span>
            </button>`).join('')}
        </div>`;
    }

    function editorGalleryComposer(imgs, galleryOrder) {
        if (!imgs.length) return '';
        const active = state.editorGallerySlot ?? 0;
        const pickIdx = galleryOrder[active] ?? 0;
        return `<div class="pcs-editor__gallery-dock" data-pcs-gallery-dock>
            <p class="pcs-editor__gallery-dock-hint">ابتدا یک بخش چیدمان را انتخاب کنید، سپس از نوار تصاویر یکی را اختصاص دهید.</p>
            <div class="pcs-editor__gallery-layout" role="tablist" aria-label="بخش‌های چیدمان">
                ${GALLERY_LAYOUT_SLOTS.map((meta, slot) => {
                    const idx = galleryOrder[slot] ?? slot;
                    const url = imgs[idx] || '';
                    return `<button type="button" class="pcs-editor__layout-slot${active === slot ? ' is-active' : ''}"
                        data-pcs-gallery-slot-btn="${slot}" role="tab" aria-selected="${active === slot ? 'true' : 'false'}">
                        <span class="pcs-editor__layout-slot-thumb">${url ? `<img src="${esc(url)}" alt="">` : '<i class="fas fa-image" aria-hidden="true"></i>'}</span>
                        <span class="pcs-editor__layout-slot-text">
                            <strong>${esc(meta.title)}</strong>
                            <small>${esc(meta.sub)} · تصویر ${idx + 1}</small>
                        </span>
                        <input type="hidden" data-pcs-gallery-slot="${slot}" value="${idx}">
                    </button>`;
                }).join('')}
            </div>
            ${editorAssetFilmstrip(imgs, pickIdx, 'data-pcs-gallery-pick')}
            <div class="pcs-editor__gallery-dock-actions">
                <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--sm" data-pcs-gallery-autofill>
                    <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i> پر کردن هوشمند
                </button>
                <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--sm" data-pcs-gallery-rotate>
                    <i class="fas fa-rotate" aria-hidden="true"></i> چرخش بخش‌ها
                </button>
            </div>
        </div>`;
    }

    function syncGalleryDockUi() {
        const dock = document.querySelector('[data-pcs-gallery-dock]');
        if (!dock) return;
        const imgs = propertyImageList();
        const ord = editorImageOrderForGallery(imgs, state.editorBuffer || {});
        const active = state.editorGallerySlot ?? 0;
        dock.querySelectorAll('[data-pcs-gallery-slot-btn]').forEach((btn) => {
            const slot = parseInt(btn.getAttribute('data-pcs-gallery-slot-btn') || '0', 10);
            const idx = ord[slot] ?? 0;
            btn.classList.toggle('is-active', slot === active);
            btn.setAttribute('aria-selected', slot === active ? 'true' : 'false');
            const thumb = btn.querySelector('.pcs-editor__layout-slot-thumb');
            const url = imgs[idx];
            if (thumb) {
                thumb.innerHTML = url
                    ? `<img src="${esc(url)}" alt="">`
                    : '<i class="fas fa-image" aria-hidden="true"></i>';
            }
            const small = btn.querySelector('.pcs-editor__layout-slot-text small');
            const meta = GALLERY_LAYOUT_SLOTS[slot] || { sub: '' };
            if (small) small.textContent = `${meta.sub} · تصویر ${idx + 1}`;
            const hid = btn.querySelector('[data-pcs-gallery-slot]');
            if (hid) hid.value = String(idx);
        });
        dock.querySelectorAll('[data-pcs-gallery-pick]').forEach((btn) => {
            const i = parseInt(btn.getAttribute('data-pcs-img-idx') || '0', 10);
            btn.classList.toggle('is-selected', i === (ord[active] ?? 0));
        });
    }

    const EMERALD_LAYOUT_SLOTS = [
        { title: 'قوس بزرگ', sub: 'تصویر شاخص' },
        { title: 'نوار کناری', sub: 'تصویر دوم' },
    ];
    const OVERLAY_DUAL_SLOT_PRESETS = {
        emerald_atelier: EMERALD_LAYOUT_SLOTS,
        pearl_gallery: [
            { title: 'دایره اصلی', sub: 'تصویر شاخص' },
            { title: 'دایره مکمل', sub: 'تصویر دوم' },
        ],
    };

    function overlayDualSlotMeta(tpl) {
        return OVERLAY_DUAL_SLOT_PRESETS[tpl] || EMERALD_LAYOUT_SLOTS;
    }

    function emeraldStripIndex(conf, imgs) {
        const n = (imgs || []).length;
        if (n < 2) return 0;
        const hero = Math.max(0, Math.min(n - 1, conf?.primary_image_index || 0));
        let strip = parseInt(conf?.secondary_image_index, 10);
        if (!Number.isFinite(strip)) strip = hero === 0 ? 1 : 0;
        strip = Math.min(n - 1, Math.max(0, strip));
        if (strip === hero) strip = (hero + 1) % n;
        return strip;
    }

    function editorEmeraldImageComposer(imgs, archIdx, stripIdx, tpl) {
        if (!imgs.length) return '<p class="pcs-editor__empty">حداقل دو تصویر لازم است.</p>';
        const slots = overlayDualSlotMeta(tpl || state.editorTemplate || 'emerald_atelier');
        const arch = Math.min(imgs.length - 1, Math.max(0, archIdx || 0));
        let strip = emeraldStripIndex({ primary_image_index: arch, secondary_image_index: stripIdx }, imgs);
        const active = state.editorEmeraldSlot ?? 0;
        const pickIdx = active === 0 ? arch : strip;
        return `<div class="pcs-editor__gallery-dock" data-pcs-emerald-dock>
            <p class="pcs-editor__gallery-dock-hint">ابتدا «قوس» یا «نوار» را انتخاب کنید، سپس از نوار تصاویر یکی را اختصاص دهید.</p>
            <div class="pcs-editor__gallery-layout" role="tablist" aria-label="جایگاه تصاویر قاب زمرد">
                ${slots.map((meta, slot) => {
                    const idx = slot === 0 ? arch : strip;
                    const url = imgs[idx] || '';
                    return `<button type="button" class="pcs-editor__layout-slot${active === slot ? ' is-active' : ''}"
                        data-pcs-emerald-slot-btn="${slot}" role="tab" aria-selected="${active === slot ? 'true' : 'false'}">
                        <span class="pcs-editor__layout-slot-thumb">${url ? `<img src="${esc(url)}" alt="">` : '<i class="fas fa-image" aria-hidden="true"></i>'}</span>
                        <span class="pcs-editor__layout-slot-text">
                            <strong>${esc(meta.title)}</strong>
                            <small>${esc(meta.sub)} · تصویر ${idx + 1}</small>
                        </span>
                        <input type="hidden" data-pcs-emerald-slot="${slot}" value="${idx}">
                    </button>`;
                }).join('')}
            </div>
            <input type="hidden" id="pcsEditImage" value="${arch}">
            <input type="hidden" id="pcsEditEmeraldStrip" value="${strip}">
            ${editorAssetFilmstrip(imgs, pickIdx, 'data-pcs-emerald-pick')}
        </div>`;
    }

    function syncEmeraldDockUi() {
        const dock = editorControlsEl()?.querySelector('[data-pcs-emerald-dock]');
        if (!dock) return;
        const imgs = propertyImageList();
        const archInp = dock.querySelector('#pcsEditImage');
        const stripInp = dock.querySelector('#pcsEditEmeraldStrip');
        const arch = parseInt(archInp?.value || '0', 10);
        let strip = parseInt(stripInp?.value || '1', 10);
        if (imgs.length > 1 && strip === arch) {
            strip = (arch + 1) % imgs.length;
            if (stripInp) stripInp.value = String(strip);
        }
        const active = state.editorEmeraldSlot ?? 0;
        dock.querySelectorAll('[data-pcs-emerald-slot-btn]').forEach((btn) => {
            const slot = parseInt(btn.getAttribute('data-pcs-emerald-slot-btn') || '0', 10);
            const idx = slot === 0 ? arch : strip;
            btn.classList.toggle('is-active', slot === active);
            btn.setAttribute('aria-selected', slot === active ? 'true' : 'false');
            const thumb = btn.querySelector('.pcs-editor__layout-slot-thumb');
            const url = imgs[idx];
            if (thumb) {
                thumb.innerHTML = url
                    ? `<img src="${esc(url)}" alt="">`
                    : '<i class="fas fa-image" aria-hidden="true"></i>';
            }
            const small = btn.querySelector('.pcs-editor__layout-slot-text small');
            const meta = overlayDualSlotMeta(state.editorTemplate || 'emerald_atelier')[slot] || { sub: '' };
            if (small) small.textContent = `${meta.sub} · تصویر ${idx + 1}`;
            const hid = btn.querySelector('[data-pcs-emerald-slot]');
            if (hid) hid.value = String(idx);
        });
        dock.querySelectorAll('[data-pcs-emerald-pick]').forEach((btn) => {
            const i = parseInt(btn.getAttribute('data-pcs-img-idx') || '0', 10);
            const pickIdx = active === 0 ? arch : strip;
            btn.classList.toggle('is-selected', i === pickIdx);
        });
    }

    function editorPrimaryPicker(imgs, selectedIndex) {
        const idx = Math.min(imgs.length - 1, Math.max(0, selectedIndex || 0));
        return `<div class="pcs-editor__primary-pick">
            <input type="hidden" id="pcsEditImage" value="${idx}">
            <p class="pcs-editor__mini-label">تصویر شاخص: <strong data-pcs-primary-label>${idx + 1}</strong> از ${imgs.length}</p>
            ${editorAssetFilmstrip(imgs, idx, 'data-pcs-primary-pick')}
        </div>`;
    }

    function editorPipImagePicker(imgs, pipIdx) {
        const idx = Math.min(imgs.length - 1, Math.max(0, pipIdx ?? 1));
        return `<select class="pcs-input pcs-editor__pip-select" data-pcs-pip-image-select aria-label="تصویر کوچک">
            ${imgs.map((_, i) => `<option value="${i}"${i === idx ? ' selected' : ''}>تصویر ${i + 1}</option>`).join('')}
        </select>`;
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
                    fmtPill.innerHTML = `<i class="fas ${fmtMeta.icon}" aria-hidden="true"></i> ${esc(fmtMeta.label)} · ${formatDimsHtml(state.format)}`;
                }
                resetEditorPreviewView();
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
            if (prev) {
                requestAnimationFrame(() => {
                    scheduleEditorPreviewScale(prev, state.format);
                });
            }
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

    async function verifyImagesForExport(root) {
        const imgs = root ? Array.from(root.querySelectorAll('img')) : [];
        if (!imgs.length) return { ok: true };
        const failures = [];
        await Promise.all(imgs.map((img) => new Promise((resolve) => {
            const check = () => {
                if (img.naturalWidth > 0 && img.naturalHeight > 0) {
                    resolve();
                    return;
                }
                failures.push(img.src || 'تصویر');
                resolve();
            };
            if (img.complete) {
                check();
                return;
            }
            img.addEventListener('load', check, { once: true });
            img.addEventListener('error', () => {
                failures.push(img.src || 'تصویر');
                resolve();
            }, { once: true });
        })));
        if (failures.length) {
            return { ok: false, message: 'برخی تصاویر برای خروجی PNG بارگذاری نشدند (ممکن است محدودیت CORS باشد).' };
        }
        return { ok: true };
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
        const list = (items || []).filter(Boolean).slice(0, 3);
        if (!list.length) return '';
        const dark = variant === 'dark';
        return `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
            ${list.map((t) => `
            <span style="${pcsTextStyle(`display:inline-flex;align-items:center;gap:7px;padding:9px 14px;border-radius:999px;font-size:19px;font-weight:700;max-width:100%;${
                dark
                    ? `color:#f8fafc;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);backdrop-filter:blur(6px);`
                    : `color:${primaryColor};background:${primaryRgba(primaryColor, 0.08)};border:1px solid ${primaryRgba(primaryColor, 0.18)};`
            }`)}">${pcsSvg(chipIconFor(t), 17, dark ? '#f1f5f9' : primaryColor)}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px;">${esc(t)}</span></span>`).join('')}
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

    function priceHighlightHtml(price, color, variant, conf, opts) {
        if (!price) return '';
        const o = opts || {};
        const dark = variant === 'dark';
        const campaign = variant === 'campaign';
        const c = conf || {};
        const basePx = o.basePx || (campaign ? 52 : dark ? 44 : 42);
        const px = posterFontSize(c, basePx, 'price');
        if (campaign) {
            return `<div style="margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 22px;border-radius:20px;background:linear-gradient(135deg,#fff 0%,#f8fafc 100%);border:2px solid ${primaryRgba(color, 0.28)};box-shadow:0 18px 44px rgba(0,0,0,.35),0 0 0 1px rgba(255,255,255,.5) inset;">
                <span style="${pcsTextStyle('font-size:20px;font-weight:800;color:#64748b;')}">قیمت</span>
                <span style="${pcsTextStyle(`font-size:${px}px;font-weight:900;color:${color};letter-spacing:-0.02em;`)}">${esc(price)}</span>
            </div>`;
        }
        if (dark) {
            return `<div style="margin-top:16px;display:inline-flex;align-items:center;gap:12px;padding:14px 24px;border-radius:16px;background:linear-gradient(135deg,${primaryRgba(color, 0.92)},${primaryRgba(color, 0.65)});border:1px solid rgba(255,255,255,.28);box-shadow:0 16px 40px ${primaryRgba(color, 0.45)};">
                ${pcsSvg('tag', 24, '#fff')}
                <span style="${pcsTextStyle(`font-size:${px}px;font-weight:900;color:#fff;`, c)}">${esc(price)}</span>
            </div>`;
        }
        return `<div style="display:inline-flex;align-items:center;gap:10px;margin-bottom:10px;padding:12px 18px;border-radius:14px;background:${primaryRgba(color, 0.08)};border:1px solid ${primaryRgba(color, 0.16)};">
            ${pcsSvg('tag', 24, color)}
            <span style="${pcsTextStyle(`font-size:${px}px;font-weight:900;color:${color};`, c)}">${esc(price)}</span>
        </div>`;
    }

    function posterFormatLayout(formatKey) {
        const fmt = FORMATS[formatKey] || FORMATS.story;
        const key = formatKey || 'story';
        const isSquare = key === 'square';
        const isPost = key === 'post';
        const isStory = key === 'story';
        const safeTop = isStory ? 96 : isPost ? 72 : 56;
        const safeBottom = isStory ? 120 : isPost ? 88 : 72;
        return {
            key,
            fmt,
            isSquare,
            isPost,
            isStory,
            w: fmt.w,
            h: fmt.h,
            pad: isSquare ? 36 : isPost ? 44 : 52,
            safeTop,
            safeBottom,
            heroLuxury: isSquare ? '62%' : isPost ? '66%' : '68%',
            footerLuxury: isSquare ? '38%' : isPost ? '34%' : '32%',
            modernHead: isSquare ? 58 : isPost ? 68 : 82,
            modernImgMin: isSquare ? Math.round(fmt.h * 0.42) : isPost ? Math.round(fmt.h * 0.4) : Math.round(fmt.h * 0.44),
            modernFooterMin: isSquare ? 200 : isPost ? 220 : 260,
            collageMainH: isSquare ? Math.round(fmt.h * 0.46) : isPost ? Math.round(fmt.h * 0.44) : Math.round(fmt.h * 0.48),
            collageThumb: isSquare ? 200 : isPost ? 228 : 268,
            collageThumbGap: isSquare ? 16 : 20,
            campaignImgRatio: isSquare ? 0.58 : isPost ? 0.56 : 0.6,
            hlLuxury: isSquare ? 52 : isPost ? 62 : 80,
            hlModern: isSquare ? 56 : isPost ? 66 : 84,
            hlCollage: isSquare ? 50 : isPost ? 58 : 76,
            hlCampaign: isSquare ? 54 : isPost ? 62 : 76,
            priceLg: isSquare ? 48 : isPost ? 54 : 64,
        };
    }

    function faNormCompareText(s) {
        const digits = '۰۱۲۳۴۵۶۷۸۹';
        return String(s || '')
            .replace(/\s+/g, ' ')
            .trim()
            .replace(/[۰-۹]/g, (c) => String(digits.indexOf(c)));
    }

    function posterDetailChipAllowed(text) {
        const s = String(text || '').trim();
        if (!s) return false;
        if (/location[_\s]*(precision|source)/i.test(s)) return false;
        if (/listing_coordinates|manual_pin|approximate|coordinates/i.test(s) && /[_.:]/.test(s)) return false;
        if (/^[_a-z0-9_.]+:\s*/i.test(s)) return false;
        return true;
    }

    function headlineInText(headline, fragment) {
        if (!fragment) return false;
        const h = faNormCompareText(headline);
        const f = faNormCompareText(fragment);
        if (!f) return false;
        return h.includes(f) || f.includes(h);
    }

    function posterContentFacts(p, headline, locLine) {
        const specs = [];
        if (p.area_label && !headlineInText(headline, p.area_label)) {
            specs.push({ icon: 'area', text: p.area_label });
        }
        if (p.rooms_label && !headlineInText(headline, p.rooms_label)) {
            specs.push({ icon: 'bed', text: p.rooms_label });
        }
        if (p.property_type && !headlineInText(headline, p.property_type)) {
            specs.push({ icon: 'building', text: p.property_type });
        }
        if (p.floor_label && !headlineInText(headline, p.floor_label)) {
            specs.push({ icon: 'building', text: p.floor_label });
        }
        if (p.build_year_label && !headlineInText(headline, p.build_year_label)) {
            specs.push({ icon: 'building', text: p.build_year_label });
        }
        const detailExtra = (p.detail_chips || []).filter((a) => a && posterDetailChipAllowed(a) && !headlineInText(headline, a));
        const amenities = [...detailExtra, ...(p.amenities || [])]
            .filter((a) => a && !headlineInText(headline, a));
        const seen = new Set();
        const dedupedAmenities = amenities.filter((a) => {
            const k = String(a);
            if (seen.has(k)) return false;
            seen.add(k);
            return true;
        });
        const maxChips = 5;
        const trimmedSpecs = specs.slice(0, maxChips);
        const amenitySlots = Math.max(0, maxChips - trimmedSpecs.length);
        return {
            locLine: locLine || '',
            specs: trimmedSpecs,
            amenities: dedupedAmenities.slice(0, amenitySlots),
        };
    }

    function posterSpecsLineHtml(facts, color, variant, opts) {
        const o = opts || {};
        const compact = !!o.compact;
        const chipLimit = compact ? 5 : 6;
        const items = [...facts.specs, ...facts.amenities.map((t) => ({ icon: amenityIconKey(t), text: t }))].slice(0, chipLimit);
        if (!items.length && !facts.locLine) return '';
        const dark = variant === 'dark';
        const prominent = !!o.prominent;
        const metaPx = prominent ? 34 : (compact ? 28 : 32);
        const iconPx = prominent ? 24 : (compact ? 20 : 24);
        const sep = dark ? 'rgba(255,255,255,.28)' : 'rgba(15,23,42,.14)';
        const textColor = dark ? '#e8edf3' : (prominent ? '#1e293b' : '#475569');
        const chipTextColor = dark ? '#f8fafc' : (prominent ? '#0f172a' : '#334155');
        const loc = facts.locLine
            ? `<div style="display:flex;align-items:center;gap:10px;margin-bottom:${items.length ? '12px' : '0'};">
                ${pcsSvg('location', iconPx, dark ? '#cbd5e1' : color)}
                <span style="${pcsTextStyle(`font-size:${metaPx}px;font-weight:700;color:${textColor};line-height:1.35;`)}">${esc(facts.locLine)}</span>
            </div>`
            : '';
        const row = items.length
            ? `<div style="display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;">
                ${items.map((it) => `
                <span style="display:inline-flex;align-items:center;gap:8px;padding:${prominent ? '10px 16px' : '8px 14px'};border-radius:12px;background:${dark ? 'rgba(255,255,255,.08)' : 'rgba(15,23,42,.05)'};border:1px solid ${sep};">
                    ${pcsSvg(it.icon, prominent ? 22 : 18, dark ? '#f1f5f9' : color)}
                    <span style="${pcsTextStyle(`font-size:${metaPx - (prominent ? 0 : 2)}px;font-weight:${prominent ? 800 : 700};color:${chipTextColor};`)}">${esc(it.text)}</span>
                </span>`).join('')}
            </div>`
            : '';
        return `<div style="margin-top:${o.noMargin ? 0 : 10}px;">${loc}${row}</div>`;
    }

    function posterPriceEditorial(price, conf, layout, color, onDark, opts) {
        if (!price) return '';
        const o = opts || {};
        const maxW = o.maxWidth || layout.w - layout.pad * 2 - 48;
        const px = posterPriceFit(conf, layout, price, maxW);
        const priceDefault = onDark ? '#fff' : color;
        const priceEmph = posterTextEmphasis(conf, 'price', priceDefault);
        if (onDark) {
            return `<div style="display:inline-flex;flex-direction:column;gap:6px;padding:16px 24px;border-radius:16px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);backdrop-filter:blur(8px);">
                <span style="${pcsTextStyle('font-size:24px;font-weight:700;color:rgba(255,255,255,.72);')}">قیمت</span>
                <span class="pcs-poster-price-value" style="${pcsTextStyle(`font-size:${px}px;line-height:1.18;${priceEmph}`)}">${esc(price)}</span>
            </div>`;
        }
        if (o.variant === 'inline') {
            return `<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:16px;padding:14px 18px;border-radius:14px;background:rgba(15,23,42,.04);">
                <span style="${pcsTextStyle(`font-size:26px;font-weight:700;color:${primaryRgba(color, 0.55)};`)}">قیمت</span>
                <span class="pcs-poster-price-value" style="${pcsTextStyle(`font-size:${px}px;line-height:1.18;${priceEmph}`)}">${esc(price)}</span>
            </div>`;
        }
        return `<div class="pcs-poster-price-block" style="padding:2px 0;max-width:${maxW}px;">
            <div class="pcs-poster-price-label" style="${pcsTextStyle(`font-size:26px;font-weight:700;color:${primaryRgba(color, 0.5)};margin-bottom:6px;`)}">قیمت</div>
            ${posterPriceValueHtml(price, px, priceEmph, maxW, conf)}
        </div>`;
    }

    function modernHeadlineMarkup(headline, conf, accent, basePx, maxWidthPx) {
        const raw = String(headline || 'ملک').trim();
        const maxW = maxWidthPx || 900;
        const fit = posterHeadlineFit(conf, basePx, raw, maxW, modernHeadlineIsSpecStyle(raw) ? 2 : 3);
        const px = fit.px;
        const emph = posterTextEmphasis(conf, 'headline', '#0f172a');
        const lineStyle = `font-size:${px}px;line-height:1.12;letter-spacing:-0.02em;${emph}`;

        if (modernHeadlineIsSpecStyle(raw)) {
            const lines = fit.lines.map((ln) => `<div style="${pcsTextStyle(lineStyle)}">${esc(ln)}</div>`).join('');
            return `<div style="max-width:100%;padding:6px 0 4px;border-inline-end:6px solid ${accent};padding-inline-end:18px;">
                ${lines}
            </div>`;
        }

        const words = raw.split(/\s+/).filter(Boolean);
        const pxHi = posterFontSize(conf, Math.round(px * 1.04), 'headline');
        const focusEmph = posterTextEmphasis(conf, 'headline', '');
        if (words.length < 2) {
            return `<div style="${pcsTextStyle(lineStyle)}">${esc(raw || 'ملک')}</div>`;
        }
        const hi = pickHeadlineFocusIndex(words);
        const before = words.slice(0, hi).join(' ');
        const focus = words[hi];
        const after = words.slice(hi + 1).join(' ');
        const inkOnAccent = normalizePosterHexColor(conf?.headline_color) || textOnColor(accent);
        const focusStyle = `font-size:${pxHi}px;line-height:1.08;${focusEmph}${focusEmph.includes('color:') ? '' : `color:${inkOnAccent};`}`;
        return `<div style="max-width:100%;display:flex;flex-direction:column;align-items:flex-start;gap:8px;">
            ${before ? `<div style="${pcsTextStyle(lineStyle)}">${esc(before)}</div>` : ''}
            <div style="display:block;max-width:100%;padding:8px 20px 10px;background:${accent};border-radius:6px;">
                <span style="${pcsTextStyle(focusStyle)}">${esc(focus)}</span>
            </div>
            ${after ? `<div style="${pcsTextStyle(lineStyle)}">${esc(after)}</div>` : ''}
        </div>`;
    }

    function collageThumbFrame(url, size, cropY, conf, ringColor) {
        if (!url) return '';
        const ring = ringColor || '#fff';
        const radius = Math.max(18, Math.round(size * 0.13));
        const innerR = Math.max(14, radius - 4);
        return `<div style="width:${size}px;height:${size}px;flex-shrink:0;border-radius:${radius}px;padding:4px;background:linear-gradient(155deg,#fff 0%,${primaryRgba(ring, 0.45)} 100%);box-shadow:0 28px 64px rgba(0,0,0,.48),0 0 0 1px rgba(255,255,255,.22);">
            <div style="width:100%;height:100%;border-radius:${innerR}px;overflow:hidden;background:#0f172a;border:2px solid rgba(255,255,255,.18);">
                ${posterImg(url, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;display:block;`, conf)}
            </div>
        </div>`;
    }

    function buildPosterRenderCtx(templateId, formatKey, conf, p, b, imgs, opts) {
        const layout = posterFormatLayout(formatKey);
        const primary = opts.primary;
        const cropY = conf.crop_y ?? 50;
        const headline = opts.headline;
        const price = opts.price;
        const locLine = opts.locLine;
        const primaryColor = opts.primaryColor;
        const accentInk = opts.accentInk;
        const brandName = opts.brandName;
        const phone = opts.phone;
        const dealLabel = opts.dealLabel;
        const facts = posterContentFacts(p, headline, locLine);
        const imgCount = imgs.filter(Boolean).length;
        const heroIdx = opts.primaryImageIndex != null
            ? opts.primaryImageIndex
            : (conf.primary_image_index || 0);
        let circleImageIndices = opts.circleImageIndices;
        if (!circleImageIndices || !circleImageIndices.length) {
            circleImageIndices = sculpturalCircleIndices(imgs, heroIdx, 3);
        }
        const stripImageIndex = opts.stripImageIndex != null
            ? opts.stripImageIndex
            : emeraldStripIndex({ primary_image_index: heroIdx, secondary_image_index: conf.secondary_image_index }, propertyImageList());
        const stripUrl = slideImageAt(stripImageIndex) || imgs[1] || primary || '';
        const g0 = imgs[0] || primary || '';
        const g1 = imgs[1] || '';
        const g2 = imgs[2] || '';
        const gold = '#c9a227';
        const cream = '#f7f2e8';
        const charcoal = '#141210';
        return {
            templateId,
            layout,
            conf,
            p,
            b,
            imgs,
            primary,
            cropY,
            headline,
            price,
            facts,
            primaryColor,
            accentInk,
            brandName,
            phone,
            dealLabel,
            imgCount,
            heroIdx,
            circleImageIndices,
            stripImageIndex,
            stripUrl,
            g0,
            g1,
            g2,
            gold,
            cream,
            charcoal,
        };
    }

    function renderLuxuryPoster(ctx) {
        const { layout, conf, primary, cropY, headline, price, facts, primaryColor, accentInk, brandName, phone, dealLabel, b, gold, cream, charcoal } = ctx;
        const pad = layout.pad;
        const contentW = layout.w - pad * 2;
        const headFit = posterHeadlineFit(conf, layout.hlLuxury, headline, contentW, 3);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', '#fff');
        const headHtml = headFit.lines.map((ln) => `<div style="${pcsTextStyle(`font-size:${hl}px;line-height:1.1;letter-spacing:-0.02em;text-shadow:0 2px 24px rgba(0,0,0,.45);${headEmph}`)}">${esc(ln)}</div>`).join('');
        const headZone = posterHeadlineBlockHeight(hl, headFit.lines.length, 1.1) + 56;
        const cardLift = layout.isStory ? 48 : 40;
        const priceColor = primaryColor || charcoal;
        return `
            <div style="position:absolute;inset:0;background:${cream};overflow:hidden;display:flex;flex-direction:column;">
                <div style="position:absolute;inset:${Math.round(pad * 0.55)}px ${pad}px ${pad + 120}px;border:1px solid rgba(201,162,39,.32);border-radius:4px;pointer-events:none;z-index:4;"></div>
                <div style="position:relative;flex:1;min-height:0;overflow:hidden;">
                    ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : `<div style="width:100%;height:100%;background:linear-gradient(165deg,#3d3830,#1a1814);"></div>`}
                    <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(18,16,14,.22) 0%,transparent 28%,transparent 58%,rgba(18,16,14,.72) 100%);pointer-events:none;"></div>
                    ${posterHeroWarmth(conf)}
                    ${posterHeroVignetteExtra(conf)}
                    ${posterPipInset(conf, primaryColor, accentInk, 'luxury_hero')}
                    <div style="position:absolute;left:${pad}px;right:${pad}px;bottom:${headZone}px;z-index:6;">
                        <div style="width:56px;height:2px;background:${gold};margin-bottom:14px;"></div>
                        ${wrapPosterHeadlineRole(headHtml, conf)}
                    </div>
                    ${brandLogoBlock(b, layout.isSquare ? 62 : 70)}
                    <div style="position:absolute;top:${pad}px;left:${pad}px;z-index:7;transform:scale(.92);transform-origin:top left;">${dealBadgeHtml(dealLabel, gold, 'dark')}</div>
                </div>
                ${posterPipInset(conf, primaryColor, accentInk, 'luxury_overlay')}
                <div style="position:relative;z-index:9;margin:-${cardLift}px ${pad}px ${layout.safeBottom}px;padding:22px 26px 20px;background:linear-gradient(180deg,rgba(255,251,245,.98),rgba(247,242,232,.98));border-radius:22px;box-shadow:0 24px 64px rgba(20,18,16,.16);border:1px solid rgba(20,18,16,.06);">
                    ${price ? posterPriceEditorialWrapped(price, conf, layout, priceColor, false, { maxWidth: contentW - 20 }) : ''}
                    ${posterSpecsLineWrapped(facts, charcoal, 'light', { compact: true, noMargin: !price }, conf)}
                    ${brandName ? `<div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(20,18,16,.08);">${brandFooterHtml(brandName, phone, 'light')}</div>` : ''}
                </div>
            </div>`;
    }

    function renderModernPoster(ctx) {
        const { layout, conf, primary, cropY, headline, price, facts, accentInk, brandName, phone, dealLabel, primaryColor } = ctx;
        const pad = layout.pad;
        const contentW = layout.w - pad * 2;
        return `
            <div style="position:absolute;inset:0;background:#f6f4f0;overflow:hidden;">
                <div style="position:absolute;top:0;right:0;width:42%;height:38%;background:linear-gradient(225deg,${primaryRgba(accentInk, 0.09)},transparent);pointer-events:none;"></div>
                <div style="position:absolute;inset:0;box-sizing:border-box;padding:${pad}px ${pad}px ${layout.safeBottom}px;display:flex;flex-direction:column;gap:18px;">
                    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-shrink:0;">
                        <div style="flex:1;min-width:0;padding-top:4px;">${wrapPosterHeadlineRole(modernHeadlineMarkup(headline, conf, accentInk, layout.hlModern, contentW - 100), conf)}</div>
                        <div style="flex-shrink:0;margin-top:2px;">${dealBadgeHtml(dealLabel, accentInk, 'light')}</div>
                    </div>
                    <div style="position:relative;flex:1;min-height:${layout.modernImgMin}px;border-radius:22px;overflow:hidden;box-shadow:0 32px 64px rgba(15,23,42,.12);border:1px solid rgba(15,23,42,.06);">
                        <div style="position:absolute;top:0;bottom:0;right:0;width:6px;background:${accentInk};z-index:2;"></div>
                        ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : `<div style="width:100%;height:100%;background:#e2e8f0;"></div>`}
                        ${posterHeroWarmth(conf)}
                        ${posterPipInset(conf, primaryColor, accentInk, 'minimal_hero')}
                    </div>
                    <div style="flex-shrink:0;display:flex;flex-direction:column;gap:16px;min-height:${layout.modernFooterMin}px;justify-content:flex-end;padding-top:6px;">
                        ${price ? posterPriceEditorialWrapped(price, conf, layout, accentInk, false, { maxWidth: contentW }) : ''}
                        ${posterSpecsLineWrapped(facts, accentInk, 'light', { compact: true, noMargin: true, prominent: true }, conf)}
                        ${brandName ? `<div style="padding-top:12px;border-top:1px solid rgba(15,23,42,.1);font-size:26px;">${brandFooterHtml(brandName, phone, 'light')}</div>` : ''}
                    </div>
                </div>
            </div>`;
    }

    function renderCollagePoster(ctx) {
        const { layout, conf, cropY, headline, price, facts, primaryColor, accentInk, brandName, phone, dealLabel, g0, g1, g2, imgCount, primary } = ctx;
        const pad = layout.pad;
        const accent = accentInk;
        const mainUrl = g0 || primary;
        const sec1 = imgCount >= 2 ? (g1 || '') : '';
        const sec2 = imgCount >= 3 ? (g2 || '') : '';
        const footerH = layout.isSquare ? 280 : layout.isPost ? 300 : 340;
        const headMaxW = layout.w - pad * 2 - 120;
        const headFit = posterHeadlineFit(conf, layout.hlCollage, headline, headMaxW, 2);
        const hl = headFit.px;
        const headBlockH = posterHeadlineBlockHeight(hl, headFit.lines.length, 1.08) + 20;
        const headTop = pad;
        const mainTop = headTop + headBlockH + 16;
        const mainWpct = layout.isSquare ? 54 : 56;
        const mainH = Math.min(layout.collageMainH, layout.h - mainTop - footerH - pad);
        const headEmph = posterTextEmphasis(conf, 'headline', '#fff');
        const headHtml = headFit.lines.map((ln) => `<div style="${pcsTextStyle(`font-size:${hl}px;line-height:1.08;letter-spacing:-0.02em;${headEmph}`)}">${esc(ln)}</div>`).join('');
        const thumbBase = layout.collageThumb;
        const thumbGap = layout.collageThumbGap;
        const thumbLg = thumbBase;
        const thumbSm = Math.round(thumbBase * 0.92);
        const stripW = Math.round(layout.w * 0.44);
        const thumbsHtml = imgCount >= 3
            ? `<div style="position:absolute;right:${pad}px;top:0;width:${stripW - pad}px;height:${mainH}px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:${thumbGap}px;z-index:6;pointer-events:none;">
                ${collageThumbFrame(sec1, thumbLg, cropY, conf, accent)}
                ${collageThumbFrame(sec2, thumbSm, cropY, conf, '#fff')}
               </div>
               ${posterPipInset(conf, primaryColor, accentInk)}`
            : imgCount === 2
                ? `<div style="position:absolute;right:${pad}px;top:0;width:${stripW - pad}px;height:${mainH}px;display:flex;align-items:center;justify-content:center;z-index:6;pointer-events:none;">
                    ${collageThumbFrame(sec1, Math.round(thumbBase * 1.04), cropY, conf, accent)}
                   </div>
                   ${posterPipInset(conf, primaryColor, accentInk)}`
                : `${posterPipInset(conf, primaryColor, accentInk)}`;
        return `
            <div style="position:absolute;inset:0;background:#0c0c0c;overflow:hidden;display:flex;flex-direction:column;">
                <div style="position:absolute;width:${stripW}px;height:100%;top:0;right:0;background:linear-gradient(180deg,${accent} 0%,${primaryRgba(accent, 0.82)} 100%);z-index:1;"></div>
                <div style="position:relative;z-index:5;padding:${headTop}px ${pad}px 0;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;min-height:${headBlockH}px;box-sizing:border-box;">
                    <div style="transform:scale(.9);transform-origin:top left;flex-shrink:0;">${dealBadgeHtml(dealLabel, '#fff', 'dark')}</div>
                    <div style="flex:1;max-width:${headMaxW}px;text-align:end;">${wrapPosterHeadlineRole(headHtml, conf)}</div>
                </div>
                <div style="position:relative;flex:1;min-height:0;z-index:4;">
                    <div style="position:absolute;left:${pad}px;top:0;width:${mainWpct}%;height:${mainH}px;border-radius:100px 100px 24px 24px;overflow:hidden;box-shadow:0 36px 80px rgba(0,0,0,.55);border:3px solid rgba(255,255,255,.12);">
                        ${mainUrl ? posterImg(mainUrl, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : '<div style="width:100%;height:100%;background:#334155;"></div>'}
                        ${posterHeroWarmth(conf)}
                    </div>
                    ${thumbsHtml}
                </div>
                <div style="position:relative;z-index:8;flex-shrink:0;padding:${pad}px ${pad}px ${layout.safeBottom}px;background:#0c0c0c;border-top:1px solid rgba(255,255,255,.08);">
                    ${price ? `<div style="margin-bottom:14px;">${posterPriceEditorialWrapped(price, conf, layout, accent, true, { maxWidth: layout.w - pad * 2 })}</div>` : ''}
                    ${posterSpecsLineWrapped(facts, '#fff', 'dark', { compact: true, noMargin: true }, conf)}
                    ${brandName ? `<div style="margin-top:12px;">${brandFooterHtml(brandName, phone, 'dark')}</div>` : ''}
                </div>
            </div>`;
    }

    function renderCampaignPoster(ctx) {
        const { layout, conf, primary, cropY, headline, price, facts, primaryColor, accentInk, brandName, phone, dealLabel } = ctx;
        const pad = layout.pad;
        const contentW = layout.w - pad * 2;
        const headFit = posterHeadlineFit(conf, layout.hlCampaign, headline, contentW, 3);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', '#0f172a');
        const headHtml = headFit.lines.map((ln) => `<div style="${pcsTextStyle(`font-size:${hl}px;line-height:1.08;letter-spacing:-0.02em;${headEmph}`)}">${esc(ln)}</div>`).join('');
        const cta = phone ? 'هماهنگی بازدید' : 'مشاوره رایگان';
        return `
            <div style="position:absolute;inset:0;background:#0a0a0f;overflow:hidden;display:flex;flex-direction:column;">
                <div style="flex:1;min-height:0;padding:${pad}px ${pad}px 0;box-sizing:border-box;display:flex;flex-direction:column;">
                    <div style="position:relative;flex:1;min-height:${Math.round(layout.h * 0.38)}px;border-radius:24px;overflow:hidden;box-shadow:0 32px 70px rgba(0,0,0,.45);">
                        ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : `<div style="width:100%;height:100%;background:#1e293b;"></div>`}
                        <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.1),transparent 50%,rgba(0,0,0,.35));pointer-events:none;"></div>
                        ${posterHeroWarmth(conf)}
                        ${posterPipInset(conf, primaryColor, accentInk)}
                        <div style="position:absolute;top:16px;right:16px;">${dealBadgeHtml(dealLabel, primaryColor, 'dark')}</div>
                        <div style="position:absolute;bottom:0;left:0;right:0;height:32%;background:linear-gradient(180deg,transparent,${primaryRgba(primaryColor, 0.88)});pointer-events:none;"></div>
                    </div>
                </div>
                <div style="flex-shrink:0;margin-top:-20px;padding:${pad + 8}px ${pad}px ${layout.safeBottom}px;background:#fff;border-radius:28px 28px 0 0;box-shadow:0 -16px 48px rgba(0,0,0,.18);">
                    <div style="margin-bottom:10px;">${wrapPosterHeadlineRole(headHtml, conf)}</div>
                    ${price ? `<div style="margin-bottom:12px;">${posterPriceEditorialWrapped(price, conf, layout, accentInk, false, { maxWidth: contentW })}</div>` : ''}
                    ${posterSpecsLineWrapped(facts, accentInk, 'light', { compact: true, noMargin: true }, conf)}
                    <div style="margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 20px;border-radius:16px;background:${primaryRgba(accentInk, 0.1)};border:1px solid ${primaryRgba(accentInk, 0.18)};">
                        <span style="${pcsTextStyle('font-size:30px;font-weight:800;color:#334155;')}">${esc(cta)}</span>
                        ${phone ? `<span dir="ltr" style="${pcsTextStyle(`font-size:34px;font-weight:900;color:${accentInk};`)}">${esc(phone)}</span>` : ''}
                    </div>
                    ${brandName ? `<div style="margin-top:12px;">${brandFooterHtml(brandName, '', 'light')}</div>` : ''}
                </div>
            </div>`;
    }

    function pearlescentOverlayUrl() {
        return cfg.templateMeta?.pearlescent?.overlay || '';
    }

    function pearlescentLayoutMetrics(canvasH) {
        return {
            photoH: Math.round(0.455 * canvasH),
            bodyTop: Math.round(0.47 * canvasH),
            bodyBottom: Math.round(0.875 * canvasH),
            footerTop: Math.round(0.878 * canvasH),
            footerBottom: Math.round(0.985 * canvasH),
        };
    }

    function renderPearlescentPoster(ctx) {
        const overlay = pearlescentOverlayUrl();
        if (!overlay) return renderModernPoster(ctx);

        const {
            layout, conf, primary, cropY, headline, price, locLine,
            primaryColor, accentInk, brandName, phone, facts, dealLabel, b, p,
        } = ctx;
        const fmt = layout.fmt;
        const m = pearlescentLayoutMetrics(fmt.h);
        const ink = '#0a3560';
        const footInk = '#ffffff';
        const sidePad = layout.isStory ? 72 : 56;
        const contentW = layout.w - sidePad * 2;
        const headFit = posterHeadlineFit(conf, layout.hlModern, headline, contentW, 3);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', ink);
        const headHtml = headFit.lines.map((ln) => `<div style="${pcsTextStyle(`font-size:${hl}px;line-height:1.1;letter-spacing:-0.02em;${headEmph}`)}">${esc(ln)}</div>`).join('');
        const metaFacts = facts && typeof facts === 'object'
            ? facts
            : posterContentFacts(p, headline, locLine);
        const specsHtml = posterSpecsLineHtml(metaFacts, accentInk, 'light', {
            compact: true,
            noMargin: true,
            prominent: true,
        });
        const priceHtml = price
            ? `<div style="margin-top:14px;">${posterPriceEditorial(price, conf, layout, accentInk, false, { maxWidth: contentW })}</div>`
            : '';
        const bodyHtml = `<div dir="rtl" style="max-width:100%;display:flex;flex-direction:column;gap:0;width:100%;overflow:visible;">
            ${wrapPosterHeadlineRole(headHtml, conf)}
            ${specsHtml ? wrapPosterMetaRole(`<div style="margin-top:12px;">${specsHtml}</div>`, conf) : ''}
            ${priceHtml ? wrapPosterPriceRole(priceHtml, conf) : ''}
        </div>`;
        const cta = phone ? 'هماهنگی بازدید' : 'مشاوره رایگان';
        const footerHtml = `
            <div style="display:flex;flex-direction:column;gap:10px;width:100%;align-items:stretch;">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px;border-radius:14px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);">
                    <span style="${pcsTextStyle(`font-size:28px;font-weight:800;color:${footInk};`)}">${esc(cta)}</span>
                    ${phone ? `<span dir="ltr" style="${pcsTextStyle(`font-size:30px;font-weight:900;color:${footInk};`)}">${esc(phone)}</span>` : ''}
                </div>
                ${brandName ? brandFooterHtml(brandName, '', 'dark') : ''}
            </div>`;
        const logoSize = layout.isStory ? 68 : 58;

        return `
            <div class="pcs-pearlescent-frame" style="position:absolute;inset:0;background:#e8f4fc;overflow:hidden;">
                <div style="position:absolute;left:0;right:0;top:0;height:${m.photoH}px;overflow:hidden;z-index:0;">
                    ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:center ${cropY}%;`, conf) : `<div style="width:100%;height:100%;background:linear-gradient(180deg,#5a8fb8 0%,#2a5080 100%);"></div>`}
                    ${posterHeroWarmth(conf)}
                    <div style="position:absolute;top:${layout.pad}px;right:${layout.pad}px;z-index:4;">${dealBadgeHtml(dealLabel, primaryColor, 'dark')}</div>
                    <div style="position:absolute;top:${layout.pad}px;left:${layout.pad}px;z-index:4;">${brandLogoBlock(b, logoSize)}</div>
                </div>
                <div style="position:absolute;left:${sidePad}px;right:${sidePad}px;top:${m.bodyTop}px;height:${Math.max(0, m.bodyBottom - m.bodyTop)}px;z-index:3;display:flex;align-items:flex-start;justify-content:flex-start;padding-top:8px;box-sizing:border-box;">
                    ${bodyHtml}
                </div>
                <div style="position:absolute;left:${sidePad - 12}px;right:${sidePad - 12}px;top:${m.footerTop}px;height:${Math.max(0, m.footerBottom - m.footerTop)}px;z-index:3;display:flex;align-items:center;justify-content:center;padding:0 8px;box-sizing:border-box;pointer-events:none;">
                    ${footerHtml}
                </div>
                <img class="pcs-pearlescent-frame__overlay" src="${esc(overlay)}" alt="" decoding="async" crossorigin="anonymous" referrerpolicy="no-referrer" style="position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none;z-index:2;">
            </div>`;
    }

    function sculpturalOverlayUrl() {
        return cfg.templateMeta?.sculptural?.overlay || '';
    }

    /** کالیبراسیون از تحلیل alpha فایل overlay (941×1672) */
    const SCULPTURAL_CALIBRATION = {
        refW: 941,
        refH: 1672,
        hero: { x0: 0, y0: 3, x1: 772, y1: 819, focusX: 347, focusY: 420 },
        text: { x0: 520, y0: 798, x1: 939, y1: 1519, padX: 34, padY: 8, padEndX: 30, padEndY: 72 },
        footer: { x0: 52, y0: 1542, x1: 888, y1: 1660 },
        badge: { cx: 718, cy: 52 },
        logo: { cx: 46, cy: 46, size: 48 },
        circles: [
            { cx: 173.05, cy: 1007.84, d: 284, inset: 0.97, z: 1 },
            { cx: 457.77, cy: 1183.04, d: 280, inset: 0.97, z: 2 },
            { cx: 176.53, cy: 1354.73, d: 286, inset: 0.97, z: 3 },
        ],
    };

    /** مرجع اندازهٔ واقعی فایل overlay (webp) */
    const SCULPTURAL_OVERLAY_REF = { w: SCULPTURAL_CALIBRATION.refW, h: SCULPTURAL_CALIBRATION.refH };

    /** اندیس تصاویر دایره‌ها — بدون تکرار تصویر قهرمان */
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

    /**
     * مختصات از تحلیل alpha قالب — سوراخ‌های شفاف overlay (941×1672).
     */
    function sculpturalLayoutMetrics(w, h) {
        const cal = SCULPTURAL_CALIBRATION;
        const sx = w / cal.refW;
        const sy = h / cal.refH;
        const px = (x) => Math.round(x * sx);
        const py = (y) => Math.round(y * sy);
        const pd = (d) => Math.round(d * sx);
        const hero = cal.hero;
        return {
            hero: {
                left: px(hero.x0),
                top: py(hero.y0),
                width: px(hero.x1 - hero.x0),
                height: py(hero.y1 - hero.y0),
                objX: ((hero.focusX - hero.x0) / (hero.x1 - hero.x0)) * 100,
                objY: ((hero.focusY - hero.y0) / (hero.y1 - hero.y0)) * 100,
            },
            circles: cal.circles
                .slice()
                .sort((a, b) => (a.z || 0) - (b.z || 0))
                .map((c) => ({
                    cx: px(c.cx),
                    cy: py(c.cy),
                    d: pd(c.d * (c.inset || 0.8)),
                    z: c.z || 1,
                })),
            text: {
                left: px(cal.text.x0 + (cal.text.padX || 0)),
                top: py(cal.text.y0 + (cal.text.padY || 0)),
                width: px((cal.text.x1 - cal.text.x0) - (cal.text.padX || 0) - (cal.text.padEndX || 0)),
                height: py((cal.text.y1 - cal.text.y0) - (cal.text.padY || 0) - (cal.text.padEndY || 0)),
            },
            footer: {
                left: px(cal.footer.x0),
                top: py(cal.footer.y0),
                width: px(cal.footer.x1 - cal.footer.x0),
                height: py(cal.footer.y1 - cal.footer.y0),
            },
            badge: { left: px(cal.badge.cx), top: py(cal.badge.cy) },
            logo: { left: px(cal.logo.cx), top: py(cal.logo.cy) },
        };
    }

    function sculpturalCircleSlotHtml(url, cx, cy, d, conf, zIndex) {
        const z = zIndex || 1;
        if (!url) {
            return `<div style="position:absolute;left:${cx - d / 2}px;top:${cy - d / 2}px;width:${d}px;height:${d}px;border-radius:50%;background:#1a2218;z-index:${z};"></div>`;
        }
        return `<div style="position:absolute;left:${cx - d / 2}px;top:${cy - d / 2}px;width:${d}px;height:${d}px;border-radius:50%;overflow:hidden;z-index:${z};isolation:isolate;background:#1a2218;">
            ${posterImg(url, 'width:100%;height:100%;min-width:100%;min-height:100%;object-fit:cover;object-position:center center;display:block;', conf)}
        </div>`;
    }

    function sculpturalMetaLine(p, metaFacts) {
        const parts = [];
        if (metaFacts.locLine) parts.push(metaFacts.locLine);
        if (p.property_type) parts.push(p.property_type);
        if (p.area_label && !parts.some((x) => x.includes(p.area_label))) parts.push(p.area_label);
        return parts.filter(Boolean).slice(0, 3).join(' · ');
    }

    function sculpturalPriceLine(price, conf, layout, h, maxW) {
        if (!price) return '';
        const safeW = Math.max(120, Math.floor(maxW * 0.92));
        const px = Math.min(posterPriceFit(conf, layout, price, safeW), Math.round(h * 0.048));
        const emph = posterTextEmphasis(conf, 'price', '#ffffff');
        return `<div style="margin-top:14px;width:100%;max-width:100%;overflow:hidden;box-sizing:border-box;">
            <span style="${pcsTextStyle(`display:block;max-width:100%;overflow:hidden;font-size:${px}px;line-height:1.15;${emph}text-shadow:0 2px 16px rgba(0,0,0,.55);`)}">${esc(price)}</span>
        </div>`;
    }

    function renderSculpturalPoster(ctx) {
        const overlay = sculpturalOverlayUrl();
        if (!overlay) return renderPearlescentPoster(ctx);

        const {
            layout, conf, primary, cropY, headline, price, locLine,
            primaryColor, accentInk, brandName, phone, facts, dealLabel, b, p,
            imgs, circleImageIndices, heroIdx,
        } = ctx;
        const fmt = layout.fmt;
        const w = fmt.w;
        const h = fmt.h;
        const m = sculpturalLayoutMetrics(w, h);
        const ink = '#f7f4ec';
        const inkMuted = 'rgba(247,244,236,.88)';
        const textShadow = 'text-shadow:0 2px 12px rgba(0,0,0,.55);';
        const textW = Math.max(140, m.text.width);
        const headFit = posterHeadlineFit(conf, layout.hlModern, headline, Math.floor(textW * 0.96), 2);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', ink);
        const headBlock = 'max-width:100%;overflow:hidden;word-wrap:break-word;overflow-wrap:anywhere;';
        const headHtml = headFit.lines.slice(0, 2).map((ln) => `<div style="${pcsTextStyle(`${headBlock}font-size:${hl}px;line-height:1.2;letter-spacing:-0.012em;${headEmph}${textShadow}`)}">${esc(ln)}</div>`).join('');
        const metaFacts = facts && typeof facts === 'object'
            ? facts
            : posterContentFacts(p, headline, locLine);
        const metaLine = sculpturalMetaLine(p, metaFacts);
        const metaHtml = metaLine
            ? `<p style="${pcsTextStyle(`${headBlock}margin:12px 0 0;font-size:${Math.round(h * 0.0165)}px;font-weight:600;color:${inkMuted};line-height:1.5;${textShadow}`)}">${esc(metaLine)}</p>`
            : '';
        const priceHtml = sculpturalPriceLine(price, conf, layout, h, textW);
        const textHtml = `<div dir="rtl" style="display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;text-align:right;unicode-bidi:plaintext;width:100%;height:100%;max-width:100%;max-height:100%;overflow:visible;box-sizing:border-box;padding-top:2px;">
            ${wrapPosterTextRole('headline', headHtml, conf)}
            ${wrapPosterTextRole('meta', metaHtml, conf)}
            ${wrapPosterTextRole('price', priceHtml, conf)}
        </div>`;
        const footerHtml = `
            <div dir="rtl" style="display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;height:100%;padding:0 14px;box-sizing:border-box;overflow:hidden;">
                ${brandName ? `<span style="${pcsTextStyle('flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;font-size:' + Math.round(h * 0.016) + 'px;font-weight:700;color:rgba(255,255,255,.9);')}">${esc(brandName)}</span>` : '<span style="flex:1;"></span>'}
                ${phone ? `<span dir="ltr" style="${pcsTextStyle('flex-shrink:0;max-width:58%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:' + Math.round(h * 0.025) + 'px;font-weight:900;color:#fff;letter-spacing:.02em;')}">${esc(phone)}</span>` : ''}
            </div>`;
        const logoSize = layout.isStory ? (SCULPTURAL_CALIBRATION.logo.size || 48) : 42;
        const circleIdx = circleImageIndices || [];
        const circlesHtml = m.circles.map((slot, i) => {
            const idx = circleIdx[i];
            const url = idx != null && imgs[idx] ? imgs[idx] : (imgs[(heroIdx + i + 1) % (imgs.length || 1)] || '');
            return sculpturalCircleSlotHtml(url, slot.cx, slot.cy, slot.d, conf, slot.z);
        }).join('');
        const heroPos = `${m.hero.objX.toFixed(1)}% ${cropY}%`;

        return `
            <div class="pcs-sculptural-frame" style="position:absolute;inset:0;background:#ebe6dc;overflow:hidden;">
                <div style="position:absolute;left:${m.hero.left}px;top:${m.hero.top}px;width:${m.hero.width}px;height:${m.hero.height}px;overflow:hidden;z-index:1;">
                    ${primary ? posterImg(primary, `width:100%;height:100%;object-fit:cover;object-position:${heroPos};`, conf) : `<div style="width:100%;height:100%;background:linear-gradient(160deg,#6b7560 0%,#2f3828 100%);"></div>`}
                    ${posterHeroWarmth(conf)}
                </div>
                ${circlesHtml}
                <img class="pcs-pearlescent-frame__overlay" src="${esc(overlay)}" alt="" decoding="async" crossorigin="anonymous" referrerpolicy="no-referrer" style="position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none;z-index:2;">
                <div style="position:absolute;left:${m.text.left}px;top:${m.text.top}px;width:${m.text.width}px;height:${m.text.height}px;z-index:3;display:flex;align-items:flex-start;justify-content:flex-start;overflow:visible;">
                    ${textHtml}
                </div>
                <div style="position:absolute;left:${m.badge.left}px;top:${m.badge.top}px;z-index:4;transform:translate(-100%,0) scale(.85);transform-origin:top right;">${dealBadgeHtml(dealLabel, primaryColor, 'dark')}</div>
                <div style="position:absolute;left:${m.logo.left}px;top:${m.logo.top}px;z-index:4;transform:translate(-50%,-50%);">${brandLogoBlock(b, logoSize)}</div>
                <div style="position:absolute;left:${m.footer.left}px;top:${m.footer.top}px;width:${m.footer.width}px;height:${m.footer.height}px;z-index:3;display:flex;align-items:center;pointer-events:none;">
                    ${footerHtml}
                </div>
            </div>`;
    }

    function emeraldAtelierOverlayUrl() {
        return cfg.templateMeta?.emerald_atelier?.overlay || '';
    }

    /** کالیبراسیون از سوراخ‌های alpha overlay (941×1672) */
    const EMERALD_CALIBRATION = {
        refW: 941,
        refH: 1672,
        arch: { x0: 142, y0: 128, x1: 636, y1: 1014, focusX: 390, focusY: 520 },
        strip: { x0: 694, y0: 326, x1: 899, y1: 1014, focusX: 798, focusY: 620 },
        text: { x0: 128, y0: 1060, x1: 916, y1: 1410, padX: 28, padY: 14, padEndX: 32, padEndY: 24 },
        footer: { x0: 48, y0: 1598, x1: 892, y1: 1658 },
        badge: { cx: 848, cy: 72 },
        logo: { cx: 92, cy: 72, size: 52 },
    };

    function emeraldAtelierPhotoIndices(imgs, heroIndex) {
        const n = (imgs || []).length;
        const hero = Math.max(0, Math.min(Math.max(0, n - 1), heroIndex || 0));
        if (n < 2) return { arch: hero, strip: hero };
        let strip = hero === 0 ? 1 : 0;
        if (strip === hero) strip = (hero + 1) % n;
        return { arch: hero, strip };
    }

    function emeraldLayoutMetrics(w, h) {
        const cal = EMERALD_CALIBRATION;
        const sx = w / cal.refW;
        const sy = h / cal.refH;
        const px = (x) => Math.round(x * sx);
        const py = (y) => Math.round(y * sy);
        const box = (b) => ({
            left: px(b.x0),
            top: py(b.y0),
            width: px(b.x1 - b.x0),
            height: py(b.y1 - b.y0),
            objX: ((b.focusX - b.x0) / (b.x1 - b.x0)) * 100,
            objY: ((b.focusY - b.y0) / (b.y1 - b.y0)) * 100,
        });
        const t = cal.text;
        return {
            arch: box(cal.arch),
            strip: box(cal.strip),
            text: {
                left: px(t.x0 + (t.padX || 0)),
                top: py(t.y0 + (t.padY || 0)),
                width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
                height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
            },
            footer: {
                left: px(cal.footer.x0),
                top: py(cal.footer.y0),
                width: px(cal.footer.x1 - cal.footer.x0),
                height: py(cal.footer.y1 - cal.footer.y0),
            },
            badge: { left: px(cal.badge.cx), top: py(cal.badge.cy) },
            logo: { left: px(cal.logo.cx), top: py(cal.logo.cy) },
        };
    }

    function emeraldPhotoSlotHtml(url, slot, conf, cropY) {
        const pos = `${slot.objX.toFixed(1)}% ${cropY}%`;
        if (!url) {
            return `<div style="position:absolute;left:${slot.left}px;top:${slot.top}px;width:${slot.width}px;height:${slot.height}px;background:#0a0a0a;z-index:1;"></div>`;
        }
        return `<div style="position:absolute;left:${slot.left}px;top:${slot.top}px;width:${slot.width}px;height:${slot.height}px;overflow:hidden;z-index:1;">
            ${posterImg(url, `width:100%;height:100%;min-width:100%;min-height:100%;object-fit:cover;object-position:${pos};display:block;`, conf)}
        </div>`;
    }

    function renderEmeraldAtelierPoster(ctx) {
        const overlay = emeraldAtelierOverlayUrl();
        if (!overlay) return renderPearlescentPoster(ctx);

        const {
            layout, conf, primary, stripUrl, cropY, headline, price, locLine,
            primaryColor, brandName, phone, dealLabel, b, p, facts,
        } = ctx;
        const fmt = layout.fmt;
        const w = fmt.w;
        const h = fmt.h;
        const m = emeraldLayoutMetrics(w, h);
        const ink = '#122820';
        const inkMuted = 'rgba(18,40,32,.78)';
        const priceInk = '#0b4d3e';
        const textW = Math.max(160, m.text.width);
        const headFit = posterHeadlineFit(conf, layout.hlModern, headline, Math.floor(textW * 0.96), 2);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', ink);
        const headBlock = 'max-width:100%;overflow:hidden;word-wrap:break-word;overflow-wrap:anywhere;';
        const headHtml = headFit.lines.slice(0, 2).map((ln) => `<div style="${pcsTextStyle(`${headBlock}font-size:${hl}px;line-height:1.22;letter-spacing:-0.01em;${headEmph}`)}">${esc(ln)}</div>`).join('');
        const metaFacts = facts && typeof facts === 'object'
            ? facts
            : posterContentFacts(p, headline, locLine);
        const metaParts = [];
        if (metaFacts.locLine) metaParts.push(metaFacts.locLine);
        if (p.property_type) metaParts.push(p.property_type);
        if (p.area_label && !metaParts.some((x) => x.includes(p.area_label))) metaParts.push(p.area_label);
        const metaLine = metaParts.filter(Boolean).slice(0, 3).join(' · ');
        const metaHtml = metaLine
            ? `<p style="${pcsTextStyle(`${headBlock}margin:10px 0 0;font-size:${Math.round(h * 0.016)}px;font-weight:600;color:${inkMuted};line-height:1.5;`)}">${esc(metaLine)}</p>`
            : '';
        let priceHtml = '';
        if (price) {
            const px = posterPriceFit(conf, layout, price, Math.floor(textW * 0.94));
            const emph = posterTextEmphasis(conf, 'price', priceInk);
            priceHtml = `<div style="margin-top:12px;width:100%;max-width:100%;overflow:hidden;">
                <span style="${pcsTextStyle(`display:block;font-size:${px}px;line-height:1.15;${emph}`)}">${esc(price)}</span>
            </div>`;
        }
        const textHtml = `<div dir="rtl" style="display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-start;text-align:right;unicode-bidi:plaintext;width:100%;height:100%;overflow:visible;box-sizing:border-box;">
            ${wrapPosterTextRole('headline', headHtml, conf)}
            ${wrapPosterTextRole('meta', metaHtml, conf)}
            ${wrapPosterTextRole('price', priceHtml, conf)}
        </div>`;
        const footerHtml = `
            <div dir="rtl" style="display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;height:100%;padding:0 16px;box-sizing:border-box;overflow:hidden;">
                ${brandName ? `<span style="${pcsTextStyle('flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;font-size:' + Math.round(h * 0.015) + 'px;font-weight:700;color:rgba(255,255,255,.92);')}">${esc(brandName)}</span>` : '<span style="flex:1;"></span>'}
                ${phone ? `<span dir="ltr" style="${pcsTextStyle('flex-shrink:0;max-width:58%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:' + Math.round(h * 0.024) + 'px;font-weight:900;color:#fff;')}">${esc(phone)}</span>` : ''}
            </div>`;
        const logoSize = layout.isStory ? (EMERALD_CALIBRATION.logo.size || 52) : 44;
        const archUrl = primary || stripUrl;
        const sideUrl = stripUrl || primary;

        return `
            <div class="pcs-emerald-frame" style="position:absolute;inset:0;background:#e8dcc8;overflow:hidden;">
                ${emeraldPhotoSlotHtml(archUrl, m.arch, conf, cropY)}
                ${emeraldPhotoSlotHtml(sideUrl, m.strip, conf, cropY)}
                <img class="pcs-pearlescent-frame__overlay" src="${esc(overlay)}" alt="" decoding="async" crossorigin="anonymous" referrerpolicy="no-referrer" style="position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none;z-index:2;">
                <div style="position:absolute;left:${m.text.left}px;top:${m.text.top}px;width:${m.text.width}px;height:${m.text.height}px;z-index:3;display:flex;align-items:flex-start;justify-content:flex-start;overflow:visible;">
                    ${textHtml}
                </div>
                <div style="position:absolute;left:${m.badge.left}px;top:${m.badge.top}px;z-index:4;transform:translate(-100%,0) scale(.82);transform-origin:top right;">${dealBadgeHtml(dealLabel, primaryColor, 'dark')}</div>
                <div style="position:absolute;left:${m.logo.left}px;top:${m.logo.top}px;z-index:4;transform:translate(-50%,-50%);">${brandLogoBlock(b, logoSize)}</div>
                <div style="position:absolute;left:${m.footer.left}px;top:${m.footer.top}px;width:${m.footer.width}px;height:${m.footer.height}px;z-index:3;display:flex;align-items:center;pointer-events:none;">
                    ${footerHtml}
                </div>
            </div>`;
    }

    function pearlGalleryOverlayUrl() {
        return cfg.templateMeta?.pearl_gallery?.overlay || '';
    }

    /** کالیبراسیون از سوراخ‌های دایره‌ای alpha overlay (940×1672) */
    const PEARL_GALLERY_CALIBRATION = {
        refW: 940,
        refH: 1672,
        primary: { cx: 452, cy: 526, d: 702 },
        secondary: { cx: 760, cy: 804, d: 310 },
        text: { x0: 108, y0: 1008, x1: 832, y1: 1518, padX: 24, padY: 10, padEndX: 28, padEndY: 18 },
        footer: { x0: 72, y0: 1554, x1: 868, y1: 1628 },
        badge: { cx: 818, cy: 92 },
        logo: { cx: 96, cy: 78, size: 50 },
    };

    function pearlLayoutMetrics(w, h) {
        const cal = PEARL_GALLERY_CALIBRATION;
        const sx = w / cal.refW;
        const sy = h / cal.refH;
        const px = (x) => Math.round(x * sx);
        const py = (y) => Math.round(y * sy);
        const circle = (c) => ({
            cx: px(c.cx),
            cy: py(c.cy),
            d: px(c.d),
        });
        const t = cal.text;
        return {
            primary: circle(cal.primary),
            secondary: circle(cal.secondary),
            text: {
                left: px(t.x0 + (t.padX || 0)),
                top: py(t.y0 + (t.padY || 0)),
                width: px((t.x1 - t.x0) - (t.padX || 0) - (t.padEndX || 0)),
                height: py((t.y1 - t.y0) - (t.padY || 0) - (t.padEndY || 0)),
            },
            footer: {
                left: px(cal.footer.x0),
                top: py(cal.footer.y0),
                width: px(cal.footer.x1 - cal.footer.x0),
                height: py(cal.footer.y1 - cal.footer.y0),
            },
            badge: { left: px(cal.badge.cx), top: py(cal.badge.cy) },
            logo: { left: px(cal.logo.cx), top: py(cal.logo.cy) },
        };
    }

    function pearlPhotoCircleHtml(url, slot, conf, cropY) {
        const pos = `50% ${cropY}%`;
        if (!url) {
            return sculpturalCircleSlotHtml('', slot.cx, slot.cy, slot.d, conf, 1);
        }
        return `<div style="position:absolute;left:${slot.cx - slot.d / 2}px;top:${slot.cy - slot.d / 2}px;width:${slot.d}px;height:${slot.d}px;border-radius:50%;overflow:hidden;z-index:1;isolation:isolate;background:#0f172a;">
            ${posterImg(url, `width:100%;height:100%;min-width:100%;min-height:100%;object-fit:cover;object-position:${pos};display:block;`, conf)}
        </div>`;
    }

    function pearlDealBadgeHtml(dealLabel) {
        if (!dealLabel) return '';
        return `<div style="display:inline-flex;align-items:center;gap:9px;padding:9px 20px 10px;border-radius:999px;background:linear-gradient(145deg,rgba(245,224,196,.97) 0%,rgba(212,175,130,.92) 48%,rgba(194,154,108,.9) 100%);border:1px solid rgba(255,255,255,.42);box-shadow:0 10px 28px rgba(8,12,24,.42),inset 0 1px 0 rgba(255,255,255,.55);backdrop-filter:blur(6px);${pcsTextStyle('font-size:18px;line-height:1.1;color:#141c28;font-weight:800;letter-spacing:.03em;')}">
            <span aria-hidden="true" style="width:7px;height:7px;border-radius:50%;background:linear-gradient(135deg,#1e293b,#0f172a);opacity:.65;flex-shrink:0;box-shadow:0 0 0 1px rgba(255,255,255,.25);"></span>
            <span>${esc(dealLabel)}</span>
        </div>`;
    }

    function renderPearlGalleryPoster(ctx) {
        const overlay = pearlGalleryOverlayUrl();
        if (!overlay) return renderPearlescentPoster(ctx);

        const {
            layout, conf, primary, stripUrl, cropY, headline, price, locLine,
            primaryColor, brandName, phone, dealLabel, b, p, facts,
        } = ctx;
        const fmt = layout.fmt;
        const w = fmt.w;
        const h = fmt.h;
        const m = pearlLayoutMetrics(w, h);
        const ink = '#f4f1eb';
        const inkMuted = 'rgba(244,241,235,.86)';
        const priceInk = '#e8c9a8';
        const textShadow = 'text-shadow:0 2px 14px rgba(0,0,0,.45);';
        const textW = Math.max(160, m.text.width);
        const headFit = posterHeadlineFit(conf, layout.hlModern, headline, Math.floor(textW * 0.96), 2);
        const hl = headFit.px;
        const headEmph = posterTextEmphasis(conf, 'headline', ink);
        const headBlock = 'max-width:100%;overflow:hidden;word-wrap:break-word;overflow-wrap:anywhere;';
        const headHtml = headFit.lines.slice(0, 2).map((ln) => `<div style="${pcsTextStyle(`${headBlock}font-size:${hl}px;line-height:1.2;letter-spacing:-0.012em;${headEmph}${textShadow}`)}">${esc(ln)}</div>`).join('');
        const metaFacts = facts && typeof facts === 'object'
            ? facts
            : posterContentFacts(p, headline, locLine);
        const metaLine = sculpturalMetaLine(p, metaFacts);
        const metaHtml = metaLine
            ? `<p style="${pcsTextStyle(`${headBlock}margin:12px 0 0;font-size:${Math.round(h * 0.0165)}px;font-weight:600;color:${inkMuted};line-height:1.5;${textShadow}`)}">${esc(metaLine)}</p>`
            : '';
        let priceHtml = '';
        if (price) {
            const px = posterPriceFit(conf, layout, price, Math.floor(textW * 0.94));
            const emph = posterTextEmphasis(conf, 'price', priceInk);
            priceHtml = `<div style="margin-top:14px;width:100%;max-width:100%;overflow:hidden;">
                <span style="${pcsTextStyle(`display:block;font-size:${px}px;line-height:1.12;${emph}${textShadow}`)}">${esc(price)}</span>
            </div>`;
        }
        const textHtml = `<div dir="rtl" style="display:flex;flex-direction:column;align-items:flex-start;justify-content:flex-end;text-align:right;unicode-bidi:plaintext;width:100%;height:100%;max-width:100%;overflow:visible;box-sizing:border-box;padding-bottom:6px;">
            ${wrapPosterTextRole('headline', headHtml, conf)}
            ${wrapPosterTextRole('meta', metaHtml, conf)}
            ${wrapPosterTextRole('price', priceHtml, conf)}
        </div>`;
        const footerInk = '#1e293b';
        const footerMuted = 'rgba(30,41,59,.82)';
        const footerHtml = `
            <div dir="rtl" style="display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;height:100%;padding:0 14px;box-sizing:border-box;overflow:hidden;">
                ${brandName ? `<span style="${pcsTextStyle('flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right;font-size:' + Math.round(h * 0.0155) + 'px;font-weight:700;color:' + footerMuted + ';')}">${esc(brandName)}</span>` : '<span style="flex:1;"></span>'}
                ${phone ? `<span dir="ltr" style="${pcsTextStyle('flex-shrink:0;max-width:58%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:' + Math.round(h * 0.023) + 'px;font-weight:900;color:' + footerInk + ';letter-spacing:.02em;')}">${esc(phone)}</span>` : ''}
            </div>`;
        const logoSize = layout.isStory ? (PEARL_GALLERY_CALIBRATION.logo.size || 50) : 44;
        const mainUrl = primary || stripUrl;
        const accentUrl = stripUrl || primary;

        return `
            <div class="pcs-pearl-frame" style="position:absolute;inset:0;background:#0b1220;overflow:hidden;">
                ${pearlPhotoCircleHtml(mainUrl, m.primary, conf, cropY)}
                ${pearlPhotoCircleHtml(accentUrl, m.secondary, conf, cropY)}
                <img class="pcs-pearlescent-frame__overlay" src="${esc(overlay)}" alt="" decoding="async" crossorigin="anonymous" referrerpolicy="no-referrer" style="position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none;z-index:2;">
                <div style="position:absolute;left:${m.text.left}px;top:${m.text.top}px;width:${m.text.width}px;height:${m.text.height}px;z-index:3;display:flex;align-items:flex-start;justify-content:flex-start;overflow:visible;">
                    ${textHtml}
                </div>
                <div style="position:absolute;left:${m.badge.left}px;top:${m.badge.top}px;z-index:4;transform:translate(-100%,0);transform-origin:top right;">${pearlDealBadgeHtml(dealLabel)}</div>
                <div style="position:absolute;left:${m.logo.left}px;top:${m.logo.top}px;z-index:4;transform:translate(-50%,-50%);">${brandLogoBlock(b, logoSize)}</div>
                <div style="position:absolute;left:${m.footer.left}px;top:${m.footer.top}px;width:${m.footer.width}px;height:${m.footer.height}px;z-index:3;display:flex;align-items:center;pointer-events:none;">
                    ${footerHtml}
                </div>
            </div>`;
    }

    function renderPosterTemplate(templateId, ctx) {
        if (templateId === 'luxury') return renderLuxuryPoster(ctx);
        if (templateId === 'minimal') return renderModernPoster(ctx);
        if (templateId === 'gallery') return renderCollagePoster(ctx);
        if (templateId === 'pearlescent') return renderPearlescentPoster(ctx);
        if (templateId === 'sculptural') return renderSculpturalPoster(ctx);
        if (templateId === 'emerald_atelier') return renderEmeraldAtelierPoster(ctx);
        if (templateId === 'pearl_gallery') return renderPearlGalleryPoster(ctx);
        return renderCampaignPoster(ctx);
    }

    function editorTypeStylePreviewCss(conf, role, fallbackColor) {
        const isHeadline = role === 'headline';
        const previewConf = {
            headline_weight: conf.headline_weight,
            price_weight: conf.price_weight,
            headline_italic: conf.headline_italic,
            price_italic: conf.price_italic,
            headline_underline: conf.headline_underline,
            price_underline: conf.price_underline,
            headline_color: conf.headline_color,
            price_color: conf.price_color,
        };
        return posterTextEmphasis(previewConf, isHeadline ? 'headline' : 'price', fallbackColor);
    }

    function editorTypeWeightSegment(role, weight) {
        const prefix = role === 'headline' ? 'pcs-headline' : 'pcs-price';
        const labels = { 500: 'معمولی', 700: 'پررنگ', 900: 'بولد' };
        return [500, 700, 900].map((w) => `
            <button type="button" class="pcs-type-segment__btn${weight === w ? ' is-active' : ''}"
                data-${prefix}-weight="${w}" aria-pressed="${weight === w ? 'true' : 'false'}">${labels[w]}</button>`).join('');
    }

    function editorTypeColorPresets(role, conf, presets, fallbackColor) {
        const custom = normalizePosterHexColor(role === 'headline' ? conf.headline_color : conf.price_color);
        const auto = !custom;
        const current = custom || fallbackColor;
        const presetBtns = presets.map((hex) => `
            <button type="button" class="pcs-type-swatch${!auto && current === hex ? ' is-active' : ''}"
                data-pcs-edit-color-preset="${role}" data-color="${hex}"
                style="--pcs-swatch:${hex};" title="${hex}" aria-label="رنگ ${hex}"></button>`).join('');
        return `
            <div class="pcs-type-colors" data-pcs-type-colors="${role}">
                <button type="button" class="pcs-type-swatch pcs-type-swatch--auto${auto ? ' is-active' : ''}"
                    data-pcs-edit-color-auto="${role}" title="رنگ پیش‌فرض قالب">
                    <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>
                    <span>خودکار</span>
                </button>
                ${presetBtns}
                <label class="pcs-type-swatch pcs-type-swatch--picker" title="رنگ دلخواه">
                    <input type="color" class="pcs-editor__color-swatch" data-pcs-edit-color="${role}" value="${esc(current)}" aria-label="رنگ ${role === 'headline' ? 'عنوان' : 'قیمت'}">
                    <i class="fas fa-eyedropper" aria-hidden="true"></i>
                </label>
            </div>`;
    }

    function editorTypeStylePanel(role, conf, active) {
        const isHeadline = role === 'headline';
        const c = conf || {};
        const weight = normalizePosterTextWeight(isHeadline ? c.headline_weight : c.price_weight, 900);
        const italic = !!(isHeadline ? c.headline_italic : c.price_italic);
        const underline = !!(isHeadline ? c.headline_underline : c.price_underline);
        const prefix = isHeadline ? 'pcs-headline' : 'pcs-price';
        const title = isHeadline ? 'عنوان' : 'قیمت';
        const sample = isHeadline ? 'آپارتمان نورگیر' : '۱۲ میلیارد تومان';
        const fallbackColor = isHeadline ? '#0f172a' : '#7c3aed';
        const previewBg = isHeadline ? 'linear-gradient(135deg,#f8fafc,#eef2ff)' : 'linear-gradient(135deg,#faf5ff,#f5f3ff)';
        const presets = isHeadline
            ? ['#0f172a', '#1e293b', '#7c3aed', '#b45309']
            : ['#7c3aed', '#5b21b6', '#0f172a', '#ea580c'];
        const previewCss = editorTypeStylePreviewCss(c, role, fallbackColor);
        const fontKey = c.font_key || 'vazirmatn';
        const family = (PCS_FONTS[fontKey] || PCS_FONTS.vazirmatn).family;
        const tabId = `pcs-type-tab-${role}`;
        return `
            <article class="pcs-type-panel${active ? ' is-active' : ''}" data-pcs-type-panel="${role}"
                id="pcs-type-panel-${role}" role="tabpanel" aria-labelledby="${tabId}"${active ? '' : ' hidden'}>
                <div class="pcs-type-panel__preview" style="background:${previewBg};">
                    <span class="pcs-type-panel__sample" style="font-family:${family};${previewCss}">${esc(sample)}</span>
                </div>
                <div class="pcs-type-panel__field">
                    <span class="pcs-type-panel__label">وزن فونت</span>
                    <div class="pcs-type-segment" role="group" aria-label="وزن ${title}">
                        ${editorTypeWeightSegment(role, weight)}
                    </div>
                </div>
                <div class="pcs-type-panel__footer">
                    <div class="pcs-type-panel__field pcs-type-panel__field--inline">
                        <span class="pcs-type-panel__label">افکت</span>
                        <div class="pcs-type-toggles">
                            <button type="button" class="pcs-type-toggle${italic ? ' is-active' : ''}" data-${prefix}-italic
                                aria-pressed="${italic ? 'true' : 'false'}" title="مورب">
                                <i class="fas fa-italic" aria-hidden="true"></i>
                            </button>
                            <button type="button" class="pcs-type-toggle${underline ? ' is-active' : ''}" data-${prefix}-underline
                                aria-pressed="${underline ? 'true' : 'false'}" title="خط زیر">
                                <i class="fas fa-underline" aria-hidden="true"></i>
                            </button>
                        </div>
                    </div>
                    <div class="pcs-type-panel__field pcs-type-panel__field--colors">
                        <span class="pcs-type-panel__label">رنگ</span>
                        ${editorTypeColorPresets(role, c, presets, fallbackColor)}
                    </div>
                </div>
            </article>`;
    }

    function editorMetaStylePanel(conf, active) {
        const c = conf || {};
        const s = Math.round(textLayoutEntry(c, 'meta').s);
        return `
            <article class="pcs-type-panel${active ? ' is-active' : ''}" data-pcs-type-panel="meta"
                id="pcs-type-panel-meta" role="tabpanel" aria-labelledby="pcs-type-tab-meta"${active ? '' : ' hidden'}>
                <p class="pcs-editor__section-hint">اندازه خط مشخصات (متراژ، محله، …) — جدا از عنوان و قیمت</p>
                <label class="pcs-editor__range-label">اندازه مشخصات <span data-pcs-meta-scale-val>${s}%</span></label>
                <input type="range" class="pcs-editor__range" data-pcs-edit-meta-scale min="50" max="180" value="${s}">
            </article>`;
    }

    function editorTextStyleControls(conf) {
        return `<div class="pcs-type-studio" data-pcs-type-studio>
            <div class="pcs-type-studio__tabs" role="tablist" aria-label="استایل متن پوستر">
                <button type="button" role="tab" class="pcs-type-studio__tab is-active" id="pcs-type-tab-headline"
                    data-pcs-type-tab="headline" aria-selected="true" aria-controls="pcs-type-panel-headline">
                    <i class="fas fa-heading" aria-hidden="true"></i><span>عنوان</span>
                </button>
                <button type="button" role="tab" class="pcs-type-studio__tab" id="pcs-type-tab-meta"
                    data-pcs-type-tab="meta" aria-selected="false" aria-controls="pcs-type-panel-meta">
                    <i class="fas fa-list-ul" aria-hidden="true"></i><span>مشخصات</span>
                </button>
                <button type="button" role="tab" class="pcs-type-studio__tab" id="pcs-type-tab-price"
                    data-pcs-type-tab="price" aria-selected="false" aria-controls="pcs-type-panel-price">
                    <i class="fas fa-tag" aria-hidden="true"></i><span>قیمت</span>
                </button>
            </div>
            ${editorTypeStylePanel('headline', conf, true)}
            ${editorMetaStylePanel(conf, false)}
            ${editorTypeStylePanel('price', conf, false)}
        </div>`;
    }

    function syncTypeStylePreview(conf) {
        const controls = editorControlsEl();
        if (!controls || !conf) return;
        ['headline', 'price'].forEach((role) => {
            const card = controls.querySelector(`[data-pcs-type-panel="${role}"]`);
            const sample = card?.querySelector('.pcs-type-panel__sample');
            if (!sample) return;
            const fallback = role === 'headline' ? '#0f172a' : '#7c3aed';
            const family = pcsFontFamily(conf);
            sample.style.fontFamily = family;
            const emph = editorTypeStylePreviewCss(conf, role, fallback);
            sample.style.cssText = `font-family:${family};${emph}`;
        });
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

    function isMagazineComposition(conf) {
        return !!conf?.pip_enabled && conf.pip_shape === 'card' && conf.pip_size === 'l';
    }

    function posterMagazineHeroBlend() {
        return `<div style="position:absolute;inset:0;z-index:5;pointer-events:none;background:linear-gradient(180deg,transparent 28%,rgba(15,23,42,.22) 58%,rgba(15,23,42,.72) 100%);"></div>
            <div style="position:absolute;inset:0;z-index:5;pointer-events:none;background:linear-gradient(90deg,rgba(0,0,0,.42) 0%,transparent 38%);"></div>`;
    }

    function posterPipClassicHtml(conf, url, primaryColor, accentInk) {
        const sizePct = { s: 22, m: 30, l: 34 }[conf.pip_size] || 30;
        const corners = {
            br: 'bottom:14%;right:5%;',
            bl: 'bottom:14%;left:5%;',
            tr: 'top:12%;right:5%;',
            tl: 'top:12%;left:5%;',
        };
        const pos = corners[conf.pip_corner] || corners.br;
        const shape = conf.pip_shape || 'rounded';
        const radius = shape === 'circle' ? '50%' : '18px';
        const aspect = shape === 'circle' ? '1/1' : '5/4';
        const crop = conf.pip_crop_y ?? 50;
        const tilt = conf.pip_tilt ?? 0;
        const rim = conf.pip_border === 'gold'
            ? 'linear-gradient(135deg,#f5e6a8 0%,#d4af37 48%,#b8860b 100%)'
            : conf.pip_border === 'brand'
                ? `linear-gradient(135deg,${primaryRgba(primaryColor, 0.95)} 0%,${primaryRgba(accentInk || primaryColor, 0.85)} 100%)`
                : 'linear-gradient(145deg,rgba(255,255,255,.98) 0%,rgba(255,255,255,.72) 100%)';
        const innerRadius = shape === 'circle' ? '50%' : '14px';
        return `<div style="position:absolute;${pos}z-index:9;width:${sizePct}%;max-width:300px;aspect-ratio:${aspect};transform:rotate(${tilt}deg);filter:drop-shadow(0 28px 48px rgba(0,0,0,.55)) drop-shadow(0 8px 18px rgba(0,0,0,.35));">
            <div style="position:absolute;inset:-18%;background:radial-gradient(ellipse at 50% 80%,rgba(0,0,0,.45),transparent 68%);opacity:.65;z-index:0;"></div>
            <div style="position:relative;z-index:1;padding:4px;border-radius:${radius};background:${rim};box-shadow:0 0 0 1px rgba(255,255,255,.35) inset;">
                <div style="position:relative;border-radius:${innerRadius};overflow:hidden;background:#0f172a;aspect-ratio:${aspect};">
                    ${posterImg(url, `width:100%;height:100%;object-fit:cover;object-position:center ${crop}%;display:block;`, conf)}
                    <div style="position:absolute;inset:0;pointer-events:none;background:linear-gradient(145deg,rgba(255,255,255,.18) 0%,transparent 42%,rgba(0,0,0,.12) 100%);"></div>
                </div>
            </div>
            <div style="position:absolute;top:10%;right:8%;width:10px;height:10px;border-radius:50%;background:${primaryColor};box-shadow:0 0 12px ${primaryRgba(primaryColor, 0.9)};z-index:2;opacity:.85;"></div>
        </div>`;
    }

    function posterPipMagazineHtml(conf, url, primaryColor, accentInk, placement) {
        const crop = conf.pip_crop_y ?? 50;
        const tilt = conf.pip_tilt ?? 0;
        const ink = accentInk || primaryColor;
        const idx = (parseInt(conf.pip_image_index, 10) || 0) + 1;
        const layout = placement === 'luxury_overlay'
            ? 'bottom:188px;left:44px;width:min(44%,400px);'
            : placement === 'minimal_hero'
                ? 'bottom:28px;left:26px;width:min(46%,360px);'
                : 'bottom:12%;left:6%;width:min(44%,380px);';
        const backTilt = tilt - 3;
        return `<div style="position:absolute;${layout}z-index:11;transform:rotate(${tilt}deg);filter:drop-shadow(0 36px 70px rgba(0,0,0,.5));">
            <div style="position:absolute;inset:10px -14px -14px 14px;border-radius:14px;border:2px solid rgba(255,255,255,.28);transform:rotate(${backTilt}deg);opacity:.55;z-index:0;"></div>
            <div style="position:relative;z-index:1;background:#fff;padding:14px 14px 52px;border-radius:12px;box-shadow:0 0 0 1px rgba(15,23,42,.08),0 24px 56px rgba(0,0,0,.38);">
                <div style="position:absolute;top:0;left:14px;right:14px;height:4px;border-radius:0 0 4px 4px;background:linear-gradient(90deg,${ink},${primaryRgba(ink, 0.45)});"></div>
                <div style="position:relative;aspect-ratio:4/5;border-radius:6px;overflow:hidden;background:#0f172a;">
                    ${posterImg(url, `width:100%;height:100%;object-fit:cover;object-position:center ${crop}%;display:block;`, conf)}
                    <div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 55%,rgba(0,0,0,.35) 100%);pointer-events:none;"></div>
                </div>
                <div style="position:absolute;left:18px;right:18px;bottom:16px;display:flex;align-items:center;justify-content:space-between;gap:10px;">
                    <span style="${pcsTextStyle('font-size:15px;font-weight:800;color:#64748b;letter-spacing:.04em;')}">نمای تکمیلی</span>
                    <span style="display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:28px;padding:0 10px;border-radius:8px;background:${primaryRgba(ink, 0.12)};${pcsTextStyle(`font-size:14px;font-weight:800;color:${ink};`)}">${idx}</span>
                </div>
            </div>
        </div>`;
    }

    function posterPipInset(conf, primaryColor, accentInk, placement = 'inline') {
        if (!conf.pip_enabled) return '';
        const url = pipImageUrl(conf);
        if (!url) return '';
        const magazine = isMagazineComposition(conf);
        if (magazine) {
            if (placement === 'luxury_hero') return posterMagazineHeroBlend();
            if (placement === 'luxury_overlay') {
                return posterPipMagazineHtml(conf, url, primaryColor, accentInk, 'luxury_overlay');
            }
            const scope = placement === 'minimal_hero' ? 'minimal_hero' : 'inline';
            return `${posterMagazineHeroBlend()}${posterPipMagazineHtml(conf, url, primaryColor, accentInk, scope)}`;
        }
        if (placement === 'luxury_overlay' || placement === 'luxury_hero') {
            if (placement === 'luxury_overlay') return '';
            return posterPipClassicHtml(conf, url, primaryColor, accentInk);
        }
        return posterPipClassicHtml(conf, url, primaryColor, accentInk);
    }

    function editorOptionChips(attr, options, activeValue) {
        return `<div class="pcs-editor__chip-row" role="group">${options.map(([val, label]) => `
            <button type="button" class="pcs-editor__chip${val === activeValue ? ' is-active' : ''}" data-${attr}="${val}">${esc(label)}</button>`).join('')}
        </div>`;
    }

    const COMPOSITION_UI = [
        { key: 'pip_classic', icon: 'fa-clone', label: 'عکس در عکس', sub: 'قاب شیشه‌ای شناور' },
        { key: 'magazine', icon: 'fa-book-open', label: 'مجله‌ای', sub: 'کارت تحریریه' },
        { key: 'cinematic', icon: 'fa-film', label: 'سینمایی', sub: 'عمق و کنتراست' },
        { key: 'clean', icon: 'fa-sun', label: 'خالص', sub: 'مینیمال' },
    ];

    function guessCompositionKey(conf) {
        if (!conf) return 'clean';
        if (!conf.pip_enabled && (conf.hero_vignette ?? 0) <= 4 && (conf.hero_warmth || 'neutral') === 'neutral') {
            return 'clean';
        }
        if (!conf.pip_enabled && (conf.hero_vignette ?? 0) >= 40) return 'cinematic';
        if (conf.pip_enabled && conf.pip_shape === 'card' && conf.pip_size === 'l') return 'magazine';
        if (conf.pip_enabled) return 'pip_classic';
        return 'clean';
    }

    function syncCompositionActiveCard(key) {
        const controls = editorControlsEl();
        if (!controls) return;
        controls.querySelectorAll('[data-pcs-composition]').forEach((btn) => {
            const on = btn.getAttribute('data-pcs-composition') === key;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
        });
    }

    function syncPipTuneVisibility(pipOn) {
        const tune = editorControlsEl()?.querySelector('[data-pcs-pip-tune]');
        if (!tune) return;
        tune.classList.toggle('is-collapsed', !pipOn);
        tune.setAttribute('aria-hidden', pipOn ? 'false' : 'true');
    }

    function editorComposeSection(imgs, conf) {
        const activeKey = guessCompositionKey(conf);
        state.editorCompositionKey = activeKey;
        const pipOn = !!conf.pip_enabled;
        const pipIdx = conf.pip_image_index ?? 1;
        const pipBlock = imgs.length < 2
            ? '<p class="pcs-editor__compose-note">برای لایه دوم حداقل دو تصویر در فایل لازم است.</p>'
            : `<div class="pcs-editor__pip-tune${pipOn ? '' : ' is-collapsed'}" data-pcs-pip-tune aria-hidden="${pipOn ? 'false' : 'true'}">
                <div class="pcs-editor__pip-tune-grid">
                    <div class="pcs-editor__pip-tune-field">
                        <span class="pcs-editor__mini-label">تصویر لایه دوم</span>
                        ${editorPipImagePicker(imgs, pipIdx)}
                    </div>
                    <div class="pcs-editor__pip-tune-field">
                        <span class="pcs-editor__mini-label">جایگاه</span>
                        ${editorOptionChips('pcs-pip-corner', [['br', 'پایین راست'], ['bl', 'پایین چپ'], ['tr', 'بالا راست'], ['tl', 'بالا چپ']], conf.pip_corner || 'br')}
                    </div>
                </div>
                <div class="pcs-editor__pip-tune-grid">
                    <div class="pcs-editor__pip-tune-field">
                        <span class="pcs-editor__mini-label">اندازه</span>
                        ${editorOptionChips('pcs-pip-size', [['s', 'ک'], ['m', 'م'], ['l', 'ب']], conf.pip_size || 'm')}
                    </div>
                    <div class="pcs-editor__pip-tune-field">
                        <span class="pcs-editor__mini-label">شکل</span>
                        ${editorOptionChips('pcs-pip-shape', [['rounded', 'گرد'], ['circle', 'دایره'], ['card', 'کارت']], conf.pip_shape || 'rounded')}
                    </div>
                </div>
                <label class="pcs-editor__range-label">چرخش لایه <span data-pcs-range-val="pip_tilt">${conf.pip_tilt ?? 0}°</span></label>
                <input type="range" class="pcs-editor__range" data-pcs-edit-range="pip_tilt" min="-10" max="10" value="${conf.pip_tilt ?? 0}">
            </div>`;

        return `<section class="pcs-editor__section pcs-editor__section--compose">
            <div class="pcs-editor__compose-head">
                <h4 class="pcs-editor__section-title"><i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i> ترکیب حرفه‌ای</h4>
                <p class="pcs-editor__section-hint">یک استایل انتخاب کنید — عکس در عکس با همان کارت فعال می‌شود، بدون سوئیچ جداگانه</p>
            </div>
            <input type="hidden" id="pcsEditPipEnabled" value="${pipOn ? '1' : '0'}">
            <input type="hidden" id="pcsEditPipImage" value="${pipIdx}">
            <div class="pcs-editor__style-grid" role="listbox" aria-label="استایل ترکیب">
                ${COMPOSITION_UI.map((item) => `
                <button type="button" class="pcs-editor__style-card${activeKey === item.key ? ' is-active' : ''}"
                    data-pcs-composition="${item.key}" role="option" aria-selected="${activeKey === item.key ? 'true' : 'false'}">
                    <span class="pcs-editor__style-card-icon" aria-hidden="true"><i class="fas ${item.icon}"></i></span>
                    <span class="pcs-editor__style-card-text">
                        <strong>${esc(item.label)}</strong>
                        <small>${esc(item.sub)}</small>
                    </span>
                </button>`).join('')}
            </div>
            <details class="pcs-editor__compose-fine">
                <summary class="pcs-editor__compose-fine-summary">تنظیم ظریف لایه و نور</summary>
                <div class="pcs-editor__compose-fine-body">
                    ${pipBlock}
                    <div class="pcs-editor__compose-mood">
                        <span class="pcs-editor__mini-label">دمای تصویر</span>
                        ${editorOptionChips('pcs-hero-warmth', [['neutral', 'خنثی'], ['warm', 'گرم'], ['cool', 'سرد']], conf.hero_warmth || 'neutral')}
                        <label class="pcs-editor__range-label">وینیت <span data-pcs-range-val="hero_vignette">${conf.hero_vignette ?? 0}%</span></label>
                        <input type="range" class="pcs-editor__range" data-pcs-edit-range="hero_vignette" min="0" max="80" value="${conf.hero_vignette ?? 0}">
                    </div>
                </div>
            </details>
        </section>`;
    }

    function syncCompositionFormFromBuffer(conf) {
        const controls = editorControlsEl();
        if (!controls || !conf) return;
        const pipEnabledHidden = controls.querySelector('#pcsEditPipEnabled');
        if (pipEnabledHidden) pipEnabledHidden.value = conf.pip_enabled ? '1' : '0';
        syncPipTuneVisibility(!!conf.pip_enabled);
        const pipHidden = controls.querySelector('#pcsEditPipImage');
        if (pipHidden) pipHidden.value = String(conf.pip_image_index ?? 1);
        syncCompositionActiveCard(guessCompositionKey(conf));
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
        const pipSelect = controls.querySelector('[data-pcs-pip-image-select]');
        if (pipSelect) pipSelect.value = String(pipIdx);
    }

    function applyCompositionPreset(key) {
        const preset = COMPOSITION_PRESETS[key];
        if (!preset || !state.editorBuffer) return;
        state.editorCompositionKey = key;
        Object.assign(state.editorBuffer, preset);
        if (state.editorBuffer.pip_enabled && propertyImageList().length > 1) {
            const p = state.editorBuffer.primary_image_index || 0;
            state.editorBuffer.pip_image_index = (p + 1) % propertyImageList().length;
        }
        syncCompositionFormFromBuffer(state.editorBuffer);
        refreshEditorPreview(state.editorTemplate);
    }

    function buildCanvasHtml(templateId, formatKey, confOverride, renderOpts) {
        const fmt = FORMATS[formatKey] || FORMATS.story;
        const opts = renderOpts || {};
        const { property: p, brand: b } = visibleData();
        const conf = confOverride
            ? normalizePosterConfig(confOverride, propertyImageList())
            : posterConfig(templateId);
        const imgs = orderedImages(templateId, confOverride ? conf : null);
        if (opts.primaryImageIndex != null) {
            conf.primary_image_index = opts.primaryImageIndex;
        }
        const primary = opts.heroImageUrl || primaryImageUrl(conf);
        const cropY = conf.crop_y ?? 50;
        const headline = (opts.headlineOverride || visibleHeadline(conf) || '').trim();
        let price = p.price?.show ? p.price.label : '';
        if (opts.suppressPrice) {
            price = '';
        } else if (opts.priceLabel !== undefined) {
            price = opts.priceLabel || '';
        }
        const locLine = opts.locationOverride !== undefined ? opts.locationOverride : (p.location_line || p.city || '');
        const primaryColor = normalizeBrandColor(
            conf.brand_primary || b.colors?.primary || '#7c3aed',
        );
        const accentInk = inkAccentOnWhite(primaryColor);
        const badgeInk = textOnColor(primaryColor);
        const brandName = b.visibility?.consultant_name !== false ? (b.consultant_name || b.brand_name || '') : '';
        const phone = b.visibility?.contact_phone !== false ? (b.contact_phone || '') : '';
        const dealLabel = p.deal_mode === 'فروش' ? 'فروش' : (p.deal_mode || 'آگهی');
        const renderCtx = buildPosterRenderCtx(templateId, formatKey, conf, p, b, imgs, {
            primary,
            headline,
            price,
            locLine,
            primaryColor,
            accentInk,
            brandName,
            phone,
            dealLabel,
            primaryImageIndex: opts.primaryImageIndex,
            circleImageIndices: opts.circleImageIndices,
            stripImageIndex: opts.stripImageIndex,
        });
        const inner = withPosterRenderConf(conf, () => renderPosterTemplate(templateId, renderCtx));

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
        const viewport = $('#pcsEditorPreviewViewport') || wrap?.closest?.('.pcs-editor__preview-viewport');
        const stage = wrap?.closest?.('.pcs-editor__preview-stage');
        if (!viewport && !stage) return null;
        const pad = 12;
        const host = viewport || stage;
        return {
            width: Math.max(180, host.clientWidth - pad),
            height: Math.max(220, host.clientHeight - pad),
        };
    }

    const EDITOR_PREVIEW_ZOOM_MIN = 0.55;
    const EDITOR_PREVIEW_ZOOM_MAX = 2.4;
    const EDITOR_PREVIEW_ZOOM_STEP = 0.12;

    function resetEditorPreviewView() {
        state.editorPreviewView = { zoom: 1, panX: 0, panY: 0 };
        applyEditorPreviewViewTransform();
    }

    function clampEditorPreviewZoom(z) {
        return Math.min(EDITOR_PREVIEW_ZOOM_MAX, Math.max(EDITOR_PREVIEW_ZOOM_MIN, z));
    }

    function setEditorPreviewZoom(nextZoom) {
        state.editorPreviewView.zoom = clampEditorPreviewZoom(nextZoom);
        applyEditorPreviewViewTransform();
        const wrap = $('#pcsEditorPreview');
        if (wrap && wrap._pcsLastVisual) {
            updateEditorPreviewScrollSize(wrap._pcsLastVisual.w, wrap._pcsLastVisual.h);
        }
    }

    function updateEditorPreviewScrollSize(visualW, visualH) {
        const wrap = $('#pcsEditorPreview');
        if (!wrap) return;
        const z = state.editorPreviewView.zoom;
        const pad = 28;
        wrap.style.minWidth = `${Math.round(visualW * z) + pad}px`;
        wrap.style.minHeight = `${Math.round(visualH * z) + pad}px`;
    }

    function applyEditorPreviewViewTransform() {
        const wrap = $('#pcsEditorPreview');
        const scaler = wrap ? $('.pcs-preview-scaler', wrap) : null;
        const { zoom, panX, panY } = state.editorPreviewView;
        if (scaler) {
            scaler.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
            scaler.style.transformOrigin = 'top center';
        }
        if (wrap?._pcsLastVisual) {
            updateEditorPreviewScrollSize(wrap._pcsLastVisual.w, wrap._pcsLastVisual.h);
        }
        const label = $('#pcsEditorPreviewZoomLabel');
        if (label) label.textContent = `${Math.round(zoom * 100)}٪`;
        const viewport = $('#pcsEditorPreviewViewport');
        viewport?.classList.toggle('is-zoomed', zoom > 1.02 || Math.abs(panX) > 2 || Math.abs(panY) > 2);
    }

    function bindEditorPreviewZoomControls() {
        const editor = $('#pcsEditor');
        if (!editor || editor.dataset.pcsZoomControlsBound === '1') return;
        editor.dataset.pcsZoomControlsBound = '1';
        editor.addEventListener('click', (e) => {
            const zoomIn = e.target.closest('[data-pcs-preview-zoom-in]');
            const zoomOut = e.target.closest('[data-pcs-preview-zoom-out]');
            const zoomReset = e.target.closest('[data-pcs-preview-zoom-reset]');
            const textLayoutReset = e.target.closest('[data-pcs-text-layout-reset]');
            if (!zoomIn && !zoomOut && !zoomReset && !textLayoutReset) return;
            e.preventDefault();
            e.stopPropagation();
            if (textLayoutReset) {
                resetEditorTextLayout();
            } else if (zoomIn) {
                setEditorPreviewZoom(state.editorPreviewView.zoom + EDITOR_PREVIEW_ZOOM_STEP);
            } else if (zoomOut) {
                setEditorPreviewZoom(state.editorPreviewView.zoom - EDITOR_PREVIEW_ZOOM_STEP);
            } else {
                resetEditorPreviewView();
            }
        });
        bindEditorTransformBar();
    }

    function bindEditorPreviewViewEvents() {
        if (state.editorPreviewViewBound) return;
        const viewport = $('#pcsEditorPreviewViewport');
        if (!viewport) return;
        state.editorPreviewViewBound = true;

        viewport.addEventListener('wheel', (e) => {
            if (!$('#pcsEditor')?.hasAttribute('hidden')) {
                e.preventDefault();
                const delta = e.deltaY > 0 ? -EDITOR_PREVIEW_ZOOM_STEP : EDITOR_PREVIEW_ZOOM_STEP;
                setEditorPreviewZoom(state.editorPreviewView.zoom + delta);
            }
        }, { passive: false });

        let panning = false;
        let panStartX = 0;
        let panStartY = 0;
        let panOriginX = 0;
        let panOriginY = 0;

        const endPan = () => {
            panning = false;
            viewport.classList.remove('is-panning');
        };

        viewport.addEventListener('mousedown', (e) => {
            if (e.button !== 0 || e.target.closest('button, a, input, select, textarea')) return;
            if (e.target.closest('[data-pcs-text-role], [data-pcs-text-resize]')) return;
            panning = true;
            panStartX = e.clientX;
            panStartY = e.clientY;
            panOriginX = state.editorPreviewView.panX;
            panOriginY = state.editorPreviewView.panY;
            viewport.classList.add('is-panning');
            e.preventDefault();
        });

        window.addEventListener('mousemove', (e) => {
            if (!panning) return;
            state.editorPreviewView.panX = panOriginX + (e.clientX - panStartX);
            state.editorPreviewView.panY = panOriginY + (e.clientY - panStartY);
            applyEditorPreviewViewTransform();
        });

        window.addEventListener('mouseup', endPan);
        viewport.addEventListener('mouseleave', endPan);

        let touchId = null;
        let touchStartX = 0;
        let touchStartY = 0;
        viewport.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 1) return;
            const t = e.touches[0];
            touchId = t.identifier;
            touchStartX = t.clientX;
            touchStartY = t.clientY;
            panOriginX = state.editorPreviewView.panX;
            panOriginY = state.editorPreviewView.panY;
        }, { passive: true });
        viewport.addEventListener('touchmove', (e) => {
            const t = [...e.touches].find((x) => x.identifier === touchId);
            if (!t) return;
            state.editorPreviewView.panX = panOriginX + (t.clientX - touchStartX);
            state.editorPreviewView.panY = panOriginY + (t.clientY - touchStartY);
            applyEditorPreviewViewTransform();
        }, { passive: true });
        viewport.addEventListener('touchend', () => { touchId = null; });
    }

    function previewMaxHeight(formatKey, wrap) {
        if (wrap?.id === 'pcsEditorPreview') {
            const b = editorPreviewBounds(wrap);
            return b ? b.height : Math.min(window.innerHeight * 0.64, 640);
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
        if (isEditorPreview && !editorPreviewPaneVisible()) {
            previewScaleAttempts.delete(wrap);
            return;
        }
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

        if (isEditorPreview) {
            wrap.style.overflow = 'visible';
            wrap.style.width = 'max-content';
            wrap.style.maxWidth = 'none';
            wrap.style.maxHeight = 'none';
            wrap.style.height = 'auto';
            wrap.style.display = 'block';
            wrap.style.margin = '0 auto';
            wrap.style.padding = '10px 12px';
            wrap.style.boxSizing = 'border-box';
        } else {
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
        if (isEditorPreview) {
            wrap._pcsLastVisual = { w: visualW, h: visualH };
            updateEditorPreviewScrollSize(visualW, visualH);
            applyEditorPreviewViewTransform();
            setupEditorTextInteraction(wrap);
        }
        wrap.classList.add('is-ready');
    }

    function editorPreviewPaneVisible() {
        const pane = $('#pcsEditorPreview')?.closest('.pcs-editor__preview-pane');
        if (!pane) return true;
        if (!isMobileViewport()) return true;
        return pane.classList.contains('is-active');
    }

    function whenImagesReady(wrap, cb, timeoutMs) {
        const limit = timeoutMs ?? 5000;
        let settled = false;
        const done = () => {
            if (settled) return;
            settled = true;
            cb();
        };
        const timer = setTimeout(done, limit);
        const finish = () => {
            clearTimeout(timer);
            done();
        };
        const imgs = wrap ? wrap.querySelectorAll('img') : [];
        if (!imgs.length) {
            finish();
            return;
        }
        let pending = 0;
        imgs.forEach((img) => {
            if (img.complete) return;
            pending += 1;
            const onEnd = () => {
                pending -= 1;
                if (pending <= 0) finish();
            };
            img.addEventListener('load', onEnd, { once: true });
            img.addEventListener('error', onEnd, { once: true });
        });
        if (pending === 0) finish();
    }

    function scheduleEditorPreviewScale(wrap, formatKey) {
        if (!wrap || wrap.id !== 'pcsEditorPreview') return;
        const viewport = $('#pcsEditorPreviewViewport');
        const maxH = previewMaxHeight(formatKey, wrap) || 640;
        if (viewport) {
            viewport.style.maxHeight = `${Math.min(maxH + 8, Math.round(window.innerHeight * 0.68))}px`;
            viewport.style.minHeight = 'min(50vh, 480px)';
        }
        const run = () => scalePreviewCanvas(wrap, formatKey);
        const runAfterLayout = () => {
            requestAnimationFrame(() => {
                requestAnimationFrame(run);
            });
        };
        runAfterLayout();
        whenImagesReady(wrap, runAfterLayout);
        clearTimeout(wrap._pcsScaleFallbackTimer);
        wrap._pcsScaleFallbackTimer = setTimeout(() => {
            scalePreviewCanvas(wrap, formatKey);
            wrap.classList.add('is-ready');
        }, 350);
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
        const verify = await verifyImagesForExport(canvas);
        if (!verify.ok) {
            throw new Error(verify.message || 'تصویر آماده export نیست');
        }
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
                sanitizePosterTextForExport(cloned);
            },
        });
    }

    async function rasterCanvasToBlob(canvasEl) {
        const webp = await new Promise((resolve) => {
            canvasEl.toBlob((b) => resolve(b), PCS_EXPORT_IMAGE_TYPE, PCS_EXPORT_IMAGE_QUALITY);
        });
        if (webp && webp.size > 0) {
            return { blob: webp, ext: PCS_EXPORT_EXT };
        }
        const png = await new Promise((resolve) => {
            canvasEl.toBlob((b) => resolve(b), 'image/png');
        });
        return { blob: png, ext: 'png' };
    }

    async function exportCanvasElement(canvas, filename, formatKey) {
        const shot = await rasterizeCanvas(canvas, formatKey || state.format);
        const { blob, ext } = await rasterCanvasToBlob(shot);
        if (!blob) throw new Error('empty blob');
        const base = String(filename || 'poster').replace(/\.(png|jpe?g|webp)$/i, '');
        const link = document.createElement('a');
        link.download = `${base}.${ext}`;
        const objUrl = URL.createObjectURL(blob);
        link.href = objUrl;
        link.click();
        URL.revokeObjectURL(objUrl);
    }

    function renderPosters() {
        const grid = $('#pcsPosterGrid');
        if (!grid) return;
        grid.innerHTML = '';
        posterTemplatesForSession().forEach((tpl) => {
            const meta = resolveTemplateMeta(tpl);
            const card = document.createElement('article');
            card.className = `pcs-poster-card pcs-poster-card--${tpl}`;
            const head = document.createElement('div');
            head.className = 'pcs-poster-card__head';
            head.innerHTML = `<span class="pcs-poster-card__badge"><i class="fas ${meta.icon}" aria-hidden="true"></i> ${esc(posterDisplayLabel(tpl, state.format))}</span>`;
            const preview = document.createElement('div');
            preview.className = 'pcs-poster-card__preview' + (state.format === 'post' ? ' is-post' : state.format === 'square' ? ' is-square' : '');
            preview.innerHTML = buildCanvasHtml(tpl, state.format);
            syncCanvasTypography(preview);
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
        const meta = resolveTemplateMeta(tpl);
        const box = $('#pcsLightboxPreview');
        const lb = $('#pcsLightbox');
        const title = $('#pcsLightboxTitle');
        const sub = $('#pcsLightboxSub');
        if (!box || !lb) return;
        state.previewTemplate = tpl;
        if (title) title.textContent = posterDisplayLabel(tpl, state.format);
        const fmtMeta = FORMAT_META[state.format];
        if (sub) {
            sub.innerHTML = fmtMeta
                ? `${esc(fmtMeta.label)} · ${formatDimsHtml(state.format)}`
                : '';
        }
        box.innerHTML = buildCanvasHtml(tpl, state.format);
        syncCanvasTypography(box);
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
        const fmt = state.format;
        let innerHtml;
        if (state.editorStorySlideId && state.editorTemplate === tpl) {
            const slide = findStorySlide(state.editorStorySlideId);
            const conf = state.editorBuffer ? { ...state.editorBuffer } : null;
            innerHtml = slide && conf ? storyPreviewHtml(slide, conf) : buildCanvasHtml(tpl, fmt);
        } else {
            const conf = state.editorTemplate === tpl && state.editorBuffer ? { ...state.editorBuffer } : null;
            innerHtml = buildCanvasHtml(tpl, fmt, conf);
        }
        const host = createExportHost(innerHtml, fmt);
        const canvas = host.querySelector('.pcs-canvas');
        try {
            await ensurePersianFonts();
            await new Promise((resolve) => whenImagesReady(host, resolve, 10000));
            sanitizePosterTextForExport(canvas);
            await exportCanvasElement(canvas, `property-${cfg.propertyId}-${tpl}-${state.format}.webp`, state.format);
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
            b.innerHTML = `<i class="fas ${meta.icon}" aria-hidden="true"></i><span class="pcs-format-btn__label">${meta.label}</span><span class="pcs-format-btn__sub">${formatDimsHtml(key)}</span>`;
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

    function storySlideIdentity(slide) {
        const catalog = cfg.storySlides || {};
        const ref = catalog[slide?.id] || {};
        const templateId = slide?.template_id || ref.template_id || 'minimal';
        const label = slide?.label || ref.label || resolveTemplateMeta(templateId).label;
        const posterMerge = { ...(ref.poster || {}), ...(slide?.poster || {}) };
        return { templateId, label, posterMerge };
    }

    function storySlideLabel(slide) {
        return storySlideIdentity(slide).label;
    }

    function storySlideTemplateId(slide) {
        return storySlideIdentity(slide).templateId;
    }

    function storySlideConf(slide) {
        const imgs = propertyImageList();
        const { posterMerge } = storySlideIdentity(slide);
        const base = { ...posterFieldDefaults(imgs), ...posterMerge };
        if (slide.image_index != null) {
            base.primary_image_index = Math.max(0, parseInt(slide.image_index, 10) || 0);
        }
        if (slide.type === 'dual_photos' && slide.image_indices?.length) {
            base.secondary_image_index = Math.max(0, parseInt(slide.image_indices[0], 10) || 1);
        }
        if (slide.type === 'gallery_price' && slide.image_indices?.length) {
            base.image_order = slide.image_indices.slice();
        }
        if (slide.title) base.headline = slide.title;
        let conf = normalizePosterConfig(base, imgs);
        const ref = storySlideCatalogRef(slide.id);
        if (ref?.poster) {
            conf = normalizePosterConfig(applyStoryPosterIdentityKeys(conf, ref.poster), imgs);
        }
        return conf;
    }

    function storySlideRenderOpts(slide, conf) {
        const opts = { showPromoBadge: false };
        if (slide.type === 'cover') {
            opts.headlineOverride = slide.title || visibleHeadline(conf);
            opts.locationOverride = slide.subtitle;
            if (slide.image_index != null) {
                opts.heroImageUrl = slideImageAt(slide.image_index);
                opts.primaryImageIndex = slide.image_index;
            }
        } else if (slide.type === 'specs') {
            const lines = (slide.lines || []).filter(Boolean);
            opts.headlineOverride = lines[0] || visibleHeadline(conf);
            opts.specLines = lines.length > 1 ? lines.slice(1) : lines;
            if (slide.image_index != null) opts.heroImageUrl = slideImageAt(slide.image_index);
        } else if (slide.type === 'gallery_price') {
            opts.headlineOverride = slide.title || visibleHeadline(conf);
            opts.galleryIndices = slide.image_indices || [];
            opts.priceLabel = slide.price_label || '';
        } else if (slide.type === 'photo_showcase') {
            opts.headlineOverride = slide.title || visibleHeadline(conf);
            opts.locationOverride = slide.subtitle;
            const imgs = propertyImageList();
            const hero = slide.image_index != null ? slide.image_index : 0;
            if (slide.image_index != null) {
                opts.heroImageUrl = slideImageAt(slide.image_index);
                opts.primaryImageIndex = slide.image_index;
            }
            if (slide.image_indices?.length) {
                opts.circleImageIndices = slide.image_indices.slice(0, 3);
            } else {
                opts.circleImageIndices = sculpturalCircleIndices(imgs, hero, 3);
            }
        } else if (slide.type === 'dual_photos') {
            opts.headlineOverride = slide.title || visibleHeadline(conf);
            opts.locationOverride = slide.subtitle;
            const hero = slide.image_index != null ? slide.image_index : 0;
            if (slide.image_index != null) {
                opts.heroImageUrl = slideImageAt(slide.image_index);
                opts.primaryImageIndex = slide.image_index;
            }
            const stripIdx = slide.image_indices?.[0];
            if (stripIdx != null) opts.stripImageIndex = stripIdx;
        } else if (slide.type === 'contact') {
            opts.headlineOverride = slide.cta || 'برای هماهنگی بازدید پیام دهید';
            opts.specLines = [];
            opts.suppressPrice = true;
        }
        return opts;
    }

    function buildStoryboardSlideHtml(slide, formatKey) {
        const fmtKey = formatKey || 'story';
        if (!slide) return buildCanvasHtml('minimal', fmtKey);
        const conf = storySlideConf(slide);
        const tpl = storySlideTemplateId(slide);
        return buildCanvasHtml(tpl, fmtKey, conf, storySlideRenderOpts(slide, conf));
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
            el.className = 'pcs-story-slide pcs-story-slide--editable';
            el.setAttribute('role', 'button');
            el.setAttribute('tabindex', '0');
            el.setAttribute('aria-label', `ویرایش استوری ${storySlideLabel(slide)}`);
            const cap = document.createElement('span');
            cap.className = 'pcs-story-slide__label';
            cap.textContent = storySlideLabel(slide);
            const frame = document.createElement('div');
            frame.className = 'pcs-story-slide__frame';
            frame.innerHTML = buildStoryboardSlideHtml(slide, 'story');
            el.appendChild(frame);
            el.appendChild(cap);
            const openSlideEditor = () => openEditor(storySlideTemplateId(slide), slide.id);
            el.addEventListener('click', openSlideEditor);
            el.addEventListener('keydown', (ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault();
                    openSlideEditor();
                }
            });
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

    function bindBrandFields() {
        const b = mergeBrand();
        const set = (id, val) => { const el = $(id); if (el) el.value = val || ''; };
        set('#pcsBrandName', b.brand_name);
        set('#pcsConsultantName', b.consultant_name);
        set('#pcsContactPhone', b.contact_phone);
        set('#pcsInstagram', b.instagram);
        const primary = normalizeBrandColor(b.colors?.primary || '#7c3aed');
        set('#pcsPrimaryColor', primary);
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

    function aiStyleTone(style) {
        const s = String(style || '').trim();
        if (/رسمی|حرفه/i.test(s)) return 'formal';
        if (/صمیمی|دوستانه/i.test(s)) return 'warm';
        if (/جذاب|تبلیغ/i.test(s)) return 'vivid';
        if (/کوتاه|مختصر/i.test(s)) return 'short';
        return 'neutral';
    }

    function aiStyleIcon(tone) {
        const icons = {
            formal: 'fa-briefcase',
            warm: 'fa-face-smile',
            vivid: 'fa-bolt',
            short: 'fa-compress',
            neutral: 'fa-pen-nib',
        };
        return icons[tone] || icons.neutral;
    }

    function truncatePreviewText(text, max) {
        const t = String(text || '').trim();
        if (t.length <= max) return t;
        return `${t.slice(0, max - 1)}…`;
    }

    function updateCharCountEl(el, counterId) {
        const counter = counterId ? $(counterId) : null;
        if (!counter || !el) return;
        const len = (el.value || '').length;
        counter.textContent = len ? `${len} کاراکتر` : '';
    }

    function renderHashtagPreview() {
        const raw = ($('#pcsHashtags')?.value || '').trim();
        const wrap = $('#pcsHashtagPreview');
        if (!wrap) return;
        const tags = raw.split(/\s+/).filter((t) => t.startsWith('#') || t.length > 0);
        if (!tags.length) {
            wrap.innerHTML = '';
            wrap.setAttribute('aria-hidden', 'true');
            return;
        }
        wrap.innerHTML = tags.map((t) => {
            const label = t.startsWith('#') ? t : `#${t}`;
            return `<span class="pcs-hashtag-chip">${esc(label)}</span>`;
        }).join('');
        wrap.removeAttribute('aria-hidden');
    }

    function bindAiCopyFieldButtons() {
        const copy = (sel, label) => {
            const el = $(sel);
            if (!el?.value) {
                toast('متنی برای کپی نیست');
                return;
            }
            navigator.clipboard.writeText(el.value);
            toast(label || 'کپی شد');
        };
        $('#pcsCopyDivarBody')?.addEventListener('click', () => copy('#pcsDivarBody', 'متن آگهی کپی شد'));
        $('#pcsCopyHashtags')?.addEventListener('click', () => copy('#pcsHashtags', 'هشتگ‌ها کپی شد'));
        $('#pcsCopyWhatsapp')?.addEventListener('click', () => copy('#pcsWhatsappText', 'متن واتساپ کپی شد'));
        $('#pcsCopyTelegram')?.addEventListener('click', () => copy('#pcsTelegramText', 'متن تلگرام کپی شد'));
    }

    function buildDivarTitleCard(opts) {
        const { style, text, index, selected } = opts;
        const tone = aiStyleTone(style);
        const len = (text || '').length;
        const idxLabel = ['۱', '۲', '۳'][index] || String(index + 1);
        const countCls = len > 50 ? ' is-over' : len > 44 ? ' is-warn' : '';
        return `
            <article class="pcs-divar-title pcs-divar-title--${tone}${selected ? ' is-selected' : ''}">
                <span class="pcs-divar-title__idx" aria-hidden="true">${idxLabel}</span>
                <div class="pcs-divar-title__main">
                    <div class="pcs-divar-title__top">
                        <span class="pcs-divar-title__tag">${esc(style || 'عنوان')}</span>
                        <span class="pcs-divar-title__count${countCls}">${len}<span aria-hidden="true"> / ۵۰</span></span>
                    </div>
                    <textarea class="pcs-divar-title__input" data-title-idx="${index}" rows="2" dir="rtl" placeholder="عنوان آگهی…">${esc(text || '')}</textarea>
                </div>
                <div class="pcs-divar-title__actions">
                    <button type="button" class="pcs-divar-icon-btn" data-copy-title="${index}" title="کپی عنوان">
                        <i class="fas fa-copy" aria-hidden="true"></i>
                    </button>
                    <button type="button" class="pcs-divar-icon-btn pcs-divar-icon-btn--pick${selected ? ' is-on' : ''}" data-use-title="${index}" title="انتخاب برای بسته انتشار">
                        <i class="fas fa-check" aria-hidden="true"></i>
                    </button>
                </div>
            </article>`;
    }

    function divarTitlesEmptyState() {
        return `<div class="pcs-divar-empty">
            <p>هنوز عنوانی نیست — <button type="button" class="pcs-divar-empty__link" data-pcs-gen-divar-titles>با AI بساز</button></p>
        </div>`;
    }

    function socialCaptionsEmptyState() {
        return `<div class="pcs-divar-empty">
            <p>کپشنی نیست — <button type="button" class="pcs-divar-empty__link" data-pcs-gen-social>با AI بساز</button></p>
        </div>`;
    }

    function buildSocialCaptionCard(opts) {
        const { style, text, index } = opts;
        const tone = aiStyleTone(style);
        const len = (text || '').length;
        const toneInitial = (style || 'ک').trim().charAt(0) || 'ک';
        return `
            <article class="pcs-social-caption pcs-social-caption--${tone}">
                <span class="pcs-social-caption__tone" title="${esc(style || '')}">${esc(toneInitial)}</span>
                <div class="pcs-social-caption__main">
                    <div class="pcs-social-caption__meta">
                        <span class="pcs-social-caption__label">${esc(style || 'کپشن')}</span>
                        <span class="pcs-social-caption__count">${len} کاراکتر</span>
                    </div>
                    <textarea class="pcs-social-caption__input" data-cap-idx="${index}" rows="4" dir="rtl" placeholder="متن کپشن…">${esc(text || '')}</textarea>
                </div>
                <div class="pcs-social-caption__actions">
                    <button type="button" class="pcs-divar-icon-btn" data-copy-cap="${index}" title="کپی کپشن">
                        <i class="fas fa-copy" aria-hidden="true"></i>
                    </button>
                </div>
            </article>`;
    }

    function buildAiCopyCard(opts) {
        const { style, text, index, kind, selected } = opts;
        const tone = aiStyleTone(style);
        const charLen = (text || '').length;
        const actions = kind === 'title'
            ? `<button type="button" class="pcs-copy-card__action" data-copy-title="${index}" title="کپی عنوان">
                    <i class="fas fa-copy" aria-hidden="true"></i><span>کپی</span>
                </button>
                <button type="button" class="pcs-copy-card__action pcs-copy-card__action--primary" data-use-title="${index}">
                    <i class="fas fa-check" aria-hidden="true"></i><span>انتخاب</span>
                </button>`
            : `<button type="button" class="pcs-copy-card__action" data-copy-cap="${index}" title="کپی کپشن">
                    <i class="fas fa-copy" aria-hidden="true"></i><span>کپی</span>
                </button>`;
        const dataAttr = kind === 'title' ? `data-title-idx="${index}"` : `data-cap-idx="${index}"`;
        return `
            <article class="pcs-copy-card pcs-copy-card--${tone}${selected ? ' is-selected' : ''}">
                <header class="pcs-copy-card__head">
                    <span class="pcs-copy-card__badge"><i class="fas ${aiStyleIcon(tone)}" aria-hidden="true"></i>${esc(style || 'متن')}</span>
                    <div class="pcs-copy-card__meta">
                        <span class="pcs-copy-card__count">${charLen} کاراکتر</span>
                        <div class="pcs-copy-card__actions">${actions}</div>
                    </div>
                </header>
                <div class="pcs-copy-card__body">
                    <textarea class="pcs-copy-card__textarea" ${dataAttr} rows="${kind === 'title' ? 2 : 5}" placeholder="متن را ویرایش کنید…">${esc(text || '')}</textarea>
                </div>
            </article>`;
    }

    function aiCopyEmptyState(message, cta) {
        return `<div class="pcs-copy-empty">
            <span class="pcs-copy-empty__icon" aria-hidden="true"><i class="fas fa-wand-magic-sparkles"></i></span>
            <p class="pcs-copy-empty__text">${esc(message)}</p>
            ${cta ? `<p class="pcs-copy-empty__hint">${esc(cta)}</p>` : ''}
        </div>`;
    }

    function renderAiStrip() {
        /* خلاصه AI فقط در تب‌های دیوار/شبکه‌ها — نه در پوسترها */
    }

    function setFieldValue(id, value) {
        const el = $(id);
        if (el) el.value = value ?? '';
    }

    function syncFormFromDraft() {
        setFieldValue('#pcsDivarBody', state.draft?.ai?.divar?.body || '');
        const bodyStyle = state.draft?.ai?.divar?.body_style || 'formal';
        const styleEl = $('#pcsDivarBodyStyle');
        if (styleEl) styleEl.value = bodyStyle;
        const tags = (state.draft?.ai?.social?.hashtags || []).join(' ');
        setFieldValue('#pcsHashtags', tags);
        setFieldValue(
            '#pcsWhatsappText',
            state.draft?.ai?.social?.whatsapp_full || state.draft?.ai?.social?.whatsapp_short || '',
        );
        setFieldValue('#pcsTelegramText', state.draft?.ai?.social?.telegram || '');
        renderDivarTitles();
        renderSocialCaptions();
        updateCharCountEl($('#pcsDivarBody'), '#pcsDivarBodyCount');
        renderHashtagPreview();
    }

    function renderDivarTitles() {
        const wrap = $('#pcsDivarTitles');
        if (!wrap) return;
        const titles = state.draft?.ai?.divar?.titles || [];
        const selected = state.draft?.ai?.divar?.selected_title_index ?? 0;
        if (!titles.length) {
            wrap.innerHTML = divarTitlesEmptyState();
            wrap.querySelector('[data-pcs-gen-divar-titles]')?.addEventListener('click', () => {
                $('#pcsGenDivarTitles')?.click();
            });
            return;
        }
        wrap.innerHTML = titles.map((t, i) => buildDivarTitleCard({
            style: t.style,
            text: t.text,
            index: i,
            selected: i === selected,
        })).join('');
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
                renderDivarTitles();
                toast('عنوان انتخاب شد');
            });
        });
        wrap.querySelectorAll('textarea[data-title-idx]').forEach((ta) => {
            ta.addEventListener('input', () => {
                const i = parseInt(ta.dataset.titleIdx, 10);
                if (state.draft.ai.divar.titles[i]) state.draft.ai.divar.titles[i].text = ta.value;
                const count = ta.closest('.pcs-divar-title')?.querySelector('.pcs-divar-title__count');
                if (count) {
                    const len = ta.value.length;
                    count.innerHTML = `${len}<span aria-hidden="true"> / ۵۰</span>`;
                    count.classList.toggle('is-warn', len > 44 && len <= 50);
                    count.classList.toggle('is-over', len > 50);
                }
                scheduleSave();
                renderAiStrip();
            });
        });
    }

    function renderSocialCaptions() {
        const wrap = $('#pcsSocialCaptions');
        if (!wrap) return;
        const caps = state.draft?.ai?.social?.captions || [];
        if (!caps.length) {
            wrap.innerHTML = socialCaptionsEmptyState();
            wrap.querySelector('[data-pcs-gen-social]')?.addEventListener('click', () => {
                $('#pcsGenSocial')?.click();
            });
            return;
        }
        wrap.innerHTML = caps.map((c, i) => buildSocialCaptionCard({
            style: c.style,
            text: c.text,
            index: i,
        })).join('');
        wrap.querySelectorAll('[data-copy-cap]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const ta = wrap.querySelector(`[data-cap-idx="${btn.getAttribute('data-copy-cap')}"]`);
                navigator.clipboard.writeText(ta?.value || '');
                toast('کپی شد');
            });
        });
        wrap.querySelectorAll('textarea[data-cap-idx]').forEach((ta) => {
            ta.addEventListener('input', () => {
                const i = parseInt(ta.dataset.capIdx, 10);
                if (state.draft?.ai?.social?.captions?.[i]) {
                    state.draft.ai.social.captions[i].text = ta.value;
                    const count = ta.closest('.pcs-social-caption')?.querySelector('.pcs-social-caption__count');
                    if (count) count.textContent = `${ta.value.length} کاراکتر`;
                    scheduleSave();
                    renderAiStrip();
                }
            });
        });
    }

    function collectDraftFromForm() {
        if (!state.draft) return null;
        const bodyEl = $('#pcsDivarBody');
        if (bodyEl) state.draft.ai.divar.body = bodyEl.value;
        const styleEl = $('#pcsDivarBodyStyle');
        if (styleEl) state.draft.ai.divar.body_style = styleEl.value || 'formal';
        state.draft.ai.social.hashtags = ($('#pcsHashtags')?.value || '').split(/\s+/).filter(Boolean);
        state.draft.ai.social.whatsapp_full = $('#pcsWhatsappText')?.value || '';
        state.draft.ai.social.telegram = $('#pcsTelegramText')?.value || '';
        return state.draft;
    }

    function setSaveStatus(status) {
        state.saveStatus = status;
        const el = $('#pcsSaveStatus');
        if (!el) return;
        const map = {
            idle: '',
            saving: 'در حال ذخیره…',
            saved: 'ذخیره شد',
            failed: 'خطا در ذخیره',
        };
        el.textContent = map[status] || '';
        el.classList.toggle('is-error', status === 'failed');
    }

    function markDraftDirty() {
        state.draftDirtyRev += 1;
    }

    function scheduleSave() {
        markDraftDirty();
        clearTimeout(state.saveTimer);
        state.saveTimer = setTimeout(() => { flushSaveDraft(); }, 800);
    }

    async function flushSaveDraft() {
        if (!state.draft || state.saveInflight) {
            state.savePending = true;
            return;
        }
        const snapshotRev = state.draftDirtyRev;
        const draftPayload = collectDraftFromForm() || state.draft;
        const draftSnapshot = JSON.stringify(draftPayload);
        const seq = ++state.saveSeq;
        state.saveInflight = true;
        setSaveStatus('saving');
        const token = csrf();
        try {
            const res = await fetch(cfg.draftUrl, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                body: JSON.stringify({ draft: JSON.parse(draftSnapshot) }),
            });
            let data = {};
            try { data = await res.json(); } catch (_) { /* ignore */ }
            if (seq !== state.saveSeq) return;
            if (!res.ok || data.ok === false) {
                setSaveStatus('failed');
                toast(data.error || 'ذخیره پیش‌نویس ناموفق بود');
                return;
            }
            const stillCurrent = snapshotRev === state.draftDirtyRev;
            if (data.draft && stillCurrent) {
                state.draft = data.draft;
            }
            if (typeof data.draft_stale === 'boolean') {
                state.session = state.session || {};
                state.session.draft_stale = data.draft_stale;
            }
            if (typeof data.property_fingerprint === 'string') {
                state.session = state.session || {};
                state.session.property_fingerprint = data.property_fingerprint;
            }
            setSaveStatus('saved');
        } catch (_) {
            if (seq === state.saveSeq) {
                setSaveStatus('failed');
                toast('خطا در ارتباط هنگام ذخیره');
            }
        } finally {
            state.saveInflight = false;
            const needsAnotherSave = state.savePending || snapshotRev !== state.draftDirtyRev;
            if (needsAnotherSave) {
                state.savePending = false;
                flushSaveDraft();
            }
        }
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
        clearTimeout(state.saveTimer);
        await flushSaveDraft();
    }

    async function loadSession() {
        const loading = $('#pcsLoading');
        const token = ++state.sessionToken;
        loading?.removeAttribute('hidden');
        try {
            const res = await fetch(cfg.sessionUrl, { headers: { Accept: 'application/json' } });
            const data = await res.json();
            if (token !== state.sessionToken) return;
            if (!data.ok) throw new Error(data.error || 'خطا');
            if ($('#pcsModal')?.hasAttribute('hidden')) return;
            state.session = data;
            state.draft = data.draft || {};
            if (ensureStoryboardSlidesStructure()) scheduleSave();
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
            if (token === state.sessionToken) loading?.setAttribute('hidden', '');
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
        const canCreate = !!state.session?.can_create_public_share;
        grid.innerHTML = `
            <div class="pcs-share-card">
                <p class="pcs-share-card__label">لینک عمومی فایل</p>
                <input type="text" class="pcs-input" id="pcsShareUrlField" readonly dir="ltr" value="${esc(url)}">
                <button type="button" class="pcs-btn pcs-btn--soft pcs-btn--block" id="pcsShareTabCopy">کپی لینک</button>
                ${!url && canCreate ? '<button type="button" class="pcs-btn pcs-btn--primary pcs-btn--block" id="pcsShareCreateLink">ایجاد لینک عمومی</button>' : ''}
                ${!url && !canCreate ? '<p class="pcs-share-card__hint">لینک عمومی فعالی وجود ندارد.</p>' : ''}
            </div>
            <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--block" id="pcsShareTabDivar">رفتن به تب آگهی دیوار</button>`;
        $('#pcsShareTabCopy')?.addEventListener('click', () => {
            const current = $('#pcsShareUrlField')?.value || url;
            if (!current) { toast('لینک عمومی موجود نیست'); return; }
            navigator.clipboard.writeText(current);
            toast('لینک کپی شد');
        });
        $('#pcsShareCreateLink')?.addEventListener('click', async () => {
            if (!cfg.publicShareUrl) {
                toast('مسیر ایجاد لینک در دسترس نیست');
                return;
            }
            try {
                const res = await fetch(cfg.publicShareUrl, {
                    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (!res.ok || !data.ok) {
                    toast(data.error || 'ایجاد لینک ناموفق بود');
                    return;
                }
                state.session.property.public_share_url = data.share_url || '';
                renderSharePanel();
                toast('لینک عمومی ایجاد شد');
            } catch (_) {
                toast('خطا در ایجاد لینک');
            }
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
        const showFooter = tab === 'posters' || tab === 'share';
        if (dl) dl.hidden = !showDl;
        footer.hidden = !showFooter;
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

    async function closeModal() {
        closePreview();
        closeSettingsSheet();
        if (!$('#pcsEditor')?.hasAttribute('hidden')) {
            closeEditor();
            if (!$('#pcsEditor')?.hasAttribute('hidden')) return;
        }
        await saveDraft();
        state.sessionToken += 1;
        resetStudioShellState();
        $('#pcsModal')?.setAttribute('hidden', '');
        unlockPageScroll();
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
            secondary_image_index: (() => {
                const stripEl = controls?.querySelector('#pcsEditEmeraldStrip');
                const fallback = prev.secondary_image_index ?? (imgs.length > 1 ? 1 : 0);
                const v = stripEl
                    ? parseInt(stripEl.value || String(fallback), 10)
                    : parseInt(String(fallback), 10);
                if (!imgs.length) return 0;
                let s = Math.min(imgs.length - 1, Math.max(0, Number.isFinite(v) ? v : 0));
                const p = imgs.length ? Math.min(imgs.length - 1, Math.max(0, primary)) : 0;
                if (imgs.length > 1 && s === p) s = (p + 1) % imgs.length;
                return s;
            })(),
            image_order: imageOrder,
            img_brightness: parseInt(controls?.querySelector('[data-pcs-edit-range="brightness"]')?.value || String(prev.img_brightness ?? 100), 10),
            img_blur: parseInt(controls?.querySelector('[data-pcs-edit-range="blur"]')?.value || String(prev.img_blur ?? 0), 10),
            img_opacity: parseInt(controls?.querySelector('[data-pcs-edit-range="opacity"]')?.value || String(prev.img_opacity ?? 100), 10),
            headline_scale: parseInt(controls?.querySelector('[data-pcs-edit-range="headline_scale"]')?.value || String(prev.headline_scale ?? 100), 10),
            price_scale: parseInt(controls?.querySelector('[data-pcs-edit-range="price_scale"]')?.value || String(prev.price_scale ?? 100), 10),
            headline_weight: normalizePosterTextWeight(
                controls?.querySelector('[data-pcs-headline-weight].is-active')?.getAttribute('data-pcs-headline-weight'),
                prev.headline_weight ?? 900,
            ),
            price_weight: normalizePosterTextWeight(
                controls?.querySelector('[data-pcs-price-weight].is-active')?.getAttribute('data-pcs-price-weight'),
                prev.price_weight ?? 900,
            ),
            headline_italic: !!controls?.querySelector('[data-pcs-headline-italic].is-active'),
            headline_underline: !!controls?.querySelector('[data-pcs-headline-underline].is-active'),
            price_italic: !!controls?.querySelector('[data-pcs-price-italic].is-active'),
            price_underline: !!controls?.querySelector('[data-pcs-price-underline].is-active'),
            headline_color: controls?.querySelector('[data-pcs-edit-color-auto="headline"].is-active')
                ? ''
                : normalizePosterHexColor(controls?.querySelector('[data-pcs-edit-color="headline"]')?.value),
            price_color: controls?.querySelector('[data-pcs-edit-color-auto="price"].is-active')
                ? ''
                : normalizePosterHexColor(controls?.querySelector('[data-pcs-edit-color="price"]')?.value),
            font_key: fontBtn?.getAttribute('data-pcs-font-key') || prev.font_key || 'vazirmatn',
            pip_enabled: controls?.querySelector('#pcsEditPipEnabled')?.value === '1',
            pip_image_index: imgs.length
                ? Math.min(imgs.length - 1, Math.max(0, parseInt(
                    controls?.querySelector('[data-pcs-pip-image-select]')?.value
                    || controls?.querySelector('#pcsEditPipImage')?.value
                    || String(prev.pip_image_index ?? 1),
                    10,
                )))
                : 0,
            pip_corner: controls?.querySelector('[data-pcs-pip-corner].is-active')?.getAttribute('data-pcs-pip-corner') || prev.pip_corner || 'br',
            pip_size: controls?.querySelector('[data-pcs-pip-size].is-active')?.getAttribute('data-pcs-pip-size') || prev.pip_size || 'm',
            pip_shape: controls?.querySelector('[data-pcs-pip-shape].is-active')?.getAttribute('data-pcs-pip-shape') || prev.pip_shape || 'rounded',
            pip_border: controls?.querySelector('[data-pcs-pip-border].is-active')?.getAttribute('data-pcs-pip-border') || prev.pip_border || 'light',
            pip_crop_y: parseInt(controls?.querySelector('[data-pcs-edit-range="pip_crop"]')?.value || String(prev.pip_crop_y ?? 50), 10),
            pip_tilt: parseInt(controls?.querySelector('[data-pcs-edit-range="pip_tilt"]')?.value || String(prev.pip_tilt ?? 0), 10),
            hero_vignette: parseInt(controls?.querySelector('[data-pcs-edit-range="hero_vignette"]')?.value || String(prev.hero_vignette ?? 0), 10),
            hero_warmth: controls?.querySelector('[data-pcs-hero-warmth].is-active')?.getAttribute('data-pcs-hero-warmth') || prev.hero_warmth || 'neutral',
            brand_primary: (() => {
                const inp = controls?.querySelector('#pcsEditBrandPrimary');
                if (!inp) return prev.brand_primary || '';
                const picked = normalizePosterHexColor(inp.value);
                const global = normalizeBrandColor(mergeBrand().colors?.primary || '#7c3aed');
                if (!picked || picked === global) return '';
                return picked;
            })(),
            text_layout: normalizeTextLayout(prev.text_layout),
        };
    }

    function updateEditorBufferFromForm(tpl) {
        if (!state.editorBuffer) return;
        Object.assign(state.editorBuffer, readEditorForm(tpl));
        state.editorBuffer.text_layout = normalizeTextLayout(state.editorBuffer.text_layout);
        state.editorBuffer.text_layout.headline.s = 100;
        state.editorBuffer.text_layout.price.s = 100;
        syncEditorDirtyFlag();
    }

    function findStorySlide(slideId) {
        return (state.draft?.storyboard?.slides || []).find((s) => s.id === slideId) || null;
    }

    function editorBrandPrimarySection(conf) {
        const b = mergeBrand();
        const global = normalizeBrandColor(b.colors?.primary || '#7c3aed');
        const val = normalizePosterHexColor(conf?.brand_primary) || global;
        const scopeHint = state.editorStorySlideId ? ' این استوری' : ' این پوستر';
        return `
            <section class="pcs-editor__section">
                <h4 class="pcs-editor__section-title"><i class="fas fa-palette" aria-hidden="true"></i> رنگ اصلی برند</h4>
                <p class="pcs-editor__section-hint">روی${scopeHint}، دکمه‌ها و جزئیات گرافیکی اعمال می‌شود</p>
                <div class="pcs-editor__brand-color-row">
                    <input type="color" id="pcsEditBrandPrimary" class="pcs-editor__color-swatch pcs-editor__color-swatch--lg"
                        value="${esc(val)}" aria-label="رنگ اصلی برند">
                    <span class="pcs-editor__brand-color-val" id="pcsEditBrandPrimaryVal">${esc(val)}</span>
                    <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--sm" id="pcsEditBrandPrimaryReset">
                        <i class="fas fa-rotate-left" aria-hidden="true"></i> پیش‌فرض برند
                    </button>
                </div>
            </section>`;
    }

    function storyPreviewHtml(slide, conf) {
        if (!slide) return '';
        const mergedSlide = {
            ...slide,
            poster: normalizePosterConfig({ ...(slide.poster || {}), ...conf }, propertyImageList()),
        };
        return buildStoryboardSlideHtml(mergedSlide, 'story');
    }

    function commitEditorToDraft(tpl) {
        if (!state.draft || !tpl) return;
        updateEditorBufferFromForm(tpl);
        if (state.editorStorySlideId) {
            const slide = findStorySlide(state.editorStorySlideId);
            if (slide) {
                slide.poster = { ...state.editorBuffer };
                const imgs = propertyImageList();
                if (slide.type === 'dual_photos' && state.editorBuffer) {
                    slide.image_index = state.editorBuffer.primary_image_index;
                    slide.image_indices = [emeraldStripIndex(state.editorBuffer, imgs)];
                }
            }
            return;
        }
        state.draft.posters = state.draft.posters || {};
        state.draft.posters[tpl] = { ...state.editorBuffer };
    }

    function clearEditorSession() {
        state.editorBuffer = null;
        state.editorTemplate = null;
        state.editorStorySlideId = null;
        state.editorSnapshot = null;
        state.editorDirty = false;
        state.editorTextRole = null;
        state.editorPosterHeadlineSuggestions = null;
        teardownEditorTextInteraction();
        syncEditorTypeTabForRole(null);
        $('#pcsEditor')?.classList.remove('pcs-editor--dirty');
    }

    function resetEditorPreviewWrap(wrap) {
        if (!wrap) return;
        wrap.classList.remove('is-ready');
        wrap.style.height = '';
        wrap.style.minHeight = '';
        wrap.style.minWidth = '';
        wrap.style.maxHeight = '';
        wrap.style.maxWidth = '';
        wrap.style.overflow = '';
        wrap.style.display = '';
        wrap.style.justifyContent = '';
        wrap.style.alignItems = '';
        wrap.style.padding = '';
        wrap._pcsLastVisual = null;
        teardownEditorTextInteraction(wrap);
    }

    const PCS_TEXT_ROLE_LABELS = { headline: 'عنوان', meta: 'مشخصات', price: 'قیمت' };

    function textLayoutEntry(conf, role) {
        return normalizeTextLayout(conf?.text_layout)[role] || defaultTextLayoutEntry();
    }

    function effectiveTextRoleScale(conf, role) {
        const entry = textLayoutEntry(conf, role);
        if (role === 'meta') return Math.round(entry.s);
        const base = role === 'headline' ? (conf?.headline_scale ?? 100) : (conf?.price_scale ?? 100);
        if (entry.s === 100) return Math.round(base);
        return Math.min(180, Math.max(50, Math.round(base * entry.s / 100)));
    }

    function setTextRoleTransformFromEffective(conf, role, effectivePct) {
        if (!conf || !role) return;
        conf.text_layout = normalizeTextLayout(conf.text_layout);
        const eff = Math.min(180, Math.max(50, Math.round(effectivePct)));
        if (role === 'meta') {
            conf.text_layout.meta.s = eff;
            return;
        }
        const base = role === 'headline' ? (conf.headline_scale ?? 100) : (conf.price_scale ?? 100);
        const safeBase = Math.max(1, base);
        conf.text_layout[role].s = Math.min(180, Math.max(50, Math.round((eff / safeBase) * 100)));
    }

    function setTextRoleTransformScale(conf, role, value) {
        if (!conf || !role) return;
        conf.text_layout = normalizeTextLayout(conf.text_layout);
        const v = Math.min(180, Math.max(50, Math.round(value)));
        conf.text_layout[role].s = v;
    }

    function setTextRoleScale(conf, role, value) {
        if (!conf) return;
        const v = Math.min(180, Math.max(50, Math.round(value)));
        conf.text_layout = normalizeTextLayout(conf.text_layout);
        if (role === 'meta') {
            conf.text_layout.meta.s = v;
            return;
        }
        if (role === 'headline') conf.headline_scale = v;
        if (role === 'price') conf.price_scale = v;
        conf.text_layout[role].s = 100;
    }

    function commitTextRoleTransformScale(conf, role) {
        if (!conf || !role) return;
        const entry = textLayoutEntry(conf, role);
        if (entry.s === 100) return;
        if (role === 'meta') return;
        const base = role === 'headline' ? (conf.headline_scale ?? 100) : (conf.price_scale ?? 100);
        const merged = Math.min(180, Math.max(50, Math.round(base * entry.s / 100)));
        if (role === 'headline') conf.headline_scale = merged;
        else conf.price_scale = merged;
        entry.s = 100;
    }

    function syncEditorTransformBar(role) {
        const bar = $('#pcsEditorTransformBar');
        if (!bar) return;
        if (!role || !state.editorBuffer) {
            bar.setAttribute('hidden', '');
            return;
        }
        bar.removeAttribute('hidden');
        const lbl = bar.querySelector('[data-pcs-transform-role-label]');
        if (lbl) lbl.textContent = PCS_TEXT_ROLE_LABELS[role] || role;
        const scaleVal = effectiveTextRoleScale(state.editorBuffer, role);
        const range = bar.querySelector('[data-pcs-transform-scale]');
        const rangeLbl = bar.querySelector('[data-pcs-transform-scale-val]');
        if (range) range.value = String(scaleVal);
        if (rangeLbl) rangeLbl.textContent = `${scaleVal}%`;
    }

    function syncEditorTypeTabForRole(role) {
        const controls = editorControlsEl();
        if (controls) {
            const tabRole = role === 'price' ? 'price' : role === 'meta' ? 'meta' : 'headline';
            controls.querySelectorAll('[data-pcs-type-tab]').forEach((btn) => {
                const on = btn.getAttribute('data-pcs-type-tab') === tabRole;
                btn.classList.toggle('is-active', on);
                btn.setAttribute('aria-selected', on ? 'true' : 'false');
            });
            controls.querySelectorAll('[data-pcs-type-panel]').forEach((panel) => {
                const key = panel.getAttribute('data-pcs-type-panel');
                const on = key === tabRole;
                panel.hidden = !on;
                panel.classList.toggle('is-active', on);
            });
        }
        const focus = $('#pcsEditorTextFocus');
        if (focus) {
            if (!role) {
                focus.setAttribute('hidden', '');
            } else {
                focus.removeAttribute('hidden');
                const lbl = focus.querySelector('[data-pcs-text-focus-label]');
                if (lbl) lbl.textContent = PCS_TEXT_ROLE_LABELS[role] || role;
            }
        }
        syncEditorTransformBar(role);
    }

    function applyTextLayoutToElement(el, conf, role) {
        if (!el) return;
        el.style.transform = '';
        el.style.transformOrigin = 'top right';
        const layoutCss = posterTextLayoutStyle(conf, role);
        if (layoutCss) {
            layoutCss.split(';').filter(Boolean).forEach((chunk) => {
                const idx = chunk.indexOf(':');
                if (idx < 0) return;
                const prop = chunk.slice(0, idx).trim();
                const val = chunk.slice(idx + 1).trim();
                if (prop) el.style[prop] = val;
            });
        }
        const badge = el.querySelector('[data-pcs-text-scale-label]');
        if (badge) {
            badge.textContent = `${effectiveTextRoleScale(conf, role)}%`;
        }
    }

    function mountPosterTextTransformChrome(el) {
        el.querySelector('.pcs-poster-text__chrome')?.remove();
        const chrome = document.createElement('div');
        chrome.className = 'pcs-poster-text__chrome';
        chrome.innerHTML = `
            <span class="pcs-poster-text__badge" data-pcs-text-scale-label>100%</span>
            <span class="pcs-poster-text__handle pcs-poster-text__handle--nw" data-pcs-text-resize="nw"></span>
            <span class="pcs-poster-text__handle pcs-poster-text__handle--ne" data-pcs-text-resize="ne"></span>
            <span class="pcs-poster-text__handle pcs-poster-text__handle--sw" data-pcs-text-resize="sw"></span>
            <span class="pcs-poster-text__handle pcs-poster-text__handle--se" data-pcs-text-resize="se"></span>
        `;
        el.appendChild(chrome);
    }

    function editorTextCanvasMetrics(previewWrap) {
        const canvas = previewWrap?.querySelector?.('.pcs-canvas');
        if (!canvas) return null;
        const fmt = FORMATS[state.format] || FORMATS.story;
        const rect = canvas.getBoundingClientRect();
        const logicalW = fmt.w || parseInt(canvas.style.width, 10) || 1080;
        const logicalH = fmt.h || parseInt(canvas.style.height, 10) || 1920;
        return { canvas, rect, logicalW, logicalH };
    }

    function teardownEditorTextInteraction(previewWrap) {
        const wrap = previewWrap || $('#pcsEditorPreview');
        if (wrap) {
            wrap.classList.remove('pcs-editor__preview--text-edit');
            const canvas = wrap.querySelector('.pcs-canvas');
            if (canvas && wrap._pcsTextCanvasHandler) {
                canvas.removeEventListener('mousedown', wrap._pcsTextCanvasHandler);
                wrap._pcsTextCanvasHandler = null;
            }
            wrap.querySelectorAll('[data-pcs-text-role]').forEach((el) => {
                el.classList.remove('is-selected', 'pcs-poster-text--hit');
                el.querySelector('.pcs-poster-text__chrome')?.remove();
            });
        }
        if (state.editorTextDrag?.onMove) {
            window.removeEventListener('mousemove', state.editorTextDrag.onMove);
            window.removeEventListener('mouseup', state.editorTextDrag.onUp);
        }
        state.editorTextDrag = null;
        syncEditorTransformBar(null);
    }

    function selectEditorTextRole(role, previewWrap) {
        const wrap = previewWrap || $('#pcsEditorPreview');
        state.editorTextRole = role || null;
        wrap?.querySelectorAll('[data-pcs-text-role]').forEach((el) => {
            const r = el.getAttribute('data-pcs-text-role');
            const on = r === role;
            el.classList.toggle('is-selected', on);
            if (on) {
                mountPosterTextTransformChrome(el);
                if (state.editorBuffer) applyTextLayoutToElement(el, state.editorBuffer, r);
            } else {
                el.querySelector('.pcs-poster-text__chrome')?.remove();
            }
        });
        syncEditorTypeTabForRole(role);
    }

    function nudgeEditorTextRole(role, dir) {
        if (!state.editorBuffer || !role) return;
        state.editorBuffer.text_layout = normalizeTextLayout(state.editorBuffer.text_layout);
        const entry = state.editorBuffer.text_layout[role];
        const step = 1.2;
        if (dir === 'x-') entry.x = Math.min(55, entry.x + step);
        if (dir === 'x+') entry.x = Math.max(-55, entry.x - step);
        if (dir === 'y-') entry.y = Math.max(-55, entry.y - step);
        if (dir === 'y+') entry.y = Math.min(55, entry.y + step);
        const wrap = $('#pcsEditorPreview');
        const el = wrap?.querySelector(`[data-pcs-text-role="${role}"]`);
        applyTextLayoutToElement(el, state.editorBuffer, role);
        syncEditorTransformBar(role);
        syncEditorDirtyFlag();
        scheduleSave();
    }

    function beginEditorTextDrag(previewWrap, el, role, mode, clientX, clientY) {
        const metrics = editorTextCanvasMetrics(previewWrap);
        if (!metrics || !state.editorBuffer) return;
        state.editorBuffer.text_layout = normalizeTextLayout(state.editorBuffer.text_layout);
        const layout = { ...state.editorBuffer.text_layout[role] };
        const start = { mode, role, x0: clientX, y0: clientY, layout, el };
        const onMove = (ev) => {
            if (!state.editorTextDrag || !state.editorBuffer) return;
            const m = editorTextCanvasMetrics(previewWrap);
            if (!m) return;
            const dxPx = ev.clientX - start.x0;
            const dyPx = ev.clientY - start.y0;
            const dxPct = (dxPx / m.rect.width) * 100;
            const dyPct = (dyPx / m.rect.height) * 100;
            const entry = state.editorBuffer.text_layout[start.role];
            if (start.mode === 'move') {
                entry.x = Math.min(55, Math.max(-55, start.layout.x + dxPct));
                entry.y = Math.min(55, Math.max(-55, start.layout.y + dyPct));
            } else {
                const delta = ((dxPx + dyPx) / m.rect.width) * 140;
                entry.s = Math.min(180, Math.max(50, start.layout.s + delta));
            }
            applyTextLayoutToElement(start.el, state.editorBuffer, start.role);
            syncEditorTransformBar(start.role);
            syncEditorDirtyFlag();
        };
        const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
            state.editorTextDrag = null;
            if (start.mode === 'resize') {
                commitTextRoleTransformScale(state.editorBuffer, start.role);
                refreshEditorPreview(state.editorTemplate);
                selectEditorTextRole(start.role, previewWrap);
            }
            scheduleSave();
        };
        state.editorTextDrag = { onMove, onUp };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    }

    function setupEditorTextInteraction(previewWrap) {
        teardownEditorTextInteraction(previewWrap);
        if (!previewWrap || previewWrap.id !== 'pcsEditorPreview') return;
        const canvas = previewWrap.querySelector('.pcs-canvas');
        if (!canvas) return;
        previewWrap.classList.add('pcs-editor__preview--text-edit');
        canvas.querySelectorAll('[data-pcs-text-role]').forEach((el) => {
            el.classList.add('pcs-poster-text--hit');
        });
        const onCanvasDown = (e) => {
            if (e.button !== 0 || !state.editorBuffer) return;
            const roleEl = e.target.closest('[data-pcs-text-role]');
            if (roleEl) {
                e.stopPropagation();
                e.preventDefault();
                const role = roleEl.getAttribute('data-pcs-text-role');
                if (!role) return;
                selectEditorTextRole(role, previewWrap);
                const resize = e.target.closest('[data-pcs-text-resize]');
                beginEditorTextDrag(previewWrap, roleEl, role, resize ? 'resize' : 'move', e.clientX, e.clientY);
                return;
            }
            if (e.target.closest('.pcs-canvas')) {
                selectEditorTextRole(null, previewWrap);
            }
        };
        previewWrap._pcsTextCanvasHandler = onCanvasDown;
        canvas.addEventListener('mousedown', onCanvasDown);
        if (state.editorTextRole) {
            selectEditorTextRole(state.editorTextRole, previewWrap);
        }
    }

    function bindEditorTransformBar() {
        const editor = $('#pcsEditor');
        if (!editor || editor.dataset.pcsTransformBarBound === '1') return;
        editor.dataset.pcsTransformBarBound = '1';
        editor.addEventListener('input', (e) => {
            const scale = e.target.closest('[data-pcs-transform-scale]');
            if (!scale || !state.editorBuffer || !state.editorTextRole) return;
            setTextRoleTransformFromEffective(state.editorBuffer, state.editorTextRole, parseInt(scale.value, 10));
            const el = $('#pcsEditorPreview')?.querySelector(`[data-pcs-text-role="${state.editorTextRole}"]`);
            applyTextLayoutToElement(el, state.editorBuffer, state.editorTextRole);
            syncEditorTransformBar(state.editorTextRole);
            syncEditorDirtyFlag();
            scheduleSave();
        });
        editor.addEventListener('change', (e) => {
            const scale = e.target.closest('[data-pcs-transform-scale]');
            if (!scale || !state.editorBuffer || !state.editorTextRole) return;
            const role = state.editorTextRole;
            if (role === 'headline' || role === 'price') {
                commitTextRoleTransformScale(state.editorBuffer, role);
                refreshEditorPreview(state.editorTemplate);
                selectEditorTextRole(role, $('#pcsEditorPreview'));
                syncEditorDirtyFlag();
                scheduleSave();
            }
        });
        editor.addEventListener('click', (e) => {
            const nudge = e.target.closest('[data-pcs-transform-nudge]');
            if (nudge && state.editorTextRole) {
                e.preventDefault();
                nudgeEditorTextRole(state.editorTextRole, nudge.getAttribute('data-pcs-transform-nudge'));
                return;
            }
            const stepBtn = e.target.closest('[data-pcs-transform-scale-step]');
            if (stepBtn && state.editorTextRole && state.editorBuffer) {
                e.preventDefault();
                const role = state.editorTextRole;
                const step = parseInt(stepBtn.getAttribute('data-pcs-transform-scale-step') || '0', 10);
                const cur = effectiveTextRoleScale(state.editorBuffer, role);
                setTextRoleTransformFromEffective(state.editorBuffer, role, cur + step);
                if (role === 'headline' || role === 'price') {
                    commitTextRoleTransformScale(state.editorBuffer, role);
                    refreshEditorPreview(state.editorTemplate);
                    selectEditorTextRole(role, $('#pcsEditorPreview'));
                } else {
                    const el = $('#pcsEditorPreview')?.querySelector(`[data-pcs-text-role="${role}"]`);
                    applyTextLayoutToElement(el, state.editorBuffer, role);
                    syncEditorTransformBar(role);
                }
                syncEditorDirtyFlag();
                scheduleSave();
            }
        });
    }

    function resetEditorTextLayout() {
        if (!state.editorBuffer) return;
        state.editorBuffer.text_layout = normalizeTextLayout(null);
        state.editorTextRole = null;
        syncEditorTypeTabForRole(null);
        refreshEditorPreview(state.editorTemplate);
        syncEditorDirtyFlag();
        scheduleSave();
        toast('چیدمان متن بازنشانی شد');
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
        if (tpl === 'emerald_atelier' && imgs.length >= 2) {
            const arch = conf.primary_image_index || 0;
            const strip = emeraldStripIndex(conf, imgs);
            meta.textContent = `قوس: تصویر ${arch + 1} · نوار: ${strip + 1} · قاب ${conf.crop_y}%`;
            return;
        }
        if (tpl === 'pearl_gallery' && imgs.length >= 2) {
            const arch = conf.primary_image_index || 0;
            const strip = emeraldStripIndex(conf, imgs);
            meta.textContent = `دایره اصلی: ${arch + 1} · مکمل: ${strip + 1} · قاب ${conf.crop_y}%`;
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
        let conf = null;
        try {
            updateEditorBufferFromForm(activeTpl);
            conf = state.editorBuffer ? { ...state.editorBuffer } : null;
            const prev = $('#pcsEditorPreview');
            if (!prev || !conf) return;
            resetEditorPreviewWrap(prev);
            if (state.editorStorySlideId) {
                const slide = findStorySlide(state.editorStorySlideId);
                prev.innerHTML = slide ? storyPreviewHtml(slide, conf) : '';
            } else {
                prev.innerHTML = buildCanvasHtml(activeTpl, state.format, conf);
            }
            syncCanvasTypography(prev);
            updateEditorLiveMeta(conf, activeTpl);
            scheduleEditorPreviewScale(prev, state.format);
            const controls = editorControlsEl();
            const cropLbl = controls?.querySelector('#pcsEditCropValue');
            if (cropLbl) cropLbl.textContent = `${conf.crop_y}%`;
            const headCount = controls?.querySelector('#pcsEditHeadlineCount');
            if (headCount) headCount.textContent = `${(controls.querySelector('#pcsEditHeadline')?.value || '').length} کاراکتر`;
            syncCropPresetActive(conf.crop_y);
            syncTypeStylePreview(conf);
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
        } catch (err) {
            console.error('pcs refreshEditorPreview', err);
            toast('خطا در به‌روزرسانی پیش‌نمایش');
        }
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
            if (t.id === 'pcsEditBrandPrimary') {
                const lbl = $('#pcsEditBrandPrimaryVal');
                if (lbl) lbl.textContent = t.value;
            }
            if (t.matches('#pcsEditHeadline, #pcsEditCrop, [data-pcs-edit-range], [data-pcs-edit-color], #pcsEditBrandPrimary')) {
                refreshEditorPreview(state.editorTemplate);
            }
        });

        pane.addEventListener('change', (e) => {
            if (!state.editorTemplate) return;
            if (e.target.matches('[data-pcs-edit-color]')) {
                const role = e.target.getAttribute('data-pcs-edit-color');
                const wrap = editorControlsEl()?.querySelector(`[data-pcs-type-colors="${role}"]`);
                wrap?.querySelector('[data-pcs-edit-color-auto]')?.classList.remove('is-active');
                wrap?.querySelectorAll('[data-pcs-edit-color-preset]').forEach((b) => b.classList.remove('is-active'));
                refreshEditorPreview(state.editorTemplate);
                return;
            }
            if (e.target.matches('[data-pcs-pip-image-select]')) {
                const controls = editorControlsEl();
                const v = e.target.value;
                const pipHidden = controls?.querySelector('#pcsEditPipImage');
                if (pipHidden) pipHidden.value = v;
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
            if (e.target.closest('#pcsEditHeadlineAi') || e.target.closest('#pcsEditHeadlineAiRefresh')) {
                e.preventDefault();
                const btn = e.target.closest('#pcsEditHeadlineAi') || e.target.closest('#pcsEditHeadlineAiRefresh');
                void runEditorPosterHeadlineAi(btn);
                return;
            }
            const posterHeadlinePick = e.target.closest('[data-pcs-pick-poster-headline]');
            if (posterHeadlinePick) {
                e.preventDefault();
                applyEditorPosterHeadlinePick(parseInt(posterHeadlinePick.getAttribute('data-pcs-pick-poster-headline') || '0', 10));
                return;
            }
            if (e.target.closest('#pcsEditBrandPrimaryReset')) {
                const global = normalizeBrandColor(mergeBrand().colors?.primary || '#7c3aed');
                const inp = controls.querySelector('#pcsEditBrandPrimary');
                if (inp) inp.value = global;
                const lbl = controls.querySelector('#pcsEditBrandPrimaryVal');
                if (lbl) lbl.textContent = global;
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

            const primaryPick = e.target.closest('[data-pcs-primary-pick]');
            if (primaryPick) {
                const idx = parseInt(primaryPick.getAttribute('data-pcs-img-idx') || '0', 10);
                const hidden = controls.querySelector('#pcsEditImage');
                if (hidden) hidden.value = String(idx);
                const lbl = controls.querySelector('[data-pcs-primary-label]');
                if (lbl) lbl.textContent = String(idx + 1);
                controls.querySelectorAll('[data-pcs-primary-pick]').forEach((btn) => {
                    const on = btn === primaryPick;
                    btn.classList.toggle('is-selected', on);
                    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }

            const emeraldSlotBtn = e.target.closest('[data-pcs-emerald-slot-btn]');
            if (emeraldSlotBtn) {
                state.editorEmeraldSlot = parseInt(emeraldSlotBtn.getAttribute('data-pcs-emerald-slot-btn') || '0', 10);
                syncEmeraldDockUi();
                return;
            }

            const emeraldPick = e.target.closest('[data-pcs-emerald-pick]');
            if (emeraldPick) {
                const idx = parseInt(emeraldPick.getAttribute('data-pcs-img-idx') || '0', 10);
                const slot = state.editorEmeraldSlot ?? 0;
                const archInp = controls.querySelector('#pcsEditImage');
                const stripInp = controls.querySelector('#pcsEditEmeraldStrip');
                const imgsList = propertyImageList();
                if (slot === 0 && archInp) {
                    archInp.value = String(idx);
                    if (stripInp && imgsList.length > 1 && parseInt(stripInp.value, 10) === idx) {
                        stripInp.value = String((idx + 1) % imgsList.length);
                    }
                } else if (stripInp) {
                    stripInp.value = String(idx);
                    if (archInp && parseInt(archInp.value, 10) === idx && imgsList.length > 1) {
                        archInp.value = String((idx + 1) % imgsList.length);
                    }
                }
                if (state.editorBuffer) {
                    state.editorBuffer.primary_image_index = parseInt(archInp?.value || '0', 10);
                    state.editorBuffer.secondary_image_index = parseInt(stripInp?.value || '1', 10);
                }
                syncEmeraldDockUi();
                refreshEditorPreview(tpl);
                return;
            }

            const gallerySlotBtn = e.target.closest('[data-pcs-gallery-slot-btn]');
            if (gallerySlotBtn) {
                state.editorGallerySlot = parseInt(gallerySlotBtn.getAttribute('data-pcs-gallery-slot-btn') || '0', 10);
                syncGalleryDockUi();
                return;
            }

            const galleryPick = e.target.closest('[data-pcs-gallery-pick]');
            if (galleryPick) {
                const idx = parseInt(galleryPick.getAttribute('data-pcs-img-idx') || '0', 10);
                const slot = state.editorGallerySlot ?? 0;
                const hidden = controls.querySelector(`[data-pcs-gallery-slot="${slot}"]`);
                if (hidden) hidden.value = String(idx);
                const slots = [0, 1, 2].map((s) => {
                    const inp = controls.querySelector(`[data-pcs-gallery-slot="${s}"]`);
                    const fallback = editorImageOrderForGallery(propertyImageList(), state.editorBuffer || {})[s];
                    const v = parseInt(inp?.value || String(fallback), 10);
                    return Number.isFinite(v) ? v : s;
                });
                slots[slot] = idx;
                if (state.editorBuffer) {
                    state.editorBuffer.image_order = buildGalleryImageOrder(propertyImageList(), slots);
                }
                syncGalleryDockUi();
                refreshEditorPreview(tpl);
                return;
            }

            if (e.target.closest('[data-pcs-gallery-autofill]')) {
                const imgsList = propertyImageList();
                const picks = imgsList.map((_, i) => i);
                const slots = [0, 1, 2].map((s) => picks[s] ?? picks[0] ?? 0);
                if (state.editorBuffer) {
                    state.editorBuffer.image_order = buildGalleryImageOrder(imgsList, slots);
                }
                [0, 1, 2].forEach((s) => {
                    const hid = controls.querySelector(`[data-pcs-gallery-slot="${s}"]`);
                    if (hid) hid.value = String(slots[s]);
                });
                syncGalleryDockUi();
                refreshEditorPreview(tpl);
                return;
            }

            if (e.target.closest('[data-pcs-gallery-rotate]')) {
                const imgsList = propertyImageList();
                const ord = editorImageOrderForGallery(imgsList, state.editorBuffer || {});
                const rotated = [ord[1], ord[2], ord[0]];
                if (state.editorBuffer) {
                    state.editorBuffer.image_order = buildGalleryImageOrder(imgsList, rotated);
                }
                [0, 1, 2].forEach((s) => {
                    const hid = controls.querySelector(`[data-pcs-gallery-slot="${s}"]`);
                    if (hid) hid.value = String(rotated[s]);
                });
                syncGalleryDockUi();
                refreshEditorPreview(tpl);
                return;
            }

            const typeTab = e.target.closest('[data-pcs-type-tab]');
            if (typeTab) {
                const role = typeTab.getAttribute('data-pcs-type-tab');
                const studio = typeTab.closest('[data-pcs-type-studio]');
                if (studio && role) {
                    studio.querySelectorAll('[data-pcs-type-tab]').forEach((btn) => {
                        const on = btn === typeTab;
                        btn.classList.toggle('is-active', on);
                        btn.setAttribute('aria-selected', on ? 'true' : 'false');
                    });
                    studio.querySelectorAll('[data-pcs-type-panel]').forEach((panel) => {
                        const on = panel.getAttribute('data-pcs-type-panel') === role;
                        panel.classList.toggle('is-active', on);
                        panel.hidden = !on;
                    });
                    if (role === 'headline' || role === 'price' || role === 'meta') {
                        selectEditorTextRole(role, $('#pcsEditorPreview'));
                    }
                }
                return;
            }

            const metaScale = e.target.closest('[data-pcs-edit-meta-scale]');
            if (metaScale && state.editorBuffer) {
                const v = parseInt(metaScale.value, 10);
                setTextRoleScale(state.editorBuffer, 'meta', v);
                const lbl = controls.querySelector('[data-pcs-meta-scale-val]');
                if (lbl) lbl.textContent = `${v}%`;
                refreshEditorPreview(tpl);
                selectEditorTextRole('meta', $('#pcsEditorPreview'));
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

            const hw = e.target.closest('[data-pcs-headline-weight]');
            if (hw) {
                hw.closest('.pcs-type-segment')?.querySelectorAll('[data-pcs-headline-weight]').forEach((b) => {
                    const on = b === hw;
                    b.classList.toggle('is-active', on);
                    b.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }
            const pw = e.target.closest('[data-pcs-price-weight]');
            if (pw) {
                pw.closest('.pcs-type-segment')?.querySelectorAll('[data-pcs-price-weight]').forEach((b) => {
                    const on = b === pw;
                    b.classList.toggle('is-active', on);
                    b.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                refreshEditorPreview(tpl);
                return;
            }
            const textToggle = e.target.closest(
                '[data-pcs-headline-italic], [data-pcs-headline-underline], [data-pcs-price-italic], [data-pcs-price-underline]',
            );
            if (textToggle) {
                textToggle.classList.toggle('is-active');
                const on = textToggle.classList.contains('is-active');
                textToggle.setAttribute('aria-pressed', on ? 'true' : 'false');
                refreshEditorPreview(tpl);
                return;
            }
            const colorPreset = e.target.closest('[data-pcs-edit-color-preset]');
            if (colorPreset) {
                const role = colorPreset.getAttribute('data-pcs-edit-color-preset');
                const hex = colorPreset.getAttribute('data-color');
                const inp = controls.querySelector(`[data-pcs-edit-color="${role}"]`);
                const wrap = controls.querySelector(`[data-pcs-type-colors="${role}"]`);
                if (inp && hex) inp.value = hex;
                wrap?.querySelector('[data-pcs-edit-color-auto]')?.classList.remove('is-active');
                wrap?.querySelectorAll('[data-pcs-edit-color-preset]').forEach((b) => {
                    b.classList.toggle('is-active', b === colorPreset);
                });
                refreshEditorPreview(tpl);
                return;
            }
            const colorAuto = e.target.closest('[data-pcs-edit-color-auto]');
            if (colorAuto) {
                const role = colorAuto.getAttribute('data-pcs-edit-color-auto');
                const wrap = controls.querySelector(`[data-pcs-type-colors="${role}"]`);
                wrap?.querySelectorAll('[data-pcs-edit-color-preset]').forEach((b) => b.classList.remove('is-active'));
                wrap?.querySelectorAll('[data-pcs-edit-color-auto]').forEach((b) => {
                    b.classList.toggle('is-active', b === colorAuto);
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

    function openEditor(tpl, storySlideId) {
        if (!state.draft) {
            toast('استودیو هنوز بارگذاری نشده است');
            return;
        }
        state.editorStorySlideId = storySlideId || null;
        let slide = null;
        if (storySlideId) {
            slide = findStorySlide(storySlideId);
            if (!slide) {
                toast('اسلاید استوری یافت نشد');
                state.editorStorySlideId = null;
                return;
            }
            state.format = 'story';
            tpl = storySlideTemplateId(slide);
        }
        state.editorTemplate = tpl;
        state.editorGallerySlot = 0;
        state.editorEmeraldSlot = 0;
        resetEditorPreviewView();
        bindEditorPreviewZoomControls();
        bindEditorPreviewViewEvents();
        if (storySlideId && slide) {
            const imgs = propertyImageList();
            state.editorBuffer = { ...storySlideConf(slide) };
            state.editorSnapshot = JSON.stringify(state.editorBuffer);
            state.editorDirty = false;
        } else {
            initEditorBuffer(tpl);
        }
        const meta = resolveTemplateMeta(tpl);
        const fmtMeta = FORMAT_META[state.format] || FORMAT_META.story;
        const conf = state.editorBuffer;
        const imgs = propertyImageList();
        const galleryOrder = editorImageOrderForGallery(imgs, conf);
        const badgeLabel = slide ? storySlideLabel(slide) : posterDisplayLabel(tpl, state.format);

        setEditorTplBadge({ ...meta, label: badgeLabel });
        const sub = $('#pcsEditorSub');
        if (sub) {
            sub.textContent = slide
                ? 'تنظیمات این اسلاید استوری — رنگ برند و تایپوگرافی فقط روی همین اسلاید'
                : 'تغییرات را در پیش‌نمایش زنده ببینید';
        }
        const fmtPill = $('#pcsEditorFormatPill');
        if (fmtPill) {
            fmtPill.hidden = false;
            fmtPill.innerHTML = `<i class="fas ${fmtMeta.icon}" aria-hidden="true"></i> ${esc(fmtMeta.label)} · ${formatDimsHtml(state.format)}`;
        }
        const dlBtn = $('#pcsEditorDownload');
        if (dlBtn) dlBtn.hidden = false;

        const controls = $('#pcsEditorControls');
        if (controls) {
            const headlineVal = conf.headline || defaultPropertyHeadline();
            const galleryBlock = tpl === 'gallery' && imgs.length
                ? `<section class="pcs-editor__section pcs-editor__section--dock">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-images" aria-hidden="true"></i> چیدمان تصاویر</h4>
                    <p class="pcs-editor__section-hint">یک کتابخانه تصویر — سه بخش پوستر بدون تکرار گرید</p>
                    ${editorGalleryComposer(imgs, galleryOrder)}
                </section>`
                : '';

            controls.innerHTML = `
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-expand" aria-hidden="true"></i> فرمت خروجی</h4>
                    <p class="pcs-editor__section-hint">پیش‌نمایش با همان ابعاد دانلود به‌روز می‌شود</p>
                    <div class="pcs-editor__format-bar" id="pcsEditFormatBar"></div>
                </section>
                ${galleryBlock}
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-pen-fancy" aria-hidden="true"></i> عنوان تبلیغاتی</h4>
                    <p class="pcs-editor__section-hint">متن اصلی روی پوستر — کوتاه و جذاب باشد</p>
                    <div class="pcs-editor__headline-row">
                        <input type="text" id="pcsEditHeadline" class="pcs-input" maxlength="120"
                            placeholder="مثلاً آپارتمان نوساز با نور عالی" value="${esc(headlineVal)}">
                        <button type="button" class="pcs-btn pcs-btn--primary pcs-btn--sm" id="pcsEditHeadlineAi"
                            title="تولید عنوان کوتاه با AI"${cfg.aiEnabled === false ? ' disabled' : ''}>
                            <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i><span>AI</span>
                        </button>
                        <button type="button" class="pcs-btn pcs-btn--soft pcs-btn--sm" id="pcsEditHeadlineFromFile">
                            <i class="fas fa-file-lines" aria-hidden="true"></i> از فایل
                        </button>
                        <button type="button" class="pcs-btn pcs-btn--ghost pcs-btn--sm" id="pcsEditHeadlineClear" title="خالی = عنوان پیش‌فرض فایل">
                            <i class="fas fa-eraser" aria-hidden="true"></i>
                        </button>
                    </div>
                    <div class="pcs-editor__headline-ai" id="pcsEditHeadlineAiPanel" hidden></div>
                    <span class="pcs-editor__meta" id="pcsEditHeadlineCount">${headlineVal.length} کاراکتر · ایده‌آل زیر ${PCS_POSTER_HEADLINE_MAX} برای استوری</span>
                </section>
                ${(tpl === 'emerald_atelier' || tpl === 'pearl_gallery') && imgs.length >= 2
                    ? `<section class="pcs-editor__section pcs-editor__section--dock">
                    <h4 class="pcs-editor__section-title"><i class="fas ${tpl === 'pearl_gallery' ? 'fa-gem' : 'fa-building-columns'}" aria-hidden="true"></i> ${tpl === 'pearl_gallery' ? 'تصاویر گالری مروارید' : 'تصاویر قاب زمرد'}</h4>
                    <p class="pcs-editor__section-hint">${tpl === 'pearl_gallery' ? 'دایره اصلی = تصویر شاخص · دایره مکمل = تصویر دوم' : 'قوس بزرگ = تصویر شاخص · نوار کناری = تصویر دوم'}</p>
                    ${editorEmeraldImageComposer(imgs, conf.primary_image_index, conf.secondary_image_index, tpl)}
                </section>`
                    : tpl !== 'gallery'
                        ? `<section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-image" aria-hidden="true"></i> تصویر شاخص</h4>
                    <p class="pcs-editor__section-hint">از نوار تصاویر یک تصویر شاخص انتخاب کنید</p>
                    ${editorPrimaryPicker(imgs, conf.primary_image_index || 0)}
                </section>`
                        : ''}
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
                ${tpl !== 'gallery' && tpl !== 'emerald_atelier' && tpl !== 'pearl_gallery' ? editorComposeSection(imgs, conf) : ''}
                ${imgs.length > 1 && tpl !== 'gallery' ? `<section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-sort" aria-hidden="true"></i> ترتیب تصاویر فایل</h4>
                    <p class="pcs-editor__section-hint">ترتیب پیش‌فرض فایل — برای قالب‌های تک‌تصویری و گالری داخلی</p>
                    ${editorImageOrderPanel(imgs, conf.image_order)}
                </section>` : ''}
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-adjust" aria-hidden="true"></i> ${tpl === 'gallery' ? 'افکت تصاویر' : 'افکت تصویر شاخص'}</h4>
                    <label class="pcs-editor__range-label">روشنایی <span data-pcs-range-val="brightness">${conf.img_brightness ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="brightness" min="40" max="160" value="${conf.img_brightness ?? 100}">
                    <label class="pcs-editor__range-label">تاری <span data-pcs-range-val="blur">${conf.img_blur ?? 0}px</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="blur" min="0" max="12" value="${conf.img_blur ?? 0}">
                    <label class="pcs-editor__range-label">شفافیت <span data-pcs-range-val="opacity">${conf.img_opacity ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="opacity" min="35" max="100" value="${conf.img_opacity ?? 100}">
                </section>
                ${editorBrandPrimarySection(conf)}
                <section class="pcs-editor__section">
                    <h4 class="pcs-editor__section-title"><i class="fas fa-font" aria-hidden="true"></i> تایپوگرافی</h4>
                    <p class="pcs-editor__section-hint">فونت روی همهٔ متن پوستر است؛ وزن و رنگ عنوان و قیمت را در کارت‌های زیر تنظیم کنید</p>
                    ${editorFontPicker(conf.font_key || 'vazirmatn')}
                    <label class="pcs-editor__range-label">اندازه عنوان <span data-pcs-range-val="headline_scale">${conf.headline_scale ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="headline_scale" min="50" max="180" value="${conf.headline_scale ?? 100}">
                    <label class="pcs-editor__range-label">اندازه قیمت <span data-pcs-range-val="price_scale">${conf.price_scale ?? 100}%</span></label>
                    <input type="range" class="pcs-editor__range" data-pcs-edit-range="price_scale" min="50" max="180" value="${conf.price_scale ?? 100}">
                    ${editorTextStyleControls(conf)}
                </section>
                <div class="pcs-editor__tip">
                    <i class="fas fa-lightbulb" aria-hidden="true"></i>
                    <span>روی پیش‌نمایش، بلوک عنوان / مشخصات / قیمت را کلیک کنید؛ بکشید تا جابه‌جا شود. دستگیره گوشه برای اندازه. تب تایپوگرافی همان بخش انتخاب‌شده را ویرایش می‌کند.</span>
                </div>`;

            bindEditorControlEvents(tpl, controls);
            renderEditorFormatBar(tpl);
            syncCropPresetActive(conf.crop_y ?? 50);
            if (tpl === 'emerald_atelier' || tpl === 'pearl_gallery') syncEmeraldDockUi();
        }

        $('#pcsEditor')?.removeAttribute('hidden');
        $('#pcsLoading')?.setAttribute('hidden', '');
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

    function renderEditorPosterHeadlineSuggestions(titles) {
        const panel = $('#pcsEditHeadlineAiPanel');
        if (!panel) return;
        const list = Array.isArray(titles) ? titles : [];
        if (!list.length) {
            panel.innerHTML = '';
            panel.setAttribute('hidden', '');
            return;
        }
        panel.removeAttribute('hidden');
        panel.innerHTML = `
            <div class="pcs-editor__headline-ai__head">
                <span>پیشنهاد AI — یکی را بزنید</span>
                <button type="button" class="pcs-editor__headline-ai__refresh" id="pcsEditHeadlineAiRefresh" title="تولید دوباره">
                    <i class="fas fa-rotate" aria-hidden="true"></i>
                </button>
            </div>
            <div class="pcs-editor__headline-ai__list" role="list">
                ${list.map((item, index) => {
                    const text = String(item?.text || '').trim();
                    const style = String(item?.style || 'پیشنهاد').trim();
                    const len = text.length;
                    const lenCls = len > PCS_POSTER_HEADLINE_MAX ? ' is-over' : len > PCS_POSTER_HEADLINE_MAX - 4 ? ' is-warn' : '';
                    return `<button type="button" class="pcs-editor__headline-ai__chip" role="listitem"
                        data-pcs-pick-poster-headline="${index}" title="${esc(style)}">
                        <span class="pcs-editor__headline-ai__chip-style">${esc(style)}</span>
                        <span class="pcs-editor__headline-ai__chip-text">${esc(text)}</span>
                        <span class="pcs-editor__headline-ai__chip-len${lenCls}">${len}/${PCS_POSTER_HEADLINE_MAX}</span>
                    </button>`;
                }).join('')}
            </div>`;
    }

    async function runEditorPosterHeadlineAi(triggerBtn) {
        const existing = state.editorPosterHeadlineSuggestions || [];
        if (existing.length && !window.confirm('پیشنهادهای قبلی با نتایج جدید AI جایگزین شوند؟')) {
            return;
        }
        await runAiAction(async () => {
            const data = await aiPost('poster-headlines');
            const incoming = data.data?.titles || [];
            if (!incoming.length) {
                toast('عنوانی از AI دریافت نشد');
                return;
            }
            state.editorPosterHeadlineSuggestions = incoming;
            renderEditorPosterHeadlineSuggestions(incoming);
            toast('عنوان‌های تبلیغاتی آماده است — یکی را انتخاب کنید');
        }, [triggerBtn, $('#pcsEditHeadlineAiRefresh')].filter(Boolean));
    }

    function applyEditorPosterHeadlinePick(index) {
        const titles = state.editorPosterHeadlineSuggestions || [];
        const item = titles[index];
        const text = String(item?.text || '').trim();
        if (!text) return;
        const controls = editorControlsEl();
        const inp = controls?.querySelector('#pcsEditHeadline');
        if (inp) inp.value = text.slice(0, 120);
        const cnt = controls?.querySelector('#pcsEditHeadlineCount');
        if (cnt) cnt.textContent = `${inp.value.length} کاراکتر`;
        refreshEditorPreview(state.editorTemplate);
        controls?.querySelectorAll('[data-pcs-pick-poster-headline]').forEach((btn) => {
            btn.classList.toggle('is-selected', parseInt(btn.getAttribute('data-pcs-pick-poster-headline'), 10) === index);
        });
        toast('عنوان روی پوستر اعمال شد');
    }

    async function aiPost(action, body) {
        const base = String(cfg.aiBaseUrl || '').replace(/\/?$/, '/');
        const res = await fetch(`${base}${action}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
            body: JSON.stringify(body || {}),
            credentials: 'same-origin',
        });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            throw new Error('پاسخ سرور نامعتبر بود');
        }
        if (!res.ok || data.ok === false) {
            throw new Error(data.error || (res.status === 429 ? 'سهمیه AI تمام شده است' : 'خطا'));
        }
        return data;
    }

    function ensureDraftAiShell() {
        if (!state.draft) {
            throw new Error('استودیو هنوز بارگذاری نشده — چند ثانیه صبر کنید و دوباره تلاش کنید');
        }
        state.draft.ai = state.draft.ai || {};
        state.draft.ai.divar = state.draft.ai.divar || { titles: [], body: '', selected_title_index: 0 };
        state.draft.ai.social = state.draft.ai.social || { captions: [], hashtags: [] };
    }

    function setAiButtonsBusy(busy, buttons) {
        (buttons || []).forEach((btn) => {
            if (!btn) return;
            btn.disabled = busy;
            btn.classList.toggle('is-busy', busy);
            btn.setAttribute('aria-busy', busy ? 'true' : 'false');
        });
    }

    async function runAiAction(fn, buttons) {
        if (state.aiInflight) {
            toast('در حال تولید محتوا…');
            return;
        }
        if (cfg.aiEnabled === false) {
            toast('سرویس هوش مصنوعی برای این حساب فعال نیست');
            return;
        }
        state.aiInflight = true;
        setAiButtonsBusy(true, buttons);
        try {
            await fn();
        } finally {
            state.aiInflight = false;
            setAiButtonsBusy(false, buttons);
        }
    }

    function bindPcsAiGeneration() {
        const modal = $('#pcsModal');
        if (!modal || modal.dataset.pcsAiGenBound === '1') return;
        modal.dataset.pcsAiGenBound = '1';

        modal.addEventListener('click', async (e) => {
            const titlesBtn = e.target.closest('#pcsGenDivarTitles');
            const bodyBtn = e.target.closest('#pcsGenDivarBody');
            const socialBtn = e.target.closest('#pcsGenSocial');
            if (!titlesBtn && !bodyBtn && !socialBtn) return;
            if (modal.hasAttribute('hidden')) return;
            e.preventDefault();

            if (titlesBtn) {
                await runAiAction(async () => {
                    try {
                        ensureDraftAiShell();
                        const data = await aiPost('divar-titles');
                        const incoming = data.data?.titles || [];
                        if (!incoming.length) {
                            toast('عنوانی از AI دریافت نشد');
                            return;
                        }
                        const prev = state.draft.ai.divar.titles || [];
                        if (prev.length && !window.confirm('عنوان‌های قبلی با نتایج جدید جایگزین شوند؟')) {
                            return;
                        }
                        state.draft.ai.divar.titles = incoming;
                        scheduleSave();
                        renderDivarTitles();
                        renderAiStrip();
                        toast('عنوان‌ها تولید شد');
                    } catch (err) {
                        toast(err.message || 'خطای AI');
                    }
                }, [titlesBtn]);
                return;
            }

            if (bodyBtn) {
                await runAiAction(async () => {
                    try {
                        ensureDraftAiShell();
                        const style = $('#pcsDivarBodyStyle')?.value || 'formal';
                        const data = await aiPost('divar-body', { style });
                        const body = data.data?.body || '';
                        if (!body.trim()) {
                            toast('متنی از AI دریافت نشد');
                            return;
                        }
                        const bodyEl = $('#pcsDivarBody');
                        if (bodyEl?.value?.trim() && !window.confirm('متن فعلی دیوار جایگزین شود؟')) {
                            return;
                        }
                        state.draft.ai.divar.body = body;
                        state.draft.ai.divar.body_style = style;
                        if (bodyEl) bodyEl.value = body;
                        updateCharCountEl(bodyEl, '#pcsDivarBodyCount');
                        scheduleSave();
                        renderAiStrip();
                        toast('متن آگهی تولید شد');
                    } catch (err) {
                        toast(err.message || 'خطای AI');
                    }
                }, [bodyBtn, $('#pcsDivarBodyStyle')]);
                return;
            }

            if (socialBtn) {
                await runAiAction(async () => {
                    try {
                        ensureDraftAiShell();
                        const data = await aiPost('social');
                        const d = data.data || {};
                        const hasManual = (state.draft.ai.social.captions || []).some((c) => (c.text || '').trim())
                            || ($('#pcsWhatsappText')?.value || '').trim()
                            || ($('#pcsTelegramText')?.value || '').trim();
                        if (hasManual && !window.confirm('متن‌های شبکه‌های اجتماعی جایگزین شوند؟')) {
                            return;
                        }
                        state.draft.ai.social.captions = d.captions || [];
                        state.draft.ai.social.hashtags = d.hashtags || [];
                        state.draft.ai.social.whatsapp_short = d.whatsapp_short || '';
                        state.draft.ai.social.whatsapp_full = d.whatsapp_full || '';
                        state.draft.ai.social.telegram = d.telegram || '';
                        state.draft.ai.social.ctas = d.ctas || [];
                        syncFormFromDraft();
                        scheduleSave();
                        renderAiStrip();
                        toast('محتوای شبکه‌ها تولید شد');
                    } catch (err) {
                        toast(err.message || 'خطای AI');
                    }
                }, [socialBtn]);
            }
        });
    }

    function bindEvents() {
        bindEditorPreviewZoomControls();
        bindEditorPreviewViewEvents();
        bindEditorSettingsDelegation();
        if (!document.body.dataset.pcsAiCopyBound) {
            document.body.dataset.pcsAiCopyBound = '1';
            bindAiCopyFieldButtons();
        }
        document.addEventListener('input', (e) => {
            const id = e.target?.id;
            if (!id || !e.target.closest('#pcsModal')) return;
            if (id === 'pcsDivarBody' || id === 'pcsHashtags' || id === 'pcsWhatsappText' || id === 'pcsTelegramText') {
                scheduleSave();
                if (id === 'pcsDivarBody') updateCharCountEl(e.target, '#pcsDivarBodyCount');
                if (id === 'pcsHashtags') renderHashtagPreview();
            }
        });
        document.addEventListener('change', (e) => {
            if (e.target?.id !== 'pcsDivarBodyStyle') return;
            if (!e.target.closest('#pcsModal')) return;
            ensureDraftAiShell();
            state.draft.ai.divar.body_style = e.target.value || 'formal';
            scheduleSave();
        });
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
        bindPcsAiGeneration();
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
            if (state.exportInflight) return;
            state.exportInflight = true;
            const btn = $('#pcsDownloadAll');
            if (btn) btn.disabled = true;
            let okCount = 0;
            let failCount = 0;
            try {
                await ensureLibs();
                await ensurePersianFonts();
                const zip = new JSZip();
                for (const tpl of posterTemplatesForSession()) {
                    const host = createExportHost(buildCanvasHtml(tpl, state.format), state.format);
                    const canvas = host.querySelector('.pcs-canvas');
                    try {
                        const shot = await rasterizeCanvas(canvas, state.format);
                        const { blob, ext } = await rasterCanvasToBlob(shot);
                        if (!blob) throw new Error('empty blob');
                        zip.file(`${tpl}-${state.format}.${ext}`, blob);
                        okCount += 1;
                    } catch (_) {
                        failCount += 1;
                    }
                    host.remove();
                }
                if (!okCount) {
                    toast('هیچ پوستری برای ZIP تولید نشد');
                    return;
                }
                const out = await zip.generateAsync({ type: 'blob' });
                const objUrl = URL.createObjectURL(out);
                const a = document.createElement('a');
                a.href = objUrl;
                a.download = `property-${cfg.propertyId}-posters.zip`;
                a.click();
                URL.revokeObjectURL(objUrl);
                toast(failCount ? `${okCount} فایل OK — ${failCount} خطا` : 'فایل ZIP آماده شد');
            } catch (_) {
                toast('خطا در ساخت ZIP');
            } finally {
                state.exportInflight = false;
                if (btn) btn.disabled = false;
            }
        });
        $('#pcsOpenSettings')?.addEventListener('click', openSettingsSheet);
        $('#pcsOpenSettingsHead')?.addEventListener('click', openSettingsSheet);
        $('#pcsFooterSettings')?.addEventListener('click', openSettingsSheet);
        $$('[data-pcs-settings-close]').forEach((el) => el.addEventListener('click', closeSettingsSheet));
        $('#pcsEditorClose')?.addEventListener('click', () => closeEditor());
        $('#pcsEditorBack')?.addEventListener('click', () => closeEditor());
        $('#pcsEditorCancel')?.addEventListener('click', () => closeEditor());
        $('#pcsEditorSave')?.addEventListener('click', () => {
            const tpl = state.editorTemplate;
            if (!tpl || !state.draft) return;
            const wasStory = !!state.editorStorySlideId;
            commitEditorToDraft(tpl);
            scheduleSave();
            renderPosters();
            renderStoryboard();
            closeEditor(true);
            toast(wasStory ? 'تغییرات استوری ذخیره شد' : 'تغییرات پوستر ذخیره شد');
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
            if (!window.confirm('تنظیمات به حالت پیش‌فرض برگردد؟')) return;
            if (state.editorStorySlideId) {
                const slide = findStorySlide(state.editorStorySlideId);
                if (slide) {
                    const ref = storySlideCatalogRef(slide.id);
                    slide.poster = ref?.poster ? { ...ref.poster } : {};
                    scheduleSave();
                    openEditor(storySlideTemplateId(slide), slide.id);
                    toast('استوری به پیش‌فرض برگشت');
                }
                return;
            }
            state.draft.posters = state.draft.posters || {};
            state.draft.posters[tpl] = null;
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

    function bootPcs() {
        bindEvents();
        document.addEventListener('touchmove', onPcsTouchMove, { passive: false });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootPcs);
    } else {
        bootPcs();
    }
})();
