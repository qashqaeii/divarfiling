/**
 * Layer editor shell — orchestrates scene state, UI, preview, save hooks.
 */
(function (global) {
    'use strict';

    const Schema = global.PCSSchema;
    const Coords = global.PCSCoords;
    const History = global.PCSHistory;
    const Renderer = global.PCSSceneRenderer;
    const Interaction = global.PCSInteraction;
    const Bindings = global.PCSBindings;
    const Templates = global.PCSTemplateScenes;

    const TOOLS = [
        { id: 'poster', icon: 'fa-sliders', label: 'تنظیمات پوستر' },
        { id: 'select', icon: 'fa-arrow-pointer', label: 'انتخاب' },
        { id: 'text', icon: 'fa-font', label: 'متن' },
        { id: 'images', icon: 'fa-image', label: 'تصاویر' },
        { id: 'property', icon: 'fa-building', label: 'اطلاعات ملک' },
        { id: 'layers', icon: 'fa-layer-group', label: 'لایه‌ها' },
        { id: 'template', icon: 'fa-swatchbook', label: 'قالب' },
    ];

    function isMob() {
        return global.PCSBridge?.isMobileViewport?.()
            ?? window.matchMedia('(max-width: 768px)').matches;
    }

    function syncMobLayout() {
        const editor = document.getElementById('pcsEditor');
        const workspace = editor?.querySelector('.pcs-le-workspace');
        const panel = document.getElementById('pcsLePanel');
        if (!editor || !workspace) return;
        const mob = isMob();
        editor.classList.toggle('pcs-editor--layer-le', session.active && mob);
        workspace.classList.toggle('pcs-le-workspace--mob', mob);
        if (!mob || !panel) return;
        const expandTools = new Set(['property', 'text', 'images', 'layers', 'template', 'poster']);
        const hasSelection = session.selection.length > 0;
        const shouldOpen = expandTools.has(session.tool) || hasSelection;
        panel.classList.toggle('pcs-le-panel--sheet-open', shouldOpen);
        panel.classList.toggle('is-collapsed', !shouldOpen && session.tool === 'select');
    }

    const session = {
        active: false,
        scene: null,
        posterConf: null,
        view: null,
        history: null,
        tool: 'select',
        selection: [],
        interaction: null,
        chromeEl: null,
        tpl: '',
        formatKey: 'story',
        ctx: null,
        onDirty: null,
        onCommitScene: null,
    };

    function syncPanelMode() {
        const layerPane = document.getElementById('pcsLePanelBody');
        const posterPane = document.getElementById('pcsLePosterPane');
        const posterMode = session.tool === 'poster';
        if (layerPane) layerPane.hidden = posterMode;
        if (posterPane) posterPane.hidden = !posterMode;
        if (posterMode) {
            setPanelTitle('تنظیمات پوستر');
            setPanelSubtitle('فرمت، عنوان، تصویر و تایپوگرافی کلی پوستر');
        }
        syncMobLayout();
    }

    function openPosterSettings() {
        session.tool = 'poster';
        syncPanelMode();
        renderToolbar(document.getElementById('pcsLeTools'));
    }

    function leavePosterSettings(nextTool) {
        session.tool = nextTool || 'select';
        syncPanelMode();
        renderToolbar(document.getElementById('pcsLeTools'));
        renderPanel(document.getElementById('pcsLePanelBody'));
    }

    function ensureScene(conf, ctx) {
        if (!Templates?.resolveSceneForPreview && !Templates?.buildInitialScene) {
            throw new Error('ماژول قالب‌های PCS لود نشده — یک بار Ctrl+F5 بزنید');
        }
        let scene;
        if (Templates.resolveSceneForPreview) {
            scene = Templates.resolveSceneForPreview(conf, ctx);
        } else {
            const base = Schema.emptyScene(ctx.templateId, ctx.formatKey, ctx.formats);
            if (conf?.scene && conf.scene.schemaVersion >= 2) {
                const normalized = Schema.normalizeScene(conf.scene, ctx.templateId, ctx.formatKey, ctx.formats);
                scene = Templates.mergeMissingTemplateLayers(normalized, conf, ctx, base);
            } else {
                scene = Templates.buildInitialScene(conf, ctx, base);
            }
        }
        if (scene && Schema.applySceneCanvasFormat) {
            Schema.applySceneCanvasFormat(scene, ctx.formatKey, ctx.formats);
        }
        return Templates.normalizeSceneLayerOrder
            ? Templates.normalizeSceneLayerOrder(scene)
            : scene;
    }

    function syncSceneToPosterConf(conf, scene) {
        conf.scene = Schema.normalizeScene(scene, scene.templateId, scene.canvas?.format);
        conf.text_layout = conf.text_layout || {};
        scene.layers.forEach((layer) => {
            if (!layer.templateRole) return;
            conf.text_layout[layer.templateRole] = { x: 0, y: 0, s: 100 };
        });
        return conf;
    }

    function renderToolbar(sidebarEl) {
        if (!sidebarEl) return;
        sidebarEl.innerHTML = TOOLS.map((t) => {
            const active = session.tool === t.id;
            return `
            <button type="button" class="pcs-le-tool${active ? ' is-active' : ''}"
                data-pcs-le-tool="${t.id}" title="${t.label}" aria-label="${t.label}">
                <i class="fas ${t.icon}" aria-hidden="true"></i>
                <span class="pcs-le-tool__label">${t.label}</span>
            </button>`;
        }).join('');
        sidebarEl.querySelectorAll('[data-pcs-le-tool]').forEach((btn) => {
            btn.addEventListener('click', () => {
                session.tool = btn.getAttribute('data-pcs-le-tool') || 'select';
                syncPanelMode();
                syncMobLayout();
                if (session.tool !== 'poster') {
                    renderPanel(document.getElementById('pcsLePanelBody'));
                }
                renderToolbar(sidebarEl);
            });
        });
    }

    const TYPE_LABELS = {
        text: 'متن',
        bound_text: 'متن',
        image: 'تصویر',
        template_frame: 'قاب',
        shape: 'پس‌زمینه',
        decor: 'تزئین',
    };

    function setPanelTitle(title) {
        const el = document.getElementById('pcsLePanelTitle');
        if (el) el.textContent = title;
    }

    function setPanelSubtitle(text) {
        const el = document.getElementById('pcsLePanelSub');
        if (el) el.textContent = text || '';
    }

    const TYPE_ICONS = {
        text: 'fa-font',
        bound_text: 'fa-link',
        image: 'fa-image',
        template_frame: 'fa-border-all',
        shape: 'fa-square',
        decor: 'fa-star',
    };

    function updateShellMeta() {
        const meta = document.getElementById('pcsLeCanvasMeta');
        const hint = document.getElementById('pcsLeCanvasHint');
        if (!session.scene || !meta) return;
        const w = session.scene.canvas.width;
        const h = session.scene.canvas.height;
        const fmtLabels = { story: 'استوری', post: 'پست', square: 'مربع' };
        const fmt = fmtLabels[session.formatKey] || session.formatKey;
        const n = session.scene.layers.filter((l) => l.visible).length;
        const sel = selectedLayer();
        meta.textContent = `${fmt} · ${w}×${h} · ${n} لایه${sel ? ` · ${sel.name}` : ''}`;
        if (hint) {
            hint.textContent = sel && !sel.locked
                ? 'گوشه‌های بنفش: اندازه · درگ: جابه‌جایی · Delete: حذف'
                : 'یک لایه روی بوم انتخاب کنید یا از «اطلاعات ملک» المان اضافه کنید';
        }
    }

    function syncLegacyConfToScene(conf) {
        if (!session.scene || !conf) return;
        const hero = session.scene.layers.find((l) => l.id === 'hero-image');
        if (hero) {
            hero.imageIndex = conf.primary_image_index ?? 0;
            hero.style = hero.style || {};
            hero.style.cropPanY = conf.crop_y ?? 50;
            if (conf.img_brightness != null) hero.style.brightness = conf.img_brightness;
            if (conf.img_blur != null) hero.style.blur = conf.img_blur;
            if (conf.img_opacity != null) hero.style.imgOpacity = conf.img_opacity;
            if (conf.hero_warmth) hero.style.warmth = conf.hero_warmth;
            if (conf.hero_vignette != null) hero.style.vignette = conf.hero_vignette;
        }
        const accent = session.scene.layers.find((l) => l.id === 'accent-image' || l.id === 'strip-image');
        if (accent && conf.secondary_image_index != null) {
            accent.imageIndex = conf.secondary_image_index;
        }
        const headline = session.scene.layers.find((l) => l.id === 'headline-1');
        if (headline && conf.headline) {
            headline.text = conf.headline;
        }
    }

    function duplicateSelectedLayer() {
        const layer = selectedLayer();
        if (!layer || layer.locked) return;
        const copy = JSON.parse(JSON.stringify(layer));
        copy.id = Schema.uid(layer.type === 'image' ? 'img' : 'text');
        copy.name = `${layer.name} (کپی)`;
        copy.x += 24;
        copy.y += 24;
        History.checkpoint(session.history, session.scene);
        session.scene.layers.push(copy);
        session.scene.layerOrder.push(copy.id);
        session.selection = [copy.id];
        refreshPreview();
        session.onDirty?.();
        renderPanel(document.getElementById('pcsLePanelBody'));
        syncInteractionSelection();
    }

    function selectedLayer() {
        if (session.selection.length !== 1 || !session.scene) return null;
        return session.scene.layers.find((l) => l.id === session.selection[0]) || null;
    }

    function deleteLayerById(id) {
        if (!session.scene || !id) return;
        const layer = session.scene.layers.find((l) => l.id === id);
        if (!layer || layer.locked) return;
        History.checkpoint(session.history, session.scene);
        session.scene.layers = session.scene.layers.filter((l) => l.id !== id);
        session.scene.layerOrder = (session.scene.layerOrder || []).filter((x) => x !== id);
        session.selection = session.selection.filter((x) => x !== id);
        refreshPreview();
        session.onDirty?.();
        renderPanel(document.getElementById('pcsLePanelBody'));
    }

    function addFreeTextLayer() {
        if (!session.scene) return;
        const w = session.scene.canvas.width;
        const h = session.scene.canvas.height;
        const id = Schema.uid('text');
        const layer = {
            id,
            type: 'text',
            name: 'متن جدید',
            visible: true,
            locked: false,
            parentId: null,
            x: Math.round(w * 0.12),
            y: Math.round(h * 0.42),
            width: Math.round(w * 0.76),
            height: 72,
            rotation: 0,
            opacity: 1,
            text: 'متن جدید',
            style: {
                fontKey: 'vazirmatn',
                fontSize: 36,
                fontWeight: 800,
                fill: '#1e293b',
                align: 'right',
                direction: 'rtl',
            },
        };
        History.checkpoint(session.history, session.scene);
        session.scene.layers.push(layer);
        session.scene.layerOrder.push(id);
        session.selection = [id];
        refreshPreview();
        session.onDirty?.();
        renderPanel(document.getElementById('pcsLePanelBody'));
        syncInteractionSelection();
    }

    function applyLayerGeometry(layer, patch) {
        if (!layer || layer.locked) return;
        History.pushHistory(session.history, session.scene);
        ['x', 'y', 'width', 'height'].forEach((k) => {
            if (patch[k] == null) return;
            const n = parseInt(patch[k], 10);
            if (Number.isFinite(n)) layer[k] = Math.max(k === 'width' || k === 'height' ? 24 : -9999, n);
        });
        const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
        if (canvas) Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf);
        renderChrome();
        session.onDirty?.();
    }

    function escAttr(s) {
        const fn = global.PCSBridge?.esc;
        return fn ? fn(s) : String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    }

    function fillToHex(fill) {
        const f = String(fill || '').trim();
        if (/^#[0-9a-fA-F]{6}$/.test(f) || /^#[0-9a-fA-F]{3}$/.test(f)) return f;
        return '#1e293b';
    }

    function previewLayer(layer) {
        if (layer?.type === 'image') {
            refreshPreview();
            return;
        }
        const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
        if (canvas && Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf)) {
            renderChrome();
            session.onDirty?.();
            return;
        }
        refreshPreview();
    }

    function isHeroImageLayer(layer) {
        return layer?.type === 'image' && (layer.id === 'hero-image' || layer.templateRole === 'hero');
    }

    function imageStyleValues(layer) {
        const st = layer.style || {};
        const conf = session.posterConf || {};
        const hero = isHeroImageLayer(layer);
        return {
            cropY: st.cropPanY ?? (hero ? conf.crop_y : 50) ?? 50,
            brightness: st.brightness ?? (hero ? conf.img_brightness : 100) ?? 100,
            blur: st.blur ?? (hero ? conf.img_blur : 0) ?? 0,
            imgOpacity: st.imgOpacity ?? (hero ? conf.img_opacity : 100) ?? 100,
            warmth: st.warmth ?? (hero ? conf.hero_warmth : 'neutral') ?? 'neutral',
            vignette: st.vignette ?? (hero ? conf.hero_vignette : 0) ?? 0,
        };
    }

    function syncPosterConfFromHeroLayer(layer) {
        if (!session.posterConf || !isHeroImageLayer(layer)) return;
        const st = layer.style || {};
        const conf = session.posterConf;
        if (st.cropPanY != null) conf.crop_y = st.cropPanY;
        if (st.brightness != null) conf.img_brightness = st.brightness;
        if (st.blur != null) conf.img_blur = st.blur;
        if (st.imgOpacity != null) conf.img_opacity = st.imgOpacity;
        if (st.warmth) conf.hero_warmth = st.warmth;
        if (st.vignette != null) conf.hero_vignette = st.vignette;
        if (layer.imageIndex != null) conf.primary_image_index = layer.imageIndex;
    }

    function patchImageStyle(layer, patch, withHistory) {
        if (!layer) return;
        layer.style = layer.style || {};
        Object.assign(layer.style, patch);
        if (withHistory) History.pushHistory(session.history, session.scene, 'imgStyle');
        syncPosterConfFromHeroLayer(layer);
        previewLayer(layer);
    }

    function renderImageInspectorSection(layer) {
        const imgs = session.ctx?.images || [];
        const idx = Math.min(imgs.length - 1, Math.max(0, layer.imageIndex ?? 0));
        const v = imageStyleValues(layer);
        const filmstrip = global.PCSBridge?.editorAssetFilmstrip
            ? global.PCSBridge.editorAssetFilmstrip(imgs, idx, 'data-pcs-le-img-pick')
            : '';
        const warmthOpts = [
            ['neutral', 'خنثی'],
            ['warm', 'گرم'],
            ['cool', 'سرد'],
        ];
        return `
            <div class="pcs-le-inspector__section">
                <span class="pcs-le-inspector__label">منبع تصویر</span>
                <p class="pcs-le-inspector__hint">از تصاویر همین فایل ملک — تصویر ${idx + 1} از ${imgs.length || 0}</p>
                ${filmstrip || '<p class="pcs-le-inspector__hint">تصویری در فایل نیست.</p>'}
            </div>
            <div class="pcs-le-inspector__section">
                <span class="pcs-le-inspector__label">قاب‌بندی</span>
                <div class="pcs-le-type__chips" role="group" aria-label="پیش‌تنظیم قاب">
                    <button type="button" class="pcs-le-type__chip${Math.abs(v.cropY - 18) <= 8 ? ' is-active' : ''}" data-pcs-le-crop-preset="18">بالا</button>
                    <button type="button" class="pcs-le-type__chip${Math.abs(v.cropY - 50) <= 8 ? ' is-active' : ''}" data-pcs-le-crop-preset="50">وسط</button>
                    <button type="button" class="pcs-le-type__chip${Math.abs(v.cropY - 82) <= 8 ? ' is-active' : ''}" data-pcs-le-crop-preset="82">پایین</button>
                </div>
                <div class="pcs-le-inspector__row">
                    <span class="pcs-le-inspector__label">موقعیت عمودی</span>
                    <span class="pcs-le-inspector__val" data-pcs-le-crop-val>${Math.round(v.cropY)}%</span>
                </div>
                <input type="range" class="pcs-le-inspector__range" min="0" max="100" value="${Math.round(v.cropY)}" data-pcs-le-crop-y ${layer.locked ? '' : ''}>
            </div>
            <div class="pcs-le-inspector__section">
                <span class="pcs-le-inspector__label">افکت تصویر</span>
                <div class="pcs-le-inspector__row">
                    <span class="pcs-le-inspector__label">روشنایی</span>
                    <span class="pcs-le-inspector__val" data-pcs-le-bright-val>${v.brightness}%</span>
                </div>
                <input type="range" class="pcs-le-inspector__range" min="40" max="160" value="${v.brightness}" data-pcs-le-brightness>
                <div class="pcs-le-inspector__row">
                    <span class="pcs-le-inspector__label">تاری</span>
                    <span class="pcs-le-inspector__val" data-pcs-le-blur-val>${v.blur}px</span>
                </div>
                <input type="range" class="pcs-le-inspector__range" min="0" max="12" value="${v.blur}" data-pcs-le-blur>
                <div class="pcs-le-inspector__row">
                    <span class="pcs-le-inspector__label">شفافیت تصویر</span>
                    <span class="pcs-le-inspector__val" data-pcs-le-imgop-val>${v.imgOpacity}%</span>
                </div>
                <input type="range" class="pcs-le-inspector__range" min="35" max="100" value="${v.imgOpacity}" data-pcs-le-img-opacity>
            </div>
            <div class="pcs-le-inspector__section">
                <span class="pcs-le-inspector__label">دمای تصویر</span>
                <div class="pcs-le-type__chips" role="group">
                    ${warmthOpts.map(([key, label]) => `
                    <button type="button" class="pcs-le-type__chip${v.warmth === key ? ' is-active' : ''}" data-pcs-le-warmth="${key}">${label}</button>`).join('')}
                </div>
                <div class="pcs-le-inspector__row">
                    <span class="pcs-le-inspector__label">وینیت</span>
                    <span class="pcs-le-inspector__val" data-pcs-le-vig-val>${v.vignette}%</span>
                </div>
                <input type="range" class="pcs-le-inspector__range" min="0" max="80" value="${v.vignette}" data-pcs-le-vignette>
            </div>`;
    }

    function bindImageInspectorControls(bodyEl, layer) {
        bodyEl.querySelectorAll('[data-pcs-le-img-pick]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const i = parseInt(btn.getAttribute('data-pcs-img-idx') || '0', 10);
                layer.imageIndex = i;
                History.pushHistory(session.history, session.scene, 'imageIndex');
                syncPosterConfFromHeroLayer(layer);
                renderPanel(document.getElementById('pcsLePanelBody'));
                previewLayer(layer);
            });
        });
        bodyEl.querySelectorAll('[data-pcs-le-crop-preset]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const val = parseInt(btn.getAttribute('data-pcs-le-crop-preset') || '50', 10);
                patchImageStyle(layer, { cropPanY: val }, true);
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
        const cropRange = bodyEl.querySelector('[data-pcs-le-crop-y]');
        cropRange?.addEventListener('input', () => {
            const val = parseInt(cropRange.value, 10);
            patchImageStyle(layer, { cropPanY: val }, false);
            bodyEl.querySelector('[data-pcs-le-crop-val]').textContent = `${val}%`;
        });
        cropRange?.addEventListener('change', () => {
            patchImageStyle(layer, { cropPanY: parseInt(cropRange.value, 10) }, true);
        });
        const bindRange = (sel, key, valSel, fmt) => {
            const inp = bodyEl.querySelector(sel);
            inp?.addEventListener('input', () => {
                const n = parseInt(inp.value, 10);
                patchImageStyle(layer, { [key]: n }, false);
                const lbl = bodyEl.querySelector(valSel);
                if (lbl) lbl.textContent = fmt(n);
            });
            inp?.addEventListener('change', () => {
                patchImageStyle(layer, { [key]: parseInt(inp.value, 10) }, true);
            });
        };
        bindRange('[data-pcs-le-brightness]', 'brightness', '[data-pcs-le-bright-val]', (n) => `${n}%`);
        bindRange('[data-pcs-le-blur]', 'blur', '[data-pcs-le-blur-val]', (n) => `${n}px`);
        bindRange('[data-pcs-le-img-opacity]', 'imgOpacity', '[data-pcs-le-imgop-val]', (n) => `${n}%`);
        bindRange('[data-pcs-le-vignette]', 'vignette', '[data-pcs-le-vig-val]', (n) => `${n}%`);
        bodyEl.querySelectorAll('[data-pcs-le-warmth]').forEach((btn) => {
            btn.addEventListener('click', () => {
                patchImageStyle(layer, { warmth: btn.getAttribute('data-pcs-le-warmth') || 'neutral' }, true);
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
    }

    function addImageLayer(preferredIndex) {
        if (!session.scene) return;
        const imgs = session.ctx?.images || [];
        const w = session.scene.canvas.width;
        const h = session.scene.canvas.height;
        const id = Schema.uid('img');
        const nImg = session.scene.layers.filter((l) => l.type === 'image').length;
        const layer = {
            id,
            type: 'image',
            name: `تصویر ${nImg + 1}`,
            visible: true,
            locked: false,
            parentId: null,
            x: Math.round(w * 0.08),
            y: Math.round(h * 0.12),
            width: Math.round(w * 0.84),
            height: Math.round(h * 0.38),
            rotation: 0,
            opacity: 1,
            imageIndex: preferredIndex ?? 0,
            style: {
                objectFit: 'cover',
                cropPanX: 50,
                cropPanY: 50,
                brightness: 100,
                blur: 0,
                imgOpacity: 100,
                warmth: 'neutral',
                vignette: 0,
            },
        };
        History.checkpoint(session.history, session.scene);
        session.scene.layers.push(layer);
        session.scene.layerOrder.push(id);
        session.selection = [id];
        refreshPreview();
        session.onDirty?.();
        session.tool = 'select';
        syncPanelMode();
        renderToolbar(document.getElementById('pcsLeTools'));
        renderPanel(document.getElementById('pcsLePanelBody'));
        syncInteractionSelection();
    }

    function previewTextLayer(layer) {
        const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
        if (canvas) Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf);
        renderChrome();
        session.onDirty?.();
    }

    async function ensureLayerFontLoaded(fontKey) {
        const bridge = global.PCSBridge;
        if (bridge?.ensurePersianFonts) {
            await bridge.ensurePersianFonts();
        }
        const spec = bridge?.PCS_FONTS?.[fontKey || 'vazirmatn']?.load;
        if (spec && document.fonts?.load) {
            try {
                await document.fonts.load(spec);
            } catch (_) { /* noop */ }
        }
    }

    function patchTextStyle(layer, patch, withHistory) {
        if (!layer || layer.locked) return;
        layer.style = layer.style || {};
        Object.assign(layer.style, patch);
        if (withHistory) History.pushHistory(session.history, session.scene, 'style');
        const fontKey = patch.fontKey;
        if (fontKey) {
            ensureLayerFontLoaded(fontKey).then(() => previewTextLayer(layer));
            return;
        }
        previewTextLayer(layer);
    }

    function renderTextTypographyHtml(layer) {
        const st = layer.style || {};
        const fonts = global.PCSBridge?.PCS_FONTS || {};
        const fontKey = st.fontKey || 'vazirmatn';
        const align = st.align || 'right';
        const fw = st.fontWeight || 700;
        const fs = st.fontSize || 32;
        const lh = st.lineHeight || 1.35;
        const fill = st.fill || '#1e293b';
        const hex = fillToHex(fill);
        const weights = [400, 600, 700, 800, 900];
        const locked = layer.locked;
        return `
        <div class="pcs-le-type">
            <span class="pcs-le-inspector__label">تایپوگرافی</span>
            <div class="pcs-le-type__fonts" role="radiogroup" aria-label="فونت">
                ${Object.entries(fonts).map(([key, meta]) => `
                <button type="button" class="pcs-le-type__font${key === fontKey ? ' is-active' : ''}"
                    data-pcs-le-font-key="${key}" style="font-family:${meta.family};" ${locked ? 'disabled' : ''}>${escAttr(meta.label)}</button>`).join('')}
            </div>
            <div class="pcs-le-type__row">
                <span class="pcs-le-inspector__label">اندازه قلم</span>
                <div class="pcs-le-type__size">
                    <input type="number" class="pcs-input pcs-le-type__size-num" min="10" max="200" value="${fs}" data-pcs-le-font-size-num ${locked ? 'disabled' : ''}>
                    <span class="pcs-le-inspector__val">px</span>
                </div>
            </div>
            <input type="range" class="pcs-le-inspector__range" min="10" max="120" value="${Math.min(120, Math.max(10, fs))}" data-pcs-le-font-size ${locked ? 'disabled' : ''}>
            <div class="pcs-le-type__row">
                <span class="pcs-le-inspector__label">وزن</span>
                <div class="pcs-le-type__seg" role="group" aria-label="وزن فونت">
                    ${weights.map((w) => `<button type="button" class="pcs-le-type__seg-btn${Number(fw) === w ? ' is-active' : ''}" data-pcs-le-weight="${w}" ${locked ? 'disabled' : ''}>${w}</button>`).join('')}
                </div>
            </div>
            <div class="pcs-le-type__row">
                <span class="pcs-le-inspector__label">تراز</span>
                <div class="pcs-le-type__seg" role="group" aria-label="تراز متن">
                    <button type="button" class="pcs-le-type__seg-btn${align === 'right' ? ' is-active' : ''}" data-pcs-le-align="right" title="راست" ${locked ? 'disabled' : ''}><i class="fas fa-align-right"></i></button>
                    <button type="button" class="pcs-le-type__seg-btn${align === 'center' ? ' is-active' : ''}" data-pcs-le-align="center" title="وسط" ${locked ? 'disabled' : ''}><i class="fas fa-align-center"></i></button>
                    <button type="button" class="pcs-le-type__seg-btn${align === 'left' ? ' is-active' : ''}" data-pcs-le-align="left" title="چپ" ${locked ? 'disabled' : ''}><i class="fas fa-align-left"></i></button>
                </div>
            </div>
            <div class="pcs-le-type__row pcs-le-type__color">
                <span class="pcs-le-inspector__label">رنگ</span>
                <input type="color" class="pcs-le-type__color-input" value="${hex}" data-pcs-le-fill-color ${locked ? 'disabled' : ''}>
            </div>
            <div class="pcs-le-type__row">
                <span class="pcs-le-inspector__label">فاصله خط</span>
                <input type="range" class="pcs-le-inspector__range pcs-le-type__lh" min="90" max="180" value="${Math.round(lh * 100)}" data-pcs-le-line-height ${locked ? 'disabled' : ''}>
            </div>
            <div class="pcs-le-type__toggs">
                <label class="pcs-le-type__check"><input type="checkbox" data-pcs-le-italic ${st.fontStyle === 'italic' ? 'checked' : ''} ${locked ? 'disabled' : ''}> مورب</label>
                <label class="pcs-le-type__check"><input type="checkbox" data-pcs-le-underline ${st.textDecoration === 'underline' ? 'checked' : ''} ${locked ? 'disabled' : ''}> زیرخط</label>
            </div>
        </div>`;
    }

    function bindTextTypographyControls(bodyEl, layer) {
        const syncUi = () => {
            bodyEl.querySelectorAll('[data-pcs-le-font-key]').forEach((btn) => {
                btn.classList.toggle('is-active', btn.getAttribute('data-pcs-le-font-key') === (layer.style?.fontKey || 'vazirmatn'));
            });
            bodyEl.querySelectorAll('[data-pcs-le-weight]').forEach((btn) => {
                btn.classList.toggle('is-active', Number(btn.getAttribute('data-pcs-le-weight')) === Number(layer.style?.fontWeight || 700));
            });
            bodyEl.querySelectorAll('[data-pcs-le-align]').forEach((btn) => {
                btn.classList.toggle('is-active', btn.getAttribute('data-pcs-le-align') === (layer.style?.align || 'right'));
            });
        };

        bodyEl.querySelectorAll('[data-pcs-le-font-key]').forEach((btn) => {
            btn.addEventListener('click', () => {
                patchTextStyle(layer, { fontKey: btn.getAttribute('data-pcs-le-font-key') || 'vazirmatn' }, true);
                syncUi();
            });
        });
        bodyEl.querySelectorAll('[data-pcs-le-weight]').forEach((btn) => {
            btn.addEventListener('click', () => {
                patchTextStyle(layer, { fontWeight: parseInt(btn.getAttribute('data-pcs-le-weight'), 10) || 700 }, true);
                syncUi();
            });
        });
        bodyEl.querySelectorAll('[data-pcs-le-align]').forEach((btn) => {
            btn.addEventListener('click', () => {
                patchTextStyle(layer, { align: btn.getAttribute('data-pcs-le-align') || 'right' }, true);
                syncUi();
            });
        });

        const applySize = (n, history) => {
            const size = Math.min(200, Math.max(10, parseInt(n, 10) || 32));
            patchTextStyle(layer, { fontSize: size }, history);
            const r = bodyEl.querySelector('[data-pcs-le-font-size]');
            const num = bodyEl.querySelector('[data-pcs-le-font-size-num]');
            if (r) r.value = String(Math.min(120, size));
            if (num) num.value = String(size);
        };

        const fsRange = bodyEl.querySelector('[data-pcs-le-font-size]');
        fsRange?.addEventListener('input', () => applySize(fsRange.value, false));
        fsRange?.addEventListener('change', () => applySize(fsRange.value, true));
        bodyEl.querySelector('[data-pcs-le-font-size-num]')?.addEventListener('change', (ev) => {
            applySize(ev.target.value, true);
        });

        const colorPick = bodyEl.querySelector('[data-pcs-le-fill-color]');
        colorPick?.addEventListener('input', () => {
            patchTextStyle(layer, { fill: colorPick.value }, false);
        });
        colorPick?.addEventListener('change', () => {
            patchTextStyle(layer, { fill: colorPick.value }, true);
        });

        const lh = bodyEl.querySelector('[data-pcs-le-line-height]');
        lh?.addEventListener('input', () => {
            patchTextStyle(layer, { lineHeight: (parseInt(lh.value, 10) || 135) / 100 }, false);
        });
        lh?.addEventListener('change', () => {
            patchTextStyle(layer, { lineHeight: (parseInt(lh.value, 10) || 135) / 100 }, true);
        });

        bodyEl.querySelector('[data-pcs-le-italic]')?.addEventListener('change', (ev) => {
            patchTextStyle(layer, { fontStyle: ev.target.checked ? 'italic' : 'normal' }, true);
        });
        bodyEl.querySelector('[data-pcs-le-underline]')?.addEventListener('change', (ev) => {
            patchTextStyle(layer, { textDecoration: ev.target.checked ? 'underline' : 'none' }, true);
        });
    }

    function bindInspectorControls(bodyEl, layer) {
        if (layer.type === 'text' || layer.type === 'bound_text') {
            bindTextTypographyControls(bodyEl, layer);
        }
        if (layer.type === 'image') {
            bindImageInspectorControls(bodyEl, layer);
        }
        const ta = bodyEl.querySelector('[data-pcs-le-text]');
        ta?.addEventListener('input', () => {
            layer.text = ta.value;
            if (layer.binding) layer.binding = { ...layer.binding, mode: 'override' };
            History.pushHistory(session.history, session.scene, 'text');
            const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
            if (canvas) Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf);
            session.onDirty?.();
        });
        bodyEl.querySelectorAll('[data-pcs-le-geom]').forEach((inp) => {
            inp.addEventListener('change', () => {
                applyLayerGeometry(layer, { [inp.name]: inp.value });
            });
        });
        bodyEl.querySelector('[data-pcs-le-delete]')?.addEventListener('click', () => {
            deleteLayerById(layer.id);
        });
        bodyEl.querySelector('[data-pcs-le-duplicate]')?.addEventListener('click', () => {
            duplicateSelectedLayer();
        });
        const op = bodyEl.querySelector('[data-pcs-le-opacity]');
        op?.addEventListener('input', () => {
            layer.opacity = (parseInt(op.value, 10) || 100) / 100;
            const v = bodyEl.querySelector('[data-pcs-le-op-val]');
            if (v) v.textContent = `${op.value}%`;
            previewLayer(layer);
        });
        bodyEl.querySelector('[data-pcs-le-detach]')?.addEventListener('click', () => {
            if (!layer.binding) return;
            layer.binding = { ...layer.binding, mode: 'detached' };
            History.pushHistory(session.history, session.scene);
            renderPanel(bodyEl);
            session.onDirty?.();
        });
    }

    function renderLayerInspector(bodyEl, layer) {
        if (!layer) return;
        const isText = layer.type === 'text' || layer.type === 'bound_text';
        const isImage = layer.type === 'image';
        const linked = layer.binding?.mode === 'linked';
        const typeLabel = TYPE_LABELS[layer.type] || layer.type;
        const icon = TYPE_ICONS[layer.type] || 'fa-layer-group';
        const opPct = Math.round((layer.opacity != null ? layer.opacity : 1) * 100);
        bodyEl.innerHTML = `
            <div class="pcs-le-inspector">
                <div class="pcs-le-inspector__head">
                    <span class="pcs-le-inspector__type"><i class="fas ${icon}" aria-hidden="true"></i> ${typeLabel}</span>
                    <span class="pcs-le-inspector__name">${layer.name || layer.id}</span>
                    ${layer.locked ? '<span class="pcs-le-badge pcs-le-badge--lock"><i class="fas fa-lock"></i> قفل</span>' : ''}
                </div>
                ${isText ? `
                <div class="pcs-le-inspector__section">
                    <span class="pcs-le-inspector__label">متن</span>
                    <textarea class="pcs-input pcs-le-inspector__textarea" rows="3" data-pcs-le-text>${escAttr(layer.text || '')}</textarea>
                    ${linked ? '<p class="pcs-le-inspector__hint">متصل به ملک — با ویرایش متن، حالت «اتصال» به «دستی» تغییر می‌کند؛ فونت و رنگ همین لایه مستقل می‌ماند.</p>' : ''}
                </div>
                ${renderTextTypographyHtml(layer)}` : ''}
                ${isImage ? renderImageInspectorSection(layer) : ''}
                <div class="pcs-le-inspector__section">
                    <span class="pcs-le-inspector__label">ابعاد و موقعیت</span>
                    <div class="pcs-le-inspector__grid">
                        <label class="pcs-le-inspector__metric">X<input type="number" name="x" class="pcs-input" value="${Math.round(layer.x)}" data-pcs-le-geom ${layer.locked ? 'disabled' : ''}></label>
                        <label class="pcs-le-inspector__metric">Y<input type="number" name="y" class="pcs-input" value="${Math.round(layer.y)}" data-pcs-le-geom ${layer.locked ? 'disabled' : ''}></label>
                        <label class="pcs-le-inspector__metric">عرض<input type="number" name="width" class="pcs-input" value="${Math.round(layer.width)}" data-pcs-le-geom ${layer.locked ? 'disabled' : ''}></label>
                        <label class="pcs-le-inspector__metric">ارتفاع<input type="number" name="height" class="pcs-input" value="${Math.round(layer.height)}" data-pcs-le-geom ${layer.locked ? 'disabled' : ''}></label>
                    </div>
                    <p class="pcs-le-inspector__hint">برای تغییر اندازه، گوشه‌های بنفش را بکشید یا عرض/ارتفاع را تنظیم کنید.</p>
                </div>
                <div class="pcs-le-inspector__section">
                    <div class="pcs-le-inspector__row">
                        <span class="pcs-le-inspector__label">شفافیت</span>
                        <span class="pcs-le-inspector__val" data-pcs-le-op-val>${opPct}%</span>
                    </div>
                    <input type="range" class="pcs-le-inspector__range" min="20" max="100" value="${opPct}" data-pcs-le-opacity ${layer.locked ? 'disabled' : ''}>
                </div>
                <div class="pcs-le-inspector__actions">
                    ${linked ? '<button type="button" class="pcs-le-btn pcs-le-btn--ghost" data-pcs-le-detach>قطع اتصال ملک</button>' : ''}
                    ${layer.locked ? '' : '<button type="button" class="pcs-le-btn pcs-le-btn--ghost" data-pcs-le-duplicate><i class="fas fa-copy"></i> کپی</button>'}
                    ${layer.locked ? '' : '<button type="button" class="pcs-le-btn pcs-le-btn--danger" data-pcs-le-delete><i class="fas fa-trash-can"></i> حذف</button>'}
                </div>
            </div>`;
        bindInspectorControls(bodyEl, layer);
    }

    function canMoveLayerInStack(layerId, direction) {
        const order = session.scene?.layerOrder || [];
        const idx = order.indexOf(layerId);
        if (idx < 0) return false;
        if (direction === 'forward') return idx < order.length - 1;
        if (direction === 'backward') return idx > 0;
        return false;
    }

    /** direction: forward = جلوتر روی بوم، backward = عقب‌تر */
    function moveLayerInStack(layerId, direction) {
        if (!session.scene?.layerOrder || !layerId) return;
        const order = session.scene.layerOrder.slice();
        const idx = order.indexOf(layerId);
        if (idx < 0) return;
        if (direction === 'forward' && idx < order.length - 1) {
            [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
        } else if (direction === 'backward' && idx > 0) {
            [order[idx], order[idx - 1]] = [order[idx - 1], order[idx]];
        } else {
            return;
        }
        session.scene.layerOrder = order;
        History.pushHistory(session.history, session.scene, 'layerOrder');
        refreshPreview();
        session.onDirty?.();
        const listHost = document.querySelector('[data-pcs-le-layers]');
        if (listHost) renderLayersList(listHost);
    }

    function clearLayerDropHints(container) {
        container?.querySelectorAll('[data-pcs-le-layer]').forEach((row) => {
            row.classList.remove('is-drop-before', 'is-drop-after');
        });
    }

    function renderLayersList(container) {
        if (!container || !session.scene) return;
        const layers = Renderer.orderedLayers(session.scene).slice().reverse();
        container.innerHTML = `
            <div class="pcs-le-layers-head">
                <span class="pcs-le-layers-head__title">لایه‌ها</span>
                <button type="button" class="pcs-le-btn pcs-le-btn--sm" data-pcs-le-add-text><i class="fas fa-plus"></i> متن</button>
            </div>
            <p class="pcs-le-inspector__hint pcs-le-layers-hint">بالا = جلوتر روی بوم · با دستگیره بکشید و بین دو لایه رها کنید</p>
            <div class="pcs-le-layers-list" data-pcs-le-layers-list>
            ${layers.map((l, displayIdx) => {
            const sel = session.selection.includes(l.id) ? ' is-selected' : '';
            const eye = l.visible ? 'fa-eye' : 'fa-eye-slash';
            const lock = l.locked ? 'fa-lock' : 'fa-lock-open';
            const typeLabel = TYPE_LABELS[l.type] || l.type;
            return `<div class="pcs-le-layer${sel}${l.locked ? ' is-locked' : ''}${!l.visible ? ' is-hidden-layer' : ''}" data-pcs-le-layer="${l.id}">
                <span class="pcs-le-layer__grip" draggable="true" data-pcs-le-layer-grip="${l.id}" title="جابه‌جایی ترتیب" aria-label="کشیدن برای تغییر ترتیب"><i class="fas fa-grip-vertical" aria-hidden="true"></i></span>
                <span class="pcs-le-layer__rank" aria-hidden="true">${displayIdx + 1}</span>
                <span class="pcs-le-layer__icon"><i class="fas ${TYPE_ICONS[l.type] || 'fa-layer-group'}" aria-hidden="true"></i></span>
                <span class="pcs-le-layer__meta">
                    <span class="pcs-le-layer__name">${l.name}</span>
                    <span class="pcs-le-layer__type">${typeLabel}</span>
                </span>
                <button type="button" class="pcs-le-layer__vis" data-pcs-le-vis="${l.id}" aria-label="نمایش"><i class="fas ${eye}"></i></button>
                <button type="button" class="pcs-le-layer__lock" data-pcs-le-lock="${l.id}" aria-label="قفل"><i class="fas ${lock}"></i></button>
                ${l.locked ? '' : `<button type="button" class="pcs-le-layer__del" data-pcs-le-layer-del="${l.id}" aria-label="حذف"><i class="fas fa-trash-can"></i></button>`}
            </div>`;
        }).join('')}
            </div>`;
        const listEl = container.querySelector('[data-pcs-le-layers-list]');
        let dragLayerId = null;
        container.querySelector('[data-pcs-le-add-text]')?.addEventListener('click', () => addFreeTextLayer());
        container.querySelectorAll('[data-pcs-le-layer-grip]').forEach((grip) => {
            grip.addEventListener('dragstart', (ev) => {
                dragLayerId = grip.getAttribute('data-pcs-le-layer-grip');
                ev.dataTransfer?.setData('application/x-pcs-layer', dragLayerId || '');
                ev.dataTransfer.effectAllowed = 'move';
                grip.closest('[data-pcs-le-layer]')?.classList.add('is-dragging');
            });
            grip.addEventListener('dragend', () => {
                dragLayerId = null;
                clearLayerDropHints(container);
                container.querySelectorAll('.is-dragging').forEach((el) => el.classList.remove('is-dragging'));
            });
        });
        container.querySelectorAll('[data-pcs-le-layer]').forEach((row) => {
            row.addEventListener('dragover', (ev) => {
                if (!ev.dataTransfer?.types?.includes('application/x-pcs-layer')) return;
                ev.preventDefault();
                const rect = row.getBoundingClientRect();
                const before = ev.clientY < rect.top + rect.height / 2;
                clearLayerDropHints(container);
                row.classList.add(before ? 'is-drop-before' : 'is-drop-after');
            });
            row.addEventListener('dragleave', (ev) => {
                if (!row.contains(ev.relatedTarget)) {
                    row.classList.remove('is-drop-before', 'is-drop-after');
                }
            });
            row.addEventListener('drop', (ev) => {
                const fromId = ev.dataTransfer?.getData('application/x-pcs-layer') || dragLayerId;
                const toId = row.getAttribute('data-pcs-le-layer');
                if (!fromId || !toId || fromId === toId) return;
                ev.preventDefault();
                const rect = row.getBoundingClientRect();
                const before = ev.clientY < rect.top + rect.height / 2;
                reorderLayerByDisplayDrop(fromId, toId, before ? 'before' : 'after');
                clearLayerDropHints(container);
            });
            row.addEventListener('click', (e) => {
                if (e.target.closest('[data-pcs-le-vis],[data-pcs-le-lock],[data-pcs-le-layer-del],[data-pcs-le-layer-grip]')) return;
                session.selection = [row.getAttribute('data-pcs-le-layer')];
                renderLayersList(container);
                syncInteractionSelection();
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
        listEl?.addEventListener('dragover', (ev) => {
            if (ev.dataTransfer?.types?.includes('application/x-pcs-layer')) ev.preventDefault();
        });
        container.querySelectorAll('[data-pcs-le-layer-del]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteLayerById(btn.getAttribute('data-pcs-le-layer-del'));
            });
        });
        container.querySelectorAll('[data-pcs-le-vis]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-pcs-le-vis');
                const layer = session.scene.layers.find((l) => l.id === id);
                if (layer) {
                    layer.visible = !layer.visible;
                    History.pushHistory(session.history, session.scene);
                    refreshPreview();
                    renderLayersList(container);
                    session.onDirty?.();
                }
            });
        });
        container.querySelectorAll('[data-pcs-le-lock]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-pcs-le-lock');
                const layer = session.scene.layers.find((l) => l.id === id);
                if (layer) {
                    layer.locked = !layer.locked;
                    History.pushHistory(session.history, session.scene);
                    renderLayersList(container);
                    session.onDirty?.();
                }
            });
        });
    }

    function reorderLayerByDisplayDrop(fromId, toId, place) {
        if (!session.scene?.layerOrder) return;
        const display = Renderer.orderedLayers(session.scene).slice().reverse().map((l) => l.id);
        const fromIdx = display.indexOf(fromId);
        let toIdx = display.indexOf(toId);
        if (fromIdx < 0 || toIdx < 0 || fromId === toId) return;
        display.splice(fromIdx, 1);
        if (fromIdx < toIdx) toIdx -= 1;
        if (place === 'after') toIdx += 1;
        display.splice(toIdx, 0, fromId);
        session.scene.layerOrder = display.slice().reverse();
        History.pushHistory(session.history, session.scene, 'layerOrder');
        refreshPreview();
        session.onDirty?.();
        const listHost = document.querySelector('[data-pcs-le-layers]');
        if (listHost) renderLayersList(listHost);
    }

    function renderPropertyPanel(container) {
        if (!container) return;
        const features = session.ctx?.features || [];
        const q = (session._propFilter || '').trim().toLowerCase();
        const filtered = features.filter((f) => !q || (f.label + f.key).toLowerCase().includes(q));
        container.innerHTML = `
            <p class="pcs-le-inspector__hint pcs-le-prop-intro">برای افزودن به بوم کلیک کنید یا روی بوم رها کنید (Drag & Drop).</p>
            <input type="search" class="pcs-input pcs-le-search" placeholder="جستجو در فیلدهای ملک…" value="${session._propFilter || ''}" data-pcs-le-prop-search>
            <div class="pcs-le-prop-list" data-pcs-le-prop-list>
                ${filtered.length ? filtered.map((f) => {
                    const line = Bindings.featureCatalogPanelLine
                        ? Bindings.featureCatalogPanelLine(f)
                        : (f.value ? `${f.label} : ${f.value}` : (f.label || '—'));
                    return `
                    <button type="button" class="pcs-le-prop-item" draggable="true" data-pcs-le-feature="${f.key}">
                        <span class="pcs-le-prop-item__icon"><i class="fas ${f.icon || 'fa-circle-dot'}" aria-hidden="true"></i></span>
                        <span class="pcs-le-prop-item__text">
                            <span class="pcs-le-prop-item__line">${escAttr(line)}</span>
                        </span>
                        <i class="fas fa-plus pcs-le-prop-item__add" aria-hidden="true"></i>
                    </button>`;
                }).join('') : '<p class="pcs-le-empty-inline">فیلدی برای نمایش نیست.</p>'}
            </div>`;
        const search = container.querySelector('[data-pcs-le-prop-search]');
        search?.addEventListener('input', () => {
            session._propFilter = search.value;
            renderPropertyPanel(container);
        });
        container.querySelectorAll('[data-pcs-le-feature]').forEach((btn) => {
            btn.addEventListener('dragstart', (ev) => {
                ev.dataTransfer?.setData('application/x-pcs-feature', btn.getAttribute('data-pcs-le-feature') || '');
            });
            btn.addEventListener('click', () => {
                const key = btn.getAttribute('data-pcs-le-feature');
                const entry = features.find((x) => x.key === key);
                if (!entry || !entry.value) return;
                const scene = session.scene;
                Templates.addFeatureLayer(scene, entry, {
                    x: scene.canvas.width * 0.5,
                    y: scene.canvas.height * 0.45,
                }, 'plain');
                History.pushHistory(session.history, scene);
                refreshPreview();
                session.onDirty?.();
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
    }

    function renderPanel(bodyEl) {
        syncMobLayout();
        if (!bodyEl || session.tool === 'poster') return;
        if (session.tool === 'layers') {
            setPanelTitle('لایه‌ها');
            setPanelSubtitle('ترتیب از بالا به پایین — بالاتر روی بوم جلوتر است');
            bodyEl.innerHTML = '<div class="pcs-le-layers" data-pcs-le-layers></div>';
            renderLayersList(bodyEl.querySelector('[data-pcs-le-layers]'));
            return;
        }
        if (session.tool === 'property') {
            setPanelTitle('اطلاعات ملک');
            setPanelSubtitle('افزودن سریع فیلدهای فایل روی پوستر');
            bodyEl.innerHTML = '<div class="pcs-le-property" data-pcs-le-property></div>';
            renderPropertyPanel(bodyEl.querySelector('[data-pcs-le-property]'));
            return;
        }
        if (session.tool === 'text') {
            setPanelTitle('متن');
            const layer = selectedLayer();
            if (layer && (layer.type === 'text' || layer.type === 'bound_text')) {
                renderLayerInspector(bodyEl, layer);
            } else {
                bodyEl.innerHTML = `
                <div class="pcs-le-tool-panel">
                    <p class="pcs-le-inspector__hint">متن آزاد اضافه کنید یا لایهٔ متن را روی بوم انتخاب کنید.</p>
                    <button type="button" class="pcs-le-btn pcs-le-btn--primary" data-pcs-le-add-text-full>
                        <i class="fas fa-font"></i> افزودن متن آزاد
                    </button>
                </div>`;
                bodyEl.querySelector('[data-pcs-le-add-text-full]')?.addEventListener('click', () => addFreeTextLayer());
            }
            return;
        }
        if (session.tool === 'images') {
            setPanelTitle('تصویر');
            setPanelSubtitle('انتخاب لایه یا افزودن تصویر از فایل');
            const layer = selectedLayer();
            if (layer?.type === 'image') {
                renderLayerInspector(bodyEl, layer);
            } else {
                const imgs = session.ctx?.images || [];
                bodyEl.innerHTML = `
                <div class="pcs-le-tool-panel">
                    <p class="pcs-le-inspector__hint">روی لایهٔ تصویر در بوم کلیک کنید تا قاب و افکت را تنظیم کنید، یا تصویر جدید اضافه کنید.</p>
                    ${imgs.length ? `<button type="button" class="pcs-le-btn pcs-le-btn--primary" data-pcs-le-add-image><i class="fas fa-image"></i> افزودن لایهٔ تصویر</button>` : '<p class="pcs-le-inspector__hint">تصویری در فایل ملک نیست.</p>'}
                </div>`;
                bodyEl.querySelector('[data-pcs-le-add-image]')?.addEventListener('click', () => addImageLayer(0));
            }
            return;
        }
        if (session.tool === 'template') {
            setPanelTitle('قالب');
            bodyEl.innerHTML = `<p class="pcs-le-inspector__hint">قالب فعلی: <strong>${session.tpl}</strong>. برای تعویض قالب، ویرایشگر را ببندید و قالب دیگری از گرید انتخاب کنید.</p>`;
            return;
        }
        setPanelTitle('ویژگی‌ها');
        setPanelSubtitle('انتخاب و ویرایش لایه');
        const layer = selectedLayer();
        if (layer) {
            renderLayerInspector(bodyEl, layer);
            return;
        }
        bodyEl.innerHTML = `
            <div class="pcs-le-empty">
                <div class="pcs-le-empty__icon" aria-hidden="true"><i class="fas fa-arrow-pointer"></i></div>
                <p class="pcs-le-empty__title">لایه‌ای انتخاب نشده</p>
                <p class="pcs-le-inspector__hint">روی بوم کلیک کنید یا از دکمه‌های زیر المان جدید بسازید.</p>
                <button type="button" class="pcs-le-btn pcs-le-btn--primary" data-pcs-le-add-text-empty><i class="fas fa-plus"></i> متن جدید</button>
                <button type="button" class="pcs-le-btn pcs-le-btn--ghost" data-pcs-le-open-prop>افزودن از اطلاعات ملک</button>
            </div>`;
        bodyEl.querySelector('[data-pcs-le-add-text-empty]')?.addEventListener('click', () => addFreeTextLayer());
        bodyEl.querySelector('[data-pcs-le-open-prop]')?.addEventListener('click', () => {
            session.tool = 'property';
            renderToolbar(document.getElementById('pcsLeTools'));
            renderPanel(bodyEl);
        });
    }

    function renderChrome() {
        session.chromeEl?.remove();
        session.chromeEl = null;
        if (!session.scene || session.selection.length !== 1) return;
        const layer = session.scene.layers.find((l) => l.id === session.selection[0]);
        if (!layer || !layer.visible) return;
        const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
        if (!canvas) return;
        const chrome = document.createElement('div');
        chrome.className = 'pcs-le-chrome';
        chrome.setAttribute('data-pcs-le-chrome', '1');
        chrome.style.cssText = `position:absolute;left:${layer.x}px;top:${layer.y}px;width:${layer.width}px;height:${layer.height}px;pointer-events:none;box-sizing:border-box;z-index:200;`;
        const label = document.createElement('span');
        label.className = 'pcs-le-chrome__label';
        label.textContent = layer.name || '';
        chrome.appendChild(label);
        Interaction.HANDLES.forEach((hn) => {
            const dot = document.createElement('span');
            dot.className = `pcs-le-handle pcs-le-handle--${hn}`;
            dot.setAttribute('data-pcs-le-handle', hn);
            dot.setAttribute('aria-hidden', 'true');
            chrome.appendChild(dot);
        });
        canvas.appendChild(chrome);
        session.chromeEl = chrome;
    }

    function interactionHooks() {
        return {
            onSelectionChange(ids) {
                session.selection = ids;
                if (ids.length && session.tool !== 'layers' && session.tool !== 'property' && session.tool !== 'poster') {
                    session.tool = 'select';
                    renderToolbar(document.getElementById('pcsLeTools'));
                }
                if (ids.length && session.tool === 'poster') {
                    leavePosterSettings('select');
                }
                renderPanel(document.getElementById('pcsLePanelBody'));
                renderChrome();
                updateShellMeta();
            },
            onLayerChange(layer, meta) {
                const canvas = document.getElementById('pcsEditorPreviewViewport')?.querySelector('.pcs-canvas');
                if (canvas) Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf);
                renderChrome();
                if (meta?.transient) {
                    const panel = document.getElementById('pcsLePanelBody');
                    if (layer.style?.fontSize != null) {
                        const r = panel?.querySelector('[data-pcs-le-font-size]');
                        const num = panel?.querySelector('[data-pcs-le-font-size-num]');
                        if (r) r.value = String(Math.min(120, layer.style.fontSize));
                        if (num) num.value = String(layer.style.fontSize);
                    }
                    panel?.querySelectorAll('[data-pcs-le-geom]').forEach((inp) => {
                        if (inp.name && layer[inp.name] != null) inp.value = String(Math.round(layer[inp.name]));
                    });
                }
                if (!meta?.transient) session.onDirty?.();
            },
            onGestureStart() {
                History.checkpoint(session.history, session.scene);
            },
            onGestureEnd() {
                History.endMerge(session.history);
                syncSceneToPosterConf(session.posterConf, session.scene);
                session.onDirty?.();
            },
            renderChrome,
        };
    }

    function syncInteractionSelection() {
        session.interaction?.setSelection?.(session.selection);
        renderChrome();
    }

    function rebindInteraction() {
        session.interaction?.destroy?.();
        const viewport = document.getElementById('pcsEditorPreviewViewport');
        const canvas = viewport?.querySelector('.pcs-canvas');
        if (!canvas || !viewport) return;
        session.interaction = Interaction.bindCanvasInteraction(
            canvas,
            () => session.scene,
            viewport,
            interactionHooks(),
        );
        syncInteractionSelection();
    }

    function refreshPreview(opts) {
        const preview = document.getElementById('pcsEditorPreview');
        const bridge = global.PCSBridge;
        if (!preview || !bridge || !session.scene) return;
        const bootstrapTypography = opts?.bootstrapTypography === true;
        const rebuildScene = opts?.rebuildScene === true;
        const skipLinkedSync = opts?.skipLinkedSync === true;
        if (bridge.buildPosterRenderContext) {
            const ctxFresh = bridge.buildPosterRenderContext(session.tpl);
            session.ctx.property = ctxFresh.property;
            session.ctx.features = ctxFresh.features;
            session.ctx.catalogByKey = Bindings.catalogMap(ctxFresh.features);
            session.ctx.overlayUrl = ctxFresh.overlayUrl;
            session.ctx.brand = ctxFresh.brand || session.ctx.brand;
        }
        session.ctx.posterConf = session.posterConf;
        if (!skipLinkedSync) {
            Bindings.syncLinkedLayers(session.scene, session.ctx);
        }
        if (rebuildScene) {
            session.scene = ensureScene(session.posterConf, session.ctx);
            syncLegacyConfToScene(session.posterConf);
        }
        session.posterConf.scene = session.scene;
        preview.innerHTML = bridge.renderPosterHtml(
            session.tpl,
            session.formatKey,
            session.posterConf,
            { preserveScene: true },
        );
        const runScale = () => {
            if (bridge.scaleLayerEditorPreview) {
                bridge.scaleLayerEditorPreview(preview, session.formatKey);
            } else {
                bridge.scheduleEditorPreviewScale?.(preview, session.formatKey);
            }
        };
        const typographyOpts = {
            templateId: session.tpl,
            formatKey: session.formatKey,
            posterConf: session.posterConf,
            skipFlowTypography: !bootstrapTypography,
        };
        runScale();
        requestAnimationFrame(() => {
            runScale();
            bridge.syncCanvasTypography?.(preview, typographyOpts);
            if (bootstrapTypography) {
                const canvas = preview.querySelector('.pcs-canvas');
                bridge.syncSceneTypographyFromFittedCanvas?.(session.scene, canvas);
            }
            rebindInteraction();
            renderChrome();
            updateShellMeta();
        });
    }

    function bindViewportResize() {
        session._resizeObs?.disconnect();
        session._resizeObs = null;
        const viewport = document.getElementById('pcsEditorPreviewViewport');
        if (!viewport || typeof ResizeObserver === 'undefined') return;
        session._resizeObs = new ResizeObserver(() => {
            const preview = document.getElementById('pcsEditorPreview');
            const bridge = global.PCSBridge;
            if (!preview || !bridge?.scaleLayerEditorPreview) return;
            bridge.scaleLayerEditorPreview(preview, session.formatKey);
            renderChrome();
        });
        session._resizeObs.observe(viewport);
    }

    function docPointFromDrop(ev, viewport) {
        const canvas = viewport?.querySelector('.pcs-canvas');
        if (!canvas || !session.scene) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        const cw = session.scene.canvas.width || 1080;
        const ch = session.scene.canvas.height || 1920;
        return {
            x: (ev.clientX - rect.left) * (cw / Math.max(1, rect.width)),
            y: (ev.clientY - rect.top) * (ch / Math.max(1, rect.height)),
        };
    }

    function bindDrop(viewport) {
        if (session._dropAbort) session._dropAbort.abort();
        session._dropAbort = new AbortController();
        const sig = session._dropAbort.signal;
        viewport?.addEventListener('dragover', (ev) => {
            if (ev.dataTransfer?.types?.includes('application/x-pcs-feature')) ev.preventDefault();
        }, { signal: sig });
        viewport?.addEventListener('drop', (ev) => {
            const key = ev.dataTransfer?.getData('application/x-pcs-feature');
            if (!key || !session.scene) return;
            ev.preventDefault();
            const doc = docPointFromDrop(ev, viewport);
            const entry = (session.ctx.features || []).find((f) => f.key === key);
            if (!entry || !entry.value) return;
            History.checkpoint(session.history, session.scene);
            Templates.addFeatureLayer(session.scene, entry, doc, 'plain');
            refreshPreview();
            session.onDirty?.();
            renderPanel(document.getElementById('pcsLePanelBody'));
        }, { signal: sig });
    }

    function mountLayerEditorLayout() {
        const editor = document.getElementById('pcsEditor');
        if (!editor) return;
        const workspace = editor.querySelector('.pcs-editor__workspace');
        if (!workspace) return;
        if (workspace.classList.contains('pcs-le-workspace') && workspace.dataset.pcsLeLayout === '2') return;
        workspace.classList.add('pcs-le-workspace');
        workspace.dataset.pcsLeLayout = '2';
        workspace.innerHTML = `
            <aside class="pcs-le-rail" aria-label="ابزارها">
                <div class="pcs-le-rail__tools" id="pcsLeTools"></div>
            </aside>
            <aside class="pcs-le-panel" id="pcsLePanel">
                <header class="pcs-le-panel__head">
                    <div class="pcs-le-panel__grab" aria-hidden="true"></div>
                    <div class="pcs-le-panel__head-text">
                        <span id="pcsLePanelTitle">ویژگی‌ها</span>
                        <span class="pcs-le-panel__sub" id="pcsLePanelSub">لایه‌ای را انتخاب کنید</span>
                    </div>
                    <button type="button" class="pcs-le-panel__collapse" id="pcsLePanelCollapse" aria-label="جمع کردن پنل"><i class="fas fa-chevron-right"></i></button>
                </header>
                <div class="pcs-le-panel__main">
                    <div class="pcs-le-panel__body" id="pcsLePanelBody"></div>
                    <div class="pcs-le-panel__poster" id="pcsLePosterPane" hidden>
                        <div class="pcs-editor__controls pcs-le-poster__controls" id="pcsEditorControls"></div>
                    </div>
                </div>
            </aside>
            <div class="pcs-le-canvas-host">
                <div class="pcs-editor__preview-pane is-active" data-pcs-editor-pane="preview">
                    <div class="pcs-editor__preview-stage pcs-le-stage">
                        <div class="pcs-le-canvas-bar">
                            <div class="pcs-le-canvas-bar__meta" id="pcsLeCanvasMeta" aria-live="polite">1080 × 1920</div>
                            <div class="pcs-le-top-tools" id="pcsLeTopTools">
                                <button type="button" class="pcs-le-top-btn" data-pcs-le-undo title="واگرد"><i class="fas fa-rotate-left"></i><span>واگرد</span></button>
                                <button type="button" class="pcs-le-top-btn" data-pcs-le-redo title="از نو"><i class="fas fa-rotate-right"></i><span>از نو</span></button>
                                <button type="button" class="pcs-le-top-btn pcs-le-top-btn--accent" data-pcs-le-fit title="جا شدن در صفحه"><i class="fas fa-expand"></i><span>جا شدن</span></button>
                            </div>
                        </div>
                        <div class="pcs-editor__preview-viewport pcs-le-viewport" id="pcsEditorPreviewViewport">
                            <div class="pcs-editor__preview pcs-le-preview-wrap" id="pcsEditorPreview"></div>
                        </div>
                        <p class="pcs-le-canvas-hint" id="pcsLeCanvasHint">گوشه‌های بنفش: تغییر اندازه · درگ: جابه‌جایی · Delete: حذف</p>
                    </div>
                </div>
            </div>`;
        const editorRoot = document.getElementById('pcsEditor');
        const orphanLegacy = document.getElementById('pcsLeLegacySettings');
        orphanLegacy?.remove();
        renderToolbar(document.getElementById('pcsLeTools'));
        document.getElementById('pcsLePanelCollapse')?.addEventListener('click', () => {
            const panel = document.getElementById('pcsLePanel');
            if (!panel) return;
            if (isMob()) {
                panel.classList.toggle('pcs-le-panel--sheet-open');
                panel.classList.toggle('is-collapsed');
                return;
            }
            panel.classList.toggle('is-collapsed');
        });
        document.querySelector('[data-pcs-le-undo]')?.addEventListener('click', () => {
            const prev = History.undo(session.history, session.scene);
            if (prev) {
                session.scene = Schema.normalizeScene(prev, session.tpl, session.formatKey);
                session.posterConf.scene = session.scene;
                refreshPreview();
                session.onDirty?.();
            }
        });
        document.querySelector('[data-pcs-le-redo]')?.addEventListener('click', () => {
            const next = History.redo(session.history, session.scene);
            if (next) {
                session.scene = Schema.normalizeScene(next, session.tpl, session.formatKey);
                session.posterConf.scene = session.scene;
                refreshPreview();
                session.onDirty?.();
            }
        });
        document.querySelector('[data-pcs-le-fit]')?.addEventListener('click', () => {
            const preview = document.getElementById('pcsEditorPreview');
            const bridge = global.PCSBridge;
            if (preview && bridge?.scaleLayerEditorPreview) {
                bridge.scaleLayerEditorPreview(preview, session.formatKey);
            }
            renderChrome();
        });
        if (!editor.dataset.pcsLeKeysBound) {
            editor.dataset.pcsLeKeysBound = '1';
            window.addEventListener('keydown', (ev) => {
                if (!session.active) return;
                if (ev.key === 'Escape') {
                    session.selection = [];
                    syncInteractionSelection();
                    renderPanel(document.getElementById('pcsLePanelBody'));
                    updateShellMeta();
                    return;
                }
                if (ev.key !== 'Delete' && ev.key !== 'Backspace') return;
                if (ev.target.closest('input, textarea, select, [contenteditable]')) return;
                const layer = selectedLayer();
                if (layer && !layer.locked) {
                    ev.preventDefault();
                    deleteLayerById(layer.id);
                }
            });
        }
    }

    function fitView() {
        const viewport = document.getElementById('pcsEditorPreviewViewport');
        if (!viewport || !session.scene) return;
        session.view.fitScale = Coords.computeFitScale(
            viewport.clientWidth,
            viewport.clientHeight,
            session.scene.canvas.width,
            session.scene.canvas.height,
        );
        session.view.zoom = 1;
        session.view.panX = 0;
        session.view.panY = 0;
    }

    function start(opts) {
        if (!global.PCSInteraction || !global.PCSSceneRenderer) {
            throw new Error('PCS layer modules not loaded');
        }
        mountLayerEditorLayout();
        global.PCSBridge?.teardownEditorTextInteraction?.(
            document.getElementById('pcsEditorPreview'),
        );
        const viewportEl = document.getElementById('pcsEditorPreviewViewport');
        viewportEl?.classList.remove('is-panning', 'is-zoomed');
        session.active = true;
        session.tpl = opts.templateId;
        session.formatKey = opts.formatKey || 'story';
        session.posterConf = opts.posterConf;
        session.ctx = {
            templateId: opts.templateId,
            formatKey: session.formatKey,
            formats: opts.formats,
            property: opts.property,
            images: opts.images || [],
            features: opts.features || [],
            catalogByKey: Bindings.catalogMap(opts.features),
            overlayUrl: opts.overlayUrl || '',
            brand: opts.brand || {},
            posterConf: opts.posterConf,
        };
        session.scene = ensureScene(session.posterConf, session.ctx);
        syncLegacyConfToScene(session.posterConf);
        session.posterConf.scene = session.scene;
        session.view = Coords.createViewState();
        session.history = History.createHistory();
        session.onDirty = opts.onDirty;
        session.onCommitScene = opts.onCommitScene;
        session.selection = [];
        session.tool = 'select';
        syncPanelMode();
        syncMobLayout();
        renderPanel(document.getElementById('pcsLePanelBody'));
        refreshPreview({ bootstrapTypography: true });
        bindDrop(document.getElementById('pcsEditorPreviewViewport'));
        bindViewportResize();
        updateShellMeta();
        const sub = document.getElementById('pcsEditorSub');
        if (sub) {
            sub.textContent = isMob()
                ? 'بوم را لمس کنید · ابزارها پایین · شیت برای ویرایش لایه'
                : 'تنظیمات کلی پوستر فقط از اولین دکمهٔ نوار ابزار (اسلیدر) · بقیهٔ دکمه‌ها برای لایه و ابزار';
        }
        syncMobLayout();
    }

    function commitToBuffer(buffer) {
        if (!session.active || !buffer) return buffer;
        syncSceneToPosterConf(buffer, session.scene);
        return buffer;
    }

    function stop() {
        session.interaction?.destroy?.();
        if (session._dropAbort) session._dropAbort.abort();
        session._dropAbort = null;
        session._resizeObs?.disconnect();
        session._resizeObs = null;
        session.active = false;
        session.scene = null;
        session.chromeEl?.remove();
        session.chromeEl = null;
        document.getElementById('pcsEditor')?.classList.remove('pcs-editor--layer-le');
        document.querySelector('.pcs-le-workspace')?.classList.remove('pcs-le-workspace--mob');
    }

    function refreshFromLegacyControls(conf, formatKey) {
        if (!session.active) return;
        const formats = session.ctx?.formats || {};
        const nextFmt = formatKey || session.formatKey || 'story';
        const prevFmt = session.formatKey;
        session.formatKey = nextFmt;
        if (session.ctx) session.ctx.formatKey = nextFmt;
        session.posterConf = conf;
        session.scene = ensureScene(conf, session.ctx);
        syncLegacyConfToScene(conf);
        const canvasFmt = session.scene?.canvas?.format;
        const canvasMismatch = canvasFmt !== nextFmt
            || Schema.canvasForFormat(nextFmt, formats).width !== session.scene?.canvas?.width
            || Schema.canvasForFormat(nextFmt, formats).height !== session.scene?.canvas?.height;
        if (nextFmt !== prevFmt || canvasMismatch) {
            Schema.applySceneCanvasFormat(session.scene, nextFmt, formats);
        }
        session.posterConf.scene = session.scene;
        fitView();
        refreshPreview({ rebuildScene: true, bootstrapTypography: true });
    }

    global.PCSLayerEditor = {
        start,
        stop,
        commitToBuffer,
        refreshFromLegacyControls,
        isActive: () => session.active,
        getScene: () => session.scene,
    };
}(typeof window !== 'undefined' ? window : globalThis));
