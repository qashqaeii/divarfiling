/* CRM Module — Drawers, Search, Type Profiles, Multi-select */

function crmParseMoneyRaw(value) {
    return String(value || '').replace(/[^\d]/g, '');
}

function crmFormatMoneyDisplay(value) {
    const raw = crmParseMoneyRaw(value);
    if (!raw) return '';
    return Number(raw).toLocaleString('en-US');
}

function crmBindMoneyInput(input) {
    if (!input || input.dataset.moneyBound === '1') return;
    input.dataset.moneyBound = '1';
    input.setAttribute('type', 'text');
    input.setAttribute('inputmode', 'numeric');
    input.setAttribute('autocomplete', 'off');
    if (input.value) input.value = crmFormatMoneyDisplay(input.value);

    input.addEventListener('input', () => {
        const raw = crmParseMoneyRaw(input.value);
        const formatted = raw ? crmFormatMoneyDisplay(raw) : '';
        if (input.value === formatted) return;
        const posFromEnd = input.value.length - (input.selectionStart || 0);
        input.value = formatted;
        const newPos = Math.max(0, formatted.length - posFromEnd);
        try { input.setSelectionRange(newPos, newPos); } catch (e) { /* ignore */ }
    });

    input.addEventListener('blur', () => {
        const raw = crmParseMoneyRaw(input.value);
        input.value = raw ? crmFormatMoneyDisplay(raw) : '';
    });
}

function initCRMMoneyInputs(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-money="1"]').forEach(crmBindMoneyInput);
    scope.querySelectorAll('form').forEach(form => {
        if (form.dataset.moneySubmitBound === '1') return;
        form.dataset.moneySubmitBound = '1';
        form.addEventListener('submit', () => {
            form.querySelectorAll('[data-money="1"]').forEach(inp => {
                inp.value = crmParseMoneyRaw(inp.value);
            });
        });
    });
}

function crmToPersianDigits(value) {
    return String(value || '').replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function crmGregorianToJalali(gy, gm, gd) {
    const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let jy = gy <= 1600 ? 0 : 979;
    gy -= gy <= 1600 ? 621 : 1600;
    const gy2 = gm > 2 ? gy + 1 : gy;
    let days = (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100)
        + Math.floor((gy2 + 399) / 400) - 80 + gd + gdm[gm - 1];
    jy += 33 * Math.floor(days / 12053);
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    jy += Math.floor((days - 1) / 365);
    if (days > 365) days = (days - 1) % 365;
    const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return [jy, jm, jd];
}

function crmFormatJalaliDatetime(value) {
    if (!value) return '';
    const raw = String(value).trim();
    if (!raw || raw === '—') return raw;
    if (/^(13|14)\d{2}[/-]/.test(raw)) return crmToPersianDigits(raw.replace(/-/g, '/'));

    const match = raw.match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[T\s](\d{1,2}):(\d{2}))?/);
    if (!match) return crmToPersianDigits(raw);

    const gy = Number(match[1]);
    const gm = Number(match[2]);
    const gd = Number(match[3]);
    if (gy >= 1300 && gy <= 1500) return crmToPersianDigits(raw.replace(/-/g, '/'));

    const [jy, jm, jd] = crmGregorianToJalali(gy, gm, gd);
    const date = `${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`;
    if (match[4] != null && match[5] != null) {
        return crmToPersianDigits(`${date} ${String(match[4]).padStart(2, '0')}:${match[5]}`);
    }
    return crmToPersianDigits(date);
}

function initCRMJalaliPickers(root) {
    if (typeof jalaliDatepicker === 'undefined') return;
    jalaliDatepicker.startWatch({
        minDate: 'attr',
        maxDate: 'attr',
        zIndex: 20050,
        separatorChars: { date: '/', between: ' ', time: ':' },
        persianDigits: true,
        autoHide: true,
        hideAfterChange: true,
    });
}

const CRMDrawer = {
    active: null,
    open(id) {
        const drawer = document.getElementById(id);
        if (!drawer) return;
        if (this.active) this.close(this.active);
        drawer.hidden = false;
        drawer.removeAttribute('hidden');
        drawer.classList.add('is-open');
        document.body.classList.add('crm-drawer-open');
        this.active = drawer;
        initCRMJalaliPickers(drawer);
        initCRMMoneyInputs(drawer);
        initPropertyDealMode(drawer);
        initCRMFormErrors();
        if (id === 'drawer-import') initCRMImportDrawer(drawer);
        else initCRMVisitOutcome(drawer);
        initCRMPropertyImages(drawer);
    },
    close(drawer) {
        const el = typeof drawer === 'string' ? document.getElementById(drawer) : drawer;
        if (!el) return;
        el.classList.remove('is-open');
        document.body.classList.remove('crm-drawer-open');
        if (this.active === el) this.active = null;
    },
    closeAll() {
        document.querySelectorAll('.crm-drawer.is-open').forEach(d => this.close(d));
    },
};

function initCRMTypeProfiles() {
    const profiles = window.crmTypeProfiles || {};
    const typeSelect = document.querySelector('[data-crm-type]') || document.querySelector('[name="customer_type"]');
    if (!typeSelect) return;

    const hint = document.getElementById('crmMoneyHint');
    const budgetFields = document.querySelectorAll('.crm-money-budget');
    const depositFields = document.querySelectorAll('.crm-money-deposit');
    const rentFields = document.querySelectorAll('.crm-money-rent');

    function applyProfile(type) {
        const p = profiles[type] || profiles['سرنخ'] || {};
        const mode = p.money_mode || 'flexible';
        if (hint && p.section_hint) hint.textContent = p.section_hint;

        const show = (els, on) => els.forEach(el => el.classList.toggle('hidden', !on));

        show(budgetFields, mode === 'budget' || mode === 'both' || mode === 'flexible');
        show(depositFields, mode === 'rent' || mode === 'both' || mode === 'flexible');
        show(rentFields, mode === 'rent' || mode === 'both' || mode === 'flexible');

        const bl = p.budget_labels || ['بودجه از', 'بودجه تا'];
        const dl = p.deposit_labels || ['ودیعه از', 'ودیعه تا'];
        const rl = p.rent_labels || ['اجاره از', 'اجاره تا'];
        document.querySelectorAll('[data-label-budget-min]').forEach(el => { el.textContent = bl[0]; });
        document.querySelectorAll('[data-label-budget-max]').forEach(el => { el.textContent = bl[1]; });
        document.querySelectorAll('[data-label-deposit-min]').forEach(el => { el.textContent = dl[0]; });
        document.querySelectorAll('[data-label-deposit-max]').forEach(el => { el.textContent = dl[1]; });
        document.querySelectorAll('[data-label-rent-min]').forEach(el => { el.textContent = rl[0]; });
        document.querySelectorAll('[data-label-rent-max]').forEach(el => { el.textContent = rl[1]; });
    }

    applyProfile(typeSelect.value);
    typeSelect.addEventListener('change', () => applyProfile(typeSelect.value));
}

function initPropertyDealMode(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-deal-mode]').forEach(dealSelect => {
        if (dealSelect.dataset.dealModeBound === '1') return;
        dealSelect.dataset.dealModeBound = '1';
        const form = dealSelect.closest('form') || scope;
        const sale = form.querySelectorAll('.crm-price-sale');
        const deposit = form.querySelectorAll('.crm-price-deposit');
        const rent = form.querySelectorAll('.crm-price-rent');

        function apply(mode) {
            const show = (els, on) => els.forEach(el => el.classList.toggle('hidden', !on));
            show(sale, mode === 'فروش' || mode === 'پیش‌فروش');
            show(deposit, mode === 'رهن و اجاره' || mode === 'اجاره');
            show(rent, mode === 'رهن و اجاره' || mode === 'اجاره');
        }
        apply(dealSelect.value);
        dealSelect.addEventListener('change', () => apply(dealSelect.value));
    });
}

