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
    const initial = initialInput || '';
    const input = {
        value: initial,
        selectionStart: initial.length,
        selectionEnd: initial.length,
        disabled: false,
        focus() {},
        setSelectionRange(start, end) {
            this.selectionStart = start;
            this.selectionEnd = end;
        },
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

test('getMobileRestartDelayMs uses progressive backoff', () => {
    assert.equal(voice.getMobileRestartDelayMs(0), 1000);
    assert.equal(voice.getMobileRestartDelayMs(1), 1800);
});

test('desktop repeated onend still restarts with short delay', () => {
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
        forceMobileVoice: false,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });
    micBtn.click();
    emitFinal(win.instances[0], 'بخش اول');
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(200);
    assert.equal(win.instances.length, 2);
    assert.equal(adapter._test.isUserListening(), true);
    adapter.destroy();
});

test('duplicate onend within debounce window is ignored', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
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
    emitFinal(win.instances[0], 'یک');
    const onend = win.instances[0].onend;
    onend && onend();
    onend && onend();
    win.runTimers(200);
    assert.equal(win.instances.length, 2);
    adapter.destroy();
});

test('mobile onend schedules at most two auto restarts then stops', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
        }
        stop() {}
    }
    const win = makeTimerWin(MockRecognition);
    let t = 10000;
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        forceMobileVoice: true,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });
    adapter._test.setNowMs(() => {
        t += 6000;
        return t;
    });

    micBtn.click();
    emitFinal(win.instances[0], 'جمله موبایل');
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(1000);
    assert.equal(win.instances.length, 2);

    emitFinal(win.instances[1], 'ادامه');
    win.instances[1].onend && win.instances[1].onend();
    win.runTimers(1800);
    assert.equal(win.instances.length, 3);
    assert.equal(adapter._test.getAutoRestartCount(), 2);

    win.instances[2].onend && win.instances[2].onend();
    assert.equal(adapter._test.isUserListening(), false);
    assert.ok(statusEl.textContent.includes('دوباره روی میکروفن'));
    assert.ok(input.value.includes('جمله موبایل'));
    adapter.destroy();
});

test('no-speech error blocks auto restart on mobile', () => {
    const { root, micBtn, statusEl, input } = makeDom();
    class MockRecognition {
        start() {
            this.onstart && this.onstart();
        }
        stop() {}
    }
    const win = makeTimerWin(MockRecognition);
    const adapter = voice.createVoiceInputAdapter(root, {
        input,
        micBtn,
        voiceStatusEl: statusEl,
        forceMobileVoice: true,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });
    micBtn.click();
    emitFinal(win.instances[0], 'بخش');
    win.instances[0].onerror && win.instances[0].onerror({ error: 'no-speech' });
    win.instances[0].onend && win.instances[0].onend();
    win.runTimers(1000);
    assert.equal(win.instances.length, 1);
    adapter.destroy();
});

test('manual stop does not auto restart', () => {
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
        forceMobileVoice: true,
        setInputValue(v) {
            input.value = v;
        },
        win,
    });
    micBtn.click();
    emitFinal(win.instances[0], 'متن');
    micBtn.click();
    win.runTimers(1000);
    assert.equal(win.instances.length, 1);
    adapter.destroy();
});

test('joinVoiceAtCursor inserts between prefix and suffix with Persian spacing', () => {
    const out = voice.joinVoiceAtCursor(
        'مشتری آپارتمان',
        'در پاسداران',
        ' دو خواب می‌خواهد',
    );
    assert.equal(out, 'مشتری آپارتمان در پاسداران دو خواب می‌خواهد');
});

test('buildLiveTextareaValue with anchorSuffix does not append to end only', () => {
    const live = voice.buildLiveTextareaValue(
        'مشتری آپارتمان',
        'در پاسداران',
        '',
        '',
        ' دو خواب می‌خواهد',
    );
    assert.equal(live, 'مشتری آپارتمان در پاسداران دو خواب می‌خواهد');
});

test('voice at cursor preserves text before and after', () => {
    const existing = 'مشتری آپارتمان دو خواب می‌خواهد';
    const cursor = existing.indexOf('دو');
    const { root, micBtn, statusEl, input } = makeDom(existing);
    input.selectionStart = cursor;
    input.selectionEnd = cursor;

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
    emitFinal(win.instances[0], 'در پاسداران');
    micBtn.click();
    assert.equal(input.value, 'مشتری آپارتمان در پاسداران دو خواب می‌خواهد');
    adapter.destroy();
});

test('voice replaces selected range', () => {
    const existing = 'مشتری آپارتمان قدیم دو خواب می‌خواهد';
    const selStart = existing.indexOf('قدیم');
    const selEnd = selStart + 'قدیم'.length;
    const { root, micBtn, statusEl, input } = makeDom(existing);
    input.selectionStart = selStart;
    input.selectionEnd = selEnd;

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
    emitFinal(win.instances[0], 'در پاسداران');
    micBtn.click();
    assert.equal(input.value, 'مشتری آپارتمان در پاسداران دو خواب می‌خواهد');
    adapter.destroy();
});

test('cursor insertion on input type text', () => {
    const existing = 'الف ب';
    const { root, micBtn, statusEl, input } = makeDom(existing);
    input.selectionStart = 4;
    input.selectionEnd = 4;

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
    emitFinal(win.instances[0], 'میان');
    micBtn.click();
    assert.equal(input.value, 'الف میان ب');
    adapter.destroy();
});
