/**
 * Pointer interaction: selection, drag, resize with document-pixel geometry.
 */
(function (global) {
    'use strict';

    const Coords = global.PCSCoords;
    const Schema = global.PCSSchema;

    const HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

    function createInteraction() {
        return {
            mode: 'idle',
            pointerId: null,
            startDoc: null,
            startLayer: null,
            handle: null,
            selectedIds: [],
        };
    }

    function hitTest(scene, docX, docY) {
        const layers = global.PCSSceneRenderer.orderedLayers(scene);
        for (let i = layers.length - 1; i >= 0; i--) {
            const l = layers[i];
            if (!l.visible || l.locked) continue;
            if (docX >= l.x && docX <= l.x + l.width && docY >= l.y && docY <= l.y + l.height) {
                return l;
            }
        }
        return null;
    }

    function resizeLayer(layer, handle, dx, dy, preserveAspect) {
        const min = 24;
        let { x, y, width, height } = layer;
        const ar = width / height;
        if (handle.includes('e')) width = Math.max(min, width + dx);
        if (handle.includes('s')) height = Math.max(min, height + dy);
        if (handle.includes('w')) {
            const nw = Math.max(min, width - dx);
            x += width - nw;
            width = nw;
        }
        if (handle.includes('n')) {
            const nh = Math.max(min, height - dy);
            y += height - nh;
            height = nh;
        }
        if (preserveAspect && (handle === 'se' || handle === 'nw' || handle === 'ne' || handle === 'sw')) {
            height = width / ar;
            if (handle.includes('n')) y = layer.y + layer.height - height;
            if (handle.includes('w')) x = layer.x + layer.width - width;
        }
        layer.x = x;
        layer.y = y;
        layer.width = width;
        layer.height = height;
    }

    function bindCanvasInteraction(canvasEl, getScene, getView, viewportEl, hooks) {
        options = hooks || {};
        const state = createInteraction(hooks);

        function docFromEvent(ev) {
            const rect = viewportEl.getBoundingClientRect();
            const view = getView();
            view._hostW = rect.width;
            view._hostH = rect.height;
            const scene = getScene();
            return Coords.viewportToDocument(
                ev.clientX - rect.left,
                ev.clientY - rect.top,
                view,
                scene.canvas.width,
                scene.canvas.height,
                { width: rect.width, height: rect.height },
            );
        }

        function onPointerDown(ev) {
            if (ev.button !== 0 && ev.pointerType !== 'touch') return;
            const scene = getScene();
            const doc = docFromEvent(ev);
            const layer = hitTest(scene, doc.x, doc.y);
            if (!layer) {
                state.selectedIds = [];
                hooks.onSelectionChange?.([]);
                hooks.renderChrome?.();
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            canvasEl.setPointerCapture(ev.pointerId);
            state.pointerId = ev.pointerId;
            state.mode = 'drag';
            state.startDoc = doc;
            state.startLayer = Schema.cloneScene({ layers: [layer] }).layers[0];
            state.selectedIds = ev.shiftKey && state.selectedIds.includes(layer.id)
                ? state.selectedIds.filter((id) => id !== layer.id)
                : ev.shiftKey
                    ? [...state.selectedIds, layer.id]
                    : [layer.id];
            hooks.onSelectionChange?.(state.selectedIds);
            hooks.renderChrome?.();
        }

        function onPointerMove(ev) {
            if (state.pointerId !== ev.pointerId || state.mode !== 'drag' || !state.startLayer) return;
            const doc = docFromEvent(ev);
            const dx = doc.x - state.startDoc.x;
            const dy = doc.y - state.startDoc.y;
            const scene = getScene();
            const layer = scene.layers.find((l) => l.id === state.startLayer.id);
            if (!layer || layer.locked) return;
            layer.x = state.startLayer.x + dx;
            layer.y = state.startLayer.y + dy;
            hooks.onLayerChange?.(layer, { transient: true });
        }

        function onPointerUp(ev) {
            if (state.pointerId !== ev.pointerId) return;
            try { canvasEl.releasePointerCapture(ev.pointerId); } catch (_) { /* noop */ }
            if (state.mode === 'drag' && state.startLayer) {
                hooks.onGestureEnd?.('move');
            }
            state.mode = 'idle';
            state.pointerId = null;
            state.startLayer = null;
        }

        canvasEl.addEventListener('pointerdown', onPointerDown);
        canvasEl.addEventListener('pointermove', onPointerMove);
        canvasEl.addEventListener('pointerup', onPointerUp);
        canvasEl.addEventListener('pointercancel', onPointerUp);

        return {
            destroy() {
                canvasEl.removeEventListener('pointerdown', onPointerDown);
                canvasEl.removeEventListener('pointermove', onPointerMove);
                canvasEl.removeEventListener('pointerup', onPointerUp);
                canvasEl.removeEventListener('pointercancel', onPointerUp);
            },
            getSelection: () => state.selectedIds.slice(),
            resizeLayer,
            HANDLES,
        };
    }

    global.PCSInteraction = {
        bindCanvasInteraction,
        hitTest,
        resizeLayer,
        HANDLES,
    };
}(typeof window !== 'undefined' ? window : globalThis));
