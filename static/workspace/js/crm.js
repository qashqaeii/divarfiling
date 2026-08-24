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
        // زمان فقط برای inputهای datetime (بدون data-jdp-only-date) فعال می‌شود
        time: true,
        hasSecond: false,
        hideAfterChange: false,
    });
}

function crmJalaliYmdFromDate(date) {
    const parts = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).formatToParts(date);
    let y = '', m = '', d = '';
    parts.forEach((part) => {
        if (part.type === 'year') y = part.value;
        if (part.type === 'month') m = part.value;
        if (part.type === 'day') d = part.value;
    });
    if (!y || !m || !d) return '';
    return `${y}/${m}/${d}`;
}

function crmLeaseDeadlinePreset(kind) {
    const now = new Date();
    const target = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (kind === 'month') target.setMonth(target.getMonth() + 1);
    else if (kind === 'quarter') target.setMonth(target.getMonth() + 3);
    else if (kind === 'half') target.setMonth(target.getMonth() + 6);
    else if (kind === 'year') target.setFullYear(target.getFullYear() + 1);
    return crmJalaliYmdFromDate(target);
}

function crmShowsLeaseDeadline(type) {
    const types = window.crmLeaseDeadlineTypes;
    const allowed = Array.isArray(types)
        ? types
        : ['مستاجر', 'متقاضی اجاره', 'متقاضی رهن و اجاره'];
    return allowed.includes(String(type || '').trim());
}

function initCRMLeaseDeadline(root) {
    const scope = root || document;
    scope.querySelectorAll('.crm-lease-deadline').forEach((block) => {
        if (block.dataset.crmLeaseBound === '1') return;
        block.dataset.crmLeaseBound = '1';
        const input = block.querySelector('[name="lease_deadline"]');
        const clearBtn = block.querySelector('[data-lease-date-clear]');
        const sync = () => {
            const raw = input ? String(input.value || '').trim() : '';
            if (clearBtn) clearBtn.hidden = !raw;
        };
        if (input) {
            input.addEventListener('change', sync);
            input.addEventListener('input', sync);
        }
        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (input) input.value = '';
                sync();
            });
        }
        block.querySelectorAll('[data-lease-date-preset]').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (input) input.value = crmLeaseDeadlinePreset(btn.getAttribute('data-lease-date-preset'));
                sync();
            });
        });
        sync();
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
        initCRMFeatureProfile(drawer);
        initCRMTypeProfiles(drawer);
        initCRMLeaseDeadline(drawer);
        initCRMPropertyOccVacancyDate(drawer);
        initCRMContactChannels(drawer);
        initCRMAreasPicker(drawer);
        initCRMFormErrors();
        if (id === 'drawer-import' || id === 'drawer-property-import') initCRMImportDrawer(drawer);
        else if (id === 'drawer-activity') initCRMActivityDrawer(drawer);
        else initCRMVisitOutcome(drawer);
        initCRMPropertyImages(drawer);
        if (typeof window.initCRMFormMaps === 'function') {
            window.initCRMFormMaps(drawer);
        }
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

function crmSetFieldLabel(section, fieldName, text) {
    const lbl = section.querySelector(`[data-field="${fieldName}"] .crm-label`);
    if (lbl && text) lbl.textContent = text;
}

function initCRMTypeProfiles(root) {
    const profiles = window.crmTypeProfiles || {};
    const scope = root || document;
    const LAND_LIKE = new Set(['زمین', 'کلنگی']);

    scope.querySelectorAll('.crm-form-sections').forEach(section => {
        const typeSelect = section.querySelector('[data-crm-type]') || section.querySelector('[name="customer_type"]');
        if (!typeSelect) return;

        const hint = section.querySelector('#crmMoneyHint');
        const prefsHint = section.querySelector('#crmPrefsHint');
        const budgetFields = section.querySelectorAll('.crm-money-budget');
        const depositFields = section.querySelectorAll('.crm-money-deposit');
        const rentFields = section.querySelectorAll('.crm-money-rent');
        const builderSections = section.querySelectorAll('.crm-builder-section');
        const builderBuyFields = section.querySelectorAll('.crm-builder-buy-field');
        const builderBuyMoney = section.querySelectorAll('.crm-money-builder-buy');
        const prefsStandard = section.querySelectorAll('.crm-prefs-standard');
        const prefsRooms = section.querySelectorAll('.crm-prefs-rooms');
        const prefsSize = section.querySelectorAll('.crm-prefs-size');
        const prefsYear = section.querySelectorAll('.crm-prefs-year');
        const prefsFloor = section.querySelectorAll('.crm-prefs-floor');
        const prefsLocation = section.querySelectorAll('.crm-prefs-location');
        const prefsAmenities = section.querySelectorAll('.crm-prefs-amenities-block');
        const leaseDeadlineFields = section.querySelectorAll('.crm-lease-deadline');
        const propertyTypeSelect = section.querySelector('[name="property_type"]');

        function applyResidentialVisibility(propType, prefsMode) {
            const isBuilder = prefsMode === 'builder';
            const showDetail = prefsMode === 'seeker' || prefsMode === 'listing' || prefsMode === 'flexible' || isBuilder;
            const landLike = LAND_LIKE.has(propType || '');
            const showUnitDetails = showDetail && !landLike;
            const show = (els, on) => els.forEach(el => el.classList.toggle('hidden', !on));
            show(prefsRooms, showUnitDetails);
            show(prefsSize, showDetail);
            show(prefsYear, showUnitDetails);
            show(prefsFloor, showUnitDetails);
            show(prefsLocation, showDetail || isBuilder);
            show(prefsAmenities, showUnitDetails);
        }

        function applyProfile(type) {
            const p = profiles[type] || profiles['سرنخ'] || {};
            const mode = p.money_mode || 'flexible';
            const prefsMode = p.prefs_mode || (mode === 'builder' ? 'builder' : 'flexible');
            const isBuilder = mode === 'builder' || prefsMode === 'builder';
            const showBudget = mode === 'budget' || mode === 'both' || mode === 'flexible' || isBuilder;
            const showRent = mode === 'rent' || mode === 'both' || mode === 'flexible';

            if (hint) hint.textContent = p.section_hint || 'محدوده مالی بر اساس نوع مخاطب';
            if (prefsHint) {
                prefsHint.textContent = p.prefs_hint
                    || (isBuilder
                        ? 'مشخصات واحدهای آپارتمان در حال فروش و محله‌های پروژه'
                        : 'نوع ملک، متراژ، خواب و امکانات مورد نظر');
            }

            const show = (els, on) => els.forEach(el => el.classList.toggle('hidden', !on));
            show(builderSections, isBuilder);
            show(prefsStandard, !isBuilder);
            show(budgetFields, showBudget);
            show(depositFields, showRent);
            show(rentFields, showRent);
            show(builderBuyFields, isBuilder);
            show(builderBuyMoney, isBuilder);
            show(leaseDeadlineFields, crmShowsLeaseDeadline(type));

            const bl = p.budget_labels || ['بودجه از', 'بودجه تا'];
            const dl = p.deposit_labels || ['ودیعه از', 'ودیعه تا'];
            const rl = p.rent_labels || ['اجاره از', 'اجاره تا'];
            crmSetFieldLabel(section, 'budget_min', bl[0]);
            crmSetFieldLabel(section, 'budget_max', bl[1]);
            crmSetFieldLabel(section, 'deposit_min', dl[0]);
            crmSetFieldLabel(section, 'deposit_max', dl[1]);
            crmSetFieldLabel(section, 'rent_min', rl[0]);
            crmSetFieldLabel(section, 'rent_max', rl[1]);

            const areasLabel = prefsMode === 'listing'
                ? 'محله ملک'
                : (isBuilder ? 'محله‌های فروش / پروژه' : 'محله‌های مورد نظر');
            crmSetFieldLabel(section, 'areas', areasLabel);

            section.querySelectorAll('[data-label-budget-min]').forEach(el => { el.textContent = bl[0]; });
            section.querySelectorAll('[data-label-budget-max]').forEach(el => { el.textContent = bl[1]; });
            section.querySelectorAll('[data-label-deposit-min]').forEach(el => { el.textContent = dl[0]; });
            section.querySelectorAll('[data-label-deposit-max]').forEach(el => { el.textContent = dl[1]; });
            section.querySelectorAll('[data-label-rent-min]').forEach(el => { el.textContent = rl[0]; });
            section.querySelectorAll('[data-label-rent-max]').forEach(el => { el.textContent = rl[1]; });

            const sellTitle = section.querySelector('#crmBuilderSellTitle');
            const sellHint = section.querySelector('#crmBuilderSellHint');
            const buyTitle = section.querySelector('#crmBuilderBuyTitle');
            const buyHint = section.querySelector('#crmBuilderBuyHint');
            const prefsBuilderTitle = section.querySelector('#crmPrefsBuilderTitle');
            const prefsTitle = section.querySelector('#crmPrefsTitle');
            if (sellTitle && p.sell_section_title) sellTitle.textContent = p.sell_section_title;
            if (sellHint && p.sell_section_hint) sellHint.textContent = p.sell_section_hint;
            if (buyTitle && p.buy_section_title) buyTitle.textContent = p.buy_section_title;
            if (buyHint && p.buy_section_hint) buyHint.textContent = p.buy_section_hint;
            if (prefsBuilderTitle) {
                prefsBuilderTitle.textContent = p.sell_section_title
                    ? p.sell_section_title.replace('خط فروش — ', 'مشخصات ')
                    : 'مشخصات واحد فروش (آپارتمان)';
            }
            if (prefsTitle) prefsTitle.textContent = p.prefs_title || 'ترجیحات ملک';

            if (isBuilder && propertyTypeSelect && p.default_property_type) {
                const hasOption = Array.from(propertyTypeSelect.options).some(o => o.value === p.default_property_type);
                if (hasOption && (!propertyTypeSelect.value || propertyTypeSelect.value === 'سایر')) {
                    propertyTypeSelect.value = p.default_property_type;
                }
            }

            applyResidentialVisibility(propertyTypeSelect ? propertyTypeSelect.value : '', prefsMode);
            section.dataset.crmPrefsMode = prefsMode;
        }

        applyProfile(typeSelect.value);
        if (typeSelect.dataset.crmTypeBound !== '1') {
            typeSelect.dataset.crmTypeBound = '1';
            typeSelect.addEventListener('change', () => applyProfile(typeSelect.value));
        }
        if (propertyTypeSelect && propertyTypeSelect.dataset.crmPropTypeBound !== '1') {
            propertyTypeSelect.dataset.crmPropTypeBound = '1';
            propertyTypeSelect.addEventListener('change', () => {
                applyResidentialVisibility(
                    propertyTypeSelect.value,
                    section.dataset.crmPrefsMode || 'flexible',
                );
            });
        }
    });
}

const CRM_PROPERTY_DEAL_PRICE_PROFILES = {
    'فروش': {
        title: 'قیمت فروش',
        hint: 'قیمت توافقی یا نهایی فروش',
        showSale: true,
        showDeposit: false,
        showRent: false,
        saleLabel: 'قیمت فروش (تومان)',
        saleHeading: 'فروش',
        saleHint: 'قیمت نهایی یا توافقی ملک',
    },
    'پیش‌فروش': {
        title: 'قیمت پیش‌فروش',
        hint: 'مبلغ پیش‌فروش واحد یا پروژه',
        showSale: true,
        showDeposit: false,
        showRent: false,
        saleLabel: 'قیمت پیش‌فروش (تومان)',
        saleHeading: 'پیش‌فروش',
        saleHint: 'مبلغ توافقی پیش‌فروش',
    },
    'رهن و اجاره': {
        title: 'رهن و اجاره',
        hint: 'مبالغ رهن و اجاره ماهانه',
        showSale: false,
        showDeposit: true,
        showRent: true,
        depositLabel: 'مبلغ رهن (تومان)',
        rentLabel: 'اجاره ماهانه (تومان)',
        depositHeading: 'رهن',
        depositHint: 'مبلغ رهن / تبدیل‌پذیر',
        rentHeading: 'اجاره',
        rentHint: 'اجاره ماهانه پس از رهن',
    },
    'اجاره': {
        title: 'اجاره',
        hint: 'ودیعه و اجاره ماهانه',
        showSale: false,
        showDeposit: true,
        showRent: true,
        depositLabel: 'ودیعه (تومان)',
        rentLabel: 'اجاره ماهانه (تومان)',
        depositHeading: 'ودیعه',
        depositHint: 'مبلغ ودیعه نزد مالک',
        rentHeading: 'اجاره',
        rentHint: 'اجاره ماهانه',
    },
};

function crmResolveDealMode(dealSelect, priceSection) {
    if (!dealSelect) return 'فروش';
    const profiles = CRM_PROPERTY_DEAL_PRICE_PROFILES;
    const pick = (raw) => {
        const mode = String(raw || '').trim();
        return mode && profiles[mode] ? mode : '';
    };
    if (dealSelect.tagName === 'SELECT') {
        const fromValue = pick(dealSelect.value);
        if (fromValue) return fromValue;
        const selected = dealSelect.options?.[dealSelect.selectedIndex];
        if (selected) {
            const fromOpt = pick(selected.value) || pick(selected.textContent);
            if (fromOpt) return fromOpt;
        }
    } else {
        const fromDataset = pick(dealSelect.dataset?.dealMode);
        if (fromDataset) return fromDataset;
    }
    const fromAttr = pick(dealSelect.getAttribute('data-initial-deal-mode'));
    if (fromAttr) return fromAttr;
    const section = priceSection || dealSelect.closest('[data-crm-prop-price]');
    if (section) {
        const fromSection = pick(section.dataset.dealMode);
        if (fromSection) return fromSection;
    }
    return 'فروش';
}

function crmOccVacancyPreset(kind) {
    const now = new Date();
    const target = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (kind === 'tomorrow') target.setDate(target.getDate() + 1);
    else if (kind === 'week') target.setDate(target.getDate() + 7);
    else if (kind === 'month') target.setMonth(target.getMonth() + 1);
    return crmJalaliYmdFromDate(target);
}

function bindCRMOccVacancyDate(shell) {
    if (!shell || shell.dataset.occVacancyBound === '1') return;
    shell.dataset.occVacancyBound = '1';
    const input = shell.querySelector('[data-occ-date]');
    const clearBtn = shell.querySelector('[data-occ-date-clear]');
    const moreVal = shell.querySelector('[data-occ-more-val]');
    const moreHint = shell.querySelector('[data-occ-more-hint]');
    const more = shell.querySelector('[data-occ-more]');
    const sync = () => {
        const raw = input ? String(input.value || '').trim() : '';
        if (clearBtn) clearBtn.hidden = !raw;
        if (moreVal) {
            moreVal.textContent = raw;
            moreVal.hidden = !raw;
        }
        if (moreHint) {
            moreHint.textContent = raw
                ? 'تاریخ انتخاب‌شده در تقویم شمسی'
                : 'تاریخ تخلیه اختیاری — تقویم شمسی';
        }
        if (more && raw) more.open = true;
    };
    if (input) {
        input.addEventListener('change', sync);
        input.addEventListener('input', sync);
    }
    if (clearBtn) {
        clearBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (input) input.value = '';
            sync();
        });
    }
    shell.querySelectorAll('[data-occ-date-preset]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (input) input.value = crmOccVacancyPreset(btn.getAttribute('data-occ-date-preset'));
            sync();
        });
    });
    sync();
}

