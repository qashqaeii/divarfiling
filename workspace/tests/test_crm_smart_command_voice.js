'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const voice = require(path.join(
    __dirname,
    '..',
    '..',
    'static',
    'workspace',
    'js',
    'crm-smart-command-voice.js',
));

function makeDom() {
    const classes = new Set();
    const root = {
        classList: {
            toggle(name, on) {
                if (on) classes.add(name);
                else classes.delete(name);
            },
        },
    };
    const micBtn = {
        classList: {
            items: new Set(),
            add(n) {
                this.items.add(n);
            },
            remove(n) {
                this.items.delete(n);
            },
            toggle(n, on) {
                if (on) this.items.add(n);
                else this.items.delete(n);
            },
        },
        listeners: {},
        addEventListener(type, fn) {
            this.listeners[type] = fn;
        },
        removeEventListener(type) {
            delete this.listeners[type];
        },
        click() {
            this.listeners.click && this.listeners.click();
        },
        setAttribute() {},
        title: '',
    };
    const statusEl = {
        textContent: '',
        hidden: true,
        classList: {
            items: new Set(),
            add(n) {
                this.items.add(n);
            },
            remove(n) {
                this.items.delete(n);
            },
        },
    };
    const input = { value: '', disabled: false, focus() {}, addEventListener() {} };
    return { root, micBtn, statusEl, input };
}

test('isSpeechRecognitionSupported false without API', () => {
    assert.equal(voice.isSpeechRecognitionSupported({}), false);
});

test('isSpeechRecognitionSupported true when constructor present', () => {
    assert.equal(
        voice.isSpeechRecognitionSupported({ webkitSpeechRecognition: function Mock() {} }),
        true,
    );
});

test('mapSpeechError maps known codes', () => {
    assert.equal(voice.mapSpeechError('not-allowed'), voice.MSG_MIC_DENIED);
    assert.equal(voice.mapSpeechError('no-speech'), voice.MSG_NO_SPEECH);
    assert.equal(voice.mapSpeechError('audio-capture'), voice.MSG_AUDIO_CAPTURE);
    assert.equal(voice.mapSpeechError('network'), voice.MSG_NETWORK);
    assert.equal(voice.mapSpeechError('unsupported'), voice.MSG_UNSUPPORTED);
    assert.equal(voice.mapSpeechError('aborted', { userCancelled: true }), null);
});

test('final transcript fills input via setInputValue', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    let captured = '';

    class MockRecognition {
        constructor() {
            MockRecognition.last = this;
        }
        start() {
            this.onstart && this.onstart();
            this.onresult &&
                this.onresult({
                    resultIndex: 0,
                    results: [{ isFinal: true, 0: { transcript: '  سلام دنیا  ' } }],
                });
            this.onend && this.onend();
        }
        stop() {}
    }

    const win = {
        webkitSpeechRecognition: MockRecognition,
        clearTimeout() {},
        setTimeout(fn) {
            return 1;
        },
    };

    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        setInputValue(text) {
            captured = text;
            input.value = text;
        },
        win,
    });

    micBtn.click();
    assert.equal(captured, 'سلام دنیا');
    assert.equal(adapter.getState(), 'idle');
    adapter.destroy();
});

test('cancel does not surface aborted error', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
        }
        stop() {
            this.onerror && this.onerror({ error: 'aborted' });
            this.onend && this.onend();
        }
    }

    const win = {
        webkitSpeechRecognition: MockRecognition,
        clearTimeout() {},
        setTimeout() {
            return 1;
        },
    };

    voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        setInputValue() {},
        win,
    });

    micBtn.click();
    micBtn.click();
    assert.notEqual(statusEl.textContent, voice.MSG_MIC_DENIED);
});

test('no-speech surfaces user message', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onerror && this.onerror({ error: 'no-speech' });
            this.onend && this.onend();
        }
        stop() {}
    }

    const win = {
        webkitSpeechRecognition: MockRecognition,
        clearTimeout() {},
        setTimeout() {
            return 1;
        },
    };

    voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        setInputValue() {},
        win,
    });

    micBtn.click();
    assert.equal(statusEl.textContent, voice.MSG_NO_SPEECH);
});

test('voice adapter does not call submitCommandText', () => {
    assert.equal(typeof voice.createVoiceInputAdapter, 'function');
    assert.equal(voice.createVoiceInputAdapter.length, 2);
});
