(function () {
  'use strict';

  var form = document.getElementById('ct-wizard-form');
  if (!form) return;

  var wizard = form.closest('.ct-wizard');
  var contractType = wizard ? wizard.getAttribute('data-contract-type') : '';
  var currentStep = wizard ? wizard.getAttribute('data-current-step') : '';
  var isSubmitting = false;

  var ROLE_LABELS = {
    landlord: 'موجر', tenant: 'مستأجر', seller: 'فروشنده',
    buyer: 'خریدار', owner: 'مالک', builder: 'سازنده',
  };

  var REQUIRED_ROLES = {
    lease: { landlord: 'حداقل یک موجر باید در قرارداد وجود داشته باشد.', tenant: 'حداقل یک مستأجر باید در قرارداد وجود داشته باشد.' },
    sale: { seller: 'حداقل یک فروشنده باید در قرارداد وجود داشته باشد.', buyer: 'حداقل یک خریدار باید در قرارداد وجود داشته باشد.' },
    jv: { owner: 'حداقل یک مالک باید در قرارداد وجود داشته باشد.', builder: 'حداقل یک سازنده باید در قرارداد وجود داشته باشد.' },
  };

  /* ——— Toast ——— */
  var toastEl = document.createElement('div');
  toastEl.className = 'ct-toast';
  toastEl.setAttribute('role', 'status');
  document.body.appendChild(toastEl);
  var toastTimer;
  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('is-visible'); }, 4000);
  }

  /* ——— Save flash ——— */
  var flashEl = document.createElement('div');
  flashEl.className = 'ct-save-flash';
  flashEl.textContent = 'تغییرات ذخیره شد';
  document.body.appendChild(flashEl);
  function showSaveFlash() {
    flashEl.classList.add('is-visible');
    setTimeout(function () { flashEl.classList.remove('is-visible'); }, 2000);
  }

  /* ——— Autosave ——— */
  var timer;
  form.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var fd = new FormData(form);
      fd.append('action', 'autosave');
      fetch(form.action || window.location.href, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      }).then(function (r) {
        if (r.ok) showSaveFlash();
      }).catch(function () {});
    }, 1500);
  });

  function parseAmount(val) {
    return parseInt(String(val || '').replace(/[^\d]/g, ''), 10) || 0;
  }

  function formatAmount(num) {
    if (!num) return '';
    return num.toLocaleString('en-US');
  }

  function tomanWordsChunk(amount) {
    if (!amount || amount <= 0) return '';
    var teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده'];
    var units = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه'];
    var tens = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود'];
    var hundreds = ['', 'یکصد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد'];
    if (amount < 10) return units[amount];
    if (amount < 20) return teens[amount - 10];
    if (amount < 100) {
      var u = amount % 10;
      var t = Math.floor(amount / 10);
      return tens[t] + (u ? ' و ' + units[u] : '');
    }
    var h = Math.floor(amount / 100);
    var r = amount % 100;
    return hundreds[h] + (r ? ' و ' + tomanWordsChunk(r) : '');
  }

  function tomanWords(amount) {
    if (!amount || amount <= 0) return '';
    if (amount < 1000) return tomanWordsChunk(amount) + ' تومان';
    if (amount < 1000000) {
      var th = Math.floor(amount / 1000);
      var rest = amount % 1000;
      var head = tomanWordsChunk(th) + ' هزار';
      if (rest) head += ' و ' + tomanWordsChunk(rest);
      return head + ' تومان';
    }
    var mil = Math.floor(amount / 1000000);
    var rem = amount % 1000000;
    var milPart = tomanWordsChunk(mil) + ' میلیون';
    if (rem) milPart += ' و ' + tomanWords(rem).replace(' تومان', '');
    return milPart + ' تومان';
  }

  function initWizardJalaliPickers(scope) {
    if (typeof initCRMJalaliPickers === 'function') {
      initCRMJalaliPickers(scope || form);
    }
  }

  function bindMoneyInput(input) {
    var wordsEl = input.closest('.crm-contract-money-card, .ct-money-card, label') &&
      input.closest('.crm-contract-money-card, .ct-money-card, label').querySelector('.ct-money-words');
    function update() {
      var num = parseAmount(input.value);
      if (num) input.value = formatAmount(num);
      if (wordsEl) wordsEl.textContent = num ? tomanWords(num) : '';
      updatePaymentSummary();
    }
    input.addEventListener('input', update);
    input.addEventListener('blur', update);
    if (input.value) update();
  }

  form.querySelectorAll('.ct-money-input').forEach(bindMoneyInput);

  /* ——— Party cards ——— */
  var partyContainer = document.getElementById('ct-party-rows');
  var partyIndex = partyContainer ? partyContainer.querySelectorAll('.ct-party-card').length : 0;

  function roleLabel(role) {
    return ROLE_LABELS[role] || role || 'طرف';
  }

  function formatPhoneDisplay(phone) {
    return (phone || '').trim();
  }

  function maskPhone(phone) {
    phone = (phone || '').trim();
    if (phone.length < 6) return phone || '';
    return phone.slice(0, 4) + '***' + phone.slice(-4);
  }

  function maskNationalId(nid) {
    nid = (nid || '').trim();
    if (nid.length < 7) return '';
    return nid.slice(0, 4) + '***' + nid.slice(-3);
  }

  function isPartyIncomplete(card) {
    var fn = card.querySelector('[name$="_first_name"]');
    var ln = card.querySelector('[name$="_last_name"]');
    return !((fn && fn.value.trim()) || (ln && ln.value.trim()));
  }

  function updatePartySummary(card) {
    var role = card.querySelector('[name$="_role"]');
    var fn = card.querySelector('[name$="_first_name"]');
    var ln = card.querySelector('[name$="_last_name"]');
    var mob = card.querySelector('[name$="_mobile"]');
    var nid = card.querySelector('[name$="_national_id"]');
    var share = card.querySelector('[name$="_ownership_share"]');
    var roleEl = card.querySelector('.ct-party-card__role');
    var nameEl = card.querySelector('.ct-party-card__name');
    var metaEl = card.querySelector('.ct-party-card__meta');
    var badgeEl = card.querySelector('.ct-party-card__badge');
    var actionsEl = card.querySelector('.ct-party-card__actions');
    var incomplete = isPartyIncomplete(card);

    card.classList.toggle('is-incomplete', incomplete);

    if (roleEl && role) roleEl.textContent = roleLabel(role.value);
    if (nameEl) {
      nameEl.textContent = incomplete
        ? 'نام وارد نشده'
        : ((fn ? fn.value : '') + ' ' + (ln ? ln.value : '')).trim();
    }
    if (metaEl) {
      if (incomplete) {
        metaEl.textContent = 'نام و اطلاعات این طرف قرارداد هنوز تکمیل نشده است.';
      } else {
        var parts = [];
        if (mob && mob.value) parts.push(formatPhoneDisplay(mob.value));
        if (nid && nid.value) parts.push(maskNationalId(nid.value));
        if (share && share.value) parts.push(share.value);
        metaEl.textContent = parts.join(' · ') || '';
      }
    }
    if (badgeEl) badgeEl.style.display = incomplete ? '' : 'none';

    if (actionsEl && !card.classList.contains('is-editing')) {
      var editBtn = actionsEl.querySelector('.ct-party-card__edit');
      var completeBtn = actionsEl.querySelector('.ct-party-card__complete');
      if (incomplete) {
        if (editBtn) editBtn.style.display = 'none';
        if (!completeBtn) {
          completeBtn = document.createElement('button');
          completeBtn.type = 'button';
          completeBtn.className = 'crm-dash-act ct-party-card__complete';
          completeBtn.textContent = 'تکمیل';
          actionsEl.insertBefore(completeBtn, actionsEl.firstChild);
          completeBtn.addEventListener('click', function () {
            card.classList.add('is-editing');
            syncPartyGrid();
          });
        } else {
          completeBtn.style.display = '';
        }
      } else {
        if (completeBtn) completeBtn.style.display = 'none';
        if (!editBtn) {
          editBtn = document.createElement('button');
          editBtn.type = 'button';
          editBtn.className = 'crm-dash-act ct-party-card__edit';
          editBtn.textContent = 'ویرایش';
          actionsEl.insertBefore(editBtn, actionsEl.firstChild);
          editBtn.addEventListener('click', function () {
            card.classList.toggle('is-editing');
            editBtn.textContent = card.classList.contains('is-editing') ? 'بستن' : 'ویرایش';
            syncPartyGrid();
          });
        } else {
          editBtn.style.display = '';
        }
      }
    }
  }

  function syncPartyGrid() {
    if (!partyContainer) return;
    var editing = partyContainer.querySelector('.ct-party-card.is-editing');
    partyContainer.classList.toggle('has-editing', !!editing);
  }

  function initPartyMenu(wrap) {
    if (!wrap || wrap.dataset.menuBound) return;
    wrap.dataset.menuBound = '1';
    var btn = wrap.querySelector('.crm-dash-act--icon, .ct-menu-btn');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      document.querySelectorAll('.ct-party-menu.is-open').forEach(function (w) {
        if (w !== wrap) w.classList.remove('is-open', 'is-drop-up');
      });
      var willOpen = !wrap.classList.contains('is-open');
      wrap.classList.toggle('is-open');
      if (willOpen) {
        var panel = wrap.querySelector('.ct-menu-panel');
        wrap.classList.remove('is-drop-up');
        if (panel) {
          var rect = panel.getBoundingClientRect();
          if (rect.bottom > window.innerHeight - 8) {
            wrap.classList.add('is-drop-up');
          }
        }
      }
    });
  }

  document.addEventListener('click', function () {
    document.querySelectorAll('.ct-party-menu.is-open').forEach(function (w) {
      w.classList.remove('is-open', 'is-drop-up');
    });
  });

  function reindexParties() {
    if (!partyContainer) return;
    partyContainer.querySelectorAll('.ct-party-card').forEach(function (card, idx) {
      card.setAttribute('data-index', idx);
      card.querySelectorAll('[name^="party_"]').forEach(function (el) {
        el.name = el.name.replace(/party_\d+_/, 'party_' + idx + '_');
      });
    });
    partyIndex = partyContainer.querySelectorAll('.ct-party-card').length;
  }

  function getPartyRoles() {
    var roles = [];
    if (!partyContainer) return roles;
    partyContainer.querySelectorAll('[name$="_role"]').forEach(function (el) {
      if (el.value) roles.push(el.value);
    });
    return roles;
  }

  function validateRequiredRoles() {
    var required = REQUIRED_ROLES[contractType];
    if (!required || currentStep !== 'parties') return true;
    var roles = getPartyRoles();
    var missing = [];
    Object.keys(required).forEach(function (role) {
      if (roles.indexOf(role) === -1) missing.push(required[role]);
    });
    if (missing.length) {
      showToast(missing[0]);
      return false;
    }
    return true;
  }

  /* Delete confirmation overlay */
  var deleteOverlay = document.createElement('div');
  deleteOverlay.className = 'ct-confirm-overlay';
  deleteOverlay.innerHTML = '<div class="ct-confirm-sheet" role="dialog" aria-labelledby="ct-delete-title">' +
    '<h3 id="ct-delete-title">حذف طرف قرارداد</h3>' +
    '<p id="ct-delete-msg"></p>' +
    '<div class="ct-confirm-actions">' +
    '<button type="button" class="is-destructive" id="ct-delete-confirm">حذف از قرارداد</button>' +
    '<button type="button" class="is-secondary" id="ct-delete-cancel">انصراف</button></div></div>';
  document.body.appendChild(deleteOverlay);
  var pendingDeleteCard = null;

  deleteOverlay.querySelector('#ct-delete-cancel').addEventListener('click', function () {
    deleteOverlay.classList.remove('is-visible');
    pendingDeleteCard = null;
  });
  deleteOverlay.querySelector('#ct-delete-confirm').addEventListener('click', function () {
    if (pendingDeleteCard) {
      pendingDeleteCard.remove();
      reindexParties();
      syncPartyGrid();
      form.dispatchEvent(new Event('input', { bubbles: true }));
    }
    deleteOverlay.classList.remove('is-visible');
    pendingDeleteCard = null;
  });
  deleteOverlay.addEventListener('click', function (e) {
    if (e.target === deleteOverlay) {
      deleteOverlay.classList.remove('is-visible');
      pendingDeleteCard = null;
    }
  });

  function confirmDeleteParty(card) {
    var fn = card.querySelector('[name$="_first_name"]');
    var ln = card.querySelector('[name$="_last_name"]');
    var name = ((fn ? fn.value : '') + ' ' + (ln ? ln.value : '')).trim() || 'این طرف';
    deleteOverlay.querySelector('#ct-delete-msg').textContent =
      name + ' از این قرارداد حذف شود؟ اطلاعات مخاطب در CRM حذف نخواهد شد.';
    pendingDeleteCard = card;
    deleteOverlay.classList.add('is-visible');
  }

  function bindPartyCard(card) {
    var editBtn = card.querySelector('.ct-party-card__edit');
    var completeBtn = card.querySelector('.ct-party-card__complete');
    var deleteBtn = card.querySelector('.ct-party-card__delete');
    var menuWrap = card.querySelector('.ct-party-menu');
    initPartyMenu(menuWrap);

    function toggleEdit() {
      card.classList.toggle('is-editing');
      if (editBtn) editBtn.textContent = card.classList.contains('is-editing') ? 'بستن' : 'ویرایش';
      syncPartyGrid();
    }

    if (editBtn) editBtn.addEventListener('click', toggleEdit);
    if (completeBtn) completeBtn.addEventListener('click', function () {
      card.classList.add('is-editing');
      syncPartyGrid();
    });
    if (deleteBtn) {
      deleteBtn.addEventListener('click', function () { confirmDeleteParty(card); });
    }

    card.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('input', function () { updatePartySummary(card); });
      el.addEventListener('change', function () { updatePartySummary(card); });
    });
    updatePartySummary(card);
  }

  if (partyContainer) {
    partyContainer.querySelectorAll('.ct-party-card').forEach(bindPartyCard);
    syncPartyGrid();
  }

  function buildPartyCardHtml(idx, defaultRole) {
    var roleOptions = Object.keys(ROLE_LABELS).map(function (k) {
      return '<option value="' + k + '"' + (k === defaultRole ? ' selected' : '') + '>' + ROLE_LABELS[k] + '</option>';
    }).join('');

    return '<article class="crm-deal-side-card crm-deal-block crm-contract-party ct-party-card is-editing is-incomplete" data-index="' + idx + '">' +
      '<div class="crm-contract-party__row ct-party-card__summary">' +
      '<div class="crm-contract-party__body ct-party-card__info">' +
      '<span class="crm-deal-stage-badge ct-party-card__role">' + roleLabel(defaultRole) + '</span>' +
      '<span class="crm-contract-party__warn ct-party-card__badge"><i class="fas fa-exclamation-circle"></i> اطلاعات ناقص</span>' +
      '<p class="crm-contract-party__name ct-party-card__name">نام وارد نشده</p>' +
      '<p class="crm-contract-party__meta ct-party-card__meta">نام و اطلاعات این طرف هنوز تکمیل نشده است.</p></div>' +
      '<div class="crm-contract-party__acts ct-party-card__actions">' +
      '<button type="button" class="crm-dash-act ct-party-card__complete">تکمیل</button>' +
      '<div class="ct-menu-wrap ct-party-menu">' +
      '<button type="button" class="crm-dash-act crm-dash-act--icon" aria-label="عملیات"><i class="fas fa-ellipsis-v"></i></button>' +
      '<div class="ct-menu-panel"><button type="button" class="ct-party-card__delete is-destructive">حذف از قرارداد</button></div></div></div></div>' +
      '<div class="ct-party-card__body"><div class="crm-contract-form-grid">' +
      '<label>نقش<select class="crm-input" name="party_' + idx + '_role">' + roleOptions + '</select></label>' +
      '<label>نوع<select class="crm-input" name="party_' + idx + '_person_type"><option value="natural">حقیقی</option><option value="legal">حقوقی</option></select></label>' +
      '<label>نام<input class="crm-input" name="party_' + idx + '_first_name"></label>' +
      '<label>نام خانوادگی<input class="crm-input" name="party_' + idx + '_last_name"></label>' +
      '<label>نام پدر<input class="crm-input" name="party_' + idx + '_father_name"></label>' +
      '<label>کد ملی<input class="crm-input" name="party_' + idx + '_national_id" inputmode="numeric"></label>' +
      '<label>موبایل<input class="crm-input" type="tel" name="party_' + idx + '_mobile" inputmode="tel"></label>' +
      '<label>قدرالسهم<input class="crm-input" name="party_' + idx + '_ownership_share" placeholder="۶ دانگ"></label>' +
      '<label class="crm-contract-span-2">نشانی<input class="crm-input" name="party_' + idx + '_address"></label>' +
      '<label>کد پستی<input class="crm-input" name="party_' + idx + '_postal_code" inputmode="numeric"></label>' +
      '</div></div></article>';
  }

  var addPartyGroup = document.getElementById('ct-add-party-group');
  if (addPartyGroup && partyContainer) {
    addPartyGroup.querySelectorAll('[data-add-role]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var role = btn.getAttribute('data-add-role') ||
          (contractType === 'lease' ? 'tenant' : contractType === 'sale' ? 'buyer' : 'builder');
        var idx = partyIndex++;
        partyContainer.insertAdjacentHTML('beforeend', buildPartyCardHtml(idx, role));
        bindPartyCard(partyContainer.lastElementChild);
        syncPartyGrid();
      });
    });
  }

  /* ——— Form submit guard ——— */
  form.addEventListener('submit', function (e) {
    if (isSubmitting) {
      e.preventDefault();
      return;
    }
    if (currentStep === 'parties' && !validateRequiredRoles()) {
      e.preventDefault();
      return;
    }
    var submitBtn = e.submitter || form.querySelector('#ct-wizard-next');
    if (submitBtn && submitBtn.type === 'submit' && submitBtn.name !== 'action') {
      isSubmitting = true;
      submitBtn.classList.add('is-loading');
      submitBtn.disabled = true;
      var orig = submitBtn.textContent;
      submitBtn.textContent = 'در حال ذخیره…';
      setTimeout(function () {
        isSubmitting = false;
        submitBtn.classList.remove('is-loading');
        submitBtn.disabled = false;
        submitBtn.textContent = orig;
      }, 8000);
    }
  });

  /* ——— Deposit mode ——— */
  var depositModeRadios = form.querySelectorAll('input[name="fin_deposit_mode"]');
  var prevDepositBlock = document.getElementById('ct-prev-deposit-block');
  function updateDepositMode() {
    if (!prevDepositBlock) return;
    var mode = form.querySelector('input[name="fin_deposit_mode"]:checked');
    prevDepositBlock.style.display = mode && mode.value === 'retained' ? 'block' : 'none';
  }
  depositModeRadios.forEach(function (r) { r.addEventListener('change', updateDepositMode); });
  updateDepositMode();

  /* ——— Penalty toggles ——— */
  form.querySelectorAll('.ct-penalty-block').forEach(function (block) {
    var toggle = block.querySelector('.ct-penalty-toggle');
    if (!toggle) return;
    function sync() {
      block.classList.toggle('is-disabled', !toggle.checked);
      block.querySelectorAll('input:not(.ct-penalty-toggle)').forEach(function (inp) {
        inp.disabled = !toggle.checked;
      });
    }
    toggle.addEventListener('change', sync);
    sync();
  });

  /* ——— Clause expand ——— */
  form.querySelectorAll('.ct-clause-item').forEach(function (item) {
    var cb = item.querySelector('input[type=checkbox]');
    var expandBtn = item.querySelector('.ct-clause-expand');
    function syncActive() {
      item.classList.toggle('is-active', cb && cb.checked);
    }
    if (cb) {
      cb.addEventListener('change', syncActive);
      syncActive();
    }
    if (expandBtn) {
      expandBtn.addEventListener('click', function (e) {
        e.preventDefault();
        item.classList.toggle('is-expanded');
        expandBtn.textContent = item.classList.contains('is-expanded') ? 'بستن متن' : 'مشاهده متن';
      });
    }
  });

  /* ——— Payments ——— */
  var paymentsContainer = document.getElementById('ct-payments');
  var paymentIndex = paymentsContainer ? paymentsContainer.querySelectorAll('.ct-payment-card').length : 0;

  function updatePaymentSummary() {
    var totalEl = document.getElementById('ct-pay-total');
    var sumEl = document.getElementById('ct-pay-sum');
    var remainEl = document.getElementById('ct-pay-remain');
    if (!totalEl) return;
    var total = parseAmount(document.querySelector('[name="fin_total_price"]') &&
      document.querySelector('[name="fin_total_price"]').value);
    var sum = 0;
    if (paymentsContainer) {
      paymentsContainer.querySelectorAll('[name$="_amount"]').forEach(function (inp) {
        sum += parseAmount(inp.value);
      });
    }
    var earnest = parseAmount(document.querySelector('[name="fin_earnest_money"]') &&
      document.querySelector('[name="fin_earnest_money"]').value);
    sum += earnest;
    totalEl.textContent = total ? formatAmount(total) : '—';
    sumEl.textContent = sum ? formatAmount(sum) : '—';
    var remain = total - sum;
    remainEl.textContent = total ? formatAmount(Math.max(0, remain)) : '—';
    if (remainEl.parentElement) {
      remainEl.parentElement.classList.toggle('is-warning', total > 0 && remain !== 0);
    }
  }

  function renderPaymentCards() {
    if (!paymentsContainer) return;
    paymentsContainer.querySelectorAll('.ct-payment-card').forEach(function (card) {
      var editBtn = card.querySelector('[data-action="edit"]');
      var delBtn = card.querySelector('[data-action="delete"]');
      if (editBtn) {
        editBtn.addEventListener('click', function () {
          card.querySelector('.ct-payment-card__form').style.display = 'block';
          card.querySelector('.ct-payment-card__view').style.display = 'none';
        });
      }
      if (delBtn) {
        delBtn.addEventListener('click', function () {
          card.remove();
          updatePaymentSummary();
        });
      }
      card.querySelectorAll('.ct-money-input').forEach(bindMoneyInput);
      card.querySelectorAll('input').forEach(function (inp) {
        inp.addEventListener('input', function () {
          var label = card.querySelector('[name$="_label"]');
          var amount = card.querySelector('[name$="_amount"]');
          var date = card.querySelector('[name$="_due_date"]');
          card.querySelector('.ct-payment-card__label').textContent = label ? label.value : '';
          card.querySelector('.ct-payment-card__amount').textContent =
            amount && amount.value ? amount.value + ' تومان' : '';
          card.querySelector('.ct-payment-card__date').textContent = date ? date.value : '';
          updatePaymentSummary();
        });
      });
    });
    updatePaymentSummary();
  }

  renderPaymentCards();

  var addPaymentBtn = document.getElementById('ct-add-payment');
  if (addPaymentBtn && paymentsContainer) {
    addPaymentBtn.addEventListener('click', function () {
      var idx = paymentIndex++;
      var html = '<div class="ct-payment-card" data-index="' + idx + '">' +
        '<div class="ct-payment-card__view">' +
        '<div class="ct-payment-card__info">' +
        '<div class="ct-payment-card__label">پرداخت</div>' +
        '<div class="ct-payment-card__amount">—</div>' +
        '<div class="ct-payment-card__date"></div></div>' +
        '<div class="ct-payment-card__actions">' +
        '<button type="button" data-action="edit">ویرایش</button>' +
        '<button type="button" data-action="delete">حذف</button></div></div>' +
        '<div class="ct-payment-card__form crm-contract-form-grid" style="display:block;margin-top:.65rem">' +
        '<label>عنوان<input class="crm-input" name="pay_' + idx + '_label" value="پرداخت ' + (idx + 1) + '"></label>' +
        '<label>مبلغ (تومان)<input class="crm-input ct-money-input" name="pay_' + idx + '_amount" inputmode="numeric"></label>' +
        '<label>تاریخ<input class="crm-input crm-jalali-date" name="pay_' + idx + '_due_date" data-jdp data-jdp-only-date placeholder="۱۴۰۵/۰۷/۱۰" autocomplete="off"></label>' +
        '</div></div>';
      paymentsContainer.insertAdjacentHTML('beforeend', html);
      renderPaymentCards();
      initWizardJalaliPickers(paymentsContainer.lastElementChild);
    });
  }

  initWizardJalaliPickers(form);

  /* ——— Send confirmation ——— */
  var sendBtn = form.querySelector('[name="action"][value="prepare_send"]');
  if (sendBtn) {
    var overlay = document.createElement('div');
    overlay.className = 'ct-confirm-overlay';
    overlay.innerHTML = '<div class="ct-confirm-sheet" role="dialog">' +
      '<h3>ارسال برای تأیید طرفین</h3>' +
      '<p>قرارداد برای طرفین پیامک می‌شود. آن‌ها با موبایل و کد ملی خود تأیید می‌کنند.</p>' +
      '<div class="ct-confirm-actions">' +
      '<button type="button" class="is-primary" id="ct-confirm-send">ارسال برای تأیید طرفین</button>' +
      '<button type="button" class="is-secondary" id="ct-confirm-cancel">انصراف</button></div></div>';
    document.body.appendChild(overlay);

    sendBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (!form.querySelector('[name="creator_ack"]') ||
          !form.querySelector('[name="creator_ack"]').checked) {
        form.reportValidity();
        return;
      }
      overlay.classList.add('is-visible');
    });

    overlay.querySelector('#ct-confirm-cancel').addEventListener('click', function () {
      overlay.classList.remove('is-visible');
    });
    overlay.querySelector('#ct-confirm-send').addEventListener('click', function () {
      if (isSubmitting) return;
      isSubmitting = true;
      overlay.classList.remove('is-visible');
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'action';
      hidden.value = 'prepare_send';
      form.appendChild(hidden);
      form.submit();
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.classList.remove('is-visible');
    });
  }

  /* ——— End ——— */
})();
