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
        { id: 'select', icon: 'fa-arrow-pointer', label: 'انتخاب' },
        { id: 'text', icon: 'fa-font', label: 'متن' },
        { id: 'images', icon: 'fa-image', label: 'تصاویر' },
        { id: 'property', icon: 'fa-building', label: 'اطلاعات ملک' },
        { id: 'layers', icon: 'fa-layer-group', label: 'لایه‌ها' },
        { id: 'template', icon: 'fa-swatchbook', label: 'قالب' },
    ];

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

    function ensureScene(conf, ctx) {
        if (conf.scene && conf.scene.schemaVersion >= 2 && (conf.scene.layers || []).length) {
            return Schema.normalizeScene(conf.scene, ctx.templateId, ctx.formatKey, ctx.formats);
        }
        return Templates.buildInitialScene(conf, ctx, Schema.emptyScene(ctx.templateId, ctx.formatKey, ctx.formats));
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
        sidebarEl.innerHTML = TOOLS.map((t) => `
            <button type="button" class="pcs-le-tool${session.tool === t.id ? ' is-active' : ''}"
                data-pcs-le-tool="${t.id}" title="${t.label}" aria-label="${t.label}">
                <i class="fas ${t.icon}" aria-hidden="true"></i>
            </button>`).join('');
        sidebarEl.querySelectorAll('[data-pcs-le-tool]').forEach((btn) => {
            btn.addEventListener('click', () => {
                session.tool = btn.getAttribute('data-pcs-le-tool') || 'select';
                renderToolbar(sidebarEl);
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
    }

    function renderLayersList(container) {
        if (!container || !session.scene) return;
        const layers = Renderer.orderedLayers(session.scene);
        container.innerHTML = layers.map((l) => {
            const sel = session.selection.includes(l.id) ? ' is-selected' : '';
            const eye = l.visible ? 'fa-eye' : 'fa-eye-slash';
            const lock = l.locked ? 'fa-lock' : 'fa-lock-open';
            return `<div class="pcs-le-layer${sel}" data-pcs-le-layer="${l.id}" draggable="true">
                <button type="button" class="pcs-le-layer__vis" data-pcs-le-vis="${l.id}" aria-label="نمایش"><i class="fas ${eye}"></i></button>
                <button type="button" class="pcs-le-layer__lock" data-pcs-le-lock="${l.id}" aria-label="قفل"><i class="fas ${lock}"></i></button>
                <span class="pcs-le-layer__name">${l.name}</span>
                <span class="pcs-le-layer__type">${l.type}</span>
            </div>`;
        }).join('');
        container.querySelectorAll('[data-pcs-le-layer]').forEach((row) => {
            row.addEventListener('click', () => {
                session.selection = [row.getAttribute('data-pcs-le-layer')];
                renderLayersList(container);
                renderChrome();
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
                    refreshPreview(false);
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

    function renderPropertyPanel(container) {
        if (!container) return;
        const features = session.ctx?.features || [];
        const q = (session._propFilter || '').trim().toLowerCase();
        const filtered = features.filter((f) => !q || (f.label + f.key).toLowerCase().includes(q));
        container.innerHTML = `
            <input type="search" class="pcs-input pcs-le-search" placeholder="جستجو…" value="${session._propFilter || ''}" data-pcs-le-prop-search>
            <div class="pcs-le-prop-list" data-pcs-le-prop-list>
                ${filtered.map((f) => `
                    <button type="button" class="pcs-le-prop-item" draggable="true" data-pcs-le-feature="${f.key}">
                        <i class="fas ${f.icon || 'fa-circle-dot'}" aria-hidden="true"></i>
                        <span class="pcs-le-prop-item__label">${f.label}</span>
                        <span class="pcs-le-prop-item__val">${f.value || '—'}</span>
                    </button>`).join('')}
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
                refreshPreview(true);
                session.onDirty?.();
                renderPanel(document.getElementById('pcsLePanelBody'));
            });
        });
    }

    function renderPanel(bodyEl) {
        if (!bodyEl) return;
        if (session.tool === 'layers') {
            bodyEl.innerHTML = '<div class="pcs-le-layers" data-pcs-le-layers></div>';
            renderLayersList(bodyEl.querySelector('[data-pcs-le-layers]'));
            return;
        }
        if (session.tool === 'property') {
            bodyEl.innerHTML = '<div class="pcs-le-property" data-pcs-le-property></div>';
            renderPropertyPanel(bodyEl.querySelector('[data-pcs-le-property]'));
            return;
        }
        if (session.tool === 'template') {
            bodyEl.innerHTML = `<p class="pcs-le-hint">قالب: <strong>${session.tpl}</strong> — تغییر قالب از لیست پوسترها.</p>
                <p class="pcs-le-hint">تنظیمات تصویر و ترکیب در بخش «تصاویر» و accordionهای پایین.</p>`;
            return;
        }
        if (session.selection.length === 1) {
            const layer = session.scene.layers.find((l) => l.id === session.selection[0]);
            if (layer && (layer.type === 'text' || layer.type === 'bound_text')) {
                bodyEl.innerHTML = `
                    <label class="pcs-le-field">متن
                        <textarea class="pcs-input" rows="3" data-pcs-le-text>${layer.text || ''}</textarea>
                    </label>
                    <label class="pcs-le-field">اندازه
                        <input type="range" min="12" max="120" value="${layer.style?.fontSize || 32}" data-pcs-le-font-size>
                    </label>`;
                const ta = bodyEl.querySelector('[data-pcs-le-text]');
                ta?.addEventListener('input', () => {
                    layer.text = ta.value;
                    layer.binding = layer.binding ? { ...layer.binding, mode: 'override' } : null;
                    History.pushHistory(session.history, session.scene, 'text');
                    refreshPreview(false);
                    session.onDirty?.();
                });
                History.endMerge(session.history);
                return;
            }
        }
        bodyEl.innerHTML = '<p class="pcs-le-hint">یک لایه روی بوم انتخاب کنید یا از «اطلاعات ملک» ویژگی اضافه کنید.</p>';
    }

    function renderChrome() {
        const viewport = document.getElementById('pcsEditorPreviewViewport');
        session.chromeEl?.remove();
        if (!viewport || !session.scene || session.selection.length !== 1) return;
        const layer = session.scene.layers.find((l) => l.id === session.selection[0]);
        if (!layer || !layer.visible) return;
        const canvas = viewport.querySelector('.pcs-canvas');
        if (!canvas) return;
        const rect = viewport.getBoundingClientRect();
        const view = session.view;
        view._hostW = rect.width;
        view._hostH = rect.height;
        const tl = Coords.documentToViewport(layer.x, layer.y, view, session.scene.canvas.width, session.scene.canvas.height, { width: rect.width, height: rect.height });
        const s = tl.scale;
        const chrome = document.createElement('div');
        chrome.className = 'pcs-le-chrome';
        chrome.style.cssText = `position:absolute;left:${tl.x}px;top:${tl.y}px;width:${layer.width * s}px;height:${layer.height * s}px;pointer-events:none;border:2px solid #7c3aed;box-sizing:border-box;z-index:40;`;
        viewport.appendChild(chrome);
        session.chromeEl = chrome;
    }

    function refreshPreview(fullRebuild) {
        const preview = document.getElementById('pcsEditorPreview');
        const bridge = global.PCSBridge;
        if (!preview || !bridge || !session.scene) return;
        Bindings.syncLinkedLayers(session.scene, session.ctx);
        if (fullRebuild || !preview.querySelector('.pcs-canvas')) {
            const html = bridge.buildCanvasHtml(session.tpl, session.formatKey, session.posterConf);
            preview.innerHTML = html;
            bridge.syncCanvasTypography?.(preview);
        }
        const canvas = preview.querySelector('.pcs-canvas');
        if (canvas) {
            Renderer.mountSceneOnCanvas(canvas, session.scene, session.ctx, session.posterConf);
        }
        bridge.scheduleEditorPreviewScale?.(preview, session.formatKey);
        renderChrome();
    }

    function bindDrop(viewport) {
        viewport?.addEventListener('dragover', (ev) => {
            if (ev.dataTransfer?.types?.includes('application/x-pcs-feature')) {
                ev.preventDefault();
            }
        });
        viewport?.addEventListener('drop', (ev) => {
            const key = ev.dataTransfer?.getData('application/x-pcs-feature');
            if (!key || !session.scene) return;
            ev.preventDefault();
            const rect = viewport.getBoundingClientRect();
            const view = session.view;
            const doc = Coords.viewportToDocument(
                ev.clientX - rect.left,
                ev.clientY - rect.top,
                view,
                session.scene.canvas.width,
                session.scene.canvas.height,
                { width: rect.width, height: rect.height },
            );
            const entry = (session.ctx.features || []).find((f) => f.key === key);
            if (!entry) return;
            Templates.addFeatureLayer(session.scene, entry, doc, 'plain');
            History.pushHistory(session.history, session.scene);
            refreshPreview(false);
            session.onDirty?.();
            renderPanel(document.getElementById('pcsLePanelBody'));
        });
    }

    function mountLayerEditorLayout() {
        const editor = document.getElementById('pcsEditor');
        if (!editor || editor.querySelector('.pcs-le-workspace')) return;
        const workspace = editor.querySelector('.pcs-editor__workspace');
        if (!workspace) return;
        workspace.classList.add('pcs-le-workspace');
        workspace.innerHTML = `
            <aside class="pcs-le-rail" aria-label="ابزارها">
                <div class="pcs-le-rail__tools" id="pcsLeTools"></div>
            </aside>
            <aside class="pcs-le-panel" id="pcsLePanel">
                <header class="pcs-le-panel__head">
                    <span id="pcsLePanelTitle">ویژگی‌ها</span>
                    <button type="button" class="pcs-le-panel__collapse" id="pcsLePanelCollapse" aria-label="بستن پنل"><i class="fas fa-chevron-right"></i></button>
                </header>
                <div class="pcs-le-panel__body" id="pcsLePanelBody"></div>
            </aside>
            <div class="pcs-le-canvas-host">
                <div class="pcs-editor__preview-pane is-active" data-pcs-editor-pane="preview">
                    <div class="pcs-editor__preview-stage pcs-le-stage">
                        <div class="pcs-le-top-tools" id="pcsLeTopTools">
                            <button type="button" class="pcs-le-top-btn" data-pcs-le-undo title="Undo"><i class="fas fa-rotate-left"></i></button>
                            <button type="button" class="pcs-le-top-btn" data-pcs-le-redo title="Redo"><i class="fas fa-rotate-right"></i></button>
                            <button type="button" class="pcs-le-top-btn" data-pcs-le-fit title="Fit">Fit</button>
                        </div>
                        <div class="pcs-editor__preview-viewport" id="pcsEditorPreviewViewport">
                            <div class="pcs-editor__preview" id="pcsEditorPreview"></div>
                        </div>
                    </div>
                </div>
                <div class="pcs-le-settings-host" id="pcsLeLegacySettings"></div>
            </div>`;
        const legacyControls = document.getElementById('pcsEditorControls');
        const host = document.getElementById('pcsLeLegacySettings');
        if (legacyControls && host) host.appendChild(legacyControls);
        renderToolbar(document.getElementById('pcsLeTools'));
        document.getElementById('pcsLePanelCollapse')?.addEventListener('click', () => {
            document.getElementById('pcsLePanel')?.classList.toggle('is-collapsed');
        });
        document.querySelector('[data-pcs-le-undo]')?.addEventListener('click', () => {
            const prev = History.undo(session.history, session.scene);
            if (prev) {
                session.scene = Schema.normalizeScene(prev, session.tpl, session.formatKey);
                refreshPreview(true);
                session.onDirty?.();
            }
        });
        document.querySelector('[data-pcs-le-redo]')?.addEventListener('click', () => {
            const next = History.redo(session.history, session.scene);
            if (next) {
                session.scene = Schema.normalizeScene(next, session.tpl, session.formatKey);
                refreshPreview(true);
                session.onDirty?.();
            }
        });
        document.querySelector('[data-pcs-le-fit]')?.addEventListener('click', () => {
            fitView();
            refreshPreview(false);
        });
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
        mountLayerEditorLayout();
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
        };
        session.scene = ensureScene(session.posterConf, session.ctx);
        session.posterConf.scene = session.scene;
        session.view = Coords.createViewState();
        session.history = History.createHistory();
        History.pushHistory(session.history, session.scene);
        session.onDirty = opts.onDirty;
        session.onCommitScene = opts.onCommitScene;
        session.selection = [];
        fitView();
        renderPanel(document.getElementById('pcsLePanelBody'));
        refreshPreview(true);
        const viewport = document.getElementById('pcsEditorPreviewViewport');
        bindDrop(viewport);
        const canvas = viewport?.querySelector('.pcs-canvas');
        session.interaction?.destroy?.();
        if (canvas) {
            session.interaction = Interaction.bindCanvasInteraction(
                canvas,
                () => session.scene,
                () => session.view,
                viewport,
                {
                    onSelectionChange(ids) {
                        session.selection = ids;
                        renderPanel(document.getElementById('pcsLePanelBody'));
                        renderChrome();
                    },
                    onLayerChange(layer, meta) {
                        Renderer.updateLayerDom(canvas, layer, session.ctx, session.posterConf);
                        renderChrome();
                        if (!meta?.transient) session.onDirty?.();
                    },
                    onGestureEnd() {
                        History.pushHistory(session.history, session.scene);
                        syncSceneToPosterConf(session.posterConf, session.scene);
                        session.onDirty?.();
                    },
                    renderChrome,
                },
            );
        }
    }

    function commitToBuffer(buffer) {
        if (!session.active || !buffer) return buffer;
        syncSceneToPosterConf(buffer, session.scene);
        return buffer;
    }

    function stop() {
        session.interaction?.destroy?.();
        session.active = false;
        session.scene = null;
        session.chromeEl?.remove();
    }

    function refreshFromLegacyControls(conf) {
        if (!session.active) return;
        session.posterConf = conf;
        if (conf.scene) session.scene = Schema.normalizeScene(conf.scene, session.tpl, session.formatKey);
        refreshPreview(true);
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