function initCRMPropertyOccVacancyDate(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-occ-shell]').forEach((shell) => bindCRMOccVacancyDate(shell));
}

function initPropertyDealMode(root) {
    const scope = root || document;
    scope.querySelectorAll('select[data-deal-mode], select[name="deal_mode"]').forEach(dealSelect => {
        const form = dealSelect.closest('form') || scope;
        const sale = form.querySelectorAll('.crm-price-sale');
        const deposit = form.querySelectorAll('.crm-price-deposit');
        const rent = form.querySelectorAll('.crm-price-rent');
        const priceSection = form.querySelector('[data-crm-prop-price]');
        const titleEl = form.querySelector('[data-crm-price-title]');
        const hintEl = form.querySelector('[data-crm-price-hint]');
        const saleLabel = form.querySelector('[data-crm-label-sale]');
        const depositLabel = form.querySelector('[data-crm-label-deposit]');
        const rentLabel = form.querySelector('[data-crm-label-rent]');
        const saleHeading = form.querySelector('[data-crm-price-sale-heading]');
        const depositHeading = form.querySelector('[data-crm-price-deposit-heading]');
        const rentHeading = form.querySelector('[data-crm-price-rent-heading]');
        const saleHint = form.querySelector('[data-crm-price-sale-hint]');
        const depositHint = form.querySelector('[data-crm-price-deposit-hint]');
        const rentHint = form.querySelector('[data-crm-price-rent-hint]');
        const perSqmEl = form.querySelector('[data-crm-price-per-sqm]');
        const saleInput = form.querySelector('[name="sale_price"]');
        const areaInput = form.querySelector('[name="area"]');
        const vacantPanels = form.querySelectorAll('[data-vacant-panel]');
        const tenantPanels = form.querySelectorAll('[data-tenant-panel]');
        const vacantCheckbox = form.querySelector('[data-vacant-checkbox], [name="is_vacant"]');
        const tenantInputs = form.querySelectorAll('[data-tenant-field], [name="tenant_phone"], [name="tenant_name"]');
        const occShell = form.querySelector('[data-occ-shell]');
        const occBtns = form.querySelectorAll('[data-occ-set]');
        const occPill = form.querySelector('[data-occ-pill]');
        const occConfirm = form.querySelector('[data-occ-confirm]');
        const PROFILES = CRM_PROPERTY_DEAL_PRICE_PROFILES;

        function parseMoney(raw) {
            if (raw == null || raw === '') return null;
            const s = String(raw).replace(/[^\d]/g, '');
            if (!s) return null;
            const n = Number(s);
            return Number.isFinite(n) ? n : null;
        }

        function formatToman(n) {
            try {
                return new Intl.NumberFormat('fa-IR').format(Math.round(n));
            } catch (e) {
                return String(Math.round(n));
            }
        }

        function updatePerSqm(mode) {
            if (!perSqmEl) return;
            const profile = PROFILES[mode] || PROFILES['فروش'];
            if (!profile.showSale) {
                perSqmEl.hidden = true;
                return;
            }
            const price = parseMoney(saleInput && saleInput.value);
            const area = parseFloat(areaInput && areaInput.value);
            if (!price || !area || area <= 0) {
                perSqmEl.hidden = true;
                perSqmEl.textContent = '';
                return;
            }
            perSqmEl.hidden = false;
            perSqmEl.innerHTML = `<i class="fas fa-calculator" aria-hidden="true"></i> حدود <strong>${formatToman(price / area)}</strong> تومان در هر متر`;
        }

        function syncOccupancyUI() {
            const vacantOn = !!(vacantCheckbox && vacantCheckbox.checked);
            vacantPanels.forEach((el) => el.classList.remove('hidden'));
            if (occShell) {
                occShell.classList.remove('hidden');
                occShell.classList.toggle('is-vacant', vacantOn);
                occShell.classList.toggle('is-occupied', !vacantOn);
            }
            occBtns.forEach((btn) => {
                const wantVacant = btn.getAttribute('data-occ-set') === '1';
                const active = wantVacant === vacantOn;
                btn.classList.toggle('is-active', active);
                btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            if (occPill) {
                occPill.textContent = vacantOn ? 'تخلیه' : 'تخلیه نیست';
            }
            if (occConfirm) {
                occConfirm.hidden = !vacantOn;
            }
            tenantPanels.forEach((el) => {
                el.classList.remove('hidden');
                el.classList.toggle('is-disabled', vacantOn);
            });
            tenantInputs.forEach((el) => {
                el.disabled = vacantOn;
                if (vacantOn && 'value' in el) el.value = '';
            });
        }

        function apply(mode) {
            const resolved = crmResolveDealMode(dealSelect, priceSection);
            const effectiveMode = (mode && PROFILES[mode]) ? mode : resolved;
            const profile = PROFILES[effectiveMode] || PROFILES['فروش'];
            const show = (els, on) => els.forEach(el => el.classList.toggle('hidden', !on));
            show(sale, profile.showSale);
            show(deposit, profile.showDeposit);
            show(rent, profile.showRent);
            syncOccupancyUI();
            if (priceSection) {
                priceSection.dataset.dealMode = effectiveMode;
            }
            if (titleEl) titleEl.textContent = profile.title || 'قیمت و یادداشت';
            if (hintEl) hintEl.textContent = profile.hint || '';
            if (saleLabel && profile.saleLabel) saleLabel.textContent = profile.saleLabel;
            if (depositLabel && profile.depositLabel) depositLabel.textContent = profile.depositLabel;
            if (rentLabel && profile.rentLabel) rentLabel.textContent = profile.rentLabel;
            if (saleHeading && profile.saleHeading) saleHeading.textContent = profile.saleHeading;
            if (depositHeading && profile.depositHeading) depositHeading.textContent = profile.depositHeading;
            if (rentHeading && profile.rentHeading) rentHeading.textContent = profile.rentHeading;
            if (saleHint && profile.saleHint) saleHint.textContent = profile.saleHint;
            if (depositHint && profile.depositHint) depositHint.textContent = profile.depositHint;
            if (rentHint && profile.rentHint) rentHint.textContent = profile.rentHint;
            updatePerSqm(effectiveMode);
        }

        if (dealSelect.dataset.dealModeBound === '1') {
            apply(crmResolveDealMode(dealSelect, priceSection));
            return;
        }
        dealSelect.dataset.dealModeBound = '1';

        apply(crmResolveDealMode(dealSelect, priceSection));
        dealSelect.addEventListener('change', () => apply(dealSelect.value));
        if (vacantCheckbox) {
            vacantCheckbox.addEventListener('change', () => syncOccupancyUI());
        }
        occBtns.forEach((btn) => {
            btn.addEventListener('click', () => {
                if (!vacantCheckbox) return;
                vacantCheckbox.checked = btn.getAttribute('data-occ-set') === '1';
                vacantCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });
        if (saleInput) saleInput.addEventListener('input', () => updatePerSqm(dealSelect.value));
        if (areaInput) areaInput.addEventListener('input', () => updatePerSqm(dealSelect.value));
        bindCRMOccVacancyDate(occShell);
    });
}

function resolveCRMFeatProfile(dealMode, propertyType) {
    const commercialTypes = new Set(['اداری', 'مغازه']);
    if (commercialTypes.has(String(propertyType || '').trim())) return 'commercial';
    const rentModes = new Set(['رهن و اجاره', 'اجاره']);
    if (rentModes.has(String(dealMode || '').trim())) return 'rent';
    return 'sale';
}

function initCRMFeatureProfile(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-crm-feat]').forEach((section) => {
        if (section.dataset.crmFeatBound === '1') return;
        section.dataset.crmFeatBound = '1';
        const form = section.closest('form') || scope;
        const dealSelect = form.querySelector('select[data-deal-mode], select[name="deal_mode"]');
        const typeSelect = form.querySelector('[name="property_type"]');
        const profileInput = section.querySelector('[data-crm-feat-profile]');
        const titleEl = section.querySelector('[data-crm-feat-title]');
        const hintEl = section.querySelector('[data-crm-feat-hint]');
        const panels = section.querySelectorAll('[data-crm-feat-panel]');
        const META = {
            rent: {
                title: 'ویژگی‌های اجاره',
                hint: 'انتخاب از گزینه‌ها — مناسب قرارداد و آگهی اجاره',
            },
            sale: {
                title: 'سایر ویژگی‌ها و امکانات',
                hint: 'انتخاب از گزینه‌ها — مناسب فایل فروش و پیش‌فروش',
            },
            commercial: {
                title: 'ویژگی‌های اداری / تجاری',
                hint: 'انتخاب از گزینه‌ها — متناسب با فضای اداری یا تجاری',
            },
        };

        function setPanelEnabled(panel, on) {
            panel.hidden = !on;
            panel.querySelectorAll('input, select, textarea, button').forEach((el) => {
                el.disabled = !on;
            });
        }

        function apply() {
            const profile = resolveCRMFeatProfile(
                dealSelect ? dealSelect.value : '',
                typeSelect ? typeSelect.value : '',
            );
            if (profileInput) profileInput.value = profile;
            const meta = META[profile] || META.sale;
            if (titleEl) titleEl.textContent = meta.title;
            if (hintEl) hintEl.textContent = meta.hint;
            panels.forEach((panel) => {
                setPanelEnabled(panel, panel.getAttribute('data-crm-feat-panel') === profile);
            });
        }

        section.querySelectorAll('.crm-feat-chip input').forEach((input) => {
            input.addEventListener('change', () => {
                const name = input.name;
                section.querySelectorAll(`.crm-feat-chip input[name="${CSS.escape(name)}"]`).forEach((el) => {
                    const chip = el.closest('.crm-feat-chip');
                    if (chip) chip.classList.toggle('is-on', el.checked);
                });
            });
        });

        section.querySelectorAll('.crm-feat-toggle input[type="checkbox"]').forEach((input) => {
            const label = input.closest('.crm-feat-toggle')?.querySelector('[data-feat-toggle-txt], .crm-feat-toggle-txt');
            const sync = () => {
                if (label) label.textContent = input.checked ? 'دارد' : 'ندارد';
            };
            input.addEventListener('change', sync);
            sync();
        });

        apply();
        if (dealSelect) dealSelect.addEventListener('change', apply);
        if (typeSelect) typeSelect.addEventListener('change', apply);
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

function initCRMActivityDrawer(root) {
    const scope = (root && root.id === 'drawer-activity') ? root : (root || document).querySelector('#drawer-activity');
    if (!scope) return;

    const select = scope.querySelector('.crm-act-type-native');
    const chips = scope.querySelectorAll('[data-act-type]');
    const otherBtn = scope.querySelector('[data-act-other]');
    const otherWrap = scope.querySelector('.crm-act-type-other');
    const content = scope.querySelector('.crm-act-content');
    const quickTypes = new Set([...chips].map(c => c.dataset.actType).filter(Boolean));

    function setQuickType(type) {
        chips.forEach(c => c.classList.toggle('is-active', c.dataset.actType === type));
        otherBtn?.classList.remove('is-active');
        if (otherWrap) otherWrap.hidden = true;
        if (select && type) select.value = type;
    }

    function showOther() {
        chips.forEach(c => c.classList.remove('is-active'));
        otherBtn?.classList.add('is-active');
        if (otherWrap) otherWrap.hidden = false;
        if (select) {
            if (!select.value || quickTypes.has(select.value)) {
                const firstOther = [...select.options].find(opt => opt.value && !quickTypes.has(opt.value));
                if (firstOther) select.value = firstOther.value;
            }
            select.focus();
        }
    }

    chips.forEach(chip => {
        chip.addEventListener('click', () => setQuickType(chip.dataset.actType));
    });
    otherBtn?.addEventListener('click', showOther);

    select?.addEventListener('change', () => {
        const value = select.value;
        if (quickTypes.has(value)) setQuickType(value);
        else showOther();
    });

    const current = select?.value || 'تماس';
    if (quickTypes.has(current)) setQuickType(current);
    else showOther();

    if (scope.classList.contains('is-open') && content) {
        window.setTimeout(() => content.focus({ preventScroll: true }), 90);
    }
}

function crmEscapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function crmAvatarInitials(name) {
    if (!name) return '؟';
    const parts = String(name).trim().split(/\s+/);
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`;
    return parts[0][0] || '؟';
}

function crmAvatarHue(name) {
    if (!name) return 0;
    let sum = 0;
    for (const ch of String(name)) sum += ch.charCodeAt(0);
    return sum % 6;
}

function initCRMSidePanel() {
    const layout = document.getElementById('crmContactsLayout');
    if (!layout) return;

    const panel = document.getElementById('crmSidePanel');
    if (!panel) {
        layout.querySelectorAll('.crm-row-selectable').forEach(row => {
            row.addEventListener('click', e => {
                if (e.target.closest('a, button, input, .crm-contacts-col-check')) return;
                const link = row.querySelector('.crm-contacts-person-link');
                if (link) window.location.href = link.href;
            });
        });
        return;
    }

    const content = document.getElementById('crmSideContent');
    const loading = document.getElementById('crmSideLoading');
    const closeBtn = document.getElementById('crmSideClose');
    const backdrop = document.getElementById('crmSideBackdrop');
    if (!content) return;

    const baseUrl = window.crmPanelBase || '/workspace/crm/contacts/';
    let activeRow = null;

    function isMobilePanel() {
        return window.matchMedia('(max-width: 900px)').matches;
    }

    function setBodyLock(locked) {
        document.body.classList.toggle('crm-side-open', locked && isMobilePanel());
    }

    function closePanel() {
        panel.classList.remove('is-open');
        if (backdrop) backdrop.hidden = true;
        setBodyLock(false);
        window.setTimeout(() => {
            if (!panel.classList.contains('is-open')) {
                panel.hidden = true;
            }
        }, 280);
        layout.classList.remove('has-side-panel');
        if (activeRow) activeRow.classList.remove('is-panel-active');
        activeRow = null;
    }

    function followLabel(state, date) {
        if (!date) return { text: 'بدون پیگیری', cls: 'crm-sp-follow--none' };
        if (state === 'overdue') return { text: `معوق · ${date}`, cls: 'crm-sp-follow--overdue' };
        if (state === 'today') return { text: `امروز · ${date}`, cls: 'crm-sp-follow--today' };
        return { text: `پیگیری · ${date}`, cls: 'crm-sp-follow--upcoming' };
    }

    function insightCard(icon, label, value, extraClass) {
        if (!value) return '';
        return `<article class="crm-sp-insight ${extraClass || ''}">
            <span class="crm-sp-insight-icon" aria-hidden="true"><i class="${icon}"></i></span>
            <div class="crm-sp-insight-copy">
                <span class="crm-sp-insight-lbl">${label}</span>
                <strong class="crm-sp-insight-val">${crmEscapeHtml(value)}</strong>
            </div>
        </article>`;
    }

    function renderPanel(data) {
        const hue = data.avatar_hue ?? crmAvatarHue(data.name);
        const initials = data.initials || crmAvatarInitials(data.name);
        const follow = followLabel(data.follow_state, data.next_follow_up);
        const statusDot = data.status_dot || '#94a3b8';

        const actions = [];
        if (data.tel_url) {
            actions.push(`<a href="${data.tel_url}" class="crm-sp-action crm-sp-action--call"><i class="fas fa-phone"></i><span>تماس</span></a>`);
        }
        if (data.whatsapp_url) {
            actions.push(`<a href="${data.whatsapp_url}" target="_blank" rel="noopener" class="crm-sp-action crm-sp-action--wa"><i class="fab fa-whatsapp"></i><span>واتساپ</span></a>`);
        }
        if (data.email) {
            actions.push(`<a href="mailto:${crmEscapeHtml(data.email)}" class="crm-sp-action crm-sp-action--mail"><i class="fas fa-envelope"></i><span>ایمیل</span></a>`);
        }

        const insights = [
            insightCard('fas fa-wallet', 'بودجه', data.budget_label),
            insightCard('fas fa-map-location-dot', 'محله', data.areas),
            insightCard('fas fa-bullseye', 'منبع', data.source),
            insightCard('fas fa-wand-magic-sparkles', 'تطبیق', data.match_count ? `${data.match_count} ملک` : '', data.match_count ? 'crm-sp-insight--accent' : ''),
        ].filter(Boolean).join('');

        const activities = (data.activities || []).map(a =>
            `<li class="crm-sp-tl-item">
                <span class="crm-sp-tl-rail" aria-hidden="true"><span class="crm-sp-tl-dot"></span></span>
                <div class="crm-sp-tl-body">
                    <div class="crm-sp-tl-head">
                        <span class="crm-sp-tl-type">${crmEscapeHtml(a.activity_type)}</span>
                        <time>${crmEscapeHtml(crmFormatJalaliDatetime(a.created_at))}</time>
                    </div>
                    ${a.content || a.title ? `<p>${crmEscapeHtml(a.content || a.title)}</p>` : ''}
                </div>
            </li>`
        ).join('');

        const timelineBlock = activities
            ? `<section class="crm-sp-section"><h3 class="crm-sp-section-title"><i class="fas fa-clock-rotate-left"></i> فعالیت اخیر</h3><ol class="crm-sp-timeline">${activities}</ol></section>`
            : `<section class="crm-sp-section crm-sp-section--empty"><div class="crm-sp-empty"><i class="fas fa-inbox"></i><p>هنوز فعالیتی ثبت نشده</p></div></section>`;

        content.innerHTML = `
            <article class="crm-sp">
                <header class="crm-sp-hero">
                    <div class="crm-sp-hero-glow" aria-hidden="true"></div>
                    <div class="crm-sp-hero-main">
                        <span class="crm-sp-avatar crm-sp-avatar--hue-${hue}" aria-hidden="true">${crmEscapeHtml(initials)}</span>
                        <div class="crm-sp-hero-copy">
                            <h2 class="crm-sp-name">${crmEscapeHtml(data.name)}</h2>
                            ${data.company_name ? `<p class="crm-sp-company"><i class="fas fa-building"></i> ${crmEscapeHtml(data.company_name)}</p>` : ''}
                            <div class="crm-sp-badges">
                                <span class="crm-sp-badge crm-sp-badge--type">${crmEscapeHtml(data.customer_type)}</span>
                                <span class="crm-sp-badge crm-sp-badge--status">
                                    <span class="crm-sp-status-dot" style="background:${crmEscapeHtml(statusDot)}"></span>
                                    ${crmEscapeHtml(data.status)}
                                </span>
                                ${data.priority === 'بالا' ? '<span class="crm-sp-badge crm-sp-badge--priority">اولویت بالا</span>' : ''}
                            </div>
                        </div>
                    </div>
                    <div class="crm-sp-follow ${follow.cls}">
                        <i class="fas fa-calendar-check" aria-hidden="true"></i>
                        <span>${crmEscapeHtml(follow.text)}</span>
                    </div>
                </header>

                ${actions.length ? `<div class="crm-sp-actions">${actions.join('')}</div>` : ''}

                ${insights ? `<section class="crm-sp-section"><h3 class="crm-sp-section-title"><i class="fas fa-chart-simple"></i> خلاصه نیاز</h3><div class="crm-sp-insights">${insights}</div></section>` : ''}

                ${data.phone ? `<section class="crm-sp-section crm-sp-section--compact"><div class="crm-sp-phone"><span>تلفن</span><strong dir="ltr">${crmEscapeHtml(data.phone)}</strong></div></section>` : ''}

                ${data.notes ? `<section class="crm-sp-section"><div class="crm-sp-notes"><i class="fas fa-note-sticky"></i><p>${crmEscapeHtml(data.notes)}</p></div></section>` : ''}

                ${timelineBlock}

                <footer class="crm-sp-foot">
                    ${data.match_eligible ? `<a href="${data.matches_url || data.detail_url + '?tab=matches'}" class="crm-sp-btn crm-sp-btn--accent"><i class="fas fa-wand-magic-sparkles"></i><span>پیشنهاد ملک${data.match_count ? ` (${data.match_count})` : ''}</span></a>` : ''}
                    <a href="${data.detail_url}" class="crm-sp-btn crm-sp-btn--primary"><i class="fas fa-user"></i><span>پروفایل کامل</span></a>
                    <a href="${data.edit_url}" class="crm-sp-btn crm-sp-btn--ghost"><i class="fas fa-pen"></i><span>ویرایش</span></a>
                </footer>
            </article>`;
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
        requestAnimationFrame(() => {
            panel.classList.add('is-open');
            if (backdrop && isMobilePanel()) backdrop.hidden = false;
            setBodyLock(true);
        });

        try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            if (!data.name && data.error) throw new Error(data.error);
            renderPanel(data);
        } catch (e) {
            content.innerHTML = `<div class="crm-sp-error"><i class="fas fa-triangle-exclamation"></i><p>${crmEscapeHtml(e.message || 'خطا در بارگذاری')}</p></div>`;
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

    if (closeBtn) closeBtn.addEventListener('click', closePanel);
    if (backdrop) backdrop.addEventListener('click', closePanel);
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

function initCRMMatchingTolerance() {
    document.querySelectorAll('[data-crm-match-tolerance]').forEach(bindCRMMatchingToleranceRoot);
}

function bindCRMMatchingToleranceRoot(root) {
    if (!root || root.dataset.bound === '1') return;
    root.dataset.bound = '1';

    const range = root.querySelector('.crm-contact-pref-tolerance-range');
    const output = root.querySelector('.crm-contact-pref-tolerance-value');
    const toast = root.querySelector('[data-crm-match-tolerance-toast]');
    const url = root.dataset.url || '';
    if (!range || !url) return;

    let previous = parseInt(range.value, 10);
    let timer = null;
    let inflight = null;

    function paintTrack() {
        const pct = (parseInt(range.value, 10) / 50) * 100;
        range.style.setProperty('--crm-tol-pct', `${pct}%`);
    }

    function syncOutput() {
        const val = parseInt(range.value, 10);
        if (output) output.textContent = `${crmToPersianDigits(String(val))}٪`;
        range.setAttribute('aria-valuenow', String(val));
    }

    function showToast(message, isError = false) {
        if (!toast) return;
        toast.textContent = message;
        toast.hidden = false;
        toast.classList.toggle('is-error', isError);
        window.clearTimeout(showToast._t);
        showToast._t = window.setTimeout(() => { toast.hidden = true; }, 2600);
    }

    function updateToleranceBadges(val) {
        const pretty = `${crmToPersianDigits(String(val))}٪`;
        document.querySelectorAll('[data-crm-match-tolerance-badge]').forEach(el => {
            el.textContent = `· تلورانس ${pretty}`;
        });
        document.querySelectorAll('[data-crm-match-precision-value]').forEach(el => {
            el.textContent = pretty;
        });
        document.querySelectorAll('.crm-contact-pref-tolerance-range').forEach(el => {
            if (el === range) return;
            el.value = String(val);
            el.setAttribute('aria-valuenow', String(val));
            el.style.setProperty('--crm-tol-pct', `${(val / 50) * 100}%`);
        });
        document.querySelectorAll('.crm-contact-pref-tolerance-value').forEach(el => {
            el.textContent = pretty;
        });
    }

    paintTrack();
    syncOutput();

    if (range.disabled) return;

    async function persist(value) {
        if (inflight) inflight.abort();
        inflight = new AbortController();
        root.classList.add('is-saving');
        const matchesRoot = document.getElementById('crmMatches');
        if (matchesRoot) {
            matchesRoot.classList.add('is-refreshing');
            const loading = matchesRoot.querySelector('[data-matches-loading]');
            if (loading) loading.hidden = false;
        }
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({ matching_tolerance_percent: value }),
                signal: inflight.signal,
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'ذخیره انجام نشد');

            previous = value;
            updateToleranceBadges(value);

            const panel = document.getElementById('crmMatches');
            if (panel && data.matches_html) {
                panel.outerHTML = data.matches_html;
                initCRMMatches();
                initCRMMatchingTolerance();
            }

            const tabCount = document.querySelector('[data-crm-match-tab-count]');
            if (tabCount && data.match_tab_count != null) {
                tabCount.textContent = crmToPersianDigits(String(data.match_tab_count));
            }

            showToast('انعطاف‌پذیری ذخیره شد — پیشنهادها به‌روز شد.');
        } catch (err) {
            if (err.name === 'AbortError') return;
            range.value = String(previous);
            paintTrack();
            syncOutput();
            showToast(err.message || 'خطا در ذخیره', true);
            const panel = document.getElementById('crmMatches');
            if (panel) {
                panel.classList.remove('is-refreshing');
                const loading = panel.querySelector('[data-matches-loading]');
                if (loading) loading.hidden = true;
            }
        } finally {
            root.classList.remove('is-saving');
            inflight = null;
        }
    }

    function scheduleSave() {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => {
            const val = parseInt(range.value, 10);
            if (val === previous) return;
            persist(val);
        }, 350);
    }

    range.addEventListener('input', () => {
        syncOutput();
        paintTrack();
        scheduleSave();
    });

    range.addEventListener('change', () => {
        window.clearTimeout(timer);
        const val = parseInt(range.value, 10);
        if (val !== previous) persist(val);
    });
}

function initCRMMatches() {
    const panel = document.getElementById('crmMatches');
    if (!panel || panel.dataset.bound === '1') return;
    panel.dataset.bound = '1';

    const jsonInput = document.getElementById('crmMatchesJson');
    const countEl = document.getElementById('crmSuggestCount');
    const submitBtn = document.getElementById('crmSuggestSubmit');
    const dock = document.getElementById('crmSuggestDock');
    const filterEmpty = panel.querySelector('[data-match-filter-empty]');

    function flattenFeeds() {
        panel.querySelectorAll('[data-match-feed]').forEach(feed => {
            const cards = [...feed.querySelectorAll('[data-match-card], [data-match-locked]')];
            if (!cards.length) return;
            cards.sort((a, b) => (Number(b.dataset.score) || 0) - (Number(a.dataset.score) || 0));
            const list = document.createElement('ul');
            list.className = 'crm-match-list crm-match-list-v3 crm-match-feed-list';
            cards.forEach((card) => list.appendChild(card));
            feed.querySelectorAll('.crm-matches-col-v3').forEach((col) => col.remove());
            feed.appendChild(list);
        });
    }

    function visibleCards() {
        return [...panel.querySelectorAll('[data-match-card]')].filter((card) => !card.hidden);
    }

    function applySourceFilter(source) {
        panel.querySelectorAll('[data-match-card]').forEach((card) => {
            card.hidden = source !== 'all' && card.dataset.source !== source;
        });
        panel.querySelectorAll('[data-match-locked]').forEach((el) => {
            el.hidden = source === 'crm';
        });
        panel.querySelectorAll('[data-match-feed]').forEach((feed) => {
            feed.classList.toggle('is-source-all', source === 'all');
        });
        const anyVisible = visibleCards().length > 0
            || (source !== 'crm' && [...panel.querySelectorAll('[data-match-locked]')].some((el) => !el.hidden));
        if (filterEmpty) filterEmpty.hidden = anyVisible;
        panel.querySelectorAll('[data-match-filter]').forEach((btn) => {
            const on = btn.dataset.matchFilter === source;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-selected', on ? 'true' : 'false');
        });
    }

    function syncCardState() {
        panel.querySelectorAll('[data-match-card]').forEach(card => {
            const cb = card.querySelector('.crm-match-select');
            card.classList.toggle('is-selected', !!(cb && cb.checked));
        });
    }

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
        const items = [...panel.querySelectorAll('.crm-match-select:checked')].map(payloadFromCheckbox);
        if (jsonInput) jsonInput.value = JSON.stringify(items);
        if (countEl) countEl.textContent = typeof crmToPersianDigits === 'function'
            ? crmToPersianDigits(String(items.length))
            : String(items.length);
        if (submitBtn) submitBtn.disabled = items.length === 0;
        if (dock) {
            dock.hidden = items.length === 0;
            dock.classList.toggle('is-active', items.length > 0);
        }
        panel.classList.toggle('is-selecting', items.length > 0);
        syncCardState();
    }

    flattenFeeds();

    const crmCount = panel.querySelectorAll('[data-match-card][data-source="crm"]').length;
    const divarCount = panel.querySelectorAll('[data-match-card][data-source="divar"]').length;
    const allCount = crmCount + divarCount;
    const setCount = (filter, value) => {
        const el = panel.querySelector(`[data-match-filter="${filter}"] em`);
        if (el) el.textContent = typeof crmToPersianDigits === 'function' ? crmToPersianDigits(String(value)) : String(value);
    };
    setCount('all', allCount);
    setCount('crm', crmCount);
    setCount('divar', divarCount);

    applySourceFilter('all');

    panel.addEventListener('change', (ev) => {
        if (ev.target && ev.target.classList.contains('crm-match-select')) updateSelection();
    });

    panel.addEventListener('click', (ev) => {
        const filterBtn = ev.target.closest('[data-match-filter]');
        if (filterBtn) {
            applySourceFilter(filterBtn.dataset.matchFilter || 'all');
            return;
        }
        if (ev.target.closest('#crmClearMatchSelection')) {
            panel.querySelectorAll('.crm-match-select:checked').forEach((cb) => { cb.checked = false; });
            updateSelection();
        }
    });

    updateSelection();
}

function initCRMPropContactMatches() {
    const root = document.getElementById('crmPropContactMatches');
    if (!root) return;

    const form = document.getElementById('crmPropSuggestForm');
    const jsonInput = document.getElementById('crmPropMatchesJson');
    const countEl = document.getElementById('crmPropSuggestCount');
    const submitBtn = document.getElementById('crmPropSuggestSubmit');
    const dock = document.getElementById('crmPropSuggestDock');
    const rows = () => [...root.querySelectorAll('[data-prop-match-card]')];
    const selects = () => [...root.querySelectorAll('.crm-prop-match-select:checked')];

    function visibleBoxes() {
        return [...root.querySelectorAll('.crm-prop-match-select:not(:disabled)')]
            .filter((cb) => {
                const row = cb.closest('[data-prop-match-card]');
                return row && !row.hidden;
            });
    }

    function syncCardState() {
        rows().forEach((card) => {
            const cb = card.querySelector('.crm-prop-match-select');
            card.classList.toggle('is-selected', !!(cb && cb.checked));
        });
    }

    function payloadFromCheckbox(cb) {
        const d = cb.dataset;
        return {
            customer_id: parseInt(d.customerId, 10),
            name: d.name || '',
            phone: d.phone || '',
            customer_type: d.customerType || '',
        };
    }

    function updateSelection() {
        const items = selects().map(payloadFromCheckbox).filter(i => i.customer_id);
        if (jsonInput) jsonInput.value = JSON.stringify(items);
        if (countEl) countEl.textContent = items.length;
        if (submitBtn) submitBtn.disabled = items.length === 0;
        if (dock) dock.classList.toggle('is-active', items.length > 0);
        root.classList.toggle('is-selecting', items.length > 0);
        syncCardState();
    }

    root.querySelectorAll('.crm-prop-match-select').forEach((cb) => {
        cb.addEventListener('change', updateSelection);
    });

    const selectAll = document.getElementById('crmPropSelectAllMatches');
    if (selectAll) {
        selectAll.addEventListener('click', () => {
            const boxes = visibleBoxes();
            const allChecked = boxes.length > 0 && boxes.every(b => b.checked);
            boxes.forEach(b => { b.checked = !allChecked; });
            updateSelection();
        });
    }

    const chipHost = root.querySelector('[data-prop-match-type-chips]');
    if (chipHost) {
        const types = [...new Set(rows().map(r => (r.dataset.customerType || '').trim()).filter(Boolean))];
        if (types.length > 1) {
            chipHost.hidden = false;
            const emptyEl = root.querySelector('[data-prop-match-filter-empty]');
            const makeChip = (value, label) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'crm-pcm-chip' + (value === 'all' ? ' is-active' : '');
                btn.setAttribute('role', 'tab');
                btn.setAttribute('aria-selected', value === 'all' ? 'true' : 'false');
                btn.dataset.matchType = value;
                btn.textContent = label;
                return btn;
            };
            chipHost.replaceChildren(makeChip('all', 'همه'));
            types.forEach((t) => chipHost.appendChild(makeChip(t, t)));
            chipHost.addEventListener('click', (ev) => {
                const btn = ev.target.closest('[data-match-type]');
                if (!btn) return;
                const type = btn.dataset.matchType || 'all';
                chipHost.querySelectorAll('[data-match-type]').forEach((c) => {
                    const on = c === btn;
                    c.classList.toggle('is-active', on);
                    c.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                let shown = 0;
                rows().forEach((row) => {
                    const match = type === 'all' || row.dataset.customerType === type;
                    row.hidden = !match;
                    if (match) shown += 1;
                });
                if (emptyEl) emptyEl.hidden = shown > 0;
            });
        }
    }

    if (form) updateSelection();
}

function initCRMContactPortfolio() {
    const root = document.getElementById('crmContactPortfolio');
    if (!root) return;

    const customerId = root.dataset.customerId;
    const filters = root.querySelector('[data-portfolio-filters]');
    const emptyMsg = root.querySelector('[data-portfolio-empty]');
    const dock = document.getElementById('crmPortfolioShareDock');
    const countEl = document.getElementById('crmPortfolioShareCount');
    const copyBtn = document.getElementById('crmPortfolioCopy');
    const waBtn = document.getElementById('crmPortfolioWhatsApp');
    const logBtn = document.getElementById('crmPortfolioShareLog');
    const selectAllBtn = document.getElementById('crmPortfolioSelectAll');
    const cards = () => [...root.querySelectorAll('[data-portfolio-card]')];
    const selects = () => [...root.querySelectorAll('.crm-portfolio-select:checked')];

    function applyFilter(role) {
        const wanted = (role || 'all').trim();
        let visible = 0;
        cards().forEach(card => {
            const cardRole = (card.dataset.role || '').trim();
            const show = wanted === 'all' || cardRole === wanted;
            card.hidden = !show;
            if (show) visible += 1;
        });
        if (emptyMsg) emptyMsg.hidden = visible > 0;
    }

    function payloadFromCheckbox(cb) {
        const d = cb.dataset;
        const item = {
            source: d.source,
            title: d.title || '',
            price_label: d.priceLabel || '',
            neighborhood: d.neighborhood || '',
        };
        if (d.area) item.area = d.area;
        if (d.role) item.role = d.role;
        if (d.source === 'crm' && d.propertyId) item.property_id = parseInt(d.propertyId, 10);
        if (d.source === 'divar') {
            if (d.listingId) item.listing_id = parseInt(d.listingId, 10);
            if (d.token) item.token = d.token;
        }
        return item;
    }

    function syncSelectionUi() {
        const n = selects().length;
        if (countEl) countEl.textContent = n;
        if (dock) dock.classList.toggle('is-active', n > 0);
        [copyBtn, waBtn, logBtn].forEach(btn => {
            if (btn) btn.disabled = n === 0;
        });
        cards().forEach(card => {
            const cb = card.querySelector('.crm-portfolio-select');
            card.classList.toggle('is-selected', !!(cb && cb.checked));
        });
    }

    async function fetchShareText(logActivity) {
        const items = selects().map(payloadFromCheckbox);
        if (!items.length || !customerId) return null;
        const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const res = await fetch(`/workspace/crm/contacts/${customerId}/share-properties/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf,
            },
            body: JSON.stringify({ items, log: !!logActivity }),
        });
        const data = await res.json();
        if (!data.ok) {
            window.alert(data.error || 'خطا در ساخت متن اشتراک');
            return null;
        }
        return data;
    }

    filters?.querySelectorAll('.crm-portfolio-filter').forEach(btn => {
        btn.addEventListener('click', () => {
            filters.querySelectorAll('.crm-portfolio-filter').forEach(b => b.classList.remove('is-active'));
            btn.classList.add('is-active');
            applyFilter(btn.dataset.filter || 'all');
        });
    });

    root.querySelectorAll('.crm-portfolio-select').forEach(cb => {
        cb.addEventListener('change', syncSelectionUi);
    });

    selectAllBtn?.addEventListener('click', () => {
        const visibleBoxes = cards()
            .filter(card => !card.hidden)
            .map(card => card.querySelector('.crm-portfolio-select'))
            .filter(Boolean);
        const allChecked = visibleBoxes.length > 0 && visibleBoxes.every(b => b.checked);
        visibleBoxes.forEach(b => { b.checked = !allChecked; });
        syncSelectionUi();
    });

    copyBtn?.addEventListener('click', async () => {
        const data = await fetchShareText(false);
        if (!data?.text) return;
        await navigator.clipboard?.writeText(data.text);
    });

    waBtn?.addEventListener('click', async () => {
        const data = await fetchShareText(false);
        if (!data?.whatsapp_url) return;
        window.open(data.whatsapp_url, '_blank');
    });

    logBtn?.addEventListener('click', async () => {
        const data = await fetchShareText(true);
        if (!data?.text) return;
        if (data.whatsapp_url && window.confirm('پیشنهاد ثبت شد. واتساپ باز شود؟')) {
            window.open(data.whatsapp_url, '_blank');
        }
        window.location.reload();
    });

    root.querySelector('[data-portfolio-toast-close]')?.addEventListener('click', (e) => {
        e.target.closest('.crm-portfolio-toast')?.remove();
    });

    const params = new URLSearchParams(window.location.search);
    if (params.get('suggested') === '1') {
        const suggestedBtn = filters?.querySelector('[data-filter="پیشنهادی"]');
        if (suggestedBtn) {
            filters.querySelectorAll('.crm-portfolio-filter').forEach(b => b.classList.remove('is-active'));
            suggestedBtn.classList.add('is-active');
            applyFilter('پیشنهادی');
        }
    }

    syncSelectionUi();
}

