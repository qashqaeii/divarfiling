/**
 * Document ↔ viewport coordinate transforms (zoom, pan, fit, DPR).
 */
(function (global) {
    'use strict';

    function createViewState() {
        return {
            zoom: 1,
            panX: 0,
            panY: 0,
            fitScale: 1,
            dpr: typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1,
        };
    }

    function computeFitScale(viewportW, viewportH, docW, docH, padding) {
        const pad = padding == null ? 24 : padding;
        const aw = Math.max(1, viewportW - pad * 2);
        const ah = Math.max(1, viewportH - pad * 2);
        return Math.min(aw / docW, ah / docH);
    }

    /** Combined scale from document px to CSS px on screen */
    function effectiveScale(view) {
        return (view.fitScale || 1) * (view.zoom || 1);
    }

    function documentToViewport(docX, docY, view, docW, docH, viewportRect) {
        const s = effectiveScale(view);
        const cx = viewportRect.width / 2;
        const cy = viewportRect.height / 2;
        const ox = cx - (docW * s) / 2 + (view.panX || 0);
        const oy = cy - (docH * s) / 2 + (view.panY || 0);
        return {
            x: ox + docX * s,
            y: oy + docY * s,
            scale: s,
        };
    }

    function viewportToDocument(vpX, vpY, view, docW, docH, viewportRect) {
        const s = effectiveScale(view);
        if (!s) return { x: 0, y: 0 };
        const cx = viewportRect.width / 2;
        const cy = viewportRect.height / 2;
        const ox = cx - (docW * s) / 2 + (view.panX || 0);
        const oy = cy - (docH * s) / 2 + (view.panY || 0);
        return {
            x: (vpX - ox) / s,
            y: (vpY - oy) / s,
        };
    }

    function applyStageTransform(stageEl, view, docW, docH) {
        if (!stageEl) return;
        const s = effectiveScale(view);
        stageEl.style.width = `${docW}px`;
        stageEl.style.height = `${docH}px`;
        stageEl.style.transformOrigin = '0 0';
        const cx = view._hostW ? view._hostW / 2 : 0;
        const cy = view._hostH ? view._hostH / 2 : 0;
        const tx = cx - (docW * s) / 2 + (view.panX || 0);
        const ty = cy - (docH * s) / 2 + (view.panY || 0);
        stageEl.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    }

    global.PCSCoords = {
        createViewState,
        computeFitScale,
        effectiveScale,
        documentToViewport,
        viewportToDocument,
        applyStageTransform,
    };
}(typeof window !== 'undefined' ? window : globalThis));
