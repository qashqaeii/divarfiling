/**
 * Agency Hub UI — frontend polish only (no backend logic)
 */
(function () {
  'use strict';

  var IR_MOBILE = /^09\d{9}$/;

  function normalizePhone(raw) {
    var p = (raw || '').trim().replace(/[\s\-()]/g, '');
    if (p.indexOf('+98') === 0) p = '0' + p.slice(3);
    if (p.indexOf('98') === 0 && p.length === 12) p = '0' + p.slice(2);
    return p;
  }

  function parsePhones(text) {
    return (text || '')
      .split(/[\n,;]+/)
      .map(normalizePhone)
      .filter(Boolean);
  }

  function initInvitePhonePreview() {
    var textarea = document.getElementById('invitePhones');
    var preview = document.getElementById('agencyPhonePreview');
    var list = document.getElementById('agencyPhoneList');
    var countEl = document.getElementById('agencyPhoneCount');
    var errorsEl = document.getElementById('agencyPhoneErrors');
    var submitBtn = document.getElementById('agencyInviteSubmit');
    if (!textarea || !preview || !list) return;

    function render() {
      var phones = parsePhones(textarea.value);
      var unique = [];
      var seen = {};
      var invalid = [];

      phones.forEach(function (p) {
        if (seen[p]) return;
        seen[p] = true;
        if (IR_MOBILE.test(p)) unique.push(p);
        else invalid.push(p);
      });

      list.innerHTML = '';
      unique.forEach(function (p) {
        var li = document.createElement('li');
        li.className = 'agency-phone-chip agency-phone-chip--ok';
        li.textContent = p;
        list.appendChild(li);
      });
      invalid.forEach(function (p) {
        var li = document.createElement('li');
        li.className = 'agency-phone-chip agency-phone-chip--bad';
        li.textContent = p;
        li.title = 'فرمت نامعتبر — باید ۱۱ رقم و با ۰۹ شروع شود';
        list.appendChild(li);
      });

      var total = unique.length + invalid.length;
      preview.hidden = total === 0;
      if (countEl) countEl.textContent = String(unique.length);

      if (errorsEl) {
        if (invalid.length) {
          errorsEl.hidden = false;
          errorsEl.textContent = invalid.length + ' شماره نامعتبر — قبل از ارسال اصلاح کنید.';
        } else {
          errorsEl.hidden = true;
          errorsEl.textContent = '';
        }
      }

      if (submitBtn) {
        submitBtn.disabled = total > 0 && unique.length === 0;
      }
    }

    textarea.addEventListener('input', render);
    textarea.addEventListener('blur', render);
    render();
  }

  function initModalInvitePreview() {
    var input = document.getElementById('agencyInvitePhone');
    var hint = document.getElementById('agencyModalPhoneHint');
    if (!input) return;

    function check() {
      var p = normalizePhone(input.value);
      if (!p) {
        if (hint) { hint.hidden = true; hint.textContent = ''; }
        return;
      }
      if (hint) {
        hint.hidden = false;
        hint.className = 'agency-form-helper' + (IR_MOBILE.test(p) ? ' agency-form-helper--ok' : ' agency-form-helper--bad');
        hint.textContent = IR_MOBILE.test(p) ? 'شماره معتبر است' : 'شماره باید ۱۱ رقم و با ۰۹ شروع شود';
      }
    }

    input.addEventListener('input', check);
    input.addEventListener('blur', check);
  }

  function initStickyStepFooter() {
    var footer = document.querySelector('.agency-step-footer--sticky');
    if (!footer || window.matchMedia('(min-width: 769px)').matches) return;
    document.body.classList.add('agency-has-sticky-footer');
  }

  function initNavScrollHint() {
    document.querySelectorAll('.agency-hub-nav__track, .a360-tabs').forEach(function (track) {
      function update() {
        var atEnd = track.scrollWidth - track.clientWidth - track.scrollLeft < 8;
        var atStart = track.scrollLeft < 8;
        track.classList.toggle('is-scroll-end', atEnd);
        track.classList.toggle('is-scroll-start', atStart);
      }
      track.addEventListener('scroll', update, { passive: true });
      update();
    });
  }

  function initMemberFilters() {
    var search = document.getElementById('agencyMemberSearch');
    var statusF = document.getElementById('agencyMemberStatusFilter');
    var licenseF = document.getElementById('agencyMemberLicenseFilter');
    var clearBtn = document.getElementById('agencyMemberFilterClear');
    var empty = document.getElementById('agencyMembersFilterEmpty');
    if (!search) return;

    // Prevent browser autofill from polluting initial search state
    search.value = '';
    search.setAttribute('autocomplete', 'off');

    function hasActiveFilters() {
      return !!(search.value.trim() || (statusF && statusF.value) || (licenseF && licenseF.value));
    }

    function updateClearBtn() {
      if (clearBtn) clearBtn.hidden = !hasActiveFilters();
    }

    function checkEmpty() {
      var rows = document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]');
      var visible = 0;
      rows.forEach(function (el) {
        if (el.style.display !== 'none') visible++;
      });
      if (empty) empty.hidden = visible > 0 || !hasActiveFilters();
    }

    function filterMembers() {
      var q = (search.value || '').trim().toLowerCase();
      var st = statusF ? statusF.value : '';
      var lic = licenseF ? licenseF.value : '';
      document.querySelectorAll('#agencyMembersTable tbody tr[data-name], .agency-member-card[data-name]').forEach(function (el) {
        var name = el.getAttribute('data-name') || '';
        var phone = el.getAttribute('data-phone') || '';
        var matchQ = !q || name.indexOf(q) !== -1 || phone.indexOf(q) !== -1;
        var matchS = !st || el.getAttribute('data-status') === st;
        var matchL = !lic || el.getAttribute('data-license') === lic;
        el.style.display = matchQ && matchS && matchL ? '' : 'none';
      });
      updateClearBtn();
      checkEmpty();
    }

    function resetFilters() {
      search.value = '';
      if (statusF) statusF.value = '';
      if (licenseF) licenseF.value = '';
      filterMembers();
      search.focus();
    }

    search.addEventListener('input', filterMembers);
    if (statusF) statusF.addEventListener('change', filterMembers);
    if (licenseF) licenseF.addEventListener('change', filterMembers);
    if (clearBtn) clearBtn.addEventListener('click', resetFilters);

    // Delayed clear for stubborn browser autofill
    window.setTimeout(function () {
      if (search.value && !search.dataset.userTyped) search.value = '';
    }, 120);
    search.addEventListener('input', function () {
      search.dataset.userTyped = '1';
    });

    filterMembers();
  }

  document.addEventListener('DOMContentLoaded', function () {
    initInvitePhonePreview();
    initModalInvitePreview();
    initStickyStepFooter();
    initNavScrollHint();
    initMemberFilters();
  });
})();