function initCRMTabJump() {
    document.querySelectorAll('[data-tab-jump]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tabJump;
            const shell = btn.closest('.crm-detail-main') || document.querySelector('.crm-detail-main');
            const tabBtn = shell?.querySelector(`.crm-tab[data-tab="${tab}"]`);
            tabBtn?.click();
        });
    });
}

function scrollCRMTabIntoView(btn) {
    if (!btn || typeof btn.scrollIntoView !== 'function') return;
    try {
        btn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    } catch (e) {
        btn.scrollIntoView(false);
    }
}

function syncContactSegrailFades(rail) {
    if (!rail) return;
    const track = rail.querySelector('.crm-contact-tabs');
    if (!track) return;
    const max = Math.max(0, track.scrollWidth - track.clientWidth);
    const absX = Math.abs(track.scrollLeft || 0);
    const atStart = absX < 3;
    const atEnd = max <= 3 || absX >= max - 3;
    rail.classList.toggle('is-at-start', atStart);
    rail.classList.toggle('is-at-end', atEnd);
    rail.classList.toggle('is-scrollable', max > 3);
}

function initContactSegrail() {
    document.querySelectorAll('[data-contact-segrail]').forEach(rail => {
        const track = rail.querySelector('.crm-contact-tabs');
        if (!track) return;
        const update = () => syncContactSegrailFades(rail);
        track.addEventListener('scroll', update, { passive: true });
        window.addEventListener('resize', update, { passive: true });
        update();
        const active = track.querySelector('.crm-tab.active');
        if (active) scrollCRMTabIntoView(active);
    });
}

