(function (global) {
    'use strict';

    /** @type {WeakMap<HTMLElement, { stop: function(): void }>} */
    const adaptersByRoot = new WeakMap();

    const FIELD_MIC_ARIA_START = 'ورود با صدا';
    const FIELD_MIC_ARIA_STOP = 'توقف ضبط';
    const FIELD_MIC_TOOLTIP = 'ورود با صدا';

    /**
     * @param {HTMLElement|null} el
     */
    function isContentEditableField(el) {
        if (!el) return false;
        return el.isContentEditable || el.getAttribute('contenteditable') === 'true';
    }

    /**
     * @param {HTMLElement|null} el
     */
    function getFieldPlainText(el) {
        if (!el) return '';
        if (isContentEditableField(el)) {
            return (el.innerText || '').replace(/\s+/g, ' ').trim();
        }
        return (el.value || '').trim();
    }

    /**
     * @param {HTMLElement|null} el
     * @param {string} text
     */
    function setFieldPlainText(el, text) {
        if (!el) return;
        if (isContentEditableField(el)) {
            el.innerText = text;
            el.classList.toggle('is-empty', !String(text || '').trim());
        } else {
            el.value = text;
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    /**
     * @param {HTMLElement} wrap
     * @returns {HTMLElement|null}
     */
    function findFieldInput(wrap) {
        const wrapEl = wrap.querySelector(':scope > .crm-field-voice__wrap');
        if (wrapEl) {
            const direct = wrapEl.querySelector(
                '.crm-input, .crm-textarea, .ws-input, .ws-textarea, .crm-msg-composer-field, .crm-act-content, .agency-space-publish-note__input, .mk-share-msg-input, [data-crm-field-voice-editor], [contenteditable="true"]',
            );
            if (direct) return direct;
        }
        return wrap.querySelector(
            '.crm-input, .crm-textarea, .ws-input, .ws-textarea, .crm-msg-composer-field, .crm-act-content, .agency-space-publish-note__input, .mk-share-msg-input, [data-crm-field-voice-editor], [contenteditable="true"]',
        );
    }

    /**
     * @param {ParentNode|Document} scope
     * @param {HTMLElement} exceptWrap
     */
    function stopOtherFieldVoices(scope, exceptWrap) {
        scope.querySelectorAll('[data-crm-field-voice]').forEach(function (otherWrap) {
            if (otherWrap === exceptWrap) return;
            const other = adaptersByRoot.get(otherWrap);
            if (other && typeof other.stop === 'function') other.stop();
        });
    }

    /**
     * @param {ParentNode|Document} [root]
     */
    function initCRMFieldVoice(root) {
        const Voice = global.CrmSmartCommandVoice;
        if (!Voice || typeof Voice.createVoiceInputAdapter !== 'function') return;

        const scope = root && typeof root.querySelectorAll === 'function' ? root : document;
        scope.querySelectorAll('[data-crm-field-voice]').forEach(function (wrap) {
            if (wrap.dataset.crmFieldVoiceReady === '1') return;

            const input = findFieldInput(wrap);
            const micBtn = wrap.querySelector('[data-crm-field-voice-mic]');
            const statusEl = wrap.querySelector('[data-crm-field-voice-status]');
            if (!input || !micBtn) return;

            var silenceAttr = wrap.getAttribute('data-crm-field-voice-silence-ms');
            var silenceMs = silenceAttr ? parseInt(silenceAttr, 10) : NaN;
            var adapterConfig = {
                input: input,
                micBtn: micBtn,
                voiceStatusEl: statusEl,
                micAriaStart: FIELD_MIC_ARIA_START,
                micAriaStop: FIELD_MIC_ARIA_STOP,
                micTooltip: FIELD_MIC_TOOLTIP,
                getInputValue: function () {
                    return getFieldPlainText(input);
                },
                setInputValue: function (text) {
                    setFieldPlainText(input, text);
                },
                getSelectionRange: function () {
                    if (isContentEditableField(input)) {
                        return { start: null, end: null };
                    }
                    if (typeof input.selectionStart === 'number' && typeof input.selectionEnd === 'number') {
                        return { start: input.selectionStart, end: input.selectionEnd };
                    }
                    return { start: null, end: null };
                },
                setSelectionRange: function (start, end) {
                    if (isContentEditableField(input)) return;
                    if (typeof input.setSelectionRange === 'function') {
                        try {
                            input.setSelectionRange(start, end);
                        } catch (_e) {
                            /* readonly or detached */
                        }
                    }
                },
                isInputDisabled: function () {
                    return !!(
                        input.disabled
                        || input.getAttribute('aria-disabled') === 'true'
                        || input.getAttribute('contenteditable') === 'false'
                    );
                },
            };
            if (!isNaN(silenceMs) && silenceMs > 0) {
                adapterConfig.silenceTimeoutMs = silenceMs;
            }
            const adapter = Voice.createVoiceInputAdapter(wrap, adapterConfig);

            micBtn.addEventListener(
                'click',
                function () {
                    stopOtherFieldVoices(scope, wrap);
                },
                true,
            );

            adaptersByRoot.set(wrap, adapter);
            wrap.dataset.crmFieldVoiceReady = '1';
        });
    }

    /**
     * @param {ParentNode|Document} [root]
     */
    function stopCRMFieldVoiceIn(root) {
        const scope = root && typeof root.querySelectorAll === 'function' ? root : document;
        scope.querySelectorAll('[data-crm-field-voice]').forEach(function (wrap) {
            const adapter = adaptersByRoot.get(wrap);
            if (adapter && typeof adapter.stop === 'function') adapter.stop();
        });
    }

    global.initCRMFieldVoice = initCRMFieldVoice;
    global.stopCRMFieldVoiceIn = stopCRMFieldVoiceIn;
})(typeof window !== 'undefined' ? window : globalThis);
