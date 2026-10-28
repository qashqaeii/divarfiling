/**
 * Pointer interaction — document coords from canvas getBoundingClientRect.
 */
(function (global) {
    'use strict';

    const Schema = global.PCSSchema;
    const Interaction = { HANDLES: ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'] };

    function docFromClient(ev, canvasEl, scene) {
        const rect = canvasEl.getBoundingClientRect();
        const cw = scene.canvas.width || 1080;
        const ch = scene.canvas.height || 1920;
        const sx = cw / Math.max(1, rect.width);
        const sy = ch / Math.max(1, rect.height);
        return {
            x: (ev.clientX - rect.left) * sx,
            y: (ev.clientY - rect.top) * sy,
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

    const HANDLE_CURSORS = {
        nw: 'nwse-resize',
        ne: 'nesw-resize',
        sw: 'nesw-resize',
        se: 'nwse-resize',
        n: 'ns-resize',
        s: 'ns-resize',
        w: 'ew-resize',
        e: 'ew-resize',
    };

    function canvasScaleXY(canvasEl, scene) {
        const rect = canvasEl.getBoundingClientRect();
        const cw = scene.canvas.width || 1080;
        const ch = scene.canvas.height || 1920;
        return {
            sx: cw / Math.max(1, rect.width),
            sy: ch / Math.max(1, rect.height),
        };
    }

    function hitTestHandle(layer, docX, docY, scene, scaleOrSx, scaleY) {
        let sx = scaleOrSx;
        let sy = scaleY;
        if (sy == null && typeof scaleOrSx === 'number') {
            sx = scaleOrSx;
            sy = scaleOrSx;
        }
        sx = sx || 1;
        sy = sy || sx;
        const padX = 14 * sx;
        const padY = 14 * sy;
        const handles = [
            ['nw', layer.x, layer.y],
            ['ne', layer.x + layer.width, layer.y],
            ['sw', layer.x, layer.y + layer.height],
            ['se', layer.x + layer.width, layer.y + layer.height],
            ['n', layer.x + layer.width / 2, layer.y],
            ['s', layer.x + layer.width / 2, layer.y + layer.height],
            ['w', layer.x, layer.y + layer.height / 2],
            ['e', layer.x + layer.width, layer.y + layer.height / 2],
        ];
        for (let i = 0; i < handles.length; i++) {
            const [name, hx, hy] = handles[i];
            if (Math.abs(docX - hx) <= padX && Math.abs(docY - hy) <= padY) return name;
        }
        return null;
    }

    function hitTestHandleAtClient(layer, clientX, clientY, canvasEl, scene) {
        const rect = canvasEl.getBoundingClientRect();
        const { sx, sy } = canvasScaleXY(canvasEl, scene);
        const docX = (clientX - rect.left) * sx;
        const docY = (clientY - rect.top) * sy;
        return hitTestHandle(layer, docX, docY, scene, sx, sy);
    }

    function clampFontSize(n) {
        return Math.min(200, Math.max(10, Math.round(n)));
    }

    function resizeLayer(layer, handle, dx, dy, opts) {
        const min = 24;
        let { x, y, width, height } = layer;
        const ar = width / Math.max(1, height);
        const preserve = opts?.preserveAspect !== false && layer.type === 'image';
        if (handle.includes('e')) width = Math.max(min, width + dx);
        if (handle.includes('w')) {
            const nw = Math.max(min, width - dx);
            x += width - nw;
            width = nw;
        }
        if (handle.includes('s')) height = Math.max(min, height + dy);
        if (handle.includes('n')) {
            const nh = Math.max(min, height - dy);
            y += height - nh;
            height = nh;
        }
        if (preserve && (handle === 'se' || handle === 'nw' || handle === 'ne' || handle === 'sw')) {
            height = width / ar;
            if (handle.includes('n')) y = layer.y + layer.height - height;
            if (handle.includes('w')) x = layer.x + layer.width - width;
        }
        layer.x = x;
        layer.y = y;
        layer.width = width;
        layer.height = height;
    }

    function bindCanvasInteraction(canvasEl, getScene, viewportEl, hooks) {
        const h = hooks || {};
        const state = {
            mode: 'idle',
            pointerId: null,
            startDoc: null,
            startLayer: null,
            handle: null,
            selectedIds: [],
            checkpointed: false,
        };

        function updateHoverCursor(ev) {
            if (state.mode !== 'idle') return;
            const scene = getScene();
            if (!scene) return;
            const { sx, sy } = canvasScaleXY(canvasEl, scene);
            const doc = docFromClient(ev, canvasEl, scene);
            let cursor = 'default';
            if (state.selectedIds.length === 1) {
                const sel = scene.layers.find((l) => l.id === state.selectedIds[0]);
                if (sel && !sel.locked) {
                    const handle = hitTestHandle(sel, doc.x, doc.y, scene, sx, sy);
                    if (handle) cursor = HANDLE_CURSORS[handle] || 'nwse-resize';
                    else if (doc.x >= sel.x && doc.x <= sel.x + sel.width
                        && doc.y >= sel.y && doc.y <= sel.y + sel.height) {
                        cursor = 'move';
                    }
                }
            }
            canvasEl.style.cursor = cursor;
        }

        function onPointerDown(ev) {
            if (ev.button !== 0) return;
            const scene = getScene();
            if (!scene) return;
            const doc = docFromClient(ev, canvasEl, scene);
            const { sx, sy } = canvasScaleXY(canvasEl, scene);
            const hit = hitTest(scene, doc.x, doc.y);
            if (!hit || hit.locked) {
                state.selectedIds = [];
                h.onSelectionChange?.([]);
                h.renderChrome?.();
                canvasEl.style.cursor = 'default';
                return;
            }
            let layer = hit;
            if (!ev.shiftKey) {
                if (!state.selectedIds.includes(layer.id) || state.selectedIds.length !== 1) {
                    state.selectedIds = [layer.id];
                }
            } else if (!state.selectedIds.includes(layer.id)) {
                state.selectedIds = [...state.selectedIds, layer.id];
            }
            let handle = null;
            if (state.selectedIds.length === 1 && state.selectedIds[0] === layer.id) {
                handle = hitTestHandle(layer, doc.x, doc.y, scene, sx, sy);
            }
            ev.preventDefault();
            ev.stopPropagation();
            try { canvasEl.setPointerCapture(ev.pointerId); } catch (_) { /* noop */ }
            state.pointerId = ev.pointerId;
            state.startDoc = doc;
            state.startLayer = JSON.parse(JSON.stringify(layer));
            state.handle = handle;
            state.mode = handle ? 'resize' : 'drag';
            canvasEl.style.cursor = handle ? (HANDLE_CURSORS[handle] || 'nwse-resize') : 'move';
            h.onSelectionChange?.(state.selectedIds);
            h.onGestureStart?.();
            h.renderChrome?.();
        }

        function onPointerMove(ev) {
            if (state.pointerId !== ev.pointerId) {
                if (state.mode === 'idle') updateHoverCursor(ev);
                return;
            }
            if (state.mode === 'idle' || !state.startLayer) return;
            const scene = getScene();
            const doc = docFromClient(ev, canvasEl, scene);
            const dx = doc.x - state.startDoc.x;
            const dy = doc.y - state.startDoc.y;
            const layer = scene.layers.find((l) => l.id === state.startLayer.id);
            if (!layer || layer.locked) return;
            if (state.mode === 'drag') {
                layer.x = state.startLayer.x + dx;
                layer.y = state.startLayer.y + dy;
            } else if (state.mode === 'resize' && state.handle) {
                Object.assign(layer, JSON.parse(JSON.stringify(state.startLayer)));
                resizeLayer(layer, state.handle, dx, dy, {
                    preserveAspect: !ev.shiftKey && layer.type === 'image',
                });
                if (layer.type === 'text' || layer.type === 'bound_text') {
                    const startH = Math.max(1, state.startLayer.height);
                    const startW = Math.max(1, state.startLayer.width);
                    const scale = Math.max(
                        layer.height / startH,
                        layer.width / startW,
                    );
                    const baseFs = state.startLayer.style?.fontSize || layer.style?.fontSize || 32;
                    layer.style = layer.style || {};
                    layer.style.fontSize = Math.round(
                        clampFontSize(baseFs * scale),
                    );
                }
            }
            h.onLayerChange?.(layer, { transient: true });
        }

        function onPointerUp(ev) {
            if (state.pointerId !== ev.pointerId) return;
            try { canvasEl.releasePointerCapture(ev.pointerId); } catch (_) { /* noop */ }
            if (state.mode !== 'idle') h.onGestureEnd?.(state.mode);
            state.mode = 'idle';
            state.pointerId = null;
            state.startLayer = null;
            state.handle = null;
            updateHoverCursor(ev);
        }

        canvasEl.style.touchAction = 'none';
        canvasEl.addEventListener('pointerdown', onPointerDown, true);
        canvasEl.addEventListener('pointermove', onPointerMove);
        canvasEl.addEventListener('pointerup', onPointerUp);
        canvasEl.addEventListener('pointercancel', onPointerUp);

        return {
            destroy() {
                canvasEl.removeEventListener('pointerdown', onPointerDown, true);
                canvasEl.removeEventListener('pointermove', onPointerMove);
                canvasEl.removeEventListener('pointerup', onPointerUp);
                canvasEl.removeEventListener('pointercancel', onPointerUp);
            },
            getSelection: () => state.selectedIds.slice(),
            setSelection(ids) {
                state.selectedIds = ids.slice();
            },
        };
    }

    global.PCSInteraction = {
        bindCanvasInteraction,
        hitTest,
        hitTestHandleAtClient,
        resizeLayer,
        HANDLES: Interaction.HANDLES,
        HANDLE_CURSORS,
    };
}(typeof window !== 'undefined' ? window : globalThis));
