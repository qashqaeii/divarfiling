/**
 * ویرایش کامل آگهی فایلینگ — مودال حرفه‌ای
 * نیاز: #listings-edit-data (json_script)، #modal-edit-listing، #editListingForm
 */
(function (window, document) {
    'use strict';

    function qs(sel, root) { return (root || document).querySelector(sel); }
    function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

    function setField(el, value) {
        if (!el) return;
        el.value = value == null || value === '' ? '' : value;
    }

    function setTriState(el, value) {
        if (!el) return;
        if (value === true || value === 1 || value === '1') el.value = '1';
        else if (value === false || value === 0 || value === '0') el.value = '0';
        else el.value = '';
    }

    function formatMoneyHint(raw) {
        var n = Number(String(raw || '').replace(/,/g, ''));
        if (!n || Number.isNaN(n)) return '';
        if (n >= 1e9) return (n / 1e9).toFixed(2).replace(/\.?0+$/, '') + ' میلیارد تومان';
        if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + ' میلیون تومان';
        if (n >= 1e3) return (n / 1e3).toFixed(0) + ' هزار تومان';
        return n.toLocaleString('fa-IR') + ' تومان';
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function ListingEditController(opts) {
        this.editUrlTemplate = opts.editUrlTemplate || '';
        this.deleteUrlTemplate = opts.deleteUrlTemplate || '';
        this.defaultDatasetId = opts.defaultDatasetId || '';

        this.editModal = qs('#modal-edit-listing');
        this.editForm = qs('#editListingForm');
        this.editTitle = qs('#editListingTitle');
        this.editSubtitle = qs('#editListingSubtitle');
        this.editToken = qs('#editListingToken');
        this.featuresJson = qs('#editFeaturesJson');
        this.imagesJson = qs('#editImagesJson');
        this.featureGroupsEl = qs('#editFeatureGroups');
        this.featuresEmpty = qs('#editFeaturesEmpty');
        this.featuresCount = qs('#editFeaturesCount');
        this.imagesGrid = qs('#editImagesGrid');
        this.imagesCount = qs('#editImagesCount');
        this.imageUrlInput = qs('#editImageUrl');
        this.imageAddBtn = qs('#editImageAddBtn');

        var listingsEditEl = qs('#listings-edit-data');
        this.listingsEditData = {};
        if (listingsEditEl) {
            try { this.listingsEditData = JSON.parse(listingsEditEl.textContent); }
            catch (e) { this.listingsEditData = {}; }
        }

        this.images = [];
        this.featureFields = [];
        this.editScroll = null;
        this.navBtns = [];
        this.navSections = [];
        this._navJumping = false;
        this._navJumpTimer = null;
        this._navScrollTimer = null;

        this.fields = {
            title: qs('#editTitle'),
            price: qs('#editPrice'),
            deposit: qs('#editDeposit'),
            rent: qs('#editRent'),
            area: qs('#editArea'),
            rooms: qs('#editRooms'),
            floor: qs('#editFloor'),
            totalFloors: qs('#editTotalFloors'),
            buildYear: qs('#editBuildYear'),
            elevator: qs('#editElevator'),
            parking: qs('#editParking'),
            storage: qs('#editStorage'),
            balcony: qs('#editBalcony'),
            lobby: qs('#editLobby'),
            pool: qs('#editPool'),
            roofGarden: qs('#editRoofGarden'),
            jacuzzi: qs('#editJacuzzi'),
            gym: qs('#editGym'),
            neighborhood: qs('#editNeighborhood'),
            city: qs('#editCity'),
            district: qs('#editDistrict'),
            street: qs('#editStreet'),
            address: qs('#editAddress'),
            latitude: qs('#editLatitude'),
            longitude: qs('#editLongitude'),
            business: qs('#editBusiness'),
            expired: qs('#editExpired'),
            ownerPhone: qs('#editOwnerPhone'),
            ownerName: qs('#editOwnerName'),
            link: qs('#editLink'),
            description: qs('#editDescription'),
            isVacant: qs('#editIsVacant'),
            vacantRow: qs('#editVacantRow'),
            vacantOff: qs('#editIsVacantOff'),
            tenantPanel: qs('#editTenantPanel'),
            tenantName: qs('#editTenantName'),
            tenantPhone: qs('#editTenantPhone'),
            vacancyDate: qs('#editVacancyDate'),
            occMore: qs('#editOccMore'),
            occMoreVal: qs('#editOccMore [data-occ-more-val]'),
            occMoreHint: qs('#editOccMore [data-occ-more-hint]'),
            occDateClear: qs('#editOccMore [data-occ-date-clear]'),
            occDatePresets: qsa('#editOccMore [data-occ-date-preset]'),
            occPill: qs('#editVacantRow [data-occ-pill]'),
            occConfirm: qs('#editVacantRow [data-occ-confirm]'),
            occBtns: qsa('#editVacantRow [data-occ-set]'),
        };

        this.moneyHints = {
            price: qs('#editPriceHint'),
            deposit: qs('#editDepositHint'),
            rent: qs('#editRentHint'),
        };

        this._bindMoneyHints();
        this._bindOccupancySwitch();
        this._bindVacancyDate();
        this._initJalaliPicker();
        this._bindNav();
        this._bindImages();
        this._bindEditButtons();
        this._bindDelete();
        this._bindFormSubmit();
        this._bindActionMenus();
        this._bindEditModalVoice();
    }

    ListingEditController.prototype._bindEditModalVoice = function () {
        var self = this;
        if (!this.editModal) return;
        if (typeof window.enhanceWorkspaceVoiceInputs === 'function') {
            window.enhanceWorkspaceVoiceInputs(this.editModal);
        } else if (typeof window.initCRMFieldVoice === 'function') {
            window.initCRMFieldVoice(this.editModal);
        }
        this.editModal.querySelectorAll('[data-modal-close]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (typeof window.stopCRMFieldVoiceIn === 'function') {
                    window.stopCRMFieldVoiceIn(self.editModal);
                }
            });
        });
    };

    ListingEditController.prototype._syncOccupancyUI = function () {
        var f = this.fields;
        var vacantOn = !!(f.isVacant && f.isVacant.checked);
        if (f.vacantRow) {
            f.vacantRow.classList.remove('hidden');
            f.vacantRow.classList.toggle('is-vacant', vacantOn);
            f.vacantRow.classList.toggle('is-occupied', !vacantOn);
        }
        (f.occBtns || []).forEach(function (btn) {
            var wantVacant = btn.getAttribute('data-occ-set') === '1';
            var active = wantVacant === vacantOn;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        if (f.occPill) f.occPill.textContent = vacantOn ? 'تخلیه' : 'تخلیه نیست';
        if (f.occConfirm) f.occConfirm.hidden = !vacantOn;
        if (f.tenantPanel) {
            f.tenantPanel.classList.remove('hidden');
            f.tenantPanel.classList.toggle('is-disabled', vacantOn);
        }
        if (f.tenantName) {
            f.tenantName.disabled = vacantOn;
            if (vacantOn) f.tenantName.value = '';
        }
        if (f.tenantPhone) {
            f.tenantPhone.disabled = vacantOn;
            if (vacantOn) f.tenantPhone.value = '';
        }
        this._syncVacancyDateUI();
    };

    ListingEditController.prototype._toPersianDigits = function (value) {
        return String(value == null ? '' : value).replace(/[0-9]/g, function (d) {
            return '۰۱۲۳۴۵۶۷۸۹'[d];
        });
    };

    ListingEditController.prototype._jalaliYmdFromDate = function (date) {
        var parts = new Intl.DateTimeFormat('en-u-ca-persian', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).formatToParts(date);
        var y = '', m = '', d = '';
        parts.forEach(function (part) {
            if (part.type === 'year') y = part.value;
            if (part.type === 'month') m = part.value;
            if (part.type === 'day') d = part.value;
        });
        if (!y || !m || !d) return '';
        return this._toPersianDigits(y + '/' + m + '/' + d);
    };

    ListingEditController.prototype._presetVacancyDate = function (kind) {
        var now = new Date();
        var target = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        if (kind === 'tomorrow') target.setDate(target.getDate() + 1);
        else if (kind === 'week') target.setDate(target.getDate() + 7);
        else if (kind === 'month') target.setMonth(target.getMonth() + 1);
        return this._jalaliYmdFromDate(target);
    };

    ListingEditController.prototype._setVacancyDate = function (value) {
        var f = this.fields;
        if (!f.vacancyDate) return;
        f.vacancyDate.value = value || '';
        this._syncVacancyDateUI();
    };

    ListingEditController.prototype._syncVacancyDateUI = function () {
        var f = this.fields;
        var raw = f.vacancyDate ? String(f.vacancyDate.value || '').trim() : '';
        if (f.occDateClear) f.occDateClear.hidden = !raw;
        if (f.occMoreVal) {
            f.occMoreVal.textContent = raw;
            f.occMoreVal.hidden = !raw;
        }
        if (f.occMoreHint) {
            f.occMoreHint.textContent = raw
                ? 'تاریخ انتخاب‌شده در تقویم شمسی'
                : 'تاریخ تخلیه اختیاری — تقویم شمسی';
        }
        if (f.occMore && raw) f.occMore.open = true;
    };

    ListingEditController.prototype._initJalaliPicker = function () {
        if (typeof jalaliDatepicker === 'undefined' || this._jalaliReady) return;
        jalaliDatepicker.startWatch({
            minDate: 'attr',
            maxDate: 'attr',
            zIndex: 20050,
            separatorChars: { date: '/', between: ' ', time: ':' },
            persianDigits: true,
            autoHide: true,
            time: false,
            hasSecond: false,
            hideAfterChange: true,
        });
        this._jalaliReady = true;
    };

    ListingEditController.prototype._bindVacancyDate = function () {
        var self = this;
        var f = this.fields;
        if (f.vacancyDate) {
            f.vacancyDate.addEventListener('change', function () { self._syncVacancyDateUI(); });
            f.vacancyDate.addEventListener('input', function () { self._syncVacancyDateUI(); });
        }
        if (f.occDateClear) {
            f.occDateClear.addEventListener('click', function (e) {
                e.preventDefault();
                self._setVacancyDate('');
            });
        }
        (f.occDatePresets || []).forEach(function (btn) {
            btn.addEventListener('click', function () {
                var kind = btn.getAttribute('data-occ-date-preset');
                self._setVacancyDate(self._presetVacancyDate(kind));
            });
        });
    };

    ListingEditController.prototype._bindOccupancySwitch = function () {
        var self = this;
        var f = this.fields;
        (f.occBtns || []).forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (!f.isVacant || f.isVacant.disabled) return;
                f.isVacant.checked = btn.getAttribute('data-occ-set') === '1';
                self._syncOccupancyUI();
            });
        });
        if (f.isVacant) {
            f.isVacant.addEventListener('change', function () {
                self._syncOccupancyUI();
            });
        }
    };

    ListingEditController.prototype._bindMoneyHints = function () {
        var self = this;
        ['price', 'deposit', 'rent'].forEach(function (key) {
            var input = self.fields[key];
            var hint = self.moneyHints[key];
            if (!input) return;
            input.addEventListener('input', function () {
                if (hint) hint.textContent = formatMoneyHint(input.value);
            });
        });
    };

    ListingEditController.prototype._bindNav = function () {
        var self = this;
        this.editScroll = qs('[data-edit-scroll]', this.editForm);
        this.navBtns = qsa('[data-edit-jump]', this.editModal || document);
        this._refreshNavSections();

        this.navBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-edit-jump');
                self._setActiveNav(btn);
                self._scrollToSection(id);
            });
        });

        if (this.editScroll) {
            this.editScroll.addEventListener('scroll', function () {
                self._onEditScroll();
            }, { passive: true });
        }
    };

    ListingEditController.prototype._refreshNavSections = function () {
        this.navSections = this.editScroll
            ? qsa('.mk-edit-section', this.editScroll)
            : [];
    };

    ListingEditController.prototype._setActiveNav = function (activeBtn) {
        this.navBtns.forEach(function (b) {
            b.classList.toggle('is-active', b === activeBtn);
        });
    };

    ListingEditController.prototype._setActiveNavById = function (sectionId) {
        if (!sectionId) return;
        this.navBtns.forEach(function (b) {
            b.classList.toggle('is-active', b.getAttribute('data-edit-jump') === sectionId);
        });
    };

    ListingEditController.prototype._sectionScrollTop = function (target) {
        var root = this.editScroll;
        if (!root || !target) return 0;
        return target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
    };

    ListingEditController.prototype._scrollToSection = function (sectionId) {
        var target = sectionId ? document.getElementById(sectionId) : null;
        var root = this.editScroll;
        if (!target || !root) return;

        this._navJumping = true;
        clearTimeout(this._navJumpTimer);
        root.scrollTo({
            top: Math.max(0, this._sectionScrollTop(target) - 4),
            behavior: 'smooth',
        });
        this._navJumpTimer = window.setTimeout(function () {
            this._navJumping = false;
            this._syncActiveNavFromScroll();
        }.bind(this), 450);
    };

    ListingEditController.prototype._syncActiveNavFromScroll = function () {
        var root = this.editScroll;
        if (!root || !this.navSections.length) return;

        var marker = root.scrollTop + 12;
        var activeId = this.navSections[0].id;

        this.navSections.forEach(function (section) {
            if (this._sectionScrollTop(section) <= marker) {
                activeId = section.id;
            }
        }.bind(this));

        this._setActiveNavById(activeId);
    };

    ListingEditController.prototype._onEditScroll = function () {
        if (this._navJumping) return;
        clearTimeout(this._navScrollTimer);
        this._navScrollTimer = window.setTimeout(function () {
            this._syncActiveNavFromScroll();
        }.bind(this), 60);
    };

    ListingEditController.prototype._resetNavState = function () {
        this._refreshNavSections();
        if (this.editScroll) this.editScroll.scrollTop = 0;
        this._setActiveNavById('sec-main');
    };

    ListingEditController.prototype._bindImages = function () {
        var self = this;
        if (this.imageAddBtn) {
            this.imageAddBtn.addEventListener('click', function () {
                self.addImageUrl();
            });
        }
        if (this.imageUrlInput) {
            this.imageUrlInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    self.addImageUrl();
                }
            });
        }
        if (this.imagesGrid) {
            this.imagesGrid.addEventListener('click', function (e) {
                var btn = e.target.closest('[data-img-action]');
                if (!btn) return;
                var idx = parseInt(btn.getAttribute('data-idx'), 10);
                var action = btn.getAttribute('data-img-action');
                if (Number.isNaN(idx)) return;
                if (action === 'remove') {
                    self.images.splice(idx, 1);
                    self.renderImages();
                } else if (action === 'up' && idx > 0) {
                    var tmp = self.images[idx - 1];
                    self.images[idx - 1] = self.images[idx];
                    self.images[idx] = tmp;
                    self.renderImages();
                } else if (action === 'down' && idx < self.images.length - 1) {
                    var tmp2 = self.images[idx + 1];
                    self.images[idx + 1] = self.images[idx];
                    self.images[idx] = tmp2;
                    self.renderImages();
                }
            });
        }
    };

    ListingEditController.prototype.addImageUrl = function () {
        var url = (this.imageUrlInput && this.imageUrlInput.value || '').trim();
        if (!url) return;
        if (!(url.indexOf('http://') === 0 || url.indexOf('https://') === 0 || url.indexOf('/') === 0)) {
            return;
        }
        if (this.images.indexOf(url) === -1) {
            this.images.push(url);
            this.renderImages();
        }
        if (this.imageUrlInput) this.imageUrlInput.value = '';
    };

    ListingEditController.prototype.renderImages = function () {
        if (this.imagesJson) this.imagesJson.value = JSON.stringify(this.images);
        if (this.imagesCount) {
            this.imagesCount.textContent = this.images.length
                ? this.images.length.toLocaleString('fa-IR') + ' تصویر'
                : 'بدون تصویر';
        }
        if (!this.imagesGrid) return;
        if (!this.images.length) {
            this.imagesGrid.innerHTML = '<p class="mk-edit-features-empty">تصویری ثبت نشده.</p>';
            return;
        }
        this.imagesGrid.innerHTML = this.images.map(function (url, idx) {
            return (
                '<div class="mk-edit-img-item">' +
                    '<div class="mk-edit-img-thumb" style="background-image:url(\'' + escapeHtml(url).replace(/'/g, '%27') + '\')"></div>' +
                    '<div class="mk-edit-img-meta">' +
                        '<span class="mk-edit-img-idx">' + (idx === 0 ? 'کاور' : (idx + 1)) + '</span>' +
                        '<code class="mk-edit-img-url" title="' + escapeHtml(url) + '">' + escapeHtml(url.length > 48 ? url.slice(0, 48) + '…' : url) + '</code>' +
                    '</div>' +
                    '<div class="mk-edit-img-actions">' +
                        '<button type="button" class="mk-edit-img-btn" data-img-action="up" data-idx="' + idx + '" title="بالا" ' + (idx === 0 ? 'disabled' : '') + '><i class="fas fa-arrow-up"></i></button>' +
                        '<button type="button" class="mk-edit-img-btn" data-img-action="down" data-idx="' + idx + '" title="پایین" ' + (idx === this.images.length - 1 ? 'disabled' : '') + '><i class="fas fa-arrow-down"></i></button>' +
                        '<button type="button" class="mk-edit-img-btn mk-edit-img-btn--danger" data-img-action="remove" data-idx="' + idx + '" title="حذف"><i class="fas fa-trash"></i></button>' +
                    '</div>' +
                '</div>'
            );
        }.bind(this)).join('');
    };

    ListingEditController.prototype.renderFeatureFields = function (fields) {
        this.featureFields = Array.isArray(fields) ? fields : [];
        if (!this.featureGroupsEl) return;

        var filled = this.featureFields.filter(function (f) { return f.value; }).length;
        if (this.featuresCount) {
            this.featuresCount.textContent = this.featureFields.length
                ? '(' + filled.toLocaleString('fa-IR') + ' از ' + this.featureFields.length.toLocaleString('fa-IR') + ')'
                : '';
        }

        if (!this.featureFields.length) {
            this.featureGroupsEl.innerHTML = '';
            if (this.featuresEmpty) this.featuresEmpty.hidden = false;
            if (this.featuresJson) this.featuresJson.value = '{}';
            return;
        }
        if (this.featuresEmpty) this.featuresEmpty.hidden = true;

        var groups = {};
        var order = [];
        this.featureFields.forEach(function (f) {
            var gid = f.group_id || 'extra';
            if (!groups[gid]) {
                groups[gid] = {
                    id: gid,
                    title: f.group_title || 'سایر',
                    icon: f.group_icon || 'fa-list',
                    items: [],
                };
                order.push(gid);
            }
            groups[gid].items.push(f);
        });

        var html = order.map(function (gid) {
            var g = groups[gid];
            var itemsHtml = g.items.map(function (item) {
                var key = item.key || '';
                var val = item.value || '';
                var inputHtml;
                if (item.input === 'tri') {
                    var sel = '';
                    var state = item.state;
                    if (val === 'دارد' || state === 'yes') sel = '1';
                    else if (val === 'ندارد' || state === 'no') sel = '0';
                    inputHtml =
                        '<select class="ws-select ws-select-sm" data-feat-key="' + escapeHtml(key) + '">' +
                            '<option value=""' + (sel === '' ? ' selected' : '') + '>نامشخص</option>' +
                            '<option value="دارد"' + (sel === '1' ? ' selected' : '') + '>دارد</option>' +
                            '<option value="ندارد"' + (sel === '0' ? ' selected' : '') + '>ندارد</option>' +
                        '</select>';
                } else if (item.input === 'select' || (item.choices && item.choices.length)) {
                    var choices = item.choices || [];
                    var opts = ['<option value=""' + (val === '' ? ' selected' : '') + '>نامشخص</option>'];
                    var seen = {};
                    choices.forEach(function (choice) {
                        var c = String(choice || '');
                        if (!c || seen[c]) return;
                        seen[c] = true;
                        opts.push(
                            '<option value="' + escapeHtml(c) + '"' + (val === c ? ' selected' : '') + '>' +
                            escapeHtml(c) +
                            '</option>'
                        );
                    });
                    if (val && !seen[val]) {
                        opts.splice(1, 0,
                            '<option value="' + escapeHtml(val) + '" selected>' + escapeHtml(val) + '</option>'
                        );
                    }
                    inputHtml =
                        '<select class="ws-select ws-select-sm" data-feat-key="' + escapeHtml(key) + '">' +
                            opts.join('') +
                        '</select>';
                } else {
                    inputHtml =
                        '<input type="text" class="ws-input ws-input-sm" data-feat-key="' + escapeHtml(key) + '" value="' + escapeHtml(val) + '" autocomplete="off">';
                }
                return (
                    '<label class="mk-edit-feature-field">' +
                        '<span class="mk-edit-feature-label">' + escapeHtml(item.label || key) + '</span>' +
                        inputHtml +
                    '</label>'
                );
            }).join('');
            return (
                '<div class="mk-edit-feature-group">' +
                    '<h4 class="mk-edit-feature-group-title"><i class="fas ' + escapeHtml(g.icon) + '" aria-hidden="true"></i> ' + escapeHtml(g.title) + '</h4>' +
                    '<div class="mk-edit-features-grid">' + itemsHtml + '</div>' +
                '</div>'
            );
        }).join('');

        this.featureGroupsEl.innerHTML = html;
        this.syncFeaturesJson();
        this._refreshNavSections();

        var self = this;
        qsa('[data-feat-key]', this.featureGroupsEl).forEach(function (el) {
            el.addEventListener('change', function () { self.syncFeaturesJson(); });
            el.addEventListener('input', function () { self.syncFeaturesJson(); });
        });
    };

    ListingEditController.prototype.syncFeaturesJson = function () {
        if (!this.featuresJson || !this.featureGroupsEl) return;
        var out = {};
        qsa('[data-feat-key]', this.featureGroupsEl).forEach(function (el) {
            var key = el.getAttribute('data-feat-key');
            if (!key) return;
            out[key] = (el.value || '').trim();
        });
        this.featuresJson.value = JSON.stringify(out);
    };

    ListingEditController.prototype.fillEditForm = function (data) {
        if (!data) return;
        var f = this.fields;
        var listingTitle = data.title || '—';
        if (this.editTitle) this.editTitle.textContent = listingTitle;
        if (this.editSubtitle) {
            this.editSubtitle.textContent = listingTitle;
            this.editSubtitle.hidden = true;
        }
        if (this.editToken) {
            if (data.token) {
                this.editToken.hidden = false;
                this.editToken.textContent = data.token;
            } else {
                this.editToken.hidden = true;
                this.editToken.textContent = '';
            }
        }

        setField(f.title, data.title);
        setField(f.price, data.price);
        setField(f.deposit, data.deposit);
        setField(f.rent, data.rent);
        setField(f.area, data.area);
        setField(f.rooms, data.rooms);
        setField(f.floor, data.floor);
        setField(f.totalFloors, data.total_floors);
        setField(f.buildYear, data.build_year);
        setTriState(f.elevator, data.elevator);
        setTriState(f.parking, data.parking);
        setTriState(f.storage, data.storage);
        setTriState(f.balcony, data.balcony);
        setTriState(f.lobby, data.lobby);
        setTriState(f.pool, data.pool);
        setTriState(f.roofGarden, data.roof_garden);
        setTriState(f.jacuzzi, data.jacuzzi);
        setTriState(f.gym, data.gym);
        setField(f.neighborhood, data.neighborhood);
        setField(f.city, data.city);
        setField(f.district, data.district);
        setField(f.street, data.street);
        setField(f.address, data.address);
        setField(f.latitude, data.latitude);
        setField(f.longitude, data.longitude);
        if (f.business) {
            var biz = data.business_type || 'شخصی';
            f.business.value = ['شخصی', 'مشاور', 'business'].indexOf(biz) >= 0 ? biz : 'شخصی';
        }
        if (f.expired) f.expired.value = data.is_expired ? '1' : '0';
        setField(f.ownerPhone, data.owner_phone);
        setField(f.ownerName, data.owner_name);
        setField(f.link, data.link);
        if (f.description) f.description.value = data.description || '';

        if (f.vacantRow) f.vacantRow.classList.remove('hidden');
        if (f.isVacant) {
            f.isVacant.checked = !!data.is_vacant;
            f.isVacant.disabled = false;
        }
        if (f.vacantOff) f.vacantOff.disabled = false;
        this._syncOccupancyUI();
        if (!data.is_vacant) {
            setField(f.tenantName, data.tenant_name);
            setField(f.tenantPhone, data.tenant_phone);
        } else {
            setField(f.tenantName, '');
            setField(f.tenantPhone, '');
        }
        this._setVacancyDate(data.vacancy_date || '');
        if (f.occMore) f.occMore.open = !!(data.vacancy_date);

        ['price', 'deposit', 'rent'].forEach(function (key) {
            var input = f[key];
            var hint = this.moneyHints[key];
            if (input && hint) hint.textContent = formatMoneyHint(input.value);
        }.bind(this));

        this.images = Array.isArray(data.images) ? data.images.slice() : [];
        this.renderImages();
        this.renderFeatureFields(data.feature_fields || []);
    };

    ListingEditController.prototype.openEdit = function (listingId, datasetId) {
        var id = String(listingId || '');
        var data = this.listingsEditData[id];
        if (!data || !this.editForm) return false;
        var dsId = datasetId || data.dataset_id || this.defaultDatasetId;
        if (this.editUrlTemplate) {
            this.editForm.action = this.editUrlTemplate
                .replace('__DATASET__', dsId)
                .replace('__LISTING__', id);
        } else {
            this.editForm.action = '/workspace/datasets/' + dsId + '/listings/' + id + '/edit/';
        }
        this.fillEditForm(data);
        if (this.editModal) {
            this.editModal.classList.add('is-open');
            document.body.classList.add('ws-modal-open');
            if (typeof window.enhanceWorkspaceVoiceInputs === 'function') {
                window.enhanceWorkspaceVoiceInputs(this.editModal);
            } else if (typeof window.initCRMFieldVoice === 'function') {
                window.initCRMFieldVoice(this.editModal);
            }
        }
        this._refreshNavSections();
        this._resetNavState();
        if (this.fields.title) this.fields.title.focus();
        return true;
    };

    ListingEditController.prototype._bindEditButtons = function () {
        var self = this;
        qsa('.js-edit-listing').forEach(function (btn) {
            btn.addEventListener('click', function () {
                btn.closest('.mk-action-menu') && btn.closest('.mk-action-menu').removeAttribute('open');
                self.openEdit(btn.dataset.id, btn.dataset.datasetId);
            });
        });
        // دکمه صفحه جزئیات
        qsa('[data-open-listing-edit]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                self.openEdit(btn.dataset.id || btn.getAttribute('data-open-listing-edit'), btn.dataset.datasetId);
            });
        });
    };

    ListingEditController.prototype._bindFormSubmit = function () {
        var self = this;
        if (!this.editForm) return;
        this.editForm.addEventListener('submit', function () {
            self.syncFeaturesJson();
            if (self.imagesJson) self.imagesJson.value = JSON.stringify(self.images || []);
        });
    };

    ListingEditController.prototype._bindDelete = function () {
        var deleteModal = qs('#modal-delete-listing');
        var deleteForm = qs('#deleteListingForm');
        var deleteText = qs('#deleteListingText');
        var self = this;
        if (!deleteForm) return;
        qsa('.js-delete-listing').forEach(function (btn) {
            btn.addEventListener('click', function () {
                btn.closest('.mk-action-menu') && btn.closest('.mk-action-menu').removeAttribute('open');
                var id = btn.dataset.id;
                var dsId = btn.dataset.datasetId || self.defaultDatasetId;
                if (self.deleteUrlTemplate) {
                    deleteForm.action = self.deleteUrlTemplate
                        .replace('__DATASET__', dsId)
                        .replace('__LISTING__', id);
                } else {
                    deleteForm.action = '/workspace/datasets/' + dsId + '/listings/' + id + '/delete/';
                }
                if (deleteText) {
                    var title = btn.dataset.title || '';
                    deleteText.textContent = title
                        ? 'آگهی «' + title + '» از فایلینگ شما حذف می‌شود و در استخراج‌های بعدی نیز دوباره نمایش داده نخواهد شد. فایل شخصی/CRM مرتبط حذف نمی‌شود.'
                        : 'این آگهی از فایلینگ شما حذف می‌شود و در استخراج‌های بعدی نیز دوباره نمایش داده نخواهد شد. فایل شخصی/CRM مرتبط حذف نمی‌شود.';
                }
                if (deleteModal) {
                    deleteModal.classList.add('is-open');
                    document.body.classList.add('ws-modal-open');
                }
            });
        });
    };

    ListingEditController.prototype._bindActionMenus = function () {
        qsa('.mk-action-menu').forEach(function (menu) {
            menu.addEventListener('toggle', function () {
                if (!menu.open) return;
                qsa('.mk-action-menu[open]').forEach(function (other) {
                    if (other !== menu) other.removeAttribute('open');
                });
            });
        });
        document.addEventListener('click', function (e) {
            if (e.target.closest('.mk-action-menu')) return;
            qsa('.mk-action-menu[open]').forEach(function (m) {
                m.removeAttribute('open');
            });
        });
    };

    window.ListingEditController = ListingEditController;

    window.initListingEdit = function (opts) {
        return new ListingEditController(opts || {});
    };
})(window, document);
