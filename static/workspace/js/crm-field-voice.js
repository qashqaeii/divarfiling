(function (global) {
    'use strict';

    /** @type {WeakMap<HTMLElement, { stop: function(): void }>} */
    const adaptersByRoot = new WeakMap();

    const FIELD_MIC_ARIA_START = 'شروع ورود صوتی';
    const FIELD_MIC_ARIA_STOP = 'توقف ورود صوتی';
    const FIELD_MIC_TOOLTIP = 'ورود صوتی';

    function findFieldInput(wrap) {
        const direct = wrap.querySelector(':scope > .crm-field-voice__wrap > .crm-input, :scope > .crm-field-voice__wrap > .crm-textarea');
        if (direct) return direct;
        return wrap.querySelector('.crm-input, .crm-textarea');
    }

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

            const adapter = Voice.createVoiceInputAdapter(wrap, {
                input: input,
                micBtn: micBtn,
                voiceStatusEl: statusEl,
                micAriaStart: FIELD_MIC_ARIA_START,
                micAriaStop: FIELD_MIC_ARIA_STOP,
                micTooltip: FIELD_MIC_TOOLTIP,
                setInputValue: function (text) {
                    input.value = text;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                },
                isInputDisabled: function () {
                    return !!input.disabled;
                },
            });

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
