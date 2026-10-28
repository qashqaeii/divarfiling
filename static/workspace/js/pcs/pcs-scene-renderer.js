/**
 * Render scene layers into canvas DOM (shared by preview + export).
 */
(function (global) {
    'use strict';

    const Bindings = global.PCSBindings;

    function esc(s) {
        return global.PCSBridge?.esc ? global.PCSBridge.esc(s) : String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    }

    function fontFamily(fontKey) {
        const fonts = global.PCSBridge?.PCS_FONTS || {};
        return fonts[fontKey]?.family || "'Vazirmatn', Tahoma, sans-serif";
    }

    function layerStyleCss(layer) {
        const st = layer.style || {};
        let css = `position:absolute;left:${layer.x}px;top:${layer.y}px;width:${layer.width}px;height:${layer.height}px;`;
        css += `opacity:${layer.opacity != null ? layer.opacity : 1};`;
        if (layer.rotation) css += `transform:rotate(${layer.rotation}deg);transform-origin:center center;`;
        css += 'box-sizing:border-box;overflow:hidden;';
        if (st.background) css += `background:${st.background};`;
        if (st.borderRadius) css += `border-radius:${st.borderRadius}px;`;
        return css;
    }

    function renderTextLayer(layer, text) {
        const st = layer.style || {};
        const fs = st.fontSize || 28;
        const fw = st.fontWeight || 700;
        const fill = st.fill || '#fff';
        const align = st.align || 'right';
        const dir = st.direction || 'rtl';
        const lh = st.lineHeight || 1.35;
        const pad = st.textPreset === 'capsule' ? '8px 18px' : '2px 4px';
        return `<div dir="${dir}" data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="text" style="${layerStyleCss(layer)}pointer-events:auto;">
            <div style="width:100%;height:100%;display:flex;align-items:center;justify-content:${align === 'center' ? 'center' : align === 'left' ? 'flex-start' : 'flex-end'};padding:${pad};font-family:${fontFamily(st.fontKey)};font-size:${fs}px;font-weight:${fw};color:${fill};line-height:${lh};text-align:${align};word-wrap:break-word;overflow-wrap:anywhere;">${esc(text)}</div>
        </div>`;
    }

    function renderImageLayer(layer, url, conf) {
        const st = layer.style || {};
        const cropY = st.cropPanY != null ? st.cropPanY : 50;
        const cropX = st.cropPanX != null ? st.cropPanX : 50;
        const fit = st.objectFit || 'cover';
        const imgHtml = url
            ? `<img src="${esc(url)}" alt="" style="width:100%;height:100%;object-fit:${fit};object-position:${cropX}% ${cropY}%;display:block;" crossorigin="anonymous">`
            : `<div style="width:100%;height:100%;background:#1e293b;"></div>`;
        const filters = [];
        if (conf?.img_brightness != null && conf.img_brightness !== 100) filters.push(`brightness(${conf.img_brightness}%)`);
        if (conf?.img_blur) filters.push(`blur(${conf.img_blur}px)`);
        if (conf?.img_opacity != null && conf.img_opacity !== 100) {
            return `<div data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="image" style="${layerStyleCss(layer)}pointer-events:auto;opacity:${(layer.opacity ?? 1) * (conf.img_opacity / 100)};">${imgHtml}</div>`;
        }
        const filt = filters.length ? `filter:${filters.join(' ')};` : '';
        return `<div data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="image" style="${layerStyleCss(layer)}pointer-events:auto;${filt}">${imgHtml}</div>`;
    }

    function renderFrameLayer(layer) {
        const url = layer.assetRef || '';
        if (!url) return '';
        return `<img data-pcs-layer-id="${esc(layer.id)}" data-pcs-layer-type="template_frame" src="${esc(url)}" alt="" style="${layerStyleCss(layer)}pointer-events:none;object-fit:fill;width:${layer.width}px;height:${layer.height}px;" crossorigin="anonymous">`;
    }

    function orderedLayers(scene) {
        const byId = {};
        (scene.layers || []).forEach((l) => { byId[l.id] = l; });
        const order = scene.layerOrder || [];
        return order.map((id) => byId[id]).filter(Boolean);
    }

    function renderSceneOverlayHtml(scene, ctx, conf) {
        const imgs = ctx.images || [];
        Bindings.syncLinkedLayers(scene, ctx);
        let html = '<div class="pcs-scene-root" data-pcs-scene-root style="position:absolute;inset:0;pointer-events:none;z-index:20;">';
        orderedLayers(scene).forEach((layer) => {
            if (!layer.visible) return;
            if (layer.type === 'template_frame') {
                html += renderFrameLayer(layer);
                return;
            }
            if (layer.type === 'image') {
                const idx = layer.imageIndex != null ? layer.imageIndex : 0;
                html += renderImageLayer(layer, imgs[idx] || imgs[0] || '', conf);
                return;
            }
            if (layer.type === 'text' || layer.type === 'bound_text') {
                const text = Bindings.bindingText(layer, ctx);
                html += renderTextLayer(layer, text);
            }
        });
        html += '</div>';
        return html;
    }

    function mountSceneOnCanvas(canvasEl, scene, ctx, conf) {
        if (!canvasEl || !scene) return;
        canvasEl.querySelector('.pcs-scene-root')?.remove();
        const host = document.createElement('div');
        host.innerHTML = renderSceneOverlayHtml(scene, ctx, conf);
        const root = host.firstElementChild;
        if (root) canvasEl.appendChild(root);
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
            const text = Bindings.bindingText(layer, ctx);
            const inner = node.querySelector('div');
            if (inner) inner.textContent = text;
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

    global.PCSSceneRenderer = {
        orderedLayers,
        renderSceneOverlayHtml,
        mountSceneOnCanvas,
        updateLayerDom,
    };
}(typeof window !== 'undefined' ? window : globalThis));