function syncPropSuggestLayout(tab) {
    const grid = document.querySelector('[data-prop-detail-grid]');
    if (!grid) return;
    grid.classList.toggle('is-suggest-contacts', tab === 'suggest-contacts');
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
            scrollCRMTabIntoView(btn);
            const rail = btn.closest('[data-contact-segrail], [data-prop-segrail]');
            if (rail && rail.hasAttribute('data-contact-segrail')) syncContactSegrailFades(rail);
            if (btn.closest('.crm-prop-tabs')) syncPropSuggestLayout(tab);
        });
    });

    const activePropTab = document.querySelector('.crm-prop-tabs .crm-tab.active');
    if (activePropTab) syncPropSuggestLayout(activePropTab.dataset.tab);

    document.querySelectorAll('.crm-form-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            const parent = btn.closest('.crm-form-sections');
            if (!parent) return;
            parent.querySelectorAll('.crm-form-tab').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            parent.querySelectorAll('[data-panel]').forEach(p => p.hidden = true);
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            const panel = parent.querySelector(`[data-panel="${tab}"]`);
            if (panel) panel.hidden = false;
        });
    });
}

function crmActivateFormTab(section, tabName) {
    section.querySelectorAll('.crm-form-tab').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
    });
    section.querySelectorAll('[data-panel]').forEach(p => { p.hidden = true; });
    const tabBtn = section.querySelector(`.crm-form-tab[data-tab="${tabName}"]`);
    const panel = section.querySelector(`[data-panel="${tabName}"]`);
    if (tabBtn) {
        tabBtn.classList.add('active');
        tabBtn.setAttribute('aria-selected', 'true');
    }
    if (panel) panel.hidden = false;
}

function parseAreasText(raw) {
    return (raw || '')
        .split(/[,،;\n|/]+/)
        .map(part => part.trim())
        .filter(Boolean);
}

function initCRMAreasPicker(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-crm-areas-picker]').forEach(picker => {
        if (picker.dataset.areasInit === '1') return;
        picker.dataset.areasInit = '1';

        const hidden = picker.querySelector('.crm-areas-hidden, input[type="hidden"][name]');
        const selectedWrap = picker.querySelector('[data-crm-areas-selected]');
        const countEl = picker.querySelector('[data-crm-areas-count]');
        const searchInput = picker.querySelector('[data-crm-areas-search]');
        const customInput = picker.querySelector('[data-crm-areas-custom-input]');
        const customAdd = picker.querySelector('[data-crm-areas-custom-add]');
        const catalog = picker.querySelector('[data-crm-areas-catalog]');
        if (!hidden || !selectedWrap) return;

        const catalogValues = new Set(
            Array.from(picker.querySelectorAll('[data-crm-areas-option]')).map(el => el.value.trim())
        );
        const selected = [];

        function hasArea(name) {
            const norm = name.trim();
            return selected.some(item => item === norm);
        }

        function syncHidden() {
            hidden.value = selected.join('، ');
            if (countEl) {
                countEl.textContent = selected.length
                    ? `${selected.length.toLocaleString('fa-IR')} محله`
                    : '۰ محله';
            }
        }

        function syncCheckboxes() {
            picker.querySelectorAll('[data-crm-areas-option]').forEach(cb => {
                cb.checked = hasArea(cb.value);
            });
        }

        function renderTags() {
            selectedWrap.innerHTML = '';
            if (!selected.length) {
                const empty = document.createElement('span');
                empty.className = 'crm-areas-selected-empty';
                empty.textContent = 'هنوز محله\u200cای انتخاب نشده';
                selectedWrap.appendChild(empty);
            } else {
                selected.forEach(name => {
                    const tag = document.createElement('span');
                    tag.className = 'crm-areas-tag' + (catalogValues.has(name) ? '' : ' crm-areas-tag--custom');
                    tag.dataset.areaName = name;

                    const label = document.createElement('span');
                    label.textContent = name;
                    tag.appendChild(label);

                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'crm-areas-tag-remove';
                    btn.setAttribute('aria-label', `حذف ${name}`);
                    btn.innerHTML = '&times;';
                    btn.addEventListener('click', () => {
                        const idx = selected.indexOf(name);
                        if (idx >= 0) selected.splice(idx, 1);
                        syncCheckboxes();
                        syncHidden();
                        renderTags();
                    });
                    tag.appendChild(btn);
                    selectedWrap.appendChild(tag);
                });
            }
            syncHidden();
        }

        function addArea(name) {
            const value = (name || '').trim();
            if (!value || hasArea(value)) return false;
            selected.push(value);
            syncCheckboxes();
            renderTags();
            return true;
        }

        function removeArea(name) {
            const idx = selected.indexOf(name);
            if (idx < 0) return;
            selected.splice(idx, 1);
            syncCheckboxes();
            renderTags();
        }

        parseAreasText(hidden.value).forEach(addArea);
        renderTags();

        picker.querySelectorAll('[data-crm-areas-option]').forEach(cb => {
            cb.addEventListener('change', () => {
                if (cb.checked) addArea(cb.value);
                else removeArea(cb.value);
            });
        });

        customAdd?.addEventListener('click', () => {
            if (addArea(customInput?.value || '')) {
                if (customInput) customInput.value = '';
            }
        });

        customInput?.addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                e.preventDefault();
                customAdd?.click();
            }
        });

        searchInput?.addEventListener('input', () => {
            const q = (searchInput.value || '').trim().toLowerCase();
            picker.querySelectorAll('[data-crm-areas-option-wrap]').forEach(row => {
                const text = row.textContent.trim().toLowerCase();
                row.classList.toggle('is-hidden', q && !text.includes(q));
            });
        });
    });
}

