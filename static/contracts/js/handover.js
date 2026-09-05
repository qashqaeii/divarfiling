(function () {
  'use strict';

  var form = document.getElementById('ct-handover-form');
  if (!form) return;

  var wizard = form.closest('.ct-handover-wizard');
  var nextBtn = document.getElementById('ct-wizard-next');

  form.addEventListener('submit', function () {
    var btn = form.querySelector('.ct-review-send-btn:not([disabled]), #ct-wizard-next');
    if (btn) {
      btn.classList.add('is-loading');
      if (btn.tagName === 'BUTTON') btn.disabled = true;
    }
  });

  function bindSteppers(root) {
    (root || document).querySelectorAll('[data-stepper]').forEach(function (wrap) {
      if (wrap.getAttribute('data-bound')) return;
      wrap.setAttribute('data-bound', '1');
      var input = wrap.querySelector('.ho-stepper__input');
      if (!input) return;
      wrap.querySelector('[data-stepper-dec]')?.addEventListener('click', function () {
        input.value = Math.max(0, (parseInt(input.value, 10) || 0) - 1);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
      wrap.querySelector('[data-stepper-inc]')?.addEventListener('click', function () {
        input.value = Math.min(99, (parseInt(input.value, 10) || 0) + 1);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });
  }
  bindSteppers(form);

  function nextIndex(prefix) {
    var max = -1;
    form.querySelectorAll('input[name^="' + prefix + '"], select[name^="' + prefix + '"]').forEach(function (el) {
      var match = el.name.match(new RegExp('^' + prefix + '(\\d+)_'));
      if (match) max = Math.max(max, parseInt(match[1], 10));
    });
    return max + 1;
  }

  var keyList = document.getElementById('ho-key-list');
  var addKeyBtn = document.getElementById('ho-add-key');
  var keyTpl = document.getElementById('ho-key-row-tpl');
  if (addKeyBtn && keyList && keyTpl) {
    addKeyBtn.addEventListener('click', function () {
      var nameInput = document.getElementById('ho-custom-key-name');
      var name = (nameInput && nameInput.value || '').trim();
      if (!name) {
        if (nameInput) nameInput.focus();
        return;
      }
      var idx = nextIndex('key_');
      var html = keyTpl.innerHTML.replace(/__IDX__/g, String(idx));
      keyList.insertAdjacentHTML('beforeend', html);
      var row = keyList.lastElementChild;
      var typeInput = row.querySelector('[name$="_type"]');
      if (typeInput) typeInput.value = name;
      bindSteppers(row);
      if (nameInput) nameInput.value = '';
      typeInput && typeInput.focus();
    });
  }

  var delivered = form.querySelectorAll('input[name="delivered_by_idx"]');
  var received = form.querySelectorAll('input[name="received_by_idx"]');
  var warn = document.getElementById('ho-same-party-warn');
  function syncPartyWarn() {
    if (!warn || !delivered.length) return;
    var d = form.querySelector('input[name="delivered_by_idx"]:checked');
    var r = form.querySelector('input[name="received_by_idx"]:checked');
    warn.hidden = !(d && r && d.value === r.value);
  }
  delivered.forEach(function (el) { el.addEventListener('change', syncPartyWarn); });
  received.forEach(function (el) { el.addEventListener('change', syncPartyWarn); });
  syncPartyWarn();

  function selectedCount(status) {
    return form.querySelectorAll('#ho-condition-list input[type="radio"][value="' + status + '"]:checked').length;
  }
  function updateConditionStat() {
    var stat = document.getElementById('ho-condition-stat');
    if (!stat) return;
    var total = form.querySelectorAll('#ho-condition-list [data-condition-card]').length;
    var ok = selectedCount('ok');
    var pending = selectedCount('unchecked');
    stat.textContent = ok + ' سالم از ' + total + (pending ? ' — ' + pending + ' بررسی‌نشده' : '');
  }
  function setAllConditions(status) {
    form.querySelectorAll('#ho-condition-list [data-condition-card]').forEach(function (card) {
      var input = card.querySelector('input[value="' + status + '"]');
      if (input) input.checked = true;
      card.setAttribute('data-status', status);
    });
    updateConditionStat();
  }
  var markAll = document.getElementById('ho-mark-all-ok');
  var resetAll = document.getElementById('ho-reset-conditions');
  if (markAll) markAll.addEventListener('click', function () { setAllConditions('ok'); });
  if (resetAll) resetAll.addEventListener('click', function () { setAllConditions('unchecked'); });
  form.addEventListener('change', function (e) {
    if (e.target.matches('#ho-condition-list input[type="radio"]')) {
      var card = e.target.closest('[data-condition-card]');
      if (card) card.setAttribute('data-status', e.target.value);
      updateConditionStat();
    }
  });
  updateConditionStat();

  var preview = document.getElementById('ho-photo-preview');
  form.querySelectorAll('input[type="file"][name="photos"]').forEach(function (input) {
    input.addEventListener('change', function () {
      if (!preview) return;
      preview.innerHTML = '';
      var files = Array.from(input.files || []);
      if (!files.length) {
        preview.hidden = true;
        return;
      }
      preview.hidden = false;
      files.forEach(function (file) {
        if (!file.type.startsWith('image/')) return;
        var img = document.createElement('img');
        img.alt = file.name;
        img.src = URL.createObjectURL(file);
        preview.appendChild(img);
      });
    });
  });

  var eqList = document.getElementById('ho-eq-list');
  var eqTpl = document.getElementById('ho-eq-row-tpl');
  function addEquipment(name) {
    if (!eqList || !eqTpl) return null;
    var empty = Array.from(eqList.querySelectorAll('[data-eq-row]')).find(function (row) {
      var input = row.querySelector('[name$="_name"]');
      return input && !input.value.trim();
    });
    if (empty && name) {
      var emptyName = empty.querySelector('[name$="_name"]');
      emptyName.value = name;
      emptyName.focus();
      return empty;
    }
    var idx = nextIndex('eq_');
    eqList.insertAdjacentHTML('beforeend', eqTpl.innerHTML.replace(/__IDX__/g, String(idx)));
    var row = eqList.lastElementChild;
    if (name) {
      var nameInput = row.querySelector('[name$="_name"]');
      if (nameInput) nameInput.value = name;
    }
    var focusEl = row.querySelector('[name$="_name"]');
    if (focusEl) focusEl.focus();
    return row;
  }
  var addEq = document.getElementById('ho-add-eq');
  if (addEq) addEq.addEventListener('click', function () { addEquipment(''); });
  form.querySelectorAll('[data-eq-chip]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      addEquipment(chip.getAttribute('data-eq-chip') || '');
      chip.classList.add('is-used');
    });
  });
  form.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-eq-remove]');
    if (!btn) return;
    var row = btn.closest('[data-eq-row]');
    if (!row) return;
    if (eqList && eqList.querySelectorAll('[data-eq-row]').length === 1) {
      row.querySelectorAll('input').forEach(function (el) {
        if (el.name.endsWith('_count')) el.value = '1';
        else el.value = '';
      });
      return;
    }
    row.remove();
  });

  var ack = document.getElementById('ho-creator-ack');
  var hint = document.getElementById('ho-review-ack-hint');
  var sendBtns = form.querySelectorAll('.ct-review-send-btn');
  function syncAck() {
    if (!ack || !sendBtns.length) return;
    sendBtns.forEach(function (btn) {
      if (btn.getAttribute('data-locked') === '1') return;
      btn.disabled = !ack.checked;
    });
    if (hint) hint.hidden = ack.checked;
  }
  sendBtns.forEach(function (btn) {
    if (btn.disabled) btn.setAttribute('data-locked', '1');
  });
  if (ack) {
    ack.addEventListener('change', syncAck);
    syncAck();
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      nextBtn.classList.add('is-loading');
    });
  }
})();