function initCRMGlobalSearch() {
    const input = document.getElementById('crmSearchInput');
    const results = document.getElementById('crmSearchResults');
    if (!input || !results) return;

    let timer = null;
    const searchUrl = input.dataset.url || '/workspace/crm/search/';

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (q.length < 2) { results.hidden = true; return; }
        timer = setTimeout(async () => {
            try {
                const res = await fetch(`${searchUrl}?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                renderResults(data);
            } catch (e) { /* ignore */ }
        }, 250);
    });

    function renderResults(data) {
        const parts = [];
        if (data.contacts?.length) {
            parts.push('<div class="crm-search-group"><div class="crm-search-group-title">مخاطبین</div>');
            data.contacts.forEach(c => {
                parts.push(`<a href="${c.url}" class="crm-search-item"><span>${c.name}</span><span class="crm-search-item-meta">${c.type} · ${c.phone || ''}</span></a>`);
            });
            parts.push('</div>');
        }
        if (data.properties?.length) {
            parts.push('<div class="crm-search-group"><div class="crm-search-group-title">املاک</div>');
            data.properties.forEach(p => {
                parts.push(`<a href="${p.url}" class="crm-search-item"><span>${p.title}</span><span class="crm-search-item-meta">${p.deal_mode} · ${p.city || ''}</span></a>`);
            });
            parts.push('</div>');
        }
        if (!parts.length) {
            results.innerHTML = '<div class="crm-empty-text" style="padding:1rem">نتیجه‌ای یافت نشد</div>';
        } else {
            results.innerHTML = parts.join('');
        }
        results.hidden = false;
    }

    document.addEventListener('click', e => {
        if (!e.target.closest('#crmGlobalSearch')) results.hidden = true;
    });
}

function initCRMMultiSelect() {
    const selectAll = document.getElementById('crmSelectAll');
    const checks = document.querySelectorAll('.crm-row-check');
    const bulkBar = document.getElementById('crmBulkBar');
    const bulkCount = document.getElementById('crmBulkCount');
    const bulkForm = document.getElementById('crmBulkForm');
    const bulkIds = document.getElementById('crmBulkIds');
    if (!checks.length) return;

    function selectedIds() {
        return [...checks].filter(c => c.checked).map(c => c.value);
    }

    function updateBulk() {
        const n = selectedIds().length;
        if (bulkBar) {
            bulkBar.hidden = n === 0;
            bulkBar.classList.toggle('is-visible', n > 0);
        }
        if (bulkCount) bulkCount.textContent = n;
        if (bulkIds) bulkIds.value = selectedIds().join(',');
        if (n === 0 && bulkForm) {
            bulkForm.reset();
            bulkForm.classList.remove('is-delete');
            bulkForm.querySelectorAll('.crm-bulk-extra').forEach(el => {
                el.hidden = true;
                el.disabled = true;
            });
        }
    }

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checks.forEach(c => { c.checked = selectAll.checked; });
            updateBulk();
        });
    }
    checks.forEach(c => c.addEventListener('change', updateBulk));

    const bulkClear = document.getElementById('crmBulkClear');
    if (bulkClear) {
        bulkClear.addEventListener('click', () => {
            checks.forEach(c => { c.checked = false; });
            if (selectAll) selectAll.checked = false;
            updateBulk();
        });
    }

    if (bulkForm) {
        const actionSel = bulkForm.querySelector('[name="bulk_action"]');
        const extras = bulkForm.querySelectorAll('.crm-bulk-extra');
        function syncExtras() {
            const action = actionSel?.value || '';
            extras.forEach(el => {
                const show = el.dataset.for === action;
                el.hidden = !show;
                el.disabled = !show;
            });
        }
        actionSel?.addEventListener('change', () => {
            syncExtras();
            bulkForm.classList.toggle('is-delete', actionSel.value === 'delete');
        });
        syncExtras();
        if (actionSel) bulkForm.classList.toggle('is-delete', actionSel.value === 'delete');

        bulkForm.addEventListener('submit', e => {
            updateBulk();
            const action = actionSel?.value;
            if (!selectedIds().length) {
                e.preventDefault();
                return;
            }
            if (action === 'delete' && !window.confirm('مخاطبین انتخاب‌شده حذف شوند؟')) {
                e.preventDefault();
            }
        });
    }
}

function getCsrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
}

const CRM_PIPELINE_GRIP_SELECTOR = '.crm-kanban-grip, .crm-pipe-grip, .crm-prop-pipeline-grip, .crm-deal-pipeline-grip';

function enableCRMPipelineTouchDrag(board, {
    cardSelector = '.crm-pipe-card--draggable',
    gripSelector = CRM_PIPELINE_GRIP_SELECTOR,
    dragThreshold = 8,
    onDrop,
    onDragOver,
} = {}) {
    if (!board || !window.matchMedia('(hover: none), (pointer: coarse)').matches) return;

    let touchState = null;

    function clearDragOver() {
        board.querySelectorAll('[data-drop-zone]').forEach(zone => zone.classList.remove('is-drag-over'));
    }

    function resetTouchDrag() {
        if (!touchState) return;
        touchState.card.classList.remove('is-dragging');
        touchState.card.style.pointerEvents = '';
        clearDragOver();
        touchState = null;
    }

    function findDropZone(x, y) {
        const hit = document.elementFromPoint(x, y);
        const zone = hit?.closest('[data-drop-zone]');
        return zone && board.contains(zone) ? zone : null;
    }

    board.querySelectorAll(cardSelector).forEach(card => {
        const grip = card.querySelector(gripSelector);
        if (!grip) return;

        grip.addEventListener('touchstart', e => {
            if (e.touches.length !== 1) return;
            const touch = e.touches[0];
            touchState = {
                card,
                startX: touch.clientX,
                startY: touch.clientY,
                active: false,
                zone: null,
            };
        }, { passive: true });

        grip.addEventListener('touchmove', e => {
            if (!touchState || touchState.card !== card) return;
            const touch = e.touches[0];
            touchState.lastY = touch.clientY;
            const dx = touch.clientX - touchState.startX;
            const dy = touch.clientY - touchState.startY;

            if (!touchState.active) {
                if (Math.hypot(dx, dy) < dragThreshold) return;
                touchState.active = true;
                card.classList.add('is-dragging');
                card.style.pointerEvents = 'none';
            }

            e.preventDefault();
            clearDragOver();
            const zone = findDropZone(touch.clientX, touch.clientY);
            if (zone) {
                zone.classList.add('is-drag-over');
                touchState.zone = zone;
                if (onDragOver) onDragOver(card, zone, touch.clientY);
            } else {
                touchState.zone = null;
            }
        }, { passive: false });

        grip.addEventListener('touchend', async () => {
            if (!touchState || touchState.card !== card) return;
            const { active, zone, lastY } = touchState;
            resetTouchDrag();
            if (active && zone && onDrop) {
                await onDrop(card, zone, lastY);
            }
        }, { passive: true });

        grip.addEventListener('touchcancel', resetTouchDrag, { passive: true });
    });
}

function initCRMPipeline() {
    const board = document.querySelector('.crm-pipeline--contacts.crm-pipeline--interactive');
    if (!board) return;

    const urlTemplate = board.dataset.statusUrl || window.crmStatusUrlTemplate || '';
    let dragged = null;

    function adjustPipelineCount(column, delta) {
        const countEl = column?.querySelector('[data-count]');
        if (!countEl) return;
        countEl.textContent = Math.max(0, parseInt(countEl.textContent, 10) + delta);
    }

    async function moveContactCard(card, zone) {
        const col = zone.closest('[data-status]');
        const newStatus = col?.dataset.status;
        const oldStatus = card.dataset.status;
        const customerId = card.dataset.customerId;
        if (!newStatus || newStatus === oldStatus) return;

        const url = urlTemplate.replace('{id}', customerId);
        const oldCol = card.closest('[data-status]');
        const newCol = col;

        zone.appendChild(card);
        card.dataset.status = newStatus;
        if (oldCol && oldCol !== newCol) {
            adjustPipelineCount(oldCol, -1);
            adjustPipelineCount(newCol, 1);
        }
        zone.querySelector('[data-empty]')?.remove();

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ status: newStatus }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
        } catch (err) {
            const oldZone = oldCol?.querySelector('[data-drop-zone]');
            if (oldZone) oldZone.appendChild(card);
            card.dataset.status = oldStatus;
            if (oldCol && oldCol !== newCol) {
                adjustPipelineCount(oldCol, 1);
                adjustPipelineCount(newCol, -1);
            }
            window.alert(err.message || 'تغییر وضعیت انجام نشد.');
        }
    }

    board.querySelectorAll('.crm-pipe-card--draggable').forEach(card => {
        card.addEventListener('dragstart', e => {
            dragged = card;
            card.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.customerId);
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('is-dragging');
            dragged = null;
            board.querySelectorAll('[data-drop-zone]').forEach(z => z.classList.remove('is-drag-over'));
        });
        const open = card.querySelector('.crm-pipe-open');
        if (open) {
            open.addEventListener('click', e => e.stopPropagation());
        }
    });

    board.querySelectorAll('[data-drop-zone]').forEach(zone => {
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            zone.classList.add('is-drag-over');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('is-drag-over'));
        zone.addEventListener('drop', async e => {
            e.preventDefault();
            zone.classList.remove('is-drag-over');
            if (!dragged) return;
            await moveContactCard(dragged, zone);
            dragged = null;
        });
    });

    enableCRMPipelineTouchDrag(board, {
        gripSelector: '.crm-kanban-grip',
        onDrop: moveContactCard,
    });
}

function initCRMDealPipeline() {
    const board = document.querySelector('.crm-pipeline--deals.crm-pipeline--interactive');
    if (!board) return;

    const urlTemplate = board.dataset.stageUrl || '';
    let dragged = null;

    function adjustPipelineCount(column, delta) {
        const countEl = column?.querySelector('[data-count]');
        if (!countEl) return;
        countEl.textContent = Math.max(0, parseInt(countEl.textContent, 10) + delta);
    }

    async function moveDealCard(card, zone) {
        const col = zone.closest('[data-stage]');
        const newStage = col?.dataset.stage;
        const oldStage = card.dataset.stage;
        const dealId = card.dataset.dealId;
        if (!newStage || newStage === oldStage) return;

        const url = urlTemplate.replace('{id}', dealId);
        const oldCol = card.closest('[data-stage]');
        const newCol = col;

        zone.appendChild(card);
        card.dataset.stage = newStage;
        if (oldCol && oldCol !== newCol) {
            adjustPipelineCount(oldCol, -1);
            adjustPipelineCount(newCol, 1);
        }
        zone.querySelector('[data-empty]')?.remove();
        syncDealPipelineZone(zone);
        if (oldCol && oldCol !== newCol) {
            syncDealPipelineZone(oldCol.querySelector('[data-drop-zone]'));
        }

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ stage: newStage }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
        } catch (err) {
            const oldZone = oldCol?.querySelector('[data-drop-zone]');
            if (oldZone) oldZone.appendChild(card);
            card.dataset.stage = oldStage;
            if (oldCol && oldCol !== newCol) {
                adjustPipelineCount(oldCol, 1);
                adjustPipelineCount(newCol, -1);
            }
            syncDealPipelineZone(zone);
            syncDealPipelineZone(oldCol?.querySelector('[data-drop-zone]'));
            window.alert(err.message || 'تغییر مرحله انجام نشد.');
        }
    }

    board.querySelectorAll('.crm-pipe-card--draggable').forEach(card => {
        card.addEventListener('dragstart', e => {
            dragged = card;
            card.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.dealId);
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('is-dragging');
            dragged = null;
            board.querySelectorAll('[data-drop-zone]').forEach(z => z.classList.remove('is-drag-over'));
        });
        const open = card.querySelector('.crm-deal-pipeline-open, .crm-deal-kanban-open, .crm-pipe-open');
        if (open) open.addEventListener('click', e => e.stopPropagation());
    });

    board.querySelectorAll('[data-drop-zone]').forEach(zone => {
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            zone.classList.add('is-drag-over');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('is-drag-over'));
        zone.addEventListener('drop', async e => {
            e.preventDefault();
            zone.classList.remove('is-drag-over');
            if (!dragged) return;
            await moveDealCard(dragged, zone);
            dragged = null;
        });
    });

    enableCRMPipelineTouchDrag(board, {
        gripSelector: '.crm-deal-pipeline-grip',
        onDrop: moveDealCard,
    });
}

function crmPipelineCardSelector() {
    return '.crm-pipe-card--draggable, .crm-files-kanban-card--link, .crm-prop-pipeline-card, .crm-deal-pipeline-card';
}

const CRM_PROP_PIPELINE_EMPTY_HTML = '<div class="crm-prop-pipeline-empty" data-empty><i class="fas fa-layer-group" aria-hidden="true"></i><span>بدون فایل</span><small>فایل را اینجا رها کنید</small></div>';
const CRM_DEAL_PIPELINE_EMPTY_HTML = '<div class="crm-deal-pipeline-empty" data-empty><i class="fas fa-handshake" aria-hidden="true"></i><span>بدون معامله</span><small>کارت را اینجا رها کنید</small></div>';

function syncDealPipelineZone(zone) {
    if (!zone) return;
    const col = zone.closest('.crm-deal-pipeline-col');
    const hasCards = zone.querySelector('.crm-deal-pipeline-card, .crm-pipe-card--draggable');
    const empty = zone.querySelector('[data-empty]');
    if (hasCards) {
        empty?.remove();
        col?.classList.remove('crm-deal-pipeline-col--empty');
    } else if (!empty) {
        zone.insertAdjacentHTML('beforeend', CRM_DEAL_PIPELINE_EMPTY_HTML);
        col?.classList.add('crm-deal-pipeline-col--empty');
    } else {
        col?.classList.add('crm-deal-pipeline-col--empty');
    }
}

function syncPropertyPipelineZone(zone) {
    if (!zone) return;
    const col = zone.closest('.crm-prop-pipeline-col');
    const hasCards = zone.querySelector(crmPipelineCardSelector());
    const empty = zone.querySelector('[data-empty]');
    if (hasCards) {
        empty?.remove();
        col?.classList.remove('crm-prop-pipeline-col--empty');
    } else if (!empty) {
        zone.insertAdjacentHTML('beforeend', CRM_PROP_PIPELINE_EMPTY_HTML);
        col?.classList.add('crm-prop-pipeline-col--empty');
    } else {
        col?.classList.add('crm-prop-pipeline-col--empty');
    }
}

function crmShareRevokeUrl(shareId) {
    const tpl = window.crmShareRevokeUrlTemplate || window.crmShareRevokeUrlBase || '';
    if (!tpl) return '';
    if (tpl.includes('{id}')) return tpl.replace('{id}', shareId);
    return tpl + shareId + '/';
}

function crmPipelineDragAfterElement(zone, y) {
    const cards = [...zone.querySelectorAll('.crm-pipe-card--draggable:not(.is-dragging)')];
    return cards.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        }
        return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function crmPipelineColumnOrder(zone) {
    return [...zone.querySelectorAll('.crm-pipe-card--draggable')].map(
        card => parseInt(card.dataset.propertyId, 10),
    ).filter(Boolean);
}

async function crmSavePipelineColumnOrder(reorderUrl, status, zone) {
    if (!reorderUrl || !status || !zone) return;
    const orderedIds = crmPipelineColumnOrder(zone);
    if (!orderedIds.length) return;
    const res = await fetch(reorderUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ transaction_status: status, ordered_ids: orderedIds }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'خطا');
}

function initCRMPropertyPipeline() {
    const board = document.querySelector('.crm-pipeline--properties.crm-pipeline--interactive');
    if (!board) return;

    const urlTemplate = board.dataset.txUrl || '';
    const reorderUrl = board.dataset.reorderUrl || '';
    let dragged = null;

    function adjustPipelineCount(column, delta) {
        const countEl = column?.querySelector('[data-count]');
        if (!countEl) return;
        countEl.textContent = Math.max(0, parseInt(countEl.textContent, 10) + delta);
    }

    function placeCardInZone(card, zone, clientY) {
        zone.querySelector('[data-empty]')?.remove();
        const after = clientY != null ? crmPipelineDragAfterElement(zone, clientY) : null;
        if (after == null) zone.appendChild(card);
        else zone.insertBefore(card, after);
    }

    async function movePropertyCard(card, zone, clientY) {
        const col = zone.closest('[data-tx-status]');
        const newStatus = col?.dataset.txStatus;
        const oldStatus = card.dataset.txStatus;
        const propertyId = card.dataset.propertyId;
        if (!newStatus) return;

        const oldCol = card.closest('[data-tx-status]');
        const oldZone = card.closest('[data-drop-zone]');
        const newCol = col;
        const sameColumn = newStatus === oldStatus;

        placeCardInZone(card, zone, clientY);

        if (sameColumn) {
            syncPropertyPipelineZone(zone);
            try {
                await crmSavePipelineColumnOrder(reorderUrl, newStatus, zone);
            } catch (err) {
                window.alert(err.message || 'تغییر ترتیب انجام نشد.');
                window.location.reload();
            }
            return;
        }

        card.dataset.txStatus = newStatus;
        if (oldCol && oldCol !== newCol) {
            adjustPipelineCount(oldCol, -1);
            adjustPipelineCount(newCol, 1);
        }
        syncPropertyPipelineZone(zone);
        if (oldZone && oldZone !== zone) syncPropertyPipelineZone(oldZone);

        const url = urlTemplate.replace('{id}', propertyId);
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ transaction_status: newStatus }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            await crmSavePipelineColumnOrder(reorderUrl, newStatus, zone);
            if (oldZone && oldZone !== zone) {
                await crmSavePipelineColumnOrder(reorderUrl, oldStatus, oldZone);
            }
        } catch (err) {
            if (oldZone) {
                zone.querySelector('[data-empty]')?.remove();
                oldZone.appendChild(card);
                card.dataset.txStatus = oldStatus;
                syncPropertyPipelineZone(zone);
                syncPropertyPipelineZone(oldZone);
            }
            if (oldCol && oldCol !== newCol) {
                adjustPipelineCount(oldCol, 1);
                adjustPipelineCount(newCol, -1);
            }
            window.alert(err.message || 'تغییر وضعیت انجام نشد.');
        }
    }

    board.querySelectorAll('.crm-pipe-card--draggable').forEach(card => {
        card.addEventListener('dragstart', e => {
            dragged = card;
            card.classList.add('is-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.propertyId);
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('is-dragging');
            dragged = null;
            board.querySelectorAll('[data-drop-zone]').forEach(z => z.classList.remove('is-drag-over'));
        });
        const open = card.querySelector('.crm-prop-pipeline-open, .crm-files-kanban-open');
        if (open) open.addEventListener('click', e => e.stopPropagation());
    });

    board.querySelectorAll('[data-drop-zone]').forEach(zone => {
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            if (!dragged) return;
            zone.classList.add('is-drag-over');
            placeCardInZone(dragged, zone, e.clientY);
        });
        zone.addEventListener('dragleave', e => {
            if (!zone.contains(e.relatedTarget)) zone.classList.remove('is-drag-over');
        });
        zone.addEventListener('drop', async e => {
            e.preventDefault();
            zone.classList.remove('is-drag-over');
            if (!dragged) return;
            await movePropertyCard(dragged, zone, e.clientY);
            dragged = null;
        });
    });

    enableCRMPipelineTouchDrag(board, {
        gripSelector: '.crm-prop-pipeline-grip',
        onDrop: movePropertyCard,
        onDragOver: (card, zone, clientY) => placeCardInZone(card, zone, clientY),
    });
}

function initCRMSavedFilters() {
    const saveUrl = window.crmFilterSaveUrl || '/workspace/crm/filters/save/';
    const deleteUrlBase = window.crmFilterDeleteUrlBase || '/workspace/crm/filters/';
    const pinUrlBase = window.crmFilterPinUrlBase || '/workspace/crm/filters/';

    document.querySelectorAll('.crm-saved-filters').forEach(root => {
        const form = root.closest('form');
        if (!form) return;

        function collectParams() {
            const params = {};
            new FormData(form).forEach((value, key) => {
                if (key === 'view' || key === 'page' || key === 'drawer') return;
                const v = String(value || '').trim();
                if (v) params[key] = v;
            });
            return params;
        }

        function renderItem(f) {
            const base = root.dataset.base || '';
            const view = root.dataset.view || 'table';
            const qs = Object.entries(f.params || {})
                .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
                .join('&');
            const href = qs ? `${base}?view=${encodeURIComponent(view)}&${qs}` : `${base}?view=${encodeURIComponent(view)}`;
            const pinned = f.is_pinned ? ' is-pinned' : '';
            const count = Object.keys(f.params || {}).length;
            return `<div class="crm-saved-filters-item${pinned}" data-filter-id="${f.id}">
                <a href="${href}" class="crm-saved-filters-link" role="menuitem">
                    <span class="crm-saved-filters-name">${f.name}</span>
                    <span class="crm-saved-filters-meta">${count} معیار</span>
                </a>
                <div class="crm-saved-filters-actions">
                    <button type="button" class="crm-saved-filters-pin" data-saved-filter-pin title="سنجاق">
                        <i class="fas fa-thumbtack" aria-hidden="true"></i>
                    </button>
                    <button type="button" class="crm-saved-filters-del" data-saved-filter-delete title="حذف">
                        <i class="fas fa-trash-can" aria-hidden="true"></i>
                    </button>
                </div>
            </div>`;
        }

        root.querySelector('[data-saved-filter-save]')?.addEventListener('click', async () => {
            const params = collectParams();
            if (!Object.keys(params).length) {
                window.alert('ابتدا حداقل یک فیلتر اعمال کنید.');
                return;
            }
            const name = window.prompt('نام فیلتر ذخیره‌شده:');
            if (!name || !name.trim()) return;
            try {
                const res = await fetch(saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({
                        name: name.trim(),
                        scope: root.dataset.scope,
                        params,
                    }),
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error || 'خطا');
                const list = root.querySelector('[data-saved-filter-list]');
                list?.querySelector('[data-saved-filter-empty]')?.remove();
                list?.insertAdjacentHTML('afterbegin', renderItem(data.filter));
                const badge = root.querySelector('.crm-saved-filters-badge');
                if (badge) {
                    badge.textContent = String(parseInt(badge.textContent || '0', 10) + 1);
                } else {
                    root.querySelector('.crm-saved-filters-btn')?.insertAdjacentHTML(
                        'beforeend',
                        `<em class="crm-saved-filters-badge">1</em>`,
                    );
                }
            } catch (err) {
                window.alert(err.message || 'ذخیره فیلتر انجام نشد.');
            }
        });

        root.addEventListener('click', async e => {
            const delBtn = e.target.closest('[data-saved-filter-delete]');
            const pinBtn = e.target.closest('[data-saved-filter-pin]');
            const item = e.target.closest('[data-filter-id]');
            if (!item) return;

            const filterId = item.dataset.filterId;
            if (delBtn) {
                e.preventDefault();
                if (!window.confirm('این فیلتر حذف شود؟')) return;
                try {
                    const res = await fetch(`${deleteUrlBase}${filterId}/delete/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const data = await res.json();
                    if (!data.ok) throw new Error(data.error || 'خطا');
                    item.remove();
                    const badge = root.querySelector('.crm-saved-filters-badge');
                    if (badge) {
                        const n = Math.max(0, parseInt(badge.textContent || '0', 10) - 1);
                        if (n) badge.textContent = String(n);
                        else badge.remove();
                    }
                    const list = root.querySelector('[data-saved-filter-list]');
                    if (list && !list.querySelector('[data-filter-id]')) {
                        list.innerHTML = '<p class="crm-saved-filters-empty" data-saved-filter-empty>هنوز فیلتری ذخیره نشده</p>';
                    }
                } catch (err) {
                    window.alert(err.message || 'حذف انجام نشد.');
                }
            }
            if (pinBtn) {
                e.preventDefault();
                try {
                    const res = await fetch(`${pinUrlBase}${filterId}/pin/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const data = await res.json();
                    if (!data.ok) throw new Error(data.error || 'خطا');
                    item.classList.toggle('is-pinned', data.filter.is_pinned);
                    const list = root.querySelector('[data-saved-filter-list]');
                    if (list && data.filter.is_pinned) {
                        list.prepend(item);
                    }
                } catch (err) {
                    window.alert(err.message || 'سنجاق انجام نشد.');
                }
            }
        });
    });
}

function initCRMVisitOutcome(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-visit-outcome]').forEach(sel => {
        const form = sel.closest('form');
        if (!form) return;
        const rejectField = form.querySelector('.crm-visit-reject-field');
        if (!rejectField) return;
        function sync() {
            const isReject = sel.value === 'رد';
            rejectField.hidden = !isReject;
            const input = rejectField.querySelector('select, input');
            if (input) input.required = isReject;
        }
        sel.addEventListener('change', sync);
        sync();
    });
}

function initCRMSidePanel() {
    const layout = document.getElementById('crmContactsLayout');
    const panel = document.getElementById('crmSidePanel');
    const content = document.getElementById('crmSideContent');
    const loading = document.getElementById('crmSideLoading');
    const closeBtn = document.getElementById('crmSideClose');
    if (!layout || !panel || !content) return;

    const baseUrl = window.crmPanelBase || '/workspace/crm/contacts/';
    let activeRow = null;

    function closePanel() {
        panel.hidden = true;
        layout.classList.remove('has-side-panel');
        if (activeRow) activeRow.classList.remove('is-panel-active');
        activeRow = null;
    }

    function renderPanel(data) {
        const acts = [];
        if (data.tel_url) acts.push(`<a href="${data.tel_url}" class="crm-preview-act" title="تماس"><i class="fas fa-phone"></i></a>`);
        if (data.whatsapp_url) acts.push(`<a href="${data.whatsapp_url}" target="_blank" class="crm-preview-act crm-preview-act--wa" title="واتساپ"><i class="fab fa-whatsapp"></i></a>`);

        const activities = (data.activities || []).map(a =>
            `<li class="crm-preview-timeline-item">
                <span class="crm-preview-timeline-dot"></span>
                <div class="crm-preview-timeline-body">
                    <div class="crm-preview-timeline-head">
                        <span class="crm-preview-timeline-type">${a.activity_type}</span>
                        <time>${crmFormatJalaliDatetime(a.created_at)}</time>
                    </div>
                    ${a.content || a.title ? `<p>${a.content || a.title}</p>` : ''}
                </div>
            </li>`
        ).join('');

        content.innerHTML = `
            <div class="crm-preview-hero">
                <div class="crm-preview-hero-text">
                    <h2>${data.name}</h2>
                    <p><span class="crm-preview-type">${data.customer_type}</span><span class="crm-preview-sep">·</span><span class="crm-preview-status">${data.status}</span></p>
                </div>
            </div>
            ${acts.length ? `<div class="crm-preview-quick">${acts.join('')}</div>` : ''}
            <dl class="crm-preview-meta">
                ${data.phone ? `<div><dt>تلفن</dt><dd dir="ltr">${data.phone}</dd></div>` : ''}
                ${data.budget_label ? `<div><dt>بودجه</dt><dd>${data.budget_label}</dd></div>` : ''}
                ${data.areas ? `<div><dt>محله</dt><dd>${data.areas}</dd></div>` : ''}
                ${data.source ? `<div><dt>منبع</dt><dd>${data.source}</dd></div>` : ''}
                ${data.match_count ? `<div><dt>تطبیق</dt><dd>${data.match_count} ملک</dd></div>` : ''}
            </dl>
            ${data.notes ? `<div class="crm-preview-notes"><p>${data.notes}</p></div>` : ''}
            ${activities ? `<div class="crm-preview-timeline"><h3>فعالیت اخیر</h3><ul>${activities}</ul></div>` : ''}
            <div class="crm-preview-foot">
                ${data.match_eligible ? `<a href="${data.matches_url || data.detail_url + '?tab=matches'}" class="crm-preview-btn crm-preview-btn--accent"><i class="fas fa-wand-magic-sparkles"></i> پیشنهاد ملک${data.match_count ? ` (${data.match_count})` : ''}</a>` : ''}
                <a href="${data.detail_url}" class="crm-preview-btn crm-preview-btn--primary">پروفایل کامل</a>
                <a href="${data.edit_url}" class="crm-preview-btn crm-preview-btn--secondary">ویرایش</a>
            </div>`;
        loading.hidden = true;
        panel.removeAttribute('aria-busy');
    }

    async function openPanel(row) {
        const url = row.dataset.panelUrl;
        if (!url) return;
        if (activeRow) activeRow.classList.remove('is-panel-active');
        activeRow = row;
        row.classList.add('is-panel-active');
        layout.classList.add('has-side-panel');
        panel.hidden = false;
        content.innerHTML = '';
        loading.hidden = false;
        panel.setAttribute('aria-busy', 'true');

        try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            renderPanel(data);
        } catch (e) {
            content.innerHTML = '<p class="crm-empty-text">خطا در بارگذاری</p>';
            loading.hidden = true;
            panel.removeAttribute('aria-busy');
        }
    }

    layout.querySelectorAll('.crm-row-selectable').forEach(row => {
        row.addEventListener('click', e => {
            if (e.target.closest('a, button, input, .crm-col-check')) return;
            openPanel(row);
        });
    });

    const firstRow = layout.querySelector('tbody .crm-row-selectable[data-panel-url]');
    const sidePanelDocked = window.matchMedia('(min-width: 901px)').matches;
    if (firstRow && sidePanelDocked) openPanel(firstRow);

    if (closeBtn) closeBtn.addEventListener('click', closePanel);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !panel.hidden) closePanel();
    });
}

function initCRMQuickLead() {
    const form = document.getElementById('crmQuickLeadForm');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';

    form.addEventListener('submit', async e => {
        if (form.dataset.ajax !== '1') return;
        e.preventDefault();
        const btn = form.querySelector('[type=submit]');
        if (btn) btn.disabled = true;

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await res.json();
            if (data.ok) {
                CRMDrawer.close('drawer-quick-lead');
                form.reset();
                if (data.url) window.location.href = data.url;
                else window.location.reload();
            } else {
                window.alert('ثبت سرنخ انجام نشد.');
            }
        } catch (err) {
            window.alert('خطای شبکه');
        } finally {
            if (btn) btn.disabled = false;
        }
    });
}

function initCRMMatches() {
    const form = document.getElementById('crmSuggestForm');
    if (!form) return;

    const jsonInput = document.getElementById('crmMatchesJson');
    const countEl = document.getElementById('crmSuggestCount');
    const submitBtn = document.getElementById('crmSuggestSubmit');
    const selects = () => [...document.querySelectorAll('.crm-match-select:checked')];

    function payloadFromCheckbox(cb) {
        const d = cb.dataset;
        const item = {
            source: d.source,
            title: d.title || '',
            price_label: d.priceLabel || '',
            neighborhood: d.neighborhood || '',
            link: d.link || '',
        };
        if (d.area) {
            const n = parseFloat(d.area);
            item.area = Number.isNaN(n) ? d.area : n;
        }
        if (d.source === 'crm' && d.propertyId) item.property_id = parseInt(d.propertyId, 10);
        if (d.source === 'divar' && d.token) item.token = d.token;
        return item;
    }

    function updateSelection() {
        const items = selects().map(payloadFromCheckbox);
        if (jsonInput) jsonInput.value = JSON.stringify(items);
        if (countEl) countEl.textContent = items.length;
        if (submitBtn) submitBtn.disabled = items.length === 0;
    }

    document.querySelectorAll('.crm-match-select').forEach(cb => {
        cb.addEventListener('change', updateSelection);
    });

    const selectAll = document.getElementById('crmSelectAllMatches');
    if (selectAll) {
        selectAll.addEventListener('click', () => {
            const boxes = document.querySelectorAll('.crm-match-select:not(:disabled)');
            const allChecked = [...boxes].every(b => b.checked);
            boxes.forEach(b => { b.checked = !allChecked; });
            updateSelection();
        });
    }

    updateSelection();
}

function initCRMTabs() {
    document.querySelectorAll('.crm-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            const shell = btn.closest('.crm-detail-main') || btn.closest('.crm-prop-main') || btn.closest('.crm-prop-detail-v2') || btn.closest('.crm-shell-page') || btn.closest('.crm-shell');
            if (!shell) return;
            shell.querySelectorAll('.crm-tab').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            shell.querySelectorAll('[data-panel]').forEach(p => p.hidden = true);
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            const panel = shell.querySelector(`[data-panel="${tab}"]`);
            if (panel) panel.hidden = false;
        });
    });

    document.querySelectorAll('.crm-form-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            const parent = btn.closest('.crm-form-sections');
            if (!parent) return;
            parent.querySelectorAll('.crm-form-tab').forEach(b => b.classList.remove('active'));
            parent.querySelectorAll('[data-panel]').forEach(p => p.hidden = true);
            btn.classList.add('active');
            const panel = parent.querySelector(`[data-panel="${tab}"]`);
            if (panel) panel.hidden = false;
        });
    });
}

function crmActivateFormTab(section, tabName) {
    section.querySelectorAll('.crm-form-tab').forEach(b => b.classList.remove('active'));
    section.querySelectorAll('[data-panel]').forEach(p => { p.hidden = true; });
    const tabBtn = section.querySelector(`.crm-form-tab[data-tab="${tabName}"]`);
    const panel = section.querySelector(`[data-panel="${tabName}"]`);
    if (tabBtn) tabBtn.classList.add('active');
    if (panel) panel.hidden = false;
}

function initCRMContactFormGuard() {
    document.querySelectorAll('#drawer-contact form').forEach(form => {
        if (form.dataset.contactGuard === '1') return;
        form.dataset.contactGuard = '1';
        form.addEventListener('submit', e => {
            const section = form.querySelector('.crm-form-sections');
            const nameInput = form.querySelector('[name="name"]');
            if (!section || !nameInput || nameInput.value.trim()) return;
            e.preventDefault();
            const field = section.querySelector('[data-field="name"]');
            if (field) {
                field.classList.add('crm-field-has-error');
                if (!field.querySelector('.crm-field-error')) {
                    const err = document.createElement('p');
                    err.className = 'crm-field-error';
                    err.setAttribute('role', 'alert');
                    err.textContent = 'نام و نام خانوادگی الزامی است.';
                    field.appendChild(err);
                }
            }
            crmActivateFormTab(section, 'basic');
            section.querySelector('.crm-form-tab[data-tab="basic"]')?.classList.add('has-error');
            window.setTimeout(() => nameInput.focus({ preventScroll: true }), 80);
        });
    });
}

function initCRMFormErrors() {
    document.querySelectorAll('.crm-form-sections').forEach(section => {
        const tabsWithErrors = new Set();
        section.querySelectorAll('.crm-field-has-error').forEach(field => {
            const panel = field.closest('[data-panel]');
            if (panel?.dataset.panel) tabsWithErrors.add(panel.dataset.panel);
        });
        section.querySelectorAll('.crm-form-tab').forEach(tab => {
            tab.classList.toggle('has-error', tabsWithErrors.has(tab.dataset.tab));
        });

        const firstError = section.querySelector('.crm-field-has-error');
        if (!firstError) return;

        const panel = firstError.closest('[data-panel]');
        if (panel?.dataset.panel) {
            crmActivateFormTab(section, panel.dataset.panel);
        }

        const block = firstError.closest('[data-form-section]');
        if (block) {
            block.classList.add('has-error');
            block.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        const fieldInput = firstError.querySelector('input, select, textarea');
        if (fieldInput) {
            window.setTimeout(() => fieldInput.focus({ preventScroll: true }), 120);
        }
    });
}

const CRM_NOTIFIED_KEY = 'crmNotifiedIds';

function initCRMNotifications() {
    if (!document.querySelector('.crm-app')) return;
    if (!('Notification' in window)) return;

    async function poll() {
        try {
            const res = await fetch('/workspace/crm/notifications/due/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await res.json();
            if (!data.ok || !data.items?.length) return;

            let seen = [];
            try { seen = JSON.parse(localStorage.getItem(CRM_NOTIFIED_KEY) || '[]'); } catch (e) { seen = []; }

            for (const item of data.items) {
                const key = `${item.kind}:${item.id}`;
                if (seen.includes(key)) continue;
                if (Notification.permission === 'granted') {
                    const n = new Notification(item.title, { body: item.body, tag: key });
                    n.onclick = () => { window.location.href = item.url; };
                    seen.push(key);
                }
            }
            localStorage.setItem(CRM_NOTIFIED_KEY, JSON.stringify(seen.slice(-50)));
        } catch (e) { /* ignore */ }
    }

    if (Notification.permission === 'default') {
        Notification.requestPermission().then(() => poll());
    } else if (Notification.permission === 'granted') {
        poll();
    }
    window.setInterval(poll, 5 * 60 * 1000);
}

function formatFileSize(bytes) {
    if (!bytes && bytes !== 0) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function initCRMImportDrawer(root) {
    const scope = root || document.getElementById('drawer-import');
    if (!scope) return;

    const zone = scope.querySelector('[data-import-dropzone]');
    const input = scope.querySelector('[data-import-file]');
    const empty = scope.querySelector('[data-import-empty]');
    const preview = scope.querySelector('[data-import-preview]');
    const filenameEl = scope.querySelector('[data-import-filename]');
    const filesizeEl = scope.querySelector('[data-import-filesize]');
    const clearBtn = scope.querySelector('[data-import-clear]');
    const submitBtn = scope.querySelector('[data-import-submit]');
    const form = scope.querySelector('#crmImportForm');

    if (!zone || !input) return;

    function setFile(file) {
        if (!file) {
            input.value = '';
            zone.classList.remove('has-file');
            empty?.removeAttribute('hidden');
            preview?.setAttribute('hidden', '');
            if (submitBtn) submitBtn.disabled = true;
            return;
        }
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        zone.classList.add('has-file');
        empty?.setAttribute('hidden', '');
        preview?.removeAttribute('hidden');
        if (filenameEl) filenameEl.textContent = file.name;
        if (filesizeEl) filesizeEl.textContent = formatFileSize(file.size);
        if (submitBtn) submitBtn.disabled = false;
    }

    function pickFile() {
        if (zone.classList.contains('has-file')) return;
        input.click();
    }

    zone.addEventListener('click', (e) => {
        if (e.target.closest('[data-import-clear]')) return;
        pickFile();
    });

    zone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            pickFile();
        }
    });

    ['dragenter', 'dragover'].forEach((ev) => {
        zone.addEventListener(ev, (e) => {
            e.preventDefault();
            zone.classList.add('is-dragover');
        });
    });
    ['dragleave', 'drop'].forEach((ev) => {
        zone.addEventListener(ev, (e) => {
            e.preventDefault();
            zone.classList.remove('is-dragover');
        });
    });

    zone.addEventListener('drop', (e) => {
        const file = e.dataTransfer?.files?.[0];
        if (file) setFile(file);
    });

    input.addEventListener('change', () => {
        const file = input.files?.[0];
        if (file) setFile(file);
    });

    clearBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setFile(null);
    });

    form?.addEventListener('submit', () => {
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.add('is-loading');
        }
    });

    if (input.files?.[0]) setFile(input.files[0]);
    else setFile(null);
}

function initCRMDealStagesEditor() {
    const editor = document.getElementById('crmDealStagesEditor');
    const list = document.getElementById('crmStagesList');
    const saveBtn = document.getElementById('crmStagesSave');
    const addBtn = document.getElementById('crmStagesAdd');
    const dataEl = document.getElementById('crmDealStagesData');
    if (!editor || !list || !dataEl) return;

    const WON = 'بسته‌شده';
    const LOST = 'از دست رفته';
    const url = editor.dataset.stagesUrl || window.crmDealStagesUrl || '';
    let stages = [];
    try {
        stages = JSON.parse(dataEl.textContent || '[]');
    } catch (e) {
        stages = [];
    }

    function middleStages() {
        return stages.slice(0, -2);
    }

    function render() {
        list.innerHTML = '';
        middleStages().forEach((name, idx) => {
            const li = document.createElement('li');
            li.className = 'crm-stages-item';
            li.draggable = true;
            li.dataset.index = String(idx);
            li.innerHTML = `
                <span class="crm-stages-grip" aria-hidden="true"><i class="fas fa-grip-vertical"></i></span>
                <input type="text" class="crm-stages-input" value="${name.replace(/"/g, '&quot;')}" maxlength="60" aria-label="نام مرحله">
                <div class="crm-stages-item-actions">
                    <button type="button" class="crm-stages-up" title="بالا" ${idx === 0 ? 'disabled' : ''}><i class="fas fa-chevron-up"></i></button>
                    <button type="button" class="crm-stages-down" title="پایین" ${idx === middleStages().length - 1 ? 'disabled' : ''}><i class="fas fa-chevron-down"></i></button>
                    <button type="button" class="crm-stages-remove" title="حذف"><i class="fas fa-trash-can"></i></button>
                </div>`;
            list.appendChild(li);
        });
        const locked = document.createElement('li');
        locked.className = 'crm-stages-locked';
        locked.innerHTML = `<span><i class="fas fa-lock"></i> ${WON}</span><span><i class="fas fa-lock"></i> ${LOST}</span>`;
        list.appendChild(locked);
        bindListEvents();
    }

    function syncFromInputs() {
        const mids = [...list.querySelectorAll('.crm-stages-item .crm-stages-input')].map(i => i.value.trim());
        stages = [...mids, WON, LOST];
    }

    function bindListEvents() {
        list.querySelectorAll('.crm-stages-input').forEach(inp => {
            inp.addEventListener('input', syncFromInputs);
        });
        list.querySelectorAll('.crm-stages-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                syncFromInputs();
                const idx = Number(btn.closest('.crm-stages-item')?.dataset.index);
                const mids = middleStages();
                if (mids.length <= 1) return;
                mids.splice(idx, 1);
                stages = [...mids, WON, LOST];
                render();
            });
        });
        list.querySelectorAll('.crm-stages-up').forEach(btn => {
            btn.addEventListener('click', () => {
                syncFromInputs();
                const idx = Number(btn.closest('.crm-stages-item')?.dataset.index);
                if (idx <= 0) return;
                const mids = middleStages();
                [mids[idx - 1], mids[idx]] = [mids[idx], mids[idx - 1]];
                stages = [...mids, WON, LOST];
                render();
            });
        });
        list.querySelectorAll('.crm-stages-down').forEach(btn => {
            btn.addEventListener('click', () => {
                syncFromInputs();
                const idx = Number(btn.closest('.crm-stages-item')?.dataset.index);
                const mids = middleStages();
                if (idx >= mids.length - 1) return;
                [mids[idx], mids[idx + 1]] = [mids[idx + 1], mids[idx]];
                stages = [...mids, WON, LOST];
                render();
            });
        });

        let dragIdx = null;
        list.querySelectorAll('.crm-stages-item').forEach(item => {
            item.addEventListener('dragstart', () => { dragIdx = Number(item.dataset.index); item.classList.add('is-dragging'); });
            item.addEventListener('dragend', () => { dragIdx = null; item.classList.remove('is-dragging'); });
            item.addEventListener('dragover', e => e.preventDefault());
            item.addEventListener('drop', e => {
                e.preventDefault();
                const targetIdx = Number(item.dataset.index);
                if (dragIdx === null || dragIdx === targetIdx) return;
                syncFromInputs();
                const mids = middleStages();
                const [moved] = mids.splice(dragIdx, 1);
                mids.splice(targetIdx, 0, moved);
                stages = [...mids, WON, LOST];
                render();
            });
        });
    }

    addBtn?.addEventListener('click', () => {
        syncFromInputs();
        const mids = middleStages();
        mids.push(`مرحله ${mids.length + 1}`);
        stages = [...mids, WON, LOST];
        render();
    });

    saveBtn?.addEventListener('click', async () => {
        syncFromInputs();
        saveBtn.disabled = true;
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ stages }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            window.location.reload();
        } catch (err) {
            window.alert(err.message || 'ذخیره مراحل انجام نشد.');
        } finally {
            saveBtn.disabled = false;
        }
    });

    render();
}

function initCRMDealChecklist() {
    const root = document.getElementById('crmDealChecklist');
    if (!root) return;
    const url = root.dataset.checklistUrl || window.crmDealChecklistUrl || '';

    root.addEventListener('click', async e => {
        const btn = e.target.closest('.crm-deal-checklist-toggle');
        if (!btn) return;
        const item = btn.closest('[data-item-id]');
        const itemId = item?.dataset.itemId;
        if (!itemId) return;

        const nextDone = !item.classList.contains('is-done');
        btn.disabled = true;
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ item_id: itemId, done: nextDone }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            item.classList.toggle('is-done', nextDone);
            btn.setAttribute('aria-pressed', nextDone ? 'true' : 'false');
            const box = btn.querySelector('.crm-deal-checklist-box');
            if (box) box.innerHTML = nextDone ? '<i class="fas fa-check"></i>' : '';
            const prog = data.progress || {};
            root.querySelector('.crm-deal-checklist-track i')?.style.setProperty('width', `${prog.pct || 0}%`);
            const ring = root.querySelector('.crm-deal-checklist-ring span');
            if (ring) ring.textContent = `${prog.pct || 0}%`;
            if (ring?.parentElement) ring.parentElement.style.setProperty('--pct', prog.pct || 0);
            const sub = root.querySelector('.crm-deal-checklist-title p');
            if (sub) sub.textContent = `${prog.required_done}/${prog.required_total} مورد الزامی · ${prog.pct}% تکمیل`;
        } catch (err) {
            window.alert(err.message || 'به‌روزرسانی چک‌لیست انجام نشد.');
        } finally {
            btn.disabled = false;
        }
    });
}

function initCRMTeamPage() {
    const root = document.querySelector('[data-crm-team]');
    if (!root) return;

    root.querySelectorAll('[data-auto-submit]').forEach(sel => {
        sel.addEventListener('change', () => sel.closest('form')?.requestSubmit());
    });

    root.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', e => {
            const msg = form.dataset.confirm;
            if (msg && !window.confirm(msg)) e.preventDefault();
        });
    });

    const copyText = async (text, btn) => {
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
            if (btn) {
                const icon = btn.querySelector('i');
                const prev = icon?.className;
                if (icon) icon.className = 'fas fa-check';
                setTimeout(() => { if (icon && prev) icon.className = prev; }, 1400);
            }
        } catch {
            window.prompt('کپی کنید:', text);
        }
    };

    document.getElementById('crm-api-key-copy')?.addEventListener('click', e => {
        copyText(document.getElementById('crm-api-key')?.textContent?.trim(), e.currentTarget);
    });
    document.getElementById('crm-api-url-copy')?.addEventListener('click', e => {
        copyText(document.getElementById('crm-api-url')?.textContent?.trim(), e.currentTarget);
    });

    const exportBtn = document.getElementById('crm-sync-export-btn');
    if (exportBtn && window.crmSyncExportUrl) {
        exportBtn.addEventListener('click', async () => {
            exportBtn.disabled = true;
            const label = exportBtn.querySelector('span');
            const prev = label?.textContent;
            if (label) label.textContent = 'در حال آماده‌سازی…';
            try {
                const res = await fetch(window.crmSyncExportUrl, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `crm-export-${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
                URL.revokeObjectURL(a.href);
            } catch {
                window.alert('خروجی گرفته نشد.');
            } finally {
                exportBtn.disabled = false;
                if (label && prev) label.textContent = prev;
            }
        });
    }

    const importInput = document.getElementById('crm-sync-import-file');
    const dropzone = document.getElementById('crm-sync-dropzone');
    const importStatus = document.getElementById('crm-sync-import-status');

    const runImport = async file => {
        if (!file || !window.crmSyncImportUrl) return;
        importStatus.hidden = false;
        importStatus.classList.remove('is-error', 'is-success');
        importStatus.textContent = 'در حال بارگذاری…';
        try {
            const text = await file.text();
            const payload = JSON.parse(text);
            const res = await fetch(window.crmSyncImportUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            const s = data.stats || {};
            importStatus.classList.add('is-success');
            importStatus.textContent = `انجام شد — مخاطب: ${s.customers || 0} · ملک: ${s.properties || 0} · ردشده: ${s.skipped || 0}`;
        } catch (err) {
            importStatus.classList.add('is-error');
            importStatus.textContent = err.message || 'ورودی نامعتبر بود.';
        }
        if (importInput) importInput.value = '';
    };

    if (importInput) {
        importInput.addEventListener('change', () => runImport(importInput.files?.[0]));
    }

    if (dropzone && importInput) {
        dropzone.addEventListener('click', () => importInput.click());
        ['dragenter', 'dragover'].forEach(ev => {
            dropzone.addEventListener(ev, e => {
                e.preventDefault();
                dropzone.classList.add('is-dragover');
            });
        });
        ['dragleave', 'drop'].forEach(ev => {
            dropzone.addEventListener(ev, e => {
                e.preventDefault();
                dropzone.classList.remove('is-dragover');
            });
        });
        dropzone.addEventListener('drop', e => {
            const file = e.dataTransfer?.files?.[0];
            if (file) runImport(file);
        });
    }

    requestAnimationFrame(() => {
        root.querySelectorAll('.crm-team-metric-bar i').forEach(bar => {
            const w = bar.style.width;
            bar.style.width = '0';
            requestAnimationFrame(() => { bar.style.width = w; });
        });
    });
}

function initCRMContactTeam() {
    const bar = document.querySelector('[data-crm-contact-team]');
    if (!bar) return;
    const shareUrl = window.crmTeamShareUrl;
    const transferUrl = window.crmTeamTransferUrl;
    const revokeTpl = window.crmShareRevokeUrlTemplate || window.crmShareRevokeUrlBase;
    const select = document.getElementById('crm-share-select');
    const shareBtn = document.getElementById('crm-share-btn');
    const transferBtn = document.getElementById('crm-transfer-btn');

    const postMember = async (url, memberId, note = '') => {
        const body = new FormData();
        body.append('member_id', memberId);
        if (note) body.append('note', note);
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
            body,
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'خطا');
    };

    if (shareBtn && shareUrl && select) {
        shareBtn.addEventListener('click', async () => {
            const memberId = select.value;
            if (!memberId) {
                window.alert('هم‌تیمی مقصد را انتخاب کنید.');
                return;
            }
            shareBtn.disabled = true;
            try {
                await postMember(shareUrl, memberId);
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'اشتراک انجام نشد.');
            } finally {
                shareBtn.disabled = false;
            }
        });
    }

    if (transferBtn && transferUrl && select) {
        transferBtn.addEventListener('click', async () => {
            const memberId = select.value;
            if (!memberId) {
                window.alert('مشاور مقصد را انتخاب کنید.');
                return;
            }
            const note = window.prompt('یادداشت انتقال (اختیاری):', '') ?? '';
            if (note === null) return;
            if (!window.confirm('مالکیت این مخاطب منتقل شود؟')) return;
            transferBtn.disabled = true;
            try {
                await postMember(transferUrl, memberId, note);
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'انتقال انجام نشد.');
            } finally {
                transferBtn.disabled = false;
            }
        });
    }

    bar.querySelectorAll('[data-revoke-share]').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!revokeTpl || !window.confirm('اشتراک لغو شود؟')) return;
            try {
                const res = await fetch(crmShareRevokeUrl(btn.dataset.revokeShare), {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error || 'خطا');
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'لغو اشتراک انجام نشد.');
            }
        });
    });
}

