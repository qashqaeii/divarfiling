/* نقشه تعاملی فایل شخصی CRM — تغییر موقعیت با تأیید */
(function (global) {
    'use strict';

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input?.value) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function fmtCoord(n) {
        return Number(n).toFixed(6);
    }

    function syncDrawerInputs(lat, lng) {
        const latInput = document.querySelector('#id_latitude, [name="latitude"]');
        const lngInput = document.querySelector('#id_longitude, [name="longitude"]');
        if (latInput) latInput.value = fmtCoord(lat);
        if (lngInput) lngInput.value = fmtCoord(lng);
    }

    function updateNavLinks(root, nav) {
        if (!root || !nav) return;
        const google = root.querySelector('[data-map-nav="google"]');
        const neshan = root.querySelector('[data-map-nav="neshan"]');
        const waze = root.querySelector('[data-map-nav="waze"]');
        if (google && nav.google_url) {
            google.href = nav.google_url;
            google.hidden = false;
        }
        if (neshan && nav.neshan_url) {
            neshan.href = nav.neshan_url;
            neshan.hidden = false;
        }
        if (waze && nav.waze_url) {
            waze.href = nav.waze_url;
            waze.hidden = false;
        }
        root.querySelector('[data-map-nav-actions]')?.removeAttribute('hidden');
    }

    function updatePlaceHint(root, lat, lng) {
        const el = root.querySelector('[data-map-coords]');
        if (el) {
            el.textContent = `${fmtCoord(lat)} ، ${fmtCoord(lng)}`;
            el.hidden = false;
        }
    }

    function initCrmPropertyMap(config) {
        const root = document.getElementById(config.rootId || 'crmPropMapFinale');
        if (!root || typeof global.initListingDetailMap !== 'function') return null;

        const dock = root.querySelector('[data-map-edit-dock]');
        const dockCoords = root.querySelector('[data-map-edit-coords]');
        const dockHint = root.querySelector('[data-map-edit-hint]');
        const confirmBtn = root.querySelector('[data-map-edit-confirm]');
        const cancelBtn = root.querySelector('[data-map-edit-cancel]');
        const emptyHint = root.querySelector('[data-map-empty-hint]');
        const marker = config.marker || {};
        const editable = !!config.editable;
        let saving = false;
        let mapApi = null;

        function setDockVisible(visible, state) {
            if (!dock) return;
            dock.hidden = !visible;
            dock.classList.toggle('is-saving', !!state?.saving);
            if (confirmBtn) confirmBtn.disabled = !!state?.saving;
            if (cancelBtn) cancelBtn.disabled = !!state?.saving;
        }

        function onDraftChange(state) {
            if (!editable) return;
            if (emptyHint) {
                emptyHint.hidden = !!(state.lat != null && state.lng != null);
            }
            if (!state.dirty || state.lat == null || state.lng == null) {
                setDockVisible(false);
                return;
            }
            if (dockCoords) {
                dockCoords.textContent = `${fmtCoord(state.lat)} ، ${fmtCoord(state.lng)}`;
            }
            if (dockHint) {
                dockHint.textContent = state.isNew
                    ? 'موقعیت جدید انتخاب شد — برای ذخیره تأیید کنید'
                    : 'موقعیت جابه‌جا شد — برای ذخیره تأیید کنید';
            }
            setDockVisible(true);
        }

        async function saveDraft() {
            if (!mapApi || saving || !config.saveUrl) return;
            const draft = mapApi.getDraft();
            if (!draft) return;
            saving = true;
            setDockVisible(true, { saving: true });
            try {
                const resp = await fetch(config.saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        Accept: 'application/json',
                    },
                    body: JSON.stringify({
                        latitude: draft.lat,
                        longitude: draft.lng,
                    }),
                    credentials: 'same-origin',
                });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'ذخیره موقعیت ناموفق بود.');
                }
                mapApi.commitDraft();
                syncDrawerInputs(data.latitude, data.longitude);
                updateNavLinks(root, data.map_navigation);
                updatePlaceHint(root, data.latitude, data.longitude);
                setDockVisible(false);
                root.classList.add('has-saved-location');
                root.classList.remove('is-empty-map');
                if (typeof global.showToast === 'function') {
                    global.showToast('موقعیت ملک ذخیره شد.', 'success');
                }
            } catch (err) {
                if (typeof global.showToast === 'function') {
                    global.showToast(err.message || 'خطا در ذخیره موقعیت', 'error');
                } else {
                    window.alert(err.message || 'خطا در ذخیره موقعیت');
                }
                setDockVisible(true, { saving: false });
            } finally {
                saving = false;
            }
        }

        confirmBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            saveDraft();
        });
        cancelBtn?.addEventListener('click', (e) => {
            e.preventDefault();
            mapApi?.revertDraft();
            setDockVisible(false);
            if (emptyHint && !mapApi?.hasLocation()) emptyHint.hidden = false;
        });

        const hasCoords = Number.isFinite(Number(marker.lat)) && Number.isFinite(Number(marker.lng));
        mapApi = global.initListingDetailMap({
            uiPrefix: config.uiPrefix || 'crmProp',
            mapId: config.mapId || 'crmPropLocationMap',
            stageId: config.stageId || 'crmPropLocationMapStage',
            marker,
            editable,
            zoom: config.zoom || 16,
            defaultCenter: config.defaultCenter || { lat: 35.6892, lng: 51.3890, zoom: 11 },
            onDraftChange: editable ? onDraftChange : null,
        });

        if (!mapApi) return null;

        if (emptyHint) emptyHint.hidden = hasCoords || !editable;
        if (hasCoords) root.classList.add('has-saved-location');
        else if (editable) root.classList.add('is-empty-map');

        // Lazy invalidate when scrolled into view
        if ('IntersectionObserver' in global) {
            const obs = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        mapApi.refresh?.();
                        obs.disconnect();
                    }
                });
            }, { rootMargin: '80px' });
            obs.observe(root);
        }

        return mapApi;
    }

    global.initCrmPropertyMap = initCrmPropertyMap;
}(window));
