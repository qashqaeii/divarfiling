(function () {
  'use strict';

  var wizard = document.querySelector('.ct-wizard[data-enable-pickers="1"]');
  if (!wizard) return;

  var apiCustomers = wizard.getAttribute('data-api-customers') || '';
  var apiProperties = wizard.getAttribute('data-api-properties') || '';
  var form = document.getElementById('ct-wizard-form');
  var modal = document.getElementById('ct-wizard-picker-modal');
  if (!modal || !form) return;

  var PAGE_SIZE = 20;
  var modalTitle = modal.querySelector('[data-ct-picker-title]');
  var modalSubtitle = modal.querySelector('[data-ct-picker-subtitle]');
  var modalIcon = modal.querySelector('[data-ct-picker-icon]');
  var modalSearch = modal.querySelector('[data-ct-picker-search]');
  var modalResults = modal.querySelector('[data-ct-picker-results]');
  var modalClose = modal.querySelector('[data-ct-picker-close]');
  var modalRetry = modal.querySelector('[data-ct-picker-retry]');

  var pickerMode = '';
  var pickerTarget = null;
  var searchTimer;
  var activeController = null;
  var selecting = false;

  var listState = {
    items: [],
    query: '',
    nextOffset: 0,
    hasMore: false,
    loading: false,
    loadingMore: false,
    error: false,
    requestGen: 0,
  };

  function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }

  function apiBase() {
    return pickerMode === 'customer' ? apiCustomers : apiProperties;
  }

  function resetListState() {
    listState.items = [];
    listState.query = '';
    listState.nextOffset = 0;
    listState.hasMore = false;
    listState.loading = false;
    listState.loadingMore = false;
    listState.error = false;
  }

  function setModalChrome(mode, title) {
    var isCustomer = mode === 'customer';
    if (modalTitle) modalTitle.textContent = title || (isCustomer ? 'انتخاب مخاطب' : 'انتخاب فایل شخصی');
    if (modalSubtitle) {
      modalSubtitle.textContent = isCustomer
        ? 'از لیست مخاطبین CRM انتخاب کنید یا جستجو کنید'
        : 'از فایل‌های شخصی خود یک ملک انتخاب کنید';
    }
    if (modalIcon) {
      modalIcon.innerHTML = isCustomer
        ? '<i class="fas fa-address-book" aria-hidden="true"></i>'
        : '<i class="fas fa-folder-open" aria-hidden="true"></i>';
    }
    if (modalSearch) {
      modalSearch.placeholder = isCustomer ? 'جستجو: نام، موبایل، شرکت…' : 'جستجو: عنوان، محله، آدرس…';
    }
  }

  function footerHtml() {
    if (listState.error) {
      return (
        '<div class="ct-picker-state ct-picker-state--error">' +
        '<i class="fas fa-circle-exclamation" aria-hidden="true"></i>' +
        '<p>بارگذاری نتایج ممکن نشد.</p>' +
        '<button type="button" class="crm-dash-act" data-ct-picker-retry-inline>تلاش مجدد</button>' +
        '</div>'
      );
    }
    if (listState.loadingMore) {
      return (
        '<div class="ct-picker-state ct-picker-state--loading" aria-live="polite">' +
        '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i><span>در حال بارگذاری…</span></div>'
      );
    }
    if (listState.items.length && !listState.hasMore) {
      return '<div class="ct-picker-state ct-picker-state--end">همه موارد نمایش داده شد</div>';
    }
    return '';
  }

  function renderCustomerRow(item) {
    var meta = item.meta ? '<span class="ct-picker-card__tag">' + escapeHtml(item.meta) + '</span>' : '';
    return (
      '<button type="button" class="ct-picker-card" data-id="' + item.id + '" role="option">' +
      '<span class="ct-picker-card__avatar" aria-hidden="true"><i class="fas fa-user"></i></span>' +
      '<span class="ct-picker-card__body">' +
      '<strong class="ct-picker-card__title">' + escapeHtml(item.name) + '</strong>' +
      '<span class="ct-picker-card__sub" dir="ltr">' + escapeHtml(item.phone_masked || item.phone || '') + '</span>' +
      meta +
      '</span>' +
      '<span class="ct-picker-card__chev" aria-hidden="true"><i class="fas fa-chevron-left"></i></span>' +
      '</button>'
    );
  }

  function renderPropertyRow(item) {
    var chips = (item.chips || []).slice(0, 3).map(function (c) {
      return '<span class="ct-picker-card__chip">' + escapeHtml(c) + '</span>';
    }).join('');
    var typeLine = item.property_type
      ? '<span class="ct-picker-card__sub">' + escapeHtml(item.property_type) +
        (item.deal_mode ? ' · ' + escapeHtml(item.deal_mode) : '') + '</span>'
      : '';
    var loc = item.location
      ? '<span class="ct-picker-card__meta">' + escapeHtml(item.location) + '</span>'
      : '';
    var price = item.price_hint
      ? '<span class="ct-picker-card__price">' + escapeHtml(item.price_hint) + '</span>'
      : '';
    return (
      '<button type="button" class="ct-picker-card ct-picker-card--property" data-id="' + item.id + '" role="option">' +
      '<span class="ct-picker-card__avatar ct-picker-card__avatar--property" aria-hidden="true"><i class="fas fa-building"></i></span>' +
      '<span class="ct-picker-card__body">' +
      '<strong class="ct-picker-card__title">' + escapeHtml(item.title) + '</strong>' +
      typeLine + loc +
      (chips ? '<span class="ct-picker-card__chips">' + chips + '</span>' : '') +
      price +
      '</span>' +
      '<span class="ct-picker-card__chev" aria-hidden="true"><i class="fas fa-chevron-left"></i></span>' +
      '</button>'
    );
  }

  function bindResultButtons() {
    if (!modalResults) return;
    modalResults.querySelectorAll('.ct-picker-card[data-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selectItem(parseInt(btn.getAttribute('data-id'), 10));
      });
    });
    var retry = modalResults.querySelector('[data-ct-picker-retry-inline]');
    if (retry) {
      retry.addEventListener('click', function () {
        fetchPage(listState.items.length === 0);
      });
    }
  }

  function renderList() {
    if (!modalResults) return;
    if (listState.loading && !listState.items.length) {
      modalResults.innerHTML =
        '<div class="ct-picker-state ct-picker-state--loading ct-picker-state--full">' +
        '<div class="ct-picker-skeleton"></div><div class="ct-picker-skeleton"></div><div class="ct-picker-skeleton"></div>' +
        '</div>';
      return;
    }
    var q = listState.query;
    if (q.length === 1) {
      modalResults.innerHTML =
        '<div class="ct-picker-state ct-picker-state--hint">' +
        '<i class="fas fa-keyboard" aria-hidden="true"></i>' +
        '<p>برای جستجو حداقل ۲ حرف وارد کنید.</p></div>';
      return;
    }
    if (!listState.items.length && !listState.loading && !listState.error) {
      modalResults.innerHTML =
        '<div class="ct-picker-state ct-picker-state--empty">' +
        '<i class="fas fa-inbox" aria-hidden="true"></i>' +
        '<p>' + (q.length >= 2 ? 'نتیجه‌ای یافت نشد.' : 'موردی برای نمایش نیست.') + '</p></div>';
      return;
    }
    var rows = listState.items.map(function (item) {
      return pickerMode === 'customer' ? renderCustomerRow(item) : renderPropertyRow(item);
    }).join('');
    modalResults.innerHTML = '<div class="ct-picker-list">' + rows + footerHtml() + '</div>';
    bindResultButtons();
  }

  function fetchPage(reset) {
    var url = apiBase();
    if (!url) return;
    if (!reset && (!listState.hasMore || listState.loadingMore || listState.loading)) return;

    var gen = ++listState.requestGen;
    if (reset) {
      listState.loading = true;
      listState.loadingMore = false;
      listState.error = false;
      listState.items = [];
      listState.nextOffset = 0;
      listState.hasMore = false;
      if (modalResults) modalResults.scrollTop = 0;
      renderList();
    } else {
      listState.loadingMore = true;
      renderList();
    }

    if (activeController) activeController.abort();
    activeController = new AbortController();
    var offset = reset ? 0 : listState.nextOffset;
    var qs = '?q=' + encodeURIComponent(listState.query || '') +
      '&limit=' + PAGE_SIZE + '&offset=' + offset;

    fetch(url + qs, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: activeController.signal,
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (gen !== listState.requestGen) return;
      activeController = null;
      listState.loading = false;
      listState.loadingMore = false;
      if (!data.ok) {
        listState.error = true;
        if (!listState.items.length) renderList();
        else {
          listState.hasMore = false;
          renderList();
        }
        return;
      }
      listState.error = false;
      var batch = data.results || [];
      if (reset) listState.items = batch;
      else listState.items = listState.items.concat(batch);
      listState.hasMore = !!data.has_more;
      listState.nextOffset = data.next_offset != null ? data.next_offset : (offset + batch.length);
      renderList();
    }).catch(function (err) {
      if (err && err.name === 'AbortError') return;
      if (gen !== listState.requestGen) return;
      activeController = null;
      listState.loading = false;
      listState.loadingMore = false;
      listState.error = true;
      renderList();
    });
  }

  function onResultsScroll() {
    if (!modalResults || listState.loading || listState.loadingMore || !listState.hasMore) return;
    var threshold = 72;
    if (modalResults.scrollTop + modalResults.clientHeight >= modalResults.scrollHeight - threshold) {
      fetchPage(false);
    }
  }

  function openModal(mode, target, title) {
    pickerMode = mode;
    pickerTarget = target;
    resetListState();
    setModalChrome(mode, title);
    if (modalSearch) modalSearch.value = '';
    listState.query = '';
    modal.showModal();
    setTimeout(function () { if (modalSearch) modalSearch.focus(); }, 50);
    fetchPage(true);
  }

  function closeModal() {
    if (typeof window.stopCRMFieldVoiceIn === 'function') {
      window.stopCRMFieldVoiceIn(modal);
    }
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
    listState.requestGen += 1;
    resetListState();
    modal.close();
    pickerMode = '';
    pickerTarget = null;
    selecting = false;
  }

  if (modalClose) modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeModal();
  });
  if (modalRetry) {
    modalRetry.addEventListener('click', function () { fetchPage(true); });
  }
  if (modalResults) {
    modalResults.addEventListener('scroll', onResultsScroll);
  }

  if (modalSearch) {
    modalSearch.addEventListener('input', function () {
      clearTimeout(searchTimer);
      var q = modalSearch.value.trim();
      searchTimer = setTimeout(function () {
        listState.query = q;
        fetchPage(true);
      }, 280);
    });
  }

  function selectItem(id) {
    if (!id || !pickerTarget || selecting) return;
    selecting = true;
    var detailUrl = apiBase().replace(/\/?$/, '/') + id + '/';
    fetch(detailUrl, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(function (r) { return r.json(); }).then(function (data) {
      selecting = false;
      if (!data.ok) {
        if (modalResults) {
          modalResults.insertAdjacentHTML('afterbegin',
            '<div class="ct-picker-toast" role="alert">انتخاب ممکن نشد — دوباره تلاش کنید.</div>');
          setTimeout(function () {
            var t = modalResults.querySelector('.ct-picker-toast');
            if (t) t.remove();
          }, 3500);
        }
        return;
      }
      if (pickerMode === 'customer') {
        applyCustomerToCard(pickerTarget, data.party || {});
      } else {
        applyPropertyToForm(data.property || {});
      }
      closeModal();
      form.dispatchEvent(new Event('input', { bubbles: true }));
    }).catch(function () {
      selecting = false;
      if (modalResults) {
        modalResults.insertAdjacentHTML('afterbegin',
          '<div class="ct-picker-toast" role="alert">خطا در ارتباط — اتصال را بررسی کنید.</div>');
      }
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
    if (card.dataset.ctPickerBound === '1') return;
    card.dataset.ctPickerBound = '1';
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

  if (typeof window.initCRMFieldVoice === 'function') {
    window.initCRMFieldVoice(modal);
  }

  window.ctWizardPickers = {
    bindPartyContactLink: bindPartyContactLink,
    partyContactLinkHtml: function (idx, customerId) {
      return (
        '<div class="ct-party-contact-link" data-ct-party-contact-link>' +
        '<button type="button" class="ct-party-contact-link__pick" data-ct-party-pick>' +
        '<i class="fas fa-address-book" aria-hidden="true"></i>' +
        '<span>انتخاب از مخاطبین</span>' +
        '<em>یا اطلاعات را دستی وارد کنید</em></button>' +
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
