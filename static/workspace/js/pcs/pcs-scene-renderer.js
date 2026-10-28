/**
 * Render scene document (single content path for scene-driven posters).
 */
(function (global) {
    'use strict';

    const Bindings = global.PCSBindings;
    const Assets = global.PCSAssets;

    function esc(s) {
        return global.PCSBridge?.esc ? global.PCSBridge.esc(s) : String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    }

    function fontFamily(fontKey) {
        const fonts = global.PCSBridge?.PCS_FONTS || {};
        return fonts[fontKey]?.family || "'Vazirmatn', Tahoma, sans-serif";
    }

    function usesSceneDocument(scene) {
        return !!(scene && scene.schemaVersion >= 2 && scene.renderMode === 'layers'
            && Array.isArray(scene.layers) && scene.layers.length > 0);
    }

    function overlayMap(ctx) {
        const m = {};
        if (ctx?.overlayUrl && ctx.templateId) m[ctx.templateId] = ctx.overlayUrl;
        if (ctx?.templateOverlays) Object.assign(m, ctx.templateOverlays);
        return m;
    }

    function layerStyleCss(layer) {
        const st = layer.style || {};
        let css = `position:absolute;left:${layer.x}px;top:${layer.y}px;width:${layer.width}px;height:${layer.height}px;`;
        css += `opacity:${layer.opacity != null ? layer.opacity : 1};`;
        css += 'box-sizing:border-box;overflow:hidden;';
        if (layer.rotation) css += `transform:rotate(${layer.rotation}deg);transform-origin:center center;`;
        if (st.background) css += `background:${st.background};`;
        if (st.borderRadius) css += `border-radius:${st.borderRadius}px;`;
        return css;
    }

    function flexJustify(align) {
        if (align === 'center') return 'center';
        if (align === 'left') return 'flex-start';
        return 'flex-end';
    }

    function applyTextLayerDom(node, layer, ctx) {
        if (!node || !layer) return;
        const st = layer.style || {};
        const text = Bindings.bindingText(layer, ctx);
        const inner = node.querySelector('[data-pcs-text-inner]') || node.querySelector('div') || node;
        inner.setAttribute('data-pcs-text-inner', '1');
        inner.textContent = text;
        inner.style.boxSizing = 'border-box';
        inner.style.width = '100%';
        inner.style.height = '100%';
        inner.style.display = 'flex';
        inner.style.alignItems = 'center';
        inner.style.justifyContent = flexJustify(st.align || 'right');
        inner.style.padding = st.textPreset === 'capsule' ? '8px 18px' : '2px 4px';
        inner.style.fontFamily = fontFamily(st.fontKey);
        inner.style.fontSize = `${st.fontSize || 28}px`;
        inner.style.fontWeight = String(st.fontWeight || 700);
        inner.style.color = st.fill || '#ffffff';
        inner.style.lineHeight = String(st.lineHeight || 1.35);
        inner.style.textAlign = st.align || 'right';
        inner.style.wordWrap = 'break-word';
        inner.style.overflowWrap = 'anywhere';
        inner.style.fontStyle = st.fontStyle === 'italic' ? 'italic' : 'normal';
        inner.style.textDecoration = st.textDecoration === 'underline' ? 'underline' : 'none';
        node.setAttribute('dir', st.direction || 'rtl');
        if (st.background) node.style.background = st.background;
        else node.style.background = '';
        if (st.borderRadius != null) node.style.borderRadius = `${st.borderRadius}px`;
        else if (!st.textPreset) node.style.borderRadius = '';
    }

    function renderTextLayer(layer, ctx) {
        const st = layer.style || {};
        const fs = st.fontSize || 28;
        const fw = st.fontWeight || 700;
        const fill = st.fill || '#fff';
        const align = st.align || 'right';
        const dir = st.direction || 'rtl';
        const lh = st.lineHeight || 1.35;
        const pad = st.textPreset === 'capsule' ? '8px 18px' : '2px 4px';
        const fStyle = st.fontStyle === 'italic' ? 'font-style:italic;' : '';
        const uLine = st.textDecoration === 'underline' ? 'text-decoration:underline;' : '';
        const text = Bindings?.bindingText ? Bindings.bindingText(layer, ctx) : String(layer.text || '');
        return `<div dir="${dir}" data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="text" style="${layerStyleCss(layer)}">
            <div data-pcs-text-inner="1" style="width:100%;height:100%;display:flex;align-items:center;justify-content:${flexJustify(align)};padding:${pad};font-family:${fontFamily(st.fontKey)};font-size:${fs}px;font-weight:${fw};color:${fill};line-height:${lh};text-align:${align};word-wrap:break-word;overflow-wrap:anywhere;box-sizing:border-box;${fStyle}${uLine}">${esc(text)}</div>
        </div>`;
    }

    function renderImageLayer(layer, url, conf) {
        const st = layer.style || {};
        const cropY = st.cropPanY != null ? st.cropPanY : (conf?.crop_y ?? 50);
        const cropX = st.cropPanX != null ? st.cropPanX : 50;
        const zoom = st.cropZoom != null ? st.cropZoom : 1;
        const fit = st.objectFit || 'cover';
        const scale = zoom !== 1 ? `transform:scale(${zoom});transform-origin:${cropX}% ${cropY}%;` : '';
        const imgHtml = url
            ? `<img src="${esc(url)}" alt="" style="width:100%;height:100%;object-fit:${fit};object-position:${cropX}% ${cropY}%;display:block;${scale}" crossorigin="anonymous">`
            : `<div style="width:100%;height:100%;background:#1e293b;"></div>`;
        const filters = [];
        const brightness = st.brightness ?? conf?.img_brightness ?? 100;
        const blurPx = st.blur ?? conf?.img_blur ?? 0;
        if (brightness !== 100) filters.push(`brightness(${brightness}%)`);
        if (blurPx > 0) filters.push(`blur(${blurPx}px)`);
        const warmth = st.warmth ?? conf?.hero_warmth;
        if (warmth === 'warm') filters.push('sepia(0.12) saturate(1.15)');
        if (warmth === 'cool') filters.push('saturate(0.88) hue-rotate(-6deg)');
        let op = layer.opacity != null ? layer.opacity : 1;
        const imgOp = st.imgOpacity ?? conf?.img_opacity ?? 100;
        if (imgOp !== 100) op *= imgOp / 100;
        const filt = filters.length ? `filter:${filters.join(' ')};` : '';
        const vig = st.vignette ?? conf?.hero_vignette ?? 0;
        const vigShadow = vig > 0
            ? `box-shadow:inset 0 0 ${Math.round(vig * 1.8)}px rgba(0,0,0,${Math.min(0.85, vig / 100)});`
            : '';
        return `<div data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="image" style="${layerStyleCss(layer)}${filt}${vigShadow}opacity:${op};">${imgHtml}</div>`;
    }

    function renderFrameLayer(layer, ctx) {
        const url = Assets?.resolveAssetRef
            ? Assets.resolveAssetRef(layer.assetRef, overlayMap(ctx))
            : '';
        if (!url) return '';
        return `<img data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="template_frame" src="${esc(url)}" alt="" style="${layerStyleCss(layer)}pointer-events:none;object-fit:fill;" crossorigin="anonymous">`;
    }

    function renderShapeLayer(layer) {
        const st = layer.style || {};
        const bg = st.background || st.fill || 'rgba(15,23,42,.08)';
        const radius = st.borderRadius != null ? `${st.borderRadius}px` : '0';
        return `<div data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="shape" style="${layerStyleCss(layer)}background:${bg};border-radius:${radius};pointer-events:none;"></div>`;
    }

    function orderedLayers(scene) {
        const byId = {};
        (scene.layers || []).forEach((l) => { byId[l.id] = l; });
        const order = scene.layerOrder || [];
        return order.map((id) => byId[id]).filter(Boolean);
    }

    function renderSceneLayersHtml(scene, ctx, conf) {
        const imgs = ctx.images || [];
        if (conf && ctx) ctx.posterConf = conf;
        if (Bindings?.syncLinkedLayers) Bindings.syncLinkedLayers(scene, ctx);
        let html = '';
        orderedLayers(scene).forEach((layer) => {
            if (!layer.visible) return;
            if (layer.type === 'template_frame') {
                html += renderFrameLayer(layer, ctx);
                return;
            }
            if (layer.type === 'shape' || layer.type === 'decor') {
                html += renderShapeLayer(layer);
                return;
            }
            if (layer.type === 'image') {
                const idx = layer.imageIndex != null ? layer.imageIndex : 0;
                html += renderImageLayer(layer, imgs[idx] || imgs[0] || '', conf);
                return;
            }
            if (layer.type === 'text' || layer.type === 'bound_text') {
                html += renderTextLayer(layer, ctx);
            }
        });
        return html;
    }

    function buildSceneCanvasHtml(templateId, formatKey, conf, ctx) {
        const bridge = global.PCSBridge;
        const fmt = bridge?.FORMATS?.[formatKey] || { w: 1080, h: 1920, cls: '' };
        const scene = conf?.scene;
        const w = scene?.canvas?.width || fmt.w;
        const h = scene?.canvas?.height || fmt.h;
        const fontKey = conf?.font_key || 'vazirmatn';
        const inner = renderSceneLayersHtml(scene, ctx, conf);
        const overlayBg = global.PCSTemplateScenes?.overlayCanvasBackground?.(templateId) || '';
        const canvasBg = overlayBg
            || (templateId === 'minimal' || templateId === 'modern' ? '#f6f4f0' : '#0f172a');
        return `<div class="pcs-canvas ${fmt.cls || ''}" data-pcs-canvas data-pcs-scene-driven="1" data-template="${esc(templateId)}" data-font-key="${esc(fontKey)}" style="width:${w}px;height:${h}px;--pcs-scale:1;position:relative;overflow:hidden;background:${canvasBg};">${inner}</div>`;
    }

    function renderPosterHtml(templateId, formatKey, conf, ctx) {
        if (usesSceneDocument(conf?.scene)) {
            return buildSceneCanvasHtml(templateId, formatKey, conf, ctx);
        }
        return global.PCSBridge?.buildCanvasHtml(templateId, formatKey, conf) || '';
    }

    function mountSceneOnCanvas(canvasEl, scene, ctx, conf) {
        if (!canvasEl || !scene) return;
        canvasEl.innerHTML = renderSceneLayersHtml(scene, ctx, conf);
    }

    function updateLayerDom(canvasEl, layer, ctx, conf) {
        const node = canvasEl?.querySelector(`[data-pcs-layer-id="${layer.id}"]`);
        if (!node) return false;
        const imgs = ctx.images || [];
        if (layer.type === 'image') {
            const idx = layer.imageIndex != null ? layer.imageIndex : 0;
            const url = imgs[idx] || imgs[0] || '';
            const img = node.querySelector('img');
            if (img && url) img.src = url;
        }
        if (layer.type === 'text' || layer.type === 'bound_text') {
            applyTextLayerDom(node, layer, ctx);
        }
        node.style.left = `${layer.x}px`;
        node.style.top = `${layer.y}px`;
        node.style.width = `${layer.width}px`;
        node.style.height = `${layer.height}px`;
        node.style.opacity = String(layer.opacity != null ? layer.opacity : 1);
        node.style.transform = layer.rotation ? `rotate(${layer.rotation}deg)` : '';
        node.style.display = layer.visible ? '' : 'none';
        return true;
    }

    function syncAllLayerDom(canvasEl, scene, ctx, conf) {
        orderedLayers(scene).forEach((layer) => updateLayerDom(canvasEl, layer, ctx, conf));
    }

    global.PCSSceneRenderer = {
        usesSceneDocument,
        orderedLayers,
        renderSceneLayersHtml,
        buildSceneCanvasHtml,
        renderPosterHtml,
        mountSceneOnCanvas,
        updateLayerDom,
        applyTextLayerDom,
        syncAllLayerDom,
    };
}(typeof window !== 'undefined' ? window : globalThis));
