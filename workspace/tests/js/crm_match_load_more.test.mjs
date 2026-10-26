/**
 * رفتار Load More — باید با crmFinishMatchLoadMore / pager در crm.js هم‌خوان بماند.
 */
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CRM_JS = join(__dirname, '../../../static/workspace/js/crm.js');

function makeBtn() {
    const state = { disabled: false, hidden: false };
    return {
        get disabled() { return state.disabled; },
        set disabled(v) { state.disabled = v; },
        get hidden() { return state.hidden; },
        set hidden(v) { state.hidden = v; },
        isConnected: true,
        classList: {
            _s: new Set(),
            add(c) { this._s.add(c); },
            remove(c) { this._s.delete(c); },
            contains(c) { return this._s.has(c); },
        },
    };
}

/** قرارداد pager پس از اصلاح: disabled فقط وقتی complete است */
function applyPagerBtnState(btn, loaded, total) {
    const complete = total > 0 && loaded >= total;
    btn.hidden = complete;
    btn.disabled = complete;
}

function finishLoadMore(btn, updatePager) {
    if (btn && btn.isConnected) btn.classList.remove('is-loading');
    if (typeof updatePager === 'function') updatePager();
    if (btn && btn.isConnected && !btn.hidden) btn.disabled = false;
}

function applyTypeFilter(cards, type) {
    let shown = 0;
    cards.forEach((row) => {
        const match = type === 'all' || row.customerType === type;
        row.hidden = !match;
        if (match) shown += 1;
    });
    return shown;
}

test('sequential three pages: button re-enabled when has_more', () => {
    const btn = makeBtn();
    const total = 100;
    let loaded = 0;
    const pageSize = 24;
    for (let page = 1; page <= 3; page += 1) {
        btn.disabled = true;
        btn.classList.add('is-loading');
        loaded += pageSize;
        const hasMore = loaded < total;
        finishLoadMore(btn, () => applyPagerBtnState(btn, loaded, total));
        assert.equal(btn.classList.contains('is-loading'), false, `page ${page}: is-loading cleared`);
        if (hasMore) {
            assert.equal(btn.disabled, false, `page ${page}: button enabled`);
            assert.equal(btn.hidden, false, `page ${page}: button visible`);
        }
    }
});

test('filter preserved after append and new type adds tab', () => {
    const cards = [
        { customerType: 'خریدار', hidden: false },
        { customerType: 'خریدار', hidden: false },
    ];
    applyTypeFilter(cards, 'خریدار');
    assert.equal(cards.every((c) => !c.hidden), true);
    cards.push({ customerType: 'مستاجر', hidden: false });
    applyTypeFilter(cards, 'خریدار');
    assert.equal(cards[0].hidden, false);
    assert.equal(cards[1].hidden, false);
    assert.equal(cards[2].hidden, true);
    const types = [...new Set(cards.map((c) => c.customerType))];
    assert.equal(types.length, 2);
});

test('selection state survives filter reapply', () => {
    const cards = [
        { customerType: 'خریدار', hidden: false, checked: true },
        { customerType: 'مستاجر', hidden: true, checked: false },
    ];
    applyTypeFilter(cards, 'خریدار');
    const selected = cards.filter((c) => c.checked);
    assert.equal(selected.length, 1);
    cards.push({ customerType: 'خریدار', hidden: false, checked: false });
    applyTypeFilter(cards, 'خریدار');
    assert.equal(cards.filter((c) => c.checked).length, 1);
});

test('crm.js contains finish helper and pager disabled contract', () => {
    const src = readFileSync(CRM_JS, 'utf8');
    assert.match(src, /function crmFinishMatchLoadMore/);
    assert.match(src, /btn\.disabled = complete/);
    assert.match(src, /crmRefreshPropMatchTypeChips\(root, \{ preserveActive: true \}\)/);
});