function initCRMPropertyImages(scope) {
    const root = (scope || document).querySelector('[data-crm-prop-images]');
    if (!root || root.dataset.ready === '1') return;
    root.dataset.ready = '1';

    const uploadUrl = root.dataset.uploadUrl;
    const maxImages = parseInt(root.dataset.maxImages || '12', 10);
    const hidden = root.querySelector('[data-crm-prop-images-json]');
    const grid = root.querySelector('[data-crm-prop-img-grid]');
    const fileInput = root.querySelector('[data-crm-prop-img-file]');
    const urlInput = root.querySelector('[data-crm-prop-img-url]');
    const urlBtn = root.querySelector('[data-crm-prop-img-url-btn]');
    const countEl = root.closest('#crm-prop-images-section')?.querySelector('[data-crm-prop-img-count]');
    const dataEl = document.getElementById('crm-prop-images-data');

    let images = [];
    try {
        images = dataEl ? JSON.parse(dataEl.textContent) : [];
        if (!Array.isArray(images)) images = [];
    } catch {
        images = [];
    }

    function syncHidden() {
        if (hidden) hidden.value = JSON.stringify(images);
        if (countEl) {
            countEl.textContent = images.length ? `${images.length} تصویر` : 'بدون تصویر';
        }
        syncHeroCover();
    }

    function syncHeroCover() {
        const coverLink = document.querySelector('[data-crm-prop-hero-cover]');
        const coverImg = coverLink?.querySelector('img');
        const emptyCover = document.querySelector('.crm-prop-hero-cover--empty');
        if (images.length && coverImg) {
            coverImg.src = images[0];
            coverLink.href = images[0];
            coverLink.style.display = '';
            emptyCover?.closest('.crm-prop-hero-visual')?.querySelector('.crm-prop-hero-cover--empty')?.remove();
        } else if (!images.length && coverImg) {
            coverImg.removeAttribute('src');
        }
    }

    function render() {
        if (!grid) return;
        grid.innerHTML = '';
        if (!images.length) {
            grid.innerHTML = '<div class="crm-prop-img-empty"><i class="fas fa-image"></i><span>هنوز تصویری اضافه نشده</span></div>';
            syncHidden();
            return;
        }
        images.forEach((url, idx) => {
            const item = document.createElement('div');
            item.className = `crm-prop-img-item${idx === 0 ? ' is-cover' : ''}`;
            const img = document.createElement('img');
            img.src = url;
            img.alt = '';
            img.loading = 'lazy';
            const actions = document.createElement('div');
            actions.className = 'crm-prop-img-item-actions';
            if (idx === 0) {
                const badge = document.createElement('span');
                badge.className = 'crm-prop-img-cover-badge';
                badge.textContent = 'کاور';
                actions.appendChild(badge);
            } else {
                const coverBtn = document.createElement('button');
                coverBtn.type = 'button';
                coverBtn.title = 'تنظیم به‌عنوان کاور';
                coverBtn.innerHTML = '<i class="fas fa-star"></i>';
                coverBtn.addEventListener('click', () => {
                    images = [url, ...images.filter((_, i) => i !== idx)];
                    render();
                });
                actions.appendChild(coverBtn);
            }
            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.title = 'حذف';
            delBtn.innerHTML = '<i class="fas fa-trash"></i>';
            delBtn.addEventListener('click', () => {
                if (!window.confirm('این تصویر حذف شود؟')) return;
                images = images.filter((_, i) => i !== idx);
                render();
            });
            actions.appendChild(delBtn);
            item.appendChild(img);
            item.appendChild(actions);
            grid.appendChild(item);
        });
        syncHidden();
    }

    async function uploadFile(file) {
        if (!uploadUrl) return;
        if (images.length >= maxImages) {
            window.alert(`حداکثر ${maxImages} تصویر مجاز است.`);
            return;
        }
        const fd = new FormData();
        fd.append('image', file);
        const res = await fetch(uploadUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
            body: fd,
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'آپلود ناموفق بود');
        images = Array.isArray(data.images) ? data.images : images.concat([data.url]);
        render();
    }

    function addUrl(raw) {
        const url = String(raw || '').trim();
        if (!url) return;
        if (!/^https?:\/\//i.test(url)) {
            window.alert('لینک باید با http یا https شروع شود.');
            return;
        }
        if (images.includes(url)) {
            window.alert('این تصویر قبلاً اضافه شده است.');
            return;
        }
        if (images.length >= maxImages) {
            window.alert(`حداکثر ${maxImages} تصویر مجاز است.`);
            return;
        }
        images.push(url);
        render();
    }

    if (fileInput) {
        fileInput.addEventListener('change', async () => {
            const files = Array.from(fileInput.files || []);
            fileInput.value = '';
            for (const file of files) {
                try {
                    await uploadFile(file);
                } catch (err) {
                    window.alert(err.message || 'آپلود ناموفق بود');
                    break;
                }
            }
        });
    }

    const uploadLabel = root.querySelector('.crm-prop-img-upload');
    if (uploadLabel) {
        ['dragenter', 'dragover'].forEach(evt => {
            uploadLabel.addEventListener(evt, e => {
                e.preventDefault();
                uploadLabel.classList.add('is-dragover');
            });
        });
        ['dragleave', 'drop'].forEach(evt => {
            uploadLabel.addEventListener(evt, e => {
                e.preventDefault();
                uploadLabel.classList.remove('is-dragover');
            });
        });
        uploadLabel.addEventListener('drop', async e => {
            const files = Array.from(e.dataTransfer?.files || []).filter(f => f.type.startsWith('image/'));
            for (const file of files) {
                try {
                    await uploadFile(file);
                } catch (err) {
                    window.alert(err.message || 'آپلود ناموفق بود');
                    break;
                }
            }
        });
    }

    if (urlBtn && urlInput) {
        urlBtn.addEventListener('click', () => {
            addUrl(urlInput.value);
            urlInput.value = '';
        });
        urlInput.addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addUrl(urlInput.value);
                urlInput.value = '';
            }
        });
    }

    document.querySelectorAll('.crm-prop-hero-cover-edit').forEach(btn => {
        btn.addEventListener('click', () => {
            window.setTimeout(() => {
                document.getElementById('crm-prop-images-section')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 280);
        });
    });

    render();
}

