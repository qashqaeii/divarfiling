(function (global) {
    'use strict';

    const VOICE_LANG = 'fa-IR';
    /** @deprecated use SILENCE_TIMEOUT_MS — kept for tests referencing old name */
    const NO_SPEECH_TIMEOUT_MS = 12000;
    const DEFAULT_SILENCE_TIMEOUT_MS = 4000;
    const DEFAULT_RESTART_DELAY_MS = 200;
    const INITIAL_NO_SPEECH_TIMEOUT_MS = 12000;

    const MSG_UNSUPPORTED =
        'ضبط صوت در این مرورگر پشتیبانی نمی‌شود. می‌توانید فرمان را تایپ کنید.';
    const MSG_MIC_DENIED =
        'دسترسی میکروفن داده نشد. از تنظیمات مرورگر اجازه میکروفن را فعال کنید.';
    const MSG_NO_SPEECH = 'صدایی تشخیص داده نشد. دوباره امتحان کنید.';
    const MSG_AUDIO_CAPTURE = 'میکروفن در دسترس نیست';
    const MSG_NETWORK = 'سرویس تشخیص صدا در دسترس نیست';
    const MSG_LISTENING = 'در حال گوش دادن… می‌توانید بین جمله‌ها مکث کنید.';
    const MSG_DONE = 'گفتار ثبت شد. متن را بررسی کنید.';
    const PRIVACY_NOTE =
        'صدا برای تبدیل به متن توسط سرویس تشخیص گفتار مرورگر پردازش می‌شود.';
    const MIC_TOOLTIP = 'فرمان صوتی';

    /** @typedef {'idle'|'listening'|'processing'|'error'} VoiceState */

    /**
     * @param {string} base
     * @param {string} segment
     */
    function appendTranscriptSegment(base, segment) {
        const piece = (segment || '').trim();
        if (!piece) return (base || '').trim();
        const prev = (base || '').trim();
        if (!prev) return piece;
        return prev + ' ' + piece;
    }

    /**
     * @param {string} finalTranscript
     * @param {string} interimTranscript
     */
    function combineListeningDisplay(finalTranscript, interimTranscript) {
        const fin = (finalTranscript || '').trim();
        const interim = (interimTranscript || '').trim();
        if (!interim) return fin;
        if (!fin) return interim;
        return fin + ' ' + interim;
    }

    /**
     * @param {string} finalTranscript
     * @param {string} interimTranscript
     * @param {{ flushInterim?: boolean }} [options]
     */
    function finalizeVoiceTranscript(finalTranscript, interimTranscript, options) {
        const opts = options || {};
        let out = (finalTranscript || '').trim();
        const interim = (interimTranscript || '').trim();
        if (opts.flushInterim && interim) {
            out = appendTranscriptSegment(out, interim);
        }
        return out.replace(/\s+/g, ' ').trim();
    }

    /**
     * Process Web Speech onresult slice (from resultIndex).
     * @param {string} priorFinal
     * @param {{ resultIndex: number, results: Array<{ isFinal: boolean, 0?: { transcript?: string } }> }} event
     * @returns {{ finalTranscript: string, interimTranscript: string }}
     */
    function applyResultEvent(priorFinal, event) {
        let finalTranscript = priorFinal || '';
        let interimTranscript = '';
        const results = event.results || [];
        for (let i = event.resultIndex; i < results.length; i += 1) {
            const result = results[i];
            const piece = (result[0] && result[0].transcript) || '';
            if (result.isFinal) {
                finalTranscript = appendTranscriptSegment(finalTranscript, piece);
            }
        }
        for (let j = 0; j < results.length; j += 1) {
            if (!results[j].isFinal) {
                interimTranscript += (results[j][0] && results[j][0].transcript) || '';
            }
        }
        return { finalTranscript, interimTranscript };
    }

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
        if ((state === 'processing' || state === 'idle') && text) {
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
     *   silenceTimeoutMs?: number,
     *   restartDelayMs?: number,
     *   win?: Window,
     *   doc?: Document,
     * }} config
     */
    function createVoiceInputAdapter(root, config) {
        const win = config.win || global;
        const doc = config.doc || (win && win.document) || null;
        const input = config.input;
        const micBtn = config.micBtn;
        const voiceStatusEl = config.voiceStatusEl || null;
        const setInputValue = config.setInputValue;
        const isInputDisabled = config.isInputDisabled || (() => !!(input && input.disabled));
        const silenceTimeoutMs = config.silenceTimeoutMs || DEFAULT_SILENCE_TIMEOUT_MS;
        const restartDelayMs = config.restartDelayMs || DEFAULT_RESTART_DELAY_MS;

        if (!root || !micBtn) {
            return { destroy: function () {}, getState: function () { return 'idle'; } };
        }

        const SpeechRecognitionCtor = getSpeechRecognitionConstructor(win);
        const supported = !!SpeechRecognitionCtor;

        /** @type {VoiceState} */
        let voiceState = 'idle';
        let recognition = null;
        let silenceTimer = null;
        let initialNoSpeechTimer = null;
        let restartTimer = null;
        let userStartedListening = false;
        let manualStop = false;
        let userCancelled = false;
        let suspendDueToBackground = false;
        let recognitionActive = false;
        let recognitionStarting = false;
        let gotAnySpeech = false;
        let finalTranscript = '';
        let interimTranscript = '';

        const privacyTitle = MIC_TOOLTIP + ' — ' + PRIVACY_NOTE;
        micBtn.setAttribute('aria-label', MIC_TOOLTIP);
        micBtn.title = supported ? privacyTitle : MSG_UNSUPPORTED;

        if (!supported) {
            micBtn.classList.add('is-unsupported');
            micBtn.setAttribute('aria-disabled', 'true');
        }

        function clearSilenceTimer() {
            if (silenceTimer) {
                win.clearTimeout(silenceTimer);
                silenceTimer = null;
            }
        }

        function clearInitialNoSpeechTimer() {
            if (initialNoSpeechTimer) {
                win.clearTimeout(initialNoSpeechTimer);
                initialNoSpeechTimer = null;
            }
        }

        function clearRestartTimer() {
            if (restartTimer) {
                win.clearTimeout(restartTimer);
                restartTimer = null;
            }
        }

        function clearAllTimers() {
            clearSilenceTimer();
            clearInitialNoSpeechTimer();
            clearRestartTimer();
        }

        function setVoiceState(next, statusMessage) {
            voiceState = next;
            root.classList.toggle('is-voice-listening', next === 'listening');
            micBtn.classList.toggle('is-listening', next === 'listening');
            micBtn.classList.toggle('is-processing', next === 'processing');
            micBtn.setAttribute('aria-pressed', next === 'listening' ? 'true' : 'false');
            setVoiceStatusEl(voiceStatusEl, next, statusMessage);
        }

        function syncLiveInput() {
            const display = combineListeningDisplay(finalTranscript, interimTranscript);
            setInputValue(display);
        }

        function resetSilenceTimer() {
            clearSilenceTimer();
            if (!userStartedListening || manualStop) return;
            silenceTimer = win.setTimeout(function () {
                if (!userStartedListening || manualStop) return;
                endListeningDueToSilence();
            }, silenceTimeoutMs);
        }

        function markSpeechActivity() {
            gotAnySpeech = true;
            clearInitialNoSpeechTimer();
            resetSilenceTimer();
        }

        function detachRecognitionHandlers(rec) {
            if (!rec) return;
            rec.onstart = null;
            rec.onresult = null;
            rec.onerror = null;
            rec.onend = null;
            rec.onspeechstart = null;
        }

        function stopRecognitionInstance() {
            if (!recognition) return;
            try {
                recognition.stop();
            } catch (_e) {
                /* ignore */
            }
        }

        function teardownRecognition(skipStop) {
            clearAllTimers();
            if (recognition) {
                detachRecognitionHandlers(recognition);
                if (!skipStop) {
                    try {
                        recognition.stop();
                    } catch (_e) {
                        /* ignore */
                    }
                }
                recognition = null;
            }
            recognitionActive = false;
            recognitionStarting = false;
        }

        function finishSession(options) {
            const opts = options || {};
            const flushInterim = !!opts.flushInterim;
            const statusMessage = opts.statusMessage || (gotAnySpeech ? MSG_DONE : MSG_NO_SPEECH);
            const isError = !!opts.isError;

            userStartedListening = false;
            manualStop = false;
            suspendDueToBackground = false;
            interimTranscript = '';
            const committed = finalizeVoiceTranscript(finalTranscript, opts.pendingInterim || '', {
                flushInterim,
            });
            if (committed) {
                setInputValue(committed);
                finalTranscript = committed;
            }
            if (input) {
                input.focus();
            }
            teardownRecognition(true);
            if (isError) {
                setVoiceState('error', statusMessage);
            } else if (statusMessage) {
                setVoiceState('idle', statusMessage);
            } else {
                setVoiceState('idle');
            }
        }

        function endListeningDueToSilence() {
            manualStop = true;
            userStartedListening = false;
            stopRecognitionInstance();
            finishSession({
                flushInterim: true,
                pendingInterim: interimTranscript,
                statusMessage: gotAnySpeech ? MSG_DONE : MSG_NO_SPEECH,
                isError: !gotAnySpeech,
            });
        }

        function endManualStop() {
            manualStop = true;
            userStartedListening = false;
            userCancelled = true;
            clearAllTimers();
            stopRecognitionInstance();
            finishSession({
                flushInterim: true,
                pendingInterim: interimTranscript,
                statusMessage: gotAnySpeech ? MSG_DONE : MSG_DONE,
            });
        }

        function bindRecognitionHandlers(rec) {
            rec.onstart = function () {
                recognitionActive = true;
                recognitionStarting = false;
                setVoiceState('listening');
                resetSilenceTimer();
            };

            rec.onspeechstart = function () {
                markSpeechActivity();
            };

            rec.onresult = function (event) {
                markSpeechActivity();
                const applied = applyResultEvent(finalTranscript, event);
                finalTranscript = applied.finalTranscript;
                interimTranscript = applied.interimTranscript;
                syncLiveInput();
                setVoiceState('listening');
            };

            rec.onerror = function (event) {
                const code = (event && event.error) || '';
                if (code === 'no-speech' && userStartedListening && !manualStop && gotAnySpeech) {
                    return;
                }
                if (code === 'aborted' && (userCancelled || manualStop || suspendDueToBackground)) {
                    return;
                }
                clearAllTimers();
                const msg = mapSpeechError(code, { userCancelled: userCancelled && code === 'aborted' });
                userStartedListening = false;
                manualStop = true;
                if (msg && !gotAnySpeech) {
                    finishSession({ isError: true, statusMessage: msg });
                } else if (msg) {
                    finishSession({ flushInterim: true, pendingInterim: interimTranscript, statusMessage: msg, isError: true });
                } else {
                    finishSession({ flushInterim: true, pendingInterim: interimTranscript });
                }
            };

            rec.onend = function () {
                recognitionActive = false;
                recognition = null;
                if (suspendDueToBackground) {
                    finishSession({
                        flushInterim: true,
                        pendingInterim: interimTranscript,
                        statusMessage: gotAnySpeech ? MSG_DONE : '',
                    });
                    return;
                }
                if (manualStop || !userStartedListening) {
                    return;
                }
                scheduleRecognitionRestart();
            };
        }

        function createRecognitionInstance() {
            const rec = new SpeechRecognitionCtor();
            rec.lang = VOICE_LANG;
            rec.continuous = true;
            rec.interimResults = true;
            rec.maxAlternatives = 1;
            bindRecognitionHandlers(rec);
            return rec;
        }

        function startRecognitionNow() {
            if (!supported || !SpeechRecognitionCtor) return false;
            if (!userStartedListening || manualStop || suspendDueToBackground) return false;
            if (recognitionStarting || recognitionActive) return false;
            recognitionStarting = true;
            try {
                recognition = createRecognitionInstance();
                recognition.start();
                return true;
            } catch (_err) {
                recognitionStarting = false;
                recognition = null;
                return false;
            }
        }

        function safeStartRecognition() {
            if (!supported || !SpeechRecognitionCtor) return;
            if (!userStartedListening || manualStop || suspendDueToBackground) return;
            if (recognitionStarting || recognitionActive) return;
            if (restartTimer) return;
            restartTimer = win.setTimeout(function () {
                restartTimer = null;
                if (!startRecognitionNow()) {
                    if (userStartedListening && !manualStop && !suspendDueToBackground) {
                        safeStartRecognition();
                    }
                }
            }, restartDelayMs);
        }

        function scheduleRecognitionRestart() {
            clearRestartTimer();
            safeStartRecognition();
        }

        function startListeningSession() {
            if (!supported || !SpeechRecognitionCtor) {
                setVoiceState('error', MSG_UNSUPPORTED);
                return;
            }
            if (isInputDisabled()) {
                return;
            }

            teardownRecognition(true);
            userStartedListening = true;
            manualStop = false;
            userCancelled = false;
            suspendDueToBackground = false;
            gotAnySpeech = false;
            interimTranscript = '';
            finalTranscript = (input && (input.value || '').trim()) || '';

            clearInitialNoSpeechTimer();
            initialNoSpeechTimer = win.setTimeout(function () {
                if (userStartedListening && !gotAnySpeech && !manualStop) {
                    manualStop = true;
                    userStartedListening = false;
                    stopRecognitionInstance();
                    finishSession({ isError: true, statusMessage: MSG_NO_SPEECH });
                }
            }, INITIAL_NO_SPEECH_TIMEOUT_MS);

            if (!startRecognitionNow()) {
                safeStartRecognition();
            }
        }

        function onMicClick() {
            if (!supported) {
                setVoiceState('error', MSG_UNSUPPORTED);
                return;
            }
            if (userStartedListening && voiceState === 'listening') {
                endManualStop();
                return;
            }
            if (userStartedListening) {
                endManualStop();
                return;
            }
            startListeningSession();
        }

        function onMicKeydown(ev) {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                onMicClick();
            }
        }

        function onVisibilityChange() {
            if (!doc || doc.visibilityState !== 'hidden') return;
            if (!userStartedListening || manualStop) return;
            suspendDueToBackground = true;
            manualStop = true;
            userStartedListening = false;
            stopRecognitionInstance();
        }

        micBtn.addEventListener('click', onMicClick);
        micBtn.addEventListener('keydown', onMicKeydown);
        if (doc && typeof doc.addEventListener === 'function') {
            doc.addEventListener('visibilitychange', onVisibilityChange);
        }

        function externalStop() {
            if (!userStartedListening && voiceState !== 'listening') return;
            endManualStop();
        }

        return {
            destroy: function () {
                externalStop();
                teardownRecognition(true);
                micBtn.removeEventListener('click', onMicClick);
                micBtn.removeEventListener('keydown', onMicKeydown);
                if (doc && typeof doc.removeEventListener === 'function') {
                    doc.removeEventListener('visibilitychange', onVisibilityChange);
                }
            },
            getState: function () {
                return voiceState;
            },
            stop: externalStop,
            /** @internal test hooks */
            _test: {
                getFinalTranscript: function () {
                    return finalTranscript;
                },
                getInterimTranscript: function () {
                    return interimTranscript;
                },
                isUserListening: function () {
                    return userStartedListening;
                },
                triggerSilenceTimeout: endListeningDueToSilence,
            },
        };
    }

    const api = {
        VOICE_LANG,
        NO_SPEECH_TIMEOUT_MS,
        DEFAULT_SILENCE_TIMEOUT_MS,
        DEFAULT_RESTART_DELAY_MS,
        INITIAL_NO_SPEECH_TIMEOUT_MS,
        MSG_UNSUPPORTED,
        MSG_MIC_DENIED,
        MSG_NO_SPEECH,
        MSG_AUDIO_CAPTURE,
        MSG_NETWORK,
        MSG_LISTENING,
        MSG_DONE,
        PRIVACY_NOTE,
        MIC_TOOLTIP,
        appendTranscriptSegment,
        combineListeningDisplay,
        finalizeVoiceTranscript,
        applyResultEvent,
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
