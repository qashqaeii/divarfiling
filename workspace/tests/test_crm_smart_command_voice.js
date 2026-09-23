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

function makeDom(initialInput) {
    const root = { classList: { toggle() {} } };
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
        classList: { items: new Set(), add(n) { this.items.add(n); }, remove(n) { this.items.delete(n); } },
    };
    const input = {
        value: initialInput || '',
        disabled: false,
        focus() {},
        addEventListener() {},
    };
    return { root, micBtn, statusEl, input };
}

function makeTimerWin(MockRecognition) {
    const queue = [];
    let id = 0;
    const instances = [];
    const win = {
        webkitSpeechRecognition: function Wrapped() {
            const inst = new MockRecognition(instances.length);
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
            while (queue.length && safety < 30) {
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
        document: { visibilityState: 'visible', addEventListener() {}, removeEventListener() {} },
    };
    return win;
}

function emitFinal(rec, text) {
    rec.onresult &&
        rec.onresult({
            resultIndex: 0,
            results: [{ isFinal: true, 0: { transcript: text } }],
        });
}

test('appendTranscriptSegmentSafe removes overlap duplicate', () => {
    const out = voice.appendTranscriptSegmentSafe(
        'یه مخاطب دارم احمدی',
        'احمدی دنبال آپارتمان است',
    );
    assert.equal(out, 'یه مخاطب دارم احمدی دنبال آپارتمان است');
});

test('applyResultEvent uses resultIndex once per final', () => {
    let cycle = '';
    cycle = voice.applyResultEvent(cycle, {
        resultIndex: 0,
        results: [{ isFinal: true, 0: { transcript: 'یه مخاطب دارم احمدی' } }],
    }).cycleFinalTranscript;
    cycle = voice.applyResultEvent(cycle, {
        resultIndex: 0,
        results: [{ isFinal: true, 0: { transcript: 'یه مخاطب دارم احمدی' } }],
    }).cycleFinalTranscript;
    assert.equal(cycle, 'یه مخاطب دارم احمدی');
});

test('three recognition cycles accumulate in textarea', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    let captured = '';

    class MockRecognition {
        constructor(index) {
            this.index = index;
        }
        start() {
            this.onstart && this.onstart();
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
        setInputValue(v) {
            captured = v;
            input.value = v;
        },
        win,
    });

    micBtn.click();
    emitFinal(win.instances[0], 'یه مخاطب دارم احمدی');
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(200);

    emitFinal(win.instances[1], 'دنبال آپارتمان صد و بیست متری در پونک می‌گرده');
    win.instances[1].onend && win.instances[1].onend();
    win.runTimers(200);

    emitFinal(win.instances[2], 'پارکینگ و آسانسور هم براش مهمه');
    micBtn.click();

    const expected =
        'یه مخاطب دارم احمدی دنبال آپارتمان صد و بیست متری در پونک می‌گرده پارکینگ و آسانسور هم براش مهمه';
    assert.equal(captured, expected);
    adapter.destroy();
});

test('onend restart does not wipe prior session transcript', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
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
        setInputValue(v) {
            input.value = v;
        },
        win,
    });
    micBtn.click();
    emitFinal(win.instances[0], 'بخش اول');
    assert.ok(input.value.includes('بخش اول'));
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(200);
    assert.ok(adapter._test.getSessionTranscript().includes('بخش اول'));
    assert.equal(adapter._test.isUserListening(), true);
    adapter.destroy();
});

test('base input before mic is preserved', () => {
    const { root, micBtn, statusEl, input } = makeDom('احمدی');
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
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
    emitFinal(win.instances[0], 'شماره‌اش 09121234567');
    micBtn.click();
    assert.equal(input.value, 'احمدی شماره‌اش 09121234567');
    adapter.destroy();
});

test('silence timeout finalizes all cycles', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
            this.onspeechstart && this.onspeechstart();
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
            input.value = v;
        },
        win,
    });
    micBtn.click();
    emitFinal(win.instances[0], 'جمله اول');
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(200);
    emitFinal(win.instances[1], 'جمله دوم');
    win.runTimers(4000);
    assert.equal(input.value, 'جمله اول جمله دوم');
    adapter.destroy();
});

test('long transcript is not truncated in textarea', () => {
    const chunk = 'کلمه ';
    let long = '';
    for (let i = 0; i < 220; i += 1) long = voice.appendTranscriptSegment(long, chunk + i);
    assert.ok(long.length > 1000);
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
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
    emitFinal(win.instances[0], long);
    micBtn.click();
    assert.equal(input.value.length, long.length);
    assert.ok(input.value.length > 1000);
    adapter.destroy();
});

test('mapSpeechError maps known codes', () => {
    assert.equal(voice.mapSpeechError('not-allowed'), voice.MSG_MIC_DENIED);
});