function initCRMContactChannels(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-crm-contact-channels]').forEach(block => {
        if (block.dataset.channelsInit === '1') return;
        block.dataset.channelsInit = '1';

        const form = block.closest('form');
        const editor = block.querySelector('[data-crm-channels-editor]');
        const summary = block.querySelector('[data-crm-channels-summary]');
        const panelNotes = block.closest('.crm-form-sections')?.querySelectorAll('[data-crm-panel-channels-note]') || [];
        const phoneInput = form?.querySelector('[name="phone"]');
        const openBtn = block.closest('.crm-form-sections')?.querySelector('[data-crm-channels-open]');

        function channelRows() {
            return block.querySelectorAll('.crm-channel-chip');
        }

        function fieldBlocks() {
            return block.querySelectorAll('[data-channel-field]');
        }

        function syncFieldVisibility() {
            fieldBlocks().forEach(row => {
                const key = row.dataset.channelField;
                const chip = block.querySelector(`.crm-channel-chip[data-channel-key="${key}"] input`);
                const active = chip?.checked;
                row.classList.toggle('is-active', !!active);
                row.classList.toggle('is-dormant', !active);
                const input = row.querySelector('.crm-contact-channel-input');
                if (input) input.disabled = !active;
            });
        }

        function phoneReady() {
            return !!(phoneInput?.value || '').replace(/\D/g, '').match(/^09\d{9}$/);
        }

        function updateReadiness() {
            channelRows().forEach(chip => {
                const input = chip.querySelector('.crm-channel-chip-input');
                const usesPhone = chip.dataset.usesPhone === '1';
                const handleInput = block.querySelector(`[name="contact_social_${chip.dataset.channelKey}"]`);
                const hasHandle = usesPhone ? phoneReady() : !!(handleInput?.value || '').trim();
                chip.classList.toggle('is-active', !!input?.checked);
                chip.classList.toggle('is-incomplete', !!input?.checked && !hasHandle);
            });
        }

        function buildSummary() {
            const active = [];
            const incomplete = [];
            channelRows().forEach(chip => {
                const cb = chip.querySelector('.crm-channel-chip-input');
                if (!cb?.checked) return;
                const label = chip.querySelector('.crm-channel-chip-label')?.textContent?.trim() || '';
                if (chip.classList.contains('is-incomplete')) incomplete.push(label);
                else active.push(label);
            });
            let text = '';
            if (active.length) text += 'فعال: ' + active.join('، ');
            if (incomplete.length) {
                text += (text ? ' — ' : '') + 'نیاز به تکمیل: ' + incomplete.join('، ');
            }
            if (!text) text = 'هیچ کانالی انتخاب نشده — شبکه‌های فعال مخاطب را مشخص کنید.';
            if (summary) summary.textContent = text;
            panelNotes.forEach(note => { note.textContent = text; });
        }

        function refresh() {
            syncFieldVisibility();
            updateReadiness();
            buildSummary();
        }

        channelRows().forEach(chip => {
            const cb = chip.querySelector('.crm-channel-chip-input');
            cb?.addEventListener('change', () => {
                refresh();
                if (cb.checked && editor?.hidden) {
                    editor.hidden = false;
                    const key = chip.dataset.channelKey;
                    const field = block.querySelector(`#crm-ch-handle-${key}`);
                    if (field && !field.disabled) field.focus();
                }
            });
        });

        block.querySelectorAll('.crm-contact-channel-input').forEach(inp => {
            inp.addEventListener('input', refresh);
        });
        phoneInput?.addEventListener('input', refresh);

        openBtn?.addEventListener('click', () => {
            if (!editor) return;
            editor.hidden = !editor.hidden;
            if (!editor.hidden) {
                crmActivateFormTab(block.closest('.crm-form-sections'), 'basic');
                const first = editor.querySelector('.crm-contact-channel-input:not(:disabled)');
                first?.focus();
            }
        });

        refresh();
    });
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

const CRM_IMPORT_ACCEPT_RE = /\.(xlsx|xls|csv)$/i;

