(function (global) {
    'use strict';

    const VOICE_LANG = 'fa-IR';
    /** @deprecated use SILENCE_TIMEOUT_MS — kept for tests referencing old name */
    const NO_SPEECH_TIMEOUT_MS = 12000;
    const DEFAULT_SILENCE_TIMEOUT_MS = 4000;
    const DEFAULT_RESTART_DELAY_MS = 200;
    const INITIAL_NO_SPEECH_TIMEOUT_MS = 12000;
    const MAX_NL_COMMAND_CHARS = 1500;
    const MAX_AUTO_RESTARTS_MOBILE = 2;
    const MOBILE_RESTART_DELAYS_MS = [1000, 1800];
    const MOBILE_RESTART_COOLDOWN_MS = 5000;
    const ONEND_DEBOUNCE_MS = 500;
    const NO_AUTO_RESTART_ERRORS = new Set([
        'no-speech',
        'audio-capture',
        'not-allowed',
        'service-not-allowed',
        'aborted',
    ]);

    const MSG_UNSUPPORTED =
        'ضبط صوت در این مرورگر پشتیبانی نمی‌شود. می‌توانید فرمان را تایپ کنید.';
    const MSG_MIC_DENIED =
        'دسترسی میکروفن داده نشد. از تنظیمات مرورگر اجازه میکروفن را فعال کنید.';
    const MSG_NO_SPEECH = 'صدایی تشخیص داده نشد. دوباره امتحان کنید.';
    const MSG_AUDIO_CAPTURE = 'میکروفن در دسترس نیست';
    const MSG_NETWORK = 'سرویس تشخیص صدا در دسترس نیست';
    const MSG_LISTENING = 'در حال گوش دادن… می‌توانید بین جمله‌ها مکث کنید.';
    const MSG_DONE = 'گفتار ثبت شد. متن را بررسی کنید.';
    const MSG_MOBILE_AUTO_STOP =
        'ضبط صوت متوقف شد. برای ادامه دوباره روی میکروفن بزنید.';
    const PRIVACY_NOTE =
        'صدا برای تبدیل به متن توسط سرویس تشخیص گفتار مرورگر پردازش می‌شود.';
    const MIC_TOOLTIP = 'فرمان صوتی';
    const MIC_TOOLTIP_STOP = 'توقف ضبط';
    const MIC_ARIA_START = 'شروع فرمان صوتی';
    const MIC_ARIA_STOP = 'توقف فرمان صوتی';

    /** @typedef {'idle'|'listening'|'processing'|'error'} VoiceState */
    /** @typedef {'idle'|'listening'} VoiceButtonState */

    function normalizeWhitespace(text) {
        return (text || '').replace(/\s+/g, ' ').trim();
    }

    /**
     * @param {string} base
     * @param {string} segment
     */
    function appendTranscriptSegment(base, segment) {
        const piece = normalizeWhitespace(segment);
        if (!piece) return normalizeWhitespace(base);
        const prev = normalizeWhitespace(base);
        if (!prev) return piece;
        return prev + ' ' + piece;
    }

    /**
     * @param {string} base
     * @param {string} segment
     */
    function appendTranscriptSegmentSafe(base, segment) {
        const piece = normalizeWhitespace(segment);
        if (!piece) return normalizeWhitespace(base);
        const prev = normalizeWhitespace(base);
        if (!prev) return piece;
        if (prev === piece || prev.endsWith(' ' + piece) || prev.endsWith(piece)) {
            return prev;
        }
        if (piece.startsWith(prev)) {
            return piece;
        }

        const maxOverlap = Math.min(prev.length, piece.length, 120);
        for (let len = maxOverlap; len >= 3; len -= 1) {
            if (prev.slice(-len) === piece.slice(0, len)) {
                const merged = prev + piece.slice(len);
                return normalizeWhitespace(merged);
            }
        }

        const prevWords = prev.split(' ');
        const pieceWords = piece.split(' ');
        for (let n = Math.min(6, prevWords.length, pieceWords.length); n >= 1; n -= 1) {
            const suffix = prevWords.slice(-n).join(' ');
            const prefix = pieceWords.slice(0, n).join(' ');
            if (suffix && suffix === prefix) {
                const rest = pieceWords.slice(n).join(' ');
                return rest ? appendTranscriptSegment(prev, rest) : prev;
            }
        }

        return appendTranscriptSegment(prev, piece);
    }

    /**
     * Insert dictated voice between preserved prefix/suffix (cursor or selection replacement).
     * @param {string} prefix
     * @param {string} voicePart
     * @param {string} suffix
     */
    function joinVoiceAtCursor(prefix, voicePart, suffix) {
        const voice = normalizeWhitespace(voicePart);
        const p = prefix || '';
        const s = suffix || '';
        if (!voice) {
            return p + s;
        }
        let piece = voice;
        if (p.length > 0 && !/\s$/.test(p)) {
            piece = ' ' + piece;
        }
        if (s.length > 0 && !/^\s/.test(s) && !/\s$/.test(piece)) {
            piece = piece + ' ';
        }
        return p + piece + s;
    }

    /**
     * @param {string} sessionTranscript
     * @param {string} cycleFinalTranscript
     * @param {string} cycleInterimTranscript
     */
    function combineSessionVoiceDisplay(sessionTranscript, cycleFinalTranscript, cycleInterimTranscript) {
        let out = normalizeWhitespace(sessionTranscript);
        out = appendTranscriptSegmentSafe(out, cycleFinalTranscript);
        const interim = normalizeWhitespace(cycleInterimTranscript);
        if (!interim) return out;
        if (!out) return interim;
        if (out.endsWith(interim) || out.endsWith(' ' + interim)) return out;
        return out + ' ' + interim;
    }

    /**
     * @param {string} baseInputText
     * @param {string} sessionTranscript
     * @param {string} cycleFinalTranscript
     * @param {string} cycleInterimTranscript
     */
    function buildLiveTextareaValue(
        baseInputText,
        sessionTranscript,
        cycleFinalTranscript,
        cycleInterimTranscript,
        anchorSuffix,
    ) {
        const voicePart = combineSessionVoiceDisplay(
            sessionTranscript,
            cycleFinalTranscript,
            cycleInterimTranscript,
        );
        if (anchorSuffix !== undefined) {
            return joinVoiceAtCursor(baseInputText, voicePart, anchorSuffix);
        }
        return appendTranscriptSegmentSafe(baseInputText, voicePart);
    }

    /**
     * @param {string} finalTranscript
     * @param {string} interimTranscript
     * @param {{ flushInterim?: boolean }} [options]
     */
    function finalizeVoiceTranscript(finalTranscript, interimTranscript, options) {
        const opts = options || {};
        let out = normalizeWhitespace(finalTranscript);
        const interim = normalizeWhitespace(interimTranscript);
        if (opts.flushInterim && interim) {
            out = appendTranscriptSegmentSafe(out, interim);
        }
        return out;
    }

    /**
     * @param {string} priorCycleFinal
     * @param {{ resultIndex: number, results: Array<{ isFinal: boolean, 0?: { transcript?: string } }> }} event
     */
    function applyResultEvent(priorCycleFinal, event) {
        let cycleFinalTranscript = priorCycleFinal || '';
        let cycleInterimTranscript = '';
        const results = event.results || [];
        for (let i = event.resultIndex; i < results.length; i += 1) {
            const result = results[i];
            const piece = (result[0] && result[0].transcript) || '';
            if (result.isFinal) {
                cycleFinalTranscript = appendTranscriptSegmentSafe(cycleFinalTranscript, piece);
            }
        }
        for (let j = 0; j < results.length; j += 1) {
            if (!results[j].isFinal) {
                cycleInterimTranscript += (results[j][0] && results[j][0].transcript) || '';
            }
        }
        return {
            cycleFinalTranscript,
            cycleInterimTranscript,
            finalTranscript: cycleFinalTranscript,
            interimTranscript: cycleInterimTranscript,
        };
    }

    /** @deprecated use combineSessionVoiceDisplay */
    function combineListeningDisplay(finalTranscript, interimTranscript) {
        return combineSessionVoiceDisplay('', finalTranscript, interimTranscript);
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
     * @param {Window|typeof globalThis} win
     */
    function isMobileVoiceWeb(win) {
        const w = win || global;
        const nav = w.navigator;
        if (!nav) return false;
        const ua = (nav.userAgent || '').toLowerCase();
        if (/android|iphone|ipad|ipod|mobile|webos|blackberry/i.test(ua)) {
            return true;
        }
        if (typeof w.matchMedia === 'function') {
            const coarse = w.matchMedia('(pointer: coarse)').matches;
            const narrow = w.matchMedia('(max-width: 768px)').matches;
            if (coarse && narrow) return true;
        }
        return false;
    }

    /**
     * @param {string} code
     */
    function shouldBlockAutoRestartAfterError(code) {
        return NO_AUTO_RESTART_ERRORS.has((code || '').trim());
    }

    /**
     * @param {number} restartIndex 0-based index of the next restart
     */
    function getMobileRestartDelayMs(restartIndex) {
        const idx = Math.max(0, Math.min(restartIndex, MOBILE_RESTART_DELAYS_MS.length - 1));
        return MOBILE_RESTART_DELAYS_MS[idx];
    }

    /**
     * @param {string} code
     * @param {{ userCancelled?: boolean }} [options]
     * @returns {string|null}
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
     *   getInputValue?: function(): string,
     *   isInputDisabled?: function(): boolean,
     *   silenceTimeoutMs?: number,
     *   restartDelayMs?: number,
     *   forceMobileVoice?: boolean,
     *   micAriaStart?: string,
     *   micAriaStop?: string,
     *   micTooltip?: string,
     *   getSelectionRange?: function(): { start: number, end: number }|null,
     *   setSelectionRange?: function(number, number): void,
     *   win?: Window,
     *   doc?: Document,
     * }} config
     */
    function createVoiceInputAdapter(root, config) {
        const win = config.win || global;
        const doc = config.doc || (win && win.document) || null;
        const forceMobileVoice = !!config.forceMobileVoice;
        const input = config.input;
        const micBtn = config.micBtn;
        const voiceStatusEl = config.voiceStatusEl || null;
        const setInputValue = config.setInputValue;
        const getInputValue = config.getInputValue || function () {
            return (input && (input.value || '').trim()) || '';
        };
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
        let sessionFinalized = false;
        let recognitionActive = false;
        let recognitionStarting = false;
        let recognitionStopping = false;
        let gotAnySpeech = false;
        let blockAutoRestart = false;
        let autoRestartCount = 0;
        let lastRestartAt = 0;
        let lastOnEndHandledAt = 0;
        let nowMs = function () {
            return Date.now();
        };

        function isMobileClient() {
            return forceMobileVoice || isMobileVoiceWeb(win);
        }

        let baseInputText = '';
        /** @type {string|undefined} */
        let anchorSuffix = undefined;
        let sessionTranscript = '';
        let cycleFinalTranscript = '';
        let cycleInterimTranscript = '';

        const getSelectionRange = config.getSelectionRange;
        const setSelectionRange = config.setSelectionRange;

        function captureListenAnchor() {
            const full = getInputValue();
            let start = full.length;
            let end = full.length;
            if (typeof getSelectionRange === 'function') {
                const range = getSelectionRange();
                if (range && Number.isFinite(range.start) && Number.isFinite(range.end)) {
                    start = range.start;
                    end = range.end;
                }
            } else if (input && typeof input.selectionStart === 'number') {
                start = input.selectionStart;
                end = input.selectionEnd;
            }
            start = Math.max(0, Math.min(start, full.length));
            end = Math.max(start, Math.min(end, full.length));
            if (
                typeof getSelectionRange === 'function'
                || (input && typeof input.selectionStart === 'number')
            ) {
                baseInputText = full.slice(0, start);
                anchorSuffix = full.slice(end);
            } else {
                baseInputText = full;
                anchorSuffix = undefined;
            }
        }

        function composeLiveInputValue() {
            return buildLiveTextareaValue(
                baseInputText,
                sessionTranscript,
                cycleFinalTranscript,
                cycleInterimTranscript,
                anchorSuffix,
            );
        }

        const micAriaStart = config.micAriaStart || MIC_ARIA_START;
        const micAriaStop = config.micAriaStop || MIC_ARIA_STOP;
        const micTooltipLabel = config.micTooltip || MIC_TOOLTIP;
        const privacyTitle = micTooltipLabel + ' — ' + PRIVACY_NOTE;
        const queryMicBtn =
            typeof micBtn.querySelector === 'function' ? micBtn.querySelector.bind(micBtn) : null;
        const voiceIconEl = queryMicBtn
            ? queryMicBtn('[data-sc="voice-icon"]')
                || queryMicBtn('.crm-nl-command__voice-icon')
                || queryMicBtn('.crm-field-voice__mic-icon')
            : null;

        /**
         * @param {VoiceButtonState} mode
         */
        function setVoiceButtonState(mode) {
            const listening = mode === 'listening';
            micBtn.classList.toggle('is-listening', listening);
            micBtn.setAttribute('aria-pressed', listening ? 'true' : 'false');
            micBtn.setAttribute('aria-label', listening ? micAriaStop : micAriaStart);
            if (supported) {
                micBtn.title = listening ? MIC_TOOLTIP_STOP : privacyTitle;
            }
            if (voiceIconEl && voiceIconEl.classList) {
                voiceIconEl.classList.toggle('fa-microphone', !listening);
                voiceIconEl.classList.toggle('fa-stop', listening);
                voiceIconEl.classList.toggle('crm-nl-command__voice-icon--stop', listening);
                voiceIconEl.classList.toggle('crm-field-voice__mic-icon--stop', listening);
            }
        }

        setVoiceButtonState('idle');
        if (!supported) {
            micBtn.title = MSG_UNSUPPORTED;
        }

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

        function resetCycleBuffers() {
            cycleFinalTranscript = '';
            cycleInterimTranscript = '';
        }

        function resetSessionBuffers() {
            baseInputText = '';
            anchorSuffix = undefined;
            sessionTranscript = '';
            resetCycleBuffers();
        }

        function setVoiceState(next, statusMessage) {
            voiceState = next;
            root.classList.toggle('is-voice-listening', next === 'listening');
            micBtn.classList.toggle('is-processing', next === 'processing');
            setVoiceButtonState(next === 'listening' ? 'listening' : 'idle');
            setVoiceStatusEl(voiceStatusEl, next, statusMessage);
        }

        function syncLiveInput() {
            setInputValue(composeLiveInputValue());
        }

        function resetSilenceTimer() {
            clearSilenceTimer();
            if (!userStartedListening || manualStop || sessionFinalized) return;
            silenceTimer = win.setTimeout(function () {
                if (!userStartedListening || manualStop || sessionFinalized) return;
                endListeningDueToSilence();
            }, silenceTimeoutMs);
        }

        function markSpeechActivity() {
            gotAnySpeech = true;
            clearInitialNoSpeechTimer();
            resetSilenceTimer();
        }

        function commitCycleToSession() {
            if (cycleFinalTranscript) {
                sessionTranscript = appendTranscriptSegmentSafe(sessionTranscript, cycleFinalTranscript);
            }
            const interim = normalizeWhitespace(cycleInterimTranscript);
            if (interim) {
                sessionTranscript = appendTranscriptSegmentSafe(sessionTranscript, cycleInterimTranscript);
            }
            resetCycleBuffers();
        }

        function buildFinalSessionText(flushRemainingInterim) {
            let voiceText = normalizeWhitespace(sessionTranscript);
            voiceText = appendTranscriptSegmentSafe(voiceText, cycleFinalTranscript);
            if (flushRemainingInterim) {
                voiceText = appendTranscriptSegmentSafe(voiceText, cycleInterimTranscript);
            }
            if (anchorSuffix !== undefined) {
                return joinVoiceAtCursor(baseInputText, voiceText, anchorSuffix);
            }
            return appendTranscriptSegmentSafe(baseInputText, voiceText);
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
                recognitionStopping = true;
                recognition.stop();
            } catch (_e) {
                recognitionStopping = false;
            }
        }

        function getRecognitionLifecycleState() {
            if (recognitionStopping) return 'stopping';
            if (recognitionStarting) return 'starting';
            if (recognitionActive) return 'listening';
            return 'idle';
        }

        function teardownRecognition(skipStop) {
            if (recognition) {
                detachRecognitionHandlers(recognition);
                if (!skipStop) {
                    try {
                        recognitionStopping = true;
                        recognition.stop();
                    } catch (_e) {
                        recognitionStopping = false;
                    }
                }
                recognition = null;
            }
            recognitionActive = false;
            recognitionStarting = false;
            recognitionStopping = false;
        }

        function finalizeMobileAutoStop() {
            manualStop = true;
            finalizeSession({
                flushInterim: true,
                statusMessage: MSG_MOBILE_AUTO_STOP,
            });
        }

        function finalizeSession(options) {
            if (sessionFinalized) return;
            const opts = options || {};
            sessionFinalized = true;
            userStartedListening = false;

            commitCycleToSession();
            const finalText = normalizeWhitespace(
                buildFinalSessionText(!!opts.flushInterim),
            );
            if (finalText) {
                setInputValue(finalText);
                if (typeof setSelectionRange === 'function' && anchorSuffix !== undefined) {
                    const caret = finalText.length - anchorSuffix.length;
                    setSelectionRange(caret, caret);
                }
            }
            if (input) {
                input.focus();
            }

            resetSessionBuffers();
            manualStop = false;
            suspendDueToBackground = false;
            clearAllTimers();
            teardownRecognition(true);

            const statusMessage = opts.statusMessage || (gotAnySpeech ? MSG_DONE : MSG_NO_SPEECH);
            if (opts.isError) {
                setVoiceState('error', statusMessage);
            } else if (statusMessage) {
                setVoiceState('idle', statusMessage);
            } else {
                setVoiceState('idle');
            }
        }

        function endListeningDueToSilence() {
            manualStop = true;
            stopRecognitionInstance();
            finalizeSession({
                flushInterim: true,
                statusMessage: gotAnySpeech ? MSG_DONE : MSG_NO_SPEECH,
                isError: !gotAnySpeech,
            });
        }

        function endManualStop() {
            manualStop = true;
            userCancelled = true;
            stopRecognitionInstance();
            finalizeSession({
                flushInterim: true,
                statusMessage: MSG_DONE,
            });
        }

        function bindRecognitionHandlers(rec) {
            rec.onstart = function () {
                recognitionActive = true;
                recognitionStarting = false;
                recognitionStopping = false;
                lastOnEndHandledAt = 0;
                setVoiceState('listening');
            };

            rec.onspeechstart = function () {
                markSpeechActivity();
            };

            rec.onresult = function (event) {
                markSpeechActivity();
                const applied = applyResultEvent(cycleFinalTranscript, event);
                cycleFinalTranscript = applied.cycleFinalTranscript;
                cycleInterimTranscript = applied.cycleInterimTranscript;
                syncLiveInput();
                setVoiceState('listening');
            };

            rec.onerror = function (event) {
                const code = (event && event.error) || '';
                if (shouldBlockAutoRestartAfterError(code)) {
                    blockAutoRestart = true;
                }
                if (code === 'no-speech' && userStartedListening && !manualStop && gotAnySpeech) {
                    return;
                }
                if (code === 'aborted' && (userCancelled || manualStop || suspendDueToBackground)) {
                    return;
                }
                manualStop = true;
                const msg = mapSpeechError(code, { userCancelled: userCancelled && code === 'aborted' });
                if (msg && !gotAnySpeech) {
                    finalizeSession({ isError: true, statusMessage: msg });
                } else if (msg) {
                    finalizeSession({ flushInterim: true, statusMessage: msg, isError: true });
                } else {
                    finalizeSession({ flushInterim: true });
                }
            };

            rec.onend = function () {
                const endedAt = nowMs();
                if (endedAt - lastOnEndHandledAt < ONEND_DEBOUNCE_MS) {
                    return;
                }
                lastOnEndHandledAt = endedAt;

                recognitionActive = false;
                recognitionStarting = false;
                recognitionStopping = false;
                recognition = null;
                if (sessionFinalized) {
                    return;
                }
                if (suspendDueToBackground) {
                    finalizeSession({
                        flushInterim: true,
                        statusMessage: gotAnySpeech ? MSG_DONE : '',
                    });
                    return;
                }
                if (manualStop || !userStartedListening) {
                    return;
                }
                commitCycleToSession();
                syncLiveInput();
                if (blockAutoRestart) {
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
            if (!userStartedListening || manualStop || suspendDueToBackground || sessionFinalized) {
                return false;
            }
            if (getRecognitionLifecycleState() !== 'idle') return false;
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
            if (!userStartedListening || manualStop || suspendDueToBackground || sessionFinalized) {
                return;
            }
            if (blockAutoRestart) return;
            if (getRecognitionLifecycleState() !== 'idle') return;
            if (restartTimer) return;
            const delay = isMobileClient()
                ? getMobileRestartDelayMs(autoRestartCount)
                : restartDelayMs;
            restartTimer = win.setTimeout(function () {
                restartTimer = null;
                if (!userStartedListening || manualStop || suspendDueToBackground || sessionFinalized) {
                    return;
                }
                if (blockAutoRestart) return;
                if (getRecognitionLifecycleState() !== 'idle') return;
                if (isMobileClient()) {
                    if (autoRestartCount >= MAX_AUTO_RESTARTS_MOBILE) {
                        finalizeMobileAutoStop();
                        return;
                    }
                    const sinceRestart = nowMs() - lastRestartAt;
                    if (lastRestartAt > 0 && sinceRestart < MOBILE_RESTART_COOLDOWN_MS) {
                        finalizeMobileAutoStop();
                        return;
                    }
                    autoRestartCount += 1;
                    lastRestartAt = nowMs();
                }
                if (!startRecognitionNow()) {
                    if (
                        !isMobileClient() &&
                        userStartedListening &&
                        !manualStop &&
                        !suspendDueToBackground &&
                        !sessionFinalized
                    ) {
                        safeStartRecognition();
                    } else if (isMobileClient()) {
                        finalizeMobileAutoStop();
                    }
                }
            }, delay);
        }

        function scheduleRecognitionRestart() {
            clearRestartTimer();
            if (blockAutoRestart) return;
            if (isMobileClient()) {
                if (autoRestartCount >= MAX_AUTO_RESTARTS_MOBILE) {
                    finalizeMobileAutoStop();
                    return;
                }
                const sinceRestart = nowMs() - lastRestartAt;
                if (lastRestartAt > 0 && sinceRestart < MOBILE_RESTART_COOLDOWN_MS) {
                    finalizeMobileAutoStop();
                    return;
                }
            }
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
            clearAllTimers();

            userStartedListening = true;
            manualStop = false;
            userCancelled = false;
            suspendDueToBackground = false;
            sessionFinalized = false;
            gotAnySpeech = false;
            blockAutoRestart = false;
            autoRestartCount = 0;
            lastRestartAt = 0;
            lastOnEndHandledAt = 0;

            captureListenAnchor();
            sessionTranscript = '';
            resetCycleBuffers();

            clearInitialNoSpeechTimer();
            initialNoSpeechTimer = win.setTimeout(function () {
                if (userStartedListening && !gotAnySpeech && !manualStop && !sessionFinalized) {
                    manualStop = true;
                    stopRecognitionInstance();
                    finalizeSession({ isError: true, statusMessage: MSG_NO_SPEECH });
                }
            }, INITIAL_NO_SPEECH_TIMEOUT_MS);

            resetSilenceTimer();
            syncLiveInput();
            setVoiceState('listening');

            if (!startRecognitionNow()) {
                safeStartRecognition();
            }
        }

        function onMicClick() {
            if (!supported) {
                setVoiceState('error', MSG_UNSUPPORTED);
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
            if (!userStartedListening || manualStop || sessionFinalized) return;
            suspendDueToBackground = true;
            manualStop = true;
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
                clearAllTimers();
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
            _test: {
                getSessionTranscript: function () {
                    return sessionTranscript;
                },
                getCycleFinalTranscript: function () {
                    return cycleFinalTranscript;
                },
                getCycleInterimTranscript: function () {
                    return cycleInterimTranscript;
                },
                getBaseInputText: function () {
                    return baseInputText;
                },
                getLiveText: function () {
                    return composeLiveInputValue();
                },
                getAnchorPrefix: function () {
                    return baseInputText;
                },
                getAnchorSuffix: function () {
                    return anchorSuffix;
                },
                /** @deprecated */
                getFinalTranscript: function () {
                    return buildFinalSessionText(true);
                },
                isUserListening: function () {
                    return userStartedListening && !sessionFinalized;
                },
                commitCycleToSession: commitCycleToSession,
                triggerSilenceTimeout: endListeningDueToSilence,
                simulateOnEnd: function () {
                    commitCycleToSession();
                    syncLiveInput();
                    scheduleRecognitionRestart();
                },
                getAutoRestartCount: function () {
                    return autoRestartCount;
                },
                getRecognitionLifecycleState: getRecognitionLifecycleState,
                isMobileClient: isMobileClient,
                setNowMs: function (fn) {
                    nowMs = typeof fn === 'function' ? fn : function () { return Date.now(); };
                },
            },
        };
    }

    const api = {
        VOICE_LANG,
        MAX_NL_COMMAND_CHARS,
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
        MSG_MOBILE_AUTO_STOP,
        MAX_AUTO_RESTARTS_MOBILE,
        MOBILE_RESTART_DELAYS_MS,
        MOBILE_RESTART_COOLDOWN_MS,
        ONEND_DEBOUNCE_MS,
        PRIVACY_NOTE,
        MIC_TOOLTIP,
        MIC_TOOLTIP_STOP,
        MIC_ARIA_START,
        MIC_ARIA_STOP,
        appendTranscriptSegment,
        appendTranscriptSegmentSafe,
        joinVoiceAtCursor,
        combineSessionVoiceDisplay,
        buildLiveTextareaValue,
        combineListeningDisplay,
        finalizeVoiceTranscript,
        applyResultEvent,
        getSpeechRecognitionConstructor,
        isSpeechRecognitionSupported,
        isMobileVoiceWeb,
        shouldBlockAutoRestartAfterError,
        getMobileRestartDelayMs,
        mapSpeechError,
        createVoiceInputAdapter,
    };

    global.CrmSmartCommandVoice = api;
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