function initCRMPropertyTeam() {
    const bar = document.querySelector('[data-crm-property-team]');
    if (!bar) return;
    const shareUrl = window.crmPropShareUrl;
    const revokeTpl = window.crmShareRevokeUrlTemplate || window.crmShareRevokeUrlBase;
    const select = document.getElementById('crm-prop-share-select');
    const shareBtn = document.getElementById('crm-prop-share-btn');

    if (shareBtn && shareUrl && select) {
        shareBtn.addEventListener('click', async () => {
            const memberId = select.value;
            if (!memberId) {
                window.alert('هم‌تیمی مقصد را انتخاب کنید.');
                return;
            }
            const modeInput = bar.querySelector('input[name="crm-prop-share-mode"]:checked');
            const shareMode = modeInput ? modeInput.value : 'confidential';
            shareBtn.disabled = true;
            try {
                const body = new FormData();
                body.append('member_id', memberId);
                body.append('share_mode', shareMode);
                const res = await fetch(shareUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
                    body,
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error || 'خطا');
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'اشتراک انجام نشد.');
            } finally {
                shareBtn.disabled = false;
            }
        });
    }

    bar.querySelectorAll('[data-revoke-share]').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!revokeTpl || !window.confirm('اشتراک لغو شود؟')) return;
            try {
                const res = await fetch(crmShareRevokeUrl(btn.dataset.revokeShare), {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (!data.ok) throw new Error(data.error || 'خطا');
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'لغو اشتراک انجام نشد.');
            }
        });
    });
}

