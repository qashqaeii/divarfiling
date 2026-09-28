(function () {
  'use strict';

  var wizard = document.querySelector('.ct-wizard[data-enable-pickers="1"]');
  if (!wizard) return;

  var apiCustomers = wizard.getAttribute('data-api-customers') || '';
  var apiProperties = wizard.getAttribute('data-api-properties') || '';
  var form = document.getElementById('ct-wizard-form');

  var modal = document.getElementById('ct-wizard-picker-modal');
  if (!modal || !form) return;

  var modalTitle = modal.querySelector('[data-ct-picker-title]');
  var modalSearch = modal.querySelector('[data-ct-picker-search]');
  var modalResults = modal.querySelector('[data-ct-picker-results]');
  var modalClose = modal.querySelector('[data-ct-picker-close]');
  var pickerMode = '';
  var pickerTarget = null;
  var searchTimer;
  var activeController = null;

  function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

  function setResultsState(html) {
    if (modalResults) modalResults.innerHTML = html;
  }

  function openModal(mode, target, title) {
    pickerMode = mode;
    pickerTarget = target;
    if (modalTitle) modalTitle.textContent = title || 'انتخاب';
    if (modalSearch) {
      modalSearch.value = '';
      modalSearch.placeholder = mode === 'customer' ? 'نام یا شماره موبایل…' : 'عنوان، محله یا آدرس…';
    }
    setResultsState('<p class="ct-picker-hint">برای جستجو حداقل ۲ حرف وارد کنید.</p>');
    modal.showModal();
    setTimeout(function () { if (modalSearch) modalSearch.focus(); }, 50);
    runSearch('');
  }

  function closeModal() {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
    modal.close();
    pickerMode = '';
    pickerTarget = null;
  }

  if (modalClose) modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeModal();
  });

  function runSearch(q) {
    var url = pickerMode === 'customer' ? apiCustomers : apiProperties;
    if (!url) return;
    if (activeController) activeController.abort();
    activeController = new AbortController();
    var qs = '?q=' + encodeURIComponent(q || '') + '&limit=20';
    setResultsState('<p class="ct-picker-loading"><i class="fas fa-spinner fa-spin"></i> در حال جستجو…</p>');
    fetch(url + qs, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: activeController.signal,
    }).then(function (r) { return r.json(); }).then(function (data) {
      activeController = null;
      if (!data.ok) {
        setResultsState('<p class="ct-picker-empty">خطا در بارگذاری</p>');
        return;
      }
      var items = data.results || [];
      if (!items.length) {
        setResultsState('<p class="ct-picker-empty">' + (q.length >= 2 || !q ? 'نتیجه‌ای یافت نشد.' : 'مخاطب یا فایلی برای نمایش نیست.') + '</p>');
        return;
      }
      var html = items.map(function (item) {
        if (pickerMode === 'customer') {
          return '<button type="button" class="ct-picker-item" data-id="' + item.id + '">' +
            '<strong>' + escapeHtml(item.name) + '</strong>' +
            '<span dir="ltr">' + escapeHtml(item.phone_masked || item.phone || '') + '</span>' +
            (item.meta ? '<em>' + escapeHtml(item.meta) + '</em>' : '') +
            '</button>';
        }
        var chips = (item.chips || []).map(function (c) { return escapeHtml(c); }).join(' · ');
        return '<button type="button" class="ct-picker-item" data-id="' + item.id + '">' +
          '<strong>' + escapeHtml(item.title) + '</strong>' +
          (item.location ? '<span>' + escapeHtml(item.location) + '</span>' : '') +
          (chips ? '<em>' + chips + '</em>' : '') +
          (item.price_hint ? '<span class="ct-picker-price">' + escapeHtml(item.price_hint) + '</span>' : '') +
          '</button>';
      }).join('');
      setResultsState(html);
      modalResults.querySelectorAll('.ct-picker-item').forEach(function (btn) {
        btn.addEventListener('click', function () {
          selectItem(parseInt(btn.getAttribute('data-id'), 10));
        });
      });
    }).catch(function (err) {
      if (err && err.name === 'AbortError') return;
      setResultsState('<p class="ct-picker-empty">خطا در ارتباط با سرور</p>');
    });
  }

  if (modalSearch) {
    modalSearch.addEventListener('input', function () {
      clearTimeout(searchTimer);
      var q = modalSearch.value.trim();
      searchTimer = setTimeout(function () { runSearch(q); }, 280);
    });
  }

  function selectItem(id) {
    if (!id || !pickerTarget) return;
    var base = pickerMode === 'customer' ? apiCustomers : apiProperties;
    var detailUrl = base.replace(/\/?$/, '/') + id + '/';
    fetch(detailUrl, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (!data.ok) return;
      if (pickerMode === 'customer') {
        applyCustomerToCard(pickerTarget, data.party || {});
      } else {
        applyPropertyToForm(data.property || {});
      }
      closeModal();
      form.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  function updateContactLinkBar(card, party) {
    var bar = card.querySelector('[data-ct-party-contact-link]');
    if (!bar) return;
    var linked = bar.querySelector('[data-ct-party-linked]');
    var pick = bar.querySelector('[data-ct-party-pick]');
    var cid = party.customer_id;
    if (cid) {
      bar.classList.add('is-linked');
      if (linked) {
        var nameEl = linked.querySelector('[data-ct-party-linked-name]');
        var phoneEl = linked.querySelector('[data-ct-party-linked-phone]');
        var fn = party.first_name || '';
        var ln = party.last_name || '';
        var display = (fn + ' ' + ln).trim() || party.company_name || 'مخاطب انتخاب‌شده';
        if (nameEl) nameEl.textContent = display;
        if (phoneEl) phoneEl.textContent = party.mobile || '';
        linked.hidden = false;
      }
      if (pick) pick.hidden = true;
    } else {
      bar.classList.remove('is-linked');
      if (linked) linked.hidden = true;
      if (pick) pick.hidden = false;
    }
  }

  function applyCustomerToCard(card, party) {
    var map = {
      person_type: party.person_type,
      first_name: party.first_name,
      last_name: party.last_name,
      father_name: party.father_name,
      national_id: party.national_id,
      mobile: party.mobile,
      address: party.address,
      postal_code: party.postal_code,
      company_name: party.company_name,
      ownership_share: party.ownership_share,
    };
    Object.keys(map).forEach(function (key) {
      var el = card.querySelector('[name$="_' + key + '"]');
      if (el && map[key] !== undefined && map[key] !== null) el.value = map[key];
    });
    var hid = card.querySelector('[data-ct-party-customer-id]');
    if (hid) hid.value = party.customer_id || '';
    card.classList.add('is-editing');
    updateContactLinkBar(card, party);
    if (typeof card.__updatePartySummary === 'function') card.__updatePartySummary();
  }

  function clearCustomerLink(card) {
    var hid = card.querySelector('[data-ct-party-customer-id]');
    if (hid) hid.value = '';
    updateContactLinkBar(card, {});
    form.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function bindPartyContactLink(card) {
    var pickBtn = card.querySelector('[data-ct-party-pick]');
    var changeBtn = card.querySelector('[data-ct-party-change]');
    var clearBtn = card.querySelector('[data-ct-party-clear]');
    if (pickBtn) {
      pickBtn.addEventListener('click', function () {
        openModal('customer', card, 'انتخاب از مخاطبین');
      });
    }
    if (changeBtn) {
      changeBtn.addEventListener('click', function () {
        openModal('customer', card, 'تغییر مخاطب');
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () { clearCustomerLink(card); });
    }
    var hid = card.querySelector('[data-ct-party-customer-id]');
    if (hid && hid.value) {
      updateContactLinkBar(card, {
        customer_id: hid.value,
        first_name: (card.querySelector('[name$="_first_name"]') || {}).value,
        last_name: (card.querySelector('[name$="_last_name"]') || {}).value,
        mobile: (card.querySelector('[name$="_mobile"]') || {}).value,
        company_name: (card.querySelector('[name$="_company_name"]') || {}).value,
      });
    }
  }

  var propertyLink = document.getElementById('ct-property-file-link');
  var propHidden = document.getElementById('prop_crm_property_id');

  function updatePropertyLinkBar(title) {
    if (!propertyLink) return;
    var linked = propertyLink.querySelector('[data-ct-property-linked]');
    var pick = propertyLink.querySelector('[data-ct-property-pick]');
    if (title) {
      propertyLink.classList.add('is-linked');
      var t = propertyLink.querySelector('[data-ct-property-linked-title]');
      if (t) t.textContent = title;
      if (linked) linked.hidden = false;
      if (pick) pick.hidden = true;
    } else {
      propertyLink.classList.remove('is-linked');
      if (linked) linked.hidden = true;
      if (pick) pick.hidden = false;
    }
  }

  function setField(name, value) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el || value === undefined || value === null) return;
    if (el.type === 'checkbox') {
      el.checked = !!value;
    } else {
      el.value = value === '' ? '' : String(value);
    }
  }

  function applyPropertyToForm(prop) {
    setField('prop_crm_property_id', prop.crm_property_id || '');
    setField('prop_crm_title', prop.crm_property_title || '');
    setField('prop_property_type', prop.property_type);
    setField('prop_usage', prop.usage);
    setField('prop_address', prop.address);
    setField('prop_postal_code', prop.postal_code);
    setField('prop_city', prop.city);
    setField('prop_district', prop.district);
    setField('prop_neighborhood', prop.neighborhood);
    setField('prop_area', prop.area);
    setField('prop_floor', prop.floor);
    setField('prop_unit', prop.unit);
    setField('prop_total_floors', prop.total_floors);
    setField('prop_units_per_floor', prop.units_per_floor);
    setField('prop_bedrooms', prop.bedrooms);
    setField('prop_build_year', prop.build_year);
    setField('prop_unit_direction', prop.unit_direction);
    setField('prop_building_direction', prop.building_direction);
    setField('prop_facade_type', prop.facade_type);
    setField('prop_floor_type', prop.floor_type);
    setField('prop_kitchen_type', prop.kitchen_type);
    setField('prop_heating', prop.heating_system);
    setField('prop_cooling', prop.cooling_system);
    setField('prop_deed_type', prop.deed_type);
    setField('prop_deed_number', prop.deed_number);
    setField('prop_main_plaque', prop.main_plaque);
    setField('prop_sub_plaque', prop.sub_plaque);
    setField('prop_has_parking', prop.has_parking);
    setField('prop_has_storage', prop.has_storage);
    setField('prop_has_elevator', prop.has_elevator);
    updatePropertyLinkBar(prop.crm_property_title || prop._crm_title || '');
  }

  function clearPropertyLink() {
    if (propHidden) propHidden.value = '';
    setField('prop_crm_title', '');
    updatePropertyLinkBar('');
    form.dispatchEvent(new Event('input', { bubbles: true }));
  }

  if (propertyLink) {
    var pickProp = propertyLink.querySelector('[data-ct-property-pick]');
    var changeProp = propertyLink.querySelector('[data-ct-property-change]');
    var clearProp = propertyLink.querySelector('[data-ct-property-clear]');
    if (pickProp) {
      pickProp.addEventListener('click', function () {
        openModal('property', propertyLink, 'انتخاب از فایل‌های شخصی');
      });
    }
    if (changeProp) {
      changeProp.addEventListener('click', function () {
        openModal('property', propertyLink, 'تغییر فایل شخصی');
      });
    }
    if (clearProp) clearProp.addEventListener('click', clearPropertyLink);
    if (propHidden && propHidden.value) {
      var titleEl = propertyLink.querySelector('[data-ct-property-linked-title]');
      updatePropertyLinkBar(titleEl ? titleEl.textContent : 'فایل انتخاب‌شده');
    }
  }

  window.ctWizardPickers = {
    bindPartyContactLink: bindPartyContactLink,
    partyContactLinkHtml: function (idx, customerId) {
      return (
        '<div class="ct-party-contact-link" data-ct-party-contact-link>' +
        '<div class="ct-party-contact-link__pick" data-ct-party-pick>' +
        '<i class="fas fa-address-book" aria-hidden="true"></i>' +
        '<span>انتخاب از مخاطبین</span>' +
        '<em>یا اطلاعات را دستی وارد کنید</em></div>' +
        '<div class="ct-party-contact-link__linked" data-ct-party-linked hidden>' +
        '<div class="ct-party-contact-link__linked-main">' +
        '<i class="fas fa-check-circle" aria-hidden="true"></i>' +
        '<div><strong data-ct-party-linked-name></strong>' +
        '<span dir="ltr" data-ct-party-linked-phone></span>' +
        '<small>انتخاب‌شده از مخاطبین</small></div></div>' +
        '<div class="ct-party-contact-link__linked-actions">' +
        '<button type="button" class="crm-dash-act" data-ct-party-change>تغییر مخاطب</button>' +
        '<button type="button" class="crm-dash-act" data-ct-party-clear>حذف اتصال</button>' +
        '</div></div>' +
        '<input type="hidden" name="party_' + idx + '_customer_id" value="' + (customerId || '') + '" data-ct-party-customer-id">' +
        '</div>'
      );
    },
  };
})();