function bindCRMImportDrawer(scope) {
    if (!scope || scope.dataset.crmImportBound === '1') return;

    const zone = scope.querySelector('[data-import-dropzone]');
    const input = scope.querySelector('[data-import-file]');
    const empty = scope.querySelector('[data-import-empty]');
    const preview = scope.querySelector('[data-import-preview]');
    const filenameEl = scope.querySelector('[data-import-filename]');
    const filesizeEl = scope.querySelector('[data-import-filesize]');
    const clearBtn = scope.querySelector('[data-import-clear]');
    const submitBtn = scope.querySelector('[data-import-submit]');
    const form = scope.querySelector('[data-crm-import-form]');

    if (!zone || !input) return;
    scope.dataset.crmImportBound = '1';

    function isImportFile(file) {
        return !!(file && CRM_IMPORT_ACCEPT_RE.test(file.name || ''));
    }

    function assignInputFile(file) {
        if (!file) return;
        if (input.files?.[0] === file) return;
        try {
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
        } catch (err) {
            /* native picker already set input.files */
        }
    }

    function setFile(file) {
        if (!file || !isImportFile(file)) {
            input.value = '';
            zone.classList.remove('has-file');
            empty?.removeAttribute('hidden');
            preview?.setAttribute('hidden', '');
            if (submitBtn) submitBtn.disabled = true;
            return;
        }
        assignInputFile(file);
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
            e.stopPropagation();
            zone.classList.add('is-dragover');
        });
    });
    ['dragleave', 'drop'].forEach((ev) => {
        zone.addEventListener(ev, (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('is-dragover');
        });
    });

    zone.addEventListener('drop', (e) => {
        const file = e.dataTransfer?.files?.[0];
        if (file) setFile(file);
    });

    input.addEventListener('change', () => {
        setFile(input.files?.[0] || null);
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

    setFile(input.files?.[0] || null);
}

function initCRMImportDrawer(root) {
    if (root) {
        bindCRMImportDrawer(root);
        return;
    }
    document.querySelectorAll('#drawer-import, #drawer-property-import').forEach(bindCRMImportDrawer);
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

    root.querySelectorAll('[data-copy-text]').forEach(btn => {
        btn.addEventListener('click', e => {
            copyText(btn.dataset.copyText || '', e.currentTarget);
        });
    });

    root.querySelectorAll('.crm-team-routing-cards').forEach(group => {
        const syncRoutingCards = () => {
            group.querySelectorAll('.crm-team-routing-card').forEach(card => {
                card.classList.toggle('is-selected', card.querySelector('input')?.checked);
            });
        };
        group.querySelectorAll('input[type="radio"]').forEach(input => {
            input.addEventListener('change', syncRoutingCards);
        });
        syncRoutingCards();
    });

    initCRMJalaliPickers(root);

    const goalForm = root.querySelector('.crm-team-goals-form');
    if (goalForm) {
        const startInput = goalForm.querySelector('input[name="period_start"]');
        const endInput = goalForm.querySelector('input[name="period_end"]');
        goalForm.querySelectorAll('[data-goal-preset]').forEach(btn => {
            btn.addEventListener('click', () => {
                const preset = btn.dataset.goalPreset;
                const startVal = preset === 'quarter'
                    ? goalForm.dataset.goalQuarterStart
                    : goalForm.dataset.goalMonthStart;
                const endVal = preset === 'quarter'
                    ? goalForm.dataset.goalQuarterEnd
                    : goalForm.dataset.goalMonthEnd;
                if (startInput && startVal) startInput.value = startVal;
                if (endInput && endVal) endInput.value = endVal;
            });
        });
    }

    document.getElementById('crm-api-key-copy')?.addEventListener('click', e => {
        copyText(window.__crmTeamApiKey || document.getElementById('crm-api-key')?.textContent?.trim(), e.currentTarget);
    });
    document.getElementById('crm-api-url-copy')?.addEventListener('click', e => {
        copyText(document.getElementById('crm-api-url')?.textContent?.trim(), e.currentTarget);
    });

    const keyEl = document.getElementById('crm-api-key');
    const keyToggle = document.getElementById('crm-api-key-toggle');
    const keyCopy = document.getElementById('crm-api-key-copy');
    const regenBtn = document.getElementById('crm-api-key-regen');
    const revealUrl = window.crmApiKeyRevealUrl;
    const regenUrl = window.crmApiKeyRegenerateUrl;

    const maskApiKey = () => {
        window.__crmTeamApiKey = '';
        if (keyEl) {
            keyEl.textContent = '••••••••••••••••';
            keyEl.classList.add('crm-team-api-key-v2--masked');
        }
        if (keyToggle) {
            keyToggle.setAttribute('aria-pressed', 'false');
            keyToggle.querySelector('i').className = 'fas fa-eye';
        }
        if (keyCopy) keyCopy.disabled = true;
    };

    const showApiKey = key => {
        window.__crmTeamApiKey = key;
        if (keyEl) {
            keyEl.textContent = key;
            keyEl.classList.remove('crm-team-api-key-v2--masked');
        }
        if (keyToggle) {
            keyToggle.setAttribute('aria-pressed', 'true');
            keyToggle.querySelector('i').className = 'fas fa-eye-slash';
        }
        if (keyCopy) keyCopy.disabled = false;
    };

    keyToggle?.addEventListener('click', async () => {
        if (keyToggle.getAttribute('aria-pressed') === 'true') {
            maskApiKey();
            return;
        }
        if (window.__crmTeamApiKey) {
            showApiKey(window.__crmTeamApiKey);
            return;
        }
        if (!revealUrl) return;
        try {
            const res = await fetch(revealUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            showApiKey(data.key);
        } catch (err) {
            window.alert(err.message || 'نمایش کلید انجام نشد.');
        }
    });

    regenBtn?.addEventListener('click', async () => {
        const msg = regenBtn.dataset.confirm;
        if (msg && !window.confirm(msg)) return;
        if (!regenUrl) return;
        regenBtn.disabled = true;
        try {
            const res = await fetch(regenUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'خطا');
            showApiKey(data.key);
            window.alert('کلید API بازتولید شد.');
        } catch (err) {
            window.alert(err.message || 'بازتولید کلید انجام نشد.');
        } finally {
            regenBtn.disabled = false;
        }
    });

    const runExport = async (scope = 'user') => {
        const btn = scope === 'agency'
            ? document.getElementById('crm-sync-export-agency-btn')
            : document.getElementById('crm-sync-export-btn');
        if (!btn || !window.crmSyncExportUrl) return;
        btn.disabled = true;
        const label = btn.querySelector('span');
        const prev = label?.textContent;
        if (label) label.textContent = 'در حال آماده‌سازی…';
        try {
            const url = scope === 'agency'
                ? `${window.crmSyncExportUrl}?scope=agency`
                : window.crmSyncExportUrl;
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `crm-export-${scope}-${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(a.href);
        } catch {
            window.alert('خروجی گرفته نشد.');
        } finally {
            btn.disabled = false;
            if (label && prev) label.textContent = prev;
        }
    };

    document.getElementById('crm-sync-export-btn')?.addEventListener('click', () => runExport('user'));
    document.getElementById('crm-sync-export-agency-btn')?.addEventListener('click', () => runExport('agency'));

    const importInput = document.getElementById('crm-sync-import-file');
    const dropzone = document.getElementById('crm-sync-dropzone');
    const importStatus = document.getElementById('crm-sync-import-status');

    const runImport = async (file, dryRun = false) => {
        if (!file || !window.crmSyncImportUrl) return;
        importStatus.hidden = false;
        importStatus.classList.remove('is-error', 'is-success');
        importStatus.textContent = dryRun ? 'در حال پیش‌نمایش…' : 'در حال بارگذاری…';
        try {
            const text = await file.text();
            const payload = JSON.parse(text);
            const url = dryRun ? `${window.crmSyncImportUrl}?dry_run=1` : window.crmSyncImportUrl;
            const res = await fetch(url, {
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
            const prefix = dryRun ? 'پیش‌نمایش' : 'انجام شد';
            importStatus.textContent = `${prefix} — مخاطب: ${s.contacts || 0} · ملک: ${s.properties || 0} · معامله: ${s.deals || 0} · ردشده: ${s.skipped || 0}${s.conflicts ? ` · تعارض: ${s.conflicts}` : ''}`;
        } catch (err) {
            importStatus.classList.add('is-error');
            importStatus.textContent = err.message || 'ورودی نامعتبر بود.';
        }
        if (importInput) importInput.value = '';
    };

    document.getElementById('crm-sync-dryrun-btn')?.addEventListener('click', () => {
        if (importInput?.files?.[0]) runImport(importInput.files[0], true);
        else importInput?.click();
    });

    function syncTeamInboxCheckMode() {
        const mobile = window.matchMedia('(max-width: 768px)').matches;
        document.querySelectorAll('.crm-team-inbox-cards input[name="customer_ids"]').forEach((cb) => {
            cb.disabled = !mobile;
            if (!mobile) cb.checked = false;
        });
        document.querySelectorAll('.crm-team-inbox-desk-check, .crm-team-inbox-table input[name="customer_ids"]').forEach((cb) => {
            cb.disabled = mobile;
            if (mobile) cb.checked = false;
        });
    }
    syncTeamInboxCheckMode();
    window.addEventListener('resize', syncTeamInboxCheckMode);

    function setTeamInboxAllChecked(checked) {
        const mobile = window.matchMedia('(max-width: 768px)').matches;
        const sel = mobile
            ? '.crm-team-inbox-cards input[name="customer_ids"]:not(:disabled)'
            : '.crm-team-inbox-table input[name="customer_ids"]:not(:disabled)';
        document.querySelectorAll(sel).forEach((cb) => {
            cb.checked = checked;
        });
    }
    document.getElementById('crm-inbox-select-all')?.addEventListener('change', (e) => {
        setTeamInboxAllChecked(e.target.checked);
    });
    document.getElementById('crm-inbox-select-all-mob')?.addEventListener('change', (e) => {
        setTeamInboxAllChecked(e.target.checked);
    });

    document.querySelectorAll('.crm-inbox-quick-assign').forEach(btn => {
        btn.addEventListener('click', () => {
            const form = document.getElementById('crm-team-inbox-quick-form');
            const memberSelect = document.querySelector('.crm-team-inbox-toolbar select[name="member_id"]');
            const quickMember = document.getElementById('crm-inbox-quick-member-id');
            const quickCustomer = document.getElementById('crm-inbox-quick-customer-id');
            if (!form || !quickCustomer) return;
            quickCustomer.value = btn.dataset.customerId || '';
            if (memberSelect && quickMember) quickMember.value = memberSelect.value;
            if (!quickMember?.value) {
                window.alert('ابتدا مشاور را از لیست بالا انتخاب کنید.');
                return;
            }
            if (!window.confirm('این سرنخ به مشاور انتخاب‌شده تخصیص داده شود؟')) return;
            form.submit();
        });
    });

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

function initCRMContactStatusPicker() {
    const picker = document.querySelector('[data-crm-status-picker]');
    if (!picker) return;
    const select = picker.querySelector('.crm-contact-hero__status-select');
    const url = picker.dataset.url || window.crmContactStatusUrl || '';
    if (!select || !url) return;

    let previous = select.value;
    select.addEventListener('change', async () => {
        const newStatus = select.value;
        select.classList.add('is-loading');
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
            previous = newStatus;
        } catch (err) {
            select.value = previous;
            window.alert(err.message || 'تغییر وضعیت انجام نشد.');
        } finally {
            select.classList.remove('is-loading');
        }
    });
}

function initCRMContactTeam() {
    const shareUrl = window.crmTeamShareUrl;
    const transferUrl = window.crmTeamTransferUrl;
    const revokeTpl = window.crmShareRevokeUrlTemplate || window.crmShareRevokeUrlBase;
    const groups = document.querySelectorAll('[data-crm-team-share]');
    if (!groups.length && !document.querySelector('[data-crm-contact-team]')) return;

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

    const bindGroup = (group) => {
        const select = group.querySelector('select');
        const shareBtn = group.querySelector('[data-crm-share]');
        const transferBtn = group.querySelector('[data-crm-transfer]');
        if (!select) return;

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
    };

    groups.forEach(bindGroup);

    document.querySelectorAll('[data-revoke-share]').forEach(btn => {
        if (btn.dataset.crmRevokeBound === '1') return;
        btn.dataset.crmRevokeBound = '1';
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
    const createMode = root.dataset.createMode === '1' || !uploadUrl;
    const maxImages = parseInt(root.dataset.maxImages || '12', 10);
    const hidden = root.querySelector('[data-crm-prop-images-json]');
    const grid = root.querySelector('[data-crm-prop-img-grid]');
    const fileInput = root.querySelector('[data-crm-prop-img-file]');
    const urlInput = root.querySelector('[data-crm-prop-img-url]');
    const urlBtn = root.querySelector('[data-crm-prop-img-url-btn]');
    const countEl = root.closest('#crm-prop-images-section')?.querySelector('[data-crm-prop-img-count]');
    const dataEl = document.getElementById('crm-prop-images-data');

    let images = [];
    let pendingPreviews = [];
    try {
        images = dataEl ? JSON.parse(dataEl.textContent) : [];
        if (!Array.isArray(images)) images = [];
    } catch {
        images = [];
    }

    function totalCount() {
        return images.length + pendingPreviews.length;
    }

    function syncHidden() {
        if (hidden) hidden.value = JSON.stringify(images);
        if (countEl) {
            const n = totalCount();
            countEl.textContent = n ? `${n} تصویر` : 'بدون تصویر';
        }
        syncHeroCover();
    }

    function syncHeroCover() {
        const coverLink = document.querySelector('[data-crm-prop-hero-cover]');
        const coverImg = coverLink?.querySelector('img');
        const emptyCover = document.querySelector('.crm-prop-hero-cover--empty');
        const coverSrc = images[0] || pendingPreviews[0] || '';
        if (coverSrc && coverImg) {
            coverImg.src = coverSrc;
            coverLink.style.display = '';
            emptyCover?.closest('.crm-prop-hero-visual')?.querySelector('.crm-prop-hero-cover--empty')?.remove();
        } else if (!coverSrc && coverImg) {
            coverImg.removeAttribute('src');
        }
    }

    function render() {
        if (!grid) return;
        grid.innerHTML = '';
        if (!totalCount()) {
            grid.innerHTML = '<div class="crm-prop-img-empty"><i class="fas fa-image"></i><span>هنوز تصویری اضافه نشده</span></div>';
            syncHidden();
            return;
        }
        images.forEach((url, idx) => {
            const item = document.createElement('div');
            item.className = `crm-prop-img-item${idx === 0 && !pendingPreviews.length ? ' is-cover' : ''}`;
            const img = document.createElement('img');
            img.src = url;
            img.alt = '';
            img.loading = 'lazy';
            const actions = document.createElement('div');
            actions.className = 'crm-prop-img-item-actions';
            if (idx === 0 && !pendingPreviews.length) {
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
        pendingPreviews.forEach((url) => {
            const item = document.createElement('div');
            item.className = 'crm-prop-img-item';
            const img = document.createElement('img');
            img.src = url;
            img.alt = '';
            item.appendChild(img);
            grid.appendChild(item);
        });
        syncHidden();
    }

    function refreshPendingFromInput() {
        pendingPreviews.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (_) { /* ignore */ }
        });
        pendingPreviews = Array.from(fileInput?.files || []).map((f) => URL.createObjectURL(f));
        render();
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
        if (totalCount() >= maxImages) {
            window.alert(`حداکثر ${maxImages} تصویر مجاز است.`);
            return;
        }
        images.push(url);
        render();
    }

    if (fileInput) {
        fileInput.addEventListener('change', async () => {
            if (createMode) {
                if (images.length + (fileInput.files?.length || 0) > maxImages) {
                    window.alert(`حداکثر ${maxImages} تصویر مجاز است.`);
                    fileInput.value = '';
                    refreshPendingFromInput();
                    return;
                }
                refreshPendingFromInput();
                return;
            }
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
            if (createMode && fileInput) {
                const dt = new DataTransfer();
                Array.from(fileInput.files || []).forEach((f) => dt.items.add(f));
                for (const file of files) {
                    if (dt.files.length + images.length >= maxImages) break;
                    dt.items.add(file);
                }
                fileInput.files = dt.files;
                refreshPendingFromInput();
                return;
            }
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

    // Desktop/table fallback — mobile cards use real <a> hit targets
    page.querySelectorAll('.crm-deals-row[data-href]').forEach(row => {
        if (row.dataset.hrefBound === '1') return;
        row.dataset.hrefBound = '1';
        row.addEventListener('click', e => {
            if (e.target.closest('a, button, input, select, textarea, label, summary')) return;
            const href = row.getAttribute('data-href');
            if (href) window.location.href = href;
        });
    });

    const search = page.querySelector('.crm-deals-search input[type="search"]');
    if (search && search.dataset.debounceBound !== '1') {
        search.dataset.debounceBound = '1';
        let timer;
        search.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => search.form?.submit(), 420);
        });
    }
    // Filter sheet uses native <details> on mobile.
    // Keep it open on desktop so selects stay in the form row.
    const details = document.getElementById('crmDealsFilterDetails');
    if (details) {
        const deskMq = window.matchMedia('(min-width: 769px)');
        const syncDetails = () => {
            if (deskMq.matches) details.setAttribute('open', '');
        };
        syncDetails();
        deskMq.addEventListener?.('change', syncDetails);
    }
}

function initCRMPropertyAdvFilters() {
    const toggle = document.getElementById('crmPropAdvToggle');
    const toggleMob = document.getElementById('crmPropAdvToggleMob');
    const panel = document.getElementById('crmPropAdvPanel');
    if (panel && panel.dataset.advBound !== '1') {
        panel.dataset.advBound = '1';
        const setOpen = (open) => {
            [toggle, toggleMob].forEach((btn) => {
                if (!btn) return;
                btn.classList.toggle('is-open', open);
                btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            panel.classList.toggle('is-open', open);
            if (open) panel.removeAttribute('hidden');
            else panel.setAttribute('hidden', '');
        };
        [toggle, toggleMob].forEach((btn) => {
            btn?.addEventListener('click', () => {
                setOpen(!panel.classList.contains('is-open'));
            });
        });
    }

    const form = document.getElementById('crmPropertyFilters');
    const sheetToggle = document.getElementById('crmFilesFilterToggle');
    const sheet = document.getElementById('crmFilesFilterSheet');
    if (form && sheetToggle && sheet && sheetToggle.dataset.bound !== '1') {
        sheetToggle.dataset.bound = '1';
        const mq = window.matchMedia('(max-width: 768px)');
        const setSheet = (open) => {
            if (!mq.matches) {
                sheet.classList.remove('is-open');
                sheet.setAttribute('aria-hidden', 'true');
                sheetToggle.setAttribute('aria-expanded', 'false');
                sheetToggle.classList.remove('is-open');
                document.body.classList.remove('crm-files-filter-open');
                return;
            }
            sheet.classList.toggle('is-open', open);
            sheetToggle.classList.toggle('is-open', open);
            sheetToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            sheet.setAttribute('aria-hidden', open ? 'false' : 'true');
            document.body.classList.toggle('crm-files-filter-open', open);
        };
        sheetToggle.addEventListener('click', () => {
            if (!mq.matches) return;
            setSheet(!sheet.classList.contains('is-open'));
        });
        sheet.querySelectorAll('[data-files-filter-close]').forEach((el) => {
            el.addEventListener('click', () => setSheet(false));
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && sheet.classList.contains('is-open')) {
                e.preventDefault();
                e.stopImmediatePropagation();
                setSheet(false);
            }
        }, true);
        form.addEventListener('submit', () => {
            if (mq.matches) setSheet(false);
        });
        const syncSelectDisabled = () => {
            const mobile = mq.matches;
            form.querySelectorAll('.crm-files-desk-select').forEach((sel) => {
                sel.disabled = mobile;
            });
            form.querySelectorAll('.crm-files-mob-select').forEach((sel) => {
                sel.disabled = !mobile;
            });
            const sheetBody = sheet.querySelector('.crm-files-mob-filter-body');
            if (panel && sheetBody) {
                if (mobile) sheetBody.appendChild(panel);
                else form.appendChild(panel);
            }
            if (!mobile) setSheet(false);
        };
        if (typeof mq.addEventListener === 'function') mq.addEventListener('change', syncSelectDisabled);
        else if (typeof mq.addListener === 'function') mq.addListener(syncSelectDisabled);
        syncSelectDisabled();
    }

    const menuRoot = document.querySelector('.crm-files-mobile');
    if (menuRoot && menuRoot.dataset.filesMenuBound !== '1') {
        menuRoot.dataset.filesMenuBound = '1';
        menuRoot.addEventListener('toggle', (e) => {
            const opened = e.target;
            if (!opened.matches('.crm-files-mob-toolbar-menu')) return;
            if (!opened.open) return;
            menuRoot.querySelectorAll('.crm-files-mob-toolbar-menu[open]').forEach((menu) => {
                if (menu !== opened) menu.removeAttribute('open');
            });
        }, true);
    }

    document.querySelectorAll('.crm-files-mobile .crm-ft-row[data-href]').forEach((row) => {
        if (row.dataset.hrefBound === '1') return;
        row.dataset.hrefBound = '1';
        row.addEventListener('click', (e) => {
            if (e.target.closest('a, button, input, select, label')) return;
            const href = row.getAttribute('data-href');
            if (href) window.location.href = href;
        });
    });
}

function initCRMPropGalleryLightbox() {
    document.querySelectorAll('[data-crm-prop-open-gallery]').forEach(btn => {
        if (btn.dataset.crmGalleryBound === '1') return;
        btn.dataset.crmGalleryBound = '1';
        btn.addEventListener('click', () => {
            const root = document.querySelector('.crm-prop-hero-gallery-wrap[data-ws-gallery]');
            const first = root?.querySelector('[data-ws-lightbox]');
            if (first) first.click();
        });
    });

    const gallery = document.querySelector('.crm-prop-hero-gallery');
    if (!gallery) return;
    gallery.querySelectorAll('[data-ws-lightbox]').forEach(btn => {
        btn.addEventListener('click', () => {
            gallery.querySelectorAll('.crm-prop-gallery-item').forEach(el => el.classList.remove('is-active'));
            btn.classList.add('is-active');
            const coverImg = document.querySelector('[data-crm-prop-hero-cover] img');
            const src = btn.getAttribute('data-ws-lightbox');
            if (coverImg && src) coverImg.src = src;
        });
    });
}


function initContactsMobileFilters() {
    const form = document.getElementById('crmContactFilters');
    const sheet = document.getElementById('crmContactsFilterSheet');
    const openBtn = document.getElementById('crmContactsFilterOpen');
    if (!form || !sheet || !openBtn) return;

    const mq = window.matchMedia('(max-width: 768px)');

    const setOpen = (open) => {
        sheet.classList.toggle('is-open', open);
        sheet.setAttribute('aria-hidden', open ? 'false' : 'true');
        openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        openBtn.classList.toggle('is-open', open);
        document.body.classList.toggle('crm-contacts-filter-open', open);
    };

    const close = () => setOpen(false);
    const open = () => {
        if (!mq.matches) return;
        setOpen(true);
    };

    openBtn.addEventListener('click', () => {
        if (sheet.classList.contains('is-open')) close();
        else open();
    });

    sheet.querySelectorAll('[data-contacts-filter-close]').forEach(el => {
        el.addEventListener('click', close);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sheet.classList.contains('is-open')) {
            e.preventDefault();
            e.stopImmediatePropagation();
            close();
        }
    }, true);

    form.addEventListener('submit', () => {
        if (mq.matches) close();
    });

    form.querySelectorAll('.crm-contacts-desk-filter-fields select').forEach(sel => {
        sel.disabled = mq.matches;
    });
    form.querySelectorAll('.crm-contacts-mob-select').forEach(sel => {
        sel.disabled = !mq.matches;
    });

    const syncSelectDisabled = () => {
        const mobile = mq.matches;
        form.querySelectorAll('.crm-contacts-desk-filter-fields select').forEach(sel => {
            sel.disabled = mobile;
        });
        form.querySelectorAll('.crm-contacts-mob-select').forEach(sel => {
            sel.disabled = !mobile;
        });
        if (!mobile) close();
    };

    if (typeof mq.addEventListener === 'function') mq.addEventListener('change', syncSelectDisabled);
    else if (typeof mq.addListener === 'function') mq.addListener(syncSelectDisabled);
    syncSelectDisabled();
}

function initContactsMobileMenus() {
    const root = document.querySelector('.crm-contacts-mobile');
    if (!root) return;

    const closeMenus = (except) => {
        root.querySelectorAll('.crm-contacts-mob-toolbar-menu[open], .crm-contacts-mob-row-more[open]').forEach(menu => {
            if (menu !== except) menu.removeAttribute('open');
        });
    };

    root.querySelectorAll('.crm-contacts-mob-row-more-trigger, .crm-contacts-mob-row-more-panel').forEach(el => {
        el.addEventListener('click', (e) => e.stopPropagation());
    });

    root.querySelectorAll('.crm-contacts-mob-toolbar-menu, .crm-contacts-mob-row-more').forEach(menu => {
        menu.addEventListener('toggle', () => {
            if (menu.open) closeMenus(menu);
        });
    });

    root.querySelectorAll('.crm-contacts-mob-row-more-item').forEach(link => {
        link.addEventListener('click', () => {
            link.closest('.crm-contacts-mob-row-more')?.removeAttribute('open');
        });
    });

    root.querySelectorAll('.crm-contacts-mob-toolbar-item[data-drawer-open]').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.crm-contacts-mob-toolbar-menu')?.removeAttribute('open');
        });
    });

    document.addEventListener('click', (e) => {
        if (!root.contains(e.target)) return;
        root.querySelectorAll('.crm-contacts-mob-toolbar-menu[open], .crm-contacts-mob-row-more[open]').forEach(menu => {
            if (!menu.contains(e.target)) menu.removeAttribute('open');
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        closeMenus();
    });
}

function initContactAsideFolds() {
    const root = document.querySelector('.crm-contact-detail-pro');
    if (!root) return;
    const folds = root.querySelectorAll('.crm-contact-side-fold');
    if (!folds.length) return;

    const apply = () => {
        folds.forEach(fold => {
            const keepOpen = fold.classList.contains('crm-contact-side-card--followup')
                || fold.classList.contains('crm-contact-side-card--deals')
                || fold.classList.contains('crm-contact-side-card--warn');
            fold.open = keepOpen;
        });
    };

    apply();
    window.matchMedia('(max-width: 768px)').addEventListener('change', apply);

    root.querySelectorAll('.crm-contact-side-fold .crm-contact-prefs-edit').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
        });
    });
}

function initContactHeroMorePanel() {
    document.querySelectorAll('.crm-contact-hero__more').forEach(details => {
        const panel = details.querySelector('.crm-contact-hero__more-panel');
        const trigger = details.querySelector('summary');
        if (!panel || !trigger || panel.dataset.crmMorePortaled === '1') return;
        panel.dataset.crmMorePortaled = '1';
        const holder = document.createComment('crm-hero-more-panel');

        const place = () => {
            const r = trigger.getBoundingClientRect();
            const pad = 8;
            const vw = document.documentElement.clientWidth;
            const vh = document.documentElement.clientHeight;
            panel.style.position = 'fixed';
            panel.style.zIndex = '20000';
            panel.style.inset = 'auto';
            panel.style.maxWidth = `${Math.max(180, vw - pad * 2)}px`;
            const pw = Math.max(panel.offsetWidth, 220);
            const ph = panel.offsetHeight;
            let left = r.right - pw;
            if (left < pad) left = r.left;
            if (left + pw > vw - pad) left = vw - pw - pad;
            if (left < pad) left = pad;
            let top = r.bottom + 6;
            if (ph && top + ph > vh - pad) {
                top = Math.max(pad, r.top - ph - 6);
            }
            panel.style.top = `${Math.round(top)}px`;
            panel.style.left = `${Math.round(left)}px`;
            panel.style.right = 'auto';
        };

        details.addEventListener('toggle', () => {
            if (details.open) {
                if (!holder.isConnected) details.appendChild(holder);
                document.body.appendChild(panel);
                place();
                requestAnimationFrame(place);
                window.addEventListener('scroll', place, true);
                window.addEventListener('resize', place);
            } else if (holder.parentNode) {
                window.removeEventListener('scroll', place, true);
                window.removeEventListener('resize', place);
                holder.parentNode.insertBefore(panel, holder);
                panel.removeAttribute('style');
            }
        });

        panel.addEventListener('click', (e) => {
            if (e.target.closest('[data-drawer-open]')) details.removeAttribute('open');
        });
    });
}

function initContactDetailMobileMenus() {
    const root = document.querySelector('.crm-contact-detail-pro');
    if (!root) return;

    const closeMenus = (except) => {
        root.querySelectorAll('.crm-contact-mob-menu[open], .crm-contact-dock-more[open], .crm-contact-hero__more[open]').forEach(menu => {
            if (menu !== except) menu.removeAttribute('open');
        });
    };

    root.querySelectorAll('.crm-contact-mob-menu, .crm-contact-dock-more, .crm-contact-hero__more').forEach(menu => {
        menu.addEventListener('toggle', () => {
            if (menu.open) closeMenus(menu);
        });
    });

    root.querySelectorAll('.crm-contact-mob-menu-item[data-drawer-open], .crm-contact-dock-more-item[data-drawer-open]').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('details')?.removeAttribute('open');
        });
    });

    root.querySelectorAll('.crm-contact-dock-more-item').forEach(link => {
        link.addEventListener('click', () => {
            if (link.getAttribute('href')) {
                link.closest('.crm-contact-dock-more')?.removeAttribute('open');
            }
        });
    });

    document.addEventListener('click', (e) => {
        const onHeroMorePanel = e.target.closest('.crm-contact-hero__more-panel');
        if (onHeroMorePanel) return;
        root.querySelectorAll('.crm-contact-mob-menu[open], .crm-contact-dock-more[open], .crm-contact-hero__more[open]').forEach(menu => {
            if (!menu.contains(e.target)) menu.removeAttribute('open');
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        closeMenus();
    });
}

function crmDrawerIdFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const openModal = (params.get('open') || '').trim();
    if (openModal.startsWith('drawer-')) return openModal;
    const drawer = (params.get('drawer') || '').trim();
    if (!drawer) return '';
    return drawer.startsWith('drawer-') ? drawer : `drawer-${drawer}`;
}

function initCRMPropertyFolders(root) {
    const scope = root || document;
    const section = scope.querySelector('[data-crm-zonkan]');
    if (!section || section.dataset.zonkanBound === '1') return;
    section.dataset.zonkanBound = '1';

    const modal = scope.querySelector('[data-zonkan-modal]');
    if (!modal) return;

    const manageModal = scope.querySelector('[data-zonkan-manage-modal]');
    const popMenu = scope.querySelector('[data-zonkan-pop]');
    const form = modal.querySelector('[data-zonkan-form]');
    const titleEl = modal.querySelector('[data-zonkan-modal-title]');
    const editIdInput = modal.querySelector('[data-zonkan-edit-id]');
    const nameInput = modal.querySelector('[data-zonkan-name]');
    const descInput = modal.querySelector('[data-zonkan-desc]');
    const pinInput = modal.querySelector('[data-zonkan-pin]');
    const deleteBtn = modal.querySelector('[data-zonkan-delete]');
    const baseUrl = window.crmZonkanUrl || '/workspace/crm/property-folders/';
    const detailBase = window.crmZonkanDetailUrlBase || `${baseUrl}`;
    const reorderUrl = window.crmZonkanReorderUrl || `${baseUrl}reorder/`;

    let selectedColor = modal.querySelector('[data-zonkan-color].is-active')?.getAttribute('data-zonkan-color') || '#6366f1';
    let selectedIcon = modal.querySelector('[data-zonkan-icon].is-active')?.getAttribute('data-zonkan-icon') || 'fa-folder';
    let popFolderId = null;

    function folderDetailUrl(id) {
        return `${detailBase}${id}/`;
    }

    function closeModal() {
        if (typeof modal.close === 'function') modal.close();
    }

    function closeManageModal() {
        if (manageModal && typeof manageModal.close === 'function') manageModal.close();
    }

    function hidePop() {
        if (!popMenu) return;
        popMenu.hidden = true;
        popFolderId = null;
    }

    function setModalSelections(color, icon) {
        selectedColor = color || selectedColor;
        selectedIcon = icon || selectedIcon;
        modal.querySelectorAll('[data-zonkan-color]').forEach((el) => {
            el.classList.toggle('is-active', el.getAttribute('data-zonkan-color') === selectedColor);
        });
        modal.querySelectorAll('[data-zonkan-icon]').forEach((el) => {
            el.classList.toggle('is-active', el.getAttribute('data-zonkan-icon') === selectedIcon);
        });
    }

    function openCreateModal() {
        if (editIdInput) editIdInput.value = '';
        if (titleEl) titleEl.textContent = 'زونکن جدید';
        if (nameInput) nameInput.value = '';
        if (descInput) descInput.value = '';
        if (pinInput) pinInput.checked = false;
        if (deleteBtn) deleteBtn.hidden = true;
        setModalSelections('#6366f1', 'fa-folder');
        if (typeof modal.showModal === 'function') modal.showModal();
    }

    function openEditModal(folderId) {
        const item = manageModal?.querySelector(`[data-folder-id="${folderId}"]`)
            || section.querySelector(`[data-zonkan-wrap="${folderId}"]`);
        const dataItem = manageModal?.querySelector(`[data-folder-id="${folderId}"]`);
        const source = dataItem || null;
        const wrap = section.querySelector(`[data-zonkan-id="${folderId}"]`);
        const name = source?.getAttribute('data-folder-name')
            || wrap?.querySelector('strong')?.textContent?.trim()
            || '';
        const desc = source?.getAttribute('data-folder-desc') || '';
        const color = source?.getAttribute('data-folder-color')
            || wrap?.style.getPropertyValue('--zonkan-color')?.trim()
            || '#6366f1';
        const icon = source?.getAttribute('data-folder-icon') || 'fa-folder';
        const pinned = source?.getAttribute('data-folder-pinned') === '1'
            || wrap?.classList.contains('is-pinned');

        if (editIdInput) editIdInput.value = String(folderId);
        if (titleEl) titleEl.textContent = 'ویرایش زونکن';
        if (nameInput) nameInput.value = name;
        if (descInput) descInput.value = desc;
        if (pinInput) pinInput.checked = !!pinned;
        if (deleteBtn) deleteBtn.hidden = false;
        setModalSelections(color, icon);
        closeManageModal();
        hidePop();
        if (typeof modal.showModal === 'function') modal.showModal();
    }

    async function patchFolder(folderId, payload) {
        const resp = await fetch(folderDetailUrl(folderId), {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error || 'عملیات ناموفق بود');
        return data;
    }

    async function deleteFolder(folderId) {
        const label = manageModal?.querySelector(`[data-folder-id="${folderId}"] strong`)?.textContent?.trim()
            || 'این زونکن';
        if (!window.confirm(`«${label}» حذف شود؟ فایل‌های داخل آن حذف نمی‌شوند.`)) return false;
        const resp = await fetch(folderDetailUrl(folderId), {
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCsrfToken() },
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error || 'حذف ناموفق بود');
        const params = new URLSearchParams(window.location.search);
        if (params.get('folder_id') === String(folderId)) params.delete('folder_id');
        const qs = params.toString();
        window.location.href = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
        return true;
    }

    async function togglePin(folderId) {
        const item = manageModal?.querySelector(`[data-folder-id="${folderId}"]`);
        const nextPinned = item ? !item.classList.contains('is-pinned') : true;
        await patchFolder(folderId, { is_pinned: nextPinned });
        window.location.reload();
    }

    modal.querySelectorAll('[data-zonkan-close]').forEach((btn) => {
        btn.addEventListener('click', closeModal);
    });
    modal.querySelectorAll('[data-zonkan-color]').forEach((btn) => {
        btn.addEventListener('click', () => {
            modal.querySelectorAll('[data-zonkan-color]').forEach((el) => el.classList.remove('is-active'));
            btn.classList.add('is-active');
            selectedColor = btn.getAttribute('data-zonkan-color') || selectedColor;
        });
    });
    modal.querySelectorAll('[data-zonkan-icon]').forEach((btn) => {
        btn.addEventListener('click', () => {
            modal.querySelectorAll('[data-zonkan-icon]').forEach((el) => el.classList.remove('is-active'));
            btn.classList.add('is-active');
            selectedIcon = btn.getAttribute('data-zonkan-icon') || selectedIcon;
        });
    });
    section.querySelectorAll('[data-zonkan-create]').forEach((btn) => {
        btn.addEventListener('click', openCreateModal);
    });
    deleteBtn?.addEventListener('click', async () => {
        const folderId = editIdInput ? editIdInput.value : '';
        if (!folderId) return;
        try {
            await deleteFolder(folderId);
        } catch (err) {
            window.alert(err.message || 'خطا در حذف زونکن');
        }
    });
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = nameInput ? String(nameInput.value || '').trim() : '';
        if (!name) return;
        const editId = editIdInput ? String(editIdInput.value || '').trim() : '';
        const payload = {
            name,
            description: descInput ? descInput.value : '',
            color: selectedColor,
            icon: selectedIcon,
            is_pinned: pinInput ? !!pinInput.checked : false,
        };
        try {
            const resp = await fetch(editId ? folderDetailUrl(editId) : baseUrl, {
                method: editId ? 'PATCH' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();
            if (!data.ok) {
                window.alert(data.error || 'ذخیره زونکن ناموفق بود');
                return;
            }
            if (!editId && data.folder?.id) {
                const params = new URLSearchParams(window.location.search);
                params.set('folder_id', String(data.folder.id));
                window.location.href = `${window.location.pathname}?${params.toString()}`;
                return;
            }
            window.location.reload();
        } catch (_err) {
            window.alert('خطا در ذخیره زونکن');
        }
    });

    manageModal?.querySelectorAll('[data-zonkan-manage-close]').forEach((btn) => {
        btn.addEventListener('click', closeManageModal);
    });
    section.querySelectorAll('[data-zonkan-manage-open]').forEach((btn) => {
        btn.addEventListener('click', () => {
            if (typeof manageModal.showModal === 'function') manageModal.showModal();
        });
    });

    const manageList = manageModal?.querySelector('[data-zonkan-manage-list]');
    let dragEl = null;
    manageList?.querySelectorAll('[data-zonkan-manage-item]').forEach((item) => {
        item.addEventListener('dragstart', () => {
            dragEl = item;
            item.classList.add('is-dragging');
        });
        item.addEventListener('dragend', () => {
            dragEl = null;
            item.classList.remove('is-dragging');
        });
        item.addEventListener('dragover', (e) => e.preventDefault());
        item.addEventListener('drop', (e) => {
            e.preventDefault();
            if (!dragEl || dragEl === item) return;
            const rect = item.getBoundingClientRect();
            const after = e.clientY > rect.top + rect.height / 2;
            if (after) item.after(dragEl);
            else item.before(dragEl);
        });
    });
    manageModal?.querySelector('[data-zonkan-reorder-save]')?.addEventListener('click', async () => {
        const btn = manageModal.querySelector('[data-zonkan-reorder-save]');
        const ids = [...manageList.querySelectorAll('[data-zonkan-manage-item]')].map(
            (el) => Number(el.getAttribute('data-folder-id')),
        );
        btn.disabled = true;
        try {
            const resp = await fetch(reorderUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({ folder_ids: ids }),
            });
            const data = await resp.json();
            if (!data.ok) throw new Error(data.error || 'ذخیره ترتیب ناموفق بود');
            window.location.reload();
        } catch (err) {
            window.alert(err.message || 'خطا در ذخیره ترتیب');
        } finally {
            btn.disabled = false;
        }
    });
    manageModal?.querySelectorAll('[data-zonkan-manage-pin]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const folderId = btn.getAttribute('data-zonkan-manage-pin');
            try {
                await togglePin(folderId);
            } catch (err) {
                window.alert(err.message || 'خطا در سنجاق');
            }
        });
    });
    manageModal?.querySelectorAll('[data-zonkan-manage-edit]').forEach((btn) => {
        btn.addEventListener('click', () => {
            openEditModal(btn.getAttribute('data-zonkan-manage-edit'));
        });
    });
    manageModal?.querySelectorAll('[data-zonkan-manage-delete]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            try {
                await deleteFolder(btn.getAttribute('data-zonkan-manage-delete'));
            } catch (err) {
                window.alert(err.message || 'خطا در حذف');
            }
        });
    });

    section.querySelectorAll('[data-zonkan-card-menu]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!popMenu) return;
            popFolderId = btn.getAttribute('data-zonkan-card-menu');
            const rect = btn.getBoundingClientRect();
            popMenu.style.top = `${rect.bottom + 6}px`;
            popMenu.style.left = `${Math.max(8, rect.left - 120)}px`;
            popMenu.hidden = false;
        });
    });
    popMenu?.querySelector('[data-zonkan-pop-pin]')?.addEventListener('click', async () => {
        if (!popFolderId) return;
        try {
            await togglePin(popFolderId);
        } catch (err) {
            window.alert(err.message || 'خطا');
        }
    });
    popMenu?.querySelector('[data-zonkan-pop-edit]')?.addEventListener('click', () => {
        if (popFolderId) openEditModal(popFolderId);
    });
    popMenu?.querySelector('[data-zonkan-pop-delete]')?.addEventListener('click', async () => {
        if (!popFolderId) return;
        try {
            await deleteFolder(popFolderId);
        } catch (err) {
            window.alert(err.message || 'خطا');
        }
    });
    document.addEventListener('click', (e) => {
        if (!popMenu || popMenu.hidden) return;
        if (e.target.closest('[data-zonkan-pop]') || e.target.closest('[data-zonkan-card-menu]')) return;
        hidePop();
    });
}

function initCRMPropertyFolderPicker(root) {
    const scope = root || document;
    const membershipBase = window.crmZonkanMembershipUrl || '/workspace/crm/property-folders/';
    scope.querySelectorAll('[data-zonkan-picker]').forEach((picker) => {
        if (picker.dataset.zonkanPickerBound === '1') return;
        picker.dataset.zonkanPickerBound = '1';
        const propertyId = picker.getAttribute('data-property-id');
        picker.querySelectorAll('[data-zonkan-toggle]').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const folderId = btn.getAttribute('data-zonkan-toggle');
                const isOn = btn.classList.contains('is-on');
                const url = `${membershipBase}${folderId}/properties/${propertyId}/`;
                try {
                    const resp = await fetch(url, {
                        method: isOn ? 'DELETE' : 'POST',
                        headers: { 'X-CSRFToken': getCsrfToken() },
                    });
                    const data = await resp.json();
                    if (!data.ok) {
                        window.alert(data.error || 'عملیات ناموفق بود');
                        return;
                    }
                    btn.classList.toggle('is-on', !isOn);
                    btn.setAttribute('aria-pressed', isOn ? 'false' : 'true');
                    const meta = btn.querySelector('.crm-zonkan-picker__card-meta');
                    if (meta) meta.textContent = isOn ? 'افزودن به مجموعه' : 'عضو این مجموعه';
                } catch (_err) {
                    window.alert('خطا در به‌روزرسانی زونکن');
                }
            });
        });
    });
}

function crmPropFolderIdsFromEl(el) {
    const raw = el?.getAttribute('data-prop-folder-ids') || '';
    return raw.split(',').map((s) => s.trim()).filter(Boolean);
}

function crmPropFolderMembershipUrl(folderId, propertyId) {
    const base = window.crmZonkanMembershipUrl || '/workspace/crm/property-folders/';
    return `${base}${folderId}/properties/${propertyId}/`;
}

function crmPropFolderBulkUrl(folderId) {
    const base = window.crmZonkanBulkUrl || '/workspace/crm/property-folders/';
    return `${base}${folderId}/properties/bulk/`;
}

function initCRMPropertyFolderAssign(root) {
    const scope = root || document;
    const modal = scope.querySelector('[data-zonkan-assign-modal]');
    if (!modal || modal.dataset.zonkanAssignBound === '1') return;
    modal.dataset.zonkanAssignBound = '1';

    const titleEl = modal.querySelector('[data-zonkan-assign-title]');
    const subEl = modal.querySelector('[data-zonkan-assign-sub]');
    const listEl = modal.querySelector('[data-zonkan-assign-list]');
    const bulkBar = scope.getElementById('crmPropFolderBulk');
    const bulkCount = scope.getElementById('crmPropFolderBulkCount');
    const bulkClear = scope.getElementById('crmPropFolderBulkClear');
    const bulkOpen = scope.getElementById('crmPropFolderBulkOpen');
    const selectModeBtn = scope.getElementById('crmPropSelectMode');
    const checks = () => [...scope.querySelectorAll('.crm-prop-row-check')];

    let assignMode = 'single';
    let assignPropertyIds = [];

    function selectedIds() {
        return checks().filter((c) => c.checked).map((c) => c.value);
    }

    function updateBulkBar() {
        const n = selectedIds().length;
        if (bulkBar) {
            bulkBar.hidden = n === 0;
            bulkBar.classList.toggle('is-visible', n > 0);
        }
        if (bulkCount) bulkCount.textContent = n;
    }

    function setSelectMode(on) {
        scope.querySelectorAll('.crm-files-pro-v2, .crm-files-pro').forEach((page) => {
            page.classList.toggle('crm-files-pro--select-mode', on);
        });
        if (selectModeBtn) {
            selectModeBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
            selectModeBtn.classList.toggle('is-active', on);
        }
        if (!on) {
            checks().forEach((c) => { c.checked = false; });
            updateBulkBar();
        }
    }

    function syncAssignTicks() {
        if (!listEl) return;
        const idSet = new Set(assignPropertyIds.map(String));
        const isBulk = assignMode === 'bulk';
        listEl.querySelectorAll('[data-zonkan-assign-folder]').forEach((btn) => {
            btn.classList.remove('is-on', 'is-partial');
            if (isBulk || idSet.size !== 1) return;
            const folderId = btn.getAttribute('data-zonkan-assign-folder');
            const propEl = scope.querySelector(`[data-property-id="${assignPropertyIds[0]}"]`);
            const memberIds = crmPropFolderIdsFromEl(propEl);
            btn.classList.toggle('is-on', memberIds.includes(String(folderId)));
        });
    }

    function openAssignModal(mode, propertyIds) {
        assignMode = mode;
        assignPropertyIds = propertyIds.map(String);
        if (titleEl) {
            titleEl.textContent = mode === 'bulk'
                ? `افزودن ${assignPropertyIds.length} فایل به زونکن`
                : 'مدیریت زونکن‌های فایل';
        }
        if (subEl) {
            subEl.textContent = mode === 'bulk'
                ? 'فایل‌های انتخاب‌شده به زونکن اضافه می‌شوند (عضویت قبلی حفظ می‌شود)'
                : 'برای افزودن یا حذف از زونکن، روی نام مجموعه بزنید';
        }
        syncAssignTicks();
        if (typeof modal.showModal === 'function') modal.showModal();
        else modal.setAttribute('open', '');
    }

    function closeAssignModal() {
        if (typeof modal.close === 'function') modal.close();
        else modal.removeAttribute('open');
    }

    async function toggleSingleMembership(folderId, propertyId) {
        const propEl = scope.querySelector(`[data-property-id="${propertyId}"]`);
        const memberIds = crmPropFolderIdsFromEl(propEl);
        const isOn = memberIds.includes(String(folderId));
        const url = crmPropFolderMembershipUrl(folderId, propertyId);
        const resp = await fetch(url, {
            method: isOn ? 'DELETE' : 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
        });
        const data = await crmParseJsonResponse(resp);
        if (!data.ok) throw new Error(data.error || 'عملیات ناموفق بود');
        const next = isOn
            ? memberIds.filter((id) => id !== String(folderId))
            : [...memberIds, String(folderId)];
        if (propEl) propEl.setAttribute('data-prop-folder-ids', next.join(','));
        return !isOn;
    }

    async function crmParseJsonResponse(resp) {
        const ct = (resp.headers.get('content-type') || '').toLowerCase();
        if (!ct.includes('application/json')) {
            throw new Error(resp.ok ? 'پاسخ سرور نامعتبر بود' : `خطای سرور (${resp.status})`);
        }
        return resp.json();
    }

    async function bulkAddToFolder(folderId) {
        const url = crmPropFolderBulkUrl(folderId);
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ property_ids: assignPropertyIds.map(Number) }),
        });
        const data = await crmParseJsonResponse(resp);
        if (!data.ok) throw new Error(data.error || 'عملیات ناموفق بود');
        assignPropertyIds.forEach((pid) => {
            const propEl = scope.querySelector(`[data-property-id="${pid}"]`);
            if (!propEl) return;
            const ids = crmPropFolderIdsFromEl(propEl);
            if (!ids.includes(String(folderId))) ids.push(String(folderId));
            propEl.setAttribute('data-prop-folder-ids', ids.join(','));
        });
        return data;
    }

    modal.querySelectorAll('[data-zonkan-assign-close]').forEach((btn) => {
        btn.addEventListener('click', closeAssignModal);
    });

    listEl?.querySelectorAll('[data-zonkan-assign-folder]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const folderId = btn.getAttribute('data-zonkan-assign-folder');
            btn.disabled = true;
            try {
                if (assignMode === 'bulk') {
                    const data = await bulkAddToFolder(folderId);
                    closeAssignModal();
                    checks().forEach((c) => { c.checked = false; });
                    updateBulkBar();
                    setSelectMode(false);
                    const added = data.added ?? 0;
                    window.alert(added > 0
                        ? `${added} فایل به زونکن اضافه شد`
                        : 'فایل‌ها از قبل در این زونکن بودند');
                    window.location.reload();
                    return;
                }
                const propertyId = assignPropertyIds[0];
                const nowOn = await toggleSingleMembership(folderId, propertyId);
                btn.classList.toggle('is-on', nowOn);
                window.location.reload();
            } catch (err) {
                window.alert(err.message || 'خطا در به‌روزرسانی زونکن');
            } finally {
                btn.disabled = false;
            }
        });
    });

    scope.querySelectorAll('[data-prop-folder-assign]').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const pid = btn.getAttribute('data-prop-folder-assign');
            if (pid) openAssignModal('single', [pid]);
        });
    });

    bulkOpen?.addEventListener('click', () => {
        const ids = selectedIds();
        if (!ids.length) return;
        openAssignModal('bulk', ids);
    });

    bulkClear?.addEventListener('click', () => {
        checks().forEach((c) => { c.checked = false; });
        updateBulkBar();
        setSelectMode(false);
    });

    checks().forEach((c) => c.addEventListener('change', updateBulkBar));

    selectModeBtn?.addEventListener('click', () => {
        const on = !scope.querySelector('.crm-files-pro--select-mode');
        setSelectMode(on);
    });

    scope.querySelectorAll('.crm-files-card-select, .crm-ft-td-check').forEach((wrap) => {
        wrap.addEventListener('click', (e) => e.stopPropagation());
    });
}

function crmStripDrawerQueryParams() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('open') && !params.has('drawer')) return;
    params.delete('open');
    params.delete('drawer');
    const qs = params.toString();
    const next = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash}`;
    window.history.replaceState({}, '', next);
}

function initCRMQueryDrawerIntent() {
    const drawerId = crmDrawerIdFromQuery();
    if (!drawerId || !document.getElementById(drawerId)) return false;
    CRMDrawer.open(drawerId);
    crmStripDrawerQueryParams();
    return true;
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-drawer-open]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.preventDefault();
            CRMDrawer.open(btn.dataset.drawerOpen);
            const formTab = btn.dataset.formTab;
            if (formTab) {
                const drawer = document.getElementById(btn.dataset.drawerOpen);
                const section = drawer?.querySelector('.crm-form-sections');
                if (section) crmActivateFormTab(section, formTab);
            }
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

    const openedFromQuery = initCRMQueryDrawerIntent();
    if (!openedFromQuery) {
        document.querySelectorAll('.crm-drawer[data-open="1"]').forEach(d => CRMDrawer.open(d.id));
    }

    initCRMTypeProfiles();
    initPropertyDealMode();
    initCRMFeatureProfile();
    initCRMGlobalSearch();
    initCRMMultiSelect();
    initCRMTabs();
    initContactSegrail();
    initCRMJalaliPickers(document);
    initCRMLeaseDeadline(document);
    initCRMPropertyOccVacancyDate(document);
    initCRMMoneyInputs(document);
    initCRMFormErrors();
    initCRMContactFormGuard();
    initCRMContactChannels(document);
    initCRMAreasPicker(document);
    initCRMPipeline();
    initCRMDealPipeline();
    initCRMPropertyPipeline();
    initCRMSavedFilters();
    initCRMPropertyFolders(document);
    initCRMPropertyFolderPicker(document);
    initCRMPropertyFolderAssign(document);
    initContactsMobileFilters();
    initContactsMobileMenus();
    initContactDetailMobileMenus();
    initContactHeroMorePanel();
    initContactAsideFolds();
    const afterCall = document.querySelector('.crm-contact-after-call');
    if (afterCall) afterCall.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    initCRMPropertyAdvFilters();
    initCRMDealStagesEditor();
    initCRMDealChecklist();
    initCRMCommissionSplit();
    initCRMContactTeam();
    initCRMContactStatusPicker();
    try { initCRMDealsPage(); } catch (err) { console.error('initCRMDealsPage', err); }
    try { initCRMPropGalleryLightbox(); } catch (err) { console.error(err); }
    try { initCRMPropertyTeam(); } catch (err) { console.error(err); }
    try { initCRMPropertyImages(); } catch (err) { console.error(err); }
    try {
        if (typeof window.initCRMFormMaps === 'function') window.initCRMFormMaps();
    } catch (err) { console.error(err); }
    try { initCRMTeamPage(); } catch (err) { console.error(err); }
    initCRMSidePanel();
    initCRMQuickLead();
    initCRMImportDrawer();
    initCRMMatches();
    initCRMPropContactMatches();
    initCRMMatchingTolerance();
    initCRMContactPortfolio();
    initCRMActivityDrawer(document);
    initCRMTabJump();
    initCRMVisitOutcome(document);
    initCRMNotifications();

    if (typeof window.wsCharts !== 'undefined' && window.Chart) {
        if (typeof initCharts === 'function') initCharts(window.wsCharts);
    }
});
