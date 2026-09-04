(function () {
  'use strict';

  var form = document.getElementById('ct-wizard-form');
  if (!form) return;

  var wizard = form.closest('.ct-wizard');
  var contractType = wizard ? wizard.getAttribute('data-contract-type') : '';

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
      }).catch(function () {});
    }, 1500);
  });

  /* ——— Money formatting ——— */
  var ROLE_LABELS = {
    landlord: 'موجر', tenant: 'مستأجر', seller: 'فروشنده',
    buyer: 'خریدار', owner: 'مالک', builder: 'سازنده',
  };

  function parseAmount(val) {
    return parseInt(String(val || '').replace(/[^\d]/g, ''), 10) || 0;
  }

  function formatAmount(num) {
    if (!num) return '';
    return num.toLocaleString('en-US');
  }

  function tomanWords(amount) {
    if (!amount || amount <= 0) return '';
    var units = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه'];
    var tens = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود'];
    if (amount < 10) return units[amount] + ' تومان';
    if (amount < 100) {
      var u = amount % 10, t = Math.floor(amount / 10);
      return (tens[t] + (u ? ' و ' + units[u] : '')) + ' تومان';
    }
    if (amount < 1000) {
      var h = Math.floor(amount / 100), r = amount % 100;
      return (units[h] + 'صد' + (r ? ' و ' + tomanWords(r).replace(' تومان', '') : '')) + ' تومان';
    }
    if (amount < 1000000) {
      var th = Math.floor(amount / 1000), rest = amount % 1000;
      return (tomanWords(th).replace(' تومان', '') + ' هزار' + (rest ? ' و ' + tomanWords(rest).replace(' تومان', '') : '')) + ' تومان';
    }
    var mil = Math.floor(amount / 1000000), rem = amount % 1000000;
    return (tomanWords(mil).replace(' تومان', '') + ' میلیون' + (rem ? ' و ' + tomanWords(rem).replace(' تومان', '') : '')) + ' تومان';
  }

  function bindMoneyInput(input) {
    var wordsEl = input.closest('.ct-money-card, label') &&
      input.closest('.ct-money-card, label').querySelector('.ct-money-words');
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

  function maskPhone(phone) {
    phone = (phone || '').trim();
    if (phone.length < 6) return phone || '—';
    return phone.slice(0, 4) + '***' + phone.slice(-4);
  }

  function updatePartySummary(card) {
    var role = card.querySelector('[name$="_role"]');
    var fn = card.querySelector('[name$="_first_name"]');
    var ln = card.querySelector('[name$="_last_name"]');
    var mob = card.querySelector('[name$="_mobile"]');
    var share = card.querySelector('[name$="_ownership_share"]');
    var roleEl = card.querySelector('.ct-party-card__role');
    var nameEl = card.querySelector('.ct-party-card__name');
    var metaEl = card.querySelector('.ct-party-card__meta');
    if (roleEl && role) roleEl.textContent = roleLabel(role.value);
    if (nameEl) nameEl.textContent = ((fn ? fn.value : '') + ' ' + (ln ? ln.value : '')).trim() || 'نام وارد نشده';
    if (metaEl) {
      var parts = [];
      if (mob && mob.value) parts.push(maskPhone(mob.value));
      if (share && share.value) parts.push(share.value);
      metaEl.textContent = parts.join(' · ') || 'اطلاعات تکمیل نشده';
    }
  }

  function bindPartyCard(card) {
    var editBtn = card.querySelector('.ct-party-card__edit');
    if (editBtn) {
      editBtn.addEventListener('click', function () {
        card.classList.toggle('is-editing');
        editBtn.textContent = card.classList.contains('is-editing') ? 'بستن' : 'ویرایش';
      });
    }
    card.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('input', function () { updatePartySummary(card); });
      el.addEventListener('change', function () { updatePartySummary(card); });
    });
    updatePartySummary(card);
  }

  if (partyContainer) {
    partyContainer.querySelectorAll('.ct-party-card').forEach(bindPartyCard);
  }

  var addPartyBtn = document.getElementById('ct-add-party');
  if (addPartyBtn && partyContainer) {
    addPartyBtn.addEventListener('click', function () {
      var idx = partyIndex++;
      var defaultRole = contractType === 'lease' ? 'tenant' : contractType === 'sale' ? 'buyer' : 'builder';
      var html = '<div class="ct-party-card is-editing" data-index="' + idx + '">' +
        '<div class="ct-party-card__summary">' +
        '<div class="ct-party-card__info">' +
        '<div class="ct-party-card__role">' + roleLabel(defaultRole) + '</div>' +
        '<p class="ct-party-card__name">نام وارد نشده</p>' +
        '<p class="ct-party-card__meta">اطلاعات تکمیل نشده</p></div>' +
        '<button type="button" class="ct-party-card__edit">بستن</button></div>' +
        '<div class="ct-party-card__body"><div class="ct-form-grid">' +
        '<label>نقش<select class="crm-input" name="party_' + idx + '_role">' +
        Object.keys(ROLE_LABELS).map(function (k) {
          return '<option value="' + k + '"' + (k === defaultRole ? ' selected' : '') + '>' + ROLE_LABELS[k] + '</option>';
        }).join('') + '</select></label>' +
        '<label>نوع<select class="crm-input" name="party_' + idx + '_person_type"><option value="natural">حقیقی</option><option value="legal">حقوقی</option></select></label>' +
        '<label>نام<input class="crm-input" name="party_' + idx + '_first_name"></label>' +
        '<label>نام خانوادگی<input class="crm-input" name="party_' + idx + '_last_name"></label>' +
        '<label>نام پدر<input class="crm-input" name="party_' + idx + '_father_name"></label>' +
        '<label>کد ملی<input class="crm-input" name="party_' + idx + '_national_id" inputmode="numeric"></label>' +
        '<label>موبایل<input class="crm-input" type="tel" name="party_' + idx + '_mobile" inputmode="tel"></label>' +
        '<label>قدرالسهم<input class="crm-input" name="party_' + idx + '_ownership_share" placeholder="۶ دانگ"></label>' +
        '<label class="ct-span-2">نشانی<input class="crm-input" name="party_' + idx + '_address"></label>' +
        '<label>کد پستی<input class="crm-input" name="party_' + idx + '_postal_code" inputmode="numeric"></label>' +
        '</div></div></div>';
      partyContainer.insertAdjacentHTML('beforeend', html);
      bindPartyCard(partyContainer.lastElementChild);
    });
  }

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
        '<div class="ct-payment-card__form ct-form-grid" style="display:block;margin-top:.75rem">' +
        '<label>عنوان<input class="crm-input" name="pay_' + idx + '_label" value="پرداخت ' + (idx + 1) + '"></label>' +
        '<label>مبلغ (تومان)<input class="crm-input ct-money-input" name="pay_' + idx + '_amount" inputmode="numeric"></label>' +
        '<label>تاریخ<input class="crm-input" name="pay_' + idx + '_due_date" placeholder="1405/07/10"></label>' +
        '</div></div>';
      paymentsContainer.insertAdjacentHTML('beforeend', html);
      renderPaymentCards();
    });
  }

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

  /* ——— Step done markers ——— */
  var currentStep = wizard ? wizard.getAttribute('data-current-step') : '';
  if (currentStep) {
    document.querySelectorAll('.ct-steps-list li').forEach(function (li) {
      var link = li.querySelector('a');
      if (!link) return;
      var href = link.getAttribute('href') || '';
      var step = href.replace('?step=', '');
      if (step && step !== currentStep && li.compareDocumentPosition(
        document.querySelector('.ct-steps-list li.is-active')
      ) & Node.DOCUMENT_POSITION_FOLLOWING) {
        li.classList.add('is-done');
      }
    });
  }
})();
