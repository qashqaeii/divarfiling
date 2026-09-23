(function (global) {
    'use strict';

    const VOICE_LANG = 'fa-IR';
    const NO_SPEECH_TIMEOUT_MS = 12000;

    const MSG_UNSUPPORTED =
        'ضبط صوت در این مرورگر پشتیبانی نمی‌شود. می‌توانید فرمان را تایپ کنید.';
    const MSG_MIC_DENIED =
        'دسترسی میکروفن داده نشد. از تنظیمات مرورگر اجازه میکروفن را فعال کنید.';
    const MSG_NO_SPEECH = 'صدایی تشخیص داده نشد. دوباره امتحان کنید.';
    const MSG_AUDIO_CAPTURE = 'میکروفن در دسترس نیست';
    const MSG_NETWORK = 'سرویس تشخیص صدا در دسترس نیست';
    const MSG_LISTENING = 'در حال گوش دادن…';
    const PRIVACY_NOTE =
        'صدا برای تبدیل به متن توسط سرویس تشخیص گفتار مرورگر پردازش می‌شود.';
    const MIC_TOOLTIP = 'فرمان صوتی';

    /** @typedef {'idle'|'listening'|'processing'|'error'} VoiceState */

    /**
     * @param {Window|typeof globalThis} win
     * @returns {typeof SpeechRecognition|undefined}
     */
    function getSpeechRecognitionConstructor(win) {
        const w = win || global;
        return w.SpeechRecognition || w.webkitSpeechRecognition;
    }

    /**
     * @param {Window|typeof globalThis} [win]
     */
    function isSpeechRecognitionSupported(win) {
        return !!getSpeechRecognitionConstructor(win);
    }

    /**
     * @param {string} code
     * @param {{ userCancelled?: boolean }} [options]
     * @returns {string|null} null = no user-visible message
     */
    function mapSpeechError(code, options) {
        const opts = options || {};
        if (code === 'aborted' && opts.userCancelled) {
            return null;
        }
        switch (code) {
            case 'not-allowed':
            case 'service-not-allowed':
                return MSG_MIC_DENIED;
            case 'no-speech':
                return MSG_NO_SPEECH;
            case 'audio-capture':
                return MSG_AUDIO_CAPTURE;
            case 'network':
                return MSG_NETWORK;
            case 'aborted':
                return null;
            case 'unsupported':
                return MSG_UNSUPPORTED;
            default:
                return MSG_NO_SPEECH;
        }
    }

    /**
     * @param {HTMLElement|null} el
     * @param {VoiceState} state
     * @param {string} [message]
     */
    function setVoiceStatusEl(el, state, message) {
        if (!el) return;
        const text = (message || '').trim();
        if (state === 'listening' && !text) {
            el.textContent = MSG_LISTENING;
            el.hidden = false;
            el.classList.remove('is-error');
            return;
        }
        if (state === 'processing' && text) {
            el.textContent = text;
            el.hidden = false;
            el.classList.remove('is-error');
            return;
        }
        if (state === 'error' && text) {
            el.textContent = text;
            el.hidden = false;
            el.classList.add('is-error');
            return;
        }
        if (state === 'idle' || !text) {
            el.textContent = '';
            el.hidden = true;
            el.classList.remove('is-error');
        }
    }

    /**
     * @param {HTMLElement} root
     * @param {{
     *   input: HTMLTextAreaElement|null,
     *   micBtn: HTMLButtonElement|null,
     *   voiceStatusEl?: HTMLElement|null,
     *   setInputValue: function(string): void,
     *   isInputDisabled?: function(): boolean,
     *   win?: Window,
     * }} config
     */
    function createVoiceInputAdapter(root, config) {
        const win = config.win || global;
        const input = config.input;
        const micBtn = config.micBtn;
        const voiceStatusEl = config.voiceStatusEl || null;
        const setInputValue = config.setInputValue;
        const isInputDisabled = config.isInputDisabled || (() => !!(input && input.disabled));

        if (!root || !micBtn) {
            return { destroy: function () {}, getState: function () { return 'idle'; } };
        }

        const SpeechRecognitionCtor = getSpeechRecognitionConstructor(win);
        const supported = !!SpeechRecognitionCtor;

        /** @type {VoiceState} */
        let voiceState = 'idle';
        let recognition = null;
        let noSpeechTimer = null;
        let userCancelled = false;
        let gotFinalTranscript = false;

        const privacyTitle = MIC_TOOLTIP + ' — ' + PRIVACY_NOTE;
        micBtn.setAttribute('aria-label', MIC_TOOLTIP);
        micBtn.title = supported ? privacyTitle : MSG_UNSUPPORTED;

        if (!supported) {
            micBtn.classList.add('is-unsupported');
            micBtn.setAttribute('aria-disabled', 'true');
        }

        function clearNoSpeechTimer() {
            if (noSpeechTimer) {
                win.clearTimeout(noSpeechTimer);
                noSpeechTimer = null;
            }
        }

        function setVoiceState(next, statusMessage) {
            voiceState = next;
            root.classList.toggle('is-voice-listening', next === 'listening');
            micBtn.classList.toggle('is-listening', next === 'listening');
            micBtn.classList.toggle('is-processing', next === 'processing');
            micBtn.setAttribute('aria-pressed', next === 'listening' ? 'true' : 'false');
            setVoiceStatusEl(voiceStatusEl, next, statusMessage);
        }

        function teardownRecognition() {
            clearNoSpeechTimer();
            if (recognition) {
                try {
                    recognition.onstart = null;
                    recognition.onresult = null;
                    recognition.onerror = null;
                    recognition.onend = null;
                    recognition.stop();
                } catch (_e) {
                    /* ignore */
                }
                recognition = null;
            }
        }

        function stopListening(cancelled) {
            userCancelled = !!cancelled;
            clearNoSpeechTimer();
            if (recognition && voiceState === 'listening') {
                try {
                    recognition.stop();
                } catch (_e) {
                    /* ignore */
                }
            } else {
                setVoiceState('idle');
            }
        }

        function applyFinalTranscript(text) {
            const trimmed = (text || '').trim();
            if (!trimmed) return;
            setInputValue(trimmed);
            if (input) {
                input.focus();
            }
        }

        function startListening() {
            if (!supported || !SpeechRecognitionCtor) {
                setVoiceState('error', MSG_UNSUPPORTED);
                return;
            }
            if (isInputDisabled()) {
                return;
            }
            if (voiceState === 'listening') {
                stopListening(true);
                return;
            }

            teardownRecognition();
            userCancelled = false;
            gotFinalTranscript = false;

            recognition = new SpeechRecognitionCtor();
            recognition.lang = VOICE_LANG;
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;

            recognition.onstart = function () {
                setVoiceState('listening');
                clearNoSpeechTimer();
                noSpeechTimer = win.setTimeout(function () {
                    if (voiceState === 'listening' && !gotFinalTranscript) {
                        userCancelled = true;
                        try {
                            recognition && recognition.stop();
                        } catch (_e) {
                            /* ignore */
                        }
                        setVoiceState('error', MSG_NO_SPEECH);
                    }
                }, NO_SPEECH_TIMEOUT_MS);
            };

            recognition.onresult = function (event) {
                let interim = '';
                let finalText = '';
                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const result = event.results[i];
                    const piece = (result[0] && result[0].transcript) || '';
                    if (result.isFinal) {
                        finalText += piece;
                    } else {
                        interim += piece;
                    }
                }
                if (interim.trim()) {
                    setVoiceState('listening', interim.trim());
                }
                if (finalText.trim()) {
                    gotFinalTranscript = true;
                    clearNoSpeechTimer();
                    setVoiceState('processing');
                    applyFinalTranscript(finalText);
                }
            };

            recognition.onerror = function (event) {
                clearNoSpeechTimer();
                const code = (event && event.error) || '';
                const msg = mapSpeechError(code, { userCancelled: userCancelled && code === 'aborted' });
                if (msg) {
                    setVoiceState('error', msg);
                } else {
                    setVoiceState('idle');
                }
            };

            recognition.onend = function () {
                clearNoSpeechTimer();
                if (voiceState === 'listening') {
                    if (!gotFinalTranscript && !userCancelled) {
                        setVoiceState('error', MSG_NO_SPEECH);
                    } else {
                        setVoiceState('idle');
                    }
                } else if (voiceState === 'processing') {
                    setVoiceState('idle');
                } else if (voiceState === 'error') {
                    /* keep error message visible */
                }
                recognition = null;
            };

            try {
                recognition.start();
            } catch (_err) {
                setVoiceState('error', MSG_UNSUPPORTED);
                teardownRecognition();
            }
        }

        function onMicClick() {
            if (!supported) {
                setVoiceState('error', MSG_UNSUPPORTED);
                return;
            }
            if (voiceState === 'listening') {
                stopListening(true);
                return;
            }
            startListening();
        }

        function onMicKeydown(ev) {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                onMicClick();
            }
        }

        micBtn.addEventListener('click', onMicClick);
        micBtn.addEventListener('keydown', onMicKeydown);

        function onInputDisabledObserver() {
            if (isInputDisabled() && voiceState === 'listening') {
                stopListening(true);
            }
        }

        if (input) {
            input.addEventListener('focus', onInputDisabledObserver);
        }

        return {
            destroy: function () {
                stopListening(true);
                teardownRecognition();
                micBtn.removeEventListener('click', onMicClick);
                micBtn.removeEventListener('keydown', onMicKeydown);
            },
            getState: function () {
                return voiceState;
            },
            stop: function () {
                stopListening(true);
            },
        };
    }

    const api = {
        VOICE_LANG,
        NO_SPEECH_TIMEOUT_MS,
        MSG_UNSUPPORTED,
        MSG_MIC_DENIED,
        MSG_NO_SPEECH,
        MSG_AUDIO_CAPTURE,
        MSG_NETWORK,
        MSG_LISTENING,
        PRIVACY_NOTE,
        MIC_TOOLTIP,
        getSpeechRecognitionConstructor,
        isSpeechRecognitionSupported,
        mapSpeechError,
        createVoiceInputAdapter,
    };

    global.CrmSmartCommandVoice = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