function initCRMCommissionSplit() {
    const card = document.querySelector('[data-crm-commission]');
    const saveBtn = document.getElementById('crm-commission-save');
    const url = window.crmDealCommissionUrl;
    if (!card || !saveBtn || !url) return;

    saveBtn.addEventListener('click', async () => {
        const splits = [];
        card.querySelectorAll('.crm-deal-commission-editor input[data-member-id]').forEach(input => {
            const pct = parseFloat(input.value || '0');
            if (pct > 0) splits.push({ member_id: parseInt(input.dataset.memberId, 10), percent: pct });
        });
        saveBtn.disabled = true;
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ splits }),
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            window.location.reload();
        } catch (err) {
            window.alert(err.message || 'ذخیره تقسیم انجام نشد.');
        } finally {
            saveBtn.disabled = false;
        }
    });
}

function initCRMDealsPage() {
    const page = document.querySelector('.crm-deals-pro');
    if (!page) return;

    page.querySelectorAll('.crm-deals-row[data-href]').forEach(row => {
        row.addEventListener('click', e => {
            if (e.target.closest('a, button, input, select, textarea, label')) return;
            window.location.href = row.dataset.href;
        });
    });

    const search = page.querySelector('.crm-deals-search input[type="search"]');
    if (search) {
        let timer;
        search.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => search.form?.submit(), 420);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-drawer-open]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            CRMDrawer.open(btn.dataset.drawerOpen);
        });
    });

    document.querySelectorAll('[data-drawer-close]').forEach(el => {
        el.addEventListener('click', () => {
            const drawer = el.closest('.crm-drawer');
            if (drawer) CRMDrawer.close(drawer);
        });
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') CRMDrawer.closeAll();
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const input = document.getElementById('crmSearchInput');
            if (input) input.focus();
        }
    });

    document.querySelectorAll('.crm-drawer[data-open="1"]').forEach(d => CRMDrawer.open(d.id));

    initCRMTypeProfiles();
    initPropertyDealMode();
    initCRMGlobalSearch();
    initCRMMultiSelect();
    initCRMTabs();
    initCRMJalaliPickers(document);
    initCRMMoneyInputs(document);
    initCRMFormErrors();
    initCRMContactFormGuard();
    initCRMPipeline();
    initCRMDealPipeline();
    initCRMPropertyPipeline();
    initCRMSavedFilters();
    initCRMDealStagesEditor();
    initCRMDealChecklist();
    initCRMCommissionSplit();
    initCRMContactTeam();
        initCRMPropertyTeam();
        initCRMPropertyImages();
        initCRMTeamPage();
    initCRMDealsPage();
    initCRMSidePanel();
    initCRMQuickLead();
    initCRMImportDrawer();
    initCRMMatches();
    initCRMVisitOutcome(document);
    initCRMNotifications();

    if (typeof window.wsCharts !== 'undefined' && window.Chart) {
        if (typeof initCharts === 'function') initCharts(window.wsCharts);
    }
});
