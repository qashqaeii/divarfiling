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
    const root = {
        classList: { toggle() {} },
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

function makeTimerWin(MockRecognition, opts) {
    const options = opts || {};
    const queue = [];
    let id = 0;
    const instances = [];
    const win = {
        webkitSpeechRecognition: function Wrapped() {
            const inst = new MockRecognition();
            instances.push(inst);
            Wrapped.last = inst;
            return inst;
        },
        clearTimeout(t) {
            const idx = queue.findIndex((q) => q.id === t);
            if (idx >= 0) queue.splice(idx, 1);
        },
        setTimeout(fn, ms) {
            id += 1;
            const entry = { id, fn, ms };
            queue.push(entry);
            return id;
        },
        runTimers(filterMs) {
            let safety = 0;
            while (queue.length && safety < 20) {
                safety += 1;
                const pending = queue.splice(0, queue.length);
                pending
                    .filter((p) => (filterMs == null ? true : p.ms === filterMs))
                    .forEach((p) => p.fn());
                if (filterMs != null) break;
            }
        },
        get instances() {
            return instances;
        },
    };
    win.document = options.doc || {
        visibilityState: 'visible',
        addEventListener() {},
        removeEventListener() {},
    };
    return win;
}

test('appendTranscriptSegment joins multiple finals with spaces', () => {
    let t = voice.appendTranscriptSegment('', 'یه فایل پونک دارم');
    t = voice.appendTranscriptSegment(t, 'صد و بیست متر دو خواب');
    t = voice.appendTranscriptSegment(t, 'فروش دوازده میلیارد');
    assert.equal(t, 'یه فایل پونک دارم صد و بیست متر دو خواب فروش دوازده میلیارد');
});

test('interim then final does not duplicate phrase', () => {
    const first = voice.applyResultEvent('', {
        resultIndex: 0,
        results: [{ isFinal: false, 0: { transcript: 'سلام' } }],
    });
    assert.equal(first.interimTranscript, 'سلام');
    const second = voice.applyResultEvent(first.finalTranscript, {
        resultIndex: 0,
        results: [
            { isFinal: true, 0: { transcript: 'سلام' } },
            { isFinal: false, 0: { transcript: ' دنیا' } },
        ],
    });
    assert.equal(second.finalTranscript, 'سلام');
    assert.equal(second.interimTranscript.trim(), 'دنیا');
});

test('combineListeningDisplay merges buffers for live UI', () => {
    assert.equal(
        voice.combineListeningDisplay('بخش اول', 'بخش موقت'),
        'بخش اول بخش موقت',
    );
});

test('finalizeVoiceTranscript flushes interim on manual stop', () => {
    assert.equal(
        voice.finalizeVoiceTranscript('قطعه نهایی', 'موقت', { flushInterim: true }),
        'قطعه نهایی موقت',
    );
});

test('mapSpeechError maps known codes', () => {
    assert.equal(voice.mapSpeechError('not-allowed'), voice.MSG_MIC_DENIED);
    assert.equal(voice.mapSpeechError('aborted', { userCancelled: true }), null);
});

test('multiple final segments append in adapter', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onresult &&
                this.onresult({
                    resultIndex: 0,
                    results: [{ isFinal: true, 0: { transcript: 'یه فایل پونک دارم' } }],
                });
        }
        stop() {
            this.onend && this.onend();
        }
    }

    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });

    micBtn.click();
    const rec = win.instances[0];
    rec.onresult &&
        rec.onresult({
            resultIndex: 0,
            results: [{ isFinal: true, 0: { transcript: 'صد و بیست متر دو خواب' } }],
        });
    assert.equal(
        adapter._test.getFinalTranscript(),
        'یه فایل پونک دارم صد و بیست متر دو خواب',
    );
    adapter.destroy();
});

test('short pause keeps session listening via onend restart', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onresult &&
                this.onresult({
                    resultIndex: 0,
                    results: [{ isFinal: true, 0: { transcript: 'جمله اول' } }],
                });
            this.onend && this.onend();
        }
        stop() {}
    }

    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        restartDelayMs: 200,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });

    micBtn.click();
    assert.equal(adapter._test.isUserListening(), true);
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(200);
    assert.equal(win.instances.length, 2);
    assert.equal(adapter._test.isUserListening(), true);
    micBtn.click();
    adapter.destroy();
});

test('silence timeout stops and keeps transcript', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    let captured = '';

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onspeechstart && this.onspeechstart();
            this.onresult &&
                this.onresult({
                    resultIndex: 0,
                    results: [{ isFinal: true, 0: { transcript: 'متن ثبت شده' } }],
                });
        }
        stop() {
            this.onend && this.onend();
        }
    }

    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        silenceTimeoutMs: 4000,
        setInputValue(v) {
            captured = v;
        },
        win,
    });

    micBtn.click();
    win.runTimers(4000);
    assert.equal(captured, 'متن ثبت شده');
    assert.equal(statusEl.textContent, voice.MSG_DONE);
    assert.equal(adapter._test.isUserListening(), false);
    adapter.destroy();
});

test('manual stop prevents restart', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onend && this.onend();
        }
        stop() {
            this.onend && this.onend();
        }
    }

    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        restartDelayMs: 200,
        setInputValue() {},
        win,
    });

    micBtn.click();
    const countAfterStart = win.instances.length;
    micBtn.click();
    win.runTimers(200);
    assert.equal(win.instances.length, countAfterStart);
    assert.equal(adapter._test.isUserListening(), false);
    adapter.destroy();
});

test('restart start exception does not crash UI', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    let starts = 0;

    class MockRecognition {
        start() {
            starts += 1;
            if (starts === 1) {
                this.onstart && this.onstart();
                this.onend && this.onend();
                return;
            }
            throw new Error('already started');
        }
        stop() {}
    }

    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        restartDelayMs: 200,
        setInputValue() {},
        win,
    });

    micBtn.click();
    win.runTimers(200);
    win.runTimers(200);
    assert.equal(adapter.getState(), 'listening');
    micBtn.click();
    adapter.destroy();
});

test('long transcript is not truncated by voice layer', () => {
    const chunk = 'کلمه ';
    let long = '';
    for (let i = 0; i < 300; i += 1) long = voice.appendTranscriptSegment(long, chunk + i);
    assert.ok(long.length > 1000);
    assert.equal(voice.finalizeVoiceTranscript(long, ''), long);
});

test('no-speech error on empty session', () => {
    const { root, micBtn, statusEl, input } = makeDom();

    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onerror && this.onerror({ error: 'no-speech' });
            this.onend && this.onend();
        }
        stop() {}
    }

    const win = makeTimerWin(MockRecognition);
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
